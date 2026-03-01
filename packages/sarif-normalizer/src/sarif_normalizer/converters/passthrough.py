"""Passthrough converter for tools that already emit SARIF v2.1.0.

Validates the incoming SARIF, enriches every run with a ``properties``
bag containing converter metadata (category, processing timestamp), and
returns the document unchanged otherwise.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sarif_normalizer.converters.base import BaseConverter
from sarif_normalizer.schema import SARIF_SCHEMA_URI, SARIF_VERSION, make_sarif_log

logger = logging.getLogger(__name__)

# Tools whose native output is already valid SARIF v2.1.0.
NATIVE_SARIF_TOOLS: frozenset[str] = frozenset(
    {
        "semgrep",
        "bandit",
        "ruff",
        "gosec",
        "trivy",
        "owasp-dependency-check",
        "brakeman",
        "cppcheck",
        "clang-sa",
        "pmd",
        "pmd-cpd",
        "checkov",
        "kics",
        "slither",
        "ggshield",
        "eslint",
    }
)

# Human-readable category labels for enrichment.
_TOOL_CATEGORIES: dict[str, str] = {
    "semgrep": "sast",
    "bandit": "sast",
    "ruff": "linter",
    "gosec": "sast",
    "trivy": "sca",
    "owasp-dependency-check": "sca",
    "brakeman": "sast",
    "cppcheck": "sast",
    "clang-sa": "sast",
    "pmd": "linter",
    "pmd-cpd": "duplication",
    "checkov": "iac",
    "kics": "iac",
    "slither": "sast",
    "ggshield": "secret-detection",
    "eslint": "linter",
}


class PassthroughConverter(BaseConverter):
    """Pass through and enrich SARIF produced by native-SARIF tools."""

    tool_name: str = "passthrough"

    def __init__(self, tool_name: str = "passthrough") -> None:
        if tool_name != "passthrough" and tool_name not in NATIVE_SARIF_TOOLS:
            logger.warning(
                "Tool %r is not in the known native-SARIF list; "
                "proceeding anyway",
                tool_name,
            )
        self.tool_name = tool_name

    # ------------------------------------------------------------------
    # BaseConverter interface
    # ------------------------------------------------------------------

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse, validate, and enrich an existing SARIF document.

        Parameters
        ----------
        raw_output:
            Raw JSON string of the SARIF document produced by the tool.
        target_path:
            Root path of the analysed project (unused for passthrough,
            kept for interface compatibility).

        Returns
        -------
        dict
            The enriched SARIF document.

        Raises
        ------
        ValueError
            If *raw_output* is not valid JSON or fails structural
            validation.
        """
        try:
            sarif_doc: dict[str, Any] = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Passthrough input is not valid JSON: {exc}") from exc

        # Normalise missing top-level fields so downstream code can rely
        # on their presence.
        sarif_doc.setdefault("$schema", SARIF_SCHEMA_URI)
        sarif_doc.setdefault("version", SARIF_VERSION)
        sarif_doc.setdefault("runs", [])

        if not self.validate_sarif(sarif_doc):
            raise ValueError(
                f"SARIF document from {self.tool_name!r} failed structural validation"
            )

        self._enrich_runs(sarif_doc)
        return sarif_doc

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    def _enrich_runs(self, sarif_doc: dict[str, Any]) -> None:
        """Add converter metadata to the ``properties`` bag of each run."""
        processing_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        category = _TOOL_CATEGORIES.get(self.tool_name, "unknown")

        for run in sarif_doc.get("runs", []):
            props: dict[str, Any] = run.setdefault("properties", {})
            props["sarif-normalizer"] = {
                "converter": "passthrough",
                "originalTool": self.tool_name,
                "category": category,
                "processedAt": processing_ts,
            }
