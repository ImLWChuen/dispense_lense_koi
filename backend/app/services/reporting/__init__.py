"""Reporting package for DispenseIQ case report and export services."""

from __future__ import annotations

from app.services.reporting.report_generator import build_case_report

__all__ = ["build_case_report"]
