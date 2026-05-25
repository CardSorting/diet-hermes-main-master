FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c543b6c4f23a5f2df22866bd7857e5d304b67a564f4feab6ac22044dde719b AS uv_source
FROM tianon/gosu:1.19-trixie@sha256:3b176695959c71e123eb390d427efc665eeb561b1540e82679c15e992006b8b9 AS gosu_source
FROM debian:13.4

# Disable Python stdout buffering to ensure logs are printed immediately
ENV PYTHONUNBUFFERED=1

# Store Playwright browsers outside the volume mount so the build-time
# install survives the /opt/data volume overlay at runtime.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/hermes/.playwright

# Install system dependencies in one layer, clear APT cache
# tini reaps orphaned zombie processes (MCP stdio subprocesses, git, bun, etc.)
# that would otherwise accumulate when hermes runs as PID 1. See #15012.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential curl nodejs npm python3 ripgrep ffmpeg gcc python3-dev libffi-dev procps git openssh-client docker-cli tini && \
    rm -rf /var/lib/apt/lists/*

# Non-root user for runtime; UID can be overridden via HERMES_UID at runtime
RUN useradd -u 10000 -m -d /opt/data hermes

COPY --chmod=0755 --from=gosu_source /gosu /usr/local/bin/
COPY --chmod=0755 --from=uv_source /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

WORKDIR /opt/hermes

# ---------- Layer-cached dependency install ----------
# Copy only package manifests first so npm install + Playwright are cached
# unless the lockfiles themselves change.
#
COPY package.json package-lock.json ./
COPY web/package.json web/package-lock.json web/
COPY herm-tui/package.json herm-tui/bun.lock herm-tui/

# Force install-links=false so file: workspace deps stay symlinks (not copies).
# Debian's older Node package manager defaults to install-links=true, which
# makes node_modules/.package-lock.json disagree with the root lockfile and
# triggers a spurious reinstall on every TUI launch (EACCES on root-owned trees).
# That disagreement trips the TUI launcher's `_tui_need_bun_install()`
# check on every startup and triggers a runtime install that then
# fails with EACCES (node_modules/ is root-owned from build time).
RUN /usr/bin/npm config set install-links false \
    && curl -fsSL https://bun.sh/install | bash \
    && /usr/bin/npm install --prefer-offline --no-audit \
    && npx playwright install --with-deps chromium --only-shell \
    && (cd web && /usr/bin/npm install --prefer-offline --no-audit) \
    && (cd herm-tui && /root/.bun/bin/bun install --frozen-lockfile) \
    && /usr/bin/npm cache clean --force

ENV PATH="/root/.bun/bin:${PATH}"

# ---------- Layer-cached Python dependency install ----------
# Copy only pyproject.toml + uv.lock so the Python dep resolve + wheel
# download + native-extension compile layer is cached unless those inputs
# change.  Before this split the Python install sat after `COPY . .`, so
# every source-only commit re-did ~4-5 min of dep work on cold builds.
#
# README.md is referenced by pyproject.toml's `readme =` field, but it's
# excluded from the build context by .dockerignore's `*.md`.  uv's build
# frontend stats the readme path during dep resolution, so we `touch` an
# empty placeholder — the real README is restored by `COPY . .` below.
#
# `uv sync --frozen --no-install-project --extra all --extra messaging`
# installs the deps reachable through the composite `[all]` extra
# (handpicked set intended for the production image), plus gateway
# messaging adapters that should work in the published image without a
# first-boot lazy install.  We do NOT use `--all-extras`:
# that would pull in `[rl]` (atroposlib + tinker + torch + wandb from
# git), `[yc-bench]` (another git dep), and `[termux-all]` (Android
# redundancy), none of which belong in the published container.
#
# The editable link is created after the source copy below.
COPY pyproject.toml uv.lock ./
RUN touch ./README.md
RUN uv sync --frozen --no-install-project --extra all --extra messaging

# ---------- Source code ----------
# .dockerignore excludes node_modules, so the installs above survive.
COPY --chown=hermes:hermes . .

# Build browser dashboard and terminal UI assets.
RUN cd web && /usr/bin/npm run build && cd ../herm-tui && bun run build

# ---------- Permissions ----------
# Make install dir world-readable so any HERMES_UID can read it at runtime.
# The venv needs to be traversable too.
# node_modules trees additionally need to be writable by the hermes user
# so the runtime `bun install` triggered by _tui_need_bun_install() in
# hermes_cli/main.py succeeds (see #18800). /opt/hermes/web is build-time
# only (HERMES_WEB_DIST points at hermes_cli/web_dist) and is intentionally
# not chowned here.
# The .venv MUST remain hermes-writable so lazy_deps.py can install
# remaining optional platform packages and future pin bumps at first use.
# Without this, `uv pip install` fails with EACCES and adapters silently
# fail to load.  See tools/lazy_deps.py.
USER root
RUN chmod -R a+rX /opt/hermes && chown -R hermes:hermes /opt/hermes/.venv /opt/hermes/herm-tui /opt/hermes/node_modules
# Start as root so the entrypoint can usermod/groupmod + gosu.
# If HERMES_UID is unset, the entrypoint drops to the default hermes user (10000).

# ---------- Link hermes-agent itself (editable) ----------
# Deps are already installed in the cached layer above; `--no-deps` makes
# this a fast (~1s) egg-link creation with no resolution or downloads.
RUN uv pip install --no-cache-dir --no-deps -e "."

# ---------- Runtime ----------
ENV HERMES_WEB_DIST=/opt/hermes/hermes_cli/web_dist
ENV HERMES_HOME=/opt/data
ENV PATH="/opt/data/.local/bin:${PATH}"
RUN mkdir -p /opt/data
VOLUME [ "/opt/data" ]
ENTRYPOINT [ "/usr/bin/tini", "-g", "--", "/opt/hermes/docker/entrypoint.sh" ]
