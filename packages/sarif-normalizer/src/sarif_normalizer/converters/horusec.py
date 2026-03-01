"""Convert Horusec JSON output to SARIF v2.1.0.

Horusec has partial SARIF awareness but its native JSON export uses a
proprietary schema::

    {
      "id": "...",
      "analysisVulnerabilities": [
        {
          "vulnerabilities": {
            "vulnHash": "...",
            "severity": "HIGH",
            "line": "42",
            "column": "10",
            "file": "path/to/file.go",
            "code": "...",
            "details": "...",
            "securityTool": "GoSec",
            "language": "Go",
            ...
          }
        },
        ...
      ]
    }

This converter normalises the Horusec structure into proper SARIF.
"""

from __future__ import annotations

import hashlib
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


class HorusecConverter(BaseConverter):
    """Convert Horusec JSON to standard SARIF v2.1.0."""

    tool_name: str = "horusec"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse Horusec JSON and return a SARIF log.

        Parameters
        ----------
        raw_output:
            Complete JSON string from Horusec analysis.
        target_path:
            Root of the analysed project.
        """
        try:
            data: dict[str, Any] = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Horusec output is not valid JSON: {exc}") from exc

        analysis_vulns: list[dict[str, Any]] = data.get("analysisVulnerabilities", [])
        horusec_version: str = data.get("version", "unknown")

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for entry in analysis_vulns:
            vuln = entry.get("vulnerabilities")
            if not isinstance(vuln, dict):
                # Some Horusec versions nest the vuln one level deeper.
                vuln = entry.get("vulnerability")
            if not isinstance(vuln, dict):
                logger.debug("Skipping entry without vulnerability data")
                continue

            result, rule = self._convert_vulnerability(vuln)
            if result is not None:
                results.append(result)
            if rule is not None and rule["id"] not in seen_rules:
                seen_rules[rule["id"]] = rule

        run = make_run(
            tool_name="horusec",
            tool_version=horusec_version,
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
    def _convert_vulnerability(
        vuln: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Map a single Horusec vulnerability to SARIF result + rule."""
        severity: str = vuln.get("severity", "MEDIUM")
        details: str = vuln.get("details", "")
        file_path: str = vuln.get("file", "")
        line_str: str = str(vuln.get("line", "1"))
        column_str: str = str(vuln.get("column", ""))
        vuln_hash: str = vuln.get("vulnHash", "")
        security_tool: str = vuln.get("securityTool", "horusec")
        language: str = vuln.get("language", "")
        code_snippet: str = vuln.get("code", "")
        confidence: str = vuln.get("confidence", "")

        # Parse line / column.
        try:
            line = max(int(line_str), 1)
        except (ValueError, TypeError):
            line = 1

        column: int | None = None
        if column_str:
            try:
                column = int(column_str)
                if column < 1:
                    column = None
            except (ValueError, TypeError):
                column = None

        level = _SEVERITY.map_severity("horusec", severity)

        # Derive rule ID from the security tool and a shortened hash.
        rule_id = f"horusec/{security_tool.lower()}"
        if vuln_hash:
            rule_id = f"horusec/{security_tool.lower()}/{vuln_hash[:12]}"

        message = details if details else f"Vulnerability detected by {security_tool}"

        # Fingerprint.
        fp_source = vuln_hash if vuln_hash else f"{file_path}:{line}:{details}"
        fingerprint = hashlib.sha256(fp_source.encode()).hexdigest()

        locations: list[dict[str, Any]] = []
        if file_path:
            locations.append(
                make_location(
                    file_path=file_path,
                    start_line=line,
                    start_column=column,
                )
            )

        properties: dict[str, Any] = {
            "securityTool": security_tool,
        }
        if language:
            properties["language"] = language
        if code_snippet:
            properties["codeSnippet"] = code_snippet
        if confidence:
            properties["confidence"] = confidence

        result = make_result(
            rule_id=rule_id,
            message=message,
            level=level,
            locations=locations,
            fingerprints={"horusec/v1": fingerprint},
            properties=properties,
        )

        rule = make_rule(
            rule_id=rule_id,
            name=f"horusec: {security_tool}",
            description=f"Vulnerability detected by {security_tool} via Horusec.",
            level=level,
        )

        return result, rule
