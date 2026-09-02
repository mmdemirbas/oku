#!/usr/bin/env bash
# One entry point for everything this repo does day to day.
#
#   ./ctl                  list the verbs
#   ./ctl --list           the same, one `name<TAB>description` per line
#   ./ctl <verb> --list    what that verb takes
#   ./ctl <verb> ...       run one; extra args pass through
#
# Everything runs through `uv`, so no venv activation is needed.
set -euo pipefail

cd "$(dirname "$0")"
REPO="$PWD"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }

# One glyph and one colour per level, the same five every driver here uses:
# ▸ a step, ✓ it worked, ! worth knowing, ⏸ preconditions not met (exit 75),
# ✗ it failed (exit 1). The contract is
# ajans/docs/reports/driver-scripts-2026-09-02.md.
step() { printf '\033[36m▸\033[0m %s\n' "$*"; }

VERBS="dev	Dev server with live reload (default port 9876)
check	Lint the doctree, or the Python
build	Write dist/{standalone,site}/
clean	Remove dist/
test	pytest, whole or in halves
fmt	ruff format, then ruff check --fix
verify	Everything CI runs: lint, doctree, build, tests
deploy	Ship this repo's kit to the global tool, and to projects
status	Which kit is the global tool building with?
setup	Dependencies, the test browser, and new docs roots"

qualifiers() {
  case "$1" in
    check)  printf '%s\n' \
      "docs	Lint the doctree; --strict fails on warnings too (default)" \
      "code	ruff check + format --check" ;;
    test)   printf '%s\n' \
      "all	The whole suite (default) - add -k, paths, -x …" \
      "fast	Without the browser suite" \
      "browser	Only the headless-chromium suite" ;;
    deploy) printf '%s\n' \
      "tool	Reinstall the global \`oku\` from this repo, --no-cache (default)" \
      "projects	Install, then \`oku build\` in each project directory given" ;;
    setup)  printf '%s\n' \
      "deps	uv sync --extra dev (default)" \
      "browser	Install the chromium Playwright needs" \
      "docs	Scaffold a docs root at <path> (init + starter page)" ;;
    *)      return 1 ;;
  esac
}

list_for() {
  local verb="$1"
  if [ -z "$verb" ]; then printf '%s\n' "$VERBS"; return 0; fi
  qualifiers "$verb" || { red "no qualifiers: $verb"; exit 1; }
}

usage() {
  echo "oku — ./ctl <verb> [qualifier]"
  echo ""
  printf '%s\n' "$VERBS" | while IFS="$(printf '\t')" read -r name why; do
    printf '  %-8s %s\n' "$name" "$why"
  done
  cat <<'EOF'

  What a verb takes:  ./ctl <verb> --list

Anything not listed is forwarded to the CLI, so `./ctl migrate --dry-run`
works too.
EOF
}

# --- author -----------------------------------------------------------------

cmd_new() {
  [ $# -ge 1 ] || { red "usage: ./ctl setup docs <path>"; exit 2; }
  mkdir -p "$1"
  (cd "$1" && uv run --project "$REPO" "$REPO/bin/oku" init)
  green "✓ docs root ready at $1"
}

# --- ship -------------------------------------------------------------------

repo_kit_stamp() {
  sed -n "s/.*__okuKitBuild = '\([^']*\)'.*/\1/p" kit/chrome.js | head -1
}

global_kit_stamp() {
  command -v oku >/dev/null 2>&1 || return 0
  oku --version 2>/dev/null | sed -n 's/.*kit \([^ ·]*\).*/\1/p' | head -1
}

# The kit stamp is hand-bumped and only covers chrome.js, so a change to
# cli.py moves neither it nor the version string — and that is the case
# where a cached wheel goes unnoticed. Seen live: the global tool matched
# the repo on both while running a cli.py without a check that had been
# added to it, so `oku check --strict` reported a tree clean that the
# repo source warns about. The digest covers every shipped file.
repo_src_digest() {
  uv run --project "$REPO" python -c \
    "import sys; sys.path.insert(0, '$REPO/src'); from oku.cli import _tool_digest; print(_tool_digest())" \
    2>/dev/null | tail -1
}

global_src_digest() {
  command -v oku >/dev/null 2>&1 || return 0
  oku --version 2>/dev/null | sed -n 's/.*src \([^ ·]*\).*/\1/p' | head -1
}

# --no-cache is load-bearing: uv reuses the cached wheel when the version
# string has not changed, so a plain --force install silently leaves the
# old kit in place while reporting success.
#
# Which is exactly why this ends by COMPARING the stamps rather than
# printing both and leaving that to the reader. A stale global tool
# reports a successful install and then builds other projects with the
# old kit; the symptom arrives later, somewhere else, as "the kit
# regressed". Whatever goes wrong, it should go wrong here and loudly.
cmd_install() {
  step "installing the global oku from $REPO"
  uv tool install --force --no-cache --from "$REPO" oku
  local want have
  want="$(repo_kit_stamp)"
  have="$(global_kit_stamp)"
  cmd_version
  if [ -z "$have" ]; then
    red "✗ installed, but the global oku does not report a kit build."
    red "  Is ~/.local/bin on your PATH?"
    exit 1
  fi
  if [ "$want" != "$have" ]; then
    red "✗ the global oku is still on kit $have, this repo is on $want."
    red "  A cached wheel was reused. Try: uv cache clean && ./ctl deploy"
    exit 1
  fi
  local want_src have_src
  want_src="$(repo_src_digest)"
  have_src="$(global_src_digest)"
  if [ -n "$want_src" ] && [ "$want_src" != "$have_src" ]; then
    red "✗ the global oku ships different code: src $have_src, this repo is $want_src."
    red "  The kit stamp matches, so this is a CLI-only drift the stamp cannot see."
    red "  Try: uv cache clean && ./ctl deploy"
    exit 1
  fi
  green "✓ global oku is building with this repo's kit ($want) and code ($want_src)"
}

cmd_version() {
  printf '  repo   kit %s · src %s\n' "$(repo_kit_stamp)" "$(repo_src_digest)"
  if command -v oku >/dev/null 2>&1; then
    printf '  global %s\n' "$(oku --version 2>/dev/null | tr '\n' ' ')"
  else
    printf '  global not installed — ./ctl deploy\n'
  fi
}

cmd_rebuild() {
  [ $# -ge 1 ] || { red "usage: ./ctl deploy projects <project-dir>..."; exit 2; }
  cmd_install
  for dir in "$@"; do
    step "building $dir"
    (cd "$dir" && oku build)
  done
}

# --- develop ----------------------------------------------------------------

cmd_lint() {
  uv run ruff check .
  uv run ruff format --check .
}

cmd_verify() {
  step "lint"; cmd_lint
  step "doctree"; uv run bin/oku check --strict
  step "build"; uv run bin/oku build >/dev/null
  step "tests"; uv run pytest -q
  green "✓ all gates pass"
}

# --- dispatch ---------------------------------------------------------------

cmd="${1:-}"; shift || true

case "$cmd" in
  ''|-h|--help|help) usage; exit 0 ;;
  --list)            list_for ""; exit 0 ;;
esac

# Only in first position: further along, `--list` may be a flag of the tool
# being forwarded to.
[ "${1:-}" = "--list" ] && { list_for "$cmd"; exit 0; }

case "$cmd" in
  dev)   uv run bin/oku serve "$@" ;;
  check)
    case "${1:-docs}" in
      docs) shift 2>/dev/null || true; uv run bin/oku check "$@" ;;
      code) cmd_lint ;;
      *)    uv run bin/oku check "$@" ;;   # a flag, not a qualifier
    esac
    ;;
  build) uv run bin/oku build "$@" ;;
  clean) uv run bin/oku clean "$@" ;;
  test)
    case "${1:-all}" in
      all)     shift 2>/dev/null || true; uv run pytest "$@" ;;
      fast)    shift; uv run pytest -q --ignore=src/oku_tests/browser "$@" ;;
      browser) shift; uv run pytest -q src/oku_tests/browser "$@" ;;
      *)       uv run pytest "$@" ;;       # a flag or a path, not a qualifier
    esac
    ;;
  fmt)
    uv run ruff format .
    uv run ruff check --fix .
    ;;
  verify) cmd_verify ;;
  deploy)
    case "${1:-tool}" in
      tool)     cmd_install ;;
      projects) shift; cmd_rebuild "$@" ;;
      *)        red "unknown: ./ctl deploy $1  (./ctl deploy --list)"; exit 1 ;;
    esac
    ;;
  status) cmd_version ;;
  setup)
    case "${1:-deps}" in
      deps)    uv sync --extra dev ;;
      browser) uv run playwright install chromium ;;
      docs)    shift; cmd_new "$@" ;;
      *)       red "unknown: ./ctl setup $1  (./ctl setup --list)"; exit 1 ;;
    esac
    ;;
  *) uv run bin/oku "$cmd" "$@" ;;
esac
