"use client";

import { useState, useEffect, Suspense, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import {
    Search,
    AlertTriangle,
    Wrench,
    BookOpen,
    Link2,
    X,
    HelpCircle,
    RefreshCw,
    CheckCircle2,
    Database,
    ExternalLink,
    Tag,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import {
    getFullKnowledgeCatalog,
    DefectDefinition,
    CauseDefinition,
    CheckDefinition,
    EvidenceRuleDefinition,
    QuestionDefinition,
    FALLBACK_DEFECTS,
    FALLBACK_CAUSES,
    FALLBACK_ACTIONS,
    FALLBACK_RULES,
    FALLBACK_QUESTIONS,
} from "@/lib/api/knowledge";

const tabs = ["Defects", "Causes", "Actions", "Rules", "Questions"] as const;
type TabType = (typeof tabs)[number];

function KnowledgeBaseContent() {
    const searchParams = useSearchParams();

    const tabFromUrl = searchParams.get("tab") as TabType | null;
    const searchFromUrl = searchParams.get("search");

    const [activeTab, setActiveTab] = useState<TabType>(
        tabFromUrl && tabs.includes(tabFromUrl) ? tabFromUrl : "Defects"
    );
    const [search, setSearch] = useState(searchFromUrl || "");

    const [prevTab, setPrevTab] = useState(tabFromUrl);
    const [prevSearch, setPrevSearch] = useState(searchFromUrl);

    // Live catalog state loaded directly from REST API
    const [defects, setDefects] = useState<DefectDefinition[]>(FALLBACK_DEFECTS);
    const [causes, setCauses] = useState<CauseDefinition[]>(FALLBACK_CAUSES);
    const [actions, setActions] = useState<CheckDefinition[]>(FALLBACK_ACTIONS);
    const [rules, setRules] = useState<EvidenceRuleDefinition[]>(FALLBACK_RULES);
    const [questions, setQuestions] = useState<QuestionDefinition[]>(FALLBACK_QUESTIONS);

    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isLiveApi, setIsLiveApi] = useState(false);
    const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);

    // Fetch live catalog from REST API
    const loadCatalog = useCallback(async (showRefreshing = false) => {
        if (showRefreshing) {
            setIsRefreshing(true);
        } else {
            setIsLoading(true);
        }

        try {
            const catalog = await getFullKnowledgeCatalog();
            setDefects(catalog.defects);
            setCauses(catalog.causes);
            setActions(catalog.actions);
            setRules(catalog.rules);
            setQuestions(catalog.questions);
            setIsLiveApi(catalog.isLive);
            setLastSyncTime(
                new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
            );
        } catch (err) {
            console.error("[KnowledgeBase] Failed to fetch live knowledge catalog:", err);
            setIsLiveApi(false);
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, []);

    useEffect(() => {
        loadCatalog();
    }, [loadCatalog]);

    // Handle URL param synchronization
    if (tabFromUrl !== prevTab) {
        setPrevTab(tabFromUrl);
        if (tabFromUrl && (tabs as readonly string[]).includes(tabFromUrl)) {
            setActiveTab(tabFromUrl);
        }
    }

    if (searchFromUrl !== prevSearch) {
        setPrevSearch(searchFromUrl);
        if (searchFromUrl !== null) {
            setSearch(searchFromUrl);
        }
    }

    const q = search.trim().toLowerCase();

    // Human-readable cause dictionary for mapping cause IDs to friendly names
    const causeNameMap: Record<string, string> = causes.reduce((acc, c) => {
        acc[c.id] = c.name;
        return acc;
    }, {} as Record<string, string>);

    // Filtered data for each tab based on search query
    const filteredDefects = defects.filter((d) => {
        if (!q) return true;
        const causeNames = (d.applicable_causes || []).map((cid) => (causeNameMap[cid] || cid).toLowerCase());
        return (
            d.name.toLowerCase().includes(q) ||
            d.code.toLowerCase().includes(q) ||
            d.description.toLowerCase().includes(q) ||
            causeNames.some((c) => c.includes(q)) ||
            (d.symptom_patterns || []).some((p) => p.value.toLowerCase().includes(q))
        );
    });

    const filteredCauses = causes.filter((c) => {
        if (!q) return true;
        return (
            c.name.toLowerCase().includes(q) ||
            c.id.toLowerCase().includes(q) ||
            c.description.toLowerCase().includes(q) ||
            (c.applicable_defects || []).some((d) => d.toLowerCase().includes(q))
        );
    });

    const filteredActions = actions.filter((a) => {
        if (!q) return true;
        const causeNames = (a.applicable_causes || []).map((cid) => (causeNameMap[cid] || cid).toLowerCase());
        return (
            a.name.toLowerCase().includes(q) ||
            a.id.toLowerCase().includes(q) ||
            (a.description && a.description.toLowerCase().includes(q)) ||
            (a.effort_level && a.effort_level.toLowerCase().includes(q)) ||
            causeNames.some((c) => c.includes(q))
        );
    });

    const filteredRules = rules.filter((r) => {
        if (!q) return true;
        const causeName = (causeNameMap[r.cause_id] || r.cause_id).toLowerCase();
        return (
            r.id.toLowerCase().includes(q) ||
            r.observation_type.toLowerCase().includes(q) ||
            r.observation_value.toLowerCase().includes(q) ||
            r.cause_id.toLowerCase().includes(q) ||
            causeName.includes(q) ||
            r.relation.toLowerCase().includes(q) ||
            r.explanation.toLowerCase().includes(q)
        );
    });

    const filteredQuestions = questions.filter((quest) => {
        if (!q) return true;
        const causeNames = (quest.applicable_causes || []).map((cid) => (causeNameMap[cid] || cid).toLowerCase());
        return (
            quest.id.toLowerCase().includes(q) ||
            quest.text.toLowerCase().includes(q) ||
            quest.purpose.toLowerCase().includes(q) ||
            (quest.expected_answer_type && quest.expected_answer_type.toLowerCase().includes(q)) ||
            causeNames.some((c) => c.includes(q))
        );
    });

    return (
        <PageContainer>
            {/* Header with Title and Live API Synchronization Status */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider bg-[#eeebff] text-[#5848e8]">
                            <Database size={12} />
                            Knowledge Engine Catalog
                        </span>

                        {isLiveApi ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200/60">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                Live REST API (v1)
                            </span>
                        ) : (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 border border-amber-200">
                                Offline Backup Mode
                            </span>
                        )}
                    </div>

                    <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-900">
                        Knowledge Base
                    </h1>

                    <p className="mt-2 text-sm text-gray-500 max-w-3xl">
                        Authoritative diagnostic catalog querying live backend REST endpoints (<code className="text-xs bg-gray-100 px-1 py-0.5 rounded font-mono">/api/v1/defects</code>, <code className="text-xs bg-gray-100 px-1 py-0.5 rounded font-mono">/causes</code>, <code className="text-xs bg-gray-100 px-1 py-0.5 rounded font-mono">/actions</code>, <code className="text-xs bg-gray-100 px-1 py-0.5 rounded font-mono">/rules</code>, <code className="text-xs bg-gray-100 px-1 py-0.5 rounded font-mono">/questions</code>).
                    </p>
                </div>

                {/* Catalog Metrics & Live Refresh Button */}
                <div className="flex items-center gap-3 self-start sm:self-center">
                    {lastSyncTime && (
                        <span className="hidden md:inline text-xs text-gray-400">
                            Synced {lastSyncTime}
                        </span>
                    )}

                    <button
                        onClick={() => loadCatalog(true)}
                        disabled={isRefreshing}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-60"
                        title="Re-query REST API endpoints to load updated rules or fluid profiles"
                    >
                        <RefreshCw size={13} className={isRefreshing ? "animate-spin text-[#6d5dfc]" : "text-gray-500"} />
                        {isRefreshing ? "Syncing..." : "Refresh Catalog"}
                    </button>
                </div>
            </div>

            {/* Live Decoupling Banner: Explaining Zero-Redeploy Rule Editing */}
            <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/50 p-4 text-xs text-blue-900 flex items-start gap-3">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
                    <CheckCircle2 size={15} />
                </div>
                <div className="flex-1 leading-relaxed">
                    <span className="font-semibold text-blue-950">Zero-Redeployment Knowledge Architecture (FR-034):</span> All diagnostic rules, defect profiles, and fluid troubleshooting checks are served dynamically from the backend. When a process engineer alters an adhesive pot-life threshold, creates a new defect category, or updates an evidence rule, changes take effect immediately across all client workstations without requiring frontend builds or server downtime.
                </div>
            </div>

            {/* Catalog Summary Metric Bar */}
            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
                <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Defect Types</span>
                    <p className="mt-1 text-xl font-bold text-gray-900">{defects.length}</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Root Causes</span>
                    <p className="mt-1 text-xl font-bold text-gray-900">{causes.length}</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Troubleshooting Actions</span>
                    <p className="mt-1 text-xl font-bold text-gray-900">{actions.length}</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Evidence Rules</span>
                    <p className="mt-1 text-xl font-bold text-gray-900">{rules.length}</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Discriminating Questions</span>
                    <p className="mt-1 text-xl font-bold text-gray-900">{questions.length}</p>
                </div>
            </div>

            {/* Search + Tabs Navigation */}
            <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex gap-1.5 overflow-x-auto pb-1 sm:pb-0">
                    {tabs.map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`rounded-xl px-4 py-2 text-sm font-semibold transition whitespace-nowrap ${
                                activeTab === tab
                                    ? "bg-[#6d5dfc] text-white shadow-sm ring-1 ring-white/20"
                                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 dark:hover:text-white"
                            }`}
                        >
                            {tab}
                            <span className={`ml-2 text-xs rounded-full px-2 py-0.5 font-bold transition ${
                                activeTab === tab
                                    ? "bg-white/25 text-white"
                                    : "bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-transparent dark:border-gray-700"
                            }`}>
                                {tab === "Defects" && defects.length}
                                {tab === "Causes" && causes.length}
                                {tab === "Actions" && actions.length}
                                {tab === "Rules" && rules.length}
                                {tab === "Questions" && questions.length}
                            </span>
                        </button>
                    ))}
                </div>

                <div className="relative w-full sm:w-[340px]">
                    <Search
                        size={16}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                    />

                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder={`Search ${activeTab.toLowerCase()} by name, code, or cause...`}
                        className="h-10 w-full rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60 pl-9 pr-9 text-sm text-gray-900 dark:text-gray-100 outline-none transition focus:border-[#6d5dfc] focus:bg-white dark:focus:bg-gray-900 focus:ring-1 focus:ring-[#6d5dfc]"
                    />

                    {search && (
                        <button
                            onClick={() => setSearch("")}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                            title="Clear search"
                        >
                            <X size={15} />
                        </button>
                    )}
                </div>
            </div>

            {/* Search filtering notice */}
            {search && (
                <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
                    <p>
                        Filtering {activeTab} for &quot;<span className="font-semibold text-gray-900">{search}</span>&quot;
                    </p>
                    <button
                        onClick={() => setSearch("")}
                        className="text-[#6d5dfc] hover:underline font-medium"
                    >
                        Clear search
                    </button>
                </div>
            )}

            {/* Content Tabs Area */}
            <div className="mt-6">
                {isLoading ? (
                    <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                        <RefreshCw size={28} className="mx-auto text-gray-400 animate-spin mb-3" />
                        <p className="text-sm font-semibold text-gray-800">Loading live knowledge catalog...</p>
                        <p className="mt-1 text-xs text-gray-500">Connecting to FastAPI REST API on port 8000.</p>
                    </div>
                ) : (
                    <>
                        {/* ======================================================= */}
                        {/* TAB 1: DEFECTS                                          */}
                        {/* ======================================================= */}
                        {activeTab === "Defects" && (
                            filteredDefects.length > 0 ? (
                                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                                    {filteredDefects.map((defect) => (
                                        <div
                                            key={defect.code}
                                            className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-gray-300"
                                        >
                                            <div className="flex items-start gap-3">
                                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-600">
                                                    <AlertTriangle size={17} />
                                                </div>

                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <p className="text-sm font-semibold text-gray-900">
                                                            {defect.name}
                                                        </p>

                                                        <span className="rounded-md bg-gray-100 px-2 py-0.5 text-xs font-mono font-medium text-gray-600">
                                                            {defect.code}
                                                        </span>
                                                    </div>

                                                    <p className="mt-1.5 text-xs leading-5 text-gray-600">
                                                        {defect.description}
                                                    </p>

                                                    {/* Symptom Triggers */}
                                                    {defect.symptom_patterns && defect.symptom_patterns.length > 0 && (
                                                        <div className="mt-3">
                                                            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1 mb-1">
                                                                <Tag size={10} /> Physical Observation Triggers
                                                            </span>
                                                            <div className="flex flex-wrap gap-1">
                                                                {defect.symptom_patterns.map((p, idx) => (
                                                                    <span
                                                                        key={`${p.type}-${p.value}-${idx}`}
                                                                        className="rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600"
                                                                    >
                                                                        {p.type}: <strong className="text-gray-800">{p.value}</strong>
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Applicable Causes */}
                                                    {defect.applicable_causes && defect.applicable_causes.length > 0 && (
                                                        <div className="mt-3">
                                                            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider block mb-1">
                                                                Associated Candidate Causes
                                                            </span>
                                                            <div className="flex flex-wrap gap-1">
                                                                {defect.applicable_causes.map((cid) => (
                                                                    <span
                                                                        key={cid}
                                                                        className="rounded-md bg-[#eeebff] px-2 py-0.5 text-[10px] font-medium text-[#5848e8]"
                                                                    >
                                                                        {causeNameMap[cid] || cid.replace(/_/g, " ")}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                                    <AlertTriangle size={28} className="mx-auto text-gray-300 mb-2" />
                                    <p className="text-sm font-semibold text-gray-800">No defects match your search</p>
                                    <p className="mt-1 text-xs text-gray-500">No defect profiles found matching &quot;{search}&quot;.</p>
                                    <button
                                        onClick={() => setSearch("")}
                                        className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                                    >
                                        Clear Search
                                    </button>
                                </div>
                            )
                        )}

                        {/* ======================================================= */}
                        {/* TAB 2: CAUSES                                           */}
                        {/* ======================================================= */}
                        {activeTab === "Causes" && (
                            filteredCauses.length > 0 ? (
                                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                                    {filteredCauses.map((cause) => (
                                        <div
                                            key={cause.id}
                                            className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-gray-300"
                                        >
                                            <div className="flex items-start gap-3">
                                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                                                    <Link2 size={17} />
                                                </div>

                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <p className="text-sm font-semibold text-gray-900">
                                                            {cause.name}
                                                        </p>
                                                        <span className="font-mono text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">
                                                            {cause.id}
                                                        </span>
                                                    </div>

                                                    <p className="mt-1 text-xs leading-5 text-gray-600">
                                                        {cause.description}
                                                    </p>

                                                    {/* Applicable Defects */}
                                                    {cause.applicable_defects && cause.applicable_defects.length > 0 && (
                                                        <div className="mt-3">
                                                            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">
                                                                Manifests In Defect Categories ({cause.applicable_defects.length})
                                                            </p>
                                                            <div className="flex flex-wrap gap-1">
                                                                {cause.applicable_defects.map((defCode) => (
                                                                    <span
                                                                        key={defCode}
                                                                        className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono font-medium text-gray-700"
                                                                    >
                                                                        {defCode}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {cause.source_references && cause.source_references.length > 0 && (
                                                        <p className="mt-2 text-[10px] text-gray-400">
                                                            Reference: {cause.source_references.join(", ")}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                                    <Link2 size={28} className="mx-auto text-gray-300 mb-2" />
                                    <p className="text-sm font-semibold text-gray-800">No root causes match your search</p>
                                    <p className="mt-1 text-xs text-gray-500">No causes found matching &quot;{search}&quot;.</p>
                                    <button
                                        onClick={() => setSearch("")}
                                        className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                                    >
                                        Clear Search
                                    </button>
                                </div>
                            )
                        )}

                        {/* ======================================================= */}
                        {/* TAB 3: ACTIONS                                          */}
                        {/* ======================================================= */}
                        {activeTab === "Actions" && (
                            filteredActions.length > 0 ? (
                                <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left">
                                            <thead>
                                                <tr className="border-b border-gray-100 bg-gray-50/50">
                                                    <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                        Action ID
                                                    </th>
                                                    <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                        Standard Procedure
                                                    </th>
                                                    <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                        Effort
                                                    </th>
                                                    <th className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                        Target Root Causes
                                                    </th>
                                                </tr>
                                            </thead>

                                            <tbody className="divide-y divide-gray-100">
                                                {filteredActions.map((action) => (
                                                    <tr
                                                        key={action.id}
                                                        className="transition hover:bg-gray-50/70"
                                                    >
                                                        <td className="px-6 py-3.5 text-xs font-mono font-semibold text-gray-700 whitespace-nowrap">
                                                            {action.id}
                                                        </td>

                                                        <td className="px-6 py-3.5 max-w-md">
                                                            <p className="text-sm font-semibold text-gray-900">
                                                                {action.name}
                                                            </p>
                                                            {action.description && (
                                                                <p className="text-xs text-gray-500 mt-0.5">
                                                                    {action.description}
                                                                </p>
                                                            )}
                                                            {action.procedure && (
                                                                <details className="mt-2 text-[11px] text-gray-600">
                                                                    <summary className="cursor-pointer text-[#6d5dfc] font-medium hover:underline">
                                                                        View SOP Procedure Steps
                                                                    </summary>
                                                                    <pre className="mt-1 whitespace-pre-wrap font-sans bg-gray-50 p-2 rounded border border-gray-100 text-gray-700 leading-relaxed">
                                                                        {action.procedure}
                                                                    </pre>
                                                                </details>
                                                            )}
                                                        </td>

                                                        <td className="px-6 py-3.5 whitespace-nowrap">
                                                            <span
                                                                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium capitalize ${
                                                                    (action.effort_level || "").toLowerCase() === "low"
                                                                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                                                        : (action.effort_level || "").toLowerCase() === "medium"
                                                                          ? "bg-amber-50 text-amber-700 border border-amber-200"
                                                                          : "bg-rose-50 text-rose-700 border border-rose-200"
                                                                }`}
                                                            >
                                                                {action.effort_level || "Medium"}
                                                            </span>
                                                        </td>

                                                        <td className="px-6 py-3.5">
                                                            <div className="flex flex-wrap gap-1">
                                                                {(action.applicable_causes || []).map((cid) => (
                                                                    <span
                                                                        key={cid}
                                                                        className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600"
                                                                    >
                                                                        {causeNameMap[cid] || cid.replace(/_/g, " ")}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            ) : (
                                <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                                    <Wrench size={28} className="mx-auto text-gray-300 mb-2" />
                                    <p className="text-sm font-semibold text-gray-800">No actions match your search</p>
                                    <p className="mt-1 text-xs text-gray-500">No recommended actions found matching &quot;{search}&quot;.</p>
                                    <button
                                        onClick={() => setSearch("")}
                                        className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                                    >
                                        Clear Search
                                    </button>
                                </div>
                            )
                        )}

                        {/* ======================================================= */}
                        {/* TAB 4: RULES                                            */}
                        {/* ======================================================= */}
                        {activeTab === "Rules" && (
                            <div className="space-y-4">
                                <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-6 text-center">
                                    <BookOpen
                                        size={32}
                                        className="mx-auto text-[#6d5dfc]/70"
                                    />

                                    <h3 className="mt-2 text-base font-semibold text-gray-900">
                                        Live Evidence Evaluation Rules ({rules.length} Active Rules)
                                    </h3>

                                    <p className="mt-1 text-xs text-gray-600 max-w-2xl mx-auto">
                                        The diagnostic engine evaluates observations against this live codified knowledge rule set, computing deterministic evidence-support scores on a 0–100 scale.
                                    </p>
                                </div>

                                {filteredRules.length > 0 ? (
                                    <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-left text-sm">
                                                <thead>
                                                    <tr className="border-b border-gray-100 bg-gray-50/50 text-xs font-semibold uppercase tracking-wide text-gray-400">
                                                        <th className="px-6 py-3.5">Rule ID</th>
                                                        <th className="px-6 py-3.5">Observation Condition</th>
                                                        <th className="px-6 py-3.5">Target Cause</th>
                                                        <th className="px-6 py-3.5">Relation</th>
                                                        <th className="px-6 py-3.5">Strength</th>
                                                        <th className="px-6 py-3.5">Engineering Rationale</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-100">
                                                    {filteredRules.map((rule) => (
                                                        <tr key={rule.id} className="transition hover:bg-gray-50/70">
                                                            <td className="px-6 py-3.5 font-mono text-xs font-semibold text-gray-600 whitespace-nowrap">
                                                                {rule.id}
                                                            </td>

                                                            <td className="px-6 py-3.5 whitespace-nowrap">
                                                                <span className="text-xs font-mono font-medium text-gray-800 bg-gray-100 px-1.5 py-0.5 rounded">
                                                                    {rule.observation_type}={rule.observation_value}
                                                                </span>
                                                            </td>

                                                            <td className="px-6 py-3.5 font-medium text-gray-900 whitespace-nowrap">
                                                                {causeNameMap[rule.cause_id] || rule.cause_id}
                                                            </td>

                                                            <td className="px-6 py-3.5 whitespace-nowrap">
                                                                <span
                                                                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wide ${
                                                                        rule.relation === "SUPPORTS"
                                                                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                                                            : rule.relation === "CONTRADICTS"
                                                                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                                                                              : "bg-gray-100 text-gray-600"
                                                                    }`}
                                                                >
                                                                    {rule.relation}
                                                                </span>
                                                            </td>

                                                            <td className="px-6 py-3.5 whitespace-nowrap">
                                                                <span className="text-[11px] font-medium text-gray-500 capitalize">
                                                                    {rule.strength.toLowerCase()}
                                                                </span>
                                                            </td>

                                                            <td className="px-6 py-3.5 text-xs text-gray-600 max-w-sm">
                                                                {rule.explanation}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                                        <BookOpen size={28} className="mx-auto text-gray-300 mb-2" />
                                        <p className="text-sm font-semibold text-gray-800">No rules match your search</p>
                                        <p className="mt-1 text-xs text-gray-500">No evidence rules found matching &quot;{search}&quot;.</p>
                                        <button
                                            onClick={() => setSearch("")}
                                            className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                                        >
                                            Clear Search
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* ======================================================= */}
                        {/* TAB 5: QUESTIONS (Discriminating Questions Catalog)      */}
                        {/* ======================================================= */}
                        {activeTab === "Questions" && (
                            <div className="space-y-4">
                                <div className="rounded-2xl border border-[#ded9ff] bg-[#faf9ff] p-6 text-center">
                                    <HelpCircle
                                        size={32}
                                        className="mx-auto text-[#6d5dfc]/70"
                                    />

                                    <h3 className="mt-2 text-base font-semibold text-gray-900">
                                        Discriminating Diagnostic Questions ({questions.length} Questions)
                                    </h3>

                                    <p className="mt-1 text-xs text-gray-600 max-w-2xl mx-auto">
                                        Questions evaluated by the Information-Gain QuestionEngine to dynamically discriminate between competing physical root causes.
                                    </p>
                                </div>

                                {filteredQuestions.length > 0 ? (
                                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                                        {filteredQuestions.map((quest) => (
                                            <div
                                                key={quest.id}
                                                className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-gray-300"
                                            >
                                                <div className="flex items-start gap-3">
                                                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                                                        <HelpCircle size={17} />
                                                    </div>

                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-mono text-xs font-bold text-gray-800 bg-gray-100 px-2 py-0.5 rounded">
                                                                {quest.id}
                                                            </span>
                                                            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600 capitalize">
                                                                {quest.expected_answer_type || "categorical"}
                                                            </span>
                                                        </div>

                                                        <p className="mt-2 text-sm font-semibold text-gray-900 leading-snug">
                                                            &ldquo;{quest.text}&rdquo;
                                                        </p>

                                                        <p className="mt-1 text-xs text-gray-500 leading-relaxed">
                                                            <strong className="text-gray-700">Discrimination Purpose:</strong> {quest.purpose}
                                                        </p>

                                                        {/* Target Causes */}
                                                        {quest.applicable_causes && quest.applicable_causes.length > 0 && (
                                                            <div className="mt-3">
                                                                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider block mb-1">
                                                                    Discriminated Causes
                                                                </span>
                                                                <div className="flex flex-wrap gap-1">
                                                                    {quest.applicable_causes.map((cid) => (
                                                                        <span
                                                                            key={cid}
                                                                            className="rounded bg-[#eeebff] px-2 py-0.5 text-[10px] font-medium text-[#5848e8]"
                                                                        >
                                                                            {causeNameMap[cid] || cid.replace(/_/g, " ")}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center">
                                        <HelpCircle size={28} className="mx-auto text-gray-300 mb-2" />
                                        <p className="text-sm font-semibold text-gray-800">No questions match your search</p>
                                        <p className="mt-1 text-xs text-gray-500">No diagnostic questions found matching &quot;{search}&quot;.</p>
                                        <button
                                            onClick={() => setSearch("")}
                                            className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
                                        >
                                            Clear Search
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>
        </PageContainer>
    );
}

export default function KnowledgeBasePage() {
    return (
        <Suspense fallback={<div className="p-8 text-center text-sm text-gray-500">Loading knowledge base...</div>}>
            <KnowledgeBaseContent />
        </Suspense>
    );
}
