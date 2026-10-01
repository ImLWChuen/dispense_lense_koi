"""
Unit tests for Synthetic Inspection Robustness Dataset Generator & Summary Utility.

Verifies:
- Deterministic fixture generation (byte-identical images across runs).
- Manifest schema validation and strict label separation (only clean controls labeled).
- Clipped edge coordinate transformation and valid normalized ROIs.
- Collision preflight on generator and summary output paths (including hardlink/symlink aliases).
- Identity validation between manifest and evaluation report (origin, profile, labels, schema version).
- Data-driven summary risk classification separating input/execution failures from demonstrated inspection defects.
- Inconsistent status_match rejection.
- Rejection of malformed reports (removed/duplicate/unknown sites, sites=null, non-object sites,
  non-string image paths, contradictory summary metrics) cleanly via CLI without tracebacks.
- Safe report publication helper reuse and sentinel-created-during-generation race prevention.
- CLI argument handling and end-to-end execution.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    NormalizedROI,
    ProcessLimits,
    RoiInspectionStatus,
)
from tests.fixtures.generate_inspection_robustness import (
    CLIPPED_ROIS,
    DEFAULT_ROIS,
    generate_robustness_dataset,
)
from tests.inspection_robustness_summary import (
    IdentityMismatchError,
    SummarySafetyError,
    classify_case_finding,
    generate_markdown_summary,
    main as summary_main,
    validate_identities,
    verify_summary_output_safe,
)
from tests.vision_inspection_dataset import (
    DatasetManifest,
    DatasetOrigin,
    ManifestCase,
    compute_dataset_metrics,
    evaluate_dataset,
)


def test_robustness_dataset_deterministic_generation(tmp_path: Path) -> None:
    """Verifies that generate_robustness_dataset produces byte-identical files across independent runs."""
    dir_1 = tmp_path / "run_1"
    dir_2 = tmp_path / "run_2"

    mpath_1 = generate_robustness_dataset(dir_1)
    mpath_2 = generate_robustness_dataset(dir_2)

    assert mpath_1.exists()
    assert mpath_2.exists()

    # Compare manifest contents
    assert mpath_1.read_text(encoding="utf-8") == mpath_2.read_text(encoding="utf-8")

    # Compare all image files byte-for-byte
    images_1 = sorted(list((dir_1 / "images").glob("*.png")))
    images_2 = sorted(list((dir_2 / "images").glob("*.png")))

    assert len(images_1) == 14
    assert len(images_2) == 14

    for p1, p2 in zip(images_1, images_2):
        assert p1.name == p2.name
        assert p1.read_bytes() == p2.read_bytes(), f"Image mismatch for {p1.name}"


def test_robustness_manifest_schema_and_integrity(tmp_path: Path) -> None:
    """Verifies generated manifest complies with DatasetManifest schema v1 and has 14 valid cases."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    assert manifest.dataset_id == "synthetic_inspection_robustness_v1"
    assert manifest.origin == DatasetOrigin.SYNTHETIC
    assert manifest.manifest_version == "v1"
    assert len(manifest.cases) == 14

    case_ids = [c.case_id for c in manifest.cases]
    assert len(case_ids) == len(set(case_ids)), "All case IDs must be unique"

    for case in manifest.cases:
        assert case.current_image_path.startswith("images/")
        assert (tmp_path / case.current_image_path).exists()
        assert len(case.profile.rois) >= 2


def test_robustness_label_separation_and_clean_controls(tmp_path: Path) -> None:
    """Verifies that only clean controls have ground truth labels, while degraded cases remain strictly unassigned."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    labeled_cases = [c for c in manifest.cases if c.expected_statuses]
    unlabeled_cases = [c for c in manifest.cases if not c.expected_statuses]

    # Exactly 3 clean controls are labeled
    assert len(labeled_cases) == 3
    labeled_ids = {c.case_id for c in labeled_cases}
    assert labeled_ids == {
        "case_01_control_clean",
        "case_10_missing_control",
        "case_11_uniform_unassessed_control",
    }

    # Clean detected control
    c1 = next(c for c in labeled_cases if c.case_id == "case_01_control_clean")
    assert c1.expected_statuses == {
        "roi_1": RoiInspectionStatus.DETECTED,
        "roi_2": RoiInspectionStatus.DETECTED,
    }

    # Clean missing control
    c10 = next(c for c in labeled_cases if c.case_id == "case_10_missing_control")
    assert c10.expected_statuses == {
        "roi_1": RoiInspectionStatus.MISSING,
        "roi_2": RoiInspectionStatus.MISSING,
    }

    # Clean uniform control
    c11 = next(c for c in labeled_cases if c.case_id == "case_11_uniform_unassessed_control")
    assert c11.expected_statuses == {
        "roi_1": RoiInspectionStatus.UNASSESSED,
        "roi_2": RoiInspectionStatus.UNASSESSED,
    }

    # All 11 remaining perturbation cases must be unlabeled
    assert len(unlabeled_cases) == 11
    for c in unlabeled_cases:
        assert c.expected_statuses is None
        assert "unassigned" in c.notes.lower()


def test_robustness_clipping_roi_mapping(tmp_path: Path) -> None:
    """Verifies that case 09 contains valid transformed normalized ROIs for edge clipping."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    c9 = next(c for c in manifest.cases if c.case_id == "case_09_clipping_edge")
    rois = {r.roi_id: r for r in c9.profile.rois}

    assert "roi_1_clipped" in rois
    assert "roi_2_shifted" in rois

    r1 = rois["roi_1_clipped"]
    assert r1.x == 0.0
    assert r1.width == 0.1875
    assert r1.y == 0.20
    assert r1.height == 0.60
    assert r1.x + r1.width <= 1.0

    r2 = rois["roi_2_shifted"]
    assert r2.x == 0.3875
    assert r2.width == 0.30
    assert r2.y == 0.20
    assert r2.height == 0.60
    assert r2.x + r2.width <= 1.0


def test_robustness_generator_collision_preflight_and_overwrite(tmp_path: Path) -> None:
    """Verifies generator target collision preflight and --overwrite authorization."""
    p1 = generate_robustness_dataset(tmp_path)
    assert p1.exists()

    with pytest.raises(FileExistsError, match="Target file already exists"):
        generate_robustness_dataset(tmp_path, overwrite=False)

    p3 = generate_robustness_dataset(tmp_path, overwrite=True)
    assert p3.exists()


def test_summary_identity_mismatch_validation(tmp_path: Path) -> None:
    """Verifies validate_identities rejects mismatched dataset IDs, versions, origins, profiles, or labels."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    report = evaluate_dataset(manifest, tmp_path)

    # 1. Matching identities succeed
    validate_identities(manifest, report)

    # 2. Report version mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["report_version"] = "v2"
    with pytest.raises(IdentityMismatchError, match="Unsupported report version"):
        validate_identities(manifest, bad_report)

    # 3. Dataset ID mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["dataset_id"] = "different_dataset_id"
    with pytest.raises(IdentityMismatchError, match="Dataset ID mismatch"):
        validate_identities(manifest, bad_report)

    # 4. Origin mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["origin"] = "real"
    with pytest.raises(IdentityMismatchError, match="Dataset origin mismatch"):
        validate_identities(manifest, bad_report)

    # 5. Case count mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["cases"] = bad_report["cases"][:-1]
    with pytest.raises(IdentityMismatchError, match="Case count mismatch"):
        validate_identities(manifest, bad_report)

    # 6. Case ID mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["cases"][0]["case_id"] = "wrong_case_id"
    with pytest.raises(IdentityMismatchError, match="Case ID mismatch at index 0"):
        validate_identities(manifest, bad_report)

    # 7. Profile mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["cases"][0]["profile"]["mode"] = "FEATURES_ONLY"
    with pytest.raises(IdentityMismatchError, match="profile specification mismatch"):
        validate_identities(manifest, bad_report)

    # 8. Label mismatch (labeled control marked unlabeled in report)
    bad_report = json.loads(json.dumps(report))
    bad_report["cases"][0]["sites"][0]["is_labeled"] = False
    with pytest.raises(IdentityMismatchError, match="should be labeled according to manifest"):
        validate_identities(manifest, bad_report)


def test_summary_inconsistent_status_match_rejected(tmp_path: Path) -> None:
    """Verifies that an inconsistent status_match flag (claiming match when predicted != expected) is rejected."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path)

    # Set site predicted_status to MISSING, but leave status_match as True
    bad_report = json.loads(json.dumps(report))
    site = bad_report["cases"][0]["sites"][0]
    site["predicted_status"] = "MISSING"
    site["status_match"] = True

    with pytest.raises(IdentityMismatchError, match="status_match contradicts expected/predicted states"):
        validate_identities(manifest, bad_report)


def test_summary_output_collision_protection(tmp_path: Path) -> None:
    """Verifies summary output path rejects aliases of manifest/report inputs and unconfirmed overwrites."""
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text("{}", encoding="utf-8")
    report_file = tmp_path / "report.json"
    report_file.write_text("{}", encoding="utf-8")

    # Output targeting manifest path directly
    with pytest.raises(SummarySafetyError, match="cannot overwrite manifest input"):
        verify_summary_output_safe(manifest_file, manifest_file, report_file, overwrite=True)

    # Output targeting report path directly
    with pytest.raises(SummarySafetyError, match="cannot overwrite report input"):
        verify_summary_output_safe(report_file, manifest_file, report_file, overwrite=True)

    # Output targeting existing summary without overwrite
    existing_summary = tmp_path / "summary.md"
    existing_summary.write_text("old", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists. Use --overwrite"):
        verify_summary_output_safe(existing_summary, manifest_file, report_file, overwrite=False)

    # Output targeting existing summary with overwrite=True succeeds
    verify_summary_output_safe(existing_summary, manifest_file, report_file, overwrite=True)


def test_summary_output_alias_collision_protection(tmp_path: Path) -> None:
    """Verifies filesystem link/alias collisions to manifest or report are rejected."""
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text("{}", encoding="utf-8")
    report_file = tmp_path / "report.json"
    report_file.write_text("{}", encoding="utf-8")

    alias_summary = tmp_path / "manifest_alias.md"
    try:
        alias_summary.hardlink_to(manifest_file)
        with pytest.raises(SummarySafetyError, match="resolves to manifest input via filesystem alias"):
            verify_summary_output_safe(alias_summary, manifest_file, report_file, overwrite=True)
    except (OSError, NotImplementedError):
        pytest.skip("Hardlinks not supported on host filesystem")


def test_summary_risk_classification_and_accounting(tmp_path: Path) -> None:
    """Verifies classify_case_finding separates input/execution failures from inspection defects."""
    # 1. Clean control matching -> MEASURED_BASELINE
    c_control_match = {
        "case_id": "case_01_control_clean",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {
                "roi_id": "roi_1",
                "is_labeled": True,
                "expected_status": "DETECTED",
                "predicted_status": "DETECTED",
                "status_match": True,
                "output_present": True,
            },
            {
                "roi_id": "roi_2",
                "is_labeled": True,
                "expected_status": "DETECTED",
                "predicted_status": "DETECTED",
                "status_match": True,
                "output_present": True,
            },
        ],
    }
    cat1, rat1 = classify_case_finding(c_control_match)
    assert cat1 == "MEASURED_BASELINE"
    assert "matched ground truth" in rat1

    # 2. Control mismatch -> DEMONSTRATED_DEFECT
    c_control_fail = {
        "case_id": "case_01_control_clean",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {
                "roi_id": "roi_1",
                "is_labeled": True,
                "expected_status": "DETECTED",
                "predicted_status": "MISSING",
                "status_match": False,
                "output_present": True,
            },
        ],
    }
    cat2, rat2 = classify_case_finding(c_control_fail)
    assert cat2 == "DEMONSTRATED_DEFECT"
    assert "Control status mismatch" in rat2

    # 3. Input failure (FILESYSTEM_ACCESS) -> INPUT_FAILURE (not DEMONSTRATED_DEFECT)
    c_fs_err = {
        "case_id": "case_missing_image",
        "analysis_status": None,
        "status": "ERROR",
        "error": {
            "category": "FILESYSTEM_ACCESS",
            "type": "FileNotFoundError",
            "message": "Image file not found on disk for case 'case_missing_image'.",
        },
        "sites": [],
    }
    cat_fs, rat_fs = classify_case_finding(c_fs_err)
    assert cat_fs == "INPUT_FAILURE"
    assert "Input failure (FILESYSTEM_ACCESS)" in rat_fs

    # 4. Input failure (IMAGE_VALIDATION) -> INPUT_FAILURE (not DEMONSTRATED_DEFECT)
    c_img_err = {
        "case_id": "case_corrupt_image",
        "analysis_status": None,
        "status": "ERROR",
        "error": {
            "category": "IMAGE_VALIDATION",
            "type": "ImageDecodeError",
            "message": "Image format unsupported, damaged, or unreadable.",
        },
        "sites": [],
    }
    cat_img, rat_img = classify_case_finding(c_img_err)
    assert cat_img == "INPUT_FAILURE"
    assert "Input failure (IMAGE_VALIDATION)" in rat_img

    # 5. Unexpected pipeline execution crash -> EXECUTION_FAILURE (not DEMONSTRATED_DEFECT)
    c_exec_err = {
        "case_id": "case_crash",
        "analysis_status": None,
        "status": "ERROR",
        "error": {
            "category": "EXECUTION_ERROR",
            "type": "RuntimeError",
            "message": "Pipeline execution error encountered while inspecting case 'case_crash'.",
        },
        "sites": [],
    }
    cat_exec, rat_exec = classify_case_finding(c_exec_err)
    assert cat_exec == "EXECUTION_FAILURE"
    assert "Execution failure (EXECUTION_ERROR)" in rat_exec

    # 6. Omitted output site -> DEMONSTRATED_DEFECT
    c_missing_out = {
        "case_id": "case_missing_output",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {"roi_id": "roi_1", "is_labeled": False, "predicted_status": "DETECTED", "output_present": False},
        ],
    }
    cat_omitted, rat_omitted = classify_case_finding(c_missing_out)
    assert cat_omitted == "DEMONSTRATED_DEFECT"
    assert "Output omitted for site(s): roi_1" in rat_omitted

    # 7. Unlabeled perturbation DETECTED without warnings -> POTENTIAL_RISK
    c_blur = {
        "case_id": "case_03_blur_heavy",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {"roi_id": "roi_1", "is_labeled": False, "predicted_status": "DETECTED", "output_present": True, "warnings": []},
            {"roi_id": "roi_2", "is_labeled": False, "predicted_status": "DETECTED", "output_present": True, "warnings": []},
        ],
    }
    cat_blur, rat_blur = classify_case_finding(c_blur)
    assert cat_blur == "POTENTIAL_RISK"
    assert "without warnings" in rat_blur

    # 8. Unlabeled perturbation DETECTED with warnings -> POTENTIAL_RISK
    c_warn = {
        "case_id": "case_warning_detected",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {
                "roi_id": "roi_1",
                "is_labeled": False,
                "predicted_status": "DETECTED",
                "output_present": True,
                "warnings": ["Low contrast edge detected."],
            },
        ],
    }
    cat_warn, rat_warn = classify_case_finding(c_warn)
    assert cat_warn == "POTENTIAL_RISK"
    assert "with warning(s)" in rat_warn

    # 9. Low-contrast gated UNRELIABLE -> MEASURED_BASELINE
    c_low_contrast = {
        "case_id": "case_06_contrast_low",
        "analysis_status": "UNRELIABLE",
        "status": "SUCCESS",
        "sites": [
            {"roi_id": "roi_1", "is_labeled": False, "predicted_status": "UNASSESSED", "output_present": True},
            {"roi_id": "roi_2", "is_labeled": False, "predicted_status": "UNASSESSED", "output_present": True},
        ],
    }
    cat_lc, rat_lc = classify_case_finding(c_low_contrast)
    assert cat_lc == "MEASURED_BASELINE"
    assert "UNASSESSED" in rat_lc


def test_summary_with_failed_case(tmp_path: Path) -> None:
    """Verifies summary reflects actual failed cases under Execution and Input Failures."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path)

    # Inject an execution failure into case 0 with matching site records
    c0 = report["cases"][0]
    c0["status"] = "ERROR"
    c0["error"] = {
        "category": "EXECUTION_ERROR",
        "type": "RuntimeError",
        "message": "Synthetic segmentation crash",
    }
    c0["analysis_status"] = None
    for s in c0["sites"]:
        s["case_failed"] = True
        s["output_present"] = False
        s["predicted_status"] = None
        s["status_match"] = False if s.get("is_labeled") else None

    # Recompute summary to match modified cases
    report["summary"] = compute_dataset_metrics(report["cases"])

    validate_identities(manifest, report)
    md = generate_markdown_summary(manifest, report)

    assert "1 case(s) failed with execution error" in md
    assert "**FAILED CASE (EXECUTION_ERROR)**: Synthetic segmentation crash" in md
    assert "Execution and Input Failures (1)" in md
    assert "EXECUTION_FAILURE" in md
    assert "Demonstrated Inspection Defects (0)" in md


def test_summary_with_filesystem_access_and_image_validation_failures(tmp_path: Path) -> None:
    """Verifies FILESYSTEM_ACCESS and IMAGE_VALIDATION errors are categorized as INPUT_FAILURE."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path)

    # Case 1: FILESYSTEM_ACCESS
    c1 = report["cases"][1]
    c1["status"] = "ERROR"
    c1["error"] = {
        "category": "FILESYSTEM_ACCESS",
        "type": "FileNotFoundError",
        "message": "Image file not found on disk for case 'case_02_blur_mild'.",
    }
    c1["analysis_status"] = None
    for s in c1["sites"]:
        s["case_failed"] = True
        s["output_present"] = False
        s["predicted_status"] = None

    # Case 2: IMAGE_VALIDATION
    c2 = report["cases"][2]
    c2["status"] = "ERROR"
    c2["error"] = {
        "category": "IMAGE_VALIDATION",
        "type": "ImageDecodeError",
        "message": "Image format unsupported, damaged, or unreadable.",
    }
    c2["analysis_status"] = None
    for s in c2["sites"]:
        s["case_failed"] = True
        s["output_present"] = False
        s["predicted_status"] = None

    # Recompute summary to match
    report["summary"] = compute_dataset_metrics(report["cases"])

    validate_identities(manifest, report)
    md = generate_markdown_summary(manifest, report)

    assert "2 case(s) failed with execution error" in md
    assert "Input failure (FILESYSTEM_ACCESS)" in md
    assert "Input failure (IMAGE_VALIDATION)" in md
    assert "Execution and Input Failures (2)" in md
    assert "Demonstrated Inspection Defects (0)" in md


def test_summary_with_wrong_control(tmp_path: Path) -> None:
    """Verifies summary reflects ground-truth control mismatches under Demonstrated Inspection Defects."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path)

    # Inject control mismatch on site 1 of case_01_control_clean
    site_0 = report["cases"][0]["sites"][0]
    site_0["predicted_status"] = "MISSING"
    site_0["status_match"] = False
    report["summary"] = compute_dataset_metrics(report["cases"])

    validate_identities(manifest, report)
    md = generate_markdown_summary(manifest, report)

    assert "1 labeled control site(s) mismatched ground truth" in md
    assert "Control status mismatch on site(s): roi_1 (expected DETECTED, got MISSING)" in md
    assert "Demonstrated Inspection Defects (1)" in md
    assert "All 6 labeled control sites matched ground truth" not in md


def test_summary_with_omitted_output(tmp_path: Path) -> None:
    """Verifies summary explicitly flags omitted output sites as DEMONSTRATED_DEFECT."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path)

    # Site 1 omitted from output on case 1
    report["cases"][1]["sites"][0]["output_present"] = False
    report["cases"][1]["sites"][0]["predicted_status"] = None
    report["summary"] = compute_dataset_metrics(report["cases"])

    validate_identities(manifest, report)
    md = generate_markdown_summary(manifest, report)

    assert "OMITTED OUTPUT" in md
    assert "Output omitted for site(s): roi_1" in md
    assert "Demonstrated Inspection Defects (1)" in md


def test_summary_with_warning_bearing_detected_site(tmp_path: Path) -> None:
    """Verifies summary renders per-site warnings and notes them in classification rationale."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path)

    # Add warning to case 1 (blur mild)
    report["cases"][1]["sites"][0]["warnings"] = ["Boundary contrast is borderline."]

    validate_identities(manifest, report)
    md = generate_markdown_summary(manifest, report)

    assert "Boundary contrast is borderline" in md
    assert "with warning(s)" in md
    assert "POTENTIAL_RISK" in md


def test_summary_with_all_unlabeled_data() -> None:
    """Verifies summary handles an entirely unlabeled dataset honestly without claiming control passes."""
    cases = [
        ManifestCase(
            case_id="case_unlabeled_1",
            description="Unlabeled test deposit",
            current_image_path="images/img1.png",
            profile=AnalysisProfile(
                mode=ImageAnalysisMode.PROCESS_LIMITS,
                rois=[NormalizedROI(roi_id="r1", x=0.1, y=0.1, width=0.5, height=0.5)],
                process_limits=ProcessLimits(min_coverage_ratio=0.05),
            ),
            expected_statuses=None,
        )
    ]
    manifest = DatasetManifest(
        manifest_version="v1",
        dataset_id="unlabeled_dataset_v1",
        origin=DatasetOrigin.SYNTHETIC,
        description="Dataset without labels",
        cases=cases,
    )

    report = {
        "report_version": "v1",
        "dataset_id": "unlabeled_dataset_v1",
        "origin": "synthetic",
        "description": "Dataset without labels",
        "run_provenance": {},
        "summary": {
            "case_counts": {"total_cases": 1, "successful_cases": 1, "failed_cases": 0, "unreviewed_labeled_cases": 0},
            "site_counts": {
                "total_sites": 1,
                "eligible_labeled_sites": 0,
                "unlabeled_sites": 1,
                "emitted_predictions": 1,
                "correct_labeled_sites": 0,
                "incorrect_labeled_sites": 0,
            },
            "status_accuracy": None,
            "abstention_rate": {"numerator": 0, "denominator": 1, "rate": 0.0},
            "false_missing_rate": {"numerator": 0, "denominator": 0, "rate": 0.0},
        },
        "cases": [
            {
                "case_id": "case_unlabeled_1",
                "description": "Unlabeled test deposit",
                "current_image_path": "images/img1.png",
                "reference_image_path": None,
                "profile": cases[0].profile.model_dump(mode="json"),
                "status": "SUCCESS",
                "analysis_status": "CALIBRATED",
                "current_inspection_coverage": {"status": "COMPLETE", "expected_roi_count": 1, "assessed_roi_count": 1},
                "reference_inspection_coverage": None,
                "sites": [
                    {
                        "roi_id": "r1",
                        "is_labeled": False,
                        "expected_status": None,
                        "predicted_status": "DETECTED",
                        "status_match": None,
                        "output_present": True,
                        "case_failed": False,
                        "warnings": [],
                    }
                ],
                "affected_observations": [],
            }
        ],
    }

    validate_identities(manifest, report)
    md = generate_markdown_summary(manifest, report)

    assert "null (no labels)" in md
    assert "No labeled control sites present in dataset" in md
    assert "POTENTIAL_RISK" in md
    assert "100% agreement" not in md


def test_summary_with_changed_blur_outcomes(tmp_path: Path) -> None:
    """Verifies that changed blur pipeline behavior (abstaining as UNRELIABLE) is classified accordingly."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path)

    # Change case 2 (heavy blur) from CALIBRATED/DETECTED to UNRELIABLE/UNASSESSED
    c2 = report["cases"][2]
    c2["analysis_status"] = "UNRELIABLE"
    c2["current_inspection_coverage"]["status"] = "NONE"
    c2["current_inspection_coverage"]["assessed_roi_count"] = 0
    c2["current_inspection_coverage"]["unassessed_roi_ids"] = ["roi_1", "roi_2"]
    for s in c2["sites"]:
        s["predicted_status"] = "UNASSESSED"
        s["warnings"] = ["Laplacian variance below sharpness threshold."]

    report["summary"] = compute_dataset_metrics(report["cases"])

    validate_identities(manifest, report)
    cat, rat = classify_case_finding(c2)
    assert cat == "MEASURED_BASELINE"
    assert "UNASSESSED" in rat

    md = generate_markdown_summary(manifest, report)
    assert "Laplacian variance below sharpness threshold" in md
    assert "Optical Defocus / Blur Blindspot (Cases 02 & 03)" not in md


def test_summary_safe_publication_sentinel_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies publish_report_file refuses to clobber a sentinel file created during generation."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    out_file = tmp_path / "out_summary.md"
    sentinel_content = "SENTINEL CONTENT THAT MUST NOT BE OVERWRITTEN"

    out_file.write_text(sentinel_content, encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "inspection_robustness_summary",
            "-m",
            str(manifest_path),
            "-r",
            str(report_path),
            "-o",
            str(out_file),
        ],
    )

    rc = summary_main()
    assert rc == 1  # Fails closed
    assert out_file.read_text(encoding="utf-8") == sentinel_content

    # Verify no temporary files remain
    tmp_files = list(tmp_path.glob(".tmp_*"))
    assert len(tmp_files) == 0


def test_summary_cli_rejects_removed_sites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies CLI rejects reports with missing site records without traceback or creating output."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    # Remove one site from case 0
    report["cases"][0]["sites"] = [report["cases"][0]["sites"][0]]

    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err
    assert "C:\\" not in captured.err and "/Users/" not in captured.err


def test_summary_cli_rejects_duplicate_sites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies CLI rejects reports with duplicate site IDs without traceback or creating output."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    # Duplicate site in case 0
    report["cases"][0]["sites"] = [report["cases"][0]["sites"][0], report["cases"][0]["sites"][0]]

    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err


def test_summary_cli_rejects_unknown_sites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies CLI rejects reports with unknown site IDs not in configured profile ROIs."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    # Rename site 0 to unknown ROI ID
    report["cases"][0]["sites"][0]["roi_id"] = "unknown_phantom_site"

    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err


def test_summary_cli_rejects_sites_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies CLI rejects reports with sites=null."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    report["cases"][0]["sites"] = None

    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err


def test_summary_cli_rejects_non_object_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies CLI rejects reports with non-object site entries."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    report["cases"][0]["sites"] = ["string_instead_of_dict", 42]

    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err


def test_summary_cli_rejects_non_string_image_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies CLI rejects reports with non-string image path without AttributeError traceback."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    report["cases"][0]["current_image_path"] = 12345

    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err


def test_summary_cli_rejects_contradictory_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies CLI rejects reports where summary metrics contradict individual case and site records."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, tmp_path / "dataset")

    # Contradictory summary: claim 999 successful cases
    report["summary"]["case_counts"]["successful_cases"] = 999

    report_path = tmp_path / "bad_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err


def test_summary_cli_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies summary CLI generates data-derived markdown with all required fields from actual report."""
    manifest_path = generate_robustness_dataset(tmp_path / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    report = evaluate_dataset(manifest, tmp_path / "dataset")
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    out_summary = tmp_path / "summary.md"

    monkeypatch.setattr(
        "sys.argv",
        [
            "inspection_robustness_summary",
            "-m",
            str(manifest_path),
            "-r",
            str(report_path),
            "-o",
            str(out_summary),
        ],
    )

    rc = summary_main()
    assert rc == 0
    assert out_summary.exists()

    md_content = out_summary.read_text(encoding="utf-8")
    assert "synthetic_inspection_robustness_v1" in md_content
    assert "POTENTIAL_RISK" in md_content
    assert "MEASURED_BASELINE" in md_content
    assert "Sites (Assessed/Exp)" in md_content
    assert "Current Cov" in md_content
    assert "Ref Cov" in md_content
    assert "Site Statuses & Warnings" in md_content
    assert "Emitted Observations" in md_content
    assert "Demonstrated Inspection Defects (0)" in md_content
    assert "Execution and Input Failures (0)" in md_content
    assert "Absence of diagnostic defect observations is NOT an automatic pass" in md_content

    # Verify absence of static scenario text
    assert "Optical Defocus / Blur Blindspot (Cases 02 & 03)" not in md_content


@pytest.fixture(scope="module")
def valid_dataset_and_report(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """Generates and evaluates the robustness dataset once for module-level CLI regression checks."""
    base_dir = tmp_path_factory.mktemp("base_dataset")
    manifest_path = generate_robustness_dataset(base_dir / "dataset")
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(manifest, base_dir / "dataset")
    return manifest_path, report


@pytest.mark.parametrize(
    "corrupt_type,corrupt_val",
    [
        ("inconsistent", 0.25),
        ("missing", "__MISSING__"),
        ("string", "0.25"),
        ("boolean_true", True),
        ("boolean_false", False),
        ("out_of_range_low", -0.1),
        ("out_of_range_high", 1.5),
        ("nonfinite_nan", float("nan")),
        ("nonfinite_inf", float("inf")),
    ],
)
def test_summary_cli_rejects_status_accuracy_rate_corruptions(
    valid_dataset_and_report: tuple[Path, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    corrupt_type: str,
    corrupt_val: Any,
) -> None:
    """Verifies CLI cleanly rejects status_accuracy rate corruptions (inconsistent, missing, string, bool, out-of-range, nonfinite)."""
    manifest_path, base_report = valid_dataset_and_report
    report = copy.deepcopy(base_report)

    if corrupt_val == "__MISSING__":
        del report["summary"]["status_accuracy"]["rate"]
    else:
        report["summary"]["status_accuracy"]["rate"] = corrupt_val

    report_path = tmp_path / "corrupted_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


@pytest.mark.parametrize(
    "corrupt_type,corrupt_val",
    [
        ("inconsistent", 0.99),
        ("missing", "__MISSING__"),
        ("string", "0.50"),
        ("boolean_true", True),
        ("boolean_false", False),
        ("out_of_range_low", -0.01),
        ("out_of_range_high", 2.0),
        ("nonfinite_nan", float("nan")),
        ("nonfinite_inf", float("inf")),
    ],
)
def test_summary_cli_rejects_abstention_rate_corruptions(
    valid_dataset_and_report: tuple[Path, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    corrupt_type: str,
    corrupt_val: Any,
) -> None:
    """Verifies CLI cleanly rejects abstention_rate rate corruptions (inconsistent, missing, string, bool, out-of-range, nonfinite)."""
    manifest_path, base_report = valid_dataset_and_report
    report = copy.deepcopy(base_report)

    if corrupt_val == "__MISSING__":
        del report["summary"]["abstention_rate"]["rate"]
    else:
        report["summary"]["abstention_rate"]["rate"] = corrupt_val

    report_path = tmp_path / "corrupted_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


@pytest.mark.parametrize(
    "corrupt_type,corrupt_val",
    [
        ("inconsistent", 0.75),
        ("missing", "__MISSING__"),
        ("string", "0.00"),
        ("boolean_true", True),
        ("boolean_false", False),
        ("out_of_range_low", -1.0),
        ("out_of_range_high", 1.2),
        ("nonfinite_nan", float("nan")),
        ("nonfinite_inf", float("inf")),
    ],
)
def test_summary_cli_rejects_false_missing_rate_corruptions(
    valid_dataset_and_report: tuple[Path, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    corrupt_type: str,
    corrupt_val: Any,
) -> None:
    """Verifies CLI cleanly rejects false_missing_rate rate corruptions (inconsistent, missing, string, bool, out-of-range, nonfinite)."""
    manifest_path, base_report = valid_dataset_and_report
    report = copy.deepcopy(base_report)

    if corrupt_val == "__MISSING__":
        del report["summary"]["false_missing_rate"]["rate"]
    else:
        report["summary"]["false_missing_rate"]["rate"] = corrupt_val

    report_path = tmp_path / "corrupted_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_file = tmp_path / "should_not_exist.md"

    monkeypatch.setattr(
        "sys.argv",
        ["inspection_robustness_summary", "-m", str(manifest_path), "-r", str(report_path), "-o", str(out_file)],
    )

    rc = summary_main()
    assert rc == 1
    assert not out_file.exists()

    captured = capsys.readouterr()
    assert "Fatal error: Report validation failed:" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


def test_generate_markdown_summary_derives_percentages_from_canonical_metrics(
    valid_dataset_and_report: tuple[Path, dict[str, Any]],
) -> None:
    """Verifies that generate_markdown_summary derives all percentages from canonical recomputed metrics."""
    manifest_path, report = valid_dataset_and_report
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    md = generate_markdown_summary(manifest, report)

    # Recomputed metrics for the 14-case matrix:
    # 6 labeled control sites, all matched -> 100.0% (6/6)
    # 8/28 sites unassessed -> 28.6% (8/28)
    # 0/4 non-missing labeled controls misclassified as missing -> 0.0% (0/4)
    assert "**100.0% (6/6)**" in md
    assert "**28.6% (8/28)**" in md
    assert "**0.0% (0/4)**" in md
    assert "All 6 labeled control sites matched ground truth" in md
    assert "8/28 total sites flagged UNASSESSED by quality gates" in md
    assert "0/4 non-missing labeled control sites misclassified as MISSING" in md
