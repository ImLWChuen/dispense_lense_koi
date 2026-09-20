"""API router for Cleanroom Telemetry and Syringe Pot Life Tracking."""

from fastapi import APIRouter, HTTPException, status
from typing import Optional

from app.schemas.telemetry import (
    ConsumableItem,
    LineTelemetrySnapshot,
    MountRequest,
    PurgeRequest,
    ScrapRequest,
    TelemetryOverviewResponse,
    ThawRequest,
)
from app.services.telemetry.telemetry_service import telemetry_service

router = APIRouter()


@router.get(
    "/overview",
    response_model=TelemetryOverviewResponse,
    summary="Get cleanroom environmental and line telemetry overview",
    description="Returns ambient cleanroom conditions, live sensor snapshots for Lines A-D, and active syringe countdowns.",
)
def get_telemetry_overview() -> TelemetryOverviewResponse:
    return telemetry_service.get_telemetry_overview()


@router.get(
    "/lines/{line_id}",
    response_model=LineTelemetrySnapshot,
    summary="Get detailed real-time sensor telemetry for a line",
    description="Returns high-frequency sensor readings, tolerances, and sparkline trends for the specified line.",
)
def get_line_telemetry(line_id: str) -> LineTelemetrySnapshot:
    return telemetry_service.get_line_snapshot(line_id)


@router.get(
    "/consumables",
    response_model=list[ConsumableItem],
    summary="List all tracked adhesive syringes and consumables",
    description="Returns inventory of syringes with real-time pot life countdowns, thaw progress, and barrel volume.",
)
def get_consumables() -> list[ConsumableItem]:
    return telemetry_service.get_consumables()


@router.post(
    "/consumables/thaw",
    response_model=ConsumableItem,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate controlled thaw/defrost cycle for a syringe",
    description="Takes a frozen adhesive syringe from -40°C storage and initiates ambient defrost countdown.",
)
def thaw_consumable(request: ThawRequest) -> ConsumableItem:
    return telemetry_service.thaw_consumable(request)


@router.post(
    "/consumables/{consumable_id}/mount",
    response_model=ConsumableItem,
    summary="Mount a thawed or ready syringe to a production line",
    description="Assigns syringe to line and activates pot life work window timer.",
)
def mount_consumable(consumable_id: str, request: MountRequest) -> ConsumableItem:
    try:
        return telemetry_service.mount_consumable(consumable_id, request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/consumables/{consumable_id}/purge",
    response_model=ConsumableItem,
    summary="Record a dispensing nozzle tip purge shot",
    description="Records purge event, updates tip cycle counts, and resets purge alert status.",
)
def purge_consumable(consumable_id: str, request: PurgeRequest) -> ConsumableItem:
    try:
        return telemetry_service.purge_consumable(consumable_id, request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/consumables/{consumable_id}/scrap",
    response_model=ConsumableItem,
    summary="Retire or scrap an expired/degraded consumable",
    description="Marks syringe as SCRAPPED with audit reason and dismounts from line.",
)
def scrap_consumable(consumable_id: str, request: ScrapRequest) -> ConsumableItem:
    try:
        return telemetry_service.scrap_consumable(consumable_id, request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
