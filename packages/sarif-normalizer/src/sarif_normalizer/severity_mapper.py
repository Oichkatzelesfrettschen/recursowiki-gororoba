"""Normalise heterogeneous severity scales to SARIF v2.1.0 levels.

Different static-analysis, secret-scanning, and complexity tools each use
their own severity vocabulary.  This module provides a single mapping
layer so that every converter can delegate severity translation here.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# SARIF v2.1.0 defines exactly four result levels.
_SARIF_LEVELS = frozenset({"error", "warning", "note", "none"})

# ---------------------------------------------------------------------------
# Generic (tool-agnostic) mapping -- used when no tool-specific override
# exists.  Keys are lowercased input strings.
# ---------------------------------------------------------------------------
_GENERIC_MAP: dict[str, str] = {
    # Critical / high -> error
    "critical": "error",
    "high": "error",
    "fatal": "error",
    "blocker": "error",
    "error": "error",
    "err": "error",
    "fail": "error",
    "failure": "error",
    # Medium -> warning
    "medium": "warning",
    "moderate": "warning",
    "warning": "warning",
    "warn": "warning",
    "major": "warning",
    # Low / informational -> note
    "low": "note",
    "info": "note",
    "information": "note",
    "informational": "note",
    "minor": "note",
    "hint": "note",
    "style": "note",
    "suggestion": "note",
    "refactor": "note",
    "convention": "note",
    # Explicit "none"
    "none": "none",
    "unknown": "none",
}

# ---------------------------------------------------------------------------
# Tool-specific overrides -- when a tool uses terminology that clashes with
# the generic map, put the correction here.
# ---------------------------------------------------------------------------
_TOOL_OVERRIDES: dict[str, dict[str, str]] = {
    # Pyright uses "information" for its lowest severity.
    "pyright": {
        "error": "error",
        "warning": "warning",
        "information": "note",
    },
    # Semgrep uses INFO / WARNING / ERROR.
    "semgrep": {
        "info": "note",
        "warning": "warning",
        "error": "error",
    },
    # Bandit uses LOW / MEDIUM / HIGH severity *and* confidence.
    "bandit": {
        "low": "note",
        "medium": "warning",
        "high": "error",
    },
    # Trivy uses CRITICAL / HIGH / MEDIUM / LOW / UNKNOWN.
    "trivy": {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
        "unknown": "none",
    },
    # Ruff follows the same pattern as flake8.
    "ruff": {
        "error": "error",
        "warning": "warning",
        "info": "note",
    },
    # PHP_CodeSniffer
    "phpcs": {
        "error": "error",
        "warning": "warning",
    },
    # Horusec
    "horusec": {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
        "info": "note",
    },
    # TruffleHog -- verified secrets are errors, unverified are warnings.
    "trufflehog": {
        "verified": "error",
        "unverified": "warning",
    },
    # detect-secrets -- all potential secrets default to warning.
    "detect-secrets": {
        "true positive": "error",
        "possible": "warning",
    },
    # Checkov
    "checkov": {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
    },
}


class SeverityMapper:
    """Map tool-native severity strings to SARIF v2.1.0 ``level`` values."""

    def __init__(self) -> None:
        self._generic_map: dict[str, str] = dict(_GENERIC_MAP)
        self._tool_overrides: dict[str, dict[str, str]] = {
            k: dict(v) for k, v in _TOOL_OVERRIDES.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map_severity(self, tool_name: str, tool_severity: str) -> str:
        """Normalise *tool_severity* to a SARIF level.

        Parameters
        ----------
        tool_name:
            Lowercase canonical name of the tool (e.g. ``"semgrep"``).
        tool_severity:
            The severity string produced by the tool.

        Returns
        -------
        str
            One of ``"error"``, ``"warning"``, ``"note"``, ``"none"``.
        """
        key = tool_severity.strip().lower()

        # If the input is already a valid SARIF level, short-circuit.
        if key in _SARIF_LEVELS:
            # Still check overrides -- a tool might map "error" differently.
            override_map = self._tool_overrides.get(tool_name.lower())
            if override_map and key in override_map:
                return override_map[key]
            return key

        # Try tool-specific override first.
        override_map = self._tool_overrides.get(tool_name.lower())
        if override_map:
            mapped = override_map.get(key)
            if mapped:
                return mapped

        # Fall back to the generic map.
        mapped = self._generic_map.get(key)
        if mapped:
            return mapped

        logger.warning(
            "Unknown severity %r from tool %r; defaulting to 'warning'",
            tool_severity,
            tool_name,
        )
        return "warning"

    def register_tool(self, tool_name: str, mapping: dict[str, str]) -> None:
        """Register or update a tool-specific severity mapping.

        Parameters
        ----------
        tool_name:
            Canonical tool name (lowercased internally).
        mapping:
            Dict mapping tool severity strings (lowercased) to SARIF levels.
        """
        clean: dict[str, str] = {}
        for src, dst in mapping.items():
            if dst not in _SARIF_LEVELS:
                raise ValueError(
                    f"Target level {dst!r} is not a valid SARIF level; "
                    f"must be one of {sorted(_SARIF_LEVELS)}"
                )
            clean[src.lower()] = dst
        self._tool_overrides[tool_name.lower()] = clean
