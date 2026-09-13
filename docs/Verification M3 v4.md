# DLK-M3-013 — REQUIRED MEMBER 2 SEMANTIC CORRECTION AND VERIFICATION

## IMPORTANT

Do **not** conclude that the current implementation is good enough based only on existing tests or the fact that the diagnosis engine runs.

The purpose of this task is to specifically verify and correct the **troubleshooting check/result semantics** before DLK-M3-013 is released.

The following requirements are mandatory and must be explicitly checked against the current code.

## Exact readiness requirements

- **remove or explicitly approve automatic cause confirmation;**
- **establish explicit technician confirmation semantics if that remains the project requirement;**
- **audit `_ACTION_OUTCOME_TO_OBSERVATION`;**
- **ensure each check outcome maps only to a fact actually demonstrated by that outcome;**
- **add tests for the corrected mappings;**
- **rerun the Phase 9–11/check-result tests;**
- **merge those corrections to `main`.**

The especially important separation remains:

```text
Check completed
≠
Check supports cause
≠
Cause confirmed
≠
Issue resolved
```

Those four concepts must stay separate.

---

# TASK OBJECTIVE

You must inspect the existing implementation and determine whether the current code actually satisfies every requirement above.

Do not merely inspect filenames or existing test names.

Trace the actual runtime logic:

```text
Troubleshooting Check
        ↓
Technician submits outcome
        ↓
Outcome handler / mapping
        ↓
Observation / evidence
        ↓
Evidence engine
        ↓
Cause ranking
        ↓
Cause confirmation state
        ↓
Issue resolution state
        ↓
Diagnosis revision
```

The final goal is:

```text
Member 2 fixes check semantics
        ↓
tests pass
        ↓
changes merged to main
        ↓
workspace synchronized
        ↓
latest code can be independently verified
        ↓
DLK-M3-013 can be released
```

---

# PHASE 1 — INSPECT THE CURRENT IMPLEMENTATION

Before making changes, inspect the repository thoroughly.

## Step 1. Locate the relevant components

Find the actual implementation of:

```text
action_planner.py
evidence_engine.py
cause_ranker.py
engine.py

actions.json
rules.json

Action model
DiagnosisAction model
ActionResult / CheckResult model
Observation model
Diagnosis model
AnalysisRevision model

Outcome handler
Check-result handler
Action-result handler
Cause confirmation logic
Issue resolution logic
```

If the repository uses different filenames, locate the equivalent components.

Do **not** assume the expected filenames exist.

---

## Step 2. Search specifically for automatic state transitions

Search the entire backend for:

```text
confirm
confirmed
cause_confirmed
resolve
resolved
issue_resolved
supports
outcome
finding
completed
success
action_outcome
```

Find every location where these values are changed.

For every location, record:

| File | Function | Current behaviour | Trigger | Correct? |
|---|---|---|---|---|
| ... | ... | ... | ... | PASS/FAIL |

Pay special attention to code similar to:

```python
if action.completed:
    cause.confirmed = True
```

or:

```python
if outcome == "SUCCESS":
    issue.resolved = True
```

These transitions must not be accepted without checking the project semantics.

---

# PHASE 2 — CHECK AUTOMATIC CAUSE CONFIRMATION

## Requirement

> **remove or explicitly approve automatic cause confirmation;**

This must be treated as a blocking requirement.

## Step 3. Determine current behaviour

Find out whether the current system does this:

```text
check completed
    ↓
check supports cause
    ↓
cause automatically confirmed
```

or:

```text
check outcome = success
    ↓
cause confirmed
```

or any equivalent automatic transition.

If automatic cause confirmation exists:

### Option A — Remove it

This is the preferred fix unless the knowledge contract explicitly defines a check/result as confirmatory.

The normal flow should become:

```text
Check completed
        ↓
Check result
        ↓
Evidence generated
        ↓
Cause support updated
        ↓
Cause remains suspected/unconfirmed
```

### Option B — Explicitly approve it

Only retain automatic cause confirmation if there is a clearly defined knowledge rule saying:

```text
this exact check
+
this exact result
=
confirmatory evidence
```

Do not infer confirmation merely because the result supports a cause.

---

# PHASE 3 — ESTABLISH TECHNICIAN CONFIRMATION SEMANTICS

## Requirement

> **establish explicit technician confirmation semantics if that remains the project requirement;**

## Step 4. Verify how the technician explicitly confirms a cause

There must be a clear distinction between:

```text
AI says:
"Air bubble is the highest-supported cause."
```

and:

```text
Technician/Engineer explicitly confirms:
"Air bubble is confirmed."
```

The first does **not** automatically become the second.

Determine what the repository currently uses for explicit confirmation:

```text
confirmed_by
confirmation_status
verification_status
engineer_confirmation
technician_confirmation
```

or equivalent.

---

## Step 5. Verify explicit confirmation flow

The code should support something conceptually equivalent to:

```text
AI ranking
    ↓
Cause = Suspected
    ↓
Recommended check
    ↓
Supporting result
    ↓
Cause remains Suspected
    ↓
Technician/Engineer explicitly confirms
    ↓
Cause = Confirmed
```

The exact field names should follow the existing project architecture.

Do not create a second competing confirmation mechanism.

---

# PHASE 4 — AUDIT `_ACTION_OUTCOME_TO_OBSERVATION`

## Requirement

> **audit `_ACTION_OUTCOME_TO_OBSERVATION`;**

This is a mandatory code-level audit.

## Step 6. Locate the mapping

Find the exact implementation of:

```python
_ACTION_OUTCOME_TO_OBSERVATION
```

If it is located elsewhere or renamed, locate its equivalent.

Print/review the entire mapping.

For every entry, determine:

```text
action/check ID
outcome
generated observation
observation value
effect on evidence
effect on cause ranking
```

---

# PHASE 5 — VERIFY THAT EACH MAPPING REPRESENTS ONLY WHAT THE RESULT PROVES

## Requirement

> **ensure each check outcome maps only to a fact actually demonstrated by that outcome;**

This is the core semantic correction.

For every mapping ask:

> What exact fact did the technician actually observe?

Then ask:

> Does the generated observation contain only that fact?

### Example of an acceptable mapping

```text
Check:
Inspect nozzle

Outcome:
Visible blockage observed

Observation:
nozzle_condition = blocked
```

This is directly demonstrated.

---

### Example of an unacceptable mapping

```text
Check:
Inspect nozzle

Outcome:
Visible blockage observed

Mapping:
nozzle_condition = blocked
dispensing_pressure = incorrect
material_viscosity = abnormal
root_cause = nozzle_blockage
issue = resolved
```

This is invalid because the check result only demonstrated nozzle blockage.

It did **not** directly demonstrate:

```text
pressure problem
material viscosity problem
confirmed root cause
resolved issue
```

Those require separate evidence or explicit confirmation.

---

## Step 7. Audit every outcome individually

Create an audit table:

| Check | Outcome | Current mapping | Fact actually demonstrated | Extra inference? | Correct? |
|---|---|---|---|---|---|
| CHK01 | ... | ... | ... | ... | PASS/FAIL |
| CHK01 | ... | ... | ... | ... | PASS/FAIL |
| CHK02 | ... | ... | ... | ... | PASS/FAIL |

Do not skip "normal-looking" mappings.

Every supported result must be checked.

---

# PHASE 6 — VERIFY UNKNOWN / INCONCLUSIVE RESULTS

## Step 8. Check UNKNOWN

For every check supporting `UNKNOWN`, verify that:

```text
UNKNOWN
    ↓
No fabricated observation
    ↓
No fabricated contradiction
    ↓
No cause confirmation
    ↓
No issue resolution
```

---

## Step 9. Check INCONCLUSIVE

Verify:

```text
INCONCLUSIVE
```

does not mean:

```text
SUPPORTS
```

or:

```text
CONTRADICTS
```

unless the project knowledge explicitly defines such semantics.

Normally:

```text
INCONCLUSIVE
    ↓
insufficient diagnostic evidence
```

---

## Step 10. Check BLOCKED

A blocked action is not the same as a negative finding.

For example:

```text
Execution:
BLOCKED

Finding:
UNKNOWN
```

must not become:

```text
no blockage found
```

or:

```text
cause contradicted
```

The system should preserve:

```text
check could not be completed
```

---

# PHASE 7 — CHECK EXECUTION STATE VS FINDING

## Step 11. Verify the two concepts are separate

The implementation must distinguish:

```text
Execution state
```

from:

```text
Finding
```

For example:

```text
COMPLETED + SUPPORTS
COMPLETED + INCONCLUSIVE
COMPLETED + UNKNOWN
BLOCKED + UNKNOWN
```

are all different valid states.

Search for any code that derives finding directly from execution state.

Bad:

```python
if status == "COMPLETED":
    finding = "SUPPORTS"
```

Correct:

```python
execution_status = "COMPLETED"
finding = technician_submitted_finding
```

unless a specific contract explicitly defines another behaviour.

---

# PHASE 8 — CHECK CAUSE CONFIRMATION

## Step 12. Search every cause-confirmation transition

Find all code paths that assign:

```text
cause_confirmed = true
```

or equivalent.

For every one, document:

```text
Trigger:
Required evidence:
Who initiated confirmation:
Is this explicitly defined as confirmatory?
```

---

## Step 13. Apply the confirmation rule

A normal supporting outcome should produce:

```text
Cause = Suspected
```

not:

```text
Cause = Confirmed
```

unless the mapping explicitly defines the result as confirmatory.

Example:

```text
Check result:
"No visible nozzle blockage"

→ contradicts nozzle blockage
→ ranking decreases
→ cause not confirmed
```

Example:

```text
Check result:
"Observed nozzle blockage"

→ supports nozzle blockage
→ ranking increases
→ cause remains suspected
```

Then:

```text
Technician/Engineer explicitly confirms
→ cause becomes confirmed
```

This is the safe default unless the existing project specification explicitly says otherwise.

---

# PHASE 9 — CHECK ISSUE RESOLUTION

## Step 14. Search every issue-resolution transition

Find all locations that assign:

```text
issue_resolved = true
```

or equivalent.

Verify that:

```text
check completed
```

does not automatically become:

```text
issue resolved
```

and:

```text
cause confirmed
```

does not automatically become:

```text
issue resolved
```

A valid resolution path should require explicit evidence that acceptable dispensing has been restored, according to the project's defined resolution semantics.

---

# PHASE 10 — ADD REGRESSION TESTS FOR CORRECTED MAPPINGS

## Requirement

> **add tests for the corrected mappings;**

Do not only add tests that verify code execution.

Tests must verify **semantic correctness**.

---

## Step 15. Test direct outcome mapping

For each important action:

```text
check
+
outcome
→
expected observation
```

Example:

```python
def test_nozzle_blockage_result_maps_only_to_nozzle_observation():
    result = handle_check_result(
        check_id="CHK_NOZZLE",
        outcome="BLOCKAGE_OBSERVED"
    )

    assert result.observations == [
        Observation(
            type="nozzle_condition",
            value="blocked"
        )
    ]
```

Also verify that it does NOT create:

```text
pressure_problem
material_problem
cause_confirmed
issue_resolved
```

unless explicitly defined.

---

## Step 16. Test UNKNOWN

```python
def test_unknown_does_not_create_evidence():
    result = handle_check_result(
        check_id="CHK_NOZZLE",
        outcome="UNKNOWN"
    )

    assert result.observations == []
```

---

## Step 17. Test INCONCLUSIVE

```python
def test_inconclusive_does_not_confirm_cause():
    result = ...

    assert result.finding == "INCONCLUSIVE"
    assert result.cause_status != "CONFIRMED"
```

---

## Step 18. Test BLOCKED

```python
def test_blocked_check_does_not_create_negative_evidence():
    result = ...

    assert result.execution_status == "BLOCKED"
    assert result.finding == "UNKNOWN"
    assert result.observations == []
```

---

## Step 19. Test supporting result without confirmation

```python
def test_supporting_result_does_not_auto_confirm_cause():
    result = ...

    assert result.finding == "SUPPORTS"
    assert result.cause_status != "CONFIRMED"
```

---

## Step 20. Test explicit confirmation separately

If the project has explicit technician/engineer confirmation:

```python
def test_explicit_confirmation_confirms_cause():
    result = confirm_cause(...)

    assert result.cause_status == "CONFIRMED"
```

This must be a separate operation from the check-result handler.

---

# PHASE 11 — RERUN PHASE 9–11 / CHECK-RESULT TESTS

## Requirement

> **rerun the Phase 9–11/check-result tests;**

After correcting the mappings:

1. Run the unit tests.
2. Run evidence-engine tests.
3. Run cause-ranking tests.
4. Run action-planner tests.
5. Run diagnosis-engine tests.
6. Run check-result tests.
7. Run revision/update tests.
8. Run integration tests involving diagnosis updates.

Do not report only:

```text
tests passed
```

Return:

```text
Total tests:
Passed:
Failed:
Skipped:
Errors:
```

For any failure:

```text
Test:
Failure:
Root cause:
Fix:
Retest result:
```

---

# PHASE 12 — RUN THE COMPLETE CHECK-RESULT INTEGRATION FLOW

After the unit tests pass, run one complete real case.

Use:

```text
Existing diagnosis
    ↓
Recommended troubleshooting check
    ↓
Technician submits result
    ↓
Check-result handler
    ↓
Observation/evidence mapping
    ↓
Evidence engine
    ↓
Cause ranker
    ↓
Next question/check
    ↓
Revision N+1
```

Verify that:

```text
Check completed
```

does not automatically produce:

```text
Cause confirmed
Issue resolved
```

unless explicitly justified.

---

# PHASE 13 — CHECK REVISION INTEGRITY

Verify:

```text
Revision N
```

remains unchanged.

After the technician result:

```text
Revision N+1
```

must contain:

```text
old evidence
+
new check result
+
new observation/evidence
+
updated ranking
```

Do not mutate Revision N.

---

# PHASE 14 — PREVENT DUPLICATE EVIDENCE INFLATION

Submit the exact same troubleshooting result twice.

Example:

```text
CHK_NOZZLE
BLOCKAGE_OBSERVED
```

First submission:

```text
evidence added
```

Second identical submission:

```text
no duplicate diagnostic weight
```

The system may retain the repeated execution record, but the cause ranking must not artificially increase because the same fact was submitted twice.

---

# PHASE 15 — FINAL SEMANTIC AUDIT

After all code and tests pass, produce this exact table:

| Requirement | Result | Evidence |
|---|---|---|
| remove or explicitly approve automatic cause confirmation | PASS/FAIL | file + function + test |
| establish explicit technician confirmation semantics if that remains the project requirement | PASS/FAIL | file + function + test |
| audit `_ACTION_OUTCOME_TO_OBSERVATION` | PASS/FAIL | file + mapping |
| ensure each check outcome maps only to a fact actually demonstrated by that outcome | PASS/FAIL | mapping test |
| add tests for the corrected mappings | PASS/FAIL | test files |
| rerun the Phase 9–11/check-result tests | PASS/FAIL | test result |
| merge those corrections to `main` | PASS/FAIL | commit/merge |

---

# PHASE 16 — GIT / MERGE REQUIREMENT

## Requirement

> **merge those corrections to `main`.**

Only after:

```text
semantic audit
↓
tests
↓
integration verification
```

should the changes be committed.

The commit should contain only the relevant fixes.

Recommended commit message:

```text
fix: correct troubleshooting outcome semantics
```

Then:

```text
1. commit changes
2. push branch
3. merge to main
4. pull latest main
5. verify working tree
6. rerun critical tests on main
```

Do not tell the user the fix is merged if it has only been committed locally.

---

# PHASE 17 — FINAL REPORT TO USER

Return:

```text
DLK-M3-013 MEMBER 2 READINESS REPORT

Automatic cause confirmation:
PASS / FAIL

Technician confirmation semantics:
PASS / FAIL

_ACTION_OUTCOME_TO_OBSERVATION audit:
PASS / FAIL

Outcome mapping correctness:
PASS / FAIL

UNKNOWN / INCONCLUSIVE handling:
PASS / FAIL

Execution state vs finding separation:
PASS / FAIL

Supporting result vs cause confirmation:
PASS / FAIL

Duplicate evidence protection:
PASS / FAIL

Regression tests:
PASS / FAIL

Integration test:
PASS / FAIL

Merged to main:
YES / NO
```

Then give:

```text
Blocking issues:
...

Fixes made:
...

Tests run:
...

Commit:
...

Merge:
...
```

---

# FINAL RELEASE GATE

Do **not** declare DLK-M3-013 ready unless all of these are true:

```text
[ ] automatic cause confirmation removed or explicitly approved
[ ] explicit technician confirmation semantics established
[ ] _ACTION_OUTCOME_TO_OBSERVATION audited
[ ] every outcome mapping is semantically correct
[ ] UNKNOWN does not fabricate evidence
[ ] INCONCLUSIVE does not fabricate evidence
[ ] BLOCKED does not become a negative finding
[ ] execution state is separate from finding
[ ] SUPPORTS does not automatically mean CONFIRMED
[ ] CONFIRMED does not automatically mean RESOLVED
[ ] duplicate results do not inflate evidence
[ ] corrected mappings have automated tests
[ ] Phase 9–11/check-result tests pass
[ ] end-to-end check-result flow passes
[ ] revision N remains unchanged
[ ] revision N+1 is correctly created
[ ] corrections are merged to main
```

# FINAL INSTRUCTION

**Do not respond that the implementation is already good enough simply because existing tests pass.**

The task is specifically to **audit the semantic correctness of troubleshooting-result handling**, especially `_ACTION_OUTCOME_TO_OBSERVATION` and automatic cause confirmation.

If the current implementation violates any requirement above, **make the minimum necessary correction, add regression tests, rerun the affected test suite, and only then report readiness for DLK-M3-013.**

The reason for this strict check is that the overall project architecture explicitly treats the diagnosis engine as evidence-based and keeps observations, inferred causes, confirmation, and resolution distinct. The planning package also requires separate records for root-cause confirmation and issue resolution and treats explicit outcomes/feedback as part of the first-prototype scope.
