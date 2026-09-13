# DLK-M3-013 — Member 2 Troubleshooting Check / Outcome Contract Verification Plan

## 1. Objective

Verify that the existing Member 2 implementation is ready for:

**DLK-M3-013 — Submit troubleshooting check result and append new diagnosis revision API**

This is a **verification and minimum-fix task**.

Do not redesign the diagnostic architecture.

Do not implement unrelated later features.

Do not implement:
- LLM integration unless an existing component is required for testing;
- computer vision;
- historical retrieval;
- PDF reporting;
- production deployment;
- advanced recovery workflows.

The goal is to establish a stable contract for:

```text
Selected troubleshooting check
        ↓
Technician executes / attempts check
        ↓
Technician submits result
        ↓
Check-result handler interprets result
        ↓
Execution state + finding are stored separately
        ↓
Finding becomes observation/evidence when applicable
        ↓
DiagnosticEngine reruns
        ↓
Updated ranking
        ↓
Updated next question / next check
        ↓
Revision N+1
        ↓
Return updated diagnosis
```

---

# 2. Critical Principle

The implementation MUST preserve these four independent concepts:

```text
Check completed
        ≠
Check supports cause
        ≠
Cause confirmed
        ≠
Issue resolved
```

Never implement logic equivalent to:

```python
if check_completed:
    cause_confirmed = True
    issue_resolved = True
```

A completed check only states that the technician completed the execution step.

Its diagnostic finding must be recorded separately.

---

# 3. FIRST — INSPECT THE EXISTING REPOSITORY

Before modifying code:

1. Inspect the repository structure.
2. Locate all existing troubleshooting/check/action code.
3. Locate:
   - `action_planner.py`
   - `actions.json`
   - check/action models
   - check/action schemas
   - `diagnosis_action.py`
   - check-result handler, if one exists
   - `CheckResult`
   - `TroubleshootingCheck`
   - `Observation`
   - `Evidence`
   - `AnalysisRevision`
   - diagnosis engine
   - evidence engine
   - cause ranker
   - existing check/action tests
4. Search for hard-coded check IDs and outcome names.
5. Search for any code that automatically sets cause confirmation or issue resolution after a check.
6. Search for duplicate or conflicting action/outcome definitions.

Do not create a new handler if the repository already has an equivalent component.

---

# 4. READINESS REQUIREMENT 1 — STABLE TROUBLESHOOTING CHECK IDs

## Goal

Every supported troubleshooting check/action must have one stable identifier.

Example:

```text
CHK_N03_NOZZLE_INSPECTION
CHK_S01_SUPPLY_INSPECTION
CHK_M01_MATERIAL_CONDITION
```

The exact naming convention must follow the existing repository if one already exists.

## Verify

For every supported check:

1. ID exists.
2. ID is unique.
3. ID is stable.
4. ID is used consistently by:
   - knowledge base;
   - action planner;
   - backend schema;
   - result handler;
   - persistence;
   - tests.
5. No duplicate definitions exist under different IDs.
6. No module relies on display text instead of the stable ID.

## Required audit

Produce:

| Check ID | Check name | Knowledge definition | Handler reference | Persistence reference | Test | Status |
|---|---|---|---|---|---|---|
| CHK... | ... | ... | ... | ... | ... | PASS/FAIL |

## Pass condition

Every supported MVP check can be identified uniquely by ID throughout the complete backend flow.

---

# 5. READINESS REQUIREMENT 2 — STABLE TECHNICIAN OUTCOME VALUES

## Goal

Define the supported result/outcome vocabulary clearly.

Separate:

### A. Execution state

Example:

```text
PENDING
IN_PROGRESS
COMPLETED
BLOCKED
SKIPPED
```

### B. Diagnostic finding

Example:

```text
SUPPORTS
CONTRADICTS
INCONCLUSIVE
UNKNOWN
NOT_APPLICABLE
```

Do not merge these into one enum.

For example:

```text
execution_status = COMPLETED
finding = SUPPORTS
```

is valid.

Also:

```text
execution_status = BLOCKED
finding = UNKNOWN
```

is valid.

And:

```text
execution_status = COMPLETED
finding = INCONCLUSIVE
```

is valid.

## Verify

1. List all currently supported execution states.
2. List all currently supported findings.
3. Confirm each has stable identifiers.
4. Confirm frontend/API/backend representations agree.
5. Confirm there are no conflicting names such as:

```text
FAILED
NOT_OBSERVED
NEGATIVE
UNSUCCESSFUL
```

being used interchangeably unless explicitly defined.

6. Confirm the semantics of each value are documented.

## Required output

Generate:

| Execution state | Meaning |
|---|---|
| PENDING | ... |
| IN_PROGRESS | ... |
| COMPLETED | ... |
| BLOCKED | ... |

and:

| Finding | Meaning |
|---|---|
| SUPPORTS | ... |
| CONTRADICTS | ... |
| INCONCLUSIVE | ... |
| UNKNOWN | ... |
| NOT_APPLICABLE | ... |

## Pass condition

There is exactly one authoritative definition of each supported execution/result value.

---

# 6. READINESS REQUIREMENT 3 — CHECK RESULT → OBSERVATION / EVIDENCE MAPPING

## Goal

Every meaningful technician outcome must have a defined semantic mapping.

The flow must be:

```text
Check ID
+
Technician result
        ↓
CheckResultHandler
        ↓
Observation / Evidence
```

Do not let the LLM decide this mapping.

Do not create mappings only in application code if the knowledge base is supposed to be the source of truth.

## Example

Suppose:

```text
Check:
CHK_N03_NOZZLE_INSPECTION
```

Possible result:

```text
Finding = BLOCKAGE_OBSERVED
```

Expected semantic output could be:

```text
Observation:
type = nozzle_condition
value = blocked
provenance = USER_CHECK_RESULT
```

Another result:

```text
Finding = NO_BLOCKAGE_OBSERVED
```

could map to:

```text
Observation:
type = nozzle_condition
value = clear
provenance = USER_CHECK_RESULT
```

The exact mappings must come from the project's existing knowledge definitions.

## Audit every mapping

Verify:

```text
check_id
outcome/result
observation_type
observation_value
provenance
confidence, if used
affected hypotheses
```

## Required mapping table

Produce:

| Check ID | Technician result | Observation type | Observation value | Provenance | Cause impact | Status |
|---|---|---|---|---|---|---|
| CHK... | ... | ... | ... | USER_CHECK_RESULT | ... | PASS |
| CHK... | ... | ... | ... | USER_CHECK_RESULT | ... | PASS |

## Pass condition

Every supported check result has one explicit and testable interpretation.

No check result has contradictory mappings.

---

# 7. READINESS REQUIREMENT 4 — UNKNOWN / INCONCLUSIVE MUST NOT FABRICATE EVIDENCE

This is a hard requirement.

## UNKNOWN

Example:

```text
execution_status = COMPLETED
finding = UNKNOWN
```

must NOT become:

```text
cause X contradicted
```

or:

```text
cause Y supported
```

unless the knowledge definition explicitly says otherwise.

## INCONCLUSIVE

Example:

```text
execution_status = COMPLETED
finding = INCONCLUSIVE
```

must not become:

```text
cause confirmed
```

or:

```text
cause disproved
```

unless explicitly defined.

## BLOCKED

Example:

```text
execution_status = BLOCKED
finding = UNKNOWN
```

must not become:

```text
check passed
```

or:

```text
cause contradicted
```

## NOT_APPLICABLE

Verify that it does not automatically become contradiction.

Its meaning must be explicitly defined by the check contract.

## Required tests

Create tests for at least:

```text
UNKNOWN
INCONCLUSIVE
BLOCKED
NOT_APPLICABLE
```

Each test must assert:

```text
no unsupported evidence is created
```

---

# 8. READINESS REQUIREMENT 5 — EXECUTION STATE AND CHECK FINDING MUST REMAIN SEPARATE

## Goal

Verify that the system stores two independent concepts.

Example 1:

```text
execution_status = COMPLETED
finding = SUPPORTS
```

Example 2:

```text
execution_status = COMPLETED
finding = INCONCLUSIVE
```

Example 3:

```text
execution_status = BLOCKED
finding = UNKNOWN
```

These must remain distinct.

## Verify persistence

Inspect the database/model/schema and confirm the representation can store both dimensions.

Do not infer finding from execution status.

Do not infer execution status from finding.

## Negative test

Attempt:

```text
execution_status = COMPLETED
```

without a finding.

The system should allow this only if the contract explicitly defines a valid incomplete/unknown finding state.

Likewise:

```text
finding = SUPPORTS
```

must not automatically imply:

```text
execution_status = COMPLETED
```

unless the API contract explicitly requires it.

## Pass condition

Both values can be changed independently and persisted independently.

---

# 9. READINESS REQUIREMENT 6 — CHECK SUPPORT DOES NOT AUTOMATICALLY CONFIRM ROOT CAUSE

This is one of the most important tests.

Example:

```text
Check:
Inspect nozzle

Result:
Supports nozzle restriction
```

Expected:

```text
finding = SUPPORTS
cause = SUSPECTED
```

NOT automatically:

```text
cause = CONFIRMED
```

unless the knowledge definition explicitly marks that check/result combination as confirmatory.

## Therefore

Each check/result mapping must define whether it is:

```text
supporting evidence
contradicting evidence
confirmatory evidence
inconclusive
```

Do not infer confirmation simply because a check supports a cause.

## Required implementation rule

Use an explicit property if the existing knowledge model supports it, for example:

```json
{
  "check_id": "CHK_N03",
  "result": "BLOCKAGE_OBSERVED",
  "effect": "SUPPORTS",
  "confirmatory": false
}
```

Do not invent this exact schema if the repository already has an equivalent representation.

Reuse the existing knowledge model where possible.

## Required tests

Test:

```text
supporting result
→ cause remains unconfirmed
```

and, if a formally confirmatory result exists:

```text
confirmatory result
→ cause may become confirmed
```

The latter should happen only when the knowledge contract explicitly defines it.

---

# 10. READINESS REQUIREMENT 7 — DETERMINISTIC RERUN AFTER CHECK RESULT

## Goal

Verify:

```text
StructuredCase N
+
CheckResult
        ↓
new observation/evidence
        ↓
DiagnosticEngine
        ↓
updated ranking
```

produces deterministic results.

## Test

Prepare a fixed case:

```text
CASE_TEST_001
Revision = N
```

Submit the same check result twice from equivalent case state.

Compare:

```text
observations
evidence classifications
cause scores
cause ordering
next question
next check
```

Expected:

```text
Run A == Run B
```

for deterministic diagnostic logic.

If an external model already influences the process, mock/isolate it for this verification.

Do not implement additional LLM functionality to satisfy this gate.

## Pass condition

Same structured case + same check result = same diagnostic result.

---

# 11. READINESS REQUIREMENT 8 — DUPLICATE / REPEATED CHECK RESULTS DO NOT INFLATE EVIDENCE

## Test A — Exact duplicate

Submit:

```text
CHK_N03
BLOCKAGE_OBSERVED
```

twice.

Expected:

```text
first submission
→ evidence added

second identical submission
→ no additional independent evidence weight
```

The system may preserve the fact that the action was repeated, but the ranking must not receive double support.

## Test B — Same observation from repeated checks

If two executions generate the same normalized observation:

```text
nozzle_condition = blocked
```

do not automatically count them as two independent observations.

## Test C — Revision preservation

Verify:

```text
Revision N
```

remains unchanged.

If a repeated submission creates a new revision, the new revision must not artificially increase support.

## Pass condition

Repeated identical or equivalent check results cannot inflate cause support.

---

# 12. REQUIRED QUESTION OF CHECK CONFIRMATION

The code agent must search for all code paths that perform:

```text
cause = confirmed
```

or:

```text
issue = resolved
```

after a troubleshooting action.

Search for patterns such as:

```text
confirmed
resolved
completed
supports
success
pass
finding
outcome
```

Then inspect every transition.

The agent must report:

```text
File
Function
Current transition
Is the transition valid?
```

Example:

| Code path | Current behaviour | Correct? |
|---|---|---|
| action result handler | COMPLETED → cause confirmed | ❌ |
| evidence mapper | SUPPORTS → evidence | ✅ |
| confirmation endpoint | explicit confirmation → cause confirmed | ✅ |

Any automatic invalid transition must be fixed before DLK-M3-013.

---

# 13. REQUIRED END-TO-END TEST

Implement one complete integration scenario.

Example:

```text
Case:
Inconsistent dispensing size

Current ranking:
Air/Supply = 82
Nozzle = 68
Material = 61

Selected check:
CHK_N03_NOZZLE_INSPECTION
```

Technician submits:

```text
execution_status = COMPLETED
finding = SUPPORTS
observation = nozzle restriction observed
```

Expected:

```text
POST check result
        ↓
load/reconstruct StructuredCase
        ↓
check-result handler
        ↓
new observation
        ↓
EvidenceEngine
        ↓
CauseRanker
        ↓
new ranking
        ↓
QuestionEngine
        ↓
ActionPlanner
        ↓
Revision N+1
        ↓
updated DiagnosisResult
```

The expected output should demonstrate:

```text
check execution = COMPLETED
finding = SUPPORTS
cause = SUSPECTED or unchanged
issue = UNRESOLVED
```

unless the knowledge explicitly defines the result as confirmatory or resolving.

---

# 14. REQUIRED FOUR-STATE SEPARATION TEST

The implementation must prove that these states can coexist independently.

## Case A

```text
Check completed
Check supports cause
Cause unconfirmed
Issue unresolved
```

## Case B

```text
Check completed
Check supports cause
Cause confirmed
Issue unresolved
```

## Case C

```text
Check completed
Finding inconclusive
Cause unconfirmed
Issue resolved
```

## Case D

```text
Check completed
Finding supports cause
Cause confirmed
Issue resolved
```

The actual allowed transitions should follow the existing project knowledge/contract.

The important requirement is that the system does not collapse these into one generic "successful" status.

---

# 15. REQUIRED NEGATIVE TESTS

Test all of the following:

### Invalid check ID

```text
CHK_UNKNOWN
```

Expected:

```text
controlled validation error
```

No fabricated check.

### Invalid result

```text
BLOCKAGE_MAYBE
```

when not defined.

Expected:

```text
controlled validation error
```

### UNKNOWN result

Expected:

```text
no fabricated evidence
```

### INCONCLUSIVE result

Expected:

```text
no automatic cause confirmation
```

### BLOCKED execution

Expected:

```text
finding remains UNKNOWN unless explicitly provided
```

### Duplicate result

Expected:

```text
no evidence inflation
```

### Previously confirmed cause

Submitting an ordinary supporting check must not incorrectly reset or silently reconfirm state.

### Resolved issue

A subsequent check result must be handled as a new revision rather than silently rewriting history.

---

# 16. REQUIRED TEST MATRIX

Generate a test matrix similar to:

| Check | Result | Execution | Finding | Observation | Cause impact | Confirmatory? | Expected |
|---|---|---|---|---|---|---|---|
| CHK01 | BLOCKAGE_FOUND | COMPLETED | SUPPORTS | nozzle=blocked | supports nozzle cause | No | PASS |
| CHK01 | CLEAR | COMPLETED | CONTRADICTS | nozzle=clear | weakens nozzle cause | No | PASS |
| CHK01 | UNKNOWN | COMPLETED | UNKNOWN | none | none | No | PASS |
| CHK01 | INCONCLUSIVE | COMPLETED | INCONCLUSIVE | none/limited | none/defined weak effect | No | PASS |
| CHK01 | ... | BLOCKED | UNKNOWN | none | none | No | PASS |

Use the actual project's checks/results rather than inventing fake production semantics.

---

# 17. REQUIRED FILE-LEVEL AUDIT

At minimum, inspect the equivalent of:

```text
backend/app/services/diagnosis/action_planner.py
backend/app/services/diagnosis/evidence_engine.py
backend/app/services/diagnosis/cause_ranker.py
backend/app/services/diagnosis/engine.py

backend/app/knowledge/actions.json
backend/app/knowledge/rules.json

backend/app/models/diagnosis_action.py
backend/app/schemas/action.py

backend/app/models/diagnosis.py
backend/app/schemas/diagnosis.py
```

Also locate any:

```text
check_result_handler.py
action_result_handler.py
outcome_handler.py
```

if they exist under different names.

Do not assume these exact files exist.

---

# 18. REQUIRED TEST FILES

Reuse existing tests where possible.

Locate or create the appropriate equivalents of:

```text
backend/tests/unit/test_action_planner.py
backend/tests/unit/test_check_result_handler.py
backend/tests/unit/test_evidence_engine.py
backend/tests/unit/test_cause_ranker.py
backend/tests/integration/test_check_result_diagnosis_revision.py
```

Do not create duplicate test files if equivalent tests already exist.

---

# 19. REQUIRED VERIFICATION REPORT

At the end, return a structured report.

## A. Stable check contract

```text
Total supported checks:
Checks with stable IDs:
Checks with duplicate IDs:
Checks with missing IDs:
```

## B. Outcome contract

```text
Execution states:
Finding states:
Invalid/duplicate states found:
```

## C. Mapping verification

```text
Total check-result mappings:
Valid:
Missing:
Conflicting:
Untested:
```

## D. State separation

Report whether all four are independent:

```text
check execution
check finding
cause conclusion
issue condition
```

## E. Determinism

```text
Same case + same result:
PASS / FAIL
```

## F. Duplicate protection

```text
Repeated exact result:
PASS / FAIL

Equivalent repeated observation:
PASS / FAIL
```

## G. Test results

List every test run and its result.

---

# 20. BLOCKING VS NON-BLOCKING FINDINGS

Separate findings into:

## BLOCKING FOR DLK-M3-013

Examples:

```text
Missing stable check IDs
Conflicting outcome values
Missing check→observation mapping
UNKNOWN creates evidence
BLOCKED becomes negative evidence
Execution state and finding are conflated
Supporting result automatically confirms cause
Repeated results inflate support
Diagnosis rerun is nondeterministic
Revision N gets mutated
Important mapping has no test
```

## NOT BLOCKING FOR DLK-M3-013

Examples:

```text
LLM integration
CV
Historical retrieval
PDF reports
Full recovery workflow UI
Advanced analytics
Production deployment
Additional defect expansion
```

---

# 21. MINIMUM FIX POLICY

If a readiness requirement fails:

1. Identify the smallest existing component responsible.
2. Fix only that component.
3. Add or update the relevant tests.
4. Re-run the affected tests.
5. Re-run the complete DLK-M3-013 end-to-end test.
6. Do not perform unrelated refactoring.

Do not redesign the entire diagnostic engine merely because one contract is missing.

---

# 22. FINAL DLK-M3-013 GATE

Mark:

```text
READY FOR DLK-M3-013
```

only when all of these are true:

```text
[ ] Every supported troubleshooting check has a stable ID
[ ] Supported technician outcome values are explicitly defined
[ ] Check-result → observation/evidence mappings are aligned
[ ] UNKNOWN does not fabricate evidence
[ ] INCONCLUSIVE does not fabricate evidence
[ ] BLOCKED is handled correctly
[ ] NOT_APPLICABLE is handled correctly
[ ] Check execution state is separate from check finding
[ ] Supporting check does not automatically confirm cause
[ ] Confirmatory checks are explicitly identified if they exist
[ ] Cause confirmation is separate from issue resolution
[ ] Diagnosis reruns deterministically
[ ] Duplicate check results do not inflate evidence
[ ] Revision N is preserved
[ ] Revision N+1 contains the new result/evidence
[ ] Updated ranking is returned
[ ] Updated next question is returned when applicable
[ ] Updated next check is returned when applicable
[ ] Important outcome mappings have automated tests
[ ] End-to-end check-result integration test passes
[ ] Negative/error cases pass
```

If any **blocking** item fails, return:

```text
NOT READY FOR DLK-M3-013
```

and identify the exact minimum fix.

If all blocking items pass, return:

```text
READY FOR DLK-M3-013
```

---

# 23. FINAL EXPECTED CONTRACT

The final implementation must reliably support:

```text
Technician
    ↓
Selects Check ID
    ↓
Executes / attempts check
    ↓
Submits execution state + finding/result
    ↓
CheckResultHandler
    ↓
Observation / Evidence mapping
    ↓
StructuredCase updated
    ↓
DiagnosticEngine reruns
    ↓
Cause ranking updated
    ↓
Next question/check updated
    ↓
Analysis Revision N+1
    ↓
Updated DiagnosisResult
```

And it must preserve:

```text
Check completed
        ≠
Check supports cause
        ≠
Cause confirmed
        ≠
Issue resolved
```

That separation is a mandatory architectural invariant for DLK-M3-013.