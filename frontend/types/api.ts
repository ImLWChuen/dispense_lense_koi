export interface Observation {
    id?: string;
    observation_type: string;
    value: string;
    original_text?: string;
    statement_type?: string;
    source?: string;
    confidence?: number;
    metadata?: Record<string, any>;
    timestamp?: string;
}

export interface CreateCaseRequest {
    description?: string;
    problem_description?: string;
    material?: string;
    method?: string;
    machine_context?: Record<string, any>;
    defect_code?: string;
    observations?: Observation[];
}

export interface CaseObservationResponse {
    id: string;
    observation_id: string;
    observation_type: string;
    value: string;
    original_text?: string;
    statement_type: string;
    source: string;
    confidence?: number;
    timestamp: string;
    created_at: string;
    first_seen_revision: number;
}

export interface CauseScoreExplanation {
    score: number;
    description: string;
}

export interface CandidateCause {
    cause_id: string;
    cause_name: string;
    description: string;
    base_probability: number;
    score: number;
    conclusion: "SUSPECTED" | "CONFIRMED" | "UNRESOLVED";
    supporting_evidence: any[];
    contradicting_evidence: any[];
    neutral_evidence: any[];
    missing_expected_evidence: string[];
    explanation?: CauseScoreExplanation;
}

export interface DiagnosisResult {
    case_id: string;
    defect: string;
    defect_name: string;
    defect_confidence: number;
    ranked_causes: CandidateCause[];
    next_question?: any;
    next_check?: any;
    issue_condition: "UNRESOLVED" | "RECOVERY_PENDING_VERIFICATION" | "RESOLVED" | "RECURRED";
    analysis_revision?: any;
}

export interface DurableCaseResponse {
    case_id: string;
    description: string;
    material?: string;
    method?: string;
    machine_context?: Record<string, any>;
    defect_code?: string;
    defect_name?: string;
    issue_condition: string;
    created_at: string;
    observations: CaseObservationResponse[];
    initial_diagnosis: DiagnosisResult;
    diagnosis: DiagnosisResult;
}
