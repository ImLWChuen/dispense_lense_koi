/**
 * Structured observation input submitted in requests (e.g. create case).
 * Allows client-omitted fields to be defaulted by the backend.
 */
export interface ObservationInput {
    id?: string;
    observation_type: string;
    value: string;
    original_text?: string | null;
    statement_type?: string;
    source?: string;
    confidence?: number | null;
    metadata?: Record<string, unknown>;
    timestamp?: string;
}

/**
 * Structured observation returned in API responses (e.g. ImageAnalysisResponse.observations).
 * Backend Pydantic schema guarantees id, observation_type, value, statement_type, source, metadata, timestamp.
 */
export interface Observation {
    id: string;
    observation_type: string;
    value: string;
    original_text: string | null;
    statement_type: string;
    source: string;
    confidence: number | null;
    metadata: Record<string, unknown>;
    timestamp: string;
}

export interface CreateCaseRequest {
    description?: string;
    problem_description?: string;
    material?: string;
    method?: string;
    machine_context?: Record<string, string | number | boolean | null | undefined>;
    defect_code?: string;
    observations?: (Observation | ObservationInput)[];
}

export interface CaseObservationResponse {
    id: string;
    observation_id: string;
    observation_type: string;
    value: string;
    original_text: string | null;
    statement_type: string;
    source: string;
    confidence: number | null;
    timestamp: string;
    created_at: string;
    first_seen_revision: number;
    metadata: Record<string, unknown>;
}

export interface CauseScoreExplanation {
    score: number;
    description: string;
}

export interface CauseEvidence {
    observation_id: string;
    cause_id: string;
    relation: string;
    strength: string;
    source: string;
    explanation: string;
    is_duplicate: boolean;
    duplicate_of: string | null;
    score_contribution: number;
}

export interface CandidateCause {
    cause_id: string;
    cause_name: string;
    score: number;
    conclusion: "SUSPECTED" | "CONFIRMED" | "UNRESOLVED";
    supporting_evidence: CauseEvidence[];
    contradicting_evidence: CauseEvidence[];
    neutral_evidence: CauseEvidence[];
    missing_evidence: string[];
    score_breakdown: Record<string, number>;

    // Legacy / UI display compatibility fields (optional, not guaranteed by backend)
    name?: string;
    description?: string;
    base_probability?: number;
    explanation?: CauseScoreExplanation;
    missing_expected_evidence?: string[];
}

export interface DiagnosticQuestion {
    question_id: string;
    text: string;
    purpose: string;
    usefulness_score: number;
    target_causes: string[];
    already_answered: boolean;
    options: string[];

    // Legacy / UI display compatibility fields (optional)
    reasoning?: string;
}

export interface DiagnosticCheck {
    check_id: string;
    name: string;
    description: string;
    procedure: string;
    priority_score: number;
    target_causes: string[];
    reasoning: string;
    required_access: string;
    effort_level: string;
    possible_outcomes: string[];

    // Legacy / UI display compatibility fields (optional)
    status?: string;
    applicable_defects?: string[];
}

export interface DiagnosisResult {
    case_id: string;
    defect: string | null;
    defect_name: string | null;
    ranked_causes: CandidateCause[];
    next_question: DiagnosticQuestion | null;
    next_check: DiagnosticCheck | null;
    explanation: string;
    issue_condition: "UNRESOLVED" | "RECOVERY_PENDING_VERIFICATION" | "RESOLVED" | "RECURRED";
    analysis_revision: AnalysisRevision | null;
    warnings: string[];

    // Legacy / UI display compatibility fields (optional)
    defect_confidence?: number;
}

export interface QuestionAnswerRecord {
    question_id: string;
    answer_value: string;
    answer_text?: string;
    source: string;
    answered_at: string;
    resulting_revision_number: number;
    text?: string;
    reasoning?: string;
    options?: string[];
}

export interface CheckResultRecord {
    check_id: string;
    execution_status: string;
    finding: string;
    finding_details?: string;
    outcome?: string;
    source: string;
    checked_at: string;
    resulting_revision_number: number;
    name?: string;
    description?: string;
    procedure?: string;
    effort_level?: string;
    target_causes?: string[];
}

export interface AnalysisRevision {
    revision_number: number;
    timestamp: string;
    defect_code: string | null;
    ranked_causes: CandidateCause[];
    new_evidence_summary: string;
    changes_from_previous: string[];
}

export interface DurableCaseResponse {
    case_id: string;
    description: string;
    material?: string;
    method?: string;
    machine_context?: Record<string, string | number | boolean | null | undefined>;
    defect_code?: string;
    defect_name?: string;
    issue_condition: string;
    created_at: string;
    observations: CaseObservationResponse[];
    previous_answers: QuestionAnswerRecord[];
    previous_check_results: CheckResultRecord[];
    analysis_revisions: AnalysisRevision[];
    initial_diagnosis: DiagnosisResult;
    diagnosis: DiagnosisResult;
}
