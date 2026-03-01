"""On-demand tool availability checking and install-command generation."""

from __future__ import annotations

import asyncio
import logging
import shutil

from tool_runner.registry import ToolDefinition

logger = logging.getLogger(__name__)

# Map from install_method to a callable that builds the install command string.
_INSTALL_BUILDERS: dict[str, object] = {}  # populated at module level below


def _pip_install_cmd(tool: ToolDefinition) -> str:
    return f"uv run --with {tool.install_package} -- {tool.name} --version"


def _npm_install_cmd(tool: ToolDefinition) -> str:
    return f"npx {tool.install_package}"


def _go_install_cmd(tool: ToolDefinition) -> str:
    return f"go install {tool.install_package}"


def _binary_install_cmd(tool: ToolDefinition) -> str:
    return (
        f"# {tool.name}: manual install required -- "
        f"download from the official release page"
    )


def _gem_install_cmd(tool: ToolDefinition) -> str:
    return f"gem install {tool.install_package}"


def _composer_install_cmd(tool: ToolDefinition) -> str:
    return f"composer global require {tool.install_package}"


_INSTALL_BUILDERS = {
    "pip": _pip_install_cmd,
    "npm": _npm_install_cmd,
    "go": _go_install_cmd,
    "binary": _binary_install_cmd,
    "gem": _gem_install_cmd,
    "composer": _composer_install_cmd,
}

# Some tools have a binary name that differs from their registry name.
_BINARY_NAME_OVERRIDES: dict[str, str] = {
    "dependency-check": "dependency-check.sh",
    "clang-analyzer": "scan-build",
    "pmd-cpd": "pmd",
    "phpcs": "phpcs",
}

# Preferred flag used to test that the binary is functional.
# Most CLIs support ``--version``; a few only support ``--help``.
_VERSION_FLAG: dict[str, str] = {
    "horusec": "version",
    "kics": "version",
    "trufflehog": "--version",
}


class ToolInstaller:
    """Check tool availability and provide install instructions."""

    # -- public API -----------------------------------------------------------

    async def check_available(self, tool: ToolDefinition) -> bool:
        """Return ``True`` if the tool binary is found on ``PATH`` and
        responds to a basic invocation (``--version`` or equivalent).

        This intentionally does **not** install anything; it only probes.
        """
        binary = _BINARY_NAME_OVERRIDES.get(tool.name, tool.name)

        # Fast path: if shutil cannot find it, skip subprocess entirely.
        if shutil.which(binary) is None:
            logger.debug("%s: binary %r not found on PATH", tool.name, binary)
            return False

        flag = _VERSION_FLAG.get(tool.name, "--version")
        try:
            proc = await asyncio.create_subprocess_exec(
                binary,
                flag,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=15)
            available = proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError, OSError):
            available = False

        logger.debug(
            "%s: available=%s (binary=%r, flag=%r)",
            tool.name,
            available,
            binary,
            flag,
        )
        return available

    def get_install_command(self, tool: ToolDefinition) -> str:
        """Return a human-readable install command for *tool*.

        The returned string is suitable for display or direct execution in
        a shell.  For ``binary`` install methods the string is a comment
        explaining that manual installation is needed.
        """
        builder = _INSTALL_BUILDERS.get(tool.install_method)
        if builder is None:
            return (
                f"# {tool.name}: unknown install method "
                f"{tool.install_method!r}"
            )
        # All builders share the same (ToolDefinition) -> str signature.
        return builder(tool)  # type: ignore[operator]
