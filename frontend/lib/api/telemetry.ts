import { apiClient } from "./client";

export type SensorStatus = "NOMINAL" | "WARNING" | "CRITICAL";

export type ConsumableState =
    | "FROZEN"
    | "THAWING"
    | "READY"
    | "MOUNTED"
    | "EXPIRED"
    | "SCRAPPED";

export type PotLifeStatus = "OPTIMAL" | "WARNING" | "CRITICAL" | "EXPIRED";

export interface CleanroomEnvironment {
    ambient_temp_c: number;
    ambient_temp_status: SensorStatus;
    relative_humidity_pct: number;
    humidity_status: SensorStatus;
    differential_pressure_pa: number;
    particle_count_per_m3: number;
    iso_class: string;
    iso_certified: boolean;
    last_updated: string;
}

export interface SensorReading {
    sensor_id: string;
    name: string;
    value: number;
    unit: string;
    target: number;
    usl: number;
    lsl: number;
    status: SensorStatus;
    sparkline: number[];
}

export interface LineTelemetrySnapshot {
    line_id: string;
    line_name: string;
    technology: string;
    status: SensorStatus;
    fluid_pressure: SensorReading;
    vacuum_pressure: SensorReading;
    nozzle_temp: SensorReading;
    syringe_temp: SensorReading;
    valve_cycle_freq_hz: number;
    active_syringe_id: string | null;
    active_syringe_lot: string | null;
    active_material_name: string | null;
}

export interface NozzleTipInfo {
    gauge: string;
    tip_type: string;
    cycle_count: number;
    max_rated_cycles: number;
    wear_percentage: number;
    last_purge_time: string | null;
    purge_required: boolean;
}

export interface ConsumableItem {
    id: string;
    lot_number: string;
    material_name: string;
    material_type: string;
    line_id: string | null;
    barrel_size_cc: number;
    current_volume_cc: number;
    volume_percent: number;
    state: ConsumableState;

    thaw_start_time: string | null;
    thaw_duration_minutes: number;
    thaw_end_time: string | null;
    thaw_progress_pct: number;

    pot_life_hours: number;
    pot_life_start_time: string | null;
    pot_life_expiry_time: string | null;
    remaining_pot_life_seconds: number;
    pot_life_status: PotLifeStatus;

    estimated_shots_remaining: number;
    nozzle_tip: NozzleTipInfo;
    scrap_reason: string | null;
    cleanroom_rack: string | null;
    notes: string | null;
}

export interface ThawRequest {
    lot_number: string;
    material_code: string;
    thaw_duration_minutes: number;
    barrel_size_cc: number;
    cleanroom_rack: string;
}

export interface MountRequest {
    line_id: string;
}

export interface PurgeRequest {
    purge_duration_ms: number;
    test_shot_count: number;
}

export interface ScrapRequest {
    reason: string;
    notes?: string;
}

export interface TelemetryOverviewResponse {
    timestamp: string;
    environment: CleanroomEnvironment;
    lines: LineTelemetrySnapshot[];
    active_syringes: ConsumableItem[];
    urgent_alerts_count: number;
    system_status: string;
}

export const telemetryApi = {
    async getOverview(): Promise<TelemetryOverviewResponse> {
        return apiClient.get<TelemetryOverviewResponse>("/telemetry/overview");
    },

    async getLineTelemetry(lineId: string): Promise<LineTelemetrySnapshot> {
        return apiClient.get<LineTelemetrySnapshot>(`/telemetry/lines/${lineId}`);
    },

    async getConsumables(): Promise<ConsumableItem[]> {
        return apiClient.get<ConsumableItem[]>("/telemetry/consumables");
    },

    async thawConsumable(data: ThawRequest): Promise<ConsumableItem> {
        return apiClient.post<ConsumableItem>("/telemetry/consumables/thaw", data);
    },

    async mountConsumable(id: string, data: MountRequest): Promise<ConsumableItem> {
        return apiClient.post<ConsumableItem>(`/telemetry/consumables/${id}/mount`, data);
    },

    async purgeConsumable(id: string, data: PurgeRequest = { purge_duration_ms: 500, test_shot_count: 5 }): Promise<ConsumableItem> {
        return apiClient.post<ConsumableItem>(`/telemetry/consumables/${id}/purge`, data);
    },

    async scrapConsumable(id: string, data: ScrapRequest): Promise<ConsumableItem> {
        return apiClient.post<ConsumableItem>(`/telemetry/consumables/${id}/scrap`, data);
    },
};
