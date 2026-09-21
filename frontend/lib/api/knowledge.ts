/**
 * Knowledge Base Catalog API Client (FR-034)
 * Provides direct REST API integration with backend knowledge endpoints:
 * - GET /api/v1/defects
 * - GET /api/v1/causes
 * - GET /api/v1/actions
 * - GET /api/v1/rules
 * - GET /api/v1/questions
 */

import { apiClient } from "./client";

export interface SymptomPattern {
    type: string;
    value: string;
}

export interface DefectDefinition {
    code: string;
    name: string;
    description: string;
    symptom_patterns?: SymptomPattern[];
    applicable_causes?: string[];
    source_references?: string[];
}

export interface CauseDefinition {
    id: string;
    name: string;
    description: string;
    applicable_defects?: string[];
    applicable_contexts?: string[];
    source_references?: string[];
}

export interface CheckDefinition {
    id: string;
    name: string;
    description: string;
    procedure?: string;
    applicable_causes?: string[];
    applicable_defects?: string[];
    required_access?: string;
    effort_level?: "low" | "medium" | "high" | string;
    source_references?: string[];
    evidence_mapping?: Record<string, unknown>;
}

export interface EvidenceRuleDefinition {
    id: string;
    observation_type: string;
    observation_value: string;
    cause_id: string;
    relation: "SUPPORTS" | "CONTRADICTS" | "NEUTRAL" | string;
    strength: "STRONG" | "MODERATE" | "WEAK" | string;
    explanation: string;
}

export interface QuestionDefinition {
    id: string;
    text: string;
    purpose: string;
    applicable_causes?: string[];
    applicable_defects?: string[];
    expected_answer_type?: string;
    evidence_mapping?: Record<string, unknown>;
}

export interface KnowledgeCatalogSummary {
    defects: DefectDefinition[];
    causes: CauseDefinition[];
    actions: CheckDefinition[];
    rules: EvidenceRuleDefinition[];
    questions: QuestionDefinition[];
    isLive: boolean;
    fetchedAt: string;
}

/**
 * Fetch all defect definitions directly from the backend REST catalog.
 */
export async function getDefects(): Promise<DefectDefinition[]> {
    return apiClient.get<DefectDefinition[]>("/defects");
}

/**
 * Fetch all root cause definitions, optionally filtered by defect code.
 */
export async function getCauses(defectCode?: string): Promise<CauseDefinition[]> {
    const query = defectCode ? `?defect_code=${encodeURIComponent(defectCode)}` : "";
    return apiClient.get<CauseDefinition[]>(`/causes${query}`);
}

/**
 * Fetch all authorized troubleshooting check/action definitions.
 */
export async function getActions(): Promise<CheckDefinition[]> {
    return apiClient.get<CheckDefinition[]>("/actions");
}

/**
 * Fetch all authorized diagnostic evidence evaluation rules.
 */
export async function getRules(params?: { causeId?: string; observationType?: string }): Promise<EvidenceRuleDefinition[]> {
    const searchParams = new URLSearchParams();
    if (params?.causeId) searchParams.set("cause_id", params.causeId);
    if (params?.observationType) searchParams.set("observation_type", params.observationType);
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return apiClient.get<EvidenceRuleDefinition[]>(`/rules${qs}`);
}

/**
 * Fetch all diagnostic questions from the knowledge catalog.
 */
export async function getQuestions(params?: { causeId?: string; defectCode?: string }): Promise<QuestionDefinition[]> {
    const searchParams = new URLSearchParams();
    if (params?.causeId) searchParams.set("cause_id", params.causeId);
    if (params?.defectCode) searchParams.set("defect_code", params.defectCode);
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return apiClient.get<QuestionDefinition[]>(`/questions${qs}`);
}

/**
 * Convenience aggregator to load the full live knowledge catalog simultaneously.
 */
export async function getFullKnowledgeCatalog(): Promise<KnowledgeCatalogSummary> {
    try {
        const [defects, causes, actions, rules, questions] = await Promise.all([
            getDefects(),
            getCauses(),
            getActions(),
            getRules(),
            getQuestions(),
        ]);

        return {
            defects,
            causes,
            actions,
            rules,
            questions,
            isLive: true,
            fetchedAt: new Date().toISOString(),
        };
    } catch (err) {
        console.warn("[KnowledgeAPI] Failed to fetch live knowledge catalog, falling back to static backup:", err);
        return {
            defects: FALLBACK_DEFECTS,
            causes: FALLBACK_CAUSES,
            actions: FALLBACK_ACTIONS,
            rules: FALLBACK_RULES,
            questions: FALLBACK_QUESTIONS,
            isLive: false,
            fetchedAt: new Date().toISOString(),
        };
    }
}

// ---------------------------------------------------------------------------
// Reliable offline fallback fixtures
// ---------------------------------------------------------------------------

export const FALLBACK_DEFECTS: DefectDefinition[] = [
    {
        code: "D01_TOO_LITTLE",
        name: "Too Little Material",
        description: "Dispensed volume is consistently less than target amount, resulting in undersized deposits.",
        applicable_causes: ["nozzle_restriction", "air_supply_issue", "material_condition", "pressure_instability", "parameter_issue", "equipment_condition"],
    },
    {
        code: "D02_TOO_MUCH",
        name: "Too Much Material",
        description: "Dispensed volume is consistently more than target amount, resulting in oversized deposits.",
        applicable_causes: ["parameter_issue", "pressure_instability", "material_condition", "nozzle_condition", "equipment_condition", "valve_issue"],
    },
    {
        code: "D03_INCONSISTENT_SIZE",
        name: "Inconsistent Dispensing Size",
        description: "Dispensed volume varies from shot to shot, producing deposits of different sizes.",
        applicable_causes: ["air_supply_issue", "nozzle_restriction", "material_condition", "pressure_instability", "parameter_issue", "equipment_condition"],
    },
    {
        code: "D04_MISSING_DOTS",
        name: "Missing Dots",
        description: "One or more dispensing locations receive no material at all.",
        applicable_causes: ["nozzle_restriction", "air_supply_issue", "valve_issue", "material_condition", "equipment_condition", "pressure_instability"],
    },
    {
        code: "D05_SPREADING",
        name: "Spreading",
        description: "Dispensed material spreads excessively on the substrate instead of forming a controlled dot.",
        applicable_causes: ["material_condition", "parameter_issue", "temperature_issue", "substrate_condition", "nozzle_condition", "equipment_condition"],
    },
    {
        code: "D06_BUBBLES_ABNORMAL_SHAPE",
        name: "Bubbles / Abnormal Shape",
        description: "Dispensed deposits contain trapped air bubbles, satellite droplets, or tailing defects.",
        applicable_causes: ["air_supply_issue", "material_condition", "nozzle_condition", "parameter_issue", "equipment_condition", "valve_issue"],
    },
];

export const FALLBACK_CAUSES: CauseDefinition[] = [
    { id: "air_supply_issue", name: "Air / Supply Issue", description: "Trapped air or inconsistent air pressure in the material supply path.", applicable_defects: ["D01_TOO_LITTLE", "D03_INCONSISTENT_SIZE", "D04_MISSING_DOTS", "D06_BUBBLES_ABNORMAL_SHAPE"] },
    { id: "nozzle_restriction", name: "Nozzle Restriction", description: "Partial or complete blockage of the dispensing nozzle.", applicable_defects: ["D01_TOO_LITTLE", "D03_INCONSISTENT_SIZE", "D04_MISSING_DOTS"] },
    { id: "material_condition", name: "Material Condition", description: "Material properties outside acceptable range (pot life, viscosity, thaw).", applicable_defects: ["D01_TOO_LITTLE", "D02_TOO_MUCH", "D03_INCONSISTENT_SIZE", "D04_MISSING_DOTS", "D05_SPREADING", "D06_BUBBLES_ABNORMAL_SHAPE"] },
    { id: "pressure_instability", name: "Pressure Instability", description: "Inconsistent dispensing pressure from supply regulator or line leaks.", applicable_defects: ["D01_TOO_LITTLE", "D02_TOO_MUCH", "D03_INCONSISTENT_SIZE", "D04_MISSING_DOTS"] },
    { id: "parameter_issue", name: "Parameter Issue", description: "Dispensing parameters (pressure, time, speed, gap) incorrectly configured.", applicable_defects: ["D01_TOO_LITTLE", "D02_TOO_MUCH", "D03_INCONSISTENT_SIZE", "D05_SPREADING", "D06_BUBBLES_ABNORMAL_SHAPE"] },
    { id: "equipment_condition", name: "Equipment Condition", description: "Mechanical wear, misalignment, or calibration drift in equipment.", applicable_defects: ["D01_TOO_LITTLE", "D02_TOO_MUCH", "D03_INCONSISTENT_SIZE", "D04_MISSING_DOTS", "D05_SPREADING", "D06_BUBBLES_ABNORMAL_SHAPE"] },
    { id: "valve_issue", name: "Valve Issue", description: "Dispensing valve malfunction, seat wear, or improper closing.", applicable_defects: ["D02_TOO_MUCH", "D04_MISSING_DOTS", "D06_BUBBLES_ABNORMAL_SHAPE"] },
    { id: "temperature_issue", name: "Temperature Issue", description: "Ambient or material temperature outside acceptable range.", applicable_defects: ["D05_SPREADING"] },
    { id: "substrate_condition", name: "Substrate Condition", description: "Substrate surface energy, contamination, or moisture affects wetting.", applicable_defects: ["D05_SPREADING"] },
    { id: "nozzle_condition", name: "Nozzle Condition", description: "Nozzle tip damage, wear, or dried fluid contamination at tip face.", applicable_defects: ["D02_TOO_MUCH", "D05_SPREADING", "D06_BUBBLES_ABNORMAL_SHAPE"] },
];

export const FALLBACK_ACTIONS: CheckDefinition[] = [
    { id: "ACT01", name: "Inspect Nozzle", effort_level: "low", applicable_causes: ["nozzle_restriction", "nozzle_condition"], description: "Visual inspection under magnification to check for blockage, dried material, or damage." },
    { id: "ACT02", name: "Check Material Supply", effort_level: "low", applicable_causes: ["air_supply_issue", "material_condition"], description: "Inspect syringe barrel, fluid levels, and check for air bubble pockets or pot life." },
    { id: "ACT03", name: "Perform Test Shots", effort_level: "medium", applicable_causes: ["pressure_instability", "parameter_issue"], description: "Dispense test matrix on reference substrate and weigh on analytical balance." },
    { id: "ACT04", name: "Verify Pressure Settings", effort_level: "medium", applicable_causes: ["pressure_instability", "parameter_issue"], description: "Check regulator gauge readings against recipe specification." },
    { id: "ACT05", name: "Perform Purge Cycle", effort_level: "low", applicable_causes: ["air_supply_issue", "nozzle_restriction"], description: "Execute high-pressure fluid purge cycle to clear trapped bubbles and dried material." },
    { id: "ACT06", name: "Inspect Valve Assembly", effort_level: "high", applicable_causes: ["valve_issue", "equipment_condition"], description: "Disassemble valve body, check seal integrity and diaphragm wear." },
    { id: "ACT07", name: "Check Temperature", effort_level: "low", applicable_causes: ["temperature_issue", "material_condition"], description: "Measure syringe heater and ambient cleanroom temperature." },
    { id: "ACT08", name: "Inspect Substrate", effort_level: "low", applicable_causes: ["substrate_condition"], description: "Verify surface cleanliness and surface energy with dyne test pens." },
    { id: "ACT09", name: "Verify Parameters", effort_level: "low", applicable_causes: ["parameter_issue"], description: "Audit active PLC recipe parameters against authorized Golden Board setup." },
    { id: "ACT10", name: "Calibrate Equipment", effort_level: "high", applicable_causes: ["equipment_condition"], description: "Run automated nozzle offset calibration and height sensor verification." },
];

export const FALLBACK_RULES: EvidenceRuleDefinition[] = [
    { id: "R001", observation_type: "deposit_size", observation_value: "undersized", cause_id: "air_supply_issue", relation: "SUPPORTS", strength: "MODERATE", explanation: "Undersized deposits can result from air displacing material volume in the supply path." },
    { id: "R002", observation_type: "deposit_size", observation_value: "undersized", cause_id: "nozzle_restriction", relation: "SUPPORTS", strength: "STRONG", explanation: "A restricted nozzle directly reduces the amount of material that can pass through." },
    { id: "R007", observation_type: "deposit_size", observation_value: "inconsistent", cause_id: "air_supply_issue", relation: "SUPPORTS", strength: "STRONG", explanation: "Intermittent air pockets cause variable displacement of material." },
    { id: "R009", observation_type: "deposit_size", observation_value: "inconsistent", cause_id: "pressure_instability", relation: "SUPPORTS", strength: "STRONG", explanation: "Fluctuating pressure directly causes varying dispensed volumes." },
    { id: "R011", observation_type: "runtime_pattern", observation_value: "after_prolonged_operation", cause_id: "air_supply_issue", relation: "SUPPORTS", strength: "STRONG", explanation: "Air expansion due to heating during prolonged operation disrupts dispensing." },
    { id: "R013", observation_type: "runtime_pattern", observation_value: "after_prolonged_operation", cause_id: "material_condition", relation: "SUPPORTS", strength: "MODERATE", explanation: "Extended time at operating temperature may degrade material properties." },
];

export const FALLBACK_QUESTIONS: QuestionDefinition[] = [
    { id: "Q01", text: "Does the problem occur immediately after startup or only after the machine has been running for a while?", purpose: "Distinguishes thermal/time-related causes from static issues.", applicable_causes: ["air_supply_issue", "material_condition", "pressure_instability", "temperature_issue"] },
    { id: "Q02", text: "Does the defect occur across all dispensing points or only at specific nozzles/locations?", purpose: "Distinguishes system-wide causes from localized nozzle clogs.", applicable_causes: ["nozzle_restriction", "air_supply_issue", "pressure_instability", "valve_issue"] },
    { id: "Q10", text: "Has the ambient temperature or material temperature changed noticeably?", purpose: "Identifies temperature-related viscosity changes.", applicable_causes: ["temperature_issue", "material_condition"] },
    { id: "Q13", text: "How long has the dispensing material been in the syringe/reservoir since it was loaded?", purpose: "Identifies pot-life / shelf-life related material degradation.", applicable_causes: ["material_condition"] },
];
