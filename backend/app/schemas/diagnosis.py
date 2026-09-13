"""
DispenseIQ — Diagnostic Intelligence Data Contracts

All typed Pydantic models used by the diagnosis engine.
These are internal engine contracts, not database ORM models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DefectCode(str, Enum):
    """Six mandatory dispensing-defect types."""
    D01_TOO_LITTLE = "D01_TOO_LITTLE"
    D02_TOO_MUCH = "D02_TOO_MUCH"
    D03_INCONSISTENT_SIZE = "D03_INCONSISTENT_SIZE"
    D04_MISSING_DOTS = "D04_MISSING_DOTS"
    D05_SPREADING = "D05_SPREADING"
    D06_BUBBLES_ABNORMAL_SHAPE = "D06_BUBBLES_ABNORMAL_SHAPE"


class EvidenceRelation(str, Enum):
    """How an observation relates to a candidate cause."""
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"
    DUPLICATE = "DUPLICATE"


class EvidenceStrength(str, Enum):
    """Strength qualifier for an evidence relation."""
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


class EvidenceSource(str, Enum):
    """Provenance of an evidence item."""
    USER = "USER"
    USER_ANSWER = "USER_ANSWER"
    MEASUREMENT = "MEASUREMENT"
    IMAGE = "IMAGE"
    SYSTEM = "SYSTEM"
    HISTORICAL_CASE = "HISTORICAL_CASE"


class ObservationType(str, Enum):
    """Categories of structured observation."""
    DEPOSIT_SIZE = "deposit_size"
    DEPOSIT_COUNT = "deposit_count"
    DEPOSIT_SHAPE = "deposit_shape"
    DEPOSIT_PRESENCE = "deposit_presence"
    TIME_PATTERN = "time_pattern"
    RUNTIME_PATTERN = "runtime_pattern"
    LOCATION_PATTERN = "location_pattern"
    SPATIAL_PATTERN = "spatial_pattern"
    FREQUENCY_PATTERN = "frequency_pattern"
    MATERIAL_STATE = "material_state"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    NOZZLE_CONDITION = "nozzle_condition"
    EQUIPMENT_CONDITION = "equipment_condition"
    PROCESS_PARAMETER = "process_parameter"
    VISUAL_APPEARANCE = "visual_appearance"
    BUBBLE_PRESENCE = "bubble_presence"
    SPREADING_BEHAVIOUR = "spreading_behaviour"
    OTHER = "other"
    QUESTION_ANSWER = "question_answer"

    # Aliases for flexible schema compatibility
    OPERATING_TIME_PATTERN = RUNTIME_PATTERN
    PRESSURE_TREND = PRESSURE
    WARMUP_CORRELATION = RUNTIME_PATTERN
    MATERIAL_BATCH_STATUS = MATERIAL_STATE
    CLEANING_STATUS = NOZZLE_CONDITION
    AIR_LINE_CHECK = BUBBLE_PRESENCE
    TEMPERATURE_DRIFT = TEMPERATURE
    MAINTENANCE_STATUS = EQUIPMENT_CONDITION
    IDLE_TIME_CORRELATION = RUNTIME_PATTERN
    SUBSTRATE_CHANGE_STATUS = SPREADING_BEHAVIOUR
    SPEED_CHANGE_LOCATION = LOCATION_PATTERN
    MECHANICAL_STATUS = EQUIPMENT_CONDITION
    VALVE_ACTUATION_SOUND = EQUIPMENT_CONDITION
    DEFECT_SYMPTOM = OTHER


class StatementType(str, Enum):
    """Distinguishes what kind of user statement was made."""
    USER_OBSERVATION = "USER_OBSERVATION"
    USER_INTERPRETATION = "USER_INTERPRETATION"
    AI_INFERENCE = "AI_INFERENCE"


class CheckExecutionStatus(str, Enum):
    """Status of a troubleshooting check execution."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SKIPPED = "SKIPPED"


class CheckFinding(str, Enum):
    """Finding from a completed troubleshooting check."""
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CauseConclusion(str, Enum):
    """Conclusion state of a candidate cause."""
    SUSPECTED = "SUSPECTED"
    CONFIRMED = "CONFIRMED"
    UNRESOLVED = "UNRESOLVED"


class IssueCondition(str, Enum):
    """Overall condition of the dispensing issue."""
    UNRESOLVED = "UNRESOLVED"
    RECOVERY_PENDING_VERIFICATION = "RECOVERY_PENDING_VERIFICATION"
    RESOLVED = "RESOLVED"
    RECURRED = "RECURRED"


class AnswerValue(str, Enum):
    """Standard answer values for diagnostic questions."""
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PARTIAL = "PARTIAL"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------

class Observation(BaseModel):
    """A single structured observation extracted from user input."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    observation_type: ObservationType = Field(..., alias="type")
    value: str
    original_text: str | None = None
    statement_type: StatementType = StatementType.USER_OBSERVATION
    source: EvidenceSource = Field(default=EvidenceSource.USER, alias="provenance")
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    @property
    def type(self) -> str:
        """Alias for observation_type to support Member 3 contract."""
        val = self.observation_type
        return str(val.value if hasattr(val, "value") else val)

    @property
    def provenance(self) -> str:
        """Alias for source to support Member 3 contract."""
        val = self.source
        return str(val.value if hasattr(val, "value") else val)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Observation):
            return False
        # Normalize type: spatial_pattern == location_pattern
        s_type = str(self.observation_type.value if hasattr(self.observation_type, "value") else self.observation_type)
        o_type = str(other.observation_type.value if hasattr(other.observation_type, "value") else other.observation_type)
        if s_type == "spatial_pattern" and o_type == "location_pattern":
            type_match = True
        elif s_type == "location_pattern" and o_type == "spatial_pattern":
            type_match = True
        else:
            type_match = (s_type == o_type)

        # Normalize value: systemic == all_points, localized == specific_nozzle
        s_val = self.value
        o_val = other.value
        norm_map = {"systemic": "all_points", "localized": "specific_nozzle"}
        s_norm = norm_map.get(s_val, s_val)
        o_norm = norm_map.get(o_val, o_val)
        val_match = (s_val == o_val) or (s_norm == o_norm)

        # Provenance: USER and USER_ANSWER are treated as equivalent user origins
        s_src = str(self.source.value if hasattr(self.source, "value") else self.source)
        o_src = str(other.source.value if hasattr(other.source, "value") else other.source)
        src_match = (s_src == o_src) or (s_src in ("USER", "USER_ANSWER") and o_src in ("USER", "USER_ANSWER"))

        return type_match and val_match and src_match


class ExtractionResult(BaseModel):
    """Result of symptom extraction from natural-language input."""
    original_description: str
    observations: list[Observation] = []
    user_hypotheses: list[str] = []
    extraction_method: str = "deterministic"
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Knowledge Models
# ---------------------------------------------------------------------------

class DefectDefinition(BaseModel):
    """Static definition of a defect type from the knowledge base."""
    code: str
    name: str
    description: str
    symptom_patterns: list[dict[str, str]] = []
    applicable_causes: list[str] = []
    source_references: list[str] = []


class CauseDefinition(BaseModel):
    """Static definition of a candidate cause from the knowledge base."""
    id: str
    name: str
    description: str
    applicable_defects: list[str] = []
    applicable_contexts: list[str] = []
    source_references: list[str] = []


class QuestionDefinition(BaseModel):
    """Static definition of a diagnostic question from the knowledge base."""
    id: str
    text: str
    purpose: str = ""
    applicable_causes: list[str] = []
    applicable_defects: list[str] = []
    expected_answer_type: str = "yes_no"
    follow_up_questions: list[str] = []
    evidence_mapping: dict[str, Any] = Field(default_factory=dict)


class CheckDefinition(BaseModel):
    """Static definition of a troubleshooting check from the knowledge base."""
    id: str
    name: str
    description: str
    procedure: str = ""
    applicable_causes: list[str] = []
    applicable_defects: list[str] = []
    required_access: str = ""
    effort_level: str = "medium"
    source_references: list[str] = []
    evidence_mapping: dict[str, Any] = Field(default_factory=dict)


class EvidenceRule(BaseModel):
    """Rule mapping an observation pattern to its effect on a cause."""
    id: str
    observation_type: str
    observation_value: str
    cause_id: str
    relation: EvidenceRelation
    strength: EvidenceStrength = EvidenceStrength.MODERATE
    explanation: str = ""


# ---------------------------------------------------------------------------
# Evidence & Ranking Models
# ---------------------------------------------------------------------------

class CauseEvidence(BaseModel):
    """Evidence evaluation for one observation against one cause."""
    observation_id: str
    cause_id: str
    relation: EvidenceRelation
    strength: EvidenceStrength = EvidenceStrength.MODERATE
    source: EvidenceSource = EvidenceSource.USER
    explanation: str = ""
    is_duplicate: bool = False
    duplicate_of: str | None = None
    score_contribution: float = 0.0


class CandidateCause(BaseModel):
    """A ranked candidate cause with all supporting/contradicting evidence."""
    cause_id: str
    cause_name: str
    score: float = 0.0
    conclusion: CauseConclusion = CauseConclusion.SUSPECTED
    supporting_evidence: list[CauseEvidence] = []
    contradicting_evidence: list[CauseEvidence] = []
    neutral_evidence: list[CauseEvidence] = []
    missing_evidence: list[str] = []
    score_breakdown: dict[str, float] = Field(default_factory=dict)

    @property
    def evidence(self) -> list[CauseEvidence]:
        """All evidence items evaluated for this candidate cause."""
        return self.supporting_evidence + self.contradicting_evidence + self.neutral_evidence


# ---------------------------------------------------------------------------
# Question & Check Models (runtime)
# ---------------------------------------------------------------------------

class Question(BaseModel):
    """A diagnostic question selected by the question engine."""
    question_id: str
    text: str
    purpose: str = ""
    usefulness_score: float = 0.0
    target_causes: list[str] = []
    already_answered: bool = False


class QuestionAnswer(BaseModel):
    """An answer to a diagnostic question provided by the user."""
    question_id: str
    answer_value: str
    answer_text: str | None = None
    source: EvidenceSource = EvidenceSource.USER
    timestamp: datetime = Field(default_factory=_utc_now)


class TroubleshootingCheck(BaseModel):
    """A troubleshooting check selected by the action planner."""
    check_id: str
    name: str
    description: str = ""
    procedure: str = ""
    priority_score: float = 0.0
    target_causes: list[str] = []
    reasoning: str = ""
    required_access: str = ""
    effort_level: str = "medium"


class CheckResult(BaseModel):
    """Result of a troubleshooting check performed by a technician."""
    check_id: str
    execution_status: CheckExecutionStatus
    finding: CheckFinding
    finding_details: str | None = None
    source: EvidenceSource = EvidenceSource.USER
    timestamp: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Analysis Revision
# ---------------------------------------------------------------------------

class AnalysisRevision(BaseModel):
    """A snapshot of the diagnosis at a point in time."""
    revision_number: int = 1
    timestamp: datetime = Field(default_factory=_utc_now)
    defect_code: str | None = None
    ranked_causes: list[CandidateCause] = []
    new_evidence_summary: str = ""
    changes_from_previous: list[str] = []


# ---------------------------------------------------------------------------
# Structured Case
# ---------------------------------------------------------------------------

class StructuredCase(BaseModel):
    """The full structured case that flows through the diagnosis engine."""
    case_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    material: str | None = None
    method: str | None = None
    machine_context: dict[str, Any] | None = None
    defect_code: str | None = None
    defect_name: str | None = None
    observations: list[Observation] = []
    previous_answers: list[QuestionAnswer] = []
    previous_check_results: list[CheckResult] = []
    analysis_revisions: list[AnalysisRevision] = []
    issue_condition: IssueCondition = IssueCondition.UNRESOLVED
    created_at: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Top-Level Request / Result
# ---------------------------------------------------------------------------

class DiagnosisRequest(BaseModel):
    """Input to the diagnostic engine."""
    case_id: str | None = None
    description: str = ""
    material: str | None = None
    method: str | None = None
    machine_context: dict[str, Any] | None = None
    defect_code: str | None = None
    observations: list[Observation] = []
    previous_answers: list[QuestionAnswer] = []
    previous_check_results: list[CheckResult] = []
    analysis_revision: int = 1


class DiagnosisResult(BaseModel):
    """Output from the diagnostic engine."""
    case_id: str
    defect: str | None = None
    defect_name: str | None = None
    ranked_causes: list[CandidateCause] = []
    next_question: Question | None = None
    next_check: TroubleshootingCheck | None = None
    explanation: str = ""
    analysis_revision: AnalysisRevision | None = None
    issue_condition: IssueCondition = IssueCondition.UNRESOLVED
    warnings: list[str] = []
