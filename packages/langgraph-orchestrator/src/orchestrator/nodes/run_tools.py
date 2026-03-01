"""Tool execution node -- runs selected analysis tools in parallel."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from tool_runner.registry import ToolRegistry
from tool_runner.runner import ToolRunner

logger = logging.getLogger(__name__)


async def _run_tools_async(
    selected_tools: list[str],
    target_path: str,
    output_dir: str,
) -> dict:
    """Run tools concurrently and collect results."""
    registry = ToolRegistry()
    runner = ToolRunner()
    tools = []
    for name in selected_tools:
        tool_def = registry.get_by_name(name)
        if tool_def is not None:
            tools.append(tool_def)
        else:
            logger.warning(f"Tool not found in registry: {name}")

    if not tools:
        logger.warning("No tools to run")
        return {}

    results = await runner.run_tools(tools, target_path, output_dir)
    return {r.tool_name: r.__dict__ for r in results}


def run_tools_node(state: dict) -> dict:
    """Execute all selected tools against the target directory.

    Reads: selected_tools, target_path, run_id
    Writes: tool_results, progress
    """
    selected = state.get("selected_tools", [])
    target_path = state["target_path"]
    run_id = state.get("run_id", "default")

    # Store tool output in a per-run directory
    output_dir = os.path.join(
        os.path.expanduser("~"),
        ".adalflow",
        "analysis",
        run_id,
        "tool_output",
    )
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Running {len(selected)} tools against {target_path}")
    tool_results = asyncio.run(_run_tools_async(selected, target_path, output_dir))

    succeeded = sum(1 for r in tool_results.values() if r.get("success"))
    failed = len(tool_results) - succeeded
    logger.info(f"Tool execution complete: {succeeded} succeeded, {failed} failed")

    errors = []
    for name, result in tool_results.items():
        if not result.get("success") and result.get("error"):
            errors.append(f"{name}: {result['error']}")

    return {
        "tool_results": tool_results,
        "errors": state.get("errors", []) + errors,
        "progress": 0.4,
    }
