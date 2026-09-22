"use client";

import { useState, useEffect } from "react";
import {
    User as UserIcon,
    Bell,
    Shield,
    Palette,
    LogOut,
    CheckCircle2,
    AlertTriangle,
    Save,
    KeyRound,
    Eye,
    EyeOff,
    Sun,
    Moon,
    Monitor,
    Building2,
    Lock,
    Sparkles,
    Check,
    Smartphone,
    Laptop,
} from "lucide-react";

import PageContainer from "@/components/layout/PageContainer";
import { useAuth } from "@/components/providers/AuthContext";
import { useTheme } from "@/components/providers/ThemeProvider";
import { authApi } from "@/lib/api/auth";

export default function SettingsPage() {
    const { user, logout, updateUser } = useAuth();
    const { theme, density, setTheme, setDensity } = useTheme();
    const [activeTab, setActiveTab] = useState<"profile" | "notifications" | "security" | "appearance">("profile");

    // Feedback states
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    // Profile form state
    const [profileForm, setProfileForm] = useState({
        first_name: "",
        last_name: "",
        department: "",
    });

    // Security / Password form state
    const [passwordForm, setPasswordForm] = useState({
        current_password: "",
        new_password: "",
        confirm_password: "",
    });
    const [showCurrentPass, setShowCurrentPass] = useState(false);
    const [showNewPass, setShowNewPass] = useState(false);
    const [showConfirmPass, setShowConfirmPass] = useState(false);

    // Notification preferences state
    const [notificationPrefs, setNotificationPrefs] = useState({
        newCases: true,
        defectAlerts: true,
        shiftDigest: false,
        causeConfirmations: true,
    });

    // Populate user profile details when user is loaded
    useEffect(() => {
        if (user) {
            setProfileForm({
                first_name: user.first_name || "",
                last_name: user.last_name || "",
                department: user.department || "SMT Line 1 - Dispensing",
            });
        }
    }, [user]);

    // Load notification preferences from localStorage on mount
    useEffect(() => {
        const storedNotifs = localStorage.getItem("dispenselens_notification_prefs");
        if (storedNotifs) {
            try {
                setNotificationPrefs(JSON.parse(storedNotifs));
            } catch {
                // Ignore parse errors
            }
        }
    }, []);

    // Auto-clear toast feedback
    useEffect(() => {
        if (successMessage) {
            const timer = setTimeout(() => setSuccessMessage(null), 4000);
            return () => clearTimeout(timer);
        }
    }, [successMessage]);

    useEffect(() => {
        if (errorMessage) {
            const timer = setTimeout(() => setErrorMessage(null), 5000);
            return () => clearTimeout(timer);
        }
    }, [errorMessage]);

    // Handle Profile Save
    const handleProfileSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSaving(true);
        setErrorMessage(null);
        setSuccessMessage(null);

        try {
            const updated = await authApi.updateProfile({
                first_name: profileForm.first_name.trim(),
                last_name: profileForm.last_name.trim(),
                department: profileForm.department.trim(),
            });

            updateUser({
                first_name: updated.first_name,
                last_name: updated.last_name,
                department: updated.department,
            });

            setSuccessMessage("Profile information updated successfully.");
        } catch (err: any) {
            console.error("Profile update error:", err);
            setErrorMessage(err.message || "Failed to update profile.");
        } finally {
            setIsSaving(false);
        }
    };

    // Handle Password Reset
    const handlePasswordSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!passwordForm.current_password) {
            setErrorMessage("Please enter your current password.");
            return;
        }

        if (passwordForm.new_password.length < 4) {
            setErrorMessage("New password must be at least 4 characters long.");
            return;
        }

        if (passwordForm.new_password !== passwordForm.confirm_password) {
            setErrorMessage("New passwords do not match. Please re-enter.");
            return;
        }

        setIsSaving(true);
        setErrorMessage(null);
        setSuccessMessage(null);

        try {
            await authApi.changePassword({
                current_password: passwordForm.current_password,
                new_password: passwordForm.new_password,
            });

            setPasswordForm({
                current_password: "",
                new_password: "",
                confirm_password: "",
            });

            setSuccessMessage("Password updated successfully. Please use your new password next time you sign in.");
        } catch (err: any) {
            console.error("Password change error:", err);
            setErrorMessage(err.message || "Failed to update password.");
        } finally {
            setIsSaving(false);
        }
    };

    // Handle Theme Change
    const handleThemeSelect = (selectedTheme: "light" | "dark" | "system") => {
        setTheme(selectedTheme);
        setSuccessMessage(`Theme updated to ${selectedTheme === "system" ? "System Default" : selectedTheme.toUpperCase()}.`);
    };

    // Handle Density Change
    const handleDensitySelect = (selectedDensity: "comfortable" | "compact") => {
        setDensity(selectedDensity);
        setSuccessMessage(`Display density set to ${selectedDensity.toUpperCase()}.`);
    };

    // Handle Notification Preferences Save
    const handleSaveNotificationPrefs = () => {
        localStorage.setItem("dispenselens_notification_prefs", JSON.stringify(notificationPrefs));
        setSuccessMessage("Notification preferences saved successfully.");
    };

    const tabs = [
        { id: "profile", label: "Profile", icon: UserIcon },
        { id: "security", label: "Security & Password", icon: Shield },
        { id: "appearance", label: "Appearance & Theme", icon: Palette },
        { id: "notifications", label: "Notifications", icon: Bell },
    ];

    const initials =
        ((user?.first_name?.[0] || "") + (user?.last_name?.[0] || "") ||
            user?.email?.[0] ||
            "U"
        ).toUpperCase();

    const roleBadge = (role: string = "technician") => {
        switch (role.toLowerCase()) {
            case "admin":
                return "bg-purple-100 text-purple-700 border-purple-200";
            case "engineer":
                return "bg-blue-100 text-blue-700 border-blue-200";
            default:
                return "bg-emerald-100 text-emerald-700 border-emerald-200";
        }
    };

    return (
        <PageContainer>
            {/* Header */}
            <div className="mb-8">
                <p className="text-sm font-semibold tracking-wide text-[#6d5dfc]">
                    Preferences
                </p>
                <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                    System & Account Settings
                </h1>
                <p className="mt-1 text-sm text-gray-500">
                    Manage operator credentials, workstation appearance, cleanroom notifications, and access preferences.
                </p>
            </div>

            {/* Layout */}
            <div className="flex flex-col md:flex-row gap-8">
                {/* Navigation Sidebar */}
                <div className="w-full md:w-64 flex-shrink-0 space-y-1.5">
                    {tabs.map((tab) => {
                        const Icon = tab.icon;
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => {
                                    setActiveTab(tab.id as any);
                                    setErrorMessage(null);
                                }}
                                className={`w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition ${
                                    isActive
                                        ? "bg-[#eeebff] dark:bg-[#5848e8]/30 text-[#5848e8] dark:text-[#a59bff] font-bold shadow-xs border border-transparent dark:border-[#6d5dfc]/40"
                                        : "text-gray-600 dark:text-gray-300 hover:bg-gray-100/80 dark:hover:bg-gray-800 dark:hover:text-white"
                                }`}
                            >
                                <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
                                <span>{tab.label}</span>
                            </button>
                        );
                    })}

                    <div className="pt-4 mt-4 border-t border-gray-200/80 dark:border-gray-800">
                        <button
                            type="button"
                            onClick={logout}
                            className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition"
                        >
                            <LogOut size={18} strokeWidth={1.8} />
                            <span>Sign Out</span>
                        </button>
                    </div>
                </div>

                {/* Content Panel */}
                <div className="flex-1 max-w-3xl space-y-4">
                    {/* Feedback Banners */}
                    {successMessage && (
                        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-semibold text-emerald-800 shadow-sm animate-in fade-in">
                            <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
                            <span>{successMessage}</span>
                        </div>
                    )}

                    {errorMessage && (
                        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-800 shadow-sm animate-in fade-in">
                            <AlertTriangle size={16} className="text-rose-600 shrink-0" />
                            <span>{errorMessage}</span>
                        </div>
                    )}

                    {/* TAB 1: PROFILE INFORMATION */}
                    {activeTab === "profile" && (
                        <div className="rounded-2xl border border-gray-200 bg-white p-7 shadow-sm">
                            <div className="border-b border-gray-100 pb-5 mb-6">
                                <h2 className="text-lg font-bold text-gray-900">Operator Profile</h2>
                                <p className="text-xs text-gray-500 mt-0.5">
                                    Personal information and workstation department assignments.
                                </p>
                            </div>

                            <form onSubmit={handleProfileSubmit} className="space-y-6">
                                {/* Operator Avatar Row */}
                                <div className="flex items-center gap-5 p-4 rounded-xl bg-gray-50/70 border border-gray-100">
                                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#eeebff] text-xl font-bold uppercase text-[#5848e8] shadow-2xs">
                                        {initials}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <p className="font-semibold text-gray-900 text-sm">
                                                {user?.first_name || "Operator"} {user?.last_name || ""}
                                            </p>
                                            <span
                                                className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${roleBadge(
                                                    user?.role
                                                )}`}
                                            >
                                                {user?.role || "Technician"}
                                            </span>
                                        </div>
                                        <p className="text-xs text-gray-500 mt-0.5">{user?.email}</p>
                                        <p className="text-[11px] text-gray-400 mt-1">
                                            Account ID: <span className="font-mono">{user?.id?.slice(0, 8)}...</span>
                                        </p>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            First Name
                                        </label>
                                        <input
                                            type="text"
                                            value={profileForm.first_name}
                                            onChange={(e) =>
                                                setProfileForm({ ...profileForm, first_name: e.target.value })
                                            }
                                            className="h-10 w-full rounded-xl border border-gray-200 bg-white px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-2 focus:ring-[#6d5dfc]/10"
                                            placeholder="Operator first name"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            Last Name
                                        </label>
                                        <input
                                            type="text"
                                            value={profileForm.last_name}
                                            onChange={(e) =>
                                                setProfileForm({ ...profileForm, last_name: e.target.value })
                                            }
                                            className="h-10 w-full rounded-xl border border-gray-200 bg-white px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-2 focus:ring-[#6d5dfc]/10"
                                            placeholder="Operator last name"
                                        />
                                    </div>

                                    <div className="md:col-span-2">
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            Corporate Email Address
                                        </label>
                                        <div className="relative">
                                            <input
                                                type="email"
                                                value={user?.email || ""}
                                                readOnly
                                                className="h-10 w-full rounded-xl border border-gray-200 bg-gray-100/70 px-3 text-sm text-gray-500 outline-none cursor-not-allowed"
                                            />
                                            <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded bg-gray-200/80 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
                                                Primary SSO
                                            </span>
                                        </div>
                                    </div>

                                    <div className="md:col-span-2">
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            Assigned Production Department / Line
                                        </label>
                                        <input
                                            type="text"
                                            value={profileForm.department}
                                            onChange={(e) =>
                                                setProfileForm({ ...profileForm, department: e.target.value })
                                            }
                                            className="h-10 w-full rounded-xl border border-gray-200 bg-white px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-2 focus:ring-[#6d5dfc]/10"
                                            placeholder="e.g. SMT Line 1 - Fluid Dispensing"
                                        />
                                    </div>
                                </div>

                                <div className="pt-4 border-t border-gray-100 flex items-center justify-end">
                                    <button
                                        type="submit"
                                        disabled={isSaving}
                                        className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#5848e8] disabled:opacity-50"
                                    >
                                        <Save size={16} />
                                        {isSaving ? "Saving..." : "Save Profile Changes"}
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}

                    {/* TAB 2: SECURITY & PASSWORD */}
                    {activeTab === "security" && (
                        <div className="rounded-2xl border border-gray-200 bg-white p-7 shadow-sm">
                            <div className="border-b border-gray-100 pb-5 mb-6">
                                <div className="flex items-center gap-2">
                                    <KeyRound size={20} className="text-[#6d5dfc]" />
                                    <h2 className="text-lg font-bold text-gray-900">Security Credentials</h2>
                                </div>
                                <p className="text-xs text-gray-500 mt-0.5">
                                    Change your password and inspect active cleanroom authentication sessions.
                                </p>
                            </div>

                            <form onSubmit={handlePasswordSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                                        Current Password
                                    </label>
                                    <div className="relative">
                                        <input
                                            type={showCurrentPass ? "text" : "password"}
                                            value={passwordForm.current_password}
                                            onChange={(e) =>
                                                setPasswordForm({ ...passwordForm, current_password: e.target.value })
                                            }
                                            className="h-10 w-full rounded-xl border border-gray-200 bg-white pl-3 pr-10 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-2 focus:ring-[#6d5dfc]/10"
                                            placeholder="Enter existing password"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowCurrentPass(!showCurrentPass)}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                        >
                                            {showCurrentPass ? <EyeOff size={16} /> : <Eye size={16} />}
                                        </button>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            New Password
                                        </label>
                                        <div className="relative">
                                            <input
                                                type={showNewPass ? "text" : "password"}
                                                value={passwordForm.new_password}
                                                onChange={(e) =>
                                                    setPasswordForm({ ...passwordForm, new_password: e.target.value })
                                                }
                                                className="h-10 w-full rounded-xl border border-gray-200 bg-white pl-3 pr-10 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-2 focus:ring-[#6d5dfc]/10"
                                                placeholder="Min. 4 characters"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowNewPass(!showNewPass)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                            >
                                                {showNewPass ? <EyeOff size={16} /> : <Eye size={16} />}
                                            </button>
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                                            Confirm New Password
                                        </label>
                                        <div className="relative">
                                            <input
                                                type={showConfirmPass ? "text" : "password"}
                                                value={passwordForm.confirm_password}
                                                onChange={(e) =>
                                                    setPasswordForm({ ...passwordForm, confirm_password: e.target.value })
                                                }
                                                className="h-10 w-full rounded-xl border border-gray-200 bg-white pl-3 pr-10 text-sm outline-none transition focus:border-[#6d5dfc] focus:ring-2 focus:ring-[#6d5dfc]/10"
                                                placeholder="Re-enter new password"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowConfirmPass(!showConfirmPass)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                            >
                                                {showConfirmPass ? <EyeOff size={16} /> : <Eye size={16} />}
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                {/* Cleanroom Security Session Status Card */}
                                <div className="mt-4 rounded-xl border border-gray-100 bg-gray-50/70 p-4 text-xs space-y-2">
                                    <div className="flex items-center gap-2 text-gray-800 font-semibold">
                                        <Lock size={14} className="text-[#6d5dfc]" />
                                        <span>Active Session Security</span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-600 pt-1">
                                        <div>
                                            <span className="text-gray-400">Authentication:</span> JWT Bearer Token
                                        </div>
                                        <div>
                                            <span className="text-gray-400">Account Status:</span> Active & Verified
                                        </div>
                                        <div>
                                            <span className="text-gray-400">Security Clearance:</span>{" "}
                                            {user?.role?.toUpperCase() || "STANDARD"}
                                        </div>
                                        <div>
                                            <span className="text-gray-400">Last Login:</span>{" "}
                                            {user?.last_login
                                                ? new Date(user.last_login).toLocaleString([], {
                                                      dateStyle: "short",
                                                      timeStyle: "short",
                                                  })
                                                : "Active now"}
                                        </div>
                                    </div>
                                </div>

                                <div className="pt-4 border-t border-gray-100 flex items-center justify-end">
                                    <button
                                        type="submit"
                                        disabled={isSaving}
                                        className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#5848e8] disabled:opacity-50"
                                    >
                                        <KeyRound size={16} />
                                        {isSaving ? "Updating..." : "Update Password"}
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}

                    {/* TAB 3: APPEARANCE & THEME */}
                    {activeTab === "appearance" && (
                        <div className="rounded-2xl border border-gray-200 bg-white p-7 shadow-sm">
                            <div className="border-b border-gray-100 pb-5 mb-6">
                                <div className="flex items-center gap-2">
                                    <Palette size={20} className="text-[#6d5dfc]" />
                                    <h2 className="text-lg font-bold text-gray-900">Workstation Appearance</h2>
                                </div>
                                <p className="text-xs text-gray-500 mt-0.5">
                                    Customize monitor contrast and visual display modes for cleanroom inspection stations.
                                </p>
                            </div>

                            <div className="space-y-6">
                                {/* Theme Selection */}
                                <div>
                                    <label className="block text-xs font-semibold text-gray-800 mb-3">
                                        Color Palette & Contrast Mode
                                    </label>
                                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                        {/* Light Mode */}
                                        <button
                                            type="button"
                                            onClick={() => handleThemeSelect("light")}
                                            className={`relative flex flex-col items-start rounded-xl border p-4 text-left transition ${
                                                theme === "light"
                                                    ? "border-[#6d5dfc] bg-[#eeebff]/30 dark:bg-[#5848e8]/25 ring-2 ring-[#6d5dfc]/30"
                                                    : "border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800/80"
                                            }`}
                                        >
                                            {theme === "light" && (
                                                 <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-[#6d5dfc] text-white">
                                                     <Check size={12} strokeWidth={3} />
                                                 </span>
                                             )}
                                             <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-600 mb-3">
                                                 <Sun size={18} />
                                             </div>
                                             <p className="text-sm font-bold text-gray-900">Cleanroom Day</p>
                                             <p className="text-[11px] text-gray-500 mt-0.5">
                                                 High-contrast light interface optimized for brightly lit cleanrooms.
                                             </p>
                                         </button>

                                         {/* Dark Mode */}
                                         <button
                                            type="button"
                                            onClick={() => handleThemeSelect("dark")}
                                            className={`relative flex flex-col items-start rounded-xl border p-4 text-left transition ${
                                                theme === "dark"
                                                    ? "border-[#6d5dfc] bg-[#eeebff]/30 dark:bg-[#5848e8]/25 ring-2 ring-[#6d5dfc]/30"
                                                    : "border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800/80"
                                            }`}
                                        >
                                            {theme === "dark" && (
                                                 <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-[#6d5dfc] text-white">
                                                     <Check size={12} strokeWidth={3} />
                                                 </span>
                                             )}
                                             <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-900 text-indigo-300 mb-3">
                                                 <Moon size={18} />
                                             </div>
                                             <p className="text-sm font-bold text-gray-900">Low-Glare Night</p>
                                             <p className="text-[11px] text-gray-500 mt-0.5">
                                                 Deep obsidian tones reducing eye fatigue on microscope screens.
                                             </p>
                                         </button>

                                         {/* System Mode */}
                                         <button
                                            type="button"
                                            onClick={() => handleThemeSelect("system")}
                                            className={`relative flex flex-col items-start rounded-xl border p-4 text-left transition ${
                                                theme === "system"
                                                    ? "border-[#6d5dfc] bg-[#eeebff]/30 dark:bg-[#5848e8]/25 ring-2 ring-[#6d5dfc]/30"
                                                    : "border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800/80"
                                            }`}
                                        >
                                            {theme === "system" && (
                                                 <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-[#6d5dfc] text-white">
                                                     <Check size={12} strokeWidth={3} />
                                                 </span>
                                             )}
                                             <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600 mb-3">
                                                 <Monitor size={18} />
                                             </div>
                                             <p className="text-sm font-bold text-gray-900">System Sync</p>
                                             <p className="text-[11px] text-gray-500 mt-0.5">
                                                 Automatically mirrors your operating system appearance preferences.
                                             </p>
                                         </button>
                                     </div>
                                 </div>

                                 {/* Density Selection */}
                                 <div className="pt-4 border-t border-gray-100 dark:border-gray-800">
                                     <label className="block text-xs font-semibold text-gray-800 mb-3">
                                         Interface Density
                                     </label>
                                     <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                         <button
                                             type="button"
                                             onClick={() => handleDensitySelect("comfortable")}
                                             className={`flex items-start gap-3 rounded-xl border p-3 text-left transition ${
                                                 density === "comfortable"
                                                     ? "border-[#6d5dfc] bg-[#eeebff]/30 dark:bg-[#5848e8]/25 ring-2 ring-[#6d5dfc]/30"
                                                     : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                                             }`}
                                         >
                                             <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                                                 <Laptop size={16} />
                                             </div>
                                             <div>
                                                 <p className="text-xs font-bold text-gray-900">Comfortable (Default)</p>
                                                 <p className="text-[11px] text-gray-500">
                                                     Standard spacing for high-resolution desktop workstation monitors.
                                                 </p>
                                             </div>
                                         </button>

                                         <button
                                             type="button"
                                             onClick={() => handleDensitySelect("compact")}
                                             className={`flex items-start gap-3 rounded-xl border p-3 text-left transition ${
                                                 density === "compact"
                                                     ? "border-[#6d5dfc] bg-[#eeebff]/30 dark:bg-[#5848e8]/25 ring-2 ring-[#6d5dfc]/30"
                                                     : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                                             }`}
                                         >
                                             <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                                                 <Smartphone size={16} />
                                             </div>
                                             <div>
                                                 <p className="text-xs font-bold text-gray-900">Compact Cleanroom</p>
                                                 <p className="text-[11px] text-gray-500">
                                                     Denser data tables and tight padding for 1080p touch terminals.
                                                 </p>
                                             </div>
                                         </button>
                                     </div>
                                 </div>
                            </div>
                        </div>
                    )}

                    {/* TAB 4: NOTIFICATIONS */}
                    {activeTab === "notifications" && (
                        <div className="rounded-2xl border border-gray-200 bg-white p-7 shadow-sm">
                            <div className="border-b border-gray-100 pb-5 mb-6">
                                <div className="flex items-center gap-2">
                                    <Bell size={20} className="text-[#6d5dfc]" />
                                    <h2 className="text-lg font-bold text-gray-900">Notification Alerts</h2>
                                </div>
                                <p className="text-xs text-gray-500 mt-0.5">
                                    Configure cleanroom threshold warnings and automated case lifecycle digests.
                                </p>
                            </div>

                            <div className="space-y-5">
                                {[
                                    {
                                        key: "newCases",
                                        title: "New Diagnostic Intakes",
                                        desc: "Immediate banner when a technician logs an intake case on your line.",
                                    },
                                    {
                                        key: "defectAlerts",
                                        title: "Line Defect & Yield Alerts",
                                        desc: "Instant warning alert when line dispensing yield drops below 98%.",
                                    },
                                    {
                                        key: "causeConfirmations",
                                        title: "Root Cause Verification Requests",
                                        desc: "Notification when physical checks yield a confirmed cause needing engineering sign-off.",
                                    },
                                    {
                                        key: "shiftDigest",
                                        title: "Shift Handover Summary",
                                        desc: "A shift-change summary of open cases, recurrence risks, and line statuses.",
                                    },
                                ].map((item) => {
                                    const isChecked = (notificationPrefs as any)[item.key];

                                    return (
                                        <div
                                            key={item.key}
                                            className="flex items-center justify-between gap-4 p-3.5 rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/40 hover:bg-gray-100/70 dark:hover:bg-gray-800 transition"
                                        >
                                            <div>
                                                <p className="text-xs font-bold text-gray-900">{item.title}</p>
                                                <p className="text-[11px] text-gray-500 mt-0.5">{item.desc}</p>
                                            </div>
                                            <label className="relative inline-flex items-center cursor-pointer shrink-0">
                                                <input
                                                    type="checkbox"
                                                    checked={isChecked}
                                                    onChange={(e) =>
                                                        setNotificationPrefs({
                                                            ...notificationPrefs,
                                                            [item.key]: e.target.checked,
                                                        })
                                                    }
                                                    className="sr-only peer"
                                                />
                                                <div className="w-11 h-6 bg-gray-200 dark:bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#6d5dfc]"></div>
                                            </label>
                                        </div>
                                    );
                                })}

                                <div className="pt-4 border-t border-gray-100 flex justify-end">
                                    <button
                                        type="button"
                                        onClick={handleSaveNotificationPrefs}
                                        className="inline-flex items-center gap-2 rounded-xl bg-[#6d5dfc] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#5848e8]"
                                    >
                                        <Save size={16} />
                                        Save Notification Preferences
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </PageContainer>
    );
}
