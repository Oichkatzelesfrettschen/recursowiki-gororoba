"""SARIF v2.1.0 constants and helper functions for building SARIF documents.

Provides factory functions that produce plain dicts conforming to the SARIF
v2.1.0 JSON schema.  No external dependencies -- only stdlib types.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SARIF_VERSION: str = "2.1.0"
SARIF_SCHEMA_URI: str = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/"
    "sarif-2.1/schema/sarif-schema-2.1.0.json"
)

# Known-good SARIF v2.1.0 schema URIs used by different tools.
# All of these refer to the same schema; tools just disagree on canonical URL.
SARIF_KNOWN_SCHEMA_URIS: frozenset[str] = frozenset({
    SARIF_SCHEMA_URI,
    "https://json.schemastore.org/sarif-2.1.0.json",
    "https://json.schemastore.org/sarif-2.1.0-rtm.6.json",
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/"
    "schemas/sarif-schema-2.1.0.json",
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/"
    "sarif-schema-2.1.0.json",
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/schemas/"
    "sarif-schema-2.1.0.json",
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemata/sarif-schema-2.1.0.json",
})

SARIF_LEVELS: tuple[str, ...] = ("error", "warning", "note", "none")

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def make_sarif_log(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a top-level SARIF log envelope.

    Parameters
    ----------
    runs:
        One or more SARIF *run* objects (see :func:`make_run`).

    Returns
    -------
    dict
        A complete ``sarifLog`` object ready for JSON serialisation.
    """
    return {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": list(runs),
    }


def make_run(
    tool_name: str,
    tool_version: str = "unknown",
    results: list[dict[str, Any]] | None = None,
    rules: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a SARIF *run* object.

    Parameters
    ----------
    tool_name:
        Human-readable name of the analysis tool.
    tool_version:
        Semantic version string for the tool.
    results:
        List of :func:`make_result` dicts.
    rules:
        List of :func:`make_rule` dicts for ``tool.driver.rules``.
    artifacts:
        Optional list of artifact objects referenced by results.
    properties:
        Optional property bag for the run.
    """
    run: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": tool_name,
                "version": tool_version,
                "rules": rules if rules is not None else [],
            },
        },
        "results": results if results is not None else [],
    }
    if artifacts is not None:
        run["artifacts"] = artifacts
    if properties is not None:
        run["properties"] = properties
    return run


def make_result(
    rule_id: str,
    message: str,
    level: str = "warning",
    locations: list[dict[str, Any]] | None = None,
    fingerprints: dict[str, str] | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a SARIF *result* object.

    Parameters
    ----------
    rule_id:
        Stable identifier for the rule that produced this result.
    message:
        Human-readable description of the finding.
    level:
        One of ``"error"``, ``"warning"``, ``"note"``, ``"none"``.
    locations:
        List of :func:`make_location` dicts.
    fingerprints:
        Optional dict of fingerprint contributions for deduplication.
    properties:
        Optional property bag.
    """
    if level not in SARIF_LEVELS:
        logger.warning("Invalid SARIF level %r; falling back to 'warning'", level)
        level = "warning"

    result: dict[str, Any] = {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
    }
    if locations:
        result["locations"] = locations
    if fingerprints:
        result["fingerprints"] = fingerprints
    if properties:
        result["properties"] = properties
    return result


def make_location(
    file_path: str,
    start_line: int = 1,
    start_column: int | None = None,
    end_line: int | None = None,
    end_column: int | None = None,
) -> dict[str, Any]:
    """Create a SARIF *location* object with a physical location.

    Parameters
    ----------
    file_path:
        Path to the file (used as the artifact URI).
    start_line:
        1-based starting line number.
    start_column:
        Optional 1-based starting column.
    end_line:
        Optional ending line number.
    end_column:
        Optional ending column.
    """
    region: dict[str, int] = {"startLine": start_line}
    if start_column is not None:
        region["startColumn"] = start_column
    if end_line is not None:
        region["endLine"] = end_line
    if end_column is not None:
        region["endColumn"] = end_column

    return {
        "physicalLocation": {
            "artifactLocation": {"uri": file_path},
            "region": region,
        },
    }


def make_rule(
    rule_id: str,
    name: str = "",
    description: str = "",
    level: str = "warning",
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a SARIF *reportingDescriptor* (rule) object.

    Parameters
    ----------
    rule_id:
        Stable, unique identifier for the rule.
    name:
        Short human-readable name.
    description:
        Longer description of what the rule detects.
    level:
        Default severity level for results produced by this rule.
    properties:
        Optional property bag.
    """
    rule: dict[str, Any] = {"id": rule_id}
    if name:
        rule["name"] = name
    if description:
        rule["fullDescription"] = {"text": description}
    if level and level in SARIF_LEVELS:
        rule["defaultConfiguration"] = {"level": level}
    if properties:
        rule["properties"] = properties
    return rule
