"""Convert lacheck plain-text output to SARIF v2.1.0.

lacheck emits lines in the format:
    "filename", line NNN: message
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

logger = logging.getLogger(__name__)

# Pattern: "filename", line NNN: message
_LINE_RE = re.compile(
    r'^"(?P<file>[^"]+)",\s*line\s+(?P<line>\d+):\s*(?P<message>.+)$'
)

_RULE_ID = "lacheck/warning"


class LacheckConverter(BaseConverter):
    """Convert lacheck plain-text output to SARIF v2.1.0."""

    tool_name: str = "lacheck"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        results: list[dict[str, Any]] = []

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = _LINE_RE.match(stripped)
            if not match:
                continue

            file_path = match.group("file")
            line_num = int(match.group("line"))
            message = match.group("message")

            results.append(
                make_result(
                    rule_id=_RULE_ID,
                    message=message,
                    level="warning",
                    locations=[
                        make_location(
                            file_path=file_path,
                            start_line=line_num,
                        ),
                    ],
                )
            )

        rules = [
            make_rule(
                rule_id=_RULE_ID,
                name="lacheck warning",
                description="LaTeX consistency warning detected by lacheck.",
                level="warning",
            ),
        ]

        run = make_run(
            tool_name="lacheck",
            tool_version="unknown",
            results=results,
            rules=rules,
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc
