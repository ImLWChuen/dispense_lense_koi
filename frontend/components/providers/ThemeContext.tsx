"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeContextType {
    theme: ThemeMode;
    setTheme: (theme: ThemeMode) => void;
    resolvedTheme: "light" | "dark";
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<ThemeMode>("light");
    const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("light");

    const applyTheme = useCallback((targetTheme: ThemeMode) => {
        if (typeof window === "undefined") return;

        const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        const isDark = targetTheme === "dark" || (targetTheme === "system" && systemPrefersDark);

        if (isDark) {
            document.documentElement.classList.add("dark");
            document.documentElement.setAttribute("data-theme", "dark");
            setResolvedTheme("dark");
        } else {
            document.documentElement.classList.remove("dark");
            document.documentElement.setAttribute("data-theme", "light");
            setResolvedTheme("light");
        }
    }, []);

    // Initial load from localStorage
    useEffect(() => {
        try {
            const stored = localStorage.getItem("dispenselens_theme") as ThemeMode | null;
            const initialTheme = stored || "light";
            setThemeState(initialTheme);
            applyTheme(initialTheme);
        } catch {
            // Ignore storage access errors
        }
    }, [applyTheme]);

    // Handle system theme changes
    useEffect(() => {
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handleChange = () => {
            if (theme === "system") {
                applyTheme("system");
            }
        };

        mediaQuery.addEventListener("change", handleChange);
        return () => mediaQuery.removeEventListener("change", handleChange);
    }, [theme, applyTheme]);

    const setTheme = (newTheme: ThemeMode) => {
        setThemeState(newTheme);
        try {
            localStorage.setItem("dispenselens_theme", newTheme);
        } catch {
            // Ignore
        }
        applyTheme(newTheme);
    };

    return (
        <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error("useTheme must be used within a ThemeProvider");
    }
    return context;
}
