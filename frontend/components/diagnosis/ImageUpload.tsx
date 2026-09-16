"use client";

import { useState } from "react";
import { Upload, X, Image as ImageIcon } from "lucide-react";

export default function ImageUpload() {
    const [files, setFiles] = useState<{ name: string; size: string }[]>([]);
    const [isDragging, setIsDragging] = useState(false);

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFiles = Array.from(e.dataTransfer.files).map((f) => ({
            name: f.name,
            size: `${(f.size / 1024).toFixed(1)} KB`,
        }));
        setFiles((prev) => [...prev, ...droppedFiles]);
    };

    const removeFile = (index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    return (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">
                Image Evidence
            </h2>

            <p className="mt-1 text-xs text-gray-500">
                Upload images of the dispensing defect for visual analysis
            </p>

            <div
                onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`mt-5 flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 transition ${
                    isDragging
                        ? "border-[#6d5dfc] bg-[#eeebff]"
                        : "border-gray-300 bg-gray-50 hover:border-gray-400"
                }`}
            >
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Upload size={22} />
                </div>

                <p className="mt-3 text-sm font-medium text-gray-700">
                    Drag and drop images here
                </p>

                <p className="mt-1 text-xs text-gray-500">
                    or click to browse · PNG, JPG up to 10 MB
                </p>

                <button className="mt-4 rounded-lg bg-white px-4 py-2 text-xs font-semibold text-[#5848e8] shadow-sm ring-1 ring-gray-200 transition hover:bg-gray-50">
                    Browse Files
                </button>
            </div>

            {files.length > 0 && (
                <div className="mt-4 space-y-2">
                    {files.map((file, index) => (
                        <div
                            key={index}
                            className="flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50 px-4 py-2.5"
                        >
                            <ImageIcon
                                size={16}
                                className="shrink-0 text-gray-400"
                            />

                            <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium text-gray-700">
                                    {file.name}
                                </p>

                                <p className="text-xs text-gray-400">
                                    {file.size}
                                </p>
                            </div>

                            <button
                                onClick={() => removeFile(index)}
                                className="shrink-0 rounded-md p-1 text-gray-400 transition hover:bg-gray-200 hover:text-gray-600"
                            >
                                <X size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
