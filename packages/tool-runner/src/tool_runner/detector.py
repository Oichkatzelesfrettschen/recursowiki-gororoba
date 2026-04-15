"""Language and framework detection from file extensions and marker files."""

from __future__ import annotations

import logging
from pathlib import Path

import pathspec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extension -> language mapping
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyx": "python",
    # JavaScript / TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    # Java / JVM
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # C / C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    # Ruby
    ".rb": "ruby",
    ".erb": "ruby",
    # PHP
    ".php": "php",
    # C#
    ".cs": "csharp",
    # Swift
    ".swift": "swift",
    # Solidity
    ".sol": "solidity",
    # LaTeX
    ".tex": "latex",
    ".sty": "latex",
    ".cls": "latex",
    ".bib": "latex",
    # Infrastructure / Config
    ".tf": "terraform",
    ".hcl": "terraform",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    # Shell
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
}

# File names (without path) that indicate a language context.
_FILENAME_MAP: dict[str, str] = {
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
    "Containerfile": "docker",
    "Makefile": "make",
    "CMakeLists.txt": "cpp",
    ".bashrc": "shell",
    ".zshrc": "shell",
    ".profile": "shell",
    ".bash_profile": "shell",
}

# ---------------------------------------------------------------------------
# Framework marker files -> language (for cases where extensions alone
# may not be present or sufficient, e.g. a repo root).
# ---------------------------------------------------------------------------

_FRAMEWORK_MARKERS: dict[str, str] = {
    "package.json": "javascript",
    "package-lock.json": "javascript",
    "yarn.lock": "javascript",
    "pnpm-lock.yaml": "javascript",
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "Pipfile": "python",
    "poetry.lock": "python",
    "go.mod": "go",
    "go.sum": "go",
    "Cargo.toml": "rust",
    "Cargo.lock": "rust",
    "Gemfile": "ruby",
    "Gemfile.lock": "ruby",
    "composer.json": "php",
    "composer.lock": "php",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
    "settings.gradle": "java",
    "settings.gradle.kts": "java",
    "tsconfig.json": "typescript",
    "hardhat.config.js": "solidity",
    "hardhat.config.ts": "solidity",
    "foundry.toml": "solidity",
    "brownie-config.yaml": "solidity",
}

# Maximum number of files to scan before returning early.
# Prevents excessively long walks in huge repositories.
_MAX_FILES_SCANNED = 50_000


def _load_gitignore_spec(target: Path) -> pathspec.PathSpec | None:
    """Load a .gitignore file from *target* (if it exists) and compile it."""
    gitignore = target / ".gitignore"
    if not gitignore.is_file():
        return None
    try:
        patterns = gitignore.read_text(encoding="utf-8", errors="replace")
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns.splitlines())
    except Exception:
        logger.debug("Failed to parse .gitignore at %s", gitignore)
        return None


class LanguageDetector:
    """Detect languages and frameworks present under a directory tree."""

    def detect(self, target_path: str) -> list[str]:
        """Scan *target_path* for source files and return detected languages.

        The returned list is sorted alphabetically and contains no duplicates.
        """
        root = Path(target_path).resolve()
        if not root.is_dir():
            logger.warning("Target path is not a directory: %s", root)
            return []

        languages: set[str] = set()

        # -- 1. Check framework marker files at the root level. ---------------
        for marker, lang in _FRAMEWORK_MARKERS.items():
            if (root / marker).exists():
                languages.add(lang)
                logger.debug("Marker %s -> %s", marker, lang)

        # -- 2. Walk the tree and inspect extensions. -------------------------
        ignore_spec = _load_gitignore_spec(root)
        files_scanned = 0

        # Directories to always skip (irrespective of .gitignore).
        _SKIP_DIRS = {
            ".git",
            "node_modules",
            "__pycache__",
            ".tox",
            ".mypy_cache",
            ".ruff_cache",
            "venv",
            ".venv",
            "vendor",
            "dist",
            "build",
            ".next",
            ".nuxt",
        }

        for item in root.rglob("*"):
            if files_scanned >= _MAX_FILES_SCANNED:
                logger.info(
                    "Reached file-scan limit (%d); stopping early.",
                    _MAX_FILES_SCANNED,
                )
                break

            # Skip ignored directories early.
            parts = item.relative_to(root).parts
            if _SKIP_DIRS & set(parts):
                continue

            if not item.is_file():
                continue

            files_scanned += 1

            # Optionally honour .gitignore patterns.
            if ignore_spec is not None:
                rel = str(item.relative_to(root))
                if ignore_spec.match_file(rel):
                    continue

            # Check exact file name first (e.g. Dockerfile).
            lang = _FILENAME_MAP.get(item.name)
            if lang:
                languages.add(lang)
                continue

            # Then check suffix.
            suffix = item.suffix.lower()
            lang = _EXTENSION_MAP.get(suffix)
            if lang:
                languages.add(lang)

        logger.info(
            "Detected languages in %s: %s (scanned %d files)",
            root,
            sorted(languages),
            files_scanned,
        )

        return sorted(languages)

    def detect_frameworks(self, target_path: str) -> list[str]:
        """Return a list of framework/build-system marker names found at the root.

        Unlike ``detect`` which returns language names, this returns the marker
        file names themselves (e.g. ``["package.json", "pyproject.toml"]``).
        """
        root = Path(target_path).resolve()
        if not root.is_dir():
            return []
        found: list[str] = []
        for marker in _FRAMEWORK_MARKERS:
            if (root / marker).exists():
                found.append(marker)
        return sorted(found)
