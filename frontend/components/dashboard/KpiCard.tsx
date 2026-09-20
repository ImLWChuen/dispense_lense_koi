import { ReactNode } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KpiCardProps {
    title: string;
    value: string;
    description: string;
    icon: ReactNode;
    trend?: string;
    trendDirection?: "up" | "down" | "neutral";
    sparkline?: number[];
    accentColor?: string;
}

export default function KpiCard({
    title,
    value,
    description,
    icon,
    trend,
    trendDirection = "up",
    sparkline = [10, 14, 12, 18, 16, 21, 25],
    accentColor = "#6d5dfc",
}: KpiCardProps) {
    // Generate normalized SVG sparkline path
    const width = 100;
    const height = 32;
    const padding = 2;

    const min = Math.min(...sparkline);
    const max = Math.max(...sparkline);
    const range = max - min || 1;

    const points = sparkline.map((val, idx) => {
        const x = padding + (idx / (sparkline.length - 1)) * (width - 2 * padding);
        const y = height - padding - ((val - min) / range) * (height - 2 * padding);
        return { x, y };
    });

    const pathD = points.reduce((acc, pt, i) => {
        return i === 0 ? `M ${pt.x},${pt.y}` : `${acc} L ${pt.x},${pt.y}`;
    }, "");

    const lastPoint = points[points.length - 1] || { x: width - padding, y: height / 2 };
    const areaD = `${pathD} L ${lastPoint.x},${height} L ${points[0].x},${height} Z`;

    const isPositive = trendDirection === "up";
    const isNegative = trendDirection === "down";

    return (
        <div className="group relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white p-5 shadow-xs transition hover:border-[#6d5dfc]/40 hover:shadow-md">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                        {title}
                    </p>

                    <p className="mt-2 text-3xl font-extrabold tracking-tight text-gray-900">
                        {value}
                    </p>
                </div>

                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#eeebff] text-[#6d5dfc] transition group-hover:scale-105 group-hover:bg-[#6d5dfc] group-hover:text-white">
                    {icon}
                </div>
            </div>

            {/* Sparkline & Trend Footer */}
            <div className="mt-4 flex items-end justify-between gap-2 border-t border-gray-100 pt-3">
                <div className="flex flex-col">
                    {trend && (
                        <div className="flex items-center gap-1">
                            {isPositive ? (
                                <TrendingUp size={14} className="text-emerald-600" />
                            ) : isNegative ? (
                                <TrendingDown size={14} className="text-rose-600" />
                            ) : (
                                <Minus size={14} className="text-gray-500" />
                            )}
                            <span
                                className={`text-xs font-bold ${
                                    isPositive
                                        ? "text-emerald-600"
                                        : isNegative
                                        ? "text-rose-600"
                                        : "text-gray-600"
                                }`}
                            >
                                {trend}
                            </span>
                        </div>
                    )}
                    <span className="text-[11px] text-gray-400 font-medium">
                        {description}
                    </span>
                </div>

                {/* SVG Sparkline */}
                {sparkline.length > 1 && (
                    <div className="w-24 shrink-0">
                        <svg
                            viewBox={`0 0 ${width} ${height}`}
                            className="h-8 w-full overflow-visible"
                        >
                            <defs>
                                <linearGradient
                                    id={`spark-grad-${title.replace(/\s+/g, "")}`}
                                    x1="0"
                                    y1="0"
                                    x2="0"
                                    y2="1"
                                >
                                    <stop offset="0%" stopColor={accentColor} stopOpacity="0.3" />
                                    <stop offset="100%" stopColor={accentColor} stopOpacity="0.0" />
                                </linearGradient>
                            </defs>
                            {/* Gradient Area */}
                            <path
                                d={areaD}
                                fill={`url(#spark-grad-${title.replace(/\s+/g, "")})`}
                            />
                            {/* Trend Line */}
                            <path
                                d={pathD}
                                fill="none"
                                stroke={accentColor}
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                            {/* Latest Endpoint Marker */}
                            <circle
                                cx={lastPoint.x}
                                cy={lastPoint.y}
                                r="3"
                                fill={accentColor}
                                className="transition-all"
                            />
                        </svg>
                    </div>
                )}
            </div>
        </div>
    );
}