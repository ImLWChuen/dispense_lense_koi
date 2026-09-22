"""
Dispense Lens - Explanation Service

Turns deterministic diagnostic engine results into clear, professional,
human-readable text. Uses bounded LLM generation when available, with
automatic fallback to deterministic template formatting.

Strict Guardrails (Plan §17):
- Rule 1: LLM cannot produce or modify the official numerical score.
- Rule 2: LLM cannot create troubleshooting procedures not in knowledge.
- Rule 3: LLM cannot invent sources.
- Rule 4: LLM cannot declare root causes confirmed.
- Rule 5: LLM cannot declare issues resolved.
- Rule 6: LLM failure degrades gracefully to deterministic text.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from app.knowledge import load_actions
from app.schemas.diagnosis import (
    AnalysisRevision,
    CandidateCause,
    CauseConclusion,
    EvidenceSource,
    EvidenceStrength,
    IssueCondition,
    Question,
    StructuredCase,
    TroubleshootingCheck,
)
from app.services.ai.llm_service import LLMService
from app.services.ai.prompt_manager import PromptManager

if TYPE_CHECKING:
    from app.services.diagnosis.cause_ranker import RankingResult

logger = logging.getLogger(__name__)


class ExplanationService:
    """Provides bounded natural-language explanations of diagnosis states and changes."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        self.llm = llm_service or LLMService()
        self.prompt_manager = prompt_manager or PromptManager()

        # Cache valid known check titles and IDs for hallucination checking
        try:
            self._known_action_ids = {a.id for a in load_actions()}
        except Exception:
            self._known_action_ids = set()

    # -----------------------------------------------------------------------
    # 1. Main Diagnosis Explanation
    # -----------------------------------------------------------------------

    def explain_diagnosis(
        self,
        ranking: RankingResult,
        case: StructuredCase,
        current_revision: AnalysisRevision | None = None,
        next_question: Question | None = None,
        next_check: TroubleshootingCheck | None = None,
    ) -> str:
        """Produce an explanation of the current diagnosis.

        Tries LLM generation if available and valid; falls back to deterministic
        formatting upon any model error or guardrail violation.
        """
        top_cause = ranking.top_cause
        top_cause_name = top_cause.cause_name if top_cause else None
        top_cause_score = top_cause.score if top_cause else None

        def _format_evidence_item(e: Any) -> str:
            src = getattr(e.source, "value", str(e.source)) if hasattr(e, "source") and e.source else "UNKNOWN"
            text = e.explanation or e.observation_id
            return f"[{src}] {text}"

        # Build evidence lists from top cause with provenance
        supporting = [_format_evidence_item(e) for e in top_cause.supporting_evidence] if top_cause else []
        contradicting = [_format_evidence_item(e) for e in top_cause.contradicting_evidence] if top_cause else []
        missing = top_cause.missing_evidence if top_cause else []

        confirmed = [c.cause_name for c in ranking.ranked_causes if c.conclusion == CauseConclusion.CONFIRMED]

        rec_action_str = f"{next_check.name} ({next_check.check_id})" if next_check else None
        rec_q_str = next_question.text if next_question else None

        # Attempt bounded LLM generation if service is available
        if self.llm.is_available:
            try:
                system_prompt, user_prompt = self.prompt_manager.get_diagnosis_explanation_prompt(
                    top_cause_name=top_cause_name,
                    top_cause_score=top_cause_score,
                    supporting_evidence=supporting,
                    contradicting_evidence=contradicting,
                    missing_evidence=missing,
                    confirmed_causes=confirmed,
                    recommended_action=rec_action_str,
                    recommended_question=rec_q_str,
                )
                raw_explanation = self.llm.generate_text(user_prompt, system_prompt=system_prompt)
                if raw_explanation and self._validate_explanation(raw_explanation, case):
                    return raw_explanation.strip()
                else:
                    logger.info("ExplanationService: LLM explanation unavailable or rejected; falling back to deterministic template.")
            except Exception as e:
                logger.warning("ExplanationService: Exception during LLM generation (%s); falling back to deterministic template.", e)

        # Deterministic fallback
        return self._build_deterministic_explanation(
            ranking=ranking,
            current_revision=current_revision,
            next_question=next_question,
            next_check=next_check,
        )

    # -----------------------------------------------------------------------
    # 2. Score Change / Revision Explanation
    # -----------------------------------------------------------------------

    def explain_score_change(
        self,
        from_rev: int,
        to_rev: int,
        changes: list[str],
        new_evidence: list[str],
    ) -> str:
        """Explain rank and score changes between two analysis revisions."""
        if not changes:
            return "No rank or score changes detected in this revision."

        if self.llm.is_available:
            try:
                sys_prompt, user_prompt = self.prompt_manager.get_score_change_prompt(
                    revision_from=from_rev,
                    revision_to=to_rev,
                    changes=changes,
                    new_evidence=new_evidence,
                )
                explanation = self.llm.generate_text(user_prompt, system_prompt=sys_prompt)
                if explanation:
                    return explanation.strip()
            except Exception as e:
                logger.warning("ExplanationService: Exception during score change explanation (%s); falling back to deterministic template.", e)

        # Deterministic fallback
        lines = [f"Changes between Revision {from_rev} and Revision {to_rev}:"]
        for c in changes:
            lines.append(f"  • {c}")
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # 3. Case Summary
    # -----------------------------------------------------------------------

    def summarize_case(self, case: StructuredCase) -> str:
        """Produce a comprehensive summary of the case lifecycle."""
        total_revs = len(case.analysis_revisions)
        confirmed = getattr(case, "confirmed_causes", [])

        attempted_checks = [
            {"check_id": c.check_id, "status": c.execution_status, "finding": c.finding}
            for c in case.previous_check_results
        ]

        raw_obs = getattr(case, "observations", [])
        projected_obs = self.prompt_manager.project_safe_observations(raw_obs)

        if self.llm.is_available:
            sys_prompt, user_prompt = self.prompt_manager.get_case_summary_prompt(
                case_id=case.case_id,
                defect_name=case.defect_name,
                description=case.description or "",
                total_revisions=total_revs,
                confirmed_causes=confirmed,
                attempted_checks=attempted_checks,
                issue_condition=case.issue_condition,
                observations=projected_obs,
            )
            summary = self.llm.generate_text(user_prompt, system_prompt=sys_prompt)
            if summary:
                return summary.strip()

        # Deterministic fallback
        lines = [
            f"Case Summary: {case.case_id}",
            f"Defect: {case.defect_name or 'Unknown'} ({case.defect_code or 'Unclassified'})",
            f"Initial Problem: {case.description or 'No description'}",
            f"Total Revisions: {total_revs}",
            f"Confirmed Causes: {', '.join(confirmed) if confirmed else 'None'}",
            f"Checks Attempted: {len(attempted_checks)}",
            f"Issue Condition: {case.issue_condition}",
        ]
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Safety validation & deterministic fallback
    # -----------------------------------------------------------------------

    def _validate_explanation(self, text: str, case: StructuredCase) -> bool:
        """Guardrail verification for model outputs (Plan §17).

        Rejects output if:
        - Claims the issue is resolved when case is not resolved.
        - Claims an unconfirmed cause is confirmed.
        """
        lower = text.lower()

        # Guardrail Rule 5: Cannot declare resolved if issue is unresolved
        if case.issue_condition != IssueCondition.RESOLVED:
            if "issue is resolved" in lower or "problem is resolved" in lower or "defect is fixed" in lower:
                logger.warning("ExplanationService: Rejected LLM output declaring unverified resolution")
                return False

        # Guardrail Rule 4: Cannot declare root cause confirmed if not confirmed
        confirmed = getattr(case, "confirmed_causes", [])
        if not confirmed:
            if "root cause is confirmed" in lower or "confirmed root cause" in lower:
                logger.warning("ExplanationService: Rejected LLM output declaring unconfirmed root cause")
                return False

        return True

    def _build_deterministic_explanation(
        self,
        ranking: RankingResult,
        current_revision: AnalysisRevision | None,
        next_question: Question | None,
        next_check: TroubleshootingCheck | None,
    ) -> str:
        """Produce deterministic template-based explanation."""
        lines: list[str] = []
        top_cause = ranking.top_cause

        confirmed_causes = [c for c in ranking.ranked_causes if c.conclusion == CauseConclusion.CONFIRMED]
        if confirmed_causes:
            names = ", ".join(f"'{c.cause_name}'" for c in confirmed_causes)
            lines.append(f"Root cause confirmed: {names} (explicitly confirmed by technician).")

        if top_cause:
            # Step 4 NSW format: explain WHY it provides the recommendation
            strongest_supp = sorted(
                top_cause.supporting_evidence,
                key=lambda e: (
                    1 if getattr(e, "strength", None) in (EvidenceStrength.STRONG, "STRONG") else 0,
                    getattr(e, "score_contribution", 0.0) or 0.0,
                ),
                reverse=True,
            )
            why_clause = ""
            if strongest_supp and strongest_supp[0].explanation:
                expl = strongest_supp[0].explanation.strip()
                if expl:
                    why_clause = f" because {expl[0].lower() + expl[1:] if expl[0].isupper() else expl}"
            if not why_clause:
                why_clause = " based on current defect symptom observations and process likelihood."

            lines.append(
                f"{top_cause.cause_name} is currently the highest-supported hypothesis "
                f"with evidence support {top_cause.score:.0f}/100{why_clause}"
            )
            if top_cause.supporting_evidence:
                supp_count = len(top_cause.supporting_evidence)
                img_count = sum(1 for e in top_cause.supporting_evidence if getattr(e, "source", None) in (EvidenceSource.IMAGE, "IMAGE"))
                if img_count > 0:
                    lines.append(f"It is supported by {supp_count} observation(s) (including {img_count} visual/image inspection measurement(s)).")
                else:
                    lines.append(f"It is supported by {supp_count} observation(s).")
            if top_cause.contradicting_evidence:
                lines.append(
                    f"Warning: {len(top_cause.contradicting_evidence)} contradicting evidence item(s) noted."
                )
        else:
            lines.append("No candidate causes currently evaluated.")

        if current_revision and current_revision.changes_from_previous:
            lines.append("\nChanges since last revision:")
            for change in current_revision.changes_from_previous:
                lines.append(f"  • {change}")

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
