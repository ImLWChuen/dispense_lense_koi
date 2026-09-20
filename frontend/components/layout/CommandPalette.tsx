"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
    Search,
    X,
    LayoutDashboard,
    Stethoscope,
    ClipboardCheck,
    BarChart3,
    BookOpen,
    FileText,
    Shield,
    Settings,
    ArrowRight,
    AlertCircle,
    Activity,
    Wrench,
    CheckCircle2,
    CornerDownLeft,
    Radio,
    Clock,
} from "lucide-react";
import { useAuth } from "@/components/providers/AuthContext";
import { casesApi } from "@/lib/api/cases";
import { DurableCaseResponse } from "@/types/api";

interface CommandPaletteProps {
    isOpen: boolean;
    onClose: () => void;
}

interface PaletteItem {
    id: string;
    title: string;
    subtitle?: string;
    category: "Quick Actions" | "Active Cases" | "Defect Codes" | "SOPs & Causes";
    icon: any;
    badge?: string;
    badgeColor?: string;
    onSelect: () => void;
}

const DEFECT_ITEMS = [
    { code: "D01", name: "Too Little Material", desc: "Dispensed volume consistently below target" },
    { code: "D02", name: "Too Much Material", desc: "Dispensed volume consistently above target" },
    { code: "D03", name: "Inconsistent Size", desc: "Deposit dimensions fluctuate between shots" },
    { code: "D04", name: "Missing Dots", desc: "One or more dispense locations receive no fluid" },
    { code: "D05", name: "Spreading", desc: "Material wets out excessively on optical substrate" },
    { code: "D06", name: "Bubbles / Abnormal Shape", desc: "Trapped air voids or irregular deposit geometry" },
];

const SOP_ITEMS = [
    { code: "ACT01", name: "Inspect Nozzle Tip", category: "SOPs & Causes", tab: "Actions", desc: "Microscopic inspection for residue or partial blockage" },
    { code: "ACT02", name: "Check Material Supply", category: "SOPs & Causes", tab: "Actions", desc: "Verify syringe level, degassing, and fluid lines" },
    { code: "ACT03", name: "Perform Test Shots", category: "SOPs & Causes", tab: "Actions", desc: "Dispense matrix onto tare balance to measure mass" },
    { code: "RC01", name: "Nozzle Restriction", category: "SOPs & Causes", tab: "Causes", desc: "Partial or full fluid path obstruction" },
    { code: "RC02", name: "Air / Supply Issue", category: "SOPs & Causes", tab: "Causes", desc: "Trapped air or fluctuating pneumatic pressure" },
    { code: "RC03", name: "Material Condition", category: "SOPs & Causes", tab: "Causes", desc: "Viscosity variation or improper thaw time" },
];

export default function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
    const router = useRouter();
    const { user, isAdmin } = useAuth();
    const [query, setQuery] = useState("");
    const [cases, setCases] = useState<DurableCaseResponse[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);

    // Fetch cases when palette opens
    useEffect(() => {
        if (isOpen) {
            casesApi.listCases()
                .then(setCases)
                .catch((err) => console.warn("Failed to cache cases for command palette:", err));
            setQuery("");
            setSelectedIndex(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [isOpen]);

    // Construct flat list of searchable items
    const items: PaletteItem[] = useMemo(() => {
        const q = query.trim().toLowerCase();
        const results: PaletteItem[] = [];

        // 1. Navigation / Quick Actions
        const quickActions: PaletteItem[] = [
            {
                id: "nav-new-diagnosis",
                title: "New Diagnostic Intake",
                subtitle: "Upload defect image and initiate root-cause investigation",
                category: "Quick Actions",
                icon: Stethoscope,
                badge: "Intake",
                badgeColor: "bg-[#eeebff] text-[#5848e8]",
                onSelect: () => router.push("/diagnosis/new"),
            },
            {
                id: "nav-telemetry",
                title: "Cleanroom Telemetry & Pot Life",
                subtitle: "Live sensor ribbons, adhesive defrosting, and syringe expiration timers",
                category: "Quick Actions",
                icon: Radio,
                badge: "Telemetry",
                badgeColor: "bg-indigo-50 text-indigo-700",
                onSelect: () => router.push("/telemetry"),
            },
            {
                id: "nav-pot-life",
                title: "Check Syringe Pot Life & Thaw",
                subtitle: "Monitor active adhesive countdowns and thaw new barrels from cold storage",
                category: "Quick Actions",
                icon: Clock,
                badge: "Pot Life",
                badgeColor: "bg-amber-50 text-amber-700",
                onSelect: () => router.push("/telemetry"),
            },
            {
                id: "nav-cases",
                title: "View All Cases",
                subtitle: "Search and filter diagnostic case history",
                category: "Quick Actions",
                icon: ClipboardCheck,
                badge: "Cases",
                badgeColor: "bg-blue-50 text-blue-600",
                onSelect: () => router.push("/cases"),
            },
            {
                id: "nav-analytics",
                title: "Production Analytics",
                subtitle: "Defect trends, Pareto distributions, and MTTR metrics",
                category: "Quick Actions",
                icon: BarChart3,
                badge: "Analytics",
                badgeColor: "bg-emerald-50 text-emerald-600",
                onSelect: () => router.push("/analytics"),
            },
            {
                id: "nav-kb",
                title: "Knowledge Base & SOPs",
                subtitle: "Defect taxonomy, root-cause rules, and inspection SOPs",
                category: "Quick Actions",
                icon: BookOpen,
                badge: "Reference",
                badgeColor: "bg-purple-50 text-purple-600",
                onSelect: () => router.push("/knowledge-base"),
            },
            {
                id: "nav-reports",
                title: "Diagnostic Reports Archive",
                subtitle: "View, audit, and download PDF engineering reports",
                category: "Quick Actions",
                icon: FileText,
                badge: "Reports",
                badgeColor: "bg-amber-50 text-amber-600",
                onSelect: () => router.push("/reports"),
            },
            {
                id: "nav-dashboard",
                title: "Overview Cockpit",
                subtitle: "Main production overview and real-time defect feed",
                category: "Quick Actions",
                icon: LayoutDashboard,
                badge: "Home",
                badgeColor: "bg-gray-100 text-gray-700",
                onSelect: () => router.push("/dashboard"),
            },
        ];

        if (isAdmin || user?.role === "admin") {
            quickActions.unshift({
                id: "nav-admin",
                title: "Admin Console",
                subtitle: "Workforce directory, role management, and audit timeline",
                category: "Quick Actions",
                icon: Shield,
                badge: "ADMIN",
                badgeColor: "bg-purple-100 text-purple-800",
                onSelect: () => router.push("/admin"),
            });
        }

        quickActions.push({
            id: "nav-settings",
            title: "Settings & Preferences",
            subtitle: "Cleanroom display settings and notification preferences",
            category: "Quick Actions",
            icon: Settings,
            badge: "Config",
            badgeColor: "bg-gray-100 text-gray-600",
            onSelect: () => router.push("/settings"),
        });

        // Filter quick actions
        const matchedActions = q
            ? quickActions.filter((a) =>
                  a.title.toLowerCase().includes(q) ||
                  (a.subtitle && a.subtitle.toLowerCase().includes(q))
              )
            : quickActions.slice(0, 4);
        results.push(...matchedActions);

        // 2. Active Cases Matches
        const matchedCases: PaletteItem[] = cases
            .filter((c) => {
                if (!q) return true;
                return (
                    c.case_id.toLowerCase().includes(q) ||
                    (c.defect_name && c.defect_name.toLowerCase().includes(q)) ||
                    (c.defect_code && c.defect_code.toLowerCase().includes(q)) ||
                    (c.machine_context?.equipment && String(c.machine_context.equipment).toLowerCase().includes(q)) ||
                    c.issue_condition.toLowerCase().includes(q)
                );
            })
            .slice(0, q ? 5 : 3)
            .map((c) => {
                const shortId = c.case_id.includes("-") ? c.case_id.split("-")[0] : c.case_id;
                const condition = c.issue_condition || "UNRESOLVED";
                const statusColor =
                    condition === "RESOLVED"
                        ? "bg-emerald-50 text-emerald-700"
                        : condition === "RECOVERY_PENDING_VERIFICATION"
                        ? "bg-blue-50 text-blue-700"
                        : "bg-amber-50 text-amber-700";

                return {
                    id: `case-${c.case_id}`,
                    title: `Case ${shortId}: ${c.defect_name || c.defect_code || "Unknown Defect"}`,
                    subtitle: `${c.machine_context?.equipment ? `Line ${c.machine_context.equipment} • ` : ""}${c.issue_condition}`,
                    category: "Active Cases",
                    icon: Activity,
                    badge: condition,
                    badgeColor: statusColor,
                    onSelect: () => router.push(`/diagnosis/${c.case_id}`),
                };
            });
        results.push(...matchedCases);

        // 3. Defect Codes (D01–D06)
        const matchedDefects: PaletteItem[] = DEFECT_ITEMS
            .filter((d) => {
                if (!q) return false;
                return (
                    d.code.toLowerCase().includes(q) ||
                    d.name.toLowerCase().includes(q) ||
                    d.desc.toLowerCase().includes(q)
                );
            })
            .slice(0, 4)
            .map((d) => ({
                id: `defect-${d.code}`,
                title: `${d.code}: ${d.name}`,
                subtitle: d.desc,
                category: "Defect Codes",
                icon: AlertCircle,
                badge: d.code,
                badgeColor: "bg-rose-50 text-rose-700",
                onSelect: () => router.push(`/knowledge-base?tab=Defects&search=${encodeURIComponent(d.code)}`),
            }));
        results.push(...matchedDefects);

        // 4. SOP & Cause Matches
        const matchedSOPs: PaletteItem[] = SOP_ITEMS
            .filter((s) => {
                if (!q) return false;
                return (
                    s.code.toLowerCase().includes(q) ||
                    s.name.toLowerCase().includes(q) ||
                    s.desc.toLowerCase().includes(q)
                );
            })
            .slice(0, 3)
            .map((s) => ({
                id: `sop-${s.code}`,
                title: `${s.code}: ${s.name}`,
                subtitle: s.desc,
                category: "SOPs & Causes",
                icon: Wrench,
                badge: s.tab,
                badgeColor: "bg-indigo-50 text-indigo-700",
                onSelect: () => router.push(`/knowledge-base?tab=${s.tab}&search=${encodeURIComponent(s.code)}`),
            }));
        results.push(...matchedSOPs);

        return results;
    }, [query, cases, isAdmin, user, router]);

    // Ensure selectedIndex stays in bounds
    useEffect(() => {
        setSelectedIndex(0);
    }, [query]);

    // Keyboard handlers
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex((prev) => (prev + 1 < items.length ? prev + 1 : 0));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : items.length - 1));
            } else if (e.key === "Enter") {
                e.preventDefault();
                if (items[selectedIndex]) {
                    items[selectedIndex].onSelect();
                    onClose();
                }
            } else if (e.key === "Escape") {
                e.preventDefault();
                onClose();
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, items, selectedIndex, onClose]);

    if (!isOpen) return null;

    // Group items by category for visual display
    const categories = Array.from(new Set(items.map((i) => i.category)));

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 p-4">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-gray-900/40 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            />

            {/* Modal Box */}
            <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-2xl transition-all">
                {/* Search Input Bar */}
                <div className="flex items-center border-b border-gray-100 px-4 py-3.5">
                    <Search size={20} className="text-[#6d5dfc] shrink-0 mr-3" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search cases, defect codes (D01-D06), SOPs, or commands..."
                        className="w-full bg-transparent text-sm sm:text-base text-gray-900 placeholder:text-gray-400 focus:outline-none"
                    />
                    {query ? (
                        <button
                            onClick={() => setQuery("")}
                            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                        >
                            <X size={16} />
                        </button>
                    ) : (
                        <kbd className="hidden sm:inline-flex items-center rounded border border-gray-200 px-2 py-0.5 text-[11px] font-semibold text-gray-400 bg-gray-50">
                            ESC
                        </kbd>
                    )}
                </div>

                {/* Items List */}
                <div
                    ref={listRef}
                    className="max-h-[60vh] overflow-y-auto px-2 py-3 divide-y divide-gray-50"
                >
                    {items.length === 0 ? (
                        <div className="py-12 text-center">
                            <AlertCircle size={32} className="mx-auto text-gray-300 mb-2" />
                            <p className="text-sm font-medium text-gray-700">No matching commands or cases</p>
                            <p className="text-xs text-gray-400 mt-1">Try searching &quot;D01&quot;, &quot;Line A&quot;, &quot;Nozzle&quot;, or &quot;New Diagnosis&quot;</p>
                        </div>
                    ) : (
                        categories.map((cat) => {
                            const catItems = items.filter((i) => i.category === cat);
                            return (
                                <div key={cat} className="py-2 first:pt-0 last:pb-0">
                                    <p className="px-3 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-gray-400">
                                        {cat}
                                    </p>
                                    <div className="space-y-1">
                                        {catItems.map((item) => {
                                            const itemIndex = items.indexOf(item);
                                            const isSelected = itemIndex === selectedIndex;
                                            const Icon = item.icon;

                                            return (
                                                <div
                                                    key={item.id}
                                                    onClick={() => {
                                                        item.onSelect();
                                                        onClose();
                                                    }}
                                                    onMouseEnter={() => setSelectedIndex(itemIndex)}
                                                    className={`group flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 cursor-pointer transition ${
                                                        isSelected
                                                            ? "bg-[#eeebff] text-[#5848e8]"
                                                            : "text-gray-700 hover:bg-gray-50"
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-3 min-w-0">
                                                        <div
                                                            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                                                                isSelected
                                                                    ? "bg-white text-[#5848e8] shadow-xs"
                                                                    : "bg-gray-100 text-gray-500 group-hover:bg-gray-200/70"
                                                            }`}
                                                        >
                                                            <Icon size={16} />
                                                        </div>
                                                        <div className="min-w-0">
                                                            <p className="text-sm font-semibold truncate">
                                                                {item.title}
                                                            </p>
                                                            {item.subtitle && (
                                                                <p
                                                                    className={`text-xs truncate ${
                                                                        isSelected
                                                                            ? "text-[#6d5dfc]/90"
                                                                            : "text-gray-400"
                                                                    }`}
                                                                >
                                                                    {item.subtitle}
                                                                </p>
                                                            )}
                                                        </div>
                                                    </div>

                                                    <div className="flex items-center gap-2 shrink-0">
                                                        {item.badge && (
                                                            <span
                                                                className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                                                                    item.badgeColor || "bg-gray-100 text-gray-600"
                                                                }`}
                                                            >
                                                                {item.badge}
                                                            </span>
                                                        )}
                                                        {isSelected && (
                                                            <CornerDownLeft size={14} className="text-[#5848e8]" />
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Footer hints */}
                <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50/60 px-4 py-2.5 text-[11px] text-gray-400">
                    <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1">
                            <kbd className="rounded border border-gray-200 bg-white px-1 py-0.5 text-[10px] font-semibold text-gray-500">↑</kbd>
                            <kbd className="rounded border border-gray-200 bg-white px-1 py-0.5 text-[10px] font-semibold text-gray-500">↓</kbd>
                            Navigate
                        </span>
                        <span className="flex items-center gap-1">
                            <kbd className="rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">↵</kbd>
                            Select
                        </span>
                    </div>
                    <span className="hidden sm:inline">
                        Dispense Lens Omnibox
                    </span>
                </div>
            </div>
        </div>
    );
}
