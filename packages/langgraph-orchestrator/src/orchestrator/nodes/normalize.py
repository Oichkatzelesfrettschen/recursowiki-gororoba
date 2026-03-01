"""SARIF normalization node -- convert raw tool output to SARIF."""

from __future__ import annotations

import json
import logging
import os

from tool_runner.registry import ToolRegistry
from sarif_normalizer.converters.passthrough import PassthroughConverter

logger = logging.getLogger(__name__)


def normalize_node(state: dict) -> dict:
    """Convert each tool's raw output into a SARIF run dict.

    Reads: tool_results, target_path
    Writes: sarif_runs, progress
    """
    tool_results = state.get("tool_results", {})
    target_path = state["target_path"]
    registry = ToolRegistry()
    passthrough = PassthroughConverter()

    sarif_runs: list[dict] = []

    for tool_name, result in tool_results.items():
        if not result.get("success"):
            logger.info(f"Skipping failed tool: {tool_name}")
            continue

        sarif_path = result.get("sarif_path")
        if not sarif_path or not os.path.isfile(sarif_path):
            logger.info(f"No SARIF output for {tool_name}")
            continue

        tool_def = registry.get_by_name(tool_name)

        try:
            with open(sarif_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            if tool_def and tool_def.sarif_native:
                sarif_doc = passthrough.convert(raw_content, target_path)
            else:
                # Try to load the converter for this tool
                converter = _get_converter(tool_name)
                if converter is not None:
                    sarif_doc = converter.convert(raw_content, target_path)
                else:
                    # Fall back to treating it as SARIF anyway (best-effort)
                    sarif_doc = passthrough.convert(raw_content, target_path)

            # Extract runs from the converted document
            for run in sarif_doc.get("runs", []):
                sarif_runs.append(run)

        except Exception as e:
            logger.error(f"Failed to normalize {tool_name} output: {e}")

    logger.info(f"Normalized {len(sarif_runs)} SARIF runs from {len(tool_results)} tools")
    return {
        "sarif_runs": sarif_runs,
        "progress": 0.6,
    }


def _get_converter(tool_name: str):
    """Dynamically load a converter for a non-native-SARIF tool."""
    converter_map = {
        "pyright": "sarif_normalizer.converters.pyright",
        "lizard": "sarif_normalizer.converters.lizard",
        "trufflehog": "sarif_normalizer.converters.trufflehog",
        "detect-secrets": "sarif_normalizer.converters.detect_secrets",
        "phpcs": "sarif_normalizer.converters.phpcs",
        "deptrac": "sarif_normalizer.converters.deptrac",
        "horusec": "sarif_normalizer.converters.horusec",
    }
    module_path = converter_map.get(tool_name)
    if module_path is None:
        return None
    try:
        import importlib
        mod = importlib.import_module(module_path)
        # Convention: each module has a class named <Tool>Converter
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                isinstance(attr, type)
                and hasattr(attr, "convert")
                and attr_name != "BaseConverter"
            ):
                return attr()
        return None
    except ImportError as e:
        logger.warning(f"Could not import converter for {tool_name}: {e}")
        return None
