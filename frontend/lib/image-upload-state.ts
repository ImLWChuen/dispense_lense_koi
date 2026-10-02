/**
 * Dispense Lens - Calibrated Image Upload State & Validation Transitions (DLK-M3-027)
 *
 * Pure configuration validation and atomic upload request-state transitions.
 * Shared between ImageUpload.tsx and regression harnesses.
 */

import type {
    ImageAnalysisResponse,
    ImportedLayoutMetadata,
    NormalizedROI,
    UploadItem,
    UploadSnapshot,
} from "@/types/image";
import type { RegionLayoutFile } from "./region-layout";

export interface InFlightController {
    token: number;
    controller: AbortController;
}

/**
 * Validates an upload item's analysis configuration before dispatching a network request.
 * Returns an error message string if invalid, or null if valid.
 */
export function validateAnalysisConfiguration(item: UploadItem): string | null {
    if (item.importedLayout && !item.importedLayout.confirmed) {
        return "Imported region layout placement must be confirmed before running analysis.";
    }

    if (!item.rois || item.rois.length === 0) {
        return "At least one target ROI must be defined before running analysis.";
    }

    for (const roi of item.rois) {
        if (!roi.roi_id || !roi.roi_id.trim()) {
            return "All ROIs must have a valid non-empty identifier.";
        }
        if (
            !Number.isFinite(roi.x) || roi.x < 0 || roi.x > 1 ||
            !Number.isFinite(roi.y) || roi.y < 0 || roi.y > 1 ||
            !Number.isFinite(roi.width) || roi.width <= 0 || roi.width > 1 ||
            !Number.isFinite(roi.height) || roi.height <= 0 || roi.height > 1
        ) {
            return `ROI ${roi.roi_id} has invalid coordinates. Coordinates must be bounded within [0, 1].`;
        }
        if (roi.x + roi.width > 1.00001 || roi.y + roi.height > 1.00001) {
            return `ROI ${roi.roi_id} extends beyond the image boundaries.`;
        }
    }

    if (item.mmPerPixel !== null && item.mmPerPixel !== undefined) {
        if (!Number.isFinite(item.mmPerPixel) || item.mmPerPixel <= 0) {
            return "Scale (mm per pixel) must be a positive finite number greater than 0.";
        }
    }

    if (item.mode === "PROCESS_LIMITS") {
        const limits = item.processLimits;
        if (!limits) {
            return "PROCESS_LIMITS mode requires at least one process limit threshold.";
        }

        const hasAnyLimit =
            (limits.min_coverage_ratio !== null && limits.min_coverage_ratio !== undefined) ||
            (limits.max_coverage_ratio !== null && limits.max_coverage_ratio !== undefined) ||
            (limits.max_overflow_ratio !== null && limits.max_overflow_ratio !== undefined) ||
            (limits.max_size_cv !== null && limits.max_size_cv !== undefined) ||
            (limits.min_presence_ratio !== null && limits.min_presence_ratio !== undefined) ||
            (limits.min_circularity !== null && limits.min_circularity !== undefined) ||
            (limits.min_solidity !== null && limits.min_solidity !== undefined) ||
            (limits.min_convexity !== null && limits.min_convexity !== undefined) ||
            (limits.max_aspect_ratio !== null && limits.max_aspect_ratio !== undefined) ||
            (limits.min_aspect_ratio !== null && limits.min_aspect_ratio !== undefined) ||
            (limits.max_bubble_count !== null && limits.max_bubble_count !== undefined) ||
            (limits.max_void_ratio !== null && limits.max_void_ratio !== undefined);

        if (!hasAnyLimit) {
            return "PROCESS_LIMITS mode requires at least one process limit threshold.";
        }

        if (limits.min_coverage_ratio !== null && limits.min_coverage_ratio !== undefined) {
            if (!Number.isFinite(limits.min_coverage_ratio) || limits.min_coverage_ratio < 0 || limits.min_coverage_ratio > 1) {
                return "Min coverage ratio must be a finite number between 0 and 1.";
            }
        }

        if (limits.max_coverage_ratio !== null && limits.max_coverage_ratio !== undefined) {
            if (!Number.isFinite(limits.max_coverage_ratio) || limits.max_coverage_ratio < 0 || limits.max_coverage_ratio > 1) {
                return "Max coverage ratio must be a finite number between 0 and 1.";
            }
        }

        if (
            limits.min_coverage_ratio !== null && limits.min_coverage_ratio !== undefined &&
            limits.max_coverage_ratio !== null && limits.max_coverage_ratio !== undefined
        ) {
            if (limits.min_coverage_ratio > limits.max_coverage_ratio) {
                return "Min coverage ratio cannot be greater than max coverage ratio.";
            }
        }

        if (limits.max_overflow_ratio !== null && limits.max_overflow_ratio !== undefined) {
            if (!Number.isFinite(limits.max_overflow_ratio) || limits.max_overflow_ratio < 0 || limits.max_overflow_ratio > 1) {
                return "Max overflow ratio must be a finite number between 0 and 1.";
            }
        }

        if (limits.max_size_cv !== null && limits.max_size_cv !== undefined) {
            if (!Number.isFinite(limits.max_size_cv) || limits.max_size_cv < 0) {
                return "Max size CV must be a non-negative finite number (>= 0).";
            }
        }

        if (limits.min_presence_ratio !== null && limits.min_presence_ratio !== undefined) {
            if (!Number.isFinite(limits.min_presence_ratio) || limits.min_presence_ratio < 0 || limits.min_presence_ratio > 1) {
                return "Min presence ratio must be a finite number between 0 and 1.";
            }
        }

        if (limits.min_circularity !== null && limits.min_circularity !== undefined) {
            if (!Number.isFinite(limits.min_circularity) || limits.min_circularity < 0 || limits.min_circularity > 1) {
                return "Min circularity must be a finite number between 0 and 1.";
            }
        }

        if (limits.min_solidity !== null && limits.min_solidity !== undefined) {
            if (!Number.isFinite(limits.min_solidity) || limits.min_solidity < 0 || limits.min_solidity > 1) {
                return "Min solidity must be a finite number between 0 and 1.";
            }
        }

        if (limits.min_convexity !== null && limits.min_convexity !== undefined) {
            if (!Number.isFinite(limits.min_convexity) || limits.min_convexity < 0 || limits.min_convexity > 1) {
                return "Min convexity must be a finite number between 0 and 1.";
            }
        }

        if (limits.max_aspect_ratio !== null && limits.max_aspect_ratio !== undefined) {
            if (!Number.isFinite(limits.max_aspect_ratio) || limits.max_aspect_ratio < 1) {
                return "Max aspect ratio must be a finite number greater than or equal to 1 (>= 1.0).";
            }
        }

        if (limits.min_aspect_ratio !== null && limits.min_aspect_ratio !== undefined) {
            if (!Number.isFinite(limits.min_aspect_ratio) || limits.min_aspect_ratio <= 0 || limits.min_aspect_ratio > 1) {
                return "Min aspect ratio must be a finite number between 0 and 1.";
            }
        }

        if (
            limits.min_aspect_ratio !== null && limits.min_aspect_ratio !== undefined &&
            limits.max_aspect_ratio !== null && limits.max_aspect_ratio !== undefined
        ) {
            if (limits.min_aspect_ratio > limits.max_aspect_ratio) {
                return "Min aspect ratio cannot be greater than max aspect ratio.";
            }
        }

        if (limits.max_bubble_count !== null && limits.max_bubble_count !== undefined) {
            if (!Number.isFinite(limits.max_bubble_count) || limits.max_bubble_count < 0) {
                return "Max bubble count must be a non-negative number (>= 0).";
            }
        }

        if (limits.max_void_ratio !== null && limits.max_void_ratio !== undefined) {
            if (!Number.isFinite(limits.max_void_ratio) || limits.max_void_ratio < 0 || limits.max_void_ratio > 1) {
                return "Max void ratio must be a finite number between 0 and 1.";
            }
        }
    } else if (item.mode === "REFERENCE_IMAGE") {
        if (!item.referenceFile) {
            return "REFERENCE_IMAGE mode requires a reference image to be uploaded.";
        }

        const rLimits = item.referenceLimits;
        if (!rLimits) {
            return "REFERENCE_IMAGE mode requires at least one tolerance or reference ratio bound.";
        }

        const hasRefLimit =
            (rLimits.tolerance_ratio !== null && rLimits.tolerance_ratio !== undefined) ||
            (rLimits.min_reference_ratio !== null && rLimits.min_reference_ratio !== undefined) ||
            (rLimits.max_reference_ratio !== null && rLimits.max_reference_ratio !== undefined) ||
            (rLimits.min_circularity_ratio !== null && rLimits.min_circularity_ratio !== undefined) ||
            (rLimits.min_solidity_ratio !== null && rLimits.min_solidity_ratio !== undefined);

        if (!hasRefLimit) {
            return "REFERENCE_IMAGE mode requires at least one tolerance or reference ratio bound.";
        }

        if (rLimits.tolerance_ratio !== null && rLimits.tolerance_ratio !== undefined) {
            if (!Number.isFinite(rLimits.tolerance_ratio) || rLimits.tolerance_ratio < 0 || rLimits.tolerance_ratio > 1) {
                return "Tolerance ratio must be a finite number between 0 and 1.";
            }
        }

        if (rLimits.min_reference_ratio !== null && rLimits.min_reference_ratio !== undefined) {
            if (!Number.isFinite(rLimits.min_reference_ratio) || rLimits.min_reference_ratio <= 0) {
                return "Min reference ratio must be a finite number greater than 0 (> 0).";
            }
        }

        if (rLimits.max_reference_ratio !== null && rLimits.max_reference_ratio !== undefined) {
            if (!Number.isFinite(rLimits.max_reference_ratio) || rLimits.max_reference_ratio <= 0) {
                return "Max reference ratio must be a finite number greater than 0 (> 0).";
            }
        }

        if (
            rLimits.min_reference_ratio !== null && rLimits.min_reference_ratio !== undefined &&
            rLimits.max_reference_ratio !== null && rLimits.max_reference_ratio !== undefined
        ) {
            if (rLimits.min_reference_ratio > rLimits.max_reference_ratio) {
                return "Min reference ratio cannot be greater than max reference ratio.";
            }
        }
    }

    return null;
}

/**
 * Transitions an upload item into the "analyzing" state with a given request token.
 */
export function startUploadAnalysis(
    prev: UploadSnapshot,
    uploadId: string,
    requestToken: number
): UploadSnapshot {
    const cur = prev[uploadId];
    if (!cur) return prev;
    return {
        ...prev,
        [uploadId]: {
            ...cur,
            status: "analyzing",
            errorMessage: null,
            activeRequestToken: requestToken,
        },
    };
}

/**
 * Sets a local validation error on an upload item without sending a request.
 */
export function setUploadValidationError(
    prev: UploadSnapshot,
    uploadId: string,
    errorMessage: string
): UploadSnapshot {
    const cur = prev[uploadId];
    if (!cur) return prev;
    return {
        ...prev,
        [uploadId]: {
            ...cur,
            status: "ready",
            errorMessage,
        },
    };
}

/**
 * Commits a successful analysis response if the upload still exists and
 * its config revision and request token match the current state.
 */
export function commitUploadSuccess(
    prev: UploadSnapshot,
    uploadId: string,
    requestToken: number,
    requestRevision: number,
    response: ImageAnalysisResponse
): UploadSnapshot {
    const cur = prev[uploadId];
    if (!cur || cur.configRevision !== requestRevision || cur.activeRequestToken !== requestToken) {
        return prev;
    }
    return {
        ...prev,
        [uploadId]: {
            ...cur,
            status: "analyzed",
            result: response,
            errorMessage: null,
            activeRequestToken: null,
        },
    };
}

/**
 * Commits an analysis error message if the upload still exists and
 * its config revision and request token match the current state.
 */
export function commitUploadError(
    prev: UploadSnapshot,
    uploadId: string,
    requestToken: number,
    requestRevision: number,
    errorMessage: string
): UploadSnapshot {
    const cur = prev[uploadId];
    if (!cur || cur.configRevision !== requestRevision || cur.activeRequestToken !== requestToken) {
        return prev;
    }
    return {
        ...prev,
        [uploadId]: {
            ...cur,
            status: "error",
            errorMessage,
            activeRequestToken: null,
        },
    };
}

/**
 * Reconfigures an upload item: bumps configRevision, clears activeRequestToken,
 * resets status to "ready", and clears any existing result or error message.
 *
 * Enforces imported layout lifecycle rules:
 * - If ROIs are cleared (length === 0), removes imported layout to allow manual drawing fallback.
 * - If ROIs are edited/modified, invalidates confirmation.
 * - If in REFERENCE_IMAGE mode and reference image is changed, invalidates confirmation.
 */
export function reconfigureUpload(
    prev: UploadSnapshot,
    uploadId: string,
    updates: Partial<UploadItem>
): UploadSnapshot {
    const current = prev[uploadId];
    if (!current) return prev;

    let nextImportedLayout = current.importedLayout ? { ...current.importedLayout } : null;

    if ("importedLayout" in updates) {
        nextImportedLayout = updates.importedLayout ?? null;
    } else if (nextImportedLayout) {
        if (updates.rois !== undefined) {
            if (updates.rois.length === 0) {
                // Clearing regions abandons imported layout and allows manual drawing fallback
                nextImportedLayout = null;
            } else {
                // Editing ROIs invalidates confirmation
                nextImportedLayout.confirmed = false;
                nextImportedLayout.confirmedAt = null;
                nextImportedLayout.confirmedRevision = null;
            }
        }
        if (
            nextImportedLayout &&
            ((updates.referenceFile !== undefined && updates.referenceFile !== current.referenceFile) ||
             (updates.referencePreviewUrl !== undefined && updates.referencePreviewUrl !== current.referencePreviewUrl))
        ) {
            if (current.mode === "REFERENCE_IMAGE" || updates.mode === "REFERENCE_IMAGE") {
                nextImportedLayout.confirmed = false;
                nextImportedLayout.confirmedAt = null;
                nextImportedLayout.confirmedRevision = null;
            }
        }
    }

    return {
        ...prev,
        [uploadId]: {
            ...current,
            ...updates,
            importedLayout: nextImportedLayout,
            activeLayoutImport: null,
            status: "ready",
            result: null,
            errorMessage: null,
            configRevision: current.configRevision + 1,
            activeRequestToken: null,
        },
    };
}

/**
 * Transitions an upload item to use an imported region layout.
 * Replaces ROI geometry, invalidates confirmation and previous results,
 * bumps configRevision, and preserves current image, mode, scale, and limits.
 */
export function importRegionLayout(
    prev: UploadSnapshot,
    uploadId: string,
    layout: RegionLayoutFile,
    options: { importedAt?: string } = {}
): UploadSnapshot {
    const current = prev[uploadId];
    if (!current) return prev;

    const newRois: NormalizedROI[] = layout.rois.map((r) => ({
        roi_id: r.roi_id,
        x: r.x,
        y: r.y,
        width: r.width,
        height: r.height,
    }));

    const importedMetadata: ImportedLayoutMetadata = {
        name: layout.name,
        sourceDimensions: {
            width: layout.source_image.width,
            height: layout.source_image.height,
        },
        importedAt: options.importedAt ?? new Date().toISOString(),
        confirmed: false,
        confirmedAt: null,
        confirmedRevision: null,
    };

    return {
        ...prev,
        [uploadId]: {
            ...current,
            rois: newRois,
            importedLayout: importedMetadata,
            activeLayoutImport: null,
            status: "ready",
            result: null,
            errorMessage: null,
            configRevision: current.configRevision + 1,
            activeRequestToken: null,
        },
    };
}

/**
 * Confirms the placement of an imported region layout on the target image.
 * Requires valid positive safe-integer target image dimensions unconditionally.
 * If targetDimensions is omitted, null, or has invalid width/height (<= 0, non-integer, non-finite),
 * the snapshot is returned unchanged (confirmed remains false, analysis remains blocked).
 * Does not rerun analysis automatically or bump configRevision.
 */
export function confirmRegionPlacement(
    prev: UploadSnapshot,
    uploadId: string,
    targetDimensions?: { width: number; height: number } | null,
    confirmedAt = new Date().toISOString()
): UploadSnapshot {
    const current = prev[uploadId];
    if (!current || !current.importedLayout) return prev;

    if (
        !targetDimensions ||
        typeof targetDimensions.width !== "number" ||
        typeof targetDimensions.height !== "number" ||
        !Number.isSafeInteger(targetDimensions.width) ||
        !Number.isSafeInteger(targetDimensions.height) ||
        targetDimensions.width <= 0 ||
        targetDimensions.height <= 0
    ) {
        return prev;
    }

    return {
        ...prev,
        [uploadId]: {
            ...current,
            importedLayout: {
                ...current.importedLayout,
                confirmed: true,
                confirmedAt,
                confirmedRevision: current.configRevision,
            },
            errorMessage: null,
        },
    };
}

export interface InFlightImportSession {
    uploadId: string;
    token: number;
    expectedRevision: number;
    startedAt: string;
    aborted: boolean;
    abort?: () => void;
}

/**
 * Coordinates asynchronous layout imports across multiple views (inline card, Studio modal).
 * Tracks monotonic tokens and captured configRevisions per upload, ensuring that
 * out-of-order completions, stale reads, late errors, or obsolete sessions cannot mutate state.
 */
export class ImportCoordinator {
    private sessions: Record<string, InFlightImportSession> = {};
    private nextToken = 1;

    public startImport(
        uploadId: string,
        currentRevision: number,
        abortFn?: () => void
    ): InFlightImportSession {
        this.cancelImport(uploadId);
        const token = this.nextToken++;
        this.sessions[uploadId] = {
            uploadId,
            token,
            expectedRevision: currentRevision,
            startedAt: new Date().toISOString(),
            aborted: false,
            abort: abortFn,
        };
        return { ...this.sessions[uploadId] };
    }

    public cancelImport(uploadId: string): void {
        const session = this.sessions[uploadId];
        if (session) {
            session.aborted = true;
            try {
                session.abort?.();
            } catch {
                // Ignore abort errors
            }
            delete this.sessions[uploadId];
        }
    }

    public cancelAll(): void {
        for (const uploadId of Object.keys(this.sessions)) {
            this.cancelImport(uploadId);
        }
    }

    public isTokenActive(uploadId: string, token: number): boolean {
        const session = this.sessions[uploadId];
        return Boolean(session && !session.aborted && session.token === token);
    }

    public canCommitImport(
        currentUpload: UploadItem | null | undefined,
        token: number
    ): boolean {
        if (!currentUpload) return false;
        const session = this.sessions[currentUpload.id];
        if (!session || session.aborted || session.token !== token) return false;
        if (currentUpload.configRevision !== session.expectedRevision) return false;
        return true;
    }

    public commitImport(
        prev: UploadSnapshot,
        uploadId: string,
        token: number,
        layout: RegionLayoutFile,
        expectedRevision: number,
        importedAt: string
    ): { nextState: UploadSnapshot; committed: boolean } {
        const nextState = commitRegionLayoutImport(prev, uploadId, token, expectedRevision, importedAt, layout);
        return {
            nextState,
            committed: nextState !== prev,
        };
    }

    /** Run non-state effects only after React exposes the imported state. */
    public finalizeCommittedImport(currentUpload: UploadItem | null | undefined): boolean {
        if (!currentUpload) return false;
        const session = this.sessions[currentUpload.id];
        if (
            !session || session.aborted ||
            currentUpload.configRevision !== session.expectedRevision + 1 ||
            currentUpload.importedLayout?.importedAt !== session.startedAt
        ) {
            return false;
        }
        this.cancelImport(currentUpload.id);
        return true;
    }

    /** Cancel sessions whose upload disappeared or configuration revision advanced. */
    public cancelStaleImports(currentUploads: UploadSnapshot): void {
        for (const [uploadId, session] of Object.entries(this.sessions)) {
            const current = currentUploads[uploadId];
            if (!current || current.configRevision !== session.expectedRevision) {
                this.cancelImport(uploadId);
            }
        }
    }
}

/** Record a selected, valid layout read as a pure upload-state transition. */
export function beginRegionLayoutImport(
    prev: UploadSnapshot,
    uploadId: string,
    token: number,
    expectedRevision: number
): UploadSnapshot {
    const current = prev[uploadId];
    if (!current || current.configRevision !== expectedRevision) return prev;
    return {
        ...prev,
        [uploadId]: {
            ...current,
            activeLayoutImport: { token, expectedRevision },
        },
    };
}

/** Clear only transient in-flight import identity; preserve existing results/layout. */
export function clearRegionLayoutImport(
    prev: UploadSnapshot,
    uploadId: string,
    token?: number
): UploadSnapshot {
    const current = prev[uploadId];
    if (!current?.activeLayoutImport) return prev;
    if (token !== undefined && current.activeLayoutImport.token !== token) return prev;
    return {
        ...prev,
        [uploadId]: {
            ...current,
            activeLayoutImport: null,
        },
    };
}

/**
 * Pure, replay-safe layout commit. It validates the request identity and captured
 * revision against the same snapshot React supplies to the updater.
 */
export function commitRegionLayoutImport(
    prev: UploadSnapshot,
    uploadId: string,
    token: number,
    expectedRevision: number,
    importedAt: string,
    layout: RegionLayoutFile
): UploadSnapshot {
    const current = prev[uploadId];
    const activeImport = current?.activeLayoutImport;
    if (
        !current || !activeImport || current.configRevision !== expectedRevision ||
        activeImport.token !== token || activeImport.expectedRevision !== expectedRevision
    ) {
        return prev;
    }
    return importRegionLayout(prev, uploadId, layout, { importedAt });
}

/** Supersede a pending read before checking the replacement file's size. */
export function beginRegionLayoutFileSelection(
    coordinator: ImportCoordinator,
    uploadId: string,
    fileSize: number,
    maxBytes: number
): boolean {
    coordinator.cancelImport(uploadId);
    return Number.isFinite(fileSize) && fileSize >= 0 && fileSize <= maxBytes;
}

/**
 * Executes an asynchronous layout file import through ImportCoordinator.
 * Protects against:
 * - A/B out-of-order completion (starting B cancels A; A cannot commit)
 * - Edits during read (editing bumps revision; older token/revision cannot commit)
 * - Abandonment during read (abandoning cancels session; read cannot commit)
 * - Deletion during read (deleting clears upload and cancels session; read cannot commit)
 * - Cross-view reads (inline and studio share the same coordinator instance)
 * - Teardown / unmount (cancelAll aborts active readers and cancels sessions)
 * - Obsolete error callbacks (errors from stale reads are discarded)
 */
export function startCoordinatedImport(
    coordinator: ImportCoordinator,
    uploadId: string,
    currentRevision: number,
    readFn: (
        onSuccess: (content: string) => void,
        onError: (err: Error) => void
    ) => (() => void), // returns abort cleanup function
    handlers: {
        getCurrentUpload: () => UploadItem | undefined;
        onStart?: (token: number, expectedRevision: number, startedAt: string) => void;
        onCommit: (token: number, layout: RegionLayoutFile, expectedRevision: number, startedAt: string) => void;
        onError: (errorMessage: string, token: number) => void;
        parseLayout: (content: string) => { ok: true; layout: RegionLayoutFile } | { ok: false; error: string };
    }
): number {
    let abortFn: (() => void) | null = null;
    const session = coordinator.startImport(uploadId, currentRevision, () => {
        abortFn?.();
    });
    const { token, expectedRevision, startedAt } = session;
    handlers.onStart?.(token, expectedRevision, startedAt);

    const cleanup = readFn(
        (content: string) => {
            const latestUpload = handlers.getCurrentUpload();
            if (!coordinator.canCommitImport(latestUpload, token)) {
                return;
            }

            const parseRes = handlers.parseLayout(content);
            if (!parseRes.ok) {
                if (coordinator.canCommitImport(handlers.getCurrentUpload(), token)) {
                    coordinator.cancelImport(uploadId);
                    handlers.onError(parseRes.error, token);
                }
                return;
            }

            handlers.onCommit(token, parseRes.layout, expectedRevision, startedAt);
        },
        () => {
            if (coordinator.isTokenActive(uploadId, token)) {
                const latestUpload = handlers.getCurrentUpload();
                if (coordinator.canCommitImport(latestUpload, token)) {
                    coordinator.cancelImport(uploadId);
                    handlers.onError("Failed to read the selected file from disk.", token);
                }
            }
        }
    );
    abortFn = cleanup;

    return token;
}

/**
 * Abandons an imported layout by clearing ROIs and removing importedLayout metadata.
 * Removes the imported-layout analysis gate and allows manual ROI creation.
 */
export function abandonImportedLayout(
    prev: UploadSnapshot,
    uploadId: string
): UploadSnapshot {
    const current = prev[uploadId];
    if (!current) return prev;

    return {
        ...prev,
        [uploadId]: {
            ...current,
            rois: [],
            importedLayout: null,
            activeLayoutImport: null,
            status: "ready",
            result: null,
            errorMessage: null,
            configRevision: current.configRevision + 1,
            activeRequestToken: null,
        },
    };
}

/**
 * Removes an upload item from the snapshot.
 */
export function removeUploadItem(
    prev: UploadSnapshot,
    uploadId: string
): UploadSnapshot {
    if (!prev[uploadId]) return prev;
    const next = { ...prev };
    delete next[uploadId];
    return next;
}

/**
 * Cleans up an in-flight controller entry only if its stored token matches the request token.
 */
export function cleanupControllerEntry(
    controllers: Record<string, InFlightController>,
    uploadId: string,
    requestToken: number
): void {
    if (controllers[uploadId]?.token === requestToken) {
        delete controllers[uploadId];
    }
}

// Aliases for regression harness or alternative naming preferences
export {
    startUploadAnalysis as startAnalysis,
    commitUploadSuccess as commitSuccess,
    commitUploadError as commitError,
    reconfigureUpload as handleReconfigure,
    removeUploadItem as handleRemove,
    cleanupControllerEntry as cleanupController,
    importRegionLayout as handleImportLayout,
    confirmRegionPlacement as handleConfirmPlacement,
    abandonImportedLayout as handleAbandonLayout,
};
