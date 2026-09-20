"""
Dispense Lens - Retrieval and Historical Case Similarity Schemas

Defines response models for historical case similarity matching,
matched factor tags, and resolution summaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SimilarCaseItem(BaseModel):
    """Represents a historical case matched by similarity criteria."""

    model_config = ConfigDict(from_attributes=True)

    case_id: str = Field(..., description="Unique UUID string of the matched case")
    short_id: str = Field(..., description="Abbreviated 8-character uppercase identifier")
    defect_code: str | None = Field(None, description="Defect code taxonomy (e.g. D01, D03)")
    defect_name: str | None = Field(None, description="Human-readable defect title")
    description: str = Field(..., description="Problem description from technician")
    material: str | None = Field(None, description="Dispensed fluid material")
    method: str | None = Field(None, description="Dispensing technology method")
    line_id: str | None = Field(None, description="Production equipment line or dispenser model")
    issue_condition: str = Field(..., description="Current lifecycle state (e.g. RESOLVED)")
    is_resolved: bool = Field(..., description="Whether the case achieved successful resolution")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Normalized similarity score")
    similarity_percentage: int = Field(..., ge=0, le=100, description="Integer percentage match (0-100)")
    matching_factors: list[str] = Field(default_factory=list, description="List of matched attribute badges")
    confirmed_causes: list[str] = Field(default_factory=list, description="Root causes confirmed by technician")
    resolution_summary: str | None = Field(None, description="Summary of corrective action and recovery verification")
    created_at: datetime = Field(..., description="Case intake timestamp")
    resolved_at: datetime | None = Field(None, description="Timestamp when recovery was verified")


class SimilarCasesResponse(BaseModel):
    """Response payload for GET /api/v1/cases/{case_id}/similar."""

    target_case_id: str = Field(..., description="UUID of the reference case compared against")
    count: int = Field(..., ge=0, description="Total number of similar cases returned")
    similar_cases: list[SimilarCaseItem] = Field(default_factory=list, description="Ranked list of similar cases")
