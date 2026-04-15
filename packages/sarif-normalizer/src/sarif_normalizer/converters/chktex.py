"""Convert chktex plain-text output to SARIF v2.1.0.

chktex with ``-v3`` emits lines in the format:
    filename:line:col:severity:message (Warning NN).
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

# Pattern: file:line:col: severity: message
# Example: main.tex:12:5: Warning: Command terminated with space. (Warning 1).
_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*"
    r"(?P<severity>\w+):\s*"
    r"(?P<message>.+?)(?:\s*\(Warning\s+(?P<code>\d+)\))?\.?\s*$"
)


class ChktexConverter(BaseConverter):
    """Convert chktex plain-text output to SARIF v2.1.0."""

    tool_name: str = "chktex"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = _LINE_RE.match(stripped)
            if not match:
                continue

            file_path = match.group("file")
            line_num = int(match.group("line"))
            col = int(match.group("col"))
            severity = match.group("severity")
            message = match.group("message")
            code = match.group("code") or "0"

            level = _SEVERITY.map_severity("chktex", severity)
            rule_id = f"chktex/W{code}"

            results.append(
                make_result(
                    rule_id=rule_id,
                    message=message,
                    level=level,
                    locations=[
                        make_location(
                            file_path=file_path,
                            start_line=line_num,
                            start_column=col,
                        ),
                    ],
                )
            )

            if rule_id not in seen_rules:
                seen_rules[rule_id] = make_rule(
                    rule_id=rule_id,
                    name=f"chktex warning {code}",
                    description=f"chktex Warning {code}",
                    level=level,
                )

        if not seen_rules:
            seen_rules["chktex/W0"] = make_rule(
                rule_id="chktex/W0",
                name="chktex warning",
                description="Generic chktex warning",
                level="warning",
            )

        run = make_run(
            tool_name="chktex",
            tool_version="unknown",
            results=results,
            rules=list(seen_rules.values()),
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc
