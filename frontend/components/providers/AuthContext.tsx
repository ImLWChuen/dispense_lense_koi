"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { API_BASE_URL } from "@/lib/api/client";

export type User = {
    id: string;
    email: string;
    first_name: string | null;
    last_name: string | null;
    role: string;
    department?: string | null;
    is_active: boolean;
    created_at?: string | null;
    last_login?: string | null;
};

type AuthContextType = {
    user: User | null;
    token: string | null;
    isAdmin: boolean;
    login: (token: string, user: User) => void;
    logout: () => void;
    updateUser: (updatedFields: Partial<User>) => void;
    refreshUser: () => Promise<void>;
    isLoading: boolean;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const logout = useCallback(() => {
        setToken(null);
        setUser(null);
        localStorage.removeItem("token");
        window.location.href = "/login";
    }, []);

    useEffect(() => {
        const storedToken = localStorage.getItem("token");
        if (storedToken) {
            setToken(storedToken);
            // Fetch user info
            fetch(`${API_BASE_URL}/auth/me`, {
                headers: {
                    Authorization: `Bearer ${storedToken}`,
                },
            })
                .then((res) => {
                    if (res.ok) {
                        return res.json();
                    } else {
                        throw new Error("Failed to authenticate");
                    }
                })
                .then((data) => {
                    setUser(data);
                })
                .catch(() => {
                    logout();
                })
                .finally(() => {
                    setIsLoading(false);
                });
        } else {
            setIsLoading(false);
        }
    }, [logout]);

    const login = (newToken: string, newUser: User) => {
        setToken(newToken);
        setUser(newUser);
        localStorage.setItem("token", newToken);
    };

    const updateUser = (updatedFields: Partial<User>) => {
        setUser((prev) => (prev ? { ...prev, ...updatedFields } : null));
    };

    const refreshUser = async () => {
        const storedToken = localStorage.getItem("token");
        if (!storedToken) return;
        try {
            const res = await fetch(`${API_BASE_URL}/auth/me`, {
                headers: {
                    Authorization: `Bearer ${storedToken}`,
                },
            });
            if (res.ok) {
                const data = await res.json();
                setUser(data);
            }
        } catch (err) {
            console.warn("Failed to refresh user:", err);
        }
    };

    const isAdmin = user?.role === "admin";

    return (
        <AuthContext.Provider value={{ user, token, isAdmin, login, logout, updateUser, refreshUser, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
