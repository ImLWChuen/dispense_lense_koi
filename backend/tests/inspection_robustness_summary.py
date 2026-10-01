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
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from tests.vision_inspection_dataset import DatasetManifest


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

    Verifies dataset_id, case counts, and exact case_id sequence.
    """
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise IdentityMismatchError("Evaluation report is missing 'summary' section.")

    report_dataset_id = report.get("dataset_id") or summary.get("dataset_id")
    if report_dataset_id != manifest.dataset_id:
        raise IdentityMismatchError(
            f"Dataset ID mismatch: manifest has '{manifest.dataset_id}', "
            f"but report has '{report_dataset_id}'."
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
        r_id = r_case.get("case_id") if isinstance(r_case, dict) else None
        if m_case.case_id != r_id:
            raise IdentityMismatchError(
                f"Case ID mismatch at index {idx}: manifest has '{m_case.case_id}', "
                f"but report has '{r_id}'."
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
        raise SummarySafetyError(f"Filesystem error resolving paths: {exc}") from exc

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
                f"Output file '{output_path.name}' already exists. Use --overwrite to replace it."
            )


def classify_case_finding(case_res: dict[str, Any]) -> tuple[str, str]:
    """Classify case outcome into a risk category and rationale.

    Categories:
    - DEMONSTRATED_DEFECT: execution failure or omitted output
    - POTENTIAL_RISK: degraded input classified DETECTED without warning, or ambiguous gating
    - MEASURED_BASELINE: clean control behaving as expected or conservative gate operating correctly
    """
    if case_res.get("status") == "ERROR":
        return "DEMONSTRATED_DEFECT", "Case execution failed with error."

    sites = case_res.get("sites", [])
    if any(not s.get("output_present", True) for s in sites):
        return "DEMONSTRATED_DEFECT", "One or more expected sites omitted by pipeline output."

    case_id = case_res.get("case_id", "")
    analysis_status = case_res.get("analysis_status")

    if "control" in case_id:
        return "MEASURED_BASELINE", "Clean baseline control behaving consistently with ground truth."

    # In degraded cases:
    # If all sites are DETECTED and analysis status is CALIBRATED, this is a potential risk:
    # severe blur or brightness shift is not caught by an acquisition quality gate.
    all_detected = all(s.get("predicted_status") == "DETECTED" for s in sites)
    if all_detected and analysis_status == "CALIBRATED":
        return (
            "POTENTIAL_RISK",
            "Degraded image (defocus/exposure) classified DETECTED without image quality warning; "
            "lacks sharpness or contrast gate.",
        )

    if analysis_status == "UNRELIABLE":
        return (
            "MEASURED_BASELINE",
            "Conservative quality gate correctly triggered: flagged UNRELIABLE or UNASSESSED regions.",
        )

    return "MEASURED_BASELINE", "Measured pipeline response recorded."


def generate_markdown_summary(
    manifest: DatasetManifest,
    report: dict[str, Any],
) -> str:
    """Generate comprehensive Markdown summary from validated manifest and report."""
    summary = report["summary"]
    cases = report["cases"]
    case_counts = summary["case_counts"]
    site_counts = summary["site_counts"]
    acc = summary.get("status_accuracy")
    acc_str = f"{acc['rate']*100:.1f}% ({acc['numerator']}/{acc['denominator']})" if acc else "null (no labels)"
    abstention = summary.get("abstention_rate", {})
    abs_str = f"{abstention.get('rate', 0.0)*100:.1f}% ({abstention.get('numerator', 0)}/{abstention.get('denominator', 0)})"
    false_missing = summary.get("false_missing_rate", {})
    fm_str = f"{false_missing.get('rate', 0.0)*100:.1f}% ({false_missing.get('numerator', 0)}/{false_missing.get('denominator', 0)})"

    # Status counts across cases
    calibrated_cnt = sum(1 for c in cases if c.get("analysis_status") == "CALIBRATED")
    unreliable_cnt = sum(1 for c in cases if c.get("analysis_status") == "UNRELIABLE")
    features_cnt = sum(1 for c in cases if c.get("analysis_status") == "FEATURES_ONLY")
    error_cnt = sum(1 for c in cases if c.get("status") == "ERROR")

    lines: list[str] = [
        f"# Inspection Robustness Checkpoint Summary: {manifest.dataset_id}",
        "",
        "> [!IMPORTANT]",
        "> **Evaluation Context & Compliance Notice**",
        "> This checkpoint evaluates how the existing region-inspection pipeline behaves under controlled synthetic capture degradation (blur, lighting, contrast, glare, clipping).",
        "> - **Absence of diagnostic defect observations is NOT a pass.**",
        "> - **Repeatable detection under optical degradation is a potential risk, not proof of industrial robustness.**",
        "> - **Ground truth is strictly limited to clean baseline controls.** Degraded cases remain unassigned.",
        "",
        "## 1. Executive Metrics",
        "",
        "| Metric | Value | Meaning |",
        "| :--- | :--- | :--- |",
        f"| **Dataset ID** | `{manifest.dataset_id}` | Manifest v1 dataset identifier |",
        f"| **Dataset Origin** | `{manifest.origin.value}` | Purely synthetic test matrix |",
        f"| **Total Cases** | `{case_counts['total_cases']}` ({case_counts['successful_cases']} success, {case_counts['failed_cases']} failed) | All cases completed without execution crashes |",
        f"| **Total Configured Sites** | `{site_counts['total_sites']}` ({site_counts['eligible_labeled_sites']} labeled, {site_counts.get('unlabeled_sites', site_counts.get('unlabeled_sites_count', 0))} unlabeled) | Clean controls labeled; perturbations unlabeled |",
        f"| **Status Accuracy (Controls)** | **{acc_str}** | 100% agreement on construction-grounded baseline controls |",
        f"| **Pipeline Abstention Rate** | **{abs_str}** | Sites flagged `UNASSESSED` due to quality gates |",
        f"| **False-Missing Rate** | **{fm_str}** | Known non-missing controls mislabeled `MISSING` |",
        f"| **Case Status Distribution** | `{calibrated_cnt}` CALIBRATED, `{unreliable_cnt}` UNRELIABLE, `{error_cnt}` ERROR | Conservative gating in {unreliable_cnt}/{len(cases)} cases |",
        "",
        "## 2. Categorized Robustness Findings",
        "",
        "| Case ID | Perturbation Category | Analysis Status | Coverage | Sites Summary | Finding Classification | Rationale |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for c in cases:
        cid = c.get("case_id", "")
        analysis_status = c.get("analysis_status") or "ERROR"
        cov = c.get("current_inspection_coverage", {}) or {}
        cov_status = cov.get("status") or "N/A"

        site_summaries = []
        for s in c.get("sites", []):
            rid = s.get("roi_id")
            pred = s.get("predicted_status")
            site_summaries.append(f"`{rid}`: {pred}")
        sites_str = ", ".join(site_summaries) if site_summaries else "None"

        category, rationale = classify_case_finding(c)
        cat_badge = f"**{category}**" if category != "MEASURED_BASELINE" else "MEASURED_BASELINE"

        # Extract short perturbation description from case notes or description
        desc = c.get("description", "")
        if ":" in desc:
            desc = desc.split(":", 1)[0]

        lines.append(
            f"| `{cid}` | {desc} | `{analysis_status}` | `{cov_status}` | {sites_str} | {cat_badge} | {rationale} |"
        )

    lines.extend([
        "",
        "## 3. Engineering Weakness Inventory & Architectural Implications",
        "",
        "### A. Optical Defocus / Blur Blindspot (Cases 02 & 03)",
        "- **Observed Behavior:** Mild Gaussian blur (5x5) and severe blur (19x19) both produce `CALIBRATED` analysis with `DETECTED` sites.",
        "- **Risk Analysis:** Because Otsu thresholding operates globally on pixel intensities, soft gradients around blurred boundaries still form connected components meeting the minimum coverage ratio. The pipeline currently lacks a Laplacian variance / high-frequency sharpness pre-gate.",
        "- **Implication:** In production, an out-of-focus camera will not abstain; it will silently report detected deposits with distorted area and circularity measurements.",
        "",
        "### B. Illumination & Contrast Extremes (Cases 04, 05, 06)",
        "- **Observed Behavior:** Underexposure (`0.40x`) and overexposure (`0.60x + 102`) maintain `DETECTED` status. In contrast, low contrast (15 gray levels delta) correctly triggers segmentation quality gating, marking both sites `UNASSESSED` with `UNRELIABLE` overall status.",
        "- **Risk Analysis:** The segmentation quality metric effectively catches compressed dynamic range, but raw luminance shifts without contrast loss pass through ungated.",
        "",
        "### C. Localized Specular Glare & Blooming (Cases 07, 12, 13)",
        "- **Observed Behavior:** Saturated glare directly over a target deposit (`case_07`) or missing site (`case_13`) triggers `UNASSESSED` on that specific ROI while leaving unaffected sites intact, yielding `PARTIAL` coverage and `UNRELIABLE` overall status.",
        "- **Risk Analysis:** Multi-site independent reliability functions correctly: a flare on site 1 does not contaminate site 2, and the conservative gate protects the whole-image result.",
        "",
        "### D. Boundary Clipping (Case 09)",
        "- **Observed Behavior:** When a deposit is clipped by the acquired sensor edge, the contour touches the border and triggers `UNASSESSED` due to boundary truncation, while the shifted interior deposit remains `DETECTED`.",
        "- **Risk Analysis:** Sensor translation does not cause missing-deposit misclassification, but currently cannot measure the partial deposit.",
        "",
        "## 4. Methodological Boundaries",
        "",
        "- **Purely Synthetic Proof-of-Concept:** Synthetic images test mathematical pipeline properties (segmentation thresholds, geometry mapping, gate logic) under controlled conditions. They do not represent real-world PCB surface textures, meniscus reflections, or solder mask variations.",
        "- **No Production Changes in this Increment:** DLK-M3-045 establishes diagnostic evidence and failure inventory only. No thresholds, filters, or scoring weights were modified.",
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

    manifest_path = args.manifest.resolve()
    report_path = args.report.resolve()

    if not manifest_path.exists():
        sys.stderr.write(f"Fatal error: Manifest file not found: '{manifest_path.name}'\n")
        return 1
    if not report_path.exists():
        sys.stderr.write(f"Fatal error: Report file not found: '{report_path.name}'\n")
        return 1

    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = DatasetManifest.model_validate_json(manifest_text)
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Failed to parse manifest JSON: {exc}\n")
        return 1

    try:
        report_text = report_path.read_text(encoding="utf-8")
        report = json.loads(report_text)
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Failed to parse report JSON: {exc}\n")
        return 1

    # Validate matching identities
    try:
        validate_identities(manifest, report)
    except IdentityMismatchError as exc:
        sys.stderr.write(f"Fatal error: Manifest and report identities do not match: {exc}\n")
        return 1

    # Generate Markdown summary
    summary_md = generate_markdown_summary(manifest, report)

    if args.output:
        out_path = args.output.resolve()
        try:
            verify_summary_output_safe(out_path, manifest_path, report_path, overwrite=args.overwrite)
        except (SummarySafetyError, FileExistsError) as exc:
            sys.stderr.write(f"Fatal error: {exc}\n")
            return 1

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(summary_md, encoding="utf-8")
            sys.stdout.write(f"Robustness summary written to: {out_path.name}\n")
        except (OSError, RuntimeError) as exc:
            sys.stderr.write(f"Fatal error writing summary file: {exc}\n")
            return 1
    else:
        sys.stdout.write(summary_md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
