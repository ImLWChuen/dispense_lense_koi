"""
Dispense Lens - LLM Prompt Manager

Centralizes all system prompts, instruction schemas, and few-shot formatting
for bounded LLM operations. Keeps prompts separate from Python business logic.

Key safety rules embedded in prompts:
- Prompts prohibit model-invented cause scores.
- Prompts prohibit model-invented troubleshooting procedures or sources.
- Prompts forbid declaring a root cause confirmed or issue resolved.
- Prompts require structured JSON output for extraction.
"""

from __future__ import annotations

import json
from typing import Any


class PromptManager:
    """Stores and formats prompts for bounded LLM tasks."""

    # -----------------------------------------------------------------------
    # 1. Symptom Extraction
    # -----------------------------------------------------------------------

    SYMPTOM_EXTRACTION_SYSTEM = """You are an industrial fluid dispensing diagnostic assistant.
Your sole job is to extract structured physical observations and user hypotheses from a technician's problem description.

CRITICAL RULES:
1. Extract ONLY objective physical observations (e.g. deposit size, timing, location, frequency, appearance).
2. Distinguish direct user observations from user hypotheses/guesses (e.g. "I think the nozzle is blocked" is a hypothesis, NOT a confirmed observation).
3. DO NOT diagnose or assign root causes.
4. DO NOT return probabilities, percentages, or confidence scores for causes (e.g., NEVER say "90% chance of air bubble").
5. Return JSON ONLY with the following schema:
{
  "observations": [
    {
      "type": "<one of: deposit_size, deposit_count, deposit_shape, deposit_presence, runtime_pattern, time_pattern, location_pattern, frequency_pattern, material_state, temperature, pressure, nozzle_condition, equipment_condition, process_parameter, visual_appearance, bubble_presence, spreading_behaviour>",
      "value": "<normalized value string, e.g. undersized, oversized, inconsistent, missing, after_prolonged_operation, intermittent, specific_nozzle, all_points, visible_bubbles, excessive_spread>"
    }
  ],
  "user_hypotheses": [
    "<string describing any guess or hypothesis the user expressed, or empty if none>"
  ]
}"""

    @classmethod
    def get_symptom_extraction_prompt(cls, description: str) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for symptom extraction."""
        user_prompt = f"Problem Description:\n\"\"\"{description.strip()}\"\"\"\n\nExtract observations and user hypotheses into JSON:"
        return cls.SYMPTOM_EXTRACTION_SYSTEM, user_prompt

    # -----------------------------------------------------------------------
    # 2. Diagnosis Explanation
    # -----------------------------------------------------------------------

    DIAGNOSIS_EXPLANATION_SYSTEM = """You are an explainable AI assistant for an industrial fluid dispensing defect detective system.
Your task is to convert deterministic diagnostic engine results into a clear, professional, technician-friendly explanation.

CRITICAL SAFETY & INTEGRITY RULES:
1. You MUST NOT invent, calculate, or alter any numerical scores. Use the exact score provided.
2. You MUST NOT invent troubleshooting procedures or sources that are not in the provided input.
3. You MUST NOT declare any root cause confirmed unless the input explicitly marks it as confirmed.
4. You MUST NOT declare the dispensing defect or issue resolved.
5. Clearly distinguish supporting evidence from contradicting evidence and missing evidence.
6. Emphasize that unverified causes remain hypotheses.
7. Respect evidence provenance tags (e.g. [IMAGE], [USER], [USER_CHECK_RESULT]) and never invent image sources, raw image bytes, or file paths."""

    @classmethod
    def get_diagnosis_explanation_prompt(
        cls,
        top_cause_name: str | None,
        top_cause_score: float | None,
        supporting_evidence: list[str],
        contradicting_evidence: list[str],
        missing_evidence: list[str],
        confirmed_causes: list[str] | None = None,
        recommended_action: str | None = None,
        recommended_question: str | None = None,
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for explaining diagnosis results."""
        context_payload = {
            "top_candidate_cause": top_cause_name,
            "evidence_support_score": f"{top_cause_score:.0f}/100" if top_cause_score is not None else None,
            "confirmed_causes": confirmed_causes or [],
            "supporting_evidence": supporting_evidence,
            "contradicting_evidence": contradicting_evidence,
            "missing_evidence": missing_evidence,
            "recommended_action": recommended_action,
            "recommended_question": recommended_question,
        }
        user_prompt = (
            "Provide a concise, factual 2-3 paragraph explanation of the current diagnostic evaluation "
            "based strictly on this structured data:\n"
            f"{json.dumps(context_payload, indent=2)}\n\n"
            "Format clearly with sections for Findings, Evidence Analysis, and Next Recommended Step."
        )
        return cls.DIAGNOSIS_EXPLANATION_SYSTEM, user_prompt

    # -----------------------------------------------------------------------
    # 3. Revision Score Change Explanation
    # -----------------------------------------------------------------------

    SCORE_CHANGE_SYSTEM = """You are an industrial dispensing diagnostic assistant explaining how new evidence changed the diagnostic ranking between revisions.

CRITICAL RULES:
1. Rely strictly on the provided score differences and evidence updates.
2. Explain clearly why a cause was upgraded or downgraded.
3. Never claim an unconfirmed cause is confirmed.
4. Keep the explanation concise and actionable for maintenance technicians."""

    @classmethod
    def get_score_change_prompt(
        cls,
        revision_from: int,
        revision_to: int,
        changes: list[str],
        new_evidence: list[str],
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for explaining revision differences."""
        payload = {
            "from_revision": revision_from,
            "to_revision": revision_to,
            "rank_and_score_changes": changes,
            "new_evidence_collected": new_evidence,
        }
        user_prompt = (
            f"Explain what changed between Revision {revision_from} and Revision {revision_to} "
            f"given the following updates:\n{json.dumps(payload, indent=2)}"
        )
        return cls.SCORE_CHANGE_SYSTEM, user_prompt

    # -----------------------------------------------------------------------
    # 4. Case Summary
    # -----------------------------------------------------------------------

    CASE_SUMMARY_SYSTEM = """You are an industrial diagnostic reporting assistant.
Your task is to generate a comprehensive case summary for maintenance records and engineering handover.

CRITICAL RULES:
1. Summarize the initial symptom, observations and evidence, checks conducted, findings, and current state.
2. If the issue is UNRESOLVED, clearly state that the issue is unresolved.
3. Do not invent details not present in the record."""

    @classmethod
    def project_safe_observations(cls, raw_observations: list[Any]) -> list[dict[str, Any]]:
        """Project raw/persisted observations into bounded text-only representation.

        Includes only:
        - observation_type
        - normalized value
        - evidence source
        - confidence (when present)
        - first-seen revision
        - safe image-analysis provenance (mode, status, roi_id, comparison basis)

        Strictly excludes raw bytes, base64 data, filesystem paths, and secrets.
        """
        allowed_provenance_keys = {
            "mode",
            "status",
            "roi_id",
            "comparison_basis",
            "coverage_ratio",
            "overflow_ratio",
            "calibrated_diameter_mm",
            "segmentation_quality",
            "min_coverage_ratio",
            "max_coverage_ratio",
            "min_presence_ratio",
            "max_overflow_ratio",
        }

        max_projected_observations = 50
        max_type_length = 64
        max_value_length = 200
        max_source_length = 64

        def _is_safe_text(val: Any, max_len: int = 200) -> bool:
            if not isinstance(val, str):
                return False
            cleaned = val.strip()
            if not cleaned or len(cleaned) > max_len:
                return False
            lower = cleaned.lower()
            # Reject secret/credential markers
            if any(s in lower for s in ("secret", "password", "token", "api_key", "bearer", "credential")):
                return False
            # Reject base64 or data URLs
            if "base64" in lower or "data:image" in lower:
                return False
            # Reject local filesystem paths and file URLs
            if "\\" in cleaned or "/" in cleaned or ":\\" in cleaned or ":/" in cleaned:
                return False
            if lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp", ".tmp")):
                return False
            return True

        def _sanitize_val(val: Any) -> Any:
            if isinstance(val, (int, float, bool)):
                return val
            if isinstance(val, str):
                return val.strip() if _is_safe_text(val, max_len=max_value_length) else None
            if isinstance(val, dict):
                cleaned: dict[str, Any] = {}
                for k, v in val.items():
                    if (
                        isinstance(k, str)
                        and _is_safe_text(k, max_len=max_type_length)
                        and not any(s in k.lower() for s in ("path", "secret", "file", "token", "key"))
                    ):
                        clean_v = _sanitize_val(v)
                        if clean_v is not None:
                            cleaned[k] = clean_v
                return cleaned if cleaned else None
            return None

        projected: list[dict[str, Any]] = []
        for obs in raw_observations or []:
            if len(projected) >= max_projected_observations:
                break

            # 1. Observation Type (must be bounded, non-blank safe string)
            obs_type = getattr(obs, "observation_type", None) or getattr(obs, "type", None)
            if obs_type is None and isinstance(obs, dict):
                obs_type = obs.get("observation_type") or obs.get("type")
            if hasattr(obs_type, "value"):
                obs_type = obs_type.value
            if not isinstance(obs_type, str) or not _is_safe_text(obs_type, max_len=max_type_length):
                continue
            obs_type_str = obs_type.strip()

            # 2. Value (must pass the same safety policy and length limit; reject raw bytes/paths/secrets/base64)
            val = getattr(obs, "value", None)
            if val is None and isinstance(obs, dict):
                val = obs.get("value")
            if isinstance(val, (bytes, bytearray)):
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                val_str = str(val)
            elif isinstance(val, str):
                val_str = val.strip()
            else:
                continue

            if not _is_safe_text(val_str, max_len=max_value_length):
                continue

            # 3. Source (must be bounded, non-blank safe string)
            src = getattr(obs, "source", None) or getattr(obs, "provenance", None)
            if src is None and isinstance(obs, dict):
                src = obs.get("source") or obs.get("provenance")
            if hasattr(src, "value"):
                src = src.value
            if not isinstance(src, str) or not _is_safe_text(src, max_len=max_source_length):
                continue
            src_str = src.strip()

            # 4. Confidence
            conf = getattr(obs, "confidence", None)
            if conf is None and isinstance(obs, dict):
                conf = obs.get("confidence")
            conf_val: float | None = None
            if conf is not None:
                try:
                    conf_val = round(float(conf), 4)
                except (ValueError, TypeError):
                    conf_val = None

            # 5. First-seen revision
            rev = getattr(obs, "first_seen_revision", None)
            if rev is None and isinstance(obs, dict):
                rev = obs.get("first_seen_revision")
            rev_val: int | None = None
            if rev is not None:
                try:
                    rev_int = int(rev)
                    if rev_int >= 1:
                        rev_val = rev_int
                except (ValueError, TypeError):
                    rev_val = None

            item: dict[str, Any] = {
                "observation_type": obs_type_str,
                "value": val_str,
                "source": src_str,
            }
            if conf_val is not None:
                item["confidence"] = conf_val
            if rev_val is not None:
                item["first_seen_revision"] = rev_val

            # 6. Safe Provenance
            meta = (
                getattr(obs, "observation_metadata", None)
                or getattr(obs, "metadata", None)
                or (
                    obs.get("metadata") or obs.get("observation_metadata") or obs.get("provenance")
                    if isinstance(obs, dict)
                    else None
                )
                or {}
            )
            if isinstance(meta, dict):
                safe_prov: dict[str, Any] = {}
                for k, v in meta.items():
                    if k in allowed_provenance_keys:
                        cleaned_v = _sanitize_val(v)
                        if cleaned_v is not None:
                            safe_prov[k] = cleaned_v
                if safe_prov:
                    item["provenance"] = safe_prov

            projected.append(item)

        return projected

    @classmethod
    def get_case_summary_prompt(
        cls,
        case_id: str,
        defect_name: str | None,
        description: str,
        total_revisions: int,
        confirmed_causes: list[str],
        attempted_checks: list[dict[str, Any]],
        issue_condition: str,
        observations: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for summarizing a diagnostic case."""
        payload: dict[str, Any] = {
            "case_id": case_id,
            "defect_name": defect_name,
            "initial_problem": description,
            "revisions_count": total_revisions,
            "confirmed_causes": confirmed_causes,
            "attempted_checks": attempted_checks,
            "final_issue_condition": issue_condition,
        }
        if observations:
            payload["observations"] = observations
        user_prompt = (
            "Generate a professional, structured case summary for technician records based on:\n"
            f"{json.dumps(payload, indent=2)}"
        )
        return cls.CASE_SUMMARY_SYSTEM, user_prompt
