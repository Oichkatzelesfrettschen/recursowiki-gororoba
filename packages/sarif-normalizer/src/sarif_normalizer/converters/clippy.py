"""Convert cargo clippy JSON message-format output to SARIF v2.1.0.

When invoked with ``--message-format json``, cargo emits one JSON object per
line.  Objects with ``reason: "compiler-message"`` contain a ``message`` dict
with ``level``, ``code.code``, ``spans[].file_name/line_start/column_start``,
and ``message`` text.
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


class ClippyConverter(BaseConverter):
    """Convert cargo clippy JSON-lines output to SARIF v2.1.0."""

    tool_name: str = "clippy"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        messages = self._parse_compiler_messages(raw_output)

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for msg in messages:
            result, rule = self._convert_message(msg)
            if result is not None:
                results.append(result)
            if rule is not None and rule["id"] not in seen_rules:
                seen_rules[rule["id"]] = rule

        run = make_run(
            tool_name="clippy",
            tool_version="unknown",
            results=results,
            rules=list(seen_rules.values()),
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_compiler_messages(raw: str) -> list[dict[str, Any]]:
        """Extract compiler-message objects from cargo JSON-lines output."""
        messages: list[dict[str, Any]] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("reason") == "compiler-message":
                msg = obj.get("message")
                if isinstance(msg, dict):
                    messages.append(msg)
        return messages

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_message(
        msg: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        level_raw: str = msg.get("level", "warning")
        text: str = msg.get("message", "")
        code_obj = msg.get("code") or {}
        code_str: str = code_obj.get("code", "clippy-diagnostic") if isinstance(code_obj, dict) else "clippy-diagnostic"

        level = _SEVERITY.map_severity("clippy", level_raw)

        # Skip internal compiler notes without actionable content.
        if level_raw in ("note",) and not code_str.startswith("clippy::"):
            return None, None

        spans: list[dict[str, Any]] = msg.get("spans", [])
        primary_span = None
        for span in spans:
            if span.get("is_primary", False):
                primary_span = span
                break
        if primary_span is None and spans:
            primary_span = spans[0]

        locations: list[dict[str, Any]] = []
        if primary_span:
            file_name = primary_span.get("file_name", "")
            if file_name:
                locations.append(
                    make_location(
                        file_path=file_name,
                        start_line=primary_span.get("line_start", 1),
                        start_column=primary_span.get("column_start"),
                        end_line=primary_span.get("line_end"),
                        end_column=primary_span.get("column_end"),
                    )
                )

        rule_id = f"clippy/{code_str}" if code_str else "clippy/unknown"

        result = make_result(
            rule_id=rule_id,
            message=text,
            level=level,
            locations=locations,
        )

        rule = make_rule(
            rule_id=rule_id,
            name=code_str,
            description=f"Clippy lint: {code_str}",
            level=level,
        )

        return result, rule
