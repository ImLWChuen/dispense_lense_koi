"""Telemetry and Syringe Pot Life Tracking Service.

Simulates and evaluates cleanroom physical sensors (temperature, humidity,
pressures, particle counts) and manages syringe adhesive defrosting,
pot life countdown, volume depletion, and tip maintenance state.
"""

from datetime import datetime, timedelta, timezone
import math
import random
import uuid
from typing import Any, Optional

from app.schemas.telemetry import (
    CleanroomEnvironment,
    ConsumableItem,
    ConsumableState,
    LineTelemetrySnapshot,
    MountRequest,
    NozzleTipInfo,
    PotLifeStatus,
    PurgeRequest,
    ScrapRequest,
    SensorReading,
    SensorStatus,
    TelemetryOverviewResponse,
    ThawRequest,
)

# Supported adhesive catalog
MATERIAL_CATALOG = {
    "NOA-68": {
        "name": "Norland NOA 68 Optical Adhesive",
        "type": "uv_acrylic",
        "pot_life_hours": 8.0,
        "default_thaw_minutes": 45,
        "default_cc": 30.0,
        "shots_per_cc": 220,
    },
    "LOCTITE-382": {
        "name": "Loctite 382 TakPak Prism",
        "type": "cyanoacrylate",
        "pot_life_hours": 12.0,
        "default_thaw_minutes": 30,
        "default_cc": 20.0,
        "shots_per_cc": 180,
    },
    "EPO-TEK-353ND": {
        "name": "EPO-TEK 353ND Optical Epoxy",
        "type": "thermal_epoxy",
        "pot_life_hours": 4.0,
        "default_thaw_minutes": 60,
        "default_cc": 10.0,
        "shots_per_cc": 350,
    },
    "DOW-OE6630": {
        "name": "Dow Corning OE-6630 LED Gel",
        "type": "dual_part_silicone",
        "pot_life_hours": 6.0,
        "default_thaw_minutes": 40,
        "default_cc": 55.0,
        "shots_per_cc": 120,
    },
}

# Production line configurations
LINE_CONFIGS = {
    "line-a": {
        "name": "Line A",
        "tech": "Piezoelectric Jetting",
        "fluid_pressure": {"target": 240.0, "usl": 255.0, "lsl": 225.0, "unit": "kPa", "name": "Fluid Feed Pressure"},
        "vacuum_pressure": {"target": -14.0, "usl": -8.0, "lsl": -20.0, "unit": "kPa", "name": "Vacuum Backpressure"},
        "nozzle_temp": {"target": 35.0, "usl": 37.0, "lsl": 33.0, "unit": "°C", "name": "Nozzle Heater"},
        "syringe_temp": {"target": 23.5, "usl": 25.5, "lsl": 21.5, "unit": "°C", "name": "Syringe Barrel Temp"},
        "base_freq_hz": 180.0,
    },
    "line-b": {
        "name": "Line B",
        "tech": "Auger Micro-Screw",
        "fluid_pressure": {"target": 210.0, "usl": 225.0, "lsl": 195.0, "unit": "kPa", "name": "Fluid Feed Pressure"},
        "vacuum_pressure": {"target": -10.0, "usl": -5.0, "lsl": -16.0, "unit": "kPa", "name": "Vacuum Backpressure"},
        "nozzle_temp": {"target": 32.0, "usl": 34.0, "lsl": 30.0, "unit": "°C", "name": "Nozzle Heater"},
        "syringe_temp": {"target": 22.8, "usl": 25.0, "lsl": 21.0, "unit": "°C", "name": "Syringe Barrel Temp"},
        "base_freq_hz": 95.0,
    },
    "line-c": {
        "name": "Line C",
        "tech": "Time-Pressure Pneumatic",
        "fluid_pressure": {"target": 250.0, "usl": 268.0, "lsl": 232.0, "unit": "kPa", "name": "Fluid Feed Pressure"},
        "vacuum_pressure": {"target": -18.0, "usl": -12.0, "lsl": -24.0, "unit": "kPa", "name": "Vacuum Backpressure"},
        "nozzle_temp": {"target": 36.5, "usl": 38.5, "lsl": 34.5, "unit": "°C", "name": "Nozzle Heater"},
        "syringe_temp": {"target": 24.0, "usl": 26.0, "lsl": 22.0, "unit": "°C", "name": "Syringe Barrel Temp"},
        "base_freq_hz": 60.0,
    },
    "line-d": {
        "name": "Line D",
        "tech": "Piston Positive Displacement",
        "fluid_pressure": {"target": 235.0, "usl": 250.0, "lsl": 220.0, "unit": "kPa", "name": "Fluid Feed Pressure"},
        "vacuum_pressure": {"target": -12.0, "usl": -6.0, "lsl": -18.0, "unit": "kPa", "name": "Vacuum Backpressure"},
        "nozzle_temp": {"target": 34.5, "usl": 36.5, "lsl": 32.5, "unit": "°C", "name": "Nozzle Heater"},
        "syringe_temp": {"target": 23.2, "usl": 25.2, "lsl": 21.2, "unit": "°C", "name": "Syringe Barrel Temp"},
        "base_freq_hz": 140.0,
    },
}


class TelemetryService:
    """Service to track live cleanroom telemetry and consumable pot life."""

    def __init__(self) -> None:
        self._consumables: dict[str, dict[str, Any]] = {}
        self._seed_initial_consumables()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _seed_initial_consumables(self) -> None:
        """Seed realistic active cleanroom syringes."""
        now = self._now()

        # Line A: NOA-68, mounted 3.2 hours ago, ~4.8h pot life remaining (Optimal)
        s1_id = "syr-noa68-line-a"
        s1_mounted = now - timedelta(hours=3, minutes=12)
        s1_expiry = s1_mounted + timedelta(hours=8)
        self._consumables[s1_id] = {
            "id": s1_id,
            "lot_number": "LOT-NOA68-2609A",
            "material_name": "Norland NOA 68 Optical Adhesive",
            "material_type": "uv_acrylic",
            "line_id": "line-a",
            "barrel_size_cc": 30.0,
            "current_volume_cc": 18.2,
            "volume_percent": 60.7,
            "state": ConsumableState.MOUNTED,
            "thaw_start_time": (s1_mounted - timedelta(minutes=45)).isoformat(),
            "thaw_duration_minutes": 45,
            "thaw_end_time": s1_mounted.isoformat(),
            "thaw_progress_pct": 100.0,
            "pot_life_hours": 8.0,
            "pot_life_start_time": s1_mounted.isoformat(),
            "pot_life_expiry_time": s1_expiry.isoformat(),
            "estimated_shots_remaining": 4004,
            "nozzle_tip": {
                "gauge": "32G",
                "tip_type": "Chamfered Ceramic",
                "cycle_count": 14250,
                "max_rated_cycles": 20000,
                "wear_percentage": 71.3,
                "last_purge_time": (now - timedelta(minutes=24)).isoformat(),
                "purge_required": False,
            },
            "cleanroom_rack": "LINE-A-HEAD",
            "notes": "Primary UV lens tacking dispenser",
        }

        # Line B: EPO-TEK-353ND, mounted 3.4 hours ago out of 4h max (Critical/Warning: ~36 mins left!)
        s2_id = "syr-epotek-line-b"
        s2_mounted = now - timedelta(hours=3, minutes=24)
        s2_expiry = s2_mounted + timedelta(hours=4)
        self._consumables[s2_id] = {
            "id": s2_id,
            "lot_number": "LOT-EPO353-2609B",
            "material_name": "EPO-TEK 353ND Optical Epoxy",
            "material_type": "thermal_epoxy",
            "line_id": "line-b",
            "barrel_size_cc": 10.0,
            "current_volume_cc": 2.1,
            "volume_percent": 21.0,
            "state": ConsumableState.MOUNTED,
            "thaw_start_time": (s2_mounted - timedelta(minutes=60)).isoformat(),
            "thaw_duration_minutes": 60,
            "thaw_end_time": s2_mounted.isoformat(),
            "thaw_progress_pct": 100.0,
            "pot_life_hours": 4.0,
            "pot_life_start_time": s2_mounted.isoformat(),
            "pot_life_expiry_time": s2_expiry.isoformat(),
            "estimated_shots_remaining": 735,
            "nozzle_tip": {
                "gauge": "30G",
                "tip_type": "Stainless Steel Luer",
                "cycle_count": 18450,
                "max_rated_cycles": 20000,
                "wear_percentage": 92.3,
                "last_purge_time": (now - timedelta(minutes=85)).isoformat(),
                "purge_required": True,
            },
            "cleanroom_rack": "LINE-B-HEAD",
            "notes": "Pre-mixed thermal cure barrel, rapid gelation window",
        }

        # Line C: DOW-OE6630, mounted 1.5 hours ago out of 6h pot life (Optimal: ~4.5h left)
        s3_id = "syr-dow6630-line-c"
        s3_mounted = now - timedelta(hours=1, minutes=30)
        s3_expiry = s3_mounted + timedelta(hours=6)
        self._consumables[s3_id] = {
            "id": s3_id,
            "lot_number": "LOT-DOW6630-2609C",
            "material_name": "Dow Corning OE-6630 LED Gel",
            "material_type": "dual_part_silicone",
            "line_id": "line-c",
            "barrel_size_cc": 55.0,
            "current_volume_cc": 42.5,
            "volume_percent": 77.3,
            "state": ConsumableState.MOUNTED,
            "thaw_start_time": (s3_mounted - timedelta(minutes=40)).isoformat(),
            "thaw_duration_minutes": 40,
            "thaw_end_time": s3_mounted.isoformat(),
            "thaw_progress_pct": 100.0,
            "pot_life_hours": 6.0,
            "pot_life_start_time": s3_mounted.isoformat(),
            "pot_life_expiry_time": s3_expiry.isoformat(),
            "estimated_shots_remaining": 5100,
            "nozzle_tip": {
                "gauge": "27G",
                "tip_type": "Tapered Polyethylene",
                "cycle_count": 6800,
                "max_rated_cycles": 25000,
                "wear_percentage": 27.2,
                "last_purge_time": (now - timedelta(minutes=38)).isoformat(),
                "purge_required": False,
            },
            "cleanroom_rack": "LINE-C-HEAD",
            "notes": "Silicone dome encapsulation",
        }

        # Line D: LOCTITE-382, mounted 4 hours ago out of 12h pot life (Optimal: ~8h left)
        s4_id = "syr-loc382-line-d"
        s4_mounted = now - timedelta(hours=4)
        s4_expiry = s4_mounted + timedelta(hours=12)
        self._consumables[s4_id] = {
            "id": s4_id,
            "lot_number": "LOT-LOC382-2609D",
            "material_name": "Loctite 382 TakPak Prism",
            "material_type": "cyanoacrylate",
            "line_id": "line-d",
            "barrel_size_cc": 20.0,
            "current_volume_cc": 14.8,
            "volume_percent": 74.0,
            "state": ConsumableState.MOUNTED,
            "thaw_start_time": (s4_mounted - timedelta(minutes=30)).isoformat(),
            "thaw_duration_minutes": 30,
            "thaw_end_time": s4_mounted.isoformat(),
            "thaw_progress_pct": 100.0,
            "pot_life_hours": 12.0,
            "pot_life_start_time": s4_mounted.isoformat(),
            "pot_life_expiry_time": s4_expiry.isoformat(),
            "estimated_shots_remaining": 2664,
            "nozzle_tip": {
                "gauge": "30G",
                "tip_type": "Teflon-Lined Stainless",
                "cycle_count": 9400,
                "max_rated_cycles": 18000,
                "wear_percentage": 52.2,
                "last_purge_time": (now - timedelta(minutes=15)).isoformat(),
                "purge_required": False,
            },
            "cleanroom_rack": "LINE-D-HEAD",
            "notes": "Lens frame tacking dispenser",
        }

        # Staged Syringe 1: In Defrosting/Thawing state for Line B replacement
        s5_id = "syr-thaw-epotek-2"
        s5_thaw_start = now - timedelta(minutes=32)
        s5_thaw_end = s5_thaw_start + timedelta(minutes=45)
        self._consumables[s5_id] = {
            "id": s5_id,
            "lot_number": "LOT-EPO353-2609STG",
            "material_name": "EPO-TEK 353ND Optical Epoxy",
            "material_type": "thermal_epoxy",
            "line_id": None,
            "barrel_size_cc": 10.0,
            "current_volume_cc": 10.0,
            "volume_percent": 100.0,
            "state": ConsumableState.THAWING,
            "thaw_start_time": s5_thaw_start.isoformat(),
            "thaw_duration_minutes": 45,
            "thaw_end_time": s5_thaw_end.isoformat(),
            "thaw_progress_pct": round((32 / 45) * 100, 1),
            "pot_life_hours": 4.0,
            "pot_life_start_time": None,
            "pot_life_expiry_time": None,
            "estimated_shots_remaining": 3500,
            "nozzle_tip": {
                "gauge": "30G",
                "tip_type": "Stainless Steel Luer",
                "cycle_count": 0,
                "max_rated_cycles": 20000,
                "wear_percentage": 0.0,
                "last_purge_time": None,
                "purge_required": False,
            },
            "cleanroom_rack": "RACK-CR1-03",
            "notes": "Defrosting upright at ambient 22°C for Line B swap",
        }

        # Staged Syringe 2: READY for use (thawed and stabilized)
        s6_id = "syr-ready-noa68-3"
        s6_thaw_end = now - timedelta(minutes=15)
        self._consumables[s6_id] = {
            "id": s6_id,
            "lot_number": "LOT-NOA68-2609RDY",
            "material_name": "Norland NOA 68 Optical Adhesive",
            "material_type": "uv_acrylic",
            "line_id": None,
            "barrel_size_cc": 30.0,
            "current_volume_cc": 30.0,
            "volume_percent": 100.0,
            "state": ConsumableState.READY,
            "thaw_start_time": (s6_thaw_end - timedelta(minutes=45)).isoformat(),
            "thaw_duration_minutes": 45,
            "thaw_end_time": s6_thaw_end.isoformat(),
            "thaw_progress_pct": 100.0,
            "pot_life_hours": 8.0,
            "pot_life_start_time": None,
            "pot_life_expiry_time": None,
            "estimated_shots_remaining": 6600,
            "nozzle_tip": {
                "gauge": "32G",
                "tip_type": "Chamfered Ceramic",
                "cycle_count": 0,
                "max_rated_cycles": 20000,
                "wear_percentage": 0.0,
                "last_purge_time": None,
                "purge_required": False,
            },
            "cleanroom_rack": "RACK-CR1-04",
            "notes": "Centrifuged and degassed, ready for mounting",
        }

        # Expired Syringe: Audit demonstration
        s7_id = "syr-exp-loc382-old"
        s7_mounted = now - timedelta(hours=14)
        s7_expiry = s7_mounted + timedelta(hours=12)
        self._consumables[s7_id] = {
            "id": s7_id,
            "lot_number": "LOT-LOC382-OLD",
            "material_name": "Loctite 382 TakPak Prism",
            "material_type": "cyanoacrylate",
            "line_id": None,
            "barrel_size_cc": 20.0,
            "current_volume_cc": 3.4,
            "volume_percent": 17.0,
            "state": ConsumableState.EXPIRED,
            "thaw_start_time": (s7_mounted - timedelta(minutes=30)).isoformat(),
            "thaw_duration_minutes": 30,
            "thaw_end_time": s7_mounted.isoformat(),
            "thaw_progress_pct": 100.0,
            "pot_life_hours": 12.0,
            "pot_life_start_time": s7_mounted.isoformat(),
            "pot_life_expiry_time": s7_expiry.isoformat(),
            "estimated_shots_remaining": 0,
            "nozzle_tip": {
                "gauge": "30G",
                "tip_type": "Teflon-Lined Stainless",
                "cycle_count": 18200,
                "max_rated_cycles": 18000,
                "wear_percentage": 100.0,
                "last_purge_time": (now - timedelta(hours=3)).isoformat(),
                "purge_required": True,
            },
            "cleanroom_rack": "QUARANTINE-BIN-01",
            "notes": "Expired pot life, viscosity increased, scheduled for disposal",
        }

    def _evaluate_consumable(self, item_dict: dict[str, Any]) -> ConsumableItem:
        """Dynamically re-evaluate pot life seconds, thaw progress, and state."""
        now = self._now()
        data = dict(item_dict)

        # Handle thaw progress
        if data.get("state") == ConsumableState.THAWING:
            if data.get("thaw_start_time") and data.get("thaw_end_time"):
                start = datetime.fromisoformat(data["thaw_start_time"])
                end = datetime.fromisoformat(data["thaw_end_time"])
                total_sec = max(1.0, (end - start).total_seconds())
                elapsed_sec = (now - start).total_seconds()
                progress = min(100.0, max(0.0, (elapsed_sec / total_sec) * 100.0))
                data["thaw_progress_pct"] = round(progress, 1)

                if now >= end:
                    data["state"] = ConsumableState.READY
                    data["thaw_progress_pct"] = 100.0

        # Handle pot life countdown
        if data.get("state") in (ConsumableState.MOUNTED, ConsumableState.READY, ConsumableState.EXPIRED):
            if data.get("pot_life_expiry_time"):
                expiry = datetime.fromisoformat(data["pot_life_expiry_time"])
                rem_sec = int((expiry - now).total_seconds())

                if rem_sec <= 0:
                    data["remaining_pot_life_seconds"] = 0
                    data["pot_life_status"] = PotLifeStatus.EXPIRED
                    if data.get("state") == ConsumableState.MOUNTED:
                        data["state"] = ConsumableState.EXPIRED
                else:
                    data["remaining_pot_life_seconds"] = rem_sec
                    if rem_sec < 1800:  # < 30 min
                        data["pot_life_status"] = PotLifeStatus.CRITICAL
                    elif rem_sec < 7200:  # < 2 hours
                        data["pot_life_status"] = PotLifeStatus.WARNING
                    else:
                        data["pot_life_status"] = PotLifeStatus.OPTIMAL
            else:
                # Not yet unsealed
                data["remaining_pot_life_seconds"] = int(data.get("pot_life_hours", 8.0) * 3600)
                data["pot_life_status"] = PotLifeStatus.OPTIMAL

        # Calculate volume percentage
        barrel = max(1.0, data.get("barrel_size_cc", 30.0))
        curr = max(0.0, data.get("current_volume_cc", 0.0))
        data["volume_percent"] = round(min(100.0, (curr / barrel) * 100.0), 1)

        # Calculate tip wear percentage
        tip_dict = data.get("nozzle_tip", {})
        cycles = tip_dict.get("cycle_count", 0)
        max_c = max(1, tip_dict.get("max_rated_cycles", 20000))
        tip_dict["wear_percentage"] = round(min(100.0, (cycles / max_c) * 100.0), 1)
        data["nozzle_tip"] = NozzleTipInfo(**tip_dict)

        return ConsumableItem(**data)

    def _generate_sensor_reading(
        self,
        sensor_id: str,
        name: str,
        target: float,
        usl: float,
        lsl: float,
        unit: str,
        noise_std: float = 0.5,
    ) -> SensorReading:
        """Generate a realistic live sensor reading with trend history sparkline."""
        # Simulated live reading with slight jitter
        jitter = random.gauss(0, noise_std)
        value = round(target + jitter, 2)

        # 25-point historical sparkline drifting around target
        sparkline = []
        curr = target + random.gauss(0, noise_std * 0.5)
        for i in range(25):
            curr += random.gauss(0, noise_std * 0.4)
            # Revert to mean
            curr = 0.85 * curr + 0.15 * target
            sparkline.append(round(curr, 2))
        sparkline[-1] = value

        # Status check
        if value > usl or value < lsl:
            status = SensorStatus.CRITICAL
        elif (value > usl - (usl - target) * 0.25) or (value < lsl + (target - lsl) * 0.25):
            status = SensorStatus.WARNING
        else:
            status = SensorStatus.NOMINAL

        return SensorReading(
            sensor_id=sensor_id,
            name=name,
            value=value,
            unit=unit,
            target=target,
            usl=usl,
            lsl=lsl,
            status=status,
            sparkline=sparkline,
        )

    def get_cleanroom_environment(self) -> CleanroomEnvironment:
        """Generate live ambient cleanroom facility readings."""
        now = self._now()
        temp_c = round(21.8 + random.uniform(-0.25, 0.25), 1)
        humidity_pct = round(44.5 + random.uniform(-0.8, 0.8), 1)
        diff_pressure = round(32.4 + random.uniform(-0.5, 0.5), 1)
        particle_count = int(280 + random.randint(-15, 25))

        return CleanroomEnvironment(
            ambient_temp_c=temp_c,
            ambient_temp_status=SensorStatus.NOMINAL,
            relative_humidity_pct=humidity_pct,
            humidity_status=SensorStatus.NOMINAL,
            differential_pressure_pa=diff_pressure,
            particle_count_per_m3=particle_count,
            iso_class="ISO Class 5",
            iso_certified=True,
            last_updated=now.isoformat(),
        )

    def get_line_snapshot(self, line_id: str) -> LineTelemetrySnapshot:
        """Generate live physical telemetry snapshot for a specific line."""
        cfg = LINE_CONFIGS.get(line_id)
        if not cfg:
            line_id = "line-a"
            cfg = LINE_CONFIGS["line-a"]

        # Find mounted consumable
        mounted_item = None
        for c in self._consumables.values():
            if c.get("line_id") == line_id and c.get("state") in (ConsumableState.MOUNTED, ConsumableState.EXPIRED):
                mounted_item = c
                break

        fp_cfg = cfg["fluid_pressure"]
        vp_cfg = cfg["vacuum_pressure"]
        nt_cfg = cfg["nozzle_temp"]
        st_cfg = cfg["syringe_temp"]

        fluid_press = self._generate_sensor_reading(
            f"{line_id}-fp", fp_cfg["name"], fp_cfg["target"], fp_cfg["usl"], fp_cfg["lsl"], fp_cfg["unit"], noise_std=1.2
        )
        vac_press = self._generate_sensor_reading(
            f"{line_id}-vp", vp_cfg["name"], vp_cfg["target"], vp_cfg["usl"], vp_cfg["lsl"], vp_cfg["unit"], noise_std=0.4
        )
        nozzle_tmp = self._generate_sensor_reading(
            f"{line_id}-nt", nt_cfg["name"], nt_cfg["target"], nt_cfg["usl"], nt_cfg["lsl"], nt_cfg["unit"], noise_std=0.25
        )
        syr_tmp = self._generate_sensor_reading(
            f"{line_id}-st", st_cfg["name"], st_cfg["target"], st_cfg["usl"], st_cfg["lsl"], st_cfg["unit"], noise_std=0.2
        )

        # Aggregate status
        statuses = [fluid_press.status, vac_press.status, nozzle_tmp.status, syr_tmp.status]
        if SensorStatus.CRITICAL in statuses:
            line_status = SensorStatus.CRITICAL
        elif SensorStatus.WARNING in statuses:
            line_status = SensorStatus.WARNING
        else:
            line_status = SensorStatus.NOMINAL

        freq = round(cfg["base_freq_hz"] + random.uniform(-1.5, 1.5), 1)

        return LineTelemetrySnapshot(
            line_id=line_id,
            line_name=cfg["name"],
            technology=cfg["tech"],
            status=line_status,
            fluid_pressure=fluid_press,
            vacuum_pressure=vac_press,
            nozzle_temp=nozzle_tmp,
            syringe_temp=syr_tmp,
            valve_cycle_freq_hz=freq,
            active_syringe_id=mounted_item["id"] if mounted_item else None,
            active_syringe_lot=mounted_item["lot_number"] if mounted_item else None,
            active_material_name=mounted_item["material_name"] if mounted_item else None,
        )

    def get_telemetry_overview(self) -> TelemetryOverviewResponse:
        """Get aggregate cleanroom telemetry, all lines, and active syringes."""
        now = self._now()
        env = self.get_cleanroom_environment()

        lines = [self.get_line_snapshot(lid) for lid in LINE_CONFIGS.keys()]

        active_syringes = []
        urgent_alerts = 0

        for c_dict in self._consumables.values():
            item = self._evaluate_consumable(c_dict)
            if item.state in (ConsumableState.MOUNTED, ConsumableState.THAWING, ConsumableState.READY):
                active_syringes.append(item)
                if item.pot_life_status in (PotLifeStatus.WARNING, PotLifeStatus.CRITICAL, PotLifeStatus.EXPIRED):
                    urgent_alerts += 1

        return TelemetryOverviewResponse(
            timestamp=now.isoformat(),
            environment=env,
            lines=lines,
            active_syringes=active_syringes,
            urgent_alerts_count=urgent_alerts,
            system_status="OPTIMAL" if urgent_alerts == 0 else "ATTENTION_REQUIRED",
        )

    def get_consumables(self) -> list[ConsumableItem]:
        """Return all tracked consumables with up-to-date countdown states."""
        items = [self._evaluate_consumable(c) for c in self._consumables.values()]
        # Sort by state priority: MOUNTED, THAWING, READY, FROZEN, EXPIRED, SCRAPPED
        state_priority = {
            ConsumableState.MOUNTED: 1,
            ConsumableState.THAWING: 2,
            ConsumableState.READY: 3,
            ConsumableState.EXPIRED: 4,
            ConsumableState.FROZEN: 5,
            ConsumableState.SCRAPPED: 6,
        }
        return sorted(items, key=lambda x: (state_priority.get(x.state, 99), x.remaining_pot_life_seconds))

    def thaw_consumable(self, req: ThawRequest) -> ConsumableItem:
        """Start a defrosting/thaw cycle for a cold-stored adhesive syringe."""
        now = self._now()
        cat = MATERIAL_CATALOG.get(req.material_code, MATERIAL_CATALOG["NOA-68"])

        c_id = f"syr-{req.material_code.lower()}-{uuid.uuid4().hex[:6]}"
        thaw_end = now + timedelta(minutes=req.thaw_duration_minutes)

        item_dict = {
            "id": c_id,
            "lot_number": req.lot_number,
            "material_name": cat["name"],
            "material_type": cat["type"],
            "line_id": None,
            "barrel_size_cc": req.barrel_size_cc,
            "current_volume_cc": req.barrel_size_cc,
            "volume_percent": 100.0,
            "state": ConsumableState.THAWING,
            "thaw_start_time": now.isoformat(),
            "thaw_duration_minutes": req.thaw_duration_minutes,
            "thaw_end_time": thaw_end.isoformat(),
            "thaw_progress_pct": 0.0,
            "pot_life_hours": cat["pot_life_hours"],
            "pot_life_start_time": None,
            "pot_life_expiry_time": None,
            "estimated_shots_remaining": int(req.barrel_size_cc * cat["shots_per_cc"]),
            "nozzle_tip": {
                "gauge": "32G",
                "tip_type": "Precision Ceramic",
                "cycle_count": 0,
                "max_rated_cycles": 20000,
                "wear_percentage": 0.0,
                "last_purge_time": None,
                "purge_required": False,
            },
            "cleanroom_rack": req.cleanroom_rack,
            "notes": f"Defrost initiated at {now.strftime('%H:%M:%S')} UTC",
        }

        self._consumables[c_id] = item_dict
        return self._evaluate_consumable(item_dict)

    def mount_consumable(self, consumable_id: str, req: MountRequest) -> ConsumableItem:
        """Mount a thawed/ready syringe to a production line."""
        item_dict = self._consumables.get(consumable_id)
        if not item_dict:
            raise KeyError(f"Consumable '{consumable_id}' not found")

        now = self._now()

        # Unmount any existing consumable on that line
        for c in self._consumables.values():
            if c.get("line_id") == req.line_id and c.get("id") != consumable_id:
                if c.get("state") == ConsumableState.MOUNTED:
                    c["state"] = ConsumableState.READY
                    c["line_id"] = None

        # Calculate pot life if not already started
        if not item_dict.get("pot_life_start_time"):
            pot_hours = item_dict.get("pot_life_hours", 8.0)
            item_dict["pot_life_start_time"] = now.isoformat()
            item_dict["pot_life_expiry_time"] = (now + timedelta(hours=pot_hours)).isoformat()

        item_dict["line_id"] = req.line_id
        item_dict["state"] = ConsumableState.MOUNTED
        item_dict["notes"] = f"Mounted to {req.line_id.upper()} at {now.strftime('%H:%M:%S')} UTC"

        return self._evaluate_consumable(item_dict)

    def purge_consumable(self, consumable_id: str, req: PurgeRequest) -> ConsumableItem:
        """Execute a clean tip purge and record shot."""
        item_dict = self._consumables.get(consumable_id)
        if not item_dict:
            raise KeyError(f"Consumable '{consumable_id}' not found")

        now = self._now()
        tip = item_dict.get("nozzle_tip", {})
        tip["cycle_count"] = tip.get("cycle_count", 0) + req.test_shot_count
        tip["last_purge_time"] = now.isoformat()
        tip["purge_required"] = False
        item_dict["nozzle_tip"] = tip

        # Deduct small volume (approx 0.05 cc per purge)
        curr_vol = max(0.1, item_dict.get("current_volume_cc", 30.0) - 0.05)
        item_dict["current_volume_cc"] = round(curr_vol, 2)

        return self._evaluate_consumable(item_dict)

    def scrap_consumable(self, consumable_id: str, req: ScrapRequest) -> ConsumableItem:
        """Scrap a consumable with reason."""
        item_dict = self._consumables.get(consumable_id)
        if not item_dict:
            raise KeyError(f"Consumable '{consumable_id}' not found")

        item_dict["state"] = ConsumableState.SCRAPPED
        item_dict["line_id"] = None
        item_dict["scrap_reason"] = req.reason
        item_dict["notes"] = f"Scrapped: {req.reason}. {req.notes or ''}"

        return self._evaluate_consumable(item_dict)


# Global singleton service
telemetry_service = TelemetryService()
