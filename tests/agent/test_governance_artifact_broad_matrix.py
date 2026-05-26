"""Second-tier broad artifact matrix — edge cases and ecosystem coverage."""

from __future__ import annotations

import pytest

from agent.governance_exemptions import (
    GOVERNANCE_POLICY_VERSION,
    _is_editor_rc_basename,
    _is_lockfile_basename,
    is_governance_artifact_path,
    is_governance_subject,
)

# Broad exempt paths — must stay non-governable after policy changes.
BROAD_EXEMPT_MATRIX: list[tuple[str, str]] = [
    # Lockfile heuristics (not all in basename set)
    ("lock", "foo.lock"),
    ("lock", "packages/lib/poetry.lock"),
    ("lock", "Gemfile.lock"),
    ("lock", "mix.lock"),
    ("lock", "Podfile.lock"),
    # Editor rc heuristics
    ("rc", ".prettierrc"),
    ("rc", ".eslintrc"),
    ("rc", ".stylelintrc.json"),
    ("rc", "tools/biome.rc.yaml"),
    # Monorepo / build
    ("mono", "mise.toml"),
    ("mono", "flake.nix"),
    ("mono", "buf.yaml"),
    ("mono", "turbo.json"),
    ("mono", ".turbo/cache/meta.json"),
    ("mono", ".changeset/config.json"),
    ("mono", "rush.json"),
    # Cloud / deploy
    ("cloud", "serverless.yml"),
    ("cloud", "fly.toml"),
    ("cloud", "render.yaml"),
    ("cloud", "pulumi/Pulumi.dev.yaml"),
    ("cloud", "skaffold.yaml"),
    # Mobile
    ("mobile", "pubspec.yaml"),
    ("mobile", "android/app/google-services.json"),
    ("mobile", "ios/Runner/Info.plist"),
    ("mobile", "capacitor.config.ts"),
    # Security / SBOM
    ("security", "sbom.json"),
    ("security", "cyclonedx.json"),
    ("security", ".snyk"),
    ("security", "security.txt"),
    # API / proto trees
    ("api", "proto/user/v1/user.proto"),
    ("api", "protos/events/order_created.proto"),
    ("api", "contracts/openapi/v2/petstore.yaml"),
    ("api", "schemas/json/user.schema.json"),
    # Design / CMS
    ("design", "design-tokens/colors.json"),
    ("design", "cms/sanity.config.ts"),
    # Mocks / test support
    ("mocks", "mocks/handlers.ts"),
    ("mocks", "__mocks__/fs.ts"),
    ("mocks", "stubs/logger.ts"),
    ("mocks", "test-utils/render.tsx"),
    # Observability
    ("ops", "grafana/dashboards/api.json"),
    ("ops", "prometheus/alerts.yml"),
    # More languages
    ("lang", "lib/main.nim"),
    ("lang", "src/app.zig"),
    ("lang", "app/Main.dart"),
    ("lang", "lib/service.ex"),
    ("lang", "policy/auth.rego"),
    ("lang", "deploy/job.nomad"),
    # Markup / BDD
    ("markup", "pages/about.astro"),
    ("markup", "tests/login.feature"),
    ("markup", "docs/guide.asciidoc"),
    # Temp / logs
    ("tmp", "tmp/build.log"),
    ("tmp", "logs/agent.log"),
    ("tmp", ".cache/vite/deps/_metadata.json"),
    # CI segment prefixes (no leading slash)
    ("ci", ".github/dependabot.yml"),
    ("ci", ".gitlab/issue_templates/bug.md"),
    ("ci", ".circleci/config.yml"),
  # Integration / smoke test suffixes
    ("test", "api/health.integration.ts"),
    ("test", "checkout.smoke.ts"),
    ("test", "pact/consumer.contract.ts"),
    # Config module variants
    ("config", "vitest.config.mts"),
    ("config", "rollup.config.cts"),
    ("config", "eslint.config.mjs"),
    # Assistant / editor
    ("editor", ".cursorindexingignore"),
    ("editor", "copilot-instructions.md"),
    ("editor", ".windsurfrules"),
    # Hermes-specific
    ("hermes", "optional-skills/github/foo/SKILL.md"),
    ("hermes", "AGENTS.md"),
    ("hermes", "uv.lock"),
    # Assets
    ("asset", "static/hero.webp"),
    ("asset", "media/intro.avif"),
    ("asset", "certs/server.pem"),
]

# Must remain governable — guard against over-broad markers.
MUST_REMAIN_GOVERNABLE: list[str] = [
    "src/domain/User.ts",
    "src/application/CreateOrder.ts",
    "src/infrastructure/persistence/Repository.ts",
    "src/ui/Button.tsx",
    "src/workflows/runner.ts",
    "src/skills/SkillRegistry.ts",
    "src/graphql/resolvers/Query.ts",
    "src/content/models/Article.ts",
    "src/schema/validation/rules.ts",
    "packages/core/src/index.ts",
    "lib/format.js",
]


@pytest.mark.parametrize("category,path", BROAD_EXEMPT_MATRIX, ids=lambda p: f"{p[0]}:{p[1]}")
def test_broad_exempt_matrix(category: str, path: str):
    assert is_governance_artifact_path(path), f"{category}: {path}"
    assert is_governance_subject(path) is False, f"{category}: {path}"


@pytest.mark.parametrize("path", MUST_REMAIN_GOVERNABLE)
def test_must_remain_governable(path: str):
    assert is_governance_artifact_path(path) is False, path
    assert is_governance_subject(path) is True, path


@pytest.mark.parametrize(
    "basename,expected",
    [
        ("yarn.lock", True),
        ("custom.lock", True),
        ("foo-lock.json", True),
        ("package.json", False),
    ],
)
def test_lockfile_heuristic(basename: str, expected: bool):
    assert _is_lockfile_basename(basename) is expected


@pytest.mark.parametrize(
    "basename,expected",
    [
        (".prettierrc", True),
        (".eslintrc", True),
        (".eslintrc.json", True),
        ("biome.rc.yaml", True),
        ("package.json", False),
    ],
)
def test_editor_rc_heuristic(basename: str, expected: bool):
    assert _is_editor_rc_basename(basename) is expected


def test_policy_version_at_least_8():
    assert GOVERNANCE_POLICY_VERSION >= 9
