"""
Unit tests for Statistical Process Control (SPC) Service and Capability Calculations.
"""

from __future__ import annotations

import pytest

from app.schemas.spc import SpcAnalysisResponse
from app.services.spc.spc_service import generate_spc_analysis, PARAM_SPECS


def test_generate_spc_analysis_dot_diameter():
    resp = generate_spc_analysis(parameter="dot_diameter", line_id="line-a", sample_size=50)

    assert isinstance(resp, SpcAnalysisResponse)
    assert resp.parameter == "dot_diameter"
    assert resp.sample_size == 50
    assert len(resp.data_points) == 50

    m = resp.metrics
    assert m.unit == "µm"
    assert m.target == 850.0
    assert m.usl == 950.0
    assert m.lsl == 750.0

    # Sanity checks on statistical capability formulas
    assert m.ucl > m.cl > m.lcl
    assert m.std_dev_within > 0
    assert m.std_dev_overall > 0
    assert m.cp > 0
    assert m.cpk > 0
    assert m.pp > 0
    assert m.ppk > 0

    # Verify I-MR Moving Ranges calculated
    assert resp.data_points[0].moving_range is None  # first point has no MR
    assert resp.data_points[1].moving_range is not None
    assert resp.data_points[1].moving_range >= 0

    # Verify Histogram
    assert len(resp.histogram) == 12
    total_histogram_count = sum(b.count for b in resp.histogram)
    assert total_histogram_count == 50

    # Verify Normal Distribution Curve points
    assert len(resp.normal_curve) == 60
    assert all(pt.y >= 0 for pt in resp.normal_curve)

    # Verify Line Comparisons
    assert len(resp.line_comparisons) == 4
    line_names = [lc.line_name for lc in resp.line_comparisons]
    assert "Line A" in line_names
    assert "Line B" in line_names


def test_generate_spc_analysis_all_parameters():
    for param_key in PARAM_SPECS.keys():
        resp = generate_spc_analysis(parameter=param_key, line_id="all", sample_size=30)
        assert resp.parameter == param_key
        assert resp.sample_size == 30
        assert resp.metrics.sample_count == 30
        assert resp.metrics.unit == PARAM_SPECS[param_key]["unit"]
        assert resp.metrics.target == PARAM_SPECS[param_key]["target"]
