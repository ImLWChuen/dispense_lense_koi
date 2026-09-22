"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

export type ThemeMode = "light" | "dark" | "system";
export type DensityMode = "comfortable" | "compact";

interface ThemeContextType {
    theme: ThemeMode;
    density: DensityMode;
    resolvedTheme: "light" | "dark";
    setTheme: (mode: ThemeMode) => void;
    setDensity: (mode: DensityMode) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<ThemeMode>("light");
    const [density, setDensityState] = useState<DensityMode>("comfortable");
    const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("light");
    const [isMounted, setIsMounted] = useState(false);

    // Apply classes and attributes directly to document.documentElement
    const applyThemeAndDensity = useCallback((currentTheme: ThemeMode, currentDensity: DensityMode) => {
        if (typeof window === "undefined") return;

        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        const isDark = currentTheme === "dark" || (currentTheme === "system" && prefersDark);
        const resolved = isDark ? "dark" : "light";

        setResolvedTheme(resolved);

        // Apply dark mode class
        if (isDark) {
            document.documentElement.classList.add("dark");
        } else {
            document.documentElement.classList.remove("dark");
        }
        document.documentElement.setAttribute("data-theme", resolved);

        // Apply density class and attribute
        document.documentElement.setAttribute("data-density", currentDensity);
        if (currentDensity === "compact") {
            document.documentElement.classList.add("density-compact");
        } else {
            document.documentElement.classList.remove("density-compact");
        }
    }, []);

    // Initial load from localStorage
    useEffect(() => {
        setIsMounted(true);
        let savedTheme: ThemeMode = "light";
        let savedDensity: DensityMode = "comfortable";

        try {
            const t = localStorage.getItem("dispenselens_theme") as ThemeMode | null;
            if (t === "light" || t === "dark" || t === "system") {
                savedTheme = t;
            }
            const d = localStorage.getItem("dispenselens_density") as DensityMode | null;
            if (d === "comfortable" || d === "compact") {
                savedDensity = d;
            }
        } catch {
            // Storage access blocked or unavailable
        }

        setThemeState(savedTheme);
        setDensityState(savedDensity);
        applyThemeAndDensity(savedTheme, savedDensity);

        // Listen for OS color scheme changes when system mode is selected
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handleOsThemeChange = () => {
            const currentSaved = (localStorage.getItem("dispenselens_theme") as ThemeMode) || "light";
            if (currentSaved === "system") {
                applyThemeAndDensity("system", (localStorage.getItem("dispenselens_density") as DensityMode) || "comfortable");
            }
        };

        mediaQuery.addEventListener("change", handleOsThemeChange);
        return () => mediaQuery.removeEventListener("change", handleOsThemeChange);
    }, [applyThemeAndDensity]);

    const setTheme = useCallback((newTheme: ThemeMode) => {
        setThemeState(newTheme);
        try {
            localStorage.setItem("dispenselens_theme", newTheme);
        } catch {
            // Ignore
        }
        applyThemeAndDensity(newTheme, density);
    }, [density, applyThemeAndDensity]);

    const setDensity = useCallback((newDensity: DensityMode) => {
        setDensityState(newDensity);
        try {
            localStorage.setItem("dispenselens_density", newDensity);
        } catch {
            // Ignore
        }
        applyThemeAndDensity(theme, newDensity);
    }, [theme, applyThemeAndDensity]);

    return (
        <ThemeContext.Provider value={{ theme, density, resolvedTheme, setTheme, setDensity }}>
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
