# DispenseLens - Diagnostic Engine Architecture & Implementation Guide

> Refer to the complete summary document: [diagnostic_engine_workflow_summary.md](file:///c:/Users/koay/Documents/KOAY%20KOAY%20FILES/USM/AI%20Horizon/dispense_lense_koi/docs/diagnostic_engine_workflow_summary.md)

## Diagnostic Engine Responsibilities

The Diagnostic Engine (`app.services.diagnosis`) coordinates the reasoning layer of DispenseLens:

1. **Intake & Extraction:** Converts natural language problem descriptions to structured observations (`SymptomExtractor`).
2. **Defect Classification:** Deterministically classifies defect symptoms into D01–D06 (`identify_defect`).
3. **Hypothesis Evaluation:** Maps observations to root cause hypotheses via domain rules (`EvidenceEngine`).
4. **Deterministic Ranking:** Ranks causes by `Evidence Support /100` and generates score breakdowns (`CauseRanker`).
5. **Adaptive Questioning:** Selects next discriminating questions based on information gain (`QuestionEngine`).
6. **Physical Action Planning:** Prioritizes shopfloor checks by balancing hypothesis coverage against technician effort (`ActionPlanner`).
7. **Execution & Check Handling:** Processes check outcomes, strictly keeping blocked checks unknown (`CheckResultHandler`).
8. **Multi-Dimensional State Machine:** Decouples check execution, finding, cause conclusion, and issue condition (`StateManager`).
9. **Bounded LLM Summaries:** Translates deterministic results into clear text with strict safety guardrails (`ExplanationService`).

For the comprehensive breakdown of implementation details and interview presentation points, see [diagnostic_engine_workflow_summary.md](file:///c:/Users/koay/Documents/KOAY%20KOAY%20FILES/USM/AI%20Horizon/dispense_lense_koi/docs/diagnostic_engine_workflow_summary.md).
