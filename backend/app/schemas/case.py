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
    StatementType,
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
