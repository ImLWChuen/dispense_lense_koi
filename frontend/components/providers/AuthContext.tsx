"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api/client";

export type User = {
    id: string;
    email: string;
    first_name: string | null;
    last_name: string | null;
    is_active: boolean;
};

type AuthContextType = {
    user: User | null;
    token: string | null;
    login: (token: string, user: User) => void;
    logout: () => void;
    isLoading: boolean;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const logout = useCallback(() => {
        setToken(null);
        setUser(null);
        localStorage.removeItem("token");
        router.push("/login");
    }, [router]);

    useEffect(() => {
        const storedToken = localStorage.getItem("token");
        if (storedToken) {
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
                    setToken(storedToken);
                    setUser(data);
                })
                .catch(() => {
                    logout();
                })
                .finally(() => {
                    setIsLoading(false);
                });
        } else {
            Promise.resolve().then(() => {
                setIsLoading(false);
            });
        }
    }, [logout]);

    const login = (newToken: string, newUser: User) => {
        setToken(newToken);
        setUser(newUser);
        localStorage.setItem("token", newToken);
    };

    return (
        <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
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
