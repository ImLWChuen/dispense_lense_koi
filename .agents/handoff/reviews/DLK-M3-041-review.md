---
task_id: DLK-M3-041
reviewed_commit: 938e99de0825167b7dadc5a72bbce2d684e93448
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-041

## Decision

Accepted at 938e99d. R1/R2 were resolved in 5af203c, and the documentation-only follow-up supplies the remaining R3 alignment measurements, page-scale zoom evidence, and target-site selector explanation. No further actionable finding in this follow-up. Historical findings below remain for traceability.

## Final verification review of 938e99d

- The latest commit changes handoff documentation only. Prior code-check results remain tied to unchanged implementation 5af203c: 7 upload-state tests, 6 projection tests, lint with zero errors/140 warnings, and successful build. Reviewer independently checked committed whitespace.
- Gemini records portrait/landscape image and overlay bounds for inline narrow/wide and studio views, including approximately 0.5–2 CSS-pixel differences attributed to border accounting/rounding. These are reported measurements, not a claim of exact zero error.
- Gemini reports CDP page-scale checks at visualViewport.scale 1.5 and 2.0, separately from DPR 2 emulation. This adds visual-viewport/page-scale zoom coverage; it is not evidence of desktop browser menu/Ctrl+plus layout zoom specifically.
- The previous hasTargetSites=false is explained by uppercase CSS affecting a case-sensitive innerText assertion. The report records the accessible region-list selector and actual target tab text confirming the section is present.
- Acceptance relies on implementer-reported browser measurements and results. The reviewer did not rerun browser execution or inspect the referenced screenshot files; the scratch harness/screenshots are not available at a repository-relative location in this checkout. Do not describe this review as independent visual verification.
- This accepts the scoped frontend workbench, not templates/alignment automation, partial scoring, real manufacturing image accuracy, or complete finalist readiness.

## Correction review of 5af203c

- R1 resolved: explicit scope is honored, shape findings are not automatically grouped, and canonical deposit_size/inconsistent fallback is present with realistic regression coverage.
- R2 resolved: explicit Draw/Inspect controls are present; drawing routes through existing ROI rectangles in Draw mode, while Inspect mode avoids drawing. Gemini reports successful inside-ROI drawing and result invalidation.
- Gemini reports both regression harnesses passing, lint with zero errors/140 warnings, production build success, and browser checks for late-response rejection and upload isolation. Reviewer inspected the changes and committed whitespace without rerunning tests/browser execution.
- R3 remains incomplete: deviceScaleFactor=2/devicePixelRatio=2 is pixel-density emulation, not evidence of actual browser page zoom. The reported hasOverlay=true only establishes element presence, not alignment. Complete an actual browser zoom check and record observed geometric alignment for portrait/landscape images, inline/studio and narrow/wide viewports. Use known synthetic landmarks plus screenshots/visual comparison, or measured image-content/rectangle/polygon bounds with a stated tolerance. Identify exact setup and observed results; correct the existing report's zoom claim.
- The real request result hasTargetSites=false should also be explained: identify whether this was a stale text selector or an actual missing region list. Do not label a false check as a successful assertion without that explanation.
- For documentation-only completion of these browser checks, do not rerun unchanged lint/build solely to repeat prior evidence; retain the successful code-check results tied to 5af203c. If code changes, rerun affected checks and browser scenarios. Mark blocked if required verification cannot be performed.

## Acceptance evidence

- Shared RegionInspectionPanel is wired into inline and studio surfaces; additive types, ID-based measurement lookup, contour validation, separate reference coverage, and removal of first-site summary cards are present.
- Existing request/configuration guards remain in use; geometry helpers account for contained image bounds. No backend implementation changed.
- Gemini reports upload-state tests (7), projection tests (6), lint with no errors and 139 warnings, production build, task validation, and browser scenarios. Reviewer inspected code and reported evidence without rerunning implementation tests or browser execution. Committed whitespace check passes.

## Historical findings from a72b1a2

### R1 — P2: Individual shape findings are mislabeled as group comparisons

`frontend/lib/region-inspection-view.ts::findEmittedObservationsForRoi` marks every `deposit_shape` observation as a group finding, regardless of explicit individual_regions scope. Backend shape findings are ordinary per-site findings. The fallback checks observation_type D03_INCONSISTENT_SIZE, but the canonical D03 pair is deposit_size/inconsistent. Consequently ordinary abnormal/tailing shape findings receive an incorrect group explanation, while legacy canonical D03 without scope is missed. The test fixture also uses the noncanonical D03 observation type.

Honor recognized explicit region_evidence_scope; use the exact canonical deposit_size/inconsistent pair only when a legacy scope is absent. Do not infer a group from deposit_shape. Add realistic tests for individual shape, explicit group, and canonical legacy D03. Verify the displayed explanation for both shape and D03 in the browser.

### R2 — P2: Selection overlays prevent drawing within existing regions

`frontend/components/diagnosis/ImageRoiEditor.tsx` gives each entire ROI rectangle pointer-events-auto and stops pointerdown propagation unconditionally. The only drawing handler lives on the parent. A drag beginning inside an existing ROI therefore cannot create a new ROI; a full-image ROI prevents all further drawing until deleted/reset. There is no explicit draw-versus-inspect mode/control, despite the task requiring that distinction and preservation of the manual workflow.

Provide a clear Draw/Edit versus Inspect interaction mode (or an equally explicit accessible control) so selecting never draws and deliberate drawing can start inside existing regions without deleting them. Keep delete/reset and keyboard selection usable. Test in both inline and studio with an existing large/full-image ROI, adding a second ROI inside it, selecting without edits, and verifying that actual edits invalidate previous evidence.

### R3 — P2: Required browser verification is incomplete

The implementation report's scenario (f) only documents a landscape image and opening/closing studio, not portrait, narrow/wide viewport, or browser zoom alignment. Scenario (h) only documents removal, not reconfiguration during an in-flight response or switching uploads. Those are explicit required checks; pure geometry/state tests do not prove the wiring. The referenced scratch/verify-all-scenarios.mjs is not present at the reported repository-relative path, so it cannot supply the missing evidence here. A temporary harness need not be committed, but the report must describe actual checks and results accurately.

Complete the omitted browser scenarios after R1/R2 fixes, including late-response rejection in the rendered UI and selection isolation. Record actual setup, inputs, expected/observed behavior and console errors, distinguishing mocked responses from real backend requests. Correct the report's PDF limitation statement: parsing does not verify visual PDF appearance. If required browser checks cannot run, mark blocked as the task instructs.

## Scope note

ImageCalibrationPanel.tsx was changed outside the task allowlist to insert a 10% reference tolerance on mode change. This is not required for workbench rendering. Revert only this task's three-line default insertion, preserving pre-existing settings, unless a concrete blocker is brought back to the planner. Do not expand threshold/configuration behavior in this correction.

## Follow-up

R1/R2/R3 are closed for this scoped task. Leave this accepted record and queue update for the next authorized local handoff commit. No next feature task or remote Git action is authorized by this review. Preserve unrelated untracked files.
