"""Convert detect-secrets JSON output to SARIF v2.1.0.

detect-secrets produces a JSON baseline file with the structure::

    {
      "version": "...",
      "plugins_used": [...],
      "results": {
        "path/to/file.py": [
          {"type": "Secret Keyword", "line_number": 10, "hashed_secret": "..."},
          ...
        ]
      }
    }

Each potential secret is mapped to a SARIF result.
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

logger = logging.getLogger(__name__)


class DetectSecretsConverter(BaseConverter):
    """Convert detect-secrets JSON baseline to SARIF v2.1.0."""

    tool_name: str = "detect-secrets"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Parse detect-secrets JSON and return a SARIF log.

        Parameters
        ----------
        raw_output:
            Complete JSON string of the detect-secrets baseline file.
        target_path:
            Root of the analysed project.
        """
        stripped = raw_output.strip()
        if not stripped:
            # Empty output means no secrets found -- return a clean SARIF log.
            run = make_run(
                tool_name="detect-secrets",
                tool_version="unknown",
                results=[],
                rules=[],
            )
            return make_sarif_log(runs=[run])

        try:
            data: dict[str, Any] = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"detect-secrets output is not valid JSON: {exc}") from exc

        ds_version: str = data.get("version", "unknown")
        file_results: dict[str, list[dict[str, Any]]] = data.get("results", {})

        results: list[dict[str, Any]] = []
        seen_rules: dict[str, dict[str, Any]] = {}

        for file_path, secrets in file_results.items():
            if not isinstance(secrets, list):
                logger.warning("Unexpected value for file %r, expected list", file_path)
                continue
            for secret in secrets:
                result, rule = self._convert_secret(file_path, secret)
                if result is not None:
                    results.append(result)
                if rule is not None and rule["id"] not in seen_rules:
                    seen_rules[rule["id"]] = rule

        run = make_run(
            tool_name="detect-secrets",
            tool_version=ds_version,
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
    def _convert_secret(
        file_path: str,
        secret: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Convert a single detect-secrets finding."""
        secret_type: str = secret.get("type", "Unknown")
        line_number: int = int(secret.get("line_number", 1))
        hashed_secret: str = secret.get("hashed_secret", "")
        is_verified: bool = secret.get("is_verified", False)

        # Rule ID derived from the detector type.
        rule_id = f"detect-secrets/{secret_type.lower().replace(' ', '-')}"

        level = "error" if is_verified else "warning"

        message = (
            f"Potential secret detected ({secret_type}) at line {line_number}"
        )

        # Fingerprint: stable across runs for the same finding.
        fp_input = f"{file_path}:{line_number}:{hashed_secret}"
        fingerprint = hashlib.sha256(fp_input.encode()).hexdigest()

        location = make_location(file_path=file_path, start_line=line_number)

        result = make_result(
            rule_id=rule_id,
            message=message,
            level=level,
            locations=[location],
            fingerprints={"detect-secrets/v1": fingerprint},
            properties={
                "secretType": secret_type,
                "hashedSecret": hashed_secret,
                "isVerified": is_verified,
            },
        )

        rule = make_rule(
            rule_id=rule_id,
            name=f"detect-secrets: {secret_type}",
            description=f"Potential {secret_type} detected by detect-secrets.",
            level=level,
        )

        return result, rule
