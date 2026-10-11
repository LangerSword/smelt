#!/bin/sh
# smelt installer — POSIX sh, set -eu, no sudo, no piping into other shells.
# Prints what it will do before doing it. Safe to rerun.
#
# Flags: --dry-run --yes --version X --uninstall --with-tui
#
# Untested on macOS. Tested in Docker (Ubuntu, Debian) — see site/README.md.
set -eu

REPO="https://github.com/LangerSword/smelt.git"
DEFAULT_VERSION="v0.6-furnace"
PKG="smelt-rs"
DRY_RUN=0
ASSUME_YES=0
VERSION="$DEFAULT_VERSION"
UNINSTALL=0
WITH_TUI=0

log()  { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "    [dry-run] $*"
  else
    log "    \$ $*"
    "$@"
  fi
}

ask() {
  if [ "$ASSUME_YES" -eq 1 ] || [ "$DRY_RUN" -eq 1 ]; then return 0; fi
  printf '%s [y/N] ' "$1"
  read -r ans
  case "$ans" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)   DRY_RUN=1 ;;
    --yes|-y)    ASSUME_YES=1 ;;
    --version)   shift; VERSION="${1:?--version needs a value}" ;;
    --uninstall) UNINSTALL=1 ;;
    --with-tui)  WITH_TUI=1 ;;
    -h|--help)
      log "smelt installer"
      log "  --dry-run      print actions, change nothing"
      log "  --yes          assume yes to prompts"
      log "  --version X    git tag/commit to install (default $DEFAULT_VERSION)"
      log "  --uninstall    remove smelt"
      log "  --with-tui     also install the Furnace TUI binary"
      exit 0 ;;
    *) die "unknown flag: $1" ;;
  esac
  shift
done

# ---- platform detection ----
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
  Linux|Darwin) ;;
  *) die "unsupported OS: $OS (only Linux and macOS are supported)" ;;
esac
case "$ARCH" in
  x86_64|arm64|aarch64) ;;
  *) die "unsupported arch: $ARCH (only x86_64 and arm64/aarch64 are supported)" ;;
esac
log "platform: $OS $ARCH"

# ---- uninstall ----
if [ "$UNINSTALL" -eq 1 ]; then
  step "uninstall"
  run uv tool uninstall "$PKG" || warn "smelt was not installed via uv tool"
  exit 0
fi

# ---- checks ----
step "checking prerequisites"

HAVE_PY=0
if command -v python3 >/dev/null 2>&1; then
  PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"
  PYOK="$(python3 -c 'import sys;print(1 if sys.version_info>=(3,11) else 0)' 2>/dev/null || echo 0)"
  if [ "$PYOK" = "1" ]; then HAVE_PY=1; log "  python $PYV ok"; else warn "python $PYV found but 3.11+ required"; fi
else
  warn "python3 not found"
fi
if [ "$HAVE_PY" -eq 0 ]; then
  warn "python 3.11+ is recommended; smelt targets 3.11+"
fi

HAVE_UV=0
if command -v uv >/dev/null 2>&1; then HAVE_UV=1; log "  uv $(uv --version 2>/dev/null | head -1) ok"; else warn "uv not found"; fi

HAVE_CARGO=0
if command -v cargo >/dev/null 2>&1; then HAVE_CARGO=1; log "  cargo ok"; else warn "cargo not found (needed to build the Rust extension)"; fi

HAVE_MATURIN=0
if command -v maturin >/dev/null 2>&1; then HAVE_MATURIN=1; log "  maturin ok"; else warn "maturin not found (needed to build the extension)"; fi

HAVE_GO=0
if command -v go >/dev/null 2>&1; then HAVE_GO=1; log "  go ok"; fi

# ---- offer installs (never silent) ----
if [ "$HAVE_UV" -eq 0 ]; then
  step "install uv"
  log "  uv is the Python package manager smelt uses to install itself."
  if ask "  Install uv from its official installer (curl https://astral.sh/uv/install.sh)?"; then
    if [ "$DRY_RUN" -eq 1 ]; then
      log "    [dry-run] curl -LsSf https://astral.sh/uv/install.sh | sh"
    else
      curl -LsSf https://astral.sh/uv/install.sh | sh
      . "$HOME/.local/bin/env" 2>/dev/null || . "$HOME/.cargo/env" 2>/dev/null || true
      HAVE_UV=1
    fi
  else
    die "uv is required. Install it manually: https://docs.astral.sh/uv/"
  fi
fi

if [ "$HAVE_CARGO" -eq 0 ] || [ "$HAVE_MATURIN" -eq 0 ]; then
  step "rust toolchain"
  log "  cargo/rustc build the Rust extension; maturin packages it into a Python wheel."
  log "  smelt's verify/bench steps never need the network, but a model run builds an extension."
  if ask "  Install the Rust toolchain via rustup (https://sh.rustup.rs)?"; then
    if [ "$DRY_RUN" -eq 1 ]; then
      log "    [dry-run] curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
    else
      curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
      . "$HOME/.cargo/env" 2>/dev/null || true
    fi
    if ask "  Install maturin (pip install maturin)?"; then
      run python3 -m pip install --user maturin || run uv tool install maturin
    fi
  else
    log "  Skipping. smelt installs, but 'smelt run' will fail at the build step without cargo."
  fi
fi

# ---- install smelt ----
step "install smelt $PKG"
log "  Source preference: PyPI (if published) else GitHub at pinned $VERSION."

SOURCE=""
if [ "$DRY_RUN" -eq 0 ] && uv tool install "$PKG" >/dev/null 2>&1; then
  SOURCE="pypi"
  log "  installed from PyPI"
else
  log "  PyPI package not available yet (or dry-run) — installing from GitHub at $VERSION"
  SOURCE="github@$VERSION"
  run uv tool install "git+${REPO}@${VERSION}"
fi
log "  source used: $SOURCE"

# ---- TUI ----
if [ "$WITH_TUI" -eq 1 ]; then
  step "furnace TUI (--with-tui)"
  TUI_BIN="furnace-$OS-$ARCH"
  TUI_URL="https://github.com/LangerSword/smelt/releases/latest/download/$TUI_BIN"
  TUI_DEST="$HOME/.local/bin/furnace"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "    [dry-run] download $TUI_URL -> $TUI_DEST + verify sha256"
  else
    if curl -fsSL "$TUI_URL" -o "$TUI_DEST" 2>/dev/null && curl -fsSL "$TUI_URL.sha256" 2>/dev/null | sha256sum -c - 2>/dev/null; then
      chmod +x "$TUI_DEST"
      log "  furnace installed at $TUI_DEST (checksum verified)"
    elif [ "$HAVE_GO" -eq 1 ]; then
      log "  no release binary — building from source with go"
      tmp="$(mktemp -d)"
      git clone --depth 1 "$REPO" "$tmp" >/dev/null 2>&1
      (cd "$tmp/tui" && go build -o "$TUI_DEST" .)
      rm -rf "$tmp"
      log "  furnace built at $TUI_DEST"
    else
      warn "no release binary for $TUI_BIN and no Go toolchain — skipping TUI"
    fi
  fi
fi

# ---- verify ----
step "verify"
if [ "$DRY_RUN" -eq 1 ]; then
  log "    [dry-run] smelt doctor"
else
  if command -v smelt >/dev/null 2>&1; then
    smelt doctor || warn "smelt doctor reported issues (see above)"
    log ""
    log "next step:  smelt run examples/demo/run_length.py:rle_encode --provider gemini"
  else
    warn "smelt not on PATH — you may need to restart your shell or add ~/.local/bin"
  fi
fi

step "done"
log "  Re-run this script any time; it is idempotent."
