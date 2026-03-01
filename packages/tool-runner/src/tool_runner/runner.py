"""Async subprocess execution for analysis tools with timeout and capture."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from tool_runner.registry import ToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Outcome of a single tool execution."""

    tool_name: str
    success: bool
    sarif_path: str | None  # Path to SARIF output file if produced
    stdout: str
    stderr: str
    return_code: int
    duration_seconds: float
    error: str | None = None


class ToolRunner:
    """Execute analysis tools as async subprocesses."""

    def __init__(self, *, concurrency: int = 4) -> None:
        self._semaphore = asyncio.Semaphore(concurrency)

    # -- public API -----------------------------------------------------------

    async def run_tool(
        self,
        tool: ToolDefinition,
        target_path: str,
        output_dir: str,
    ) -> ToolResult:
        """Run a single tool against *target_path*, writing output to *output_dir*.

        The SARIF (or native) output file is placed at
        ``<output_dir>/<tool.name>.sarif`` (or ``.json`` / ``.xml`` for
        non-SARIF tools).
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        extension = ".sarif" if tool.sarif_native else ".json"
        output_file = str(output_path / f"{tool.name}{extension}")

        command_str = tool.command_template.format(
            target=target_path,
            output=output_file,
        )

        logger.info("Running %s: %s", tool.name, command_str)

        # Check for required API key before executing.
        if tool.requires_api_key and tool.env_var_key:
            if not os.environ.get(tool.env_var_key):
                msg = (
                    f"Required environment variable {tool.env_var_key} "
                    f"is not set for {tool.name}"
                )
                logger.warning(msg)
                return ToolResult(
                    tool_name=tool.name,
                    success=False,
                    sarif_path=None,
                    stdout="",
                    stderr="",
                    return_code=-1,
                    duration_seconds=0.0,
                    error=msg,
                )

        # Decide whether to use shell mode.  Templates that contain shell
        # redirects (``>``) or pipes (``|``) must be run through the shell.
        use_shell = ">" in command_str or "|" in command_str

        start = time.monotonic()

        try:
            async with self._semaphore:
                if use_shell:
                    proc = await asyncio.create_subprocess_shell(
                        command_str,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                else:
                    parts = command_str.split()
                    proc = await asyncio.create_subprocess_exec(
                        *parts,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                try:
                    raw_stdout, raw_stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=tool.timeout,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    elapsed = time.monotonic() - start
                    msg = (
                        f"{tool.name} timed out after {tool.timeout}s"
                    )
                    logger.error(msg)
                    return ToolResult(
                        tool_name=tool.name,
                        success=False,
                        sarif_path=None,
                        stdout="",
                        stderr="",
                        return_code=-1,
                        duration_seconds=elapsed,
                        error=msg,
                    )

        except FileNotFoundError as exc:
            elapsed = time.monotonic() - start
            msg = f"{tool.name} binary not found: {exc}"
            logger.error(msg)
            return ToolResult(
                tool_name=tool.name,
                success=False,
                sarif_path=None,
                stdout="",
                stderr="",
                return_code=-1,
                duration_seconds=elapsed,
                error=msg,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            msg = f"{tool.name} failed to start: {exc}"
            logger.error(msg)
            return ToolResult(
                tool_name=tool.name,
                success=False,
                sarif_path=None,
                stdout="",
                stderr="",
                return_code=-1,
                duration_seconds=elapsed,
                error=msg,
            )

        elapsed = time.monotonic() - start

        stdout_text = raw_stdout.decode("utf-8", errors="replace")
        stderr_text = raw_stderr.decode("utf-8", errors="replace")
        return_code = proc.returncode if proc.returncode is not None else -1

        # Many analysis tools use non-zero exit codes to signal "findings
        # detected" (e.g. bandit returns 1 when issues are found).  We
        # consider the run successful if the output file was actually written.
        sarif_produced = Path(output_file).is_file()
        success = sarif_produced or return_code == 0

        logger.info(
            "%s finished in %.1fs (rc=%d, output=%s)",
            tool.name,
            elapsed,
            return_code,
            "yes" if sarif_produced else "no",
        )

        return ToolResult(
            tool_name=tool.name,
            success=success,
            sarif_path=output_file if sarif_produced else None,
            stdout=stdout_text,
            stderr=stderr_text,
            return_code=return_code,
            duration_seconds=elapsed,
        )

    async def run_tools(
        self,
        tools: list[ToolDefinition],
        target_path: str,
        output_dir: str,
    ) -> list[ToolResult]:
        """Run multiple tools in parallel, returning results in the same order."""
        tasks = [
            self.run_tool(tool, target_path, output_dir)
            for tool in tools
        ]
        results: list[ToolResult] = await asyncio.gather(*tasks)
        return results
