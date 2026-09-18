import Link from "next/link";
import { ArrowRight, SearchX } from "lucide-react";

export default function SimilarCases() {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Similar Cases
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Historical cases with similar symptoms
            </p>

            <div className="mt-5 flex flex-col items-center justify-center space-y-2 py-6 text-gray-400">
                <SearchX size={32} />
                <p className="text-sm">No similar cases found</p>
                <p className="text-xs">Vector similarity search is pending implementation.</p>
            </div>
        </div>
    );
}
