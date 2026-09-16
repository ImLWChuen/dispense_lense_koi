"""
DispenseIQ — Durable Case Schemas

Defines request and response schemas for persistent diagnostic case lifecycle
operations under /api/v1/cases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.knowledge import get_defect_by_code
from app.schemas.diagnosis import (
    CauseConclusion,
    CheckExecutionStatus,
    CheckFinding,
    DiagnosisRequest,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    Question,
    StatementType,
    TroubleshootingCheck,
    AnalysisRevision,
)


class CreateCaseRequest(BaseModel):
    """Transport schema for initiating and persisting a durable diagnostic case.

    Accepts an initial problem description and/or structured observations.
    Rejects caller-supplied case IDs, revision history, or prior answers/checks.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    problem_description: str | None = None
    material: str | None = None
    method: str | None = None
    machine_context: dict[str, Any] | None = None
    defect_code: str | None = None
    observations: list[Observation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_request_payload(self) -> CreateCaseRequest:
        # Allow problem_description as an alias for description
        if self.problem_description and not self.description:
            self.description = self.problem_description

        # Validate defect_code against knowledge base if supplied
        if self.defect_code is not None:
            defect = get_defect_by_code(self.defect_code)
            if defect is None:
                raise ValueError(f"Unknown defect code: '{self.defect_code}'")

        # Validate that sufficient evidence input is provided
        has_description = bool(self.description and self.description.strip())
        has_observations = bool(self.observations)
        if not has_description and not has_observations:
            raise ValueError(
                "Insufficient evidence input: provide a non-empty description or at least one observation."
            )

        return self

    def to_diagnosis_request(self) -> DiagnosisRequest:
        """Convert transport request into domain DiagnosisRequest for engine evaluation."""
        return DiagnosisRequest(
            case_id=None,
            description=self.description,
            material=self.material,
            method=self.method,
            machine_context=self.machine_context,
            defect_code=self.defect_code,
            observations=list(self.observations),
            previous_answers=[],
            previous_check_results=[],
            analysis_revision=1,
        )


class QuestionAnswerRecord(BaseModel):
    """Persisted record of a technician question answer."""

    model_config = ConfigDict(extra="ignore")

    question_id: str
    answer_value: str
    answer_text: str | None = None
    source: EvidenceSource | str = EvidenceSource.USER
    answered_at: datetime
    resulting_revision_number: int
    text: str | None = None
    reasoning: str | None = None
    options: list[Any] | None = None


class CheckResultRecord(BaseModel):
    """Persisted record of a technician troubleshooting check result."""

    model_config = ConfigDict(extra="ignore")

    check_id: str
    execution_status: CheckExecutionStatus | str
    finding: CheckFinding | str
    finding_details: str | None = None
    outcome: str | None = None
    source: EvidenceSource | str = EvidenceSource.USER_CHECK_RESULT
    checked_at: datetime
    resulting_revision_number: int
    name: str | None = None
    description: str | None = None
    procedure: str | None = None
    effort_level: str | None = None
    target_causes: list[str] | None = None


class CaseObservationResponse(BaseModel):
    """Observation representation in durable case responses."""

    model_config = ConfigDict(extra="ignore")

    id: str
    observation_id: str
    observation_type: ObservationType | str
    value: str
    original_text: str | None = None
    statement_type: StatementType | str = StatementType.USER_OBSERVATION
    source: EvidenceSource | str = EvidenceSource.USER
    confidence: float | None = None
    timestamp: datetime
    created_at: datetime
    first_seen_revision: int = 1


class DurableCaseResponse(BaseModel):
    """Canonical representation of a persisted diagnostic case."""

    model_config = ConfigDict(extra="ignore")

    case_id: str
    description: str = ""
    material: str | None = None
    method: str | None = None
    machine_context: dict[str, Any] | None = None
    defect_code: str | None = None
    defect_name: str | None = None
    issue_condition: IssueCondition | str
    created_at: datetime
    observations: list[CaseObservationResponse] = Field(default_factory=list)
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    previous_check_results: list[CheckResultRecord] = Field(default_factory=list)
    analysis_revisions: list[AnalysisRevision] = Field(default_factory=list)
    initial_diagnosis: DiagnosisResult
    diagnosis: DiagnosisResult


class SubmitAnswerRequest(BaseModel):
    """Transport schema for submitting a technician question answer.

    Enforces optimistic concurrency via expected_revision and validates that
    the required question ID and answer string are non-empty.
    """

    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(
        ...,
        description="Identifier of the diagnostic question being answered (e.g. 'Q01').",
    )
    answer: str = Field(
        ...,
        description="The technician answer string or key (e.g. 'after_prolonged_operation', 'UNKNOWN').",
    )
    expected_revision: int = Field(
        ...,
        description="Expected current revision number of the case for optimistic locking.",
    )
    answer_text: str | None = Field(
        default=None,
        description="Optional raw technician statement or additional context.",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_answer_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "answer" not in data and "answer_value" in data:
                data = dict(data)
                data["answer"] = data.pop("answer_value")
        return data

    @model_validator(mode="after")
    def validate_payload(self) -> SubmitAnswerRequest:
        if not self.question_id or not self.question_id.strip():
            raise ValueError("question_id must be a non-empty string.")
        if not self.answer or not self.answer.strip():
            raise ValueError("answer must be a non-empty string.")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be >= 1.")
        return self


class CaseAnswerResponse(DurableCaseResponse):
    """Canonical representation of a durable case after question answer submission.

    Extends DurableCaseResponse with current revision, the newly submitted answer record,
    full answer history, previous check results, and recommended next steps.
    """

    current_revision: int
    submitted_answer: QuestionAnswerRecord
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    previous_check_results: list[CheckResultRecord] = Field(default_factory=list)
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None


class SubmitCheckResultRequest(BaseModel):
    """Transport schema for submitting a technician troubleshooting check result.

    Enforces optimistic concurrency via expected_revision and validates that
    check_id is non-empty and expected_revision is >= 1.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    check_id: str = Field(
        ...,
        description="Identifier of the troubleshooting check performed (e.g. 'ACT01').",
    )
    execution_status: CheckExecutionStatus = Field(
        default=CheckExecutionStatus.COMPLETED,
        validation_alias=AliasChoices("execution_status", "status"),
        description="Execution status of the check (COMPLETED, BLOCKED, FAILED, etc.).",
    )
    finding: CheckFinding = Field(
        default=CheckFinding.INCONCLUSIVE,
        validation_alias=AliasChoices("finding", "result"),
        description="Technician finding from the check (SUPPORTS, CONTRADICTS, INCONCLUSIVE, etc.).",
    )
    outcome: str | None = Field(
        default=None,
        description="Specific outcome key (e.g. 'blockage_found', 'consistent_but_wrong_size').",
    )
    finding_details: str | None = Field(
        default=None,
        description="Optional details or technician notes describing the finding.",
    )
    expected_revision: int = Field(
        ...,
        description="Expected current revision number of the case for optimistic locking.",
    )

    @field_validator("execution_status")
    @classmethod
    def validate_execution_status(cls, v: CheckExecutionStatus) -> CheckExecutionStatus:
        if v in (CheckExecutionStatus.PENDING, CheckExecutionStatus.IN_PROGRESS):
            raise ValueError(
                f"Cannot submit check result with unfinished execution status: '{v.value}'. "
                "Check must be completed, blocked, failed, skipped, unknown, or not applicable."
            )
        return v

    @model_validator(mode="after")
    def validate_payload(self) -> SubmitCheckResultRequest:
        if not self.check_id or not self.check_id.strip():
            raise ValueError("check_id must be a non-empty string.")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be >= 1.")
        if self.execution_status in (CheckExecutionStatus.PENDING, CheckExecutionStatus.IN_PROGRESS):
            raise ValueError(
                f"Cannot submit check result with unfinished execution status: '{self.execution_status.value}'. "
                "Check must be completed, blocked, failed, skipped, unknown, or not applicable."
            )
        return self


class CaseCheckResultResponse(DurableCaseResponse):
    """Canonical representation of a durable case after check result submission.

    Extends DurableCaseResponse with current revision, the newly submitted check result record,
    full check result history, previous answer history, and recommended next steps.
    """

    current_revision: int
    submitted_check_result: CheckResultRecord
    previous_check_results: list[CheckResultRecord] = Field(default_factory=list)
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None


class CauseConfirmationRecord(BaseModel):
    """Persisted record of an explicit technician root-cause confirmation."""

    model_config = ConfigDict(extra="ignore")

    cause_id: str
    confirmed_by: str = "technician"
    notes: str | None = None
    confirmed_at: datetime
    resulting_revision_number: int


class SubmitCauseConfirmationRequest(BaseModel):
    """Transport schema for explicitly confirming a diagnostic root cause.

    Enforces optimistic concurrency via expected_revision and validates that
    cause_id is non-empty and expected_revision is >= 1.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    cause_id: str = Field(
        ...,
        description="Identifier of the candidate cause being confirmed as root cause.",
    )
    expected_revision: int = Field(
        ...,
        description="Expected current revision number of the case for optimistic locking.",
    )
    confirmed_by: str = Field(
        default="technician",
        max_length=64,
        description="Identifier or role of the person confirming the cause.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional technician notes or observations explaining the confirmation.",
    )

    @model_validator(mode="after")
    def validate_payload(self) -> SubmitCauseConfirmationRequest:
        if not self.cause_id or not self.cause_id.strip():
            raise ValueError("cause_id must be a non-empty string.")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be >= 1.")
        if self.confirmed_by is not None and len(self.confirmed_by) > 64:
            raise ValueError("confirmed_by must be at most 64 characters.")
        return self


class CaseCauseConfirmationResponse(DurableCaseResponse):
    """Canonical representation of a durable case after explicit cause confirmation.

    Extends DurableCaseResponse with current revision, the newly submitted confirmation record,
    full confirmation history, check result history, answer history, and recommended next steps.
    """

    current_revision: int
    submitted_confirmation: CauseConfirmationRecord
    previous_confirmations: list[CauseConfirmationRecord] = Field(default_factory=list)
    previous_check_results: list[CheckResultRecord] = Field(default_factory=list)
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    confirmed_cause: str | None = None
    selected_cause_conclusion: CauseConclusion | str = CauseConclusion.CONFIRMED
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None


class LifecycleEventRecord(BaseModel):
    """Persisted record of an issue lifecycle event (recovery action or verification)."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    case_id: str
    event_type: str
    prior_issue_condition: IssueCondition | str
    resulting_issue_condition: IssueCondition | str
    resulting_revision_number: int
    actor: str = "technician"
    details: str = ""
    verification_passed: bool | None = None
    created_at: datetime


class SubmitRecoveryActionRequest(BaseModel):
    """Transport schema for recording an applied corrective/recovery action.

    Transitions issue condition to RECOVERY_PENDING_VERIFICATION.
    Enforces optimistic concurrency via expected_revision and validates that
    recovery_details is a non-empty string, expected_revision is >= 1, and
    performed_by is at most 64 characters.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_revision: int = Field(
        ...,
        description="Expected current revision number of the case for optimistic locking.",
    )
    recovery_details: str = Field(
        ...,
        description="Description of the applied corrective/recovery action.",
    )
    performed_by: str = Field(
        default="technician",
        max_length=64,
        description="Identifier or role of the person performing the recovery action.",
    )

    @model_validator(mode="after")
    def validate_payload(self) -> SubmitRecoveryActionRequest:
        if not self.recovery_details or not self.recovery_details.strip():
            raise ValueError("recovery_details must be a non-empty string.")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be >= 1.")
        if self.performed_by is not None and len(self.performed_by) > 64:
            raise ValueError("performed_by must be at most 64 characters.")
        return self


class SubmitRecoveryVerificationRequest(BaseModel):
    """Transport schema for verifying the recovery result of a case.

    Transitions issue condition to RESOLVED (if passed) or UNRESOLVED (if failed).
    Enforces optimistic concurrency via expected_revision and validates that
    expected_revision is >= 1, and verified_by is at most 64 characters.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_revision: int = Field(
        ...,
        description="Expected current revision number of the case for optimistic locking.",
    )
    verification_passed: bool = Field(
        ...,
        description="True if verification succeeded (test shots/inspection nominal), False otherwise.",
    )
    verification_details: str = Field(
        default="",
        description="Supporting notes or findings regarding the verification.",
    )
    verified_by: str = Field(
        default="technician",
        max_length=64,
        description="Identifier or role of the person verifying the recovery.",
    )

    @model_validator(mode="after")
    def validate_payload(self) -> SubmitRecoveryVerificationRequest:
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be >= 1.")
        if self.verified_by is not None and len(self.verified_by) > 64:
            raise ValueError("verified_by must be at most 64 characters.")
        return self


class CaseRecoveryActionResponse(DurableCaseResponse):
    """Canonical representation of a durable case after recovery action submission.

    Extends DurableCaseResponse with current revision, the submitted recovery action record,
    lifecycle event history, confirmation history, check result history, answer history,
    and recommended next steps.
    """

    current_revision: int
    submitted_recovery_action: LifecycleEventRecord
    submitted_event: LifecycleEventRecord
    lifecycle_events: list[LifecycleEventRecord] = Field(default_factory=list)
    previous_confirmations: list[CauseConfirmationRecord] = Field(default_factory=list)
    previous_check_results: list[CheckResultRecord] = Field(default_factory=list)
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    confirmed_cause: str | None = None
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None


class CaseRecoveryVerificationResponse(DurableCaseResponse):
    """Canonical representation of a durable case after recovery verification submission.

    Extends DurableCaseResponse with current revision, the submitted verification record,
    lifecycle event history, confirmation history, check result history, answer history,
    and recommended next steps.
    """

    current_revision: int
    submitted_verification: LifecycleEventRecord
    submitted_event: LifecycleEventRecord
    lifecycle_events: list[LifecycleEventRecord] = Field(default_factory=list)
    previous_confirmations: list[CauseConfirmationRecord] = Field(default_factory=list)
    previous_check_results: list[CheckResultRecord] = Field(default_factory=list)
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    confirmed_cause: str | None = None
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None


class SubmitRecurrenceRequest(BaseModel):
    """Transport schema for reporting a recurred issue on a previously resolved case.

    Transitions issue condition from RESOLVED to RECURRED.
    Enforces optimistic concurrency via expected_revision and validates that
    recurrence_details is a non-empty string, expected_revision is >= 1, and
    reported_by is at most 64 characters.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_revision: int = Field(
        ...,
        description="Expected current revision number of the case for optimistic locking.",
    )
    recurrence_details: str = Field(
        ...,
        description="Description of the recurred defect observations or symptoms.",
    )
    reported_by: str = Field(
        default="technician",
        max_length=64,
        description="Identifier or role of the person reporting the recurrence.",
    )

    @model_validator(mode="after")
    def validate_payload(self) -> SubmitRecurrenceRequest:
        if not self.recurrence_details or not self.recurrence_details.strip():
            raise ValueError("recurrence_details must be a non-empty string.")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be >= 1.")
        if self.reported_by is not None and len(self.reported_by) > 64:
            raise ValueError("reported_by must be at most 64 characters.")
        return self


class CaseRecurrenceResponse(DurableCaseResponse):
    """Canonical representation of a durable case after recurrence submission.

    Extends DurableCaseResponse with current revision, the submitted recurrence record,
    lifecycle event history, confirmation history, check result history, answer history,
    and recommended next steps.
    """

    current_revision: int
    submitted_recurrence: LifecycleEventRecord
    submitted_event: LifecycleEventRecord
    lifecycle_events: list[LifecycleEventRecord] = Field(default_factory=list)
    previous_confirmations: list[CauseConfirmationRecord] = Field(default_factory=list)
    previous_check_results: list[CheckResultRecord] = Field(default_factory=list)
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    confirmed_cause: str | None = None
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None


class CaseOutcomeSummary(BaseModel):
    """Compact direct projection of current persisted case outcome."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    issue_condition: IssueCondition | str = Field(
        ...,
        description="Current issue condition (e.g. UNRESOLVED, RECOVERY_PENDING_VERIFICATION, RESOLVED, RECURRED).",
    )
    current_revision: int = Field(
        ...,
        description="Current 1-based revision sequence number.",
    )
    confirmed_causes: list[str] = Field(
        default_factory=list,
        description="List of cause IDs that are currently confirmed based on persisted cause conclusions.",
    )
    currently_confirmed_causes: list[str] = Field(
        default_factory=list,
        description="Alias for confirmed_causes.",
    )
    is_resolved: bool = Field(
        ...,
        description="True if the issue_condition is currently RESOLVED, False otherwise.",
    )
    resolved: bool = Field(
        ...,
        description="Alias for is_resolved.",
    )


class CaseReportResponse(BaseModel):
    """Deterministic read model of a durable case and its full audit history."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # Case / report basis
    case_id: str = Field(..., description="Unique case identifier.")
    current_revision: int = Field(..., description="Current revision number of the case.")
    defect_code: str | None = Field(default=None, description="Persisted defect code identifier.")
    defect_name: str | None = Field(default=None, description="Persisted human-readable defect title.")
    description: str = Field(default="", description="Technician problem description.")
    material: str | None = Field(default=None, description="Fluid material name or category.")
    method: str | None = Field(default=None, description="Dispensing method.")
    machine_context: dict[str, Any] | None = Field(default=None, description="Equipment/process parameters.")
    issue_condition: IssueCondition | str = Field(..., description="Current issue condition.")
    created_at: datetime = Field(..., description="Case creation timestamp.")

    # Current diagnosis snapshot (latest persisted analysis)
    current_diagnosis: DiagnosisResult = Field(
        ...,
        description="Latest persisted diagnostic analysis snapshot.",
    )
    diagnosis: DiagnosisResult = Field(
        ...,
        description="Latest persisted diagnostic analysis snapshot (alias).",
    )

    # Audit histories in deterministic ascending order
    question_answers: list[QuestionAnswerRecord] = Field(
        default_factory=list,
        description="Chronological history of technician question-answer events.",
    )
    question_answer_history: list[QuestionAnswerRecord] = Field(
        default_factory=list,
        description="Chronological history of technician question-answer events (alias).",
    )
    check_results: list[CheckResultRecord] = Field(
        default_factory=list,
        description="Chronological history of technician troubleshooting-check events.",
    )
    troubleshooting_check_history: list[CheckResultRecord] = Field(
        default_factory=list,
        description="Chronological history of technician troubleshooting-check events (alias).",
    )
    cause_confirmations: list[CauseConfirmationRecord] = Field(
        default_factory=list,
        description="Chronological history of explicit root-cause confirmations.",
    )
    cause_confirmation_history: list[CauseConfirmationRecord] = Field(
        default_factory=list,
        description="Chronological history of explicit root-cause confirmations (alias).",
    )
    lifecycle_events: list[LifecycleEventRecord] = Field(
        default_factory=list,
        description="Chronological history of issue lifecycle events (recovery, verification, recurrence).",
    )
    issue_lifecycle_history: list[LifecycleEventRecord] = Field(
        default_factory=list,
        description="Chronological history of issue lifecycle events (alias).",
    )

    # Current outcome summary
    outcome_summary: CaseOutcomeSummary = Field(
        ...,
        description="Compact direct projection of current persisted outcome state.",
    )
    current_outcome_summary: CaseOutcomeSummary = Field(
        ...,
        description="Compact direct projection of current persisted outcome state (alias).",
    )
