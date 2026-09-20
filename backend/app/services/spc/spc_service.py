"""
Dispense Lens - Statistical Process Control (SPC) Service

Calculates cleanroom process capability indices (Cp, Cpk, Pp, Ppk, Cpm),
control limits (UCL, CL, LCL for I-MR charts), Nelson out-of-control rules,
frequency histogram bins, and normal Gaussian probability density distributions.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.schemas.spc import (
    SpcAnalysisResponse,
    SpcCapabilityMetrics,
    SpcDataPoint,
    SpcHistogramBin,
    SpcLineComparison,
    SpcNormalCurvePoint,
)

# Standard parameter specifications for Cleanroom Dispensing
PARAM_SPECS: dict[str, dict[str, Any]] = {
    "dot_diameter": {
        "label": "Dot Diameter",
        "unit": "µm",
        "target": 850.0,
        "usl": 950.0,
        "lsl": 750.0,
        "base_mean": 853.5,
        "base_sigma": 18.2,
    },
    "dispense_weight": {
        "label": "Deposit Weight",
        "unit": "mg",
        "target": 12.50,
        "usl": 14.00,
        "lsl": 11.00,
        "base_mean": 12.58,
        "base_sigma": 0.27,
    },
    "line_width": {
        "label": "Bead / Line Width",
        "unit": "µm",
        "target": 320.0,
        "usl": 360.0,
        "lsl": 280.0,
        "base_mean": 321.6,
        "base_sigma": 7.1,
    },
    "fluid_pressure": {
        "label": "Dispense Pressure",
        "unit": "kPa",
        "target": 240.0,
        "usl": 260.0,
        "lsl": 220.0,
        "base_mean": 241.4,
        "base_sigma": 3.4,
    },
}

# Line configurations
LINE_CONFIGS: dict[str, dict[str, Any]] = {
    "line-a": {"name": "Line A", "tech": "Piezoelectric Jetting", "sigma_mult": 1.0, "mean_shift": 0.2},
    "line-b": {"name": "Line B", "tech": "Auger Micro-Screw", "sigma_mult": 1.25, "mean_shift": 0.8},
    "line-c": {"name": "Line C", "tech": "Time-Pressure Pneumatic", "sigma_mult": 1.45, "mean_shift": -1.2},
    "line-d": {"name": "Line D", "tech": "Piston Positive Displacement", "sigma_mult": 0.95, "mean_shift": 0.1},
}


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float, mu: float, sigma: float) -> float:
    """Gaussian normal probability density function."""
    if sigma <= 0:
        return 0.0
    exponent = -0.5 * (((x - mu) / sigma) ** 2)
    return (1.0 / (sigma * math.sqrt(2.0 * math.pi))) * math.exp(exponent)


def generate_spc_analysis(
    parameter: str = "dot_diameter",
    line_id: str = "all",
    sample_size: int = 50,
) -> SpcAnalysisResponse:
    """Generate comprehensive Statistical Process Control analysis."""
    param_key = parameter if parameter in PARAM_SPECS else "dot_diameter"
    spec = PARAM_SPECS[param_key]
    
    target = spec["target"]
    usl = spec["usl"]
    lsl = spec["lsl"]
    base_mean = spec["base_mean"]
    base_sigma = spec["base_sigma"]
    
    # Adjust for selected line
    if line_id in LINE_CONFIGS:
        cfg = LINE_CONFIGS[line_id]
        mean_gen = base_mean + (cfg["mean_shift"] * base_sigma * 0.1)
        sigma_gen = base_sigma * cfg["sigma_mult"]
    else:
        mean_gen = base_mean
        sigma_gen = base_sigma

    # Generate pseudo-deterministic series
    rng = random.Random(hash((param_key, line_id, sample_size)) & 0xFFFFFFFF)
    now = datetime.now(timezone.utc)

    values: list[float] = []
    data_points: list[SpcDataPoint] = []
    
    start_time = now - timedelta(minutes=sample_size * 4)
    active_line_key = line_id if line_id in LINE_CONFIGS else "line-a"
    active_line_name = LINE_CONFIGS.get(active_line_key, {}).get("name", "Line A")

    for i in range(sample_size):
        # Generate with slight realistic cleanroom auto-correlation / shift
        drift = math.sin(i / 8.0) * (0.2 * sigma_gen)
        # Occasional Nelson rule simulation on points 28-30 for demonstration if >= 40 samples
        anomaly = 0.0
        if sample_size >= 40 and i == 32:
            anomaly = 3.2 * sigma_gen  # Rule 1 trigger
            
        val = rng.gauss(mean_gen + drift, sigma_gen) + anomaly
        val = round(val, 2 if spec["unit"] == "mg" else 1)
        values.append(val)

        ts = (start_time + timedelta(minutes=i * 4)).strftime("%H:%M:%S")
        lot_idx = (i // 10) + 1
        subgroup = f"LOT-{lot_idx:02d}"

        data_points.append(
            SpcDataPoint(
                index=i + 1,
                timestamp=ts,
                value=val,
                moving_range=None,
                subgroup_id=subgroup,
                line_id=active_line_name,
                is_out_of_control=False,
                violations=[],
            )
        )

    # Calculate Moving Ranges
    moving_ranges: list[float] = []
    for i in range(1, len(values)):
        mr = abs(values[i] - values[i - 1])
        moving_ranges.append(mr)
        data_points[i].moving_range = round(mr, 2 if spec["unit"] == "mg" else 1)

    n = len(values)
    mean_val = sum(values) / n
    mean_offset = mean_val - target

    # Sample standard deviation (s_overall)
    variance_sum = sum((x - mean_val) ** 2 for x in values)
    s_overall = math.sqrt(variance_sum / (n - 1)) if n > 1 else sigma_gen

    # Within-subgroup standard deviation via Moving Range (sigma_within)
    # d2 = 1.128 for n=2
    d2 = 1.128
    mr_mean = sum(moving_ranges) / len(moving_ranges) if moving_ranges else 0.0
    sigma_within = (mr_mean / d2) if d2 > 0 else s_overall

    # Control limits for Individuals (X)
    ucl = mean_val + (3.0 * sigma_within)
    cl = mean_val
    lcl = mean_val - (3.0 * sigma_within)

    # Control limits for Moving Range (MR)
    # D4 = 3.267 for n=2
    ucl_mr = 3.267 * mr_mean
    cl_mr = mr_mean

    # Capability Indices
    cp = (usl - lsl) / (6.0 * sigma_within) if sigma_within > 0 else 0.0
    cpu = (usl - mean_val) / (3.0 * sigma_within) if sigma_within > 0 else 0.0
    cpl = (mean_val - lsl) / (3.0 * sigma_within) if sigma_within > 0 else 0.0
    cpk = max(0.0, min(cpu, cpl))

    pp = (usl - lsl) / (6.0 * s_overall) if s_overall > 0 else 0.0
    ppu = (usl - mean_val) / (3.0 * s_overall) if s_overall > 0 else 0.0
    ppl = (mean_val - lsl) / (3.0 * s_overall) if s_overall > 0 else 0.0
    ppk = max(0.0, min(ppu, ppl))

    # Cpm (Taguchi capability index)
    cpm_denom = 6.0 * math.sqrt((s_overall ** 2) + (mean_offset ** 2))
    cpm = (usl - lsl) / cpm_denom if cpm_denom > 0 else 0.0

    # PPM Defect calculation
    if s_overall > 0:
        z_usl = (usl - mean_val) / s_overall
        z_lsl = (mean_val - lsl) / s_overall
        p_upper = 1.0 - _norm_cdf(z_usl)
        p_lower = 1.0 - _norm_cdf(z_lsl)
        ppm_total = round((p_upper + p_lower) * 1_000_000, 1)
    else:
        ppm_total = 0.0

    # Determine Capability Status
    if cpk >= 1.67:
        cap_status = "WORLD_CLASS"
        status_desc = "Six Sigma World-Class Capability (Cpk ≥ 1.67) - Zero containment required."
    elif cpk >= 1.33:
        cap_status = "CAPABLE"
        status_desc = "Process is Capable (1.33 ≤ Cpk < 1.67) - Meets high-precision automotive/SMT standard."
    elif cpk >= 1.00:
        cap_status = "MARGINAL"
        status_desc = "Marginal Process (1.00 ≤ Cpk < 1.33) - Monitor closely for nozzle or pressure drift."
    else:
        cap_status = "INCAPABLE"
        status_desc = "Incapable Process (Cpk < 1.00) - Immediate CAPA / engineering intervention required."

    # Nelson / Western Electric Rules Out-of-Control Detection
    rules_violated: dict[str, int] = {
        "RULE_1_BEYOND_3_SIGMA": 0,
        "RULE_2_NINE_SAME_SIDE": 0,
        "RULE_3_SIX_TREND": 0,
        "RULE_4_FOURTEEN_ALTERNATING": 0,
    }

    for i in range(n):
        point_violations: list[str] = []
        v = values[i]

        # Rule 1: Point falls outside 3 sigma (UCL or LCL)
        if v > ucl or v < lcl:
            point_violations.append("RULE_1_BEYOND_3_SIGMA")
            rules_violated["RULE_1_BEYOND_3_SIGMA"] += 1

        # Rule 2: 9 points in a row on the same side of center line
        if i >= 8:
            window = values[i - 8 : i + 1]
            if all(w > cl for w in window) or all(w < cl for w in window):
                point_violations.append("RULE_2_NINE_SAME_SIDE")
                rules_violated["RULE_2_NINE_SAME_SIDE"] += 1

        # Rule 3: 6 points in a row steadily increasing or decreasing
        if i >= 5:
            window = values[i - 5 : i + 1]
            increasing = all(window[j] < window[j + 1] for j in range(5))
            decreasing = all(window[j] > window[j + 1] for j in range(5))
            if increasing or decreasing:
                point_violations.append("RULE_3_SIX_TREND")
                rules_violated["RULE_3_SIX_TREND"] += 1

        # Rule 4: 14 points alternating up and down
        if i >= 13:
            window = values[i - 13 : i + 1]
            alternating = True
            for j in range(12):
                diff1 = window[j + 1] - window[j]
                diff2 = window[j + 2] - window[j + 1]
                if (diff1 > 0 and diff2 > 0) or (diff1 < 0 and diff2 < 0):
                    alternating = False
                    break
            if alternating:
                point_violations.append("RULE_4_FOURTEEN_ALTERNATING")
                rules_violated["RULE_4_FOURTEEN_ALTERNATING"] += 1

        if point_violations:
            data_points[i].is_out_of_control = True
            data_points[i].violations = point_violations

    metrics = SpcCapabilityMetrics(
        parameter=param_key,
        parameter_label=spec["label"],
        unit=spec["unit"],
        sample_count=n,
        target=target,
        usl=usl,
        lsl=lsl,
        mean=round(mean_val, 2),
        mean_offset=round(mean_offset, 2),
        std_dev_overall=round(s_overall, 2),
        std_dev_within=round(sigma_within, 2),
        ucl=round(ucl, 2),
        cl=round(cl, 2),
        lcl=round(lcl, 2),
        ucl_mr=round(ucl_mr, 2),
        cl_mr=round(cl_mr, 2),
        cp=round(cp, 2),
        cpk=round(cpk, 2),
        pp=round(pp, 2),
        ppk=round(ppk, 2),
        cpm=round(cpm, 2),
        ppm_total=ppm_total,
        capability_status=cap_status,
        status_description=status_desc,
    )

    # -------------------------------------------------------------
    # Frequency Histogram & Normal PDF Curve
    # -------------------------------------------------------------
    min_val = min(values)
    max_val = max(values)
    span_min = min(lsl - (0.1 * (usl - lsl)), min_val - 2)
    span_max = max(usl + (0.1 * (usl - lsl)), max_val + 2)

    num_bins = 12
    bin_width = (span_max - span_min) / num_bins
    histogram_bins: list[SpcHistogramBin] = []

    for b in range(num_bins):
        b_start = span_min + (b * bin_width)
        b_end = b_start + bin_width
        b_center = (b_start + b_end) / 2.0
        
        # Count elements in bin
        if b == num_bins - 1:
            count = sum(1 for v in values if b_start <= v <= b_end)
        else:
            count = sum(1 for v in values if b_start <= v < b_end)
            
        freq = count / n
        pdf_val = _norm_pdf(b_center, mean_val, s_overall)

        histogram_bins.append(
            SpcHistogramBin(
                bin_start=round(b_start, 2),
                bin_end=round(b_end, 2),
                bin_center=round(b_center, 2),
                count=count,
                frequency=round(freq, 3),
                normal_pdf=round(pdf_val, 5),
            )
        )

    # Smooth Normal Distribution Bell Curve (60 points)
    normal_curve: list[SpcNormalCurvePoint] = []
    curve_points = 60
    step = (span_max - span_min) / (curve_points - 1)
    for c in range(curve_points):
        x = span_min + (c * step)
        y = _norm_pdf(x, mean_val, s_overall)
        normal_curve.append(SpcNormalCurvePoint(x=round(x, 2), y=round(y, 6)))

    # -------------------------------------------------------------
    # Line Capability Comparisons
    # -------------------------------------------------------------
    line_comparisons: list[SpcLineComparison] = []
    for l_key, l_cfg in LINE_CONFIGS.items():
        l_sigma = base_sigma * l_cfg["sigma_mult"]
        l_mean = base_mean + (l_cfg["mean_shift"] * base_sigma * 0.1)
        l_cp = (usl - lsl) / (6.0 * l_sigma)
        l_cpu = (usl - l_mean) / (3.0 * l_sigma)
        l_cpl = (l_mean - lsl) / (3.0 * l_sigma)
        l_cpk = max(0.0, min(l_cpu, l_cpl))
        
        l_status = "World-Class" if l_cpk >= 1.67 else "Capable" if l_cpk >= 1.33 else "Marginal" if l_cpk >= 1.0 else "Action Req"

        line_comparisons.append(
            SpcLineComparison(
                line_id=l_key,
                line_name=l_cfg["name"],
                technology=l_cfg["tech"],
                sample_count=sample_size,
                mean=round(l_mean, 2),
                std_dev=round(l_sigma, 2),
                cp=round(l_cp, 2),
                cpk=round(l_cpk, 2),
                violations_count=0 if l_cpk >= 1.33 else 2,
                status=l_status,
            )
        )

    return SpcAnalysisResponse(
        parameter=param_key,
        line_id=line_id,
        sample_size=sample_size,
        metrics=metrics,
        data_points=data_points,
        histogram=histogram_bins,
        normal_curve=normal_curve,
        line_comparisons=line_comparisons,
        rules_violated_summary=rules_violated,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
