"use client";

import { Activity, Lock, Mail } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

export default function LoginPage() {
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        // Simulate login
        setTimeout(() => {
            window.location.href = "/dashboard";
        }, 800);
    };

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm backdrop-blur-xl">
            <div className="flex flex-col items-center mb-8">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#6d5dfc] text-white mb-4">
                    <Activity size={24} />
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-gray-900">
                    Welcome back
                </h1>
                <p className="mt-1 text-sm text-gray-500">
                    Sign in to your DispenseIQ account
                </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                        Email address
                    </label>
                    <div className="relative">
                        <Mail
                            size={18}
                            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                        />
                        <input
                            type="email"
                            defaultValue="sarah.mitchell@example.com"
                            required
                            className="h-11 w-full rounded-xl border border-gray-200 bg-gray-50 pl-10 pr-4 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                            placeholder="you@company.com"
                        />
                    </div>
                </div>

                <div>
                    <div className="flex items-center justify-between mb-1">
                        <label className="block text-sm font-medium text-gray-700">
                            Password
                        </label>
                        <a href="#" className="text-xs font-medium text-[#6d5dfc] hover:text-[#5848e8]">
                            Forgot password?
                        </a>
                    </div>
                    <div className="relative">
                        <Lock
                            size={18}
                            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                        />
                        <input
                            type="password"
                            defaultValue="password123"
                            required
                            className="h-11 w-full rounded-xl border border-gray-200 bg-gray-50 pl-10 pr-4 text-sm outline-none transition focus:border-[#6d5dfc] focus:bg-white"
                            placeholder="••••••••"
                        />
                    </div>
                </div>

                <button
                    type="submit"
                    disabled={isLoading}
                    className="flex h-11 w-full items-center justify-center rounded-xl bg-[#6d5dfc] px-4 text-sm font-semibold text-white transition hover:bg-[#5848e8] disabled:opacity-70 disabled:cursor-not-allowed mt-2"
                >
                    {isLoading ? "Signing in..." : "Sign in"}
                </button>
            </form>

            <div className="mt-8 text-center text-sm text-gray-500">
                Don't have an account?{" "}
                <Link href="#" className="font-semibold text-[#6d5dfc] hover:text-[#5848e8]">
                    Request access
                </Link>
            </div>
        </div>
    );
}
