"""
Unit tests for CheckResultHandler (DLK-M3-013).

Verifies:
1. All 6 execution statuses and 5 findings are supported.
2. Non-executing checks (BLOCKED, FAILED, UNKNOWN, SKIPPED, NOT_APPLICABLE)
   MUST remain UNKNOWN and produce ZERO observations.
3. COMPLETED checks with INCONCLUSIVE / UNKNOWN produce ZERO observations.
4. COMPLETED checks with SUPPORTS / CONTRADICTS produce typed CHECK_RESULT
   observations and domain observations.
5. Negative tests: unknown check ID rejection (ValueError) and invalid outcome rejection (ValueError).
6. Full coverage of all 10 standard troubleshooting checks (ACT01 to ACT10).
"""

import os
import sys
import unittest
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parents[2])
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.schemas.diagnosis import (
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    EvidenceSource,
    ObservationType,
)
from app.services.diagnosis.engine import CheckResultHandler




class TestCheckResultHandler(unittest.TestCase):
    def test_all_statuses_and_findings_instantiation(self):
        """Verify technician can instantiate CheckResult with any status and finding combination."""
        all_statuses = [
            CheckExecutionStatus.PENDING,
            CheckExecutionStatus.IN_PROGRESS,
            CheckExecutionStatus.COMPLETED,
            CheckExecutionStatus.BLOCKED,
            CheckExecutionStatus.FAILED,
            CheckExecutionStatus.UNKNOWN,
            CheckExecutionStatus.NOT_APPLICABLE,
            CheckExecutionStatus.SKIPPED,
        ]
        all_findings = [
            CheckFinding.SUPPORTS,
            CheckFinding.CONTRADICTS,
            CheckFinding.INCONCLUSIVE,
            CheckFinding.UNKNOWN,
            CheckFinding.NOT_APPLICABLE,
        ]
        for status in all_statuses:
            for finding in all_findings:
                cr = CheckResult(
                    check_id="ACT01",
                    execution_status=status,
                    finding=finding,
                )
                self.assertEqual(cr.execution_status, status)
                self.assertEqual(cr.finding, finding)
                self.assertEqual(cr.source, EvidenceSource.USER_CHECK_RESULT)

    def test_non_executing_checks_produce_zero_observations(self):
        """BLOCKED, FAILED, UNKNOWN, SKIPPED, NOT_APPLICABLE must produce 0 observations and remain UNKNOWN."""
        non_executing_statuses = [
            CheckExecutionStatus.BLOCKED,
            CheckExecutionStatus.FAILED,
            CheckExecutionStatus.UNKNOWN,
            CheckExecutionStatus.SKIPPED,
            CheckExecutionStatus.NOT_APPLICABLE,
        ]
        for status in non_executing_statuses:
            cr = CheckResult(
                check_id="ACT01",
                execution_status=status,
                finding=CheckFinding.SUPPORTS,  # Even if caller passes SUPPORTS
                finding_details=f"Machine door locked: {status.value}",
            )
            obs, summary = CheckResultHandler.handle(cr)
            self.assertEqual(len(obs), 0, f"{status} check must produce 0 observations")
            self.assertEqual(cr.finding, CheckFinding.UNKNOWN, f"{status} finding must be forced to UNKNOWN")
            self.assertIn("remains UNKNOWN", summary)
            self.assertNotIn("no blockage", summary.lower())

    def test_completed_inconclusive_or_unknown_produces_zero_observations(self):
        """COMPLETED check with INCONCLUSIVE or UNKNOWN finding must produce ZERO observations."""
        for finding in (CheckFinding.INCONCLUSIVE, CheckFinding.UNKNOWN, CheckFinding.NOT_APPLICABLE):
            cr = CheckResult(
                check_id="ACT01",
                execution_status=CheckExecutionStatus.COMPLETED,
                finding=finding,
                finding_details="Inspection result could not be determined.",
            )
            obs, summary = CheckResultHandler.handle(cr)
            self.assertEqual(len(obs), 0, f"Completed check with {finding} must produce 0 observations")
            self.assertIn(finding.value, summary)

    def test_completed_supports_generates_check_result_and_domain_obs(self):
        """Completed ACT01 check with SUPPORTS generates check_result observation and domain observation."""
        cr = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="Heavy tip blockage found.",
        )
        obs, summary = CheckResultHandler.handle(cr)
        self.assertGreaterEqual(len(obs), 1)

        # Check direct check_result observation
        check_obs = next((o for o in obs if o.observation_type == ObservationType.CHECK_RESULT), None)
        self.assertIsNotNone(check_obs, "Must generate an observation with ObservationType.CHECK_RESULT")
        assert check_obs is not None
        self.assertEqual(check_obs.value, "ACT01:blockage_found")
        self.assertEqual(check_obs.source, EvidenceSource.USER_CHECK_RESULT)

        # Check domain observation
        domain_obs = next((o for o in obs if o.observation_type == ObservationType.NOZZLE_CONDITION), None)
        self.assertIsNotNone(domain_obs)
        assert domain_obs is not None
        self.assertEqual(domain_obs.value, "blocked")  # DLK-M3-013: blockage ≠ damage

        self.assertIn("COMPLETED", summary)
        self.assertIn("SUPPORTS", summary)

    def test_completed_contradicts_generates_check_result_and_domain_obs(self):
        """Completed ACT01 check with CONTRADICTS generates clean nozzle observation."""
        cr = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.CONTRADICTS,
            finding_details="No visible blockage.",
        )
        obs, summary = CheckResultHandler.handle(cr)
        self.assertGreaterEqual(len(obs), 1)

        check_obs = next((o for o in obs if o.observation_type == ObservationType.CHECK_RESULT), None)
        self.assertIsNotNone(check_obs)
        assert check_obs is not None
        self.assertEqual(check_obs.value, "ACT01:no_blockage")

        domain_obs = next((o for o in obs if o.observation_type == ObservationType.NOZZLE_CONDITION), None)
        self.assertIsNotNone(domain_obs)
        assert domain_obs is not None
        self.assertEqual(domain_obs.value, "clean")

    def test_explicit_outcome_field(self):
        """Explicit outcome field overrides or directs outcome resolution."""
        cr = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="damage_found",
        )
        obs, _ = CheckResultHandler.handle(cr)
        check_obs = next((o for o in obs if o.observation_type == ObservationType.CHECK_RESULT), None)
        self.assertIsNotNone(check_obs)
        assert check_obs is not None
        self.assertEqual(check_obs.value, "ACT01:damage_found")

    def test_negative_unknown_check_id(self):
        """Submitting an unknown check_id must raise a controlled ValueError."""
        cr = CheckResult(
            check_id="CHK_UNKNOWN",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
        )
        with self.assertRaises(ValueError) as ctx:
            CheckResultHandler.handle(cr)
        self.assertIn("Unknown check_id 'CHK_UNKNOWN'", str(ctx.exception))

    def test_negative_invalid_outcome_in_field(self):
        """Submitting an invalid outcome in outcome field must raise a controlled ValueError."""
        cr = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            outcome="BLOCKAGE_MAYBE",
        )
        with self.assertRaises(ValueError) as ctx:
            CheckResultHandler.handle(cr)
        self.assertIn("Invalid outcome 'BLOCKAGE_MAYBE'", str(ctx.exception))

    def test_negative_invalid_outcome_in_details(self):
        """Submitting an invalid outcome identifier in finding_details must raise a controlled ValueError."""
        cr = CheckResult(
            check_id="ACT01",
            execution_status=CheckExecutionStatus.COMPLETED,
            finding=CheckFinding.SUPPORTS,
            finding_details="BLOCKAGE_MAYBE",
        )
        with self.assertRaises(ValueError) as ctx:
            CheckResultHandler.handle(cr)
        self.assertIn("Invalid outcome 'BLOCKAGE_MAYBE'", str(ctx.exception))

    def test_all_10_actions_matrix(self):
        """Verify all 10 supported troubleshooting checks (ACT01-ACT10) produce valid observations."""
        test_matrix = [
            ("ACT01", CheckFinding.SUPPORTS, "ACT01:blockage_found"),
            ("ACT01", CheckFinding.CONTRADICTS, "ACT01:no_blockage"),
            ("ACT02", CheckFinding.SUPPORTS, "ACT02:air_bubbles_found"),
            ("ACT02", CheckFinding.CONTRADICTS, "ACT02:material_normal"),
            ("ACT03", CheckFinding.SUPPORTS, "ACT03:high_variation"),
            ("ACT03", CheckFinding.CONTRADICTS, "ACT03:consistent_and_correct"),
            ("ACT04", CheckFinding.SUPPORTS, "ACT04:pressure_unstable"),
            ("ACT04", CheckFinding.CONTRADICTS, "ACT04:pressure_stable"),
            ("ACT05", CheckFinding.SUPPORTS, "ACT05:improvement_temporary"),
            ("ACT05", CheckFinding.CONTRADICTS, "ACT05:no_improvement"),
            ("ACT06", CheckFinding.SUPPORTS, "ACT06:parameters_deviated"),
            ("ACT06", CheckFinding.CONTRADICTS, "ACT06:parameters_correct"),
            ("ACT07", CheckFinding.SUPPORTS, "ACT07:valve_worn"),
            ("ACT07", CheckFinding.CONTRADICTS, "ACT07:valve_normal"),
            ("ACT08", CheckFinding.SUPPORTS, "ACT08:temperature_high"),
            ("ACT08", CheckFinding.CONTRADICTS, "ACT08:temperature_normal"),
            ("ACT09", CheckFinding.SUPPORTS, "ACT09:contamination_found"),
            ("ACT09", CheckFinding.CONTRADICTS, "ACT09:surface_clean"),
            ("ACT10", CheckFinding.SUPPORTS, "ACT10:calibration_drift"),
            ("ACT10", CheckFinding.CONTRADICTS, "ACT10:calibration_ok"),
        ]

        for check_id, finding, expected_value in test_matrix:
            cr = CheckResult(
                check_id=check_id,
                execution_status=CheckExecutionStatus.COMPLETED,
                finding=finding,
            )
            obs, summary = CheckResultHandler.handle(cr)
            self.assertGreaterEqual(len(obs), 1, f"No observations for {check_id} {finding.value}")
            check_obs = next((o for o in obs if o.observation_type == ObservationType.CHECK_RESULT), None)
            self.assertIsNotNone(check_obs, f"Missing check_result observation for {check_id}")
            assert check_obs is not None
            self.assertEqual(check_obs.value, expected_value)


if __name__ == "__main__":
    unittest.main()
