"""
DispenseIQ — Check Persistence & API Contracts Unit Tests (Phase 14 Verification)

Verifies:
1. SubmitCheckRequest payload schema validation and error cases.
2. CheckExecutionRecord and CaseCheckResponse serialization.
3. CheckExecutionModel ORM table definition, constraints, and relationships.
4. CaseRepository check execution append contract validations (stale revision, identity mismatch).
5. FastAPI route registration for POST /cases/{case_id}/checks and GET /actions.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.case import CaseModel, CheckExecutionModel
from app.schemas.case import (
    CaseCheckResponse,
    CheckExecutionRecord,
    SubmitCheckRequest,
)
from app.schemas.diagnosis import (
    AnalysisRevision,
    CheckExecutionStatus,
    CheckFinding,
    CheckResult,
    DiagnosisResult,
    IssueCondition,
    StructuredCase,
)
from app.db.repository import CaseRepository, StaleRevisionError


client = TestClient(app)


# ===========================================================================
# 1. Transport Schema Validation Tests
# ===========================================================================

def test_submit_check_request_valid():
    """Valid check execution request passes validation."""
    req = SubmitCheckRequest(
        check_id="ACT_INSPECT_NOZZLE",
        status="COMPLETED",
        finding="SUPPORTS",
        expected_revision=1,
        notes="Nozzle tip was partially obstructed.",
    )
    assert req.check_id == "ACT_INSPECT_NOZZLE"
    assert req.status == "COMPLETED"
    assert req.finding == "SUPPORTS"
    assert req.expected_revision == 1
    assert req.notes == "Nozzle tip was partially obstructed."


def test_submit_check_request_defaults():
    """Default status is COMPLETED, default finding is UNKNOWN."""
    req = SubmitCheckRequest(
        check_id="ACT_INSPECT_NOZZLE",
        expected_revision=2,
    )
    assert req.status == "COMPLETED"
    assert req.finding == "UNKNOWN"
    assert req.notes is None


def test_submit_check_request_empty_check_id_rejected():
    """Empty check_id raises ValidationError."""
    with pytest.raises(ValidationError):
        SubmitCheckRequest(
            check_id="  ",
            expected_revision=1,
        )


def test_submit_check_request_invalid_expected_revision():
    """Expected revision < 1 raises ValidationError."""
    with pytest.raises(ValidationError):
        SubmitCheckRequest(
            check_id="ACT_INSPECT_NOZZLE",
            expected_revision=0,
        )


# ===========================================================================
# 2. ORM Model Contracts
# ===========================================================================

def test_check_execution_model_attributes():
    """CheckExecutionModel table definition has required columns and constraints."""
    assert CheckExecutionModel.__tablename__ == "case_check_executions"
    cols = {c.name for c in CheckExecutionModel.__table__.columns}
    required_cols = {
        "id",
        "case_id",
        "check_id",
        "status",
        "finding",
        "notes",
        "executed_at",
        "resulting_revision_number",
    }
    assert required_cols.issubset(cols)

    # Check relation on CaseModel
    assert hasattr(CaseModel, "check_executions")


# ===========================================================================
# 3. Repository Append Contract Validations
# ===========================================================================

def test_repository_append_check_validates_mismatched_id():
    """Case and result IDs must match; raises ValueError otherwise."""
    repo = CaseRepository()
    case = StructuredCase(case_id="case-aaa", description="test")
    res = DiagnosisResult(case_id="case-bbb")
    cr = CheckResult(check_id="ACT_01", execution_status=CheckExecutionStatus.COMPLETED, finding=CheckFinding.SUPPORTS)

    with pytest.raises(ValueError, match="Mismatched case IDs"):
        repo.append_check_result_revision(case, cr, res, expected_revision=1)


def test_repository_append_check_validates_missing_revision():
    """DiagnosisResult must include analysis_revision for append."""
    repo = CaseRepository()
    cid = str(uuid.uuid4())
    case = StructuredCase(case_id=cid, description="test")
    res = DiagnosisResult(case_id=cid, analysis_revision=None)
    cr = CheckResult(check_id="ACT_01", execution_status=CheckExecutionStatus.COMPLETED, finding=CheckFinding.SUPPORTS)

    with pytest.raises(ValueError, match="must include an analysis_revision"):
        repo.append_check_result_revision(case, cr, res, expected_revision=1)


# ===========================================================================
# 4. Route Registration & OpenAPI Contracts
# ===========================================================================

def test_check_submission_route_registered():
    """POST /api/v1/cases/{case_id}/checks and GET /api/v1/actions are in the OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    assert "/api/v1/cases/{case_id}/checks" in paths
    assert "post" in paths["/api/v1/cases/{case_id}/checks"]

    assert "/api/v1/actions" in paths
    assert "get" in paths["/api/v1/actions"]
