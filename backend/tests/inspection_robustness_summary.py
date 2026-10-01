"""
Dispense Lens - Inspection Robustness Summary Utility

Consumes the offline evaluator's JSON report and Manifest v1, validates identity
consistency, enforces input/output file safety, and generates a structured Markdown
summary report distinguishing:
- Measured behavior (reproducible pipeline outputs)
- Potential risks requiring engineering review (e.g. degraded inputs classified DETECTED)
- Demonstrated defects and execution failures
"""

from __future__ import annotations

import argparse
import json
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
    format_safe_schema_error,
    publish_report_file,
)


class SummarySafetyError(Exception):
    """Raised when output file safety checks fail (e.g. input overwrite collision)."""
    pass


class IdentityMismatchError(ValueError):
    """Raised when manifest and evaluation report identities do not match."""
    pass


def validate_identities(
    manifest: DatasetManifest,
    report: dict[str, Any],
) -> None:
    """Validate that the JSON report corresponds exactly to the supplied manifest.

    Verifies schema version, dataset_id, origin, case counts, case_ids,
    image paths, analysis profiles, and ground-truth label specifications.
    """
    if not isinstance(report, dict):
        raise IdentityMismatchError("Evaluation report root must be a JSON object.")

    report_version = report.get("report_version")
    if report_version != "v1":
        raise IdentityMismatchError(
            f"Unsupported report version: '{report_version}' (expected 'v1')."
        )

    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise IdentityMismatchError("Evaluation report is missing 'summary' section.")

    report_dataset_id = report.get("dataset_id") or summary.get("dataset_id")
    if report_dataset_id != manifest.dataset_id:
        raise IdentityMismatchError(
            f"Dataset ID mismatch: manifest has '{manifest.dataset_id}', "
            f"but report has '{report_dataset_id}'."
        )

    report_origin = report.get("origin")
    if report_origin != manifest.origin.value:
        raise IdentityMismatchError(
            f"Origin mismatch: manifest has '{manifest.origin.value}', "
            f"but report has '{report_origin}'."
        )

    report_cases = report.get("cases")
    if not isinstance(report_cases, list):
        raise IdentityMismatchError("Evaluation report is missing 'cases' list.")

    if len(report_cases) != len(manifest.cases):
        raise IdentityMismatchError(
            f"Case count mismatch: manifest contains {len(manifest.cases)} cases, "
            f"but report contains {len(report_cases)} cases."
        )

    for idx, (m_case, r_case) in enumerate(zip(manifest.cases, report_cases)):
        if not isinstance(r_case, dict):
            raise IdentityMismatchError(f"Report case at index {idx} is not a JSON object.")

        r_id = r_case.get("case_id")
        if m_case.case_id != r_id:
            raise IdentityMismatchError(
                f"Case ID mismatch at index {idx}: manifest has '{m_case.case_id}', "
                f"but report has '{r_id}'."
            )

        m_curr = m_case.current_image_path.strip()
        r_curr = (r_case.get("current_image_path") or "").strip()
        if m_curr != r_curr:
            raise IdentityMismatchError(
                f"Current image path mismatch in case '{m_case.case_id}': "
                f"manifest has '{m_curr}', but report has '{r_curr}'."
            )

        m_ref = (m_case.reference_image_path or "").strip()
        r_ref = (r_case.get("reference_image_path") or "").strip()
        if m_ref != r_ref:
            raise IdentityMismatchError(
                f"Reference image path mismatch in case '{m_case.case_id}': "
                f"manifest has '{m_ref}', but report has '{r_ref}'."
            )

        m_profile_dict = m_case.profile.model_dump(mode="json")
        r_profile_dict = r_case.get("profile")
        if m_profile_dict != r_profile_dict:
            raise IdentityMismatchError(
                f"Profile specification mismatch in case '{m_case.case_id}'."
            )

        r_sites = r_case.get("sites", [])
        if m_case.expected_statuses is not None:
            for s in r_sites:
                roi_id = s.get("roi_id")
                if roi_id in m_case.expected_statuses:
                    expected_val = m_case.expected_statuses[roi_id].value
                    if not s.get("is_labeled"):
                        raise IdentityMismatchError(
                            f"Label status mismatch in case '{m_case.case_id}', site '{roi_id}': "
                            "manifest has ground truth but report site is not labeled."
                        )
                    if s.get("expected_status") != expected_val:
                        raise IdentityMismatchError(
                            f"Expected status mismatch in case '{m_case.case_id}', site '{roi_id}': "
                            f"manifest has '{expected_val}', report has '{s.get('expected_status')}'."
                        )
                else:
                    if s.get("is_labeled"):
                        raise IdentityMismatchError(
                            f"Unexpected labeled site in case '{m_case.case_id}', site '{roi_id}': "
                            "manifest does not define expected status for this ROI."
                        )
        else:
            for s in r_sites:
                if s.get("is_labeled") or s.get("expected_status") is not None:
                    raise IdentityMismatchError(
                        f"Label mismatch in case '{m_case.case_id}': "
                        "manifest defines no expected statuses, but report site is marked labeled."
                    )


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
    - DEMONSTRATED_DEFECT: execution failure, omitted output site, or labeled control mismatch
    - POTENTIAL_RISK: unlabeled perturbation resulting in DETECTED (with or without warnings), or unexpected missing site
    - MEASURED_BASELINE: labeled control matching ground truth, or conservative gating observed
    """
    if case_res.get("status") == "ERROR" or case_res.get("error"):
        err = case_res.get("error") or "Execution failure"
        return "DEMONSTRATED_DEFECT", f"Case execution failed: {err}"

    sites = case_res.get("sites", [])
    omitted = [s.get("roi_id", "?") for s in sites if not s.get("output_present", True)]
    if omitted:
        return "DEMONSTRATED_DEFECT", f"Output omitted for site(s): {', '.join(omitted)}"

    # Check for labeled sites
    labeled_sites = [s for s in sites if s.get("is_labeled")]
    if labeled_sites:
        mismatches = [
            f"{s.get('roi_id')} (expected {s.get('expected_status')}, got {s.get('predicted_status')})"
            for s in labeled_sites
            if s.get("status_match") is False
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
    summary = report["summary"]
    cases = report["cases"]
    case_counts = summary.get("case_counts", {})
    site_counts = summary.get("site_counts", {})

    acc = summary.get("status_accuracy")
    if acc and isinstance(acc, dict) and acc.get("denominator", 0) > 0:
        acc_str = f"{acc['rate']*100:.1f}% ({acc['numerator']}/{acc['denominator']})"
        if acc["numerator"] == acc["denominator"]:
            acc_meaning = f"All {acc['denominator']} labeled control sites matched ground truth"
        else:
            acc_meaning = f"{acc['denominator'] - acc['numerator']} labeled control site(s) mismatched ground truth"
    else:
        acc_str = "null (no labels)"
        acc_meaning = "No labeled control sites present in dataset"

    abstention = summary.get("abstention_rate", {})
    if abstention and isinstance(abstention, dict) and abstention.get("denominator", 0) > 0:
        abs_str = f"{abstention.get('rate', 0.0)*100:.1f}% ({abstention.get('numerator', 0)}/{abstention.get('denominator', 0)})"
        abs_meaning = f"{abstention.get('numerator', 0)}/{abstention.get('denominator', 0)} total sites flagged UNASSESSED by quality gates"
    else:
        abs_str = "0.0% (0/0)"
        abs_meaning = "No sites evaluated"

    false_missing = summary.get("false_missing_rate", {})
    if false_missing and isinstance(false_missing, dict) and false_missing.get("denominator", 0) > 0:
        fm_str = f"{false_missing.get('rate', 0.0)*100:.1f}% ({false_missing.get('numerator', 0)}/{false_missing.get('denominator', 0)})"
        fm_meaning = f"{false_missing.get('numerator', 0)}/{false_missing.get('denominator', 0)} non-missing labeled control sites misclassified as MISSING"
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
    unlabeled_sites_cnt = site_counts.get("unlabeled_sites", site_counts.get("unlabeled_sites_count", 0))
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
            err_msg = c.get("error") or "Execution failure"
            site_parts.append(f"**FAILED CASE**: {err_msg}")
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
    defects = [c for c in cases if classify_case_finding(c)[0] == "DEMONSTRATED_DEFECT"]
    risks = [c for c in cases if classify_case_finding(c)[0] == "POTENTIAL_RISK"]
    baselines = [c for c in cases if classify_case_finding(c)[0] == "MEASURED_BASELINE"]

    lines.extend([
        "",
        "## 3. Finding Breakdown & Review Inventory",
        "",
        f"### A. Demonstrated Defects ({len(defects)})",
    ])
    if defects:
        for c in defects:
            lines.append(f"- **`{c.get('case_id')}`:** {classify_case_finding(c)[1]}")
    else:
        lines.append("- None detected in this evaluation run.")

    lines.extend([
        "",
        f"### B. Potential Risks Requiring Engineering Review ({len(risks)})",
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
        f"### C. Measured Baseline Outcomes ({len(baselines)})",
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

    # Validate matching identities
    try:
        validate_identities(manifest, report)
    except IdentityMismatchError as exc:
        sys.stderr.write(f"Fatal error: Manifest and report identities do not match: {exc}\n")
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
    summary_md = generate_markdown_summary(manifest, report)

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
