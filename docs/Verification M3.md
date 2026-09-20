# DLK-M3-012 - Member 2 Question-Answer Contract Readiness Verification

## Objective

Verify whether the existing Member 2 implementation is ready for:

**DLK-M3-012 - Submit technician answer and append new diagnosis revision API**

Do **not** redesign or rewrite the diagnosis engine.

Do **not** implement Phase 12 LLM integration.

Do **not** implement CV, historical retrieval, root-cause confirmation, recovery verification, or other later-stage features.

This task is strictly to inspect the existing codebase, verify the seven readiness requirements below, run tests, identify gaps, and make only the **minimum changes necessary to satisfy the readiness contract**.

The readiness flow is:

```text
POST technician answer
        ↓
load/reconstruct StructuredCase
        ↓
QuestionAnswerHandler interprets answer
        ↓
new observations are added
        ↓
DiagnosticEngine reruns
        ↓
new ranking / next question / next check
        ↓
persist revision N+1
        ↓
return updated analysis
```

The goal is to prove that the **middle diagnostic portion** is reliable enough for Member 3 / backend integration.

---

# 1. FIRST: INSPECT THE EXISTING IMPLEMENTATION

Before changing anything:

1. Inspect the repository structure.
2. Locate the current implementation of:
   - `Question`
   - question knowledge definitions
   - `questions.json`
   - `QuestionAnswerHandler`, or the equivalent existing answer-processing component
   - `StructuredCase`
   - `Observation`
   - `QuestionAnswer`
   - `DiagnosticEngine`
   - `question_engine.py`
   - `evidence_engine.py`
   - `cause_ranker.py`
   - `action_planner.py`
   - analysis revision/state models
   - existing unit/integration tests
3. Identify whether answer processing is already implemented under another filename or service.
4. Reuse existing architecture instead of creating duplicate handlers or parallel logic.
5. Do not modify unrelated modules.

Create an inspection report before editing:

```text
Existing component:
Location:
Current responsibility:
Used by:
Existing tests:
Potential issue:
```

---

# 2. READINESS REQUIREMENT 1 - STABLE QUESTION DEFINITIONS

## Goal

Verify that every MVP diagnostic question has a stable contract.

For every supported question, verify:

```text
question_id
question text
allowed answer values
answer semantics
related observations
applicability
```

### Check

For every question in `knowledge/questions.json`:

1. Confirm `question_id` exists.
2. Confirm the ID is unique.
3. Confirm allowed answer values are explicitly defined.
4. Confirm answer names are consistent.
5. Confirm there are no duplicate or conflicting option names.
6. Confirm the handler uses the exact same IDs and answer values.
7. Confirm the question engine refers to the same identifiers.
8. Check for hard-coded answer names elsewhere in the code.
9. Identify any mismatch between:
   - JSON
   - Python enums/constants
   - handler mappings
   - API schemas
   - frontend values, if already present.

### Required output

Produce:

```text
Question Contract Audit

Q01
- ID: PASS/FAIL
- Allowed answers: PASS/FAIL
- Handler alignment: PASS/FAIL
- Conflicting definitions: YES/NO

Q02
...
```

Also produce a final mapping:

| Question ID | Allowed answers | Handler mapping | Status |
|---|---|---|---|
| Q01 | ... | ... | PASS |
| Q02 | ... | ... | PASS |

### Pass condition

Every MVP question has one clear definition.

No contradictory option names or semantics remain.

---

# 3. READINESS REQUIREMENT 2 - QUESTIONANSWERHANDLER ALIGNMENT

## Goal

Verify that `QuestionAnswerHandler` correctly interprets every supported answer according to the knowledge definition.

For every supported question/answer combination:

```text
Question ID
+
Answer
↓
QuestionAnswerHandler
↓
Observation(s)
```

### Check

For each answer:

1. Confirm the answer is recognized.
2. Confirm the handler maps it to the intended observation type.
3. Confirm the generated observation value is correct.
4. Confirm provenance is correct.
5. Confirm confidence is handled consistently if the project uses it.
6. Confirm the handler does not use conflicting hard-coded semantics.
7. Confirm the handler does not infer a cause when only an observation should be created.

Example:

```text
Q01
Answer: ALL_POINTS

Expected:
Observation:
type = spatial_pattern
value = systemic
provenance = USER_ANSWER
```

### Must reject behaviour such as:

```text
Answer:
"I think the nozzle is blocked."

↓
confirmed_cause = nozzle_blockage
```

A technician answer may represent a user hypothesis, but it must not silently become system-confirmed evidence.

### Pass condition

Every supported answer maps to the intended structured meaning, with no conflicting mapping.

---

# 4. READINESS REQUIREMENT 3 - ANSWER → OBSERVATION SEMANTICS

## Goal

Create executable tests proving the exact semantic transformation.

For every MVP question, test at least:

```text
normal positive answer
normal negative/alternative answer
UNKNOWN
NOT_APPLICABLE
```

Where other domain-specific options exist, test those too.

Each test must verify:

```text
input answer
↓
generated observation type
↓
generated observation value
↓
provenance
↓
confidence, if used
```

### Example

```python
def test_q01_all_points():
    result = handler.handle(
        question_id="Q01",
        answer="ALL_POINTS"
    )

    assert result.observations == [
        Observation(
            type="spatial_pattern",
            value="systemic",
            provenance="USER_ANSWER"
        )
    ]
```

### UNKNOWN test

```text
Q01
Answer = UNKNOWN

Expected:
observations = []
```

or whatever explicit project semantics already define.

The critical requirement is:

```text
UNKNOWN must not invent evidence.
```

### NOT_APPLICABLE test

Verify that:

```text
NOT_APPLICABLE
```

does not automatically become contradiction.

It must follow the defined semantics for that particular question.

### User hypothesis test

If a question allows a hypothesis-style answer, verify that:

```text
user hypothesis
≠
confirmed cause
```

### Pass condition

Each test proves the intended answer-to-observation contract.

---

# 5. READINESS REQUIREMENT 4 - DETERMINISTIC DIAGNOSIS RERUN

## Goal

Verify that adding the same answer to the same case produces deterministic analysis.

Use:

```text
StructuredCase N
+
QuestionAnswer A
```

Run the diagnosis twice.

Expected:

```text
Run 1 → Result X
Run 2 → Result X
```

The following must remain deterministic:

```text
generated observations
evidence classification
cause scores
cause ordering
next question
next check
```

assuming all inputs are identical.

### Test

Construct one fixture:

```text
case_id = TEST-001
revision = N
```

Submit:

```text
Q01 = ALL_POINTS
```

Run the handler and engine twice.

Compare:

```text
observations
evidence
ranked causes
scores
next question
next check
```

### Pass condition

No random or order-dependent behaviour is introduced into deterministic diagnostic logic.

If LLM functionality is already present but not required for this checkpoint, isolate it or mock it so the diagnostic rerun itself remains deterministic.

Do not implement Phase 12 merely to satisfy this test.

---

# 6. READINESS REQUIREMENT 5 - DUPLICATE EVIDENCE PROTECTION

## Goal

Verify that submitting the same answer repeatedly does not create repeated diagnostic evidence or artificially increase cause support.

### Test A - Same answer submitted twice

```text
Initial case
↓
Q01 = ALL_POINTS
↓
Observation added
↓
rerun
```

Then:

```text
Q01 = ALL_POINTS again
```

Expected:

```text
No second independent copy of the same evidence
```

The system may record that the answer was repeated, but repeated evidence must not receive another full diagnostic contribution.

### Test B - Equivalent observation wording

For example:

```text
"all dispensing points affected"
```

and:

```text
"problem affects every point"
```

If both normalize to the same structured observation, they must not be treated as two independent pieces of evidence.

### Test C - Revision history

Verify that:

```text
Revision N
```

remains intact.

If a duplicate submission creates a new revision because the API requires one, the diagnostic evidence should still not be inflated.

### Pass condition

Repeated evidence cannot artificially improve a cause score.

This is especially important because the diagnostic plan explicitly requires duplicate/correlated evidence protection.

---

# 7. READINESS REQUIREMENT 6 - UPDATED DIAGNOSTIC RESULT

## Goal

Verify that a technician answer actually changes the investigation when the answer contains useful new information.

Test:

```text
Revision N
        ↓
Question answer
        ↓
QuestionAnswerHandler
        ↓
New observation
        ↓
Evidence Engine
        ↓
Cause Ranker
        ↓
Question Engine / Action Planner
        ↓
Revision N+1
```

Verify all of the following:

### A. New evidence exists

The answer creates the expected observation.

### B. Evidence is evaluated

The observation reaches the evidence engine.

### C. Ranking updates

At least one applicable cause should change when the answer is intentionally designed to discriminate between hypotheses.

Do not require the #1 cause to change in every scenario.

The requirement is that the answer is actually incorporated into the analysis.

### D. Next question updates

Verify that the question engine receives the updated case.

A useful answer may eliminate a question or cause another question to become more useful.

### E. Next check updates

Where the updated evidence affects troubleshooting options, verify that the action planner receives the new state.

### F. Evidence explanation remains valid

The returned evidence should explain the updated ranking.

### Pass condition

A question answer propagates through the entire diagnostic pipeline instead of merely being stored.

---

# 8. READINESS REQUIREMENT 7 - REVISION N → N+1

## Goal

Verify that the system creates a clean new analysis revision without mutating the previous one.

Expected:

```text
Revision N
   ↓
answer submitted
   ↓
new observation
   ↓
diagnostic rerun
   ↓
Revision N+1
```

### Verify

Revision N contains:

```text
original observations
original ranking
original evidence
original next question/check
```

Revision N+1 contains:

```text
previous observations
+
new observation
+
updated evidence
+
updated ranking
+
updated next question/check
```

### Critical test

After Revision N+1 is created:

1. Read Revision N.
2. Verify its values are unchanged.
3. Read Revision N+1.
4. Verify the new evidence exists.

### Pass condition

Historical analysis is immutable.

No previous revision is silently rewritten.

---

# 9. REQUIRED END-TO-END CONTRACT TEST

After testing the seven requirements independently, create one complete integration test.

Use a realistic MVP question.

Example:

```text
Initial case:

Defect:
INCONSISTENT_SIZE

Current ranking:

Air/Supply Issue = 82
Nozzle Restriction = 68
Material Condition = 61

Next question:
Q01
"Does the problem occur across all dispensing points?"
```

Technician submits:

```text
Q01 = ALL_POINTS
```

Expected flow:

```text
POST answer
        ↓
reconstruct StructuredCase
        ↓
QuestionAnswerHandler
        ↓
Observation:
spatial_pattern = systemic
provenance = USER_ANSWER
        ↓
EvidenceEngine
        ↓
CauseRanker
        ↓
new ranking
        ↓
QuestionEngine
        ↓
new next question
        ↓
ActionPlanner
        ↓
new next check
        ↓
Revision N+1
        ↓
updated DiagnosisResult
```

Verify that every stage receives the updated information.

---

# 10. REQUIRED NEGATIVE TESTS

Before marking the checkpoint complete, test:

### Invalid question ID

```text
Q999
```

Expected:

```text
controlled validation error
```

No diagnosis corruption.

### Invalid answer

```text
Q01 = RANDOM_VALUE
```

Expected:

```text
controlled validation error
```

### UNKNOWN

```text
Q01 = UNKNOWN
```

Expected:

```text
no fabricated observation
```

### NOT_APPLICABLE

Verify it does not automatically become contradiction.

### Duplicate answer

Verify no duplicate evidence inflation.

### Missing reconstructed case

Expected:

```text
controlled error
```

No silently invented case state.

### Corrupted previous revision

Expected:

```text
controlled error
```

Do not silently reconstruct an incorrect history.

---

# 11. REQUIRED TEST FILES

Reuse the project's existing test structure where possible.

Locate or create the appropriate tests for:

```text
backend/tests/
├── unit/
│   ├── test_question_answer_handler.py
│   ├── test_question_engine.py
│   ├── test_evidence_engine.py
│   ├── test_cause_ranker.py
│   └── test_diagnosis_engine.py
│
└── integration/
    └── test_question_answer_diagnosis_revision.py
```

Do not create duplicate test modules if equivalent ones already exist.

---

# 12. REQUIRED MAPPING TABLE

Generate a machine-readable or documentation mapping table:

| Question ID | Answer | Observation Type | Observation Value | Provenance | Confidence | Expected |
|---|---|---|---|---|---|---|
| Q01 | ALL_POINTS | spatial_pattern | systemic | USER_ANSWER | N/A | observation |
| Q01 | ONE_POINT | spatial_pattern | localized | USER_ANSWER | N/A | observation |
| Q01 | UNKNOWN | - | - | - | - | no evidence |
| Q01 | NOT_APPLICABLE | - | - | - | - | no contradiction |
| Q02 | ... | ... | ... | ... | ... | ... |

The purpose of this table is to give Member 3 a stable contract.

Member 3 should not need to interpret diagnostic meaning manually.

---

# 13. REQUIRED VERIFICATION REPORT

At the end of the task, do NOT simply say:

```text
"Looks good."
```

Return a structured report:

## A. Repository findings

```text
Question definitions:
QuestionAnswerHandler:
StructuredCase:
DiagnosticEngine:
Revision handling:
Tests:
```

## B. Seven-gate results

```text
1. Stable question definitions       PASS / FAIL
2. Handler alignment                PASS / FAIL
3. Answer→observation semantics     PASS / FAIL
4. Deterministic rerun              PASS / FAIL
5. Duplicate evidence protection    PASS / FAIL
6. Updated diagnosis                PASS / FAIL
7. Revision N→N+1                   PASS / FAIL
```

## C. Tests executed

For every test:

```text
test name
result
failure reason if any
```

## D. Changes made

List:

```text
files created
files modified
files deleted
```

Do not make unrelated refactoring changes.

## E. Remaining gaps

Clearly separate:

```text
BLOCKING FOR DLK-M3-012
```

from:

```text
NOT BLOCKING FOR DLK-M3-012
```

---

# 14. DLK-M3-012 READINESS GATE

Mark the Member 2 component as:

## READY

only when all of the following are true:

```text
[ ] Stable question IDs
[ ] Stable allowed answer values
[ ] questions.json and handler aligned
[ ] Every supported answer has a defined semantic mapping
[ ] UNKNOWN does not invent evidence
[ ] NOT_APPLICABLE has correct semantics
[ ] User hypotheses are not treated as confirmed causes
[ ] Answer→observation tests pass
[ ] Same case + same answer is deterministic
[ ] Duplicate evidence does not inflate support
[ ] Earlier evidence is preserved
[ ] Updated ranking works
[ ] Updated next-question selection works
[ ] Updated next-check selection works
[ ] Revision N remains unchanged
[ ] Revision N+1 contains new evidence
[ ] End-to-end answer→rerun test passes
[ ] Negative validation tests pass
```

---

# 15. WHAT IS NOT REQUIRED FOR THIS CHECKPOINT

Do NOT block DLK-M3-012 because the following are incomplete:

```text
[ ] Root-cause confirmation workflow
[ ] Recovery verification
[ ] Full troubleshooting result workflow
[ ] LLM integration
[ ] Computer vision
[ ] Historical retrieval
[ ] Vector search
[ ] PDF reports
[ ] All six defect categories
[ ] Production deployment
[ ] Production accuracy
```

These belong to later milestones.

---

# 16. FINAL DECISION

After completing all checks, give exactly one final status:

```text
READY FOR DLK-M3-012
```

or

```text
NOT READY FOR DLK-M3-012
```

If NOT READY, list only the blocking items and explain the minimum required fix for each.

Do not implement later-phase features just to obtain READY status.

The target is a stable:

```text
Question
   ↓
Answer
   ↓
Observation
   ↓
Updated StructuredCase
   ↓
DiagnosticEngine
   ↓
Updated Analysis
   ↓
Revision N+1
```

contract.