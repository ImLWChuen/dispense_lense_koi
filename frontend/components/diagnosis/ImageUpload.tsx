"use client";

import { useState, useRef } from "react";
import { Upload, X, Image as ImageIcon, Loader2 } from "lucide-react";

interface ImageUploadProps {
    onAnalysisComplete?: (observations: any[]) => void;
}

export default function ImageUpload({ onAnalysisComplete }: ImageUploadProps) {
    const [files, setFiles] = useState<{ name: string; size: string; status: 'uploading' | 'analyzed' | 'error', message?: string }[]>([]);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const processFile = async (file: File) => {
        const fileObj = {
            name: file.name,
            size: `${(file.size / 1024).toFixed(1)} KB`,
            status: 'uploading' as const
        };
        
        setFiles((prev) => [...prev, fileObj]);
        const index = files.length; // Actually we should match by name or generate ID, but this is simple

        try {
            const formData = new FormData();
            formData.append("file", file);

            const res = await fetch("http://127.0.0.1:8000/api/v1/images/analyze", {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                throw new Error("Analysis failed");
            }

            const data = await res.json();
            
            const detectedSummary = data.length > 0
                ? `Detected: ${data.map((d: any) => `${d.observation_type.replace(/_/g, ' ')}: ${d.value}`).join(', ')}`
                : 'Normal (no defect features detected)';

            setFiles((prev) => prev.map(f => f.name === file.name ? {
                ...f, 
                status: 'analyzed', 
                message: detectedSummary 
            } : f));

            if (onAnalysisComplete && data.length > 0) {
                onAnalysisComplete(data);
            }

        } catch (err: any) {
            setFiles((prev) => prev.map(f => f.name === file.name ? {
                ...f, 
                status: 'error', 
                message: err.message || 'Error analyzing' 
            } : f));
        }
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFiles = Array.from(e.dataTransfer.files);
        for (const file of droppedFiles) {
            await processFile(file);
        }
    };
    
    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const selectedFiles = Array.from(e.target.files);
            for (const file of selectedFiles) {
                await processFile(file);
            }
        }
    };

    const removeFile = (name: string) => {
        setFiles((prev) => prev.filter((f) => f.name !== name));
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
                onClick={() => fileInputRef.current?.click()}
                className={`mt-5 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 transition ${
                    isDragging
                        ? "border-[#6d5dfc] bg-[#eeebff]"
                        : "border-gray-300 bg-gray-50 hover:border-gray-400"
                }`}
            >
                <input 
                    type="file" 
                    className="hidden" 
                    ref={fileInputRef} 
                    onChange={handleFileChange}
                    accept="image/*"
                    multiple 
                />
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#eeebff] text-[#6d5dfc]">
                    <Upload size={22} />
                </div>

                <p className="mt-3 text-sm font-medium text-gray-700">
                    Drag and drop images here
                </p>

                <p className="mt-1 text-xs text-gray-500">
                    or click to browse · PNG, JPG up to 10 MB
                </p>

                <button className="mt-4 rounded-lg bg-white px-4 py-2 text-xs font-semibold text-[#5848e8] shadow-sm ring-1 ring-gray-200 transition hover:bg-gray-50" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                    Browse Files
                </button>
            </div>

            {files.length > 0 && (
                <div className="mt-4 space-y-2">
                    {files.map((file, index) => (
                        <div
                            key={index}
                            className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 ${file.status === 'error' ? 'border-red-100 bg-red-50' : 'border-gray-100 bg-gray-50'}`}
                        >
                            {file.status === 'uploading' ? (
                                <Loader2 size={16} className="shrink-0 animate-spin text-[#6d5dfc]" />
                            ) : (
                                <ImageIcon
                                    size={16}
                                    className={`shrink-0 ${file.status === 'error' ? 'text-red-400' : 'text-[#6d5dfc]'}`}
                                />
                            )}

                            <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium text-gray-700">
                                    {file.name}
                                </p>

                                <p className={`text-xs ${file.status === 'error' ? 'text-red-500' : file.status === 'analyzed' ? 'text-green-600 font-medium' : 'text-gray-400'}`}>
                                    {file.message || file.size}
                                </p>
                            </div>

                            <button
                                onClick={() => removeFile(file.name)}
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
