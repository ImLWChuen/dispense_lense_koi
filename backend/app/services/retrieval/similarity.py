"""
Dispense Lens - Multi-Attribute Case Similarity Engine

Computes normalized similarity scores and human-readable matching factors
between a target diagnostic case and historical candidate cases.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.case import CaseModel

STOPWORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with",
    "by", "is", "are", "was", "were", "of", "from", "it", "this", "that",
    "has", "had", "have", "been", "be", "not", "during", "after", "before",
}


def _tokenize(text: str | None) -> set[str]:
    """Tokenize and filter text into normalized lowercase alphanumeric words."""
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _normalize_defect_code(code: str | None) -> str:
    """Normalize defect taxonomy codes (e.g. 'D03_INCONSISTENT_SIZE' -> 'D03')."""
    if not code:
        return ""
    upper = code.strip().upper()
    match = re.match(r"^(D0[1-9]|D[1-9][0-9])", upper)
    return match.group(1) if match else upper


def calculate_case_similarity(
    target: CaseModel,
    candidate: CaseModel,
) -> tuple[float, list[str]]:
    """Calculate multi-attribute similarity between target and candidate cases.

    Returns:
        tuple of (similarity_score in [0.0, 1.0], list of matched factor labels).
    """
    score = 0.0
    factors: list[str] = []

    # 1. Defect Code Matching (Max: 0.35)
    target_dcode = _normalize_defect_code(target.defect_code)
    cand_dcode = _normalize_defect_code(candidate.defect_code)

    if target_dcode and cand_dcode:
        if target_dcode == cand_dcode:
            score += 0.35
            defect_title = candidate.defect_name or candidate.defect_code or cand_dcode
            factors.append(f"Same Defect ({defect_title})")
        else:
            # Check for defect name token overlap if codes differ
            t_name_tokens = _tokenize(target.defect_name)
            c_name_tokens = _tokenize(candidate.defect_name)
            if t_name_tokens and c_name_tokens:
                overlap = len(t_name_tokens & c_name_tokens) / len(t_name_tokens | c_name_tokens)
                if overlap > 0.3:
                    score += 0.18
                    factors.append("Related Defect Category")
    elif target.defect_name and candidate.defect_name:
        t_name_tokens = _tokenize(target.defect_name)
        c_name_tokens = _tokenize(candidate.defect_name)
        if t_name_tokens and c_name_tokens:
            overlap = len(t_name_tokens & c_name_tokens) / len(t_name_tokens | c_name_tokens)
            score += overlap * 0.35
            if overlap >= 0.5:
                factors.append(f"Similar Defect Name ({candidate.defect_name})")

    # 2. Fluid Material Compatibility (Max: 0.15)
    if target.material and candidate.material:
        t_mat = target.material.strip().lower()
        c_mat = candidate.material.strip().lower()
        if t_mat == c_mat:
            score += 0.15
            factors.append(f"Same Material ({candidate.material})")
        else:
            t_mat_tokens = _tokenize(target.material)
            c_mat_tokens = _tokenize(candidate.material)
            if t_mat_tokens and c_mat_tokens:
                jaccard = len(t_mat_tokens & c_mat_tokens) / len(t_mat_tokens | c_mat_tokens)
                score += jaccard * 0.15
                if jaccard > 0.4:
                    factors.append(f"Compatible Material ({candidate.material})")

    # 3. Dispensing Method & Line Equipment (Max: 0.15)
    # Method (Max: 0.10)
    if target.method and candidate.method:
        t_method = target.method.strip().lower().replace("-", "_")
        c_method = candidate.method.strip().lower().replace("-", "_")
        if t_method == c_method:
            score += 0.10
            formatted_method = candidate.method.replace("_", " ").title()
            factors.append(f"Same Method ({formatted_method})")
        elif ("jet" in t_method and "jet" in c_method) or ("pressure" in t_method and "pressure" in c_method):
            score += 0.05
            factors.append("Similar Dispense Technology")

    # Line / Equipment model (Max: 0.05)
    t_ctx = target.machine_context or {}
    c_ctx = candidate.machine_context or {}
    t_line = t_ctx.get("line_id") or t_ctx.get("line")
    c_line = c_ctx.get("line_id") or c_ctx.get("line")
    t_model = t_ctx.get("dispenser_model") or t_ctx.get("machine_model")
    c_model = c_ctx.get("dispenser_model") or c_ctx.get("machine_model")

    if t_line and c_line and str(t_line).lower() == str(c_line).lower():
        score += 0.05
        factors.append(f"Same Line ({c_line})")
    elif t_model and c_model and str(t_model).lower() == str(c_model).lower():
        score += 0.05
        factors.append(f"Same Dispenser ({c_model})")

    # 4. Observation & Finding Overlap (Max: 0.15)
    t_obs_types = {
        obs.observation_type.lower()
        for obs in (target.observations or [])
        if getattr(obs, "observation_type", None)
    }
    c_obs_types = {
        obs.observation_type.lower()
        for obs in (candidate.observations or [])
        if getattr(obs, "observation_type", None)
    }

    if t_obs_types and c_obs_types:
        obs_jaccard = len(t_obs_types & c_obs_types) / len(t_obs_types | c_obs_types)
        score += obs_jaccard * 0.15
        if obs_jaccard >= 0.25:
            factors.append("Shared Symptoms & Checks")

    # 5. Problem Description Lexical Similarity (Max: 0.10)
    t_desc_tokens = _tokenize(target.description)
    c_desc_tokens = _tokenize(candidate.description)
    if t_desc_tokens and c_desc_tokens:
        desc_jaccard = len(t_desc_tokens & c_desc_tokens) / len(t_desc_tokens | c_desc_tokens)
        score += desc_jaccard * 0.10
        if desc_jaccard >= 0.20:
            factors.append("Matching Problem Description")

    # 6. Resolution Status Prioritization (Max: 0.10)
    raw_cond = str(candidate.issue_condition).strip().upper()
    is_resolved = raw_cond in ("RESOLVED", "ISSUECONDITION.RESOLVED")
    if is_resolved:
        score += 0.10
        factors.append("Verified Resolution Available")
    elif candidate.cause_confirmations:
        score += 0.05
        factors.append("Confirmed Root Cause")

    normalized_score = min(1.0, max(0.0, round(score, 4)))
    return normalized_score, factors
