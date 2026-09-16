import Link from "next/link";
import {
    ArrowLeft,
    CheckCircle2,
    Download,
    FileText,
    Share2,
    Calendar,
    Settings,
    Activity,
    AlertTriangle
} from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";

interface PageProps {
    params: {
        id: string;
    };
}

export default function ReportDetailPage({ params }: PageProps) {
    const { id } = params;

    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="mb-6">
                        <Link
                            href="/reports"
                            className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-900 transition"
                        >
                            <ArrowLeft size={16} />
                            Back to Reports
                        </Link>
                    </div>

                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
                        <div>
                            <div className="flex items-center gap-3 mb-2">
                                <span className="inline-flex rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
                                    Complete
                                </span>
                                <span className="text-sm font-medium text-gray-500">
                                    Diagnostic Report
                                </span>
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-gray-900">
                                Nozzle Restriction — Line A
                            </h1>
                            <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
                                <div className="flex items-center gap-1.5">
                                    <FileText size={16} />
                                    <span>{id}</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <Calendar size={16} />
                                    <span>Sep 15, 2026</span>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            <button className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50">
                                <Share2 size={16} />
                                Share
                            </button>
                            <button className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-[#5848e8]">
                                <Download size={16} />
                                Download PDF
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                        <div className="lg:col-span-2 space-y-6">
                            {/* Executive Summary */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h2 className="text-lg font-semibold text-gray-900 mb-4">Executive Summary</h2>
                                <p className="text-sm leading-relaxed text-gray-600">
                                    On September 15, 2026, Line A experienced a significant drop in dispensing volume, leading to partial fills. The AI diagnostic system identified a potential nozzle restriction as the root cause with 94% confidence. Visual inspection and flow tests confirmed partial blockage due to material curing in the nozzle tip. The issue was resolved by replacing the nozzle assembly and flushing the line.
                                </p>
                            </div>

                            {/* Analysis Steps */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h2 className="text-lg font-semibold text-gray-900 mb-4">Diagnostic Analysis</h2>
                                
                                <div className="relative border-l border-gray-200 ml-3 space-y-8">
                                    <div className="relative pl-6">
                                        <span className="absolute -left-3 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-red-100 ring-4 ring-white">
                                            <AlertTriangle size={14} className="text-red-600" />
                                        </span>
                                        <h3 className="text-sm font-semibold text-gray-900">Issue Detected</h3>
                                        <p className="mt-1 text-sm text-gray-600">Vision system reported 15% reduction in dispensed volume over 30 cycles.</p>
                                    </div>
                                    
                                    <div className="relative pl-6">
                                        <span className="absolute -left-3 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 ring-4 ring-white">
                                            <Activity size={14} className="text-blue-600" />
                                        </span>
                                        <h3 className="text-sm font-semibold text-gray-900">AI Hypothesis Generated</h3>
                                        <p className="mt-1 text-sm text-gray-600">System generated hypothesis of nozzle restriction based on pressure-volume curves matching known blockage profiles.</p>
                                    </div>
                                    
                                    <div className="relative pl-6">
                                        <span className="absolute -left-3 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-green-100 ring-4 ring-white">
                                            <CheckCircle2 size={14} className="text-green-600" />
                                        </span>
                                        <h3 className="text-sm font-semibold text-gray-900">Resolution</h3>
                                        <p className="mt-1 text-sm text-gray-600">Nozzle #4 replaced and purged. Test runs showed volume returned to nominal 12.5mg target.</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-6">
                            {/* Metadata */}
                            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                                <h3 className="text-sm font-semibold text-gray-900 mb-4">Report Details</h3>
                                <dl className="space-y-4">
                                    <div>
                                        <dt className="text-xs font-medium text-gray-500">Related Case</dt>
                                        <dd className="mt-1 text-sm font-medium text-[#6d5dfc]">DSP-2026-0184</dd>
                                    </div>
                                    <div>
                                        <dt className="text-xs font-medium text-gray-500">Equipment</dt>
                                        <dd className="mt-1 text-sm text-gray-900">Dispenser Unit A-4</dd>
                                    </div>
                                    <div>
                                        <dt className="text-xs font-medium text-gray-500">Material</dt>
                                        <dd className="mt-1 text-sm text-gray-900">Adhesive Loctite 3525</dd>
                                    </div>
                                    <div>
                                        <dt className="text-xs font-medium text-gray-500">Prepared By</dt>
                                        <dd className="mt-1 text-sm text-gray-900 flex items-center gap-2">
                                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#eeebff] text-[10px] font-semibold text-[#5848e8]">
                                                SM
                                            </div>
                                            Sarah Mitchell
                                        </dd>
                                    </div>
                                </dl>
                            </div>

                            {/* Recommendations */}
                            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6">
                                <div className="flex items-center gap-2 mb-4">
                                    <Settings size={18} className="text-gray-700" />
                                    <h3 className="text-sm font-semibold text-gray-900">Preventative Actions</h3>
                                </div>
                                <ul className="space-y-3">
                                    <li className="flex items-start gap-2 text-sm text-gray-700">
                                        <div className="mt-0.5 h-1.5 w-1.5 rounded-full bg-[#6d5dfc] flex-shrink-0" />
                                        Increase purge frequency to every 2 hours during continuous operation.
                                    </li>
                                    <li className="flex items-start gap-2 text-sm text-gray-700">
                                        <div className="mt-0.5 h-1.5 w-1.5 rounded-full bg-[#6d5dfc] flex-shrink-0" />
                                        Review material pot life limits at ambient temperature &gt; 25°C.
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
