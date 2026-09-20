"""Pydantic schemas for Cleanroom Telemetry and Syringe Pot Life Tracking."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class SensorStatus(str, Enum):
    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ConsumableState(str, Enum):
    FROZEN = "FROZEN"
    THAWING = "THAWING"
    READY = "READY"
    MOUNTED = "MOUNTED"
    EXPIRED = "EXPIRED"
    SCRAPPED = "SCRAPPED"


class PotLifeStatus(str, Enum):
    OPTIMAL = "OPTIMAL"    # > 2 hours remaining
    WARNING = "WARNING"    # 30 mins to 2 hours remaining
    CRITICAL = "CRITICAL"  # < 30 mins remaining
    EXPIRED = "EXPIRED"    # <= 0 seconds remaining


class CleanroomEnvironment(BaseModel):
    """Ambient cleanroom facility sensor readings."""
    ambient_temp_c: float = Field(..., description="Cleanroom temperature in Celsius")
    ambient_temp_status: SensorStatus = SensorStatus.NOMINAL
    relative_humidity_pct: float = Field(..., description="Cleanroom relative humidity percentage")
    humidity_status: SensorStatus = SensorStatus.NOMINAL
    differential_pressure_pa: float = Field(..., description="Positive pressure differential in Pascals")
    particle_count_per_m3: int = Field(..., description="Airborne particles >= 0.5 µm per cubic meter")
    iso_class: str = Field("ISO Class 5", description="Cleanroom ISO classification standard")
    iso_certified: bool = Field(True, description="Whether currently within ISO 5 cleanliness thresholds")
    last_updated: str = Field(..., description="ISO 8601 timestamp of measurement")


class SensorReading(BaseModel):
    """Detailed reading for a specific physical machine sensor."""
    sensor_id: str
    name: str
    value: float
    unit: str
    target: float
    usl: float
    lsl: float
    status: SensorStatus
    sparkline: list[float] = Field(default_factory=list, description="Recent 20-30 data points for sparkline visual")


class LineTelemetrySnapshot(BaseModel):
    """Real-time physical telemetry snapshot for an automated dispensing line."""
    line_id: str
    line_name: str
    technology: str
    status: SensorStatus
    fluid_pressure: SensorReading
    vacuum_pressure: SensorReading
    nozzle_temp: SensorReading
    syringe_temp: SensorReading
    valve_cycle_freq_hz: float = Field(..., description="Jetting / stroke frequency in Hz")
    active_syringe_id: Optional[str] = None
    active_syringe_lot: Optional[str] = None
    active_material_name: Optional[str] = None


class NozzleTipInfo(BaseModel):
    """Dispensing nozzle tip wear and maintenance state."""
    gauge: str = Field("32G", description="Nozzle needle gauge or orifice size")
    tip_type: str = Field("Chamfered Ceramic", description="Material and tip geometry")
    cycle_count: int = Field(0, description="Accumulated dispensing cycles/shots")
    max_rated_cycles: int = Field(20000, description="Maximum recommended cycles before replacement")
    wear_percentage: float = Field(0.0, description="Wear percentage 0-100%")
    last_purge_time: Optional[str] = None
    purge_required: bool = False


class ConsumableItem(BaseModel):
    """Complete lifecycle tracking model for an adhesive syringe or reservoir."""
    id: str
    lot_number: str
    material_name: str
    material_type: str = Field("uv_acrylic", description="uv_acrylic, thermal_epoxy, dual_part_silicone, cyanoacrylate")
    line_id: Optional[str] = None
    barrel_size_cc: float = Field(30.0, description="Syringe capacity in cubic centimeters")
    current_volume_cc: float = Field(30.0, description="Remaining fluid volume in cc")
    volume_percent: float = Field(100.0, description="Remaining volume percentage 0-100%")
    state: ConsumableState = ConsumableState.READY

    # Thaw / Defrost tracking
    thaw_start_time: Optional[str] = None
    thaw_duration_minutes: int = 45
    thaw_end_time: Optional[str] = None
    thaw_progress_pct: float = 100.0

    # Pot life work window tracking
    pot_life_hours: float = 8.0
    pot_life_start_time: Optional[str] = None
    pot_life_expiry_time: Optional[str] = None
    remaining_pot_life_seconds: int = 0
    pot_life_status: PotLifeStatus = PotLifeStatus.OPTIMAL

    # Usage and hardware
    estimated_shots_remaining: int = 4500
    nozzle_tip: NozzleTipInfo = Field(default_factory=NozzleTipInfo)
    scrap_reason: Optional[str] = None
    cleanroom_rack: Optional[str] = None
    notes: Optional[str] = None


class ThawRequest(BaseModel):
    """Payload to initiate controlled defrost/thaw of a frozen syringe."""
    lot_number: str
    material_code: str = Field(..., description="NOA-68, LOCTITE-382, EPO-TEK-353ND, DOW-OE6630")
    thaw_duration_minutes: int = Field(45, ge=10, le=180)
    barrel_size_cc: float = Field(30.0, ge=3.0, le=100.0)
    cleanroom_rack: str = Field("RACK-CR1-04", description="Location ID in cleanroom staging area")


class MountRequest(BaseModel):
    """Payload to mount a ready syringe to a production line."""
    line_id: str = Field(..., description="Target line: line-a, line-b, line-c, line-d")


class PurgeRequest(BaseModel):
    """Payload to execute and record a nozzle tip purge shot."""
    purge_duration_ms: int = Field(500, ge=100, le=5000)
    test_shot_count: int = Field(5, ge=1, le=20)


class ScrapRequest(BaseModel):
    """Payload to scrap an expired or contaminated consumable."""
    reason: str = Field(..., description="EXPIRED_POT_LIFE, VISCOSITY_DRIFT, AIR_BUBBLES, NOZZLE_DAMAGE")
    notes: Optional[str] = None


class TelemetryOverviewResponse(BaseModel):
    """Aggregated cleanroom telemetry and active pot life countdown response."""
    timestamp: str
    environment: CleanroomEnvironment
    lines: list[LineTelemetrySnapshot]
    active_syringes: list[ConsumableItem]
    urgent_alerts_count: int
    system_status: str = "NORMAL"
