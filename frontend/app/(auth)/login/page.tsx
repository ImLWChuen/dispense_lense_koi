"use client";

import { Activity, Lock, Mail } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/components/providers/AuthContext";
import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api/client";

export default function LoginPage() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [email, setEmail] = useState("sarah.mitchell@example.com");
    const [password, setPassword] = useState("password123");
    const { login } = useAuth();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        
        try {
            const formData = new URLSearchParams();
            formData.append("username", email);
            formData.append("password", password);

            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body: formData,
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || "Failed to sign in");
            }

            const data = await response.json();
            
            // fetch user data using token
            const userResponse = await fetch(`${API_BASE_URL}/auth/me`, {
                headers: {
                    Authorization: `Bearer ${data.access_token}`,
                },
            });
            const userData = await userResponse.json();
            
            login(data.access_token, userData);
            router.push("/dashboard");
        } catch (err: any) {
            setError(err.message || "An unexpected error occurred.");
        } finally {
            setIsLoading(false);
        }
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
                    Sign in to your Dispense Lens account
                </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                    <div className="rounded-xl bg-red-50 p-3 text-sm text-red-600 border border-red-100">
                        {error}
                    </div>
                )}
                
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
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
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
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
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

            {/* Quick Demo Credentials */}
            <div className="mt-6 pt-5 border-t border-gray-100">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 text-center mb-2.5">
                    Demo One-Click Credentials
                </p>
                <div className="grid grid-cols-3 gap-2">
                    <button
                        type="button"
                        onClick={() => {
                            setEmail("admin@example.com");
                            setPassword("password");
                        }}
                        className="rounded-xl border border-purple-200 bg-purple-50/70 py-1.5 px-2 text-center text-xs font-semibold text-purple-700 hover:bg-purple-100 transition"
                    >
                        Admin
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            setEmail("tech@example.com");
                            setPassword("password");
                        }}
                        className="rounded-xl border border-emerald-200 bg-emerald-50/70 py-1.5 px-2 text-center text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition"
                    >
                        Technician
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            setEmail("sarah.mitchell@example.com");
                            setPassword("password");
                        }}
                        className="rounded-xl border border-blue-200 bg-blue-50/70 py-1.5 px-2 text-center text-xs font-semibold text-blue-700 hover:bg-blue-100 transition"
                    >
                        Engineer
                    </button>
                </div>
            </div>

            <div className="mt-6 text-center text-sm text-gray-500">
                Don&apos;t have an account?{" "}
                <Link href="/register" className="font-semibold text-[#6d5dfc] hover:text-[#5848e8]">
                    Register here
                </Link>
            </div>
        </div>
    );
}
