"""Convert Pyright JSON diagnostic output to SARIF v2.1.0.

Pyright (when invoked with ``--outputjson``) emits a JSON object whose
``generalDiagnostics`` array contains typed diagnostics with file, range,
message, and severity.  This converter maps each diagnostic to a SARIF
result.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sarif_normalizer.converters.base import BaseConverter
from sarif_normalizer.schema import (
    make_location,
    make_result,
    make_rule,
    make_run,
    make_sarif_log,
)
from sarif_normalizer.severity_mapper import SeverityMapper

logger = logging.getLogger(__name__)

_SEVERITY = SeverityMapper()


class PyrightConverter(BaseConverter):
    """Convert Pyright JSON output to a SARIF v2.1.0 document."""

    tool_name: str = "pyright"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse Pyright JSON and return a SARIF log.

        Parameters
        ----------
        raw_output:
            The complete JSON string produced by ``pyright --outputjson``.
        target_path:
            Root of the analysed project (used to relativise paths).

        Returns
        -------
        dict
            A SARIF v2.1.0 log object.
        """
        try:
            data: dict[str, Any] = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Pyright output is not valid JSON: {exc}") from exc

        diagnostics: list[dict[str, Any]] = data.get("generalDiagnostics", [])
        version: str = data.get("version", "unknown")

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for diag in diagnostics:
            result, rule = self._convert_diagnostic(diag)
            if result is not None:
                results.append(result)
            if rule is not None and rule["id"] not in seen_rules:
                seen_rules[rule["id"]] = rule

        run = make_run(
            tool_name="pyright",
            tool_version=version,
            results=results,
            rules=list(seen_rules.values()),
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_diagnostic(
        diag: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Convert a single Pyright diagnostic to a SARIF result + rule.

        Returns ``(None, None)`` if the diagnostic cannot be converted
        (e.g. missing required fields).
        """
        message: str = diag.get("message", "")
        severity: str = diag.get("severity", "warning")
        file_path: str = diag.get("file", "")
        rule_name: str = diag.get("rule", "pyright-diagnostic")

        if not file_path:
            logger.debug("Skipping diagnostic without file path: %s", message[:80])
            return None, None

        # Pyright range is 0-based; SARIF expects 1-based.
        rng: dict[str, Any] = diag.get("range", {})
        start = rng.get("start", {})
        end = rng.get("end", {})
        start_line: int = start.get("line", 0) + 1
        start_col: int = start.get("character", 0) + 1
        end_line: int = end.get("line", 0) + 1
        end_col: int = end.get("character", 0) + 1

        level = _SEVERITY.map_severity("pyright", severity)

        location = make_location(
            file_path=file_path,
            start_line=start_line,
            start_column=start_col,
            end_line=end_line,
            end_column=end_col,
        )

        result = make_result(
            rule_id=rule_name,
            message=message,
            level=level,
            locations=[location],
        )

        rule = make_rule(
            rule_id=rule_name,
            name=rule_name,
            description=f"Pyright diagnostic: {rule_name}",
            level=level,
        )

        return result, rule
