"""
Dispense Lens - Statistical Process Control (SPC) Schemas

Defines the data contract for Cleanroom Dispensing Process Capability (Cp/Cpk),
I-MR (Individuals & Moving Range) control charts, and Gaussian normal distributions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SpcDataPoint(BaseModel):
    """An individual metrology measurement on the cleanroom dispensing line."""
    index: int = Field(..., description="Chronological sequential run index")
    timestamp: str = Field(..., description="Timestamp of the measurement")
    value: float = Field(..., description="Observed measurement value")
    moving_range: Optional[float] = Field(None, description="|X_i - X_{i-1}| for I-MR chart")
    subgroup_id: str = Field(..., description="Batch or lot identification code")
    line_id: str = Field(..., description="Dispensing line ID")
    is_out_of_control: bool = Field(False, description="True if any Nelson / Western Electric rule is triggered")
    violations: List[str] = Field(default_factory=list, description="Triggered Nelson rule codes")


class SpcCapabilityMetrics(BaseModel):
    """Calculated statistical process capability indices and control limits."""
    parameter: str = Field(..., description="Parameter key, e.g. dot_diameter, dispense_weight")
    parameter_label: str = Field(..., description="Display label, e.g. Dot Diameter")
    unit: str = Field(..., description="Engineering unit, e.g. µm, mg, kPa")
    sample_count: int = Field(...)

    # Specification limits (Engineering tolerances)
    target: float = Field(..., description="Nominal target value T")
    usl: float = Field(..., description="Upper Specification Limit")
    lsl: float = Field(..., description="Lower Specification Limit")

    # Statistical central tendencies
    mean: float = Field(..., description="Sample mean X-bar")
    mean_offset: float = Field(..., description="Difference from nominal target (X-bar - T)")
    std_dev_overall: float = Field(..., description="Overall sample standard deviation (s)")
    std_dev_within: float = Field(..., description="Within-subgroup standard deviation (MR-bar / d2)")

    # Control limits for Individuals (X) chart
    ucl: float = Field(..., description="Upper Control Limit (X-bar + 3 * sigma_within)")
    cl: float = Field(..., description="Center Line (X-bar)")
    lcl: float = Field(..., description="Lower Control Limit (X-bar - 3 * sigma_within)")

    # Control limits for Moving Range (MR) chart
    ucl_mr: float = Field(..., description="Upper Control Limit for MR (3.267 * MR-bar)")
    cl_mr: float = Field(..., description="Center Line for MR (MR-bar)")

    # Capability indices
    cp: float = Field(..., description="Process Capability (USL - LSL) / (6 * sigma_within)")
    cpk: float = Field(..., description="Process Capability Index min(USL - X-bar, X-bar - LSL) / (3 * sigma_within)")
    pp: float = Field(..., description="Process Performance (USL - LSL) / (6 * s_overall)")
    ppk: float = Field(..., description="Process Performance Index min(USL - X-bar, X-bar - LSL) / (3 * s_overall)")
    cpm: float = Field(..., description="Taguchi capability index penalizing deviation from target T")
    ppm_total: float = Field(..., description="Estimated Parts Per Million non-conforming")

    # Quality classification
    capability_status: str = Field(..., description="WORLD_CLASS (Cpk >= 1.67), CAPABLE (1.33-1.67), MARGINAL (1.00-1.33), INCAPABLE (< 1.00)")
    status_description: str = Field(...)


class SpcHistogramBin(BaseModel):
    """A single frequency bin in the process capability histogram."""
    bin_start: float
    bin_end: float
    bin_center: float
    count: int
    frequency: float
    normal_pdf: float = Field(..., description="Height of fitted Gaussian normal PDF at bin_center")


class SpcNormalCurvePoint(BaseModel):
    """X, Y coordinates for plotting the fitted smooth Gaussian normal distribution curve."""
    x: float
    y: float


class SpcLineComparison(BaseModel):
    """Comparative capability summary across different dispensing equipment lines."""
    line_id: str
    line_name: str
    technology: str
    sample_count: int
    mean: float
    std_dev: float
    cp: float
    cpk: float
    violations_count: int
    status: str


class SpcAnalysisResponse(BaseModel):
    """Complete response payload for the Statistical Process Control (SPC) analytics suite."""
    parameter: str
    line_id: str
    sample_size: int
    metrics: SpcCapabilityMetrics
    data_points: List[SpcDataPoint]
    histogram: List[SpcHistogramBin]
    normal_curve: List[SpcNormalCurvePoint]
    line_comparisons: List[SpcLineComparison]
    rules_violated_summary: Dict[str, int]
    generated_at: str
