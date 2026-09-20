"""
Dispense Lens - Symptom Extractor

Converts natural-language problem descriptions into structured observations.
Uses deterministic keyword matching first; LLM extraction is deferred to
Phase 9 (bounded LLM integration).

Key design rules:
- Distinguish USER_OBSERVATION from USER_INTERPRETATION and AI_INFERENCE.
- Never auto-promote a user hypothesis to a confirmed cause.
- Preserve the original description alongside extracted observations.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.diagnosis import (
    EvidenceSource,
    ExtractionResult,
    Observation,
    ObservationType,
    StatementType,
)


# ---------------------------------------------------------------------------
# Keyword → Observation mapping tables
# ---------------------------------------------------------------------------

# Each entry: (compiled regex, ObservationType, normalized value)
_KEYWORD_RULES: list[tuple[re.Pattern, ObservationType, str]] = []


def _add_rule(pattern: str, obs_type: ObservationType, value: str) -> None:
    _KEYWORD_RULES.append((re.compile(pattern, re.IGNORECASE), obs_type, value))


# --- deposit size ---
_add_rule(r"\b(too\s*small|undersized|smaller|small\s*dots?|tiny|insufficient)\b",
          ObservationType.DEPOSIT_SIZE, "undersized")
_add_rule(r"\b(too\s*(big|large)|oversized|larger|big\s*dots?|excessive\s*material)\b",
          ObservationType.DEPOSIT_SIZE, "oversized")
_add_rule(r"\b(inconsistent|variable|varying|uneven|different\s*sizes?|some.*larger.*some.*smaller|some.*smaller.*some.*larger)\b",
          ObservationType.DEPOSIT_SIZE, "inconsistent")
_add_rule(r"\b(too\s*little|not\s*enough|below\s*target|less\s*material)\b",
          ObservationType.DEPOSIT_SIZE, "too_little")
_add_rule(r"\b(too\s*much|excess|above\s*target|more\s*material)\b",
          ObservationType.DEPOSIT_SIZE, "too_much")

# --- deposit presence ---
_add_rule(r"\b(missing(\s*dots?)?|no\s*dots?|no\s*deposit|absent|skipped|no\s*material\s*dispensed)\b",
          ObservationType.DEPOSIT_PRESENCE, "missing")

# --- deposit shape ---
_add_rule(r"\b(abnormal\s*shapes?|irregular\s*shapes?|deformed|misshapen)\b",
          ObservationType.DEPOSIT_SHAPE, "abnormal")
_add_rule(r"\b(tailing|stringing|string)\b",
          ObservationType.DEPOSIT_SHAPE, "tailing")
_add_rule(r"\b(satellite\s*dots?|satellites?|splatter)\b",
          ObservationType.DEPOSIT_SHAPE, "satellite_dots")
_add_rule(r"\b(flat\s*dots?|flat\s*deposits?|pancake)\b",
          ObservationType.DEPOSIT_SHAPE, "flat")

# --- bubbles ---
_add_rule(r"\b(bubbles?|air\s*bubbles?|voids?|air\s*entrap(?:ment)?|trapped\s*air)\b",
          ObservationType.BUBBLE_PRESENCE, "visible_bubbles")
_add_rule(r"\b(craters?|holes?\s*in\s*(?:the\s*)?dots?)\b",
          ObservationType.VISUAL_APPEARANCE, "crater_shape")

# --- spreading ---
_add_rule(r"\b(spreads?|spreading|bleeds?|bleeding|wetting\s*too\s*much)\b",
          ObservationType.SPREADING_BEHAVIOUR, "excessive_spread")

# --- runtime / time pattern ---
_add_rule(r"\b((?:after|running\s+for|has\s+been\s+running)\s*(?:around\s*|approx\s*)?(?:\d+\s*(?:min|minute|hour)s?|a\s*while|prolonged|extended|long|some\s*time)|after\s*(?:the\s*machine\s*(?:has\s*been\s*)?)?running|over\s*time|gets?\s*worse\s*over\s*time|worsens?\s*over\s*time)\b",
          ObservationType.RUNTIME_PATTERN, "after_prolonged_operation")
_add_rule(r"\b(immediately|right\s*away|from\s*(the\s*)?start|at\s*startup)\b",
          ObservationType.RUNTIME_PATTERN, "immediately")
_add_rule(r"\b(worse(ns?)?\s*over\s*time|gradual(ly)?|progressive(ly)?)\b",
          ObservationType.RUNTIME_PATTERN, "worsens_over_time")


# --- frequency ---
_add_rule(r"\b(intermittent(ly)?|sometimes|occasional(ly)?|sporadic(ally)?|random(ly)?)\b",
          ObservationType.FREQUENCY_PATTERN, "intermittent")
_add_rule(r"\b(always|every\s*time|consistent(ly)?|constant(ly)?|every\s*shot|all\s*the\s*time)\b",
          ObservationType.FREQUENCY_PATTERN, "consistent")

# --- location ---
_add_rule(r"\b(one\s*nozzle|specific\s*nozzle|single\s*nozzle|same\s*location|one\s*position)\b",
          ObservationType.LOCATION_PATTERN, "specific_nozzle")
_add_rule(r"\b(all\s*(nozzles?|points?|locations?|positions?)|every\s*(nozzle|point|location)|across\s*all\s*(?:dispensing\s*)?(?:nozzles?|points?|locations?|positions?))\b",
          ObservationType.LOCATION_PATTERN, "all_points")

# --- material ---
_add_rule(r"\b(low\s*viscosity|thin\s*material|watery)\b",
          ObservationType.MATERIAL_STATE, "low_viscosity")
_add_rule(r"\b(high\s*viscosity|thick\s*material|stiff)\b",
          ObservationType.MATERIAL_STATE, "high_viscosity")
_add_rule(r"\b(separated|phase\s*separation|settling)\b",
          ObservationType.MATERIAL_STATE, "separated")

# --- temperature ---
_add_rule(r"\b(hot|warm|elevated\s*temp|high\s*temp|temperature\s*(rose|increased|high))\b",
          ObservationType.TEMPERATURE, "elevated")
_add_rule(r"\b(cold|cool|low\s*temp|temperature\s*(dropped|decreased|low))\b",
          ObservationType.TEMPERATURE, "low")

# --- pressure ---
_add_rule(r"\b(pressure\s*(fluctuat\w*|unstable|varying|inconsistent|drop\w*))\b",
          ObservationType.PRESSURE, "fluctuating")
_add_rule(r"\b(pressure\s*(stable|constant|steady|normal))\b",
          ObservationType.PRESSURE, "stable")

# --- nozzle ---
_add_rule(r"\b(nozzle\s*(blocked|clogged|restricted|plugged))\b",
          ObservationType.NOZZLE_CONDITION, "blocked")
_add_rule(r"\b(nozzle\s*(damaged|worn|broken|chipped))\b",
          ObservationType.NOZZLE_CONDITION, "damaged")
_add_rule(r"\b(nozzle\s*(clean|clear|new|replaced))\b",
          ObservationType.NOZZLE_CONDITION, "clean")

# --- equipment ---
_add_rule(r"\b(equipment\s*(worn|old|degraded)|machine\s*(worn|old))\b",
          ObservationType.EQUIPMENT_CONDITION, "worn")

# --- leaking / dripping ---
_add_rule(r"\b(leak(ing)?|drip(ping)?|oozing)\b",
          ObservationType.VISUAL_APPEARANCE, "leaking_dripping")


# ---------------------------------------------------------------------------
# Hypothesis detection - user statements like "I think the nozzle is blocked"
# ---------------------------------------------------------------------------

_HYPOTHESIS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"i\s*think\s+(?:the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
    (re.compile(r"(?:it\s*)?(?:might|could|may)\s+be\s+(?:a\s+|the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
    (re.compile(r"(?:i\s*)?suspect\s+(?:the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
    (re.compile(r"(?:probably|likely)\s+(?:a\s+|the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
]


# ---------------------------------------------------------------------------
# Negation detection
# ---------------------------------------------------------------------------

_NEGATION_REGEX = re.compile(
    r"\b(no|not|without|never|neither|nor|n't)\b",
    re.IGNORECASE,
)


def _is_match_negated(text: str, match_start: int) -> bool:
    """Check if a match is locally negated by looking backward within the sentence or clause."""
    lookback_window = text[max(0, match_start - 50) : match_start]
    # Split by clause-ending punctuation
    clauses = re.split(r"[\.\,\;\!\?]", lookback_window)
    clause_before = clauses[-1]
    return bool(_NEGATION_REGEX.search(clause_before))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SymptomExtractor:
    """Extracts structured observations from natural-language descriptions.

    Uses deterministic keyword matching first. If deterministic rules yield
    no observations or if enhanced interpretation is needed, safely falls back
    to bounded LLM-assisted extraction.
    """

    def __init__(self, llm_service: Any = None) -> None:
        if llm_service is not None:
            self.llm = llm_service
        else:
            try:
                from app.services.ai.llm_service import LLMService
                self.llm = LLMService()
            except ImportError:
                self.llm = None

    def extract(self, description: str, use_llm: bool = True) -> ExtractionResult:
        """Extract observations from a free-text problem description.

        Args:
            description: The technician's natural-language description.
            use_llm: Whether to attempt bounded LLM fallback if deterministic rules find no observations.

        Returns:
            ExtractionResult containing the original text, extracted
            observations, and any detected user hypotheses.
        """
        if not description or not description.strip():
            return ExtractionResult(
                original_description=description or "",
                warnings=["Empty description provided."],
            )

        observations: list[Observation] = []
        user_hypotheses: list[str] = []
        warnings: list[str] = []
        seen_keys: set[tuple[str, str]] = set()

        # --- 1. Extract user hypotheses and mask them from objective observation matching ---
        masked_description = description
        for pattern, _ in _HYPOTHESIS_PATTERNS:
            for match in pattern.finditer(description):
                hypothesis_text = match.group(1).strip()
                if hypothesis_text and hypothesis_text not in user_hypotheses:
                    user_hypotheses.append(hypothesis_text)
                start, end = match.span()
                masked_description = (
                    masked_description[:start]
                    + " " * (end - start)
                    + masked_description[end:]
                )

        # --- 2. Extract structured observations via keyword rules with negation checks ---
        for regex, obs_type, value in _KEYWORD_RULES:
            matches = list(regex.finditer(masked_description))
            if not matches:
                continue

            has_non_negated_match = any(
                not _is_match_negated(masked_description, m.start())
                for m in matches
            )

            if has_non_negated_match:
                key = (obs_type.value if isinstance(obs_type, ObservationType) else obs_type, value)
                if key not in seen_keys:
                    seen_keys.add(key)
                    observations.append(Observation(
                        observation_type=obs_type,
                        value=value,
                        original_text=description,
                        statement_type=StatementType.USER_OBSERVATION,
                        source=EvidenceSource.USER,
                    ))

        method = "deterministic"

        # --- 3. Bounded LLM fallback when deterministic extraction finds nothing ---
        if not observations and use_llm and self.llm and getattr(self.llm, "is_available", False):
            llm_result = self.llm.extract_symptoms(description)
            if llm_result and isinstance(llm_result, dict):
                llm_obs = llm_result.get("observations", [])
                llm_hyps = llm_result.get("user_hypotheses", [])

                for hyp in llm_hyps:
                    hyp_str = str(hyp).strip()
                    if hyp_str and hyp_str not in user_hypotheses:
                        user_hypotheses.append(hyp_str)

                for raw_obs in llm_obs:
                    raw_type = str(raw_obs.get("type", "")).strip().lower()
                    raw_val = str(raw_obs.get("value", "")).strip().lower()

                    # Find matching ObservationType
                    matched_type = None
                    for ot in ObservationType:
                        if ot.value.lower() == raw_type:
                            matched_type = ot
                            break

                    if matched_type and raw_val:
                        key = (matched_type.value, raw_val)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            observations.append(Observation(
                                observation_type=matched_type,
                                value=raw_val,
                                original_text=description,
                                statement_type=StatementType.USER_OBSERVATION,
                                source=EvidenceSource.USER,
                            ))

                if observations:
                    method = "llm"

        # --- 4. Warn if no observations could be extracted ---
        if not observations:
            warnings.append(
                "No structured observations could be extracted from the "
                "description. The description has been preserved for "
                "manual review or LLM-assisted extraction."
            )

        return ExtractionResult(
            original_description=description,
            observations=observations,
            user_hypotheses=user_hypotheses,
            extraction_method=method,
            warnings=warnings,
        )
