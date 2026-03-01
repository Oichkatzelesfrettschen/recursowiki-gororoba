"""Convert lizard complexity-analysis output (JSON or CSV) to SARIF v2.1.0.

lizard reports per-function metrics: cyclomatic complexity (CC), NLOC,
token count, parameter count, and function length.  This converter flags
functions whose CC exceeds a configurable threshold (default 10) as SARIF
warnings.
"""

from __future__ import annotations

import csv
import io
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

logger = logging.getLogger(__name__)

_DEFAULT_CC_THRESHOLD: int = 10

# Rule definitions for the findings we produce.
_RULE_HIGH_CC = "lizard/high-cyclomatic-complexity"


class LizardConverter(BaseConverter):
    """Convert lizard JSON or CSV output to SARIF v2.1.0."""

    tool_name: str = "lizard"

    def __init__(self, cc_threshold: int = _DEFAULT_CC_THRESHOLD) -> None:
        self.cc_threshold = cc_threshold

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse lizard output and return a SARIF log.

        The method auto-detects whether *raw_output* is JSON or CSV.
        """
        raw_stripped = raw_output.strip()
        if not raw_stripped:
            return self._empty_sarif()

        # Auto-detect format.
        if raw_stripped.startswith("{") or raw_stripped.startswith("["):
            functions = self._parse_json(raw_stripped)
        else:
            functions = self._parse_csv(raw_stripped)

        results: list[dict[str, Any]] = []
        for func in functions:
            result = self._assess_function(func)
            if result is not None:
                results.append(result)

        rules = [
            make_rule(
                rule_id=_RULE_HIGH_CC,
                name="High cyclomatic complexity",
                description=(
                    f"Function cyclomatic complexity exceeds threshold "
                    f"of {self.cc_threshold}"
                ),
                level="warning",
            ),
        ]

        run = make_run(
            tool_name="lizard",
            tool_version="unknown",
            results=results,
            rules=rules,
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(raw: str) -> list[dict[str, Any]]:
        """Parse lizard JSON and return a flat list of function records."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"lizard output is not valid JSON: {exc}") from exc

        functions: list[dict[str, Any]] = []

        # lizard JSON can be a list of file objects or a single object.
        if isinstance(data, list):
            file_list = data
        elif isinstance(data, dict):
            file_list = data.get("files", [data])
        else:
            return functions

        for file_obj in file_list:
            if not isinstance(file_obj, dict):
                continue
            filename = file_obj.get("filename", "")
            for func in file_obj.get("function_list", []):
                if isinstance(func, dict):
                    func.setdefault("filename", filename)
                    functions.append(func)

        return functions

    @staticmethod
    def _parse_csv(raw: str) -> list[dict[str, Any]]:
        """Parse lizard CSV output.

        lizard CSV columns (default order):
            NLOC, CCN, token, PARAM, length, location, file, function,
            start, end
        Some exports use a header row; others do not.  We handle both.
        """
        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)
        if not rows:
            return []

        # Detect header row.
        first = [c.strip().lower() for c in rows[0]]
        has_header = "ccn" in first or "nloc" in first or "cyclomatic_complexity" in first

        if has_header:
            header = first
            data_rows = rows[1:]
        else:
            # Assume default column order.
            header = [
                "nloc", "ccn", "token", "param", "length",
                "location", "file", "function", "start", "end",
            ]
            data_rows = rows

        functions: list[dict[str, Any]] = []
        for row in data_rows:
            if not row or all(c.strip() == "" for c in row):
                continue
            record: dict[str, Any] = {}
            for idx, col in enumerate(header):
                if idx < len(row):
                    record[col] = row[idx].strip()
            functions.append(record)

        return functions

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def _assess_function(self, func: dict[str, Any]) -> dict[str, Any] | None:
        """Return a SARIF result if the function exceeds the CC threshold."""
        cc = self._extract_int(func, ("ccn", "cyclomatic_complexity", "cc"))
        if cc is None or cc <= self.cc_threshold:
            return None

        file_path = str(
            func.get("filename", "")
            or func.get("file", "")
        )
        func_name = str(
            func.get("name", "")
            or func.get("function", "")
            or func.get("function_name", "")
        )
        start_line = self._extract_int(func, ("start_line", "start", "line")) or 1
        end_line = self._extract_int(func, ("end_line", "end"))
        nloc = self._extract_int(func, ("nloc",))
        token_count = self._extract_int(func, ("token", "token_count"))
        param_count = self._extract_int(func, ("param", "parameter_count"))

        message_parts = [
            f"Function '{func_name}' has cyclomatic complexity {cc}",
            f"(threshold {self.cc_threshold})",
        ]
        extras: list[str] = []
        if nloc is not None:
            extras.append(f"NLOC={nloc}")
        if token_count is not None:
            extras.append(f"tokens={token_count}")
        if param_count is not None:
            extras.append(f"params={param_count}")
        if extras:
            message_parts.append("[" + ", ".join(extras) + "]")

        message = " ".join(message_parts)

        location = make_location(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
        )

        return make_result(
            rule_id=_RULE_HIGH_CC,
            message=message,
            level="warning",
            locations=[location],
            properties={
                "cyclomaticComplexity": cc,
                "functionName": func_name,
            },
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_int(
        record: dict[str, Any], keys: tuple[str, ...]
    ) -> int | None:
        """Return the first integer value found under any of *keys*."""
        for key in keys:
            val = record.get(key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    continue
        return None

    def _empty_sarif(self) -> dict[str, Any]:
        """Return an empty but valid SARIF document."""
        run = make_run(tool_name="lizard", tool_version="unknown", results=[])
        return make_sarif_log(runs=[run])
