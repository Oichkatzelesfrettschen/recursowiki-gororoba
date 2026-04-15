"""Convert cargo-deny JSON diagnostics to SARIF v2.1.0.

``cargo deny check --format json`` writes one JSON object per line to stderr.
Each diagnostic has ``fields.severity``, ``fields.message``, and optionally
``fields.labels[].span`` with file/line information.
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


class CargoDenyConverter(BaseConverter):
    """Convert cargo-deny JSON diagnostics to SARIF v2.1.0."""

    tool_name: str = "cargo-deny"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        diagnostics = self._parse_jsonl(raw_output)

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for diag in diagnostics:
            result, rule = self._convert_diagnostic(diag)
            if result is not None:
                results.append(result)
            if rule is not None and rule["id"] not in seen_rules:
                seen_rules[rule["id"]] = rule

        run = make_run(
            tool_name="cargo-deny",
            tool_version="unknown",
            results=results,
            rules=list(seen_rules.values()),
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc

    # ------------------------------------------------------------------

    @staticmethod
    def _parse_jsonl(raw: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict):
                    diagnostics.append(obj)
            except json.JSONDecodeError:
                continue
        return diagnostics

    @staticmethod
    def _convert_diagnostic(
        diag: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        fields: dict[str, Any] = diag.get("fields", diag)
        severity: str = fields.get("severity", fields.get("level", "warning"))
        message: str = fields.get("message", "")

        if not message:
            return None, None

        level = _SEVERITY.map_severity("cargo-deny", severity)

        # Extract code/category for rule grouping.
        code = fields.get("code", "")
        if isinstance(code, dict):
            code = code.get("code", "")
        rule_id = f"cargo-deny/{code}" if code else "cargo-deny/diagnostic"

        # Try to extract location from labels.
        labels: list[dict[str, Any]] = fields.get("labels", [])
        locations: list[dict[str, Any]] = []
        for label in labels:
            span = label.get("span", {})
            file_path = span.get("file_name", "") or span.get("file", "")
            if file_path:
                locations.append(
                    make_location(
                        file_path=file_path,
                        start_line=span.get("line_start", 1),
                        start_column=span.get("column_start"),
                    )
                )
                break

        result = make_result(
            rule_id=rule_id,
            message=message,
            level=level,
            locations=locations if locations else None,
        )

        rule = make_rule(
            rule_id=rule_id,
            name=code or "cargo-deny diagnostic",
            description=f"cargo-deny: {code}" if code else "cargo-deny diagnostic",
            level=level,
        )

        return result, rule
