export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
    constructor(
        public status: number,
        public message: string,
        public data?: unknown
    ) {
        super(message);
        this.name = "ApiError";
    }
}

export const apiClient = {
    async get<T>(path: string, options: RequestInit = {}): Promise<T> {
        return this.request<T>(path, { ...options, method: "GET" });
    },

    async post<T>(path: string, data?: unknown, options: RequestInit = {}): Promise<T> {
        const isFormData = data instanceof FormData;
        return this.request<T>(path, {
            ...options,
            method: "POST",
            body: isFormData ? data : (data !== undefined ? JSON.stringify(data) : undefined),
        });
    },

    async patch<T>(path: string, data?: unknown, options: RequestInit = {}): Promise<T> {
        const isFormData = data instanceof FormData;
        return this.request<T>(path, {
            ...options,
            method: "PATCH",
            body: isFormData ? data : (data !== undefined ? JSON.stringify(data) : undefined),
        });
    },

    async put<T>(path: string, data?: unknown, options: RequestInit = {}): Promise<T> {
        const isFormData = data instanceof FormData;
        return this.request<T>(path, {
            ...options,
            method: "PUT",
            body: isFormData ? data : (data !== undefined ? JSON.stringify(data) : undefined),
        });
    },

    async request<T>(path: string, options: RequestInit): Promise<T> {
        const url = `${API_BASE_URL}${path}`;
        const headers = new Headers(options.headers);

        if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }

        if (typeof window !== "undefined" && !headers.has("Authorization")) {
            const token = localStorage.getItem("token");
            if (token) {
                headers.set("Authorization", `Bearer ${token}`);
            }
        }

        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (!response.ok) {
            let errorMessage = "An error occurred while communicating with the server.";
            let errorData: unknown;

            try {
                errorData = await response.json();
                if (errorData && typeof errorData === "object" && "detail" in errorData) {
                    const detail = (errorData as { detail: unknown }).detail;
                    if (typeof detail === "string") {
                        errorMessage = detail;
                    } else if (Array.isArray(detail)) {
                        const messages = detail
                            .map((d: { msg?: string; loc?: (string | number)[] }) => {
                                const field = d.loc ? d.loc.filter((x) => x !== "body").join(".") : "";
                                return field ? `${field}: ${d.msg}` : d.msg;
                            })
                            .filter(Boolean);
                        errorMessage = messages.length > 0 ? messages.join("; ") : "Invalid input parameters.";
                    } else {
                        errorMessage = JSON.stringify(detail);
                    }
                }
            } catch {
                // Ignore parse errors if response is not JSON
            }

            if (response.status === 413) {
                errorMessage = "Payload too large. Uploaded file must not exceed 10 MB.";
            } else if (response.status === 500) {
                errorMessage = "An unexpected error occurred during processing. Please try again.";
            }

            throw new ApiError(response.status, errorMessage, errorData);
        }

        // Return null for 204 No Content
        if (response.status === 204) {
            return null as unknown as T;
        }

        return response.json();
    },
};
