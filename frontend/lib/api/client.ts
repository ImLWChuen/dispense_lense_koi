const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
    constructor(
        public status: number,
        public message: string,
        public data?: any
    ) {
        super(message);
        this.name = "ApiError";
    }
}

export const apiClient = {
    async get<T>(path: string, options: RequestInit = {}): Promise<T> {
        return this.request<T>(path, { ...options, method: "GET" });
    },

    async post<T>(path: string, data?: any, options: RequestInit = {}): Promise<T> {
        return this.request<T>(path, {
            ...options,
            method: "POST",
            body: data ? JSON.stringify(data) : undefined,
        });
    },

    async request<T>(path: string, options: RequestInit): Promise<T> {
        const url = `${API_BASE_URL}${path}`;
        const headers = new Headers(options.headers);

        if (options.body && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }

        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (!response.ok) {
            let errorMessage = "An error occurred while fetching the data.";
            let errorData;

            try {
                errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
                }
            } catch (e) {
                // Ignore parse errors if the response is not JSON
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
