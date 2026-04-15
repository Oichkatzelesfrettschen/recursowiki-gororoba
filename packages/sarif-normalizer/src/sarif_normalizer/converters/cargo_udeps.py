"""Convert cargo-udeps JSON output to SARIF v2.1.0.

``cargo udeps --output json`` produces a JSON object with ``unused_deps``
mapping crate names to lists of unused normal, dev, and build dependencies.
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

logger = logging.getLogger(__name__)

_RULE_ID = "cargo-udeps/unused-dependency"


class CargoUdepsConverter(BaseConverter):
    """Convert cargo-udeps JSON output to SARIF v2.1.0."""

    tool_name: str = "cargo-udeps"

    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        try:
            data: dict[str, Any] = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"cargo-udeps output is not valid JSON: {exc}") from exc

        results: list[dict[str, Any]] = []

        unused_deps = data.get("unused_deps", {})
        for crate_name, dep_info in unused_deps.items():
            if not isinstance(dep_info, dict):
                continue
            manifest = dep_info.get("manifest_path", "")
            for dep_kind in ("normal", "development", "build"):
                deps = dep_info.get(dep_kind, [])
                if not isinstance(deps, list):
                    continue
                for dep_name in deps:
                    if not isinstance(dep_name, str):
                        # Some formats nest {name, ...} dicts.
                        dep_name = dep_name.get("name", str(dep_name)) if isinstance(dep_name, dict) else str(dep_name)
                    message = (
                        f"Unused {dep_kind} dependency '{dep_name}' in crate '{crate_name}'"
                    )
                    if manifest:
                        message += f" ({manifest})"
                    results.append(
                        make_result(
                            rule_id=_RULE_ID,
                            message=message,
                            level="warning",
                            properties={
                                "crate": crate_name,
                                "dependency": dep_name,
                                "kind": dep_kind,
                            },
                        )
                    )

        rules = [
            make_rule(
                rule_id=_RULE_ID,
                name="Unused dependency",
                description="A dependency declared in Cargo.toml is not used by the crate.",
                level="warning",
            ),
        ]

        run = make_run(
            tool_name="cargo-udeps",
            tool_version="unknown",
            results=results,
            rules=rules,
        )
        sarif_doc = make_sarif_log(runs=[run])

        if not self.validate_sarif(sarif_doc):
            logger.error("Generated SARIF failed validation")

        return sarif_doc
