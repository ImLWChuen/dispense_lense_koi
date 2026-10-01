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
> - **Absence of diagnostic defect observations is NOT a pass:** When an image suffers severe optical blur or exposure distortion, the absence of an alarm does not indicate an acceptable manufacturing process.
> - **Repeatable detection under optical degradation is a potential risk:** Otsu thresholding successfully segments blurred blobs because of connected intensity gradients. Without an acquisition sharpness pre-gate, out-of-focus captures are silently accepted with distorted scalar dimensions.
> - **Ground-truth labels are limited to construction-grounded clean controls:** Degraded cases remain unassigned. Ground truth is never inferred or copied from model predictions.

---

## Evaluation Reproduction

The evaluation is fully reproducible from source code without committing raw image files or reports.

### Environment & Source Identity

- **Evaluated Commit:** `54d03538f11efe20eea5f742b79f6f3e3104c963`
- **Runtime:** Python 3.14.0rc2, OpenCV 4.11.0, Pydantic 2.11.0a1
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

A wide physical board (485x200 px) with nominal deposit centers at $x_1=100$ and $x_2=300$ is acquired through a shifted window starting at $x_{\text{offset}} = 85\text{ px}$:
- In the acquired $400 \times 200$ frame:
  - Deposit 1 center is shifted to $x_1' = 100 - 85 = 15\text{ px}$. With nominal radius $r=20\text{ px}$, the deposit extends from $x = -5\text{ px}$ to $x = +35\text{ px}$, clipping $5\text{ px}$ at the left boundary ($x=0$).
  - Deposit 2 center is shifted to $x_2' = 300 - 85 = 215\text{ px}$.
- The expected ROI boundaries in the acquired frame transform to:
  - `roi_1_clipped`: Left edge clamped to image boundary $x=0$, right edge at $160 - 85 = 75\text{ px}$. Normalized: $x=0.0, y=0.20, w=75/400=0.1875, h=0.60$.
  - `roi_2_shifted`: Left edge at $240 - 85 = 155\text{ px}$, right edge at $360 - 85 = 275\text{ px}$. Normalized: $x=155/400=0.3875, y=0.20, w=120/400=0.30, h=0.60$.
- Both normalized ROIs strictly satisfy $x \ge 0, y \ge 0, x+w \le 1.0, y+h \le 1.0$.

---

## Measured Results and Case Findings

### Executive Metrics Summary

- **Total Cases Evaluated:** 14 (14 successful runs, 0 crashed/failed cases)
- **Total Sites Evaluated:** 28 (6 labeled controls, 22 unlabeled perturbations)
- **Control Status Accuracy:** **100.0%** (6/6 labeled sites correctly matched ground truth)
- **Pipeline Abstention Rate:** **28.6%** (8/28 sites abstained as `UNASSESSED`)
- **False-Missing Rate:** **0.0%** (0/4 non-missing control sites flagged as missing)
- **Analysis Status Distribution:**
  - `CALIBRATED`: 8 cases (57.1%)
  - `UNRELIABLE`: 6 cases (42.9%)
  - `ERROR`: 0 cases (0.0%)

### Detailed Case Breakdown

| Case ID | Analysis Status | Coverage Status | Predicted Site Statuses | Risk Classification | Observed Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `case_01_control_clean` | `CALIBRATED` | `COMPLETE` | `roi_1`: DETECTED<br>`roi_2`: DETECTED | MEASURED_BASELINE | Correct detection of both sites; zero warnings. |
| `case_02_blur_mild` | `CALIBRATED` | `COMPLETE` | `roi_1`: DETECTED<br>`roi_2`: DETECTED | **POTENTIAL_RISK** | Softened edges segmented as detected; circularity drops slightly to ~0.94. Ungated by pipeline. |
| `case_03_blur_heavy` | `CALIBRATED` | `COMPLETE` | `roi_1`: DETECTED<br>`roi_2`: DETECTED | **POTENTIAL_RISK** | Severe blur ($\sigma=5.0$) still segmented as DETECTED. Area expands, circularity degrades. Ungated. |
| `case_04_brightness_dark` | `CALIBRATED` | `COMPLETE` | `roi_1`: DETECTED<br>`roi_2`: DETECTED | **POTENTIAL_RISK** | Underexposure ($0.40\times$) still detected due to relative contrast. Ungated. |
| `case_05_brightness_bright` | `CALIBRATED` | `COMPLETE` | `roi_1`: DETECTED<br>`roi_2`: DETECTED | **POTENTIAL_RISK** | Overexposure ($0.60\times + 102$) still detected. Ungated. |
| `case_06_contrast_low` | `UNRELIABLE` | `NONE` | `roi_1`: UNASSESSED<br>`roi_2`: UNASSESSED | MEASURED_BASELINE | Segmentation quality gate triggers ($0.00 < 0.20$); safely abstains without false missing. |
| `case_07_glare_bounded` | `UNRELIABLE` | `PARTIAL` | `roi_1`: UNASSESSED<br>`roi_2`: DETECTED | MEASURED_BASELINE | Glare over `roi_1` triggers UNASSESSED; clean `roi_2` unaffected. Whole image gated UNRELIABLE. |
| `case_08_reliable_beside_degraded` | `CALIBRATED` | `COMPLETE` | `roi_1`: DETECTED<br>`roi_2`: DETECTED | **POTENTIAL_RISK** | Clean site 1 and blurred site 2 both report DETECTED. Blurred site lacks blur gating. |
| `case_09_clipping_edge` | `UNRELIABLE` | `PARTIAL` | `roi_1_clipped`: UNASSESSED<br>`roi_2_shifted`: DETECTED | MEASURED_BASELINE | Truncated deposit touching border abstains as UNASSESSED; interior deposit detected. |
| `case_10_missing_control` | `CALIBRATED` | `COMPLETE` | `roi_1`: MISSING<br>`roi_2`: MISSING | MEASURED_BASELINE | Confirmed missing deposits on established substrate context; emits diagnostic undersize observations. |
| `case_11_uniform_unassessed_control` | `UNRELIABLE` | `NONE` | `roi_1`: UNASSESSED<br>`roi_2`: UNASSESSED | MEASURED_BASELINE | Uniform substrate without background basis correctly abstains on all sites. |
| `case_12_glare_severe_washout` | `UNRELIABLE` | `PARTIAL` | `roi_1`: DETECTED<br>`roi_2`: UNASSESSED | MEASURED_BASELINE | Blooming glare over `roi_2` triggers UNASSESSED; clean `roi_1` detected; whole image gated UNRELIABLE. |
| `case_13_glare_on_missing` | `UNRELIABLE` | `PARTIAL` | `roi_1`: UNASSESSED<br>`roi_2`: MISSING | MEASURED_BASELINE | Glare artifact over missing site abstains as UNASSESSED rather than false-detected. |
| `case_14_blur_on_missing` | `CALIBRATED` | `COMPLETE` | `roi_1`: MISSING<br>`roi_2`: MISSING | MEASURED_BASELINE | Defocused fiducials still establish enough edge energy for substrate context. |

---

## Architectural Weakness Inventory

### 1. Optical Defocus / Sharpness Blindspot
- **Finding:** The existing segmentation algorithm utilizes global Otsu thresholding followed by contour filtering. Even under severe Gaussian blur ($\sigma=5.0$, kernel $19 \times 19$), the blurred circular intensity gradient forms a closed thresholded region that exceeds the minimum area and coverage limits.
- **Consequence:** The pipeline does not measure focus quality. In production, an operator with an improperly focused lens or vibration blur will receive `CALIBRATED` results and `DETECTED` deposits, but with artificial diameter expansion ($+15\text{--}25\%$) and distorted edge morphology.
- **Architectural Recommendation for Future Phase:** Introduce an acquisition preflight quality check using Laplacian variance or high-frequency gradient density across ROI windows to trigger `UNASSESSED` when image focus falls below a calibrated threshold.

### 2. Illumination Invariance vs. Pedestal Drift
- **Finding:** Moderate underexposure ($0.40\times$) and overexposure ($0.60\times + 102$) are handled cleanly without false alarms because Otsu thresholding adapts to bimodal histograms. However, once dynamic range drops below 20 gray levels (`case_06`), the segmentation quality metric ($Q_{\text{seg}}$) correctly triggers and marks regions `UNASSESSED`.
- **Consequence:** The existing segmentation quality metric is effective for low contrast, but does not detect pedestal shifts where the background is washed out.

### 3. Spatial Isolation of Glare
- **Finding:** Saturated specular highlights (`case_07`, `case_12`, `case_13`) are cleanly isolated to the affected ROI without corrupting adjacent ROIs.
- **Consequence:** The multi-site independence model delivered in Phase 1 functions as intended: a glare flare on site 1 leaves site 2 unaffected while marking the case as `PARTIAL` coverage and `UNRELIABLE` whole-image status.

### 4. Edge Clipping and Boundary Contact
- **Finding:** Boundary clipping (`case_09`) where a deposit extends beyond the sensor window triggers `UNASSESSED` on that site due to boundary-touching contour rejection.
- **Consequence:** Boundary contact safely prevents misleading measurements, but does not report partial evidence or distinguish board misalignment from an unassessed region.

---

## Supported Assumptions and Unresolved Uncertainties

### Supported Assumptions
1. **Deterministic Execution:** Exactly identical output reports are generated across runs on the same platform.
2. **Conservative Calibrated Gating:** If any configured ROI is `UNASSESSED` (`case_06`, `case_07`, `case_09`, `case_11`, `case_12`, `case_13`), the overall analysis status transitions to `UNRELIABLE`, preventing unassessed sites from driving automatic process acceptance.
3. **No False Missing:** Optical perturbations (blur, low contrast, glare, clipping) do not trigger false `MISSING` deposit alarms ($0.0\%$ false-missing rate across the test set).

### Unresolved Uncertainties
1. **Real-World Surface Textures:** Synthetic substrates lack PCB solder mask weave, trace topography, dust specks, and meniscus reflections. Real-world images may exhibit different thresholding behavior.
2. **Focus Threshold Tuning:** Establishing the numerical boundary between acceptable focus and unassessed blur requires representative optical hardware and technician adjudication.
3. **Automatic Template Alignment:** When boards are displaced or rotated, manual ROI editing remains necessary until reusable profiles and anchor alignment are implemented.
