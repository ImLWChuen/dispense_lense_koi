import React from "react";

export default function DashboardLoading() {
    return (
        <div className="min-h-[calc(100vh-5rem)] p-4 sm:p-6 lg:p-8 animate-pulse">
            <div className="mx-auto max-w-7xl space-y-6">
                {/* Header Skeleton */}
                <div className="flex flex-col gap-2">
                    <div className="h-4 w-32 rounded-md bg-gray-200" />
                    <div className="h-8 w-64 rounded-lg bg-gray-300" />
                    <div className="h-4 w-96 rounded-md bg-gray-200" />
                </div>

                {/* KPI Grid Skeleton */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="h-28 rounded-2xl border border-gray-100 bg-white p-5 shadow-xs">
                            <div className="flex items-center justify-between">
                                <div className="h-4 w-24 rounded bg-gray-200" />
                                <div className="h-8 w-8 rounded-lg bg-gray-100" />
                            </div>
                            <div className="mt-4 h-7 w-16 rounded bg-gray-300" />
                        </div>
                    ))}
                </div>

                {/* Main Content Area Skeleton */}
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    <div className="h-80 rounded-2xl border border-gray-100 bg-white p-6 shadow-xs lg:col-span-2">
                        <div className="h-5 w-40 rounded bg-gray-200" />
                        <div className="mt-6 h-56 w-full rounded-xl bg-gray-100" />
                    </div>
                    <div className="h-80 rounded-2xl border border-gray-100 bg-white p-6 shadow-xs">
                        <div className="h-5 w-32 rounded bg-gray-200" />
                        <div className="mt-6 space-y-3">
                            <div className="h-10 w-full rounded-lg bg-gray-100" />
                            <div className="h-10 w-full rounded-lg bg-gray-100" />
                            <div className="h-10 w-full rounded-lg bg-gray-100" />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
