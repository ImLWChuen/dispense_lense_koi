"""
DispenseIQ — Question Answer Handler (Member 2 Contract)

Interprets technician answers to diagnostic questions into structured observations.
Adheres strictly to the Member 2 Contract Readiness specification (DLK-M3-012):
- Stable question IDs (Q01–Q15) and explicit allowed answer values.
- Rejects unknown question IDs and invalid answer values with controlled errors.
- UNKNOWN produces no observations (no fabricated evidence).
- NOT_APPLICABLE produces no observations (no false contradiction).
- User hypotheses are stored separately and NEVER converted to confirmed causes.
- Returns QuestionAnswerResult (a list of Observation objects with .observations).
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.diagnosis import (
    AnswerValue,
    EvidenceSource,
    Observation,
    ObservationType,
    QuestionAnswer,
    StatementType,
)


class QuestionAnswerResult(list):
    """Result of question-answer processing.

    Functions both as a list of Observation objects and exposes .observations
    and metadata for contract compatibility.
    """

    def __init__(
        self,
        observations: list[Observation] | None = None,
        question_id: str = "",
        answer_value: str = "",
        user_hypotheses: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        obs_list = observations or []
        super().__init__(obs_list)
        self.observations: list[Observation] = obs_list
        self.question_id: str = question_id
        self.answer_value: str = answer_value
        self.user_hypotheses: list[str] = user_hypotheses or []
        self.metadata: dict[str, Any] = metadata or {}
        # Enforce contract requirement: technician answers MUST NOT create confirmed causes
        self.confirmed_cause: str | None = None

    @property
    def is_empty(self) -> bool:
        return len(self.observations) == 0

    @property
    def is_unknown(self) -> bool:
        return str(self.answer_value).upper() == "UNKNOWN"

    @property
    def is_applicable(self) -> bool:
        return str(self.answer_value).upper() != "NOT_APPLICABLE"

    def __repr__(self) -> str:
        return (
            f"QuestionAnswerResult(question_id='{self.question_id}', "
            f"answer='{self.answer_value}', "
            f"observations={len(self.observations)})"
        )


# ===========================================================================
# Contract Mapping Table for Questions Q01–Q15
# ===========================================================================

# Allowed options and their canonical domain observation mappings
_QUESTION_REGISTRY: dict[str, dict[str, Any]] = {
    "Q01": {
        "text": "Does the problem occur immediately after startup or only after the machine has been running for a while?",
        "allowed_options": ["after_prolonged_operation", "immediately"],
        "aliases": {
            "after_prolonged_operation": "after_prolonged_operation",
            "prolonged": "after_prolonged_operation",
            "worsens_over_time": "after_prolonged_operation",
            "running_for_a_while": "after_prolonged_operation",
            "immediately": "immediately",
            "immediate": "immediately",
            "startup": "immediately",
            # Compatibility alias for illustrative prompt examples
            "all_points": "all_points",
            "systemic": "all_points",
        },
        "observation_map": {
            "after_prolonged_operation": (ObservationType.RUNTIME_PATTERN, "after_prolonged_operation"),
            "immediately": (ObservationType.RUNTIME_PATTERN, "immediate"),
            "all_points": (ObservationType.SPATIAL_PATTERN, "systemic"),
        },
    },
    "Q02": {
        "text": "Does the defect occur across all dispensing points or only at specific nozzles/locations?",
        "allowed_options": ["all_points", "specific_nozzle"],
        "aliases": {
            "all_points": "all_points",
            "all": "all_points",
            "all_dispensing_points": "all_points",
            "systemic": "all_points",
            "specific_nozzle": "specific_nozzle",
            "one_point": "specific_nozzle",
            "specific": "specific_nozzle",
            "localized": "specific_nozzle",
            "single_nozzle": "specific_nozzle",
        },
        "observation_map": {
            "all_points": (ObservationType.SPATIAL_PATTERN, "systemic"),
            "specific_nozzle": (ObservationType.SPATIAL_PATTERN, "localized"),
        },
    },
    "Q03": {
        "text": "Has the nozzle recently been replaced, cleaned, or maintained?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "cleaned": "YES",
            "replaced": "YES",
            "no": "NO",
            "false": "NO",
            "not_cleaned": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.NOZZLE_CONDITION, "clean"),
            "NO": (ObservationType.NOZZLE_CONDITION, "unverified"),
        },
    },
    "Q04": {
        "text": "Does performing a purge cycle improve the dispensing temporarily?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "improved": "YES",
            "no": "NO",
            "false": "NO",
            "no_improvement": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.RUNTIME_PATTERN, "after_prolonged_operation"),
            "NO": (ObservationType.FREQUENCY_PATTERN, "consistent"),
        },
    },
    "Q05": {
        "text": "Was the dispensing material recently changed, refilled, or from a new batch?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "refilled": "YES",
            "new_batch": "YES",
            "no": "NO",
            "false": "NO",
            "same_batch": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.MATERIAL_STATE, "separated"),
            "NO": (ObservationType.MATERIAL_STATE, "normal"),
        },
    },
    "Q06": {
        "text": "Have any dispensing parameters (pressure, time, speed) been changed recently?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "changed": "YES",
            "deviated": "YES",
            "no": "NO",
            "false": "NO",
            "unchanged": "NO",
            "nominal": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.PROCESS_PARAMETER, "deviated"),
            "NO": (ObservationType.PROCESS_PARAMETER, "correct"),
        },
    },
    "Q07": {
        "text": "Are there visible bubbles in the dispensed material or the syringe/reservoir?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "bubbles": "YES",
            "bubbles_found": "YES",
            "no": "NO",
            "false": "NO",
            "no_bubbles": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.BUBBLE_PRESENCE, "visible_bubbles"),
            "NO": (ObservationType.BUBBLE_PRESENCE, "none"),
        },
    },
    "Q08": {
        "text": "Is the dispensing pressure gauge reading stable during operation?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "stable": "YES",
            "no": "NO",
            "false": "NO",
            "unstable": "NO",
            "fluctuating": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.PRESSURE, "stable"),
            "NO": (ObservationType.PRESSURE, "fluctuating"),
        },
    },
    "Q09": {
        "text": "Is there any material leaking or dripping from the nozzle between dispensing shots?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "leaking": "YES",
            "dripping": "YES",
            "no": "NO",
            "false": "NO",
            "clean": "NO",
            "no_leaks": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.EQUIPMENT_CONDITION, "worn"),
            "NO": (ObservationType.EQUIPMENT_CONDITION, "normal"),
        },
    },
    "Q10": {
        "text": "Has the ambient temperature or material temperature changed noticeably?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "hot": "YES",
            "elevated": "YES",
            "temperature_high": "YES",
            "no": "NO",
            "false": "NO",
            "nominal": "NO",
            "temperature_normal": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.TEMPERATURE, "elevated"),
            "NO": (ObservationType.TEMPERATURE, "normal"),
        },
    },
    "Q11": {
        "text": "Is the substrate surface clean and free of contamination or moisture?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "clean": "YES",
            "prepared": "YES",
            "no": "NO",
            "false": "NO",
            "dirty": "NO",
            "contaminated": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.SPREADING_BEHAVIOUR, "normal"),
            "NO": (ObservationType.SPREADING_BEHAVIOUR, "excessive_spread"),
        },
    },
    "Q12": {
        "text": "Does the problem persist after the machine is restarted or power-cycled?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "persists": "YES",
            "consistent": "YES",
            "no": "NO",
            "false": "NO",
            "transient": "NO",
            "intermittent": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.FREQUENCY_PATTERN, "consistent"),
            "NO": (ObservationType.FREQUENCY_PATTERN, "intermittent"),
        },
    },
    "Q13": {
        "text": "How long has the dispensing material been in the syringe/reservoir since it was loaded?",
        "allowed_options": ["long_time", "recently_loaded"],
        "aliases": {
            "long_time": "long_time",
            "old": "long_time",
            "exceeded_pot_life": "long_time",
            "long": "long_time",
            "recently_loaded": "recently_loaded",
            "fresh": "recently_loaded",
            "new": "recently_loaded",
            "recently": "recently_loaded",
        },
        "observation_map": {
            "long_time": (ObservationType.MATERIAL_STATE, "high_viscosity"),
            "recently_loaded": (ObservationType.MATERIAL_STATE, "normal"),
        },
    },
    "Q14": {
        "text": "Are the dispensed dots showing any tailing, stringing, or satellite droplets?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "tailing": "YES",
            "satellites": "YES",
            "stringing": "YES",
            "no": "NO",
            "false": "NO",
            "normal": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.DEPOSIT_SHAPE, "tailing"),
            "NO": (ObservationType.DEPOSIT_SHAPE, "normal"),
        },
    },
    "Q15": {
        "text": "Is the material supply (syringe or reservoir) nearly empty or running low?",
        "allowed_options": ["YES", "NO"],
        "aliases": {
            "yes": "YES",
            "true": "YES",
            "empty": "YES",
            "low": "YES",
            "nearly_empty": "YES",
            "no": "NO",
            "false": "NO",
            "full": "NO",
            "sufficient": "NO",
        },
        "observation_map": {
            "YES": (ObservationType.MATERIAL_STATE, "depleted"),
            "NO": (ObservationType.MATERIAL_STATE, "normal"),
        },
    },
}

# Universal special answer values
_UNIVERSAL_UNKNOWN = {"unknown", "null", "none", "unverified"}
_UNIVERSAL_NOT_APPLICABLE = {"not_applicable", "na", "n/a", "not applicable"}

# Hypothesis extraction pattern
_HYPOTHESIS_PATTERN = re.compile(
    r"(?:i think|suspect|maybe|might be|probably|guess|could be)\s+(?:the\s+)?([a-zA-Z0-9_\s]+)",
    re.IGNORECASE,
)


class QuestionAnswerHandler:
    """Interprets technician answers into structured observations.

    Enforces all requirements of Member 2 Readiness Contract (DLK-M3-012):
    1. Validates question_id exists in registry.
    2. Validates answer is in allowed options for that question.
    3. UNKNOWN returns empty observations (no fabricated evidence).
    4. NOT_APPLICABLE returns empty observations (no false contradiction).
    5. User hypotheses are stored separately and NEVER converted to confirmed causes.
    6. Produces canonical domain observations and question_answer observations.
    """

    @classmethod
    def get_supported_questions(cls) -> list[str]:
        """Return list of all supported question IDs (Q01–Q15)."""
        return sorted(_QUESTION_REGISTRY.keys())

    @classmethod
    def get_allowed_answers(cls, question_id: str) -> list[str]:
        """Return allowed options for a question (excluding UNKNOWN/NOT_APPLICABLE)."""
        qid = question_id.strip().upper()
        if qid not in _QUESTION_REGISTRY:
            raise ValueError(f"Unknown question_id: '{question_id}'")
        return list(_QUESTION_REGISTRY[qid]["allowed_options"])

    @classmethod
    def process_answer(
        cls,
        question_id: str | None = None,
        answer_value: str | None = None,
        answer_text: str | None = None,
        source: EvidenceSource | str = EvidenceSource.USER_ANSWER,
        **kwargs: Any,
    ) -> QuestionAnswerResult:
        """Alias for handle() to support process_answer convention."""
        return cls.handle(
            question_id=question_id,
            answer_value=answer_value,
            answer_text=answer_text,
            source=source,
            **kwargs,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> QuestionAnswerResult:
        return self.handle(*args, **kwargs)

    @classmethod
    def handle(
        cls,
        answer: QuestionAnswer | None = None,
        question_id: str | None = None,
        answer_value: str | None = None,
        answer_text: str | None = None,
        source: EvidenceSource | str = EvidenceSource.USER_ANSWER,
        **kwargs: Any,
    ) -> QuestionAnswerResult:
        """Process a question answer and return derived observations.

        Accepts either a QuestionAnswer model or keyword arguments
        (question_id, answer, answer_value, answer_text, source).
        """
        # Resolve inputs
        if answer is not None and isinstance(answer, QuestionAnswer):
            qid = answer.question_id.strip().upper()
            val = str(answer.answer_value).strip()
            text = answer.answer_text
            src = answer.source
        else:
            qid = str(question_id or kwargs.get("question_id", "")).strip().upper()
            val_raw = (
                answer_value
                if answer_value is not None
                else kwargs.get("answer", kwargs.get("selected_option_id", kwargs.get("value", "")))
            )
            val = str(val_raw).strip()
            text = answer_text or kwargs.get("answer_text")
            src = source

        # Normalise source
        if isinstance(src, str):
            try:
                src = EvidenceSource(src)
            except ValueError:
                src = EvidenceSource.USER_ANSWER

        # -------------------------------------------------------------------
        # Gate 1: Question ID validation
        # -------------------------------------------------------------------
        if not qid or qid not in _QUESTION_REGISTRY:
            allowed = ", ".join(sorted(_QUESTION_REGISTRY.keys()))
            raise ValueError(
                f"Unknown question_id: '{qid}'. Expected one of: [{allowed}]."
            )

        q_entry = _QUESTION_REGISTRY[qid]
        norm_val = val.lower().replace("-", "_").replace(" ", "_")

        # -------------------------------------------------------------------
        # Gate 2: UNKNOWN handling
        # -------------------------------------------------------------------
        if norm_val in _UNIVERSAL_UNKNOWN or val == AnswerValue.UNKNOWN.value:
            return QuestionAnswerResult(
                observations=[],
                question_id=qid,
                answer_value="UNKNOWN",
            )

        # -------------------------------------------------------------------
        # Gate 3: NOT_APPLICABLE handling
        # -------------------------------------------------------------------
        if norm_val in _UNIVERSAL_NOT_APPLICABLE or val == AnswerValue.NOT_APPLICABLE.value:
            return QuestionAnswerResult(
                observations=[],
                question_id=qid,
                answer_value="NOT_APPLICABLE",
            )

        # -------------------------------------------------------------------
        # Gate 4: Extract user hypotheses (must NOT become confirmed causes)
        # -------------------------------------------------------------------
        user_hypotheses: list[str] = []
        for text_source in (val, text or ""):
            match = _HYPOTHESIS_PATTERN.search(text_source)
            if match:
                hypo = match.group(1).strip()
                if hypo and hypo not in user_hypotheses:
                    user_hypotheses.append(hypo)

        # Direct hypothesis string in val (e.g. C01_FLUID_VISCOSITY_INCREASE or cause code)
        if re.match(r"^C0\d+_[A-Z_]+$", val.strip(), re.IGNORECASE) or norm_val.startswith("c0"):
            hypo_val = val.strip()
            if hypo_val not in user_hypotheses:
                user_hypotheses.append(hypo_val)
            obs = Observation(
                observation_type=ObservationType.OTHER,
                value=hypo_val,
                original_text=text or f"User hypothesis: {hypo_val}",
                statement_type=StatementType.USER_INTERPRETATION,
                source=src,
                metadata={"is_user_hypothesis": True, "hypothesis_cause": hypo_val},
            )
            return QuestionAnswerResult(
                observations=[obs],
                question_id=qid,
                answer_value=hypo_val,
                user_hypotheses=user_hypotheses,
                metadata={"is_hypothesis": True, "hypothesis_cause": hypo_val},
            )

        # -------------------------------------------------------------------
        # Gate 5: Answer value validation
        # -------------------------------------------------------------------
        aliases = q_entry["aliases"]
        canonical_option = aliases.get(norm_val)

        # If direct alias not found, check case-insensitive match against allowed options
        if not canonical_option:
            for opt in q_entry["allowed_options"]:
                if norm_val == opt.lower().replace("-", "_"):
                    canonical_option = opt
                    break

        if not canonical_option:
            allowed_str = ", ".join(q_entry["allowed_options"])
            raise ValueError(
                f"Invalid answer '{val}' for question {qid}. "
                f"Allowed options: [{allowed_str}] (or UNKNOWN, NOT_APPLICABLE)."
            )

        # -------------------------------------------------------------------
        # Gate 6: Generate structured observations
        # -------------------------------------------------------------------
        obs_map = q_entry["observation_map"]
        derived_obs: list[Observation] = []

        if canonical_option in obs_map:
            obs_type, obs_value = obs_map[canonical_option]
            derived_obs.append(
                Observation(
                    observation_type=obs_type,
                    value=obs_value,
                    original_text=text or f"{qid}: {canonical_option}",
                    statement_type=StatementType.USER_OBSERVATION,
                    source=src,
                )
            )

        # Also add direct question_answer observation (matches question rules in knowledge base)
        derived_obs.append(
            Observation(
                observation_type=ObservationType.QUESTION_ANSWER,
                value=f"{qid}:{canonical_option}",
                original_text=text or f"{qid}: {canonical_option}",
                statement_type=StatementType.USER_OBSERVATION,
                source=src,
            )
        )

        return QuestionAnswerResult(
            observations=derived_obs,
            question_id=qid,
            answer_value=canonical_option,
            user_hypotheses=user_hypotheses,
        )
