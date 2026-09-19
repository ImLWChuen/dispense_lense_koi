"""
DispenseIQ — Evidence Engine

The core reasoning layer. Evaluates every observation against every
candidate cause to determine SUPPORTS / CONTRADICTS / NEUTRAL / DUPLICATE.

Design rules:
- Every evidence item records its provenance (USER, MEASUREMENT, etc.).
- Duplicate/correlated observations do NOT independently contribute weight.
- Missing evidence is distinguished from contradictory evidence.
- The engine is deterministic — no LLM involvement in scoring.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from app.knowledge import (
    get_causes_for_defect,
    get_rules_for_cause,
    get_rules_for_observation,
    load_evidence_rules,
)
from app.schemas.diagnosis import (
    CandidateCause,
    CauseConclusion,
    CauseEvidence,
    EvidenceRelation,
    EvidenceSource,
    EvidenceStrength,
    Observation,
)
from app.utils.scoring import (
    SCORING_CONFIG,
    clamp_score,
    contradiction_weight,
    support_weight,
)


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

# Semantic groups: observations in the same group with similar values
# are considered duplicates.
_SEMANTIC_GROUPS: dict[str, set[str]] = {
    "deposit_size_small": {"undersized", "small", "too_little", "insufficient", "below_target", "too_small", "undersize"},
    "deposit_size_large": {"oversized", "large", "too_much", "excessive", "above_target", "too_large", "oversize"},
    "deposit_size_variable": {"inconsistent", "variable", "varying", "uneven"},
    "deposit_missing": {"missing", "absent", "no_deposit"},
    "bubble_air": {"visible_bubbles", "air_entrapment", "bubble", "bubbles", "air_bubble", "air_bubbles"},
    "spread_excess": {"excessive_spread", "flat_spread", "bleeding", "spread", "spreading"},
    "time_prolonged": {"after_prolonged_operation", "worsens_over_time"},
    "frequency_intermittent": {"intermittent", "sporadic"},
    "frequency_consistent": {"consistent", "constant"},
    "location_single": {"specific_nozzle", "one_position", "localized"},
    "location_all": {"all_points", "varies_across_points", "systemic"},
}


def _to_evidence_source(src: Any) -> EvidenceSource:
    """Safely convert a source value to EvidenceSource enum."""
    if isinstance(src, EvidenceSource):
        return src
    if isinstance(src, str):
        try:
            return EvidenceSource(src)
        except ValueError:
            return EvidenceSource.USER
    return EvidenceSource.USER


def _normalize_type_and_val(obs_type: Any, val: Any) -> tuple[str, str]:
    """Normalize observation type and value for canonical rule matching."""
    t = str(obs_type.value if hasattr(obs_type, "value") else obs_type).strip().lower()
    v = str(val.value if hasattr(val, "value") else val).strip().lower()

    if t == "spatial_pattern":
        t = "location_pattern"

    # Normalize common vision/client/synonym aliases
    if v in ("too_small", "undersize", "small", "too_little", "below_target"):
        v = "undersized"
    elif v in ("too_large", "oversize", "large", "too_much", "excessive", "above_target"):
        v = "oversized"
    elif v in ("bubble", "bubbles", "air_bubble", "air_bubbles", "air_entrapment"):
        v = "visible_bubbles"
    elif v in ("spread", "spreading", "flat_spread", "bleeding"):
        v = "excessive_spread"
    elif v in ("systemic",):
        v = "all_points"
    elif v in ("localized",):
        v = "specific_nozzle"

    return t, v


def _get_semantic_group(obs_type: str, value: str) -> str | None:
    """Return the semantic group key for an observation, if any."""
    normalized_type, normalized_val = _normalize_type_and_val(obs_type, value)
    for group_key, values in _SEMANTIC_GROUPS.items():
        if normalized_val in values:
            return f"{normalized_type}:{group_key}"
    return None


def _is_duplicate(
    obs: Observation,
    existing_observations: list[Observation],
) -> tuple[bool, str | None]:
    """Check if an observation is a semantic duplicate of an existing one.

    Returns:
        (is_duplicate, duplicate_of_id)
    """
    obs_t, obs_v = _normalize_type_and_val(obs.observation_type, obs.value)
    obs_group = _get_semantic_group(obs_t, obs_v)

    for existing in existing_observations:
        if existing.id == obs.id:
            continue

        ex_t, ex_v = _normalize_type_and_val(existing.observation_type, existing.value)

        # Same normalized type + same normalized value → definite duplicate
        if ex_t == obs_t and ex_v == obs_v:
            return True, existing.id

        # Same semantic group → likely duplicate
        if obs_group:
            existing_group = _get_semantic_group(ex_t, ex_v)
            if existing_group == obs_group:
                return True, existing.id

        # Fuzzy text similarity on the original text (if both have it)
        if (obs.original_text and existing.original_text
                and obs.original_text != existing.original_text):
            ratio = SequenceMatcher(
                None,
                obs.original_text.lower(),
                existing.original_text.lower(),
            ).ratio()
            if ratio > 0.85:
                return True, existing.id

    return False, None


# ---------------------------------------------------------------------------
# Evidence evaluation
# ---------------------------------------------------------------------------

class EvidenceEngine:
    """Evaluates observations against candidate causes using knowledge rules.

    The evaluation is purely deterministic. For each (observation, cause) pair
    the engine looks up matching rules and produces a CauseEvidence record.
    """

    def evaluate(
        self,
        observations: list[Observation],
        defect_code: str,
    ) -> list[CandidateCause]:
        """Evaluate all observations against all candidate causes for a defect."""
        return self._evaluate_internal(observations, defect_code)

    evaluate_all = evaluate

    def _evaluate_internal(
        self,
        observations: list[Observation],
        defect_code: str,
    ) -> list[CandidateCause]:
        """Evaluate all observations against all candidate causes for a defect.

        Steps for each cause:
        1. Look up static rules linking observations to this cause.
        2. Filter out semantic duplicates (only the first contributes score).
        3. Score supporting / contradicting evidence.
        4. Identify missing evidence and apply penalties.
        5. Calculate total score and clamp to [0, 100].
        6. Return causes sorted by score descending.
        """
        # 1. Retrieve applicable causes for this defect
        cause_defs = get_causes_for_defect(defect_code)
        if not cause_defs:
            return []

        # 2. Load all evidence rules once
        all_rules = load_evidence_rules()

        # 3. For each cause, evaluate every observation
        candidates: list[CandidateCause] = []

        for cause_def in cause_defs:
            supporting: list[CauseEvidence] = []
            contradicting: list[CauseEvidence] = []
            neutral: list[CauseEvidence] = []
            missing_evidence: list[str] = []
            score_breakdown: dict[str, float] = {
                "base": SCORING_CONFIG.base_score,
                "positive_evidence": 0.0,
                "contradiction_penalty": 0.0,
                "duplicate_ignored": 0.0,
                "missing_penalty": 0.0,
            }

            # Track which observations have been processed (for duplicate detection)
            processed_observations: list[Observation] = []

            for obs in observations:
                # --- Duplicate check ---
                is_dup, dup_of = _is_duplicate(obs, processed_observations)
                processed_observations.append(obs)

                obs_t, obs_v = _normalize_type_and_val(obs.observation_type, obs.value)

                # Find matching rules (comparing normalized types & values)
                matching_rules = [
                    r for r in all_rules
                    if (r.cause_id == cause_def.id
                        and _normalize_type_and_val(r.observation_type, r.observation_value) == (obs_t, obs_v))
                ]

                if not matching_rules:
                    # No rule → NEUTRAL / UNKNOWN for this cause
                    evidence = CauseEvidence(
                        observation_id=obs.id,
                        cause_id=cause_def.id,
                        relation=EvidenceRelation.NEUTRAL,
                        strength=EvidenceStrength.WEAK,
                        source=_to_evidence_source(obs.source),
                        explanation=f"No evidence rule links '{obs.observation_type}={obs.value}' to '{cause_def.name}'.",
                        is_duplicate=is_dup,
                        duplicate_of=dup_of,
                        score_contribution=0.0,
                    )
                    neutral.append(evidence)
                    continue

                # Use the strongest matching rule
                best_rule = max(
                    matching_rules,
                    key=lambda r: _strength_order(r.strength),
                )

                # Calculate score contribution
                if is_dup:
                    score_contrib = 0.0
                elif best_rule.relation == EvidenceRelation.SUPPORTS:
                    strength_str = best_rule.strength.value if isinstance(best_rule.strength, EvidenceStrength) else best_rule.strength
                    score_contrib = support_weight(strength_str)
                elif best_rule.relation == EvidenceRelation.CONTRADICTS:
                    strength_str = best_rule.strength.value if isinstance(best_rule.strength, EvidenceStrength) else best_rule.strength
                    score_contrib = -contradiction_weight(strength_str)
                else:
                    score_contrib = 0.0

                evidence = CauseEvidence(
                    observation_id=obs.id,
                    cause_id=cause_def.id,
                    relation=EvidenceRelation(best_rule.relation.value if isinstance(best_rule.relation, EvidenceRelation) else best_rule.relation),
                    strength=EvidenceStrength(best_rule.strength.value if isinstance(best_rule.strength, EvidenceStrength) else best_rule.strength),
                    source=_to_evidence_source(obs.source),
                    explanation=best_rule.explanation,
                    is_duplicate=is_dup,
                    duplicate_of=dup_of,
                    score_contribution=score_contrib,
                )

                if is_dup:
                    evidence.relation = EvidenceRelation.DUPLICATE
                    neutral.append(evidence)
                    score_breakdown["duplicate_ignored"] += 1
                elif best_rule.relation == EvidenceRelation.SUPPORTS:
                    supporting.append(evidence)
                    score_breakdown["positive_evidence"] += score_contrib
                elif best_rule.relation == EvidenceRelation.CONTRADICTS:
                    contradicting.append(evidence)
                    score_breakdown["contradiction_penalty"] += abs(score_contrib)
                else:
                    neutral.append(evidence)

            # 4. Identify missing evidence (symptom observations only, not unexecuted checks/questions)
            cause_rules = [
                r for r in all_rules
                if r.cause_id == cause_def.id
                and not str(r.observation_type).startswith("check_")
                and str(r.observation_type) != "check_result"
                and not str(r.observation_type).startswith("question_")
                and str(r.observation_type) != "question_answer"
                and str(r.observation_type) != "spatial_pattern"
            ]
            observed_types = {_normalize_type_and_val(o.observation_type, o.value) for o in observations}
            for rule in cause_rules:
                if _normalize_type_and_val(rule.observation_type, rule.observation_value) not in observed_types:
                    if rule.relation == EvidenceRelation.SUPPORTS:
                        missing_desc = f"{rule.observation_type}={rule.observation_value} has not been observed."
                        if missing_desc not in missing_evidence:
                            missing_evidence.append(missing_desc)

            # Limit missing evidence penalty
            missing_penalty = min(
                len(missing_evidence) * SCORING_CONFIG.missing_evidence_penalty,
                15.0,  # cap to avoid over-penalizing
            )
            score_breakdown["missing_penalty"] = missing_penalty

            # 5. Calculate final score (each cause score clamped between 0 and 100)
            raw_score = (
                score_breakdown["base"]
                + score_breakdown["positive_evidence"]
                - score_breakdown["contradiction_penalty"]
                - missing_penalty
            )
            final_score = clamp_score(raw_score)

            candidates.append(CandidateCause(
                cause_id=cause_def.id,
                cause_name=cause_def.name,
                score=final_score,
                conclusion=CauseConclusion.SUSPECTED,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                neutral_evidence=neutral,
                missing_evidence=missing_evidence,
                score_breakdown=score_breakdown,
            ))

        # 6. Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def update_with_new_evidence(
        self,
        existing_candidates: list[CandidateCause],
        new_observations: list[Observation],
        defect_code: str,
    ) -> list[CandidateCause]:
        """Re-evaluate causes with new evidence added to existing observations.

        Merges new observations into the existing evidence and recalculates
        all scores from scratch. This preserves the additive evidence model
        while preventing stale scores.

        Args:
            existing_candidates: Previously ranked causes.
            new_observations: Newly arrived observations to incorporate.
            defect_code: The identified defect code.

        Returns:
            Updated list of CandidateCause with recalculated scores.
        """
        # Collect all prior observations from existing evidence
        existing_obs_ids: set[str] = set()
        prior_observations: list[Observation] = []

        for candidate in existing_candidates:
            for ev in (candidate.supporting_evidence
                       + candidate.contradicting_evidence
                       + candidate.neutral_evidence):
                existing_obs_ids.add(ev.observation_id)

        # We can't reconstruct full Observation objects from evidence alone,
        # so the caller should pass all observations (old + new).
        # For now, just re-evaluate with new observations merged.
        all_observations = new_observations  # caller is expected to pass all

        return self.evaluate(all_observations, defect_code)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STRENGTH_ORDER = {
    EvidenceStrength.STRONG: 3,
    EvidenceStrength.MODERATE: 2,
    EvidenceStrength.WEAK: 1,
    "STRONG": 3,
    "MODERATE": 2,
    "WEAK": 1,
}


def _strength_order(strength: EvidenceStrength | str) -> int:
    """Return numeric order for sorting by strength."""
    return _STRENGTH_ORDER.get(strength, 1)
