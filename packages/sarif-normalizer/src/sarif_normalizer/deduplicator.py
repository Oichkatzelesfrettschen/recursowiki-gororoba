"""Cross-tool fingerprint-based deduplication for SARIF documents.

When multiple tools report the same issue (same file, same line, similar
rule and message), only one representative result should survive.  This
module builds a composite fingerprint from location, rule-ID pattern,
and message similarity, then drops duplicates while preserving the
highest-severity instance.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from sarif_normalizer.schema import SARIF_LEVELS

logger = logging.getLogger(__name__)

# Severity ordering -- higher index means more severe.
_SEVERITY_RANK: dict[str, int] = {
    level: idx for idx, level in enumerate(SARIF_LEVELS)
}
# SARIF_LEVELS is ("error", "warning", "note", "none") -- reverse so
# "error" has the highest rank.
_SEVERITY_RANK = {
    "none": 0,
    "note": 1,
    "warning": 2,
    "error": 3,
}


class SarifDeduplicator:
    """Remove duplicate findings across runs in a SARIF document.

    Two results are considered duplicates when they share the same
    *canonical fingerprint*, computed from:

    1. The file path of the primary location.
    2. The start line of the primary location.
    3. A normalised form of the rule ID (tool prefix stripped).
    4. A normalised form of the message text.

    When duplicates exist across different runs (tools), the instance
    with the highest severity is kept.  If severities are equal, the
    first encountered instance wins.
    """

    def deduplicate(self, sarif_doc: dict[str, Any]) -> dict[str, Any]:
        """Return a new SARIF document with duplicates removed.

        The input document is not mutated.

        Parameters
        ----------
        sarif_doc:
            A valid SARIF v2.1.0 log dict (may contain multiple runs).

        Returns
        -------
        dict
            A copy of the input with duplicate results removed.
        """
        if not isinstance(sarif_doc, dict):
            logger.error("Expected dict, got %s", type(sarif_doc).__name__)
            return sarif_doc

        runs = sarif_doc.get("runs", [])
        if not runs:
            return dict(sarif_doc)

        # First pass: collect all results with their fingerprints and
        # record which (run_index, result_index) to keep.
        #
        # fingerprint -> (severity_rank, run_idx, result_idx)
        best: dict[str, tuple[int, int, int]] = {}

        for run_idx, run in enumerate(runs):
            for res_idx, result in enumerate(run.get("results", [])):
                fp = self._fingerprint(result)
                rank = _SEVERITY_RANK.get(result.get("level", "warning"), 2)
                existing = best.get(fp)
                if existing is None or rank > existing[0]:
                    best[fp] = (rank, run_idx, res_idx)

        # Build the set of (run_idx, result_idx) pairs to keep.
        keep: set[tuple[int, int]] = {(ri, resi) for _, ri, resi in best.values()}

        total_before = sum(len(r.get("results", [])) for r in runs)

        # Second pass: rebuild runs with only the kept results.
        new_runs: list[dict[str, Any]] = []
        for run_idx, run in enumerate(runs):
            old_results = run.get("results", [])
            new_results = [
                res for res_idx, res in enumerate(old_results)
                if (run_idx, res_idx) in keep
            ]
            new_run = dict(run)
            new_run["results"] = new_results
            new_runs.append(new_run)

        total_after = sum(len(r["results"]) for r in new_runs)
        removed = total_before - total_after
        if removed > 0:
            logger.info(
                "Deduplication removed %d of %d results (%d remaining)",
                removed,
                total_before,
                total_after,
            )

        new_doc = dict(sarif_doc)
        new_doc["runs"] = new_runs
        return new_doc

    # ------------------------------------------------------------------
    # Fingerprinting
    # ------------------------------------------------------------------

    def _fingerprint(self, result: dict[str, Any]) -> str:
        """Compute a canonical fingerprint for a SARIF result.

        If the result already carries explicit fingerprints (produced by
        a converter), we incorporate them.  Otherwise we synthesise one
        from location + rule + message.
        """
        # Check for pre-computed fingerprints.
        existing_fps = result.get("fingerprints", {})
        if existing_fps:
            # Use the first available fingerprint value.
            return next(iter(existing_fps.values()))

        file_path, start_line = self._primary_location(result)
        rule_id = self._normalise_rule(result.get("ruleId", ""))
        message = self._normalise_message(
            result.get("message", {}).get("text", "")
        )

        composite = f"{file_path}:{start_line}:{rule_id}:{message}"
        return hashlib.sha256(composite.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _primary_location(result: dict[str, Any]) -> tuple[str, int]:
        """Extract file path and start line from the first location."""
        locations = result.get("locations", [])
        if not locations:
            return ("", 0)
        phys = locations[0].get("physicalLocation", {})
        uri = phys.get("artifactLocation", {}).get("uri", "")
        line = phys.get("region", {}).get("startLine", 0)
        return (uri, line)

    @staticmethod
    def _normalise_rule(rule_id: str) -> str:
        """Strip tool-specific prefixes to compare rules across tools.

        For example ``"semgrep/python.security.sql-injection"`` and
        ``"bandit/B608"`` are left as-is (they are genuinely different),
        but ``"trufflehog/aws-key"`` and ``"detect-secrets/aws-key"``
        would both normalise to ``"aws-key"`` via prefix stripping.
        """
        # Remove common tool prefixes separated by "/".
        parts = rule_id.split("/", 1)
        if len(parts) == 2:
            return parts[1].lower()
        return rule_id.lower()

    @staticmethod
    def _normalise_message(message: str) -> str:
        """Reduce a message to a canonical comparison form.

        Strips whitespace, lowercases, and removes variable content like
        hashes, UUIDs, and hex addresses so that semantically identical
        messages from different tools can match.
        """
        text = message.lower().strip()
        # Remove hex hashes (8+ hex chars).
        text = re.sub(r"\b[0-9a-f]{8,}\b", "<hash>", text)
        # Remove quoted strings.
        text = re.sub(r"['\"][^'\"]*['\"]", "<str>", text)
        # Collapse whitespace.
        text = re.sub(r"\s+", " ", text)
        return text
