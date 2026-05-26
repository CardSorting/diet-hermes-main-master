"""
[LAYER: CORE]

Canonical JoyZoning governance exemption policy.

Files that cannot carry ``[LAYER: TYPE]`` headers (docs, manifests, DB/ORM,
generated/vendor trees) must never be blocked by the governance transform hook
or flagged by the file-mutation verifier as layering failures.

Python gates, ``joyzoning_governance``, ``file_tools`` audits, and
``scripts/joy_check.py`` all import from this module.

Central pipeline::

  enforce_governance_on_mutation → extract_and_partition (1-pass)
    → run_governance_validation_gate → iter_governance_subject_files
    → validate_joy_zoning(skip_subject_check=True)

Keep ``broccolidb/utils/joy-zoning.ts`` ``GOVERNANCE_*`` constants aligned when
editing this file (search for ``Keep in sync with agent/governance_exemptions``).
"""

from __future__ import annotations

import functools
import json
import os
import re
from typing import Any, Callable, Dict, Iterator, List, Literal, NamedTuple, Optional, Set, Tuple

# Bump when exemption policy changes (tests assert monotonic awareness).
GOVERNANCE_POLICY_VERSION = 16

GovernancePathKind = Literal["exempt", "subject", "ineligible"]

__all__ = (
    "GOVERNANCE_POLICY_VERSION",
    "GovernancePathKind",
    "GOVERNANCE_EXEMPT_BASENAMES",
    "GOVERNANCE_EXEMPT_EXTENSIONS",
    "GOVERNANCE_EXEMPT_PATH_MARKERS",
    "GOVERNANCE_SOURCE_EXTENSIONS",
    "GOVERNANCE_FAULT_MARKER",
    "enforce_governance_on_mutation",
    "evaluate_governance_transform",
    "extract_and_partition_governance_paths",
    "extract_governance_tool_paths",
    "filter_governance_subjects",
    "governance_gate_targets",
    "governance_policy_summary",
    "governance_skip_reason",
    "invalidate_governance_path_cache",
    "is_governance_artifact_path",
    "is_governance_fault_error",
    "is_governance_subject",
    "is_governance_subject_content",
    "is_governance_transform_result",
    "iter_governance_subject_files",
    "normalize_governance_path",
    "partition_governance_paths",
    "resolve_governance_path_kind",
    "run_governance_validation_gate",
    "classify_governance_artifact",
)


class _GovPathContext(NamedTuple):
    """Cached path classification + parsed components (single LRU entry per path)."""

    kind: GovernancePathKind
    normalized_lower: str
    basename: str
    ext: str


class _PathBuckets:
    """Mutable partition accumulator (exempt vs subject lists)."""

    __slots__ = ("exempt", "subjects", "_seen_exempt", "_seen_subjects")

    def __init__(self) -> None:
        self.exempt: List[str] = []
        self.subjects: List[str] = []
        self._seen_exempt: Set[str] = set()
        self._seen_subjects: Set[str] = set()

    def add(self, path: str, kind: GovernancePathKind) -> None:
        if kind == "exempt":
            if path not in self._seen_exempt:
                self._seen_exempt.add(path)
                self.exempt.append(path)
        elif kind == "subject":
            if path not in self._seen_subjects:
                self._seen_subjects.add(path)
                self.subjects.append(path)

    def as_tuple(self) -> Tuple[List[str], List[str]]:
        return self.exempt, self.subjects

_GOVERNANCE_SKIP_LABELS: Dict[str, str] = {
    "documentation": "documentation/markdown",
    "database": "database/ORM artifact",
    "package_manifest": "package manifest",
    "config": "toolchain/config file",
    "test_artifact": "test or spec file",
    "storybook": "Storybook artifact",
    "declaration": "TypeScript declaration stub",
    "web_asset": "web/markup asset (not TS/JS source)",
    "non_js_language": "non-JavaScript language source",
    "infrastructure": "infrastructure-as-code",
    "vendor_or_build": "vendor or build output",
    "ci_cd": "CI/CD configuration",
    "environment": "environment file",
    "non_layerable_artifact": "non-layerable artifact",
}

# Re-use style/blocklist from joy_zoning without circular import at module level.
_STRICT_BLOCKLIST = frozenset({
    ".json", ".json5", ".lock", ".sum", ".bin", ".exe", ".iso",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
})

GOVERNANCE_EXEMPT_BASENAMES = frozenset({
    # Node / JS package manifests
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "npm-shrinkwrap.json", "bun.lockb", "bun.lock", "lerna.json", "nx.json",
    "pnpm-workspace.yaml", "renovate.json", "dependabot.yml",
    # Other language package manifests
    "composer.json", "composer.lock", "cargo.lock", "go.sum", "go.mod",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "pipfile", "pipfile.lock", "poetry.lock", "uv.lock",
    "gemfile", "gemfile.lock", "rakefile", "podfile", "podfile.lock",
    "build.gradle", "settings.gradle", "gradle.properties", "pom.xml", "build.xml",
    # TS/JS toolchain configs (basename match is case-insensitive)
    "tsconfig.json", "jsconfig.json", "tsconfig.build.json", "tsconfig.app.json",
    "turbo.json", "biome.json", "nest-cli.json", "angular.json", "project.json",
    "vite.config.ts", "vite.config.js", "vitest.config.ts", "jest.config.js",
    "jest.config.ts", "webpack.config.js", "rollup.config.js", "next.config.js",
    "next.config.mjs", "nuxt.config.ts", "eslint.config.js", "eslint.config.mjs",
    "prettier.config.js", "postcss.config.js", "tailwind.config.js",
    "playwright.config.ts", "cypress.config.ts", "stryker.config.js",
    "wrangler.toml", "deno.json", "deno.jsonc",
    # ORM / DB config files
    "schema.prisma", "drizzle.config.ts", "drizzle.config.js", "ormconfig.json",
    # Containers & compose
    "docker-compose.yml", "docker-compose.yaml", "containerfile",
    "dockerfile", "earthfile", "makefile", "cmakelists.txt", "justfile",
    # CI / deploy platform configs
    "vercel.json", "railway.json", "firebase.json", "netlify.toml", "app.json",
    "app.config.js", "app.config.ts", "catalog-info.yaml",
    "jenkinsfile", "vagrantfile", "procfile", "fastfile",
    # Docs & legal (markdown variants normalized to lowercase basename)
    "readme.md", "changelog.md", "changes.md", "history.md", "contributing.md",
    "code_of_conduct.md", "security.md", "agents.md", "claude.md", "gemini.md",
    "scratchpad.md", "implementation_plan.md", "task.md", "walkthrough.md",
    "notice", "copying", "patents", "authors", "contributors", "license",
    "license.md", "license.txt",
    # Dotfiles / editor / VCS
    ".gitignore", ".dockerignore", ".npmignore", ".prettierignore", ".eslintignore",
    ".gcloudignore", ".slugignore", ".cursorignore", ".editorconfig",
    ".nvmrc", ".node-version", ".python-version", ".ruby-version", ".java-version",
    ".tool-versions", ".npmrc", ".yarnrc", ".yarnrc.yml",
    ".gitattributes", ".mailmap", ".cursorrules", ".browserslistrc",
    ".prettierrc", ".eslintrc", ".babelrc", ".stylelintrc", ".nycrc",
    "codeowners",
    # Monorepo / build orchestration
    "moon.yml", "mise.toml", "flake.nix", "shell.nix", "default.nix",
    "buf.yaml", "buf.gen.yaml", "buf.lock", "redocly.yaml", "spectral.yaml",
    "graphql.config.yml", "graphql.config.yaml", "apollo.config.js",
    "components.json", "turbo.json", "rush.json", "pnpm-workspace.yaml",
    "workspace.json", "cargo.toml",
    # Mobile / desktop packaging
    "pubspec.yaml", "pubspec.lock", "info.plist", "entitlements.plist",
    "google-services.json", "google-services.plist", "capacitor.config.ts",
    "ionic.config.json", "eas.json", "appcenter-config.json",
    # Cloud / PaaS (additional)
    "serverless.yml", "serverless.yaml", "sam.template.yaml", "template.yaml",
    "fly.toml", "render.yaml", "railway.toml", "wrangler.toml",
    "pulumi.yaml", "pulumi.yml", "skaffold.yaml", "tiltfile",
    # Security / compliance / SBOM
    "sbom.json", "sbom.spdx.json", "cyclonedx.json", "grype.yaml", "trivy.yaml",
    "osv-scanner.toml", ".snyk", "security.txt",
    # Editor / assistant (additional)
    ".cursorindexingignore", ".continueignore", ".aiderignore",
    "copilot-instructions.md", ".windsurfrules",
    # Package managers (additional)
    "bunfig.toml", "pnpmfile.cjs", ".yarnrc.yml", ".pnp.cjs",
    "mix.exs", "rebar.config", "stack.yaml", "cabal.project",
    "Package.swift", "Cartfile", "Podfile.lock",
    # PHP / Java / .NET / misc tooling
    "phpunit.xml", "phpunit.xml.dist", "phpcs.xml", "phpstan.neon",
    "application.properties", "application.yml", "logback.xml",
    "global.json", "nuget.config", "packages.config",
    "kustomization.yaml", "kustomization.yml",
    ".gitmodules", ".gitkeep", ".gitattributes",
    "crowdin.yml", "lighthouserc.js", "size-limit.json",
    "cartfile", "cartfile.resolved", "cartfile.private",
    "site.webmanifest", "manifest.webmanifest",
    "makefile.win", "gnumakefile",
    "vitest.workspace.ts", "vitest.workspace.js",
    "sonar-project.properties", "detekt.yml", "rust-toolchain.toml",
    "tool-versions", "mcp.json", "catalog-info.yml",
    # Python / packaging (additional)
    "manifest.in", "setup.cfg", "constraints.txt", "requirements-dev.txt",
    "environment.yml", "conda-lock.yml",
    # Bazel / Meson / CMake
    "workspace", "build", "meson.build", "meson_options.txt", "cmakelists.txt",
    "gnumakefile", "makefile.am",
    # Tooling configs (additional)
    "dprint.json", "rome.json", "rome.jsonc", "tsup.config.ts", "unbuild.config.ts",
    "ladle.config.ts", "chromatic.config.json", "storybook.config.ts",
    "commitlint.config.js", "release.config.js", "semantic-release.config.js",
    ".releaserc", ".releaserc.json", ".commitlintrc.js",
    "funding.yml", ".funding.json",
    # Registry / agent descriptors
    "agent.json", "plugin.json",
    # Extensionless CLI / env markers (repo root)
    ".venv", "hermes",
    # Nix / flakes (additional)
    "flake.lock",
})

GOVERNANCE_EXEMPT_EXTENSIONS = _STRICT_BLOCKLIST | frozenset({
    # Documentation
    ".md", ".mdx", ".mdc", ".markdown", ".rst", ".txt", ".adoc", ".textile", ".org",
    # Database / ORM / query
    ".dbml", ".kql", ".sql", ".sqlite", ".sqlite3", ".db", ".prisma", ".psql",
    ".mysql", ".pgsql", ".ddl", ".dml",
    # Config / data exchange
    ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".properties",
    ".csv", ".tsv", ".parquet", ".feather",
    # API / schema specs
    ".graphql", ".gql", ".proto", ".avsc", ".avdl", ".thrift", ".raml",
    ".wsdl", ".xsd", ".xsl", ".xslt",
    # Web assets (non-governable source)
    ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
    ".vue", ".svelte", ".php", ".erb", ".haml",
    # Other languages (layer tags are TS/JS-only)
    ".py", ".pyi", ".rb", ".go", ".rs", ".java", ".kt", ".kts", ".scala",
    ".cs", ".fs", ".fsx", ".swift", ".m", ".mm", ".h", ".cpp", ".c", ".cc",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    # Infra-as-code
    ".tf", ".tfvars", ".hcl",
    # i18n
    ".po", ".pot", ".mo",
    # Templates / diagrams
    ".hbs", ".ejs", ".njk", ".mustache", ".handlebars", ".liquid",
    ".puml", ".plantuml", ".drawio",
    # Notebooks / logs / patches
    ".ipynb", ".log", ".patch", ".diff",
    # Bundles / binaries / archives
    ".map", ".min.js", ".min.css", ".min.ts", ".min.tsx", ".bundle.js",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z", ".rar", ".jar", ".war",
    ".pem", ".crt", ".cer", ".p12", ".pfx", ".key", ".jks",
    ".ico", ".icns", ".wasm", ".wat",
    ".mp3", ".mp4", ".wav", ".webm", ".mp4", ".mov", ".avi",
    ".pdf", ".doc", ".docx",
    ".xml", ".plist", ".info", ".lcov",
    # More markup / templates
    ".astro", ".mdown", ".asciidoc", ".feature", ".robot", ".story",
    # More languages / runtimes
    ".nim", ".zig", ".dart", ".ex", ".exs", ".erl", ".hrl", ".hs", ".lhs",
    ".lua", ".r", ".jl", ".v", ".sv", ".ml", ".mli", ".clj", ".cljs",
    ".groovy", ".gradle", ".gradle.kts", ".kt", ".kts",
    # Policy / IaC (additional)
    ".rego", ".nomad", ".pp", ".hcl", ".cue", ".bicep", ".arm",
    # .NET / JVM project files
    ".sln", ".csproj", ".vbproj", ".fsproj", ".xproj", ".nuspec", ".gemspec",
    # Design / media (additional)
    ".sketch", ".fig", ".xd", ".psd", ".ai", ".eps", ".webp", ".avif",
    ".heic", ".heif", ".flac", ".ogg", ".m4a",
    # Certificates / keys (path + ext)
    ".csr", ".der", ".p7b", ".p7c",
    # Snapshots / changesets
    ".changeset", ".changeset.md",
    # Data / interchange (additional)
    ".jsonl", ".ndjson", ".arrow", ".orc", ".avro",
    ".twig", ".blade.php", ".wxml", ".wxss", ".wxs",
    # Office / misc
    ".pptx", ".xlsx", ".ods", ".odt",
    # Mail / subtitles / misc data
    ".eml", ".mbox", ".srt", ".vtt", ".ass",
    # Build descriptors
    ".cmake", ".bazel", ".bzl", ".nix",
    # LaTeX / academic templates (skills, papers)
    ".tex", ".ltx", ".bib", ".bst", ".sty", ".cls", ".ins", ".dtx", ".bbx", ".cbx",
    # Desktop / TUI assets
    ".eikon",
    # systemd / unit files
    ".service", ".socket", ".timer", ".mount", ".target",
    # Extensionless-adjacent bundles
    ".desktop", ".ics", ".vcf",
})

GOVERNANCE_EXEMPT_PATH_MARKERS = (
    # DB / ORM / migrations
    "/migrations/", "/migration/", "/migrate/", "/db/migrate/",
    "/prisma/", "/drizzle/", "/typeorm/", "/sequelize/", "/objection/",
    "/knex/", "/alembic/", "/liquibase/", "/flyway/",
    "/supabase/", "/hasura/", "/metabase/", "/cockroach/", "/atlas/",
    "/database/", "/databases/", "/db/migrations/", "/db/schema/",
    "/database/schema/",
    "/seeders/", "/seeds/", "/sql/",
    # Test / fixture data
    "/fixtures/", "/__fixtures__/", "/testdata/", "/test-data/",
    "/snapshots/", "/__snapshots__/", "/golden/", "/__mocks__/", "/mock-data/",
    # Docs / site / reports
    "/docs/", "/documentation/", "/doc/", "/reports/", "/report/",
    "/website/", "/site/", "/blog/", "/changelog/", "/wiki/",
    # Generated / vendor / build output
    "/generated/", "/__generated__/", "/vendor/", "/third_party/",
    "/third-party/", "/externals/", "/submodules/",
    "/node_modules/", "/.venv/", "/venv/", "/.git/",
    "/dist/", "/build/", "/out/", "/output/", "/target/", "/coverage/",
    "/.next/", "/.nuxt/", "/.svelte-kit/", "/.turbo/", "/.cache/",
    "/locales/", "/i18n/", "/translations/",
    # API specs & collections
    "/openapi/", "/swagger/", "/postman/", "/insomnia/",
    # IDE / editor
    "/.cursor/", "/.vscode/", "/.idea/",
    # CI / CD / hooks
    "/.github/", "/.gitlab/", "/.circleci/", "/.travis/",
    "/.jenkins/", "/.buildkite/",
    # Infra / deploy / k8s
    "/terraform/", "/.pulumi/", "/cdktf/", "/ansible/",
    "/kubernetes/", "/k8s/", "/helm/", "/charts/", "/deploy/",
    "/docker/", "/.vercel/", "/.netlify/",
    # UI tooling / e2e (dirs, not app source)
    "/.storybook/", "/storybook-static/", "/cypress/", "/playwright/",
    "/e2e/", "/benchmarks/",
    "/patches/", "/.pnpm-store/", "/.pnpm/", "/.yarn/",
    # Monorepo / tooling caches
    "/.turbo/", "/.moon/", "/.changeset/", "/.rush/", "/.nx/",
    # Temp / logs / local state
    "/tmp/", "/temp/", "/.tmp/", "/logs/", "/log/",
    # Legal / compliance dirs
    "/legal/", "/licenses/", "/license/",
    # API / contract artifacts (dirs — not ``src/.../schema`` TS modules)
    "/proto/", "/protos/", "/protobuf/", "/contracts/openapi/",
    "/schemas/json/", "/json-schema/",
    # Design / content / CMS
    "/design-tokens/", "/cms/", "/sanity/",
    # Mocks / stubs / fakes (test support trees)
    "/mocks/", "/__mocks__/", "/stubs/", "/fakes/", "/doubles/",
    "/test-utils/",
    # Observability / ops config
    "/grafana/", "/prometheus/", "/alertmanager/", "/datadog/",
    # Mobile / native asset trees
    "/android/", "/ios/", "/macos/", "/windows/", "/linux/",
    "/res/", "/resources/", "/assets/raw/",
    # Hermes optional-skills tree (markdown skills — not TS source)
    "/optional-skills/", "/.plans/", "/.devcontainer/", "/acp_registry/",
    "/issue_templates/",
    "/paste_store/", "/.broccolidb/",
    "/templates/aaai", "/templates/acl/", "/templates/colm", "/templates/neurips",
    "/research-paper-writing/",
)

GOVERNANCE_EXEMPT_BASENAME_SUFFIXES = (
    ".d.ts",
    ".config.ts", ".config.js", ".config.mjs", ".config.cjs",
    ".config.json", ".setup.ts", ".setup.js",
    ".test.ts", ".test.tsx", ".test.js", ".test.jsx",
    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx",
    ".stories.ts", ".stories.tsx", ".stories.js", ".stories.jsx",
    ".mock.ts", ".mock.tsx", ".bench.ts", ".bench.tsx",
    ".e2e.ts", ".e2e.tsx", ".cy.ts", ".cy.tsx",
    ".min.ts", ".min.tsx", ".min.js", ".min.jsx",
    ".generated.ts", ".generated.tsx", ".gen.ts", ".gen.tsx",
    ".snap", ".snapshot",
    ".integration.ts", ".integration.tsx", ".integration.js",
    ".smoke.ts", ".smoke.tsx", ".contract.ts", ".fixture.ts",
    ".config.mts", ".config.cts", ".config.mjs",
    ".setup.mts", ".setup.cts",
    ".workspace.ts", ".workspace.js", ".workspace.mjs",
    ".node.ts", ".node.cts",
    ".opts.ts", ".opts.js",
    ".overrides.ts", ".overrides.js",
    ".bench.ts", ".bench.tsx", ".bench.js",
    ".test.mjs", ".test.cjs", ".spec.mjs", ".spec.cjs",
)

GOVERNANCE_COMPOUND_SUFFIXES = (
    ".min.js", ".min.css", ".min.ts", ".min.tsx", ".min.mjs",
    ".bundle.js", ".bundle.css",
    ".tar.gz", ".tar.bz2", ".tar.xz",
    ".test.ts.snap", ".test.tsx.snap", ".test.js.snap",
)

GOVERNANCE_EXEMPT_SEGMENT_PREFIXES = (
    "node_modules/", ".git/", ".venv/", "venv/", "dist/", "build/",
    "coverage/", ".husky/", ".cursor/", ".idea/",
    ".github/", ".gitlab/", ".circleci/", ".travis/", ".buildkite/",
    "out/", "target/", ".output/", ".cache/", ".turbo/", ".next/", ".nuxt/", ".svelte-kit/",
    ".moon/", ".nx/", ".rush/",
    "tmp/", "temp/", ".tmp/", "logs/", "log/",
    "mocks/", "__mocks__/", "stubs/", "fakes/", "doubles/", "test-utils/",
    "proto/", "protos/", ".changeset/", ".pnpm/", ".yarn/", ".pnpm-store/",
    "docs/", "documentation/", "reports/", "website/", "wiki/", "blog/",
    "migrations/", "migration/", "prisma/", "drizzle/", "supabase/", "hasura/",
    "fixtures/", "__fixtures__/", "testdata/", "test-data/", "snapshots/", "__snapshots__/",
    "generated/", "__generated__/", "vendor/", "third_party/", "third-party/",
    "e2e/", "cypress/", "playwright/", ".storybook/", "storybook-static/",
    "terraform/", "k8s/", "helm/", "charts/", "deploy/", "infra/",
    "grafana/", "prometheus/", "alertmanager/", "datadog/",
    "optional-skills/", "design-tokens/", "cms/", "sanity/",
    "android/", "ios/", "legal/", "licenses/",
    ".plans/", ".devcontainer/", "acp_registry/",
    "issue_templates/", "actions/",
    ".broccolidb/", "paste_store/",
    "herm-tui/bin/",
)


def _build_infix_path_markers() -> Tuple[str, ...]:
    """Merge path markers + segment prefixes into one substring scan (except ``skills/``)."""
    seen: Set[str] = set(GOVERNANCE_EXEMPT_PATH_MARKERS)
    ordered: List[str] = list(GOVERNANCE_EXEMPT_PATH_MARKERS)
    for seg in GOVERNANCE_EXEMPT_SEGMENT_PREFIXES:
        if seg == "skills/":
            continue
        for form in (seg, f"/{seg}"):
            if form not in seen:
                seen.add(form)
                ordered.append(form)
    return tuple(ordered)


# Single-pass directory / tree exemption scan (built once at import).
_GOVERNANCE_INFIX_MARKERS: Tuple[str, ...] = _build_infix_path_markers()
_GOVERNANCE_INFIX_RE = re.compile(
    "|".join(re.escape(marker) for marker in _GOVERNANCE_INFIX_MARKERS)
)
_EXEMPT_DB_PATH_RE = re.compile(
    r"/(?:migrations|prisma|drizzle|seeders)/"
)
_EXEMPT_VENDOR_RE = re.compile(
    r"(?:^|/)(?:node_modules|dist|build|\.next|coverage)(?:/|$)"
)
_EXEMPT_DOC_PATH_RE = re.compile(r"/(?:docs|reports|website)/")
_EXEMPT_CI_PATH_RE = re.compile(r"/(?:\.github/workflows/|\.gitlab-ci|\.husky/)")

GOVERNANCE_SOURCE_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".jsx"})

GOVERNANCE_FAULT_MARKER = "GOVERNANCE FAULT"

_V4A_FILE_HEADER = re.compile(
    r"^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+)$",
    re.MULTILINE,
)

_FILE_MUTATION_TOOLS = frozenset({
    "write_file", "patch", "multi_replace_file_content", "replace_file_content",
})

_GOVERNANCE_TRANSFORM_TOOLS = _FILE_MUTATION_TOOLS

_USER_EXEMPT_MARKERS_CACHE: Optional[frozenset[str]] = None
_VALIDATE_JOY_ZONING: Optional[Callable[..., Dict[str, Any]]] = None
_GET_LAYER: Optional[Callable[[str, Optional[str]], str]] = None
_LAYER_TAG_SUPPORTED: Optional[Callable[..., bool]] = None

# Reused gate success payload (avoid per-call dict allocation on hot hook path).
_GOVERNANCE_GATE_OK: Dict[str, Any] = {
    "success": True,
    "singleResults": [],
    "layeringViolations": [],
    "hasLayeringCheck": False,
}


def _user_extra_exempt_markers() -> frozenset[str]:
    """Optional ``joyzoning.governance.extra_exempt_paths`` from config.yaml."""
    global _USER_EXEMPT_MARKERS_CACHE
    if _USER_EXEMPT_MARKERS_CACHE is not None:
        return _USER_EXEMPT_MARKERS_CACHE
    markers: List[str] = []
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        jz = cfg.get("joyzoning") if isinstance(cfg, dict) else {}
        gov = jz.get("governance") if isinstance(jz, dict) else {}
        if isinstance(gov, dict):
            for raw in gov.get("extra_exempt_paths") or []:
                if isinstance(raw, str) and raw.strip():
                    markers.append(normalize_governance_path(raw).lower())
    except Exception:
        pass
    _USER_EXEMPT_MARKERS_CACHE = frozenset(markers)
    return _USER_EXEMPT_MARKERS_CACHE


def normalize_governance_path(file_path: str) -> str:
    """Normalize a path for governance policy checks."""
    return file_path.replace("\\", "/").strip()


def _joy_zoning_validate() -> Callable[..., Dict[str, Any]]:
    global _VALIDATE_JOY_ZONING
    if _VALIDATE_JOY_ZONING is None:
        from agent.joy_zoning import validate_joy_zoning

        _VALIDATE_JOY_ZONING = validate_joy_zoning
    return _VALIDATE_JOY_ZONING


def _joy_zoning_get_layer() -> Callable[[str, Optional[str]], str]:
    global _GET_LAYER
    if _GET_LAYER is None:
        from agent.joy_zoning import get_layer

        _GET_LAYER = get_layer
    return _GET_LAYER


def _layer_tag_supported_fn() -> Callable[..., bool]:
    global _LAYER_TAG_SUPPORTED
    if _LAYER_TAG_SUPPORTED is None:
        from agent.joy_zoning import is_layer_tag_supported

        _LAYER_TAG_SUPPORTED = is_layer_tag_supported
    return _LAYER_TAG_SUPPORTED


def _path_has_infix_marker(normalized_lower: str) -> bool:
    return _GOVERNANCE_INFIX_RE.search(normalized_lower) is not None


def _is_lockfile_basename(basename: str) -> bool:
    """Heuristic: ecosystem lockfiles and shrinkwraps (case-insensitive basename)."""
    if not basename:
        return False
    lower = basename.lower()
    if lower.endswith(".lock") or lower.endswith("-lock.json"):
        return True
    if lower in {"bun.lockb", "bun.lock", "pnpm-lock.yaml", "yarn.lock", "uv.lock"}:
        return True
    if lower.endswith(".lockb") or lower.endswith(".lock.yaml"):
        return True
    return False


def _iter_path_extensions(file_path: str) -> Tuple[str, ...]:
    """Return extension segments from right to left (e.g. ``.tar.gz`` → ``('.gz', '.tar')``)."""
    exts: List[str] = []
    name = file_path.lower()
    while name:
        base, ext = os.path.splitext(name)
        if not ext:
            break
        exts.append(ext)
        if base == name:
            break
        name = base
    return tuple(exts)


def _is_compound_exempt_path(normalized_path: str) -> bool:
    return normalized_path.endswith(GOVERNANCE_COMPOUND_SUFFIXES)


def _is_env_file_basename(basename: str) -> bool:
    lower = basename.lower()
    if lower.startswith(".env"):
        return True
    if lower in {".envrc", "envrc"}:
        return True
    if lower.startswith("env.") and lower.endswith((
        ".local", ".example", ".sample", ".development", ".production", ".test",
    )):
        return True
    return False


def _is_makefile_variant(basename: str) -> bool:
    lower = basename.lower()
    if lower in {"makefile", "gnumakefile", "makefile.win", "makefile.am"}:
        return True
    if lower.startswith("makefile.") or lower.startswith("gnumakefile."):
        return True
    return False


def _is_build_system_basename(basename: str) -> bool:
    lower = basename.lower()
    if lower in {"workspace", "build", "meson.build", "meson_options.txt", "cmakelists.txt"}:
        return True
    if lower.startswith("dockerfile.") or lower.startswith("containerfile."):
        return True
    return False


def _is_release_or_plan_doc(basename: str) -> bool:
    lower = basename.lower()
    if lower.startswith("release_") and lower.endswith(".md"):
        return True
    if lower.startswith("release-") and lower.endswith(".md"):
        return True
    return False


def _is_repo_root_skills_tree(normalized: str) -> bool:
    """Hermes-style ``skills/<category>/...`` at repo root (not ``src/skills``)."""
    if normalized.startswith("skills/"):
        return True
    return False


def _is_paste_or_local_store(normalized: str) -> bool:
    return "/paste_store/" in normalized or "/.broccolidb/" in normalized


def _is_test_harness_source(normalized: str, basename: str) -> bool:
    """Non-``.test.*`` harness files under test directories (benchmarks, stress)."""
    if not any(m in normalized for m in ("/tests/", "/test/", "/__tests__/", "/benchmarks/")):
        return False
    lower = basename.lower()
    if re.match(r"^(benchmark|stress|perf|load|setup|teardown)(\.|$)", lower):
        return True
    return False


def _is_extensionless_artifact_basename(basename: str, normalized: str) -> bool:
    """Tracked paths with no extension that are never layerable source."""
    if not basename or "." in basename:
        return False
    lower = basename.lower()
    if lower in {".venv", "venv", "hermes", "makefile", "dockerfile", "license", "readme"}:
        return True
    if normalized.startswith("scripts/") and lower not in {"makefile", "dockerfile"}:
        return True
    # content-addressed store blobs (hash filenames)
    if re.fullmatch(r"[a-f0-9]{32,128}", lower):
        return True
    return False


def _is_config_tool_basename(basename: str) -> bool:
    """Known toolchain config filenames not covered by suffix rules."""
    lower = basename.lower()
    if lower.endswith(".config.ts") or lower.endswith(".config.js"):
        return True
    if lower.endswith(".config.mjs") or lower.endswith(".config.cjs"):
        return True
    if lower.endswith(".config.json") or lower.endswith(".config.yaml"):
        return True
    if re.match(r"^[a-z0-9_.-]+\.config\.(ts|js|mjs|cjs|mts|cts)$", lower):
        return True
    return False


def _is_editor_rc_basename(basename: str) -> bool:
    """Dot-rc and tool-rc config files without a governable extension."""
    if not basename:
        return False
    lower = basename.lower()
    if lower.startswith(".") and lower.endswith("rc"):
        return True
    if lower.endswith("rc.json") or lower.endswith("rc.yaml") or lower.endswith("rc.yml"):
        return True
    if lower.startswith(".eslintrc.") or lower.startswith(".prettierrc."):
        return True
    if lower.endswith(".cjs") and "rc" in lower:
        return True
    return False


def _basename_exempt_heuristics(basename: str, normalized: str) -> bool:
    """Fast basename / path-shape checks (no extension table walk)."""
    if basename in GOVERNANCE_EXEMPT_BASENAMES:
        return True
    if (
        _is_lockfile_basename(basename)
        or _is_editor_rc_basename(basename)
        or _is_env_file_basename(basename)
        or _is_makefile_variant(basename)
        or _is_build_system_basename(basename)
        or _is_release_or_plan_doc(basename)
        or _is_config_tool_basename(basename)
    ):
        return True
    if _is_repo_root_skills_tree(normalized) or _is_paste_or_local_store(normalized):
        return True
    if _is_extensionless_artifact_basename(basename, normalized) or _is_test_harness_source(
        normalized, basename
    ):
        return True
    if _is_compound_exempt_path(normalized):
        return True
    if basename in {"dockerfile", "containerfile"} or basename.startswith("dockerfile."):
        return True
    return False


def _artifact_exempt_impl(normalized_lower: str, basename: str) -> bool:
    """Uncached exemption decision (``normalized_lower`` is already lowercased)."""
    if _basename_exempt_heuristics(basename, normalized_lower):
        return True
    if basename.endswith(GOVERNANCE_EXEMPT_BASENAME_SUFFIXES):
        return True
    primary_ext = os.path.splitext(normalized_lower)[1]
    if primary_ext in GOVERNANCE_EXEMPT_EXTENSIONS:
        return True
    for ext in _iter_path_extensions(normalized_lower)[1:]:
        if ext in GOVERNANCE_EXEMPT_EXTENSIONS:
            return True
    if _path_has_infix_marker(normalized_lower):
        return True
    for extra in _user_extra_exempt_markers():
        if extra in normalized_lower or normalized_lower.endswith(extra):
            return True
    return False


def _compute_path_context(normalized_lower: str) -> _GovPathContext:
    basename = os.path.basename(normalized_lower)
    ext = os.path.splitext(normalized_lower)[1]
    if _artifact_exempt_impl(normalized_lower, basename):
        kind: GovernancePathKind = "exempt"
    elif ext not in GOVERNANCE_SOURCE_EXTENSIONS:
        kind = "ineligible"
    else:
        kind = "subject"
    return _GovPathContext(kind, normalized_lower, basename, ext)


@functools.lru_cache(maxsize=8192)
def _governance_path_context(file_path: str) -> _GovPathContext:
    """Cached classification + parsed path components for a single lookup per path."""
    return _compute_path_context(normalize_governance_path(file_path).lower())


def invalidate_governance_path_cache() -> None:
    """Clear path-classifier LRUs (e.g. after ``extra_exempt_paths`` config changes)."""
    global _USER_EXEMPT_MARKERS_CACHE
    _USER_EXEMPT_MARKERS_CACHE = None
    _governance_path_context.cache_clear()


def resolve_governance_path_kind(file_path: str) -> GovernancePathKind:
    """Single classifier: exempt artifact, governable TS/JS subject, or ineligible."""
    if not file_path or not str(file_path).strip():
        return "exempt"
    return _governance_path_context(file_path).kind


def is_governance_subject_content(file_path: str, content: Optional[str] = None) -> bool:
    """Content eligibility when path is already classified as a ``subject``."""
    return _layer_tag_supported_fn()(file_path, content, skip_artifact_check=True)


def read_governance_file_text(file_path: str) -> Optional[str]:
    """Read UTF-8 text for gate/audit pipelines (returns None on failure)."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as handle:
            return handle.read()
    except OSError:
        return None


def is_governance_artifact_path(file_path: str) -> bool:
    """Return True when the path cannot carry [LAYER: TYPE] tags (exempt)."""
    return resolve_governance_path_kind(file_path) == "exempt"


def governance_policy_summary() -> Dict[str, Any]:
    """Introspection helper — counts of static policy tables (for CLI/debug)."""
    return {
        "version": GOVERNANCE_POLICY_VERSION,
        "exempt_basenames": len(GOVERNANCE_EXEMPT_BASENAMES),
        "exempt_extensions": len(GOVERNANCE_EXEMPT_EXTENSIONS),
        "exempt_path_markers": len(GOVERNANCE_EXEMPT_PATH_MARKERS),
        "exempt_basename_suffixes": len(GOVERNANCE_EXEMPT_BASENAME_SUFFIXES),
        "exempt_segment_prefixes": len(GOVERNANCE_EXEMPT_SEGMENT_PREFIXES),
        "infix_markers": len(_GOVERNANCE_INFIX_MARKERS),
        "compound_suffixes": len(GOVERNANCE_COMPOUND_SUFFIXES),
        "source_extensions": sorted(GOVERNANCE_SOURCE_EXTENSIONS),
        "path_cache_info": _governance_path_context.cache_info()._asdict(),
    }


def is_governance_transform_result(payload: Dict[str, Any]) -> bool:
    """True when a parsed tool-result dict came from the governance transform hook."""
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    return isinstance(err, str) and GOVERNANCE_FAULT_MARKER in err


def is_governance_subject(file_path: str, content: Optional[str] = None) -> bool:
    """Return True when JoyZoning layering rules apply to this file path."""
    if _governance_path_context(file_path).kind != "subject":
        return False
    return is_governance_subject_content(file_path, content)


def _partition_raw_path(
    raw: str,
    buckets: _PathBuckets,
    *,
    kind: Optional[GovernancePathKind] = None,
) -> None:
    """Classify one path into exempt/subject lists (deduped, stable append)."""
    if not raw:
        return
    p = normalize_governance_path(raw)
    resolved_kind = kind if kind is not None else _governance_path_context(raw).kind
    buckets.add(p, resolved_kind)


def partition_governance_paths(paths: List[str]) -> Tuple[List[str], List[str]]:
    """Split paths into (exempt artifacts, governable subjects), deduped, stable order."""
    buckets = _PathBuckets()
    for raw in paths:
        _partition_raw_path(raw, buckets)
    return buckets.as_tuple()


def _iter_governance_tool_paths(tool_name: str, args: Dict[str, Any]) -> Iterator[str]:
    """Yield unique normalized paths from a file-mutating tool invocation."""
    seen: Set[str] = set()

    def _yield_raw(raw: str) -> Iterator[str]:
        p = normalize_governance_path(raw)
        if p and p not in seen:
            seen.add(p)
            yield p

    if not isinstance(args, dict):
        return

    for key in ("path", "file_path", "target_file", "filepath", "target", "filename"):
        val = args.get(key)
        if isinstance(val, str) and val:
            yield from _yield_raw(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item:
                    yield from _yield_raw(item)

    for key in ("files", "paths", "file_paths", "targets"):
        val = args.get(key)
        if not isinstance(val, list):
            continue
        for item in val:
            if isinstance(item, str) and item:
                yield from _yield_raw(item)
            elif isinstance(item, dict):
                nested = item.get("path") or item.get("file_path")
                if isinstance(nested, str) and nested:
                    yield from _yield_raw(nested)

    if tool_name in _FILE_MUTATION_TOOLS:
        from agent.tool_dispatch_helpers import _extract_file_mutation_targets

        for p in _extract_file_mutation_targets(tool_name, args):
            yield from _yield_raw(p)

    if tool_name == "patch" and (args.get("mode") or "replace") == "patch":
        body = args.get("patch") or ""
        if isinstance(body, str):
            for match in _V4A_FILE_HEADER.finditer(body):
                yield from _yield_raw(match.group(1).strip())


def extract_and_partition_governance_paths(
    tool_name: str,
    args: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    """Tool-hook entry: extract + classify mutation targets in a single pass."""
    buckets = _PathBuckets()
    for p in _iter_governance_tool_paths(tool_name, args):
        buckets.add(p, _governance_path_context(p).kind)
    return buckets.as_tuple()


def filter_governance_subjects(paths: List[str]) -> List[str]:
    """Return paths subject to layering governance (stable order, deduped)."""
    return partition_governance_paths(paths)[1]


def governance_gate_targets(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """Paths to run through the governance gate for a tool call (may be empty)."""
    return extract_and_partition_governance_paths(tool_name, args)[1]


def iter_governance_subject_files(
    file_paths: List[str],
    *,
    subjects_only: bool = False,
) -> Iterator[Tuple[str, str]]:
    """Yield ``(path, content)`` for governable subjects that pass content eligibility."""
    if subjects_only:
        candidates = file_paths
    else:
        _, candidates = partition_governance_paths(file_paths)
    tag_fn = _layer_tag_supported_fn()
    for file_path in candidates:
        if not os.path.isfile(file_path):
            continue
        content = read_governance_file_text(file_path)
        if content is None:
            continue
        norm = normalize_governance_path(file_path)
        if not tag_fn(norm, content, skip_artifact_check=True):
            continue
        yield file_path, content


def run_governance_validation_gate(
    files: List[str],
    *,
    validate: Optional[Callable[..., Dict[str, Any]]] = None,
    get_layer: Optional[Callable[[str, Optional[str]], str]] = None,
    subjects_only: bool = False,
) -> Dict[str, Any]:
    """Run layering validation on governable subjects only (central gate pipeline).

    When ``subjects_only`` is True, ``files`` is already partitioned (hook fast-path).
    """
    validate_fn = validate or _joy_zoning_validate()
    layer_fn = get_layer or _joy_zoning_get_layer()
    single_results: List[Dict[str, Any]] = []

    for file_path, content in iter_governance_subject_files(files, subjects_only=subjects_only):
        audit = validate_fn(file_path, content, skip_subject_check=True)
        if audit.get("success") or audit.get("skipped"):
            continue
        single_results.append({
            "file": file_path,
            "layer": layer_fn(file_path, content),
            "errors": audit.get("errors") or [],
        })
    if not single_results:
        return {**_GOVERNANCE_GATE_OK}
    return {
        "success": False,
        "singleResults": single_results,
        "layeringViolations": [],
        "hasLayeringCheck": True,
    }


def _classify_exempt_category(ctx: _GovPathContext) -> str:
    """Map an exempt path context to a category label (ctx.kind must be ``exempt``)."""
    norm = ctx.normalized_lower
    basename = ctx.basename
    ext = ctx.ext

    if ext in {".md", ".mdx", ".mdc", ".rst", ".txt", ".adoc"}:
        return "documentation"
    if ext in {".sql", ".prisma", ".db", ".sqlite", ".sqlite3", ".dbml"}:
        return "database"
    if _EXEMPT_DB_PATH_RE.search(norm):
        return "database"
    if basename == "package.json" or ext in {".json", ".json5"} or "lock" in basename:
        return "package_manifest"
    if ext in {".yaml", ".yml", ".toml"} or basename.endswith(".config.ts"):
        return "config"
    if basename.endswith(GOVERNANCE_EXEMPT_BASENAME_SUFFIXES):
        if ".test." in basename or ".spec." in basename or basename.endswith((".test.ts", ".spec.ts")):
            return "test_artifact"
        if ".stories." in basename:
            return "storybook"
        if ".d.ts" in basename:
            return "declaration"
        if ".config." in basename:
            return "config"
    if ext in {".html", ".css", ".scss", ".vue", ".svelte"}:
        return "web_asset"
    if ext in {".py", ".go", ".rs", ".java", ".rb", ".sh"}:
        return "non_js_language"
    if ext in {".tf", ".hcl"}:
        return "infrastructure"
    if _EXEMPT_VENDOR_RE.search(norm):
        return "vendor_or_build"
    if _EXEMPT_DOC_PATH_RE.search(norm):
        return "documentation"
    if _EXEMPT_CI_PATH_RE.search(norm):
        return "ci_cd"
    if _is_env_file_basename(basename):
        return "environment"
    if _is_lockfile_basename(basename):
        return "package_manifest"
    return "non_layerable_artifact"


def classify_governance_artifact(file_path: str) -> Optional[str]:
    """Return exemption category label, or None if the path is governable."""
    ctx = _governance_path_context(file_path)
    if ctx.kind != "exempt":
        return None
    return _classify_exempt_category(ctx)


def governance_skip_reason(file_path: str) -> Optional[str]:
    """Human-readable reason a path is exempt from layering (for CLI/tools)."""
    category = classify_governance_artifact(file_path)
    if not category:
        return None
    return _GOVERNANCE_SKIP_LABELS.get(category, category)


def is_governance_fault_error(preview: str) -> bool:
    """True when a tool error preview is from the governance transform hook."""
    return GOVERNANCE_FAULT_MARKER in (preview or "")


def extract_governance_tool_paths(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """Collect file paths targeted by a file-mutating tool invocation."""
    return list(_iter_governance_tool_paths(tool_name, args))


def enforce_governance_on_mutation(
    tool_name: str,
    args: Dict[str, Any],
    result: Any,
    *,
    run_gate: Optional[Callable[[List[str]], Dict[str, Any]]] = None,
) -> Optional[str]:
    """Run the governance gate on file mutations; return replacement JSON when blocked.

    When ``run_gate`` is omitted, uses the built-in validation pipeline
    (``subjects_only`` — no second partition). Inject ``run_gate`` in tests only.
    """
    if tool_name not in _GOVERNANCE_TRANSFORM_TOOLS or not isinstance(args, dict):
        return None

    exempt, target_files = extract_and_partition_governance_paths(tool_name, args)
    if not target_files:
        return None

    gate = (
        run_gate(target_files)
        if run_gate is not None
        else run_governance_validation_gate(target_files, subjects_only=True)
    )
    if gate.get("success", True):
        return None

    return json.dumps(_governance_fault_payload(target_files, exempt, gate, result))


# Back-compat alias (tests and older imports).
evaluate_governance_transform = enforce_governance_on_mutation


def _governance_fault_payload(
    dirty_files: List[str],
    exempt_skipped: List[str],
    gate: Dict[str, Any],
    original_result: Any,
) -> Dict[str, Any]:
    failures_log: List[str] = []
    for item in gate.get("singleResults", []):
        failures_log.append(f"  • {item['file']} [Layer: {item.get('layer', 'unknown')}]")
        for err in item.get("errors", []):
            failures_log.append(f"    - {err}")

    report = (
        "==============================================================\n"
        f"{GOVERNANCE_FAULT_MARKER}: JoyZoning Layering Violations Detected!\n"
        "==============================================================\n"
        "Your changes succeeded at the filesystem level, but they breached\n"
        "the strict structural architecture policies of this codebase.\n"
        "You MUST resolve these violations immediately before calling any other tool.\n\n"
        "📂 Tag & Format Compliance Failures:\n" + "\n".join(failures_log) + "\n\n"
        "==============================================================\n"
        "🔧 RECOMMENDATION:\n"
        "  1. Add correct `/** [LAYER: TYPE] */` headers to governable TS/JS source.\n"
        "  2. Refactor forbidden imports using Dependency Inversion.\n"
        "  3. Exempt (no layer tags): .md, package.json, lockfiles, SQL/migrations, ORM.\n"
        "=============================================================="
    )
    return {
        "success": False,
        "error": report,
        "dirty_files": dirty_files,
        "exempt_skipped": exempt_skipped,
        "original_result": original_result,
    }
