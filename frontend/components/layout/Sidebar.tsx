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
    Shield,
    Stethoscope,
    Radio,
    X,
} from "lucide-react";
import { useAuth } from "@/components/providers/AuthContext";

interface SidebarProps {
    isMobileOpen?: boolean;
    onCloseMobile?: () => void;
}

const navigation = [
    {
        name: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
    },
    {
        name: "Telemetry",
        href: "/telemetry",
        icon: Radio,
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

export default function Sidebar({ isMobileOpen = false, onCloseMobile }: SidebarProps) {
    const pathname = usePathname();
    const { user, isAdmin } = useAuth();

    const handleLinkClick = () => {
        if (onCloseMobile) {
            onCloseMobile();
        }
    };

    return (
        <aside
            className={`fixed left-0 top-0 z-50 flex h-screen w-72 lg:w-64 flex-col border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-[#111827] shadow-xl lg:shadow-none transition-all duration-200 ease-in-out ${
                isMobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
            }`}
        >
            {/* Brand */}
            <div className="flex h-20 items-center justify-between border-b border-gray-100 dark:border-gray-800 px-6">
                <Link
                    href="/dashboard"
                    onClick={handleLinkClick}
                    className="flex items-center gap-3"
                >
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#6d5dfc] text-white shadow-sm shadow-indigo-200">
                        <Activity size={21} />
                    </div>

                    <div>
                        <h1 className="text-lg font-bold tracking-tight text-gray-900 dark:text-gray-100">
                            Dispense Lens
                        </h1>

                        <p className="text-[11px] text-gray-500 dark:text-gray-400 font-medium">
                            Defect Intelligence
                        </p>
                    </div>
                </Link>

                {/* Mobile close button */}
                <button
                    onClick={onCloseMobile}
                    aria-label="Close navigation menu"
                    className="flex lg:hidden h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-600 dark:hover:text-gray-200"
                >
                    <X size={18} />
                </button>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1 px-3 py-5 overflow-y-auto">
                <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
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
                            onClick={handleLinkClick}
                            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                                isActive
                                    ? "bg-[#eeebff] dark:bg-[#5848e8]/20 text-[#5848e8] dark:text-[#a59bff]"
                                    : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/60 hover:text-gray-900 dark:hover:text-gray-100"
                            }`}
                        >
                            <Icon size={18} strokeWidth={1.8} />
                            {item.name}
                        </Link>
                    );
                })}

                {/* Administration section - shown for Admins */}
                {(isAdmin || user?.role === "admin") && (
                    <div className="pt-4 mt-4 border-t border-gray-100 dark:border-gray-800">
                        <div className="flex items-center justify-between px-3 pb-2">
                            <p className="text-[11px] font-semibold uppercase tracking-wider text-[#6d5dfc]">
                                Management
                            </p>
                            <span className="rounded bg-[#eeebff] dark:bg-[#5848e8]/30 px-1.5 py-0.5 text-[10px] font-bold text-[#5848e8] dark:text-[#a59bff]">
                                ADMIN
                            </span>
                        </div>
                        <Link
                            href="/admin"
                            onClick={handleLinkClick}
                            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                                pathname === "/admin" || pathname.startsWith("/admin/")
                                    ? "bg-[#5848e8] text-white shadow-sm shadow-indigo-200"
                                    : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800/60 hover:text-gray-900 dark:hover:text-gray-100"
                            }`}
                        >
                            <Shield
                                size={18}
                                strokeWidth={1.8}
                                className={pathname.startsWith("/admin") ? "text-white" : "text-[#6d5dfc]"}
                            />
                            Admin Console
                        </Link>
                    </div>
                )}
            </nav>

            {/* Bottom */}
            <div className="border-t border-gray-100 dark:border-gray-800 p-3">
                <Link
                    href="/settings"
                    onClick={handleLinkClick}
                    className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                        pathname === "/settings"
                            ? "bg-[#eeebff] dark:bg-[#5848e8]/20 text-[#5848e8] dark:text-[#a59bff]"
                            : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/60 hover:text-gray-900 dark:hover:text-gray-100"
                    }`}
                >
                    <Settings size={18} strokeWidth={1.8} />
                    Settings
                </Link>
            </div>
        </aside>
    );
}