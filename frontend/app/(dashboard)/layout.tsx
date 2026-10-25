/**
 * Authenticated Dashboard Route Group Layout
 *
 * Wraps all main portal routes in the interactive DashboardShell
 * (sidebar navigation, top header, real-time telemetry ribbon, and command palette).
 */

import DashboardShell from "@/components/layout/DashboardShell";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <DashboardShell>{children}</DashboardShell>;
}
