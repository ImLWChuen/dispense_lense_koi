"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
    Bell,
    Search,
    LogOut,
    X,
    CheckCircle2,
    AlertTriangle,
    PlusCircle,
    Info,
    Check,
    Trash2,
    ArrowRight,
    FileText,
    BookOpen,
    ExternalLink,
    Shield,
    Menu,
    Command,
} from "lucide-react";
import { useAuth } from "@/components/providers/AuthContext";
import { casesApi } from "@/lib/api/cases";
import { analyticsApi } from "@/lib/api/analytics";
import { DurableCaseResponse } from "@/types/api";
import { notificationService, AppNotification } from "@/lib/notifications";

interface HeaderProps {
    onOpenMobileMenu?: () => void;
    onOpenCommandPalette?: () => void;
}

// Reference knowledge base items for global search fallback
const KB_ITEMS = [
    { type: "Defect", tab: "Defects", code: "D01", name: "Too Little Material", desc: "Dispensed volume consistently less than target amount." },
    { type: "Defect", tab: "Defects", code: "D02", name: "Too Much Material", desc: "Dispensed volume consistently more than target amount." },
    { type: "Defect", tab: "Defects", code: "D03", name: "Inconsistent Size", desc: "Dispensed volume varies from shot to shot." },
    { type: "Defect", tab: "Defects", code: "D04", name: "Missing Dots", desc: "One or more locations receive no material." },
    { type: "Defect", tab: "Defects", code: "D05", name: "Spreading", desc: "Material spreads excessively on the substrate." },
    { type: "Defect", tab: "Defects", code: "D06", name: "Bubbles / Abnormal Shape", desc: "Deposits contain trapped air or abnormal shape." },
    { type: "Root Cause", tab: "Causes", code: "RC01", name: "Nozzle Restriction", desc: "Partial or complete blockage of dispensing nozzle." },
    { type: "Root Cause", tab: "Causes", code: "RC02", name: "Air / Supply Issue", desc: "Trapped air or inconsistent air pressure." },
    { type: "Root Cause", tab: "Causes", code: "RC03", name: "Material Condition", desc: "Material viscosity outside acceptable range." },
    { type: "Root Cause", tab: "Causes", code: "RC04", name: "Pressure Instability", desc: "Inconsistent dispensing pressure from supply." },
    { type: "Action", tab: "Actions", code: "ACT01", name: "Inspect Nozzle", desc: "Examine tip under microscope for clogs." },
    { type: "Action", tab: "Actions", code: "ACT02", name: "Check Material Supply", desc: "Verify syringe level and degassing." },
    { type: "Action", tab: "Actions", code: "ACT03", name: "Perform Test Shots", desc: "Dispense 10 sample dots and measure weight." },
];

function formatTimeAgo(dateString: string): string {
    const diff = Math.floor((Date.now() - new Date(dateString).getTime()) / 1000);
    if (diff < 60) return "Just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

export default function Header({ onOpenMobileMenu, onOpenCommandPalette }: HeaderProps) {
    const { user, logout } = useAuth();
    const router = useRouter();

    // User details
    const firstName = user?.first_name || "Guest";
    const lastName = user?.last_name || "";
    const initials = (firstName[0] || "") + (lastName[0] || "");
    const role = user?.role ? user.role.toUpperCase() : (user ? "TECHNICIAN" : "");
    const isAdmin = user?.role === "admin";

    // Search state
    const [searchQuery, setSearchQuery] = useState("");
    const [isSearchOpen, setIsSearchOpen] = useState(false);
    const [cases, setCases] = useState<DurableCaseResponse[]>([]);
    const searchRef = useRef<HTMLDivElement>(null);

    // Notification state
    const [notifications, setNotifications] = useState<AppNotification[]>([]);
    const [isNotifOpen, setIsNotifOpen] = useState(false);
    const [notifFilter, setNotifFilter] = useState<"all" | "unread">("all");
    const notifRef = useRef<HTMLDivElement>(null);

    // Fetch initial cases for search cache
    useEffect(() => {
        casesApi.listCases().then(setCases).catch((err) => console.warn("Search cases cache error:", err));
    }, []);

    // Load and sync notifications
    useEffect(() => {
        const loadNotifs = () => {
            setNotifications(notificationService.getNotifications());
        };

        loadNotifs();

        const handleNotifUpdate = () => {
            loadNotifs();
        };

        window.addEventListener("dispenselens_notifications_updated", handleNotifUpdate);

        // Subscribe to live SSE events from backend
        const unsubscribe = analyticsApi.subscribeToEvents((event) => {
            if (!event || !event.event_type) return;

            let title = "System Notification";
            let message = "A new system update occurred.";
            let type: AppNotification["type"] = "SYSTEM";
            let link = "/dashboard";

            if (event.event_type === "CASE_CREATED") {
                type = "CASE_CREATED";
                title = "New Case Created";
                message = `Case ${event.case_id ? event.case_id.split("-")[0] : ""} registered with defect: ${event.defect_type || "Unknown"}`;
                link = event.case_id ? `/diagnosis/${event.case_id}` : "/cases";
            } else if (event.event_type === "CAUSE_CONFIRMED") {
                type = "CAUSE_CONFIRMED";
                title = "Root Cause Confirmed";
                message = `Cause confirmed for case ${event.case_id ? event.case_id.split("-")[0] : ""}.`;
                link = event.case_id ? `/diagnosis/${event.case_id}` : "/cases";
            } else if (event.event_type === "CASE_COMPLETED") {
                type = "CASE_COMPLETED";
                title = "Case Resolved";
                message = `Case ${event.case_id ? event.case_id.split("-")[0] : ""} has been verified and resolved.`;
                link = event.case_id ? `/diagnosis/${event.case_id}` : "/cases";
            }

            notificationService.addNotification({
                type,
                title,
                message,
                link,
            });
        });

        return () => {
            window.removeEventListener("dispenselens_notifications_updated", handleNotifUpdate);
            unsubscribe();
        };
    }, []);

    // Click outside listener for notifications dropdown
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
                setIsNotifOpen(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Notification actions
    const unreadCount = notifications.filter((n) => !n.read).length;
    const filteredNotifications = notifFilter === "unread" ? notifications.filter((n) => !n.read) : notifications;

    const handleNotificationClick = (notif: AppNotification) => {
        notificationService.markAsRead(notif.id);
        setIsNotifOpen(false);
        if (notif.link) {
            if (notif.link.startsWith("/diagnosis/")) {
                const targetCaseId = notif.link.replace("/diagnosis/", "").split("/")[0];
                if (cases.length > 0) {
                    const exists = cases.some((c) => c.case_id === targetCaseId);
                    if (!exists) {
                        router.push(`/cases?search=${targetCaseId.slice(0, 8)}`);
                        return;
                    }
                }
            }
            router.push(notif.link);
        }
    };

    const getNotifIcon = (type: AppNotification["type"]) => {
        switch (type) {
            case "CASE_COMPLETED":
                return <CheckCircle2 size={16} className="text-emerald-600" />;
            case "CAUSE_CONFIRMED":
                return <AlertTriangle size={16} className="text-amber-600" />;
            case "CASE_CREATED":
                return <PlusCircle size={16} className="text-[#6d5dfc]" />;
            default:
                return <Info size={16} className="text-blue-600" />;
        }
    };

    const getNotifBg = (type: AppNotification["type"]) => {
        switch (type) {
            case "CASE_COMPLETED":
                return "bg-emerald-50";
            case "CAUSE_CONFIRMED":
                return "bg-amber-50";
            case "CASE_CREATED":
                return "bg-[#eeebff]";
            default:
                return "bg-blue-50";
        }
    };

    return (
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-gray-200 bg-white/90 px-4 sm:px-6 lg:px-8 backdrop-blur">
            {/* Left side: Hamburger (mobile) + Global Search Trigger */}
            <div className="flex items-center gap-3">
                {/* Mobile Drawer Trigger */}
                <button
                    onClick={onOpenMobileMenu}
                    aria-label="Open navigation menu"
                    className="flex lg:hidden h-10 w-10 items-center justify-center rounded-xl text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition"
                >
                    <Menu size={20} />
                </button>

                {/* Global Command Palette Trigger Button */}
                <button
                    onClick={onOpenCommandPalette}
                    className="group relative flex h-10 w-52 sm:w-72 md:w-80 lg:w-96 items-center justify-between rounded-xl border border-gray-200 bg-gray-50 px-3.5 text-sm text-gray-400 transition hover:border-[#6d5dfc]/50 hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#6d5dfc]/15"
                >
                    <div className="flex items-center gap-2.5 truncate">
                        <Search size={17} className="text-gray-400 group-hover:text-[#6d5dfc] transition-colors" />
                        <span className="truncate text-gray-400 group-hover:text-gray-600">
                            Search cases, defects, SOPs...
                        </span>
                    </div>

                    <div className="hidden sm:flex items-center gap-1 shrink-0">
                        <kbd className="flex items-center gap-0.5 rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-gray-400 shadow-2xs">
                            <span className="text-[11px]">⌘</span>K
                        </kbd>
                    </div>
                </button>
            </div>

            {/* Right side: Notifications + User Profile */}
            <div className="flex items-center gap-3 sm:gap-4">
                {/* Notification Dropdown Container */}
                <div ref={notifRef} className="relative">
                    <button
                        onClick={() => setIsNotifOpen(!isNotifOpen)}
                        className={`relative flex h-10 w-10 items-center justify-center rounded-xl text-gray-500 transition ${
                            isNotifOpen ? "bg-gray-100 text-[#6d5dfc]" : "hover:bg-gray-100 hover:text-gray-700"
                        }`}
                        aria-label="View notifications"
                    >
                        <Bell size={19} />
                        {unreadCount > 0 && (
                            <span className="absolute right-2 top-2 flex h-2.5 w-2.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
                            </span>
                        )}
                    </button>

                    {/* Notification Panel */}
                    {isNotifOpen && (
                        <div className="absolute right-0 top-12 z-50 w-80 sm:w-96 max-w-[calc(100vw-2rem)] rounded-2xl border border-gray-200 bg-white shadow-2xl animate-in fade-in-50 zoom-in-95">
                            {/* Panel Header */}
                            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
                                <div className="flex items-center gap-2">
                                    <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
                                    {unreadCount > 0 && (
                                        <span className="rounded-full bg-[#eeebff] px-2 py-0.5 text-[11px] font-bold text-[#5848e8]">
                                            {unreadCount} new
                                        </span>
                                    )}
                                </div>

                                <div className="flex items-center gap-2">
                                    {unreadCount > 0 && (
                                        <button
                                            onClick={() => notificationService.markAllAsRead()}
                                            className="text-xs text-gray-500 hover:text-[#6d5dfc] transition"
                                            title="Mark all as read"
                                        >
                                            Mark all read
                                        </button>
                                    )}
                                    <button
                                        onClick={() => setIsNotifOpen(false)}
                                        className="text-gray-400 hover:text-gray-600 rounded-lg p-1"
                                    >
                                        <X size={16} />
                                    </button>
                                </div>
                            </div>

                            {/* Filter Tabs */}
                            <div className="flex border-b border-gray-100 px-4 pt-2 gap-4 text-xs font-medium">
                                <button
                                    onClick={() => setNotifFilter("all")}
                                    className={`pb-2 border-b-2 transition ${
                                        notifFilter === "all"
                                            ? "border-[#6d5dfc] text-[#5848e8]"
                                            : "border-transparent text-gray-400 hover:text-gray-600"
                                    }`}
                                >
                                    All ({notifications.length})
                                </button>
                                <button
                                    onClick={() => setNotifFilter("unread")}
                                    className={`pb-2 border-b-2 transition ${
                                        notifFilter === "unread"
                                            ? "border-[#6d5dfc] text-[#5848e8]"
                                            : "border-transparent text-gray-400 hover:text-gray-600"
                                    }`}
                                >
                                    Unread ({unreadCount})
                                </button>
                            </div>

                            {/* Notification List */}
                            <div className="max-h-[360px] overflow-y-auto divide-y divide-gray-50">
                                {filteredNotifications.length > 0 ? (
                                    filteredNotifications.map((notif) => (
                                        <div
                                            key={notif.id}
                                            onClick={() => handleNotificationClick(notif)}
                                            className={`flex items-start gap-3 p-3.5 cursor-pointer transition hover:bg-gray-50 ${
                                                !notif.read ? "bg-[#eeebff]/20" : ""
                                            }`}
                                        >
                                            <div
                                                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${getNotifBg(
                                                    notif.type
                                                )}`}
                                            >
                                                {getNotifIcon(notif.type)}
                                            </div>

                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between">
                                                    <p className={`text-xs font-semibold truncate ${!notif.read ? "text-gray-900" : "text-gray-600"}`}>
                                                        {notif.title}
                                                    </p>
                                                    <span className="text-[10px] text-gray-400 shrink-0 ml-1">
                                                        {formatTimeAgo(notif.timestamp)}
                                                    </span>
                                                </div>

                                                <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                                                    {notif.message}
                                                </p>
                                            </div>

                                            {!notif.read && (
                                                <span className="h-2 w-2 shrink-0 rounded-full bg-[#6d5dfc] mt-1.5" />
                                            )}
                                        </div>
                                    ))
                                ) : (
                                    <div className="py-8 text-center">
                                        <Bell size={28} className="mx-auto text-gray-300 mb-2" />
                                        <p className="text-xs font-semibold text-gray-700">No notifications</p>
                                        <p className="text-[11px] text-gray-400 mt-0.5">
                                            {notifFilter === "unread"
                                                ? "You've read all your notifications!"
                                                : "No updates at this time."}
                                        </p>
                                    </div>
                                )}
                            </div>

                            {/* Panel Footer */}
                            <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-2.5 text-center">
                                <Link
                                    href="/cases"
                                    onClick={() => setIsNotifOpen(false)}
                                    className="text-xs font-medium text-[#6d5dfc] hover:underline inline-flex items-center gap-1"
                                >
                                    View all diagnostic cases <ArrowRight size={11} />
                                </Link>
                            </div>
                        </div>
                    )}
                </div>

                {/* User Profile */}
                <div className="flex items-center gap-2.5 sm:gap-3 border-l border-gray-200 pl-3 sm:pl-5">
                    {isAdmin && (
                        <Link
                            href="/admin"
                            className="hidden md:flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-[#eeebff] px-2.5 py-1 text-xs font-semibold text-[#5848e8] hover:bg-[#5848e8] hover:text-white transition shadow-xs"
                            title="Open Admin Oversight Console"
                        >
                            <Shield size={13} />
                            Admin
                        </Link>
                    )}

                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#eeebff] text-sm font-semibold uppercase text-[#5848e8]">
                        {initials}
                    </div>

                    <div className="hidden sm:block">
                        <p className="text-sm font-semibold text-gray-900 leading-tight">
                            {firstName} {lastName}
                        </p>

                        <div className="flex items-center gap-1.5 mt-0.5">
                            <span
                                className={`inline-block rounded-md px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider ${
                                    role === "ADMIN"
                                        ? "bg-purple-100 text-purple-700 border border-purple-200"
                                        : role === "ENGINEER"
                                        ? "bg-blue-100 text-blue-700 border border-blue-200"
                                        : "bg-emerald-100 text-emerald-700 border border-emerald-200"
                                }`}
                            >
                                {role}
                            </span>
                        </div>
                    </div>

                    {user && (
                        <button
                            onClick={logout}
                            className="ml-1 sm:ml-2 rounded-xl p-2 text-gray-500 hover:bg-gray-100 hover:text-red-500 transition-colors"
                            title="Sign out"
                        >
                            <LogOut size={18} />
                        </button>
                    )}
                </div>
            </div>
        </header>
    );
}
