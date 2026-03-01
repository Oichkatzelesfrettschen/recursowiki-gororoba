"""Combine multiple SARIF documents into a single unified log.

The merger collects runs from every input document into one SARIF log.
When multiple runs originate from the same tool (identified by
``tool.driver.name``), their results and rules are consolidated into a
single run.  A shared artifacts array is built from all referenced file
paths.
"""

from __future__ import annotations

import logging
from typing import Any

from sarif_normalizer.schema import SARIF_SCHEMA_URI, SARIF_VERSION

logger = logging.getLogger(__name__)


class SarifMerger:
    """Merge several SARIF v2.1.0 documents into one."""

    def merge(self, sarif_docs: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine all SARIF logs into a single document.

        Each input document may contain one or more runs.  Runs that
        share the same ``tool.driver.name`` are merged into a single run
        with combined results, rules, and artifacts.

        Parameters
        ----------
        sarif_docs:
            List of SARIF v2.1.0 log dicts.

        Returns
        -------
        dict
            A single SARIF v2.1.0 log with one run per distinct tool.
        """
        if not sarif_docs:
            return self._empty_log()

        # Collect runs grouped by tool name.
        tool_runs: dict[str, _ToolAccumulator] = {}

        for doc_idx, doc in enumerate(sarif_docs):
            if not isinstance(doc, dict):
                logger.warning("Skipping non-dict document at index %d", doc_idx)
                continue
            for run in doc.get("runs", []):
                tool_name = self._tool_name(run)
                if tool_name not in tool_runs:
                    tool_runs[tool_name] = _ToolAccumulator(run)
                else:
                    tool_runs[tool_name].absorb(run)

        # Build the merged log.
        merged_runs: list[dict[str, Any]] = []
        for tool_name in sorted(tool_runs):
            merged_runs.append(tool_runs[tool_name].to_run())

        # Build a shared artifacts array from all file URIs referenced
        # across every merged run.
        artifact_uris = self._collect_artifact_uris(merged_runs)
        artifacts: list[dict[str, Any]] = [
            {"location": {"uri": uri}} for uri in sorted(artifact_uris)
        ]

        merged_log: dict[str, Any] = {
            "$schema": SARIF_SCHEMA_URI,
            "version": SARIF_VERSION,
            "runs": merged_runs,
        }

        if artifacts:
            # Attach the shared artifact list to each run as well so
            # viewers that only inspect a single run still see it.
            for run in merged_runs:
                run["artifacts"] = list(artifacts)

        return merged_log

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_name(run: dict[str, Any]) -> str:
        """Extract a canonical tool name from a SARIF run."""
        try:
            return run["tool"]["driver"]["name"]
        except (KeyError, TypeError):
            return "unknown"

    @staticmethod
    def _collect_artifact_uris(runs: list[dict[str, Any]]) -> set[str]:
        """Gather every unique artifact URI mentioned in results."""
        uris: set[str] = set()
        for run in runs:
            for result in run.get("results", []):
                for loc in result.get("locations", []):
                    phys = loc.get("physicalLocation", {})
                    uri = phys.get("artifactLocation", {}).get("uri")
                    if uri:
                        uris.add(uri)
            for artifact in run.get("artifacts", []):
                uri = artifact.get("location", {}).get("uri")
                if uri:
                    uris.add(uri)
        return uris

    @staticmethod
    def _empty_log() -> dict[str, Any]:
        return {
            "$schema": SARIF_SCHEMA_URI,
            "version": SARIF_VERSION,
            "runs": [],
        }


# ======================================================================
# Internal accumulator for merging runs of the same tool
# ======================================================================


class _ToolAccumulator:
    """Accumulates results, rules, and properties from multiple runs of
    the same tool into one consolidated run."""

    def __init__(self, initial_run: dict[str, Any]) -> None:
        driver = initial_run.get("tool", {}).get("driver", {})
        self.tool_name: str = driver.get("name", "unknown")
        self.tool_version: str = driver.get("version", "unknown")
        self.tool_extensions: list[dict[str, Any]] = (
            initial_run.get("tool", {}).get("extensions", [])
        )

        self.results: list[dict[str, Any]] = list(initial_run.get("results", []))
        self._rule_index: dict[str, dict[str, Any]] = {}
        for rule in driver.get("rules", []):
            rid = rule.get("id", "")
            if rid:
                self._rule_index[rid] = rule

        self.artifacts: list[dict[str, Any]] = list(initial_run.get("artifacts", []))
        self.properties: dict[str, Any] = dict(initial_run.get("properties", {}))

    def absorb(self, run: dict[str, Any]) -> None:
        """Merge another run into this accumulator."""
        self.results.extend(run.get("results", []))

        driver = run.get("tool", {}).get("driver", {})
        for rule in driver.get("rules", []):
            rid = rule.get("id", "")
            if rid and rid not in self._rule_index:
                self._rule_index[rid] = rule

        self.artifacts.extend(run.get("artifacts", []))

        # Merge properties (shallow).
        for key, val in run.get("properties", {}).items():
            self.properties.setdefault(key, val)

        # Keep the newest version string.
        incoming_ver = driver.get("version", "")
        if incoming_ver and incoming_ver != "unknown":
            self.tool_version = incoming_ver

    def to_run(self) -> dict[str, Any]:
        """Produce the merged SARIF run dict."""
        run: dict[str, Any] = {
            "tool": {
                "driver": {
                    "name": self.tool_name,
                    "version": self.tool_version,
                    "rules": list(self._rule_index.values()),
                },
            },
            "results": self.results,
        }
        if self.tool_extensions:
            run["tool"]["extensions"] = self.tool_extensions
        if self.properties:
            run["properties"] = self.properties
        return run
