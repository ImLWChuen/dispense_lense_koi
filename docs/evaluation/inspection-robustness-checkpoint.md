# Inspection Robustness Checkpoint

## Objective and Scope

This document establishes a reproducible synthetic evaluation checkpoint measuring how the manual-region inspection pipeline responds to controlled acquisition degradation:
- Optical defocus (mild and severe Gaussian blur)
- Illumination shifts (underexposure, overexposure, and compressed low contrast)
- Specular glare (localized bounded spot and severe whole-frame blooming)
- Acquisition clipping (sensor translation with deposit truncated at the image border)
- Mixed conditions (reliable site beside severely blurred site, glare on missing substrate)
- Construction-grounded clean controls (detected, missing, and uniform unassessed)

> [!IMPORTANT]
> **Methodological Boundaries & Compliance Notice**
> - **Absence of diagnostic defect observations is NOT a pass:** When an image suffers optical blur or exposure distortion, the absence of an alarm indicates only that the pipeline either abstained or passed ungated; it does not indicate acceptable manufacturing quality.
> - **Detection under synthetic blur is an observed pipeline behavior:** Otsu thresholding segments blurred blobs because of connected intensity gradients. The observed behavior on synthetic images must be distinguished from production camera performance.
> - **Ground-truth labels are limited to construction-grounded clean controls:** Degraded cases remain unassigned. Ground truth is never inferred or copied from model predictions.

---

## Evaluation Reproduction and Provenance

The evaluation is fully reproducible from source code without committing raw image files or reports.

### Environment & Source Identity

- **Evaluated Codebase Commit:** `54d03538f11efe20eea5f742b79f6f3e3104c963` (accepted DLK-M3-044)
- **Evaluation Tooling Provenance:** Working tree uncommitted scripts (`backend/tests/fixtures/generate_inspection_robustness.py` and `backend/tests/inspection_robustness_summary.py`)
- **Runtime Environment:** Python 3.14.0, OpenCV 5.0.0, Pydantic 2.13.5 (recorded in evaluator `run_provenance`)
- **Platform:** Windows (PowerShell 7 / Windows Terminal)
- **Target Branch:** `backend-database`

### Reproduction Commands

```powershell
# 1. Deterministically generate 14-case synthetic dataset and manifest v1:
& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_inspection_robustness.py -o scratch/robustness_checkpoint --overwrite

# 2. Execute offline evaluation against the vision pipeline:
& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_dataset.py -m scratch/robustness_checkpoint/manifest.json -o scratch/robustness_checkpoint/report.json --overwrite

# 3. Generate structured Markdown summary:
& .\backend\.venv\Scripts\python.exe backend/tests/inspection_robustness_summary.py -m scratch/robustness_checkpoint/manifest.json -r scratch/robustness_checkpoint/report.json -o scratch/robustness_checkpoint/summary.md --overwrite
```

### Determinism Profile

- **Generated Inputs:** Dataset image files (`images/*.png`) and `manifest.json` are byte-identical across independent runs.
- **Evaluation Outputs:** Evaluator output report non-timing fields (statuses, metrics, measurements, confusion matrix, counts, warnings, observations) are strictly deterministic; execution timestamps (`run_provenance.timestamp`) and elapsed timings (`elapsed_seconds`, `total_elapsed_seconds`) vary by run.

### Representative Fixture Visual Inspection

Representative synthetic fixture images were visually inspected in the scratch generation directory using image inspection tooling:
- `scratch/robustness_checkpoint/images/case_01_control_clean.png`: Two high-contrast dark circular deposits (radius 20 px, gray level 30) centered at nominal coordinates (100, 100) and (300, 100) on a bright uniform substrate (gray level 245).
- `scratch/robustness_checkpoint/images/case_02_blur_mild.png`: Mild Gaussian blur (kernel $5 \times 5, \sigma=1.5$); deposits exhibit slightly softened boundary gradients with dark cores preserved.
- `scratch/robustness_checkpoint/images/case_03_blur_heavy.png`: Severe Gaussian blur (kernel $19 \times 19, \sigma=5.0$); diffuse boundaries extending into substrate with reduced peak intensity gradient.
- `scratch/robustness_checkpoint/images/case_07_glare_bounded.png`: Saturated white specular spot (radius 25 px, intensity 255) directly masking the left deposit (`roi_1`), while the right deposit (`roi_2`) remains unaffected.
- `scratch/robustness_checkpoint/images/case_09_clipping_edge.png`: Translated frame ($dx = +85\text{ px}$); left deposit is truncated at the left image border ($x=0$, 5 px clipped), while the right deposit is shifted inward to $x=215\text{ px}$.

---

## Dataset Matrix Specification

All images are generated at nominal resolution `400 x 200` pixels with 3 color channels (8-bit sRGB). Two expected sites (`roi_1` and `roi_2`) are configured with illustrative synthetic limits (`min_coverage_ratio = 0.05`, `max_coverage_ratio = 0.50`, `min_circularity = 0.70`).

| Case ID | Perturbation Description | Transformation Details | ROIs | Expected Status |
| :--- | :--- | :--- | :--- | :--- |
| `case_01_control_clean` | Clean baseline control | Crisp circular deposits (radius 20 px, color 30) on substrate (color 245) | `roi_1`, `roi_2` nominal | `roi_1`: DETECTED<br>`roi_2`: DETECTED |
| `case_02_blur_mild` | Mild optical defocus | Gaussian blur kernel (5x5, $\sigma=1.5$) | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_03_blur_heavy` | Severe optical defocus | Gaussian blur kernel (19x19, $\sigma=5.0$) | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_04_brightness_dark` | Underexposure | Luminance scaling: $\text{img} \times 0.40$ (substrate ~98, deposit ~12) | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_05_brightness_bright` | Overexposure | Pedestal shift: $\text{img} \times 0.60 + 102$ (substrate ~249, deposit ~120) | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_06_contrast_low` | Low contrast | Compressed range: substrate 140, deposit 125 ($\Delta = 15$ gray levels) | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_07_glare_bounded` | Bounded specular glare | Saturated white disc (radius 25 px, color 255) over `roi_1` | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_08_reliable_beside_degraded` | Mixed clean / blur | `roi_1` crisp clean baseline; `roi_2` Gaussian blur (17x17, $\sigma=4.5$) | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_09_clipping_edge` | Boundary truncation | Sensor translation $dx = +85\text{ px}$. Left deposit shifted to $x=15\text{ px}$ | `roi_1_clipped`, `roi_2_shifted` | *Unassigned* |
| `case_10_missing_control` | Clean missing control | Bare substrate with 6 perimeter fiducials, empty ROIs | `roi_1`, `roi_2` nominal | `roi_1`: MISSING<br>`roi_2`: MISSING |
| `case_11_uniform_unassessed_control` | Uniform unassessed control | Featureless gray canvas (128) without substrate fiducials | `roi_1`, `roi_2` nominal | `roi_1`: UNASSESSED<br>`roi_2`: UNASSESSED |
| `case_12_glare_severe_washout` | Severe glare blooming | Saturated ellipse ($r_x=120, r_y=80$, color 255) over right board half | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_13_glare_on_missing` | Glare on missing site | Substrate with fiducials, empty sites, glare spot (radius 18 px) on `roi_1` | `roi_1`, `roi_2` nominal | *Unassigned* |
| `case_14_blur_on_missing` | Blur on missing site | Substrate with fiducials blurred with Gaussian filter (21x21, $\sigma=6.0$) | `roi_1`, `roi_2` nominal | *Unassigned* |

### Acquisition Coordinate Transformation for Case 09 (Edge Clipping)

A wide physical board ($485 \times 200\text{ px}$) with nominal deposit centers at $x_1=100$ and $x_2=300$ is acquired through a shifted window starting at $x_{\text{offset}} = 85\text{ px}$:
- In the acquired $400 \times 200$ frame:
  - Deposit 1 center is shifted to $x_1' = 100 - 85 = 15\text{ px}$. With nominal radius $r=20\text{ px}$, the deposit extends from $x = -5\text{ px}$ to $x = +35\text{ px}$, clipping $5\text{ px}$ at the left boundary ($x=0$).
  - Deposit 2 center is shifted to $x_2' = 300 - 85 = 215\text{ px}$.
- The expected ROI boundaries in the acquired frame transform to:
  - `roi_1_clipped`: Left edge clamped to image boundary $x=0$, right edge at $160 - 85 = 75\text{ px}$. Normalized: $x=0.0, y=0.20, w=75/400=0.1875, h=0.60$.
  - `roi_2_shifted`: Left edge at $240 - 85 = 155\text{ px}$, right edge at $360 - 85 = 275\text{ px}$. Normalized: $x=155/400=0.3875, y=0.20, w=120/400=0.30, h=0.60$.
- Both normalized ROIs strictly satisfy $x \ge 0, y \ge 0, x+w \le 1.0, y+h \le 1.0$.

---

## Measured Results and Reconciled Data

### Executive Metrics

- **Total Cases Evaluated:** 14 (14 successful runs, 0 crashed/failed cases)
- **Total Sites Evaluated:** 28 (6 labeled control sites, 22 unlabeled perturbation sites)
- **Control Status Accuracy:** **100.0%** (6/6 labeled sites correctly matched ground truth: 2 detected in case 01, 2 missing in case 10, 2 unassessed in case 11)
- **Pipeline Abstention Rate:** **28.6%** (8/28 total sites flagged `UNASSESSED` by quality gates)
- **False-Missing Rate (Controls Only):** **0.0%** (0/4 non-missing labeled control sites misclassified as MISSING; note this evaluates only the 4 non-missing labeled control sites, not unlabeled perturbations)
- **Analysis Status Distribution:**
  - `CALIBRATED`: 8 cases (57.1%)
  - `UNRELIABLE`: 6 cases (42.9%)
  - `ERROR`: 0 cases (0.0%)

### Measured Scalar Metrics on Blur Cases vs. Baseline Control

Derived measurements from evaluation report:
- **Baseline Control (`case_01_control_clean`):**
  - Equivalent diameter: $39.94\text{ px}$
  - Deposit area: $1253.0\text{ px}^2$
  - Circularity: $0.9526$
  - Segmentation quality: $1.0000$
- **Mild Optical Defocus (`case_02_blur_mild`, $5 \times 5, \sigma=1.5$):**
  - Equivalent diameter: $39.94\text{ px}$ ($0.0\%$ change vs. baseline)
  - Deposit area: $1253.0\text{ px}^2$ ($0.0\%$ change vs. baseline)
  - Circularity: $0.9526$ (identical to baseline)
  - Segmentation quality: $1.0000$
- **Severe Optical Defocus (`case_03_blur_heavy`, $19 \times 19, \sigma=5.0$):**
  - Equivalent diameter: $41.38\text{ px}$ (increase of $+1.44\text{ px}$ or $+3.61\%$ vs. baseline $39.94\text{ px}$)
  - Deposit area: $1345.0\text{ px}^2$ (increase of $+92.0\text{ px}^2$ or $+7.34\%$ vs. baseline $1253.0\text{ px}^2$)
  - Circularity: $0.9381$ (slight degradation of $-0.0145$ vs. baseline $0.9526$)
  - Segmentation quality: $1.0000$

### Detailed Per-Case Findings

| Case ID | Perturbation | Status | Sites (Assessed/Exp) | Current Cov | Ref Cov | Site Statuses & Warnings | Emitted Observations | Finding Classification | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `case_01_control_clean` | Clean baseline control | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: DETECTED<br>`roi_2`: DETECTED | None | MEASURED_BASELINE | All 2 labeled control site(s) matched ground truth. |
| `case_02_blur_mild` | Mild optical defocus | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: DETECTED<br>`roi_2`: DETECTED | None | **POTENTIAL_RISK** | Unlabeled perturbation produced DETECTED (CALIBRATED) without warnings; requires review against domain expectations. |
| `case_03_blur_heavy` | Severe optical defocus | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: DETECTED<br>`roi_2`: DETECTED | None | **POTENTIAL_RISK** | Unlabeled perturbation produced DETECTED (CALIBRATED) without warnings; requires review against domain expectations. |
| `case_04_brightness_dark` | Underexposure | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: DETECTED<br>`roi_2`: DETECTED | None | **POTENTIAL_RISK** | Unlabeled perturbation produced DETECTED (CALIBRATED) without warnings; requires review against domain expectations. |
| `case_05_brightness_bright` | Overexposure | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: DETECTED<br>`roi_2`: DETECTED | None | **POTENTIAL_RISK** | Unlabeled perturbation produced DETECTED (CALIBRATED) without warnings; requires review against domain expectations. |
| `case_06_contrast_low` | Low contrast | `UNRELIABLE` | 0/2 | `NONE` | N/A | `roi_1`: UNASSESSED (warnings: Low contrast ambiguous segmentation.; ROI 'roi_1' segmentation quality (0.30) is below reliable threshold.)<br>`roi_2`: UNASSESSED (warnings: Low contrast ambiguous segmentation.; ROI 'roi_2' segmentation quality (0.30) is below reliable threshold.) | None | MEASURED_BASELINE | Unlabeled perturbation triggered UNRELIABLE (2/2 sites UNASSESSED); requires review. |
| `case_07_glare_bounded` | Bounded specular glare spot covering roi_1 | `UNRELIABLE` | 1/2 | `PARTIAL` | N/A | `roi_1`: UNASSESSED (warnings: Low contrast ambiguous segmentation.; ROI 'roi_1' segmentation quality (0.20) is below reliable threshold.)<br>`roi_2`: DETECTED | None | MEASURED_BASELINE | Unlabeled perturbation triggered UNRELIABLE (1/2 sites UNASSESSED); requires review. |
| `case_08_reliable_beside_degraded` | Mixed clean / blur acquisition | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: DETECTED<br>`roi_2`: DETECTED | None | **POTENTIAL_RISK** | Unlabeled perturbation produced DETECTED (CALIBRATED) without warnings; requires review against domain expectations. |
| `case_09_clipping_edge` | Edge clipping at window boundary | `UNRELIABLE` | 1/2 | `PARTIAL` | N/A | `roi_1_clipped`: UNASSESSED (warnings: Candidate is clipped by window boundary or border-dominant.; ROI 'roi_1_clipped' segmentation quality (0.30) is below reliable threshold.)<br>`roi_2_shifted`: DETECTED | None | MEASURED_BASELINE | Unlabeled perturbation triggered UNRELIABLE (1/2 sites UNASSESSED); requires review. |
| `case_10_missing_control` | Clean baseline control for missing deposits | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: MISSING (warnings: No deposit detected inside target ROI; established background indicates missing deposit.)<br>`roi_2`: MISSING (warnings: No deposit detected inside target ROI; established background indicates missing deposit.) | deposit_size:undersized (affected: ['roi_1', 'roi_2'])<br>deposit_shape:abnormal (affected: ['roi_1', 'roi_2']) | MEASURED_BASELINE | All 2 labeled control site(s) matched ground truth. |
| `case_11_uniform_unassessed_control` | Clean baseline control for uniform input | `UNRELIABLE` | 0/2 | `NONE` | N/A | `roi_1`: UNASSESSED (warnings: Target and surroundings are both uniform; cannot establish background or missing deposit without reference.; ROI 'roi_1' segmentation quality (0.00) is below reliable threshold.)<br>`roi_2`: UNASSESSED (warnings: Target and surroundings are both uniform; cannot establish background or missing deposit without reference.; ROI 'roi_2' segmentation quality (0.00) is below reliable threshold.) | None | MEASURED_BASELINE | All 2 labeled control site(s) matched ground truth. |
| `case_12_glare_severe_washout` | Severe glare blooming over right board | `UNRELIABLE` | 1/2 | `PARTIAL` | N/A | `roi_1`: DETECTED<br>`roi_2`: UNASSESSED (warnings: Low target contrast against ambiguous background; polarity/background cannot be distinguished.; ROI 'roi_2' segmentation quality (0.00) is below reliable threshold.) | None | MEASURED_BASELINE | Unlabeled perturbation triggered UNRELIABLE (1/2 sites UNASSESSED); requires review. |
| `case_13_glare_on_missing` | Glare spot over missing site | `UNRELIABLE` | 1/2 | `PARTIAL` | N/A | `roi_1`: UNASSESSED (warnings: Segmentation mask is background-dominant (covers > 90% of window).; ROI 'roi_1' segmentation quality (0.20) is below reliable threshold.)<br>`roi_2`: MISSING (warnings: No deposit detected inside target ROI; established background indicates missing deposit.) | None | MEASURED_BASELINE | Unlabeled perturbation triggered UNRELIABLE (1/2 sites UNASSESSED); requires review. |
| `case_14_blur_on_missing` | Blur on missing site substrate | `CALIBRATED` | 2/2 | `COMPLETE` | N/A | `roi_1`: MISSING (warnings: No deposit detected inside target ROI; established background indicates missing deposit.)<br>`roi_2`: MISSING (warnings: No deposit detected inside target ROI; established background indicates missing deposit.) | deposit_size:undersized (affected: ['roi_1', 'roi_2'])<br>deposit_shape:abnormal (affected: ['roi_1', 'roi_2']) | **POTENTIAL_RISK** | Unlabeled perturbation produced MISSING on 2/2 sites; requires review. |

---

## Architectural Findings and Engineering Implications

### 1. Optical Defocus and Pipeline Response
- **Measured Finding:** In both mild Gaussian blur ($5 \times 5, \sigma=1.5$) and severe Gaussian blur ($19 \times 19, \sigma=5.0$), Otsu thresholding successfully segments the deposit. For mild blur, the resulting binarized mask produces metrics identical to the baseline ($39.94\text{ px}$ diameter). For heavy blur, intensity gradient spreading causes a measured $+3.61\%$ equivalent diameter expansion ($41.38\text{ px}$) and $+7.34\%$ area expansion ($1345.0\text{ px}^2$), with a slight circularity decrease ($0.9381$). Both cases report `DETECTED` without quality warnings.
- **Engineering Hypothesis vs. Proven Need:** The pipeline currently lacks a high-frequency sharpness pre-gate (e.g., Laplacian variance). In factory deployment, optical defocus from lens misalignment or mechanical vibration could pass undetected while introducing subtle dimensional inflation. However, whether an explicit focus gate is necessary in practice remains an engineering hypothesis that requires validation against representative optical hardware and technician ground truth, rather than an architectural change based solely on synthetic Gaussian blur.

### 2. Illumination Invariance vs. Low Dynamic Range
- **Measured Finding:** Both underexposure ($0.40\times$) and overexposure ($0.60\times + 102$) are handled cleanly without warnings because global Otsu thresholding adapts to bimodal distributions. When dynamic range is compressed to $\Delta = 15$ gray levels (`case_06_contrast_low`), the segmentation quality metric drops to $0.30$ (triggering low-contrast warnings and flagging both regions `UNASSESSED`), gating the whole image to `UNRELIABLE`.
- **Engineering Implication:** The existing segmentation quality metric operates as intended to reject low-contrast ambiguous captures, but does not measure raw illumination drift or background pedestal washout.

### 3. Spatial Isolation of Glare
- **Measured Finding:** Saturated specular highlights (`case_07`, `case_12`, `case_13`) trigger `UNASSESSED` exclusively on the affected ROI without corrupting adjacent ROIs.
- **Engineering Implication:** Multi-site independent reliability operates conservatively: a glare flare on site 1 leaves site 2 unaffected while setting whole-image coverage to `PARTIAL` and status to `UNRELIABLE`.

### 4. Edge Clipping and Boundary Contact
- **Measured Finding:** Boundary contact contour rejection in `case_09_clipping_edge` triggers `UNASSESSED` on the truncated deposit while the shifted interior deposit remains `DETECTED`.
- **Engineering Implication:** Boundary contact safely prevents inaccurate measurements on truncated deposits, but does not provide partial geometry evidence or distinguish framing displacement from deposit defects.

---

## Supported Assumptions and Unresolved Uncertainties

### Supported Assumptions
1. **Deterministic Pipeline Outputs:** Aside from run timestamps and execution timings, all pipeline outputs (statuses, metrics, measurements, counts, warnings, observations) are strictly deterministic across runs on the same platform.
2. **Conservative Calibrated Gating:** If any configured ROI is `UNASSESSED`, the overall analysis status transitions to `UNRELIABLE`, preventing unassessed sites from driving automatic process acceptance.
3. **Control Status Accuracy:** Labeled baseline controls achieve 100.0% status agreement (6/6 sites) with zero false-missing classifications (0/4 non-missing control sites misclassified).

### Unresolved Uncertainties
1. **Real-World Surface Textures:** Synthetic substrates lack PCB solder mask weave, trace topography, dust specks, and meniscus reflections. Real-world captures may exhibit different thresholding and quality score distributions.
2. **Focus Gating Necessity:** Determining whether an acquisition sharpness check is required in production requires representative optical hardware images and technician adjudication.
3. **Automatic Template Alignment:** When boards are displaced or rotated, manual ROI editing remains necessary until reusable profiles and anchor alignment are implemented.
