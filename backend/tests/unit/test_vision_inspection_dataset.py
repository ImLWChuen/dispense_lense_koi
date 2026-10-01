"""
Dispense Lens - Unit Tests for Local Image Dataset Evaluation Runner

Verifies:
- Transparent hand-calculated metric accounting (status accuracy, abstentions, false missings).
- Invariant: failed cases and missing pipeline outputs do not drop out to inflate accuracy.
- Invariant: all-unlabeled datasets yield null (None) status accuracy, never 0% or 100%.
- Manifest schema validation (unique case IDs, valid ROI IDs in labels, mode requirements).
- Path resolution and security (rejection of absolute paths, path traversal escape, missing files).
- Overwrite protection for evaluation reports.
- Offline execution of multi-case synthetic datasets with process limits and reference images.
- Partial-run continuation and error recording when corrupt images are encountered.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from pydantic import ValidationError

from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    NormalizedROI,
    ProcessLimits,
    ReferenceLimits,
    RoiInspectionStatus,
)
from tests.fixtures.generate_local_image_evaluation import generate_synthetic_dataset
from tests.vision_inspection_dataset import (
    DatasetManifest,
    DatasetOrigin,
    ManifestCase,
    PathValidationError,
    compute_dataset_metrics,
    evaluate_dataset,
    resolve_and_validate_path,
)


def test_hand_calculated_metrics_accounting() -> None:
    """Verifies hand-calculated metrics across correct, incorrect, unlabeled, missing output, and failed cases.

    Scenario:
    - Case 1 (SUCCESS, 2 ROIs):
        - r1: labeled DETECTED, predicted DETECTED -> MATCH (correct)
        - r2: labeled UNASSESSED, predicted MISSING -> MISMATCH (false missing!)
    - Case 2 (SUCCESS, 2 ROIs):
        - r1: labeled DETECTED, pipeline omitted output -> MISSING OUTPUT (mismatch/incorrect)
        - r2: unlabeled, predicted DETECTED -> UNLABELED (excluded from accuracy)
    - Case 3 (ERROR, 2 ROIs):
        - r1: labeled DETECTED, case threw exception -> FAILED CASE (mismatch/incorrect)
        - r2: unlabeled, case threw exception -> FAILED CASE UNLABELED
    - Case 4 (SUCCESS, 1 ROI):
        - r1: labeled MISSING, predicted MISSING -> MATCH (correct)

    Total sites: 7
    Unlabeled sites: 2 (Case 2 r2, Case 3 r2)
    Eligible labeled sites: 5 (Case 1 r1, Case 1 r2, Case 2 r1, Case 3 r1, Case 4 r1)
    Correct labeled sites: 2 (Case 1 r1, Case 4 r1)
    Incorrect labeled sites: 3 (Case 1 r2 [mismatch], Case 2 r1 [missing output], Case 3 r1 [failed case])

    Status Accuracy: 2 / 5 = 0.4000 (Accuracy does NOT drop failed/missing sites!)
    Emitted predictions: 4 (Case 1 r1, Case 1 r2, Case 2 r2, Case 4 r1)
    Emitted unassessed: 0
    Abstention rate: 0 / 4 = 0.0

    Known non-missing labels: 4 (Case 1 r1 [DET], Case 1 r2 [UNASSESSED], Case 2 r1 [DET], Case 3 r1 [DET])
    False missing count: 1 (Case 1 r2: expected UNASSESSED, predicted MISSING)
    False missing rate: 1 / 4 = 0.2500
    """
    case_results = [
        {
            "case_id": "c1",
            "status": "SUCCESS",
            "sites": [
                {
                    "roi_id": "r1",
                    "is_labeled": True,
                    "expected_status": "DETECTED",
                    "predicted_status": "DETECTED",
                    "status_match": True,
                    "output_present": True,
                    "case_failed": False,
                },
                {
                    "roi_id": "r2",
                    "is_labeled": True,
                    "expected_status": "UNASSESSED",
                    "predicted_status": "MISSING",
                    "status_match": False,
                    "output_present": True,
                    "case_failed": False,
                },
            ],
        },
        {
            "case_id": "c2",
            "status": "SUCCESS",
            "sites": [
                {
                    "roi_id": "r1",
                    "is_labeled": True,
                    "expected_status": "DETECTED",
                    "predicted_status": None,
                    "status_match": False,
                    "output_present": False,  # Missing output!
                    "case_failed": False,
                },
                {
                    "roi_id": "r2",
                    "is_labeled": False,
                    "expected_status": None,
                    "predicted_status": "DETECTED",
                    "status_match": None,
                    "output_present": True,
                    "case_failed": False,
                },
            ],
        },
        {
            "case_id": "c3",
            "status": "ERROR",
            "sites": [
                {
                    "roi_id": "r1",
                    "is_labeled": True,
                    "expected_status": "DETECTED",
                    "predicted_status": None,
                    "status_match": False,
                    "output_present": False,
                    "case_failed": True,  # Failed case!
                },
                {
                    "roi_id": "r2",
                    "is_labeled": False,
                    "expected_status": None,
                    "predicted_status": None,
                    "status_match": None,
                    "output_present": False,
                    "case_failed": True,
                },
            ],
        },
        {
            "case_id": "c4",
            "status": "SUCCESS",
            "sites": [
                {
                    "roi_id": "r1",
                    "is_labeled": True,
                    "expected_status": "MISSING",
                    "predicted_status": "MISSING",
                    "status_match": True,
                    "output_present": True,
                    "case_failed": False,
                },
            ],
        },
    ]

    metrics = compute_dataset_metrics(case_results)

    # Case counts
    assert metrics["case_counts"]["total_cases"] == 4
    assert metrics["case_counts"]["successful_cases"] == 3
    assert metrics["case_counts"]["failed_cases"] == 1

    # Site counts
    sc = metrics["site_counts"]
    assert sc["total_sites"] == 7
    assert sc["eligible_labeled_sites"] == 5
    assert sc["unlabeled_sites"] == 2
    assert sc["emitted_predictions"] == 4
    assert sc["correct_labeled_sites"] == 2
    assert sc["incorrect_labeled_sites"] == 3

    # Failure accounting
    fa = metrics["failure_accounting"]
    assert fa["failed_cases_count"] == 1
    assert fa["failed_case_sites_count"] == 2
    assert fa["failed_case_labeled_sites_count"] == 1
    assert fa["missing_output_sites_count"] == 1
    assert fa["missing_output_labeled_sites_count"] == 1
    assert fa["unlabeled_sites_count"] == 2

    # Status accuracy
    acc = metrics["status_accuracy"]
    assert acc is not None
    assert acc["numerator"] == 2
    assert acc["denominator"] == 5
    assert acc["rate"] == 0.4000

    # False-missing rate
    fm = metrics["false_missing_rate"]
    assert fm["numerator"] == 1
    assert fm["denominator"] == 4
    assert fm["rate"] == 0.2500

    # Confusion matrix (only emitted predictions for labeled sites: c1.r1, c1.r2, c4.r1)
    cm = metrics["confusion_matrix"]
    assert cm["DETECTED"]["DETECTED"] == 1
    assert cm["UNASSESSED"]["MISSING"] == 1
    assert cm["MISSING"]["MISSING"] == 1
    assert cm["DETECTED"]["MISSING"] == 0

    # Boundary accuracy statement
    assert metrics["boundary_accuracy"]["status"] == "not_evaluated"


def test_null_status_accuracy_when_all_unlabeled() -> None:
    """Verifies that datasets with zero labeled sites return null accuracy, never 0% or 100%."""
    case_results = [
        {
            "case_id": "c1",
            "status": "SUCCESS",
            "sites": [
                {
                    "roi_id": "r1",
                    "is_labeled": False,
                    "expected_status": None,
                    "predicted_status": "DETECTED",
                    "status_match": None,
                    "output_present": True,
                    "case_failed": False,
                },
                {
                    "roi_id": "r2",
                    "is_labeled": False,
                    "expected_status": None,
                    "predicted_status": "MISSING",
                    "status_match": None,
                    "output_present": True,
                    "case_failed": False,
                },
            ],
        }
    ]
    metrics = compute_dataset_metrics(case_results)
    assert metrics["status_accuracy"] is None
    assert metrics["site_counts"]["eligible_labeled_sites"] == 0
    assert metrics["site_counts"]["unlabeled_sites"] == 2
    assert metrics["false_missing_rate"]["denominator"] == 0
    assert metrics["false_missing_rate"]["rate"] == 0.0


def test_manifest_validation_duplicate_case_ids() -> None:
    """Duplicate case IDs in manifest must raise validation error."""
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[NormalizedROI(roi_id="r1", x=0.2, y=0.2, width=0.5, height=0.5)],
        process_limits=ProcessLimits(min_coverage_ratio=0.05),
    )
    case1 = ManifestCase(
        case_id="duplicate_id",
        current_image_path="img1.png",
        profile=profile,
    )
    case2 = ManifestCase(
        case_id="duplicate_id",
        current_image_path="img2.png",
        profile=profile,
    )
    with pytest.raises(ValueError, match="Duplicate case_id"):
        DatasetManifest(
            manifest_version="v1",
            dataset_id="test_dup",
            origin=DatasetOrigin.SYNTHETIC,
            cases=[case1, case2],
        )


def test_manifest_validation_invalid_label_roi() -> None:
    """Expected status assigned to an ROI not in profile.rois must raise validation error."""
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[NormalizedROI(roi_id="r1", x=0.2, y=0.2, width=0.5, height=0.5)],
        process_limits=ProcessLimits(min_coverage_ratio=0.05),
    )
    with pytest.raises(ValueError, match="unknown ROI ID 'r_nonexistent'"):
        ManifestCase(
            case_id="case_invalid_roi",
            current_image_path="img1.png",
            profile=profile,
            expected_statuses={"r_nonexistent": RoiInspectionStatus.DETECTED},
        )


def test_manifest_validation_reference_mode_requires_reference_path() -> None:
    """REFERENCE_IMAGE profile mode requires reference_image_path to be specified."""
    ref_profile = AnalysisProfile(
        mode=ImageAnalysisMode.REFERENCE_IMAGE,
        rois=[NormalizedROI(roi_id="r1", x=0.2, y=0.2, width=0.5, height=0.5)],
        reference_limits=ReferenceLimits(tolerance_ratio=0.2),
    )
    with pytest.raises(ValueError, match="REFERENCE_IMAGE mode but provides no reference_image_path"):
        ManifestCase(
            case_id="case_missing_ref_path",
            current_image_path="img1.png",
            reference_image_path=None,
            profile=ref_profile,
        )


def test_path_validation_traversal_and_absolute_rejection(tmp_path: Path) -> None:
    """Path resolution must reject absolute paths and directory traversal attempts."""
    # Absolute path rejection in validator
    profile = AnalysisProfile(
        mode=ImageAnalysisMode.PROCESS_LIMITS,
        rois=[NormalizedROI(roi_id="r1", x=0.2, y=0.2, width=0.5, height=0.5)],
        process_limits=ProcessLimits(min_coverage_ratio=0.05),
    )
    with pytest.raises(ValueError, match="relative path"):
        ManifestCase(
            case_id="c1",
            current_image_path="/absolute/path/image.png",
            profile=profile,
        )

    # Path traversal escape via resolver
    with pytest.raises(PathValidationError, match="traversal"):
        resolve_and_validate_path("../../etc/passwd", tmp_path)

    # Non-existent relative path
    with pytest.raises(PathValidationError, match="does not exist"):
        resolve_and_validate_path("missing_file.png", tmp_path)


def test_end_to_end_synthetic_evaluation(tmp_path: Path) -> None:
    """Generates synthetic dataset in scratch folder, executes runner, and validates report."""
    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    assert manifest_path.exists()

    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw_manifest)

    report = evaluate_dataset(manifest, tmp_path)

    # Validate report top-level fields
    assert report["report_version"] == "v1"
    assert report["dataset_id"] == "synthetic_sample_v1"
    assert report["origin"] == "synthetic"
    assert "source_commit" in report["run_provenance"]
    assert len(report["cases"]) == 5

    # Check case 4 (two-site, dot-1 labeled, dot-2 unlabeled)
    c4 = next(c for c in report["cases"] if c["case_id"] == "case_04_mixed_two_site")
    assert c4["status"] == "SUCCESS"
    dot1 = next(s for s in c4["sites"] if s["roi_id"] == "dot-1")
    dot2 = next(s for s in c4["sites"] if s["roi_id"] == "dot-2")
    assert dot1["is_labeled"] is True
    assert dot1["status_match"] is True
    assert dot2["is_labeled"] is False
    assert dot2["status_match"] is None

    # Check overall summary metrics
    summary = report["summary"]
    assert summary["case_counts"]["total_cases"] == 5
    assert summary["case_counts"]["successful_cases"] == 5
    assert summary["case_counts"]["failed_cases"] == 0
    # Total sites: 1 + 1 + 1 + 2 + 1 = 6
    assert summary["site_counts"]["total_sites"] == 6
    assert summary["site_counts"]["unlabeled_sites"] == 1
    assert summary["site_counts"]["eligible_labeled_sites"] == 5
    assert summary["site_counts"]["correct_labeled_sites"] == 5

    acc = summary["status_accuracy"]
    assert acc is not None
    assert acc["numerator"] == 5
    assert acc["denominator"] == 5
    assert acc["rate"] == 1.0

    # Ensure strictly valid JSON without NaN or Inf
    serialized = json.dumps(report, allow_nan=False)
    assert "NaN" not in serialized


def test_corrupt_image_error_containment(tmp_path: Path) -> None:
    """Verifies that a corrupt image logs case error, continues remaining cases, and includes failures in metrics."""
    manifest_path = generate_synthetic_dataset(output_dir=tmp_path, include_corrupt=True)
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw_manifest)

    report = evaluate_dataset(manifest, tmp_path)

    assert report["summary"]["case_counts"]["total_cases"] == 6
    assert report["summary"]["case_counts"]["successful_cases"] == 5
    assert report["summary"]["case_counts"]["failed_cases"] == 1

    corrupt_case = next(c for c in report["cases"] if c["case_id"] == "case_06_corrupt_image")
    assert corrupt_case["status"] == "ERROR"
    assert corrupt_case["error"] is not None
    assert "ImageValidationError" in corrupt_case["error"]["type"] or "Exception" in corrupt_case["error"]["type"]

    # Invariant: the corrupt case's labeled site is in eligible labeled sites, reducing accuracy
    summary = report["summary"]
    # Total labeled sites: 5 (from valid cases) + 1 (from corrupt case) = 6
    assert summary["site_counts"]["eligible_labeled_sites"] == 6
    assert summary["site_counts"]["correct_labeled_sites"] == 5
    assert summary["status_accuracy"]["rate"] == pytest.approx(5 / 6, abs=1e-4)


def test_static_example_manifest_validity() -> None:
    """Verifies that backend/tests/fixtures/local_image_evaluation_example.json is valid Manifest v1."""
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "local_image_evaluation_example.json"
    assert fixture_path.exists(), f"Fixture file not found: {fixture_path}"
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw)
    assert manifest.manifest_version == "v1"
    assert manifest.origin == DatasetOrigin.SYNTHETIC
    assert len(manifest.cases) == 5


def test_cli_overwrite_protection_and_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies CLI exit codes for success, file collision without overwrite, and successful overwrite."""
    from tests.vision_inspection_dataset import main

    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    report_path = tmp_path / "report.json"

    # 1. First run without report existing -> should exit 0 and write report
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(report_path)],
    )
    rc1 = main()
    assert rc1 == 0
    assert report_path.exists()

    # 2. Second run when report exists and --overwrite is NOT set -> should exit 1
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(report_path)],
    )
    rc2 = main()
    assert rc2 == 1

    # 3. Third run when report exists and --overwrite IS set -> should exit 0
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(report_path), "--overwrite"],
    )
    rc3 = main()
    assert rc3 == 0


def test_cli_fatal_validation_prevents_partial_success_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies that a fatal schema validation error exits 1 and writes NO success report."""
    from tests.vision_inspection_dataset import main

    # Create invalid manifest with duplicate case IDs
    invalid_manifest = {
        "manifest_version": "v1",
        "dataset_id": "invalid_dataset",
        "origin": "synthetic",
        "cases": [
            {
                "case_id": "dup_case",
                "current_image_path": "images/img1.png",
                "profile": {
                    "mode": "PROCESS_LIMITS",
                    "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}],
                    "process_limits": {"min_coverage_ratio": 0.05},
                },
            },
            {
                "case_id": "dup_case",
                "current_image_path": "images/img2.png",
                "profile": {
                    "mode": "PROCESS_LIMITS",
                    "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}],
                    "process_limits": {"min_coverage_ratio": 0.05},
                },
            },
        ],
    }
    bad_manifest_path = tmp_path / "bad_manifest.json"
    bad_manifest_path.write_text(json.dumps(invalid_manifest), encoding="utf-8")
    report_path = tmp_path / "should_not_exist.json"

    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(bad_manifest_path), "-o", str(report_path)],
    )
    rc = main()
    assert rc == 1
    assert not report_path.exists(), "Fatal schema failure must write no output report."


def test_cli_rejects_overwriting_manifest_and_source_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies that --output pointing to manifest or any source image is rejected regardless of --overwrite."""
    from tests.vision_inspection_dataset import main

    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    manifest_bytes_orig = manifest_path.read_bytes()
    img_path = tmp_path / "images" / "case_01_detected.png"
    img_bytes_orig = img_path.read_bytes()
    ref_img_path = tmp_path / "images" / "case_05_reference_ref.png"
    ref_img_bytes_orig = ref_img_path.read_bytes()

    # 1. Output targets manifest with --overwrite -> MUST FAIL (Exit 1)
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(manifest_path), "--overwrite"],
    )
    rc_manifest = main()
    assert rc_manifest == 1
    assert manifest_path.read_bytes() == manifest_bytes_orig, "Manifest must remain byte-identical."

    # 2. Output targets source current image with --overwrite -> MUST FAIL (Exit 1)
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(img_path), "--overwrite"],
    )
    rc_img = main()
    assert rc_img == 1
    assert img_path.read_bytes() == img_bytes_orig, "Source image must remain byte-identical."

    # 3. Output targets source reference image with --overwrite -> MUST FAIL (Exit 1)
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(ref_img_path), "--overwrite"],
    )
    rc_ref = main()
    assert rc_ref == 1
    assert ref_img_path.read_bytes() == ref_img_bytes_orig, "Reference image must remain byte-identical."


def test_cli_rejects_filesystem_alias_of_protected_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies that hardlinks / aliases of protected input files are rejected via samefile checks."""
    import os
    from tests.vision_inspection_dataset import main

    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    manifest_bytes_orig = manifest_path.read_bytes()

    # Create hardlink alias to manifest
    alias_path = tmp_path / "manifest_alias.json"
    try:
        os.link(manifest_path, alias_path)
    except (OSError, NotImplementedError):
        # On filesystems without hardlink support, copy file and test direct resolved equivalence
        pytest.skip("Hardlinks not supported on current filesystem")

    assert alias_path.exists()
    assert os.path.samefile(manifest_path, alias_path)

    # Output targets alias with --overwrite -> MUST FAIL (Exit 1)
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(alias_path), "--overwrite"],
    )
    rc = main()
    assert rc == 1
    assert manifest_path.read_bytes() == manifest_bytes_orig, "Manifest must remain unmodified."


def test_generator_collision_preflight_and_overwrite(tmp_path: Path) -> None:
    """Verifies generator preflight collision check and --overwrite authorization."""
    # First generation succeeds
    p1 = generate_synthetic_dataset(output_dir=tmp_path)
    assert p1.exists()

    # Second generation without overwrite must raise FileExistsError
    with pytest.raises(FileExistsError, match="Target file already exists"):
        generate_synthetic_dataset(output_dir=tmp_path, overwrite=False)

    # Third generation with overwrite=True succeeds
    p3 = generate_synthetic_dataset(output_dir=tmp_path, overwrite=True)
    assert p3.exists()


def test_report_preserves_full_profile_and_case_provenance(tmp_path: Path) -> None:
    """Verifies report persists full profile (rois, scale, limits), notes, and provenance in success & error records."""
    manifest_path = generate_synthetic_dataset(output_dir=tmp_path, include_corrupt=True)
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw_manifest)

    report = evaluate_dataset(manifest, tmp_path)

    for case_res in report["cases"]:
        # Profile must be a complete dictionary containing mode, rois, etc.
        prof = case_res["profile"]
        assert isinstance(prof, dict)
        assert "mode" in prof
        assert "rois" in prof
        assert len(prof["rois"]) >= 1
        assert "x" in prof["rois"][0]
        assert "y" in prof["rois"][0]
        assert "width" in prof["rois"][0]
        assert "height" in prof["rois"][0]

        # Case notes and image paths must survive
        assert case_res["current_image_path"].startswith("images/")
        assert case_res["notes"] is not None

        # Provenance must survive
        assert case_res["label_provenance"] is not None
        assert case_res["label_provenance_status"] in ("provided", "inherited")


def test_reference_inspection_coverage_distinct_from_material_coverage(tmp_path: Path) -> None:
    """Verifies explicit current and reference inspection coverage summaries separate from coverage ratios."""
    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw_manifest)

    report = evaluate_dataset(manifest, tmp_path)

    ref_case = next(c for c in report["cases"] if c["case_id"] == "case_05_reference_comparison")
    assert ref_case["status"] == "SUCCESS"

    # Material coverage ratios are separate floats
    assert isinstance(ref_case["current_coverage_ratio"], float)
    assert isinstance(ref_case["reference_coverage_ratio"], float)

    # Current inspection coverage summary
    curr_cov = ref_case["current_inspection_coverage"]
    assert curr_cov["status"] == "COMPLETE"
    assert curr_cov["expected_roi_count"] == 1
    assert curr_cov["assessed_roi_count"] == 1
    assert curr_cov["unassessed_roi_ids"] == []
    assert curr_cov["missing_roi_ids"] == []

    # Reference inspection coverage summary
    ref_cov = ref_case["reference_inspection_coverage"]
    assert ref_cov is not None
    assert ref_cov["status"] == "COMPLETE"
    assert ref_cov["expected_roi_count"] == 1
    assert ref_cov["assessed_roi_count"] == 1
    assert ref_cov["unassessed_roi_ids"] == []
    assert ref_cov["missing_roi_ids"] == []


def test_unreviewed_provenance_flagging(tmp_path: Path) -> None:
    """Verifies that cases with labels but no case or dataset provenance are visibly flagged as unreviewed."""
    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Strip dataset provenance
    raw_manifest["label_provenance"] = None
    # Strip case 1 provenance
    raw_manifest["cases"][0]["label_provenance"] = None

    manifest = DatasetManifest.model_validate(raw_manifest)
    report = evaluate_dataset(manifest, tmp_path)

    c1 = report["cases"][0]
    assert c1["label_provenance_status"] == "unreviewed"
    assert "UNREVIEWED_PROVENANCE" in str(c1["label_provenance"])
    assert any("lacks documented provenance" in w for w in c1["case_warnings"])
    assert report["summary"]["case_counts"]["unreviewed_labeled_cases"] >= 1


def test_error_message_sanitizer_suppresses_private_paths(tmp_path: Path) -> None:
    """Verifies that sanitize_error_message redacts absolute Windows and Unix paths."""
    from tests.vision_inspection_dataset import sanitize_error_message

    fake_win_path = r"C:\Users\SecretAdmin\ConfidentialProject\dataset\images\test.png"
    fake_unix_path = "/home/secret_engineer/private_data/images/test.png"

    raw_err = f"Permission denied accessing '{fake_win_path}' and '{fake_unix_path}'"
    clean_err = sanitize_error_message(raw_err, tmp_path)

    assert fake_win_path not in clean_err
    assert fake_unix_path not in clean_err
    assert "<redacted_path>" in clean_err


def test_fatal_path_traversal_manifest_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that path traversal in manifest image paths fails during preflight with exit code 1."""
    from tests.vision_inspection_dataset import main

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}],
        "process_limits": {"min_coverage_ratio": 0.05},
    }
    traversal_manifest = {
        "manifest_version": "v1",
        "dataset_id": "traversal_test",
        "origin": "synthetic",
        "cases": [
            {
                "case_id": "c_escape",
                "current_image_path": "../../secret.png",
                "profile": profile,
            }
        ],
    }
    mpath = tmp_path / "traversal_manifest.json"
    mpath.write_text(json.dumps(traversal_manifest), encoding="utf-8")
    rpath = tmp_path / "report.json"

    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(mpath), "-o", str(rpath)],
    )
    rc = main()
    assert rc == 1
    assert not rpath.exists(), "Fatal traversal preflight must prevent writing report."


def test_final_publication_sentinel_collision_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies that if a destination file appears during evaluation, publication fails atomically without clobbering."""
    import tests.vision_inspection_dataset as vid
    from tests.vision_inspection_dataset import main
    from tests.fixtures.generate_local_image_evaluation import generate_synthetic_dataset

    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    output_report = tmp_path / "sentinel_report.json"
    sentinel_bytes = b"ORIGINAL_SENTINEL_CONTENT_DO_NOT_CLOBBER_12345"

    # Define mock evaluation that creates the sentinel file at destination during evaluation
    real_evaluate = vid.evaluate_dataset

    def mocked_evaluate(manifest, dataset_root):
        output_report.write_bytes(sentinel_bytes)
        return real_evaluate(manifest, dataset_root)

    monkeypatch.setattr(vid, "evaluate_dataset", mocked_evaluate)
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(output_report)],
    )

    rc = main()
    assert rc == 1, "Must exit with nonzero exit code when destination exists without --overwrite"
    # Verify sentinel remains byte-identical
    assert output_report.read_bytes() == sentinel_bytes, "Sentinel file must remain unmodified"
    # Verify no temporary files remain in directory
    temp_files = list(tmp_path.glob(".tmp_*"))
    assert temp_files == [], f"Temporary files must be cleaned up: {temp_files}"
    captured = capsys.readouterr()
    assert "already exists. Use --overwrite to replace it." in captured.err


def test_error_sanitizer_slash_backslash_spaces_unc_and_mnt(tmp_path: Path) -> None:
    """Verifies that sanitize_error_message redacts Windows paths with spaces/slashes, UNC paths, and /mnt paths."""
    from tests.vision_inspection_dataset import sanitize_error_message

    test_cases = [
        ("Windows forward slash with spaces", "Failed at C:/Users/Kee Chun Shang/private/model.png: error", "Kee Chun Shang"),
        ("Windows forward slash without spaces", "Failed at C:/private/model/file: error", "C:/private"),
        ("Windows backslash with spaces", r"Failed at C:\Users\Kee Chun Shang\private.txt: error", "Kee Chun Shang"),
        ("Windows backslash without spaces", r"Failed at D:\Confidential\Dataset\img.png: error", "Confidential"),
        ("UNC double backslash", r"Network error: \\server\share\private.png: failed", "server"),
        ("UNC double forward slash", "Network error: //server/share/file: failed", "server"),
        ("POSIX /mnt path", "Mounted filesystem error: /mnt/private/file: unreadable", "/mnt/private"),
        ("Unix standard /home path", "Filesystem error: /home/secret_engineer/data.bin: unreadable", "secret_engineer"),
    ]

    for label, raw_err, private_fragment in test_cases:
        clean = sanitize_error_message(raw_err, tmp_path)
        assert private_fragment not in clean, f"[{label}] Leaked private fragment '{private_fragment}' in '{clean}'"
        assert "<redacted_path>" in clean, f"[{label}] Expected <redacted_path> in '{clean}'"


@pytest.mark.parametrize(
    "bad_path,private_fragment",
    [
        ("C:/private/model/file.png", "C:/private/model/file.png"),
        ("C:/Users/Kee Chun Shang/private/model.png", "Kee Chun Shang"),
        (r"C:\Users\Kee Chun Shang\private.txt", "Kee Chun Shang"),
        (r"\\server\share\private.png", "server"),
        ("//server/share/file.png", "server"),
        ("/mnt/private/file.png", "/mnt/private/file.png"),
    ],
)
def test_schema_rejection_suppresses_private_paths(
    tmp_path: Path, bad_path: str, private_fragment: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies that schema validation rejects absolute/UNC/mnt paths without leaking raw path inputs into stderr."""
    from tests.vision_inspection_dataset import main

    profile = {
        "mode": "PROCESS_LIMITS",
        "rois": [{"roi_id": "r1", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}],
    }
    manifest_data = {
        "manifest_version": "v1",
        "dataset_id": "private_path_test",
        "origin": "synthetic",
        "cases": [
            {
                "case_id": "case_priv",
                "current_image_path": bad_path,
                "profile": profile,
            }
        ],
    }
    mpath = tmp_path / "private_manifest.json"
    mpath.write_text(json.dumps(manifest_data), encoding="utf-8")
    rpath = tmp_path / "report.json"

    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(mpath), "-o", str(rpath)],
    )
    rc = main()
    assert rc == 1
    assert not rpath.exists()

    captured = capsys.readouterr()
    assert private_fragment not in captured.err, f"Private fragment '{private_fragment}' leaked in stderr:\n{captured.err}"
    assert "Manifest schema validation failed" in captured.err
    assert "current_image_path must be a relative path" in captured.err


def test_preflight_oserror_suppresses_private_paths_and_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies that CLI path preflight catching an OSError returns exit 1 without leaking host paths or traceback."""
    from tests.vision_inspection_dataset import main

    private_dir = r"C:\Users\Kee Chun Shang\TopSecret"

    def mock_resolve(self):
        raise OSError(13, f"Permission denied: '{private_dir}'")

    monkeypatch.setattr(Path, "resolve", mock_resolve)
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", "any_manifest.json", "-o", "any_report.json"],
    )

    rc = main()
    assert rc == 1
    captured = capsys.readouterr()
    assert private_dir not in captured.err
    assert "Traceback" not in captured.err
    assert "Fatal error: Filesystem access error occurred during CLI path preflight" in captured.err


def test_per_case_oserror_suppresses_private_paths_in_report_and_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verifies that per-case filesystem access errors suppress private host paths in report JSON and warnings."""
    from tests.vision_inspection_dataset import main
    from tests.fixtures.generate_local_image_evaluation import generate_synthetic_dataset

    manifest_path = generate_synthetic_dataset(output_dir=tmp_path)
    output_report = tmp_path / "error_report.json"
    private_path = r"C:\Users\Kee Chun Shang\Confidential\image.png"

    # Mock Path.read_bytes to raise PermissionError with private path on case 1
    real_read_bytes = Path.read_bytes

    def mock_read_bytes(self):
        if "case_01" in str(self):
            raise PermissionError(13, f"Access is denied: '{private_path}'")
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", mock_read_bytes)
    monkeypatch.setattr(
        "sys.argv",
        ["vision_inspection_dataset", "-m", str(manifest_path), "-o", str(output_report)],
    )

    rc = main()
    assert rc == 0, "Evaluation should complete with per-case error recorded."
    assert output_report.exists()

    report_text = output_report.read_text(encoding="utf-8")
    report = json.loads(report_text)

    # Assert private path is absent from the entire serialized report JSON
    assert private_path not in report_text
    assert "Kee Chun Shang" not in report_text

    # Check case 1 error details
    c1 = next(c for c in report["cases"] if c["case_id"] == "case_01_clean_detected")
    assert c1["status"] == "ERROR"
    assert c1["error"]["category"] == "FILESYSTEM_ACCESS"
    assert c1["error"]["type"] == "PermissionError"
    assert "Filesystem access error" in c1["error"]["message"]
    assert private_path not in c1["error"]["message"]

    captured = capsys.readouterr()
    assert private_path not in captured.out
    assert private_path not in captured.err
