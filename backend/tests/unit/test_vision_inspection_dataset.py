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
