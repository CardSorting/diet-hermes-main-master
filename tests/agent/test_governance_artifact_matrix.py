"""Broad artifact matrix — exempt vs governable classification."""

from __future__ import annotations

import pytest

from plugins.dietcode.lib.agent.governance_exemptions import (
    classify_governance_artifact,
    governance_skip_reason,
    is_governance_artifact_path,
    is_governance_subject,
    partition_governance_paths,
)

# (category, path) — every path must be exempt from layering governance.
EXEMPT_ARTIFACT_MATRIX: list[tuple[str, str]] = [
    # --- Documentation ---
    ("docs", "README.md"),
    ("docs", "CHANGELOG.MD"),
    ("docs", "docs/api/reference.md"),
    ("docs", "docs/reports/typingjoy-agentic-benchmark.md"),
    ("docs", "website/content/blog/post.mdx"),
    ("docs", ".cursor/rules/project.mdc"),
    ("docs", "NOTES.txt"),
    ("docs", "AUTHORS"),
    ("docs", "CODEOWNERS"),
    # --- Node / JS manifests ---
    ("package", "package.json"),
    ("package", "package-lock.json"),
    ("package", "pnpm-lock.yaml"),
    ("package", "yarn.lock"),
    ("package", "bun.lockb"),
    ("package", "pnpm-workspace.yaml"),
    ("package", "lerna.json"),
    ("package", "nx.json"),
    # --- Other ecosystems ---
    ("package", "pyproject.toml"),
    ("package", "Cargo.toml"),
    ("package", "go.mod"),
    ("package", "Gemfile"),
    ("package", "Gemfile.lock"),
    ("package", "build.gradle"),
    ("package", "pom.xml"),
    ("package", "composer.json"),
    # --- Toolchain / linter configs ---
    ("config", "tsconfig.json"),
    ("config", "jsconfig.json"),
    ("config", "vite.config.ts"),
    ("config", "vitest.config.ts"),
    ("config", "jest.config.js"),
    ("config", "eslint.config.mjs"),
    ("config", "tailwind.config.js"),
    ("config", "playwright.config.ts"),
    ("config", ".prettierrc"),
    ("config", ".eslintrc"),
    ("config", ".editorconfig"),
    ("config", "biome.json"),
    # --- Database / ORM ---
    ("database", "prisma/schema.prisma"),
    ("database", "drizzle.config.ts"),
    ("database", "db/migrations/20240101_init.sql"),
    ("database", "supabase/migrations/001_users.sql"),
    ("database", "src/db/seeders/dev.sql"),
    ("database", "schema.dbml"),
    ("database", "dump.sqlite"),
    # --- Docker / compose ---
    ("container", "Dockerfile"),
    ("container", "docker-compose.yml"),
    ("container", "compose.yaml"),
    ("container", "Containerfile"),
    # --- CI / CD ---
    ("ci", ".github/workflows/ci.yml"),
    ("ci", ".gitlab-ci.yml"),
    ("ci", ".circleci/config.yml"),
    ("ci", ".husky/pre-commit"),
    ("ci", "Jenkinsfile"),
    ("ci", "renovate.json"),
    # --- Env / secrets templates ---
    ("env", ".env"),
    ("env", ".env.local"),
    ("env", ".env.example"),
    # --- Web / non-JS languages ---
    ("web", "index.html"),
    ("web", "styles/main.css"),
    ("web", "App.vue"),
    ("web", "Button.svelte"),
    ("lang", "scripts/deploy.sh"),
    ("lang", "main.py"),
    ("lang", "lib/helper.go"),
    ("lang", "Program.cs"),
    ("iac", "infra/main.tf"),
    ("iac", "terraform/variables.tfvars"),
    # --- i18n / API specs ---
    ("i18n", "locales/en.po"),
    ("api", "openapi/api.yaml"),
    ("api", "schema.graphql"),
    ("api", "service.proto"),
    # --- Test / story artifacts ---
    ("test", "src/foo.test.ts"),
    ("test", "src/bar.spec.tsx"),
    ("test", "src/ui/Button.stories.ts"),
    ("test", "src/__tests__/helper.test.js"),
    ("test", "e2e/login.cy.ts"),
    ("test", "src/types/global.d.ts"),
    # --- Build / vendor ---
    ("vendor", "node_modules/react/index.js"),
    ("vendor", "dist/bundle.js"),
    ("vendor", "build/output.js"),
    ("vendor", ".next/static/chunks/main.js"),
    ("vendor", "coverage/lcov.info"),
    # --- Generated / fixtures ---
    ("generated", "src/generated/client.ts"),
    ("fixtures", "fixtures/users.json"),
    ("fixtures", "__snapshots__/widget.test.ts.snap"),
    # --- Assets / binaries ---
    ("asset", "public/logo.png"),
    ("asset", "fonts/inter.woff2"),
    ("asset", "archive/release.zip"),
    # --- IDE ---
    ("ide", ".vscode/settings.json"),
    ("ide", ".idea/workspace.xml"),
    ("ide", ".cursor/rules"),
    # --- User-reported false positives ---
    ("reported", "/Users/dev/Desktop/TypingJoy/package.json"),
    ("reported", "/Users/dev/Desktop/TypingJoy/README.md"),
    ("reported", "/Users/dev/Desktop/TypingJoy/docs/reports/benchmark.md"),
    # Compound extensions (v8)
    ("compound", "dist/app.min.js"),
    ("compound", "backup.tar.gz"),
]

GOVERNABLE_SOURCE_MATRIX: list[str] = [
    "src/domain/User.ts",
    "src/domain/services/OrderService.ts",
    "src/core/AppController.ts",
    "src/infrastructure/db/Client.ts",
    "src/ui/components/Button.tsx",
    "lib/utils/format.js",
    "packages/api/src/handler.ts",
    "apps/web/src/main.tsx",
    "src/validation/schema/resolver.ts",
    "src/workflows/runner.ts",
    "src/domain/entities/Order.ts",
]


@pytest.mark.parametrize("category,path", EXEMPT_ARTIFACT_MATRIX, ids=lambda p: f"{p[0]}:{p[1]}")
def test_exempt_artifact_matrix(category: str, path: str):
    assert is_governance_artifact_path(path) is True, f"{category}: {path}"
    assert is_governance_subject(path) is False, f"{category}: {path}"
    assert classify_governance_artifact(path) is not None, f"{category}: {path}"


@pytest.mark.parametrize("path", GOVERNABLE_SOURCE_MATRIX)
def test_governable_source_matrix(path: str):
    assert is_governance_artifact_path(path) is False, path
    assert is_governance_subject(path) is True, path


def test_mixed_batch_partition_large():
    paths = [p for _, p in EXEMPT_ARTIFACT_MATRIX[:20]] + GOVERNABLE_SOURCE_MATRIX[:3]
    exempt, subjects = partition_governance_paths(paths)
    assert len(exempt) == 20
    assert subjects == GOVERNABLE_SOURCE_MATRIX[:3]


@pytest.mark.parametrize(
    "path,expected_category",
    [
        ("README.md", "documentation"),
        ("package.json", "package_manifest"),
        ("prisma/schema.prisma", "database"),
        ("src/foo.test.ts", "test_artifact"),
        (".env.local", "environment"),
        ("node_modules/react/index.js", "vendor_or_build"),
    ],
)
def test_classify_governance_artifact_categories(path: str, expected_category: str):
    assert classify_governance_artifact(path) == expected_category


def test_app_workflows_dir_is_governable_not_ci_workflows():
    """``/workflows/`` must not exempt application source under ``src/workflows/``."""
    assert is_governance_subject("src/workflows/runner.ts") is True
    assert is_governance_artifact_path(".github/workflows/ci.yml") is True


def test_governance_skip_reason_labels():
    assert "documentation" in (governance_skip_reason("docs/guide.md") or "")
    assert governance_skip_reason("src/core/App.ts") is None
