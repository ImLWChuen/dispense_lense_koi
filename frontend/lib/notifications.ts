export interface AppNotification {
    id: string;
    type: "CASE_CREATED" | "CAUSE_CONFIRMED" | "CASE_COMPLETED" | "SYSTEM";
    title: string;
    message: string;
    timestamp: string; // ISO string
    read: boolean;
    link?: string;
}

const STORAGE_KEY = "dispenseiq_notifications";

// Initial seed notifications to ensure realistic data is present on first load
const SEED_NOTIFICATIONS: AppNotification[] = [
    {
        id: "seed-notif-1",
        type: "CASE_COMPLETED",
        title: "Case Resolved",
        message: "Case 546cac0a (Too Little Material) on Dispensing Line A has been verified and resolved.",
        timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(), // 15 mins ago
        read: false,
        link: "/diagnosis/546cac0a-34aa-4307-8263-f3b2da6c30a4",
    },
    {
        id: "seed-notif-2",
        type: "CAUSE_CONFIRMED",
        title: "Root Cause Confirmed",
        message: "Root cause 'Nozzle Restriction' confirmed for Case 546cac0a.",
        timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(), // 45 mins ago
        read: false,
        link: "/diagnosis/546cac0a-34aa-4307-8263-f3b2da6c30a4",
    },
    {
        id: "seed-notif-3",
        type: "CASE_CREATED",
        title: "New Diagnostic Case",
        message: "Case 9ee072ae registered for Inconsistent Size on Dispensing Line B.",
        timestamp: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), // 2 hours ago
        read: true,
        link: "/diagnosis/9ee072ae-1331-48a5-a0db-194ce7077963",
    },
    {
        id: "seed-notif-4",
        type: "SYSTEM",
        title: "Live Engine Connected",
        message: "DispenseIQ real-time diagnostic engine synchronized successfully.",
        timestamp: new Date(Date.now() - 24 * 3600 * 1000).toISOString(), // 1 day ago
        read: true,
        link: "/dashboard",
    },
];

export const notificationService = {
    getNotifications(): AppNotification[] {
        if (typeof window === "undefined") return [];
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                // Seed initial notifications
                localStorage.setItem(STORAGE_KEY, JSON.stringify(SEED_NOTIFICATIONS));
                return SEED_NOTIFICATIONS;
            }
            return JSON.parse(raw);
        } catch {
            return SEED_NOTIFICATIONS;
        }
    },

    saveNotifications(notifications: AppNotification[]) {
        if (typeof window === "undefined") return;
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications));
            window.dispatchEvent(new CustomEvent("dispenseiq_notifications_updated"));
        } catch (e) {
            console.error("Failed to save notifications:", e);
        }
    },

    addNotification(item: Omit<AppNotification, "id" | "timestamp" | "read"> & { read?: boolean }): AppNotification {
        const current = this.getNotifications();
        const newNotif: AppNotification = {
            id: `notif-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
            timestamp: new Date().toISOString(),
            read: item.read ?? false,
            ...item,
        };
        const updated = [newNotif, ...current].slice(0, 50); // Keep last 50
        this.saveNotifications(updated);
        return newNotif;
    },

    markAsRead(id: string) {
        const current = this.getNotifications();
        const updated = current.map((n) => (n.id === id ? { ...n, read: true } : n));
        this.saveNotifications(updated);
    },

    markAllAsRead() {
        const current = this.getNotifications();
        const updated = current.map((n) => ({ ...n, read: true }));
        this.saveNotifications(updated);
    },

    clearAll() {
        this.saveNotifications([]);
    },

    getUnreadCount(): number {
        return this.getNotifications().filter((n) => !n.read).length;
    },
};
