---
task_id: DLK-M3-029
reviewed_commit: 9cb20fae5093b1d4e617fcccf7e54ae89be23b5a
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-029

## Decision

Accepted after reviewing correction commit `9cb20fae5093b1d4e617fcccf7e54ae89be23b5a`. R1-R12 are resolved. The technician workflow now distinguishes rejected, committed, unconfirmed, and synchronized outcomes; gates stale state behind GET-only recovery; preserves or clears form input according to confirmed mutation outcome; and keeps question completion styling tied to persisted answers.

## Final correction review: `9cb20fae5093b1d4e617fcccf7e54ae89be23b5a`

- R11 resolved: POST failure plus GET failure retains the original mutation error, emits a truthful `state_refresh_required` warning, disables subsequent mutations, and recovers through GET-only retry without replaying the POST.
- R11 presentation resolved across questions, troubleshooting, and lifecycle pages: committed POST plus failed GET displays `Action Saved`, while unconfirmed POST plus failed GET displays `State Refresh Required`.
- R12 resolved: `DiagnosticQuestion` has an independent `disabled` prop; active in-flight and refresh-gated questions retain neutral styling and the help icon, while only persisted historical answers display the green completed state and check icon.
- `frontend/components/diagnosis/DiagnosticQuestion.tsx` was added to the task's allowed paths before modification.
- Test 15 now covers all four POST/GET outcomes, gating, form lifecycle, GET-only recovery, and zero replay. Test 16 covers active, in-flight, refresh-required, and persisted-answer question presentation states.

## Correction review: `c10fb6acada181ae81271522b9f120436720d1a2`

### R11 — POST failure plus GET failure leaves stale workflow state active (high)

- In `coordinateWorkflowMutation`, the rejected-POST branch catches a failed `performRefresh` but still emits `refreshWarning: null` and `isRefreshRequired: false` at `frontend/lib/diagnostic-workflow-state.ts:442-459`.
- The pages therefore render the mutation-error banner claiming that persisted case data "has been re-synchronized," even though the GET failed, and allow another mutation using the stale revision.
- This is especially unsafe for transport failures, where the client may not know whether the server committed the POST before the connection failed.
- When both POST and GET fail, preserve the original mutation error and technician input, set `isRefreshRequired: true`, expose a distinct synchronization warning that does not claim the action was saved or rejected with certainty, and gate all further mutations until the GET-only retry succeeds. The regression currently asserting `isRefreshRequired: false` for Scenario C must be corrected and must prove that the retry performs no POST.

### R12 — An in-flight question is displayed as already answered (medium)

- `frontend/app/(dashboard)/diagnosis/[id]/questions/page.tsx:327` passes `isAnswered={isSubmitting || isRefreshRequired}` to the active question.
- `DiagnosticQuestion` uses `isAnswered` for the green completed styling and check icon, so the UI temporarily claims the question was answered before the POST succeeds. It also conflates submission locking with persisted completion.
- Add a separate `disabled` prop to `DiagnosticQuestion`, keep the active question's `isAnswered` false until it becomes historical, and pass `disabled={isSubmitting || isRefreshRequired}`. Add `frontend/components/diagnosis/DiagnosticQuestion.tsx` to this task's allowed paths before editing it, and add a focused regression or component-level assertion for the distinct states.

### Resolved in this correction

- R8 is resolved for committed POSTs: failed durable refresh now produces an `Action Saved` warning, clears the submitted form, gates further mutations, and offers GET-only retry.
- R9 is resolved: questions, troubleshooting, and lifecycle pages use the production `coordinateWorkflowMutation` and `retryWorkflowRefresh` helpers, and lifecycle payload builders are used in production.
- R10 is resolved: focused task-owned ESLint returns zero errors and zero warnings.

## Correction review: `563cf07f71210ff6e993fa1eb7ff161558480214`

### R8 — A successful mutation followed by a failed refresh is reported as a failed mutation (high)

- The question handler wraps `submitAnswer` and the follow-up `getCase` in the same `try` block at `frontend/app/(dashboard)/diagnosis/[id]/questions/page.tsx:68-89`.
- The troubleshooting handler does the same at `frontend/app/(dashboard)/diagnosis/[id]/troubleshooting/page.tsx:72-99`.
- All four lifecycle handlers repeat the same sequence at `frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx:69-193`.
- If the POST succeeds but the subsequent GET fails, the catch path labels the action as failed. Troubleshooting and lifecycle handlers also reject to the child, which preserves the form and invites the technician to resubmit an operation that the server already committed. Revision checks should prevent a duplicate write, but the interface is still untruthful and forces an avoidable conflict/recovery cycle.
- Separate mutation outcome from refresh outcome. Once the POST resolves, treat the technician action as committed and clear the corresponding form. If the follow-up GET fails, show a distinct `saved, refresh required` state, retain or safely merge the POST response, and prevent another lifecycle/check submission until a fresh durable GET succeeds. A rejected POST must continue to preserve input and display the original mutation error. Never automatically replay either result.

### R9 — Mutation regression helpers are not used by production handlers (medium)

- `applyMutationSuccess`, `applyMutationFailure`, and `evaluateFormInputsOnMutation` are imported only by `frontend/scripts/test-diagnostic-workflow-state.mjs`; production pages and components never call them.
- `buildRecoveryVerificationPayload` is also tested directly but the verification page calls `casesApi.verifyCase` without using it.
- Consequently, tests 9, 10, and 13 pass even while the production handlers contain R8. Extract and use a production mutation-result coordinator, or make the pages/components consume the existing helpers in a way that covers the actual POST-success/GET-failure, POST-failure/GET-success, and full-success transitions. The Node regression must execute the same decision logic used by the pages.

### R10 — Verification evidence overstates lint cleanliness (low)

- Focused ESLint reports two warnings in `frontend/scripts/test-diagnostic-workflow-state.mjs`: unused `VALID_EXECUTION_STATUSES` at line 38 and unused `initialCase` at line 441.
- The implementation report and queue state claim zero warnings on modified files. Remove the unused values or record the exact warning count truthfully.

### Resolved from the first review

- R1 is resolved for rejected POSTs: mutation errors survive durable resynchronization, and check/lifecycle child forms retain entered values.
- R2 is resolved: `resolveActiveCheck` does not reactivate historical checks.
- R3 is resolved: lifecycle pass/fail badges require a verification event and a boolean result.
- R4 is resolved: all six supported execution statuses are exposed and non-completed results remain evidence-neutral.
- R5 is resolved: blank recovery-verification details are rejected by the UI and payload builder.
- R6 is resolved when both the POST and follow-up GET succeed; R8 covers the remaining partial-success branch.
- R7 is partially resolved: canonical `no_blockage` and the new helper scenarios are present, but R9 must connect mutation regressions to production behavior.

## Findings

### R1 — Submission failures are cleared and technician input is discarded (high)

- `frontend/app/(dashboard)/diagnosis/[id]/questions/page.tsx:77-82`, `frontend/app/(dashboard)/diagnosis/[id]/troubleshooting/page.tsx:85-90`, and the mutation handlers in `frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx` set the mutation error and then call `fetchCase()`.
- Each `fetchCase()` clears `error` after a successful refresh, so a 409, network failure, or server failure disappears immediately.
- The parent handlers swallow the error. `TroubleshootingChecklist` and `EngineerVerification` therefore treat the callback as successful and clear the technician's outcome, notes, or verification details.
- Resynchronize the durable case without clearing the original mutation error. The parent mutation callbacks must reject or return an explicit failure result so child forms clear their fields only after confirmed success. Do not replay a rejected mutation automatically.

### R2 — Exhausted workflows reactivate the first historical check (high)

- `frontend/components/diagnosis/TroubleshootingChecklist.tsx:69` falls back to `actions[0]` when no active or pending check exists.
- `frontend/app/(dashboard)/diagnosis/[id]/troubleshooting/page.tsx:289-296` passes the historical actions even when `next_check` is null.
- The fallback is rendered as active and exposes submission controls at `TroubleshootingChecklist.tsx:247`, allowing an exhausted case to resubmit an old check and potentially duplicate history or change ranking.
- Resolve an active check only when `activeCheckId` matches a pending action, or when a genuinely pending action exists. Render every historical action read-only when no active check exists. Add a regression for an all-historical action list with no active check.

### R3 — Non-verification lifecycle events are labelled `FAILED` (medium)

- `frontend/components/diagnosis/EngineerVerification.tsx:534-543` checks `verification_passed !== undefined`.
- The API represents recovery-action and recurrence events with `verification_passed: null`; `null !== undefined` is true, so those events receive a red `FAILED` badge.
- Render the pass/fail badge only when `typeof verification_passed === "boolean"`, preferably also restricting it to recovery-verification events. Add regression coverage for null, true, and false values.

### R4 — The UI cannot submit all supported check execution statuses (medium)

- `frontend/components/diagnosis/TroubleshootingChecklist.tsx:72` and `:266` expose only `COMPLETED`, `BLOCKED`, and `SKIPPED`.
- DLK-M3-029 requires the technician workflow to support `FAILED`, `UNKNOWN`, and `NOT_APPLICABLE` as well.
- Expose every supported status with understandable labels. Map every non-completed status to `finding: UNKNOWN` and omit the outcome; require an explanatory reason where the contract or technician workflow needs one. Cover all statuses in the production-helper regression.

### R5 — Recovery verification accepts empty evidence details (medium)

- `frontend/components/diagnosis/EngineerVerification.tsx:89-98` submits `verificationDetails.trim()` without validating it, and the button at `:431-447` remains enabled when details are blank.
- The workflow requirement calls for actual verification details or test observations. An empty string creates a formally completed event without usable evidence.
- Require non-blank details for both passed and failed recovery verification, preserve them after submission failure, and test this through the production payload/helper path.

### R6 — Successful mutation responses can temporarily erase durable histories (medium)

- The pages replace `caseData` directly with each mutation response.
- Several mutation response builders do not include all newly added confirmation and lifecycle history fields, so a successful answer, check, or cause-confirmation mutation can make previously persisted history disappear until a later reload.
- After every successful mutation, fetch the authoritative durable case before updating the completed UI state, or populate every mutation response with the same complete histories as `GET /api/v1/cases/{case_id}`. The frontend refresh is the smaller change within this task's authorized contract.

### R7 — The regression script does not exercise the failing production paths (medium)

- `frontend/scripts/test-diagnostic-workflow-state.mjs:185-199` uses `clear_flow` for `ACT01`, while the canonical action key is `no_blockage`.
- The stale/error test feeds an error directly to a view helper, so it cannot detect `fetchCase()` clearing a real mutation error. The confirmed-cause preservation scenario constructs an object rather than exercising a production state transition.
- Add production helpers and direct regressions for mutation refresh/error preservation, input clearing only on success, no-active-check selection, lifecycle badge rendering, complete status payloads, and required verification details. Use the canonical action outcome key.

## Verification

- Reviewed final correction commit `9cb20fae5093b1d4e617fcccf7e54ae89be23b5a` on `backend-database`; it has not been pushed by this review.
- Task packet validation returned `VALID`; committed whitespace check passed.
- Focused backend lifecycle/API suite: 89 passed.
- The correction contains no backend source changes, so the previously verified full-backend result remains applicable: 481 passed using repository-local `--basetemp`.
- Workflow state regression: 16 passed, with the existing Node module-type warning.
- Focused ESLint across the corrected task files returned zero errors and zero warnings.
- Production frontend build passed, including TypeScript and all 13 static pages.
- Full repository `npm run lint` returned 10 errors and eight warnings, all in files outside this correction. The full-repository gate remains failing and must continue to be reported separately from the clean focused result.
- The protected uncommitted `frontend/app/(dashboard)/cases/[id]/page.tsx` and other unrelated working-tree files remain outside the reviewed commit.

## Follow-up

DLK-M3-029 is complete and ready for the user's chosen Git publication and integration step. The protected case-detail edit and unrelated working-tree files remain outside all reviewed commits. Final end-to-end acceptance remains a separate next-stage planning decision.
