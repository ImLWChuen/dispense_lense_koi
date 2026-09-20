/**
 * Pure state derivations and payload builders for the diagnostic workflow (DLK-M3-029).
 *
 * Provides deterministic logic for:
 * 1. Mutually exclusive questions and troubleshooting view states.
 * 2. Physical check outcome mapping and payload generation.
 * 3. Lifecycle action legality based on persisted issue condition.
 * 4. Stale/failed mutation handling preserving canonical case state and mutation errors.
 * 5. Truthful evidence-support formatting.
 * 6. Active check resolution and read-only historical check safety.
 * 7. Pass/fail verification badge gating.
 */

import type {
    DurableCaseResponse,
    SubmitCheckResultPayload,
    SubmitCauseConfirmationPayload,
    SubmitRecoveryActionPayload,
    SubmitRecoveryVerificationPayload,
    SubmitRecurrencePayload,
} from "@/types/api";

// ---------------------------------------------------------------------------
// 1. Questions View Derivation
// ---------------------------------------------------------------------------

export interface QuestionsViewState {
    isLoading: boolean;
    error: string | null;
    caseData: DurableCaseResponse | null;
    hasNextQuestion: boolean;
}

export interface QuestionsViewDerived {
    showInitialLoading: boolean;
    showDedicatedError: boolean;
    showStaleBanner: boolean;
    showActiveQuestion: boolean;
    showNoNextQuestion: boolean;
}

export function deriveQuestionsView(state: QuestionsViewState): QuestionsViewDerived {
    const hasCase = state.caseData !== null;
    const hasError = state.error !== null;

    return {
        // Initial loading: in-flight with no prior data and no error
        showInitialLoading: state.isLoading && !hasCase && !hasError,
        // Initial error: failed with no prior data
        showDedicatedError: !state.isLoading && hasError && !hasCase,
        // Stale/mutation error banner: error occurred after or while data is loaded
        showStaleBanner: hasError && hasCase,
        // Active question: case loaded, engine provided next question
        showActiveQuestion: hasCase && state.hasNextQuestion,
        // No next question: case loaded, engine returned no next question
        showNoNextQuestion: hasCase && !state.hasNextQuestion,
    };
}

// ---------------------------------------------------------------------------
// 2. Troubleshooting View Derivation & Active Check Resolution
// ---------------------------------------------------------------------------

export interface TroubleshootingViewState {
    isLoading: boolean;
    error: string | null;
    caseData: DurableCaseResponse | null;
    hasNextCheck: boolean;
}

export interface TroubleshootingViewDerived {
    showInitialLoading: boolean;
    showDedicatedError: boolean;
    showStaleBanner: boolean;
    showActiveCheck: boolean;
    showNoNextCheck: boolean;
}

export function deriveTroubleshootingView(state: TroubleshootingViewState): TroubleshootingViewDerived {
    const hasCase = state.caseData !== null;
    const hasError = state.error !== null;

    return {
        showInitialLoading: state.isLoading && !hasCase && !hasError,
        showDedicatedError: !state.isLoading && hasError && !hasCase,
        showStaleBanner: hasError && hasCase,
        showActiveCheck: hasCase && state.hasNextCheck,
        showNoNextCheck: hasCase && !state.hasNextCheck,
    };
}

export interface IdentifiableAction {
    id: string;
    status: string;
}

/**
 * Resolves the active pending check for execution.
 * Only resolves an action if activeCheckId matches a genuinely pending action,
 * or if the list contains a pending action.
 * If all actions are completed/historical, returns undefined so all items remain read-only.
 */
export function resolveActiveCheck<T extends IdentifiableAction>(
    actions: T[],
    activeCheckId?: string | null
): T | undefined {
    if (activeCheckId) {
        const matchingPending = actions.find(
            (a) => a.id === activeCheckId && a.status === "pending"
        );
        if (matchingPending) return matchingPending;
    }
    return actions.find((a) => a.status === "pending");
}

// ---------------------------------------------------------------------------
// 3. Physical Check Result Payload Builder
// ---------------------------------------------------------------------------

export const VALID_EXECUTION_STATUSES = [
    "COMPLETED",
    "BLOCKED",
    "SKIPPED",
    "FAILED",
    "UNKNOWN",
    "NOT_APPLICABLE",
] as const;

export type ValidExecutionStatus = (typeof VALID_EXECUTION_STATUSES)[number];

export interface BuildCheckResultParams {
    check_id: string;
    execution_status: string; // COMPLETED | BLOCKED | FAILED | SKIPPED | UNKNOWN | NOT_APPLICABLE
    finding?: string; // SUPPORTS | CONTRADICTS | INCONCLUSIVE | UNKNOWN
    outcome?: string | null;
    finding_details?: string | null;
    expected_revision: number;
}

export function buildCheckResultPayload(params: BuildCheckResultParams): SubmitCheckResultPayload {
    if (!params.check_id || !params.check_id.trim()) {
        throw new Error("check_id must be a non-empty string.");
    }
    if (params.expected_revision < 1) {
        throw new Error("expected_revision must be >= 1.");
    }

    const status = params.execution_status.toUpperCase() as ValidExecutionStatus;
    if (!VALID_EXECUTION_STATUSES.includes(status)) {
        throw new Error(
            `Invalid execution_status: '${params.execution_status}'. Must be one of: ${VALID_EXECUTION_STATUSES.join(", ")}.`
        );
    }

    if (status === "COMPLETED") {
        const finding = (params.finding || "INCONCLUSIVE").toUpperCase();
        if (finding === "SUPPORTS" || finding === "CONTRADICTS") {
            if (!params.outcome || !params.outcome.trim()) {
                throw new Error(`An explicit canonical outcome is required when check finding is ${finding}.`);
            }
            return {
                check_id: params.check_id.trim(),
                execution_status: "COMPLETED",
                finding,
                outcome: params.outcome.trim(),
                finding_details: params.finding_details?.trim() || null,
                expected_revision: params.expected_revision,
            };
        }

        // INCONCLUSIVE or other non-directional completed finding: omit outcome
        return {
            check_id: params.check_id.trim(),
            execution_status: "COMPLETED",
            finding: "INCONCLUSIVE",
            outcome: null,
            finding_details: params.finding_details?.trim() || null,
            expected_revision: params.expected_revision,
        };
    }

    // For BLOCKED, FAILED, SKIPPED, UNKNOWN, NOT_APPLICABLE:
    // Finding is forced to UNKNOWN, outcome is omitted, details are preserved
    return {
        check_id: params.check_id.trim(),
        execution_status: status,
        finding: "UNKNOWN",
        outcome: null,
        finding_details: params.finding_details?.trim() || null,
        expected_revision: params.expected_revision,
    };
}

export function formatOutcomeLabel(outcomeKey: string): string {
    if (!outcomeKey) return "";
    return outcomeKey
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(" ");
}

// ---------------------------------------------------------------------------
// 4. Lifecycle Actions Legality & Badges
// ---------------------------------------------------------------------------

export interface AvailableLifecycleActions {
    canConfirmCause: boolean;
    canSubmitRecoveryAction: boolean;
    canVerifyRecovery: boolean;
    canReportRecurrence: boolean;
}

export function getAvailableLifecycleActions(issueCondition: string | null | undefined): AvailableLifecycleActions {
    const condition = (issueCondition || "").replace("IssueCondition.", "").trim().toUpperCase();

    switch (condition) {
        case "UNRESOLVED":
        case "RECURRED":
            return {
                canConfirmCause: true,
                canSubmitRecoveryAction: true,
                canVerifyRecovery: false,
                canReportRecurrence: false,
            };
        case "RECOVERY_PENDING_VERIFICATION":
            return {
                canConfirmCause: false,
                canSubmitRecoveryAction: false,
                canVerifyRecovery: true,
                canReportRecurrence: false,
            };
        case "RESOLVED":
            return {
                canConfirmCause: false,
                canSubmitRecoveryAction: false,
                canVerifyRecovery: false,
                canReportRecurrence: true,
            };
        default:
            return {
                canConfirmCause: false,
                canSubmitRecoveryAction: false,
                canVerifyRecovery: false,
                canReportRecurrence: false,
            };
    }
}

/**
 * Determines whether a PASSED/FAILED badge should be rendered for a lifecycle event.
 * Only renders for recovery verification events where verification_passed is a strict boolean.
 * Returns false for recovery action and recurrence events where verification_passed is null.
 */
export function shouldShowVerificationBadge(
    eventType: string | null | undefined,
    verificationPassed: boolean | null | undefined
): boolean {
    const isVerificationEvent =
        eventType === "RECOVERY_VERIFICATION" || eventType === "VERIFICATION";
    return isVerificationEvent && typeof verificationPassed === "boolean";
}

// ---------------------------------------------------------------------------
// 5. Lifecycle Action Payload Builders
// ---------------------------------------------------------------------------

export function buildCauseConfirmationPayload(
    causeId: string,
    expectedRevision: number,
    notes?: string | null,
    confirmedBy: string = "technician"
): SubmitCauseConfirmationPayload {
    if (!causeId || !causeId.trim()) {
        throw new Error("cause_id must be a non-empty string.");
    }
    if (expectedRevision < 1) {
        throw new Error("expected_revision must be >= 1.");
    }
    return {
        cause_id: causeId.trim(),
        expected_revision: expectedRevision,
        confirmed_by: confirmedBy.trim() || "technician",
        notes: notes?.trim() || null,
    };
}

export function buildRecoveryActionPayload(
    expectedRevision: number,
    recoveryDetails: string,
    performedBy: string = "technician"
): SubmitRecoveryActionPayload {
    if (expectedRevision < 1) {
        throw new Error("expected_revision must be >= 1.");
    }
    if (!recoveryDetails || !recoveryDetails.trim()) {
        throw new Error("recovery_details must be a non-empty string.");
    }
    return {
        expected_revision: expectedRevision,
        recovery_details: recoveryDetails.trim(),
        performed_by: performedBy.trim() || "technician",
    };
}

export function buildRecoveryVerificationPayload(
    expectedRevision: number,
    verificationPassed: boolean,
    verificationDetails?: string | null,
    verifiedBy: string = "technician"
): SubmitRecoveryVerificationPayload {
    if (expectedRevision < 1) {
        throw new Error("expected_revision must be >= 1.");
    }
    if (!verificationDetails || !verificationDetails.trim()) {
        throw new Error("verification_details must be a non-empty string containing test observations.");
    }
    return {
        expected_revision: expectedRevision,
        verification_passed: Boolean(verificationPassed),
        verification_details: verificationDetails.trim(),
        verified_by: verifiedBy.trim() || "technician",
    };
}

export function buildRecurrencePayload(
    expectedRevision: number,
    recurrenceDetails: string,
    reportedBy: string = "technician"
): SubmitRecurrencePayload {
    if (expectedRevision < 1) {
        throw new Error("expected_revision must be >= 1.");
    }
    if (!recurrenceDetails || !recurrenceDetails.trim()) {
        throw new Error("recurrence_details must be a non-empty string.");
    }
    return {
        expected_revision: expectedRevision,
        recurrence_details: recurrenceDetails.trim(),
        reported_by: reportedBy.trim() || "technician",
    };
}

// ---------------------------------------------------------------------------
// 6. Evidence Support Formatting
// ---------------------------------------------------------------------------

export function formatEvidenceSupport(score: number | null | undefined): string {
    if (score === null || score === undefined || isNaN(score)) {
        return "Not available";
    }
    const clamped = Math.min(100, Math.max(0, Math.round(score)));
    return `${clamped}/100`;
}

// ---------------------------------------------------------------------------
// 7. Mutation State & Input Lifecycle Helpers
// ---------------------------------------------------------------------------

export interface MutationState<T> {
    data: T | null;
    error: string | null;
}

/**
 * Applies a successful mutation state update by saving refreshed data and clearing any error.
 */
export function applyMutationSuccess<T>(refreshedData: T): MutationState<T> {
    return {
        data: refreshedData,
        error: null,
    };
}

/**
 * Applies a failed mutation state update by saving refreshed data while strictly PRESERVING
 * the original mutation error message.
 */
export function applyMutationFailure<T>(
    refreshedData: T | null,
    mutationError: string
): MutationState<T> {
    return {
        data: refreshedData,
        error: mutationError,
    };
}

export interface FormInputState<T> {
    value: T;
    isSubmitting: boolean;
    error: string | null;
}

/**
 * Evaluates form input state following a mutation.
 * Inputs are cleared ONLY on confirmed success.
 * On failure, the technician's entered input is strictly preserved.
 */
export function evaluateFormInputsOnMutation<T>(
    currentInput: T,
    emptyInput: T,
    success: boolean,
    errorMsg?: string | null
): FormInputState<T> {
    if (success) {
        return {
            value: emptyInput,
            isSubmitting: false,
            error: null,
        };
    }
    return {
        value: currentInput,
        isSubmitting: false,
        error: errorMsg || "Mutation failed.",
    };
}
