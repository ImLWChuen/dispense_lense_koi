"""
DispenseIQ — Diagnostic Engine Orchestrator

Phases 9–11 Implementation & Phase 13 Orchestrator:
- Phase 9: Check Result Handling (supports COMPLETED, BLOCKED, UNKNOWN, FAILED,
           NOT_APPLICABLE; strictly enforces that BLOCKED checks remain UNKNOWN
           and never convert to negative findings).
- Phase 10: Re-ranking After New Evidence (preserves prior revisions, incorporates
            new observations, recalculates evidence, generates new revision, explains
            what changed).
- Phase 11: State Management (maintains 4 independent dimensions: step execution,
            step finding, cause conclusion, issue condition; strictly forbids
            coupling check completion to cause confirmation or issue resolution).
- Phase 13: Full diagnostic lifecycle orchestration.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.knowledge import (
    get_action_by_id,
    get_causes_for_defect,
    load_actions,
    load_questions,
)
from app.schemas.diagnosis import (
    AnalysisRevision,
    AnswerValue,
    CandidateCause,
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    DiagnosisRequest,
    DiagnosisResult,
    EvidenceRelation,
    EvidenceSource,
    EvidenceStrength,
    IssueCondition,
    Observation,
    ObservationType,
    Question,
    QuestionAnswer,
    StatementType,
    StructuredCase,
    TroubleshootingCheck,
)
from app.services.diagnosis.action_planner import ActionPlanner
from app.services.diagnosis.cause_ranker import CauseRanker, RankingResult
from app.services.diagnosis.defect_identifier import identify_defect
from app.services.diagnosis.evidence_engine import EvidenceEngine
from app.services.diagnosis.question_engine import QuestionEngine
from app.services.diagnosis.symptom_extractor import SymptomExtractor
from app.utils.scoring import SCORING_CONFIG


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


# ===========================================================================
# PHASE 11: State Management
# ===========================================================================

class StateManager:
    """Manages and enforces strict independence between the four state dimensions:

    1. Step Execution:  PENDING, IN_PROGRESS, COMPLETED, BLOCKED, SKIPPED, FAILED, UNKNOWN, NOT_APPLICABLE
    2. Step Finding:    SUPPORTS, CONTRADICTS, INCONCLUSIVE, UNKNOWN, NOT_APPLICABLE
    3. Cause Conclusion: SUSPECTED, CONFIRMED, UNRESOLVED
    4. Issue Condition: UNRESOLVED, RECOVERY_PENDING_VERIFICATION, RESOLVED, RECURRED

    CRITICAL RULE:
        Completing a check does NOT automatically confirm a cause.
        Confirming a cause does NOT automatically resolve the dispensing issue.
        Resolving an issue requires independent recovery verification.
    """

    # Legal transitions for overall IssueCondition
    _VALID_ISSUE_TRANSITIONS: dict[IssueCondition, set[IssueCondition]] = {
        IssueCondition.UNRESOLVED: {
            IssueCondition.RECOVERY_PENDING_VERIFICATION,
            IssueCondition.UNRESOLVED,
        },
        IssueCondition.RECOVERY_PENDING_VERIFICATION: {
            IssueCondition.RESOLVED,
            IssueCondition.UNRESOLVED,  # verification failed, revert
            IssueCondition.RECOVERY_PENDING_VERIFICATION,
        },
        IssueCondition.RESOLVED: {
            IssueCondition.RECURRED,
            IssueCondition.RESOLVED,
        },
        IssueCondition.RECURRED: {
            IssueCondition.RECOVERY_PENDING_VERIFICATION,
            IssueCondition.UNRESOLVED,
            IssueCondition.RECURRED,
        },
    }

    @staticmethod
    def validate_state_independence(
        execution_status: CheckExecutionStatus,
        finding: CheckFinding,
        cause_conclusion: CauseConclusion,
        issue_condition: IssueCondition,
    ) -> tuple[bool, list[str]]:
        """Verify that state dimensions remain independent and do not violate rules.

        Returns:
            (is_valid, list of warning messages)
        """
        warnings: list[str] = []

        # Rule 1: BLOCKED execution must have UNKNOWN / INCONCLUSIVE finding
        non_executing = {
            CheckExecutionStatus.BLOCKED,
            CheckExecutionStatus.FAILED,
            CheckExecutionStatus.UNKNOWN,
            CheckExecutionStatus.NOT_APPLICABLE,
            CheckExecutionStatus.SKIPPED,
        }
        if execution_status in non_executing and finding not in (
            CheckFinding.UNKNOWN,
            CheckFinding.INCONCLUSIVE,
            CheckFinding.NOT_APPLICABLE,
        ):
            warnings.append(
                f"Check execution is {execution_status.value} but finding was recorded as {finding.value}. "
                f"Non-completed checks must remain UNKNOWN."
            )

        # Rule 2: COMPLETED check must not automatically confirm a cause
        # (cause confirmation requires high confidence + direct confirmatory verification)
        if (
            execution_status == CheckExecutionStatus.COMPLETED
            and cause_conclusion == CauseConclusion.CONFIRMED
        ):
            # Allowed only when explicitly justified, but flag for audit
            pass

        # Rule 3: COMPLETED check must never automatically set issue to RESOLVED
        if (
            execution_status == CheckExecutionStatus.COMPLETED
            and issue_condition == IssueCondition.RESOLVED
        ):
            warnings.append(
                "A completed troubleshooting check cannot directly declare the issue RESOLVED. "
                "Issue resolution requires independent verification (e.g. post-repair test shots)."
            )

        is_valid = len(warnings) == 0
        return is_valid, warnings

    @staticmethod
    def evaluate_cause_conclusion(
        candidate: CandidateCause,
        check_results: list[CheckResult] | None = None,
    ) -> CauseConclusion:
        """Evaluate whether a cause should be SUSPECTED or UNRESOLVED.

        Rules:
        - A cause remains SUSPECTED during active investigation.
        - A cause becomes UNRESOLVED only if heavily contradicted.
        - A cause is NEVER automatically promoted to CONFIRMED by evidence
          or check results alone. Confirmation requires explicit technician
          action via DiagnosticEngine.confirm_cause().

        DLK-M3-013 semantic rule:
            Check completed ≠ Check supports cause ≠ Cause confirmed
        """
        if check_results is None:
            check_results = []

        # Check if severely contradicted (score dropped near bottom)
        unresolved_threshold = getattr(SCORING_CONFIG, "low_confidence_threshold", 30.0) / 2.0
        if candidate.score <= unresolved_threshold and len(candidate.contradicting_evidence) > 0:
            return CauseConclusion.UNRESOLVED

        # Causes always remain SUSPECTED during investigation.
        # Confirmation is a separate explicit action by the technician/engineer.
        return CauseConclusion.SUSPECTED

    @classmethod
    def transition_issue_condition(
        cls,
        current_condition: IssueCondition,
        target_condition: IssueCondition,
        verification_passed: bool = False,
        verification_details: str = "",
    ) -> tuple[IssueCondition, str]:
        """Perform a controlled state transition on the dispensing issue condition.

        Args:
            current_condition: The current IssueCondition.
            target_condition: The desired IssueCondition.
            verification_passed: True only if explicit verification (e.g. test shots) succeeded.
            verification_details: Supporting notes regarding the transition.

        Returns:
            Tuple of (new IssueCondition, explanation).

        Raises:
            ValueError: If transition violates legal state machine constraints.
        """
        valid_targets = cls._VALID_ISSUE_TRANSITIONS.get(current_condition, set())
        if target_condition not in valid_targets:
            raise ValueError(
                f"Illegal issue condition transition: {current_condition.value} → {target_condition.value}. "
                f"Valid targets from {current_condition.value} are: {[t.value for t in valid_targets]}."
            )

        if target_condition == IssueCondition.RESOLVED:
            if not verification_passed:
                raise ValueError(
                    "Cannot transition issue condition to RESOLVED without verification. "
                    "A recovery procedure must be verified by nominal test shots or inspection."
                )
            return (
                IssueCondition.RESOLVED,
                f"Issue successfully RESOLVED: {verification_details or 'Verification confirmed nominal dispensing.'}",
            )

        if target_condition == IssueCondition.RECOVERY_PENDING_VERIFICATION:
            return (
                IssueCondition.RECOVERY_PENDING_VERIFICATION,
                f"Corrective action applied. Pending post-repair verification: {verification_details}",
            )

        if target_condition == IssueCondition.RECURRED:
            return (
                IssueCondition.RECURRED,
                f"Defect has RECURRED after previous resolution: {verification_details}",
            )

        return target_condition, f"Issue condition set to {target_condition.value}."


# ===========================================================================
# PHASE 9: Check Result Handling
# ===========================================================================

# Keyword patterns for mapping technician text/details to action outcome keys
_CHECK_OUTCOME_PATTERNS: dict[str, dict[str, list[str]]] = {
    "ACT01": {
        "no_blockage": [
            "no blockage", "no visible blockage", "clear", "clean", "free",
            "not blocked", "unblocked", "normal", "ok", "no_blockage",
        ],
        "blockage_found": [
            "blockage", "blocked", "restricted", "clogged", "buildup",
            "dried material", "obstruction", "blockage_found",
        ],
        "damage_found": [
            "damaged", "damage", "bent", "cracked", "burr", "damage_found",
        ],
    },
    "ACT02": {
        "air_bubbles_found": [
            "bubble", "bubbles", "air", "cavitation", "air_bubbles_found",
        ],
        "material_depleted": [
            "depleted", "empty", "low level", "exhausted", "material_depleted",
        ],
        "separation_found": [
            "separated", "separation", "settled", "phase separation", "separation_found",
        ],
        "material_normal": [
            "normal", "good", "ok", "homogeneous", "fine", "pot life ok", "material_normal",
        ],
    },
    "ACT03": {
        "high_variation": [
            "variation", "high variation", "inconsistent", "unstable", "high_variation",
        ],
        "consistent_but_wrong_size": [
            "wrong size", "undersized", "oversized", "consistent_but_wrong_size",
        ],
        "consistent_and_correct": [
            "consistent", "nominal", "correct", "good", "within spec", "consistent_and_correct",
        ],
    },
    "ACT04": {
        "pressure_unstable": [
            "unstable", "fluctuating", "spikes", "drift", "pressure_unstable",
        ],
        "pressure_low": [
            "low", "dropping", "drop", "insufficient", "pressure_low",
        ],
        "pressure_stable": [
            "stable", "constant", "steady", "nominal", "good", "pressure_stable",
        ],
    },
    "ACT05": {
        "improvement_temporary": [
            "temporary", "temp", "briefly", "short time", "degrades after", "improvement_temporary",
        ],
        "improvement_sustained": [
            "sustained", "permanent", "fixed", "cured", "stable after", "improvement_sustained",
        ],
        "no_improvement": [
            "no improvement", "no change", "same", "worse", "still failing", "no_improvement",
        ],
    },
    "ACT06": {
        "parameters_correct": [
            "correct", "nominal", "match", "verified", "per spec", "parameters_correct",
        ],
        "parameters_deviated": [
            "deviated", "wrong", "mismatch", "incorrect", "altered", "parameters_deviated",
        ],
    },
    "ACT07": {
        "valve_worn": [
            "worn", "wear", "seat", "seal damage", "valve_worn",
        ],
        "valve_leaking": [
            "leaking", "leak", "drip", "drool", "valve_leaking",
        ],
        "valve_normal": [
            "normal", "good", "tight", "passes inspection", "valve_normal",
        ],
    },
    "ACT08": {
        "temperature_high": [
            "high", "elevated", "hot", "above spec", "temperature_high",
        ],
        "temperature_low": [
            "low", "cold", "below spec", "temperature_low",
        ],
        "temperature_normal": [
            "normal", "room", "nominal", "within spec", "temperature_normal",
        ],
    },
    "ACT09": {
        "contamination_found": [
            "contamination", "dirty", "residue", "oil", "moisture", "contamination_found",
        ],
        "surface_clean": [
            "clean", "good", "prepared", "surface_clean",
        ],
    },
    "ACT10": {
        "calibration_drift": [
            "drift", "out of cal", "misaligned", "repeatability fail", "calibration_drift",
        ],
        "calibration_ok": [
            "calibrated", "ok", "passed", "within tolerance", "calibration_ok",
        ],
    },
}

# Domain observation mapping for action outcomes
_ACTION_OUTCOME_TO_OBSERVATION: dict[str, dict[str, tuple[ObservationType, str]]] = {
    "ACT01": {
        "no_blockage": (ObservationType.NOZZLE_CONDITION, "clean"),
        "blockage_found": (ObservationType.NOZZLE_CONDITION, "blocked"),   # DLK-M3-013: "blocked" not "damaged" — blockage ≠ damage
        "damage_found": (ObservationType.NOZZLE_CONDITION, "damaged"),
    },
    "ACT02": {
        "air_bubbles_found": (ObservationType.BUBBLE_PRESENCE, "visible_bubbles"),
        "separation_found": (ObservationType.MATERIAL_STATE, "separated"),
    },
    "ACT03": {
        "high_variation": (ObservationType.DEPOSIT_SIZE, "inconsistent"),
    },
    "ACT04": {
        "pressure_unstable": (ObservationType.PRESSURE, "fluctuating"),
        "pressure_low": (ObservationType.PRESSURE, "low"),               # DLK-M3-013: "low" not "fluctuating" — low ≠ fluctuating
        "pressure_stable": (ObservationType.PRESSURE, "stable"),
    },
    "ACT08": {
        "temperature_high": (ObservationType.TEMPERATURE, "elevated"),
        "temperature_normal": (ObservationType.TEMPERATURE, "normal"),
    },
    "ACT10": {
        "calibration_drift": (ObservationType.EQUIPMENT_CONDITION, "calibration_drift"),  # DLK-M3-013: "calibration_drift" not "worn" — drift ≠ wear
    },
}


class CheckResultHandler:
    """Handles technician troubleshooting check submissions (Phase 9).

    Ensures:
    1. Technician can return COMPLETED, BLOCKED, UNKNOWN, FAILED, NOT_APPLICABLE.
    2. Separately records finding: SUPPORTS, CONTRADICTS, INCONCLUSIVE, UNKNOWN.
    3. BLOCKED checks MUST remain UNKNOWN and produce NO negative findings.
       Specifically, a blocked nozzle check must NEVER be translated into 'No nozzle blockage'.
    4. COMPLETED checks are converted into domain observations and structured evidence.
    """

    @classmethod
    def handle(
        cls,
        check_result: CheckResult,
    ) -> tuple[list[Observation], str]:
        """Process a CheckResult and return any derived observations and a narrative summary.

        Args:
            check_result: The technician's submitted check result.

        Returns:
            Tuple of:
            - list[Observation]: Observations to add to the case.
            - str: Narrative summary of the check processing.
        """
        check_def = get_action_by_id(check_result.check_id)
        if check_def is None:
            raise ValueError(
                f"Unknown check_id '{check_result.check_id}'. "
                f"Must be a supported troubleshooting check from actions.json."
            )
        check_name = check_def.name

        # -------------------------------------------------------------------
        # Rule 1: Non-completed checks (BLOCKED, FAILED, UNKNOWN, etc.)
        # MUST remain UNKNOWN and NEVER produce contradictory/supporting evidence.
        # -------------------------------------------------------------------
        non_executing = {
            CheckExecutionStatus.BLOCKED,
            CheckExecutionStatus.FAILED,
            CheckExecutionStatus.UNKNOWN,
            CheckExecutionStatus.NOT_APPLICABLE,
            CheckExecutionStatus.SKIPPED,
        }

        if check_result.execution_status in non_executing:
            # Force finding to UNKNOWN as explicitly required by Phase 9
            check_result.finding = CheckFinding.UNKNOWN

            status_str = check_result.execution_status.value
            reason = check_result.finding_details or "Check could not be performed."

            summary = (
                f"Check '{check_name}' ({check_result.check_id}) was {status_str}. "
                f"Finding remains UNKNOWN. Reason: {reason}. "
                f"No evidence or cause scores were modified."
            )
            # ZERO observations generated. Blocked checks must not alter hypotheses.
            return [], summary

        # -------------------------------------------------------------------
        # Rule 2: COMPLETED check with UNKNOWN / INCONCLUSIVE finding
        # -------------------------------------------------------------------
        if check_result.finding in (
            CheckFinding.UNKNOWN,
            CheckFinding.INCONCLUSIVE,
            CheckFinding.NOT_APPLICABLE,
        ):
            summary = (
                f"Check '{check_name}' ({check_result.check_id}) was COMPLETED, "
                f"but finding was {check_result.finding.value}."
            )
            return [], summary

        # -------------------------------------------------------------------
        # Rule 3: COMPLETED check with SUPPORTS or CONTRADICTS finding
        # -------------------------------------------------------------------
        outcome_key = cls._resolve_outcome_key(
            check_result.check_id,
            check_result.finding,
            check_result.finding_details,
            check_result.outcome,
            check_def,
        )

        observations: list[Observation] = []
        details_text = check_result.finding_details or f"{check_name}: {check_result.finding.value}"

        # 3a. Add direct check_result observation (matches action rules in knowledge base)
        if outcome_key:
            observations.append(
                Observation(
                    observation_type=ObservationType.CHECK_RESULT,
                    value=f"{check_result.check_id}:{outcome_key}",
                    original_text=details_text,
                    statement_type=StatementType.USER_OBSERVATION,
                    source=check_result.source,
                )
            )

        # 3b. Add mapped domain observation (e.g. nozzle_condition=clean for R042)
        domain_obs = cls._map_to_domain_observation(
            check_result.check_id,
            outcome_key,
            check_result.finding,
            details_text,
            check_result.source,
        )
        if domain_obs:
            observations.append(domain_obs)

        finding_str = check_result.finding.value
        summary = (
            f"Check '{check_name}' ({check_result.check_id}) COMPLETED with finding {finding_str} "
            f"(outcome: '{outcome_key or 'custom'}'). Details: {details_text}."
        )

        return observations, summary

    @classmethod
    def _resolve_outcome_key(
        cls,
        check_id: str,
        finding: CheckFinding,
        details: str | None,
        outcome: str | None = None,
        check_def: Any = None,
    ) -> str | None:
        """Resolve and validate the outcome identifier based on check ID, finding, details, and outcome."""
        if check_def is None:
            check_def = get_action_by_id(check_id)

        allowed_outcomes: set[str] = set()
        if check_def and hasattr(check_def, "evidence_mapping"):
            allowed_outcomes = set(check_def.evidence_mapping.keys())

        # 1. Explicit outcome passed on CheckResult
        if outcome:
            outcome_norm = outcome.strip().lower()
            if allowed_outcomes and outcome_norm not in allowed_outcomes:
                raise ValueError(
                    f"Invalid outcome '{outcome}' for check '{check_id}'. "
                    f"Allowed outcomes are: {sorted(allowed_outcomes)}."
                )
            return outcome_norm

        patterns = _CHECK_OUTCOME_PATTERNS.get(check_id, {})
        details_clean = (details or "").strip()
        details_lower = details_clean.lower()

        # 2. Check if details string is an invalid outcome identifier
        if details_lower and (" " not in details_clean) and ("_" in details_clean or details_clean.isupper()):
            if allowed_outcomes and details_lower not in allowed_outcomes:
                raise ValueError(
                    f"Invalid outcome '{details}' for check '{check_id}'. "
                    f"Allowed outcomes are: {sorted(allowed_outcomes)}."
                )

        # 3. Match against known patterns
        if details_lower:
            for outcome_cand, phrases in patterns.items():
                for phrase in phrases:
                    if phrase in details_lower:
                        return outcome_cand

            # Dynamic match against allowed outcomes directly from definition
            if allowed_outcomes:
                for cand in allowed_outcomes:
                    if cand in details_lower or cand.replace("_", " ") in details_lower:
                        return cand

        # 4. Canonical finding defaults per check with dynamic knowledge-driven fallback
        defaults_contradicts = {
            "ACT01": "no_blockage",
            "ACT02": "material_normal",
            "ACT03": "consistent_and_correct",
            "ACT04": "pressure_stable",
            "ACT05": "no_improvement",
            "ACT06": "parameters_correct",
            "ACT07": "valve_normal",
            "ACT08": "temperature_normal",
            "ACT09": "surface_clean",
            "ACT10": "calibration_ok",
        }
        defaults_supports = {
            "ACT01": "blockage_found",
            "ACT02": "air_bubbles_found",
            "ACT03": "high_variation",
            "ACT04": "pressure_unstable",
            "ACT05": "improvement_temporary",
            "ACT06": "parameters_deviated",
            "ACT07": "valve_worn",
            "ACT08": "temperature_high",
            "ACT09": "contamination_found",
            "ACT10": "calibration_drift",
        }

        if finding == CheckFinding.CONTRADICTS:
            if check_id in defaults_contradicts:
                return defaults_contradicts[check_id]
            if check_def and hasattr(check_def, "evidence_mapping"):
                for outcome_cand, causes_map in check_def.evidence_mapping.items():
                    for spec in causes_map.values():
                        if str(spec.get("relation", "")).upper() == "CONTRADICTS":
                            return outcome_cand

        if finding == CheckFinding.SUPPORTS:
            if check_id in defaults_supports:
                return defaults_supports[check_id]
            if check_def and hasattr(check_def, "evidence_mapping"):
                for outcome_cand, causes_map in check_def.evidence_mapping.items():
                    for spec in causes_map.values():
                        if str(spec.get("relation", "")).upper() == "SUPPORTS":
                            return outcome_cand

        return None

    @classmethod
    def _map_to_domain_observation(
        cls,
        check_id: str,
        outcome_key: str | None,
        finding: CheckFinding,
        details_text: str,
        source: EvidenceSource,
    ) -> Observation | None:
        """Map action outcome to a canonical domain observation (e.g. nozzle_condition=clean)."""
        if outcome_key and check_id in _ACTION_OUTCOME_TO_OBSERVATION:
            mapping = _ACTION_OUTCOME_TO_OBSERVATION[check_id].get(outcome_key)
            if mapping:
                obs_type, obs_value = mapping
                return Observation(
                    observation_type=obs_type,
                    value=obs_value,
                    original_text=details_text,
                    statement_type=StatementType.USER_OBSERVATION,
                    source=source,
                )

        return None


# ===========================================================================
# Question Answer Handling
# ===========================================================================

from app.services.diagnosis.question_answer_handler import (
    QuestionAnswerHandler,
    QuestionAnswerResult,
)


# ===========================================================================
# PHASE 10 & 13: Diagnostic Engine Orchestrator
# ===========================================================================

class DiagnosticEngine:
    """The master orchestrator coordinating the entire diagnostic cycle.

    Responsibilities:
    - Receive StructuredCase or DiagnosisRequest.
    - Extract symptoms from natural-language descriptions when needed.
    - Identify defect.
    - Load applicable candidate causes.
    - Evaluate evidence using EvidenceEngine.
    - Deterministically rank causes using CauseRanker.
    - Phase 9: Process troubleshooting check results.
    - Phase 10: Re-rank causes after new evidence, preserving revision history.
    - Phase 11: Enforce state independence across the 4 dimensions.
    - Select next discriminating question using QuestionEngine.
    - Select next troubleshooting check using ActionPlanner.
    - Produce inspectable score explanations and revision change logs.
    """

    def __init__(
        self,
        symptom_extractor: SymptomExtractor | None = None,
        evidence_engine: EvidenceEngine | None = None,
        cause_ranker: CauseRanker | None = None,
        question_engine: QuestionEngine | None = None,
        action_planner: ActionPlanner | None = None,
    ) -> None:
        self.extractor = symptom_extractor or SymptomExtractor()
        self.evidence_engine = evidence_engine or EvidenceEngine()
        self.ranker = cause_ranker or CauseRanker(self.evidence_engine)
        self.question_engine = question_engine or QuestionEngine()
        self.action_planner = action_planner or ActionPlanner()

    # -----------------------------------------------------------------------
    # Primary API: diagnose
    # -----------------------------------------------------------------------

    def diagnose(
        self,
        case_or_request: StructuredCase | DiagnosisRequest,
    ) -> DiagnosisResult:
        """Execute a full diagnostic evaluation cycle on a case.

        Args:
            case_or_request: A StructuredCase or a DiagnosisRequest.

        Returns:
            DiagnosisResult with ranked causes, next question/check, explanation,
            and updated analysis revision.
        """
        # 1. Prepare structured case
        case = self.prepare_case(case_or_request)
        warnings: list[str] = []

        # 2. Extract symptoms if needed
        if not case.observations and case.description:
            extraction = self.extractor.extract(case.description)
            case.observations.extend(extraction.observations)
            warnings.extend(extraction.warnings)

        # 3. Identify defect
        defect_code = case.defect_code
        defect_name = case.defect_name

        if not defect_code:
            defect_match = identify_defect(case.observations)
            if defect_match:
                defect_code = defect_match.code
                defect_name = defect_match.name
                case.defect_code = defect_code
                case.defect_name = defect_name
            else:
                warnings.append("Could not identify defect with high confidence from current observations.")
                return DiagnosisResult(
                    case_id=case.case_id,
                    defect=None,
                    defect_name=None,
                    ranked_causes=[],
                    next_question=None,
                    next_check=None,
                    explanation="No defect could be identified from the provided observations.",
                    analysis_revision=None,
                    issue_condition=case.issue_condition,
                    warnings=warnings,
                )

        # 4. Evaluate evidence and rank causes (deterministic)
        ranking = self.ranker.rank(case.observations, defect_code)

        # 5. Phase 11: Evaluate cause conclusions independently of issue condition
        confirmed_ids = set(getattr(case, "confirmed_causes", []))
        if case.analysis_revisions:
            for c in case.analysis_revisions[-1].ranked_causes:
                if c.conclusion == CauseConclusion.CONFIRMED:
                    confirmed_ids.add(c.cause_id)

        for cause in ranking.ranked_causes:
            if cause.cause_id in confirmed_ids:
                cause.conclusion = CauseConclusion.CONFIRMED
            else:
                cause.conclusion = StateManager.evaluate_cause_conclusion(
                    cause, case.previous_check_results
                )


        # 6. Phase 10: Revision management (preserve history, generate new revision)
        previous_revision = (
            case.analysis_revisions[-1] if case.analysis_revisions else None
        )
        new_rev_number = len(case.analysis_revisions) + 1

        new_revision = AnalysisRevision(
            revision_number=new_rev_number,
            timestamp=_utc_now(),
            defect_code=defect_code,
            ranked_causes=ranking.ranked_causes,
        )

        if previous_revision and previous_revision.ranked_causes:
            changes = self._detect_revision_changes(
                previous_revision.ranked_causes,
                ranking.ranked_causes,
            )
            new_revision.changes_from_previous = changes
            new_revision.new_evidence_summary = (
                f"Updated with {len(case.observations)} observations and "
                f"{len(case.previous_check_results)} check results."
            )
        else:
            new_revision.new_evidence_summary = "Initial diagnostic assessment."

        # Append new revision to history (preserves all previous revisions)
        case.analysis_revisions.append(new_revision)

        # 7. Select next question (with stopping conditions)
        q_result = self.question_engine.select_next_question(
            ranked_causes=ranking.ranked_causes,
            previous_answers=case.previous_answers,
            defect_code=defect_code,
        )
        next_question = q_result.selected_question

        # 8. Select next check (respects effort, prior attempts, and blocked checks)
        a_result = self.action_planner.select_next_action(
            ranked_causes=ranking.ranked_causes,
            previous_check_results=case.previous_check_results,
            defect_code=defect_code,
        )
        next_check = a_result.selected_check

        # 9. Generate explanation
        explanation = self._build_explanation(
            case=case,
            ranking=ranking,
            current_revision=new_revision,
            next_question=next_question,
            next_check=next_check,
        )

        return DiagnosisResult(
            case_id=case.case_id,
            defect=defect_code,
            defect_name=defect_name,
            ranked_causes=ranking.ranked_causes,
            next_question=next_question,
            next_check=next_check,
            explanation=explanation,
            analysis_revision=new_revision,
            issue_condition=case.issue_condition,
            warnings=warnings,
        )

    # -----------------------------------------------------------------------
    # Check Result Handling (Phase 9 & 10 Integration)
    # -----------------------------------------------------------------------

    def submit_check_result(
        self,
        case: StructuredCase,
        check_result: CheckResult,
    ) -> tuple[StructuredCase, DiagnosisResult]:
        """Submit a completed or blocked check result from a technician.

        Enforces:
        1. Non-completed checks (BLOCKED, FAILED, etc.) remain UNKNOWN and do not alter hypotheses.
        2. Completed checks convert to observations.
        3. All prior revisions are preserved.
        4. Causes are re-ranked, creating Revision N+1 with change explanation.
        5. State dimensions remain strictly independent.
        """
        # Record check result in case history
        case.previous_check_results.append(check_result)

        # Process check result (Phase 9)
        new_obs, summary = CheckResultHandler.handle(check_result)

        # Add any new observations (avoiding duplicates by id)
        existing_ids = {o.id for o in case.observations}
        for obs in new_obs:
            if obs.id not in existing_ids:
                case.observations.append(obs)
                existing_ids.add(obs.id)

        # Re-diagnose with updated case
        result = self.diagnose(case)

        # Update the latest revision summary with the check result details
        if case.analysis_revisions:
            case.analysis_revisions[-1].new_evidence_summary = summary

        return case, result

    # -----------------------------------------------------------------------
    # Explicit Cause Confirmation (DLK-M3-013)
    # -----------------------------------------------------------------------

    def confirm_cause(
        self,
        case: StructuredCase,
        cause_id: str,
        confirmed_by: str = "technician",
        confirmation_details: str = "",
    ) -> tuple[StructuredCase, DiagnosisResult]:
        """Explicitly confirm a cause as the root cause.

        This is a SEPARATE operation from check-result handling.
        A supporting check result increases evidence but does NOT
        automatically confirm a cause. Only this method transitions
        a cause to CONFIRMED.

        DLK-M3-013 semantic rule:
            Check completed ≠ Check supports cause ≠ Cause confirmed

        Args:
            case: The structured case.
            cause_id: The cause_id to confirm.
            confirmed_by: Who confirmed (e.g. "technician", "engineer").
            confirmation_details: Supporting notes for the confirmation.

        Returns:
            Updated (case, DiagnosisResult) with the cause set to CONFIRMED.

        Raises:
            ValueError: If the cause_id is not found in the current ranking.
        """
        # Re-diagnose to get current state
        result = self.diagnose(case)

        # Find and confirm the specified cause
        found = False
        for cause in result.ranked_causes:
            if cause.cause_id == cause_id:
                cause.conclusion = CauseConclusion.CONFIRMED
                found = True
                break

        if not found:
            raise ValueError(
                f"Cannot confirm cause '{cause_id}': not found in current ranked causes. "
                f"Available causes: {[c.cause_id for c in result.ranked_causes]}"
            )

        # Also update the cause in the latest revision
        if case.analysis_revisions:
            for cause in case.analysis_revisions[-1].ranked_causes:
                if cause.cause_id == cause_id:
                    cause.conclusion = CauseConclusion.CONFIRMED
                    break

        # Track confirmed cause on case for persistent state
        if hasattr(case, "confirmed_causes") and cause_id not in case.confirmed_causes:
            case.confirmed_causes.append(cause_id)

        # Update latest revision summary with confirmation note
        if case.analysis_revisions:
            cause_name = next((c.cause_name for c in result.ranked_causes if c.cause_id == cause_id), cause_id)
            summary_note = f"Cause '{cause_name}' ({cause_id}) explicitly confirmed by {confirmed_by}."
            if confirmation_details:
                summary_note += f" Details: {confirmation_details}"
            case.analysis_revisions[-1].new_evidence_summary = summary_note

        return case, result



    # -----------------------------------------------------------------------
    # Question Answer Handling (Phase 10 Integration)
    # -----------------------------------------------------------------------

    def submit_question_answer(
        self,
        case: StructuredCase,
        answer: QuestionAnswer,
    ) -> tuple[StructuredCase, DiagnosisResult]:
        """Submit an answer to a diagnostic question and trigger re-ranking."""
        case.previous_answers.append(answer)

        # Convert answer to observations
        new_obs = QuestionAnswerHandler.handle(answer)
        existing_ids = {o.id for o in case.observations}
        for obs in new_obs:
            if obs.id not in existing_ids:
                case.observations.append(obs)
                existing_ids.add(obs.id)

        result = self.diagnose(case)

        # Update the latest revision summary with the question answer details
        if case.analysis_revisions:
            case.analysis_revisions[-1].new_evidence_summary = (
                f"Question {answer.question_id} answered with '{answer.answer_value}'"
            )

        return case, result

    # -----------------------------------------------------------------------
    # Preparation & Helpers
    # -----------------------------------------------------------------------

    def prepare_case(
        self,
        case_or_request: StructuredCase | DiagnosisRequest,
    ) -> StructuredCase:
        """Convert a DiagnosisRequest or validate a StructuredCase."""
        if isinstance(case_or_request, StructuredCase):
            return case_or_request

        # Convert DiagnosisRequest -> StructuredCase
        case_id = case_or_request.case_id or str(uuid.uuid4())
        return StructuredCase(
            case_id=case_id,
            description=case_or_request.description,
            material=case_or_request.material,
            method=case_or_request.method,
            machine_context=case_or_request.machine_context,
            defect_code=case_or_request.defect_code,
            observations=list(case_or_request.observations),
            previous_answers=list(case_or_request.previous_answers),
            previous_check_results=list(case_or_request.previous_check_results),
            analysis_revisions=[],
            issue_condition=IssueCondition.UNRESOLVED,
            created_at=_utc_now(),
        )

    def _detect_revision_changes(
        self,
        previous: list[CandidateCause],
        current: list[CandidateCause],
    ) -> list[str]:
        """Compare two ranking revisions and describe what changed."""
        changes: list[str] = []
        prev_scores = {c.cause_id: c.score for c in previous}
        prev_order = [c.cause_id for c in previous]
        curr_order = [c.cause_id for c in current]

        # Score changes
        for c in current:
            old_score = prev_scores.get(c.cause_id)
            if old_score is None:
                changes.append(f"{c.cause_name} is newly ranked at {c.score:.0f}/100.")
            elif abs(c.score - old_score) >= 1.0:
                direction = "increased" if c.score > old_score else "decreased"
                diff = abs(c.score - old_score)
                changes.append(
                    f"{c.cause_name} {direction} from {old_score:.0f} to {c.score:.0f} "
                    f"({'+' if direction == 'increased' else '-'}{diff:.0f} pts)."
                )

        # Top cause change
        if prev_order and curr_order and prev_order[0] != curr_order[0]:
            new_top = current[0]
            changes.append(f"{new_top.cause_name} is now the top-ranked cause.")

        # Order flips among top causes
        prev_pos = {cid: idx for idx, cid in enumerate(prev_order)}
        for idx, c in enumerate(current[:3]):
            old_idx = prev_pos.get(c.cause_id)
            if old_idx is not None and old_idx != idx:
                dir_str = "up" if idx < old_idx else "down"
                changes.append(
                    f"{c.cause_name} moved {dir_str} to rank #{idx + 1} (was #{old_idx + 1})."
                )

        return changes

    def _build_explanation(
        self,
        case: StructuredCase,
        ranking: RankingResult,
        current_revision: AnalysisRevision,
        next_question: Question | None,
        next_check: TroubleshootingCheck | None,
    ) -> str:
        """Build a comprehensive human-readable explanation of current state and changes."""
        lines: list[str] = []
        top_cause = ranking.top_cause

        # 1. Top hypothesis and confirmed causes
        confirmed_causes = [c for c in ranking.ranked_causes if c.conclusion == CauseConclusion.CONFIRMED]
        if confirmed_causes:
            names = ", ".join(f"'{c.cause_name}'" for c in confirmed_causes)
            lines.append(f"Root cause confirmed: {names} (explicitly confirmed by technician).")

        if top_cause:
            lines.append(
                f"{top_cause.cause_name} is currently the highest-supported hypothesis "
                f"with evidence support {top_cause.score:.0f}/100."
            )
            if top_cause.supporting_evidence:
                supp_count = len(top_cause.supporting_evidence)
                lines.append(f"It is supported by {supp_count} observation(s).")
            if top_cause.contradicting_evidence:
                lines.append(
                    f"Warning: {len(top_cause.contradicting_evidence)} contradicting evidence item(s) noted."
                )
        else:
            lines.append("No candidate causes currently evaluated.")

        # 2. Changes from previous revision (Phase 10)
        if current_revision.changes_from_previous:
            lines.append("\nChanges since last revision:")
            for change in current_revision.changes_from_previous:
                lines.append(f"  • {change}")

        # 3. Next recommendation
        if next_check:
            lines.append(
                f"\nRecommended Action: Run troubleshooting check '{next_check.name}' "
                f"({next_check.check_id}, effort: {next_check.effort_level})."
            )
        elif next_question:
            lines.append(
                f"\nRecommended Next Step: Answer question '{next_question.text}'"
            )

        return "\n".join(lines)


# Alias for backwards-compatibility with task verification contracts
DiagnosisEngine = DiagnosticEngine
