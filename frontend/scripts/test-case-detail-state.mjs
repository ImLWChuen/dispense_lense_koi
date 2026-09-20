/**
 * Deterministic regression suite for Case Detail state and timeline derivation (DLK-M3-030).
 *
 * Verifies:
 * 1. Complete rich timeline: creation, revision, answer, check, confirmation, recovery verification, and recurrence entries.
 * 2. Deterministic ordering: chronological and revision sorting with stable tie-breaker.
 * 3. Minimal/missing optional histories: no fake events generated when collections are empty/missing.
 * 4. Timestamp formatting: valid timestamps formatted; invalid/missing timestamps safely return "Not recorded", never "Invalid Date".
 * 5. Case state derivation: current revision, top-ranked cause, and formatted issue condition derived strictly from persisted data.
 * 6. Identity truthfulness: no hardcoded engineer or technician identity is emitted.
 */

import assert from "node:assert/strict";
import {
    formatCaseTimestamp,
    deriveCurrentRevision,
    deriveTopRankedCause,
    deriveCaseOwner,
    formatIssueCondition,
    deriveCaseTimeline,
} from "../lib/case-detail-state.ts";

function runTests() {
    let testsPassed = 0;

    // --- 1. Rich Timeline with all 7 Event Types ---
    {
        const richCase = {
            case_id: "case-rich-001",
            description: "Dispense dot volume drift during shift",
            defect_code: "D03_INCONSISTENT_SIZE",
            defect_name: "Inconsistent Deposit Size",
            issue_condition: "RESOLVED",
            created_at: "2026-09-20T08:00:00Z",
            current_revision: 6,
            analysis_revisions: [
                {
                    revision_number: 1,
                    timestamp: "2026-09-20T08:00:05Z",
                    defect_code: "D03_INCONSISTENT_SIZE",
                    ranked_causes: [{ cause_id: "C01", cause_name: "Nozzle Clog", score: 85 }],
                    new_evidence_summary: "Initial analysis baseline established.",
                    changes_from_previous: [],
                },
                {
                    revision_number: 2,
                    timestamp: "2026-09-20T08:05:00Z",
                    defect_code: "D03_INCONSISTENT_SIZE",
                    ranked_causes: [{ cause_id: "C01", cause_name: "Nozzle Clog", score: 92 }],
                    new_evidence_summary: "Evidence boosted by question Q01.",
                    changes_from_previous: ["Nozzle Clog score increased"],
                },
            ],
            previous_answers: [
                {
                    question_id: "Q01",
                    answer_value: "after_prolonged_operation",
                    answer_text: "Dot shrinkage observed after 2 hours",
                    source: "TECHNICIAN",
                    answered_at: "2026-09-20T08:04:30Z",
                    resulting_revision_number: 2,
                },
            ],
            previous_check_results: [
                {
                    check_id: "CHK_NOZZLE_INSPECT",
                    execution_status: "COMPLETED",
                    finding: "SUPPORTS",
                    outcome: "partial_clog_visible",
                    source: "TECHNICIAN",
                    checked_at: "2026-09-20T08:10:00Z",
                    resulting_revision_number: 3,
                },
            ],
            previous_confirmations: [
                {
                    cause_id: "C01",
                    confirmed_by: "Alex Chen",
                    notes: "Visual inspection verified partial clog in tip",
                    confirmed_at: "2026-09-20T08:15:00Z",
                    resulting_revision_number: 4,
                },
            ],
            lifecycle_events: [
                {
                    id: 1,
                    case_id: "case-rich-001",
                    event_type: "RECOVERY_ACTION",
                    prior_issue_condition: "UNRESOLVED",
                    resulting_issue_condition: "RECOVERY_PENDING_VERIFICATION",
                    resulting_revision_number: 5,
                    actor: "Alex Chen",
                    details: "Ultrasonic cleaning of dispense nozzle completed",
                    verification_passed: null,
                    created_at: "2026-09-20T08:20:00Z",
                },
                {
                    id: 2,
                    case_id: "case-rich-001",
                    event_type: "RECOVERY_VERIFICATION",
                    prior_issue_condition: "RECOVERY_PENDING_VERIFICATION",
                    resulting_issue_condition: "RESOLVED",
                    resulting_revision_number: 6,
                    actor: "Alex Chen",
                    details: "Test coupon run passed 50/50 dots within spec",
                    verification_passed: true,
                    created_at: "2026-09-20T08:30:00Z",
                },
                {
                    id: 3,
                    case_id: "case-rich-001",
                    event_type: "RECURRENCE",
                    prior_issue_condition: "RESOLVED",
                    resulting_issue_condition: "RECURRED",
                    resulting_revision_number: 7,
                    actor: "Pat Taylor",
                    details: "Similar dot shrinkage noted on second shift",
                    verification_passed: null,
                    created_at: "2026-09-20T14:00:00Z",
                },
            ],
            diagnosis: {
                case_id: "case-rich-001",
                defect: "D03_INCONSISTENT_SIZE",
                defect_name: "Inconsistent Deposit Size",
                ranked_causes: [{ cause_id: "C01", cause_name: "Nozzle Partial Clog", score: 95 }],
                next_question: null,
                next_check: null,
                explanation: "Persistent partial clog identified.",
                issue_condition: "RECURRED",
                analysis_revision: { revision_number: 7 },
                warnings: [],
            },
        };

        const timeline = deriveCaseTimeline(richCase);

        // Verify all 7 event types are represented
        const eventNames = timeline.map((e) => e.event);
        assert.ok(eventNames.some((n) => n.includes("Case created")), "Missing creation event");
        assert.ok(eventNames.some((n) => n.includes("Diagnosis Revision")), "Missing revision event");
        assert.ok(eventNames.some((n) => n.includes("Question Answered")), "Missing answer event");
        assert.ok(eventNames.some((n) => n.includes("Troubleshooting Check")), "Missing check event");
        assert.ok(eventNames.some((n) => n.includes("Cause Confirmed")), "Missing confirmation event");
        assert.ok(eventNames.some((n) => n.includes("Recovery Action")), "Missing recovery action event");
        assert.ok(eventNames.some((n) => n.includes("Recovery Verification (PASSED)")), "Missing recovery verification event");
        assert.ok(eventNames.some((n) => n.includes("Recurrence Reported")), "Missing recurrence event");

        assert.equal(timeline.length, 9); // 1 creation + 2 revisions + 1 answer + 1 check + 1 confirmation + 1 action + 1 verification + 1 recurrence
        testsPassed++;
        console.log("✓ Test 1 Passed: Complete rich timeline contains all 7 canonical event types.");
    }

    // --- 2. Deterministic Chronological / Revision Ordering ---
    {
        const shuffledCase = {
            case_id: "case-order-001",
            description: "Test ordering",
            created_at: "2026-09-20T08:00:00Z",
            analysis_revisions: [
                { revision_number: 2, timestamp: "2026-09-20T08:20:00Z", new_evidence_summary: "Rev 2" },
                { revision_number: 1, timestamp: "2026-09-20T08:05:00Z", new_evidence_summary: "Rev 1" },
            ],
            previous_answers: [
                { question_id: "Q02", answer_value: "val2", answered_at: "2026-09-20T08:25:00Z", resulting_revision_number: 3 },
                { question_id: "Q01", answer_value: "val1", answered_at: "2026-09-20T08:10:00Z", resulting_revision_number: 2 },
            ],
            previous_check_results: [],
            previous_confirmations: [],
            lifecycle_events: [],
        };

        const timeline = deriveCaseTimeline(shuffledCase);
        assert.equal(timeline[0].event, "Case created");
        assert.equal(timeline[1].event, "Diagnosis Revision 1");
        assert.equal(timeline[2].event, "Question Answered: Q01");
        assert.equal(timeline[3].event, "Diagnosis Revision 2");
        assert.equal(timeline[4].event, "Question Answered: Q02");

        testsPassed++;
        console.log("✓ Test 2 Passed: Timeline sorts deterministically by chronological time and revision.");
    }

    // --- 3. Missing Optional Histories Produce No Fake Events ---
    {
        const minimalCase = {
            case_id: "case-min-001",
            description: "Minimal case description",
            created_at: "2026-09-20T08:00:00Z",
            issue_condition: "UNRESOLVED",
            previous_answers: [],
            previous_check_results: [],
            previous_confirmations: [],
            lifecycle_events: [],
            analysis_revisions: [],
        };

        const timeline = deriveCaseTimeline(minimalCase);
        assert.equal(timeline.length, 1);
        assert.equal(timeline[0].event, "Case created");
        assert.equal(timeline[0].detail, "Symptom: Minimal case description");

        testsPassed++;
        console.log("✓ Test 3 Passed: Minimal case produces only the genuine creation event with zero fake events.");
    }

    // --- 4. Invalid and Missing Timestamps Return 'Not recorded' ---
    {
        assert.equal(formatCaseTimestamp(null), "Not recorded");
        assert.equal(formatCaseTimestamp(undefined), "Not recorded");
        assert.equal(formatCaseTimestamp(""), "Not recorded");
        assert.equal(formatCaseTimestamp("   "), "Not recorded");
        assert.equal(formatCaseTimestamp("not-a-timestamp"), "Not recorded");

        const validFormatted = formatCaseTimestamp("2026-09-20T08:00:00Z");
        assert.notEqual(validFormatted, "Not recorded");
        assert.ok(!validFormatted.includes("Invalid Date"), "Must never render Invalid Date");

        const caseWithBadDates = {
            case_id: "case-baddate-001",
            description: "Bad date test",
            created_at: "invalid-date",
            analysis_revisions: [
                { revision_number: 1, timestamp: "", new_evidence_summary: "No timestamp revision" },
            ],
        };
        const timeline = deriveCaseTimeline(caseWithBadDates);
        assert.equal(timeline[0].displayTime, "Not recorded");
        assert.equal(timeline[1].displayTime, "Not recorded");

        testsPassed++;
        console.log("✓ Test 4 Passed: Invalid and missing timestamps consistently return 'Not recorded' and never 'Invalid Date'.");
    }

    // --- 5. Current Revision, Top Cause, and Issue Condition Derivation ---
    {
        const testCase = {
            case_id: "case-state-001",
            description: "Derivation test",
            issue_condition: "IssueCondition.RECOVERY_PENDING_VERIFICATION",
            current_revision: 4,
            diagnosis: {
                ranked_causes: [
                    { cause_id: "C02", cause_name: "Fluid Viscosity Drift", score: 91 },
                    { cause_id: "C01", cause_name: "Nozzle Wear", score: 45 },
                ],
            },
        };

        assert.equal(deriveCurrentRevision(testCase), 4);
        assert.equal(deriveTopRankedCause(testCase), "Fluid Viscosity Drift");
        assert.equal(formatIssueCondition(testCase.issue_condition), "Recovery Pending Verification");

        const fallbackCase = {
            case_id: "case-fb-001",
            issue_condition: "RESOLVED",
            diagnosis: {
                ranked_causes: [],
                analysis_revision: { revision_number: 3 },
            },
        };
        assert.equal(deriveCurrentRevision(fallbackCase), 3);
        assert.equal(deriveTopRankedCause(fallbackCase), null);
        assert.equal(formatIssueCondition(fallbackCase.issue_condition), "Resolved");

        testsPassed++;
        console.log("✓ Test 5 Passed: Current revision, top-ranked cause, and status correctly derived from real case data.");
    }

    // --- 6. Identity Truthfulness: No Hardcoded Engineer or Technician Identity ---
    {
        const unassignedCase = {
            case_id: "case-owner-001",
            machine_context: {},
        };
        assert.equal(deriveCaseOwner(unassignedCase), "Not recorded");

        const operatorCase = {
            case_id: "case-owner-002",
            machine_context: { operator: "Jane Doe" },
        };
        assert.equal(deriveCaseOwner(operatorCase), "Jane Doe");

        assert.notEqual(deriveCaseOwner(unassignedCase), "Engineer");
        assert.notEqual(deriveCaseOwner(unassignedCase), "technician");

        // Verify timeline entries omit actor clause or never generate hardcoded 'technician' / 'Engineer'
        const anonymousCase = {
            case_id: "case-anon-001",
            description: "Anonymous test case",
            created_at: "2026-09-20T08:00:00Z",
            previous_confirmations: [
                {
                    cause_id: "C01",
                    confirmed_by: "", // empty
                    notes: "Visual check",
                    resulting_revision_number: 2,
                },
                {
                    cause_id: "C02",
                    confirmed_by: null, // null
                    resulting_revision_number: 3,
                },
            ],
            lifecycle_events: [
                {
                    event_type: "RECOVERY_ACTION",
                    resulting_revision_number: 4,
                    actor: "",
                    details: "Cleaned nozzle",
                },
                {
                    event_type: "RECOVERY_ACTION",
                    resulting_revision_number: 5,
                    actor: null,
                    details: null,
                    resulting_issue_condition: "RECOVERY_PENDING_VERIFICATION",
                },
                {
                    event_type: "RECOVERY_VERIFICATION",
                    resulting_revision_number: 6,
                    actor: "   ",
                    verification_passed: true,
                    details: "Coupon OK",
                },
                {
                    event_type: "RECURRENCE",
                    resulting_revision_number: 7,
                    actor: null,
                    details: "Shift 2 drift",
                },
            ],
        };

        const timeline = deriveCaseTimeline(anonymousCase);
        for (const entry of timeline) {
            const lowerDetail = entry.detail.toLowerCase();
            assert.ok(
                !lowerDetail.includes("technician"),
                `Entry '${entry.key}' must not invent 'technician' identity: ${entry.detail}`
            );
            assert.ok(
                !lowerDetail.includes("engineer"),
                `Entry '${entry.key}' must not invent 'engineer' identity: ${entry.detail}`
            );
        }

        // Verify confirmation detail when confirmed_by is absent
        assert.equal(timeline.find((e) => e.key.includes("04-confirmation-C01"))?.detail, "Confirmed · Notes: Visual check");
        assert.equal(timeline.find((e) => e.key.includes("04-confirmation-C02"))?.detail, "Confirmed");

        // Verify recovery action detail when actor is absent
        assert.equal(timeline.find((e) => e.key.includes("05-recovery-action-4"))?.detail, "Action: Cleaned nozzle");
        assert.equal(timeline.find((e) => e.key.includes("05-recovery-action-5"))?.detail, "Transitioned to RECOVERY_PENDING_VERIFICATION");

        // Verify verification detail when actor is absent
        assert.equal(timeline.find((e) => e.key.includes("05-recovery-verification-6"))?.detail, "Result: Passed · Coupon OK");

        // Verify recurrence detail when actor is absent
        assert.equal(timeline.find((e) => e.key.includes("05-recurrence-7"))?.detail, "Shift 2 drift");

        // Verify populated actor IS included
        const populatedCase = {
            case_id: "case-pop-001",
            created_at: "2026-09-20T08:00:00Z",
            previous_confirmations: [
                { cause_id: "C01", confirmed_by: "Alex Chen", resulting_revision_number: 2 },
            ],
            lifecycle_events: [
                { event_type: "RECOVERY_ACTION", resulting_revision_number: 3, actor: "Alex Chen", details: "Cleaned" },
                { event_type: "RECOVERY_VERIFICATION", resulting_revision_number: 4, actor: "Alex Chen", verification_passed: true },
                { event_type: "RECURRENCE", resulting_revision_number: 5, actor: "Pat Taylor" },
            ],
        };
        const popTimeline = deriveCaseTimeline(populatedCase);
        assert.ok(popTimeline.find((e) => e.key.includes("04-confirmation-C01"))?.detail.includes("by Alex Chen"));
        assert.ok(popTimeline.find((e) => e.key.includes("05-recovery-action-3"))?.detail.includes("(by Alex Chen)"));
        assert.ok(popTimeline.find((e) => e.key.includes("05-recovery-verification-4"))?.detail.includes("(by Alex Chen)"));
        assert.ok(popTimeline.find((e) => e.key.includes("05-recurrence-5"))?.detail.includes("(by Pat Taylor)"));

        testsPassed++;
        console.log("✓ Test 6 Passed: Case owner and timeline entries render persisted identities only; zero hardcoded technician/engineer.");
    }

    // --- 7. Deterministic Timeline Keys Without Event IDs ---
    {
        const caseWithoutIds = {
            case_id: "case-noids-001",
            description: "No IDs test",
            created_at: "2026-09-20T08:00:00Z",
            lifecycle_events: [
                {
                    event_type: "RECOVERY_ACTION",
                    resulting_revision_number: 2,
                    actor: "Alex Chen",
                    details: "Cleaned tip",
                    created_at: "2026-09-20T08:10:00Z",
                    // id omitted
                },
                {
                    event_type: "RECOVERY_VERIFICATION",
                    resulting_revision_number: 3,
                    actor: "Alex Chen",
                    verification_passed: true,
                    created_at: "2026-09-20T08:20:00Z",
                    id: null,
                },
                {
                    event_type: "RECURRENCE",
                    resulting_revision_number: 4,
                    actor: "Alex Chen",
                    created_at: "2026-09-20T10:00:00Z",
                    id: undefined,
                },
            ],
        };

        const run1 = deriveCaseTimeline(caseWithoutIds);
        const run2 = deriveCaseTimeline(caseWithoutIds);

        // Deep equality check between two separate calls
        assert.deepEqual(run1, run2, "Calling deriveCaseTimeline twice must produce identical results with stable keys");

        // Verify keys contain stable index suffixes
        assert.equal(run1[1].key, "05-recovery-action-2-idx-0");
        assert.equal(run1[2].key, "05-recovery-verification-3-idx-1");
        assert.equal(run1[3].key, "05-recurrence-4-idx-2");

        testsPassed++;
        console.log("✓ Test 7 Passed: Timeline keys are fully deterministic when event IDs are omitted or null.");
    }

    console.log(`\nAll ${testsPassed} case-detail state regression tests passed successfully.`);
}

runTests();
