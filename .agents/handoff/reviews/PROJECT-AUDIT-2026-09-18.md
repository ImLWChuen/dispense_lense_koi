# Whole-project audit — 18 September 2026

Reviewed checkout: `c26bb21938b7f1d2b6531161b8ba7ad790bf06e2`, branch `backend-database`.

Decision: changes required before claiming a reliable end-to-end competition MVP. This is a cross-member audit, not a replacement task packet. No production fixes, commits, pushes or merges were performed.

## Scope and verification

Reviewed frontend input, diagnosis, evidence analysis, check execution, verification, image and report surfaces; diagnostic extraction, evidence scoring, action selection and LLM boundaries; backend case/history persistence, reporting, dependencies and integration changes since `458467f`; handoff contracts and evaluation code.

Checks actually run:

- Frontend TypeScript: `tsc --noEmit --incremental false` passed.
- Frontend lint: failed, 32 errors and 9 warnings. Findings include explicit-any, React effect rules and navigation/escaping issues. Lint failure is a quality-gate failure, not evidence that every flagged location fails at runtime.
- Backend unit tests: 135 passed, 12 warnings.
- Full backend pytest attempted but stalled on database access and was interrupted. Bounded PostgreSQL connection checks timed out both inside and outside the sandbox. This is an environment limitation; no current full-suite pass/fail conclusion is claimed.
- Deterministic benchmark: 12 scenarios; defect accuracy 100%, top-1 accuracy 91.7%, top-3 coverage 100%. These are narrow synthetic scenario results, not industrial validation or measured technician time savings.
- Local executable probes reproduced negation/hypothesis extraction errors, inconclusive-check evidence loss, contradictory-observation duplicate suppression, and permissive LLM narrative validation.
- No production build or complete browser journey was performed. Live Gemini responses were not tested. Previously recorded 350 passing backend tests apply to the earlier accepted checkout, not automatically to this merge.

Priority: P1 = core workflow/data-trust blocker; P2 = material correctness or release-readiness problem. Ownership means correction ownership, not attribution of blame.

## Confirmed findings

### A01 — P1 — Completed checks cannot submit informative findings

Owner: Member 1, with Member 2 defining outcome choices.

`frontend/components/diagnosis/TroubleshootingChecklist.tsx:62-85` initializes `outcomes`, but never calls its setter. There is no outcome selector. Therefore Mark Complete always sends `finding=INCONCLUSIVE`, regardless of the notes. The API client also does not send the backend's structured `outcome` field.

Executable proof: CheckResultHandler given ACT01, COMPLETED, INCONCLUSIVE and notes `Nozzle blockage found` returns zero observations and an inconclusive summary. The backend is following its contract; the UI cannot convey the intended finding. The central check → evidence → re-ranking loop therefore does not work as presented.

Correction: expose check-specific outcomes from the knowledge contract, submit outcome and finding separately from execution status, and verify actual score/evidence changes through the UI. Do not map recovery success directly to CONTRADICTS; successful recovery does not establish absence of the suspected cause.

### A02 — P1 — Cause confirmation automatically claims successful recovery

Owner: Member 1.

`frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx:38-72` maps confirming a cause to RESOLVED, confirms the top cause, optionally records recovery, then submits verification with hard-coded `Tests passed. Issue fixed.`. The technician has not separately recorded acceptance criteria or a verification result. Without recovery text, confirmation may persist before recovery verification fails; the local revision is not refreshed on this partial failure, so retrying can conflict.

Correction: independent controls for cause confirmation, recovery action, and observed recovery verification. Preserve genuine technician evidence; refresh state after each accepted mutation and on conflicts. Allow confirming a cause while leaving the issue unresolved and resolving an issue without fabricating cause certainty.

### A03 — P1 — Negated and hypothetical text becomes positive observed evidence

Owner: Member 2.

`backend/app/services/diagnosis/symptom_extractor.py:189-211` detects hypotheses, then independently scans the full original text using positive keyword rules. It neither excludes hypothesis spans nor understands negation.

Reproduced outputs:

- `No bubbles are visible.` → bubble_presence=visible_bubbles, USER_OBSERVATION.
- `I suspect nozzle blocked.` → nozzle_condition=blocked, USER_OBSERVATION.

Correction: preserve statement scope, polarity and uncertainty. Hypotheses must not become measured facts; uncertain extraction should ask for confirmation. Add realistic negation, mixed-sentence and hypothesis tests.

### A04 — P1 — Duplicate detection suppresses contradictory evidence

Owner: Member 2.

`backend/app/services/diagnosis/evidence_engine.py:100-109` accepts high original-text similarity as duplicate evidence without requiring semantic agreement. Reproduced: blocked / `Inspection confirms the nozzle is blocked.` followed by clean / `Inspection confirms the nozzle is not blocked.` is marked duplicate. Duplicate contributions are zeroed by the scorer.

Correction: compare normalized meaning and polarity before similarity; opposing values must remain contradictions or time-qualified new observations. Test the actual score contribution, not just duplicate flags.

### A05 — P1 — Case retrieval discards stored outcome and provenance

Owner: Member 3, coordinated with Member 2 integration.

The latest integration changes `backend/app/api/cases.py:305,346-347,535,598-599` to build previous_check_results from the execution projection, explicitly replacing outcome with None and source with USER_CHECK_RESULT. The canonical check-result table and report mapper retain these fields. A recorded structured outcome is consequently lost in GET and answer responses even though it is still in storage and reporting.

Correction: hydrate canonical check-result history, or losslessly join the projection. Verify exact semantic parity across submission, GET, answer response and JSON/PDF report, including nonempty outcome and provenance. This is a newly identified integration regression, not proof of physical database deletion.

### A06 — P1 — Real analysis screens display invented fallback evidence

Owner: Member 1.

`frontend/components/diagnosis/DiagnosisSummary.tsx:15-21` substitutes an unrelated sensor defect, 92% score, three causes and five observations when values are absent/falsy. A legitimate zero score becomes 92. `frontend/app/(dashboard)/diagnosis/[id]/analysis/page.tsx:244` renders ImageAnalysis unconditionally; that component hard-codes an undersized deposit and `0.8mm (target: 1.2mm)` without an image service result.

Correction: render explicit unavailable/empty/error states and preserve zero values. Show measurements only when tied to actual image evidence. Clearly isolate any sample mode from real cases.

### A07 — P2 — Structured form labels do not match engine observation values

Owner: Members 1 and 2.

ProblemForm offers `Every shot`, `Intermittent`, `After prolonged operation`, `Specific nozzle`, etc. `frontend/app/(dashboard)/diagnosis/new/page.tsx:30-40` sends these labels verbatim as observation values. EvidenceEngine uses exact type/value comparisons. Canonical values include consistent, intermittent, specific_nozzle and runtime_pattern=after_prolonged_operation; a runtime condition is also being sent under frequency_pattern.

Furthermore `backend/app/services/diagnosis/engine.py:704` extracts description text only when no structured observations exist. Choosing a structured field therefore suppresses potentially useful description evidence.

Correction: use separate display labels and canonical values/types; merge valid structured and text evidence with provenance/deduplication. Test form submissions against meaningful rule contributions.

### A08 — P2 — Rejecting a cause silently records nothing

Owner: Member 1; Member 2 defines rejection semantics.

`frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx:73-86` handles rejection with a console warning and navigation. Notes and rejection are not persisted. A technician can reasonably believe the action was recorded.

Correction: implement an agreed rejection/contradictory-evidence flow, or disable the control with an explicit explanation until supported. Do not reuse a cause-confirmation endpoint to represent rejection.

### A09 — P2 — UI completion state is not tied to successful persistence or sufficient evidence

Owner: Member 1.

TroubleshootingChecklist changes local status before awaiting a server result and does not roll it back on failure. The troubleshooting page declares `Checks Complete` and `sufficient physical evidence` whenever next_check is absent, including a failed initial load or exhausted/blocked checks. Absence of a next check is not a statement of evidential sufficiency.

Correction: adopt persisted response state after success; preserve retryable state after failure; distinguish loading, error, exhausted checks, blocked progress and sufficient evidence using explicit engine state.

### A10 — P2 — Explanation UI does not match the scoring contract

Owner: Members 1 and 2.

`analysis/page.tsx:59-61` reads score_breakdown.question/check; the scorer emits positive_evidence, contradiction_penalty, duplicate_ignored and missing_penalty. Thus real contributions display as zero. EngineerVerification labels the heuristic score `% confidence`, whereas `backend/app/utils/scoring.py:8` explicitly states evidence support is not calibrated probability.

Correction: display the actual component breakdown and evidence links; retain a numeric 0–100 score with accurate evidence-support wording and explain missing/contradictory evidence. Calibrated probability requires separate validation.

### A11 — P2 — LLM boundary does not enforce its stated narrative constraints

Owner: Member 2.

`backend/app/services/ai/explanation_service.py:190` validates only a few exact phrases for resolved/confirmed states. It does not verify scores, procedure/source claims, or equivalent wording. Executable probe accepted `The nozzle is definitely the cause. Production can resume; the fault has been eliminated. Confidence: 99%.` for an unresolved case without a confirmed cause. LLM extraction also labels inferred output USER_OBSERVATION/USER in symptom_extractor.py rather than preserving AI inference provenance.

Correction: restrict generation to structured, validated fields and render critical state/score/procedure claims from trusted data. Preserve AI provenance and require confirmation where needed. Keep deterministic fallback until the enabled LLM path has adversarial and failure-mode coverage. This probe demonstrates a validation weakness, not a claim that a live model produced that text.

### A12 — P2 — Runtime dependency is declared only for development

Owner: Member 3.

`backend/app/services/ai/llm_service.py:29` unconditionally imports httpx. ExplanationService imports LLMService and DiagnosticEngine imports ExplanationService. `backend/pyproject.toml` lists httpx only in the dev extra. A clean runtime installation without dev dependencies can fail to import the app, even with LLM disabled.

Correction: declare httpx as a runtime dependency or make the optional feature genuinely lazy with a documented extra; verify clean non-dev installation and startup.

### A13 — P2 — Reports and image upload are not complete user features

Owner: Member 1; Member 3 only if optional CV is brought back into scope.

Reports list contains mockReports; report detail contains static content; frontend/lib/api/reports.ts is empty. Backend JSON/PDF reporting exists but is not connected to this workflow. ImageUpload stores dropped files locally; Browse Files has no picker handler and no backend upload/analysis connection. Vision/API image files are placeholders.

Correction: wire real case report retrieval/download; label or remove placeholder routes. CV remains explicitly deferred in the accepted MVP; its absence alone is not a regression, but implying real visual analysis is a product defect.

### A14 — P2 — Evaluation overstates what is measured

Owner: Member 2.

`backend/app/evaluation/benchmark.py:69,86` counts at most one proposed question and assigns evidence_traceability_rate=100.0. It does not simulate the full question/check/recovery loop or measure traceability. Passing 12 curated initial-diagnosis examples does not establish ranking calibration or troubleshooting-time reduction.

Correction: label current metrics as initial-diagnosis synthetic evaluation; calculate provenance coverage, replay multi-step scenarios, include negative/unknown/blocked/contradictory evidence, and report measured failures. Keep engineer validation and time-saving claims separate from code tests.

### A15 — P2 — Frontend quality gate remains failing

Owner: Member 1.

Verified lint result: 32 errors, 9 warnings. TypeScript passes, partly because broad any types avoid enforcing response contracts. In cases.ts, check/verification methods still declare DiagnosisResult despite returning wrapper response objects; finding_text is not accepted by the strict backend schema when provided. The current troubleshooting caller passes undefined so this extra-field issue is latent there, not its present failure cause.

Correction: fix the quality gate and type the actual endpoint responses; validate a production build and browser workflow after the functional corrections. Avoid merely disabling lint rules to declare completion.

## Additional design gaps requiring an explicit scope decision

- Process context: material/method/machine_context are stored, but ranking/action selection primarily receive observations and defect code. The frontend request also omits material/method. Do not imply equipment/material-specific applicability until supported combinations and rules are defined and tested.
- Recurrence exists in the backend but is not wired in casesApi. Decide whether recurrence must be demonstrated, then connect it if required.
- Authentication is explicitly deferred. A local synthetic demonstration is a different release target from a publicly exposed multi-user service; do not claim production readiness based on the current milestone.
- Startup/configuration: default frontend/backend CORS assume port 3000, which conflicts with this user's Open WebUI. Document the known 3001 frontend/8000 backend setup and a repeatable database startup/migration procedure.
- Deployment/migration validation: test a fresh database and an upgrade from the previously applied revision, especially the renamed execution-history migration. This audit did not establish compatibility with every teammate's existing database.
- Persistence invariant review: append_analysis_revision now checks CheckExecutionModel rather than canonical CaseCheckResultModel at repository.py:828. Legacy histories without projection rows receive weaker completeness validation. Restore canonical-history validation and test legacy records; live database reproduction remains outstanding.

## Correction sequence and ownership

1. Member 1: separate confirmation/recovery; make real outcomes selectable; remove fabricated case/image values. Member 2: fix negation, hypothesis isolation and contradictory duplicate handling. Member 3: restore lossless history responses and runtime dependencies. These can be coordinated without new architecture.
2. Agree the transport contract for canonical observations, check outcomes, response wrappers and score breakdown. Then Member 1 connects forms, reports, errors/retries and verification to that contract.
3. Member 2 tightens optional LLM output/provenance and builds multi-step evaluation. Keep optional CV/vector/auth expansion out of this correction cycle unless explicitly rescheduled.
4. With PostgreSQL reachable, rerun full backend tests and history-parity regressions; pass frontend lint/type/build checks; execute browser journeys for all six defects plus unknown, blocked, contradiction, partial-failure/retry and failed recovery cases.
5. Reassess completion based on demonstrated user journeys. Earlier implementation percentages measured scoped code milestones; they should not be interpreted as end-to-end submission acceptance.

Acceptance scenario: create a case with text plus canonical context, answer questions, submit a meaningful check, see evidence/ranking update, independently confirm cause and record recovery, verify actual acceptance results, reload with identical history, and export an accurate report. On errors, no invented success or lost user input. Each of the six categories must be represented by a documented scenario; no claim of factory accuracy without suitable evidence.
