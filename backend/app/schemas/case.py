"""
DispenseIQ — Durable Case Schemas

Defines request and response schemas for persistent diagnostic case lifecycle
operations under /api/v1/cases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.knowledge import get_defect_by_code
from app.schemas.diagnosis import (
    DiagnosisRequest,
    DiagnosisResult,
    EvidenceSource,
    IssueCondition,
    Observation,
    ObservationType,
    Question,
    StatementType,
    TroubleshootingCheck,
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


class QuestionAnswerRecord(BaseModel):
    """Persisted record of a technician question answer."""

    model_config = ConfigDict(extra="ignore")

    question_id: str
    answer_value: str
    answer_text: str | None = None
    source: EvidenceSource | str = EvidenceSource.USER
    answered_at: datetime
    resulting_revision_number: int


class CaseAnswerResponse(DurableCaseResponse):
    """Canonical representation of a durable case after question answer submission.

    Extends DurableCaseResponse with current revision, the newly submitted answer record,
    full answer history, and recommended next steps.
    """

    current_revision: int
    submitted_answer: QuestionAnswerRecord
    previous_answers: list[QuestionAnswerRecord] = Field(default_factory=list)
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None


class SubmitCheckRequest(BaseModel):
    """Transport schema for submitting a technician troubleshooting check result.

    Enforces optimistic concurrency via expected_revision and validates that
    the required check ID, status, and finding are valid domain values.
    """

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(
        ...,
        description="Identifier of the troubleshooting check executed (e.g. 'ACT_INSPECT_NOZZLE').",
    )
    status: str = Field(
        default="COMPLETED",
        description="Execution status (COMPLETED, BLOCKED, SKIPPED, FAILED, UNKNOWN, NOT_APPLICABLE).",
    )
    finding: str = Field(
        default="UNKNOWN",
        description="Observed check finding (SUPPORTS, CONTRADICTS, INCONCLUSIVE, UNKNOWN, NOT_APPLICABLE).",
    )
    expected_revision: int = Field(
        ...,
        description="Expected current revision number of the case for optimistic locking.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional technician notes or observations recorded during check.",
    )

    @model_validator(mode="after")
    def validate_payload(self) -> SubmitCheckRequest:
        if not self.check_id or not self.check_id.strip():
            raise ValueError("check_id must be a non-empty string.")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be >= 1.")
        return self


class CheckExecutionRecord(BaseModel):
    """Persisted record of a technician troubleshooting check execution."""

    model_config = ConfigDict(extra="ignore")

    check_id: str
    status: str
    finding: str
    notes: str | None = None
    executed_at: datetime
    resulting_revision_number: int


class CaseCheckResponse(DurableCaseResponse):
    """Canonical representation of a durable case after troubleshooting check submission.

    Extends DurableCaseResponse with current revision, the newly submitted check execution record,
    full check history, and recommended next steps.
    """

    current_revision: int
    submitted_check: CheckExecutionRecord
    previous_checks: list[CheckExecutionRecord] = Field(default_factory=list)
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None
