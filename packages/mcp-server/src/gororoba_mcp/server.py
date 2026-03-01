"""Gororoba MCP server -- expose code analysis tools via Model Context Protocol.

Supports stdio (primary, for Claude Code) and SSE (for web clients) transports.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    ResourceTemplate,
    Tool,
    TextContent,
    Prompt,
    PromptMessage,
    PromptArgument,
    GetPromptResult,
)

logger = logging.getLogger(__name__)

app = Server("gororoba")

# In-memory store of analysis results keyed by run_id
_results_store: dict[str, dict] = {}


def _get_target_path() -> str:
    """Get the default analysis target from environment or cwd."""
    return os.environ.get("GOROROBA_TARGET", os.getcwd())


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            uriTemplate="sarif://results/{run_id}",
            name="Full SARIF document",
            description="Complete unified SARIF analysis results for a run",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="sarif://results/{run_id}/findings/{severity}",
            name="Findings by severity",
            description="Filtered findings (error, warning, note)",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="sarif://results/{run_id}/metrics",
            name="Analysis metrics",
            description="Aggregate analysis metrics (counts, complexity)",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="sarif://results/{run_id}/topology",
            name="Dependency topology",
            description="Structural dependency graph",
            mimeType="application/json",
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    parts = uri.replace("sarif://results/", "").split("/")
    if not parts:
        return json.dumps({"error": "Invalid URI"})

    run_id = parts[0]
    result = _results_store.get(run_id)
    if result is None:
        return json.dumps({"error": f"No results for run_id: {run_id}"})

    if len(parts) == 1:
        # Full SARIF
        return json.dumps(result.get("unified_sarif", {}), indent=2)

    sub = parts[1] if len(parts) > 1 else ""

    if sub == "findings" and len(parts) > 2:
        severity = parts[2]
        sarif = result.get("unified_sarif", {})
        findings = []
        for run in sarif.get("runs", []):
            for res in run.get("results", []):
                if res.get("level") == severity:
                    findings.append(res)
        return json.dumps(findings, indent=2)

    if sub == "metrics":
        return json.dumps(result.get("metrics", {}), indent=2)

    if sub == "topology":
        return json.dumps(result.get("blueprint_topology", {}), indent=2)

    return json.dumps({"error": f"Unknown resource path: {uri}"})


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_directory",
            description="Run the full code analysis pipeline on a directory. Returns a run_id to query results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the directory to analyze. Defaults to GOROROBA_TARGET env var.",
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of specific tool names to run.",
                    },
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of languages to restrict detection to.",
                    },
                },
            },
        ),
        Tool(
            name="get_findings",
            description="Query analysis findings with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Analysis run ID"},
                    "severity": {
                        "type": "string",
                        "enum": ["error", "warning", "note"],
                        "description": "Filter by severity level",
                    },
                    "file": {"type": "string", "description": "Filter by file path"},
                    "tool": {"type": "string", "description": "Filter by tool name"},
                    "limit": {
                        "type": "integer",
                        "description": "Max findings to return (default 50)",
                        "default": 50,
                    },
                },
                "required": ["run_id"],
            },
        ),
        Tool(
            name="get_metrics",
            description="Get aggregate analysis metrics for a run.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Analysis run ID"},
                },
                "required": ["run_id"],
            },
        ),
        Tool(
            name="explain_finding",
            description="Get a human-readable explanation of a specific finding.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Analysis run ID"},
                    "finding_index": {
                        "type": "integer",
                        "description": "Index of the finding in the results",
                    },
                },
                "required": ["run_id", "finding_index"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "analyze_directory":
        return await _tool_analyze_directory(arguments)
    elif name == "get_findings":
        return await _tool_get_findings(arguments)
    elif name == "get_metrics":
        return await _tool_get_metrics(arguments)
    elif name == "explain_finding":
        return await _tool_explain_finding(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _tool_analyze_directory(args: dict) -> list[TextContent]:
    path = args.get("path") or _get_target_path()
    tools = args.get("tools")
    languages = args.get("languages")

    try:
        from orchestrator.graph import run_analysis
        result = run_analysis(
            target_path=path,
            tools=tools,
            languages=languages,
        )
        run_id = result.get("run_id", "unknown")
        _results_store[run_id] = result

        metrics = result.get("metrics", {})
        summary = (
            f"Analysis complete (run_id: {run_id})\n"
            f"Tools run: {metrics.get('tool_count', 0)}\n"
            f"Total findings: {metrics.get('total_findings', 0)}\n"
            f"  Errors: {metrics.get('error_count', 0)}\n"
            f"  Warnings: {metrics.get('warning_count', 0)}\n"
            f"  Notes: {metrics.get('note_count', 0)}\n\n"
            f"Use get_findings(run_id='{run_id}') to query results.\n"
            f"Use get_metrics(run_id='{run_id}') for detailed metrics."
        )
        return [TextContent(type="text", text=summary)]

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return [TextContent(type="text", text=f"Analysis failed: {e}")]


async def _tool_get_findings(args: dict) -> list[TextContent]:
    run_id = args["run_id"]
    result = _results_store.get(run_id)
    if result is None:
        return [TextContent(type="text", text=f"No results for run_id: {run_id}")]

    sarif = result.get("unified_sarif", {})
    severity_filter = args.get("severity")
    file_filter = args.get("file")
    tool_filter = args.get("tool")
    limit = args.get("limit", 50)

    findings = []
    for run in sarif.get("runs", []):
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "")
        if tool_filter and tool_name != tool_filter:
            continue
        for res in run.get("results", []):
            if severity_filter and res.get("level") != severity_filter:
                continue
            file_path = ""
            line = 0
            for loc in res.get("locations", []):
                ph = loc.get("physicalLocation", {})
                file_path = ph.get("artifactLocation", {}).get("uri", "")
                line = ph.get("region", {}).get("startLine", 0)
                break
            if file_filter and file_filter not in file_path:
                continue
            findings.append({
                "tool": tool_name,
                "rule": res.get("ruleId", ""),
                "level": res.get("level", "warning"),
                "file": file_path,
                "line": line,
                "message": res.get("message", {}).get("text", ""),
            })
            if len(findings) >= limit:
                break
        if len(findings) >= limit:
            break

    return [TextContent(type="text", text=json.dumps(findings, indent=2))]


async def _tool_get_metrics(args: dict) -> list[TextContent]:
    run_id = args["run_id"]
    result = _results_store.get(run_id)
    if result is None:
        return [TextContent(type="text", text=f"No results for run_id: {run_id}")]
    return [TextContent(type="text", text=json.dumps(result.get("metrics", {}), indent=2))]


async def _tool_explain_finding(args: dict) -> list[TextContent]:
    run_id = args["run_id"]
    finding_index = args.get("finding_index", 0)
    result = _results_store.get(run_id)
    if result is None:
        return [TextContent(type="text", text=f"No results for run_id: {run_id}")]

    sarif = result.get("unified_sarif", {})
    idx = 0
    for run in sarif.get("runs", []):
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "")
        rules = {r["id"]: r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}
        for res in run.get("results", []):
            if idx == finding_index:
                rule_id = res.get("ruleId", "unknown")
                rule_info = rules.get(rule_id, {})
                explanation = (
                    f"Finding #{finding_index}\n"
                    f"Tool: {tool_name}\n"
                    f"Rule: {rule_id}\n"
                    f"Level: {res.get('level', 'warning')}\n"
                    f"Message: {res.get('message', {}).get('text', '')}\n"
                )
                if rule_info.get("fullDescription", {}).get("text"):
                    explanation += f"\nDescription: {rule_info['fullDescription']['text']}\n"
                if rule_info.get("helpUri"):
                    explanation += f"Reference: {rule_info['helpUri']}\n"
                locs = res.get("locations", [])
                if locs:
                    ph = locs[0].get("physicalLocation", {})
                    explanation += (
                        f"\nLocation: {ph.get('artifactLocation', {}).get('uri', '')}:"
                        f"{ph.get('region', {}).get('startLine', '?')}\n"
                    )
                return [TextContent(type="text", text=explanation)]
            idx += 1

    return [TextContent(type="text", text=f"Finding #{finding_index} not found")]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name="security_audit",
            description="Analyze this codebase for security vulnerabilities",
            arguments=[
                PromptArgument(
                    name="path",
                    description="Path to analyze (defaults to current directory)",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="quality_review",
            description="Review code quality and technical debt",
            arguments=[
                PromptArgument(
                    name="path",
                    description="Path to analyze (defaults to current directory)",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="architecture_map",
            description="Map the architecture of this codebase",
            arguments=[
                PromptArgument(
                    name="path",
                    description="Path to analyze (defaults to current directory)",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="full_analysis",
            description="Run complete analysis with all applicable tools",
            arguments=[
                PromptArgument(
                    name="path",
                    description="Path to analyze (defaults to current directory)",
                    required=False,
                ),
            ],
        ),
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    path = (arguments or {}).get("path") or _get_target_path()

    prompts = {
        "security_audit": (
            f"Run a security audit on the codebase at `{path}`. "
            "Use the analyze_directory tool with security-focused tools "
            "(semgrep, bandit, trivy, trufflehog, detect-secrets). "
            "After analysis, use get_findings to list all error-level findings, "
            "then explain_finding for the most critical ones."
        ),
        "quality_review": (
            f"Review code quality at `{path}`. "
            "Use analyze_directory with quality tools (ruff, eslint, pyright, lizard). "
            "Focus on complexity metrics and code smells. "
            "Summarize findings by severity and suggest improvements."
        ),
        "architecture_map": (
            f"Map the architecture of `{path}`. "
            "Run a full analysis, then examine the topology resource "
            "to understand the dependency structure. "
            "Describe the major modules, their responsibilities, and connections."
        ),
        "full_analysis": (
            f"Run a comprehensive analysis of `{path}`. "
            "Use analyze_directory with all default tools. "
            "Review metrics, findings by severity, and architecture topology. "
            "Provide a complete report with actionable recommendations."
        ),
    }

    text = prompts.get(name, f"Unknown prompt: {name}")
    return GetPromptResult(
        description=f"Prompt: {name}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=text),
            )
        ],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the MCP server over stdio."""
    import asyncio

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info("Starting gororoba MCP server (stdio)")

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
