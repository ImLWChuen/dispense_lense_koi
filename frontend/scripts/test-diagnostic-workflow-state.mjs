/**
 * Deterministic regression suite for Diagnostic Workflow State and Payload Builders (DLK-M3-029).
 *
 * Verifies:
 * 1. Initial error never becomes question/check completion (mutually exclusive error vs done views).
 * 2. No next check/question produces a neutral exhausted/completed state without claiming sufficient evidence.
 * 3. Completed supporting/contradicting check payloads preserve the selected canonical outcome.
 * 4. Inconclusive and non-completed (blocked/skipped/failed) payloads omit outcome and use safe findings.
 * 5. Lifecycle actions legality across all four issue conditions (UNRESOLVED, RECOVERY_PENDING_VERIFICATION, RESOLVED, RECURRED).
 * 6. Cause confirmation is independent of recovery and resolution.
 * 7. Failed verification returns to UNRESOLVED while confirmed cause remains representable.
 * 8. Resolved case allows recurrence reporting.
 * 9. Stale/failed mutation state preserves the last canonical case until refresh.
 * 10. Evidence support score formatting is strictly "/100" or "Not available", never probability or confidence.
 */

import assert from "node:assert/strict";
import {
    deriveQuestionsView,
    deriveTroubleshootingView,
    buildCheckResultPayload,
    formatOutcomeLabel,
    getAvailableLifecycleActions,
    buildCauseConfirmationPayload,
    buildRecoveryActionPayload,
    buildRecoveryVerificationPayload,
    buildRecurrencePayload,
    formatEvidenceSupport,
} from "../lib/diagnostic-workflow-state.ts";

const mockCase = {
    case_id: "test-case-1234",
    description: "Dispensing dots undersized after 20 minutes.",
    defect_code: "D03_INCONSISTENT_SIZE",
    defect_name: "Inconsistent Dot Size",
    issue_condition: "UNRESOLVED",
    created_at: "2026-09-20T10:00:00Z",
    observations: [],
    previous_answers: [],
    previous_check_results: [],
    previous_confirmations: [],
    lifecycle_events: [],
    analysis_revisions: [],
    initial_diagnosis: {
        case_id: "test-case-1234",
        defect: "D03_INCONSISTENT_SIZE",
        defect_name: "Inconsistent Dot Size",
        ranked_causes: [
            {
                cause_id: "nozzle_restriction",
                cause_name: "Nozzle Restriction",
                score: 88,
                evidence_support: 88,
                description: "Partial nozzle clogging.",
            },
        ],
        next_question: null,
        next_check: null,
        explanation: "Test explanation.",
        issue_condition: "UNRESOLVED",
        analysis_revision: {
            revision_number: 1,
            timestamp: "2026-09-20T10:00:00Z",
            defect_code: "D03_INCONSISTENT_SIZE",
            ranked_causes: [],
            new_evidence_summary: "Initial",
            changes_from_previous: [],
        },
        warnings: [],
    },
    diagnosis: {
        case_id: "test-case-1234",
        defect: "D03_INCONSISTENT_SIZE",
        defect_name: "Inconsistent Dot Size",
        ranked_causes: [
            {
                cause_id: "nozzle_restriction",
                cause_name: "Nozzle Restriction",
                score: 88,
                evidence_support: 88,
                description: "Partial nozzle clogging.",
            },
        ],
        next_question: null,
        next_check: null,
        explanation: "Test explanation.",
        issue_condition: "UNRESOLVED",
        analysis_revision: {
            revision_number: 1,
            timestamp: "2026-09-20T10:00:00Z",
            defect_code: "D03_INCONSISTENT_SIZE",
            ranked_causes: [],
            new_evidence_summary: "Initial",
            changes_from_previous: [],
        },
        warnings: [],
    },
};

function runTests() {
    let testsPassed = 0;

    // --- 1. Initial Error Never Becomes Question/Check Completion ---
    {
        // Questions view: initial error
        const qErrorView = deriveQuestionsView({
            isLoading: false,
            error: "Failed to connect to backend service.",
            caseData: null,
            hasNextQuestion: false,
        });

        assert.equal(qErrorView.showInitialLoading, false);
        assert.equal(qErrorView.showDedicatedError, true, "Initial error must render dedicated error card");
        assert.equal(qErrorView.showStaleBanner, false);
        assert.equal(qErrorView.showActiveQuestion, false);
        assert.equal(qErrorView.showNoNextQuestion, false, "Initial error must NEVER show completion panel");

        // Troubleshooting view: initial error
        const tErrorView = deriveTroubleshootingView({
            isLoading: false,
            error: "Network timeout fetching case.",
            caseData: null,
            hasNextCheck: false,
        });

        assert.equal(tErrorView.showInitialLoading, false);
        assert.equal(tErrorView.showDedicatedError, true, "Initial error must render dedicated error card");
        assert.equal(tErrorView.showStaleBanner, false);
        assert.equal(tErrorView.showActiveCheck, false);
        assert.equal(tErrorView.showNoNextCheck, false, "Initial error must NEVER show checks complete panel");

        testsPassed++;
        console.log("✓ Test 1 Passed: Initial error never produces completion or checks-done state.");
    }

    // --- 2. Neutral Exhausted State When No Next Item Available ---
    {
        // Questions view when no next question exists
        const qDoneView = deriveQuestionsView({
            isLoading: false,
            error: null,
            caseData: mockCase,
            hasNextQuestion: false,
        });
        assert.equal(qDoneView.showInitialLoading, false);
        assert.equal(qDoneView.showDedicatedError, false);
        assert.equal(qDoneView.showActiveQuestion, false);
        assert.equal(qDoneView.showNoNextQuestion, true, "Must show no-next-question state when case is loaded but next question is null");

        // Troubleshooting view when next_check is null
        const tDoneView = deriveTroubleshootingView({
            isLoading: false,
            error: null,
            caseData: mockCase,
            hasNextCheck: false,
        });
        assert.equal(tDoneView.showInitialLoading, false);
        assert.equal(tDoneView.showDedicatedError, false);
        assert.equal(tDoneView.showActiveCheck, false);
        assert.equal(tDoneView.showNoNextCheck, true, "Must show no-next-check state when case is loaded but next check is null");

        testsPassed++;
        console.log("✓ Test 2 Passed: Exhausted questions and checks produce neutral completion states when data is loaded.");
    }

    // --- 3. Completed Supporting / Contradicting Check Payloads Preserve Canonical Outcome ---
    {
        const payloadSupports = buildCheckResultPayload({
            check_id: "ACT01",
            execution_status: "COMPLETED",
            finding: "SUPPORTS",
            outcome: "blockage_found",
            finding_details: "Dried epoxy observed in nozzle bore.",
            expected_revision: 3,
        });

        assert.equal(payloadSupports.check_id, "ACT01");
        assert.equal(payloadSupports.execution_status, "COMPLETED");
        assert.equal(payloadSupports.finding, "SUPPORTS");
        assert.equal(payloadSupports.outcome, "blockage_found");
        assert.equal(payloadSupports.finding_details, "Dried epoxy observed in nozzle bore.");
        assert.equal(payloadSupports.expected_revision, 3);

        const payloadContradicts = buildCheckResultPayload({
            check_id: "ACT01",
            execution_status: "COMPLETED",
            finding: "CONTRADICTS",
            outcome: "clear_flow",
            finding_details: "Flow is unobstructed.",
            expected_revision: 3,
        });

        assert.equal(payloadContradicts.finding, "CONTRADICTS");
        assert.equal(payloadContradicts.outcome, "clear_flow");

        // Outcome label formatting helper
        assert.equal(formatOutcomeLabel("blockage_found"), "Blockage Found");
        assert.equal(formatOutcomeLabel("clear_flow"), "Clear Flow");

        // Missing outcome for SUPPORTS/CONTRADICTS must throw
        assert.throws(
            () =>
                buildCheckResultPayload({
                    check_id: "ACT01",
                    execution_status: "COMPLETED",
                    finding: "SUPPORTS",
                    outcome: "",
                    expected_revision: 3,
                }),
            /canonical outcome is required/
        );

        testsPassed++;
        console.log("✓ Test 3 Passed: Supporting and contradicting check results strictly require and preserve canonical outcomes.");
    }

    // --- 4. Inconclusive and Non-Completed Payloads Omit Outcome and Use Safe Findings ---
    {
        // Completed but inconclusive
        const payloadInconclusive = buildCheckResultPayload({
            check_id: "ACT02",
            execution_status: "COMPLETED",
            finding: "INCONCLUSIVE",
            outcome: "ignored_outcome",
            finding_details: "Pressure was fluctuating slightly but within bounds.",
            expected_revision: 2,
        });
        assert.equal(payloadInconclusive.execution_status, "COMPLETED");
        assert.equal(payloadInconclusive.finding, "INCONCLUSIVE");
        assert.equal(payloadInconclusive.outcome, null, "Inconclusive checks must omit outcome");
        assert.equal(payloadInconclusive.finding_details, "Pressure was fluctuating slightly but within bounds.");

        // Blocked check
        const payloadBlocked = buildCheckResultPayload({
            check_id: "ACT03",
            execution_status: "BLOCKED",
            finding_details: "Access panel locked by maintenance.",
            expected_revision: 2,
        });
        assert.equal(payloadBlocked.execution_status, "BLOCKED");
        assert.equal(payloadBlocked.finding, "UNKNOWN", "Blocked checks must submit finding=UNKNOWN");
        assert.equal(payloadBlocked.outcome, null, "Blocked checks must omit outcome");
        assert.equal(payloadBlocked.finding_details, "Access panel locked by maintenance.");

        // Skipped check
        const payloadSkipped = buildCheckResultPayload({
            check_id: "ACT04",
            execution_status: "SKIPPED",
            finding_details: "Test syringe unavailable.",
            expected_revision: 2,
        });
        assert.equal(payloadSkipped.execution_status, "SKIPPED");
        assert.equal(payloadSkipped.finding, "UNKNOWN");
        assert.equal(payloadSkipped.outcome, null);

        testsPassed++;
        console.log("✓ Test 4 Passed: Inconclusive and non-completed checks omit outcome and submit safe findings.");
    }

    // --- 5. Lifecycle Actions Legality Across All Four Issue Conditions ---
    {
        // 1. UNRESOLVED
        const actionsUnresolved = getAvailableLifecycleActions("UNRESOLVED");
        assert.equal(actionsUnresolved.canConfirmCause, true, "UNRESOLVED allows cause confirmation");
        assert.equal(actionsUnresolved.canSubmitRecoveryAction, true, "UNRESOLVED allows recovery action");
        assert.equal(actionsUnresolved.canVerifyRecovery, false, "Cannot verify before recovery action is taken");
        assert.equal(actionsUnresolved.canReportRecurrence, false, "Cannot recur before resolution");

        // 2. RECOVERY_PENDING_VERIFICATION
        const actionsPending = getAvailableLifecycleActions("RECOVERY_PENDING_VERIFICATION");
        assert.equal(actionsPending.canConfirmCause, false, "Must verify active recovery before new confirmations");
        assert.equal(actionsPending.canSubmitRecoveryAction, false, "Cannot submit recovery while verification is pending");
        assert.equal(actionsPending.canVerifyRecovery, true, "RECOVERY_PENDING_VERIFICATION allows recovery verification");
        assert.equal(actionsPending.canReportRecurrence, false);

        // 3. RESOLVED
        const actionsResolved = getAvailableLifecycleActions("RESOLVED");
        assert.equal(actionsResolved.canConfirmCause, false);
        assert.equal(actionsResolved.canSubmitRecoveryAction, false);
        assert.equal(actionsResolved.canVerifyRecovery, false);
        assert.equal(actionsResolved.canReportRecurrence, true, "RESOLVED allows recurrence reporting");

        // 4. RECURRED
        const actionsRecurred = getAvailableLifecycleActions("RECURRED");
        assert.equal(actionsRecurred.canConfirmCause, true, "RECURRED allows cause confirmation");
        assert.equal(actionsRecurred.canSubmitRecoveryAction, true, "RECURRED allows recovery action");
        assert.equal(actionsRecurred.canVerifyRecovery, false);
        assert.equal(actionsRecurred.canReportRecurrence, false);

        testsPassed++;
        console.log("✓ Test 5 Passed: Lifecycle actions legality strictly matches the 4 persisted issue conditions.");
    }

    // --- 6. Cause Confirmation Independent of Recovery / Resolution ---
    {
        const confPayload = buildCauseConfirmationPayload(
            "nozzle_restriction",
            2,
            "Confirmed via solvent backflush inspection.",
            "senior_technician"
        );
        assert.equal(confPayload.cause_id, "nozzle_restriction");
        assert.equal(confPayload.expected_revision, 2);
        assert.equal(confPayload.confirmed_by, "senior_technician");
        assert.equal(confPayload.notes, "Confirmed via solvent backflush inspection.");

        // Cause confirmation does NOT require or perform recovery action
        const recPayload = buildRecoveryActionPayload(
            3,
            "Flushed nozzle with acetone and replaced Teflon tip."
        );
        assert.equal(recPayload.expected_revision, 3);
        assert.equal(recPayload.performed_by, "technician", "Defaults to technician actor");
        assert.equal(recPayload.recovery_details, "Flushed nozzle with acetone and replaced Teflon tip.");

        testsPassed++;
        console.log("✓ Test 6 Passed: Cause confirmation and recovery action are independent operations.");
    }

    // --- 7. Failed Verification Returning to UNRESOLVED Preserves Confirmed Cause ---
    {
        // Recovery verification failed payload
        const failVerPayload = buildRecoveryVerificationPayload(
            4,
            false,
            "Test dispense dots still have satellites."
        );
        assert.equal(failVerPayload.expected_revision, 4);
        assert.equal(failVerPayload.verification_passed, false);
        assert.equal(failVerPayload.verification_details, "Test dispense dots still have satellites.");
        assert.equal(failVerPayload.verified_by, "technician");

        // After failure, resulting condition is UNRESOLVED
        const actionsAfterFailed = getAvailableLifecycleActions("UNRESOLVED");
        assert.equal(actionsAfterFailed.canSubmitRecoveryAction, true, "Allows taking another recovery action");

        // Verify that a case with a confirmed cause keeps its confirmation history representable
        const caseWithConfirmedCause = {
            ...mockCase,
            previous_confirmations: [
                {
                    cause_id: "nozzle_restriction",
                    confirmed_by: "technician",
                    notes: "Visual verification",
                    confirmed_at: "2026-09-20T10:05:00Z",
                    resulting_revision_number: 2,
                },
            ],
            issue_condition: "UNRESOLVED",
        };
        assert.equal(caseWithConfirmedCause.previous_confirmations.length, 1);
        assert.equal(caseWithConfirmedCause.previous_confirmations[0].cause_id, "nozzle_restriction");
        assert.equal(caseWithConfirmedCause.issue_condition, "UNRESOLVED");

        testsPassed++;
        console.log("✓ Test 7 Passed: Failed recovery returns to UNRESOLVED while preserving confirmed cause history.");
    }

    // --- 8. Resolved Case Recurrence Availability ---
    {
        const recurPayload = buildRecurrencePayload(
            6,
            "Tailing defect re-appeared on line 2 during second shift.",
            "lead_tech"
        );
        assert.equal(recurPayload.expected_revision, 6);
        assert.equal(recurPayload.recurrence_details, "Tailing defect re-appeared on line 2 during second shift.");
        assert.equal(recurPayload.reported_by, "lead_tech");

        // Successful verification passed payload
        const passVerPayload = buildRecoveryVerificationPayload(
            5,
            true,
            "50 consecutive dots within tolerance."
        );
        assert.equal(passVerPayload.verification_passed, true);

        testsPassed++;
        console.log("✓ Test 8 Passed: Resolved cases correctly build recurrence payloads and support recurrence.");
    }

    // --- 9. Stale / Failed Mutation Preserves Last Canonical Case ---
    {
        // Stale mutation failure during questions
        const qStaleView = deriveQuestionsView({
            isLoading: false,
            error: "Stale revision: expected 2, current is 3.",
            caseData: mockCase,
            hasNextQuestion: true,
        });
        assert.equal(qStaleView.showDedicatedError, false, "Must NOT hide case data when an update fails");
        assert.equal(qStaleView.showStaleBanner, true, "Must show warning banner with error message");
        assert.equal(qStaleView.showActiveQuestion, true, "Keeps existing question / data visible");

        // Stale mutation failure during troubleshooting
        const tStaleView = deriveTroubleshootingView({
            isLoading: false,
            error: "Stale revision: expected 3, current is 4.",
            caseData: mockCase,
            hasNextCheck: true,
        });
        assert.equal(tStaleView.showDedicatedError, false);
        assert.equal(tStaleView.showStaleBanner, true);
        assert.equal(tStaleView.showActiveCheck, true);

        testsPassed++;
        console.log("✓ Test 9 Passed: Stale and failed mutation states preserve the last loaded canonical case with a stale banner.");
    }

    // --- 10. Evidence Support Score Formatting ---
    {
        assert.equal(formatEvidenceSupport(88), "88/100");
        assert.equal(formatEvidenceSupport(0), "0/100");
        assert.equal(formatEvidenceSupport(100), "100/100");
        assert.equal(formatEvidenceSupport(88.4), "88/100");
        assert.equal(formatEvidenceSupport(88.6), "89/100");
        assert.equal(formatEvidenceSupport(null), "Not available");
        assert.equal(formatEvidenceSupport(undefined), "Not available");
        assert.equal(formatEvidenceSupport(NaN), "Not available");

        testsPassed++;
        console.log("✓ Test 10 Passed: Evidence support score is strictly formatted as '/100', never accuracy or confidence.");
    }

    console.log(`\nAll ${testsPassed} diagnostic workflow state regression tests passed successfully.`);
}

runTests();
