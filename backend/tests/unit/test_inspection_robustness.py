"""
Unit tests for Synthetic Inspection Robustness Dataset Generator & Summary Utility.

Verifies:
- Deterministic fixture generation (byte-identical images across runs).
- Manifest schema validation and strict label separation (only clean controls labeled).
- Clipped edge coordinate transformation and valid normalized ROIs.
- Collision preflight on generator and summary output paths.
- Identity validation between manifest and evaluation report.
- Summary risk classification across success, unassessed, missing output, and failed cases.
- CLI argument handling and execution.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    # First generation succeeds
    p1 = generate_robustness_dataset(tmp_path)
    assert p1.exists()

    # Second generation without overwrite must raise FileExistsError
    with pytest.raises(FileExistsError, match="Target file already exists"):
        generate_robustness_dataset(tmp_path, overwrite=False)

    # Third generation with overwrite=True succeeds
    p3 = generate_robustness_dataset(tmp_path, overwrite=True)
    assert p3.exists()


def test_summary_identity_mismatch_validation(tmp_path: Path) -> None:
    """Verifies validate_identities rejects mismatched dataset IDs, case counts, or case ordering."""
    manifest_path = generate_robustness_dataset(tmp_path)
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    report = evaluate_dataset(manifest, tmp_path)

    # 1. Matching identities succeed
    validate_identities(manifest, report)

    # 2. Dataset ID mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["dataset_id"] = "different_dataset_id"
    with pytest.raises(IdentityMismatchError, match="Dataset ID mismatch"):
        validate_identities(manifest, bad_report)

    # 3. Case count mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["cases"] = bad_report["cases"][:-1]
    with pytest.raises(IdentityMismatchError, match="Case count mismatch"):
        validate_identities(manifest, bad_report)

    # 4. Case ID mismatch
    bad_report = json.loads(json.dumps(report))
    bad_report["cases"][0]["case_id"] = "wrong_case_id"
    with pytest.raises(IdentityMismatchError, match="Case ID mismatch at index 0"):
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


def test_summary_risk_classification_and_accounting(tmp_path: Path) -> None:
    """Verifies classify_case_finding and generate_markdown_summary across hand-crafted mixed outcomes."""
    # 1. Clean control -> MEASURED_BASELINE
    c_control = {
        "case_id": "case_01_control_clean",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {"roi_id": "roi_1", "predicted_status": "DETECTED", "output_present": True},
            {"roi_id": "roi_2", "predicted_status": "DETECTED", "output_present": True},
        ],
    }
    cat1, _ = classify_case_finding(c_control)
    assert cat1 == "MEASURED_BASELINE"

    # 2. Defocused case remaining DETECTED without gate -> POTENTIAL_RISK
    c_blur = {
        "case_id": "case_02_blur_heavy",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {"roi_id": "roi_1", "predicted_status": "DETECTED", "output_present": True},
            {"roi_id": "roi_2", "predicted_status": "DETECTED", "output_present": True},
        ],
    }
    cat2, _ = classify_case_finding(c_blur)
    assert cat2 == "POTENTIAL_RISK"

    # 3. Low-contrast correctly gated UNRELIABLE -> MEASURED_BASELINE
    c_low_contrast = {
        "case_id": "case_06_contrast_low",
        "analysis_status": "UNRELIABLE",
        "status": "SUCCESS",
        "sites": [
            {"roi_id": "roi_1", "predicted_status": "UNASSESSED", "output_present": True},
            {"roi_id": "roi_2", "predicted_status": "UNASSESSED", "output_present": True},
        ],
    }
    cat3, _ = classify_case_finding(c_low_contrast)
    assert cat3 == "MEASURED_BASELINE"

    # 4. Missing output site -> DEMONSTRATED_DEFECT
    c_missing_out = {
        "case_id": "case_missing_output",
        "analysis_status": "CALIBRATED",
        "status": "SUCCESS",
        "sites": [
            {"roi_id": "roi_1", "predicted_status": "DETECTED", "output_present": False},
        ],
    }
    cat4, _ = classify_case_finding(c_missing_out)
    assert cat4 == "DEMONSTRATED_DEFECT"

    # 5. Execution failure -> DEMONSTRATED_DEFECT
    c_failed = {
        "case_id": "case_execution_fail",
        "analysis_status": None,
        "status": "ERROR",
        "sites": [],
    }
    cat5, _ = classify_case_finding(c_failed)
    assert cat5 == "DEMONSTRATED_DEFECT"


def test_summary_cli_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies summary CLI generates markdown from actual generated dataset and report."""
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
    assert "Optical Defocus / Blur Blindspot" in md_content
    assert "Absence of diagnostic defect observations is NOT a pass" in md_content
