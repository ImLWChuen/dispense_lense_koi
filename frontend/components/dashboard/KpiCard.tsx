import { ReactNode } from "react";

interface KpiCardProps {
    title: string;
    value: string;
    description: string;
    icon: ReactNode;
    trend?: string;
}

export default function KpiCard({
                                    title,
                                    value,
                                    description,
                                    icon,
                                    trend,
                                }: KpiCardProps) {
    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-sm font-medium text-gray-500">
                        {title}
                    </p>

                    <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900">
                        {value}
                    </p>
                </div>

                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    {icon}
                </div>
            </div>

            <div className="mt-4 flex items-center gap-2 text-xs">
                {trend && (
                    <span className="font-semibold text-green-600">
            {trend}
          </span>
                )}

                <span className="text-gray-500">
          {description}
        </span>
            </div>
        </div>
    );
}