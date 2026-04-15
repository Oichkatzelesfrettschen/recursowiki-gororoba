"""Async subprocess execution for analysis tools with timeout and capture."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import signal
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

        # Some tools (e.g. checkov) write output to a directory rather than a
        # single file.  Provide both {output} and {output_dir} as template
        # variables; tools that need a directory use {output_dir}.
        tool_output_dir = str(output_path / f"{tool.name}_out")
        os.makedirs(tool_output_dir, exist_ok=True)

        command_str = tool.command_template.format(
            target=target_path,
            output=output_file,
            output_dir=tool_output_dir,
        )

        # For pip-installable tools, wrap with `uv run --with` to guarantee
        # the correct package (including extras like bandit[sarif]) is
        # available in an ephemeral environment.
        command_str = self._maybe_wrap_with_uv(tool, command_str)

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
                        start_new_session=True,
                    )
                else:
                    parts = command_str.split()
                    proc = await asyncio.create_subprocess_exec(
                        *parts,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        start_new_session=True,
                    )

                try:
                    raw_stdout, raw_stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=tool.timeout,
                    )
                except asyncio.TimeoutError:
                    await self._kill_process_group(proc)
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

        # Some tools (checkov) write to a directory with a fixed filename
        # like results_sarif.sarif.  Detect and relocate to {output_file}.
        if not sarif_produced:
            sarif_produced = self._collect_dir_output(
                tool_output_dir, output_file,
            )

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

    @staticmethod
    async def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
        """Kill the entire process group rooted at *proc*.

        Sends SIGTERM first for graceful shutdown, then SIGKILL after 5s
        if the group is still alive.  Using process groups (via
        start_new_session=True) ensures grandchild processes spawned by
        tools like checkov or trufflehog are also terminated.
        """
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return
        # Give the group a moment to exit cleanly before escalating.
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(proc.pid, signal.SIGKILL)

    @staticmethod
    def _collect_dir_output(tool_output_dir: str, output_file: str) -> bool:
        """Check *tool_output_dir* for SARIF/JSON files and move the first
        match to *output_file*.

        Returns ``True`` if a file was found and relocated.
        """
        dir_path = Path(tool_output_dir)
        if not dir_path.is_dir():
            return False

        # Look for common output file names written by tools that take a
        # directory argument (e.g. checkov writes results_sarif.sarif).
        for candidate in sorted(dir_path.iterdir()):
            if candidate.is_file() and candidate.suffix in (".sarif", ".json"):
                shutil.move(str(candidate), output_file)
                logger.info(
                    "Relocated %s -> %s", candidate.name, output_file,
                )
                return True
        return False

    @staticmethod
    def _maybe_wrap_with_uv(tool: ToolDefinition, command_str: str) -> str:
        """Wrap pip-installable tool commands with ``uv run --with`` when
        the install package includes extras (e.g. ``bandit[sarif]``) or
        the tool binary is not found on PATH.

        This ensures tools run in an ephemeral uv environment with the
        correct dependencies, without polluting the system.
        """
        if tool.install_method != "pip":
            return command_str

        # Skip wrapping if uv itself is not available.
        if shutil.which("uv") is None:
            return command_str

        # Determine the binary name (first token of the command).
        binary = command_str.split()[0] if command_str else ""

        has_extras = "[" in tool.install_package
        binary_missing = binary and shutil.which(binary) is None

        if has_extras or binary_missing:
            # Shell redirects (>) require shell mode, so we must preserve the
            # full command string rather than splitting it.
            return f"uv run --with {tool.install_package} -- {command_str}"

        return command_str

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
