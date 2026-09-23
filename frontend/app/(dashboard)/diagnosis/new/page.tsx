"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Rows3, Columns2 } from "lucide-react";
import PageContainer from "@/components/layout/PageContainer";
import ProblemForm, { ProblemFormData } from "@/components/diagnosis/ProblemForm";
import ImageUpload from "@/components/diagnosis/ImageUpload";
import { casesApi } from "@/lib/api/cases";
import { CreateCaseRequest, Observation, ObservationInput } from "@/types/api";
import { UploadSnapshot } from "@/types/image";

export default function NewDiagnosisPage() {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [uploadSnapshot, setUploadSnapshot] = useState<UploadSnapshot>({});
    const [layoutMode, setLayoutMode] = useState<"stacked" | "split">("stacked");

    const handleSubmit = async (data: ProblemFormData) => {
        if (isSubmitting) return;
        setIsSubmitting(true);
        setError(null);

        try {
            // 1. Derive active calibrated observations strictly from current snapshot
            const observations: (Observation | ObservationInput)[] = [];

            for (const uploadItem of Object.values(uploadSnapshot)) {
                if (uploadItem.status === "analyzed" && uploadItem.result?.status === "CALIBRATED") {
                    for (const obs of uploadItem.result.observations) {
                        if (obs.source === "IMAGE" && obs.statement_type === "AI_INFERENCE") {
                            observations.push({
                                id: obs.id,
                                observation_type: obs.observation_type,
                                value: obs.value,
                                original_text: obs.original_text,
                                statement_type: obs.statement_type,
                                source: obs.source,
                                confidence: obs.confidence,
                                metadata: obs.metadata,
                                timestamp: obs.timestamp,
                            });
                        }
                    }
                }
            }

            // 2. Derive canonical manual observations
            if (data.depositSize) {
                observations.push({
                    observation_type: "deposit_size",
                    value: data.depositSize,
                    source: "USER",
                    statement_type: "USER_OBSERVATION",
                });
            }

            if (data.frequency) {
                observations.push({
                    observation_type: "frequency_pattern",
                    value: data.frequency,
                    source: "USER",
                    statement_type: "USER_OBSERVATION",
                });
            }

            if (data.location) {
                observations.push({
                    observation_type: "location_pattern",
                    value: data.location,
                    source: "USER",
                    statement_type: "USER_OBSERVATION",
                });
            }

            if (data.recentChange && data.recentChange !== "none") {
                const obsType =
                    data.recentChange === "material_refilled"
                        ? "material_state"
                        : data.recentChange === "nozzle_changed"
                            ? "nozzle_condition"
                            : data.recentChange === "parameters_changed"
                                ? "process_parameter"
                                : "equipment_condition";

                observations.push({
                    observation_type: obsType,
                    value: data.recentChange,
                    source: "USER",
                    statement_type: "USER_OBSERVATION",
                });
            }

            // 3. Assemble CreateCaseRequest with controlled material and machine context
            const request: CreateCaseRequest = {
                defect_code: data.defect || undefined,
                description: data.description,
                material: data.material.trim() || undefined,
                machine_context: data.equipment ? { equipment: data.equipment } : undefined,
                observations,
            };

            const response = await casesApi.createCase(request);
            router.push(`/diagnosis/${response.case_id}`);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "An unexpected error occurred while creating the diagnosis.";
            setError(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <PageContainer>
            {/* Header with Title and Layout Toggle */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <p className="text-sm font-medium text-[#6d5dfc]">
                        Diagnostic workflow
                    </p>

                    <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
                        New Diagnosis
                    </h1>

                    <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
                        Describe the dispensing symptom and provide evidence
                        to begin AI-assisted troubleshooting.
                    </p>
                </div>

                {/* View Layout Controls */}
                <div className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#141b29] p-1.5 shadow-2xs">
                    <button
                        type="button"
                        onClick={() => setLayoutMode("stacked")}
                        className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${layoutMode === "stacked"
                                ? "bg-[#6d5dfc] text-white shadow-xs"
                                : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800"
                            }`}
                        title="Spacious Full-Width Stacked View"
                    >
                        <Rows3 size={15} />
                        <span>Spacious Stacked (Full Width)</span>
                    </button>

                    <button
                        type="button"
                        onClick={() => setLayoutMode("split")}
                        className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${layoutMode === "split"
                                ? "bg-[#6d5dfc] text-white shadow-xs"
                                : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800"
                            }`}
                        title="Balanced 50/50 Split View"
                    >
                        <Columns2 size={15} />
                        <span>Balanced Split (50/50)</span>
                    </button>
                </div>
            </div>

            {error && (
                <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 shadow-sm">
                    {error}
                </div>
            )}
            {isSubmitting && (
                <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-700 shadow-sm">
                    Creating diagnosis case and running initial AI evaluation... Please wait.
                </div>
            )}

            {/* Layout Mode 1: Spacious Stacked (Full Width) */}
            {layoutMode === "stacked" ? (
                <div className="mt-8 space-y-8">
                    {/* Visual Defect Evidence */}
                    <div>
                        <ImageUpload
                            onSnapshotChange={setUploadSnapshot}
                            isFullWidth={true}
                        />
                    </div>

                    {/* Defect Taxonomy & Problem Description */}
                    <div>
                        <ProblemForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
                    </div>

                    {/* Full-width Tips Banner */}
                    <div className="rounded-2xl border border-[#ded9ff] dark:border-[#6d5dfc]/30 bg-[#faf9ff] dark:bg-[#161e2e] p-5 sm:p-6 shadow-2xs">
                        <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                            Tips for better diagnosis
                        </p>

                        <ul className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs leading-5 text-gray-600 dark:text-gray-300">
                            <li className="flex items-start gap-2.5">
                                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                <span>Be specific about when the defect appears (steady vs. occasional)</span>
                            </li>

                            <li className="flex items-start gap-2.5">
                                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                <span>Specify whether all nozzles or specific dispensing points are affected</span>
                            </li>

                            <li className="flex items-start gap-2.5">
                                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                <span>Include material details (epoxy, solder paste, RTV silicone)</span>
                            </li>

                            <li className="flex items-start gap-2.5">
                                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                <span>Draw precise rectangular target ROIs over uploaded deposit images</span>
                            </li>
                        </ul>
                    </div>
                </div>
            ) : (
                /* Layout Mode 2: Balanced Split (50/50) */
                <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2 items-start">
                    <div>
                        <ProblemForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
                    </div>

                    <div className="space-y-6">
                        <ImageUpload
                            onSnapshotChange={setUploadSnapshot}
                            isFullWidth={false}
                        />

                        {/* Tips Card */}
                        <div className="rounded-2xl border border-[#ded9ff] dark:border-[#6d5dfc]/30 bg-[#faf9ff] dark:bg-[#161e2e] p-5 shadow-2xs">
                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                                Tips for better diagnosis
                            </p>

                            <ul className="mt-3 space-y-2.5 text-xs leading-5 text-gray-600 dark:text-gray-300">
                                <li className="flex items-start gap-2">
                                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                    Be specific about when the defect appears (steady vs. occasional)
                                </li>

                                <li className="flex items-start gap-2">
                                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                    Specify whether all nozzles or specific dispensing points are affected
                                </li>

                                <li className="flex items-start gap-2">
                                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                    Include material details (epoxy, solder paste, RTV silicone)
                                </li>

                                <li className="flex items-start gap-2">
                                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                    Draw precise rectangular target ROIs over uploaded deposit images
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            )}
        </PageContainer>
    );
}
