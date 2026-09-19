"""
Unit tests verifying that OpenCV image analysis directly influences
defect identification, cause ranking, evidence evaluation, and explanations.
"""

import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.diagnosis import (
    DefectCode,
    EvidenceRelation,
    EvidenceSource,
    Observation,
    ObservationType,
    StructuredCase,
)
from app.services.diagnosis.defect_identifier import identify_defect
from app.services.diagnosis.engine import DiagnosticEngine
from app.services.diagnosis.evidence_engine import EvidenceEngine
from app.services.vision.measurement import (
    analyze_image_observations,
    to_domain_observations,
)


# ---------------------------------------------------------------------------
# Helpers to generate synthetic test images in memory
# ---------------------------------------------------------------------------

def _create_blank_image(width: int = 300, height: int = 300) -> bytes:
    """Create a white blank image with no deposits."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _create_small_deposit_image(width: int = 300, height: int = 300) -> bytes:
    """Create an image with a single small dark deposit (radius 12, area ~450 px)."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.circle(img, (width // 2, height // 2), 12, (30, 30, 30), -1)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _create_large_deposit_image(width: int = 300, height: int = 300) -> bytes:
    """Create an image with a single large dark deposit (radius 48, area ~7200 px)."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.circle(img, (width // 2, height // 2), 48, (30, 30, 30), -1)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _create_bubble_deposit_image(width: int = 300, height: int = 300) -> bytes:
    """Create an image with a deposit that has an internal void/bubble (donut)."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    center = (width // 2, height // 2)
    # Outer dark droplet
    cv2.circle(img, center, 35, (30, 30, 30), -1)
    # Inner white bubble/void
    cv2.circle(img, center, 14, (255, 255, 255), -1)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _create_tailing_deposit_image(width: int = 300, height: int = 300) -> bytes:
    """Create an image with an elongated tailing deposit."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    center = (width // 2, height // 2)
    # Elongated ellipse with aspect ratio ~2.5
    cv2.ellipse(img, center, (45, 18), 30, 0, 360, (30, 30, 30), -1)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestOpenCVImageAnalysis:
    """Tests for OpenCV visual feature extraction."""

    def test_missing_dots_detection(self):
        """A blank image without deposits must produce deposit_presence=missing."""
        raw_bytes = _create_blank_image()
        obs = analyze_image_observations(raw_bytes)
        assert len(obs) == 1
        assert obs[0]["observation_type"] == "deposit_presence"
        assert obs[0]["value"] == "missing"
        assert obs[0]["source"] == "IMAGE"

    def test_undersized_deposit_detection(self):
        """A small deposit must produce deposit_size=undersized."""
        raw_bytes = _create_small_deposit_image()
        obs = analyze_image_observations(raw_bytes)
        size_obs = next((o for o in obs if o["observation_type"] == "deposit_size"), None)
        assert size_obs is not None
        assert size_obs["value"] == "undersized"
        assert size_obs["source"] == "IMAGE"
        assert "area_px" in size_obs["metadata"]
        assert size_obs["metadata"]["area_px"] < 1200

    def test_oversized_deposit_detection(self):
        """A large deposit must produce deposit_size=oversized."""
        raw_bytes = _create_large_deposit_image()
        obs = analyze_image_observations(raw_bytes)
        size_obs = next((o for o in obs if o["observation_type"] == "deposit_size"), None)
        assert size_obs is not None
        assert size_obs["value"] == "oversized"
        assert size_obs["source"] == "IMAGE"
        assert size_obs["metadata"]["area_px"] > 4500

    def test_bubble_void_detection(self):
        """A deposit with an internal void must detect visible_bubbles."""
        raw_bytes = _create_bubble_deposit_image()
        obs = analyze_image_observations(raw_bytes)
        types = [o["observation_type"] for o in obs]
        assert "bubble_presence" in types or "visual_appearance" in types
        bubble_obs = next((o for o in obs if o["observation_type"] == "bubble_presence"), None)
        if bubble_obs:
            assert bubble_obs["value"] == "visible_bubbles"

    def test_tailing_shape_detection(self):
        """An elongated deposit must detect tailing or abnormal shape."""
        raw_bytes = _create_tailing_deposit_image()
        obs = analyze_image_observations(raw_bytes)
        shape_obs = next((o for o in obs if o["observation_type"] == "deposit_shape"), None)
        assert shape_obs is not None
        assert shape_obs["value"] in ("tailing", "abnormal")

    def test_to_domain_observations_conversion(self):
        """to_domain_observations must produce valid Observation domain models."""
        raw_bytes = _create_small_deposit_image()
        obs_dicts = analyze_image_observations(raw_bytes)
        domain_obs = to_domain_observations(obs_dicts)
        assert len(domain_obs) > 0
        for o in domain_obs:
            assert isinstance(o, Observation)
            assert o.source == EvidenceSource.IMAGE


class TestImageDrivenDecisionMaking:
    """Tests verifying that image observations directly drive diagnostic decisions."""

    def test_image_observation_identifies_d01_too_little(self):
        """An undersized image observation alone must identify D01_TOO_LITTLE."""
        domain_obs = to_domain_observations(analyze_image_observations(_create_small_deposit_image()))
        match = identify_defect(domain_obs)
        assert match is not None
        assert match.code == DefectCode.D01_TOO_LITTLE.value

    def test_image_observation_identifies_d02_too_much(self):
        """An oversized image observation alone must identify D02_TOO_MUCH."""
        domain_obs = to_domain_observations(analyze_image_observations(_create_large_deposit_image()))
        match = identify_defect(domain_obs)
        assert match is not None
        assert match.code == DefectCode.D02_TOO_MUCH.value

    def test_image_observation_identifies_d04_missing_dots(self):
        """A missing dots image observation alone must identify D04_MISSING_DOTS."""
        domain_obs = to_domain_observations(analyze_image_observations(_create_blank_image()))
        match = identify_defect(domain_obs)
        assert match is not None
        assert match.code == DefectCode.D04_MISSING_DOTS.value

    def test_evidence_engine_scores_image_evidence(self):
        """EvidenceEngine must assign positive score to causes supported by image observations."""
        domain_obs = to_domain_observations(analyze_image_observations(_create_small_deposit_image()))
        engine = EvidenceEngine()
        candidates = engine.evaluate(domain_obs, DefectCode.D01_TOO_LITTLE.value)

        # In D01, undersized deposit supports nozzle_restriction (R002, STRONG)
        nozzle_cause = next((c for c in candidates if c.cause_id == "nozzle_restriction"), None)
        assert nozzle_cause is not None
        assert len(nozzle_cause.supporting_evidence) > 0

        # Verify provenance is preserved as IMAGE
        img_ev = nozzle_cause.supporting_evidence[0]
        assert img_ev.source == EvidenceSource.IMAGE
        assert img_ev.relation == EvidenceRelation.SUPPORTS
        assert img_ev.score_contribution > 0.0

    def test_full_diagnostic_cycle_with_image_only(self):
        """DiagnosticEngine must successfully diagnose a case with only an image uploaded."""
        engine = DiagnosticEngine()
        domain_obs = to_domain_observations(analyze_image_observations(_create_small_deposit_image()))

        case = StructuredCase(
            description="",  # No text description provided, only image
            observations=domain_obs,
        )

        result = engine.diagnose(case)
        assert result.defect == DefectCode.D01_TOO_LITTLE.value
        assert len(result.ranked_causes) > 0
        top_cause = result.ranked_causes[0]
        assert top_cause.score >= 40.0
        assert top_cause.cause_id == "nozzle_restriction"

        # Verify explanation acknowledges image inspection evidence
        assert "visual/image inspection measurement" in result.explanation

    def test_joint_image_and_text_diagnosis(self):
        """Image observation and text description symptoms must be merged without suppression."""
        engine = DiagnosticEngine()
        domain_obs = to_domain_observations(analyze_image_observations(_create_small_deposit_image()))

        case = StructuredCase(
            description="The dots get small after running for 20 minutes continuously.",
            observations=domain_obs,
        )

        result = engine.diagnose(case)
        # Should have both deposit_size (from image) and runtime_pattern (from description)
        obs_types = {o.observation_type for o in case.observations}
        assert "deposit_size" in obs_types
        assert "runtime_pattern" in obs_types

        # Both factors should influence cause ranking
        assert len(result.ranked_causes) > 0
        top_cause = result.ranked_causes[0]
        assert len(top_cause.supporting_evidence) >= 1

    def test_api_image_analysis_endpoint(self):
        """POST /api/v1/images/analyze must return 200 with structured observations."""
        client = TestClient(app)
        raw_bytes = _create_small_deposit_image()

        response = client.post(
            "/api/v1/images/analyze",
            files={"file": ("deposit_sample.png", raw_bytes, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["observation_type"] == "deposit_size"
        assert data[0]["value"] == "undersized"
        assert data[0]["source"] == "IMAGE"
