"""Convert Deptrac text output to SARIF v2.1.0.

Deptrac (a PHP dependency-analysis tool) produces plain-text violation
lines when it detects forbidden layer dependencies.  Common formats:

    ClassName must not depend on DisallowedClass (LayerA -> LayerB)
    path/to/File.php::ClassName must not depend on DisallowedClass (LayerA -> LayerB)
    path/to/File.php:42 - ClassName must not depend on DisallowedClass (LayerA -> LayerB)

This converter uses regex patterns to extract the relevant parts and
maps each violation to a SARIF warning.
"""

from __future__ import annotations

import hashlib
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

_RULE_ID = "deptrac/forbidden-dependency"

# Patterns to match common deptrac output formats.
# Pattern 1: "path/File.php:42 - ClassName must not depend on Target (A -> B)"
_PAT_WITH_FILE_LINE = re.compile(
    r"^(?P<file>[^\s:]+):(?P<line>\d+)\s*[-:]\s*(?P<message>.+)$"
)
# Pattern 2: "path/File.php::ClassName must not depend on Target (A -> B)"
_PAT_WITH_FILE = re.compile(
    r"^(?P<file>[^\s:]+)::(?P<message>.+)$"
)
# Pattern 3: "ClassName must not depend on Target (A -> B)"
_PAT_PLAIN = re.compile(
    r"^(?P<class>[A-Z][\w\\]+)\s+(?P<message>must not depend on .+)$"
)
# Pattern to extract layer info from the parenthesised suffix.
_PAT_LAYERS = re.compile(
    r"\((?P<source_layer>[^)]+?)\s*->\s*(?P<target_layer>[^)]+?)\)\s*$"
)


class DeptracConverter(BaseConverter):
    """Convert Deptrac text output to SARIF v2.1.0."""

    tool_name: str = "deptrac"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse Deptrac text lines and return a SARIF log.

        Parameters
        ----------
        raw_output:
            The complete text output from ``deptrac analyse``.
        target_path:
            Root of the analysed project.
        """
        results: list[dict[str, Any]] = []

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            result = self._parse_line(stripped)
            if result is not None:
                results.append(result)

        rules = [
            make_rule(
                rule_id=_RULE_ID,
                name="Forbidden dependency",
                description=(
                    "A class depends on another class that is not allowed "
                    "by the configured layer rules."
                ),
                level="warning",
            ),
        ]

        run = make_run(
            tool_name="deptrac",
            tool_version="unknown",
            results=results,
            rules=rules,
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_line(self, line: str) -> dict[str, Any] | None:
        """Attempt to parse a single Deptrac violation line."""
        file_path = ""
        start_line = 1
        message = ""

        # Try each pattern in order of specificity.
        m = _PAT_WITH_FILE_LINE.match(line)
        if m:
            file_path = m.group("file")
            start_line = int(m.group("line"))
            message = m.group("message").strip()
        else:
            m = _PAT_WITH_FILE.match(line)
            if m:
                file_path = m.group("file")
                message = m.group("message").strip()
            else:
                m = _PAT_PLAIN.match(line)
                if m:
                    message = f"{m.group('class')} {m.group('message')}"
                else:
                    # Line does not match any known pattern -- skip it.
                    # Deptrac also emits summary / header lines we ignore.
                    return None

        if not message:
            return None

        # Extract layer information for the properties bag.
        properties: dict[str, Any] = {}
        lm = _PAT_LAYERS.search(message)
        if lm:
            properties["sourceLayer"] = lm.group("source_layer").strip()
            properties["targetLayer"] = lm.group("target_layer").strip()

        # Build fingerprint.
        fp_input = f"{file_path}:{start_line}:{message}"
        fingerprint = hashlib.sha256(fp_input.encode()).hexdigest()

        locations: list[dict[str, Any]] = []
        if file_path:
            locations.append(make_location(file_path=file_path, start_line=start_line))

        return make_result(
            rule_id=_RULE_ID,
            message=message,
            level="warning",
            locations=locations,
            fingerprints={"deptrac/v1": fingerprint},
            properties=properties if properties else None,
        )
