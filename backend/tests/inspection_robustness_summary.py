"""
Dispense Lens - Inspection Robustness Summary Utility

Consumes the offline evaluator's JSON report and Manifest v1, validates identity
consistency, enforces input/output file safety, and generates a structured Markdown
summary report distinguishing:
- Measured behavior (reproducible pipeline outputs)
- Potential risks requiring engineering review (e.g. degraded inputs classified DETECTED)
- Demonstrated inspection defects (control mismatches, omitted site outputs)
- Input and execution failures (filesystem access, image decode/validation, execution error)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from pydantic import ValidationError

# Ensure backend root is on sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from tests.vision_inspection_dataset import (
    DatasetManifest,
    compute_dataset_metrics,
    format_safe_schema_error,
    publish_report_file,
)


class SummarySafetyError(Exception):
    """Raised when output file safety checks fail (e.g. input overwrite collision)."""
    pass


class IdentityMismatchError(ValueError):
    """Raised when manifest and evaluation report identities or structures do not match."""
    pass


def validate_identities(
    manifest: DatasetManifest,
    report: dict[str, Any],
) -> None:
    """Validate that the JSON report corresponds exactly to the supplied manifest.

    Verifies schema version, dataset_id, origin, case counts, case_ids,
    image paths, analysis profiles, complete site membership, structural types,
    and checks metric consistency between summary and case records.
    """
    if not isinstance(report, dict):
        raise IdentityMismatchError("Evaluation report root must be a JSON object.")

    # 1. Report version / schema
    report_version = report.get("report_version")
    if not isinstance(report_version, str) or report_version != "v1":
        raise IdentityMismatchError(
            f"Unsupported report version: '{report_version}' (expected 'v1')."
        )

    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise IdentityMismatchError("Evaluation report is missing 'summary' section.")

    # 2. Dataset ID & Origin
    report_dataset_id = report.get("dataset_id") or summary.get("dataset_id")
    if not isinstance(report_dataset_id, str) or report_dataset_id != manifest.dataset_id:
        raise IdentityMismatchError("Dataset ID mismatch between manifest and report.")

    report_origin = report.get("origin")
    if not isinstance(report_origin, str) or report_origin != manifest.origin.value:
        raise IdentityMismatchError("Dataset origin mismatch between manifest and report.")

    # 3. Case count
    report_cases = report.get("cases")
    if not isinstance(report_cases, list):
        raise IdentityMismatchError("Evaluation report 'cases' must be a list.")

    if len(report_cases) != len(manifest.cases):
        raise IdentityMismatchError("Case count mismatch between manifest and report.")

    # 4. Per-case identity, paths, profile, and complete site records
    for idx, (m_case, r_case) in enumerate(zip(manifest.cases, report_cases)):
        if not isinstance(r_case, dict):
            raise IdentityMismatchError(f"Report case at index {idx} must be a JSON object.")

        r_id = r_case.get("case_id")
        if not isinstance(r_id, str) or m_case.case_id != r_id:
            raise IdentityMismatchError(f"Case ID mismatch at index {idx}.")

        # Image path validation
        r_curr = r_case.get("current_image_path")
        if not isinstance(r_curr, str):
            raise IdentityMismatchError(f"Case '{m_case.case_id}' current_image_path must be a string.")
        if m_case.current_image_path.strip() != r_curr.strip():
            raise IdentityMismatchError(f"Case '{m_case.case_id}' current_image_path mismatch.")

        r_ref = r_case.get("reference_image_path")
        if r_ref is not None and not isinstance(r_ref, str):
            raise IdentityMismatchError(f"Case '{m_case.case_id}' reference_image_path must be a string or null.")
        m_ref_str = (m_case.reference_image_path or "").strip()
        r_ref_str = (r_ref or "").strip()
        if m_ref_str != r_ref_str:
            raise IdentityMismatchError(f"Case '{m_case.case_id}' reference_image_path mismatch.")

        # Profile specification
        r_profile = r_case.get("profile")
        if not isinstance(r_profile, dict):
            raise IdentityMismatchError(f"Case '{m_case.case_id}' profile must be a JSON object.")
        if m_case.profile.model_dump(mode="json") != r_profile:
            raise IdentityMismatchError(f"Case '{m_case.case_id}' profile specification mismatch.")

        # Configured ROIs from manifest profile
        configured_roi_ids = [roi.roi_id for roi in m_case.profile.rois]
        configured_roi_set = set(configured_roi_ids)

        # Validate sites list
        r_sites = r_case.get("sites")
        if not isinstance(r_sites, list):
            raise IdentityMismatchError(f"Case '{m_case.case_id}' sites must be a list.")

        if len(r_sites) != len(configured_roi_ids):
            raise IdentityMismatchError(
                f"Case '{m_case.case_id}' site count mismatch: "
                f"expected {len(configured_roi_ids)} configured ROIs, got {len(r_sites)}."
            )

        # Validate each site structure and exact/unique ROI membership
        seen_roi_ids: set[str] = set()
        for site_idx, s in enumerate(r_sites):
            if not isinstance(s, dict):
                raise IdentityMismatchError(
                    f"Case '{m_case.case_id}' site at index {site_idx} must be a JSON object."
                )

            roi_id = s.get("roi_id")
            if not isinstance(roi_id, str):
                raise IdentityMismatchError(
                    f"Case '{m_case.case_id}' site at index {site_idx} missing valid roi_id."
                )

            if roi_id in seen_roi_ids:
                raise IdentityMismatchError(
                    f"Case '{m_case.case_id}' contains duplicate site ID: '{roi_id}'."
                )
            seen_roi_ids.add(roi_id)

            if roi_id not in configured_roi_set:
                raise IdentityMismatchError(
                    f"Case '{m_case.case_id}' contains unknown site ID '{roi_id}' not in profile ROIs."
                )

            # Validate boolean site flags
            is_labeled = s.get("is_labeled")
            output_present = s.get("output_present")
            case_failed = s.get("case_failed")

            if not isinstance(is_labeled, bool):
                raise IdentityMismatchError(f"Site '{roi_id}' in case '{m_case.case_id}' is_labeled must be a boolean.")
            if not isinstance(output_present, bool):
                raise IdentityMismatchError(f"Site '{roi_id}' in case '{m_case.case_id}' output_present must be a boolean.")
            if not isinstance(case_failed, bool):
                raise IdentityMismatchError(f"Site '{roi_id}' in case '{m_case.case_id}' case_failed must be a boolean.")

            # Ground truth alignment
            if m_case.expected_statuses and roi_id in m_case.expected_statuses:
                expected_val = m_case.expected_statuses[roi_id].value
                if not is_labeled:
                    raise IdentityMismatchError(
                        f"Site '{roi_id}' in case '{m_case.case_id}' should be labeled according to manifest."
                    )
                if s.get("expected_status") != expected_val:
                    raise IdentityMismatchError(
                        f"Site '{roi_id}' in case '{m_case.case_id}' expected_status mismatch."
                    )

                # Validate status_match consistency
                pred_status = s.get("predicted_status")
                expected_match = (output_present and (pred_status == expected_val))
                if s.get("status_match") != expected_match:
                    raise IdentityMismatchError(
                        f"Site '{roi_id}' in case '{m_case.case_id}' status_match contradicts expected/predicted states."
                    )
            else:
                if is_labeled or s.get("expected_status") is not None:
                    raise IdentityMismatchError(
                        f"Site '{roi_id}' in case '{m_case.case_id}' is unexpectedly marked labeled."
                    )
                if s.get("status_match") is not None:
                    raise IdentityMismatchError(
                        f"Site '{roi_id}' in case '{m_case.case_id}' status_match should be null for unlabeled site."
                    )

        if seen_roi_ids != configured_roi_set:
            raise IdentityMismatchError(
                f"Case '{m_case.case_id}' does not cover all configured ROIs exactly."
            )

    # 5. Recompute dataset metrics using compute_dataset_metrics and verify consistency
    recomputed = compute_dataset_metrics(report_cases)

    # Check case counts
    r_cc = summary.get("case_counts")
    e_cc = recomputed["case_counts"]
    if not isinstance(r_cc, dict) or r_cc != e_cc:
        raise IdentityMismatchError("Report case_counts contradicts individual case records.")

    # Check site counts
    r_sc = summary.get("site_counts")
    e_sc = recomputed["site_counts"]
    if not isinstance(r_sc, dict):
        raise IdentityMismatchError("Report site_counts must be a JSON object.")
    for k in (
        "total_sites",
        "eligible_labeled_sites",
        "unlabeled_sites",
        "emitted_predictions",
        "correct_labeled_sites",
        "incorrect_labeled_sites",
    ):
        if r_sc.get(k) != e_sc.get(k):
            raise IdentityMismatchError(f"Report site_counts '{k}' contradicts individual site records.")

    def _validate_rate_field(
        metric_name: str,
        metric_dict: dict[str, Any],
        expected_rate: float,
    ) -> None:
        if "rate" not in metric_dict:
            raise IdentityMismatchError(f"Report {metric_name} missing 'rate' field.")
        val = metric_dict["rate"]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
            raise IdentityMismatchError(f"Report {metric_name} rate must be a finite numeric non-boolean value.")
        if val < 0.0 or val > 1.0:
            raise IdentityMismatchError(f"Report {metric_name} rate must be between 0.0 and 1.0.")
        if abs(val - expected_rate) > 1e-4:
            raise IdentityMismatchError(
                f"Report {metric_name} rate ({val}) contradicts recomputed metric rate ({expected_rate})."
            )

    # Check status accuracy
    r_acc = summary.get("status_accuracy")
    e_acc = recomputed["status_accuracy"]
    if e_acc is None:
        if r_acc is not None:
            raise IdentityMismatchError("Report status_accuracy must be null when there are no eligible labeled sites.")
    else:
        if not isinstance(r_acc, dict):
            raise IdentityMismatchError("Report status_accuracy must be a JSON object.")
        if (
            isinstance(r_acc.get("numerator"), bool)
            or r_acc.get("numerator") != e_acc["numerator"]
            or isinstance(r_acc.get("denominator"), bool)
            or r_acc.get("denominator") != e_acc["denominator"]
        ):
            raise IdentityMismatchError("Report status_accuracy contradicts labeled site records.")
        _validate_rate_field("status_accuracy", r_acc, e_acc["rate"])

    # Check abstention rate
    r_abs = summary.get("abstention_rate")
    e_abs = recomputed["abstention_rate"]
    if not isinstance(r_abs, dict):
        raise IdentityMismatchError("Report abstention_rate must be a JSON object.")
    if (
        isinstance(r_abs.get("numerator"), bool)
        or r_abs.get("numerator") != e_abs["numerator"]
        or isinstance(r_abs.get("denominator"), bool)
        or r_abs.get("denominator") != e_abs["denominator"]
    ):
        raise IdentityMismatchError("Report abstention_rate contradicts site prediction records.")
    _validate_rate_field("abstention_rate", r_abs, e_abs["rate"])

    # Check false missing rate
    r_fm = summary.get("false_missing_rate")
    e_fm = recomputed["false_missing_rate"]
    if not isinstance(r_fm, dict):
        raise IdentityMismatchError("Report false_missing_rate must be a JSON object.")
    if (
        isinstance(r_fm.get("numerator"), bool)
        or r_fm.get("numerator") != e_fm["numerator"]
        or isinstance(r_fm.get("denominator"), bool)
        or r_fm.get("denominator") != e_fm["denominator"]
    ):
        raise IdentityMismatchError("Report false_missing_rate contradicts ground-truth label records.")
    _validate_rate_field("false_missing_rate", r_fm, e_fm["rate"])


def verify_summary_output_safe(
    output_path: Path,
    manifest_path: Path,
    report_path: Path,
    overwrite: bool,
) -> None:
    """Ensure output summary path does not collide with manifest or report inputs."""
    try:
        out_resolved = output_path.resolve()
        m_resolved = manifest_path.resolve()
        r_resolved = report_path.resolve()
    except (OSError, RuntimeError) as exc:
        raise SummarySafetyError("Filesystem error resolving paths during output preflight.") from exc

    # 1. Direct path equality
    if out_resolved == m_resolved:
        raise SummarySafetyError(
            f"Output path cannot overwrite manifest input: '{output_path.name}'"
        )
    if out_resolved == r_resolved:
        raise SummarySafetyError(
            f"Output path cannot overwrite report input: '{output_path.name}'"
        )

    # 2. Filesystem alias check if output file exists
    if output_path.exists():
        try:
            if manifest_path.exists() and os.path.samefile(output_path, manifest_path):
                raise SummarySafetyError(
                    f"Output path resolves to manifest input via filesystem alias: '{output_path.name}'"
                )
            if report_path.exists() and os.path.samefile(output_path, report_path):
                raise SummarySafetyError(
                    f"Output path resolves to report input via filesystem alias: '{output_path.name}'"
                )
        except (OSError, RuntimeError):
            pass

        if not overwrite:
            raise FileExistsError(
                f"Output summary '{output_path.name}' already exists. Use --overwrite to replace it."
            )


def classify_case_finding(case_res: dict[str, Any]) -> tuple[str, str]:
    """Classify case outcome into a risk category and rationale purely from report data.

    Categories:
    - INPUT_FAILURE: input/environment failure (filesystem access, image decode, path validation)
    - EXECUTION_FAILURE: unexpected CV/pipeline execution failure
    - DEMONSTRATED_DEFECT: demonstrated inspection defect (control mismatch or omitted site output)
    - POTENTIAL_RISK: unlabeled perturbation resulting in DETECTED (with/without warnings) or missing site
    - MEASURED_BASELINE: labeled control matching ground truth, or conservative gating observed
    """
    if case_res.get("status") == "ERROR" or case_res.get("error"):
        err = case_res.get("error")
        if isinstance(err, dict):
            err_cat = err.get("category", "EXECUTION_ERROR")
            err_msg = err.get("message", "Pipeline execution error")
        elif isinstance(err, str):
            err_cat = "EXECUTION_ERROR"
            err_msg = err
        else:
            err_cat = "EXECUTION_ERROR"
            err_msg = "Unknown execution error"

        if err_cat in ("FILESYSTEM_ACCESS", "IMAGE_VALIDATION", "PATH_VALIDATION"):
            return "INPUT_FAILURE", f"Input failure ({err_cat}): {err_msg}"
        return "EXECUTION_FAILURE", f"Execution failure ({err_cat}): {err_msg}"

    sites = case_res.get("sites", [])
    omitted = [s.get("roi_id", "?") for s in sites if not s.get("output_present", True)]
    if omitted:
        return "DEMONSTRATED_DEFECT", f"Output omitted for site(s): {', '.join(omitted)}"

    # Check for labeled sites: compute agreement directly from expected vs predicted states
    labeled_sites = [s for s in sites if s.get("is_labeled")]
    if labeled_sites:
        mismatches = [
            f"{s.get('roi_id')} (expected {s.get('expected_status')}, got {s.get('predicted_status')})"
            for s in labeled_sites
            if s.get("expected_status") != s.get("predicted_status")
        ]
        if mismatches:
            return "DEMONSTRATED_DEFECT", f"Control status mismatch on site(s): {', '.join(mismatches)}"
        return "MEASURED_BASELINE", f"All {len(labeled_sites)} labeled control site(s) matched ground truth."

    # Unlabeled perturbation cases
    analysis_status = case_res.get("analysis_status")
    if analysis_status in ("UNCALIBRATED", "FEATURES_ONLY"):
        norm_status = "UNCALIBRATED"
    else:
        norm_status = analysis_status or "UNKNOWN"

    case_warnings = case_res.get("case_warnings", [])
    site_warnings = [w for s in sites for w in s.get("warnings", [])]
    has_warnings = bool(case_warnings or site_warnings)

    all_detected = bool(sites) and all(s.get("predicted_status") == "DETECTED" for s in sites)
    any_unassessed = any(s.get("predicted_status") == "UNASSESSED" for s in sites)
    any_missing = any(s.get("predicted_status") == "MISSING" for s in sites)

    if all_detected:
        if has_warnings:
            return (
                "POTENTIAL_RISK",
                f"Unlabeled perturbation produced DETECTED ({norm_status}) with warning(s); requires review.",
            )
        return (
            "POTENTIAL_RISK",
            f"Unlabeled perturbation produced DETECTED ({norm_status}) without warnings; requires review against domain expectations.",
        )

    if any_unassessed or norm_status == "UNRELIABLE":
        unassessed_cnt = sum(1 for s in sites if s.get("predicted_status") == "UNASSESSED")
        return (
            "MEASURED_BASELINE",
            f"Unlabeled perturbation triggered {norm_status} ({unassessed_cnt}/{len(sites)} sites UNASSESSED); requires review.",
        )

    if any_missing:
        missing_cnt = sum(1 for s in sites if s.get("predicted_status") == "MISSING")
        return (
            "POTENTIAL_RISK",
            f"Unlabeled perturbation produced MISSING on {missing_cnt}/{len(sites)} sites; requires review.",
        )

    return "MEASURED_BASELINE", f"Measured pipeline response: {norm_status}."


def generate_markdown_summary(
    manifest: DatasetManifest,
    report: dict[str, Any],
) -> str:
    """Generate comprehensive Markdown summary from validated manifest and report data."""
    cases = report["cases"]
    recomputed = compute_dataset_metrics(cases)
    case_counts = recomputed["case_counts"]
    site_counts = recomputed["site_counts"]

    acc = recomputed["status_accuracy"]
    if acc and isinstance(acc, dict) and acc.get("denominator", 0) > 0:
        acc_rate = acc["rate"]
        acc_num = acc["numerator"]
        acc_den = acc["denominator"]
        acc_str = f"{acc_rate * 100:.1f}% ({acc_num}/{acc_den})"
        if acc_num == acc_den:
            acc_meaning = f"All {acc_den} labeled control sites matched ground truth"
        else:
            acc_meaning = f"{acc_den - acc_num} labeled control site(s) mismatched ground truth"
    else:
        acc_str = "null (no labels)"
        acc_meaning = "No labeled control sites present in dataset"

    abstention = recomputed["abstention_rate"]
    if abstention and isinstance(abstention, dict) and abstention.get("denominator", 0) > 0:
        abs_rate = abstention["rate"]
        abs_num = abstention["numerator"]
        abs_den = abstention["denominator"]
        abs_str = f"{abs_rate * 100:.1f}% ({abs_num}/{abs_den})"
        abs_meaning = f"{abs_num}/{abs_den} total sites flagged UNASSESSED by quality gates"
    else:
        abs_str = "0.0% (0/0)"
        abs_meaning = "No sites evaluated"

    false_missing = recomputed["false_missing_rate"]
    if false_missing and isinstance(false_missing, dict) and false_missing.get("denominator", 0) > 0:
        fm_rate = false_missing["rate"]
        fm_num = false_missing["numerator"]
        fm_den = false_missing["denominator"]
        fm_str = f"{fm_rate * 100:.1f}% ({fm_num}/{fm_den})"
        fm_meaning = f"{fm_num}/{fm_den} non-missing labeled control sites misclassified as MISSING"
    else:
        fm_str = "null (no non-missing controls)"
        fm_meaning = "No non-missing labeled control sites evaluated"

    # Status distribution
    calibrated_cnt = sum(1 for c in cases if c.get("analysis_status") == "CALIBRATED")
    uncalibrated_cnt = sum(1 for c in cases if c.get("analysis_status") in ("UNCALIBRATED", "FEATURES_ONLY"))
    unreliable_cnt = sum(1 for c in cases if c.get("analysis_status") == "UNRELIABLE")
    error_cnt = sum(1 for c in cases if c.get("status") == "ERROR")

    failed_cases_cnt = case_counts.get("failed_cases", 0)
    total_cases_cnt = case_counts.get("total_cases", len(cases))
    if failed_cases_cnt > 0:
        total_cases_meaning = f"{failed_cases_cnt} case(s) failed with execution error"
    else:
        total_cases_meaning = f"All {total_cases_cnt} cases completed without execution error"

    labeled_sites_cnt = site_counts.get("eligible_labeled_sites", 0)
    unlabeled_sites_cnt = site_counts.get("unlabeled_sites", 0)
    total_sites_meaning = f"{labeled_sites_cnt} labeled control sites, {unlabeled_sites_cnt} unlabeled perturbation sites"

    dist_meaning = (
        f"{unreliable_cnt}/{len(cases)} cases gated UNRELIABLE; "
        f"{uncalibrated_cnt} UNCALIBRATED; {calibrated_cnt} CALIBRATED; {error_cnt} ERROR"
    )

    lines: list[str] = [
        f"# Inspection Robustness Checkpoint Summary: {manifest.dataset_id}",
        "",
        "> [!IMPORTANT]",
        "> **Evaluation Context & Compliance Notice**",
        "> This checkpoint summarizes offline evaluation outcomes across configured cases.",
        "> - **Absence of diagnostic defect observations is NOT an automatic pass.**",
        "> - **Repeatable detection under optical degradation is a potential risk, not proof of industrial robustness.**",
        "> - **Ground truth is strictly limited to verified clean controls.** Perturbations and degraded cases remain unassigned.",
        "",
        "## 1. Executive Metrics",
        "",
        "| Metric | Value | Meaning |",
        "| :--- | :--- | :--- |",
        f"| **Dataset ID** | `{manifest.dataset_id}` | Manifest v1 dataset identifier |",
        f"| **Dataset Origin** | `{manifest.origin.value}` | Evaluated dataset origin |",
        f"| **Total Cases** | `{total_cases_cnt}` ({case_counts.get('successful_cases', 0)} success, {failed_cases_cnt} failed) | {total_cases_meaning} |",
        f"| **Total Configured Sites** | `{site_counts.get('total_sites', 0)}` ({labeled_sites_cnt} labeled, {unlabeled_sites_cnt} unlabeled) | {total_sites_meaning} |",
        f"| **Status Accuracy (Controls)** | **{acc_str}** | {acc_meaning} |",
        f"| **Pipeline Abstention Rate** | **{abs_str}** | {abs_meaning} |",
        f"| **False-Missing Rate (Controls)** | **{fm_str}** | {fm_meaning} |",
        f"| **Case Status Distribution** | `{calibrated_cnt}` CALIBRATED, `{uncalibrated_cnt}` UNCALIBRATED, `{unreliable_cnt}` UNRELIABLE, `{error_cnt}` ERROR | {dist_meaning} |",
        "",
        "## 2. Categorized Robustness Findings",
        "",
        "| Case ID | Perturbation | Status | Sites (Assessed/Exp) | Current Cov | Ref Cov | Site Statuses & Warnings | Emitted Observations | Finding Classification | Rationale |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for c in cases:
        cid = c.get("case_id", "")
        desc = c.get("description", "")
        if ":" in desc:
            desc = desc.split(":", 1)[0]

        is_failed = (c.get("status") == "ERROR") or bool(c.get("error"))
        status_val = c.get("analysis_status")
        if is_failed:
            status_display = "**ERROR**"
        elif status_val in ("UNCALIBRATED", "FEATURES_ONLY"):
            status_display = "`UNCALIBRATED`"
        elif status_val:
            status_display = f"`{status_val}`"
        else:
            status_display = "`N/A`"

        curr_cov = c.get("current_inspection_coverage") or {}
        exp_count = curr_cov.get("expected_roi_count", len(c.get("sites", [])))
        ass_count = curr_cov.get("assessed_roi_count", sum(1 for s in c.get("sites", []) if s.get("predicted_status") in ("DETECTED", "MISSING")))
        sites_ratio = f"{ass_count}/{exp_count}"
        curr_cov_status = f"`{curr_cov.get('status', 'N/A')}`" if curr_cov else "`N/A`"

        ref_cov = c.get("reference_inspection_coverage")
        if ref_cov:
            ref_cov_status = f"`{ref_cov.get('status', 'N/A')}` ({ref_cov.get('assessed_roi_count', 0)}/{ref_cov.get('expected_roi_count', 0)})"
        else:
            ref_cov_status = "N/A"

        site_parts = []
        if is_failed:
            err_obj = c.get("error")
            err_cat = err_obj.get("category", "ERROR") if isinstance(err_obj, dict) else "ERROR"
            err_msg = err_obj.get("message", str(err_obj)) if isinstance(err_obj, dict) else str(err_obj or "Execution failure")
            site_parts.append(f"**FAILED CASE ({err_cat})**: {err_msg}")
        else:
            for s in c.get("sites", []):
                rid = s.get("roi_id", "?")
                if not s.get("output_present", True):
                    site_parts.append(f"`{rid}`: **OMITTED OUTPUT**")
                else:
                    p = s.get("predicted_status", "UNKNOWN")
                    sw = s.get("warnings", [])
                    if sw:
                        site_parts.append(f"`{rid}`: {p} (warnings: {'; '.join(sw)})")
                    else:
                        site_parts.append(f"`{rid}`: {p}")
        sites_str = "<br>".join(site_parts) if site_parts else "None"

        obs_list = c.get("affected_observations", [])
        if obs_list:
            obs_parts = []
            for o in obs_list:
                otype = o.get("observation_type", "")
                oval = o.get("value", "")
                aff = o.get("affected_roi_ids", [])
                obs_parts.append(f"{otype}:{oval} (affected: {aff})")
            obs_str = "<br>".join(obs_parts)
        else:
            obs_str = "None"

        category, rationale = classify_case_finding(c)
        cat_badge = f"**{category}**" if category != "MEASURED_BASELINE" else "MEASURED_BASELINE"

        lines.append(
            f"| `{cid}` | {desc} | {status_display} | {sites_ratio} | {curr_cov_status} | {ref_cov_status} | {sites_str} | {obs_str} | {cat_badge} | {rationale} |"
        )

    # Section 3: Dynamic Breakdown
    inspection_defects = [c for c in cases if classify_case_finding(c)[0] == "DEMONSTRATED_DEFECT"]
    exec_failures = [c for c in cases if classify_case_finding(c)[0] in ("INPUT_FAILURE", "EXECUTION_FAILURE")]
    risks = [c for c in cases if classify_case_finding(c)[0] == "POTENTIAL_RISK"]
    baselines = [c for c in cases if classify_case_finding(c)[0] == "MEASURED_BASELINE"]

    lines.extend([
        "",
        "## 3. Finding Breakdown & Review Inventory",
        "",
        f"### A. Demonstrated Inspection Defects ({len(inspection_defects)})",
    ])
    if inspection_defects:
        for c in inspection_defects:
            lines.append(f"- **`{c.get('case_id')}`:** {classify_case_finding(c)[1]}")
    else:
        lines.append("- None detected in this evaluation run.")

    lines.extend([
        "",
        f"### B. Execution and Input Failures ({len(exec_failures)})",
    ])
    if exec_failures:
        for c in exec_failures:
            lines.append(f"- **`{c.get('case_id')}`:** {classify_case_finding(c)[1]}")
    else:
        lines.append("- None detected in this evaluation run.")

    lines.extend([
        "",
        f"### C. Potential Risks Requiring Engineering Review ({len(risks)})",
    ])
    if risks:
        for c in risks:
            cov_val = c.get("current_inspection_coverage", {}).get("status", "N/A")
            lines.append(
                f"- **`{c.get('case_id')}`:** {classify_case_finding(c)[1]} "
                f"(Status: `{c.get('analysis_status')}` / Coverage: `{cov_val}`)."
            )
    else:
        lines.append("- No potential risk cases identified.")

    lines.extend([
        "",
        f"### D. Measured Baseline Outcomes ({len(baselines)})",
    ])
    if baselines:
        for c in baselines:
            lines.append(f"- **`{c.get('case_id')}`:** {classify_case_finding(c)[1]}")
    else:
        lines.append("- No baseline cases evaluated.")

    lines.extend([
        "",
        "## 4. Methodological Boundaries",
        "",
        "- **Purely Synthetic Proof-of-Concept:** Evaluates mathematical pipeline properties under controlled perturbations. Does not represent physical PCB textures, meniscus variations, or factory dust.",
        "- **Absence of Observations is Not a Pass:** Absence of a diagnostic defect observation on degraded captures indicates the case was either unassessed or passed ungated; it does not indicate production readiness.",
        "- **Evaluation Tooling Scope:** Summary generation is diagnostic and reporting only. No production algorithms, thresholds, or scoring rules were altered.",
    ])

    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for robustness summary utility."""
    parser = argparse.ArgumentParser(
        prog="inspection_robustness_summary",
        description="Generates a Markdown robustness summary from an evaluation report and manifest.",
    )
    parser.add_argument(
        "-m",
        "--manifest",
        type=Path,
        required=True,
        help="Path to DatasetManifest JSON file.",
    )
    parser.add_argument(
        "-r",
        "--report",
        type=Path,
        required=True,
        help="Path to evaluation report JSON file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Optional path to output Markdown file. If omitted, summary is printed to stdout.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Authorize overwriting existing output summary file.",
    )
    return parser


def main() -> int:
    """CLI entry point for inspection robustness summary."""
    parser = build_arg_parser()
    args = parser.parse_args()

    # Preflight resolution of CLI arguments
    try:
        manifest_path: Path = args.manifest.resolve()
        if not manifest_path.exists():
            sys.stderr.write(f"Fatal error: Manifest file not found: '{manifest_path.name}'\n")
            return 1
        if not manifest_path.is_file():
            sys.stderr.write(f"Fatal error: Manifest path is not a regular file: '{manifest_path.name}'\n")
            return 1

        report_path: Path = args.report.resolve()
        if not report_path.exists():
            sys.stderr.write(f"Fatal error: Report file not found: '{report_path.name}'\n")
            return 1
        if not report_path.is_file():
            sys.stderr.write(f"Fatal error: Report path is not a regular file: '{report_path.name}'\n")
            return 1

        output_path: Path | None = args.output.resolve() if args.output else None
    except (OSError, RuntimeError):
        sys.stderr.write("Fatal error: Filesystem access error occurred during CLI path preflight\n")
        return 1

    # Load and parse manifest
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        sys.stderr.write(f"Fatal error: Failed to read manifest file: '{manifest_path.name}'\n")
        return 1

    try:
        raw_manifest = json.loads(manifest_text)
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"Fatal error: Manifest syntax error: Invalid JSON at line {exc.lineno}, column {exc.colno}\n"
        )
        return 1

    try:
        manifest = DatasetManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        safe_schema_msg = format_safe_schema_error(exc)
        sys.stderr.write(f"Fatal error: Manifest schema validation failed:\n{safe_schema_msg}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Manifest validation failed: {type(exc).__name__}\n")
        return 1

    # Load and parse report
    try:
        report_text = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        sys.stderr.write(f"Fatal error: Failed to read report file: '{report_path.name}'\n")
        return 1

    try:
        report = json.loads(report_text)
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"Fatal error: Report syntax error: Invalid JSON at line {exc.lineno}, column {exc.colno}\n"
        )
        return 1

    if not isinstance(report, dict):
        sys.stderr.write("Fatal error: Report root must be a JSON object.\n")
        return 1

    # Validate matching identities, structural types, and metrics
    try:
        validate_identities(manifest, report)
    except IdentityMismatchError:
        sys.stderr.write("Fatal error: Report validation failed: identity, structure, or metric discrepancy detected.\n")
        return 1
    except Exception:
        sys.stderr.write("Fatal error: Malformed report JSON or structure.\n")
        return 1

    # Preflight output safety if writing to file
    if output_path is not None:
        try:
            verify_summary_output_safe(
                output_path, manifest_path, report_path, overwrite=args.overwrite
            )
        except (SummarySafetyError, FileExistsError) as exc:
            sys.stderr.write(f"Fatal error: {exc}\n")
            return 1

    # Generate Markdown summary
    try:
        summary_md = generate_markdown_summary(manifest, report)
    except Exception:
        sys.stderr.write("Fatal error: Failed to generate summary from report structure.\n")
        return 1

    # Publish output safely
    if output_path is not None:
        temp_path = output_path.with_name(f".tmp_{output_path.name}_{uuid.uuid4().hex}")
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(summary_md, encoding="utf-8")
            publish_report_file(temp_path, output_path, overwrite=args.overwrite)
        except FileExistsError:
            sys.stderr.write(
                f"Fatal error: Output summary '{output_path.name}' already exists. Use --overwrite to replace it.\n"
            )
            return 1
        except OSError as exc:
            if "Atomic no-clobber publication unsupported" in str(exc):
                sys.stderr.write(f"Fatal error: {exc}\n")
            else:
                sys.stderr.write(
                    f"Fatal error: Filesystem access error while writing summary file '{output_path.name}'\n"
                )
            return 1
        except RuntimeError:
            sys.stderr.write(
                f"Fatal error: Filesystem access error while writing summary file '{output_path.name}'\n"
            )
            return 1
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

        sys.stdout.write(f"Robustness summary written to: {output_path.name}\n")
    else:
        sys.stdout.write(summary_md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
