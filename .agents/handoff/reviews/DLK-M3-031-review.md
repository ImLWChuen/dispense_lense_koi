---
task_id: DLK-M3-031
reviewed_commit: 4e868160d0701a8e904349f2d18c112a2e396c97
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-031

## Decision

Changes requested for one remaining documentation correction. The correction commit resolves R2-R4 and the substantive workflow/order problems in R1. The runbook still names four buttons/panels differently from the checked-in UI and does not actually label its entered demo data as synthetic.

Keep this as a correction round within DLK-M3-031. No new feature task is released.

## Correction review: `4e868160d0701a8e904349f2d18c112a2e396c97`

### Resolved

- R1 workflow/order is substantively resolved: the runbook uses the actual new-diagnosis inputs, puts optional image analysis before `Start Diagnosis`, uses ACT01 only conditionally with `blockage_found`, and represents recovery/verification through their real free-text and pass/fail controls.
- R2 is resolved: README, runbook, and normative task wording use `Evidence Support /100`, explicitly reject probability/Bayesian interpretation, and avoid fixed ranking scores.
- R3 is resolved: README requires Node.js 20.9.0+, and preflight routes the actual/overridden version through `Test-NodeVersionSupported`. Reviewer replay observed rejection of v18.19.0 and acceptance of v20.9.0 and v22.12.0 at the Node decision.
- R4 is resolved: missing/blank database configuration fails, configured input reports only its source, and reviewer replay with a synthetic credential marker found no password or complete PostgreSQL URL in output.

### R5 — Runbook labels and synthetic-data instructions still do not match the demonstrable UI (medium)

- `docs/demo/local-demo-runbook.md:79-80` says click `Analyze Image`; the rendered button is `Analyze`.
- `docs/demo/local-demo-runbook.md:97` calls the rendered `Evidence` card `Evidence Panel`.
- `docs/demo/local-demo-runbook.md:113` says click `Record Check Finding` (or an unspecified submit button); the rendered control is `Submit Check Result`.
- `docs/demo/local-demo-runbook.md:138` says click `Submit Verification Result`; the selected-pass control renders `Submit Passed Verification` (`Submit Failed Verification` for the failed branch).
- `docs/demo/local-demo-runbook.md:184` calls `Dispensing Line A` and `Lead Technician #104` synthetic identifiers. The first is an ordinary fixed select value, and the current UI has no editable operator field for the second. The actual entered symptom, material, check, recovery, and verification strings are not marked as synthetic.
- Replace the four labels with their exact rendered text. Mark the data that can actually be entered as synthetic, for example by prefixing the symptom and free-text notes with `[SYNTHETIC DEMO]` and using a clearly synthetic material description. Remove the nonexistent operator-entry example and explain that the current prototype records a generic technician actor.

### Correction verification

- Exact correction commit and allowed-path diff inspected; no product code, dependency, schema, or diagnostic-semantic change.
- PowerShell AST parse: 3/3 scripts passed.
- Node decision replay: v18.19.0 rejected; v20.9.0 and v22.12.0 accepted at the production helper.
- Database-output replay: blank override rejected; configured synthetic URL accepted without emitting its URL or password marker.
- Focused backend health tests: 2 passed.
- Frontend lint: passed with zero reported findings.
- Frontend production build: passed TypeScript and generated all 13 routes.
- Task validation: `VALID`; committed whitespace check passed.
- Docker-backed positive startup remains unavailable to this reviewer because the local Docker engine cannot be accessed. The safe failure path remains correct.

## Acceptance evidence

- Reviewed exact local commit `5803f1a1f7ef909899f021ddcd77b85dc0c79f0e` on `backend-database`.
- The commit changes only the eight authorized task/handoff/script/documentation paths. Unrelated untracked files remain outside the commit.
- All three PowerShell scripts parse successfully through `System.Management.Automation.Language.Parser.ParseFile`.
- Reviewer preflight returned non-zero and correctly distinguished the unavailable Docker engine while leaving ports and processes untouched.
- Reviewer `start-db.ps1` run returned non-zero with the required Docker Desktop/Linux-engine recovery instruction.
- Reviewer `verify-demo.ps1` run returned non-zero when neither application service was running and issued the expected startup instructions.
- Focused backend health test: 2 passed.
- Frontend lint: passed with zero reported findings.
- Frontend production build: passed; TypeScript completed and all 13 pages/routes generated.
- Task validation: `VALID`.
- Committed whitespace check: passed.
- The implementer's successful live Docker/startup/identity report could not be independently repeated in this reviewer environment because Docker engine access is currently unavailable. This limitation does not cause the findings below.

## Findings

### R1 — The timed runbook instructs operators to use controls and domain values that do not exist (high)

- `docs/demo/local-demo-runbook.md:67-75` directs the operator to enter `SYNTHETIC-LINE-04`, dispensing method, target diameter, pressure, and nozzle gauge, then click `Create Case`.
- The checked-in `ProblemForm` exposes a fixed Equipment/Line select (`Dispensing Line A-D`), free-text Material Type, the six defect cards, three manual-observation selects, and the `Start Diagnosis` button. It has no dispensing-method, target-diameter, pressure, or nozzle-gauge controls, and the fixed equipment select cannot accept `SYNTHETIC-LINE-04`.
- `docs/demo/local-demo-runbook.md:80-93` places image upload after case creation. The image upload/calibration control is on `/diagnosis/new`; analyzed image observations are collected into the case request before `Start Diagnosis` navigates away. The documented order cannot attach that image evidence to the created case.
- `docs/demo/local-demo-runbook.md:115-137` invents workflow labels and inputs: ACT01 is `Inspect Nozzle`, its supporting canonical outcome is `blockage_found`, not `RESTRICTION_OBSERVED`; recovery is free-text and must not be relabelled as `ACT01 - Replace Dispensing Tip`; verification is pass/fail plus free-text details and has no `VERIFY01`; the UI has no editable `Actor` field.
- The optional image step claims exact diameter/coverage/classification outputs without providing a validated fixture that produces them. A rehearsal operator therefore cannot depend on those values.
- Rewrite the default demonstration path from the actual rendered controls and labels. Put optional image configuration before `Start Diagnosis`. Use `Completed` + `Supports` + `blockage_found` only when ACT01 is the actual recommended next check. Treat recovery and verification as the free-text/boolean controls they are. Do not claim exact outputs or rankings unless a rehearsed fixture/run produced them; instruct the narrator to state the values actually displayed. The default no-image route must remain a complete runnable fallback.

### R2 — Documentation misrepresents deterministic evidence scores as probabilities and a Bayesian model (high)

- `README.md:7,144` calls scores numeric confidence percentages/calculations.
- `docs/demo/local-demo-runbook.md:99-120` presents cause scores as percentages such as `74% confidence` and `92%` and gives fixed ranking results that are not guaranteed by the documented inputs.
- `docs/demo/local-demo-runbook.md:158` calls the engine a Bayesian scoring model.
- The accepted contract in `docs/api/frontend-backend-contract.md:141-151` states that the deterministic 0-100 value is an evidence-support metric, is not a calibrated probability, does not sum to 100 across causes, and must be labelled `Evidence Support` or `Evidence Support /100` rather than confidence/probability/accuracy. The engine does not implement a Bayesian model.
- Replace every confidence-percentage/Bayesian claim in README, the runbook, and the DLK-M3-031 task wording with the accepted `Evidence Support /100` description. Do not prescribe fixed cause scores; use the actual displayed ordering and explain supporting and contradicting evidence.

### R3 — Fresh-clone prerequisites accept a Node.js version that cannot run the checked-in Next.js release (high)

- `README.md:18` says Node.js 18+ is supported, and `scripts/demo-preflight.ps1:99-105` accepts any installed Node version while recommending v18+.
- The installed checked-in Next.js 16.3.4 package declares `engines.node: >=20.9.0` in `frontend/node_modules/next/package.json`.
- A teammate following the quickstart with Node 18 can pass preflight but fail dependency install/build/startup, defeating the task's fresh-clone outcome.
- Require Node.js `>=20.9.0` in README and preflight. Parse the installed `node --version` value and fail with a non-zero actionable message when it is below the checked-in Next requirement. Add a dependency-free way to exercise the unsupported-version decision logic without changing the machine's installed Node version.

### R4 — Preflight prints a complete credential-bearing database URL and treats an empty `.env` value as configured (medium)

- `scripts/demo-preflight.ps1:156-159` prints the complete default PostgreSQL URL, including username and password, when configuration is absent. This directly violates the task requirement that scripts never print credentials or complete database URLs.
- `scripts/demo-preflight.ps1:137-150` treats any matching `DATABASE_URL=` line as configured, including an empty or whitespace-only value. The next migration/backend step then fails even though preflight reported a pass.
- Keep the corrective message secret-safe: point to `.env.example` or the README without echoing a URL. Parse only enough to determine that the selected environment or `.env` value is nonblank; never display the value. Add controlled checks for missing, blank, and nonblank configuration while preserving `.env` and the caller's environment.

## Follow-up

Correct R5 within DLK-M3-031 and update its implementation report with fresh evidence. Preserve the current safe startup behavior and resolved R1-R4 work. Do not change application product code, API/database contracts, diagnostic rules, weights, or dependencies.

Required correction verification:

1. Static cross-check against the rendered UI source for the four corrected control labels.
2. Static check that the runbook's entered symptom/material/notes are explicitly marked synthetic and that it no longer suggests an editable operator identity.
3. Frontend lint/build, task validation, and whitespace check. Product/backend tests do not need to be repeated for this documentation-only correction.

The correction should be one local commit on `backend-database`. Do not push, merge, create/update a pull request, or touch unrelated untracked files. Review and queue updates from this review remain uncommitted for inclusion in that correction commit.
