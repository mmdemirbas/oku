#!/usr/bin/env bash
# One entry point for everything this repo does day to day.
#
#   ./ctl                  the verbs, one `name<TAB>description` per line
#   ./ctl <verb> --list    that verb's targets
#   ./ctl <verb> ...       run one; extra args pass through
#
# The verbs are declared in ajans.toml and each is an op_ function below; the
# block at the end lists, dispatches and checks them (contract 2:
# ajans/docs/project-contract.md). A bare verb with targets is its default:
# `./ctl test` is `test all`, `./ctl deploy` is `deploy tool`.
#
# Everything runs through `uv`, so no venv activation is needed.
set -euo pipefail

cd "$(dirname "$0")"
REPO="$PWD"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }

# One glyph and one colour per level, the same five every driver here uses:
# ▸ a step, ✓ it worked, ! worth knowing, ⏸ preconditions not met (exit 75),
# ✗ it failed (exit 1).
step() { printf '\033[36m▸\033[0m %s\n' "$*"; }

# --- author -----------------------------------------------------------------

op_dev() { uv run bin/oku serve "$@"; }

# Bare `check` lints the doctree (`check docs` lands here too); a flag is the
# CLI's, not a target. `check code` is ruff, below.
op_check() {
  if [ "${1:-}" = docs ]; then shift; fi
  uv run bin/oku check "$@"
}

op_build() { uv run bin/oku build "$@"; }
op_clean() { uv run bin/oku clean "$@"; }

# The CLI's other verbs, reached through ctl as they always were.
op_migrate() { uv run bin/oku migrate "$@"; }
op_vendor() { uv run bin/oku vendor "$@"; }
op_spec() { uv run bin/oku spec "$@"; }
op_preview() { uv run bin/oku preview "$@"; }

op_setup() {
  case "${1:-deps}" in
    deps) uv sync --extra dev ;;
    *)    red "unknown: ./ctl setup $1  (./ctl setup --list)"; exit 64 ;;
  esac
}
op_setup_browser() { uv run playwright install chromium "$@"; }


op_setup_docs() {
  [ $# -ge 1 ] || { red "usage: ./ctl setup docs <path>"; exit 2; }
  mkdir -p "$1"
  (cd "$1" && uv run --project "$REPO" "$REPO/bin/oku" init)
  green "✓ docs root ready at $1"
}

# --- ship -------------------------------------------------------------------

op_deploy() {
  case "${1:-tool}" in
    tool) install_tool ;;
    *)    red "unknown: ./ctl deploy $1  (./ctl deploy --list)"; exit 64 ;;
  esac
}

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
install_tool() {
  step "installing the global oku from $REPO"
  # The extras are the tool's capabilities, not options: without `verify`
  # every other project's session finds `oku verify` "not installed" and
  # skips the browser check; without `search` dist/site ships no index.
  uv tool install --force --no-cache "oku[search,verify] @ $REPO"
  install_verify_browser
  # The vendor cache (fonts, mermaid, Prism) lives inside the tool's own
  # site-packages, which the reinstall just replaced.
  step "refilling the global oku's vendor cache"
  (cd "$REPO" && oku vendor) || { red "✗ oku vendor failed; built pages will lack fonts offline."; exit 1; }
  local want have
  want="$(repo_kit_stamp)"
  have="$(global_kit_stamp)"
  show_version
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
  if [ -z "$want_src" ]; then
    red "✗ could not compute this repo's code digest, so code drift cannot be checked."
    red "  Run: uv run --project $REPO python -c 'from oku.cli import _tool_digest; print(_tool_digest())'"
    exit 1
  fi
  if [ "$want_src" != "$have_src" ]; then
    red "✗ the global oku ships different code: src $have_src, this repo is $want_src."
    red "  The kit stamp matches, so this is a CLI-only drift the stamp cannot see."
    red "  Try: uv cache clean && ./ctl deploy"
    exit 1
  fi
  if ! "$(global_tool_python)" -c 'import playwright, pagefind' 2>/dev/null; then
    red "✗ the global oku is missing playwright or pagefind, so oku verify or"
    red "  the search index will not run outside this repo."
    exit 1
  fi
  green "✓ global oku is building with this repo's kit ($want) and code ($want_src)"
}

global_tool_python() {
  printf '%s/oku/bin/python\n' "$(uv tool dir)"
}

# The playwright the tool carries pins one chromium revision, and a
# browser fetched for another venv's playwright does not satisfy it.
# Idempotent: a revision already in the cache is not downloaded again.
install_verify_browser() {
  step "fetching the chromium the global oku's playwright expects"
  "$(global_tool_python)" -m playwright install chromium
}

show_version() {
  printf '  repo   kit %s · src %s\n' "$(repo_kit_stamp)" "$(repo_src_digest)"
  if command -v oku >/dev/null 2>&1; then
    printf '  global %s\n' "$(oku --version 2>/dev/null | tr '\n' ' ')"
  else
    printf '  global not installed — ./ctl deploy\n'
  fi
}

op_deploy_projects() {
  [ $# -ge 1 ] || { red "usage: ./ctl deploy projects <project-dir>..."; exit 2; }
  install_tool
  for dir in "$@"; do
    step "building $dir"
    (cd "$dir" && oku build)
  done
}

# The plugin talks to the global oku over a preview protocol, so an oku
# behind this checkout is brought up to it first. One already current is
# left alone: reinstalling it costs a minute and changes nothing. Which
# IDEs, where their plugins go and whether each can load the plugin is
# ide/intellij/install.py's business; its exit status is this one's.
op_deploy_ide() {
  if [ "$(repo_kit_stamp)" = "$(global_kit_stamp)" ] && [ "$(repo_src_digest)" = "$(global_src_digest)" ]; then
    step "the global oku is this checkout's (kit $(repo_kit_stamp)); leaving it as it is"
  else
    step "the global oku is not this checkout's; deploying it first"
    install_tool
  fi
  uv run python ide/intellij/install.py install "$@"
}

op_status() {
  show_version
  printf '  ides\n'
  uv run python ide/intellij/install.py list | sed 's/^/  /'
}

# --- develop ----------------------------------------------------------------

op_check_code() {
  uv run ruff check .
  uv run ruff format --check .
}

op_verify() {
  step "ajans.toml and ctl name the same operations"; ./ctl --check
  step "lint"; op_check_code
  step "doctree"; uv run bin/oku check --strict
  step "build"; uv run bin/oku build >/dev/null
  step "tests"; uv run pytest -q
  green "✓ all gates pass"
}

# Bare `test` is the whole suite (`test all` lands here too); a flag or a path
# goes to pytest.
op_test() {
  if [ "${1:-}" = all ]; then shift; fi
  uv run pytest "$@"
}
op_test_fast() { uv run pytest -q --ignore=src/oku_tests/browser "$@"; }
op_test_browser() { uv run pytest -q src/oku_tests/browser "$@"; }

op_fmt() {
  uv run ruff format .
  uv run ruff check --fix .
}

# >>> ajans runtime 3 >>>
# Written by `ajans contract sync`; edits here are overwritten. The operations
# are declared in ajans.toml and implemented above as op_<verb>[_<target>].

# Where this file is. A relative path was relative to where ctl was started,
# and the driver may have changed directory since - usually into its own, with
# `cd "$(dirname "$0")"` - so it is tried against here, then against where the
# last cd came from, and failing both the directory the driver changed into.
# A function rather than inline: bash 3.2 cannot parse a `case` inside `$(...)`.
_ajans_where() {
	local src="${BASH_SOURCE[0]}" base
	case "$src" in
		/*) ;;
		*)
			for base in "$PWD" "${OLDPWD:-}"; do
				if [[ -n "$base" && -f "$base/$src" ]]; then
					src="$base/$src"
					break
				fi
			done
			;;
	esac
	case "$src" in
		/*) ;;
		*) src="$PWD/${src##*/}" ;;
	esac
	(cd "$(dirname "$src")" && pwd)
}
_ajans_root="$(_ajans_where)"

_ajans_fn() {
	local name="op_$*"
	name="${name// /_}"
	name="${name//-/_}"
	printf '%s' "${name//./_}"
}

# Reads ajans.toml with awk. Modes: list [verb], keys.
#
# awk and bash ship with the OS, so the listing and the check need nothing
# a package manager can move: version 2 looked for a python3 with tomllib,
# and one Homebrew upgrade was enough to lose it. /usr/bin/awk first, so a
# Homebrew gawk ahead of it on PATH is not what runs.
#
# It reads TOML as manifests are written - each operation an
# [operations.<key>] table, its summary a one-line string - and steps over
# every other value, multi-line ones included. A manifest written otherwise
# (dotted operation keys, inline operation tables, a multi-line summary) is
# refused with its line rather than read wrong.
_ajans_toml() {
	local awk=/usr/bin/awk
	if [[ ! -x "$awk" ]]; then awk="awk"; fi
	if [[ ! -f "$_ajans_root/ajans.toml" ]]; then
		printf '✗ no ajans.toml beside %s\n' "$_ajans_root/ctl" >&2
		return 66
	fi
	# shellcheck disable=SC2016 # the program is awk: its $ are fields, not expansions
	_AJANS_MODE="$1" _AJANS_VERB="${2:-}" LC_ALL=C "$awk" '
BEGIN { SQ = "\047"; DQ = "\""; mode = ENVIRON["_AJANS_MODE"]; verb = ENVIRON["_AJANS_VERB"] }
function fail(why) { if (BAD == "") BAD = "ajans.toml:" NR ": " why; exit }
function ws() { while (P <= length(L) && index(" \t", substr(L, P, 1))) P++ }
function at(s) { return substr(L, P, length(s)) == s }
function hex(h,   i, d, v) {
	for (i = 1; i <= length(h); i++) {
		d = index("0123456789abcdef", tolower(substr(h, i, 1)))
		if (d == 0) fail("an escape that is not hex: \\u" h)
		v = v * 16 + d - 1
	}
	return v
}
function utf8(c) {
	if (c < 128) return sprintf("%c", c)
	if (c < 2048) return sprintf("%c%c", 192 + int(c / 64), 128 + c % 64)
	if (c < 65536) return sprintf("%c%c%c", 224 + int(c / 4096), 128 + int(c / 64) % 64, 128 + c % 64)
	return sprintf("%c%c%c%c", 240 + int(c / 262144), 128 + int(c / 4096) % 64, 128 + int(c / 64) % 64, 128 + c % 64)
}
# A one-line "basic" string from P, its escapes decoded into S.
function basic(   c, n) {
	S = ""
	for (P++; P <= length(L); P++) {
		c = substr(L, P, 1)
		if (c == DQ) { P++; return }
		if (c != "\\") { S = S c; continue }
		c = substr(L, ++P, 1)
		if (c == "u" || c == "U") {
			n = c == "u" ? 4 : 8
			if (length(substr(L, P + 1, n)) < n) fail("a \\" c " escape cut short")
			S = S utf8(hex(substr(L, P + 1, n)))
			P += n
		} else if (index("btnfr" DQ "\\", c) == 0) fail("an escape TOML does not have: \\" c)
		else S = S (c == "b" ? "\b" : c == "t" ? "\t" : c == "n" ? "\n" : c == "f" ? "\f" : c == "r" ? "\r" : c)
	}
	fail("a string that does not end on its line")
}
# A one-line literal string from P into S.
function literal(   e) {
	e = index(substr(L, P + 1), SQ)
	if (e == 0) fail("a string that does not end on its line")
	S = substr(L, P + 1, e - 1)
	P += e + 1
}
# One key: bare, "basic" or literal, into S. 0 when there is none.
function part(   s) {
	ws()
	if (at(DQ)) { basic(); return 1 }
	if (at(SQ)) { literal(); return 1 }
	for (s = P; P <= length(L) && substr(L, P, 1) ~ /[A-Za-z0-9_-]/; P++);
	S = substr(L, s, P - s)
	return P > s
}
# A dotted key into K[1..KN].
function path() {
	KN = 0
	if (!part()) return 0
	K[++KN] = S
	for (ws(); at("."); ws()) {
		P++
		if (!part()) return 0
		K[++KN] = S
	}
	return 1
}
# Past a value, or to the end of its line when it goes on: ML (a multi-line
# string still open) and DEPTH (arrays and tables still open) carry on to the
# next line, where no key or header can begin.
function skip(   c) {
	while (P <= length(L)) {
		if (ML != "") {
			if (ML == DQ && at("\\")) { P += 2; continue }
			if (!at(ML ML ML)) { P++; continue }
			for (P += 3; at(ML); P++);
			ML = ""
			if (DEPTH == 0) return
			continue
		}
		c = substr(L, P, 1)
		if (at(DQ DQ DQ) || at(SQ SQ SQ)) { ML = c; P += 3; continue }
		if (c == DQ || c == SQ) {
			if (c == DQ) basic(); else literal()
			if (DEPTH == 0) return
			continue
		}
		if (c == "#") return
		if (c == "[" || c == "{") DEPTH++
		else if (c == "]" || c == "}") { if (--DEPTH == 0) { P++; return } }
		else if (DEPTH == 0 && index(" \t,", c)) return
		P++
	}
}
# A summary: a one-line string.
function text() {
	if (at(DQ DQ DQ) || at(SQ SQ SQ)) fail("a multi-line string; a summary is read on one line")
	if (at(DQ)) basic()
	else if (at(SQ)) literal()
	else fail("a summary that is not a string")
	return S
}
function header(   arrays) {
	P++
	arrays = at("[")
	if (arrays) P++
	if (!path()) fail("a table header it cannot read")
	ws()
	if (!at(arrays ? "]]" : "]")) fail("a table header with no closing bracket")
	if (K[1] != "operations" && K[1] != "verbs") { TABLE = "other"; return }
	if (arrays) fail("an array of tables; each operation is its own [operations.<key>] table")
	if (K[1] == "verbs" && KN > 1) fail("a table under [verbs]; each verb there is a string")
	if (KN == 1) { TABLE = K[1]; return }
	if (!(K[2] in SEEN)) { SEEN[K[2]] = 1; OPS[++N] = K[2] }
	OP = K[2]
	TABLE = KN == 2 ? "op" : "below"
}
function keyval() {
	if (!path()) fail("a line that is neither a [table] nor key = value")
	ws()
	if (!at("=")) fail("a key with no = after it")
	P++
	ws()
	if (TABLE == "op" && KN == 1 && K[1] == "summary") SUMMARY[OP] = text()
	else if (TABLE == "verbs" && KN == 1) VERBS[K[1]] = text()
	else if (TABLE == "operations" || TABLE == "verbs" || (TABLE == "" && (K[1] == "operations" || K[1] == "verbs")))
		fail("operations written as dotted keys or inline tables; each is read as its own [operations.<key>] table")
	else skip()
}
{
	L = $0
	sub(/\r$/, "", L)
	P = 1
	if (ML != "" || DEPTH > 0) { skip(); next }
	ws()
	if (P > length(L) || at("#")) next
	if (at("[")) header()
	else keyval()
}
END {
	if (BAD == "" && (ML != "" || DEPTH > 0)) BAD = "ajans.toml: a value that never ends"
	if (BAD != "") { printf "✗ %s\n", BAD > "/dev/stderr"; exit 65 }
	for (i = 1; i <= N; i++) {
		key = OPS[i]
		cut = index(key, " ")
		head = cut ? substr(key, 1, cut - 1) : key
		if (mode == "keys") { gsub(/[ .-]/, "_", key); print "op_" key }
		else if (verb != "") { if (head == verb && cut && cut < length(key)) print substr(key, cut + 1) "\t" SUMMARY[key] }
		else if (!(head in LISTED)) { LISTED[head] = 1; print head "\t" ((head in SEEN) ? SUMMARY[head] : VERBS[head]) }
	}
}' "$_ajans_root/ajans.toml"
}

_ajans_check() {
	local declared defined missing extra fn count noun
	declared="$(_ajans_toml keys)" || return
	declared="$(printf '%s\n' "$declared" | sort)"
	defined="$(declare -F | awk '$3 ~ /^op_/ { print $3 }' | sort)"
	missing="$(comm -23 <(printf '%s\n' "$declared") <(printf '%s\n' "$defined") | sed '/^$/d')"
	extra="$(comm -13 <(printf '%s\n' "$declared") <(printf '%s\n' "$defined") | sed '/^$/d')"
	if [[ -z "$missing" && -z "$extra" ]]; then
		count="$(printf '%s\n' "$declared" | grep -c .)"
		if [[ "$count" == 1 ]]; then noun=operation; else noun=operations; fi
		printf '✓ ajans.toml and ctl agree: %s %s\n' "$count" "$noun"
		return 0
	fi
	if [[ -n "$missing" ]]; then
		while IFS= read -r fn; do printf '✗ declared, no function: %s\n' "$fn" >&2; done <<<"$missing"
	fi
	if [[ -n "$extra" ]]; then
		while IFS= read -r fn; do printf '✗ function, not declared: %s\n' "$fn" >&2; done <<<"$extra"
	fi
	return 1
}

_ajans_main() {
	case "${1:-}" in
	'' | --list | -h | --help)
		_ajans_toml list
		return
		;;
	--check)
		_ajans_check
		return
		;;
	esac
	if [[ "${2:-}" == --list ]]; then
		_ajans_toml list "$1"
		return
	fi
	local fn
	if [[ $# -ge 2 ]]; then
		fn="$(_ajans_fn "$1 $2")"
		if declare -F "$fn" >/dev/null; then
			shift 2
			"$fn" "$@"
			return
		fi
	fi
	fn="$(_ajans_fn "$1")"
	if declare -F "$fn" >/dev/null; then
		shift
		"$fn" "$@"
		return
	fi
	if declare -F | awk -v p="$fn"_ '$3 ~ "^" p { found = 1 } END { exit !found }'; then
		printf '✗ %s needs a target: ./ctl %s --list\n' "$1" "$1" >&2
	else
		printf '✗ %s: not an operation of this project (./ctl --list)\n' "$*" >&2
	fi
	return 64
}

_ajans_main "$@"
# <<< ajans runtime <<<
