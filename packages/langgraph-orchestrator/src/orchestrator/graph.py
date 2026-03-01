"""LangGraph StateGraph definition for the analysis pipeline."""

from __future__ import annotations

import logging
import uuid

from langgraph.graph import StateGraph, END

from orchestrator.state import AnalysisState
from orchestrator.nodes.detect import detect_node
from orchestrator.nodes.run_tools import run_tools_node
from orchestrator.nodes.normalize import normalize_node
from orchestrator.nodes.merge import merge_node
from orchestrator.nodes.blueprint import blueprint_node
from orchestrator.nodes.semantic import semantic_node
from orchestrator.nodes.synthesis import synthesis_node
from orchestrator.edges import should_run_agents

logger = logging.getLogger(__name__)


def build_analysis_graph() -> StateGraph:
    """Construct the full analysis pipeline as a LangGraph StateGraph.

    Graph flow:
        detect -> run_tools -> normalize -> merge -> route ->
            [agents: blueprint + semantic -> synthesis] | [end]
    """
    graph = StateGraph(AnalysisState)

    # Add nodes
    graph.add_node("detect", detect_node)
    graph.add_node("run_tools", run_tools_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("merge", merge_node)
    graph.add_node("blueprint", blueprint_node)
    graph.add_node("semantic", semantic_node)
    graph.add_node("synthesis", synthesis_node)

    # Linear pipeline: detect -> run_tools -> normalize -> merge
    graph.set_entry_point("detect")
    graph.add_edge("detect", "run_tools")
    graph.add_edge("run_tools", "normalize")
    graph.add_edge("normalize", "merge")

    # Conditional: after merge, either run agents or go directly to END
    graph.add_conditional_edges(
        "merge",
        should_run_agents,
        {
            "agents": "blueprint",
            "end": END,
        },
    )

    # Agent synthesis: blueprint and semantic run, then synthesis
    # Note: LangGraph does not support fan-out from a single node to two
    # parallel nodes in the basic StateGraph. We chain them sequentially.
    graph.add_edge("blueprint", "semantic")
    graph.add_edge("semantic", "synthesis")
    graph.add_edge("synthesis", END)

    return graph


def run_analysis(
    target_path: str,
    tools: list[str] | None = None,
    languages: list[str] | None = None,
    run_id: str | None = None,
) -> AnalysisState:
    """Run the full analysis pipeline synchronously.

    Args:
        target_path: Absolute path to the directory to analyze.
        tools: Optional list of tool names to restrict execution to.
        languages: Optional list of languages to restrict detection to.
        run_id: Optional run identifier; generated if not provided.

    Returns:
        The final AnalysisState with all fields populated.
    """
    if run_id is None:
        run_id = uuid.uuid4().hex[:12]

    graph = build_analysis_graph()
    app = graph.compile()

    initial_state: AnalysisState = {
        "target_path": target_path,
        "requested_tools": tools or [],
        "requested_languages": languages or [],
        "run_id": run_id,
        "errors": [],
        "progress": 0.0,
    }

    logger.info(f"Starting analysis run {run_id} for {target_path}")
    result = app.invoke(initial_state)
    logger.info(f"Analysis run {run_id} complete")
    return result
