"""Semantic Agent node -- business logic summarization from code and comments."""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


def semantic_node(state: dict) -> dict:
    """Summarize business logic per module by analyzing code structure and comments.

    Reads: target_path, unified_sarif
    Writes: semantic_summaries, progress
    """
    target_path = state.get("target_path", "")
    sarif = state.get("unified_sarif", {})

    if not target_path or not os.path.isdir(target_path):
        return {"semantic_summaries": {}, "progress": 0.85}

    # Group findings by directory (module proxy)
    module_findings: dict[str, list[str]] = defaultdict(list)
    for run in sarif.get("runs", []):
        for result in run.get("results", []):
            for location in result.get("locations", []):
                uri = (
                    location
                    .get("physicalLocation", {})
                    .get("artifactLocation", {})
                    .get("uri", "")
                )
                if uri:
                    module = os.path.dirname(uri) or "(root)"
                    msg = result.get("message", {}).get("text", "")
                    module_findings[module].append(msg)

    # Extract module-level summaries from docstrings and comments
    summaries: dict[str, dict] = {}

    for dirpath, _dirs, files in os.walk(target_path):
        rel_dir = os.path.relpath(dirpath, target_path)
        if rel_dir == ".":
            rel_dir = "(root)"

        module_doc = ""
        file_purposes: list[str] = []

        for fname in sorted(files):
            fpath = os.path.join(dirpath, fname)
            if fname.endswith(".py"):
                doc = _extract_python_module_doc(fpath)
                if doc:
                    file_purposes.append(f"{fname}: {doc}")
            elif fname.endswith((".js", ".ts", ".tsx", ".jsx")):
                doc = _extract_js_header_comment(fpath)
                if doc:
                    file_purposes.append(f"{fname}: {doc}")

            # Check for __init__.py module docstring
            if fname == "__init__.py":
                module_doc = _extract_python_module_doc(fpath) or ""

        findings_for_module = module_findings.get(rel_dir, [])

        if file_purposes or findings_for_module or module_doc:
            summaries[rel_dir] = {
                "module_doc": module_doc,
                "file_summaries": file_purposes[:20],  # cap to avoid state bloat
                "finding_count": len(findings_for_module),
                "sample_findings": findings_for_module[:5],
            }

    logger.info(f"Semantic analysis: {len(summaries)} modules analyzed")
    return {
        "semantic_summaries": summaries,
        "progress": 0.85,
    }


def _extract_python_module_doc(file_path: str) -> str | None:
    """Extract the first docstring from a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(4096)  # read first 4K only
        match = re.search(r'^(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')', content, re.DOTALL)
        if match:
            doc = (match.group(1) or match.group(2) or "").strip()
            # Return first line only
            return doc.split("\n")[0].strip()
    except Exception:
        pass
    return None


def _extract_js_header_comment(file_path: str) -> str | None:
    """Extract the first block comment from a JS/TS file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(4096)
        match = re.search(r"/\*\*?\s*(.*?)(?:\*/|\n\s*\*\s*@)", content, re.DOTALL)
        if match:
            lines = match.group(1).strip().split("\n")
            # Clean leading * from JSDoc lines
            cleaned = [re.sub(r"^\s*\*\s?", "", line).strip() for line in lines]
            first = next((l for l in cleaned if l), None)
            return first
    except Exception:
        pass
    return None
