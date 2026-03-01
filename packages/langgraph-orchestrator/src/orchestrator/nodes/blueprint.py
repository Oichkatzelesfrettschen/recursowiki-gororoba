"""Blueprint Agent node -- structural topology extraction from SARIF."""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


def blueprint_node(state: dict) -> dict:
    """Build a structural dependency graph from SARIF findings and source files.

    Reads: unified_sarif, target_path
    Writes: blueprint_topology, progress
    """
    sarif = state.get("unified_sarif", {})
    target_path = state.get("target_path", "")

    # Build a map of files -> findings for structural analysis
    file_findings: dict[str, list[dict]] = defaultdict(list)
    for run in sarif.get("runs", []):
        for result in run.get("results", []):
            for location in result.get("locations", []):
                physical = location.get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {})
                uri = artifact.get("uri", "")
                if uri:
                    file_findings[uri].append({
                        "rule_id": result.get("ruleId", ""),
                        "level": result.get("level", "warning"),
                        "message": result.get("message", {}).get("text", ""),
                    })

    # Build dependency graph from import analysis
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_files: set[str] = set()

    for file_path, findings in file_findings.items():
        node_id = file_path
        if node_id not in seen_files:
            seen_files.add(node_id)
            nodes.append({
                "id": node_id,
                "type": _classify_file(file_path),
                "finding_count": len(findings),
                "severity_max": _max_severity(findings),
            })

    # Attempt to find import relationships from Python files
    if target_path and os.path.isdir(target_path):
        edges = _extract_import_edges(target_path, seen_files)

    topology = {
        "nodes": nodes,
        "edges": edges,
        "file_count": len(nodes),
        "edge_count": len(edges),
    }

    logger.info(f"Blueprint: {len(nodes)} nodes, {len(edges)} edges")
    return {
        "blueprint_topology": topology,
        "progress": 0.85,
    }


def _classify_file(path: str) -> str:
    """Classify a file as source, test, config, or docs."""
    lower = path.lower()
    if "test" in lower or "spec" in lower:
        return "test"
    if lower.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")):
        return "config"
    if lower.endswith((".md", ".rst", ".txt")):
        return "docs"
    return "source"


def _max_severity(findings: list[dict]) -> str:
    """Return the highest severity among findings."""
    levels = {"error": 3, "warning": 2, "note": 1, "none": 0}
    max_level = 0
    max_name = "none"
    for f in findings:
        level = f.get("level", "warning")
        if levels.get(level, 0) > max_level:
            max_level = levels[level]
            max_name = level
    return max_name


def _extract_import_edges(target_path: str, known_files: set[str]) -> list[dict]:
    """Best-effort Python import graph extraction."""
    edges: list[dict] = []
    import_re = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)

    for root, _dirs, files in os.walk(target_path):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, target_path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                for match in import_re.finditer(content):
                    module = match.group(1)
                    # Convert module path to file path guess
                    module_file = module.replace(".", "/") + ".py"
                    if module_file in known_files or rel_path in known_files:
                        edges.append({
                            "source": rel_path,
                            "target": module_file,
                            "type": "import",
                        })
            except Exception:
                continue

    return edges
