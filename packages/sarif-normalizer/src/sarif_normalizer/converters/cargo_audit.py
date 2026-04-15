"""Convert cargo-audit JSON output to SARIF v2.1.0.

``cargo audit --json`` produces a single JSON object with a
``vulnerabilities.list[]`` array.  Each entry contains ``advisory`` (id,
title, description, url) and ``package`` (name, version) metadata.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sarif_normalizer.converters.base import BaseConverter
from sarif_normalizer.schema import (
    make_result,
    make_rule,
    make_run,
    make_sarif_log,
)
from sarif_normalizer.severity_mapper import SeverityMapper

logger = logging.getLogger(__name__)

_SEVERITY = SeverityMapper()


class CargoAuditConverter(BaseConverter):
    """Convert cargo-audit JSON output to SARIF v2.1.0."""

    tool_name: str = "cargo-audit"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        try:
            data: dict[str, Any] = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"cargo-audit output is not valid JSON: {exc}") from exc

        vulns: list[dict[str, Any]] = (
            data.get("vulnerabilities", {}).get("list", [])
        )

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for vuln in vulns:
            result, rule = self._convert_vuln(vuln)
            if result is not None:
                results.append(result)
            if rule is not None and rule["id"] not in seen_rules:
                seen_rules[rule["id"]] = rule

        run = make_run(
            tool_name="cargo-audit",
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
    def _convert_vuln(
        vuln: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        advisory: dict[str, Any] = vuln.get("advisory", {})
        package: dict[str, Any] = vuln.get("package", {})

        adv_id: str = advisory.get("id", "UNKNOWN")
        title: str = advisory.get("title", "")
        description: str = advisory.get("description", "")
        url: str = advisory.get("url", "")
        pkg_name: str = package.get("name", "unknown")
        pkg_version: str = package.get("version", "unknown")

        patched = vuln.get("versions", {}).get("patched", [])
        patched_str = ", ".join(patched) if patched else "none"

        message = (
            f"{adv_id}: {title} in {pkg_name}@{pkg_version} "
            f"(patched: {patched_str})"
        )
        if url:
            message += f" -- {url}"

        rule_id = f"cargo-audit/{adv_id}"

        result = make_result(
            rule_id=rule_id,
            message=message,
            level="error",
            properties={
                "package": pkg_name,
                "version": pkg_version,
                "advisory_url": url,
            },
        )

        rule = make_rule(
            rule_id=rule_id,
            name=adv_id,
            description=description or title,
            level="error",
        )

        return result, rule
