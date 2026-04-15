"""Convert taplo lint text output to SARIF v2.1.0.

taplo lint writes diagnostics to stderr in forms like:
    error[rule_name]: message
      --> filename:line:col
or simpler multi-line patterns.  This converter handles the common output
format and produces one SARIF result per diagnostic.
"""

from __future__ import annotations

import logging
import re
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

# Primary diagnostic line: "error[rule]: message"
_DIAG_RE = re.compile(
    r"^(?P<severity>error|warning|info)\[(?P<rule>[^\]]+)\]:\s*(?P<message>.+)$"
)

# Location line: "  --> filename:line:col"
_LOC_RE = re.compile(
    r"^\s*-->\s*(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+)"
)


class TaploConverter(BaseConverter):
    """Convert taplo lint stderr output to SARIF v2.1.0."""

    tool_name: str = "taplo"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        lines = raw_output.splitlines()
        i = 0
        while i < len(lines):
            diag_match = _DIAG_RE.match(lines[i].strip())
            if not diag_match:
                i += 1
                continue

            severity = diag_match.group("severity")
            rule_name = diag_match.group("rule")
            message = diag_match.group("message")
            level = _SEVERITY.map_severity("taplo", severity)
            rule_id = f"taplo/{rule_name}"

            # Look ahead for location.
            locations: list[dict[str, Any]] = []
            if i + 1 < len(lines):
                loc_match = _LOC_RE.match(lines[i + 1])
                if loc_match:
                    locations.append(
                        make_location(
                            file_path=loc_match.group("file"),
                            start_line=int(loc_match.group("line")),
                            start_column=int(loc_match.group("col")),
                        )
                    )
                    i += 1  # consume location line

            results.append(
                make_result(
                    rule_id=rule_id,
                    message=message,
                    level=level,
                    locations=locations if locations else None,
                )
            )

            if rule_id not in seen_rules:
                seen_rules[rule_id] = make_rule(
                    rule_id=rule_id,
                    name=rule_name,
                    description=f"taplo lint: {rule_name}",
                    level=level,
                )

            i += 1

        if not seen_rules:
            seen_rules["taplo/unknown"] = make_rule(
                rule_id="taplo/unknown",
                name="taplo lint",
                description="Generic taplo lint diagnostic",
                level="warning",
            )

        run = make_run(
            tool_name="taplo",
            tool_version="unknown",
            results=results,
            rules=list(seen_rules.values()),
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc
