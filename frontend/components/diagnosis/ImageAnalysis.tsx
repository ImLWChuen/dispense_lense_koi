import { Image as ImageIcon, Scan, CheckCircle2 } from "lucide-react";

export default function ImageAnalysis() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Scan size={20} />
                </div>

                <div>
                    <h2 className="text-base font-semibold text-gray-900">
                        Image Analysis
                    </h2>

                    <p className="text-xs text-gray-500">
                        Visual defect assessment
                    </p>
                </div>
            </div>

            {/* Mock image preview */}
            <div className="mt-5 flex aspect-[16/10] items-center justify-center rounded-xl bg-gray-100">
                <div className="text-center">
                    <ImageIcon size={40} className="mx-auto text-gray-300" />

                    <p className="mt-2 text-xs text-gray-400">
                        Defect image preview
                    </p>
                </div>
            </div>

            {/* Mock analysis results */}
            <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                    <div className="flex items-center gap-2">
                        <CheckCircle2
                            size={13}
                            className="text-green-600"
                        />

                        <span className="text-xs font-medium text-gray-700">
                            Deposit Shape
                        </span>
                    </div>

                    <span className="text-xs text-gray-500">
                        Undersized, flat profile
                    </span>
                </div>

                <div className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                    <div className="flex items-center gap-2">
                        <CheckCircle2
                            size={13}
                            className="text-green-600"
                        />

                        <span className="text-xs font-medium text-gray-700">
                            Deposit Diameter
                        </span>
                    </div>

                    <span className="text-xs text-gray-500">
                        0.8mm (target: 1.2mm)
                    </span>
                </div>

                <div className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                    <div className="flex items-center gap-2">
                        <CheckCircle2
                            size={13}
                            className="text-green-600"
                        />

                        <span className="text-xs font-medium text-gray-700">
                            Surface Quality
                        </span>
                    </div>

                    <span className="text-xs text-gray-500">
                        Smooth, no bubbles
                    </span>
                </div>
            </div>

            <p className="mt-3 text-[10px] text-gray-400">
                Image analysis results are for reference only. Engineer
                verification is required.
            </p>
        </div>
    );
}
