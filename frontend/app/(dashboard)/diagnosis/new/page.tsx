"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";
import ProblemForm from "@/components/diagnosis/ProblemForm";
import ImageUpload from "@/components/diagnosis/ImageUpload";
import { casesApi } from "@/lib/api/cases";
import { CreateCaseRequest, Observation } from "@/types/api";

export default function NewDiagnosisPage() {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (data: Record<string, unknown>) => {
        setIsSubmitting(true);
        setError(null);

        try {
            const observations: Observation[] = [];
            
            if (data.depositSize) {
                observations.push({
                    observation_type: "deposit_size",
                    value: data.depositSize as string,
                });
            }
            if (data.frequency) {
                observations.push({
                    observation_type: "frequency_pattern",
                    value: data.frequency as string,
                });
            }
            if (data.location) {
                observations.push({
                    observation_type: "location_pattern",
                    value: data.location as string,
                });
            }

            const request: CreateCaseRequest = {
                defect_code: data.defect as string,
                description: data.description as string,
                machine_context: data.equipment ? { equipment: data.equipment } : undefined,
                observations: observations,
            };

            const response = await casesApi.createCase(request);
            router.push(`/diagnosis/${response.case_id}`);
        } catch (err: any) {
            console.error("Failed to create diagnosis", err);
            setError(err.message || "An error occurred while creating the diagnosis.");
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
                            <div className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-700">
                                {error}
                            </div>
                        )}
                        {isSubmitting && (
                            <div className="mt-4 rounded-xl bg-blue-50 p-4 text-sm text-blue-700">
                                Creating diagnosis... Please wait.
                            </div>
                        )}
                    </div>

                    <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-3">
                        <div className="xl:col-span-2">
                            <ProblemForm onSubmit={handleSubmit} />
                        </div>

                        <div>
                            <ImageUpload />

                            {/* Tips Card */}
                            <div className="mt-6 rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-5">
                                <p className="text-sm font-semibold text-gray-900">
                                    Tips for better diagnosis
                                </p>

                                <ul className="mt-3 space-y-2.5 text-xs leading-5 text-gray-600">
                                    <li className="flex items-start gap-2">
                                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                        Be specific about when the defect
                                        appears (startup vs. prolonged
                                        operation)
                                    </li>

                                    <li className="flex items-start gap-2">
                                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                        Note whether the issue affects all
                                        nozzles or specific ones
                                    </li>

                                    <li className="flex items-start gap-2">
                                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                        Include any recent maintenance or
                                        material changes
                                    </li>

                                    <li className="flex items-start gap-2">
                                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d5dfc]" />
                                        Upload close-up photos of affected
                                        deposits if possible
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
