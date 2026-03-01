"""Convert trufflehog JSON-lines output to SARIF v2.1.0.

trufflehog emits one JSON object per line.  Each object contains at
minimum ``SourceMetadata``, ``DetectorName``, ``Raw``, and ``Verified``.
Verified secrets are mapped to ``"error"``; unverified to ``"warning"``.
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

_RULE_SECRET = "trufflehog/secret-detected"


class TrufflehogConverter(BaseConverter):
    """Convert trufflehog JSON-lines output to SARIF v2.1.0."""

    tool_name: str = "trufflehog"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse trufflehog output and return a SARIF log.

        Parameters
        ----------
        raw_output:
            One JSON object per line, as produced by trufflehog.
        target_path:
            Root of the analysed project.
        """
        findings = self._parse_jsonl(raw_output)

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for finding in findings:
            result, rule = self._convert_finding(finding)
            if result is not None:
                results.append(result)
            if rule is not None and rule["id"] not in seen_rules:
                seen_rules[rule["id"]] = rule

        if not seen_rules:
            seen_rules[_RULE_SECRET] = make_rule(
                rule_id=_RULE_SECRET,
                name="Secret detected",
                description="trufflehog detected a potential secret in the source.",
                level="warning",
            )

        run = make_run(
            tool_name="trufflehog",
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
    def _parse_jsonl(raw: str) -> list[dict[str, Any]]:
        """Parse newline-delimited JSON."""
        findings: list[dict[str, Any]] = []
        for lineno, line in enumerate(raw.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict):
                    findings.append(obj)
            except json.JSONDecodeError:
                logger.debug("Skipping non-JSON line %d", lineno)
        return findings

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert_finding(
        self, finding: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Convert a single trufflehog finding to a SARIF result + rule."""
        detector: str = finding.get("DetectorName", "unknown-detector")
        verified: bool = finding.get("Verified", False)
        raw_secret: str = finding.get("Raw", "")

        # Build a redacted message -- never put the raw secret into SARIF.
        redacted = self._redact(raw_secret)

        source_meta: dict[str, Any] = finding.get("SourceMetadata", {})
        data: dict[str, Any] = source_meta.get("Data", {})

        # trufflehog puts file info in different sub-keys depending on
        # the source type (filesystem, git, etc.).
        file_path, line = self._extract_location(data)

        level_key = "verified" if verified else "unverified"
        level = _SEVERITY.map_severity("trufflehog", level_key)

        verified_label = "VERIFIED" if verified else "unverified"
        message = (
            f"{verified_label} secret detected by {detector}: {redacted}"
        )

        rule_id = f"trufflehog/{detector}"

        # Fingerprint based on detector + file + hashed raw.
        fp_input = f"{detector}:{file_path}:{hashlib.sha256(raw_secret.encode()).hexdigest()}"
        fingerprint = hashlib.sha256(fp_input.encode()).hexdigest()

        locations: list[dict[str, Any]] = []
        if file_path:
            locations.append(make_location(file_path=file_path, start_line=line))

        result = make_result(
            rule_id=rule_id,
            message=message,
            level=level,
            locations=locations,
            fingerprints={"trufflehog/v1": fingerprint},
            properties={
                "detector": detector,
                "verified": verified,
            },
        )

        rule = make_rule(
            rule_id=rule_id,
            name=f"trufflehog: {detector}",
            description=f"Secret detected by the {detector} detector.",
            level=level,
        )

        return result, rule

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_location(data: dict[str, Any]) -> tuple[str, int]:
        """Best-effort extraction of file path and line from SourceMetadata.Data."""
        # Filesystem source
        file_path = str(data.get("Filesystem", {}).get("file", "")
                        or data.get("Git", {}).get("file", "")
                        or data.get("file", "")
                        or "")
        line_val = (data.get("Filesystem", {}).get("line", 0)
                    or data.get("Git", {}).get("line", 0)
                    or data.get("line", 0))
        try:
            line = max(int(line_val), 1)
        except (ValueError, TypeError):
            line = 1
        return file_path, line

    @staticmethod
    def _redact(secret: str, visible: int = 4) -> str:
        """Return a redacted version of *secret* for safe display."""
        if len(secret) <= visible:
            return "****"
        return secret[:visible] + "****"
