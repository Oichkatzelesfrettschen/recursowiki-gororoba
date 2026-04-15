"""Tool definitions and registry for 32 static analysis tools."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable descriptor for a single analysis tool."""

    name: str
    category: str  # "security", "quality", "complexity", "secrets"
    install_method: str  # "pip", "npm", "go", "binary", "gem", "composer"
    install_package: str  # e.g. "bandit[sarif]"
    command_template: str  # e.g. "bandit -r {target} -f sarif -o {output}"
    sarif_native: bool  # True if tool outputs SARIF directly
    languages: list[str] = field(default_factory=list)  # ["python"] or ["*"]
    optional: bool = False  # True for conditional tools
    requires_api_key: bool = False  # True for ggshield
    env_var_key: str | None = None  # Environment variable for API key
    timeout: int = 300  # Per-tool timeout in seconds


# ---------------------------------------------------------------------------
# 23 tool definitions grouped by category
# ---------------------------------------------------------------------------

_SECURITY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="semgrep",
        category="security",
        install_method="pip",
        install_package="semgrep",
        command_template="semgrep scan --config auto --sarif --output {output} {target}",
        sarif_native=True,
        languages=["*"],
        timeout=600,
    ),
    ToolDefinition(
        name="bandit",
        category="security",
        install_method="pip",
        install_package="bandit[sarif]",
        command_template="bandit -r {target} -f sarif -o {output}",
        sarif_native=True,
        languages=["python"],
        timeout=600,
    ),
    ToolDefinition(
        name="gosec",
        category="security",
        install_method="go",
        install_package="github.com/securego/gosec/v2/cmd/gosec@latest",
        command_template="gosec -fmt=sarif -out={output} {target}/...",
        sarif_native=True,
        languages=["go"],
    ),
    ToolDefinition(
        name="trivy",
        category="security",
        install_method="binary",
        install_package="trivy",
        command_template="trivy fs --format sarif --output {output} {target}",
        sarif_native=True,
        languages=["*"],
        timeout=600,
    ),
    ToolDefinition(
        name="dependency-check",
        category="security",
        install_method="binary",
        install_package="dependency-check",
        command_template=(
            "dependency-check --scan {target} --format SARIF --out {output} "
            "--disableAssembly"
        ),
        sarif_native=True,
        languages=["java", "javascript", "python", "ruby", "php"],
        optional=True,
        timeout=900,
    ),
    ToolDefinition(
        name="brakeman",
        category="security",
        install_method="gem",
        install_package="brakeman",
        command_template="brakeman -p {target} -f sarif -o {output}",
        sarif_native=True,
        languages=["ruby"],
        optional=True,
    ),
    ToolDefinition(
        name="phpcs",
        category="security",
        install_method="composer",
        install_package="squizlabs/php_codesniffer",
        command_template=(
            "phpcs --standard=PSR12 --report=json --report-file={output} {target}"
        ),
        sarif_native=False,
        languages=["php"],
        optional=True,
    ),
    ToolDefinition(
        name="horusec",
        category="security",
        install_method="binary",
        install_package="horusec",
        command_template=(
            "horusec start -p {target} -o json -O {output} --disable-docker"
        ),
        sarif_native=False,
        languages=["*"],
        timeout=900,
    ),
    # -- Rust security -------------------------------------------------------
    ToolDefinition(
        name="cargo-audit",
        category="security",
        install_method="binary",
        install_package="cargo-audit",
        command_template="cargo audit --file {target}/Cargo.lock --json > {output}",
        sarif_native=False,
        languages=["rust"],
        timeout=120,
    ),
    ToolDefinition(
        name="cargo-deny",
        category="security",
        install_method="binary",
        install_package="cargo-deny",
        command_template="cargo deny --manifest-path {target}/Cargo.toml check --format json 2> {output}",
        sarif_native=False,
        languages=["rust"],
        timeout=300,
    ),
]

_QUALITY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="ruff",
        category="quality",
        install_method="pip",
        install_package="ruff",
        command_template="ruff check {target} --output-format sarif -o {output}",
        sarif_native=True,
        languages=["python"],
    ),
    ToolDefinition(
        name="eslint",
        category="quality",
        install_method="npm",
        install_package="eslint",
        command_template=(
            "eslint {target} -f @microsoft/eslint-formatter-sarif -o {output}"
        ),
        sarif_native=True,
        languages=["javascript", "typescript"],
    ),
    ToolDefinition(
        name="pyright",
        category="quality",
        install_method="npm",
        install_package="pyright",
        command_template="pyright {target} --outputjson > {output}",
        sarif_native=False,
        languages=["python"],
    ),
    ToolDefinition(
        name="cppcheck",
        category="quality",
        install_method="binary",
        install_package="cppcheck",
        command_template="cppcheck --enable=all --output-format=sarif --output-file={output} {target}",
        sarif_native=True,
        languages=["c", "cpp"],
        timeout=900,
    ),
    ToolDefinition(
        name="clang-analyzer",
        category="quality",
        install_method="binary",
        install_package="clang",
        command_template=(
            "scan-build -o {output} --use-analyzer=/usr/bin/clang "
            "-plist-html {target}"
        ),
        sarif_native=False,
        languages=["c", "cpp"],
        optional=True,
    ),
    ToolDefinition(
        name="pmd",
        category="quality",
        install_method="binary",
        install_package="pmd",
        command_template=(
            "pmd check -d {target} -R rulesets/java/quickstart.xml "
            "-f sarif -r {output}"
        ),
        sarif_native=True,
        languages=["java"],
        optional=True,
    ),
    # -- Rust quality --------------------------------------------------------
    ToolDefinition(
        name="clippy",
        category="quality",
        install_method="binary",
        install_package="clippy",
        command_template=(
            "cargo clippy --manifest-path {target}/Cargo.toml"
            " --message-format json -- -W clippy::all 2>&1 > {output}"
        ),
        sarif_native=False,
        languages=["rust"],
        timeout=600,
    ),
    ToolDefinition(
        name="cargo-udeps",
        category="quality",
        install_method="binary",
        install_package="cargo-udeps",
        command_template="cargo udeps --manifest-path {target}/Cargo.toml --output json > {output}",
        sarif_native=False,
        languages=["rust"],
        timeout=600,
    ),
    # -- LaTeX quality -------------------------------------------------------
    ToolDefinition(
        name="chktex",
        category="quality",
        install_method="binary",
        install_package="chktex",
        command_template="find {target} -name '*.tex' -print0 | xargs -0 chktex -q -v3 > {output}",
        sarif_native=False,
        languages=["latex"],
        timeout=120,
    ),
    ToolDefinition(
        name="lacheck",
        category="quality",
        install_method="binary",
        install_package="lacheck",
        command_template="find {target} -name '*.tex' -exec lacheck {{}} \\; > {output}",
        sarif_native=False,
        languages=["latex"],
        timeout=120,
    ),
    # -- TOML quality --------------------------------------------------------
    ToolDefinition(
        name="taplo",
        category="quality",
        install_method="binary",
        install_package="taplo",
        command_template="taplo lint '{target}/**/*.toml' 2> {output}",
        sarif_native=False,
        languages=["toml"],
        timeout=120,
    ),
    # -- Docker / Shell quality ----------------------------------------------
    ToolDefinition(
        name="hadolint",
        category="quality",
        install_method="binary",
        install_package="hadolint",
        command_template="find {target} -name 'Dockerfile*' -print0 | xargs -0 hadolint --format sarif > {output}",
        sarif_native=True,
        languages=["docker"],
        timeout=60,
    ),
    ToolDefinition(
        name="shellcheck",
        category="quality",
        install_method="binary",
        install_package="shellcheck",
        command_template="find {target} -name '*.sh' -print0 | xargs -0 shellcheck --format json > {output}",
        sarif_native=False,
        languages=["shell"],
        timeout=120,
    ),
]

_COMPLEXITY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="pmd-cpd",
        category="complexity",
        install_method="binary",
        install_package="pmd",
        command_template=(
            "pmd cpd --dir {target} --minimum-tokens 100 --format xml > {output}"
        ),
        sarif_native=False,
        languages=["java", "python", "javascript", "typescript", "cpp", "c"],
        optional=True,
    ),
    ToolDefinition(
        name="deptrac",
        category="complexity",
        install_method="composer",
        install_package="qossmic/deptrac-shim",
        command_template=(
            "deptrac analyse --formatter=json --output={output} {target}"
        ),
        sarif_native=False,
        languages=["php"],
        optional=True,
    ),
    ToolDefinition(
        name="lizard",
        category="complexity",
        install_method="pip",
        install_package="lizard",
        command_template="lizard {target} --xml > {output}",
        sarif_native=False,
        languages=["*"],
    ),
]

_SECRETS_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="checkov",
        category="secrets",
        install_method="pip",
        install_package="checkov",
        command_template=(
            "checkov -d {target} -o sarif --output-file-path {output_dir}"
        ),
        sarif_native=True,
        languages=["terraform", "yaml", "json", "docker"],
        timeout=900,
    ),
    ToolDefinition(
        name="kics",
        category="secrets",
        install_method="binary",
        install_package="kics",
        command_template=(
            "kics scan -p {target} --report-formats sarif -o {output}"
        ),
        sarif_native=True,
        languages=["terraform", "yaml", "json", "docker"],
        timeout=600,
    ),
    ToolDefinition(
        name="slither",
        category="secrets",
        install_method="pip",
        install_package="slither-analyzer",
        command_template="slither {target} --sarif {output}",
        sarif_native=True,
        languages=["solidity"],
        optional=True,
    ),
    ToolDefinition(
        name="trufflehog",
        category="secrets",
        install_method="binary",
        install_package="trufflehog",
        command_template=(
            "trufflehog filesystem {target} --json > {output}"
        ),
        sarif_native=False,
        languages=["*"],
        timeout=600,
    ),
    ToolDefinition(
        name="detect-secrets",
        category="secrets",
        install_method="pip",
        install_package="detect-secrets",
        command_template="detect-secrets scan {target} --all-files > {output}",
        sarif_native=False,
        languages=["*"],
    ),
    ToolDefinition(
        name="ggshield",
        category="secrets",
        install_method="pip",
        install_package="ggshield",
        command_template=(
            "ggshield secret scan path {target} --json --output {output}"
        ),
        sarif_native=False,
        languages=["*"],
        requires_api_key=True,
        env_var_key="GITGUARDIAN_API_KEY",
    ),
]


class ToolRegistry:
    """Central registry that holds all 32 tool definitions."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        for tool in (
            _SECURITY_TOOLS
            + _QUALITY_TOOLS
            + _COMPLEXITY_TOOLS
            + _SECRETS_TOOLS
        ):
            self._tools[tool.name] = tool

    # -- query helpers --------------------------------------------------------

    def get_all(self) -> list[ToolDefinition]:
        """Return every registered tool."""
        return list(self._tools.values())

    def get_by_name(self, name: str) -> ToolDefinition | None:
        """Look up a single tool by its exact name."""
        return self._tools.get(name)

    def get_by_category(self, category: str) -> list[ToolDefinition]:
        """Return all tools belonging to *category*."""
        return [t for t in self._tools.values() if t.category == category]

    def get_for_languages(self, languages: list[str]) -> list[ToolDefinition]:
        """Return tools that apply to any of the given *languages*.

        Tools with ``languages=["*"]`` match every query.
        """
        lang_set = set(languages)
        results: list[ToolDefinition] = []
        for tool in self._tools.values():
            if "*" in tool.languages or lang_set & set(tool.languages):
                results.append(tool)
        return results
