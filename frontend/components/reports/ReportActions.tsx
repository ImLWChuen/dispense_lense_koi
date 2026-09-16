import { Download, Printer, Share2 } from "lucide-react";

export default function ReportActions() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-900">
                Report Actions
            </h2>

            <div className="mt-4 space-y-2">
                <button className="flex w-full items-center gap-3 rounded-xl border border-gray-200 p-3 text-left transition hover:bg-gray-50">
                    <Download size={16} className="text-gray-500" />

                    <div>
                        <p className="text-sm font-medium text-gray-800">
                            Download PDF
                        </p>

                        <p className="text-[10px] text-gray-500">
                            Save report as PDF document
                        </p>
                    </div>
                </button>

                <button className="flex w-full items-center gap-3 rounded-xl border border-gray-200 p-3 text-left transition hover:bg-gray-50">
                    <Printer size={16} className="text-gray-500" />

                    <div>
                        <p className="text-sm font-medium text-gray-800">
                            Print Report
                        </p>

                        <p className="text-[10px] text-gray-500">
                            Send to printer
                        </p>
                    </div>
                </button>

                <button className="flex w-full items-center gap-3 rounded-xl border border-gray-200 p-3 text-left transition hover:bg-gray-50">
                    <Share2 size={16} className="text-gray-500" />

                    <div>
                        <p className="text-sm font-medium text-gray-800">
                            Share Report
                        </p>

                        <p className="text-[10px] text-gray-500">
                            Email or link to team members
                        </p>
                    </div>
                </button>
            </div>
        </div>
    );
}
