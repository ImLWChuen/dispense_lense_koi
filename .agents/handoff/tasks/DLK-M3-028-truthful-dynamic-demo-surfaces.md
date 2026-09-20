---
task_id: DLK-M3-028
title: Truthful dynamic dashboard, reports, analytics, and evidence-support labels
status: implemented
created_by: ChatGPT planner/reviewer
assigned_to: Gemini implementer
depends_on: [DLK-M3-027]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-028: Truthful dynamic dashboard, reports, analytics, and evidence-support labels

## Objective

Make the competition-facing dashboard, case list, reports, analytics, and shared diagnosis summary render only persisted or correctly derived project data. Remove fabricated report records, sample report narratives, invented equipment/cause values, unsupported accuracy claims, fixed trend percentages, and default diagnosis scores. Every deterministic cause score shown to a technician must be labelled **Evidence Support /100**, never confidence or probability.

This is the first reviewable increment of Phase 3. It covers the approved plan's Task 14 plus the shared score-label correction identified in the cross-project review. Stop for ChatGPT review after this task. A later Phase 3 task will correct troubleshooting outcomes, verification lifecycle actions, rejection/exhaustion behavior, and the protected case-detail route.

## Current evidence

- Current branch at release is `backend-database`, head `48be5781b811a8523473cb3f94e95f219984f46f`, after merging the latest `origin/main` and accepting `DLK-M3-027`.
- `DLK-M3-027` is accepted. Its calibrated image workflow and backend-aligned frontend diagnosis types must remain intact.
- The latest teammate merge added `/api/v1/analytics/dashboard`, `/api/v1/analytics/performance`, and `/api/v1/analytics/events`, so the older instruction to create client-only analytics from `GET /cases` is stale. Use and correct the existing analytics endpoints rather than adding another analytics subsystem.
- `backend/app/api/analytics.py` currently fabricates several result values: `ai_accuracy_rate` is `100` or `92`; recent-case confidence defaults to `90` and reads nonexistent `probability`/`confidence` keys from revision 1; equipment falls back to `Dispensing Line A`; dashboard trends use fixed values such as `+100%` and `-15%`; performance trends include fixed `-15%`, `+5%`, and `+2%`; and the insight substitutes `Nozzle Condition` when no confirmed cause exists.
- The deterministic cause value is `CandidateCause.score`, an evidence-support score from 0 to 100. It is not a calibrated probability and must not be called confidence or accuracy.
- `frontend/app/(dashboard)/reports/page.tsx` displays three mock reports when the API is empty or fails. `frontend/app/(dashboard)/reports/[id]/page.tsx` and `frontend/components/reports/ReportPreview.tsx` contain fixed Line A/nozzle narratives and other fallback results.
- `frontend/app/(dashboard)/dashboard/page.tsx` labels unsupported data as engine accuracy and defaults it to 100. `RecentCases.tsx` labels the backend value confidence.
- `frontend/components/diagnosis/DiagnosisSummary.tsx` invents a defect, description, score 92, case ID, cause count, observation count, and status when data is absent. `ConfidenceScore.tsx` renders every score as a percentage without explaining its meaning.
- The cases list is API-driven, but it still falls back to a generic `Dispensing Line` and has task-relevant lint errors.
- Current frontend baseline after synchronization: `npm run build` passes; `npm run lint` reports 29 errors and 15 warnings. Task-owned files contain several of those findings. Every task-owned frontend file must be lint-clean; unrelated auth, knowledge-base, verification, and protected case-detail findings remain outside this task.
- Existing unrelated working-tree items at release are:
  - modified `frontend/app/(dashboard)/cases/[id]/page.tsx`;
  - untracked `.agents.zip`;
  - untracked `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`;
  - untracked `frontend/AGENTS.md` and `frontend/CLAUDE.md`.
  Preserve all of them. The case-detail route directly overlaps later Phase 3 work and is expressly prohibited in this task.
- Backend database tests must use the separately named disposable test database through `TEST_DATABASE_URL`. Never point tests, migrations, cleanup, or fixtures at the development `dispenselens` database.

## Requirements

### 1. Follow the installed Next.js 16 contract

- Before changing frontend code, read `frontend/AGENTS.md` and the relevant installed Next.js guides under `frontend/node_modules/next/dist/docs/`, including client/server components and data fetching.
- Do not add or upgrade dependencies. The repository has no frontend test framework; do not introduce one here.
- Resolve all ESLint findings in files changed by this task without suppressing rules.

### 2. Correct the analytics transport semantics

- Replace recent-case `confidence` with nullable `evidence_support`. Read it from the latest persisted analysis revision's top-ranked cause `score`, or return `null` when no ranked cause exists. Do not read `probability` or `confidence`, multiply a guessed fraction, use revision 1 when a later revision exists, or supply a default score.
- Replace dashboard `ai_accuracy_rate` and performance `diagnostic_accuracy_rate` with a plainly named, truthfully derived metric such as `cause_confirmation_rate`. Define it as the percentage of cases in the applicable population that have at least one persisted cause confirmation. Document the denominator and return `null` when the denominator is zero.
- Analytics score/rate fields may be numeric percentages only when the numerator and denominator are real persisted data. They are descriptive workflow metrics, not model accuracy.
- Make trend fields nullable. Calculate a period-over-period trend only when both current and comparable prior populations support it; otherwise return `null`. Never replace unavailable trends with `+100%`, `-15%`, `+5%`, `+2%`, `0%`, or another plausible-looking value.
- Return actual recorded equipment/machine context when present. When it is absent, return a neutral value such as `Not recorded`; never name a line or machine that was not stored.
- Use `Under investigation` when no cause is confirmed or ranked. Do not invent a nozzle or other cause.
- A dashboard insight may mention a cause only when a confirmed-cause aggregate supports it. With no confirmed cause, omit that claim and render a neutral evidence-limited message or `null`.
- Keep the current endpoints and period options. Do not add tables, migrations, background aggregation, authentication, or a second analytics API.
- Update the Pydantic and TypeScript response contracts together. This task explicitly authorizes the narrow analytics response rename/nullability changes above; any wider public API change requires returning to the planner.

### 3. Add regression coverage for truthful analytics

- Add focused tests before implementation for at least:
  - an empty database: zero real counts, empty distributions, nullable rates/trends/scores, and no sample equipment/cause/text;
  - a case without machine context or ranked causes: `Not recorded`, `Under investigation`, and `evidence_support=null`;
  - more than one analysis revision: the latest top cause score becomes `evidence_support` exactly;
  - cause confirmations: unique confirmed cases produce the documented confirmation rate without being labelled accuracy;
  - a period without a valid comparison population: trend is `null`;
  - no confirmed cause: insight does not name a fallback cause.
- Exercise the real FastAPI response models and endpoint behavior against the approved disposable PostgreSQL test destination. Do not weaken or bypass `TEST_DATABASE_URL` safety.

### 4. Make dashboard and analytics pages truthful

- Consume the corrected typed analytics responses. Remove all frontend defaults that turn missing values into plausible results.
- Replace the dashboard's `AI Diagnostic Status` / accuracy presentation with the real confirmation-coverage metric and a plain explanation of what it measures. Show `Not available` when its denominator is zero.
- Render trends only when the API returns a real trend. `KpiCard` must support a missing trend without displaying `0%` as a substitute.
- Label recent-case cause scores `Evidence Support` and render `N/A` when absent. Do not append `% confidence` or imply probability.
- Keep real loading, empty, and error states distinct. A failed request must not render a plausible zero-data dashboard.
- SSE and polling may remain only as refresh mechanisms. Do not claim a live machine connection, hardware telemetry, or model accuracy.
- Analytics charts must use only response arrays. When an array is empty or a metric is unavailable, show a neutral empty/unavailable state. Do not populate placeholder bins or sample chart rows that imply observed production data.

### 5. Make case and report surfaces truthful

- Keep the cases list backed by `casesApi.listCases()`. Display `Not recorded` for absent equipment rather than a generic line. Preserve explicit loading, error, empty, search, and status-filter states.
- Treat each durable case as having a read-only report at its case ID. The report list must contain only real cases returned by the API. Empty results show an empty state; request failure shows an error with a retry path. Never substitute mock reports.
- Fetch `GET /cases/{case_id}/report` for report detail and populate the page from the typed `CaseReportResponse` only.
- Rewrite `ReportPreview` as a typed data component and use it from the detail route. Render only fields and events present in the report: case/defect/context, observations/evidence, ranked causes, questions/checks, cause confirmations, recovery/verification/recurrence lifecycle events, and outcome summary as applicable.
- Remove fixed report IDs, Line A/nozzle stories, invented measurements, sample recommendations, and fallback causes. Missing sections must say that the information was not recorded or show a neutral empty state.
- Keep PDF download on the configured API base URL through `reportsApi`. A download action must use the actual case ID. Do not create fake report IDs or claim a download succeeded merely because a timer elapsed.
- Replace `Record<string, any>` and other task-owned `any` types with backend-aligned types or `unknown` plus runtime narrowing.

### 6. Correct shared evidence-score presentation

- Shared cause-score components must label a candidate's numeric score `Evidence Support /100` or `Evidence Support`, not diagnostic confidence, probability, or accuracy.
- `DiagnosisSummary` must derive defect, description, case ID, state, cause count, observation count, and top score only from the supplied durable case. Missing data must remain visibly unavailable; remove every sample/default diagnosis value.
- A score of exactly zero is valid and must not be treated as absent. Clamp only the visual bar to `[0,100]`; do not alter the displayed backend score.
- Update current usages in `CauseCard`, the dashboard recent-cases table, case table if retained, and other task-owned surfaces. Verification-specific wording inside `EngineerVerification` is deferred to the next Phase 3 task and must not be edited here.

### 7. Contract documentation

- Update `docs/api/frontend-backend-contract.md` with the corrected analytics response names, nullability, evidence-support meaning, cause-confirmation-rate definition, and unavailable-state rules.
- State explicitly that no current endpoint provides calibrated diagnostic/model accuracy and that deterministic evidence-support scores do not sum to 100 or represent probabilities.
- Record that raw report/image facts are rendered only when persisted. Do not document mock fallbacks as supported behavior.

## Interfaces and data contracts

The task authorizes these coordinated analytics response corrections:

- `RecentCaseRecord.confidence` becomes `evidence_support: float | null` (or an equivalent numeric type with the same JSON behavior).
- Dashboard `ai_accuracy_rate` becomes `cause_confirmation_rate: float | null`.
- Performance `diagnostic_accuracy_rate` becomes `cause_confirmation_rate: float | null`.
- Trend fields used by these endpoints become nullable when no honest comparison can be calculated.
- Existing endpoint paths, period values, case/report endpoints, durable lifecycle semantics, and diagnosis score computation remain unchanged.

`cause_confirmation_rate` is a workflow coverage metric: unique cases with at least one cause confirmation divided by cases in the endpoint's population, multiplied by 100. It must never be described as correctness or accuracy.

`evidence_support` is copied from the latest persisted top-ranked `CandidateCause.score`. It is a 0-100 evidence-support score, not a probability. `null` means no ranked cause exists.

## Allowed paths

- `backend/app/api/analytics.py`
- `backend/app/schemas/analytics.py`
- `backend/tests/integration/test_analytics_api.py`
- `frontend/lib/api/analytics.ts`
- `frontend/lib/api/reports.ts`
- `frontend/types/api.ts` only for report/analytics-aligned typing required by this task
- `frontend/app/(dashboard)/dashboard/page.tsx`
- `frontend/app/(dashboard)/cases/page.tsx`
- `frontend/app/(dashboard)/reports/page.tsx`
- `frontend/app/(dashboard)/reports/[id]/page.tsx`
- `frontend/app/(dashboard)/analytics/page.tsx`
- `frontend/components/dashboard/KpiCard.tsx`
- `frontend/components/dashboard/RecentCases.tsx`
- `frontend/components/dashboard/DefectDistribution.tsx`
- `frontend/components/dashboard/CauseDistribution.tsx`
- `frontend/components/dashboard/AiInsights.tsx`
- `frontend/components/analytics/DefectChart.tsx`
- `frontend/components/analytics/CauseChart.tsx`
- `frontend/components/analytics/ResolutionChart.tsx`
- `frontend/components/cases/CaseTable.tsx`
- `frontend/components/reports/ReportPreview.tsx`
- `frontend/components/reports/ReportActions.tsx`
- `frontend/components/diagnosis/ConfidenceScore.tsx`
- `frontend/components/diagnosis/CauseCard.tsx`
- `frontend/components/diagnosis/DiagnosisSummary.tsx`
- `docs/api/frontend-backend-contract.md`
- `.agents/handoff/tasks/DLK-M3-028-truthful-dynamic-demo-surfaces.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-027-review.md` only if an already pending accepted review record must be included unchanged

If renaming `ConfidenceScore.tsx` to a truthful component filename, the replacement file and only the directly affected imports are allowed. Record the rename explicitly in the implementation report.

## Prohibited scope

- `frontend/app/(dashboard)/cases/[id]/page.tsx`; it contains an unrelated uncommitted teammate/user change and must not be staged, overwritten, reformatted, or included in the implementation commit.
- `frontend/app/(dashboard)/diagnosis/[id]/verification/page.tsx`, `frontend/components/diagnosis/EngineerVerification.tsx`, `frontend/components/diagnosis/TroubleshootingChecklist.tsx`, and troubleshooting/check submission behavior. These form the next Phase 3 increment.
- Authentication/login/register/provider work, knowledge-base UI, similar-case/vector retrieval, calibrated image workflow changes, or raw image persistence.
- Diagnosis rules, weights, score calculation, question/check meaning, lifecycle state transitions, database schemas/migrations, or report-generation backend semantics.
- Invented analytics values, synthetic production results, hidden defaults, or conversions that relabel evidence support as accuracy/confidence.
- New dependencies, a frontend test framework, a second analytics subsystem, hardware telemetry, background workers, deployment, or unrelated refactoring.
- Cleaning, resetting, reverting, stashing, overwriting, or committing unrelated working-tree files, including `.agents.zip`, `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`, `frontend/AGENTS.md`, and `frontend/CLAUDE.md`.
- Remote Git operations, changes to `main`, pull-request creation, merge, rebase, or force-push.

## Implementation guidance

1. Perform the handoff preflight. Confirm the branch, accepted dependency, exact status, and protected working-tree files. Change this task and `QUEUE.md` to `in_progress` before product edits.
2. Read the required installed Next.js 16 guidance and inspect the actual Pydantic report/diagnosis/analytics schemas. Treat current API code as implementation evidence, not as proof that its labels are valid.
3. Add failing analytics endpoint regressions for the truthfulness requirements before changing analytics code. Use only the validated disposable test database.
4. Correct the Pydantic analytics schemas and endpoint computations together. Prefer small private helpers where they make the denominator, latest-revision selection, and nullable trend behavior testable. Do not change diagnostic scoring.
5. Update the frontend analytics contract and then the dashboard/analytics consumers. Remove fallback operators that turn missing results into `100`, `92`, `90`, or `0%` claims.
6. Replace the report list/detail fallbacks with typed actual-data, empty, and error states. Reuse the existing JSON and PDF endpoints; do not create report persistence.
7. Correct the shared evidence-support components and diagnosis summary. Ensure zero-valued scores render and absent scores do not become defaults.
8. Update the frontend-backend contract. Run focused tests/lint, full frontend build, repository-wide lint comparison, backend suite, and static fabricated-string searches.
9. Complete the implementation report, set the task and queue to `implemented`, stage only allowed task files plus required handoff records, and create one atomic local commit.

## Acceptance criteria

- [ ] Empty analytics data returns zero real counts, empty distributions, nullable rates/trends/scores, and no sample equipment, cause, narrative, or percentage.
- [ ] Recent-case `evidence_support` comes exactly from the latest persisted top-ranked cause score and is `null` when no ranking exists.
- [ ] Cause-confirmation coverage is calculated from persisted unique case confirmations, documented with its denominator, and never labelled model/diagnostic accuracy.
- [ ] No dashboard/performance trend uses a fixed plausible value; unavailable comparisons are `null` and hidden or labelled unavailable in the UI.
- [ ] Dashboard and analytics distinguish loading, error, empty, unavailable, and actual-data states and show no fabricated defaults.
- [ ] Report list/detail use only actual case/report responses; empty or failed responses never display mock report rows or sample narratives.
- [ ] PDF download uses the configured API base and actual case ID.
- [ ] Case list shows only stored context and a neutral missing-context label; the protected case-detail route remains untouched.
- [ ] Every displayed cause score in task-owned surfaces is labelled Evidence Support /100 (or Evidence Support) and is never described as confidence, probability, or accuracy.
- [ ] `DiagnosisSummary` contains no fallback defect, description, score, counts, case ID, or state that could be mistaken for persisted data.
- [ ] Task-owned TypeScript contains no explicit `any`, passes focused ESLint, and the production frontend build passes.
- [ ] Focused analytics tests and the full backend suite pass against the validated disposable test database. No development records are read for test assertions or mutated.
- [ ] Documentation matches the implemented JSON names, nullability, and meaning.
- [ ] No prohibited or unrelated file is staged or committed.

## Verification

Run from the stated directory and record the exact output, counts, warnings, and any environment limitation.

1. From `backend/`, after setting a validated local `TEST_DATABASE_URL` that is separate from `DATABASE_URL`:

   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_analytics_api.py --basetemp .phase3-analytics-pytest-tmp`

2. From `backend/`, full suite against the same safe disposable destination:

   `.\.venv\Scripts\python.exe -m pytest -q --basetemp .phase3-full-pytest-tmp`

   If the safe PostgreSQL test destination is unavailable, do not use the development database or weaken the test bootstrap. Record the exact blocker and leave the task `blocked`, not `implemented`.

3. From `frontend/`, focused lint across every changed frontend source. Include every changed path in one command. At minimum cover all task-owned files that remain present after implementation.

4. From `frontend/`:

   `npm run build`

5. From `frontend/`:

   `npm run lint`

   Compare the result with the release baseline of 29 errors and 15 warnings. Every task-owned file must be clean and the repository-wide totals must decrease or remain attributable only to untouched out-of-scope files.

6. From the repository root, run a targeted search over task-owned product files for fabricated/sample terms and inspect every match:

   `git grep -n -E "mockFallbackReports|Dispensing Line A|Nozzle Restriction|AI Diagnostic Status|diagnostic accuracy|engine accuracy|% confidence|\\b92(\\.0)?\\b|\\b90\\b" -- backend/app/api/analytics.py backend/app/schemas/analytics.py frontend/app frontend/components frontend/lib/api`

   Legitimate option values such as the analytics period `90d` are not findings. No task-owned user-facing result fallback may remain.

7. From the repository root:

   `python .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-028-truthful-dynamic-demo-surfaces.md`

8. From the repository root, inspect task range and whitespace:

   `git diff --check`

   `git status --short`

   `git diff --stat`

## Planner decision boundaries

Return to the planner before changing any diagnosis rule, evidence weight, scoring algorithm, question/check meaning, lifecycle transition, report-generation contract, database schema/migration, dependency, authentication policy, or protected case-detail file. The analytics field renames/nullability explicitly listed in this task are authorized; no wider public interface change is authorized.

If an honest metric cannot be calculated from current persisted data, use `null`/unavailable or omit its presentation. Do not invent a proxy and do not add new persistence merely to keep the old card visible.

## Git instructions

Create one atomic local commit after all required checks pass. Do not push, merge, rebase a shared branch, create or update a pull request, or change `main`.

Proposed commit message: `fix(analytics): make demo surfaces data truthful`

## Implementation report

### Summary

- Removed all fabricated fallback data from backend analytics and frontend user interfaces: deleted synthetic `mockFallbackReports`, placeholder defect stories ("A particle or debris is obscuring..."), fallback score 92, fallback cause counts (3) and observation counts (5), placeholder case numbers ("Case DSP-2026"), synthetic equipment lines ("Dispensing Line A"), and unsupported AI accuracy claims (100%, 92%).
- Corrected backend analytics endpoints (`/api/v1/analytics/dashboard`, `/api/v1/analytics/performance`): replaced `ai_accuracy_rate`/`diagnostic_accuracy_rate` with `cause_confirmation_rate: Optional[float]` (calculated strictly as `unique confirmed cases / population cases * 100`, returning `None` if the population is 0). Replaced `confidence` with `evidence_support: Optional[float]`, reading directly from the latest persisted analysis revision's top-ranked cause score.
- Made period-over-period trends strictly nullable: trends return `None` whenever no valid comparable prior population exists (>0 records) rather than substituting synthetic trends (`+100%`, `-15%`, `0%`).
- Frontend components and pages (Dashboard, Cases, Reports, Analytics, ConfidenceScore, CauseCard, DiagnosisSummary, CaseTable, RecentCases, Defect/Cause/Resolution charts) render only real persisted data. Clean loading, empty, and retryable error states are displayed when data is missing or unavailable.
- Cause scores are consistently labeled `Evidence Support /100` or `Evidence Support` across all task-owned surfaces. Zero is treated as a valid score (`0/100`).
- Updated `docs/api/frontend-backend-contract.md` matrix and added Section 3.7.

### Files changed

- `backend/app/schemas/analytics.py`
- `backend/app/api/analytics.py`
- `backend/tests/integration/test_analytics_api.py`
- `docs/api/frontend-backend-contract.md`
- `frontend/lib/api/analytics.ts`
- `frontend/lib/api/reports.ts`
- `frontend/components/dashboard/KpiCard.tsx`
- `frontend/components/dashboard/RecentCases.tsx`
- `frontend/components/dashboard/DefectDistribution.tsx`
- `frontend/components/dashboard/CauseDistribution.tsx`
- `frontend/components/dashboard/AiInsights.tsx`
- `frontend/app/(dashboard)/dashboard/page.tsx`
- `frontend/components/analytics/DefectChart.tsx`
- `frontend/components/analytics/CauseChart.tsx`
- `frontend/components/analytics/ResolutionChart.tsx`
- `frontend/app/(dashboard)/analytics/page.tsx`
- `frontend/components/cases/CaseTable.tsx`
- `frontend/app/(dashboard)/cases/page.tsx`
- `frontend/components/reports/ReportPreview.tsx`
- `frontend/app/(dashboard)/reports/page.tsx`
- `frontend/app/(dashboard)/reports/[id]/page.tsx`
- `frontend/components/diagnosis/ConfidenceScore.tsx`
- `frontend/components/diagnosis/CauseCard.tsx`
- `frontend/components/diagnosis/DiagnosisSummary.tsx`
- `.agents/handoff/tasks/DLK-M3-028-truthful-dynamic-demo-surfaces.md`
- `.agents/handoff/QUEUE.md`

### Decisions made

- Explicitly defined `cause_confirmation_rate` as a workflow coverage metric measuring technician root-cause confirmation activity, preventing misinterpretation as model accuracy or precision.
- Defined `evidence_support` as the deterministic 0-100 score of the top-ranked candidate cause from the latest revision; made it nullable when no ranked causes exist.
- Used idiomatic asynchronous promise resolution (`.then(...)` / `.catch(...)`) with `isCurrent` cancellation guards for React 19 component data fetching, eliminating synchronous state updates in effects and ensuring full compliance with `react-hooks/set-state-in-effect`.
- Preserved zero as a valid score (`0/100`) while clamping the visual bar width to `[0, 100]`.
- Strictly preserved protected teammate file `frontend/app/(dashboard)/cases/[id]/page.tsx` without staging or modifying it.

### Verification results

- **PostgreSQL Integration Tests**: `backend/.venv/Scripts/python.exe -m pytest -v backend/tests/integration/test_analytics_api.py --basetemp .phase3-analytics-pytest-tmp` (6 passed in 3.41s) with `TEST_DATABASE_URL="postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"`.
- **Full Backend Suite**: `backend/.venv/Scripts/python.exe -m pytest -q --basetemp .phase3-full-pytest-tmp` (472 passed, 42 warnings in 53.17s).
- **Focused ESLint**: `npx eslint` across all 20 task-owned files passed with 0 errors and 0 warnings.
- **Production Build**: `npm run build` in `frontend/` passed cleanly (Compiled in 998ms, TypeScript finished in 3.2s, 13/13 static pages generated).
- **Repository-wide Lint**: `npm run lint` decreased from 29 errors / 15 warnings down to 15 errors / 9 warnings (0 errors in task-owned files).
- **Targeted Grep Search**: `git grep -n -E "mockFallbackReports|Dispensing Line A|Nozzle Restriction|AI Diagnostic Status|diagnostic accuracy|engine accuracy|% confidence|\b92(\.0)?\b|\b90\b" ...` confirmed zero fabricated fallback strings in task-owned files.
- **Task Validation**: `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-028-truthful-dynamic-demo-surfaces.md` reported `VALID`.
- **Whitespace Check**: `git diff --check` passed cleanly with 0 errors.

### Limitations and follow-up

- Troubleshooting checklist outcomes, verification lifecycle actions (`EngineerVerification`, `TroubleshootingChecklist`), and rejection/exhaustion logic remain deferred to Phase 3B.
- The protected teammate working-tree modification in `frontend/app/(dashboard)/cases/[id]/page.tsx` was not touched, staged, or committed.

### Proposed commit message

`fix(analytics): make demo surfaces data truthful`
