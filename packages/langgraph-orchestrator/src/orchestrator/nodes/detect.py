"""Language and framework detection node."""

from __future__ import annotations

import logging

from tool_runner.detector import LanguageDetector
from orchestrator.edges import select_tools_for_languages

logger = logging.getLogger(__name__)


def detect_node(state: dict) -> dict:
    """Detect languages/frameworks in the target and select tools.

    Reads: target_path, requested_tools, requested_languages
    Writes: detected_languages, detected_frameworks, selected_tools, progress
    """
    target_path = state["target_path"]
    logger.info(f"Detecting languages in {target_path}")

    detector = LanguageDetector()
    detected = detector.detect(target_path)

    # Use user-requested languages if provided, otherwise auto-detected
    languages = state.get("requested_languages") or detected
    state_updates: dict = {
        "detected_languages": detected,
        "detected_frameworks": detector.detect_frameworks(target_path),
        "progress": 0.1,
    }

    # Select tools: user-requested subset, or auto from languages
    requested = state.get("requested_tools")
    if requested:
        state_updates["selected_tools"] = requested
    else:
        state_updates["selected_tools"] = select_tools_for_languages(languages)

    logger.info(
        f"Detected languages={detected}, selected tools={state_updates['selected_tools']}"
    )
    return state_updates
