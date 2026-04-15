"""Convert shellcheck JSON output to SARIF v2.1.0.

``shellcheck --format json`` emits a JSON array of objects, each with
``file``, ``line``, ``column``, ``endLine``, ``endColumn``, ``level``,
``code``, and ``message``.
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


class ShellcheckConverter(BaseConverter):
    """Convert shellcheck JSON output to SARIF v2.1.0."""

    tool_name: str = "shellcheck"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        try:
            findings: list[dict[str, Any]] = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"shellcheck output is not valid JSON: {exc}") from exc

        if not isinstance(findings, list):
            raise ValueError("shellcheck JSON output must be an array")

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for finding in findings:
            result, rule = self._convert_finding(finding)
            if result is not None:
                results.append(result)
            if rule is not None and rule["id"] not in seen_rules:
                seen_rules[rule["id"]] = rule

        run = make_run(
            tool_name="shellcheck",
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
    def _convert_finding(
        finding: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        file_path: str = finding.get("file", "")
        line: int = finding.get("line", 1)
        column: int = finding.get("column", 1)
        end_line: int = finding.get("endLine", line)
        end_column: int = finding.get("endColumn", column)
        level_raw: str = finding.get("level", "warning")
        code: int = finding.get("code", 0)
        message: str = finding.get("message", "")

        if not file_path:
            return None, None

        level = _SEVERITY.map_severity("shellcheck", level_raw)
        rule_id = f"SC{code}"

        locations = [
            make_location(
                file_path=file_path,
                start_line=max(line, 1),
                start_column=max(column, 1),
                end_line=max(end_line, 1),
                end_column=max(end_column, 1),
            ),
        ]

        result = make_result(
            rule_id=rule_id,
            message=message,
            level=level,
            locations=locations,
        )

        rule = make_rule(
            rule_id=rule_id,
            name=f"ShellCheck SC{code}",
            description=f"shellcheck rule SC{code}",
            level=level,
        )

        return result, rule
