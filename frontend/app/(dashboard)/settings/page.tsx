"use client";

import { useState } from "react";
import { User, Bell, Shield, Palette } from "lucide-react";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import PageContainer from "@/components/layout/PageContainer";

export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState("profile");

    const tabs = [
        { id: "profile", label: "Profile", icon: User },
        { id: "notifications", label: "Notifications", icon: Bell },
        { id: "security", label: "Security", icon: Shield },
        { id: "appearance", label: "Appearance", icon: Palette },
    ];

    return (
        <div className="min-h-screen">
            <Sidebar />

            <div className="ml-64">
                <Header />

                <PageContainer>
                    <div className="mb-8">
                        <h1 className="text-3xl font-bold tracking-tight text-gray-900">
                            Settings
                        </h1>
                        <p className="mt-2 text-sm text-gray-500">
                            Manage your account preferences and application settings.
                        </p>
                    </div>

                    <div className="flex flex-col md:flex-row gap-8">
                        {/* Sidebar Tabs */}
                        <div className="w-full md:w-64 flex-shrink-0 space-y-1">
                            {tabs.map((tab) => {
                                const Icon = tab.icon;
                                const isActive = activeTab === tab.id;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${
                                            isActive
                                                ? "bg-[#eeebff] text-[#5848e8]"
                                                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                                        }`}
                                    >
                                        <Icon size={18} strokeWidth={1.8} />
                                        {tab.label}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 max-w-3xl">
                            {activeTab === "profile" && (
                                <div className="rounded-2xl border border-gray-200 bg-white p-8">
                                    <h2 className="text-xl font-semibold text-gray-900 mb-6">Profile Information</h2>
                                    
                                    <form className="space-y-6">
                                        <div className="flex items-center gap-6 mb-8">
                                            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[#eeebff] text-2xl font-bold text-[#5848e8]">
                                                SM
                                            </div>
                                            <div>
                                                <button type="button" className="rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50">
                                                    Change avatar
                                                </button>
                                                <p className="mt-2 text-xs text-gray-500">JPG, GIF or PNG. Max size of 800K</p>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                                                <input type="text" defaultValue="Sarah" className="h-10 w-full rounded-xl border border-gray-200 bg-gray-50 px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white" />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                                                <input type="text" defaultValue="Mitchell" className="h-10 w-full rounded-xl border border-gray-200 bg-gray-50 px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white" />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                                                <input type="email" defaultValue="sarah.mitchell@example.com" className="h-10 w-full rounded-xl border border-gray-200 bg-gray-50 px-3 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white" />
                                            </div>
                                            <div className="md:col-span-2">
                                                <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                                                <input type="text" defaultValue="Manufacturing Engineer" readOnly className="h-10 w-full rounded-xl border border-gray-200 bg-gray-100 px-3 text-sm text-gray-500 outline-none cursor-not-allowed" />
                                            </div>
                                        </div>

                                        <div className="pt-4 border-t border-gray-100 flex justify-end">
                                            <button type="button" className="rounded-xl bg-[#6d5dfc] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#5848e8]">
                                                Save Changes
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            )}

                            {activeTab === "notifications" && (
                                <div className="rounded-2xl border border-gray-200 bg-white p-8">
                                    <h2 className="text-xl font-semibold text-gray-900 mb-6">Notification Preferences</h2>
                                    <div className="space-y-6">
                                        {[
                                            { title: "New Diagnostic Reports", desc: "Receive email when a new diagnostic report is ready." },
                                            { title: "Defect Alerts", desc: "Get notified immediately when defects exceed threshold." },
                                            { title: "Weekly Summary", desc: "A weekly digest of performance metrics and case resolutions." },
                                        ].map((item, i) => (
                                            <div key={i} className="flex items-start justify-between">
                                                <div>
                                                    <h3 className="text-sm font-medium text-gray-900">{item.title}</h3>
                                                    <p className="text-sm text-gray-500">{item.desc}</p>
                                                </div>
                                                <label className="relative inline-flex items-center cursor-pointer">
                                                    <input type="checkbox" defaultChecked={i < 2} className="sr-only peer" />
                                                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#6d5dfc]"></div>
                                                </label>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="pt-6 mt-6 border-t border-gray-100 flex justify-end">
                                        <button type="button" className="rounded-xl bg-[#6d5dfc] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#5848e8]">
                                            Save Preferences
                                        </button>
                                    </div>
                                </div>
                            )}
                            
                            {(activeTab === "security" || activeTab === "appearance") && (
                                <div className="rounded-2xl border border-gray-200 bg-white p-8 flex items-center justify-center min-h-[300px]">
                                    <div className="text-center">
                                        <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gray-100 text-gray-400 mb-4">
                                            {activeTab === "security" ? <Shield size={24} /> : <Palette size={24} />}
                                        </div>
                                        <h2 className="text-lg font-medium text-gray-900 mb-1">Coming Soon</h2>
                                        <p className="text-sm text-gray-500">These settings are not yet available in this environment.</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </PageContainer>
            </div>
        </div>
    );
}
