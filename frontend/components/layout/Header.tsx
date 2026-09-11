"use client";

import { Bell, Search } from "lucide-react";

export default function Header() {
    return (
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-gray-200 bg-white/90 px-8 backdrop-blur">
            {/* Search */}
            <div className="relative w-[360px]">
                <Search
                    size={18}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                />

                <input
                    type="text"
                    placeholder="Search cases, diagnoses..."
                    className="h-10 w-full rounded-xl border border-gray-200 bg-gray-50 pl-10 pr-4 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                />
            </div>

            {/* Right side */}
            <div className="flex items-center gap-5">
                <button className="relative rounded-xl p-2 text-gray-500 hover:bg-gray-100">
                    <Bell size={19} />

                    <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
                </button>

                <div className="flex items-center gap-3 border-l border-gray-200 pl-5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#eeebff] text-sm font-semibold text-[#5848e8]">
                        SM
                    </div>

                    <div>
                        <p className="text-sm font-semibold text-gray-900">
                            Sarah Mitchell
                        </p>

                        <p className="text-xs text-gray-500">
                            Manufacturing Engineer
                        </p>
                    </div>
                </div>
            </div>
        </header>
    );
}