---
task_id: DLK-M3-042
reviewed_commit: bc83079767925dc390e0e706cd4ab56077b9306c
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-042

## Decision and evidence

Changes requested. The four new integration scenarios meaningfully exercise the public image API, durable case lifecycle and reports, and conservative quality gates. No production code changed. Gemini reports 4 focused tests and 605 full backend tests passing, plus the synthetic baseline. Reviewer inspected source and reported evidence; did not rerun tests or browser execution under the planner/reviewer policy.

## R1 — P2: Make the multi-site browser rehearsal reproducible and demonstrate it

`docs/demo/region-inspection-acceptance.md:75-110` does not provide sample generation steps, deposit sizes, or the two expected ROI configurations. It describes a multi-deposit upload but only names `dot-1`; the implementation report records one polygon and does not demonstrate selecting two distinct sites or preserving both from browser intake. This leaves the integrated multi-site frontend-to-case boundary unproven by the reported browser run. Automated API coverage is useful but does not establish what the frontend submits.

Provide a self-contained PowerShell-compatible sample-generation command using existing fixtures, exact dimensions/deposit radii, two normalized ROI rectangles, explicit limits, and the actual UI steps to create them. Scenario A's 400x200 image, radii 10 and 15, left/right half ROIs and min coverage 0.10 are a suitable starting point. Configure before Analyze; explain that adding/deleting ROIs clears evidence and requires analysis again before Start Diagnosis. Perform the real two-site browser flow, select both sites and record distinct measurements, then verify both affected IDs and snapshots in the created/reloaded case and JSON/PDF report. Record actual site IDs, case ID, environment and artifact paths. Do not promise a fixed ranking or exact zero geometric drift without measurements. Update readiness claims to match the evidence.

## R2 — P2: Correct persistence and PDF-verification claims

`docs/demo/region-inspection-acceptance.md:140-143` incorrectly says normalized geometries and contours are stored. The generated evidence snapshots in `backend/app/services/vision/defect_classifier.py:56-75` retain scalar measurements; outlines are transient analysis-response data, not persisted by this workflow. Document persisted affected IDs, scalar snapshots and supplied limits separately from transient images/outlines; saved-image reconstruction is unavailable. At line 102, describe legacy fields as the first triggering/affected site's metadata, not necessarily the first configured ROI.

The PDF tooling paragraph implies manual visual inspection, while the implementation report only establishes downloaded bytes and pypdf text extraction. State visual PDF layout inspection is unverified unless it was actually performed and recorded. The task permits this disclosed limitation; do not install tooling or expand scope merely to remove it.

## Correction boundary

Continue DLK-M3-042; no new task packet or production changes. Update the guide, implementation report and affected readiness wording, record the missing browser evidence, and commit locally with this review record. Preserve existing development records and unrelated files. No push, PR or merge. Documentation-only corrections do not require repeating the full backend suite; rerun affected checks if test code changes.
