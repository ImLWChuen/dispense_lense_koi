"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import CommandPalette from "@/components/layout/CommandPalette";
import LiveTelemetryRibbon from "@/components/telemetry/LiveTelemetryRibbon";

interface DashboardShellProps {
    children: React.ReactNode;
}

export default function DashboardShell({ children }: DashboardShellProps) {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

    // Global keyboard shortcut: Ctrl+K or Cmd+K
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setIsCommandPaletteOpen((prev) => !prev);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, []);

    return (
        <div className="min-h-screen bg-[#f7f8fa]">
            {/* Sidebar (Desktop fixed rail & Mobile slide-over drawer) */}
            <Sidebar
                isMobileOpen={isMobileMenuOpen}
                onCloseMobile={() => setIsMobileMenuOpen(false)}
            />

            {/* Backdrop overlay for mobile drawer */}
            {isMobileMenuOpen && (
                <div
                    className="fixed inset-0 z-40 bg-gray-900/50 backdrop-blur-xs lg:hidden transition-opacity"
                    onClick={() => setIsMobileMenuOpen(false)}
                    aria-hidden="true"
                />
            )}

            {/* Main Content Area (Offset by sidebar width on desktop lg:pl-64) */}
            <div className="flex min-h-screen flex-col lg:pl-64">
                <Header
                    onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
                    onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
                />

                <LiveTelemetryRibbon />

                <div className="flex-1">
                    {children}
                </div>
            </div>

            {/* Universal Command Palette (Ctrl+K / ⌘K) */}
            <CommandPalette
                isOpen={isCommandPaletteOpen}
                onClose={() => setIsCommandPaletteOpen(false)}
            />
        </div>
    );
}
