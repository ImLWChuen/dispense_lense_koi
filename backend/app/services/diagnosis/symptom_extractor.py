"""
DispenseIQ — Symptom Extractor

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
_add_rule(r"\b(intermittent|sometimes|occasional|sporadic|random(ly)?)\b",
          ObservationType.FREQUENCY_PATTERN, "intermittent")
_add_rule(r"\b(always|every\s*time|consistent(ly)?|constant(ly)?|every\s*shot|all\s*the\s*time)\b",
          ObservationType.FREQUENCY_PATTERN, "consistent")

# --- location ---
_add_rule(r"\b(one\s*nozzle|specific\s*nozzle|single\s*nozzle|same\s*location|one\s*position)\b",
          ObservationType.LOCATION_PATTERN, "specific_nozzle")
_add_rule(r"\b(all\s*(nozzles?|points?|locations?|positions?)|every\s*(nozzle|point|location)|across\s*all)\b",
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
_add_rule(r"\b(pressure\s*(fluctuat|unstable|varying|inconsistent|drop))\b",
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
# Hypothesis detection — user statements like "I think the nozzle is blocked"
# ---------------------------------------------------------------------------

_HYPOTHESIS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"i\s*think\s+(?:the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
    (re.compile(r"(?:it\s*)?(?:might|could|may)\s+be\s+(?:a\s+|the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
    (re.compile(r"(?:i\s*)?suspect\s+(?:the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
    (re.compile(r"(?:probably|likely)\s+(?:a\s+|the\s+)?(.+?)(?:\.|$)", re.IGNORECASE), ""),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SymptomExtractor:
    """Extracts structured observations from natural-language descriptions.

    Uses deterministic keyword matching. LLM-assisted extraction is
    added in Phase 9 as a bounded supplement, not a replacement.
    """

    def extract(self, description: str) -> ExtractionResult:
        """Extract observations from a free-text problem description.

        Args:
            description: The technician's natural-language description.

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

        # --- 1. Extract user hypotheses (do NOT create observations) ---
        for pattern, _ in _HYPOTHESIS_PATTERNS:
            match = pattern.search(description)
            if match:
                hypothesis_text = match.group(1).strip()
                if hypothesis_text:
                    user_hypotheses.append(hypothesis_text)

        # --- 2. Extract structured observations via keyword rules ---
        for regex, obs_type, value in _KEYWORD_RULES:
            if regex.search(description):
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

        # --- 3. Warn if no observations could be extracted ---
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
            extraction_method="deterministic",
            warnings=warnings,
        )
