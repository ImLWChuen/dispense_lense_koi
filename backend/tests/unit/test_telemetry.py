"""Unit tests for cleanroom telemetry and syringe pot life tracking."""

import pytest
from datetime import datetime, timedelta, timezone

from app.schemas.telemetry import (
    ConsumableState,
    MountRequest,
    PotLifeStatus,
    PurgeRequest,
    ScrapRequest,
    SensorStatus,
    ThawRequest,
)
from app.services.telemetry.telemetry_service import TelemetryService


def test_cleanroom_environment_and_overview():
    service = TelemetryService()
    overview = service.get_telemetry_overview()

    assert overview.environment.iso_class == "ISO Class 5"
    assert overview.environment.iso_certified is True
    assert 20.0 <= overview.environment.ambient_temp_c <= 25.0
    assert 40.0 <= overview.environment.relative_humidity_pct <= 50.0
    assert overview.environment.particle_count_per_m3 < 3520  # ISO 5 limit

    # 4 lines should be returned
    assert len(overview.lines) == 4
    line_ids = [l.line_id for l in overview.lines]
    assert "line-a" in line_ids
    assert "line-b" in line_ids
    assert "line-c" in line_ids
    assert "line-d" in line_ids

    # Sparklines should exist for each sensor
    for line in overview.lines:
        assert len(line.fluid_pressure.sparkline) >= 20
        assert line.fluid_pressure.unit == "kPa"
        assert line.nozzle_temp.unit == "°C"


def test_line_telemetry_snapshot():
    service = TelemetryService()
    line_a = service.get_line_snapshot("line-a")

    assert line_a.line_name == "Line A"
    assert line_a.technology == "Piezoelectric Jetting"
    assert line_a.fluid_pressure.target == 240.0
    assert line_a.vacuum_pressure.target == -14.0
    assert line_a.nozzle_temp.target == 35.0
    assert line_a.syringe_temp.target == 23.5
    assert line_a.valve_cycle_freq_hz > 0


def test_consumable_thaw_lifecycle():
    service = TelemetryService()
    req = ThawRequest(
        lot_number="LOT-TEST-THAW-01",
        material_code="NOA-68",
        thaw_duration_minutes=45,
        barrel_size_cc=30.0,
        cleanroom_rack="RACK-CR1-09",
    )
    thawed_item = service.thaw_consumable(req)

    assert thawed_item.lot_number == "LOT-TEST-THAW-01"
    assert thawed_item.material_name == "Norland NOA 68 Optical Adhesive"
    assert thawed_item.state == ConsumableState.THAWING
    assert thawed_item.thaw_duration_minutes == 45
    assert thawed_item.cleanroom_rack == "RACK-CR1-09"
    assert thawed_item.barrel_size_cc == 30.0
    assert thawed_item.current_volume_cc == 30.0


def test_consumable_mount_purge_and_scrap():
    service = TelemetryService()

    # Thaw new syringe
    req = ThawRequest(
        lot_number="LOT-TEST-MOUNT-01",
        material_code="EPO-TEK-353ND",
        thaw_duration_minutes=15,
        barrel_size_cc=10.0,
        cleanroom_rack="RACK-CR1-02",
    )
    item = service.thaw_consumable(req)
    item_id = item.id

    # Mount to Line C
    mount_req = MountRequest(line_id="line-c")
    mounted = service.mount_consumable(item_id, mount_req)
    assert mounted.state == ConsumableState.MOUNTED
    assert mounted.line_id == "line-c"
    assert mounted.pot_life_expiry_time is not None
    assert mounted.remaining_pot_life_seconds > 0

    # Purge nozzle tip
    purge_req = PurgeRequest(purge_duration_ms=500, test_shot_count=5)
    purged = service.purge_consumable(item_id, purge_req)
    assert purged.nozzle_tip.cycle_count == 5
    assert purged.nozzle_tip.last_purge_time is not None
    assert purged.nozzle_tip.purge_required is False

    # Scrap syringe
    scrap_req = ScrapRequest(reason="VISCOSITY_DRIFT", notes="Exceeded allowable cleanroom work time")
    scrapped = service.scrap_consumable(item_id, scrap_req)
    assert scrapped.state == ConsumableState.SCRAPPED
    assert scrapped.line_id is None
    assert scrapped.scrap_reason == "VISCOSITY_DRIFT"


def test_pot_life_status_degradation():
    service = TelemetryService()
    now = datetime.now(timezone.utc)

    # Optimal (> 2h)
    optimal_dict = {
        "id": "syr-opt",
        "lot_number": "LOT-OPT",
        "material_name": "Test Material",
        "material_type": "uv_acrylic",
        "state": ConsumableState.MOUNTED,
        "pot_life_hours": 8.0,
        "pot_life_start_time": (now - timedelta(hours=1)).isoformat(),
        "pot_life_expiry_time": (now + timedelta(hours=7)).isoformat(),
        "barrel_size_cc": 30.0,
        "current_volume_cc": 28.0,
    }
    evaluated_opt = service._evaluate_consumable(optimal_dict)
    assert evaluated_opt.pot_life_status == PotLifeStatus.OPTIMAL

    # Warning (30m - 2h)
    warn_dict = {
        "id": "syr-warn",
        "lot_number": "LOT-WARN",
        "material_name": "Test Material",
        "material_type": "uv_acrylic",
        "state": ConsumableState.MOUNTED,
        "pot_life_hours": 8.0,
        "pot_life_start_time": (now - timedelta(hours=7)).isoformat(),
        "pot_life_expiry_time": (now + timedelta(minutes=45)).isoformat(),
        "barrel_size_cc": 30.0,
        "current_volume_cc": 10.0,
    }
    evaluated_warn = service._evaluate_consumable(warn_dict)
    assert evaluated_warn.pot_life_status == PotLifeStatus.WARNING

    # Critical (< 30m)
    crit_dict = {
        "id": "syr-crit",
        "lot_number": "LOT-CRIT",
        "material_name": "Test Material",
        "material_type": "uv_acrylic",
        "state": ConsumableState.MOUNTED,
        "pot_life_hours": 8.0,
        "pot_life_start_time": (now - timedelta(hours=7, minutes=45)).isoformat(),
        "pot_life_expiry_time": (now + timedelta(minutes=15)).isoformat(),
        "barrel_size_cc": 30.0,
        "current_volume_cc": 4.0,
    }
    evaluated_crit = service._evaluate_consumable(crit_dict)
    assert evaluated_crit.pot_life_status == PotLifeStatus.CRITICAL

    # Expired (<= 0)
    exp_dict = {
        "id": "syr-exp",
        "lot_number": "LOT-EXP",
        "material_name": "Test Material",
        "material_type": "uv_acrylic",
        "state": ConsumableState.MOUNTED,
        "pot_life_hours": 8.0,
        "pot_life_start_time": (now - timedelta(hours=9)).isoformat(),
        "pot_life_expiry_time": (now - timedelta(minutes=10)).isoformat(),
        "barrel_size_cc": 30.0,
        "current_volume_cc": 2.0,
    }
    evaluated_exp = service._evaluate_consumable(exp_dict)
    assert evaluated_exp.pot_life_status == PotLifeStatus.EXPIRED
    assert evaluated_exp.state == ConsumableState.EXPIRED
    assert evaluated_exp.remaining_pot_life_seconds == 0
