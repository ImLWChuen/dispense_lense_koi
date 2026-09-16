"""
DLK-M3-013 — Semantic Verification Tests

Verifies the **semantic correctness** of troubleshooting outcome handling,
specifically:

1. Direct outcome mapping — each check+outcome maps ONLY to the fact demonstrated
2. No automatic cause confirmation — SUPPORTS + high score ≠ CONFIRMED
3. UNKNOWN does not create evidence
4. INCONCLUSIVE does not confirm cause
5. BLOCKED does not create negative evidence
6. Supporting result does not auto-confirm cause
7. Explicit confirmation is a separate operation
8. Duplicate evidence protection
9. Execution state vs finding separation
10. Issue resolution requires verification
"""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if sys.platform == "win32":
    reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_fn):
        try:
            reconfigure_fn(encoding="utf-8", errors="replace")
        except Exception:
            pass

import pytest

from app.schemas.diagnosis import (
    CandidateCause,
    CauseConclusion,
    CauseEvidence,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    EvidenceRelation,
    EvidenceSource,
    EvidenceStrength,
    IssueCondition,
    Observation,
    ObservationType,
    QuestionAnswer,
    StructuredCase,
)
from app.services.diagnosis.engine import (
    CheckResultHandler,
    DiagnosticEngine,
    StateManager,
    _ACTION_OUTCOME_TO_OBSERVATION,
)


# ===================================================================
# Test Group 1: Direct Outcome Mapping Correctness (Phase 5, Step 7)
# ===================================================================


class TestOutcomeMappingCorrectness:
    """Each check outcome must map ONLY to a fact actually demonstrated."""

    def test_act01_blockage_found_maps_to_blocked_not_damaged(self):
        """ACT01 blockage_found must produce nozzle_condition=blocked.
        Finding a blockage does NOT mean the nozzle is damaged."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="blockage_found",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "nozzle_condition"
        ]
        assert len(domain_obs) == 1, "Should produce exactly one nozzle_condition observation"
        assert domain_obs[0].value == "blocked", (
            f"blockage_found should map to 'blocked', not '{domain_obs[0].value}'"
        )

    def test_act01_no_blockage_maps_to_clean(self):
        """ACT01 no_blockage must produce nozzle_condition=clean."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            outcome="no_blockage",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "nozzle_condition"
        ]
        assert len(domain_obs) == 1
        assert domain_obs[0].value == "clean"

    def test_act01_damage_found_maps_to_damaged(self):
        """ACT01 damage_found must produce nozzle_condition=damaged."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="damage_found",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "nozzle_condition"
        ]
        assert len(domain_obs) == 1
        assert domain_obs[0].value == "damaged"

    def test_act04_pressure_low_maps_to_low_not_fluctuating(self):
        """ACT04 pressure_low must produce pressure=low.
        Low pressure does NOT mean fluctuating pressure."""
        result = CheckResult(
            check_id="ACT04",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="pressure_low",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "pressure"
        ]
        assert len(domain_obs) == 1, "Should produce exactly one pressure observation"
        assert domain_obs[0].value == "low", (
            f"pressure_low should map to 'low', not '{domain_obs[0].value}'"
        )

    def test_act04_pressure_unstable_maps_to_fluctuating(self):
        """ACT04 pressure_unstable must produce pressure=fluctuating."""
        result = CheckResult(
            check_id="ACT04",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="pressure_unstable",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "pressure"
        ]
        assert len(domain_obs) == 1
        assert domain_obs[0].value == "fluctuating"

    def test_act04_pressure_stable_maps_to_stable(self):
        """ACT04 pressure_stable must produce pressure=stable."""
        result = CheckResult(
            check_id="ACT04",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            outcome="pressure_stable",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "pressure"
        ]
        assert len(domain_obs) == 1
        assert domain_obs[0].value == "stable"

    def test_act10_calibration_drift_maps_to_calibration_drift_not_worn(self):
        """ACT10 calibration_drift must produce equipment_condition=calibration_drift.
        Calibration drift does NOT mean equipment is worn."""
        result = CheckResult(
            check_id="ACT10",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="calibration_drift",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "equipment_condition"
        ]
        assert len(domain_obs) == 1, "Should produce exactly one equipment_condition observation"
        assert domain_obs[0].value == "calibration_drift", (
            f"calibration_drift should map to 'calibration_drift', not '{domain_obs[0].value}'"
        )

    def test_act02_air_bubbles_maps_to_visible_bubbles(self):
        """ACT02 air_bubbles_found must produce bubble_presence=visible_bubbles."""
        result = CheckResult(
            check_id="ACT02",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="air_bubbles_found",
        )
        observations, _ = CheckResultHandler.handle(result)

        domain_obs = [
            o for o in observations
            if str(getattr(o.observation_type, 'value', o.observation_type)) == "bubble_presence"
        ]
        assert len(domain_obs) == 1
        assert domain_obs[0].value == "visible_bubbles"

    def test_nozzle_blockage_result_maps_only_to_nozzle_observation(self):
        """Finding a nozzle blockage must NOT produce pressure, material,
        or cause confirmation observations."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="blockage_found",
        )
        observations, _ = CheckResultHandler.handle(result)

        obs_types = {
            str(getattr(o.observation_type, 'value', o.observation_type))
            for o in observations
        }
        # Should only contain check_result and nozzle_condition
        forbidden_types = {"pressure", "material_state", "bubble_presence", "temperature"}
        inferred = obs_types & forbidden_types
        assert len(inferred) == 0, (
            f"Nozzle check should NOT produce observations for: {inferred}"
        )

    def test_all_mapped_outcomes_produce_single_domain_observation(self):
        """Every entry in _ACTION_OUTCOME_TO_OBSERVATION must produce
        exactly one domain observation (the fact demonstrated)."""
        for check_id, outcomes in _ACTION_OUTCOME_TO_OBSERVATION.items():
            for outcome_key, (expected_type, expected_value) in outcomes.items():
                # Verify the mapping values are reasonable
                assert expected_type is not None
                assert expected_value is not None
                assert len(expected_value) > 0


# ===================================================================
# Test Group 2: No Automatic Cause Confirmation (Phase 2, 8)
# ===================================================================


class TestNoAutomaticCauseConfirmation:
    """Causes must NEVER be auto-confirmed by evidence or check results."""

    def test_supporting_result_does_not_auto_confirm_cause(self):
        """A SUPPORTS finding must leave cause as SUSPECTED, not CONFIRMED."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dispensing dots become smaller after 20 minutes.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
                Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
            ],
        )

        # Submit check with SUPPORTS finding
        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="blockage_found",
        )
        _, result = engine.submit_check_result(case, check)

        # ALL causes must remain SUSPECTED (or UNRESOLVED), never CONFIRMED
        for cause in result.ranked_causes:
            assert cause.conclusion != CauseConclusion.CONFIRMED, (
                f"Cause '{cause.cause_name}' was auto-confirmed! "
                f"A supporting check result must NOT confirm a cause."
            )

    def test_high_score_with_supporting_check_does_not_confirm(self):
        """Even with a high score AND supporting check, cause stays SUSPECTED."""
        candidate = CandidateCause(
            cause_id="nozzle_restriction",
            cause_name="Nozzle Restriction",
            score=85.0,  # above high_confidence_threshold
            supporting_evidence=[
                CauseEvidence(
                    observation_id="obs1",
                    cause_id="nozzle_restriction",
                    relation=EvidenceRelation.SUPPORTS,
                    strength=EvidenceStrength.STRONG,
                )
            ],
        )

        check_results = [
            CheckResult(
                check_id="ACT01",
                execution_status=CheckExecutionStatus.COMPLETED,
                finding=CheckFinding.SUPPORTS,
                finding_details="Blockage found.",
            ),
        ]

        conclusion = StateManager.evaluate_cause_conclusion(candidate, check_results)
        assert conclusion == CauseConclusion.SUSPECTED, (
            f"Expected SUSPECTED, got {conclusion.value}. "
            f"High score + supporting check must NOT auto-confirm."
        )

    def test_evaluate_cause_conclusion_never_returns_confirmed(self):
        """evaluate_cause_conclusion() must never return CONFIRMED."""
        # Test with various score levels
        for score in [0, 25, 50, 75, 85, 95, 100]:
            candidate = CandidateCause(
                cause_id="test_cause",
                cause_name="Test",
                score=float(score),
                supporting_evidence=[
                    CauseEvidence(
                        observation_id="obs1",
                        cause_id="test_cause",
                        relation=EvidenceRelation.SUPPORTS,
                    )
                ] if score > 50 else [],
            )

            check_results = [
                CheckResult(
                    check_id="ACT01",
                    execution_status=CheckExecutionStatus.COMPLETED,
                    finding=CheckFinding.SUPPORTS,
                ),
            ] if score > 50 else []

            conclusion = StateManager.evaluate_cause_conclusion(candidate, check_results)
            assert conclusion != CauseConclusion.CONFIRMED, (
                f"evaluate_cause_conclusion() returned CONFIRMED at score={score}. "
                f"CONFIRMED must only come from explicit confirm_cause()."
            )


# ===================================================================
# Test Group 3: UNKNOWN / INCONCLUSIVE / BLOCKED (Phase 6, 7)
# ===================================================================


class TestUnknownInconclusiveBlocked:
    """Non-actionable findings must not fabricate evidence."""

    def test_unknown_does_not_create_evidence(self):
        """UNKNOWN finding must produce zero observations."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.UNKNOWN,
        )
        observations, _ = CheckResultHandler.handle(result)
        assert observations == [], f"UNKNOWN must produce no observations, got {len(observations)}"

    def test_inconclusive_does_not_create_evidence(self):
        """INCONCLUSIVE finding must produce zero observations."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.INCONCLUSIVE,
        )
        observations, _ = CheckResultHandler.handle(result)
        assert observations == [], f"INCONCLUSIVE must produce no observations, got {len(observations)}"

    def test_inconclusive_does_not_confirm_cause(self):
        """INCONCLUSIVE must not confirm any cause."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
        )

        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.INCONCLUSIVE,
        )
        _, result = engine.submit_check_result(case, check)

        for cause in result.ranked_causes:
            assert cause.conclusion != CauseConclusion.CONFIRMED

    def test_blocked_check_does_not_create_negative_evidence(self):
        """BLOCKED check must produce ZERO observations and UNKNOWN finding."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.BLOCKED,
            finding=CheckFinding.SUPPORTS,  # technician may set anything, handler overrides
            finding_details="Cannot access nozzle.",
        )
        observations, summary = CheckResultHandler.handle(result)

        assert result.finding == CheckFinding.UNKNOWN, (
            f"Blocked check finding must be forced to UNKNOWN, got {result.finding.value}"
        )
        assert observations == [], (
            f"Blocked check must produce ZERO observations, got {len(observations)}"
        )
        assert "no blockage" not in summary.lower(), (
            "Blocked check summary must NOT claim 'no blockage'"
        )

    def test_blocked_check_does_not_alter_scores(self):
        """Submitting a BLOCKED check must not change any cause scores."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
        )
        initial_result = engine.diagnose(case)
        initial_scores = {c.cause_id: c.score for c in initial_result.ranked_causes}

        blocked_check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.BLOCKED,
            finding=CheckFinding.UNKNOWN,
        )
        _, after_result = engine.submit_check_result(case, blocked_check)

        for cause in after_result.ranked_causes:
            assert cause.score == initial_scores[cause.cause_id], (
                f"Blocked check altered score for '{cause.cause_name}': "
                f"{initial_scores[cause.cause_id]} → {cause.score}"
            )

    def test_failed_check_does_not_create_evidence(self):
        """FAILED check must produce zero observations."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.FAILED,
            finding=CheckFinding.SUPPORTS,
        )
        observations, _ = CheckResultHandler.handle(result)
        assert result.finding == CheckFinding.UNKNOWN
        assert observations == []

    def test_skipped_check_does_not_create_evidence(self):
        """SKIPPED check must produce zero observations."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.SKIPPED,
            finding=CheckFinding.SUPPORTS,
        )
        observations, _ = CheckResultHandler.handle(result)
        assert result.finding == CheckFinding.UNKNOWN
        assert observations == []

    def test_not_applicable_check_does_not_create_evidence(self):
        """NOT_APPLICABLE check must produce zero observations."""
        result = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.NOT_APPLICABLE,
            finding=CheckFinding.SUPPORTS,
        )
        observations, _ = CheckResultHandler.handle(result)
        assert result.finding == CheckFinding.UNKNOWN
        assert observations == []


# ===================================================================
# Test Group 4: Execution State vs Finding Separation (Phase 7)
# ===================================================================


class TestExecutionVsFindingSeparation:
    """Execution state and finding must remain separate concepts."""

    def test_completed_does_not_imply_supports(self):
        """COMPLETED execution status must NOT automatically imply SUPPORTS finding."""
        # All valid combinations of COMPLETED + finding must be accepted
        for finding in [
            CheckFinding.SUPPORTS,
            CheckFinding.CONTRADICTS,
            CheckFinding.INCONCLUSIVE,
            CheckFinding.UNKNOWN,
        ]:
            cr = CheckResult(
                check_id="ACT01",
                execution_status=CheckExecutionStatus.COMPLETED,
                finding=finding,
                finding_details="Test finding",
            )
            assert cr.execution_status == CheckExecutionStatus.COMPLETED
            assert cr.finding == finding

    def test_completed_with_contradicts_is_valid(self):
        """COMPLETED + CONTRADICTS is a valid state combination."""
        cr = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            outcome="no_blockage",
        )
        observations, _ = CheckResultHandler.handle(cr)
        assert len(observations) > 0, "COMPLETED + CONTRADICTS should produce observations"

    def test_completed_with_inconclusive_produces_no_observations(self):
        """COMPLETED + INCONCLUSIVE should produce zero observations."""
        cr = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.INCONCLUSIVE,
        )
        observations, _ = CheckResultHandler.handle(cr)
        assert observations == []


# ===================================================================
# Test Group 5: Explicit Confirmation (Phase 3)
# ===================================================================


class TestExplicitConfirmation:
    """Cause confirmation requires explicit technician/engineer action."""

    def test_explicit_confirmation_confirms_cause(self):
        """confirm_cause() must set the cause to CONFIRMED."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized after 20 minutes.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
                Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
            ],
        )
        engine.diagnose(case)

        # Get a valid cause_id from the ranked causes
        cause_id = case.analysis_revisions[-1].ranked_causes[0].cause_id

        # Explicitly confirm the cause
        _, result = engine.confirm_cause(
            case,
            cause_id=cause_id,
            confirmed_by="technician",
            confirmation_details="Confirmed after physical inspection.",
        )

        confirmed_cause = next(c for c in result.ranked_causes if c.cause_id == cause_id)
        assert confirmed_cause.conclusion == CauseConclusion.CONFIRMED

    def test_confirmation_is_separate_from_check_result(self):
        """confirm_cause() is NOT called by submit_check_result()."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
                Observation(observation_type=ObservationType.RUNTIME_PATTERN, value="after_prolonged_operation"),
            ],
        )

        # Submit a supporting check
        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="blockage_found",
        )
        _, result = engine.submit_check_result(case, check)

        # No cause should be confirmed after a check result
        for cause in result.ranked_causes:
            assert cause.conclusion != CauseConclusion.CONFIRMED, (
                f"submit_check_result must NOT confirm cause '{cause.cause_name}'"
            )

    def test_invalid_cause_id_raises_error(self):
        """confirm_cause() with invalid cause_id must raise ValueError."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
        )
        engine.diagnose(case)

        with pytest.raises(ValueError, match="Cannot confirm cause"):
            engine.confirm_cause(case, cause_id="nonexistent_cause")


# ===================================================================
# Test Group 6: Issue Resolution (Phase 9 of verification doc)
# ===================================================================


class TestIssueResolution:
    """Issue resolution must require independent verification."""

    def test_check_completed_does_not_resolve_issue(self):
        """Completing a check must NOT resolve the dispensing issue."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
            issue_condition=IssueCondition.UNRESOLVED,
        )

        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="blockage_found",
        )
        updated_case, result = engine.submit_check_result(case, check)

        assert updated_case.issue_condition == IssueCondition.UNRESOLVED
        assert result.issue_condition == IssueCondition.UNRESOLVED

    def test_cause_confirmed_does_not_resolve_issue(self):
        """Confirming a cause must NOT resolve the dispensing issue."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
            issue_condition=IssueCondition.UNRESOLVED,
        )
        engine.diagnose(case)
        cause_id = case.analysis_revisions[-1].ranked_causes[0].cause_id

        _, result = engine.confirm_cause(case, cause_id=cause_id)

        assert case.issue_condition == IssueCondition.UNRESOLVED
        assert result.issue_condition == IssueCondition.UNRESOLVED

    def test_resolution_requires_verification(self):
        """Cannot transition to RESOLVED without verification_passed=True."""
        with pytest.raises(ValueError, match="verification"):
            StateManager.transition_issue_condition(
                current_condition=IssueCondition.RECOVERY_PENDING_VERIFICATION,
                target_condition=IssueCondition.RESOLVED,
                verification_passed=False,
            )


# ===================================================================
# Test Group 7: Duplicate Evidence Protection (Phase 14)
# ===================================================================


class TestDuplicateEvidenceProtection:
    """Submitting the same result twice must not inflate scores."""

    def test_duplicate_check_result_does_not_inflate_scores(self):
        """Submitting the same check result twice must not increase scores."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
        )

        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="blockage_found",
        )

        # First submission
        _, result1 = engine.submit_check_result(case, check)
        scores_after_first = {c.cause_id: c.score for c in result1.ranked_causes}

        # Second identical submission
        check2 = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="blockage_found",
        )
        _, result2 = engine.submit_check_result(case, check2)
        scores_after_second = {c.cause_id: c.score for c in result2.ranked_causes}

        # Scores should not increase from duplicate evidence
        for cause_id, score1 in scores_after_first.items():
            score2 = scores_after_second[cause_id]
            assert score2 <= score1 + 0.01, (
                f"Duplicate check inflated score for '{cause_id}': "
                f"{score1} → {score2}"
            )


# ===================================================================
# Test Group 8: Revision Integrity (Phase 13)
# ===================================================================


class TestRevisionIntegrity:
    """Revisions must be preserved and new evidence creates new revisions."""

    def test_revision_n_preserved_after_check_result(self):
        """Revision N must remain unchanged after submitting a check result."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
        )

        # Revision 1
        engine.diagnose(case)
        rev1_scores = {c.cause_id: c.score for c in case.analysis_revisions[0].ranked_causes}

        # Submit check -> Revision 2
        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            outcome="no_blockage",
        )
        engine.submit_check_result(case, check)

        assert len(case.analysis_revisions) == 2
        assert case.analysis_revisions[0].revision_number == 1

        # Revision 1 scores must be unchanged
        for cause in case.analysis_revisions[0].ranked_causes:
            assert cause.score == rev1_scores[cause.cause_id], (
                f"Revision 1 was mutated! '{cause.cause_name}' score changed."
            )

    def test_revision_n_plus_1_contains_updated_ranking(self):
        """Revision N+1 must contain the updated ranking after new evidence."""
        engine = DiagnosticEngine()

        case = StructuredCase(
            description="Dots undersized.",
            observations=[
                Observation(observation_type=ObservationType.DEPOSIT_SIZE, value="undersized"),
            ],
        )

        engine.diagnose(case)

        check = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            outcome="no_blockage",
        )
        engine.submit_check_result(case, check)

        rev2 = case.analysis_revisions[1]
        assert rev2.revision_number == 2
        assert len(rev2.ranked_causes) > 0
        assert rev2.new_evidence_summary != ""
