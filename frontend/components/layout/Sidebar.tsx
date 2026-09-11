"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Activity,
    BarChart3,
    BookOpen,
    ClipboardCheck,
    FileText,
    LayoutDashboard,
    Settings,
    Stethoscope,
} from "lucide-react";

const navigation = [
    {
        name: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
    },
    {
        name: "New Diagnosis",
        href: "/diagnosis/new",
        icon: Stethoscope,
    },
    {
        name: "Cases",
        href: "/cases",
        icon: ClipboardCheck,
    },
    {
        name: "Analytics",
        href: "/analytics",
        icon: BarChart3,
    },
    {
        name: "Knowledge Base",
        href: "/knowledge-base",
        icon: BookOpen,
    },
    {
        name: "Reports",
        href: "/reports",
        icon: FileText,
    },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r border-gray-200 bg-white">
            {/* Brand */}
            <div className="flex h-20 items-center border-b border-gray-100 px-6">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#6d5dfc] text-white">
                        <Activity size={21} />
                    </div>

                    <div>
                        <h1 className="text-lg font-bold tracking-tight">
                            DispenseIQ
                        </h1>

                        <p className="text-[11px] text-gray-500">
                            Defect Intelligence
                        </p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1 px-3 py-5">
                <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                    Workspace
                </p>

                {navigation.map((item) => {
                    const Icon = item.icon;

                    const isActive =
                        pathname === item.href ||
                        pathname.startsWith(`${item.href}/`);

                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                                isActive
                                    ? "bg-[#eeebff] text-[#5848e8]"
                                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                            }`}
                        >
                            <Icon size={18} strokeWidth={1.8} />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom */}
            <div className="border-t border-gray-100 p-3">
                <Link
                    href="/settings"
                    className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50"
                >
                    <Settings size={18} strokeWidth={1.8} />
                    Settings
                </Link>
            </div>
        </aside>
    );
}