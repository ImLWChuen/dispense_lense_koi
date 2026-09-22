"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
    Shield,
    Users,
    UserPlus,
    KeyRound,
    Edit3,
    Trash2,
    CheckCircle2,
    XCircle,
    Search,
    Filter,
    RefreshCw,
    Activity,
    Clock,
    AlertTriangle,
    Check,
    X,
    Building2,
    Briefcase,
    ChevronRight,
    ChevronLeft,
    ArrowUpRight,
    ArrowUpDown,
    Lock,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import { useAuth, User } from "@/components/providers/AuthContext";
import {
    adminApi,
    AdminOverviewStats,
    EmployeeSummary,
    CreateEmployeeRequest,
    UpdateEmployeeRequest,
} from "@/lib/api/admin";

export default function AdminDashboardPage() {
    const { user, isAdmin, isLoading: authLoading, login } = useAuth();
    const router = useRouter();

    // Data states
    const [overview, setOverview] = useState<AdminOverviewStats | null>(null);
    const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    // Filtering & pagination states
    const [searchQuery, setSearchQuery] = useState("");
    const [roleFilter, setRoleFilter] = useState("ALL");
    const [statusFilter, setStatusFilter] = useState<"ALL" | "ACTIVE" | "INACTIVE">("ALL");
    const [sortField, setSortField] = useState<"name" | "role" | "cases">("name");
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
    const [currentPage, setCurrentPage] = useState(1);
    const PAGE_SIZE = 6;

    // Audit trail filtering states
    const [auditCategory, setAuditCategory] = useState<"ALL" | "CONFIRMATION" | "LIFECYCLE">("ALL");
    const [auditSearch, setAuditSearch] = useState("");

    // Modal states
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
    const [selectedEmployee, setSelectedEmployee] = useState<EmployeeSummary | null>(null);

    // Form states
    const [addForm, setAddForm] = useState<CreateEmployeeRequest>({
        email: "",
        password: "",
        first_name: "",
        last_name: "",
        role: "technician",
        department: "SMT Line 1 - Dispensing",
        is_active: true,
    });

    const [editForm, setEditForm] = useState<UpdateEmployeeRequest>({
        email: "",
        first_name: "",
        last_name: "",
        role: "technician",
        department: "",
        is_active: true,
    });

    const [newPassword, setNewPassword] = useState("");
    const [actionLoading, setActionLoading] = useState(false);

    const fetchData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [overviewData, employeeList] = await Promise.all([
                adminApi.getOverview(),
                adminApi.listEmployees(),
            ]);
            setOverview(overviewData);
            setEmployees(employeeList);
        } catch (err: any) {
            console.error("Admin dashboard load error:", err);
            setError(err.message || "Failed to load administrative data.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (!authLoading) {
            if (user && user.role === "admin") {
                fetchData();
            } else {
                setIsLoading(false);
            }
        }
    }, [user, authLoading]);

    // Toast auto-clear
    useEffect(() => {
        if (successMessage) {
            const timer = setTimeout(() => setSuccessMessage(null), 4000);
            return () => clearTimeout(timer);
        }
    }, [successMessage]);

    // Handle employee creation
    const handleCreateEmployee = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!addForm.email || !addForm.password || !addForm.first_name) {
            alert("Please fill in email, password, and first name.");
            return;
        }

        setActionLoading(true);
        try {
            await adminApi.createEmployee(addForm);
            setSuccessMessage(`Employee ${addForm.email} created successfully.`);
            setIsAddModalOpen(false);
            setAddForm({
                email: "",
                password: "",
                first_name: "",
                last_name: "",
                role: "technician",
                department: "SMT Line 1 - Dispensing",
                is_active: true,
            });
            fetchData();
        } catch (err: any) {
            alert(err.message || "Failed to create employee.");
        } finally {
            setActionLoading(false);
        }
    };

    // Open Edit Modal
    const openEditModal = (emp: EmployeeSummary) => {
        setSelectedEmployee(emp);
        setEditForm({
            email: emp.email,
            first_name: emp.first_name || "",
            last_name: emp.last_name || "",
            role: emp.role,
            department: emp.department || "",
            is_active: emp.is_active,
        });
        setIsEditModalOpen(true);
    };

    // Handle employee update
    const handleUpdateEmployee = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedEmployee) return;

        setActionLoading(true);
        try {
            await adminApi.updateEmployee(selectedEmployee.id, editForm);
            setSuccessMessage(`Employee ${editForm.email || selectedEmployee.email} updated.`);
            setIsEditModalOpen(false);
            setSelectedEmployee(null);
            fetchData();
        } catch (err: any) {
            alert(err.message || "Failed to update employee.");
        } finally {
            setActionLoading(false);
        }
    };

    // Open Password Reset Modal
    const openPasswordModal = (emp: EmployeeSummary) => {
        setSelectedEmployee(emp);
        setNewPassword("");
        setIsPasswordModalOpen(true);
    };

    // Handle password reset
    const handleResetPassword = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedEmployee || !newPassword) return;
        if (newPassword.length < 4) {
            alert("Password must be at least 4 characters.");
            return;
        }

        setActionLoading(true);
        try {
            await adminApi.resetPassword(selectedEmployee.id, newPassword);
            setSuccessMessage(`Password reset successfully for ${selectedEmployee.email}.`);
            setIsPasswordModalOpen(false);
            setSelectedEmployee(null);
            setNewPassword("");
        } catch (err: any) {
            alert(err.message || "Failed to reset password.");
        } finally {
            setActionLoading(false);
        }
    };

    // Toggle active status
    const handleToggleActive = async (emp: EmployeeSummary) => {
        if (emp.id === user?.id) {
            alert("You cannot deactivate your own administrator account.");
            return;
        }

        const newStatus = !emp.is_active;
        try {
            await adminApi.updateEmployee(emp.id, { is_active: newStatus });
            setSuccessMessage(`Employee ${emp.email} ${newStatus ? "activated" : "deactivated"}.`);
            fetchData();
        } catch (err: any) {
            alert(err.message || "Failed to update employee status.");
        }
    };

    // Filtered & Sorted employees
    const filteredEmployees = employees.filter((emp) => {
        if (roleFilter !== "ALL" && emp.role.toLowerCase() !== roleFilter.toLowerCase()) {
            return false;
        }
        if (statusFilter === "ACTIVE" && !emp.is_active) return false;
        if (statusFilter === "INACTIVE" && emp.is_active) return false;

        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase().trim();
        const fullName = `${emp.first_name || ""} ${emp.last_name || ""}`.toLowerCase();
        const email = emp.email.toLowerCase();
        const dept = (emp.department || "").toLowerCase();

        return fullName.includes(q) || email.includes(q) || dept.includes(q);
    });

    const sortedEmployees = [...filteredEmployees].sort((a, b) => {
        let comp = 0;
        if (sortField === "name") {
            const nameA = `${a.first_name || ""} ${a.last_name || ""} ${a.email}`.toLowerCase();
            const nameB = `${b.first_name || ""} ${b.last_name || ""} ${b.email}`.toLowerCase();
            comp = nameA.localeCompare(nameB);
        } else if (sortField === "role") {
            comp = a.role.localeCompare(b.role);
        } else if (sortField === "cases") {
            comp = (a.cases_handled || 0) - (b.cases_handled || 0);
        }
        return sortOrder === "asc" ? comp : -comp;
    });

    const totalPages = Math.max(1, Math.ceil(sortedEmployees.length / PAGE_SIZE));
    const paginatedEmployees = sortedEmployees.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

    const toggleSort = (field: "name" | "role" | "cases") => {
        if (sortField === field) {
            setSortOrder(sortOrder === "asc" ? "desc" : "asc");
        } else {
            setSortField(field);
            setSortOrder(field === "cases" ? "desc" : "asc");
        }
        setCurrentPage(1);
    };

    // Filtered audit activities
    const filteredActivities = (overview?.recent_activities || []).filter((act) => {
        if (auditCategory === "CONFIRMATION" && act.type !== "CAUSE_CONFIRMATION") return false;
        if (auditCategory === "LIFECYCLE" && act.type === "CAUSE_CONFIRMATION") return false;
        if (auditSearch.trim()) {
            const q = auditSearch.toLowerCase().trim();
            const title = (act.title || "").toLowerCase();
            const desc = (act.description || "").toLowerCase();
            const actor = (act.actor || "").toLowerCase();
            return title.includes(q) || desc.includes(q) || actor.includes(q);
        }
        return true;
    });

    // Helper for role badge colors
    const getRoleBadge = (role: string) => {
        switch (role.toLowerCase()) {
            case "admin":
                return "bg-purple-100 text-purple-700 border-purple-200";
            case "engineer":
                return "bg-blue-100 text-blue-700 border-blue-200";
            case "technician":
                return "bg-emerald-100 text-emerald-700 border-emerald-200";
            default:
                return "bg-slate-100 text-slate-700 border-slate-200";
        }
    };

    // Access Denied State if not admin
    if (!authLoading && (!user || user.role !== "admin")) {
        return (
            <PageContainer>
                <div className="mx-auto max-w-xl py-16 text-center">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-100 text-amber-600 shadow-sm mb-4">
                        <Shield size={32} />
                    </div>
                    <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
                        Administrator Access Required
                    </h2>
                    <p className="mt-2 text-sm text-gray-600 leading-relaxed">
                        You are currently signed in as <strong>{user?.email || "Guest"}</strong> ({user?.role || "Non-admin"}).
                        This oversight dashboard is strictly restricted to supervisory personnel with Administrator privileges.
                    </p>
                    <div className="mt-6 flex items-center justify-center gap-4">
                        <Link
                            href="/dashboard"
                            className="rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 shadow-sm transition"
                        >
                            Return to Dashboard
                        </Link>
                        <Link
                            href="/login"
                            className="rounded-xl bg-[#6d5dfc] px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-[#5848e8] transition"
                        >
                            Sign In as Admin
                        </Link>
                    </div>
                </div>
            </PageContainer>
        );
    }

    return (
        <PageContainer>
                    {/* Feedback Toast */}
                    {successMessage && (
                        <div className="mb-6 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 shadow-sm animate-in fade-in slide-in-from-top-2">
                            <div className="flex items-center gap-2">
                                <CheckCircle2 size={18} className="text-emerald-600" />
                                <span>{successMessage}</span>
                            </div>
                            <button onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
                                <X size={16} />
                            </button>
                        </div>
                    )}

                    {error && (
                        <div className="mb-6 flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800 shadow-sm">
                            <div className="flex items-center gap-2">
                                <AlertTriangle size={18} className="text-rose-600" />
                                <span>{error}</span>
                            </div>
                            <button onClick={() => setError(null)} className="text-rose-600 hover:text-rose-800">
                                <X size={16} />
                            </button>
                        </div>
                    )}

                    {/* Page Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="inline-flex items-center gap-1 rounded-md bg-[#eeebff] px-2.5 py-0.5 text-xs font-semibold text-[#5848e8]">
                                    <Shield size={12} />
                                    Executive Oversight
                                </span>
                                <span className="text-xs text-gray-400">•</span>
                                <span className="text-xs font-medium text-emerald-600 flex items-center gap-1">
                                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                    Live Operations
                                </span>
                            </div>

                            <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
                                Employee Oversight & Workforce Management
                            </h1>

                            <p className="mt-1 text-sm text-gray-500">
                                Oversee engineering personnel, manage credential security, audit operational diagnostics, and manage team assignments.
                            </p>
                        </div>

                        <div className="flex items-center gap-3">
                            <button
                                onClick={fetchData}
                                disabled={isLoading}
                                className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition active:scale-95 disabled:opacity-50"
                            >
                                <RefreshCw size={15} className={isLoading ? "animate-spin" : ""} />
                                Refresh
                            </button>

                            <button
                                onClick={() => setIsAddModalOpen(true)}
                                className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#5848e8] transition active:scale-95"
                            >
                                <UserPlus size={16} />
                                Add Employee
                            </button>
                        </div>
                    </div>

                    {/* Top KPI Metric Cards */}
                    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
                        {/* Total Workforce */}
                        <div className="relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white p-6 shadow-sm transition hover:shadow-md">
                            <div className="flex items-center justify-between">
                                <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                                    Total Workforce
                                </p>
                                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-[#6d5dfc]">
                                    <Users size={20} />
                                </div>
                            </div>
                            <div className="mt-4">
                                <p className="text-3xl font-extrabold tracking-tight text-gray-900">
                                    {overview?.total_employees ?? employees.length}
                                </p>
                                <p className="mt-1 text-xs text-gray-500 flex items-center gap-1.5">
                                    <span className="font-semibold text-emerald-600">
                                        {overview?.active_employees ?? 0} active
                                    </span>
                                    <span>•</span>
                                    <span>{overview?.inactive_employees ?? 0} inactive</span>
                                </p>
                            </div>
                        </div>

                        {/* Technicians & Engineers */}
                        <div className="relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white p-6 shadow-sm transition hover:shadow-md">
                            <div className="flex items-center justify-between">
                                <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                                    Field Engineers & Techs
                                </p>
                                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                                    <Briefcase size={20} />
                                </div>
                            </div>
                            <div className="mt-4">
                                <p className="text-3xl font-extrabold tracking-tight text-gray-900">
                                    {(overview?.role_breakdown?.technician || 0) + (overview?.role_breakdown?.engineer || 0)}
                                </p>
                                <p className="mt-1 text-xs text-gray-500">
                                    {overview?.role_breakdown?.engineer || 0} Process Engineers, {overview?.role_breakdown?.technician || 0} Line Techs
                                </p>
                            </div>
                        </div>

                        {/* Cases Handled */}
                        <div className="relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white p-6 shadow-sm transition hover:shadow-md">
                            <div className="flex items-center justify-between">
                                <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                                    Cases Supervised
                                </p>
                                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                                    <Activity size={20} />
                                </div>
                            </div>
                            <div className="mt-4">
                                <p className="text-3xl font-extrabold tracking-tight text-gray-900">
                                    {overview?.total_cases_monitored ?? 0}
                                </p>
                                <p className="mt-1 text-xs text-gray-500 flex items-center gap-1.5">
                                    <span className="font-semibold text-emerald-600">
                                        {overview?.resolved_cases_count ?? 0} resolved
                                    </span>
                                    <span>•</span>
                                    <span className="text-amber-600">
                                        {overview?.unresolved_cases_count ?? 0} active
                                    </span>
                                </p>
                            </div>
                        </div>

                        {/* Security & Access Health */}
                        <div className="relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white p-6 shadow-sm transition hover:shadow-md">
                            <div className="flex items-center justify-between">
                                <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                                    RBAC Security
                                </p>
                                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-[#5848e8]">
                                    <Shield size={20} />
                                </div>
                            </div>
                            <div className="mt-4">
                                <p className="text-3xl font-extrabold tracking-tight text-gray-900">
                                    100%
                                </p>
                                <p className="mt-1 text-xs text-gray-500">
                                    All accounts bounded to roles & departments
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Main Content Layout: Directory + Activity Audit */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* Left 2 Cols: Employee Management Table */}
                        <div className="lg:col-span-2 space-y-4">
                            <div className="rounded-2xl border border-gray-200/80 bg-white shadow-sm">
                                {/* Table Toolbar */}
                                <div className="border-b border-gray-100 p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                                    <div className="flex-1 relative">
                                        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                                        <input
                                            type="text"
                                            value={searchQuery}
                                            onChange={(e) => {
                                                setSearchQuery(e.target.value);
                                                setCurrentPage(1);
                                            }}
                                            placeholder="Search by name, email, or department..."
                                            className="h-10 w-full rounded-xl border border-gray-200 dark:border-gray-750 bg-gray-50/50 dark:bg-gray-850 pl-10 pr-4 text-sm text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 outline-none transition focus:border-[#6d5dfc] focus:bg-white dark:focus:bg-gray-800"
                                        />
                                    </div>

                                    <div className="flex items-center gap-3">
                                        {/* Role Filter */}
                                        <select
                                            value={roleFilter}
                                            onChange={(e) => {
                                                setRoleFilter(e.target.value);
                                                setCurrentPage(1);
                                            }}
                                            className="h-10 rounded-xl border border-gray-200 dark:border-gray-750 bg-white dark:bg-gray-850 px-3 text-xs font-medium text-gray-700 dark:text-gray-200 outline-none focus:border-[#6d5dfc]"
                                        >
                                            <option value="ALL">All Roles</option>
                                            <option value="ADMIN">Admin</option>
                                            <option value="ENGINEER">Engineer</option>
                                            <option value="TECHNICIAN">Technician</option>
                                            <option value="VIEWER">Viewer</option>
                                        </select>

                                        {/* Status Filter */}
                                        <select
                                            value={statusFilter}
                                            onChange={(e) => {
                                                setStatusFilter(e.target.value as any);
                                                setCurrentPage(1);
                                            }}
                                            className="h-10 rounded-xl border border-gray-200 dark:border-gray-750 bg-white dark:bg-gray-850 px-3 text-xs font-medium text-gray-700 dark:text-gray-200 outline-none focus:border-[#6d5dfc]"
                                        >
                                            <option value="ALL">All Status</option>
                                            <option value="ACTIVE">Active</option>
                                            <option value="INACTIVE">Inactive</option>
                                        </select>
                                    </div>
                                </div>

                                {/* Employees Table */}
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left text-sm">
                                        <thead className="bg-gray-50/60 text-[11px] font-semibold uppercase tracking-wider text-gray-500 border-b border-gray-100">
                                            <tr>
                                                <th className="px-5 py-3.5">
                                                    <button
                                                        type="button"
                                                        onClick={() => toggleSort("name")}
                                                        className="inline-flex items-center gap-1.5 font-semibold text-gray-700 hover:text-[#6d5dfc] transition uppercase tracking-wider"
                                                    >
                                                        <span>Employee</span>
                                                        <ArrowUpDown size={12} className={sortField === "name" ? "text-[#6d5dfc]" : "text-gray-400"} />
                                                    </button>
                                                </th>
                                                <th className="px-4 py-3.5">
                                                    <button
                                                        type="button"
                                                        onClick={() => toggleSort("role")}
                                                        className="inline-flex items-center gap-1.5 font-semibold text-gray-700 hover:text-[#6d5dfc] transition uppercase tracking-wider"
                                                    >
                                                        <span>Role</span>
                                                        <ArrowUpDown size={12} className={sortField === "role" ? "text-[#6d5dfc]" : "text-gray-400"} />
                                                    </button>
                                                </th>
                                                <th className="px-4 py-3.5">Department</th>
                                                <th className="px-4 py-3.5">Status</th>
                                                <th className="px-4 py-3.5">
                                                    <button
                                                        type="button"
                                                        onClick={() => toggleSort("cases")}
                                                        className="inline-flex items-center gap-1.5 font-semibold text-gray-700 hover:text-[#6d5dfc] transition uppercase tracking-wider"
                                                    >
                                                        <span>Activity</span>
                                                        <ArrowUpDown size={12} className={sortField === "cases" ? "text-[#6d5dfc]" : "text-gray-400"} />
                                                    </button>
                                                </th>
                                                <th className="px-5 py-3.5 text-right">Management</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100">
                                            {isLoading ? (
                                                <tr>
                                                    <td colSpan={6} className="py-12 text-center text-gray-500">
                                                        <div className="inline-flex items-center gap-2">
                                                            <RefreshCw size={18} className="animate-spin text-[#6d5dfc]" />
                                                            Loading employee records...
                                                        </div>
                                                    </td>
                                                </tr>
                                            ) : sortedEmployees.length === 0 ? (
                                                <tr>
                                                    <td colSpan={6} className="py-12 text-center text-gray-500">
                                                        No employees match the specified filters.
                                                    </td>
                                                </tr>
                                            ) : (
                                                paginatedEmployees.map((emp) => {
                                                    const initials =
                                                        (emp.first_name?.[0] || emp.email[0]).toUpperCase() +
                                                        (emp.last_name?.[0] || "").toUpperCase();
                                                    const isSelf = emp.id === user?.id;

                                                    return (
                                                        <tr key={emp.id} className="hover:bg-gray-50/80 transition-colors">
                                                            {/* User Details */}
                                                            <td className="px-5 py-4">
                                                                <div className="flex items-center gap-3">
                                                                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#eeebff] text-xs font-bold text-[#5848e8]">
                                                                        {initials}
                                                                    </div>
                                                                    <div>
                                                                        <div className="flex items-center gap-2">
                                                                            <p className="font-semibold text-gray-900 leading-tight">
                                                                                {emp.first_name || "-"} {emp.last_name || ""}
                                                                            </p>
                                                                            {isSelf && (
                                                                                <span className="rounded bg-gray-100 px-1.5 py-0.2 text-[10px] font-semibold text-gray-600">
                                                                                    You
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                        <p className="text-xs text-gray-500 mt-0.5">
                                                                            {emp.email}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            </td>

                                                            {/* Role Badge */}
                                                            <td className="px-4 py-4">
                                                                <span
                                                                    className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider border ${getRoleBadge(
                                                                        emp.role
                                                                    )}`}
                                                                >
                                                                    {emp.role}
                                                                </span>
                                                            </td>

                                                            {/* Department */}
                                                            <td className="px-4 py-4">
                                                                <span className="text-xs font-medium text-gray-700">
                                                                    {emp.department || "General"}
                                                                </span>
                                                            </td>

                                                            {/* Status */}
                                                            <td className="px-4 py-4">
                                                                <button
                                                                    onClick={() => handleToggleActive(emp)}
                                                                    disabled={isSelf}
                                                                    title={isSelf ? "Cannot deactivate yourself" : "Click to toggle active status"}
                                                                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition ${
                                                                        emp.is_active
                                                                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                                                            : "bg-rose-50 text-rose-700 border border-rose-200"
                                                                    } ${isSelf ? "cursor-not-allowed opacity-80" : "hover:scale-105"}`}
                                                                >
                                                                    <span
                                                                        className={`h-1.5 w-1.5 rounded-full ${
                                                                            emp.is_active ? "bg-emerald-500" : "bg-rose-500"
                                                                        }`}
                                                                    />
                                                                    {emp.is_active ? "Active" : "Disabled"}
                                                                </button>
                                                            </td>

                                                            {/* Workload Metrics */}
                                                            <td className="px-4 py-4">
                                                                <div className="text-xs text-gray-600">
                                                                    <span className="font-semibold text-gray-900">
                                                                        {emp.cases_handled}
                                                                    </span>{" "}
                                                                    confirmations
                                                                </div>
                                                                <div className="text-[11px] text-gray-400 mt-0.5">
                                                                    {emp.last_login
                                                                        ? `Active ${new Date(emp.last_login).toLocaleDateString()}`
                                                                        : "No logins recorded"}
                                                                </div>
                                                            </td>

                                                            {/* Action Tools */}
                                                            <td className="px-5 py-4 text-right">
                                                                <div className="inline-flex items-center gap-1">
                                                                    <button
                                                                        onClick={() => openEditModal(emp)}
                                                                        title="Edit Employee Information & Role"
                                                                        className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-900 transition"
                                                                    >
                                                                        <Edit3 size={15} />
                                                                    </button>

                                                                    <button
                                                                        onClick={() => openPasswordModal(emp)}
                                                                        title="Reset Password"
                                                                        className="rounded-lg p-1.5 text-gray-500 hover:bg-indigo-50 hover:text-[#6d5dfc] transition"
                                                                    >
                                                                        <KeyRound size={15} />
                                                                    </button>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    );
                                                })
                                            )}
                                        </tbody>
                                    </table>
                                </div>

                                {/* Pagination Controls */}
                                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 px-5 py-3.5 bg-gray-50/40 text-xs text-gray-500">
                                    <div>
                                        Showing <span className="font-semibold text-gray-800">{sortedEmployees.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1}</span> to{" "}
                                        <span className="font-semibold text-gray-800">{Math.min(currentPage * PAGE_SIZE, sortedEmployees.length)}</span> of{" "}
                                        <span className="font-semibold text-gray-800">{sortedEmployees.length}</span> employees
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <button
                                            type="button"
                                            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                                            disabled={currentPage === 1}
                                            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 shadow-2xs hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 transition"
                                        >
                                            <ChevronLeft size={13} />
                                            Previous
                                        </button>
                                        <span className="px-2 font-medium text-gray-600">
                                            Page {currentPage} of {totalPages}
                                        </span>
                                        <button
                                            type="button"
                                            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                                            disabled={currentPage >= totalPages}
                                            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 shadow-2xs hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 transition"
                                        >
                                            Next
                                            <ChevronRight size={13} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Right Col: Operations Audit Feed & Department Breakdown */}
                        <div className="space-y-6">
                            {/* Department Breakdown Card */}
                            <div className="rounded-2xl border border-gray-200/80 bg-white p-5 shadow-sm">
                                <div className="flex items-center gap-2 mb-4">
                                    <Building2 size={16} className="text-[#6d5dfc]" />
                                    <h3 className="font-bold text-gray-900 text-sm">
                                        Department Distribution
                                    </h3>
                                </div>
                                <div className="space-y-3">
                                    {overview &&
                                        Object.entries(overview.department_breakdown).map(([dept, count], i) => {
                                            const pct = Math.round((count / (overview.total_employees || 1)) * 100);
                                            return (
                                                <div key={`dept-${dept}-${i}`} className="space-y-1">
                                                    <div className="flex justify-between text-xs">
                                                        <span className="text-gray-700 font-medium truncate max-w-[180px]">
                                                            {dept}
                                                        </span>
                                                        <span className="text-gray-500 font-semibold">{count}</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-[#6d5dfc] rounded-full transition-all duration-500"
                                                            style={{ width: `${pct}%` }}
                                                        />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                </div>
                            </div>

                            {/* Live Operational Audit Log */}
                            <div className="rounded-2xl border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <Clock size={16} className="text-[#6d5dfc]" />
                                        <h3 className="font-bold text-gray-900 dark:text-white text-sm">
                                            Recent Operational Activities
                                        </h3>
                                    </div>
                                    <span className="text-[10px] font-bold uppercase tracking-wider rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-gray-600 dark:text-gray-300">
                                        AUDIT TRAIL
                                    </span>
                                </div>

                                {/* Audit Search & Category Tabs */}
                                <div className="space-y-2 mb-4">
                                    <div className="relative">
                                        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                                        <input
                                            type="text"
                                            value={auditSearch}
                                            onChange={(e) => setAuditSearch(e.target.value)}
                                            placeholder="Search audit actions, titles, actors..."
                                            className="h-8 w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-850 pl-8 pr-3 text-xs text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 outline-none focus:border-[#6d5dfc] focus:bg-white dark:focus:bg-gray-800 transition"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <button
                                            type="button"
                                            onClick={() => setAuditCategory("ALL")}
                                            className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                                                auditCategory === "ALL"
                                                    ? "bg-[#eeebff] dark:bg-[#5848e8]/30 text-[#5848e8] dark:text-[#a59bff] font-semibold"
                                                    : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 dark:hover:text-white"
                                            }`}
                                        >
                                            All ({overview?.recent_activities?.length || 0})
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setAuditCategory("CONFIRMATION")}
                                            className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                                                auditCategory === "CONFIRMATION"
                                                    ? "bg-purple-100 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 dark:border dark:border-purple-800/50 font-semibold"
                                                    : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 dark:hover:text-white"
                                            }`}
                                        >
                                            Confirmations
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setAuditCategory("LIFECYCLE")}
                                            className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                                                auditCategory === "LIFECYCLE"
                                                    ? "bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 dark:border dark:border-blue-800/50 font-semibold"
                                                    : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 dark:hover:text-white"
                                            }`}
                                        >
                                            Lifecycle
                                        </button>
                                    </div>
                                </div>

                                <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
                                    {filteredActivities.length > 0 ? (
                                        filteredActivities.map((act, i) => (
                                            <div
                                                key={`activity-${act.id || act.type || "item"}-${i}`}
                                                className="flex items-start gap-3 rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-850 p-3 text-xs hover:bg-gray-50 dark:hover:bg-gray-800 transition"
                                            >
                                                <div
                                                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg ${
                                                        act.type === "CAUSE_CONFIRMATION"
                                                            ? "bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400"
                                                            : "bg-blue-100 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400"
                                                    }`}
                                                >
                                                    <CheckCircle2 size={13} />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center justify-between gap-1">
                                                        <p className="font-semibold text-gray-900 dark:text-white truncate">
                                                            {act.title}
                                                        </p>
                                                        <span className="text-[10px] text-gray-400 shrink-0">
                                                            {act.timestamp
                                                                ? new Date(act.timestamp).toLocaleTimeString([], {
                                                                      hour: "2-digit",
                                                                      minute: "2-digit",
                                                                  })
                                                                : "Recent"}
                                                        </span>
                                                    </div>
                                                    <p className="text-[11px] text-gray-500 dark:text-gray-400 line-clamp-2 mt-0.5">
                                                        {act.description}
                                                    </p>
                                                    <div className="mt-1 flex items-center gap-1.5 text-[10px] text-gray-400">
                                                        <span className="font-medium text-gray-600 dark:text-gray-300">{act.actor}</span>
                                                        <span>•</span>
                                                        <span className="uppercase font-mono text-[9px] px-1 rounded bg-gray-200/70 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                                                            {act.type === "CAUSE_CONFIRMATION" ? "Confirmation" : "Lifecycle"}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <p className="text-xs text-gray-400 text-center py-6">
                                            {auditSearch || auditCategory !== "ALL"
                                                ? "No operational events match the current filter."
                                                : "No operational events recorded yet."}
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* MODAL 1: ADD EMPLOYEE */}
                    {isAddModalOpen && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-in fade-in">
                            <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
                                <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-4">
                                    <div className="flex items-center gap-2">
                                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                                            <UserPlus size={18} />
                                        </div>
                                        <h3 className="font-bold text-gray-900">Add New Employee</h3>
                                    </div>
                                    <button
                                        onClick={() => setIsAddModalOpen(false)}
                                        className="rounded-lg p-1 text-gray-400 hover:text-gray-600"
                                    >
                                        <X size={18} />
                                    </button>
                                </div>

                                <form onSubmit={handleCreateEmployee} className="space-y-4">
                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                First Name *
                                            </label>
                                            <input
                                                type="text"
                                                required
                                                value={addForm.first_name}
                                                onChange={(e) => setAddForm({ ...addForm, first_name: e.target.value })}
                                                placeholder="Alex"
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                Last Name
                                            </label>
                                            <input
                                                type="text"
                                                value={addForm.last_name || ""}
                                                onChange={(e) => setAddForm({ ...addForm, last_name: e.target.value })}
                                                placeholder="Chen"
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            />
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            Corporate Email *
                                        </label>
                                        <input
                                            type="email"
                                            required
                                            value={addForm.email}
                                            onChange={(e) => setAddForm({ ...addForm, email: e.target.value })}
                                            placeholder="alex.chen@example.com"
                                            className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            Initial Password *
                                        </label>
                                        <input
                                            type="password"
                                            required
                                            value={addForm.password}
                                            onChange={(e) => setAddForm({ ...addForm, password: e.target.value })}
                                            placeholder="••••••••"
                                            className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                Role
                                            </label>
                                            <select
                                                value={addForm.role}
                                                onChange={(e) => setAddForm({ ...addForm, role: e.target.value })}
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            >
                                                <option value="technician">Technician</option>
                                                <option value="engineer">Engineer</option>
                                                <option value="admin">Administrator</option>
                                                <option value="viewer">Viewer</option>
                                            </select>
                                        </div>

                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                Department
                                            </label>
                                            <input
                                                type="text"
                                                value={addForm.department || ""}
                                                onChange={(e) => setAddForm({ ...addForm, department: e.target.value })}
                                                placeholder="SMT Line 1"
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            />
                                        </div>
                                    </div>

                                    {addForm.role === "admin" && (
                                        <div className="rounded-xl border border-amber-200 bg-amber-50/90 p-3 text-xs text-amber-900 animate-in fade-in">
                                            <div className="flex items-start gap-2">
                                                <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
                                                <div>
                                                    <p className="font-semibold text-amber-900">Elevated Privilege Notice</p>
                                                    <p className="mt-0.5 text-[11px] text-amber-800 leading-relaxed">
                                                        This account will receive full administrative access to workforce credentials, system logs, and security controls.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    <div className="flex items-center gap-2 pt-2">
                                        <input
                                            type="checkbox"
                                            id="add-active"
                                            checked={addForm.is_active}
                                            onChange={(e) => setAddForm({ ...addForm, is_active: e.target.checked })}
                                            className="h-4 w-4 rounded text-[#6d5dfc] focus:ring-[#6d5dfc]"
                                        />
                                        <label htmlFor="add-active" className="text-xs text-gray-700 font-medium">
                                            Account is active and permitted to sign in immediately
                                        </label>
                                    </div>

                                    <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100">
                                        <button
                                            type="button"
                                            onClick={() => setIsAddModalOpen(false)}
                                            className="rounded-xl px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={actionLoading}
                                            className="rounded-xl bg-[#6d5dfc] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#5848e8] transition disabled:opacity-50"
                                        >
                                            {actionLoading ? "Creating..." : "Create Account"}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}

                    {/* MODAL 2: EDIT EMPLOYEE */}
                    {isEditModalOpen && selectedEmployee && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-in fade-in">
                            <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
                                <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-4">
                                    <div className="flex items-center gap-2">
                                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                                            <Edit3 size={18} />
                                        </div>
                                        <h3 className="font-bold text-gray-900">Edit Employee Details</h3>
                                    </div>
                                    <button
                                        onClick={() => setIsEditModalOpen(false)}
                                        className="rounded-lg p-1 text-gray-400 hover:text-gray-600"
                                    >
                                        <X size={18} />
                                    </button>
                                </div>

                                <form onSubmit={handleUpdateEmployee} className="space-y-4">
                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                First Name
                                            </label>
                                            <input
                                                type="text"
                                                value={editForm.first_name || ""}
                                                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                Last Name
                                            </label>
                                            <input
                                                type="text"
                                                value={editForm.last_name || ""}
                                                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            />
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            Corporate Email
                                        </label>
                                        <input
                                            type="email"
                                            value={editForm.email || ""}
                                            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                                            className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                Role
                                            </label>
                                            <select
                                                value={editForm.role}
                                                onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                                                disabled={selectedEmployee.id === user?.id}
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            >
                                                <option value="technician">Technician</option>
                                                <option value="engineer">Engineer</option>
                                                <option value="admin">Administrator</option>
                                                <option value="viewer">Viewer</option>
                                            </select>
                                        </div>

                                        <div>
                                            <label className="block text-xs font-semibold text-gray-700 mb-1">
                                                Department
                                            </label>
                                            <input
                                                type="text"
                                                value={editForm.department || ""}
                                                onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            />
                                        </div>
                                    </div>

                                    {editForm.role === "admin" && (
                                        <div className="rounded-xl border border-amber-200 bg-amber-50/90 p-3 text-xs text-amber-900 animate-in fade-in">
                                            <div className="flex items-start gap-2">
                                                <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
                                                <div>
                                                    <p className="font-semibold text-amber-900">Elevated Privilege Warning</p>
                                                    <p className="mt-0.5 text-[11px] text-amber-800 leading-relaxed">
                                                        Granting Administrator privileges provides unrestricted authority over workforce accounts, password resets, role modifications, and operational audit trails. Ensure this authorization complies with cleanroom security policy.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    <div className="flex items-center gap-2 pt-2">
                                        <input
                                            type="checkbox"
                                            id="edit-active"
                                            checked={editForm.is_active}
                                            disabled={selectedEmployee.id === user?.id}
                                            onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                                            className="h-4 w-4 rounded text-[#6d5dfc] focus:ring-[#6d5dfc]"
                                        />
                                        <label htmlFor="edit-active" className="text-xs text-gray-700 font-medium">
                                            Active Account
                                        </label>
                                    </div>

                                    <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100">
                                        <button
                                            type="button"
                                            onClick={() => setIsEditModalOpen(false)}
                                            className="rounded-xl px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={actionLoading}
                                            className="rounded-xl bg-[#6d5dfc] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#5848e8] transition disabled:opacity-50"
                                        >
                                            {actionLoading ? "Saving..." : "Save Changes"}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}

                    {/* MODAL 3: RESET PASSWORD */}
                    {isPasswordModalOpen && selectedEmployee && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-in fade-in">
                            <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
                                <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-4">
                                    <div className="flex items-center gap-2">
                                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-50 text-[#6d5dfc]">
                                            <KeyRound size={18} />
                                        </div>
                                        <h3 className="font-bold text-gray-900">Reset Employee Password</h3>
                                    </div>
                                    <button
                                        onClick={() => setIsPasswordModalOpen(false)}
                                        className="rounded-lg p-1 text-gray-400 hover:text-gray-600"
                                    >
                                        <X size={18} />
                                    </button>
                                </div>

                                <p className="text-xs text-gray-500 mb-4">
                                    Set a new password for <strong>{selectedEmployee.email}</strong>. The user will be required to authenticate with this password on next login.
                                </p>

                                <form onSubmit={handleResetPassword} className="space-y-4">
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            New Password
                                        </label>
                                        <div className="relative">
                                            <input
                                                type="text"
                                                required
                                                value={newPassword}
                                                onChange={(e) => setNewPassword(e.target.value)}
                                                placeholder="Enter new password"
                                                className="h-10 w-full rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-[#6d5dfc]"
                                            />
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => setNewPassword("TempPass@" + Math.floor(1000 + Math.random() * 9000))}
                                            className="mt-1.5 text-xs text-[#6d5dfc] hover:underline"
                                        >
                                            Generate secure temporary password
                                        </button>
                                    </div>

                                    <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100">
                                        <button
                                            type="button"
                                            onClick={() => setIsPasswordModalOpen(false)}
                                            className="rounded-xl px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={actionLoading || !newPassword}
                                            className="rounded-xl bg-[#6d5dfc] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#5848e8] transition disabled:opacity-50"
                                        >
                                            {actionLoading ? "Updating..." : "Confirm New Password"}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}
                </PageContainer>
    );
}
