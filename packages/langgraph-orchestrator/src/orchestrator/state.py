"""Analysis pipeline state schema for LangGraph."""

from __future__ import annotations

from typing import Any, TypedDict


class AnalysisState(TypedDict, total=False):
    """Typed state flowing through the analysis graph.

    Fields are populated progressively as each node executes.
    """

    # Input
    target_path: str
    requested_tools: list[str]       # user-specified subset, or empty for auto
    requested_languages: list[str]   # user-specified, or empty for auto-detect

    # Detection
    detected_languages: list[str]
    detected_frameworks: list[str]

    # Tool selection and execution
    selected_tools: list[str]
    tool_results: dict[str, Any]     # tool_name -> ToolResult dict

    # SARIF pipeline
    sarif_runs: list[dict]           # individual SARIF run dicts
    unified_sarif: dict              # merged + deduplicated SARIF document

    # Agent synthesis
    blueprint_topology: dict         # structural dependency graph
    semantic_summaries: dict         # module-level business logic summaries
    final_documentation: str         # synthesized output

    # Metrics
    metrics: dict                    # aggregate complexity, debt, security counts

    # Bookkeeping
    run_id: str
    errors: list[str]
    progress: float                  # 0.0 to 1.0
