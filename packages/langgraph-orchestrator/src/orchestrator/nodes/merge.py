"""SARIF merge and deduplication node."""

from __future__ import annotations

import logging

from sarif_normalizer.merger import SarifMerger
from sarif_normalizer.deduplicator import SarifDeduplicator

logger = logging.getLogger(__name__)


def merge_node(state: dict) -> dict:
    """Merge individual SARIF runs into a single document and deduplicate.

    Reads: sarif_runs
    Writes: unified_sarif, metrics, progress
    """
    sarif_runs = state.get("sarif_runs", [])
    if not sarif_runs:
        logger.info("No SARIF runs to merge")
        return {
            "unified_sarif": {"$schema": "", "version": "2.1.0", "runs": []},
            "metrics": _empty_metrics(),
            "progress": 0.7,
        }

    # Wrap each run in a minimal SARIF log for the merger
    sarif_docs = []
    for run in sarif_runs:
        sarif_docs.append({
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [run],
        })

    merger = SarifMerger()
    merged = merger.merge(sarif_docs)

    deduplicator = SarifDeduplicator()
    unified = deduplicator.deduplicate(merged)

    metrics = _compute_metrics(unified)
    logger.info(
        f"Merged SARIF: {metrics['total_findings']} findings "
        f"({metrics['error_count']} errors, {metrics['warning_count']} warnings, "
        f"{metrics['note_count']} notes)"
    )

    return {
        "unified_sarif": unified,
        "metrics": metrics,
        "progress": 0.7,
    }


def _compute_metrics(sarif: dict) -> dict:
    """Extract aggregate metrics from a unified SARIF document."""
    total = 0
    errors = 0
    warnings = 0
    notes = 0
    tools_run: list[str] = []

    for run in sarif.get("runs", []):
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "unknown")
        tools_run.append(tool_name)
        for result in run.get("results", []):
            total += 1
            level = result.get("level", "warning")
            if level == "error":
                errors += 1
            elif level == "warning":
                warnings += 1
            elif level == "note":
                notes += 1

    return {
        "total_findings": total,
        "error_count": errors,
        "warning_count": warnings,
        "note_count": notes,
        "tools_run": tools_run,
        "tool_count": len(tools_run),
    }


def _empty_metrics() -> dict:
    return {
        "total_findings": 0,
        "error_count": 0,
        "warning_count": 0,
        "note_count": 0,
        "tools_run": [],
        "tool_count": 0,
    }
