/**
 * Auth API Service
 *
 * Client interface for user identity and profile management:
 * - Fetching current session identity (`/auth/me`).
 * - Updating name, contact details, and department allocations.
 * - Changing password credentials.
 */

import { apiClient } from "./client";
import { User } from "@/components/providers/AuthContext";

/**
 * Payload for updating operator user profile fields.
 */
export interface UpdateProfileRequest {
    first_name?: string;
    last_name?: string;
    department?: string;
}

/**
 * Payload for updating operator security password.
 */
export interface ChangePasswordRequest {
    current_password: string;
    new_password: string;
}

export const authApi = {
    async getMe(): Promise<User> {
        return apiClient.get<User>("/auth/me");
    },

    async updateProfile(data: UpdateProfileRequest): Promise<User> {
        return apiClient.patch<User>("/auth/me", data);
    },

    async changePassword(data: ChangePasswordRequest): Promise<{ message: string }> {
        return apiClient.post<{ message: string }>("/auth/me/change-password", data);
    },
};
