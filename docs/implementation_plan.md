# Member 2 - AI + Diagnostic Intelligence
## Dispense Lens / AI Dispensing Defect Detective

## 1. Role Objective

The responsibility of Member 2 is to implement the **Diagnostic Intelligence Layer** that makes Dispense Lens an evidence-based troubleshooting engine rather than a generic chatbot.

The engine must support this cycle:

```text
User problem
    ↓
Extract structured symptoms
    ↓
Identify possible defect
    ↓
Retrieve applicable causes
    ↓
Evaluate evidence
    ↓
Rank possible causes
    ↓
Explain why
    ↓
Select next question OR troubleshooting check
    ↓
Receive user result
    ↓
Update evidence
    ↓
Re-rank causes
    ↓
Continue / resolve / handover
```

This follows the project requirement that the useful AI interaction is a repeated cycle of interpreting evidence, assessing hypotheses, selecting the next useful step, collecting the result, and updating the case. A single generative response is not sufficient.

---

# 2. Files Owned by Member 2

Use the existing Team KOI structure as the implementation target.

```text
backend/app/
│
├── services/
│   ├── diagnosis/
│   │   ├── engine.py
│   │   ├── symptom_extractor.py
│   │   ├── question_engine.py
│   │   ├── cause_ranker.py
│   │   ├── evidence_engine.py
│   │   └── action_planner.py
│   │
│   └── ai/
│       ├── llm_service.py
│       ├── prompt_manager.py
│       └── explanation_service.py
│
├── evaluation/
│   ├── benchmark.py
│   ├── metrics.py
│   └── scenarios.py
│
└── utils/
    └── scoring.py
```

Do not create unnecessary additional services. The planning package already identifies these as the intended diagnosis and AI boundaries, while the overall architecture treats them as logical modules rather than separate deployed services.

---

# 3. Responsibilities of Each File

## `engine.py`

Main orchestrator.

Responsibilities:

- receive a structured diagnosis request;
- call symptom extraction when required;
- identify the defect;
- load applicable causes;
- call the evidence engine;
- call the cause ranker;
- select the next question;
- select the next troubleshooting check;
- create the final structured diagnosis response;
- update analysis revision information.

This file should coordinate the other components rather than contain all their logic.

---

## `symptom_extractor.py`

Converts natural-language descriptions into structured observations.

Example input:

```text
"The dispensing dots become smaller after the machine
has been running for around 20 minutes."
```

Expected structured information:

```json
{
  "observations": [
    {
      "type": "deposit_size",
      "value": "undersized"
    },
    {
      "type": "time_pattern",
      "value": "after_prolonged_operation"
    }
  ]
}
```

The extractor must distinguish:

```text
USER OBSERVATION
USER INTERPRETATION
AI INFERENCE
```

For example, if the user says:

> "I think the nozzle is blocked."

store:

```text
user_statement:
"I think the nozzle is blocked."

user_hypothesis:
"nozzle_blockage"
```

Do NOT automatically create:

```text
confirmed_cause:
"nozzle_blockage"
```

The project explicitly requires observations and inferred causes to remain separate.

---

## `question_engine.py`

Selects the next most useful question.

Responsibilities:

- select only relevant questions;
- avoid already answered questions;
- handle `UNKNOWN`;
- handle unavailable information;
- identify when enough information has been gathered;
- avoid asking an arbitrary fixed number of questions;
- explain why the question is useful.

The competition initially suggests approximately five questions, but the project design allows additional questions when uncertainty remains.

---

## `cause_ranker.py`

Calculates cause-support scores.

Example:

```text
Air / Supply Issue       82
Nozzle Restriction       68
Material Condition       61
Pressure Instability     48
```

The score must come from the algorithm.

The LLM must NOT generate the score.

The planning documents specifically recommend inspectable score contributions and prohibit unexplained model-generated percentages.

---

## `evidence_engine.py`

Determines how each observation affects each candidate cause.

It must support:

```text
SUPPORTS
CONTRADICTS
UNKNOWN / MISSING
DUPLICATE / ALREADY REPRESENTED
```

This is one of the most important parts of the system.

---

## `action_planner.py`

Selects the next troubleshooting check.

The highest-ranked cause does not automatically determine the first action.

The action planner should consider:

```text
applicability
information gained
required access
effort
existing evidence
procedure/source requirements
previously attempted checks
```

The requirements explicitly distinguish **cause order** from **action order**.

---

## `llm_service.py`

Handles communication with the selected LLM provider.

The LLM is a supporting component, not the diagnostic authority.

Allowed uses:

```text
symptom extraction
natural-language interpretation
explanation generation
summary generation
```

Not allowed:

```text
inventing scores
inventing procedures
inventing sources
confirming causes automatically
declaring repair automatically
overriding structured diagnostic logic
```

The project explicitly describes this as **bounded model use**.

---

## `prompt_manager.py`

Stores and manages prompts.

Keep prompts separate from Python business logic.

Suggested prompts:

```text
extract_symptoms
explain_diagnosis
explain_score_change
summarize_case
```

Prompts should require structured output wherever applicable.

---

## `explanation_service.py`

Takes deterministic engine results and turns them into understandable text.

Input:

```json
{
  "cause": "air_supply_issue",
  "score": 82,
  "supporting_evidence": [
    "defect occurs intermittently",
    "problem appears after prolonged operation"
  ],
  "contradicting_evidence": [
    "no visible bubble reported"
  ],
  "missing_evidence": [
    "material supply condition has not been checked"
  ]
}
```

Output:

```text
Air / Supply Issue is currently the highest-supported cause
because the defect appears intermittently and becomes more
noticeable after prolonged operation.

However, the cause is not confirmed because the material
supply condition has not yet been checked.
```

---

# 4. Overall Implementation Order

Do not code everything at once.

Build in this order:

```text
PHASE 1
Define contracts and data structures
        ↓
PHASE 2
Create knowledge representation
        ↓
PHASE 3
Implement symptom extraction
        ↓
PHASE 4
Implement defect identification
        ↓
PHASE 5
Implement evidence engine
        ↓
PHASE 6
Implement cause ranking
        ↓
PHASE 7
Implement question engine
        ↓
PHASE 8
Implement action planner
        ↓
PHASE 9
Implement bounded LLM
        ↓
PHASE 10
Build diagnosis orchestrator
        ↓
PHASE 11
Connect SQL / backend contracts
        ↓
PHASE 12
Implement evaluation
        ↓
PHASE 13
Expand from one defect to all six
```

The planning package uses the same progression: specification → first connected diagnosis → adaptive conversation → guided checks → full six-defect coverage → evaluation.

---

# 5. PHASE 1 - Define the Data Contracts

Before implementing algorithms, define the data objects.

Create internal Pydantic models or equivalent typed models for:

```text
DiagnosisRequest
DiagnosisResult

StructuredCase
Observation

CandidateCause
CauseEvidence

Question
QuestionAnswer

TroubleshootingCheck
CheckResult

AnalysisRevision
```

---

## 5.1 `DiagnosisRequest`

Recommended structure:

```python
class DiagnosisRequest(BaseModel):
    case_id: str | None
    description: str
    material: str | None
    method: str | None
    machine_context: dict | None = None
    observations: list[Observation] = []
    previous_answers: list[QuestionAnswer] = []
    previous_check_results: list[CheckResult] = []
    analysis_revision: int = 1
```

Do not require every context field.

Unknown context must be allowed.

The current first-prototype scope explicitly supports plain-language input, process context, unknown answers and optional image uploads; sensor data is not required.

---

# 6. PHASE 2 - Define the Knowledge Model

Initially support these six mandatory defects:

```text
D01_TOO_LITTLE
D02_TOO_MUCH
D03_INCONSISTENT_SIZE
D04_MISSING_DOTS
D05_SPREADING
D06_BUBBLES_ABNORMAL_SHAPE
```

The challenge explicitly lists these six defect types.

For each defect define:

```text
description
symptom patterns
possible causes
relevant questions
relevant checks
source references
applicable context
```
Do not put domain rules directly inside Python files.

Use the project's knowledge structure:

```text
backend/app/knowledge/
├── defects.json
├── causes.json
├── questions.json
├── actions.json
└── rules.json
```

Team KOI specifically defines these files and says they establish the domain knowledge source.

The coding agent should create a **knowledge access interface**, for example:

```python
get_defect(defect_id)
get_candidate_causes(defect_id, context)
get_evidence_rules(cause_id)
get_questions(cause_ids)
get_actions(cause_ids, context)
```

### Important update

Do **not** create an independent second set of rules inside:

```text
cause_ranker.py
question_engine.py
action_planner.py
```

The algorithms should **consume knowledge**, not duplicate it.

The planning package also explicitly recommends one canonical authored knowledge source rather than conflicting JSON and SQL rule copies.

---

# 7. PHASE 3 - Implement Symptom Extraction

## Step 3.1 - Normalize text

Input:

```text
"The dots are small after 20 minutes."
```

Normalize into:

```text
deposit size = undersized
time relation = prolonged operation
```

Do not lose the original sentence.

Store:

```text
original_description
extracted_observations
```

---

## Step 3.2 - Use an LLM only when appropriate

The LLM should return structured JSON.

Example:

```json
{
  "observations": [
    {
      "type": "deposit_size",
      "value": "undersized",
      "confidence": null
    },
    {
      "type": "runtime_pattern",
      "value": "after_prolonged_operation",
      "confidence": null
    }
  ]
}
```

Do not ask the LLM to return root-cause probabilities.

---

## Step 3.3 - Validate the response

If the LLM returns:

```text
"Air bubble is 90% likely."
```

that response must be rejected for the extraction stage because it has crossed into diagnosis.

The system should retain the original input and either:

```text
retry
or
fall back to simple extraction
```

The requirements specifically require model failures and invalid outputs to be handled visibly rather than converted into fabricated success.

---

# 8. PHASE 4 - Defect Identification

Create a deterministic defect mapper first.

Example:

```python
def identify_defect(observations):
    if has_inconsistent_deposit_size(observations):
        return "D03_INCONSISTENT_SIZE"

    if has_missing_deposit(observations):
        return "D04_MISSING_DOTS"

    if has_excessive_spreading(observations):
        return "D05_SPREADING"

    ...
```

Do not begin with a neural-network classifier.

The first prototype needs traceable behaviour.

Example:

```text
Input:
Some dots are larger and some are smaller.

Output:
D03_INCONSISTENT_SIZE

Reason:
Deposit size varies across dispensing shots.
```

---

# 9. PHASE 5 - Evidence Engine

This is the core reasoning layer.

## Step 5.1 - Retrieve candidate causes

For the identified defect:

```text
D03_INCONSISTENT_SIZE
```

retrieve:

```text
Air / Supply Issue
Nozzle Restriction
Material Condition
Pressure Instability
Parameter Issue
Equipment Condition
```

Only retrieve causes applicable to the selected process/material scope.

---

## Step 5.2 - Evaluate every observation

For every:

```text
observation × candidate cause
```

determine:

```text
SUPPORTS
CONTRADICTS
NEUTRAL / UNKNOWN
DUPLICATE
```

Example:

```text
Observation:
"Defect happens intermittently."

Cause:
Air / Supply Issue

Evaluation:
SUPPORTS
```

Example:

```text
Observation:
"Defect always occurs at exactly one nozzle."

Cause:
Air / Supply Issue

Evaluation:
CONTRADICTS / WEAKENS
```

---

## Step 5.3 - Preserve provenance

Every evidence item should record:

```text
source = USER
source = MEASUREMENT
source = IMAGE
source = SYSTEM
source = HISTORICAL_CASE
```

Do not treat all evidence as equally reliable automatically.

The project requires provenance to remain distinguishable between user observations, measurements, retrieved guidance and inferred causes.

---

## Step 5.4 - Prevent duplicate evidence

Example:

```text
Observation A:
"Dot is small."

Observation B:
"Deposit is undersized."

Observation C:
"Dispensing volume is low."
```

These might represent the same underlying observation.

Do not allow all three to independently contribute full weight.

The requirements explicitly warn against inflating support with repeated or correlated observations.

---

# 10. PHASE 6 - Cause Ranking Algorithm

The Team KOI files explicitly contain:

```text
backend/app/services/retrieval/
├── case_retriever.py
├── embeddings.py
└── similarity.py
```

and describe historical cases as an input to diagnosis.

Therefore the cause ranker should be designed to accept:

```python
historical_evidence: list[HistoricalEvidence]
```

Example:

```text
Current case:
Undersized/intermittent dispensing

Historical evidence:
5 similar cases

3 confirmed:
Air / Supply Issue

1 confirmed:
Nozzle Restriction

1 confirmed:
Material Condition
```

The historical results should become **evidence**, not automatic truth.

For example:

```text
Historical evidence:
supports Air / Supply Issue

BUT

current case:
different material
```

Therefore the historical contribution may be reduced or ignored depending on applicability.

### Important

Member 2 does **not** implement:

```text
embeddings.py
similarity.py
case_retriever.py
```

Those belong to the Historical Retrieval module.

Member 2 only defines **how retrieved historical evidence affects diagnosis**.

---

For the first implementation, use a deterministic evidence-support algorithm.

Do NOT claim this is a calibrated probability.

Use:

```text
Evidence Support: XX/100
```

rather than:

```text
Probability: XX%
```

unless later testing establishes a valid probability interpretation.

---

## 10.1 Suggested scoring design

Use a configurable scoring model.

For example:

```text
final_score =
    positive_evidence_score
    - contradiction_penalty
    - uncertainty_penalty
```

Do not hard-code the exact final weights until the team reviews representative scenarios.

Create:

```python
SCORING_CONFIG = {
    "strong_support": ...,
    "moderate_support": ...,
    "weak_support": ...,
    "contradiction": ...,
    "duplicate": 0,
}
```

Keep the configuration centralized in:

```text
backend/app/utils/scoring.py
```

---

## 10.2 Score every cause independently

Do not force the scores to sum to 100.

Example:

```text
Air / Supply Issue       82
Nozzle Restriction       68
Material Condition       61
Pressure Instability     48
```

These can represent independent evidence support.

The planning document explicitly says candidate scores do not necessarily need to sum to 100.

---

## 10.3 Return score explanation

For each cause return:

```json
{
  "cause": "air_supply_issue",
  "score": 82,
  "supporting_evidence": [
    "...",
    "..."
  ],
  "contradicting_evidence": [
    "..."
  ],
  "missing_evidence": [
    "..."
  ]
}
```

The UI can then display:

```text
Air / Supply Issue
Evidence Support: 82/100

Supporting Evidence
✓ Issue appears after prolonged operation
✓ Dispensing size varies intermittently

Contradicting Evidence
⚠ No visible bubble reported

Missing Information
? Supply condition has not been checked
```

---

# 11. PHASE 7 - Diagnostic Question Engine

The Question Engine should not simply generate five generic questions.

It should select questions that distinguish the **current competing hypotheses**.

## Step 7.1 - Identify missing evidence

Example:

```text
Air Issue:       82
Nozzle Issue:    68
Material Issue:  61
```

Missing evidence:

```text
Does the problem happen at one nozzle
or across all dispensing points?
```

---

## Step 7.2 - Find candidate questions

Retrieve questions associated with those causes.

Example:

```text
Q01:
Does the problem occur immediately or after operation?

Q02:
Does the defect occur across all dispensing points?

Q03:
Has the nozzle recently been replaced?

Q04:
Does purging change the result?
```

---

## Step 7.3 - Rank questions

Use a simple information-usefulness approach.

Conceptually:

```text
Question usefulness =
    number of competing causes affected
    +
    amount of uncertainty reduced
    +
    applicability
    -
    already_answered_penalty
```

You do not need a sophisticated information-theory model for Version 1.

---

## Step 7.4 - Stop asking questions

The engine must stop when:

```text
sufficient evidence exists
OR
no useful unanswered question remains
OR
a troubleshooting check is more useful
OR
the case must be handed over
```

The project explicitly requires a stopping condition and no endless questioning.

---

# 12. PHASE 8 - Action Planner

When enough information is available, choose a troubleshooting check.

Example:

```text
Top causes:

Air issue       82
Nozzle issue    68
Material issue  61
```

Possible checks:

```text
Check nozzle
Check supply condition
Check material state
Check dispensing settings
Perform test shots
```

The Action Planner should rank checks based on:

```text
1. Applicable?
2. Safe/approved within current knowledge?
3. Has it already been attempted?
4. How much information can it provide?
5. How many hypotheses can it distinguish?
6. Is the technician able to perform it?
```

A high-ranked cause does not automatically mean its associated check must happen first.

---

# 13. PHASE 9 - Check Result Handling

The technician must be able to return:

```text
COMPLETED
BLOCKED
UNKNOWN
FAILED
NOT_APPLICABLE
```

Then separately record the finding:

```text
SUPPORTS
CONTRADICTS
INCONCLUSIVE
UNKNOWN
```

For example:

```text
Check:
Inspect nozzle

Execution:
BLOCKED

Finding:
UNKNOWN
```

Never translate this into:

```text
"No nozzle blockage."
```

The project specifically requires blocked checks to remain unknown.

---

# 14. PHASE 10 - Re-ranking After New Evidence

This is essential.

Example:

### Revision 1

```text
Air issue       82
Nozzle issue    68
Material issue  61
```

Technician checks nozzle.

Result:

```text
No visible blockage.
```

### Revision 2

```text
Air issue       82
Material issue  61
Nozzle issue    38
```

The engine should:

1. preserve Revision 1;
2. add the new observation;
3. recalculate evidence;
4. generate Revision 2;
5. explain what changed.

The project requires the analysis to be updated when new evidence arrives while preserving the investigation history.

---

# 15. PHASE 11 - State Management

Keep these four state dimensions separate.

```text
Step execution
    Pending
    In Progress
    Completed
    Blocked
    Skipped

Step finding
    Supports
    Contradicts
    Inconclusive
    Unknown
    Not Applicable

Cause conclusion
    Suspected
    Confirmed
    Unresolved

Issue condition
    Unresolved
    Recovery Pending Verification
    Resolved
    Recurred
```

Do not do this:

```python
if check_completed:
    cause = "confirmed"
    issue = "resolved"
```

That is explicitly incorrect.

The project requires cause confirmation and issue resolution to remain independent.

---

# 16. PHASE 12 - LLM Integration

Only after the deterministic diagnosis pipeline works should the LLM be integrated.

## LLM responsibility #1 - Symptom extraction

```text
Technician:
"The dot gets smaller after 20 minutes."

LLM:
{
    "deposit_size": "undersized",
    "runtime_pattern": "after_prolonged_operation"
}
```

---

## LLM responsibility #2 - Explanation

Input:

```text
Cause:
Air Issue

Score:
82

Evidence:
- intermittent variation
- prolonged-operation pattern

Contradiction:
- no visible bubble reported
```

Output:

```text
Air / Supply Issue is currently the highest-supported
cause because the defect appears intermittently and
becomes more noticeable after prolonged operation.

It is not confirmed yet because the supply condition
has not been directly checked.
```

---

## LLM responsibility #3 - Summary

At the end of the case:

```text
The investigation started with inconsistent dispensing size.
The nozzle check did not support blockage, so nozzle restriction
was downgraded. Air/supply-related causes remain the strongest
supported hypothesis. The issue is currently unresolved.
```

---

# 17. LLM Safety / Reliability Rules

The coding agent must enforce these rules:

### Rule 1

LLM cannot produce the official numerical score.

### Rule 2

LLM cannot create a troubleshooting procedure that isn't present in the knowledge base.

### Rule 3

LLM cannot invent a source.

### Rule 4

LLM cannot declare a root cause confirmed.

### Rule 5

LLM cannot declare the dispensing issue resolved.

### Rule 6

LLM failure must not corrupt the deterministic analysis.

### Rule 7

Original user wording must remain available.

The planning task explicitly requires validated output, honest handling of model failures, and preservation of user wording/source references.

---

# 18. PHASE 13 - Diagnosis Engine Orchestrator

`engine.py` should eventually expose something conceptually like:

```python
class DiagnosticEngine:

    def diagnose(
        self,
        case: StructuredCase
    ) -> DiagnosisResult:

        structured_case = self.prepare_case(case)

        defect = self.identify_defect(
            structured_case
        )

        candidates = self.get_candidates(
            defect,
            structured_case.context
        )

        evidence = self.evaluate_evidence(
            structured_case,
            candidates
        )

        ranked_causes = self.rank_causes(
            candidates,
            evidence
        )

        next_question = self.select_question(
            structured_case,
            ranked_causes
        )

        next_check = self.select_check(
            structured_case,
            ranked_causes
        )

        explanation = self.explain(
            structured_case,
            ranked_causes
        )

        return DiagnosisResult(
            defect=defect,
            causes=ranked_causes,
            next_question=next_question,
            next_check=next_check,
            explanation=explanation
        )
```

The important design principle is that `engine.py` coordinates; individual modules perform individual responsibilities.

---

# 19. PHASE 14 - SQL Database Integration

Member 2 owns the intelligence, while Member 2 and Member 3/B need a clear interface.

The diagnostic engine should **read knowledge from the database and return structured analysis**.

It should not directly own persistence logic.

The planning documents explicitly state that the engine consumes a structured case and returns analysis, while the case-record layer stores snapshots and workflow orchestration coordinates the calls.

### Engine reads:

```text
defects
causes
defect_causes
evidence_rules
questions
cause_questions
checks
cause_checks
sources
```

### Engine receives:

```text
case
observations
answers
previous checks
previous analysis
context
```

### Engine returns:

```text
defect
ranked causes
scores
evidence
next question
next check
explanation
analysis revision
```

### Backend/B stores:

```text
cases
observations
answers
analysis revisions
cause rankings
check executions
outcomes
```

Do not make `engine.py` perform raw SQL persistence.

---

# 20. PHASE 15 - Evaluation Framework

Create:

```text
backend/app/evaluation/
├── benchmark.py
├── metrics.py
└── scenarios.py
```

---

## `scenarios.py`

Create controlled scenarios.

Minimum:

```text
6 defects × 2 scenarios = 12 scenarios
```

For each defect:

### Scenario A

Normal supported evidence.

### Scenario B

Missing/contradictory evidence or blocked check.

This matches the project's proposed functional coverage floor.

---

# 21. Example Evaluation Scenario

```python
SCENARIO_01 = {
    "name": "Inconsistent size - intermittent",
    "description":
        "Dispensing dots become smaller intermittently "
        "after prolonged operation.",

    "expected_defect":
        "D03_INCONSISTENT_SIZE",

    "acceptable_causes": [
        "air_supply_issue",
        "nozzle_restriction",
        "material_condition"
    ],

    "expected_top_causes": [
        "air_supply_issue",
        "nozzle_restriction"
    ],

    "must_not_claim":
        "confirmed_cause"
}
```

Important:

Do not force one cause to be "correct" when multiple causes are legitimately supported. The evaluation plan explicitly says ambiguous cases can have multiple acceptable hypotheses.

---

# 22. Evaluation Metrics

## Metric 1 - Defect Classification Accuracy

```text
correct defect classifications
───────────────────────────────
total scenarios
```

---

## Metric 2 - Top-1 Cause Accuracy

```text
scenario where accepted cause is ranked #1
─────────────────────────────────────────
total scenarios
```

Use only where the test scenario has a sufficiently defined expected top cause.

---

## Metric 3 - Top-3 Cause Coverage

More appropriate for ambiguous diagnosis.

```text
scenario where an acceptable cause appears
within the top 3
────────────────────────────────────────
total applicable scenarios
```

---

## Metric 4 - Average Number of Questions

Measure:

```text
Total questions asked
─────────────────────
Completed cases
```

This helps determine whether the engine is asking too many questions.

---

## Metric 5 - Evidence Traceability

For each ranked cause:

```text
Does every score contribution
map to an evidence item?
```

---

## Metric 6 - Contradiction Handling

Test whether a contradictory observation reduces or changes the applicable cause support according to the scoring design.

---

## Metric 7 - Duplicate Evidence Handling

Submit the same observation multiple times.

The score should not keep increasing simply because the evidence was duplicated.

---

## Metric 8 - Model Failure Handling

Force the LLM service to fail.

Expected result:

```text
Diagnosis remains functional
+
LLM explanation unavailable
+
No fabricated explanation
+
Original evidence retained
```

These behaviours are explicitly part of the project's acceptance checks.

---

# 23. Unit Tests Required

Create:

```text
backend/tests/
├── unit/
│   ├── test_symptom_extractor.py
│   ├── test_evidence_engine.py
│   ├── test_cause_ranker.py
│   ├── test_question_engine.py
│   ├── test_action_planner.py
│   ├── test_scoring.py
│   └── test_ai_outputs.py
│
└── fixtures/
    └── sample_cases.py
```

---

## Cause-ranker tests

Test:

```text
✓ supporting evidence increases support
✓ contradiction changes support
✓ missing evidence is not treated as contradiction
✓ duplicate evidence does not double-count
✓ unsupported context is excluded
✓ ranking is deterministic
```

---

## Question-engine tests

Test:

```text
✓ unanswered useful question selected
✓ answered question not repeated
✓ UNKNOWN handled
✓ contradictory answer changes next question
✓ stopping condition works
✓ no infinite loop
```

---

## Action-planner tests

Test:

```text
✓ applicable check selected
✓ unavailable check excluded
✓ blocked check produces alternative
✓ repeated failed check is not blindly repeated
✓ action explanation is present
```

---

## LLM tests

Test:

```text
✓ valid structured extraction
✓ malformed JSON
✓ hallucinated cause
✓ invented source
✓ invented procedure
✓ service timeout
✓ service unavailable
✓ ambiguous user statement
```

---

# 24. First Implementation Milestone

Do NOT immediately implement all six defect categories.

The first successful milestone should be:

## Inconsistent Dispensing Size

```text
User:
"Some dots become smaller after the machine runs for 20 minutes."

                 ↓

Symptom Extractor

                 ↓

Defect:
Inconsistent Dispensing Size

                 ↓

Candidates:

Air / Supply Issue       82
Nozzle Restriction       68
Material Condition       61
Pressure Instability     48

                 ↓

Question:

"Does the problem occur across all dispensing
points or only at one location?"

                 ↓

User:
"All dispensing points."

                 ↓

Evidence update

                 ↓

New ranking

                 ↓

Recommended check

                 ↓

Technician result

                 ↓

New analysis revision
```

This should be your **first end-to-end working scenario**. The planning package explicitly describes one connected diagnosis as the first integration milestone before expanding to all six defects.

---

# 25. Then Expand to All Six Defects

Once the first scenario works:

```text
D01 Too Little Material
D02 Too Much Material
D03 Inconsistent Size
D04 Missing Dots
D05 Spreading
D06 Bubbles / Abnormal Shape
```

For every defect create:

```text
candidate causes
evidence rules
questions
checks
outcomes
evaluation scenarios
```

The system should not silently skip a defect because evidence is incomplete. An unsupported scope should be surfaced honestly.

---

# 26. What NOT to Implement Yet

To keep Member 2 focused, defer:

```text
X Autonomous AI agent framework
X Direct machine control
X Automatic machine parameter adjustment
X Complex Bayesian model
X Deep neural network for root cause
X Vector database / semantic retrieval
X Advanced computer vision
X Real-time sensor integration
X Automated retraining from user feedback
```

These are not necessary for the core prototype and some remain explicitly deferred/open decisions.

The first version should prove:

```text
structured evidence
+
deterministic diagnosis
+
adaptive questions
+
troubleshooting checks
+
bounded LLM
```

---

# 27. Definition of Done for Member 2

Member 2 is done only when all of these are true:

### Core engine

```text
[ ] engine.py works
[ ] symptom extraction works
[ ] defect identification works
[ ] evidence engine works
[ ] cause ranking works
[ ] question engine works
[ ] action planner works
```

### AI

```text
[ ] LLM symptom extraction works
[ ] LLM explanation works
[ ] invalid LLM output handled
[ ] LLM cannot modify official scores
[ ] LLM cannot invent procedures
```

### Evidence

```text
[ ] supporting evidence shown
[ ] contradicting evidence shown
[ ] missing evidence shown
[ ] duplicate evidence handled
[ ] provenance preserved
```

### Adaptive behaviour

```text
[ ] answers update diagnosis
[ ] questions are not repeated unnecessarily
[ ] UNKNOWN works
[ ] BLOCKED works
[ ] failed checks lead to alternatives
```

### Evaluation

```text
[ ] 12 minimum functional scenarios
[ ] unit tests
[ ] cause ranking benchmark
[ ] defect classification benchmark
[ ] question-count measurement
[ ] model failure scenario
```

### Integration

```text
[ ] engine accepts structured case
[ ] engine returns structured result
[ ] database contract documented
[ ] backend can invoke engine
[ ] analysis revision can be saved
[ ] frontend can display the result
```

---

# 28. Recommended Coding Sequence

The coding agent should follow this exact order:

```text
1. Inspect existing repository.
2. Do NOT overwrite existing working code.
3. Identify existing backend models/schemas/database utilities.
4. Define diagnosis data contracts.
5. Build scoring utilities.
6. Build knowledge loading/query interface.
7. Implement symptom extractor.
8. Implement defect identification.
9. Implement evidence engine.
10. Implement cause ranker.
11. Write unit tests for evidence + ranking.
12. Implement question engine.
13. Implement action planner.
14. Write question/action tests.
15. Implement diagnosis orchestrator.
16. Build one complete inconsistent-size scenario.
17. Add bounded LLM service.
18. Add explanation service.
19. Add model failure handling.
20. Connect engine to the existing backend API.
21. Add SQL/database integration through existing backend contracts.
22. Add analysis revision handling.
23. Expand knowledge to remaining five defects.
24. Add evaluation scenarios.
25. Run benchmark.
26. Fix failures.
27. Document final architecture and scoring behaviour.
```

Do not jump directly to Step 23 before Step 16 works.

---

# 29. Important Database Boundary

The coding agent must respect this architecture:

```text
                 SQL DATABASE
                      ▲
                      │
                Backend / B
                      │
               structured case
                      │
                      ▼
              MEMBER 2 ENGINE
                      │
            ┌─────────┼─────────┐
            ▼         ▼         ▼
       Knowledge   Evidence   Ranking
            │         │         │
            └─────────┼─────────┘
                      ▼
                  Diagnosis
                      │
                      ▼
                 Backend / B
                      │
                      ▼
                 SQL DATABASE
```

Do NOT put SQL CRUD logic directly inside:

```text
cause_ranker.py
evidence_engine.py
question_engine.py
```

Those components should operate on structured Python objects.

Database persistence should remain behind the backend/repository/API boundary. The project explicitly separates the diagnostic engine from case-record persistence.

---

# 30. READY-TO-PASTE PROMPT FOR THE CODING AI AGENT

Use the following as the implementation instruction to another coding agent:

---

## CODING AGENT TASK

You are implementing **Member 2 - AI + Diagnostic Intelligence** for the Dispense Lens project.

The objective is to build an explainable AI troubleshooting engine for fluid-dispensing defects.

Use the existing project structure:

```text
backend/app/
├── services/
│   ├── diagnosis/
│   │   ├── engine.py
│   │   ├── symptom_extractor.py
│   │   ├── question_engine.py
│   │   ├── cause_ranker.py
│   │   ├── evidence_engine.py
│   │   └── action_planner.py
│   └── ai/
│       ├── llm_service.py
│       ├── prompt_manager.py
│       └── explanation_service.py
├── evaluation/
│   ├── benchmark.py
│   ├── metrics.py
│   └── scenarios.py
└── utils/
    └── scoring.py
```

### Primary architecture

Implement:

```text
Structured Case
      ↓
Symptom Extraction
      ↓
Defect Identification
      ↓
Candidate Cause Retrieval
      ↓
Evidence Evaluation
      ↓
Cause Ranking
      ↓
Question / Action Selection
      ↓
Structured Diagnosis Result
      ↓
LLM Explanation
```

### Critical rules

1. The LLM must NOT calculate the official cause score.
2. The LLM must NOT invent causes without structured knowledge support.
3. The LLM must NOT invent troubleshooting procedures.
4. The LLM must NOT invent sources.
5. The LLM must NOT confirm root cause automatically.
6. The LLM must NOT mark the issue resolved automatically.
7. Use deterministic, inspectable scoring.
8. Distinguish supporting evidence from contradicting evidence.
9. Distinguish missing evidence from contradictory evidence.
10. Do not double-count duplicate/correlated evidence.
11. Preserve evidence provenance.
12. Support `UNKNOWN`, `BLOCKED`, `INCONCLUSIVE`, and `NOT_APPLICABLE`.
13. Preserve analysis revisions rather than overwriting previous reasoning.
14. Do not silently convert a blocked check into negative evidence.
15. Cause confirmation and issue resolution must remain separate states.

### First implementation target

Implement one complete scenario:

```text
Defect:
Inconsistent Dispensing Size
```

Example:

```text
"The dispensing dots become smaller after
the machine has been running for 20 minutes."
```

The engine should:

1. extract structured observations;
2. identify the defect;
3. retrieve possible causes;
4. calculate evidence support;
5. rank causes;
6. explain supporting/contradicting/missing evidence;
7. choose a useful question;
8. process the answer;
9. update the evidence;
10. produce a new analysis revision.

Only after this scenario works should the remaining five defects be added.

### Initial six defects

```text
D01_TOO_LITTLE
D02_TOO_MUCH
D03_INCONSISTENT_SIZE
D04_MISSING_DOTS
D05_SPREADING
D06_BUBBLES_ABNORMAL_SHAPE
```

### Testing

Create unit tests for:

```text
symptom extraction
evidence evaluation
cause ranking
question selection
action planning
scoring
LLM output validation
```

Create at least:

```text
12 functional scenarios
```

using:

```text
6 defects ×
1 normal supported scenario +
1 missing/contradictory/blocked scenario
```

Also test:

```text
duplicate evidence
unknown answers
blocked checks
contradictory evidence
model failure
unsupported context
cause confirmed + issue unresolved
cause unconfirmed + issue resolved
```

### Database boundary

Do not put database persistence logic inside the diagnostic algorithms.

The engine should receive a structured case and return a structured diagnosis.

Use existing backend/database interfaces to obtain:

```text
defects
causes
evidence rules
questions
checks
sources
previous case evidence
```

and return:

```text
identified defect
ranked causes
support scores
supporting evidence
contradicting evidence
missing evidence
next question
next check
explanation
analysis revision
```

### Code quality

Before writing new files:

1. Inspect the existing repository.
2. Reuse existing models, schemas, utilities and database helpers.
3. Do not overwrite working code unnecessarily.
4. Keep each module focused on one responsibility.
5. Use typed Python models.
6. Add docstrings for public classes/functions.
7. Handle external LLM failures explicitly.
8. Do not hard-code secrets.
9. Keep scoring configuration centralized.
10. Run relevant unit tests after each major component.

At the end, provide:

```text
1. Files created
2. Files modified
3. Architecture implemented
4. Scoring method
5. Test results
6. Known limitations
7. Remaining integration work
```

Do not claim production accuracy or calibrated probabilities unless they have actually been evaluated and demonstrated.

---

# 31. Final Architecture to Show the Coding Agent

```text
                         USER
                           │
                           ▼
                ┌────────────────────┐
                │ Symptom Extractor   │
                │      LLM            │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │  Structured Case   │
                └─────────┬──────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
       ┌───────────────┐     ┌───────────────┐
       │ Knowledge Base│     │ Evidence Engine│
       └───────┬───────┘     └───────┬───────┘
               │                     │
               └──────────┬──────────┘
                          ▼
                  ┌───────────────┐
                  │ Cause Ranker  │
                  └───────┬───────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
      ┌──────────────┐       ┌────────────────┐
      │Question Engine│       │ Action Planner │
      └──────┬───────┘       └───────┬────────┘
             │                       │
             └───────────┬───────────┘
                         ▼
                    TECHNICIAN
                         │
                         ▼
                  Check / Answer
                         │
                         ▼
                  Evidence Update
                         │
                         ▼
                   Re-ranking
                         │
                         ▼
              ┌─────────────────────┐
              │ Explanation Service │
              │        LLM          │
              └──────────┬──────────┘
                         ▼
                 Human-readable
                    Diagnosis
```

The resulting system should therefore be presented as:

> **A structured diagnostic engine with bounded AI assistance - not an LLM chatbot.**

That positioning is consistent with the project requirements: the system should identify and rank possible causes, explain its reasoning, ask useful questions, recommend logical troubleshooting actions, and update the investigation when new evidence appears.