import { apiClient } from "./client";

export interface EmployeeSummary {
    id: string;
    email: string;
    first_name: string | null;
    last_name: string | null;
    role: string;
    department: string | null;
    is_active: boolean;
    created_at: string | null;
    last_login: string | null;
    cases_handled: number;
    actions_performed: number;
}

export interface AdminActivityItem {
    id: string;
    type: string;
    title: string;
    description: string;
    actor: string;
    timestamp: string | null;
}

export interface AdminOverviewStats {
    total_employees: number;
    active_employees: number;
    inactive_employees: number;
    role_breakdown: Record<string, number>;
    department_breakdown: Record<string, number>;
    total_cases_monitored: number;
    resolved_cases_count: number;
    unresolved_cases_count: number;
    recent_activities: AdminActivityItem[];
}

export interface CreateEmployeeRequest {
    email: string;
    password: string;
    first_name: string;
    last_name?: string;
    role: string;
    department?: string;
    is_active?: boolean;
}

export interface UpdateEmployeeRequest {
    email?: string;
    first_name?: string;
    last_name?: string;
    role?: string;
    department?: string;
    is_active?: boolean;
}

export const adminApi = {
    async getOverview(): Promise<AdminOverviewStats> {
        return apiClient.get<AdminOverviewStats>("/admin/overview");
    },

    async listEmployees(params?: {
        search?: string;
        role?: string;
        is_active?: boolean;
    }): Promise<EmployeeSummary[]> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.set("search", params.search);
        if (params?.role && params.role !== "ALL") queryParams.set("role", params.role);
        if (params?.is_active !== undefined) queryParams.set("is_active", String(params.is_active));

        const queryString = queryParams.toString();
        const path = queryString ? `/admin/users?${queryString}` : "/admin/users";
        return apiClient.get<EmployeeSummary[]>(path);
    },

    async createEmployee(data: CreateEmployeeRequest): Promise<EmployeeSummary> {
        return apiClient.post<EmployeeSummary>("/admin/users", data);
    },

    async updateEmployee(userId: string, data: UpdateEmployeeRequest): Promise<EmployeeSummary> {
        return apiClient.request<EmployeeSummary>(`/admin/users/${userId}`, {
            method: "PUT",
            body: JSON.stringify(data),
        });
    },

    async resetPassword(userId: string, newPassword: string): Promise<{ message: string }> {
        return apiClient.post<{ message: string }>(`/admin/users/${userId}/reset-password`, {
            new_password: newPassword,
        });
    },

    async deleteEmployee(userId: string, hardDelete: boolean = false): Promise<{ message: string }> {
        return apiClient.request<{ message: string }>(`/admin/users/${userId}?hard_delete=${hardDelete}`, {
            method: "DELETE",
        });
    },
};
