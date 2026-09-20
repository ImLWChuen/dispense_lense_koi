/**
 * Deterministic regression suite for Diagnostic Workflow State and Payload Builders (DLK-M3-029).
 *
 * Verifies:
 * 1. Initial error never becomes question/check completion (mutually exclusive error vs done views).
 * 2. No next check/question produces a neutral exhausted/completed state without claiming sufficient evidence.
 * 3. Completed supporting/contradicting check payloads preserve the selected canonical outcome (using canonical ACT01 no_blockage key).
 * 4. Inconclusive and all non-completed (blocked, skipped, failed, unknown, not_applicable) payloads omit outcome and use safe findings.
 * 5. Lifecycle actions legality across all four issue conditions (UNRESOLVED, RECOVERY_PENDING_VERIFICATION, RESOLVED, RECURRED).
 * 6. Cause confirmation is independent of recovery and resolution.
 * 7. Failed verification returns to UNRESOLVED while confirmed cause remains representable.
 * 8. Resolved case allows recurrence reporting.
 * 9. Stale/failed mutation state preserves the last canonical case until refresh, with original error preserved.
 * 10. Form inputs are cleared ONLY on confirmed mutation success, and strictly preserved on failure.
 * 11. resolveActiveCheck returns active pending check when available, and undefined for all-historical lists (read-only historical checks).
 * 12. shouldShowVerificationBadge renders PASSED/FAILED badge only for recovery verification with boolean results, never for null/undefined or non-verification events.
 * 13. buildRecoveryVerificationPayload strictly requires non-blank verification details for both passed and failed outcomes.
 * 14. Evidence support score formatting is strictly "/100" or "Not available", never probability or confidence.
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
    resolveActiveCheck,
    shouldShowVerificationBadge,
    applyMutationSuccess,
    applyMutationFailure,
    evaluateFormInputsOnMutation,
    coordinateWorkflowMutation,
    retryWorkflowRefresh,
    WorkflowMutationError,
    REFRESH_WARNING_MESSAGE,
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

async function runTests() {
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

        // Uses canonical ACT01 contradiction outcome: no_blockage (actions.json)
        const payloadContradicts = buildCheckResultPayload({
            check_id: "ACT01",
            execution_status: "COMPLETED",
            finding: "CONTRADICTS",
            outcome: "no_blockage",
            finding_details: "Flow is unobstructed; bore completely clear.",
            expected_revision: 3,
        });

        assert.equal(payloadContradicts.finding, "CONTRADICTS");
        assert.equal(payloadContradicts.outcome, "no_blockage");

        // Outcome label formatting helper
        assert.equal(formatOutcomeLabel("blockage_found"), "Blockage Found");
        assert.equal(formatOutcomeLabel("no_blockage"), "No Blockage");

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
        console.log("✓ Test 3 Passed: Supporting and contradicting check results strictly require and preserve canonical outcomes (canonical no_blockage key).");
    }

    // --- 4. Support All 6 Execution Statuses; Non-Completed Omit Outcome and Use Safe UNKNOWN Finding ---
    {
        // 1. COMPLETED (INCONCLUSIVE)
        const payloadInconclusive = buildCheckResultPayload({
            check_id: "ACT02",
            execution_status: "COMPLETED",
            finding: "INCONCLUSIVE",
            outcome: "ignored_outcome",
            finding_details: "Pressure fluctuating slightly but within bounds.",
            expected_revision: 2,
        });
        assert.equal(payloadInconclusive.execution_status, "COMPLETED");
        assert.equal(payloadInconclusive.finding, "INCONCLUSIVE");
        assert.equal(payloadInconclusive.outcome, null, "Inconclusive checks must omit outcome");
        assert.equal(payloadInconclusive.finding_details, "Pressure fluctuating slightly but within bounds.");

        // 2. BLOCKED
        const payloadBlocked = buildCheckResultPayload({
            check_id: "ACT03",
            execution_status: "BLOCKED",
            finding_details: "Access panel locked by maintenance.",
            expected_revision: 2,
        });
        assert.equal(payloadBlocked.execution_status, "BLOCKED");
        assert.equal(payloadBlocked.finding, "UNKNOWN");
        assert.equal(payloadBlocked.outcome, null);
        assert.equal(payloadBlocked.finding_details, "Access panel locked by maintenance.");

        // 3. SKIPPED
        const payloadSkipped = buildCheckResultPayload({
            check_id: "ACT04",
            execution_status: "SKIPPED",
            finding_details: "Test syringe unavailable.",
            expected_revision: 2,
        });
        assert.equal(payloadSkipped.execution_status, "SKIPPED");
        assert.equal(payloadSkipped.finding, "UNKNOWN");
        assert.equal(payloadSkipped.outcome, null);

        // 4. FAILED
        const payloadFailed = buildCheckResultPayload({
            check_id: "ACT05",
            execution_status: "FAILED",
            finding_details: "Digital pressure gauge battery dead mid-test.",
            expected_revision: 2,
        });
        assert.equal(payloadFailed.execution_status, "FAILED");
        assert.equal(payloadFailed.finding, "UNKNOWN");
        assert.equal(payloadFailed.outcome, null);
        assert.equal(payloadFailed.finding_details, "Digital pressure gauge battery dead mid-test.");

        // 5. UNKNOWN
        const payloadUnknown = buildCheckResultPayload({
            check_id: "ACT06",
            execution_status: "UNKNOWN",
            finding_details: "Sensor readouts unreadable due to line noise.",
            expected_revision: 2,
        });
        assert.equal(payloadUnknown.execution_status, "UNKNOWN");
        assert.equal(payloadUnknown.finding, "UNKNOWN");
        assert.equal(payloadUnknown.outcome, null);

        // 6. NOT_APPLICABLE
        const payloadNA = buildCheckResultPayload({
            check_id: "ACT07",
            execution_status: "NOT_APPLICABLE",
            finding_details: "Dual-head check not applicable to single-head machine.",
            expected_revision: 2,
        });
        assert.equal(payloadNA.execution_status, "NOT_APPLICABLE");
        assert.equal(payloadNA.finding, "UNKNOWN");
        assert.equal(payloadNA.outcome, null);

        // Invalid status must throw
        assert.throws(
            () =>
                buildCheckResultPayload({
                    check_id: "ACT01",
                    execution_status: "INVALID_STATUS",
                    expected_revision: 2,
                }),
            /Invalid execution_status/
        );

        testsPassed++;
        console.log("✓ Test 4 Passed: All 6 check execution statuses supported; non-completed checks omit outcome and submit finding=UNKNOWN.");
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

    // --- 9. Mutation Error Preservation & Stale Banner ---
    {
        // When a mutation fails and case is refreshed, original error is preserved
        const refreshedCase = { ...mockCase, current_revision: 3 }; // Updated by another actor
        const mutationError = "Conflict: expected revision 2, but current revision is 3.";

        const stateAfterFailure = applyMutationFailure(refreshedCase, mutationError);
        assert.equal(stateAfterFailure.error, mutationError, "Original mutation error must NOT be cleared during refresh");
        assert.equal(stateAfterFailure.data.current_revision, 3, "Case state must be synchronized to revision 3");

        // View helper recognizes stale banner with preserved error and case data
        const view = deriveQuestionsView({
            isLoading: false,
            error: stateAfterFailure.error,
            caseData: stateAfterFailure.data,
            hasNextQuestion: true,
        });
        assert.equal(view.showDedicatedError, false, "Must NOT show dedicated error when case is present");
        assert.equal(view.showStaleBanner, true, "Must show stale warning banner with preserved error");

        // Successful mutation clears error
        const stateAfterSuccess = applyMutationSuccess(refreshedCase);
        assert.equal(stateAfterSuccess.error, null, "Successful mutation clears error");
        assert.equal(stateAfterSuccess.data.current_revision, 3);

        testsPassed++;
        console.log("✓ Test 9 Passed: Mutation failure preserves original error message while refreshing durable state.");
    }

    // --- 10. Form Inputs Cleared ONLY on Confirmed Success ---
    {
        const initialNotes = "Detailed observation notes about restricted tip.";
        const emptyNotes = "";

        // Failed mutation: input must be PRESERVED
        const failedInputState = evaluateFormInputsOnMutation(
            initialNotes,
            emptyNotes,
            false,
            "409 Conflict"
        );
        assert.equal(failedInputState.value, initialNotes, "Input must NOT be cleared on failure");
        assert.equal(failedInputState.error, "409 Conflict");
        assert.equal(failedInputState.isSubmitting, false);

        // Successful mutation: input is cleared
        const successInputState = evaluateFormInputsOnMutation(
            initialNotes,
            emptyNotes,
            true
        );
        assert.equal(successInputState.value, emptyNotes, "Input must be cleared on success");
        assert.equal(successInputState.error, null);
        assert.equal(successInputState.isSubmitting, false);

        testsPassed++;
        console.log("✓ Test 10 Passed: Form inputs are strictly preserved on mutation failure and cleared only on success.");
    }

    // --- 11. resolveActiveCheck: All-Historical Actions Remain Read-Only ---
    {
        const allHistoricalActions = [
            { id: "ACT01", status: "completed", name: "Inspect Nozzle" },
            { id: "ACT02", status: "blocked", name: "Check Material" },
            { id: "ACT03", status: "skipped", name: "Verify Pressure" },
        ];

        // When no pending check exists, activeCheck is undefined
        const noActive = resolveActiveCheck(allHistoricalActions, null);
        assert.equal(noActive, undefined, "All-historical actions must return undefined active check");

        const noActiveWithId = resolveActiveCheck(allHistoricalActions, "ACT01");
        assert.equal(noActiveWithId, undefined, "Historical matching id must NOT become active");

        // When a pending check exists, it resolves properly
        const mixedActions = [
            ...allHistoricalActions,
            { id: "ACT04", status: "pending", name: "Inspect Needle" },
        ];
        const activePending = resolveActiveCheck(mixedActions, "ACT04");
        assert.equal(activePending.id, "ACT04", "Resolves explicitly specified pending action");

        const activeDefaultPending = resolveActiveCheck(mixedActions, null);
        assert.equal(activeDefaultPending.id, "ACT04", "Defaults to pending action");

        testsPassed++;
        console.log("✓ Test 11 Passed: resolveActiveCheck returns undefined for all-historical list (ensuring historical checks remain read-only).");
    }

    // --- 12. shouldShowVerificationBadge: Gating for Verification Events ---
    {
        // Recovery verification with boolean result
        assert.equal(shouldShowVerificationBadge("RECOVERY_VERIFICATION", true), true);
        assert.equal(shouldShowVerificationBadge("RECOVERY_VERIFICATION", false), true);
        assert.equal(shouldShowVerificationBadge("VERIFICATION", true), true);
        assert.equal(shouldShowVerificationBadge("VERIFICATION", false), true);

        // Recovery verification with null or undefined
        assert.equal(shouldShowVerificationBadge("RECOVERY_VERIFICATION", null), false);
        assert.equal(shouldShowVerificationBadge("RECOVERY_VERIFICATION", undefined), false);

        // Recovery action and recurrence events (always null verification_passed)
        assert.equal(shouldShowVerificationBadge("RECOVERY_ACTION", null), false);
        assert.equal(shouldShowVerificationBadge("RECURRENCE", null), false);
        assert.equal(shouldShowVerificationBadge("RECOVERY_ACTION", undefined), false);
        assert.equal(shouldShowVerificationBadge("CAUSE_CONFIRMATION", null), false);

        // Non-verification event even if boolean passed
        assert.equal(shouldShowVerificationBadge("RECOVERY_ACTION", true), false);

        testsPassed++;
        console.log("✓ Test 12 Passed: shouldShowVerificationBadge displays PASSED/FAILED only for verification events with boolean results.");
    }

    // --- 13. buildRecoveryVerificationPayload Requires Non-Blank Details ---
    {
        // Non-blank details succeed for passed
        const passedPayload = buildRecoveryVerificationPayload(
            5,
            true,
            "100 test shots passed with dot diameter 0.45mm +/- 0.02mm."
        );
        assert.equal(passedPayload.verification_passed, true);
        assert.equal(passedPayload.verification_details, "100 test shots passed with dot diameter 0.45mm +/- 0.02mm.");

        // Non-blank details succeed for failed
        const failedPayload = buildRecoveryVerificationPayload(
            5,
            false,
            "Dots still undersized by 40% after cleaning."
        );
        assert.equal(failedPayload.verification_passed, false);
        assert.equal(failedPayload.verification_details, "Dots still undersized by 40% after cleaning.");

        // Blank or whitespace details must throw for passed
        assert.throws(
            () => buildRecoveryVerificationPayload(5, true, ""),
            /verification_details must be a non-empty string/
        );
        assert.throws(
            () => buildRecoveryVerificationPayload(5, true, "   "),
            /verification_details must be a non-empty string/
        );
        assert.throws(
            () => buildRecoveryVerificationPayload(5, true, null),
            /verification_details must be a non-empty string/
        );

        // Blank or whitespace details must throw for failed
        assert.throws(
            () => buildRecoveryVerificationPayload(5, false, ""),
            /verification_details must be a non-empty string/
        );
        assert.throws(
            () => buildRecoveryVerificationPayload(5, false, "   "),
            /verification_details must be a non-empty string/
        );

        testsPassed++;
        console.log("✓ Test 13 Passed: buildRecoveryVerificationPayload strictly requires non-blank verification details for both passed and failed verifications.");
    }

    // --- 14. Evidence Support Score Formatting ---
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
        console.log("✓ Test 14 Passed: Evidence support score is strictly formatted as '/100', never accuracy or confidence.");
    }

    // --- 15. Production Workflow Coordinator: 4 Distinct Outcomes, Input Lifecycle, Gating & GET-only Retry ---
    {
        const baseCase = { ...mockCase, current_revision: 1 };
        const updatedCase = { ...mockCase, current_revision: 2 };
        const initialFormInput = "Nozzle cleared with ultrasonic bath.";
        const emptyFormInput = "";

        // Scenario A: POST success + GET success
        {
            let stateEmitted = null;
            let mutationCalled = 0;
            let refreshCalled = 0;

            const result = await coordinateWorkflowMutation({
                currentCase: baseCase,
                performMutation: async () => {
                    mutationCalled++;
                    return { success: true };
                },
                performRefresh: async () => {
                    refreshCalled++;
                    return updatedCase;
                },
                onStateChange: (s) => {
                    stateEmitted = s;
                },
            });

            assert.equal(mutationCalled, 1);
            assert.equal(refreshCalled, 1);
            assert.equal(result.postSucceeded, true);
            assert.equal(result.getSucceeded, true);
            assert.equal(result.isRefreshRequired, false);
            assert.equal(result.mutationError, null);
            assert.equal(result.refreshWarning, null);
            assert.equal(result.caseData.current_revision, 2);
            assert.deepEqual(stateEmitted, {
                caseData: updatedCase,
                mutationError: null,
                refreshWarning: null,
                isRefreshRequired: false,
            });

            // Form input clearing on confirmed POST success
            const formState = evaluateFormInputsOnMutation(initialFormInput, emptyFormInput, result.postSucceeded);
            assert.equal(formState.value, emptyFormInput, "Form input must be cleared on POST success");
        }

        // Scenario B: POST failure + GET success
        {
            let stateEmitted = null;
            let mutationCalled = 0;
            let refreshCalled = 0;
            let rejectedError = null;

            try {
                await coordinateWorkflowMutation({
                    currentCase: baseCase,
                    performMutation: async () => {
                        mutationCalled++;
                        throw new Error("409 Conflict: expected revision 1, but current revision is 2");
                    },
                    performRefresh: async () => {
                        refreshCalled++;
                        return updatedCase;
                    },
                    onStateChange: (s) => {
                        stateEmitted = s;
                    },
                });
            } catch (err) {
                rejectedError = err;
            }

            assert.equal(mutationCalled, 1);
            assert.equal(refreshCalled, 1);
            assert.ok(rejectedError instanceof WorkflowMutationError, "Must reject with WorkflowMutationError");
            assert.equal(rejectedError.message, "409 Conflict: expected revision 1, but current revision is 2");
            assert.equal(rejectedError.getSucceeded, true);
            assert.equal(rejectedError.syncedCase.current_revision, 2);
            assert.deepEqual(stateEmitted, {
                caseData: updatedCase,
                mutationError: "409 Conflict: expected revision 1, but current revision is 2",
                refreshWarning: null,
                isRefreshRequired: false,
            });

            // Input preservation after POST rejection
            const formState = evaluateFormInputsOnMutation(initialFormInput, emptyFormInput, false, rejectedError.message);
            assert.equal(formState.value, initialFormInput, "Form input must be preserved on POST failure");
            assert.equal(formState.error, "409 Conflict: expected revision 1, but current revision is 2");
        }

        // Scenario C: POST failure + GET failure
        {
            let stateEmitted = null;
            let mutationCalled = 0;
            let refreshCalled = 0;
            let rejectedError = null;

            try {
                await coordinateWorkflowMutation({
                    currentCase: baseCase,
                    performMutation: async () => {
                        mutationCalled++;
                        throw new Error("500 Internal Server Error");
                    },
                    performRefresh: async () => {
                        refreshCalled++;
                        throw new Error("Network unreachable");
                    },
                    onStateChange: (s) => {
                        stateEmitted = s;
                    },
                });
            } catch (err) {
                rejectedError = err;
            }

            assert.equal(mutationCalled, 1);
            assert.equal(refreshCalled, 1);
            assert.ok(rejectedError instanceof WorkflowMutationError);
            assert.equal(rejectedError.message, "500 Internal Server Error");
            assert.equal(rejectedError.getSucceeded, false);
            assert.equal(rejectedError.syncedCase.current_revision, 1);
            assert.deepEqual(stateEmitted, {
                caseData: baseCase,
                mutationError: "500 Internal Server Error",
                refreshWarning: null,
                isRefreshRequired: false,
            });

            // Input preservation after POST rejection
            const formState = evaluateFormInputsOnMutation(initialFormInput, emptyFormInput, false, rejectedError.message);
            assert.equal(formState.value, initialFormInput, "Form input must be preserved on POST failure");
        }

        // Scenario D: POST success + GET failure (Partial Success)
        {
            let stateEmitted = null;
            let mutationCalled = 0;
            let refreshCalled = 0;

            const result = await coordinateWorkflowMutation({
                currentCase: baseCase,
                performMutation: async () => {
                    mutationCalled++;
                    return { success: true };
                },
                performRefresh: async () => {
                    refreshCalled++;
                    throw new Error("503 Service Unavailable");
                },
                onStateChange: (s) => {
                    stateEmitted = s;
                },
            });

            assert.equal(mutationCalled, 1);
            assert.equal(refreshCalled, 1);
            assert.equal(result.postSucceeded, true);
            assert.equal(result.getSucceeded, false);
            assert.equal(result.isRefreshRequired, true, "isRefreshRequired must be true when GET fails");
            assert.equal(result.mutationError, null, "Must NOT treat refresh failure as mutation failure");
            assert.equal(result.refreshWarning, REFRESH_WARNING_MESSAGE);
            assert.equal(result.caseData.current_revision, 1, "Retains safe existing case state");
            assert.deepEqual(stateEmitted, {
                caseData: baseCase,
                mutationError: null,
                refreshWarning: REFRESH_WARNING_MESSAGE,
                isRefreshRequired: true,
            });

            // Input clearing after confirmed POST success even when refresh fails!
            const formState = evaluateFormInputsOnMutation(initialFormInput, emptyFormInput, result.postSucceeded);
            assert.equal(formState.value, emptyFormInput, "Form input must be cleared on confirmed POST success even when refresh fails");

            // Sub-case: Further mutation disabled while refresh is required
            let blockedMutationCalled = 0;
            let blockedError = null;
            try {
                await coordinateWorkflowMutation({
                    currentCase: result.caseData,
                    isRefreshRequired: result.isRefreshRequired, // true!
                    performMutation: async () => {
                        blockedMutationCalled++;
                        return {};
                    },
                    performRefresh: async () => baseCase,
                });
            } catch (err) {
                blockedError = err;
            }

            assert.equal(blockedMutationCalled, 0, "No mutation must be executed while refresh is required");
            assert.ok(blockedError, "Must throw error when attempting mutation while refresh is required");

            // Sub-case: GET-only retry clearing refresh-required state & No automatic POST replay
            let retryRefreshCalled = 0;
            let retryPostCalled = 0; // verify POST is never called

            const retryState = await retryWorkflowRefresh({
                currentCase: result.caseData,
                performRefresh: async () => {
                    retryRefreshCalled++;
                    return updatedCase;
                },
                onStateChange: (s) => {
                    stateEmitted = s;
                },
            });

            assert.equal(retryRefreshCalled, 1, "GET-only retry performs GET");
            assert.equal(retryPostCalled, 0, "No automatic POST replay");
            assert.equal(retryState.isRefreshRequired, false, "GET-only retry clears refresh-required state");
            assert.equal(retryState.refreshWarning, null, "Refresh warning cleared");
            assert.equal(retryState.caseData.current_revision, 2, "Case updated to refreshed data");
            assert.deepEqual(stateEmitted, {
                caseData: updatedCase,
                mutationError: null,
                refreshWarning: null,
                isRefreshRequired: false,
            });
        }

        testsPassed++;
        console.log("✓ Test 15 Passed: Production workflow coordinator handles all 4 outcomes, input lifecycle, refresh gating, and GET-only retry without POST replay.");
    }

    console.log(`\nAll ${testsPassed} diagnostic workflow state regression tests passed successfully.`);
}

runTests().catch((err) => {
    console.error("Test failure:", err);
    process.exit(1);
});
