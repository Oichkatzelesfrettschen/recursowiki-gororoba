"""Download-and-install provisioner for binary analysis tools.

Reads tools.toml, checks PATH, and downloads/installs missing binaries.
Existing installer.py is left untouched for backward compatibility.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

def _find_tools_toml() -> Path:
    """Walk from CWD upward to find tools.toml, fall back to package-relative."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "tools.toml"
        if candidate.exists():
            return candidate
    # Fallback: relative to this file (works inside Docker /app)
    return Path(__file__).resolve().parents[5] / "tools.toml"


_ROOT_TOML = _find_tools_toml()
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"


def _bin_dir() -> Path:
    d = Path(os.environ.get("GOROROBA_TOOL_BIN", str(_DEFAULT_BIN_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_manifest(path: Path | None = None) -> dict:
    p = path or _ROOT_TOML
    if not p.exists():
        logger.warning("tools.toml not found at %s", p)
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f)


class ToolProvisioner:
    """Provision binary tools declared in tools.toml."""

    def __init__(self, manifest_path: Path | None = None) -> None:
        self._manifest = _load_manifest(manifest_path)
        self._bin_dir = _bin_dir()
        self._tools: dict = self._manifest.get("tools", {})

    # -- public API -----------------------------------------------------------

    async def provision_all(
        self,
        tool_names: list[str] | None = None,
    ) -> dict[str, bool]:
        """Provision all (or selected) tools. Returns {name: installed}."""
        names = tool_names or list(self._tools.keys())
        tasks = [self._provision_one(n) for n in names if n in self._tools]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: dict[str, bool] = {}
        for name, result in zip(
            [n for n in names if n in self._tools], results
        ):
            if isinstance(result, Exception):
                logger.error("Failed to provision %s: %s", name, result)
                out[name] = False
            else:
                out[name] = result
        return out

    async def check_available(self, name: str) -> bool:
        """Return True if the binary for *name* is on PATH."""
        spec = self._tools.get(name)
        if spec is None:
            return False
        binary = spec.get("binary", name)
        return shutil.which(binary) is not None

    # -- internals ------------------------------------------------------------

    async def _provision_one(self, name: str) -> bool:
        spec = self._tools[name]
        binary = spec.get("binary", name)

        if shutil.which(binary) is not None:
            logger.info("%s: already available", name)
            return True

        method = spec.get("method", "binary")
        if method == "binary":
            return await self._install_binary(name, spec)
        elif method == "script":
            return await self._install_script(name, spec)
        elif method == "apt":
            return await self._install_apt(name, spec)
        elif method == "docker-copy":
            # docker-copy tools are baked into the Docker image at build time.
            # Outside Docker, we cannot provision them automatically.
            logger.warning(
                "%s: docker-copy method -- only available in Docker image",
                name,
            )
            return False
        else:
            logger.warning("%s: unknown method %r", name, method)
            return False

    async def _install_binary(self, name: str, spec: dict) -> bool:
        url_template = spec.get("url", "")
        version = spec.get("version", "latest")
        binary = spec.get("binary", name)
        url = url_template.replace("{version}", version)

        # Install apt prereqs (e.g. JRE for PMD)
        requires_apt = spec.get("requires_apt", [])
        if requires_apt:
            await self._apt_install(requires_apt)

        logger.info("%s: downloading from %s", name, url)

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "archive"
            extract_dir = Path(tmp) / "extract"
            extract_dir.mkdir()

            proc = await asyncio.create_subprocess_exec(
                "curl", "-fsSL", "-o", str(archive_path), url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(
                    "%s: download failed: %s", name, stderr.decode().strip()
                )
                return False

            # Extract based on file extension
            if url.endswith(".tar.gz") or url.endswith(".tgz"):
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(extract_dir)
            elif url.endswith(".zip"):
                with zipfile.ZipFile(archive_path) as zf:
                    zf.extractall(extract_dir)
            else:
                logger.error("%s: unsupported archive format: %s", name, url)
                return False

            # Find the binary in extracted contents
            found = self._find_binary(extract_dir, binary)
            if found is None:
                logger.error(
                    "%s: binary %r not found in archive", name, binary
                )
                return False

            dest = self._bin_dir / binary
            shutil.copy2(found, dest)
            dest.chmod(0o755)
            logger.info("%s: installed to %s", name, dest)

        return shutil.which(binary) is not None or (self._bin_dir / binary).exists()

    async def _install_script(self, name: str, spec: dict) -> bool:
        script = spec.get("script", "")
        if not script:
            logger.error("%s: no install script defined", name)
            return False

        logger.info("%s: running install script", name)
        proc = await asyncio.create_subprocess_shell(
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "HORUSEC_CLI_PATH": str(self._bin_dir)},
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(
                "%s: script failed (rc=%d): %s",
                name, proc.returncode, stderr.decode().strip(),
            )
            return False

        binary = spec.get("binary", name)
        # The script may install to /usr/local/bin; copy to our bin dir
        system_path = shutil.which(binary)
        if system_path and Path(system_path) != self._bin_dir / binary:
            dest = self._bin_dir / binary
            shutil.copy2(system_path, dest)
            dest.chmod(0o755)

        logger.info("%s: installed via script", name)
        return True

    async def _install_apt(self, name: str, spec: dict) -> bool:
        package = spec.get("package", name)
        binary = spec.get("binary", name)

        if shutil.which(binary) is not None:
            return True

        logger.info("%s: installing via apt-get (%s)", name, package)
        return await self._apt_install([package])

    async def _apt_install(self, packages: list[str]) -> bool:
        cmd = ["apt-get", "update", "-qq"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        cmd = [
            "apt-get", "install", "-y", "-qq", "--no-install-recommends",
            *packages,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(
                "apt-get install %s failed: %s",
                " ".join(packages), stderr.decode().strip(),
            )
            return False
        return True

    @staticmethod
    def _find_binary(root: Path, name: str) -> Path | None:
        """Walk extracted directory to find the named binary."""
        for path in root.rglob(name):
            if path.is_file():
                return path
        # Some archives put the binary inside a subdirectory
        for path in root.rglob("*"):
            if path.is_file() and path.name == name:
                return path
        return None
