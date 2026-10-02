# Portable Region Layouts: Workflow and File Contract

- **Task**: DLK-M3-046
- **Status**: Implemented (Pending Review)
- **Schema Format**: `dispense-region-layout` (Version 1)

---

## 1. Overview and Scope Boundaries

Portable region layouts allow technicians to export defined target inspection regions from an image in the Dispense Lens workbench and load them onto another image of the same or similar product.

### Scope Guarantees
- **Geometry-Only Reuse**: Portable layouts store only normalized region geometry (`x`, `y`, `width`, `height`), region IDs, layout name, and source image pixel dimensions.
- **No Confidential Leakage**: Layout files **never** export or import raw images, URLs, filesystem paths, scale calibration (`mm_per_pixel`), process limit thresholds, reference images, analysis outcomes, or defect observations.
- **No Shared Storage**: Import and export operate entirely client-side via explicit local JSON file downloads and uploads. No database persistence, IndexedDB, or localStorage is used.
- **No Automatic Alignment or Registration**: Loaded coordinates map normalized rectangles directly onto the target image. The system does not attempt automatic computer vision registration, feature matching, or rotation.
- **Mandatory Placement Confirmation**: All analysis execution paths (UI buttons and programmatic dispatches) are strictly blocked until a technician inspects the region placement on the target image and clicks **Confirm region placement**.

---

## 2. File Format Specification

Portable layout files must adhere strictly to the JSON schema below. Unknown properties at the root or nested levels are rejected.

### Example File (`dispense-region-layout.json`)

```json
{
  "format": "dispense-region-layout",
  "version": 1,
  "name": "Two-site top-down layout",
  "source_image": {
    "width": 1920,
    "height": 1080
  },
  "rois": [
    {
      "roi_id": "dot-1",
      "x": 0.15,
      "y: 0.20,
      "width": 0.30,
      "height": 0.30
    },
    {
      "roi_id": "dot-2",
      "x": 0.55,
      "y": 0.20,
      "width": 0.30,
      "height": 0.30
    }
  ]
}
```

### Schema Rules and Invariants

| Field | Type | Rules & Validation Invariants |
|---|---|---|
| `format` | string | Exact string literal: `"dispense-region-layout"`. |
| `version` | integer | Exact integer: `1`. No silent upgrade or downgrade. |
| `name` | string | 1 to 100 characters, trimmed, non-blank, no ASCII control characters (`\x00-\x1F`, `\x7F`). Rendered safely as text, never HTML. |
| `source_image` | object | Must contain only `width` and `height`. No extraneous keys. |
| `source_image.width` | integer | Positive safe integer (`> 0`). |
| `source_image.height` | integer | Positive safe integer (`> 0`). |
| `rois` | array | 1 to 100 region objects. Array order is preserved exactly. |
| `rois[i].roi_id` | string | 1 to 100 characters, trimmed, non-blank, no control characters. Must not have leading/trailing whitespace. Must be unique within the file. |
| `rois[i].x`, `rois[i].y` | number | Finite JSON numbers within `[0.0, 1.0]`. |
| `rois[i].width`, `rois[i].height` | number | Finite JSON numbers within `(0.0, 1.0]`. |
| Extents (`x + width`, `y + height`) | number | Must not exceed `1.00001` (standard image boundary tolerance). |

### File Size Limit
The maximum allowed file payload is **256 KiB** (262,144 bytes UTF-8). Files exceeding this limit are rejected before parsing.

---

## 3. Technician Workflow

### 3.1 Saving a Layout
1. In either the inline image card or the Computer Vision Defect Studio, configure target ROIs on an uploaded image.
2. Click **Save layout**. (Disabled if no ROIs are drawn, or if image preview dimensions have not loaded).
3. In the save dialog, review the source dimensions and number of regions, and optionally edit the layout name (defaulting to `<image-filename> layout`).
4. Click **Save & Download JSON**. The browser downloads `dispense-region-layout.json`.
5. Saving a layout has no side effects on the current upload's state, configuration, or analysis readiness.

### 3.2 Loading a Layout
1. On any target upload, click **Load layout** and select a valid `.json` layout file from local disk.
2. The file is validated pure client-side against the v1 specification.
3. Upon successful import:
   - The upload's ROIs are replaced with the imported regions.
   - Any prior analysis results, error messages, and emitted diagnostic evidence for that upload are cleared immediately.
   - Any in-flight analysis request for that upload is aborted.
   - The upload's configuration revision is bumped.
   - Placement confirmation is set to **unconfirmed**.
   - Current image, analysis mode (`FEATURES_ONLY`, `PROCESS_LIMITS`, `REFERENCE_IMAGE`), scale calibration (`mm_per_pixel`), process limits, and reference image are preserved unchanged.

### 3.3 Inspecting Placement and Confirming
1. A persistent pending-confirmation banner appears above the image canvas in both inline and Studio views.
2. The banner displays:
   - Layout name and region count.
   - Layout source dimensions vs. target image dimensions.
   - **Dimension Mismatch Warning**: If target dimensions differ from layout source dimensions, an explicit warning explains that normalized coordinates are mapped to the target aspect ratio, and reminds the technician that matching dimensions alone do not guarantee part alignment.
   - If target image dimensions are unreadable, confirmation is blocked.
3. **Safety Checklist**: The technician is instructed to:
   - Check physical product orientation and camera framing.
   - Verify every expected dispense site is enclosed by its corresponding target box.
   - In `REFERENCE_IMAGE` mode, verify that the reference image corresponds correctly to the part and layout.
   - Separately review preserved scale calibration, process limits, and tolerances.
4. Technicians may drag or adjust ROIs in the canvas prior to confirmation.
5. Click **Confirm region placement**. This unlocks the **Analyze** button.
   - *Confirmation certifies positioning only*; it does not certify product pass/fail or determine defect root causes.

### 3.4 Invalidation Rules
Confirmation belongs strictly to the upload and its current geometry revision:
- **Editing ROIs**: Moving, resizing, adding, or deleting an ROI resets confirmation to `false` and invalidates any completed analysis.
- **Reference Image Changes**: In `REFERENCE_IMAGE` mode, changing or replacing the reference image invalidates confirmation.
- **Loading Another Layout**: Replaces geometry and resets confirmation to `false`.
- **Switching Views**: Toggling between inline and Studio views, expanding/collapsing cards, or selecting individual ROIs does **not** invalidate confirmation.
- **New Images**: New image uploads never inherit confirmation from other uploads.

### 3.5 Manual Fallback and Abandoning Layout
Technicians can abandon an imported layout at any time:
- Click **Abandon & Draw Manually** in the confirmation banner, or click **Reset ROIs** / clear all regions.
- This clears the imported layout metadata, removes the confirmation gate, and allows drawing regions manually.
- Manual-only workflows (where no imported layout is present) remain fully functional without any confirmation requirement.

---

## 4. Verification and Conformance

The implementation is verified by automated deterministic regression suites:
- `frontend/scripts/test-region-layout.mjs`: Tests pure parser boundaries (0/100/101 ROIs, exact 256 KiB vs oversized, control characters, leading/trailing whitespace rejection on IDs, duplicate IDs, unknown keys, coordinate extents, and round-trip serialization fidelity).
- `frontend/scripts/test-image-upload-state.mjs`: Tests upload state machine transitions (pending/confirmed states, analysis gating, target dimension validation, ROI edit invalidation, reference image change invalidation, manual abandon fallback, stale analysis responses, and asynchronous file read races).
- `npm run lint` and `npm run build`: Zero errors, full TypeScript type safety, and zero added linter warnings.
