"""Synthesis Agent node -- recursive bottom-up documentation from analysis."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def synthesis_node(state: dict) -> dict:
    """Synthesize final documentation from blueprint topology and semantic summaries.

    Reads: blueprint_topology, semantic_summaries, unified_sarif, metrics
    Writes: final_documentation, progress
    """
    topology = state.get("blueprint_topology", {})
    summaries = state.get("semantic_summaries", {})
    metrics = state.get("metrics", {})
    sarif = state.get("unified_sarif", {})

    sections: list[str] = []

    # Header
    target = state.get("target_path", "unknown")
    sections.append(f"# Code Analysis Report\n\nTarget: `{target}`\n")

    # Metrics summary
    sections.append("## Summary\n")
    sections.append(
        f"- **Tools executed**: {metrics.get('tool_count', 0)}\n"
        f"- **Total findings**: {metrics.get('total_findings', 0)}\n"
        f"- **Errors**: {metrics.get('error_count', 0)}\n"
        f"- **Warnings**: {metrics.get('warning_count', 0)}\n"
        f"- **Notes**: {metrics.get('note_count', 0)}\n"
    )

    # Architecture overview
    if topology.get("nodes"):
        sections.append("## Architecture\n")
        sections.append(
            f"- **Files analyzed**: {topology.get('file_count', 0)}\n"
            f"- **Dependency edges**: {topology.get('edge_count', 0)}\n"
        )

        # Group nodes by type
        by_type: dict[str, list[str]] = {}
        for node in topology["nodes"]:
            node_type = node.get("type", "source")
            by_type.setdefault(node_type, []).append(node["id"])

        for ntype, files in sorted(by_type.items()):
            sections.append(f"\n### {ntype.title()} files ({len(files)})\n")
            for f in files[:20]:
                sections.append(f"- `{f}`\n")
            if len(files) > 20:
                sections.append(f"- ... and {len(files) - 20} more\n")

    # Module summaries
    if summaries:
        sections.append("\n## Module Analysis\n")
        for module, info in sorted(summaries.items()):
            doc = info.get("module_doc", "")
            sections.append(f"\n### {module}\n")
            if doc:
                sections.append(f"_{doc}_\n")
            if info.get("file_summaries"):
                sections.append("\nFiles:\n")
                for fs in info["file_summaries"]:
                    sections.append(f"- {fs}\n")
            fc = info.get("finding_count", 0)
            if fc:
                sections.append(f"\nFindings: {fc}\n")

    # Top findings by severity
    sections.append("\n## Key Findings\n")
    all_findings = _collect_findings(sarif)
    errors = [f for f in all_findings if f["level"] == "error"]
    warnings = [f for f in all_findings if f["level"] == "warning"]

    if errors:
        sections.append(f"\n### Errors ({len(errors)})\n")
        for finding in errors[:20]:
            sections.append(
                f"- **{finding['rule_id']}** in `{finding['file']}:{finding['line']}` "
                f"-- {finding['message']}\n"
            )
        if len(errors) > 20:
            sections.append(f"- ... and {len(errors) - 20} more\n")

    if warnings:
        sections.append(f"\n### Warnings ({len(warnings)})\n")
        for finding in warnings[:20]:
            sections.append(
                f"- **{finding['rule_id']}** in `{finding['file']}:{finding['line']}` "
                f"-- {finding['message']}\n"
            )
        if len(warnings) > 20:
            sections.append(f"- ... and {len(warnings) - 20} more\n")

    final_doc = "".join(sections)
    logger.info(f"Synthesis complete: {len(final_doc)} chars")

    return {
        "final_documentation": final_doc,
        "progress": 1.0,
    }


def _collect_findings(sarif: dict) -> list[dict]:
    """Extract a flat list of findings from unified SARIF."""
    findings: list[dict] = []
    for run in sarif.get("runs", []):
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "unknown")
        for result in run.get("results", []):
            file_path = ""
            line = 0
            for loc in result.get("locations", []):
                physical = loc.get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {})
                file_path = artifact.get("uri", "")
                region = physical.get("region", {})
                line = region.get("startLine", 0)
                break  # take first location

            findings.append({
                "tool": tool_name,
                "rule_id": result.get("ruleId", "unknown"),
                "level": result.get("level", "warning"),
                "message": result.get("message", {}).get("text", ""),
                "file": file_path,
                "line": line,
            })

    # Sort: errors first, then warnings, then notes
    level_order = {"error": 0, "warning": 1, "note": 2, "none": 3}
    findings.sort(key=lambda f: level_order.get(f["level"], 3))
    return findings
