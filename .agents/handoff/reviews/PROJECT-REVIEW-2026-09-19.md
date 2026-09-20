# Cross-member project review - 2026-09-19

Reviewed checkout: `backend-database`, commit `b2aa0fdf000de47eda61164df19eb0829af33fa0` (PR #16 head at review time).

## Assessment

Changes required before calling this an integrated, submission-ready prototype. The backend has substantial durable lifecycle functionality, but the technician UI does not yet preserve its meaning. There are also reproducible errors in symptom extraction, evidence handling, and image interpretation. This is a cross-project assessment, not a rejection of the narrow DLK-M3-025 runtime fix.

Scope: static inspection of frontend routes/components/API adapters, backend routing and schemas, diagnosis/scoring/question/check pipeline, image analysis, persistence/lifecycle/reporting, runtime configuration and evaluation. Focused executable probes and unit/type/lint checks supplement inspection. This is not an exhaustive proof that every path is correct or an independent engineering validation of dispensing knowledge.

No implementation code changed. No next task generated. Existing untracked files preserved. Findings below are requirements for the planner to allocate to the appropriate owner.

## Verification

- Backend unit suite: **186 passed** using `backend/.venv/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider --basetemp .review-tmp-20260919` from backend.
- Initial unit attempt encountered a Windows temporary-directory permission error; rerun with a workspace temporary directory passed. This was an environment issue, not a product failure.
- Frontend type check: **failed**, TS2322 at `frontend/app/(dashboard)/cases/[id]/page.tsx:36`.
- Frontend lint: **failed**, 36 errors and 13 warnings. Several are type/style errors; lint counts are not counts of functional defects.
- Database integration suite: **not run**. `TEST_DATABASE_URL` is absent after application environment loading. Development records were not used for tests. The earlier reported 401-test result was not independently reproduced in this review.
- No production build or browser end-to-end run was performed. The confirmed TypeScript failure already blocks accepting the frontend validation gate.
- Executable offline probes reproduced description suppression, negation/hypothesis extraction errors, exact-value mismatches, contradictory-reading deduplication, and scale-dependent image classification.

## Findings

### F01 - P1 - Case details route fails its component contract (Member 1)

Location: `frontend/app/(dashboard)/cases/[id]/page.tsx:36`; `frontend/components/cases/CaseDetails.tsx:14`.

The route renders `CaseDetails caseId=...`, but the component accepts `caseData` and performs no fetch. TypeScript rejects the prop; if execution bypasses that check, the component renders "Case details not available." for a valid case. Fetch the case and pass its response, with loading/error handling, or explicitly implement a case-ID-driven component. Acceptance: a case opened from the list displays its actual persisted lifecycle and the frontend type check passes.

### F02 - P1 - Physical checks cannot submit decisive evidence (Member 1, contract verified with Member 2/3)

Location: `frontend/components/diagnosis/TroubleshootingChecklist.tsx:62-85`; `backend/app/services/diagnosis/engine.py:456-467`.

`outcomes` starts empty and `setOutcomes` is never called. Every completed check therefore submits `INCONCLUSIVE`, regardless of the technician's notes. The backend deliberately returns no observations for that finding, so a real blockage observation does not update the ranking. The API adapter also lacks an explicit outcome argument. Expose the check's supported outcomes with technician-readable labels and submit the canonical finding/outcome. Do not infer "fixed" means CONTRADICTS: successful correction and diagnostic contradiction are different concepts. Acceptance: a supported blockage outcome changes evidence/ranking; an inconclusive or blocked check does not.

### F03 - P1 - Verification collapses three independent decisions (Member 1)

Location: `frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx:44-72`; `frontend/components/diagnosis/EngineerVerification.tsx`.

The only confirmation path confirms the top cause, records corrective action, and immediately submits successful verification with invented text "Tests passed. Issue fixed." The user cannot save cause confirmation while the issue remains unresolved, record pending recovery, or record a failed verification through this screen. This violates the agreed separation of cause confirmation and issue resolution. Use separate explicit actions/forms, collect actual verification results and criteria, and display backend state. Acceptance: confirmed-but-unresolved, recovery-pending, failed recovery, resolved-without-confirmed-cause where permitted, and recurrence remain representable.

### F04 - P1 - Human-readable form values silently miss evidence rules (Member 1 + Member 2/3)

Location: `frontend/components/diagnosis/ProblemForm.tsx:74-87,267,287`; `frontend/app/(dashboard)/diagnosis/new/page.tsx:32-42`; `backend/app/services/diagnosis/evidence_engine.py`.

The form sends labels directly, while evidence rules require exact canonical values. Probe for D01: `Every shot` matched 0 evidence relations versus 2 for `consistent`; `Specific nozzle` matched 0 versus 3 for `specific_nozzle`. "After prolonged operation" is also sent as frequency rather than runtime context. Define an explicit label/value/type mapping and validate supported structured values at the API boundary. Preserve genuinely unknown data as unknown rather than silently pretending to interpret it.

### F05 - P1 - Structured evidence suppresses the written description (Member 2)

Location: `backend/app/services/diagnosis/engine.py:702-705`.

Extraction runs only when the observation list is empty. Reproduction: "Nozzle blocked after prolonged operation." produces nozzle and runtime observations alone; adding `deposit_size=undersized` results in only that size observation. Normal UI use therefore discards diagnostic context whenever a dropdown or image supplies evidence. Extract description evidence once at intake, combine it with structured evidence using provenance-aware deduplication, and avoid re-extracting on later revisions. Acceptance: filling an extra field does not erase the description's evidence.

### F06 - P1 - Negated observations and hypotheses become positive observations (Member 2)

Location: `backend/app/services/diagnosis/symptom_extractor.py`, hypothesis collection followed by unrestricted keyword matching in `extract`.

Offline probes:

- `No bubbles are visible.` -> `bubble_presence=visible_bubbles`, USER_OBSERVATION.
- `I think the nozzle blocked.` -> `nozzle_condition=blocked`, USER_OBSERVATION, while also recording a hypothesis.

Detecting a hypothesis does not exclude its text from the observation pass. Handle negation and clause-level uncertainty before promoting text to evidence; ask a clarifying question where interpretation is ambiguous. Preserve original wording and hypothesis provenance. Acceptance: negation never becomes positive evidence and suspected conditions do not score as directly observed facts.

### F07 - P1 - Fuzzy deduplication discards contradictory evidence (Member 2)

Location: `backend/app/services/diagnosis/evidence_engine.py`, `_is_duplicate` fuzzy original-text comparison.

Probe: pressure=stable with "The pressure is stable during the entire dispensing cycle." followed by pressure=fluctuating with "The pressure is unstable during the entire dispensing cycle." is classified as a duplicate. The similarity check ignores contradictory structured meaning, leading to zero weight for the later evidence. Require semantic agreement before text similarity can suppress evidence; opposite values must remain contradictory or explicit updates with history. Acceptance: the reproduced pair is retained and affects ranking rather than becoming DUPLICATE.

### F08 - P1 - Image size classification has no reference scale or acceptance target (Member 3)

Location: `backend/app/services/vision/measurement.py:28-38`.

The largest dark contour is classified against 1,000/5,000 raw pixels. Synthetic probe: a black circle of radius 15 in a 100x100 white image is TOO_SMALL (area 666); the same proportional circle at 4x resolution is TOO_LARGE (area 11,120). Camera distance/resolution alone changes the supposed manufacturing defect. Require calibrated scale/reference geometry and target tolerance, or return bounded image features with an explicit unsupported/uncalibrated result. Do not treat arbitrary uploaded pictures as measured volume or size compliance.

### F09 - P2 - Image output does not match diagnostic values or preserve provenance (Member 3 + Member 1)

Location: `backend/app/api/images.py:25-29`; `backend/app/services/vision/measurement.py`; `backend/app/schemas/diagnosis.py:168`.

The image API returns `TOO_SMALL`/`TOO_LARGE`; rules expect `undersized`/`oversized` or other canonical values. Probe: TOO_SMALL contributes 0 matching relations for D01; undersized contributes 4. The response contains no image provenance and `Observation.source` defaults to USER, so persisted output looks like a technician observation. Define a canonical image-evidence contract including source, applicability, measurement uncertainty/reference, and user confirmation where appropriate. Resolve F08 before making these image values influence scores.

### F10 - P2 - Rejection appears submitted but is discarded (Member 1 + Member 2 contract decision)

Location: `frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx:74-86`.

Submit Rejection only writes a console warning and navigates away; neither rejection nor notes are persisted. Provide a supported rejection/challenge workflow with explicit history and diagnostic consequences, or disable the action and explain the limitation. Acceptance: rejection has a durable, visible result and survives reload.

### F11 - P2 - Partial verification failure leaves an unrecoverable stale UI until reload (Member 1)

Location: `frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx:42-90`.

Each of the three requests commits independently, but updated revisions live only in a local variable. If request two or three fails after cause confirmation commits, the catch does not reload case state. Retrying starts from the old revision and conflicts. After a partial success, refresh persisted state and resume the correct remaining operation. This is separate from server transaction integrity: each individual backend event is atomic, while the UI sequence is not.

### F12 - P2 - No remaining check is presented as sufficient evidence (Member 1, with Member 2 response support)

Location: `frontend/app/(dashboard)/diagnosis/[id]/troubleshooting/page.tsx:85,165-179`; `backend/app/services/diagnosis/action_planner.py`.

The planner returns no check when all have been attempted, including blocked/skipped/inconclusive checks, or no useful check exists. The UI then claims sufficient physical evidence and offers verification. A failed initial fetch can also reach this success panel because null data implies no check. Represent exhausted/blocked/unsupported/error states separately from diagnostic sufficiency. Acceptance: skipping every check does not produce a sufficient-evidence claim; failed requests never render successful completion.

### F13 - P2 - Check status becomes completed before the server accepts it (Member 1)

Location: `frontend/components/diagnosis/TroubleshootingChecklist.tsx:53-69,85`.

Local status is changed immediately and the callback is not awaited; failure leaves the check visibly complete. State is initialized from props once and does not reconcile later canonical responses. Await submission, update after success or roll back on error, and reconcile history. Acceptance: a 409 or network failure cannot falsely show a saved completion.

### F14 - P2 - Removing an image does not remove its observations (Member 1)

Location: `frontend/components/diagnosis/ImageUpload.tsx:77-79`; `frontend/app/(dashboard)/diagnosis/new/page.tsx:17-20`.

Removal changes the local file list only; parent observations are append-only and submitted even after the image disappears. Removing an in-flight upload can still add its observations later. Track uploads/observations by stable ID, propagate removal and ignore obsolete responses. Acceptance: a removed image has no effect on the created case, including when removed before upload completion.

### F15 - P2 - Image upload ignores the configured backend URL (Member 1)

Location: `frontend/components/diagnosis/ImageUpload.tsx:29`; `frontend/lib/api/client.ts:1`.

Image upload always targets 127.0.0.1:8000, while case requests use NEXT_PUBLIC_API_URL. On another technician's computer or a hosted frontend, images target that computer rather than the configured API. Use shared configuration with multipart-aware transport. Acceptance: all API calls reach the configured backend without requiring it on the browser's own machine.

### F16 - P2 - Reports and analytics present static results as actual case outcomes (Member 1)

Location: `frontend/app/(dashboard)/reports/page.tsx:13`; `frontend/app/(dashboard)/reports/[id]/page.tsx`; `frontend/app/(dashboard)/analytics/page.tsx:65-90`.

Reports use a mock list and a fixed "Nozzle Restriction - Line A" resolved narrative with 94% confidence for any ID; PDF/share buttons have no handlers. Analytics displays literal values including 284 cases, 8.4-minute resolution, and 92% accuracy. Backend durable JSON/PDF report endpoints already exist under cases. Connect reports to the selected case and those endpoints; derive analytics from actual supported data or clearly label sample content. Never use these literals as competition evaluation evidence. Acceptance: different case IDs yield their actual report and download; empty data does not show measured performance.

### F17 - P2 - Evidence scores are presented as confidence probabilities (Member 1 + Member 2)

Location: `frontend/components/diagnosis/ConfidenceScore.tsx`; `frontend/components/diagnosis/EngineerVerification.tsx`; `backend/app/services/diagnosis/cause_ranker.py`.

The backend explicitly describes scores as non-probabilistic Evidence Support /100 that do not sum to 100; the UI renders percentages and "% confidence". This implies calibration the system does not establish. Keep a numerical score but label it evidence support, explain its contributors/missing evidence, and keep confirmation separate. A calibrated probability would require a different validated model/evaluation decision.

### F18 - P2 - Upload endpoint does not enforce its advertised size limit (Member 3)

Location: `backend/app/api/images.py:23`; `frontend/components/diagnosis/ImageUpload.tsx`.

The UI advertises a 10 MB limit, but neither side enforces it. Backend reads the whole body and decodes it without a decoded-pixel budget. Large/compressed images can consume excessive memory and block the async handler during synchronous OpenCV processing. Enforce a bounded stream/body size and decoded image dimensions, and move CPU-bound processing off the event loop. Acceptance: oversize input is rejected predictably before expensive processing; valid bounded images still work.

## Scope and evidence limitations requiring team decisions

- **Process applicability:** material/method/machine context is stored, but the active ranker/action selection does not use it to filter recommendations. The new-case form only collects a generic line name. Member 2 should define supported dispensing methods/materials and the required context; Member 1 collects it and Member 3 validates/preserves it. Do not claim all equipment/material combinations are supported.
- **Knowledge traceability:** source IDs such as `dispensing_troubleshoot_ch2` and `air_management_guide` occur in knowledge JSON but no resolver/reference content was found in the searched docs/knowledge paths. This is a source-verification gap, not proof the underlying domain statements are false. Supply actual references, applicability and review status before claiming externally validated engineering guidance.
- **Authentication is a mock:** login uses a delayed redirect; no API identity/access enforcement is implemented in the inspected route dependencies. Keep this explicitly a local/team demo until an authentication/deployment decision is made. CORS does not establish user identity. Actor values such as "engineer" currently identify submitted labels, not verified users.
- **Historical retrieval is unfinished:** SimilarCases explicitly says vector search is pending; retrieval service files are placeholders. Treat as incomplete capability rather than claim similar-case retrieval works.
- **Evaluation question count is misleading:** `backend/app/evaluation/benchmark.py:98` counts whether the initial response proposes one question, not questions actually answered through a diagnostic session. It cannot demonstrate reduced troubleshooting effort/time. Use controlled multi-step scenarios, record actual interactions and label synthetic results. Clinical/industrial performance is not established by unit tests or the static dashboard.
- **List scaling:** the case list loads all cases, observations and revision snapshots with multiple per-case queries. It is reasonable for a small demo but has no pagination/summary-only contract for growth. This is a future scaling concern, not a current measured outage.

## Positive findings

- Backend domain/lifecycle model separates check execution, findings, cause confirmation, recovery action, verification and recurrence.
- Repository append operations use expected revisions and row locks; stale-write protection exists rather than relying only on UI state.
- Read-only durable report generation and JSON/PDF endpoints are implemented; frontend integration can reuse them.
- Offline deterministic diagnosis and bounded AI fallback exist; the unit suite passes.
- Dedicated test database safety is implemented. This review did not bypass it to get a green full-suite result.

## Recommended order and ownership

1. Member 1 restores the case-details contract and frontend validation gates.
2. Member 1 with Member 2/3 agrees canonical observation/check payloads and fixes F02/F04/F09. Add browser-to-API contract scenarios, not only manually constructed backend requests.
3. Member 2 fixes F05–F07 and verifies all six defect categories with negated, suspected, conflicting and mixed evidence.
4. Member 1 separates lifecycle actions and handles partial failures/rejections/exhaustion (F03/F10–F13). Member 3 supplies contract examples and integration support.
5. Member 3 bounds image analysis and uploads (F08/F09/F18); Member 1 fixes image state/configuration (F14/F15).
6. Member 1 connects truthful reports and evidence-score labels; team explicitly labels or removes demonstration metrics.
7. Run full backend tests against an explicitly configured disposable database, frontend lint/type/build checks, and browser workflows covering successful resolution, failed correction, blocked/inconclusive checks, stale revisions, recurrence, image removal and report export.

Member 3's next stage should prioritize contracts, image safety/correctness and end-to-end support. Additional generic API features will not resolve the highest-impact frontend and reasoning gaps above. No completion percentage is assigned: backend test count is not a measure of integrated product readiness.
