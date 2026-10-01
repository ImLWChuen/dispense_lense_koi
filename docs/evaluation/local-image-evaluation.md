# Local Image Dataset Evaluation Runbook and Worksheet

Date: 2026-10-01<br>
Task: `DLK-M3-044`<br>
Feature Branch: `backend-database`<br>
Scope: Offline, manifest-driven evaluation of team-supplied local image datasets using the Dispense Lens region inspection pipeline.

---

## 1. Scope and Objective

This runbook establishes a repeatable, offline, and secure procedure for evaluating local image sets against the Dispense Lens region inspection computer vision pipeline (`backend/app/api/images.py` `_sync_analyze_image`, `backend/app/services/vision/`).

It allows engineering and QA teams to inspect per-site results, measure status accuracy against caller-provided ground truth, track abstention and false-missing rates, and identify pipeline failures without running web servers, databases, or network connections.

> [!WARNING]
> **No Representative Dataset or Manufacturing Accuracy Claim:**
> The runner and synthetic examples provided in this milestone demonstrate **evaluation tooling and reporting integrity only**. No curated representative factory dataset or independently reviewed real-world ground-truth labels are provided in the repository. Synthetic benchmark results **do not** prove factory-line accuracy, sub-millimeter precision, or defect recall under variable industrial lighting, board warping, or translucent adhesives. Real-image accuracy benchmarks remain pending until a representative dataset with independent domain-expert adjudication is supplied.

---

## 2. Architecture & Data Contracts

### 2.1 Manifest v1 Specification

A dataset manifest is a versioned JSON file specifying the dataset metadata, origin, and evaluation cases.

| Field | Type | Required | Description |
|---|---|---|---|
| `manifest_version` | String | Yes | Must be `"v1"` or `"1.0"`. |
| `dataset_id` | String | Yes | Unique identifier for the dataset (e.g., `batch_20261001_lotA`). |
| `origin` | String | Yes | Classification: `"synthetic"` or `"real"`. Never mix origins in one manifest. |
| `description` | String | No | High-level summary of dataset contents and collection intent. |
| `label_provenance` | String / Dict | No | Overview of annotation protocol, annotators, and review status. |
| `cases` | Array[Case] | Yes | List of evaluation cases (minimum 1). |

Each entry in `cases` contains:

| Case Field | Type | Required | Description |
|---|---|---|---|
| `case_id` | String | Yes | Unique case ID within the manifest. |
| `description` | String | No | Human-readable case description. |
| `current_image_path` | String | Yes | Relative path to current inspection image from `dataset_root`. |
| `reference_image_path` | String | Optional | Relative path to reference image. Required when `profile.mode == "REFERENCE_IMAGE"`. |
| `profile` | Object | Yes | Standard `AnalysisProfile` object containing ROIs, process limits, or reference limits. |
| `expected_statuses` | Dict[str, str] | No | Optional map of `roi_id` to expected status (`DETECTED`, `MISSING`, `UNASSESSED`). Unmentioned ROIs are treated as unlabeled. |
| `label_provenance` | String / Dict | No | Provenance notes for this case's labels. |
| `notes` | String | No | Capture conditions, lighting, scale, or substrate details. |

### 2.2 Path Containment and Security

To protect host environments from arbitrary file access:
1. **Relative Paths Only:** `current_image_path` and `reference_image_path` must be strictly relative paths (no leading `/`, `\`, or drive letters).
2. **Directory Containment:** All image paths are resolved against `--dataset-root` (or the manifest's parent directory). Any attempt to escape the dataset root via traversal (`..`) is caught during preflight and triggers a fatal error (exit code 1).
3. **Payload Limits:** Decoded images must exist, be regular files, and not exceed the existing `MAX_FILE_SIZE_BYTES` (10 MB).
4. **Data Privacy & Path Sanitization:** Output reports record relative image paths only; host absolute paths, private directory identifiers, environment variables, and raw exception paths are suppressed and redacted (`<redacted_path>`).
5. **Protected Inputs & Atomic Replacement:** The output report path can never target the manifest or any current/reference source image (directly or via filesystem links/aliases), regardless of `--overwrite`. Reports are serialized and written atomically to a temporary file before replacement.

### 2.3 Output Report Schema v1

The runner outputs a single self-contained JSON report:
- `report_version`: `"v1"`
- `dataset_id`: Copied from manifest.
- `origin`: `"synthetic"` or `"real"`.
- `run_provenance`: Source commit hash (via `git rev-parse HEAD`), Python version, OpenCV version, Pydantic version, and UTC ISO timestamp.
- `summary`:
  - `case_counts`: Total, successful, failed cases, and unreviewed labeled cases count.
  - `site_counts`: Total sites, eligible labeled sites, unlabeled sites, emitted predictions, correct labeled sites, incorrect labeled sites.
  - `failure_accounting`: Failed cases count, failed-case sites count, failed-case labeled sites count, missing-output sites count, unlabeled sites count.
  - `status_accuracy`: Null if 0 labeled sites. If labeled sites exist: `{numerator, denominator, rate}` where denominator is all eligible labeled sites (failures are **not** dropped).
  - `abstention_rate`: `{numerator, denominator, rate}` computed over emitted predictions (`predicted_status == "UNASSESSED"`).
  - `false_missing_rate`: `{numerator, denominator, rate}` computed over known non-`MISSING` labels (`expected_status in ["DETECTED", "UNASSESSED"]` but `predicted_status == "MISSING"`).
  - `confusion_matrix`: 3x3 matrix across `DETECTED`, `MISSING`, and `UNASSESSED` for emitted labeled predictions.
  - `boundary_accuracy`: Explicitly recorded as `{"status": "not_evaluated", "reason": "External ground-truth masks or contours are not part of manifest v1."}`.
- `cases`: Detailed per-case execution records with elapsed execution time, analysis status, full `profile` (mode, ROI coordinates, scale, process/reference limits), case `notes`, safe relative image paths, `label_provenance` and `label_provenance_status` (`provided`, `inherited`, `unreviewed`, `unlabeled`), separate `current_coverage_ratio` and `current_inspection_coverage` (status, expected/assessed counts, unassessed/missing ROI IDs), separate `reference_coverage_ratio` and `reference_inspection_coverage`, per-site scalar measurements, and sanitized warnings/errors without host absolute paths.

---

## 3. CLI Reference & PowerShell Commands

### 3.1 Runner CLI (`backend/tests/vision_inspection_dataset.py`)

```powershell
# Display help and options
& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_dataset.py --help

# Basic execution against a local manifest
& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_dataset.py `
  --manifest scratch/eval_sample/manifest.json `
  --output scratch/eval_sample/report.json

# Explicit dataset root and overwrite authorization
& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_dataset.py `
  -m scratch/eval_sample/manifest.json `
  -d scratch/eval_sample `
  -o scratch/eval_sample/report.json `
  --overwrite
```

#### Exit Codes
- `0`: Evaluation completed successfully. The report was written to `--output` (including runs where individual cases experienced image decode/analysis errors).
- `1`: Fatal error. Manifest syntax/validation error, path traversal escape in manifest, protected input collision (manifest or source images), or report file already exists without `--overwrite`. No report is written.

### 3.2 Synthetic Dataset Generator (`backend/tests/fixtures/generate_local_image_evaluation.py`)

A helper script to generate standard synthetic image fixtures and manifests in a target directory:

```powershell
# Display generator help
& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_local_image_evaluation.py --help

# Generate standard 5-case synthetic dataset (includes 1 unlabeled site)
& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_local_image_evaluation.py `
  --output-dir scratch/eval_sample/standard

# Generate an all-unlabeled dataset (demonstrates null accuracy)
& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_local_image_evaluation.py `
  --output-dir scratch/eval_sample/unlabeled `
  --all-unlabeled

# Generate dataset including an intentionally corrupt image (demonstrates error containment)
& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_local_image_evaluation.py `
  --output-dir scratch/eval_sample/corrupt `
  --include-corrupt
```

---

## 4. Team Evaluation Protocol

When evaluating real-world factory images, the team must follow this standardized evaluation workflow:

```
[1. Secure Image Intake] ──> [2. Blind Annotation] ──> [3. Manifest Creation]
                                                               │
[6. Adjudication & Action] <── [5. Report Inspection] <── [4. Offline Execution]
```

### Step 1: Secure Image Intake
1. Store raw images in a dedicated local folder outside the git repository (e.g., `D:\Datasets\DispenseLens\Lot_20261001\`).
2. Never commit proprietary customer images, raw factory photographs, or secret production credentials to Git.
3. Record hardware setup: camera model, lens focal length, working distance, lighting modality (ring light, coaxial, diffuse backlight), and optical resolution ($\mu\text{m}/\text{px}$).

### Step 2: Blind Ground-Truth Annotation
1. Annotators must inspect raw images and record expected statuses **independently before viewing algorithm predictions**.
2. For each ROI, determine:
   - `DETECTED`: Clear deposit visible within target ROI meeting nominal process specifications.
   - `MISSING`: Target region is bare substrate with visible context/fiducials confirming absence.
   - `UNASSESSED`: Ambiguous contrast, foreign debris, lighting flare, or optical obstruction preventing trustworthy human confirmation.
3. Record notes if the deposit displays abnormal wetting, satellite droplets, or bubbles.

### Step 3: Manifest Creation
1. Define ROI normalized coordinates $[x, y, w, h] \in [0.0, 1.0]$.
2. Set appropriate `process_limits` (e.g., `min_coverage_ratio`, `max_overflow_ratio`).
3. Set `origin: "real"`.
4. Include `expected_statuses` and `label_provenance`.

### Step 4: Run Evaluation CLI
Execute `backend/tests/vision_inspection_dataset.py` with explicit `--output`.

### Step 5: Report Inspection & Adjudication
1. Check `summary.case_counts` for failed cases.
2. Check `summary.status_accuracy` and the 3x3 confusion matrix.
3. Filter cases where `status_match == false`.
4. Convene an adjudication review for each disagreement:
   - **Type A (Pipeline Flaw):** Algorithm failed (e.g., missed edge due to low contrast, false bubble detection). Log issue for future CV enhancement.
   - **Type B (Ambiguous Ground Truth):** Deposit morphology was borderline. Re-evaluate labeling criteria.
   - **Type C (Substrate/Lighting Anomaly):** Severe shadow or flare violated capture assumptions. Update capture instructions.

---

## 5. Evaluation Worksheet Template

Use this worksheet structure (in Markdown or spreadsheet form) to track real-image evaluation trials:

| Case ID | Image Path | Capture Notes (Light / Focus / Scale) | ROI ID | Expected Status | Annotator | Predicted Status | Match? | Adjudication Notes |
|---|---|---|---|---|---|---|---|---|
| `PCB-001` | `images/pcb_001.png` | Coaxial white LED, 50mm lens, 12.5 um/px | `dot-1` | `DETECTED` | Alice | `DETECTED` | Yes | Clean deposit centered. |
| `PCB-001` | `images/pcb_001.png` | Coaxial white LED, 50mm lens, 12.5 um/px | `dot-2` | `MISSING` | Alice | `MISSING` | Yes | Confirmed bare solder pad. |
| `PCB-002` | `images/pcb_002.png` | Ring light, slight glare on top-right pad | `dot-1` | `DETECTED` | Bob | `UNASSESSED` | No | Glare caused low segmentation quality (0.32); algorithm properly abstained. Re-shot with polarized filter. |
| `PCB-003` | `images/pcb_003.png` | Diffuse dome, calibrated 10.0 um/px | `dot-1` | `DETECTED` | Bob | `DETECTED` | Yes | Overflow 2.1% flagged by process limit. |

---

## 6. Unresolved Evaluation Decisions & Future Roadmap

The following capabilities are explicitly deferred and must not be assumed complete:
1. **Representative Factory Dataset:** Acquisition of an authorized, multi-vendor, multi-adhesive production dataset is pending partner agreement.
2. **External Boundary Mask Benchmark:** Manifest v1 evaluates discrete status classification and scalar limits. Pixel-level external contour/mask IoU requires external ground-truth annotation format v2 (deferred).
3. **Automated Registration / Alignment:** ROIs currently assume static or pre-aligned coordinates. Automated template fiducial alignment is tracked under the broader M3 roadmap.
4. **Scoring Model Calibration:** Region inspection outputs currently provide diagnostic observations; integration into formal composite risk scoring remains bounded by Milestone 3 gates.
