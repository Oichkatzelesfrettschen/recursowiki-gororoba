"""Convert PHP_CodeSniffer XML (checkstyle format) to SARIF v2.1.0.

PHP_CodeSniffer can produce output in checkstyle XML format::

    <checkstyle version="...">
      <file name="path/to/file.php">
        <error line="10" column="5" severity="error"
               message="..." source="PEAR.Functions.ValidDefaultValue" />
        ...
      </file>
    </checkstyle>

This converter parses the XML and maps each ``<error>`` element to a
SARIF result.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
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


class PhpcsConverter(BaseConverter):
    """Convert PHP_CodeSniffer checkstyle XML to SARIF v2.1.0."""

    tool_name: str = "phpcs"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse PHPCS XML and return a SARIF log.

        Parameters
        ----------
        raw_output:
            Complete XML string in checkstyle format from phpcs.
        target_path:
            Root of the analysed project.
        """
        try:
            root = ET.fromstring(raw_output)
        except ET.ParseError as exc:
            raise ValueError(f"PHPCS output is not valid XML: {exc}") from exc

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for file_el in root.iter("file"):
            file_path = file_el.get("name", "")
            for violation_el in file_el:
                # Both <error> and <warning> tags appear inside <file>.
                result, rule = self._convert_violation(file_path, violation_el)
                if result is not None:
                    results.append(result)
                if rule is not None and rule["id"] not in seen_rules:
                    seen_rules[rule["id"]] = rule

        phpcs_version = root.get("version", "unknown")

        run = make_run(
            tool_name="PHP_CodeSniffer",
            tool_version=phpcs_version,
            results=results,
            rules=list(seen_rules.values()),
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_violation(
        file_path: str,
        el: ET.Element,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Convert a single ``<error>`` or ``<warning>`` element."""
        line_str = el.get("line", "1")
        col_str = el.get("column", "")
        severity_str = el.get("severity", el.tag)  # tag itself is "error" or "warning"
        message = el.get("message", "")
        source = el.get("source", "phpcs/unknown-rule")

        try:
            line = int(line_str)
        except (ValueError, TypeError):
            line = 1

        column: int | None = None
        if col_str:
            try:
                column = int(col_str)
            except (ValueError, TypeError):
                pass

        level = _SEVERITY.map_severity("phpcs", severity_str)

        # Use the PHPCS source as the rule ID (e.g. "PEAR.Functions.ValidDefaultValue").
        rule_id = source if source else "phpcs/unknown-rule"

        location = make_location(
            file_path=file_path,
            start_line=line,
            start_column=column,
        )

        result = make_result(
            rule_id=rule_id,
            message=message,
            level=level,
            locations=[location],
        )

        rule = make_rule(
            rule_id=rule_id,
            name=source,
            description=f"PHP_CodeSniffer rule: {source}",
            level=level,
        )

        return result, rule
