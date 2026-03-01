"""Abstract base class for all SARIF converters."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from sarif_normalizer.schema import SARIF_SCHEMA_URI, SARIF_VERSION

logger = logging.getLogger(__name__)


class BaseConverter(ABC):
    """Base class that every tool-specific converter must inherit from.

    Subclasses MUST set ``tool_name`` and implement :meth:`convert`.
    """

    tool_name: str = ""

    @abstractmethod
    def convert(self, raw_output: str, target_path: str = ".") -> dict[str, Any]:
        """Convert raw tool output into a SARIF v2.1.0 dict.

        Parameters
        ----------
        raw_output:
            The complete text output from the analysis tool (JSON, CSV,
            XML, or plain text depending on the tool).
        target_path:
            Root path of the analysed project, used to resolve relative
            file references inside the tool output.

        Returns
        -------
        dict
            A valid SARIF v2.1.0 log object.
        """
        ...  # pragma: no cover

    def validate_sarif(self, sarif_doc: dict[str, Any]) -> bool:
        """Perform basic structural validation of a SARIF document.

        This is a lightweight check -- it does NOT run full JSON-schema
        validation, but it catches the most common structural problems.

        Returns
        -------
        bool
            ``True`` when the document passes all checks.
        """
        if not isinstance(sarif_doc, dict):
            logger.error("SARIF document must be a dict, got %s", type(sarif_doc).__name__)
            return False

        if sarif_doc.get("version") != SARIF_VERSION:
            logger.error(
                "Expected SARIF version %s, got %r",
                SARIF_VERSION,
                sarif_doc.get("version"),
            )
            return False

        schema = sarif_doc.get("$schema", "")
        if schema and schema != SARIF_SCHEMA_URI:
            logger.warning("Unexpected $schema URI: %s", schema)

        runs = sarif_doc.get("runs")
        if not isinstance(runs, list) or len(runs) == 0:
            logger.error("SARIF document must contain at least one run")
            return False

        for idx, run in enumerate(runs):
            if not isinstance(run, dict):
                logger.error("Run #%d is not a dict", idx)
                return False
            tool = run.get("tool")
            if not isinstance(tool, dict):
                logger.error("Run #%d is missing 'tool' object", idx)
                return False
            driver = tool.get("driver")
            if not isinstance(driver, dict):
                logger.error("Run #%d is missing 'tool.driver' object", idx)
                return False
            if "name" not in driver:
                logger.error("Run #%d driver is missing 'name'", idx)
                return False
            results = run.get("results")
            if results is not None and not isinstance(results, list):
                logger.error("Run #%d 'results' must be a list or absent", idx)
                return False

        return True
