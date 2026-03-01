"""Conditional edge functions for routing between graph nodes."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maps languages to the tool names that should run for them.
LANGUAGE_TOOL_MAP: dict[str, list[str]] = {
    "python": ["semgrep", "bandit", "ruff", "pyright", "lizard", "detect-secrets", "trivy", "checkov"],
    "javascript": ["semgrep", "eslint", "lizard", "detect-secrets", "trivy"],
    "typescript": ["semgrep", "eslint", "lizard", "detect-secrets", "trivy"],
    "java": ["semgrep", "pmd", "pmd-cpd", "lizard", "detect-secrets", "trivy", "owasp-dependency-check"],
    "go": ["semgrep", "gosec", "lizard", "detect-secrets", "trivy"],
    "c": ["semgrep", "cppcheck", "clang-sa", "lizard", "detect-secrets"],
    "cpp": ["semgrep", "cppcheck", "clang-sa", "lizard", "detect-secrets"],
    "ruby": ["semgrep", "brakeman", "lizard", "detect-secrets", "trivy"],
    "php": ["semgrep", "phpcs", "deptrac", "lizard", "detect-secrets"],
    "rust": ["semgrep", "lizard", "detect-secrets", "trivy"],
    "csharp": ["semgrep", "lizard", "detect-secrets"],
    "solidity": ["slither", "detect-secrets"],
    "terraform": ["checkov", "kics", "trivy"],
    "docker": ["checkov", "trivy", "kics"],
    "yaml": ["checkov", "kics"],
}

# Tools that run regardless of language
UNIVERSAL_TOOLS: list[str] = ["trufflehog", "horusec"]


def select_tools_for_languages(detected_languages: list[str]) -> list[str]:
    """Given detected languages, return the union of applicable tools."""
    selected: set[str] = set(UNIVERSAL_TOOLS)
    for lang in detected_languages:
        lang_lower = lang.lower()
        if lang_lower in LANGUAGE_TOOL_MAP:
            selected.update(LANGUAGE_TOOL_MAP[lang_lower])
        else:
            logger.info(f"No tool mapping for language: {lang}")
    return sorted(selected)


def should_run_agents(state: dict) -> str:
    """Decide whether to run multi-agent synthesis or skip to end.

    Returns the next node name: 'agents' or 'end'.
    """
    unified = state.get("unified_sarif", {})
    runs = unified.get("runs", [])
    total_results = sum(len(run.get("results", [])) for run in runs)
    if total_results == 0:
        logger.info("No findings in unified SARIF; skipping agent synthesis")
        return "end"
    return "agents"
