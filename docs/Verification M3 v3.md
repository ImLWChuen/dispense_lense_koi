# DLK-M3-013 - Member 2 Check-Result Semantic Correction and Readiness Plan

## 1. Objective

Fix and verify the existing Member 2 troubleshooting-check implementation so it is safe to release:

**DLK-M3-013 - Technician troubleshooting-check result API**

This is a **targeted semantic correction task**.

Do not rebuild the diagnosis engine.

Do not implement unrelated features.

Do not add LLM, CV, historical retrieval, analytics, reporting, or other later-stage functionality unless an existing test requires a minimal compatibility change.

The final flow must support:

```text
Selected troubleshooting check
        ↓
Technician performs / attempts check
        ↓
Technician submits result
        ↓
Check-result interpretation
        ↓
Check execution state stored
        +
Check finding stored separately
        ↓
Outcome mapped to only the fact demonstrated
        ↓
Evidence / observation updated
        ↓
DiagnosticEngine reruns
        ↓
Cause ranking updated deterministically
        ↓
Next question / next check updated
        ↓
Analysis Revision N+1
```

---

# 2. NON-NEGOTIABLE SEMANTIC RULE

The following four concepts must always remain independent:

```text
Check completed
      ≠
Check supports cause
      ≠
Cause confirmed
      ≠
Issue resolved
```

Never introduce or retain logic that implicitly performs:

```python
if check_completed:
    cause_confirmed = True
    issue_resolved = True
```

or:

```python
if finding == SUPPORTS:
    cause_confirmed = True
```

unless the specific check/outcome is explicitly defined as **confirmatory** in the knowledge model.

The project architecture separates evidence/ranking from user verification and final confirmation.

---

# PHASE 0 - INSPECT BEFORE MODIFYING

## Step 0.1 - Inspect the repository

Do not modify anything yet.

Locate:

```text
backend/app/services/diagnosis/
    engine.py
    evidence_engine.py
    cause_ranker.py
    action_planner.py

backend/app/knowledge/
    actions.json
    rules.json
    causes.json
    questions.json

backend/app/models/
    diagnosis.py
    action.py
    diagnosis_action.py
    answer.py
    ...

backend/app/schemas/
    diagnosis.py
    action.py
    ...

backend/app/api/
    actions.py
    diagnoses.py
    ...

backend/tests/
    existing diagnosis/action/check-result tests
```

Also search for these exact concepts:

```text
_ACTION_OUTCOME_TO_OBSERVATION
action_outcome
check_outcome
finding
execution_status
cause_confirmed
confirmed_cause
issue_resolved
resolved
supports
contradicts
unknown
inconclusive
```

If the actual project uses a different filename or symbol, use the existing implementation rather than creating a duplicate.

---

## Step 0.2 - Produce an implementation map

Before editing, report:

```text
Component:
File:
Function/class:
Current responsibility:
Relevant tests:
Potential semantic issue:
```

The code agent must explicitly identify where the current:

```text
check result
→ observation/evidence
→ ranking
→ cause confirmation
→ issue resolution
```

pipeline occurs.

---

# PHASE 1 - AUDIT AUTOMATIC CAUSE CONFIRMATION

## Step 1.1 - Search for all automatic confirmation paths

Search the repository for:

```text
cause_confirmed
confirmed_cause
cause_status
CONFIRMED
confirm_cause
resolve_cause
supports
```

Inspect every place where a check/action result can change cause status.

Generate a table:

| File | Function | Trigger | Current transition |
|---|---|---|---|
| ... | ... | check result | ... |

---

## Step 1.2 - Remove invalid automatic confirmation

The default behaviour must be:

```text
check completed
        ↓
finding recorded
        ↓
evidence updated
        ↓
cause ranking updated
```

NOT:

```text
check completed
        ↓
cause confirmed
```

and NOT:

```text
check supports cause
        ↓
cause confirmed
```

unless that check/result is deliberately and explicitly marked as confirmatory.

---

## Step 1.3 - Establish confirmation semantics

Determine whether the existing project requires explicit technician/engineer confirmation.

There are two valid possibilities:

### Option A - Explicit confirmation required

Then:

```text
check result
    ↓
evidence/ranking
    ↓
suspected cause
    ↓
technician/engineer confirmation
    ↓
confirmed cause
```

Implement or preserve an explicit confirmation action.

### Option B - A specific check is formally confirmatory

Then the knowledge definition must explicitly state something equivalent to:

```text
check_id
+
result
+
confirmatory = true
```

Do not infer confirmatory behaviour from generic `SUPPORTS`.

If the repository already has a confirmation model, reuse it.

---

## Step 1.4 - Acceptance condition

After this phase:

```text
NORMAL SUPPORTING CHECK
→ increases/changes evidence
→ does not automatically confirm cause

EXPLICIT CONFIRMATION
→ may confirm cause

ISSUE RESOLUTION
→ remains separate
```

---

# PHASE 2 - AUDIT `_ACTION_OUTCOME_TO_OBSERVATION`

## Step 2.1 - Locate the mapping

Find the exact implementation of:

```text
_ACTION_OUTCOME_TO_OBSERVATION
```

If it does not exist under that exact name, identify the equivalent check/action outcome mapping.

Document:

```text
action/check ID
+
outcome
→
observation
```

---

## Step 2.2 - Audit every mapping

For every entry, ask:

> "Does this outcome actually prove the observation being created?"

For example:

```text
Check:
Inspect nozzle

Outcome:
No visible blockage
```

Valid mapping:

```text
nozzle_condition = clear / no_visible_blockage
```

Potentially invalid mapping:

```text
nozzle_condition = confirmed_functional
```

because the check may only demonstrate a visual observation, not complete equipment functionality.

---

## Step 2.3 - Remove semantic overreach

Each mapping must only assert what the check result actually demonstrates.

Use this rule:

```text
OUTCOME
  ↓
DIRECTLY OBSERVABLE FACT
  ↓
EVIDENCE INTERPRETATION
```

Do not jump directly from:

```text
check result
```

to:

```text
root cause confirmed
```

or:

```text
machine fully healthy
```

unless explicitly justified by the knowledge definition.

---

# PHASE 3 - DEFINE THE CHECK OUTCOME CONTRACT

## Step 3.1 - Audit check IDs

Each troubleshooting action/check must have:

```text
stable check_id
stable name
defined applicable context
defined outcome values
```

Example:

```text
CHK_NOZZLE_INSPECTION
CHK_SUPPLY_INSPECTION
CHK_MATERIAL_CONDITION
```

Do not allow the frontend or handler to rely on display labels as identifiers.

---

## Step 3.2 - Audit execution states

Separate execution state from finding.

### Execution state

```text
PENDING
IN_PROGRESS
COMPLETED
BLOCKED
SKIPPED
```

### Finding

```text
SUPPORTS
CONTRADICTS
INCONCLUSIVE
UNKNOWN
NOT_APPLICABLE
```

Do not collapse these into one status field.

Examples:

```text
COMPLETED + SUPPORTS
COMPLETED + INCONCLUSIVE
COMPLETED + UNKNOWN
BLOCKED + UNKNOWN
```

must all be representable.

This matches the project's requirement for explicit user completion/outcomes and separate cause/issue states.

---

# PHASE 4 - VERIFY EVERY OUTCOME MAPPING

## Step 4.1 - Create a formal mapping table

Produce:

| Check ID | Outcome | Execution state | Observation type | Observation value | Evidence effect | Confirmatory? |
|---|---|---|---|---|---|---|
| CHK01 | RESULT_A | COMPLETED | ... | ... | SUPPORTS | No |
| CHK01 | RESULT_B | COMPLETED | ... | ... | CONTRADICTS | No |
| CHK01 | UNKNOWN | COMPLETED | none | none | none | No |
| CHK01 | INCONCLUSIVE | COMPLETED | none/limited | ... | none/limited | No |

Use the actual project values.

Do not invent production semantics merely to populate the table.

---

## Step 4.2 - Verify UNKNOWN

For every check supporting UNKNOWN:

```text
UNKNOWN
→ no fabricated observation
→ no fabricated contradiction
→ no fabricated support
→ no cause confirmation
```

---

## Step 4.3 - Verify INCONCLUSIVE

For:

```text
INCONCLUSIVE
```

do not automatically:

```text
support
```

or:

```text
contradict
```

unless explicitly defined.

Default:

```text
INCONCLUSIVE
→ uncertainty remains
```

---

## Step 4.4 - Verify BLOCKED

For:

```text
execution_status = BLOCKED
```

the system should preserve:

```text
finding = UNKNOWN
```

unless the technician explicitly provides a legitimate finding despite the blocked step.

Never convert:

```text
BLOCKED
```

into:

```text
check failed
```

or:

```text
cause contradicted
```

---

## Step 4.5 - Verify NOT_APPLICABLE

Do not automatically convert:

```text
NOT_APPLICABLE
```

into:

```text
CONTRADICTS
```

unless the specific knowledge definition explicitly says that this result carries that meaning.

Default behaviour should be:

```text
NOT_APPLICABLE
→ no unsupported evidence
```

---

# PHASE 5 - WRITE TESTS FOR CORRECTED MAPPINGS

## Step 5.1 - Identify existing tests

Locate current:

```text
Phase 9 tests
Phase 10 tests
Phase 11 tests
check-result tests
action planner tests
evidence engine tests
cause ranker tests
```

Do not duplicate equivalent tests.

---

## Step 5.2 - Add unit tests for each important mapping

For every meaningful check/result:

```text
input:
check_id + outcome

expected:
execution state
finding
observation
evidence effect
cause state
issue state
```

Example:

```python
def test_nozzle_check_supports_without_confirming():
    result = handle_check_result(
        check_id="CHK_NOZZLE",
        outcome="BLOCKAGE_FOUND"
    )

    assert result.finding == "SUPPORTS"
    assert result.observation.type == "nozzle_condition"
    assert result.observation.value == "blocked"
    assert result.cause_status != "CONFIRMED"
```

---

## Step 5.3 - Test UNKNOWN

```python
def test_unknown_does_not_create_evidence():
    result = handle_check_result(
        check_id="CHK_NOZZLE",
        outcome="UNKNOWN"
    )

    assert result.observation is None
    assert result.evidence_effect is None
```

Adapt the exact assertions to the project's existing contract.

---

## Step 5.4 - Test INCONCLUSIVE

```python
def test_inconclusive_does_not_confirm_cause():
    result = handle_check_result(
        check_id="CHK_NOZZLE",
        outcome="INCONCLUSIVE"
    )

    assert result.cause_status != "CONFIRMED"
```

---

## Step 5.5 - Test BLOCKED

```python
def test_blocked_check_does_not_create_negative_evidence():
    result = handle_check_result(
        check_id="CHK_NOZZLE",
        execution_status="BLOCKED"
    )

    assert result.finding == "UNKNOWN"
    assert result.evidence_effect is None
```

---

## Step 5.6 - Test NOT_APPLICABLE

Verify:

```text
NOT_APPLICABLE
→ no accidental contradiction
```

---

# PHASE 6 - TEST DETERMINISTIC RERUN

## Step 6.1 - Create a fixed case

Use one stable test fixture:

```text
CASE_DLKM3013_001
```

with:

```text
Revision N
known observations
known candidate causes
known initial ranking
```

---

## Step 6.2 - Apply one check result

Example:

```text
check = CHK_NOZZLE
result = BLOCKAGE_FOUND
```

Run:

```text
CheckResultHandler
→ StructuredCase update
→ DiagnosticEngine
```

---

## Step 6.3 - Save resulting analysis

Capture:

```text
observations
evidence
cause rankings
scores
next question
next check
```

---

## Step 6.4 - Repeat with identical state

Run the same test again from the same reconstructed case.

Expected:

```text
Result A == Result B
```

for deterministic diagnostic components.

---

# PHASE 7 - TEST DUPLICATE / REPEATED RESULTS

## Step 7.1 - Submit identical result twice

Example:

```text
CHK_NOZZLE
BLOCKAGE_FOUND
```

First time:

```text
evidence added
```

Second time:

```text
no duplicate independent evidence contribution
```

---

## Step 7.2 - Verify score stability

Compare:

```text
Score after first result
Score after repeated identical result
```

The score must not incorrectly double.

Example of prohibited behaviour:

```text
first:
Nozzle = 60

second identical result:
Nozzle = 120
```

unless the project's scoring system explicitly represents repeated independent observations, which is not the default expectation here.

---

## Step 7.3 - Verify equivalent observations

If two outcomes normalize to the same observation:

```text
nozzle_condition = blocked
```

they should not automatically be counted as two independent facts.

---

# PHASE 8 - VERIFY REVISION HANDLING

## Step 8.1 - Confirm Revision N remains immutable

Before submitting a check result:

```text
Revision N
```

After:

```text
Revision N+1
```

Verify Revision N remains exactly as originally recorded.

---

## Step 8.2 - Verify new evidence belongs to N+1

Revision N+1 must contain:

```text
old evidence
+
new check result
+
new observation/evidence
+
updated ranking
+
updated next question/check
```

---

## Step 8.3 - Confirm no mutation

Explicitly test:

```text
load Revision N
```

after Revision N+1 has been created.

Expected:

```text
Revision N unchanged
```

This aligns with the project's requirement to preserve evidence/history and update affected analysis rather than silently mutating earlier state.

---

# PHASE 9 - VERIFY CAUSE CONFIRMATION AND ISSUE RESOLUTION

## Step 9.1 - Test normal supporting check

Scenario:

```text
check = COMPLETED
finding = SUPPORTS
```

Expected:

```text
cause = SUSPECTED / unchanged
issue = UNRESOLVED
```

unless explicitly defined otherwise.

---

## Step 9.2 - Test explicit cause confirmation

If the project currently has technician/engineer confirmation:

```text
supporting evidence
        ↓
technician/engineer confirms
        ↓
cause = CONFIRMED
```

Verify this occurs only through the explicit confirmation mechanism.

---

## Step 9.3 - Test issue resolution separately

A user may resolve the issue while the cause remains unknown.

Test:

```text
cause = UNCONFIRMED
issue = RESOLVED
```

Also test:

```text
cause = CONFIRMED
issue = UNRESOLVED
```

These states must be valid.

The product requirements explicitly call for independent root-cause confirmation and issue-resolution records.

---

# PHASE 10 - RERUN PHASE 9–11 / CHECK-RESULT TESTS

After fixing the semantic mappings:

1. Run all existing diagnosis tests from Phases 9–11.
2. Run all action/check-result tests.
3. Run the newly added mapping tests.
4. Run integration tests.
5. Run duplicate-evidence tests.
6. Run deterministic rerun tests.
7. Run cause-confirmation/state tests.

Do not accept only the new tests.

The old behaviour must remain stable unless it was intentionally corrected.

---

# PHASE 11 - FINAL DLK-M3-013 INTEGRATION TEST

Run one complete scenario:

```text
Existing Diagnosis Revision N
        ↓
Selected Check
        ↓
Technician submits result
        ↓
Check-result handler
        ↓
Observation/evidence created
        ↓
StructuredCase updated
        ↓
DiagnosticEngine reruns
        ↓
Ranking updated
        ↓
Next question updated if needed
        ↓
Next check updated if needed
        ↓
Revision N+1 persisted
        ↓
Updated analysis returned
```

Verify the API response contains at least:

```text
revision
identified defect
ranked causes
evidence
next question
next check
execution/finding state
cause status
issue status
```

Use the project's actual response schema rather than creating a second incompatible schema.

---

# PHASE 12 - FINAL AUDIT BEFORE MERGE

Generate a final audit:

## Check contract

```text
[ ] Stable check IDs
[ ] Stable outcome values
[ ] No conflicting labels
```

## Mapping

```text
[ ] _ACTION_OUTCOME_TO_OBSERVATION audited
[ ] Every outcome maps only to demonstrated facts
[ ] UNKNOWN safe
[ ] INCONCLUSIVE safe
[ ] BLOCKED safe
[ ] NOT_APPLICABLE safe
```

## State separation

```text
[ ] Execution state independent
[ ] Finding independent
[ ] Cause confirmation independent
[ ] Issue resolution independent
```

## Ranking

```text
[ ] Check result changes evidence correctly
[ ] Ranking reruns deterministically
[ ] Duplicate results do not inflate support
```

## History

```text
[ ] Revision N immutable
[ ] Revision N+1 correctly created
[ ] Previous evidence preserved
```

## Tests

```text
[ ] Mapping tests pass
[ ] Phase 9 tests pass
[ ] Phase 10 tests pass
[ ] Phase 11 tests pass
[ ] Check-result tests pass
[ ] Integration test passes
```
---

# PHASE 13 - FINAL READINESS REPORT

Return exactly this structure:

## 1. Semantic corrections made

```text
- ...
- ...
```

## 2. Automatic cause confirmation

```text
Removed:
...
or

Explicitly retained with:
...
```

## 3. `_ACTION_OUTCOME_TO_OBSERVATION` audit

```text
Total mappings:
Correct:
Corrected:
Unresolved:
```

## 4. Tests

```text
Mapping tests:
Phase 9:
Phase 10:
Phase 11:
Check-result integration:
Duplicate result:
Deterministic rerun:
State separation:
```

## 5. Git

```text
Commit:
Branch:
Merged to main: YES/NO
```

## 6. Final gate

Return exactly one:

```text
READY FOR DLK-M3-013
```

or:

```text
NOT READY FOR DLK-M3-013
```

If NOT READY, list only the remaining blockers.

---

# FINAL ACCEPTANCE CONDITIONS

DLK-M3-013 is READY only when all of these are true:

```text
[✓] Every check/action has a stable ID

[✓] Technician outcomes are explicitly defined

[✓] _ACTION_OUTCOME_TO_OBSERVATION is audited

[✓] Each outcome creates only the observation/evidence
    that the outcome actually demonstrates

[✓] UNKNOWN does not fabricate evidence

[✓] INCONCLUSIVE does not fabricate evidence

[✓] BLOCKED does not fabricate evidence

[✓] NOT_APPLICABLE does not automatically become contradiction

[✓] Check execution state is separate from check finding

[✓] SUPPORTS does not automatically mean CONFIRMED

[✓] Explicit confirmation semantics are defined

[✓] Cause confirmation remains separate from issue resolution

[✓] Rerunning the same case + result is deterministic

[✓] Duplicate/repeated results do not inflate evidence

[✓] Revision N is preserved

[✓] Revision N+1 contains the new evidence and updated analysis

[✓] Mapping tests exist and pass

[✓] Phase 9–11/check-result tests pass

[✓] End-to-end technician check-result flow passes

[✓] Semantic corrections are committed

[✓] Corrections are merged to main, or merge-ready if permissions prevent it
```

## The single most important rule

When making a correction, always ask:

> **"What fact did this technician outcome actually demonstrate?"**

The mapping must stop there.

For example:

```text
Nozzle check:
"No visible blockage"
        ↓
FACT:
No visible blockage observed
        ↓
EVIDENCE:
weakens nozzle-blockage hypothesis
        ↓
NOT:
"Nozzle is definitely healthy"
        ↓
NOT:
"Another cause is confirmed"
        ↓
NOT:
"Issue is resolved"
```

That semantic boundary is the core of the DLK-M3-013 correction.