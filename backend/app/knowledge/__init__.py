"""
DispenseIQ — Knowledge Base Loader

Loads defect definitions, causes, questions, actions, and evidence rules
from the static JSON knowledge files. These are the structured domain
knowledge the diagnostic engine operates on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.schemas.diagnosis import (
    CauseDefinition,
    CheckDefinition,
    DefectDefinition,
    EvidenceRule,
    EvidenceRelation,
    EvidenceStrength,
    QuestionDefinition,
)

# Resolve the knowledge directory relative to this file
_KNOWLEDGE_DIR = Path(__file__).resolve().parent


def _load_json(filename: str) -> dict[str, Any]:
    """Load and parse a JSON file from the knowledge directory."""
    filepath = _KNOWLEDGE_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Knowledge file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Defects
# ---------------------------------------------------------------------------

def load_defects() -> list[DefectDefinition]:
    """Load all defect definitions from defects.json."""
    data = _load_json("defects.json")
    return [DefectDefinition(**d) for d in data.get("defects", [])]


def get_defect_by_code(code: str) -> DefectDefinition | None:
    """Retrieve a specific defect definition by its code."""
    for defect in load_defects():
        if defect.code == code:
            return defect
    return None


# ---------------------------------------------------------------------------
# Causes
# ---------------------------------------------------------------------------

def load_causes() -> list[CauseDefinition]:
    """Load all cause definitions from causes.json."""
    data = _load_json("causes.json")
    return [CauseDefinition(**c) for c in data.get("causes", [])]


def get_causes_for_defect(defect_code: str) -> list[CauseDefinition]:
    """Retrieve causes applicable to a specific defect code."""
    defect = get_defect_by_code(defect_code)
    if not defect:
        return []
    cause_ids = set(defect.applicable_causes)
    return [c for c in load_causes() if c.id in cause_ids]


def get_cause_by_id(cause_id: str) -> CauseDefinition | None:
    """Retrieve a specific cause definition by its ID."""
    for cause in load_causes():
        if cause.id == cause_id:
            return cause
    return None


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def load_questions() -> list[QuestionDefinition]:
    """Load all question definitions from questions.json."""
    data = _load_json("questions.json")
    return [QuestionDefinition(**q) for q in data.get("questions", [])]


def get_questions_for_causes(cause_ids: list[str]) -> list[QuestionDefinition]:
    """Retrieve questions applicable to any of the given cause IDs."""
    cause_set = set(cause_ids)
    return [
        q for q in load_questions()
        if cause_set.intersection(q.applicable_causes)
    ]


def get_questions_for_defect(defect_code: str) -> list[QuestionDefinition]:
    """Retrieve questions applicable to a specific defect code."""
    return [
        q for q in load_questions()
        if defect_code in q.applicable_defects
    ]


# ---------------------------------------------------------------------------
# Actions / Checks
# ---------------------------------------------------------------------------

def load_actions() -> list[CheckDefinition]:
    """Load all check/action definitions from actions.json."""
    data = _load_json("actions.json")
    return [CheckDefinition(**a) for a in data.get("actions", [])]


def get_actions_for_causes(cause_ids: list[str]) -> list[CheckDefinition]:
    """Retrieve checks applicable to any of the given cause IDs."""
    cause_set = set(cause_ids)
    return [
        a for a in load_actions()
        if cause_set.intersection(a.applicable_causes)
    ]


def get_action_by_id(action_id: str) -> CheckDefinition | None:
    """Retrieve a specific check definition by its ID."""
    for action in load_actions():
        if action.id == action_id:
            return action
    return None


# Ergonomic aliases (checks == actions)
load_checks = load_actions
get_checks_for_causes = get_actions_for_causes
get_check_by_id = get_action_by_id


# ---------------------------------------------------------------------------
# Evidence Rules
# ---------------------------------------------------------------------------

def load_evidence_rules() -> list[EvidenceRule]:
    """Load all evidence evaluation rules from rules.json and actions.json mappings."""
    data = _load_json("rules.json")
    rules = []
    for r in data.get("rules", []):
        rules.append(EvidenceRule(
            id=r["id"],
            observation_type=r["observation_type"],
            observation_value=r["observation_value"],
            cause_id=r["cause_id"],
            relation=EvidenceRelation(r["relation"]),
            strength=EvidenceStrength(r.get("strength", "MODERATE")),
            explanation=r.get("explanation", ""),
        ))

    # Also load action evidence mappings as structured rules
    try:
        actions_data = _load_json("actions.json")
        existing_keys = {(r.cause_id, r.observation_type, r.observation_value) for r in rules}
        for a in actions_data.get("actions", []):
            aid = a["id"]
            for outcome, causes_map in a.get("evidence_mapping", {}).items():
                for cause_id, spec in causes_map.items():
                    rel = spec.get("relation", "NEUTRAL")
                    stn = spec.get("strength", "MODERATE")
                    # Check result rule format: check_result -> ACT01:no_blockage
                    key1 = (cause_id, "check_result", f"{aid}:{outcome}")
                    if key1 not in existing_keys:
                        rules.append(EvidenceRule(
                            id=f"AR_{aid}_{outcome}_{cause_id}",
                            observation_type="check_result",
                            observation_value=f"{aid}:{outcome}",
                            cause_id=cause_id,
                            relation=EvidenceRelation(rel),
                            strength=EvidenceStrength(stn),
                            explanation=f"Troubleshooting check '{a.get('name', aid)}' finding '{outcome}' {rel.lower()} {cause_id}.",
                        ))
                        existing_keys.add(key1)

                    # Action outcome rule format: check_ACT01 -> no_blockage
                    key2 = (cause_id, f"check_{aid}", outcome)
                    if key2 not in existing_keys:
                        rules.append(EvidenceRule(
                            id=f"AR_{aid}_{outcome}_{cause_id}_direct",
                            observation_type=f"check_{aid}",
                            observation_value=outcome,
                            cause_id=cause_id,
                            relation=EvidenceRelation(rel),
                            strength=EvidenceStrength(stn),
                            explanation=f"Troubleshooting check '{a.get('name', aid)}' finding '{outcome}' {rel.lower()} {cause_id}.",
                        ))
                        existing_keys.add(key2)
    except Exception:
        pass

    return rules


def get_rules_for_cause(cause_id: str) -> list[EvidenceRule]:
    """Retrieve all evidence rules applicable to a specific cause."""
    return [r for r in load_evidence_rules() if r.cause_id == cause_id]


def get_rules_for_observation(
    observation_type: str, observation_value: str
) -> list[EvidenceRule]:
    """Retrieve all evidence rules matching a specific observation."""
    return [
        r for r in load_evidence_rules()
        if r.observation_type == observation_type
        and r.observation_value == observation_value
    ]


# ---------------------------------------------------------------------------
# Canonical Knowledge Access Interface (as specified in docs/implementation_plan.md)
# ---------------------------------------------------------------------------

def get_defect(defect_id: str) -> DefectDefinition | None:
    """Retrieve defect by code/id."""
    return get_defect_by_code(defect_id)


def get_candidate_causes(
    defect_id: str,
    context: dict[str, Any] | None = None,
) -> list[CauseDefinition]:
    """Retrieve causes applicable to a defect, optionally filtered by context."""
    causes = get_causes_for_defect(defect_id)
    if context and "material" in context and context["material"]:
        mat = str(context["material"]).lower()
        filtered = [
            c for c in causes
            if not c.applicable_contexts or any(mat in ctx.lower() for ctx in c.applicable_contexts)
        ]
        if filtered:
            return filtered
    return causes


def get_evidence_rules(cause_id: str | None = None) -> list[EvidenceRule]:
    """Retrieve evidence rules, optionally filtered by cause ID."""
    if cause_id:
        return get_rules_for_cause(cause_id)
    return load_evidence_rules()


def get_questions(cause_ids: list[str] | None = None) -> list[QuestionDefinition]:
    """Retrieve questions, optionally filtered by applicable cause IDs."""
    if cause_ids:
        return get_questions_for_causes(cause_ids)
    return load_questions()


def get_actions(
    cause_ids: list[str] | None = None,
    context: dict[str, Any] | None = None,
) -> list[CheckDefinition]:
    """Retrieve actions/checks, optionally filtered by cause IDs."""
    if cause_ids:
        return get_actions_for_causes(cause_ids)
    return load_actions()
