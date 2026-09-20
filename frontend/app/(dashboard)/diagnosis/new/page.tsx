"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
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
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div>
                        <p className="text-sm font-medium text-[#6d5dfc]">
                            Diagnostic workflow
                        </p>

                        <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                            New Diagnosis
                        </h1>

                        <p className="mt-2 text-sm text-gray-500">
                            Describe the dispensing symptom and provide evidence
                            to begin AI-assisted troubleshooting.
                        </p>

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
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="xl:col-span-2">
                            <ProblemForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
                        </div>

                        <div>
                            <ImageUpload onSnapshotChange={setUploadSnapshot} />

                            {/* Tips Card */}
                            <div className="mt-6 rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-5">
                                <p className="text-sm font-semibold text-gray-900">
                                    Tips for better diagnosis
                                </p>

                                <ul className="mt-3 space-y-2.5 text-xs leading-5 text-gray-600">
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
                </PageContainer>
            </div>
        </div>
    );
}
