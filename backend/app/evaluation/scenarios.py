"""
Dispense Lens - Evaluation Scenarios (Phase 15 Placeholder)

Defines 12 controlled functional benchmark scenarios covering all six mandatory
dispensing defect categories (6 defects × 2 scenarios each):
- Scenario A: Normal supported evidence leading to candidate causes.
- Scenario B: Missing, contradictory, or blocked check conditions.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class EvaluationScenario(BaseModel):
    """Specification of an evaluation benchmark scenario."""
    id: str
    defect_code: str
    name: str
    description: str
    expected_defect: str
    acceptable_causes: list[str] = Field(default_factory=list)
    expected_top_causes: list[str] = Field(default_factory=list)
    must_not_claim: list[str] = Field(default_factory=list)
    initial_observations: list[dict[str, Any]] = Field(default_factory=list)
    actions_to_simulate: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 12 Benchmark Scenarios
# ---------------------------------------------------------------------------

SCENARIOS: list[EvaluationScenario] = [
    # D01: Too Little Material
    EvaluationScenario(
        id="SCENARIO_D01_A",
        defect_code="D01_TOO_LITTLE",
        name="Too Little Material - Consistent Undersized",
        description="Dispensed dots are consistently undersized across all boards.",
        expected_defect="D01_TOO_LITTLE",
        acceptable_causes=["nozzle_restriction", "air_supply_issue", "pressure_instability"],
        expected_top_causes=["nozzle_restriction"],
        must_not_claim=["confirmed_cause", "issue_resolved"],
        initial_observations=[
            {"type": "deposit_size", "value": "undersized"},
            {"type": "frequency_pattern", "value": "consistent"},
        ],
    ),
    EvaluationScenario(
        id="SCENARIO_D01_B",
        defect_code="D01_TOO_LITTLE",
        name="Too Little Material - Blocked Check",
        description="Small deposits reported; nozzle check is blocked by production schedule.",
        expected_defect="D01_TOO_LITTLE",
        acceptable_causes=["nozzle_restriction", "air_supply_issue", "material_condition"],
        expected_top_causes=["nozzle_restriction", "air_supply_issue"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "deposit_size", "value": "undersized"},
        ],
        actions_to_simulate=[
            {"check_id": "ACT_INSPECT_NOZZLE", "status": "BLOCKED", "finding": "UNKNOWN"},
        ],
    ),

    # D02: Too Much Material
    EvaluationScenario(
        id="SCENARIO_D02_A",
        defect_code="D02_TOO_MUCH",
        name="Too Much Material - Normal Supported",
        description="Deposits are oversized with tailing visible after shots.",
        expected_defect="D02_TOO_MUCH",
        acceptable_causes=["parameter_issue", "pressure_instability", "valve_issue"],
        expected_top_causes=["parameter_issue", "valve_issue"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "deposit_size", "value": "oversized"},
            {"type": "visual_appearance", "value": "leaking_dripping"},
        ],
    ),
    EvaluationScenario(
        id="SCENARIO_D02_B",
        defect_code="D02_TOO_MUCH",
        name="Too Much Material - Contradictory Evidence",
        description="Excessive material observed but pressure check is confirmed normal and stable.",
        expected_defect="D02_TOO_MUCH",
        acceptable_causes=["parameter_issue", "material_condition", "valve_issue"],
        expected_top_causes=["valve_issue", "parameter_issue"],
        must_not_claim=["pressure_instability_as_top"],
        initial_observations=[
            {"type": "deposit_size", "value": "oversized"},
            {"type": "pressure", "value": "stable"},
        ],
    ),

    # D03: Inconsistent Dispensing Size
    EvaluationScenario(
        id="SCENARIO_D03_A",
        defect_code="D03_INCONSISTENT_SIZE",
        name="Inconsistent Size - Prolonged Runtime",
        description="The dispensing dots become smaller after the machine has been running for around 20 minutes.",
        expected_defect="D03_INCONSISTENT_SIZE",
        acceptable_causes=["air_supply_issue", "nozzle_restriction", "material_condition"],
        expected_top_causes=["air_supply_issue", "nozzle_restriction"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "deposit_size", "value": "undersized"},
            {"type": "runtime_pattern", "value": "after_prolonged_operation"},
        ],
    ),
    EvaluationScenario(
        id="SCENARIO_D03_B",
        defect_code="D03_INCONSISTENT_SIZE",
        name="Inconsistent Size - Intermittent With Clean Nozzle",
        description="Dot size varies intermittently across shots; nozzle clean check reveals no blockage.",
        expected_defect="D03_INCONSISTENT_SIZE",
        acceptable_causes=["air_supply_issue", "pressure_instability", "material_condition"],
        expected_top_causes=["air_supply_issue", "pressure_instability"],
        must_not_claim=["nozzle_restriction_as_top"],
        initial_observations=[
            {"type": "deposit_size", "value": "inconsistent"},
            {"type": "frequency_pattern", "value": "intermittent"},
            {"type": "nozzle_condition", "value": "clean"},
        ],
    ),

    # D04: Missing Dots
    EvaluationScenario(
        id="SCENARIO_D04_A",
        defect_code="D04_MISSING_DOTS",
        name="Missing Dots - Specific Nozzle",
        description="Missing deposits observed consistently at nozzle 3.",
        expected_defect="D04_MISSING_DOTS",
        acceptable_causes=["nozzle_restriction", "valve_issue", "equipment_condition"],
        expected_top_causes=["nozzle_restriction"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "deposit_presence", "value": "missing"},
            {"type": "location_pattern", "value": "specific_nozzle"},
        ],
    ),
    EvaluationScenario(
        id="SCENARIO_D04_B",
        defect_code="D04_MISSING_DOTS",
        name="Missing Dots - Intermittent Random",
        description="Dots occasionally missing at random points on the PCB.",
        expected_defect="D04_MISSING_DOTS",
        acceptable_causes=["air_supply_issue", "valve_issue", "pressure_instability"],
        expected_top_causes=["air_supply_issue"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "deposit_presence", "value": "missing"},
            {"type": "frequency_pattern", "value": "intermittent"},
        ],
    ),

    # D05: Spreading
    EvaluationScenario(
        id="SCENARIO_D05_A",
        defect_code="D05_SPREADING",
        name="Spreading - High Temperature",
        description="Adhesive dots bleed and spread excessively when ambient temperature is elevated.",
        expected_defect="D05_SPREADING",
        acceptable_causes=["material_condition", "parameter_issue", "substrate_condition"],
        expected_top_causes=["material_condition"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "spreading_behaviour", "value": "excessive_spread"},
            {"type": "temperature", "value": "elevated"},
        ],
    ),
    EvaluationScenario(
        id="SCENARIO_D05_B",
        defect_code="D05_SPREADING",
        name="Spreading - Low Viscosity Material Batch",
        description="Excessive wetting on substrate reported immediately after loading a new material batch.",
        expected_defect="D05_SPREADING",
        acceptable_causes=["material_condition", "parameter_issue"],
        expected_top_causes=["material_condition"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "spreading_behaviour", "value": "excessive_spread"},
            {"type": "material_state", "value": "low_viscosity"},
        ],
    ),

    # D06: Bubbles / Abnormal Shape
    EvaluationScenario(
        id="SCENARIO_D06_A",
        defect_code="D06_BUBBLES_ABNORMAL_SHAPE",
        name="Bubbles - Visible Voids",
        description="Air bubbles and craters visible in dispensed deposits after cartridge reload.",
        expected_defect="D06_BUBBLES_ABNORMAL_SHAPE",
        acceptable_causes=["air_supply_issue", "material_condition"],
        expected_top_causes=["air_supply_issue"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "bubble_presence", "value": "visible_bubbles"},
        ],
    ),
    EvaluationScenario(
        id="SCENARIO_D06_B",
        defect_code="D06_BUBBLES_ABNORMAL_SHAPE",
        name="Abnormal Shape - Damaged Nozzle Tip",
        description="Irregular satellite dots and deformed deposits with suspected nozzle tip contact.",
        expected_defect="D06_BUBBLES_ABNORMAL_SHAPE",
        acceptable_causes=["nozzle_condition", "parameter_issue"],
        expected_top_causes=["nozzle_condition"],
        must_not_claim=["confirmed_cause"],
        initial_observations=[
            {"type": "deposit_shape", "value": "abnormal"},
            {"type": "nozzle_condition", "value": "damaged"},
        ],
    ),
]
