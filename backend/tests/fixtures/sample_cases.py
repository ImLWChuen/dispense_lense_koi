"""
DispenseIQ — Sample Cases Test Fixtures (Section 23)

Provides standardized sample cases covering all six dispensing defects,
various process contexts, observations, and technician inputs.
"""

from __future__ import annotations

from typing import Any

from app.schemas.diagnosis import (
    DiagnosisRequest,
    EvidenceSource,
    Observation,
    ObservationType,
    StatementType,
)


SAMPLE_CASE_D01_TOO_LITTLE = DiagnosisRequest(
    description="Dispensed dots are too small and inconsistent across all dispensing locations.",
    material="silicone",
    method="time_pressure",
    machine_context={"pressure_bar": 1.8, "temperature_c": 22.5},
    observations=[
        Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="undersized",
            original_text="dots are too small",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
        Observation(
            observation_type=ObservationType.LOCATION_PATTERN,
            value="all_points",
            original_text="across all dispensing locations",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
    ],
)

SAMPLE_CASE_D02_TOO_MUCH = DiagnosisRequest(
    description="Deposits are oversized and excessive material is bleeding between pins.",
    material="epoxy",
    method="auger_screw",
    machine_context={"speed_mm_s": 50.0},
    observations=[
        Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="oversized",
            original_text="deposits are oversized",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
        Observation(
            observation_type=ObservationType.SPREADING_BEHAVIOUR,
            value="excessive_spread",
            original_text="excessive material is bleeding",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
    ],
)

SAMPLE_CASE_D03_INCONSISTENT_SIZE = DiagnosisRequest(
    description="Dispensing dots become smaller intermittently after prolonged operation of 20 minutes.",
    material="epoxy",
    method="time_pressure",
    machine_context={"runtime_minutes": 25},
    observations=[
        Observation(
            observation_type=ObservationType.DEPOSIT_SIZE,
            value="inconsistent",
            original_text="dots become smaller intermittently",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
        Observation(
            observation_type=ObservationType.RUNTIME_PATTERN,
            value="after_prolonged_operation",
            original_text="after prolonged operation of 20 minutes",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
    ],
)

SAMPLE_CASE_D04_MISSING_DOTS = DiagnosisRequest(
    description="No material dispensed at position 4; missing dots observed randomly on board.",
    material="solder_paste",
    method="jetting",
    machine_context={"valve_cycles": 120000},
    observations=[
        Observation(
            observation_type=ObservationType.DEPOSIT_PRESENCE,
            value="missing",
            original_text="missing dots observed",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
        Observation(
            observation_type=ObservationType.FREQUENCY_PATTERN,
            value="intermittent",
            original_text="randomly on board",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
    ],
)

SAMPLE_CASE_D05_SPREADING = DiagnosisRequest(
    description="Adhesive dots spread flat and run together after dispensing under high temperature.",
    material="underfill",
    method="jetting",
    machine_context={"ambient_temp_c": 32.0},
    observations=[
        Observation(
            observation_type=ObservationType.SPREADING_BEHAVIOUR,
            value="excessive_spread",
            original_text="dots spread flat and run together",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
        Observation(
            observation_type=ObservationType.TEMPERATURE,
            value="elevated",
            original_text="under high temperature",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
    ],
)

SAMPLE_CASE_D06_BUBBLES = DiagnosisRequest(
    description="Visible bubbles and voids trapped inside the dots with deformed craters.",
    material="silicone",
    method="time_pressure",
    machine_context={"air_purge_status": "skipped"},
    observations=[
        Observation(
            observation_type=ObservationType.BUBBLE_PRESENCE,
            value="visible_bubbles",
            original_text="visible bubbles and voids trapped",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
        Observation(
            observation_type=ObservationType.VISUAL_APPEARANCE,
            value="crater_shape",
            original_text="deformed craters",
            statement_type=StatementType.USER_OBSERVATION,
            source=EvidenceSource.USER,
        ),
    ],
)

ALL_SAMPLE_CASES = [
    SAMPLE_CASE_D01_TOO_LITTLE,
    SAMPLE_CASE_D02_TOO_MUCH,
    SAMPLE_CASE_D03_INCONSISTENT_SIZE,
    SAMPLE_CASE_D04_MISSING_DOTS,
    SAMPLE_CASE_D05_SPREADING,
    SAMPLE_CASE_D06_BUBBLES,
]
