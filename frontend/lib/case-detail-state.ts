/**
 * Pure state and view derivation helpers for Case Detail (DLK-M3-030).
 */

import type { DurableCaseResponse } from "@/types/api";

export interface CaseTimelineEntry {
    key: string;
    event: string;
    timestamp: string | null;
    displayTime: string;
    revision?: number;
    detail: string;
}

export function formatCaseTimestamp(timestamp?: string | null): string {
    if (!timestamp || typeof timestamp !== "string" || timestamp.trim() === "") {
        return "Not recorded";
    }
    const d = new Date(timestamp);
    if (isNaN(d.getTime())) {
        return "Not recorded";
    }
    return d.toLocaleString();
}

export function deriveCurrentRevision(caseData: DurableCaseResponse): number {
    if (typeof caseData.current_revision === "number") {
        return caseData.current_revision;
    }
    if (caseData.diagnosis?.analysis_revision?.revision_number) {
        return caseData.diagnosis.analysis_revision.revision_number;
    }
    if (caseData.analysis_revisions && caseData.analysis_revisions.length > 0) {
        return Math.max(...caseData.analysis_revisions.map((r) => r.revision_number));
    }
    return 1;
}

export function deriveTopRankedCause(caseData: DurableCaseResponse): string | null {
    const causes = caseData.diagnosis?.ranked_causes;
    if (causes && causes.length > 0 && causes[0].cause_name) {
        return causes[0].cause_name;
    }
    return null;
}

export function deriveCaseOwner(caseData: DurableCaseResponse): string {
    if (caseData.machine_context && typeof caseData.machine_context === "object") {
        const op = caseData.machine_context.operator;
        if (typeof op === "string" && op.trim() !== "") {
            return op.trim();
        }
    }
    return "Not recorded";
}

export function formatIssueCondition(condition?: string | null): string {
    if (!condition) return "Unknown";
    const clean = condition.replace("IssueCondition.", "");
    return clean
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(" ");
}

function getTimestampMs(ts: string | null | undefined): number {
    if (!ts || typeof ts !== "string") return 0;
    const ms = Date.parse(ts);
    return isNaN(ms) ? 0 : ms;
}

export function deriveCaseTimeline(caseData: DurableCaseResponse): CaseTimelineEntry[] {
    if (!caseData) return [];

    const entries: CaseTimelineEntry[] = [];

    // 1. Case Creation
    entries.push({
        key: `00-creation-${caseData.case_id}`,
        event: "Case created",
        timestamp: caseData.created_at || null,
        displayTime: formatCaseTimestamp(caseData.created_at),
        revision: 1,
        detail: caseData.description ? `Symptom: ${caseData.description}` : "Case created",
    });

    // 2. Diagnosis Revisions
    if (Array.isArray(caseData.analysis_revisions)) {
        for (const rev of caseData.analysis_revisions) {
            entries.push({
                key: `01-revision-${rev.revision_number}`,
                event: `Diagnosis Revision ${rev.revision_number}`,
                timestamp: rev.timestamp || null,
                displayTime: formatCaseTimestamp(rev.timestamp),
                revision: rev.revision_number,
                detail: rev.new_evidence_summary || "Analysis updated.",
            });
        }
    }

    // 3. Question Answers
    if (Array.isArray(caseData.previous_answers)) {
        for (const ans of caseData.previous_answers) {
            entries.push({
                key: `02-answer-${ans.question_id}-${ans.resulting_revision_number}`,
                event: `Question Answered: ${ans.question_id}`,
                timestamp: ans.answered_at || null,
                displayTime: formatCaseTimestamp(ans.answered_at),
                revision: ans.resulting_revision_number,
                detail: `Answer: ${ans.answer_text || ans.answer_value}`,
            });
        }
    }

    // 4. Troubleshooting Checks
    if (Array.isArray(caseData.previous_check_results)) {
        for (const check of caseData.previous_check_results) {
            const outcomeText = check.outcome ? ` · Outcome: ${check.outcome}` : "";
            entries.push({
                key: `03-check-${check.check_id}-${check.resulting_revision_number}`,
                event: `Troubleshooting Check: ${check.execution_status}`,
                timestamp: check.checked_at || null,
                displayTime: formatCaseTimestamp(check.checked_at),
                revision: check.resulting_revision_number,
                detail: `Finding: ${check.finding}${outcomeText}`,
            });
        }
    }

    // 5. Cause Confirmations
    if (Array.isArray(caseData.previous_confirmations)) {
        for (const conf of caseData.previous_confirmations) {
            const notesText = conf.notes ? ` · Notes: ${conf.notes}` : "";
            entries.push({
                key: `04-confirmation-${conf.cause_id}-${conf.resulting_revision_number}`,
                event: `Cause Confirmed: ${conf.cause_id}`,
                timestamp: conf.confirmed_at || null,
                displayTime: formatCaseTimestamp(conf.confirmed_at),
                revision: conf.resulting_revision_number,
                detail: `Confirmed by ${conf.confirmed_by || "technician"}${notesText}`,
            });
        }
    }

    // 6. Issue Lifecycle Events (Recovery Actions, Recovery Verifications, Recurrences)
    if (Array.isArray(caseData.lifecycle_events)) {
        for (const evt of caseData.lifecycle_events) {
            const eventType = (evt.event_type || "").toUpperCase();
            const idSuffix = evt.id !== undefined && evt.id !== null ? evt.id : Math.random().toString(36).substring(2, 7);

            if (eventType === "RECOVERY_ACTION") {
                entries.push({
                    key: `05-recovery-action-${evt.resulting_revision_number}-${idSuffix}`,
                    event: "Recovery Action",
                    timestamp: evt.created_at || null,
                    displayTime: formatCaseTimestamp(evt.created_at),
                    revision: evt.resulting_revision_number,
                    detail: evt.details
                        ? `Action: ${evt.details} (by ${evt.actor || "technician"})`
                        : `Transitioned to ${evt.resulting_issue_condition} (by ${evt.actor || "technician"})`,
                });
            } else if (eventType === "RECOVERY_VERIFICATION") {
                const passed = evt.verification_passed === true;
                const detailsText = evt.details ? ` · ${evt.details}` : "";
                entries.push({
                    key: `05-recovery-verification-${evt.resulting_revision_number}-${idSuffix}`,
                    event: `Recovery Verification (${passed ? "PASSED" : "FAILED"})`,
                    timestamp: evt.created_at || null,
                    displayTime: formatCaseTimestamp(evt.created_at),
                    revision: evt.resulting_revision_number,
                    detail: `Result: ${passed ? "Passed" : "Failed"}${detailsText} (by ${evt.actor || "technician"})`,
                });
            } else if (eventType === "RECURRENCE") {
                entries.push({
                    key: `05-recurrence-${evt.resulting_revision_number}-${idSuffix}`,
                    event: "Recurrence Reported",
                    timestamp: evt.created_at || null,
                    displayTime: formatCaseTimestamp(evt.created_at),
                    revision: evt.resulting_revision_number,
                    detail: `${evt.details || "Issue recurred"} (by ${evt.actor || "technician"})`,
                });
            } else {
                const detailsText = evt.details ? ` · ${evt.details}` : "";
                entries.push({
                    key: `05-lifecycle-${evt.event_type}-${evt.resulting_revision_number}-${idSuffix}`,
                    event: `Lifecycle Event: ${evt.event_type.replace(/_/g, " ")}`,
                    timestamp: evt.created_at || null,
                    displayTime: formatCaseTimestamp(evt.created_at),
                    revision: evt.resulting_revision_number,
                    detail: `${evt.prior_issue_condition} → ${evt.resulting_issue_condition}${detailsText}`,
                });
            }
        }
    }

    // Deterministic Sort:
    // 1. Valid timestamp ascending (if both have valid timestamps)
    // 2. Revision ascending
    // 3. Stable key tie-breaker
    entries.sort((a, b) => {
        const timeA = getTimestampMs(a.timestamp);
        const timeB = getTimestampMs(b.timestamp);
        if (timeA !== timeB && timeA > 0 && timeB > 0) {
            return timeA - timeB;
        }
        const revA = a.revision ?? 0;
        const revB = b.revision ?? 0;
        if (revA !== revB) {
            return revA - revB;
        }
        return a.key.localeCompare(b.key);
    });

    return entries;
}
