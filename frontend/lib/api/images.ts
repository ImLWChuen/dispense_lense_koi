/**
 * Dispense Lens - Calibrated Image API Client
 *
 * Implements multipart POST /api/v1/images/analyze communicating with
 * the backend image analysis service.
 */

import { apiClient } from "./client";
import { AnalysisProfile, ImageAnalysisResponse } from "@/types/image";

export const imagesApi = {
    /**
     * Submit an image and analysis profile for calibrated feature extraction and defect evaluation.
     *
     * @param file Primary inspection image (JPEG or PNG, <= 10 MB)
     * @param profile Typed AnalysisProfile specification (mode, rois, limits, scale)
     * @param referenceFile Optional golden reference image (required when mode="REFERENCE_IMAGE")
     * @param signal Optional AbortSignal for request cancellation
     */
    async analyze(
        file: File,
        profile: AnalysisProfile,
        referenceFile?: File | null,
        signal?: AbortSignal
    ): Promise<ImageAnalysisResponse> {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("profile", JSON.stringify(profile));

        if (profile.mode === "REFERENCE_IMAGE" && referenceFile) {
            formData.append("reference_file", referenceFile);
        }

        return apiClient.request<ImageAnalysisResponse>("/images/analyze", {
            method: "POST",
            body: formData,
            signal,
        });
    },
};
