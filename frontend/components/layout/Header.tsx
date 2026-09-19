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
} from "lucide-react";
import { useAuth } from "@/components/providers/AuthContext";
import { casesApi } from "@/lib/api/cases";
import { analyticsApi } from "@/lib/api/analytics";
import { DurableCaseResponse } from "@/types/api";
import { notificationService, AppNotification } from "@/lib/notifications";

// Reference knowledge base items for global search
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

export default function Header() {
    const { user, logout } = useAuth();
    const router = useRouter();

    // User details
    const firstName = user?.first_name || "Guest";
    const lastName = user?.last_name || "";
    const initials = (firstName[0] || "") + (lastName[0] || "");
    const role = user ? "User" : "";

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

        window.addEventListener("dispenseiq_notifications_updated", handleNotifUpdate);

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
            window.removeEventListener("dispenseiq_notifications_updated", handleNotifUpdate);
            unsubscribe();
        };
    }, []);

    // Click outside listener for search and notifications dropdowns
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
                setIsSearchOpen(false);
            }
            if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
                setIsNotifOpen(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Search matches calculation
    const query = searchQuery.trim().toLowerCase();
    const matchingCases = query
        ? cases.filter((c) =>
              c.case_id.toLowerCase().includes(query) ||
              (c.defect_name && c.defect_name.toLowerCase().includes(query)) ||
              (c.defect_code && c.defect_code.toLowerCase().includes(query)) ||
              (c.machine_context?.equipment && c.machine_context.equipment.toLowerCase().includes(query)) ||
              c.issue_condition.toLowerCase().includes(query)
          ).slice(0, 4)
        : [];

    const matchingKB = query
        ? KB_ITEMS.filter((item) =>
              item.name.toLowerCase().includes(query) ||
              item.code.toLowerCase().includes(query) ||
              item.desc.toLowerCase().includes(query)
          ).slice(0, 3)
        : [];

    const hasSearchResults = matchingCases.length > 0 || matchingKB.length > 0;

    const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            setIsSearchOpen(false);
            if (matchingCases.length === 1) {
                router.push(`/diagnosis/${matchingCases[0].case_id}`);
            } else {
                router.push(`/cases?search=${encodeURIComponent(searchQuery)}`);
            }
        } else if (e.key === "Escape") {
            setIsSearchOpen(false);
        }
    };

    const handleClearSearch = () => {
        setSearchQuery("");
        setIsSearchOpen(false);
    };

    // Notification actions
    const unreadCount = notifications.filter((n) => !n.read).length;
    const filteredNotifications = notifFilter === "unread" ? notifications.filter((n) => !n.read) : notifications;

    const handleNotificationClick = (notif: AppNotification) => {
        notificationService.markAsRead(notif.id);
        setIsNotifOpen(false);
        if (notif.link) {
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
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-gray-200 bg-white/90 px-8 backdrop-blur">
            {/* Global Search Bar */}
            <div ref={searchRef} className="relative w-[380px]">
                <Search
                    size={18}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
                />

                <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setIsSearchOpen(true);
                    }}
                    onFocus={() => setIsSearchOpen(true)}
                    onKeyDown={handleSearchKeyDown}
                    placeholder="Search cases, diagnoses, defects..."
                    className="h-10 w-full rounded-xl border border-gray-200 bg-gray-50 pl-10 pr-9 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white focus:ring-2 focus:ring-[#6d5dfc]/10"
                />

                {searchQuery && (
                    <button
                        onClick={handleClearSearch}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                        <X size={15} />
                    </button>
                )}

                {/* Search Autocomplete Dropdown */}
                {isSearchOpen && query && (
                    <div className="absolute left-0 top-12 w-full max-h-[440px] overflow-y-auto rounded-2xl border border-gray-200 bg-white p-2 shadow-xl animate-in fade-in-50 zoom-in-95 z-50">
                        {hasSearchResults ? (
                            <>
                                {/* Matching Cases */}
                                {matchingCases.length > 0 && (
                                    <div className="mb-2">
                                        <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                                            Cases
                                        </p>
                                        {matchingCases.map((c) => (
                                            <button
                                                key={c.case_id}
                                                onClick={() => {
                                                    setIsSearchOpen(false);
                                                    router.push(`/diagnosis/${c.case_id}`);
                                                }}
                                                className="w-full flex items-center justify-between rounded-xl px-3 py-2 text-left transition hover:bg-gray-50 group"
                                            >
                                                <div className="flex items-center gap-2.5 truncate">
                                                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#eeebff] text-[#5848e8]">
                                                        <FileText size={14} />
                                                    </div>
                                                    <div className="truncate">
                                                        <p className="text-xs font-semibold text-gray-900 group-hover:text-[#6d5dfc] truncate">
                                                            {c.defect_name || c.defect_code || "Unknown Defect"}
                                                        </p>
                                                        <p className="text-[11px] text-gray-500 font-mono">
                                                            #{c.case_id.split("-")[0]} • {c.machine_context?.equipment || "Line"}
                                                        </p>
                                                    </div>
                                                </div>
                                                <span className="shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-md bg-gray-100 text-gray-600">
                                                    {c.issue_condition === "RESOLVED" ? "Resolved" : "Active"}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {/* Matching Knowledge Base */}
                                {matchingKB.length > 0 && (
                                    <div className="mb-2 border-t border-gray-100 pt-2">
                                        <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                                            Knowledge Base
                                        </p>
                                        {matchingKB.map((kb) => (
                                            <button
                                                key={kb.code}
                                                onClick={() => {
                                                    setIsSearchOpen(false);
                                                    router.push(`/knowledge-base?tab=${kb.tab}&search=${encodeURIComponent(kb.name)}`);
                                                }}
                                                className="w-full flex items-center justify-between rounded-xl px-3 py-2 text-left transition hover:bg-gray-50 group"
                                            >
                                                <div className="flex items-center gap-2.5 truncate">
                                                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                                                        <BookOpen size={14} />
                                                    </div>
                                                    <div className="truncate">
                                                        <p className="text-xs font-semibold text-gray-900 group-hover:text-[#6d5dfc] truncate">
                                                            {kb.name}
                                                        </p>
                                                        <p className="text-[11px] text-gray-500 truncate">
                                                            {kb.desc}
                                                        </p>
                                                    </div>
                                                </div>
                                                <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-50 text-amber-700">
                                                    {kb.type}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {/* Quick Action Link */}
                                <div className="border-t border-gray-100 pt-2 px-1">
                                    <button
                                        onClick={() => {
                                            setIsSearchOpen(false);
                                            router.push(`/cases?search=${encodeURIComponent(searchQuery)}`);
                                        }}
                                        className="w-full flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2 text-xs font-medium text-[#6d5dfc] hover:bg-[#eeebff] transition"
                                    >
                                        <span>View all matching cases for &quot;{searchQuery}&quot;</span>
                                        <ArrowRight size={13} />
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="py-6 text-center">
                                <p className="text-xs font-medium text-gray-600">No results found for &quot;{searchQuery}&quot;</p>
                                <p className="text-[11px] text-gray-400 mt-1">Try searching by defect type, case ID, or equipment line.</p>
                                <button
                                    onClick={() => {
                                        setIsSearchOpen(false);
                                        router.push(`/cases?search=${encodeURIComponent(searchQuery)}`);
                                    }}
                                    className="mt-3 inline-flex items-center gap-1.5 text-xs text-[#6d5dfc] hover:underline"
                                >
                                    Search in Cases list <ArrowRight size={12} />
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Right side: Notifications & User Profile */}
            <div className="flex items-center gap-5">
                {/* Notification Bell with Dropdown */}
                <div ref={notifRef} className="relative">
                    <button
                        onClick={() => setIsNotifOpen(!isNotifOpen)}
                        className={`relative rounded-xl p-2.5 transition ${
                            isNotifOpen ? "bg-gray-100 text-[#6d5dfc]" : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                        }`}
                        title="Notifications"
                        aria-label="Open notifications"
                    >
                        <Bell size={19} />
                        {unreadCount > 0 && (
                            <span className="absolute right-1.5 top-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white ring-2 ring-white">
                                {unreadCount > 9 ? "9+" : unreadCount}
                            </span>
                        )}
                    </button>

                    {/* Notification Dropdown Panel */}
                    {isNotifOpen && (
                        <div className="absolute right-0 top-12 w-[360px] rounded-2xl border border-gray-200 bg-white shadow-2xl animate-in fade-in-50 zoom-in-95 z-50 overflow-hidden">
                            {/* Panel Header */}
                            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 bg-gray-50/70">
                                <div className="flex items-center gap-2">
                                    <h3 className="text-sm font-bold text-gray-900">Notifications</h3>
                                    {unreadCount > 0 && (
                                        <span className="rounded-full bg-[#eeebff] px-2 py-0.5 text-[11px] font-semibold text-[#5848e8]">
                                            {unreadCount} new
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-1">
                                    {unreadCount > 0 && (
                                        <button
                                            onClick={() => notificationService.markAllAsRead()}
                                            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900 transition"
                                            title="Mark all as read"
                                        >
                                            <Check size={12} />
                                            Mark read
                                        </button>
                                    )}
                                    {notifications.length > 0 && (
                                        <button
                                            onClick={() => notificationService.clearAll()}
                                            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-red-500 transition"
                                            title="Clear all notifications"
                                        >
                                            <Trash2 size={13} />
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* Filter Tabs */}
                            <div className="flex border-b border-gray-100 px-4 pt-2 gap-3 text-xs font-medium">
                                <button
                                    onClick={() => setNotifFilter("all")}
                                    className={`pb-2 border-b-2 transition ${
                                        notifFilter === "all"
                                            ? "border-[#6d5dfc] text-[#6d5dfc]"
                                            : "border-transparent text-gray-500 hover:text-gray-800"
                                    }`}
                                >
                                    All ({notifications.length})
                                </button>
                                <button
                                    onClick={() => setNotifFilter("unread")}
                                    className={`pb-2 border-b-2 transition ${
                                        notifFilter === "unread"
                                            ? "border-[#6d5dfc] text-[#6d5dfc]"
                                            : "border-transparent text-gray-500 hover:text-gray-800"
                                    }`}
                                >
                                    Unread ({unreadCount})
                                </button>
                            </div>

                            {/* Notification List */}
                            <div className="max-h-[360px] overflow-y-auto divide-y divide-gray-50">
                                {filteredNotifications.length > 0 ? (
                                    filteredNotifications.map((notif) => (
                                        <button
                                            key={notif.id}
                                            onClick={() => handleNotificationClick(notif)}
                                            className={`w-full flex items-start gap-3 px-4 py-3 text-left transition hover:bg-gray-50/80 ${
                                                !notif.read ? "bg-[#faf9ff]" : "bg-white"
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
                                                <div className="flex items-center justify-between gap-1">
                                                    <p className={`text-xs truncate ${!notif.read ? "font-bold text-gray-900" : "font-semibold text-gray-800"}`}>
                                                        {notif.title}
                                                    </p>
                                                    <span className="text-[10px] text-gray-400 shrink-0">
                                                        {formatTimeAgo(notif.timestamp)}
                                                    </span>
                                                </div>
                                                <p className="mt-0.5 text-xs text-gray-600 line-clamp-2 leading-relaxed">
                                                    {notif.message}
                                                </p>
                                            </div>

                                            {!notif.read && (
                                                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#6d5dfc]" />
                                            )}
                                        </button>
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
                <div className="flex items-center gap-3 border-l border-gray-200 pl-5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#eeebff] text-sm font-semibold uppercase text-[#5848e8]">
                        {initials}
                    </div>

                    <div>
                        <p className="text-sm font-semibold text-gray-900">
                            {firstName} {lastName}
                        </p>

                        <p className="text-xs text-gray-500">
                            {role}
                        </p>
                    </div>

                    {user && (
                        <button
                            onClick={logout}
                            className="ml-2 rounded-xl p-2 text-gray-500 hover:bg-gray-100 hover:text-red-500 transition-colors"
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