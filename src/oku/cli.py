"""
oku · CLI for the shared HTML chrome kit.

This module is the canonical CLI implementation. Two ways to invoke:

- `uv tool install .` puts `oku` on PATH; subsequent `oku
  serve` etc. just work from anywhere.
- `bin/oku serve` (the PEP 723-annotated shim) runs `main()` from
  here without any install — handy for in-tree work.

Commands:
  oku init    — create an _oku symlink to the kit in the current directory
  oku build   — build all HTMLs in current dir into
                     dist/{standalone,site,markdown}/
  oku clean   — remove dist/ from the current project
  oku serve   — start a local HTTP server in the project root so symlinked
                     kit assets load (file:// has browser-specific restrictions)

All commands take zero flags. Output paths are printed with file:// or http://
prefix for click-to-open.
"""

import argparse
import base64
import collections
import datetime
import difflib
import hashlib
import http.server
import ipaddress
import json
import mimetypes
import os
import queue
import re
import unicodedata
import shlex
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote


try:  # installed distribution
    from importlib.metadata import PackageNotFoundError, version as _dist_version

    try:
        _PKG_VERSION = _dist_version("oku")
    except PackageNotFoundError:  # running from a checkout
        _PKG_VERSION = "0.4.6+source"
except ImportError:  # pragma: no cover — Python < 3.8
    _PKG_VERSION = "0.4.6+source"


def _kit_assets_dir() -> Path:
    """Locate the kit's asset directory.

    Two layouts are valid:

    - **Installed** (uv tool install / pip install): hatchling's
      force-include packs everything into
      ``<site-packages>/oku/assets/`` — chrome.{css,js},
      chrome-boot.js, renderer.js, plus schema/, glossary/, extrefs/.
    - **Development** (cloned repo, no install): the same shape lives
      at ``<repo>/kit/``. Walk up from ``cli.py`` until we find a
      directory containing ``kit/chrome.css`` AND ``kit/schema``.
    """
    here = Path(__file__).resolve()
    pkg_assets = here.parent / "assets"
    if (pkg_assets / "chrome.css").exists():
        return pkg_assets
    for ancestor in [here.parent, *here.parents]:
        if (ancestor / "kit" / "chrome.css").exists() and (ancestor / "kit" / "schema").exists():
            return ancestor / "kit"
    raise RuntimeError(
        "Could not locate kit assets — expected kit/chrome.css + kit/schema "
        "at the repo root, or oku/assets/ from a wheel install."
    )


KIT_DIR = _kit_assets_dir()
KIT_FILES = ["chrome.css", "chrome.js", "chrome-boot.js", "renderer.js"]


_DEFAULT_STUB_BODY_RE = re.compile(r"<body\s*>\s*</body>", re.IGNORECASE)


def _is_default_shaped_stub(content: str) -> bool:
    """True if the stub looks like one we generated — empty <body>.

    `oku init` re-writes default-shaped stubs to refresh the kit
    cache-buster. Anything an author has added inside <body> counts as
    customisation and means the stub stays untouched.
    """
    return bool(_DEFAULT_STUB_BODY_RE.search(content))


def _kit_version() -> int:
    """Integer mtime of the most recently modified kit asset.

    Used as a cache-buster in per-page stub URLs (?v=<n>): static file
    servers (IntelliJ's :63342, plain http.server, file://) don't send
    revalidation headers we control, so without this the browser caches
    chrome.js/chrome.css/renderer.js indefinitely and changes to the kit
    don't take effect until the reader hard-reloads. The query string
    forces a fresh fetch the moment any kit file is touched.
    """
    latest = 0.0
    for name in KIT_FILES:
        p = KIT_DIR / name
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        if mt > latest:
            latest = mt
    return int(latest)


SKIP_DIRS = {
    # `_kit` kept alongside `_oku` so legacy projects still skip the symlink dir.
    "dist",
    "_oku",
    "_kit",
    "node_modules",
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".idea",
    # templates/ ships the starter pair for `oku init` (now under
    # src/oku/templates/). Walking it earlier produced stray
    # starter.{md,html} pages in every build.
    "templates",
    # _internal/ holds session / scratch docs the user explicitly keeps
    # out of the published site.
    "_internal",
}


_project_skip_cache: dict[str, frozenset[str]] = {}


def _kit_build_stamp() -> str:
    """The kit's own build stamp (__okuKitBuild in chrome.js).

    A globally installed `oku` carries a COPY of the kit, so the stamp is
    the only way to tell whether the tool a project builds with is the
    kit you just edited. `uv tool install --force` reuses the cached
    wheel when the version string has not changed, which makes a stale
    tool look freshly installed — this is how that shows up.
    """
    try:
        text = (_kit_assets_dir() / "chrome.js").read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    m = re.search(r"__okuKitBuild\s*=\s*'([^']+)'", text)
    return m.group(1) if m else "unknown"


def _rebuild_command(root: Path) -> str:
    """The command that rebuilds this tree, run from anywhere.

    It carries the absolute source directory on purpose: the reader is
    looking at an artifact, which says nothing about where its source
    sits, and a bare ``oku build`` only works from one directory they
    would have to already know.

    Collapsed to ``~`` when the tree sits under $HOME. The artifact
    travels to other people, and a home-relative path is the whole
    instruction to the one person who can act on it without carrying
    their account name to everyone else. The tilde stays OUTSIDE any
    quoting `shlex` adds, because a quoted ``~`` is a literal directory
    name to the shell rather than the home expansion.
    """
    resolved = root.resolve()
    try:
        home_rel = resolved.relative_to(Path.home()).as_posix()
    except ValueError:
        shown = shlex.quote(resolved.as_posix())
    else:
        shown = "~/" + shlex.quote(home_rel)
    return f"cd {shown} && oku build"


def _artifact_kit_stamp(dist: Path) -> str | None:
    """The kit stamp a previous build left in ``dist/``, or None.

    Read before the build overwrites it, because this process is the
    only place both numbers exist at once. The artifact cannot learn the
    installed stamp — it would have to reach the network to ask, and a
    document that calls home when a teammate opens it is a worse defect
    than the one this reports. The installed tool, for its part, does
    not know an artifact exists until it is asked to replace one.

    One file answers it: every page in a tree is built from the same kit
    in the same pass, so the shared copy under ``dist/site`` settles it,
    and a standalone page is the fallback for a tree built without one.
    """
    shared = dist / "site" / "_oku" / "chrome.js"
    probes = [shared] if shared.exists() else sorted((dist / "standalone").rglob("*.html"))[:1]
    for probe in probes:
        try:
            text = probe.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r"__okuKitBuild\s*=\s*'([^']+)'", text)
        if m:
            return m.group(1)
    return None


class _VersionAction(argparse.Action):
    """Print `--version` verbatim, on one line.

    argparse's built-in version action runs the text through
    HelpFormatter, which wraps it at terminal width. `./ctl deploy`
    reads the `kit` and `src` fields back out of this line with sed to
    decide whether the global tool is stale, so a wrap landing mid-field
    would silently break the staleness gate — the exact failure the
    digest was added to close. Adding the `src` field moved the wrap onto
    the space before the assets path and did break it, which is how this
    was found.
    """

    def __init__(self, option_strings, dest, version: str = "", help: str | None = None) -> None:
        super().__init__(option_strings, dest, nargs=0, help=help)
        self.version = version

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        print(self.version)
        parser.exit()


def _tool_digest() -> str:
    """A content digest over everything the wheel ships.

    The kit stamp above is hand-bumped and lives in chrome.js, so it
    answers one question: did the *kit* change. It cannot answer "is the
    installed tool running this repo's code", because a change to cli.py
    moves neither the stamp nor the version string — and `uv tool install`
    reuses its cached wheel when the version has not changed.

    That combination has already produced a silent wrong answer: the
    global tool reported the same version and the same kit stamp as the
    repo while running a cli.py without a check that had been added to
    it, so `oku check --strict` called a tree clean that the repo source
    warns about. A verify gate that reports success from stale code is
    worse than a slow one.

    Derived rather than declared, so it cannot be forgotten on the day it
    matters.

    The `sha256:` prefix is part of the value, not decoration. Printed
    bare it is twelve hex characters in a version line, which is what an
    abbreviated git commit looks like — a reader holding a rendering
    defect ran `git cat-file -t 8cd13843bf28`, got "Not a valid object
    name", and had no way to tell whether the tool that built their page
    predated the fix. A digest answers "same or different", never "older
    or newer", and the prefix says so at the one place anyone reads it.
    """
    h = hashlib.sha256()
    for f in _tool_files():
        try:
            h.update(f.name.encode())
            h.update(f.read_bytes())
        except OSError:
            return "unknown"
    return "sha256:" + h.hexdigest()[:12]


def _tool_files() -> list[Path]:
    """Every file the digest and the date are computed over.

    One list rather than two, because a date covering a different set
    than the digest is a version line whose two halves can disagree
    about which build they describe.
    """
    files = [Path(__file__)]
    assets = _kit_assets_dir()
    # `vendor/` is a fetched cache that deliberately does not ship, so a
    # populated one made the repo's digest differ from the installed
    # tool's forever. A staleness gate that always fires is one nobody
    # reads — the failure this digest exists to prevent, wearing the
    # opposite sign.
    files += sorted(
        p
        for p in assets.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and "vendor" not in p.parts
    )
    return files


def _tool_dated() -> str:
    """When this build's files were laid down, to the minute.

    The half of the staleness question a digest cannot answer. A digest
    compares; it does not order, so a reader who cannot run this repo's
    `./ctl status` — which is everyone using the installed tool from
    another project — can see that their build differs from something
    and not whether it is the older one. A date orders against the date
    a fix landed, which is the question actually being asked.

    Derived from the files rather than stamped at build time, so it
    needs neither git nor a build hook and cannot go stale on its own.
    `uv tool install` writes every file at the moment it installs, so
    for an installed tool this is the install time; for a checkout it is
    the last edit. Both are "the code as of", which is why the version
    line says exactly that and not "built".
    """
    newest = 0.0
    for f in _tool_files():
        try:
            newest = max(newest, f.stat().st_mtime)
        except OSError:
            return "unknown"
    if not newest:
        return "unknown"
    return datetime.datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M")


def find_kit_json(root: Path) -> Path | None:
    """Return the first existing kit.json under root, preferring the
    docs root over the project root.

    Lookup order:
      1. ``root/docs/kit.json`` — canonical (schema description says
         "Lives at docs/kit.json (or wherever the project's docs root
         is)"). Authors who keep pages under docs/ get this for free.
      2. ``root/kit.json`` — fallback for projects where the project
         root *is* the docs root (no docs/ subdir).

    Returns None if neither exists. The build copies the result, when
    present, into the dist site's docs root so chrome.js's runtime
    fetch (``__okuDocsRoot + 'kit.json'``) resolves.
    """
    candidates = (root / "docs" / "kit.json", root / "kit.json")
    for c in candidates:
        if c.exists():
            return c
    return None


def project_skip_dirs(root: Path) -> frozenset[str]:
    """Read kit.json's optional ``skip_dirs`` array. Cached per (resolved)
    root so repeated find_* calls don't re-parse kit.json.

    Example kit.json fragment::

        {
          "name": "lakelab",
          "skip_dirs": ["logs", "build", "tmp", "target"]
        }

    Authors use this to extend the always-skipped set for project-specific
    junk dirs (build artefacts, log dumps, large datasets) that don't fit
    the auto-skip rule (dot-dirs).
    """
    key = str(root.resolve())
    cached = _project_skip_cache.get(key)
    if cached is not None:
        return cached
    extras: set[str] = set()
    kit_json = find_kit_json(root)
    if kit_json is not None:
        try:
            data = json.loads(kit_json.read_text(encoding="utf-8"))
            raw = data.get("skip_dirs") if isinstance(data, dict) else None
            if isinstance(raw, list):
                extras.update(str(x) for x in raw if isinstance(x, str))
        except (json.JSONDecodeError, OSError):
            pass
    result = frozenset(extras)
    _project_skip_cache[key] = result
    return result


_git_ignored_cache: dict[str, frozenset[str]] = {}


def project_skips_gitignored(root: Path) -> bool:
    """kit.json's optional ``skip_gitignored`` flag. Off by default.

    Off because gitignore is a VERSION-CONTROL policy and this is a
    PUBLICATION policy, and they are not the same question. Plenty of
    projects gitignore generated pages they fully intend to publish, and
    with the flag on, editing ``.gitignore`` would silently change what
    the site contains — action at a distance, from a file nobody thinks
    of as build configuration.

    Where the two policies DO coincide the flag says so explicitly, and
    then the answer is worth having: ``SKIP_DIRS`` can only ever list
    the names somebody remembered, and .gitignore is a list the project
    already maintains.

        {"name": "lakelab", "skip_gitignored": true}

    ``skip_dirs`` remains the direct way to say it, and needs no git.
    """
    kit_json = find_kit_json(root)
    if kit_json is None:
        return False
    try:
        data = json.loads(kit_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(data, dict) and data.get("skip_gitignored") is True


def project_shows_rebuild_command(root: Path) -> bool:
    """kit.json's optional ``rebuild_command`` flag. On by default.

        {"name": "lakelab", "rebuild_command": false}

    A built page says what it was built from, and the Rebuild button
    carries the one fact a reader cannot derive from the artifact: where
    the source lives. That path names a directory on the author's
    machine — collapsed to ``~`` when it sits under $HOME, so it names a
    layout rather than an account, but a layout is still something a
    page hands to everyone it reaches.

    Off, the page keeps every fact that does not identify a machine: the
    tool version, the kit stamp, how old the build is, and the drift
    warning when a site tree's `_oku/` no longer matches its pages. Only
    the command goes, and with it the button — the runtime already draws
    nothing when `cmd` is absent, so there is no disabled state to
    explain.

    On by default because the defect this exists for is the opposite
    one: a delivered report was opened, a rendering bug was reported
    against it, and the bug had been fixed three stamps earlier with
    nothing on the file to say it was old. A page that cannot say how to
    remake itself is the common failure; a page that should not say
    where it came from is the exception, and an exception is a thing a
    project asks for.
    """
    kit_json = find_kit_json(root)
    if kit_json is None:
        return True
    try:
        data = json.loads(kit_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    return not (isinstance(data, dict) and data.get("rebuild_command") is False)


def git_ignored_paths(root: Path) -> frozenset[str]:
    """Absolute paths under ``root`` that git is told to ignore, when the
    project has opted in with ``skip_gitignored``. Empty otherwise, which
    is the default and the behaviour every existing project keeps.

    One subprocess per root, cached. ``--directory`` collapses a
    wholly-ignored directory to one entry, so the walker prunes the
    subtree instead of stat-ing everything under it.

    Empty also means "no opinion", not "nothing is ignored": when git is
    absent, when ``root`` is not in a repository, or when ``root`` is
    ITSELF ignored. Git answers ``./`` in that last case and everything
    below would look like junk, so a project that gitignores its own
    docs directory keeps building even with the flag on.
    """
    key = str(root.resolve())
    cached = _git_ignored_cache.get(key)
    if cached is not None:
        return cached
    lines: list[str] = []
    if project_skips_gitignored(root):
        try:
            out = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-o", "-i", "--exclude-standard", "--directory"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if out.returncode == 0:
                lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
        except (OSError, subprocess.SubprocessError):
            lines = []
        if any(ln.strip().rstrip("/") in ("", ".") for ln in lines):
            lines = []
    result = frozenset(os.path.abspath(os.path.join(str(root), ln.rstrip("/"))) for ln in lines)
    _git_ignored_cache[key] = result
    return result


def iter_repo_files(root: Path, suffixes: tuple[str, ...], *, extra_skip: frozenset[str] | None = None):
    """Yield Path objects under `root` whose name ends with one of `suffixes`,
    pruning at the directory level so we never descend into junk subtrees.

    What gets skipped:

    - Names in ``SKIP_DIRS`` (the hard-coded set: ``dist``, ``_kit``,
      ``node_modules``, ``__pycache__``, etc.).
    - Names in ``extra_skip`` (caller-supplied — typically the kit.json
      ``skip_dirs`` list resolved via ``project_skip_dirs(root)``).
    - Any directory whose name starts with ``.`` — covers ``.git`` /
      ``.venv`` / ``.cache`` / ``.run`` / ``.claude`` / ``.scratch`` /
      ``.playwright-mcp`` without each having to be enumerated. Hidden
      dirs are almost never docs.
    - Anything git is told to ignore — ONLY when kit.json opts in with
      ``skip_gitignored`` (``git_ignored_paths``). Off by default: what
      a project keeps out of version control and what it keeps out of
      its site are two different questions.

    Path.rglob has no equivalent prune hook — it walks every subdirectory
    and forces the caller to filter post-hoc. That's the dominant cost of
    `oku init` on trees with build artefacts (lakelab: 4.6 GB of
    tasks/<id>/.run/ subtrees got fully walked even though only a handful
    of .md / .json files were docs). os.walk lets us mutate ``dirnames[:]``
    in place to skip those subtrees entirely. Symlinks intentionally NOT
    followed — would re-enter the repo via ``_kit`` → kit/ → … and walk
    twice.
    """
    skip = SKIP_DIRS | (extra_skip or frozenset())
    ignored = git_ignored_paths(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # In-place mutation is the documented way to prune os.walk.
        dirnames[:] = [
            d
            for d in dirnames
            if d not in skip
            and not d.startswith(".")
            and os.path.abspath(os.path.join(dirpath, d)) not in ignored
        ]
        for fn in filenames:
            for suf in suffixes:
                if fn.endswith(suf):
                    if os.path.abspath(os.path.join(dirpath, fn)) in ignored:
                        break
                    yield Path(dirpath) / fn
                    break


try:
    import jsonschema as _jsonschema  # type: ignore

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


# ---------- file:// printer ----------
def file_url(p: Path) -> str:
    return f"file://{p.resolve()}"


def report(label: str, path: Path) -> None:
    print(f"  {label:<14} {file_url(path)}")


def _kit_starter_md() -> str | None:
    """The starter markdown shipped with the package, with the
    placeholder tokens left in place — they read as a form to fill in."""
    for base in (Path(__file__).parent / "templates", _kit_assets_dir() / "templates"):
        candidate = base / "starter.md"
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except OSError:
                return None
    return None


# ---------- init ----------
def cmd_init(args: argparse.Namespace) -> int:
    """Idempotently scaffold the CURRENT directory as a docs root.

    Creates two things in cwd if missing:

    - ``_oku`` → KIT_DIR symlink (kit JS/CSS + schema/glossary/extrefs).
      If a stale symlink already points somewhere else, it is replaced;
      a non-symlink path of the same name is left alone with an error.
    - ``index.html`` — entry stub. A single on-disk stub at the docs
      root is what makes IDE-served workflows work (IntelliJ's built-in
      HTTP server, Live Server, etc.); deeper pages stay source-only and
      rely on the dev server's in-memory synthesis.
    - ``index.md`` — starter page, ONLY in a directory that holds no
      page source yet. An empty docs root that renders nothing is a bad
      first minute; a filled-in front-matter block and a TL;DR is a page
      an author can start typing into.

    Run this in whichever directory you treat as your docs root —
    typically ``cd docs && oku init``. The command never creates
    or descends into a "docs" subdir; cwd IS the docs root.
    """
    root = Path.cwd()
    kit_link = root / "_oku"

    if kit_link.is_symlink():
        # Resolve before comparing — the on-disk symlink may be relative
        # (e.g. "../kit") while KIT_DIR is absolute. Comparing literals
        # would falsely flag the link as pointing somewhere else.
        if kit_link.resolve() == KIT_DIR.resolve():
            print(f"✓ Already linked: {kit_link} -> {os.readlink(kit_link)}")
        else:
            # Stale symlink — replace it. Symlinks are cheap; refreshing
            # avoids "the kit moved, init won't fix it" surprises.
            old = os.readlink(kit_link)
            kit_link.unlink()
            kit_link.symlink_to(KIT_DIR)
            print(f"✓ Refreshed {kit_link} -> {KIT_DIR} (was -> {old})")
    elif kit_link.exists():
        print(f"✗ {kit_link} exists and is not a symlink — refusing to overwrite", file=sys.stderr)
        return 1
    else:
        kit_link.symlink_to(KIT_DIR)
        print(f"✓ Linked {kit_link} -> {KIT_DIR}")

    # `oku init` deliberately does NOT generate .json twins of .md files.
    # The source of truth stays the .md (or hand-authored .json) — no
    # duplication on disk. `oku serve` synthesises the .json view in
    # memory; `oku build` emits dist/ artifacts. IDE static servers
    # need either oku serve OR a build artifact to render .md pages.
    index_html = root / "index.html"
    title = "Documentation"
    index_json = root / "index.json"
    if index_json.exists():
        try:
            data = json.loads(index_json.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("title"), str):
                title = data["title"]
        except (json.JSONDecodeError, OSError):
            pass
    # Starter page — only when the directory holds no page source at
    # all, so re-running init in a real docs tree never adds a stray
    # index.md next to the pages that are already there.
    index_md = root / "index.md"
    has_source = any(
        p.suffix in (".md", ".json") and p.name not in ("kit.json", "site-manifest.json")
        for p in root.iterdir()
        if p.is_file()
    )
    if not has_source:
        template = _kit_starter_md()
        if template is not None:
            index_md.write_text(template, encoding="utf-8")
            print(f"✓ Created {index_md} (starter page — fill in the front-matter)")

    fresh = _stub_for(title, inline_manifest=_init_time_manifest(root))
    if index_html.exists():
        existing = index_html.read_text(encoding="utf-8")
        if existing == fresh:
            print(f"✓ Already present: {index_html}")
        elif _is_default_shaped_stub(existing):
            # Default-shaped (empty <body>): safe to rewrite so the
            # cache-buster + embedded site manifest stay current. Any
            # author customisation lives outside this shape and would be
            # preserved by the elif above.
            index_html.write_text(fresh, encoding="utf-8")
            print(f"✓ Refreshed {index_html} (kit cache-buster + page list updated)")
        else:
            print(f"✓ Already present: {index_html} (custom content, untouched)")
    else:
        index_html.write_text(fresh, encoding="utf-8")
        print(f"✓ Created {index_html}")
    print()
    print("  Author pages as <name>.md next to index.html (JSON still works).")
    print("  Open index.html in your IDE, or run `oku serve` from the")
    print("  project root for a live-reloading dev server.")
    return 0


# ---------- build ----------
# The href/src may carry an optional ?v=<n> cache-buster — match it
# greedily so the standalone-build inliner can swap the tag whether or
# not the stub generator stamped a version on it.
LINK_TO_KIT_CSS = re.compile(r'<link\s+rel="stylesheet"\s+href="_oku/chrome\.css(?:\?[^"]*)?"\s*/?>', re.I)
SCRIPT_TO_KIT_BOOT = re.compile(r'<script\s+src="_oku/chrome-boot\.js(?:\?[^"]*)?"\s*></script>', re.I)
SCRIPT_TO_KIT_MAIN = re.compile(r'<script\s+src="_oku/chrome\.js(?:\?[^"]*)?"\s+defer\s*></script>', re.I)
SCRIPT_TO_KIT_RENDERER = re.compile(
    r'<script\s+src="_oku/renderer\.js(?:\?[^"]*)?"\s+defer\s*></script>', re.I
)


def find_html_files(root: Path):
    """Find kit-rendered HTML files under root, skipping generated dirs.

    Files that don't reference the kit boot or renderer (scratch pages,
    foreign HTML) are skipped — processing them would overwrite real
    pages in the dist output.
    """
    out = []
    extra = project_skip_dirs(root)
    for p in iter_repo_files(root, (".html",), extra_skip=extra):
        if not p.is_file():
            continue
        try:
            # 64K, not 2K: `oku init` writes the entry stub with an inline
            # window.__okuManifest, which on a site of any size pushes the
            # kit <script> past a small sniff window. The stub then reads
            # as foreign HTML and the build silently ignores whatever the
            # author customised in it.
            head = p.read_text(encoding="utf-8", errors="ignore")[:65536]
        except OSError:
            continue
        if "_oku/chrome.js" not in head and "_oku/chrome-boot.js" not in head:
            continue
        out.append(p)
    return sorted(out, key=lambda x: str(x).lower())


def iter_page_stubs(root: Path, json_pages: list | None = None):
    """Yield (html_path, html_text, page_data) for every page in root.

    Combines two source styles into one iterable for the build / preview
    code path (D5):

    - On-disk ``page.html`` stubs paired with their ``page.json`` —
      authored as a pair, kit-loaded the usual way. page_data is None;
      downstream re-reads the json sibling.
    - Synthesized stubs for ``page.json`` (or ``page.md``) pages with
      no on-disk ``page.html`` sibling. page_data is the parsed page
      dict so downstream can write the json into dist (for md cases
      where the json isn't on disk) and inject pagefind keywords.

    The path always uses the .html suffix and reflects where the page
    source actually lives on disk; for synthesized stubs the file may
    not exist. On-disk stubs win when both forms describe the same
    path, so authors can override the default stub.
    """
    stubs: dict[Path, tuple[str, dict | None]] = {}
    for p in find_html_files(root):
        stubs[p.resolve()] = (p.read_text(encoding="utf-8"), None)
    pages_iter = json_pages if json_pages is not None else find_json_pages(root)
    for json_path, page in pages_iter:
        stub_path = json_path.with_suffix(".html").resolve()
        if stub_path in stubs:
            # An authored stub keeps its own HTML — but it must still
            # carry its page data. Dropping it here left the standalone
            # build with nothing to inline, so the artifact fell back to
            # fetching `<page>.json`, which a file:// origin blocks: the
            # documented authoring shape (`page.md` + a thin `page.html`)
            # produced a standalone file that renders BLANK when opened
            # off disk. It also kept the page out of the Pagefind index,
            # since build_site only injects a body when it has the page.
            existing_html, existing_page = stubs[stub_path]
            if existing_page is None:
                stubs[stub_path] = (existing_html, page)
            continue
        title = page.get("title") or json_path.stem
        stubs[stub_path] = (_stub_for(title), page)
    return sorted(
        [(p, h, d) for p, (h, d) in stubs.items()],
        key=lambda x: str(x[0]).lower(),
    )


# ---------- JSON pages + site manifest ----------
# ---------- Markdown → page-JSON ----------
#
# Minimal markdown subset converter. Supports the common cases an
# existing .md doc would use: ATX headings, paragraphs with inline
# formatting (**bold**, *italic*, `code`, [text](url)), fenced code
# blocks (incl. ``` mermaid → diagram), unordered + ordered lists,
# blockquotes (→ callout), GFM-style pipe tables, horizontal rules.
#
# Not a full CommonMark parser, but covers everything an author would
# reach for. Supported (P4 closed): nested lists, footnotes, definition
# lists, reference-style links, sanitised inline HTML, YAML
# front-matter. If the author writes something exotic outside this
# vocabulary the converter passes it through as text rather than
# producing invalid kit JSON.


# The accent tokens the kit hand-tunes, in the order the schema names
# them. `_applyAccent` in kit/renderer.js is the implementation and
# `test_authority_agreement.py` holds the three lists — this one, the
# palette map's keys, and the schema's own description — against each
# other. They disagreed once, and the page that found it rendered every
# diagram as an "Unsupported color format" card.
_KIT_ACCENTS = ("teal", "amber", "indigo", "rose", "violet", "green", "slate")

# The CSS named colours, so a bare word that is neither a kit token nor
# one of these can be reported as a typo at build time instead of being
# swallowed by a browser. Only bare words are judged: `#hex`, `rgb(...)`,
# `color-mix(...)` and every other function form are the browser's to
# parse, and a check that guesses at those is one authors learn to
# ignore.
_CSS_NAMED_COLOURS = frozenset(
    """
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond
blue blueviolet brown burlywood cadetblue chartreuse chocolate coral
cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray
darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid
darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey
darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue
firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod
gray grey greenyellow honeydew hotpink indianred indigo ivory khaki lavender
lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon
lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue
lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue
mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen
mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin
navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod
palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum
powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon
sandybrown seagreen seashell sienna silver skyblue slateblue slategray
slategrey snow springgreen steelblue tan thistle tomato turquoise violet wheat
white whitesmoke yellow yellowgreen transparent currentcolor
""".split()
)


def _md_slug(text: str) -> str:
    """ATX-heading style id: lowercase, punctuation dropped, spaces → '-'.

    The body of this function is mirrored EXACTLY by `slugify` in
    kit/renderer.js and in kit/chrome.js, and `test_heading_slug.py`
    holds the three against each other. The reason is one defect wearing
    three hats: `oku check` validates a page's `#fragment` links against
    THIS answer, the renderer writes the id the reader actually lands on,
    and chrome.js names the h3s under a section. When they disagreed, a
    Turkish `## Özet` got the id `zet`, a Chinese heading got a
    positional `sec-3` that moves when a section is inserted above it,
    and `[Özet](#özet)` passed the check and landed nowhere.

    Composed first, then marks dropped. NFC is what makes the same title
    give the same id whichever normalisation form it was typed in — a
    decomposed `é` is `e` plus an acute, and without the compose step it
    would slug as `e` while the composed one slugs as `é`. Marks that
    survive composition are then dropped, which is what turns a
    lowercased `İ` — `i` plus a combining dot — into the plain `i` a
    Turkish author would type into a link.

    An empty result is the CALLER's decision — the check wants a name it
    can report, the renderer wants a positional id that cannot collide.

    Not identical to GitHub's slugger, which keeps runs of hyphens: a
    heading `A - B` is `a-b` here and `a---b` there. That difference
    predates this and changing it would move every existing id.
    """
    s = re.sub(r"[^\w\s-]", "", unicodedata.normalize("NFC", text.lower())).strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def _strip_md_front_matter(text: str) -> tuple[str, dict]:
    """Pull a leading ``---\\n...\\n---\\n`` YAML block off the front of a
    markdown source and return ``(remaining_text, meta_dict)``.

    The parser handles ``key: value`` lines plus **continuation lines** —
    an indented line after a key continues that key's value, joined with
    a single space, which is how a `summary:` too long for one line is
    written. Nested mappings and flow style still fall through as raw
    strings.

    A line inside the block that is none of those — not a key, not a
    continuation, not blank, not a `#` comment — means this is not
    front-matter, and the whole text is returned untouched with
    ``_front_matter_error`` in the meta for `oku check` to report.

    Both rules exist because the scanner used to stop at the NEXT ``---``
    wherever it was, and silently discard every line it had passed over.
    A page whose front-matter was missing its closing delimiter lost the
    paragraphs above the first thematic break in the body, and
    `oku check --strict` was clean, because the deleted text never
    reached any pass that could see it. The folded `summary:` in this
    repo's own `docs/format-comparison.md` lost its second and third
    lines that way, and the truncated sentence — cut mid-clause at
    "converter weight and" — shipped in `site-manifest.json`, in
    `llms.txt` and on the page's cover.
    """
    # A UTF-8 BOM is not whitespace to `str.strip()`, so a file saved by
    # Notepad or written by PowerShell redirection failed the `---` test
    # below, kept its front-matter as body text, and — having no title —
    # was tagged `_materialised_by: oku-init`, which turns the prose lint
    # off. The whole page silently changed category because of one
    # invisible character.
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text, {}
    meta: dict = {}
    order: list[str] = []
    j = 1
    last_key: str | None = None
    while j < len(lines) and lines[j].strip() != "---":
        line = lines[j]
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key, raw = m.group(1), m.group(2)
            meta[key] = raw.strip()
            order.append(key)
            last_key = key
        elif last_key is not None and line[:1] in (" ", "\t") and line.strip():
            meta[last_key] = (str(meta[last_key]) + " " + line.strip()).strip()
        elif not line.strip() or line.lstrip().startswith("#"):
            pass
        else:
            # Not front-matter. Give the text back whole rather than
            # discarding the lines this loop has already walked past.
            return text, {"_front_matter_error": (j + 1, line.strip()[:60])}
        j += 1
    if j >= len(lines):
        # Unterminated front-matter — back off and keep the text intact.
        return text, {}
    for key in order:
        meta[key] = _coerce_front_matter_value(str(meta[key]))
    return "\n".join(lines[j + 1 :]), meta


def _coerce_front_matter_value(raw: str):
    """Quotes off, then a best-effort number or bool.

    Kept separate from the scanner so a continuation line is joined
    BEFORE coercion — otherwise `summary: 42` on one line and its
    continuation on the next would have coerced to an int and then
    concatenated onto one.
    """
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        # Quotes are how the emitter says "this one is a string" — an
        # `order: "007"` that came back as the int 7, or a `flag: "true"`
        # that came back as a bool, made the quoting decorative and the
        # round trip lossy at the one moment `oku migrate` was about to
        # delete the source.
        return raw[1:-1]
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


# A fence opens with three or more backticks OR tildes; the closing run
# must be the same character and at least as long. Tilde fences are the
# GFM way to show a backtick-fenced sample verbatim, so the CLI has to
# agree with the renderer on them.
_FENCE_OPEN_RE = re.compile(r"^([`~]{3,})\s*([\w-]*)[^\n]*$")


def _fence_close_re(opener: str) -> re.Pattern[str]:
    return re.compile(r"^" + re.escape(opener[0]) + r"{" + str(len(opener)) + r",}\s*$")


_MD_FENCE_CAPTION_RE = re.compile(r"^\*([^*].*)\*\s*$")

# Fence tags that lift into typed v2 blocks: ```oku-<kind> with a JSON
# object body. ```mermaid is the one non-namespaced tag — GitHub and
# friends render it natively, so the source stays portable.
_FENCE_KINDS = {
    "chart",
    "chart-grid",
    "table",
    "kpi-grid",
    "step-flow",
    "timeline",
    "compare-grid",
    "insight",
    "example",
    "live-snippet",
    "annotated-code",
    "diagram",
    "info-tip",
    "copy",
    # NOT "tldr": the fence lifts to a block that no v2 renderer case
    # draws and no `$defs` entry validates. `> [!TLDR]` is the one way.
}


def _lift_fence_block(lang: str, body: str) -> dict | None:
    """Map a typed fence to its v2 block, or None when not liftable.

    Not-liftable (bad JSON, non-object payload, unknown kind) is NOT an
    exception path — the fence stays verbatim in the markdown string so
    the page still renders as a code block; `oku check` reports it.
    """
    if lang == "mermaid":
        return {"k": "diagram", "src": body}
    kind = lang[len("oku-") :]
    if kind not in _FENCE_KINDS:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    payload.pop("k", None)
    return {"k": kind, **payload}


def md_to_v2_page(
    text: str,
    default_title: str = "Untitled",
    *,
    block_lines: dict[int, int] | None = None,
) -> dict:
    """Convert a markdown (v3) page source into a v2 page dict.

    Pass ``block_lines`` to receive ``{index in b[]: 1-based line in the
    ORIGINAL file}`` for every lifted fence. `oku check` reports failures
    by block index, and an index is not a location: an author told that
    ``b[5]`` is wrong has to count typed fences through their own page to
    find it. With the line, the message points at the fence.

    The body is preserved as VERBATIM markdown strings in ``b[]`` — the
    kit renderer owns markdown parsing, and migration round-trips
    byte-for-byte. Only typed fences are lifted out of the text:

    - ``` ```oku-<kind> ``` with a JSON object body → ``{"k": <kind>, …}``
    - ``` ```mermaid ``` → ``{"k": "diagram", "src": …}``

    An italic-only line after a lifted diagram fence (blank lines
    allowed between, must be followed by a blank line or EOF) becomes
    the diagram ``caption``. YAML front-matter populates ``m`` and may
    hoist ``title`` → ``t``. Raw HTML islands and every other markdown
    construct pass through untouched inside the strings.
    """
    original = text
    text, front_meta = _strip_md_front_matter(text)
    title = default_title
    if isinstance(front_meta.get("title"), str) and front_meta["title"].strip():
        title = front_meta["title"].strip()
    else:
        # No front-matter title (README and friends): hoist a leading
        # `# H1` into the page title so the cover doesn't double it.
        m = re.match(r"\s*#\s+(.+?)\s*(?:\{#[\w-]+\})?\s*\n", text + "\n")
        if m:
            title = m.group(1).strip()
            text = text[m.end() :]

    # Front-matter and a hoisted H1 are removed above, so a line index into
    # `lines` is not a line in the file the author edits. Both removals are
    # prefixes, so the difference in line count is the offset.
    line_offset = original.count("\n") - text.count("\n") if block_lines is not None else 0

    lines = text.split("\n")
    n = len(lines)
    blocks: list = []
    buf: list[str] = []

    def flush() -> None:
        chunk = "\n".join(buf)
        if chunk.strip():
            if block_lines is not None:
                # `strip("\n")` drops leading blank lines, so the block's
                # first real line is that many past where the buffer began.
                lead = len(chunk) - len(chunk.lstrip("\n"))
                block_lines[len(blocks)] = buf_start + lead + 1 + line_offset
            blocks.append(chunk.strip("\n"))
        buf.clear()

    i = 0
    buf_start = 0
    plain_fence_close: re.Pattern | None = None
    while i < n:
        line = lines[i]
        if not buf:
            buf_start = i
        if plain_fence_close is not None:
            buf.append(line)
            if plain_fence_close.match(line):
                plain_fence_close = None
            i += 1
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m:
            ticks, lang = m.group(1), (m.group(2) or "").lower()
            if lang == "mermaid" or lang.startswith("oku-"):
                close_re = _fence_close_re(ticks)
                body_lines: list[str] = []
                j = i + 1
                while j < n and not close_re.match(lines[j]):
                    body_lines.append(lines[j])
                    j += 1
                block = _lift_fence_block(lang, "\n".join(body_lines))
                if block is None:
                    buf.append(line)
                    buf.extend(body_lines)
                    if j < n:
                        buf.append(lines[j])
                    i = j + 1
                    continue
                # Italic caption convention — diagrams only (the one
                # typed block whose schema carries `caption`).
                if block.get("k") == "diagram" and "caption" not in block:
                    k = j + 1
                    while k < n and not lines[k].strip():
                        k += 1
                    cap = _MD_FENCE_CAPTION_RE.match(lines[k]) if k < n else None
                    if cap and (k + 1 >= n or not lines[k + 1].strip()):
                        block["caption"] = cap.group(1).strip()
                        j = k
                flush()
                if block_lines is not None:
                    # The fence's opening line, in the ORIGINAL file: `lines`
                    # here is the body after front-matter (and possibly a
                    # hoisted H1) was removed, so the offset is what makes
                    # the number match what the author's editor shows.
                    block_lines[len(blocks)] = i + 1 + line_offset
                blocks.append(block)
                i = j + 1
                continue
            plain_fence_close = _fence_close_re(ticks)
        buf.append(line)
        i += 1
    flush()

    page: dict = {"k": "page", "t": title, "b": blocks}
    meta = {k: v for k, v in front_meta.items() if k != "title"}
    if meta:
        page["m"] = meta
    return page


# A markdown page is reported under a `.json` path that does not exist on
# disk — `_synth_json_path` invents it so downstream `with_suffix(".html")`
# keeps working. That is fine inside the pipeline and wrong in a message:
# an author (or an agent) told that `notes/plan.json` has an error opens
# it and finds nothing there. These two registries are what let `oku check`
# name the file that was actually written, and the line inside it.
_PAGE_SOURCE_OF: dict[Path, Path] = {}
_PAGE_BLOCK_LINES: dict[Path, dict[int, int]] = {}


def _remember_source(virtual: Path, source: Path, block_lines: dict[int, int]) -> None:
    _PAGE_SOURCE_OF[virtual] = source
    if block_lines:
        _PAGE_BLOCK_LINES[virtual] = block_lines


def _locate(path: Path, block_index: int | None) -> tuple[Path, int | None]:
    """Map a reported page path (possibly virtual) to the real file, plus
    the source line of a block index when one is known."""
    source = _PAGE_SOURCE_OF.get(path, path)
    line = None
    if block_index is not None:
        line = (_PAGE_BLOCK_LINES.get(path) or {}).get(block_index)
    return source, line


# A kind an author may reasonably reach for as `oku-<kind>`, and the one
# form that actually works. Every entry here is a place the kit offers
# two spellings of one idea — which is the shape that makes an author
# guess. The fence is refused and this names the survivor.
_MARKDOWN_FORM_OF = {
    "tldr": "a `> [!TLDR]` blockquote",
    "callout": "a GFM admonition — `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, …",
    "note": "a `> [!NOTE]` blockquote",
    "tip": "a `> [!TIP]` blockquote",
    "warning": "a `> [!WARNING]` blockquote",
    "code": "a plain fenced code block with a language, e.g. ```python",
    "image": "`![alt](src.png)`",
    "svg": "an HTML island — the `<svg>` tag at column 0",
    "heading": "a `##` / `###` markdown heading",
    "paragraph": "plain markdown prose",
    "list": "a markdown list",
    "section": "a `##` heading, which opens a section",
}


def _known_meta_keys() -> list[str]:
    """Front-matter keys the kit reads, from the schema rather than a
    second list that would drift from it. `title` is included because an
    author writes it in front-matter even though it is hoisted to `t`
    and never lands in `m`."""
    schema = _load_schema()
    props = ((schema.get("$defs") or {}).get("meta") or {}).get("properties") or {}
    return sorted(set(props) | {"title"})


def _did_you_mean(needle: str, haystack, limit: int = 3) -> str:
    """` Did you mean: a, b?` — or nothing when nothing is close.

    Every unresolved-reference check already holds the set of valid
    values at the point it rejects one, and printed the rejection
    without them. That leaves the author knowing a name is wrong and not
    what the right one is, which is answered by opening the page or the
    registry — a file read to recover a string the checker had in hand.

    Deliberately silent below the cutoff: a wrong suggestion is worse
    than none, because it gets applied.
    """
    near = difflib.get_close_matches(
        str(needle).lower(), sorted({str(h).lower() for h in haystack}), n=limit, cutoff=0.6
    )
    return f" Did you mean: {', '.join(near)}?" if near else ""


_BLOCK_INDEX_RE = re.compile(r"\bb[.\[](\d+)")


def _block_index_in(where: str, message: str) -> int | None:
    """Pull the `b[5]` / `b.5` index out of a locator or a message."""
    for text in (where, message):
        m = _BLOCK_INDEX_RE.search(text or "")
        if m:
            return int(m.group(1))
    return None


def _page_from_source_file(p: Path) -> dict | None:
    """Read + convert one page source (any registered format); None
    when unreadable or not a recognised source.

    A source whose front-matter carries a `title` is a hand-authored
    kit page and gets the full lint. Markdown WITHOUT a front-matter
    title (README, CHANGELOG, CLAUDE, SKILL.md and friends) gets the
    `_materialised_by` tag so the linter's prose rules skip
    author-owned repo prose.
    """
    parser = _source_parser_for(p)
    if parser is None:
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    if parser is md_to_v2_page:
        block_lines: dict[int, int] = {}
        page = parser(text, default_title=_source_stem_path(p).name, block_lines=block_lines)
        _remember_source(_synth_json_path(p), p, block_lines)
    else:
        page = parser(text, default_title=_source_stem_path(p).name)
    if parser is md_to_v2_page:
        _, front_meta = _strip_md_front_matter(text)
        if not front_meta.get("title"):
            page.setdefault("m", {}).setdefault("_materialised_by", "oku-init")
    _apply_meta_defaults(page, p)
    refs = collect_file_refs(page, p)
    if refs:
        page.setdefault("m", {})["_files"] = refs
    return page


# ---------- metadata the author should not have to write ----------
#
# Every field an author fills in before writing a sentence is formatting
# work, and the eleven pages in this repo's own docs tree showed most of
# it being answered the same way every time: `accent` teal on 8 of 11,
# `audience` "Author" on 7, `read_time` hand-counted prose that goes
# stale on the next edit, `updated` a second hand-maintained date that
# already matched `date` on one page and had drifted on two others.
#
# What is derivable is derived, what is constant across a tree comes
# from kit.json, and either can still be overridden per page — an
# authored value always wins. Derived keys are listed in `m._derived`
# so `oku check` can tell "the author wrote this" from "we worked it
# out", and the leading underscore keeps them out of `page_to_md`, so a
# migrate round-trip never writes them back into the source.

_WORDS_PER_MINUTE = 220
# Below this a reading estimate is not information — it takes longer to
# read the estimate than to skim the page.
_MIN_READ_MINUTES = 2

_tree_defaults_cache: dict[Path, dict] = {}
_git_date_cache: dict[tuple[str, int], str | None] = {}
# One `git log` per directory instead of one per page. `None` marks a
# directory git could not answer for, so the per-file path is tried
# there and only there.
_git_dir_dates: dict[str, dict[str, str] | None] = {}


def _tree_defaults(source: Path) -> dict:
    """Tree-wide meta defaults from the nearest kit.json.

    kit.json already carries what is true of a docs tree rather than of
    one page (name, description, domains, lang). A colour and a reader
    are the same kind of fact: a tree with a different accent on every
    page is not a design, and `oku check` warns about exactly that.
    """
    start = source.parent if source.is_file() else source
    for d in (start, *start.parents):
        cached = _tree_defaults_cache.get(d)
        if cached is not None:
            return cached
        kit_json = d / "kit.json"
        if not kit_json.is_file():
            continue
        try:
            data = json.loads(kit_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        defaults = {k: data[k] for k in ("accent", "audience") if isinstance(data.get(k), str)}
        _tree_defaults_cache[d] = defaults
        return defaults
    return {}


# The one derived value that is WORDS rather than a number or a date,
# so it is the one that reads as a mistake on a translated page: a
# Turkish cover carrying "~17 min read" under a Turkish title. A code
# with no entry falls back to English rather than guessing.
_READ_TIME_PHRASE = {
    "en": "~{n} min read",
    "tr": "~{n} dakikalık okuma",
}


def _page_language(source: Path) -> str:
    """The language a source file is written in, from its name suffix.

    Only a code the tree DECLARES counts, so `format-comparison.md` is
    not read as language `comparison`.
    """
    codes, default = declared_languages(source.parent)
    if not codes:
        return "en"
    _, lang = split_language_suffix(source.stem, codes)
    return lang or default


def _read_time_for(page: dict, lang: str = "en") -> str | None:
    """A reading estimate from the body, or None when the page is short
    enough that the estimate says nothing."""
    words = 0
    for blk in page.get("b") or []:
        if isinstance(blk, str):
            words += len(blk.split())
        elif isinstance(blk, dict):
            # Typed blocks are read by looking, not by reading. Count
            # their prose at a discount rather than not at all.
            words += len(json.dumps(blk, ensure_ascii=False).split()) // 2
    minutes = round(words / _WORDS_PER_MINUTE)
    if minutes < _MIN_READ_MINUTES:
        return None
    phrase = _READ_TIME_PHRASE.get(lang, _READ_TIME_PHRASE["en"])
    return phrase.format(n=minutes)


def _git_last_modified(p: Path) -> str | None:
    """The file's last commit date as YYYY-MM-DD, or None.

    Deliberately NOT the filesystem mtime: a fresh clone stamps every
    file with the checkout time, which would render the whole tree as
    "updated today" — worse than showing nothing, because it looks like
    information.
    """
    try:
        key = (str(p.resolve()), int(p.stat().st_mtime))
    except OSError:
        return None
    if key in _git_date_cache:
        return _git_date_cache[key]
    dates = _git_dates_in(p.parent)
    if dates is not None:
        # The directory's whole history is in hand: a file missing from
        # it is one git has never seen, and asking again per file is how
        # the newest pages became the most expensive ones — `git log`
        # walks the entire history before returning empty.
        out = dates.get(p.name)
    else:
        out = _git_date_one(p)
    _git_date_cache[key] = out
    return out


def _git_dates_in(directory: Path) -> dict[str, str] | None:
    """Last commit date per file in one directory, from ONE `git log`.

    Profiled on a 100-page tree: `_git_last_modified` was 9.0s of a
    12.9s build (70%), 100 subprocesses at 78-90ms each, because the
    cache key is per (path, mtime) and nothing batched. One
    `git log --name-only` covering every page in this repo takes 0.09s.

    `--relative` makes the paths relative to `cwd`, so the directory is
    both the scope and the key. Newest-first, so the first sighting of a
    name is its answer. None means git could not answer for this
    directory at all — not a repository, or git is absent — and the
    caller falls back to asking per file.
    """
    key = str(directory)
    if key in _git_dir_dates:
        return _git_dir_dates[key]
    result: dict[str, str] | None = None
    try:
        r = subprocess.run(
            ["git", "log", "--format=%cs", "--name-only", "--relative", "--", "."],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            result = {}
            current = ""
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", line):
                    current = line
                elif current and line not in result:
                    result[line] = current
    except (OSError, subprocess.SubprocessError):
        result = None
    _git_dir_dates[key] = result
    return result


def _git_date_one(p: Path) -> str | None:
    """The single-file question, for a directory git has no answer for."""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", p.name],
            cwd=p.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.stdout.strip()):
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _apply_meta_defaults(page: dict, source: Path) -> None:
    """Fill the meta an author should not have to write. Authored values
    always win; every filled key is recorded in `m._derived`."""
    if not isinstance(page, dict) or page.get("k") != "page":
        return
    meta = page.get("m")
    if meta is None:
        meta = {}
    derived: list[str] = []

    for key, value in _tree_defaults(source).items():
        if not meta.get(key):
            meta[key] = value
            derived.append(key)

    if not meta.get("read_time"):
        rt = _read_time_for(page, _page_language(source))
        if rt:
            meta["read_time"] = rt
            derived.append("read_time")

    if not meta.get("updated"):
        when = _git_last_modified(source)
        if when:
            meta["updated"] = when
            derived.append("updated")

    if derived:
        meta["_derived"] = derived
    if meta:
        page["m"] = meta


def _front_matter_value(v) -> str:
    """Render one front-matter value the minimal parser reads back."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        # A real number needs no quotes — and must not get them, or it
        # comes back a string. Only a STRING that looks like a number
        # does, which is the test two lines down.
        return str(v)
    s = str(v)
    # The reader strips wrapping quotes; quote only when the raw form
    # would coerce or trim differently than intended.
    if s != s.strip() or s.lower() in {"true", "false"} or _looks_numeric(s) or not s:
        return '"' + s + '"'
    return s


def _looks_numeric(s: str) -> bool:
    """Whether the reader would hand this back as a number.

    A version string (`order: "1.10"`) and a zero-padded id
    (`ref: "007"`) are the cases: both are strings the author wrote and
    both come back changed unless the emitter quotes them.
    """
    try:
        int(s)
        return True
    except ValueError:
        pass
    try:
        float(s)
        return True
    except ValueError:
        return False


def page_to_md(page: dict) -> str:
    """Emit a v3 markdown source from a page dict — the inverse of
    md_to_v2_page. v1 pages are shimmed to v2 first. Markdown strings
    land verbatim; typed blocks become ```oku-<kind> fences with a
    compact JSON body; diagrams become ```mermaid fences with the
    italic caption line. md_to_v2_page(page_to_md(p)) round-trips."""
    if page.get("kind") == "page" and "k" not in page:
        page = _v1_to_v2(page)
    meta = page.get("m") or {}
    # Values the build worked out (tree accent, reading estimate, commit
    # date) must never be written back into a source — one migrate would
    # re-introduce every field the derivation exists to remove, and the
    # next edit would leave the frozen copy silently stale.
    derived = set(meta.get("_derived") or ())
    fm: list[str] = ["---", f"title: {_front_matter_value(page.get('t', ''))}"]
    for key, v in meta.items():
        if key.startswith("_") or key in derived or "\n" in str(v):
            continue
        fm.append(f"{key}: {_front_matter_value(v)}")
    fm.append("---")
    parts: list[str] = ["\n".join(fm)]
    for blk in page.get("b") or []:
        if isinstance(blk, str):
            parts.append(blk.strip("\n"))
            continue
        if not isinstance(blk, dict):
            continue
        kind = blk.get("k")
        if kind == "diagram" and isinstance(blk.get("src"), str) and set(blk) <= {"k", "src", "caption"}:
            seg = "```mermaid\n" + blk["src"] + "\n```"
            if blk.get("caption"):
                seg += "\n\n*" + str(blk["caption"]) + "*"
            parts.append(seg)
            continue
        payload = {kk: v for kk, v in blk.items() if kk != "k"}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        parts.append(f"```oku-{kind}\n{body}\n```")
    return "\n\n".join(parts) + "\n"


# ---------------- source registry ----------------

# Two source formats, and the registry stays because the SECOND one is
# not going anywhere: `.json` is how every v1/v2 page written before the
# markdown format existed still renders. `.md` is what an author writes.
#
# HTML is not in this table and never was in the way it looks — it is
# the OUTPUT. Every page, whatever its source, is delivered as HTML by
# `oku build`. `.src.html` was a third thing: authoring the *source* in
# HTML, which is a different question from delivering HTML, and one the
# format comparison answered against. An author who wants raw HTML in a
# page uses an island; that is the escape hatch and it has no limits.
_PAGE_SOURCE_PARSERS = {
    ".md": md_to_v2_page,
}
_PAGE_SOURCE_EMITTERS = {
    "md": page_to_md,
}
_SOURCE_SUFFIXES = (".md",)


def _source_parser_for(p: Path):
    """Parser callable for a page-source path, or None."""
    return _PAGE_SOURCE_PARSERS.get(p.suffix)


def _source_stem_path(p: Path) -> Path:
    """The path minus its SOURCE suffix."""
    return p.with_suffix("")


def _source_sibling(p: Path) -> Path:
    """The `.md` source a virtual `.json`/`.html` page path came from.

    `notes/index.tr.json` → `notes/index.tr.md`. Same trap as
    `_synth_json_path` in the other direction: `with_suffix` on the stem
    `index.tr` yields `index.md`, so a translation resolved to its
    original and every page whose name carries a dot served the wrong
    file.
    """
    return p.with_name(p.name[: -len(p.suffix)] + ".md")


def _synth_json_path(p: Path) -> Path:
    """`notes/index.tr.md` → `notes/index.tr.json`.

    Deliberately not `p.with_suffix("").with_suffix(".json")`.
    `with_suffix` replaces the LAST dotted part, so the stem `index.tr`
    becomes `index.json` — the same virtual path `index.md` produces.
    The walker's dedupe then drops one of the two, and a page vanishes
    from the site with nothing said. That was true of any `a.b.md`
    before a language ever entered the picture: `api.v2.md` and
    `notes.2026-08.md` collided with `api.md` and `notes.md`.
    """
    return p.with_name(p.name[: -len(p.suffix)] + ".json")


def find_markdown_pages(root: Path) -> list[tuple[Path, dict]]:
    """Walk *.md files under root, return (md_path, synthesized_page_dict).

    Skips SKIP_DIRS. Every .md the walker reaches becomes a page —
    including repo-root files (README, CHANGELOG, CLAUDE, …) which
    earlier revisions filtered out as "project meta". Files that fail
    to convert are silently omitted (the converter is permissive —
    only an unreadable file would trigger this).
    """
    out: list[tuple[Path, dict]] = []
    extra = project_skip_dirs(root)
    for p in iter_repo_files(root, _SOURCE_SUFFIXES, extra_skip=extra):
        page = _page_from_source_file(p)
        if page is not None:
            out.append((p, page))
    return sorted(out, key=lambda x: str(x[0]).lower())


def _stub_for(title: str, *, inline_manifest: dict | None = None) -> str:
    """Minimal HTML stub for a page. Authored on disk by `oku init`
    (for the entry stub), synthesized in-memory by the dev server, and
    written to dist/ by the build.

    Everything the page needs at runtime — fonts, the body skeleton
    (page-chrome + layout + nav + main + toc), and the autoBoot call
    — is owned by the kit's CSS and JS. The stub stays small so
    authors who customise it have little to read or maintain.

    When ``inline_manifest`` is supplied, the dict is embedded as a
    ``window.__okuManifest`` script before the kit loads — so the
    site-tree sidebar populates even when the page is opened via a
    static file server (IDE, file://) that can't reach the dev-time
    manifest synthesis.
    """
    v = _kit_version()
    manifest_block = ""
    if inline_manifest is not None:
        manifest_json = json.dumps(inline_manifest, ensure_ascii=False, separators=(",", ":"))
        manifest_block = f"<script>window.__okuManifest={manifest_json};</script>\n"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{html_escape(title)}</title>\n"
        f"{manifest_block}"
        f'<script src="_oku/chrome-boot.js?v={v}"></script>\n'
        f'<link rel="stylesheet" href="_oku/chrome.css?v={v}">\n'
        f'<script src="_oku/chrome.js?v={v}" defer></script>\n'
        f'<script src="_oku/renderer.js?v={v}" defer></script>\n'
        "</head>\n<body></body>\n</html>\n"
    )


def _init_time_manifest(root: Path) -> dict:
    """Manifest snapshot for the init-time stub.

    Drops ``generated_at`` (which would otherwise differ on every run
    and trigger a needless re-write) and trims to the fields the
    runtime sidebar actually consumes. The result is what gets
    embedded as window.__okuManifest in docs/index.html.

    ``build`` goes with it, for a second reason on top of the churn: it
    holds a path on the author's machine and this stub is a SOURCE file
    that gets committed. The build metadata belongs in the artifacts,
    which is where `build_standalone` and the dist/site manifest put it.
    """
    manifest = compute_manifest(root)
    manifest.pop("generated_at", None)
    manifest.pop("build", None)
    return manifest


def html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_KIT_URL_RE = re.compile(r'((?:src|href)=")(_oku/)', re.I)


def _retarget_kit_urls(html: str, depth: int) -> str:
    """Rewrite ``_oku/`` URLs in a stub for a page nested ``depth``
    levels deep (depth 0 = top-level dist page).

    Pages at e.g. dist/site/examples/storage/iceberg-detail.html need
    `_oku/chrome.js` to resolve to `dist/site/_oku/chrome.js` —
    that's two levels up. This rewriter prefixes the kit URL with the
    right number of `../`.
    """
    if depth <= 0:
        return html
    prefix = "../" * depth
    return _KIT_URL_RE.sub(lambda m: m.group(1) + prefix + m.group(2), html)


_FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*vendor/fonts/[^}]*\}\s*", re.S)
_FONT_URL_RE = re.compile(r'url\("vendor/fonts/')


def _retarget_font_urls(css: str, vendor_base: str) -> str:
    """Point chrome.css's @font-face rules at a copy the page can reach.

    Two callers, two answers. Served or copied, the stylesheet is a file
    and `vendor/fonts/x.woff2` resolves beside it — nothing to do. Inlined
    into a standalone page, the same string resolves against the PAGE, so
    it names a directory that does not exist and the reader silently gets
    the system font stack.

    When the fonts were never fetched the whole rule is dropped rather
    than repointed. A shipped @font-face whose file is absent costs a
    failed request per page for a fallback the font-family declarations
    already provide — and the point of vendoring was that a delivered
    page reaches for nothing.
    """
    if not vendor_fonts_present():
        return _FONT_FACE_RE.sub("", css)
    return _FONT_URL_RE.sub(f'url("{vendor_base}fonts/', css)


def _is_page(data) -> bool:
    """True for either v1 ({kind:'page'}) or v2 ({k:'page'}) shape."""
    return isinstance(data, dict) and (data.get("k") == "page" or data.get("kind") == "page")


def _page_title(data: dict) -> str:
    return data.get("t") or data.get("title") or ""


def _page_meta(data: dict) -> dict:
    m = data.get("m") if data.get("m") is not None else data.get("meta")
    return m if isinstance(m, dict) else {}


def _page_blocks(data: dict) -> list:
    b = data.get("b") if data.get("b") is not None else data.get("blocks")
    return b if isinstance(b, list) else []


# ---------------------------------------------------------------------------
# v1 → v2 conversion
#
# Pages on disk authored against the v1 schema (kind/title/blocks/section/
# paragraph/heading/list/callout/tldr/info-tip/rich-strings) are converted
# into the compact v2 shape (k/t/m/b with markdown strings inside b[]).
# The kit's renderer.js carries the same logic so unmigrated pages still
# render. `oku migrate` runs this on disk so the source becomes v2 too.
# ---------------------------------------------------------------------------


def _rich_to_md(rich) -> str:
    if rich is None:
        return ""
    if isinstance(rich, str):
        return rich
    if not isinstance(rich, list):
        return ""
    out: list[str] = []
    for seg in rich:
        if isinstance(seg, str):
            out.append(seg)
            continue
        if not isinstance(seg, dict):
            continue
        k = seg.get("kind")
        text = seg.get("text") or ""
        if k == "em":
            out.append(f"*{text}*")
        elif k == "strong":
            out.append(f"**{text}**")
        elif k == "code":
            out.append(f"`{text}`")
        elif k == "link":
            out.append(f"[{text or seg.get('href', '')}]({seg.get('href', '')})")
        elif k == "glossary-term":
            term = seg.get("term") or ""
            out.append(f"[{text or term}](#g/{term})")
        elif k == "ext-ref":
            name = seg.get("name") or ""
            out.append(f"[{text or name}](#x/{name})")
        elif k == "html":
            out.append(text)
    return "".join(out)


def _v1_to_v2_th(h):
    if isinstance(h, dict) and not isinstance(h, list) and "label" in h:
        out = dict(h)
        out["label"] = _rich_to_md(h["label"])
        return out
    return _rich_to_md(h)


def _v1_to_v2_tc(c):
    if isinstance(c, dict) and not isinstance(c, list) and isinstance(c.get("values"), list):
        out = dict(c)
        if "value" in c:
            out["value"] = _rich_to_md(c["value"])
        return out
    return _rich_to_md(c)


def _v1_to_v2_tr(r):
    if isinstance(r, list):
        return [_v1_to_v2_tc(c) for c in r]
    if isinstance(r, dict) and "cells" in r:
        out = dict(r)
        out["cells"] = [_v1_to_v2_tc(c) for c in r["cells"]]
        return out
    return r


def _v1_to_v2_block(blk):
    """Convert one v1 content-block into either a markdown string or a v2 typed block dict."""
    if not isinstance(blk, dict):
        return None
    k = blk.get("kind")
    if k == "paragraph":
        return _rich_to_md(blk.get("content"))
    if k == "heading":
        lvl = max(3, min(6, blk.get("level") or 3))
        out = "#" * lvl + " " + (blk.get("title") or "")
        if blk.get("id"):
            out += " {#" + blk["id"] + "}"
        return out
    if k == "list":
        style = blk.get("style") or "bullet"
        items = blk.get("items") or []
        lines = []
        for i, it in enumerate(items):
            marker = f"{i + 1}." if style == "numbered" else "-"
            lines.append(f"{marker} {_rich_to_md(it)}")
        return "\n".join(lines)
    if k == "callout":
        typ = (blk.get("type") or "note").upper()
        title = blk.get("title") or ""
        body = ""
        if blk.get("content") is not None:
            md = _rich_to_md(blk["content"])
            if md:
                body = "\n" + "\n".join("> " + ln for ln in md.split("\n"))
        return f"> [!{typ}]" + (f" {title}" if title else "") + body
    if k == "tldr":
        body = ""
        if blk.get("summary"):
            body += "\n> " + _rich_to_md(blk["summary"])
        if isinstance(blk.get("bullets"), list) and blk["bullets"]:
            body += "\n>"
            for bl in blk["bullets"]:
                body += "\n> - " + _rich_to_md(bl)
        title = blk.get("title") or ""
        return "> [!TLDR]" + (f" {title}" if title else "") + body
    if k == "info-tip":
        parts: list[str] = []
        for sub in blk.get("content") or []:
            c = _v1_to_v2_block(sub)
            if isinstance(c, str):
                parts.append(c)
        body = ""
        if parts:
            chunks = "\n\n".join(parts)
            body = "\n" + "\n".join("> " + ln for ln in chunks.split("\n"))
        return "> [!TIP]" + (f" {blk.get('summary')}" if blk.get("summary") else "") + body
    if k == "insight":
        return {"k": "insight", "b": _rich_to_md(blk.get("content"))}
    if k == "code":
        lang = blk.get("language") or ""
        return f"```{lang}\n{blk.get('source') or ''}\n```"
    if k == "diagram":
        out_d = {"k": "diagram", "src": blk.get("source") or ""}
        if blk.get("caption"):
            out_d["caption"] = blk["caption"]
        return out_d
    if k == "image":
        out_img = {"k": "image", "src": blk.get("src") or ""}
        if blk.get("alt"):
            out_img["alt"] = blk["alt"]
        if blk.get("caption"):
            out_img["caption"] = blk["caption"]
        if blk.get("width") is not None:
            out_img["width"] = blk["width"]
        return out_img
    if k == "svg":
        out_svg = {"k": "svg", "src": blk.get("source") or ""}
        if blk.get("caption"):
            out_svg["caption"] = blk["caption"]
        if blk.get("label"):
            out_svg["label"] = blk["label"]
        return out_svg
    if k == "live-snippet":
        out_l = {"k": "live-snippet", "src": blk.get("source") or ""}
        if blk.get("language"):
            out_l["lang"] = blk["language"]
        if blk.get("label"):
            out_l["label"] = blk["label"]
        return out_l
    if k == "annotated-code":
        out_a = {"k": "annotated-code", "src": blk.get("source") or ""}
        if blk.get("language"):
            out_a["lang"] = blk["language"]
        if blk.get("annotations"):
            out_a["annotations"] = blk["annotations"]
        return out_a
    if k == "table":
        out_t: dict = {"k": "table"}
        if blk.get("view"):
            out_t["view"] = blk["view"]
        if blk.get("headers"):
            out_t["headers"] = [_v1_to_v2_th(h) for h in blk["headers"]]
        if blk.get("rows"):
            out_t["rows"] = [_v1_to_v2_tr(r) for r in blk["rows"]]
        if blk.get("groups"):
            out_t["groups"] = [
                {
                    "t": _rich_to_md(g.get("title")) if g.get("title") else "",
                    "rows": [_v1_to_v2_tr(r) for r in (g.get("rows") or [])],
                }
                for g in blk["groups"]
            ]
        return out_t
    if k == "kpi-grid":
        return {"k": "kpi-grid", "tiles": blk.get("tiles") or []}
    if k == "step-flow":
        steps = []
        for s in blk.get("steps") or []:
            o = {"t": s.get("title") or ""}
            if s.get("content") is not None:
                o["b"] = _rich_to_md(s["content"])
            if s.get("meta"):
                o["meta"] = s["meta"]
            if s.get("href"):
                o["href"] = s["href"]
            steps.append(o)
        return {"k": "step-flow", "steps": steps}
    if k == "compare-grid":
        cards = []
        for c in blk.get("cards") or []:
            o = {"t": c.get("title") or ""}
            parts = []
            if c.get("content") is not None:
                parts.append(_rich_to_md(c["content"]))
            if c.get("items"):
                parts.append("\n".join(f"- {_rich_to_md(it)}" for it in c["items"]))
            if c.get("blocks"):
                for sub in c["blocks"]:
                    conv = _v1_to_v2_block(sub)
                    if isinstance(conv, str):
                        parts.append(conv)
            o["b"] = "\n\n".join(p for p in parts if p)
            if c.get("verdict"):
                o["verdict"] = c["verdict"]
            if c.get("accent"):
                o["accent"] = c["accent"]
            if c.get("href"):
                o["href"] = c["href"]
            cards.append(o)
        return {"k": "compare-grid", "cards": cards}
    if k == "chart":
        out_c = dict(blk)
        out_c.pop("kind", None)
        out_c["k"] = "chart"
        return out_c
    if k == "chart-grid":
        out_cg = dict(blk)
        out_cg.pop("kind", None)
        out_cg["k"] = "chart-grid"
        return out_cg
    if k == "example":
        o2: dict = {"k": "example"}
        if blk.get("title"):
            o2["t"] = blk["title"]
        if blk.get("code"):
            cc = blk["code"]
            o2["code"] = {"k": "code", "src": cc.get("source") or ""}
            if cc.get("language"):
                o2["code"]["lang"] = cc["language"]
        if blk.get("output"):
            o2["output"] = _v1_to_v2_block(blk["output"])
        return o2
    return None


def _v1_to_v2(data: dict) -> dict:
    """Convert a v1 page dict to v2 in-memory. Idempotent — v2 input passes through."""
    if not isinstance(data, dict):
        return data
    if data.get("k") == "page":
        return data
    if data.get("kind") != "page":
        return data
    out: dict = {"k": "page"}
    if data.get("title"):
        out["t"] = data["title"]
    meta = dict(data.get("meta") or {})
    if data.get("accent") and "accent" not in meta:
        meta["accent"] = data["accent"]
    # Drop materialised marker noise that came from md_to_page seeding.
    if meta:
        out["m"] = meta
    b: list = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            joined = "\n\n".join(x for x in buf if x.strip())
            if joined:
                b.append(joined)
            buf.clear()

    for top in data.get("blocks") or []:
        if not isinstance(top, dict):
            continue
        if top.get("kind") == "section":
            flush()
            head = "## " + (top.get("title") or "")
            if top.get("id"):
                head += " {#" + top["id"] + "}"
            buf.append(head)
            if top.get("lead"):
                buf.append(_rich_to_md(top["lead"]))
            for sub in top.get("blocks") or []:
                conv = _v1_to_v2_block(sub)
                if isinstance(conv, str):
                    buf.append(conv)
                elif conv is not None:
                    flush()
                    b.append(conv)
        else:
            conv = _v1_to_v2_block(top)
            if isinstance(conv, str):
                buf.append(conv)
            elif conv is not None:
                flush()
                b.append(conv)
    flush()
    out["b"] = b
    return out


def find_json_pages(root: Path):
    """Recursively find *.json files where the root object has kind == 'page'.

    ALSO converts .md files into synthesized page dicts. The returned
    path uses a .json suffix (the in-memory virtual path) so downstream
    code that does `path.with_suffix(".html")` still works.

    Returns list of (path, parsed-data) tuples sorted by path.
    """
    pages = []
    real_json: set[Path] = set()
    extra = project_skip_dirs(root)
    # Two passes — JSON first so the MD pass can dedupe against real
    # JSON siblings regardless of os.walk traversal order. Both use the
    # pruned walker so SKIP_DIRS subtrees are never descended into.
    for p in iter_repo_files(root, (".json",), extra_skip=extra):
        if p.name in ("kit.json", "site-manifest.json", "package.json", "tsconfig.json"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if _is_page(data):
            pages.append((p, data))
            real_json.add(p)
    # Also walk .md files — convert each into a synthesized page dict
    # via md_to_page. The "path" returned uses .json so consumers that
    # do path.with_suffix(".html") still derive the right stub URL.
    # Every .md the walker reaches becomes a page — README, CHANGELOG,
    # CLAUDE.md, AGENTS.md and friends included. Authors who don't
    # want a given file in the site tree should put it under a
    # SKIP_DIRS-matching subdirectory.
    seen_stems: set = set()
    for p in iter_repo_files(root, _SOURCE_SUFFIXES, extra_skip=extra):
        synth_path = _synth_json_path(p)
        # Don't shadow a real .json sibling.
        if synth_path in real_json or synth_path in seen_stems:
            continue
        page = _page_from_source_file(p)
        if page is None:
            continue
        seen_stems.add(synth_path)
        pages.append((synth_path, page))
    return sorted(pages, key=lambda x: str(x[0]).lower())


_schema_cache = None


def _load_schema():
    """Lazy-load and cache the page schema."""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache
    schema_path = KIT_DIR / "schema" / "page.schema.json"
    if schema_path.exists():
        try:
            _schema_cache = json.loads(schema_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _schema_cache = {}
    else:
        _schema_cache = {}
    return _schema_cache


_validator_cache = None


def _get_validator():
    """Build (and cache) a jsonschema validator for the page schema.

    `jsonschema.validate(data, schema)` is the convenience entry point — but
    it runs `check_schema(schema)` on every call, which dominates validation
    time when batching many pages (16 pages × ~100ms = 1.6s wasted in
    `cmd_build`'s profile). Build the validator once, reuse for every page.
    """
    global _validator_cache
    if _validator_cache is not None:
        return _validator_cache
    schema = _load_schema()
    if not schema:
        return None
    try:
        validator_cls = _jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        _validator_cache = validator_cls(schema)
    except _jsonschema.SchemaError:
        _validator_cache = None
    return _validator_cache


_MAX_ECHO_CHARS = 160


def _focused_schema_message(err, schema: dict) -> str:
    """Name the fix instead of echoing the payload back.

    A malformed block fails `$defs/block`'s `anyOf`, and jsonschema words
    that failure as "<the entire instance> is not valid under any of the
    given schemas". The instance is the author's own JSON, handed back to
    them in place of the one sentence they needed, and it grows with the
    payload: on a 14-node sankey with `edges` written for `links`, the echo
    was 1235 of the 1372 bytes the run printed.

    A block says which shape it means — `k` — so re-validate it against that
    one `$defs` entry. The blanket rejection becomes `'links' is a required
    property` plus `Additional properties are not allowed ('edges' was
    unexpected)`, which is both shorter and the actual answer.
    """
    instance = err.instance
    kind = instance.get("k") if isinstance(instance, dict) else None
    defs = schema.get("$defs") or {}
    sub = defs.get(kind) if isinstance(kind, str) else None

    if sub is not None:
        try:
            validator_cls = _jsonschema.validators.validator_for(schema)
            focused = validator_cls({**sub, "$defs": defs})
            # Deduped and capped: one bad block can fail a dozen ways, and
            # printing all of them buries the page the same way the echo did.
            msgs = list(dict.fromkeys(e.message for e in focused.iter_errors(instance)))
        except _jsonschema.SchemaError:
            msgs = []
        if msgs:
            shown = "; ".join(msgs[:3])
            more = f" (+{len(msgs) - 3} more)" if len(msgs) > 3 else ""
            return f"k={kind}: {shown}{more}"

    if err.validator in ("anyOf", "oneOf"):
        if not isinstance(kind, str):
            return "block matches no known kind — it has no `k` field."
        if kind not in defs:
            return f"k={kind!r} is not a known block kind."
        return f"k={kind}: does not match the schema for that kind."

    text = err.message
    return text if len(text) <= _MAX_ECHO_CHARS else text[:_MAX_ECHO_CHARS].rstrip() + "…"


def validate_pages(pages) -> list:
    """Validate each parsed page against the schema. Returns a list of
    (path, error_message) tuples. Empty list = clean.

    Soft-fails: if jsonschema isn't installed, returns [] without error.
    Hint printed once at module import time.
    """
    if not _HAS_JSONSCHEMA:
        return []
    validator = _get_validator()
    if validator is None:
        return []
    schema = _load_schema() or {}
    errors: list[tuple[Path, str]] = []
    for p, data in pages:
        # v1 pages still on disk validate against the v2 schema by
        # converting in-memory first. Migration to disk via `oku migrate`
        # is optional — this keeps `oku check` accurate for either shape.
        v2 = _v1_to_v2(data) if isinstance(data, dict) and data.get("k") != "page" else data
        # Every failing block, not the first. Stopping at one was called
        # "keeping the report focused"; in practice it meant a page with
        # three malformed blocks reported one, and an author who fixed
        # it and re-ran got the next — three rounds to learn what one
        # run could have said. One real page had a table, a KPI grid and
        # a step flow all wrong, and only the table was ever named.
        #
        # One error PER BLOCK, though: a block that fails `anyOf` emits a
        # sub-error for every branch it didn't match, and printing forty
        # of those for one bad table buries the page.
        seen_paths: set[str] = set()
        for err in validator.iter_errors(v2):
            field = ".".join(str(x) for x in err.absolute_path) or "(root)"
            block_path = ".".join(str(x) for x in list(err.absolute_path)[:2]) or "(root)"
            if block_path in seen_paths:
                continue
            seen_paths.add(block_path)
            errors.append((p, f"{field}: {_focused_schema_message(err, schema)}"))
    return errors


# ---------- oku check (doctree linter) ----------
#
# A single pass over every page-JSON the project owns, surfacing problems
# at three severities:
#
#   error    — broken in a way the renderer can't paper over (unknown
#              kind, missing required field, duplicate anchor, unresolved
#              glossary term, deprecated primitive). Exits non-zero.
#   warning  — works at runtime but indicates rot: missing language on a
#              code block, page with no meta.summary, forbidden process
#              language ("round-N", "v2 review") leaking into prose.
#              Exits zero unless --strict.
#   info     — opinion / quality nudges (no title on a chart, etc.).
#
# Output is human-readable by default; --json emits a machine-parseable
# stream for the oku skill's auto-verify step.
#
# The function is also the right entry point for tests: it returns the
# list of issues so unit tests can assert against shapes rather than
# parsing stdout.

# Deprecated block kinds the renderer no longer wires up. Listed here so
# that any old content still using these surfaces a clear migration
# pointer (instead of a generic "unknown block kind" warning).
_DEPRECATED_KINDS = {
    "bar-chart": "chart with type:bar (top-level rows[] preserved)",
    "scope-grid": "compare-grid with verdict in/out and items[] on each card",
}

# Block kinds the kit knows how to render. Cross-checked against the
# renderer's switch in kit/renderer.js — keep this list in sync when a
# kind is added or removed.
_KNOWN_BLOCK_KINDS = {
    "section",
    "paragraph",
    "heading",
    "callout",
    "insight",
    "info-tip",
    "list",
    "code",
    "annotated-code",
    "table",
    "tldr",
    "kpi-grid",
    # `oku-chart-grid` is a documented fence tag, renderer.js lists it in
    # FENCE_KINDS and draws it in _renderChartGrid, and the schema has a
    # `$defs/chart-grid`. Only this set had missed it, so `oku check`
    # answered a correctly-authored small-multiples fence with
    # `unknown-kind` — the linter rejecting a page the renderer draws.
    "chart-grid",
    "step-flow",
    "timeline",
    "compare-grid",
    "chart",
    "diagram",
    "image",
    "svg",
    "live-snippet",
    "example",
    "copy",
}

_KNOWN_INLINE_KINDS = {"glossary-term", "ext-ref", "code", "em", "strong", "link", "html"}

# Phrases that signal process / round breadcrumbs in prose — the kit
# documents current behaviour, never how it got there. Matched
# case-insensitively, word-boundary-anchored where it matters.
_FORBIDDEN_PROSE_PATTERNS = [
    re.compile(r"\bround[- ]\d+\b", re.IGNORECASE),
    re.compile(r"\bv\d+ review\b", re.IGNORECASE),
    re.compile(r"\bfixed in round\b", re.IGNORECASE),
    re.compile(r"\bsince round\b", re.IGNORECASE),
    re.compile(r"\b(?:from |in )earlier rounds?\b", re.IGNORECASE),
]


def _placeholder_message(hit: str) -> str:
    """Also two emitters. "Word-search for placeholders before
    delivering" was a step in the skill's manual checklist, which is the
    wrong place for anything a regex can do — a checklist step is
    skipped silently and a check is not.
    """
    return (
        f"Prose still carries the placeholder {hit!r}. Replace it or delete the sentence before delivering."
    )


def _process_breadcrumb_message(hit: str) -> str:
    """One message, two emitters — a b[] string and prose nested inside
    a typed payload both raise this, and the two copies had already
    drifted apart in punctuation.

    It names the escape because the author reading it is usually right:
    a report that corrects an earlier round has to be able to cite that
    round, and without a named way out the only way past `--strict` is
    to rewrite every citation into a date, which loses the reference.
    """
    return (
        f"Prose contains process/history reference {hit!r}; the kit documents "
        "current behaviour only. A page whose SUBJECT is a history — a report "
        "citing an earlier round, an audit, a changelog — declares "
        "`documents_history: true` in its front-matter and is exempt."
    )


def _load_registry(kit_dir: Path, kind: str) -> dict:
    """Load all glossary or extrefs JSON files under kit/{kind}/ and
    return a {term_key: {domain, langs}} index. Term keys are stored
    lowercase for case-insensitive matching."""
    out: dict = {}
    base = kit_dir / kind
    if not base.is_dir():
        return out
    for f in base.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        domain = data.get("domain") or f.stem
        for term, langs in (data.get("entries") or {}).items():
            key = term.lower()
            entry = out.setdefault(key, {"domain": domain, "term": term, "langs": set()})
            if isinstance(langs, dict):
                for lang in langs:
                    entry["langs"].add(lang)
    return out


_MD_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s*\{#([\w-]+)\})?\s*$")
# Registry ids are human-readable keys, spaces included ("Iceberg paper",
# "Time travel") — a \w-only id silently skipped most real references,
# so unresolved ones were never reported.
_MD_GLOSS_REF_RE = re.compile(r"\]\(#g/([^)\n]+?)\)")
_MD_EXTREF_REF_RE = re.compile(r"\]\(#x/([^)\n]+?)\)")
# Every inline-link destination, with the optional title dropped. Images
# share the syntax and are collected too: a src that resolves nowhere is
# the same defect wearing a different tag.
_MD_LINK_TARGET_RE = re.compile(r"\]\(\s*<?([^)\s<>]+?)>?(?:\s+[\"'(][^\n]*?)?\s*\)")
# A destination the kit does not own: another origin, a registry
# reference (checked separately), or a data URI.
_FOREIGN_HREF_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#g/|#x/|#f/)", re.I)
# The three primitives an author writes as a link rather than a fence.
# They were reachable from the skill briefing and from docs/reference.md,
# and from nothing that ships in the wheel — `oku spec` listed 17 block
# kinds and 53 chart types and did not know these existed. A primitive
# nobody can discover is the failure that command exists to fix, so the
# names live here, `oku spec` prints them from this table, and
# test_authority_agreement holds it against the prefixes renderer.js
# actually dispatches on.
_INLINE_KINDS = {"filepath": "#f/", "glossary-term": "#g/", "ext-ref": "#x/"}
_MD_SETEXT_EQ_RE = re.compile(r"^=+\s*$")
_MD_HR_RE = re.compile(r"^-{3,}\s*$")
_MD_HTML_ISLAND_RE = re.compile(r"^</?([a-zA-Z][\w-]*)(?:[\s/>]|$)")
# Inline-level tags never open an island — mirrors INLINE_HTML_TAGS in
# renderer.js: a paragraph that starts with one of these stays prose,
# and parseInline renders it there. The two halves are one list because
# a tag in only one of them ships as visible angle brackets.
_INLINE_HTML_TAGS = {
    "a",
    "abbr",
    "b",
    "br",
    "cite",
    "code",
    "del",
    "em",
    "i",
    "ins",
    "kbd",
    "mark",
    "q",
    "s",
    "samp",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "u",
    "var",
}
# A code span, bounded by the paragraph it sits in. The opening run is
# 1..10 backticks and the body takes anything that does not start that
# same run and does not cross a BLANK line — which is CommonMark's own
# rule, and the renderer's: `joinParagraph` glues a paragraph's lines
# before inline parsing, so a span may wrap across one newline and can
# never reach past the paragraph.
#
# It was defined twice — here, and `(`+)(?:.|\n)*?\1` two thousand lines
# below, which won at call time for BOTH. That one pairs any backtick run
# with the next equal run across ANY distance, so one stray backtick in
# prose swallowed everything up to the next code span on the page. The
# swallowed region is invisible to `collect_page_assets`, so an image in
# it was never copied into `dist/site` and never inlined into the
# standalone page — the reader got a broken image and the build said
# nothing — and invisible to the link scan that would have reported the
# same region's broken links.
#
# The 1..10 bound is what keeps it linear: the unbounded `(`+)` form
# backtracks over every run length at every position, and 8000
# consecutive backticks took 11.6 s to scan (the old cross-line form took
# 17 s at 4000). Bounded, the same input is under a millisecond. A span
# opened with more than ten backticks is not recognised, and that
# direction is the safe one — an unrecognised span means a link inside it
# is CHECKED rather than a real reference being dropped.
_INLINE_CODE_RE = re.compile(r"(`{1,10})(?:(?!\1)(?:[^\n]|\n(?![ \t]*\n)))*\1")


def _mask_code_spans(text: str) -> str:
    """Blank inline code spans, keeping every line break and every
    column.

    The other way to ignore a code span is to delete it, which is what
    the reference collectors do — they report no position. A rule that
    reports `file:line` cannot: dropping the span moves everything after
    it, so the locator names a line the author has to count to find.
    """
    return _INLINE_CODE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _md_island_tag(line: str) -> str | None:
    """Tag name when the line opens a block-level HTML island, else None."""
    m = _MD_HTML_ISLAND_RE.match(line)
    if not m:
        return None
    tag = m.group(1).lower()
    return None if tag in _INLINE_HTML_TAGS else tag


# Elements that never take a closing tag. Mirrors VOID_HTML_TAGS in
# renderer.js — an island holding one of these leaves nothing open.
_VOID_HTML_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
# Elements whose body is text, not markup — an island opened by one runs
# to its closing tag whatever blank lines are inside it.
_RAW_TEXT_TAGS = {"script", "style", "pre", "textarea"}
_HTML_TAG_RE = re.compile(r"<(/?)([a-zA-Z][\w-]*)([^>]*)>")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_HTML_RAW_TEXT_RE = re.compile(r"<(script|style|textarea)\b[^>]*>.*?</\1\s*>", re.I | re.S)
# Spliced from the set above rather than spelled again — a tag on one
# list and not the other is a <pre> whose body is read as prose.
_RAW_TEXT_OPEN_RE = re.compile(r"<(?:" + "|".join(sorted(_RAW_TEXT_TAGS)) + r")\b", re.I)
_RAW_TEXT_CLOSE_RE = re.compile(r"</(?:" + "|".join(sorted(_RAW_TEXT_TAGS)) + r")\s*>", re.I)


def _island_balance(src: str, stack: list[tuple[str, int]], lineno: int = 0) -> None:
    """Apply one island line's tags to a stack of still-open elements.

    Mirrors ``islandPieces`` in renderer.js. A blank line ends an HTML
    *block*, never the element — so what an island leaves open takes the
    blocks that follow, and this is the same walk the renderer does to
    decide where they go. The stack is mutated in place; each entry is
    the tag and the line that opened it.
    """
    scan = _HTML_RAW_TEXT_RE.sub(lambda m: " " * len(m.group(0)), _HTML_COMMENT_RE.sub("", src))
    for m in _HTML_TAG_RE.finditer(scan):
        tag = m.group(2).lower()
        if tag in _VOID_HTML_TAGS:
            continue
        if m.group(1):
            opened = [i for i, (t, _) in enumerate(stack) if t == tag]
            if opened:
                del stack[opened[-1] :]
            elif stack:
                stack.pop()
        elif not m.group(3).rstrip().endswith("/"):
            stack.append((tag, lineno))


_PROSE_SKIP_KEYS = {"src", "source", "code", "k", "language", "lang"}


def _iter_block_strings(obj):
    """Yield every string nested anywhere inside a typed block payload."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from _iter_block_strings(x)
    elif isinstance(obj, dict):
        for key, v in obj.items():
            if key in _PROSE_SKIP_KEYS:
                continue
            yield from _iter_block_strings(v)


def _iter_block_hrefs(obj):
    """Yield every `href` value nested anywhere inside a typed block.

    A compare-card, a step card and a table row can each carry one, and
    `compare-grid`'s preview mechanism depends on the href resolving to
    an in-page anchor — so an href that lands nowhere costs a figure,
    not just a click.
    """
    if isinstance(obj, list):
        for x in obj:
            yield from _iter_block_hrefs(x)
    elif isinstance(obj, dict):
        for key, v in obj.items():
            if key == "href" and isinstance(v, str):
                yield v
            else:
                yield from _iter_block_hrefs(v)


def _split_md_fences(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str, str]]]:
    """Split a markdown string into prose lines and fence records.

    Returns (prose_lines, fences) where prose_lines is [(lineno, line)]
    OUTSIDE fenced code, and fences is [(lineno, lang, body)] for every
    fenced block. Line numbers are 1-based within the string.
    """
    lines = text.split("\n")
    prose: list[tuple[int, str]] = []
    fences: list[tuple[int, str, str]] = []
    close_re: re.Pattern | None = None
    fence_start = 0
    fence_lang = ""
    fence_body: list[str] = []
    for i, line in enumerate(lines, start=1):
        if close_re is not None:
            if close_re.match(line):
                fences.append((fence_start, fence_lang, "\n".join(fence_body)))
                close_re = None
                fence_body = []
            else:
                fence_body.append(line)
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m:
            close_re = _fence_close_re(m.group(1))
            fence_start = i
            fence_lang = (m.group(2) or "").lower()
            continue
        prose.append((i, line))
    if close_re is not None:
        fences.append((fence_start, fence_lang, "\n".join(fence_body)))
    return prose, fences


def _lint_md_string(
    text: str,
    *,
    skip_prose: bool,
    skip_history: bool = False,
    open_els: list[tuple[str, int]] | None = None,
    abs_line: Callable[[int], int | None] | None = None,
) -> tuple[
    list[tuple[str, str, str, str]],
    list[tuple[int, str]],
    list[str],
    list[str],
]:
    """Lint one markdown b[] string.

    Returns (issues, heading_ids, glossary_terms, extref_names) where
    issues are (severity, code, locator, message) tuples and
    heading_ids are (lineno, id) pairs for page-level duplicate checks.
    Locators are 1-based line numbers within the string.

    Covers the strict-GFM subset (setext headings, ambiguous `---`,
    indented code candidates, lazy blockquote continuation), the
    HTML-island audit, and oku-* fences that failed to lift.

    `skip_prose` turns off every prose rule, for a page materialised
    from repo markdown the kit does not own. `skip_history` turns off
    ONE of them. They are separate because a page that legitimately
    cites a prior round is still a page the author is writing, and a
    `TODO` left in it is still a `TODO` — folding the exemption into
    `skip_prose` would have taken `placeholder-text` with it.
    """
    issues: list[tuple[str, str, str, str]] = []
    heading_ids: list[tuple[int, str]] = []
    prose, fences = _split_md_fences(text)

    for lineno, lang, _body in fences:
        if lang.startswith("oku-"):
            # A kind that has a markdown form is not a missing feature —
            # it is the same feature spelled the one way that works. Say
            # which, rather than making the author infer it from a list
            # that does not contain what they typed.
            kind = lang[4:]
            instead = _MARKDOWN_FORM_OF.get(kind)
            detail = (
                f" `{kind}` has no fence: write it as {instead}."
                if instead
                else f" The body must be a single JSON object and the kind one of {sorted(_FENCE_KINDS)}."
            )
            issues.append(
                (
                    "error",
                    "fence-not-lifted",
                    f"line {lineno}",
                    f"```{lang} fence did not lift to a typed block.{detail}",
                )
            )
        elif not lang:
            issues.append(
                (
                    "info",
                    "code-no-language",
                    f"line {lineno}",
                    "Code fence has no language tag; Prism syntax highlighting and the language pill are skipped.",
                )
            )

    prev_nonblank: str | None = None
    prev_blank = True
    in_island = False
    raw_text_close: re.Pattern[str] | None = None
    # Elements an island opened and has not closed yet. The renderer
    # keeps writing into them, so one that never closes swallows the
    # rest of the section — the same defect the truncation used to be,
    # from the other side, and equally silent.
    #
    # Handed in by the caller when the page has more than one markdown
    # string, because a typed fence CUTS one document into several and
    # the tags do not care where the cut fell: an island opened before an
    # `oku-insight` fence is closed after it, in a different `b[]` entry.
    # Scanning each entry from empty reported that island as never
    # closed, at error severity, which refused to build every other page
    # in the tree as well. The renderer carries the same state across the
    # same boundary (`emitMarkdown`'s `carry`), and these two have to
    # agree or one of them is lying about a page the other draws.
    carried = open_els is not None
    open_els = open_els if open_els is not None else []

    def _open_line(lineno: int) -> int:
        # An entry outlives the block that pushed it, so a line number
        # relative to that block is meaningless by the time it is
        # reported. When the caller carries the stack it also knows how
        # to resolve a line against the whole page, and does it here —
        # once, at push time — rather than the caller re-resolving a
        # number whose origin block it can no longer identify.
        return (abs_line(lineno) or lineno) if abs_line else lineno

    def _report_unclosed(boundary: str) -> None:
        for tag, opened_at in open_els:
            issues.append(
                (
                    "error",
                    "island-unclosed",
                    f"line {opened_at}",
                    f"HTML island <{tag}> is never closed {boundary}. Everything after it is "
                    f"written inside it — add the matching </{tag}>.",
                )
            )
        open_els.clear()

    # A `TODO` in backticks is the token being NAMED — the kit's own
    # severity table has to spell the four it catches, and did, in a
    # payload the rule did not reach — while a bare TODO is one left
    # behind. Masked rather than stripped so `line {lineno}` still
    # points at the line the author sees.
    #
    # The breadcrumb rule deliberately does NOT mask. `round-5` in a
    # code span is still a citation of a round, which
    # `test_round_breadcrumb_in_inline_text_flagged` pins, and a page
    # whose subject IS that history has `documents_history` instead.
    masked = dict(
        zip(
            [ln for ln, _ in prose],
            _mask_code_spans("\n".join(line for _, line in prose)).split("\n"),
        )
    )

    in_raw_text = False
    for lineno, line in prose:
        stripped = line.strip()
        if not stripped:
            prev_nonblank = None
            prev_blank = True
            # A blank line ends the html BLOCK. The element stays open —
            # that is what lets an author put markdown inside an island —
            # so `open_els` is deliberately untouched here. A raw-text
            # element (<pre>, <script>) does not even end its block.
            if raw_text_close is None:
                in_island = False
            continue
        if raw_text_close is not None:
            if raw_text_close.search(line):
                _island_balance(line, open_els, _open_line(lineno))
                raw_text_close = None
                in_island = False
            prev_nonblank = line
            prev_blank = False
            continue
        island_tag = None if in_island else _md_island_tag(line)
        if island_tag:
            # One island, one note. A blank line inside an island starts
            # a second html block — `</div>` on its own line is one —
            # and reporting each of them names the same island twice.
            if not open_els:
                issues.append(
                    (
                        "info",
                        "html-island",
                        f"line {lineno}",
                        f"Raw HTML island <{island_tag}> — renders fully in the kit, stripped by external markdown viewers.",
                    )
                )
            in_island = True
            if island_tag in _RAW_TEXT_TAGS:
                closer = re.compile(r"</" + island_tag + r"\s*>", re.I)
                _island_balance(line, open_els, _open_line(lineno))
                if not closer.search(line):
                    raw_text_close = closer
                prev_nonblank = line
                prev_blank = False
                continue
        # An island is markup the reader sees THROUGH, so what is
        # written between its tags is prose. These two rules used to sit
        # at the foot of this loop, past three `continue`s, so a `TODO`
        # or a round citation inside a <div> was never looked at.
        #
        # A raw-text element is the exception, and NESTED raw text is
        # why this is tracked here rather than left to the branches
        # above: those arm only on an island's opening tag, so a <pre>
        # inside a <div> — the idiom the kit documents for multi-line
        # code in an island — is an ordinary island line to them. `//
        # TODO: implement` in a code sample is the sample.
        # Counted on the MASKED line, or a sentence ABOUT raw text arms
        # the suppression: this repo's own roadmap says "a `<pre>` inside
        # a `<div>`", which opened a raw-text element that never closed
        # and silenced both rules for every line after it in the block.
        # A real `<pre>` is never written inside a code span.
        code_line = masked.get(lineno, line)
        opens = len(_RAW_TEXT_OPEN_RE.findall(code_line))
        closes = len(_RAW_TEXT_CLOSE_RE.findall(code_line))
        line_is_code = in_raw_text or opens > 0
        if opens > closes:
            in_raw_text = True
        elif closes > opens:
            in_raw_text = False
        if not skip_prose and not line_is_code:
            if not skip_history:
                for pat in _FORBIDDEN_PROSE_PATTERNS:
                    m = pat.search(line)
                    if m:
                        issues.append(
                            (
                                "warning",
                                "process-breadcrumb",
                                f"line {lineno}",
                                _process_breadcrumb_message(m.group(0)),
                            )
                        )
                        break
            ph = _PLACEHOLDER_RE.search(masked.get(lineno, line))
            if ph:
                issues.append(
                    (
                        "warning",
                        "placeholder-text",
                        f"line {lineno}",
                        _placeholder_message(ph.group(0)),
                    )
                )

        if in_island:
            _island_balance(line, open_els, _open_line(lineno))
            prev_nonblank = line
            prev_blank = False
            continue
        # A section boundary ends the run of blocks the renderer emits in
        # one pass, so an island still open here does not reach its own
        # closing tag either.
        hlevel = _MD_HEADING_LINE_RE.match(line)
        if hlevel and len(hlevel.group(1)) == 2 and open_els:
            _report_unclosed(f"before the `## {hlevel.group(2)}` heading")
        if _MD_SETEXT_EQ_RE.match(line) and prev_nonblank is not None:
            issues.append(
                (
                    "error",
                    "setext-heading",
                    f"line {lineno}",
                    "Setext heading (`===` underline) is outside the strict-GFM subset — use an ATX `#` heading.",
                )
            )
        elif (
            _MD_HR_RE.match(line)
            and prev_nonblank is not None
            and not prev_nonblank.lstrip().startswith(("|", "-", "#", ">"))
        ):
            issues.append(
                (
                    "warning",
                    "ambiguous-hr",
                    f"line {lineno}",
                    "`---` directly under a text line is a setext heading in CommonMark but an <hr> in the kit — insert a blank line before it.",
                )
            )
        if (
            prev_blank
            and len(line) - len(line.lstrip(" ")) >= 4
            and not re.match(r"^([-*]|\d+\.|>)", stripped)
        ):
            issues.append(
                (
                    "warning",
                    "indented-code",
                    f"line {lineno}",
                    "Indented block after a blank line is an indented code block in CommonMark; the kit treats it as a paragraph. Use a ``` fence, or out-dent.",
                )
            )
        if (
            prev_nonblank is not None
            and prev_nonblank.lstrip().startswith(">")
            and not stripped.startswith(">")
        ):
            issues.append(
                (
                    "warning",
                    "lazy-continuation",
                    f"line {lineno}",
                    "Line continues a blockquote without a `>` marker (lazy continuation) — CommonMark keeps it in the quote, the kit does not. Prefix the line with `> `.",
                )
            )
        hm = _MD_HEADING_LINE_RE.match(line)
        if hm:
            heading_ids.append((lineno, hm.group(3) or _md_slug(hm.group(2)) or "section"))
        prev_nonblank = line
        prev_blank = False

    # The end of a string is not the end of the document when the
    # document was cut into several; the caller reports what is still
    # open once the last one has been walked.
    if not carried:
        _report_unclosed("in this page")

    # Inline code spans hold convention samples (`[label](#g/term-id)`)
    # — never real references; strip before collecting.
    prose_text = _INLINE_CODE_RE.sub("", "\n".join(line for _, line in prose))
    gloss = _MD_GLOSS_REF_RE.findall(prose_text)
    x_refs = _MD_EXTREF_REF_RE.findall(prose_text)
    return issues, heading_ids, gloss, x_refs


_MD_ONE_CODE_SPAN_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_MD_LINK_CONSTRUCT_RE = re.compile(r"\[[^\]]*\]\([^)\n]*\)")


_MD_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _md_fence_mask(md: str) -> str:
    """Blank every fenced code block, keeping the line count.

    A link, a `#f/` reference or a path inside a fence is a picture of
    markdown, not markdown — `docs/reference.md` shows the source of
    every primitive it draws, and this file's own briefing shows a page
    skeleton with `![images](path.png)` in it. Checking those reports
    the author for writing an example.

    Nothing here is new behaviour: `_INLINE_CODE_RE` used to run
    unbounded across newlines, so a fence's opening and closing
    backticks matched each other as ONE enormous code span and the body
    fell out of every scan by accident. Bounding that regex to a
    paragraph — which is what stops it backtracking for eleven seconds
    on a page with an odd backtick — took the accident away, so the
    exclusion is stated on purpose instead.

    CommonMark's closing rule, not a toggle: a closer is the same
    character, at least as long as the opener, and carries no info
    string. A toggle reads ```` ```oku-chart ```` as the END of an
    enclosing ```` ```markdown ```` block and everything after it
    inverts.
    """
    out: list[str] = []
    fence: tuple[str, int] | None = None
    for line in md.split("\n"):
        m = _MD_FENCE_OPEN_RE.match(line)
        if fence is None:
            if m:
                fence = (m.group(1)[0], len(m.group(1)))
                out.append("")
                continue
            out.append(line)
            continue
        if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not m.group(2).strip():
            fence = None
        out.append("")
    return "\n".join(out)


def _md_code_spans(md: str):
    """Yield `(line, text)` for every inline code span outside a fence.

    The inverse of `_INLINE_CODE_RE`, which every other pass uses to
    throw code spans away. This one keeps them, because a path written
    in one is the thing `path-in-code-span` is looking for.

    Three exclusions. Two are about not reporting an author who already
    did the right thing: a fenced block is a program, not prose about a
    file, and a code span inside a link label is already clickable — the
    label of a `#f/` link sits inside the chip the nudge would
    recommend, and ``[`docs/charts.md`](charts.md)`` — a real line in
    this repo — points the reader at the rendered page, which is a
    better destination than a preview of its source.

    The third is about not reporting a span that is not one. Between an
    island's `<pre>` and its `</pre>` the renderer hands the region to
    the browser as markup, so a backtick there is a character the reader
    SEES and there is no span to convert; a chip could not render inside
    a `<pre>` either. `oku check --fix` declined to rewrite those from
    the day it landed, which left the check naming a warning with no
    remedy behind it — the shape that teaches an author to stop reading
    the report. Counted on the MASKED line, for the reason the island
    lint states beside the same two regexes: prose writes "a `<pre>`
    inside a `<div>`", and that sentence is not an open tag.
    """
    raw_depth = 0
    for lineno, line in enumerate(_md_fence_mask(md).splitlines(), 1):
        code_line = _mask_code_spans(_HTML_COMMENT_RE.sub("", line))
        opened = len(_RAW_TEXT_OPEN_RE.findall(code_line))
        closed = len(_RAW_TEXT_CLOSE_RE.findall(code_line))
        inside = raw_depth or opened > closed
        raw_depth = max(0, raw_depth + opened - closed)
        if inside:
            continue
        for m in _MD_ONE_CODE_SPAN_RE.finditer(_MD_LINK_CONSTRUCT_RE.sub("", line)):
            yield lineno, m.group(1).strip()


def _looks_like_a_path(text: str) -> bool:
    """Cheap gate before the filesystem is asked about a code span.

    A page carries hundreds of code spans and two or three of them name
    files; resolving every `--dry-run`, `k`, `title` and `SELECT *`
    against the disk would be one stat per span.

    A separator is required, and that is precision rather than economy.
    A bare `kit.json` in "add a kit.json to your project" names a file
    the READER is going to create; that this repo happens to have one of
    its own does not make it the file the sentence is about. Measured on
    this repo's docs, requiring a separator drops 8 of 12 notes and
    every one it drops is that case. A check that guesses trains authors
    to ignore checks, so the nudge takes the loss.
    """
    if not (2 <= len(text) <= 200) or any(c.isspace() for c in text):
        return False
    if text.startswith(("-", "#", "$", "@")) or "://" in text:
        return False
    return "/" in text


def _chippable_path(text: str) -> bool:
    """`_looks_like_a_path` decides whether to ASK the filesystem; this
    decides whether the answer can be written as a link.

    A `#f/` chip is `[`p`](#f/p)`, so a path holding a bracket or a
    paren would end the label or the target early and leave the reader
    with broken markdown where they had a working code span. Rare, and
    the check reports those anyway — the nudge is still right, it is
    only the mechanical rewrite that has to decline.
    """
    return not any(c in text for c in "[]()`")


def _chip_link(path: str) -> str:
    """The one spelling of a file reference, in one place.

    The check's message, the rewrite and the briefing all quote this
    form, and a second copy of it is how the message comes to recommend
    something the rewrite does not produce.
    """
    return f"[`{path}`](#f/{path})"


def _rewrite_code_span_paths(md: str, resolves) -> tuple[str, list[str]]:
    """Turn every certain code-span path in one markdown source into a
    chip, and say which paths moved.

    `resolves(text)` is the caller's — it owns the filesystem question,
    so this function is the same rewrite whether it is asked about a real
    tree or a fixture, and the check and the fix cannot disagree about
    which spans qualify by asking different questions.

    Four places a backtick appears that this must not touch:

    - **Front matter.** A backtick in a YAML scalar is not prose.
    - **A plain fence.** ```` ```bash ```` holds a program, and a path in
      a program is the program.
    - **A raw-text island region.** Between `<pre>` and `</pre>` the
      backticks are literal characters the reader sees, because the
      renderer hands that region to the browser as markup.
    - **A link construct.** The span is already clickable, and the label
      of a chip sits inside one.

    A TYPED fence is rewritten, and that is the case the whole thing is
    for: an `oku-table` cell is prose an author wrote, and a table is
    where a path most often ends up as a bare code span. The body is
    JSON and the rewrite is textual, which is safe for one reason worth
    stating — JSON's grammar has no backtick outside a string literal,
    so a matched span is inside one by construction, and the replacement
    introduces no character JSON escapes. The body is re-parsed anyway
    before it is kept: a fence that stops being JSON is reverted whole
    rather than written out broken.
    """
    lines = md.split("\n")
    out: list[str] = []
    rewritten: list[str] = []
    i = 0

    # Front matter, copied through untouched.
    if lines and lines[0].strip() == "---":
        out.append(lines[0])
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            out.append(lines[i])
            i += 1
        if i < len(lines):
            out.append(lines[i])
            i += 1

    def rewrite_line(line: str) -> str:
        blocked = [(m.start(), m.end()) for m in _MD_LINK_CONSTRUCT_RE.finditer(line)]
        pieces: list[str] = []
        last = 0
        for m in _MD_ONE_CODE_SPAN_RE.finditer(line):
            if any(a <= m.start() < b for a, b in blocked):
                continue
            text = m.group(1).strip()
            if not (_looks_like_a_path(text) and _chippable_path(text) and resolves(text)):
                continue
            pieces.append(line[last : m.start()])
            pieces.append(_chip_link(text))
            rewritten.append(text)
            last = m.end()
        if not pieces:
            return line
        pieces.append(line[last:])
        return "".join(pieces)

    fence: tuple[str, int, str] | None = None
    body_new: list[str] = []
    body_old: list[str] = []
    mark = 0
    raw_depth = 0
    for line in lines[i:]:
        m = _MD_FENCE_OPEN_RE.match(line)
        if fence is None:
            if m:
                info = m.group(2).strip()
                fence = (m.group(1)[0], len(m.group(1)), info)
                body_new, body_old, mark = [], [], len(rewritten)
                out.append(line)
                continue
            # A raw-text region inside an island is markup the reader
            # sees, so its backticks are characters and not a span.
            # Counted on the MASKED line, for the reason the island lint
            # states next to the same two regexes: this repo's own prose
            # writes "a `<pre>` inside a `<div>`", and counting that as
            # an opening tag armed a suppression that never lifted —
            # measured, it silenced 8 of the 10 rewrites on this repo's
            # own docs, every one of them on a line of ordinary prose.
            code_line = _mask_code_spans(_HTML_COMMENT_RE.sub("", line))
            opened = len(_RAW_TEXT_OPEN_RE.findall(code_line))
            closed = len(_RAW_TEXT_CLOSE_RE.findall(code_line))
            out.append(line if (raw_depth or opened > closed) else rewrite_line(line))
            raw_depth = max(0, raw_depth + opened - closed)
            continue
        closing = m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not m.group(2).strip()
        if not closing:
            body_old.append(line)
            body_new.append(rewrite_line(line) if fence[2].startswith("oku-") else line)
            continue
        if body_new != body_old:
            try:
                json.loads("\n".join(body_new))
            except (ValueError, TypeError):
                # The rewrite broke the payload, which it should not be
                # able to do — so keep the fence the author wrote and
                # report nothing for it, rather than writing out a page
                # the renderer cannot read.
                body_new = body_old
                del rewritten[mark:]
        out.extend(body_new)
        out.append(line)
        fence = None
    if fence is not None:
        # An unclosed fence is a page `oku check` already refuses; leave
        # what the author wrote where the lint can name it.
        out.extend(body_old)
        del rewritten[mark:]
    return "\n".join(out), rewritten


_MD_FOOTNOTE_DEF_RE = re.compile(r"^ {0,3}\[\^([^\]]+)\]:")
_MD_FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+?)\]")
_MD_LINK_DEF_RE = re.compile(r"^ {0,3}\[([^\]^][^\]]*)\]:\s*(\S+)")
_MD_LINK_REF_RE = re.compile(r"\[([^\]]+?)\]\[([^\]]*?)\]")


def _md_reference_definitions(strings: list[str]) -> tuple[set[str], set[str]]:
    """Collect footnote and link-reference definitions across every
    markdown string of one page — the scope the renderer resolves in."""
    fn_defs: set[str] = set()
    link_defs: set[str] = set()
    for text in strings:
        prose, _ = _split_md_fences(text)
        for _, line in prose:
            m = _MD_FOOTNOTE_DEF_RE.match(line)
            if m:
                fn_defs.add(m.group(1))
                continue
            m = _MD_LINK_DEF_RE.match(line)
            if m:
                link_defs.add(m.group(1).lower())
    return fn_defs, link_defs


def _lint_md_reference_forms(
    text: str, fn_defs: set[str], link_defs: set[str]
) -> list[tuple[str, str, str, str]]:
    """Report a footnote or reference link with no definition anywhere on
    the page. The renderer leaves it as literal source text, so nothing
    else in the pipeline tells the author it did not resolve."""
    issues: list[tuple[str, str, str, str]] = []
    prose, _ = _split_md_fences(text)
    for lineno, raw in prose:
        if _MD_FOOTNOTE_DEF_RE.match(raw) or _MD_LINK_DEF_RE.match(raw):
            continue
        line = _INLINE_CODE_RE.sub("", raw)
        for fid in _MD_FOOTNOTE_REF_RE.findall(line):
            if fid not in fn_defs:
                issues.append(
                    (
                        "warning",
                        "undefined-footnote",
                        f"line {lineno}",
                        f"Footnote reference [^{fid}] has no [^{fid}]: definition on this page; it renders as literal text.",
                    )
                )
        for text, label in _MD_LINK_REF_RE.findall(line):
            key = (label or text).lower()
            if key not in link_defs:
                issues.append(
                    (
                        "warning",
                        "undefined-link-reference",
                        f"line {lineno}",
                        f"Reference link [{text}][{label}] has no [{key}]: definition on this page; it renders as literal text.",
                    )
                )
    return issues


def _md_heading_level_skips(body: list) -> list[tuple[str, int, str]]:
    """Find headings that jump more than one level down (## → ####).

    The outline is what a screen reader announces and what the on-page
    TOC nests by, so a skipped level is a structural defect, not a
    styling preference. Levels are tracked across the whole page: a
    typed fence opens a new b[] string mid-section, and the heading
    before it still counts.
    """
    out: list[tuple[str, int, str]] = []
    prev = 0
    for idx, blk in enumerate(body):
        if not isinstance(blk, str):
            continue
        prose, _ = _split_md_fences(blk)
        for lineno, line in prose:
            m = _MD_HEADING_LINE_RE.match(line)
            if not m:
                continue
            level = len(m.group(1))
            if prev and level > prev + 1:
                out.append((f"b[{idx}]", lineno, f"h{prev} → h{level}"))
            prev = level
    return out


def _known_chart_types() -> list[str]:
    """Chart `type` values, read from the schema enum — the single
    source of truth. Empty when the schema is unavailable; callers must
    treat empty as "unknown set", never as "nothing is valid"."""
    schema = _load_schema()
    if not isinstance(schema, dict):
        return []
    try:
        enum = schema["$defs"]["chart"]["properties"]["type"]["enum"]
    except (KeyError, TypeError):
        return []
    return [t for t in enum if isinstance(t, str)]


# Fields inside one row of a chart payload that carry an order. A pair
# written the wrong way round is a data error the author can fix, and it
# is not one a reader can see: the renderer orders the pair before it
# draws (`markSpan` in chrome.js), so a box-plot with q3 below q1 draws a
# perfectly ordinary box in the wrong place. Before that it drew nothing
# at all and logged `<rect> attribute width: A negative value is not
# valid` — which named the attribute and not the chart, so the report
# that arrived said the kit was broken.
#
# Equality passes throughout. A zero-width bin or a task that starts and
# ends in the same week is degenerate, not inverted, and a check that
# guesses at intent is one authors learn to ignore.
_CHART_ORDERED_PAIRS: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "box-plot": ("boxes", (("min", "q1"), ("q1", "median"), ("median", "q3"), ("q3", "max"))),
    "range-bar": ("ranges", (("low", "mid"), ("mid", "high"), ("low", "high"))),
    "histogram": ("bins", (("lo", "hi"),)),
    "gantt": ("tasks", (("start", "end"),)),
    "candlestick": (
        "entries",
        (("low", "open"), ("low", "close"), ("open", "high"), ("close", "high"), ("low", "high")),
    ),
}


def _chart_shape_issues(blk: dict) -> list[tuple[str, str]]:
    """Chart payload sanity by type — friendlier than the raw schema
    error. Returns (code, message) tuples."""
    out: list[tuple[str, str]] = []

    def bad(code: str, message: str) -> None:
        out.append((code, message))

    ctype = blk.get("type")
    known = _known_chart_types()
    if ctype is not None and known and ctype not in known:
        # A near match answers the question outright; without one the
        # author still needs the menu, and dropping it in favour of the
        # suggestion left them with less than before.
        near = _did_you_mean(ctype, known)
        menu = "" if near else f" Known: {', '.join(known)}."
        bad(
            "chart-unknown-type",
            f"chart type '{ctype}' is not supported.{near}{menu} "
            "`oku spec <type>` prints a payload for any of them.",
        )
        return out

    # Every chart needs data, and only 22 of the 53 types had a shape
    # check saying so. Measured by emptying each shipped example's main
    # data array: 12 types passed every gate, and dropping the key
    # entirely got 17 through — each rendering a box with nothing in it,
    # which is the one failure no linter was catching.
    #
    # One rule rather than 53: a chart with no populated collection
    # anywhere cannot draw, whatever its type. Scalars alone are never
    # enough — even a gauge carries `zones`.
    if ctype is not None and not any(
        isinstance(v, (list, dict)) and len(v) > 0 for k, v in blk.items() if k not in ("k", "type")
    ):
        bad(
            "chart-no-data",
            f"chart with type:{ctype} carries no data — every collection in it is empty or absent, "
            "so it renders as an empty box. `oku spec "
            f"{ctype}` prints a payload with the right shape.",
        )
    if ctype == "bar":
        if not blk.get("rows"):
            bad("chart-bar-missing-rows", "chart with type:bar requires a `rows` array.")
    elif ctype in ("scatter", "line", "area", "bubble", "quadrant"):
        if not blk.get("series"):
            bad("chart-cartesian-missing-series", f"chart with type:{ctype} requires a `series` array.")
        if ctype == "quadrant" and not blk.get("quadrants"):
            bad(
                "chart-quadrant-missing-quadrants",
                "chart with type:quadrant requires a `quadrants` object ({x, y, labels?}).",
            )
    elif ctype in ("stacked-bar", "grouped-bar"):
        if not blk.get("categories"):
            bad(
                "chart-multi-bar-missing-categories",
                f"chart with type:{ctype} requires a `categories` array.",
            )
        if not blk.get("series"):
            bad("chart-multi-bar-missing-series", f"chart with type:{ctype} requires a `series` array.")
    elif ctype in ("donut", "pie"):
        if not blk.get("slices"):
            bad("chart-donut-missing-slices", f"chart with type:{ctype} requires a `slices` array.")
    elif ctype == "heatmap":
        if not blk.get("cells"):
            bad("chart-heatmap-missing-cells", "chart with type:heatmap requires a `cells` 2D array.")
    elif ctype == "sparkline":
        if not blk.get("values"):
            bad("chart-sparkline-missing-values", "chart with type:sparkline requires a `values` array.")
    elif ctype == "waffle":
        if not blk.get("segments"):
            bad("chart-waffle-missing-segments", "chart with type:waffle requires a `segments` array.")
    elif ctype == "gauge":
        if blk.get("value") is None or blk.get("max") is None:
            bad("chart-gauge-missing-fields", "chart with type:gauge requires `value` and `max`.")
    elif ctype == "radar":
        if not blk.get("axes") or not blk.get("series"):
            bad("chart-radar-missing-fields", "chart with type:radar requires `axes` and `series`.")
    elif ctype == "box-plot":
        if not blk.get("boxes"):
            bad("chart-boxplot-missing-boxes", "chart with type:box-plot requires a `boxes` array.")
    elif ctype == "bullet":
        if not blk.get("tracks"):
            bad("chart-bullet-missing-tracks", "chart with type:bullet requires a `tracks` array.")
    elif ctype == "slope":
        if not blk.get("items"):
            bad("chart-slope-missing-items", "chart with type:slope requires an `items` array.")
    elif ctype == "histogram":
        if not blk.get("bins"):
            bad(
                "chart-histogram-missing-bins",
                "chart with type:histogram requires a `bins` array of {lo, hi, count}.",
            )
    elif ctype == "calendar-heatmap":
        if not blk.get("date_values"):
            bad(
                "chart-calendar-missing-date-values",
                "chart with type:calendar-heatmap requires a `date_values` object (YYYY-MM-DD → number).",
            )
    elif ctype == "treemap":
        if not blk.get("tree"):
            bad(
                "chart-treemap-missing-tree",
                "chart with type:treemap requires a `tree` array of {label, value}.",
            )
    elif ctype == "ridgeline":
        if not blk.get("distributions"):
            bad(
                "chart-ridgeline-missing-distributions",
                "chart with type:ridgeline requires a `distributions` array.",
            )
    elif ctype == "funnel":
        if not blk.get("stages"):
            bad("chart-funnel-missing-stages", "chart with type:funnel requires a `stages` array.")
    elif ctype in ("sankey", "network"):
        if not blk.get("nodes") or not blk.get("links"):
            bad(
                "chart-graph-missing-payload",
                f"chart with type:{ctype} requires both `nodes` and `links` arrays.",
            )
    elif ctype in ("scatter-matrix", "parallel-coordinates"):
        if not blk.get("variables") or not blk.get("records"):
            bad(
                "chart-multivariate-missing-payload",
                f"chart with type:{ctype} requires both `variables` and `records` arrays.",
            )
    elif ctype == "chord":
        if not blk.get("groups") or not blk.get("matrix"):
            bad(
                "chart-chord-missing-payload",
                "chart with type:chord requires both `groups` and `matrix` (N×N flow matrix).",
            )
    elif ctype == "geo":
        if not blk.get("regions"):
            bad(
                "chart-geo-missing-regions",
                "chart with type:geo requires a `regions` array of {id, value, label?}.",
            )

    if ctype in _CHART_ORDERED_PAIRS:
        key, pairs = _CHART_ORDERED_PAIRS[ctype]
        flipped: list[str] = []
        for i, row in enumerate(blk.get(key) or []):
            if not isinstance(row, dict):
                continue
            for lower, upper in pairs:
                a, b = row.get(lower), row.get(upper)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > b:
                    who = row.get("label") or row.get("date") or f"{key}[{i}]"
                    flipped.append(f"{who}: {lower} {a} is above {upper} {b}")
        if flipped:
            # One line per offending row would bury the page report under a
            # 900-bin histogram; the first two say what the mistake is and
            # the count says how far it goes.
            more = f" (+{len(flipped) - 2} more)" if len(flipped) > 2 else ""
            bad(
                "chart-inverted-range",
                f"chart with type:{ctype} has a range written the wrong way round — "
                f"{'; '.join(flipped[:2])}{more}. The kit draws the pair in order, "
                "so the figure looks right and reads wrong.",
            )
    return out


def check_pages(pages: list, root: Path, kit_dir: Path | None = None) -> list[dict]:
    """Run the full lint pass and return a list of issue dicts.

    Each issue: {path: Path, severity: str, code: str, where: str, message: str}
    severity is one of 'error' | 'warning' | 'info'.
    """
    if kit_dir is None:
        kit_dir = KIT_DIR
    issues: list[dict] = []

    def add(p: Path, severity: str, code: str, where: str, message: str, line: int | None = None) -> None:
        # `line` is for findings that sit at a point INSIDE a block — a
        # link halfway down a prose chunk. Without it the block's own
        # line is used, which is right for a typed fence and can be
        # hundreds of lines off for prose on a page with few fences.
        issues.append(
            {
                "path": p,
                "severity": severity,
                "code": code,
                "where": where,
                "message": message,
                "_line": line,
            }
        )

    # 1. Schema validation — surfaces shape errors before anything else.
    if _HAS_JSONSCHEMA:
        for p, err in validate_pages(pages):
            add(p, "error", "schema", "(root)", err)

    # Load glossary + extref registries once.
    glossary = _load_registry(kit_dir, "glossary")
    extrefs = _load_registry(kit_dir, "extrefs")

    # 2. Stray demo pages — `<thing>-demo.{html,json}` is forbidden;
    # primitive examples live inline in reference.json.
    for p, _data in pages:
        stem = p.stem
        if stem.endswith("-demo") and stem != "markdown-demo":
            add(
                p,
                "error",
                "stray-demo",
                "(filename)",
                f"Demo page '{p.name}' is forbidden — fold the example into docs/primitives.json instead.",
            )

    # Anchors and link destinations are collected per page here and
    # resolved after the loop, because a link can cross pages and the
    # target's anchors are not known until every page has been read.
    anchors_by_page: dict[Path, set[str]] = {}
    links_by_page: dict[Path, list[tuple[str, str]]] = {}

    # Per-page passes — every rule below reads the v2 shape (k/t/m/b).
    # Legacy v1 pages are shimmed through _v1_to_v2 first so the lint
    # surface is format-independent: a page authored as markdown, v2
    # JSON, or v1 JSON gets the same rules.
    for p, page in pages:
        if isinstance(page, dict) and page.get("kind") == "page" and "k" not in page:
            # Deprecated kinds exist only in the v1 vocabulary and the
            # shim silently drops them — flag BEFORE shimming.
            def _walk_v1(blocks, path):
                for i, blk in enumerate(blocks):
                    if not isinstance(blk, dict):
                        continue
                    kind = blk.get("kind")
                    here = f"{path}[{i}]:kind={kind}"
                    if kind in _DEPRECATED_KINDS:
                        add(
                            p,
                            "error",
                            "deprecated-kind",
                            here,
                            f"Block kind '{kind}' is no longer supported. Migrate to: {_DEPRECATED_KINDS[kind]}.",
                        )
                    if kind == "section":
                        _walk_v1(blk.get("blocks") or [], here + ".blocks")
                    elif kind == "info-tip":
                        _walk_v1(blk.get("content") or [], here + ".content")

            _walk_v1(page.get("blocks") or [], "blocks")
            page = _v1_to_v2(page)
        meta = page.get("m") if isinstance(page.get("m"), dict) else {}
        body = page.get("b") or []

        # Pages materialised from repo markdown without front-matter
        # (README, CHANGELOG, CLAUDE and friends) carry author-owned
        # prose verbatim; the process-breadcrumb rule is meant for
        # hand-authored kit pages, so it is skipped for those. All
        # structural rules still apply.
        is_materialised = meta.get("_materialised_by") == "oku-init"

        # And a page whose SUBJECT is a history says so. The rule above
        # scopes itself by who wrote the prose, which is the wrong
        # question for a hand-authored measurement report correcting an
        # earlier round: every citation of that round raised a warning,
        # `oku check --strict` exited 1, and the only way past it was to
        # rewrite each citation into a date — losing the reference the
        # reader needs. Observed at 29 warnings on one document, all on
        # correct prose.
        #
        # Narrow on purpose. It exempts this rule on this page, and
        # nothing else: `placeholder-text` still fires, and a tree-wide
        # switch was not added because it would silently exempt pages
        # written later, from a file nobody opens while writing prose.
        documents_history = meta.get("documents_history") is True

        seen_ids: dict[str, int] = {}
        gloss_refs: list[tuple[str, str, int | None]] = []
        file_refs: list[tuple[str, str, int | None]] = []
        code_spans: list[tuple[str, str, int | None]] = []
        extref_refs: list[tuple[str, str, int | None]] = []
        link_refs: list[tuple[str, str, int | None]] = []
        asset_refs: list[tuple[str, str, int | None]] = []
        # One island stack for the whole page, because a typed fence cuts
        # one markdown document into several `b[]` strings and an island
        # opened before the fence is closed after it. Scanning each string
        # from empty reported that island as never closed, at error
        # severity, which refused to build every other page in the tree
        # too. The renderer carries the same state across the same
        # boundary; these two describe one document and must agree.
        island_open: list[tuple[str, int]] = []
        # Footnote / link-reference definitions resolve page-wide, so they
        # are collected before any string is linted.
        fn_defs, link_defs = _md_reference_definitions([b for b in body if isinstance(b, str)])
        for where, lineno, jump in _md_heading_level_skips(body):
            add(
                p,
                "warning",
                "heading-level-skip",
                f"{where} line {lineno}",
                f"Heading jumps {jump} — a level was skipped, which breaks the document outline for "
                "screen readers and for the on-page TOC.",
            )

        block_starts = _PAGE_BLOCK_LINES.get(p) or {}
        for idx, blk in enumerate(body):
            where = f"b[{idx}]"
            # Every line number the string passes report is relative to
            # the START OF THE BLOCK, and a block boundary is invisible
            # in the source — the author sees one file. Printed raw, the
            # number looks precise and points somewhere else; on the
            # probe that found this, a fence on file line 10 was reported
            # as line 5. `base` is what converts them.
            base = block_starts.get(idx)

            def _abs(rel: int | None, _base: int | None = None) -> int | None:
                _base = base if _base is None else _base
                return _base + rel - 1 if (_base and rel) else None

            # Through `_asset_hrefs` rather than a second set of regexes,
            # so the check reports exactly what the build would publish.
            # A page-level scan would lose the block, and the block is
            # how an author finds the reference in a long file.
            for href in _asset_hrefs(blk):
                pos = blk.find(href) if isinstance(blk, str) else -1
                asset_refs.append((where, href, _abs(blk[:pos].count("\n") + 1) if pos >= 0 else None))

            if isinstance(blk, str):
                # 3. Markdown-string passes: strict-GFM subset, HTML
                # island audit, unlifted fences, process prose.
                str_issues, heading_ids, gloss, x_refs = _lint_md_string(
                    blk,
                    skip_prose=is_materialised,
                    skip_history=documents_history,
                    open_els=island_open,
                    abs_line=_abs,
                )
                str_issues = str_issues + _lint_md_reference_forms(blk, fn_defs, link_defs)
                for severity, code, loc, message in str_issues:
                    m_line = re.search(r"\bline (\d+)", loc or "")
                    if code == "island-unclosed":
                        # Already page-absolute. The island stack is
                        # carried across blocks, so the line a tag opened
                        # on belongs to whichever block that was, and it
                        # was resolved there — re-resolving it here would
                        # measure it from the wrong start.
                        absolute = int(m_line.group(1)) if m_line else None
                        shown = loc
                    else:
                        absolute = _abs(int(m_line.group(1))) if m_line else None
                        shown = re.sub(r"\bline \d+", f"line {absolute}", loc) if absolute else loc
                    add(p, severity, code, f"{where} {shown}", message, line=absolute)
                for lineno, hid in heading_ids:
                    if hid in seen_ids:
                        add(
                            p,
                            "error",
                            "duplicate-anchor",
                            f"{where} line {_abs(lineno) or lineno}",
                            f"Section / heading id '{hid}' already used in this page. Ids are "
                            "document-global, so the second one is unreachable — every link and "
                            "TOC entry lands on the first. Pin a distinct id with {#other-id}.",
                            line=_abs(lineno),
                        )
                    seen_ids[hid] = seen_ids.get(hid, 0) + 1
                gloss_refs.extend((where, t, None) for t in gloss)
                extref_refs.extend((where, x, None) for x in x_refs)
                # Exact line per link: a prose block runs from one typed
                # fence to the next, so on a page with few fences it can
                # be the whole document, and the block's own line would
                # be hundreds of lines from the link that is wrong.
                scrubbed = _INLINE_CODE_RE.sub("", _md_fence_mask(blk))
                for m in _MD_LINK_TARGET_RE.finditer(scrubbed):
                    link_refs.append((where, m.group(1), _abs(scrubbed[: m.start()].count("\n") + 1)))
                for m in _MD_FILE_REF_RE.finditer(scrubbed):
                    file_refs.append((where, m.group(1).strip(), _abs(scrubbed[: m.start()].count("\n") + 1)))
                code_spans.extend((where, text, _abs(rel)) for rel, text in _md_code_spans(blk))
                continue
            if not isinstance(blk, dict):
                add(p, "error", "invalid-block", where, "Block must be a markdown string or a typed object.")
                continue

            kind = blk.get("k")
            where = f"{where}:k={kind}"

            # 4. Deprecated / unknown kinds — flag with migration pointer.
            if kind in _DEPRECATED_KINDS:
                add(
                    p,
                    "error",
                    "deprecated-kind",
                    where,
                    f"Block kind '{kind}' is no longer supported. Migrate to: {_DEPRECATED_KINDS[kind]}.",
                )
            elif kind and kind not in _KNOWN_BLOCK_KINDS:
                add(
                    p,
                    "error",
                    "unknown-kind",
                    where,
                    f"Unknown block kind '{kind}'.{_did_you_mean(kind, _KNOWN_BLOCK_KINDS)} "
                    f"Known: {sorted(_KNOWN_BLOCK_KINDS)}. `oku spec <kind>` prints a payload.",
                )

            # 5. Code blocks should declare a language (Prism + the
            # language pill need it).
            if kind == "code" and not blk.get("language"):
                add(
                    p,
                    "info",
                    "code-no-language",
                    where,
                    "Code block has no `language` field; Prism syntax highlighting and the language pill are skipped.",
                )

            # 6. Chart shape sanity by type.
            if kind == "chart":
                for code, message in _chart_shape_issues(blk):
                    add(p, "error", code, where, message)

            # 6b. Layout primitives with an empty collection render to
            # nothing at all — zero height, no message, no console
            # warning. The author sees a gap and has to guess. Charts
            # are already covered by the shape checks above.
            for empty_kind, field in (
                ("kpi-grid", "tiles"),
                ("step-flow", "steps"),
                ("timeline", "events"),
                ("compare-grid", "cards"),
                # `panels`, not `charts`: it is what `$defs/chart-grid`
                # requires and what `_renderChartGrid` iterates. Keyed on
                # `charts`, this fired on every correctly-authored grid.
                ("chart-grid", "panels"),
            ):
                if kind == empty_kind and not blk.get(field):
                    add(
                        p,
                        "error",
                        f"empty-{empty_kind}",
                        where,
                        f"{empty_kind} has no `{field}`; it renders as a zero-height gap.",
                    )
            # A table carries its rows either in `rows` or under
            # `groups[].rows`, and counting only the first reported every
            # grouped table on the page as empty.
            if kind == "table":
                n_rows = len(blk.get("rows") or [])
                for grp in blk.get("groups") or []:
                    n_rows += len(grp.get("rows") or [])
                if not n_rows and not blk.get("headers"):
                    # No columns and no rows: the renderer emits a
                    # `<table>` with nothing inside it. There is no empty
                    # state this could be — unlike the header-only case
                    # below, which is one.
                    add(
                        p,
                        "error",
                        "empty-table",
                        where,
                        "Table has neither `headers` nor rows; it renders as an empty table element.",
                    )
                elif not n_rows:
                    add(
                        p,
                        "info",
                        "empty-table",
                        where,
                        "Table has headers but no rows — intentional as an empty state, a mistake otherwise.",
                    )

            # Prose nested inside typed payloads (step bodies, card
            # bodies, table cells, …) is markdown too — same glossary /
            # ext-ref resolution and process-prose rules.
            link_refs.extend((where, h, None) for h in _iter_block_hrefs(blk))
            for s in _iter_block_strings(blk):
                s_refs = _INLINE_CODE_RE.sub("", s)
                gloss_refs.extend((where, t, None) for t in _MD_GLOSS_REF_RE.findall(s_refs))
                extref_refs.extend((where, x, None) for x in _MD_EXTREF_REF_RE.findall(s_refs))
                link_refs.extend((where, h, None) for h in _MD_LINK_TARGET_RE.findall(s_refs))
                file_refs.extend((where, f, None) for f in _MD_FILE_REF_RE.findall(s_refs))
                code_spans.extend((where, text, None) for _rel, text in _md_code_spans(s))
                if not is_materialised:
                    # `s_refs` already has the code spans out. Prose in a
                    # step body, a card, a KPI label or a table cell is
                    # prose an author writes and a reader reads, and it
                    # was reached by every content rule but this one — so
                    # a `TODO` left in a paragraph was reported and the
                    # same `TODO` left in the card beside it shipped.
                    ph = _PLACEHOLDER_RE.search(s_refs)
                    if ph:
                        add(p, "warning", "placeholder-text", where, _placeholder_message(ph.group(0)))
                if not is_materialised and not documents_history:
                    for pat in _FORBIDDEN_PROSE_PATTERNS:
                        m = pat.search(s)
                        if m:
                            add(
                                p,
                                "warning",
                                "process-breadcrumb",
                                where,
                                _process_breadcrumb_message(m.group(0)),
                            )
                            break

        # Every block walked: whatever an island still has open now is
        # open at the end of the document, which is the one place the
        # renderer cannot carry it any further either.
        for tag, opened_at in island_open:
            add(
                p,
                "error",
                "island-unclosed",
                f"b[0] line {opened_at}",
                f"HTML island <{tag}> is never closed in this page. Everything after it is "
                f"written inside it — add the matching </{tag}>.",
                line=opened_at,
            )
        island_open.clear()

        anchors_by_page[p] = set(seen_ids)
        links_by_page[p] = link_refs

        # 8. Glossary + ext-ref resolution — every inline reference
        # must land on an entry the kit knows about.
        for where, term, ref_line in gloss_refs:
            if term.lower() not in glossary:
                add(
                    p,
                    "warning",
                    "unresolved-glossary",
                    f"{where} #g/{term}",
                    f"Glossary term '{term}' not found in any kit/glossary/*.json registry."
                    + _did_you_mean(term, glossary),
                    line=ref_line,
                )
        for where, name, ref_line in extref_refs:
            if name.lower() not in extrefs:
                add(
                    p,
                    "warning",
                    "unresolved-extref",
                    f"{where} #x/{name}",
                    f"External reference '{name}' not found in any kit/extrefs/*.json registry."
                    + _did_you_mean(name, extrefs),
                    line=ref_line,
                )

        # 8b. File references. The chip renders and copies whatever
        # happens here — the point of the check is that a preview which
        # will not open is reported at build time rather than found by
        # a reader clicking it.
        for where, href, ref_line in file_refs:
            target, status = resolve_file_ref(href, p)
            if status == "missing":
                add(
                    p,
                    "warning",
                    "filepath-missing",
                    f"{where} #f/{href}",
                    f"No file at '{href}' — tried it against this page's directory and against "
                    "the project root. The chip renders and copies the path; nothing opens.",
                    line=ref_line,
                )
                continue
            if status == "outside":
                add(
                    p,
                    "warning",
                    "filepath-outside",
                    f"{where} #f/{href}",
                    f"'{href}' resolves to {target}, outside the project root "
                    f"({project_root_for(p.parent)}). A page carries the bytes of the files it "
                    "previews, so a reference reaching past the project would publish them; "
                    "this one renders as a path to copy and nothing else.",
                    line=ref_line,
                )
                continue
            payload = _file_ref_payload(href, p)
            if payload.get("status") == "over-cap":
                add(
                    p,
                    "info",
                    "filepath-not-carried",
                    f"{where} #f/{href}",
                    f"'{href}' is {payload.get('bytes')} bytes, over the "
                    f"{payload.get('cap')}-byte cap for content travelling inside a page. "
                    "The chip names the file and copies its path; there is no preview.",
                    line=ref_line,
                )

        # 8c. A path in a code span is a dead end. The reader who
        # wants to see the file leaves the page, finds it, and comes
        # back — which is what every document does with the paths it
        # mentions, and the reason the filepath chip exists. The nudge
        # is decidable, and only fires where it is certain: the span
        # names a file that is really there, inside the project, and
        # the author has not already made it a chip.
        #
        # A WARNING, so it is printed without --verbose and `--strict`
        # answers for it. It was an info note, and an info note is one
        # line of summary naming the code — which is how a primitive
        # ends up unused in the very pages that document it: this repo's
        # own reference page named `src/oku/cli.py` in a table cell, and
        # nothing that ran on every build ever said so out loud. Two
        # things make the raise honest rather than nagging. The gate is
        # already the certain case (`_looks_like_a_path` requires a
        # separator, and the file must resolve inside the project), and
        # `oku check --fix` does the rewrite, so the warning names a
        # remedy that is one command rather than an afternoon.
        #
        # A materialised page is exempt. A README or a CLAUDE.md renders
        # through the kit but is also read on GitHub, where `#f/…` is a
        # link to an anchor that does not exist — so this is the one
        # place the nudge would make the file worse.
        span_counts: dict[str, int] = {}
        span_first: dict[str, tuple[str, int | None]] = {}
        for where, text, span_line in code_spans:
            if is_materialised or not _looks_like_a_path(text):
                continue
            if text not in span_counts:
                _target, status = resolve_file_ref(text, p)
                if status != "ok":
                    span_counts[text] = 0
                    continue
                span_first[text] = (where, span_line)
            if text in span_first:
                span_counts[text] = span_counts.get(text, 0) + 1
        for text, n in span_counts.items():
            if not n:
                continue
            where, span_line = span_first[text]
            # One note per distinct path, and it carries the count: ten
            # cells naming one file is one decision to make and ten
            # edits to make it with, and a reader of the report should
            # be told which number they are looking at.
            times = "" if n == 1 else f" ({n} times on this page)"
            add(
                p,
                "warning",
                "path-in-code-span",
                f"{where} `{text}`",
                f"'{text}' is a file that exists{times}. Written as {_chip_link(text)} the reader "
                "gets a preview on hover, the whole file on click and a button that copies the "
                "path — instead of a string they have to go and find. `oku check --fix` rewrites "
                "every one of these.",
                line=span_line,
            )

        # 8d. An image the project does not own. A standalone page
        # carries the BYTES of everything it shows, so a reference
        # reaching past the project publishes a file from outside it to
        # whoever the page is sent to — and the build did that in
        # silence, because "above the tree being built" is a different
        # question and a repo's `../screenshots/` is a legitimate
        # answer to it. Same fence as `#f/`, same reason.
        for where, href, ref_line in asset_refs:
            if re.match(r"^[a-z][a-z0-9+.-]*:|^//|^#", href, re.I):
                continue
            href_base = root if href.startswith("/") else p.parent
            target = (href_base / unquote(href.lstrip("/"))).resolve()
            if not target.is_file() or asset_within_project(target, p):
                continue
            add(
                p,
                "warning",
                "image-outside",
                f"{where} {href}",
                f"'{href}' resolves to {target}, outside the project root "
                f"({project_root_for(p.parent)}). A standalone page carries the bytes of every "
                "image it shows, so this one would hand a file from outside the project to "
                "whoever the page is sent to. It is left as a reference no delivered page "
                "resolves — copy the file into the project and point at it there.",
                line=ref_line,
            )

        # 9. Page-level metadata sanity. The no-summary nudge applies
        # only to hand-authored kit pages — materialised repo markdown
        # (README, CLAUDE, notes/ …) has no front-matter to carry one.
        meta = _page_meta(page)
        fm_err = meta.get("_front_matter_error")
        if fm_err:
            bad_line, snippet = fm_err
            add(
                p,
                "error",
                "front-matter-malformed",
                f"line {bad_line}",
                f"Front-matter opened with `---` but line {bad_line} is not `key: value`, "
                f"a continuation or a comment: `{snippet}`. The whole block is being read as "
                "body text. Close the front-matter above this line, indent it to continue the "
                "key above, or delete the opening `---`.",
                line=bad_line,
            )
        # `$defs/meta` is `additionalProperties: true` on purpose — a
        # project may carry its own keys — but that also means a typo is
        # accepted in silence. `sumary:` produced nothing beyond the
        # info-level no-summary nudge, which is hidden at default
        # verbosity, so the page shipped without a summary and the check
        # said nothing at all. Permissive about unknown keys, loud about
        # ones that look like a known key spelled wrong.
        if not is_materialised:
            known_meta = _known_meta_keys()
            for key in sorted(meta):
                if key in known_meta or key.startswith("_"):
                    continue
                near = _did_you_mean(key, known_meta)
                if near:
                    add(
                        p,
                        "warning",
                        "unknown-meta-key",
                        f"meta.{key}",
                        f"Front-matter key '{key}' is not one the kit reads.{near} "
                        "`oku spec front-matter` lists them.",
                    )
        accent = meta.get("accent")
        if isinstance(accent, str) and accent.strip() and not is_materialised:
            token = accent.strip()
            # Letters only, so `#b45309`, `rgb(...)` and every other
            # function form fall to the browser — a check that guesses at
            # those is one authors learn to ignore. Unicode letters, not
            # ASCII: `rosé` is as unparseable as `rose` was, and a rule
            # that reads only ASCII is one that stops at the first
            # accented typo.
            if re.fullmatch(r"[^\W\d_]+", token) and token.lower() not in _CSS_NAMED_COLOURS:
                if token.lower() not in _KIT_ACCENTS:
                    near = _did_you_mean(token.lower(), list(_KIT_ACCENTS))
                    add(
                        p,
                        "warning",
                        "accent-unknown",
                        "meta.accent",
                        f"accent '{token}' is neither a kit token nor a CSS colour name.{near} "
                        f"The kit tunes {', '.join(_KIT_ACCENTS)}; anything else has to be a "
                        "colour the browser can parse (a hex, `rgb(...)`, `hsl(...)`). "
                        "The page will keep the default accent.",
                    )
        if not meta.get("summary") and not is_materialised:
            add(
                p,
                "info",
                "no-summary",
                "meta.summary",
                "Page has no meta.summary — site-manifest tooltips + llms.txt lose the one-line description.",
            )
        if not _page_title(page):
            add(
                p,
                "error",
                "no-title",
                "title",
                "Page has no title; the document <title> and cover <h1> will be empty.",
            )

        # 10. Presentation. Style advice written as prose in a briefing
        # decays, because nothing fails when it is ignored. The half of
        # it that a tool can decide without judgement lives here, so the
        # briefing can be about content.
        if not is_materialised:
            for issue in _presentation_issues(page, _tree_defaults(p), kit_dir):
                add(p, *issue)

    # 11. Link destinations. Glossary and ext-ref ids were resolved
    # above; every OTHER local destination was unchecked, so a heading
    # renamed on one page left a dead `#anchor` on another with nothing
    # to report it. Cross-page, because `guide.md#setup` needs the
    # target page's anchors and those are only known now.
    #
    # Warning rather than error: a page can legitimately link into a
    # tree this run was not pointed at, and a linter that blocks a build
    # over a link it cannot see is one authors switch off.
    # Keyed by the RESOLVED path: a page path and a path built from a
    # link are the same file by two routes, and on macOS the temp root
    # alone (/var vs /private/var) is enough to make them compare unequal
    # — which silently turned every cross-page anchor check into a
    # file-exists check.
    anchors_by_target = {k.resolve(): v for k, v in anchors_by_page.items()}
    for p, refs in links_by_page.items():
        for where, href, ref_line in refs:
            if not href or _FOREIGN_HREF_RE.match(href):
                continue
            file_part, _, frag = href.partition("#")
            if not file_part:
                if frag and frag not in anchors_by_page.get(p, set()):
                    add(
                        p,
                        "warning",
                        "unresolved-anchor",
                        f"{where} #{frag}",
                        f"Link points at '#{frag}', which is not a heading id on this page."
                        + _did_you_mean(frag, anchors_by_page.get(p, set())),
                        line=ref_line,
                    )
                continue
            if file_part.startswith("/"):
                continue  # root-absolute: relative to the served root, not to us
            target = (p.parent / file_part).resolve()
            # `foo.md` and `foo.html` both name the page whose virtual
            # path is `foo.json`; renderLink rewrites the first to the
            # second, so both have to resolve to the same entry.
            page_key = target.with_suffix(".json")
            if page_key in anchors_by_target:
                if frag and frag not in anchors_by_target[page_key]:
                    add(
                        p,
                        "warning",
                        "unresolved-anchor",
                        f"{where} {href}",
                        f"Link points at '#{frag}' on {file_part}, which has no such heading id."
                        + _did_you_mean(frag, anchors_by_target[page_key]),
                        line=ref_line,
                    )
                continue
            # A `.html` that is not on disk yet may still be a page: it is
            # what the build will write beside a source this walk did not
            # reach. `oku check` from the repo root resolved these through
            # `anchors_by_target`; the same command from `docs/` reported
            # nine of them as broken, on links that build and open fine.
            # The walk root is a choice about scope, not about which links
            # exist, so the two runs have to agree.
            if not target.exists() and any(target.with_suffix(s).exists() for s in (".md", ".json")):
                continue
            if not target.exists():
                add(
                    p,
                    "warning",
                    "unresolved-link",
                    f"{where} {href}",
                    f"Link target '{file_part}' does not exist relative to this page."
                    + _did_you_mean(file_part, [q.name for q in p.parent.glob("*") if q.is_file()]),
                    line=ref_line,
                )

    # 12. Translation anchor parity. The language switch carries the
    # reader's `#fragment` across, so an id that exists on one side and
    # not the other drops them at the top of a page they were already
    # deep inside — and it does it silently, because both pages render
    # perfectly well on their own.
    #
    # This cannot be left to the slugifier: it strips non-ASCII, so a
    # Turkish heading never produces its English original's id by
    # accident. The translated side has to pin `{#id}` by hand, which is
    # exactly the kind of manual step that is right on the day it is
    # written and wrong two edits later.
    for p, anchors in anchors_by_page.items():
        codes, default = declared_languages(p.parent)
        if not codes:
            continue  # monolingual tree: nothing to pair with
        base_stem, lang = split_language_suffix(p.stem, codes)
        if not lang or lang == default:
            continue
        base_anchors = anchors_by_target.get((p.parent / (base_stem + p.suffix)).resolve())
        if base_anchors is None:
            # A page whose name merely ends in a language code, with no
            # original beside it. `_fold_language_variants` keeps it as
            # its own page for the same reason.
            continue
        missing = sorted(base_anchors - anchors)
        extra = sorted(anchors - base_anchors)
        if missing or extra:
            parts = []
            if missing:
                parts.append(f"absent here: {', '.join(missing)}")
            if extra:
                parts.append(f"absent from the original: {', '.join(extra)}")
            add(
                p,
                "warning",
                "translation-anchor-drift",
                "(page)",
                f"Heading ids differ from {base_stem}{p.suffix} — {'; '.join(parts)}. "
                "The language switch carries the #fragment across, so a reader deep in one "
                "language lands at the top of the other. Pin the id with {#id} on both sides.",
            )

    # 13. Accent consistency, per tree. Cross-page, so it runs after the
    # per-page loop. A tree with a different accent on every page is not
    # a design; the fix is one line in kit.json.
    by_tree: dict[Path, dict[str, list[Path]]] = {}
    tree_size: dict[Path, int] = {}
    for p, page in pages:
        tree_size[p.parent] = tree_size.get(p.parent, 0) + 1
        if _tree_defaults(p).get("accent"):
            continue  # the tree HAS an answer; a page override is a choice
        meta = _page_meta(page)
        accent = meta.get("accent")
        if accent and "accent" not in (meta.get("_derived") or ()):
            by_tree.setdefault(p.parent, {}).setdefault(str(accent), []).append(p)
    for where, accents in by_tree.items():
        # Two pages disagreeing is a coincidence; it takes a third page
        # before "no convention" is distinguishable from "two pages".
        if len(accents) < 2 or tree_size.get(where, 0) < 3:
            continue
        names = ", ".join(sorted(accents))
        for paths in accents.values():
            for p in paths:
                add(
                    p,
                    "info",
                    "accent-divergence",
                    "meta.accent",
                    f"{len(accents)} different accents in this directory ({names}) and no default "
                    "in kit.json. Set the tree's accent once there and override only where a page "
                    "genuinely differs.",
                )

    # Point every issue at the file the author edits, and at the line
    # inside it. Done once here rather than at each of the ~40 `add`
    # sites: the locator formats differ per check, the mapping does not.
    for issue in issues:
        source, line = _locate(issue["path"], _block_index_in(issue.get("where", ""), issue["message"]))
        issue["path"] = source
        exact = issue.pop("_line", None)
        if exact is not None:
            issue["line"] = exact
        elif line is not None:
            issue["line"] = line

    return issues


# Fields whose value the build can supply, and where from. Setting one
# by hand is allowed — the authored value always wins — but it is worth
# a note, because a hand-counted reading time is wrong after the next
# edit and nothing tells the author.
_DERIVABLE_META = {
    "read_time": "the body at 220 words per minute",
    "updated": "the file's last commit date",
}

# Placeholders that mean "not finished". Word-boundaried and
# case-sensitive for the acronyms, so prose about a TODO list or the
# word "todos" does not trip it; `{{ }}` catches an unfilled template.
_PLACEHOLDER_RE = re.compile(
    r"\{\{[^}]*\}\}|\b(?:TODO|TBD|FIXME|XXX)\b|\blorem ipsum\b",
    re.IGNORECASE if False else 0,
)

_ISLAND_STYLE_RE = re.compile(r"<style[\s>]|style\s*=\s*[\"'][^\"']*(?:#[0-9a-fA-F]{3,8}|rgb\()")
_HTML_ISLAND_RE = re.compile(r"^<[a-zA-Z][^\s>]*", re.MULTILINE)
# The lines of a mermaid source that carry colour. A hex anywhere else is
# part of a label ("#3 pick") and none of this rule's business.
_MERMAID_STYLE_LINE_RE = re.compile(r"^\s*(?:classDef|style|linkStyle)\s|^\s*%%\{")
_RAW_COLOUR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(")

# Primitives whose whole job is the relationship BETWEEN their members.
# With one member there is no relationship left — what remains is a
# titled box with an accent on it, which is the "looks like a
# visualization" shape rather than a visualization.
_GROUP_PRIMITIVES = {
    "compare-grid": ("cards", "a second option to weigh it against"),
    "step-flow": ("steps", "a second stage to lead to"),
    "timeline": ("events", "a second moment to sit after"),
    "kpi-grid": ("tiles", "a second figure to sit beside"),
    "chart-grid": ("panels", "a second panel to compare against"),
}

# Mermaid node labels: the text inside [], (), {}, or their doubled
# forms, with optional quotes. Deliberately loose — it is only used to
# compare against headings, and a label this misses simply does not
# count toward the ratio.
_MERMAID_LABEL_RE = re.compile(r"[\[\(\{]{1,2}\s*\"?([^\"\[\]\(\)\{\}|]+?)\"?\s*[\]\)\}]{1,2}")


def _normalise_label(text: str) -> str:
    """Lowercased, punctuation-free, markup-free comparison key."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[`*_#]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.lower().split())


def _page_headings(page: dict) -> set[str]:
    """Every `##` / `###` heading on the page, normalised."""
    out: set[str] = set()
    for blk in page.get("b") or []:
        if isinstance(blk, dict):
            if blk.get("k") == "heading" and blk.get("t"):
                out.add(_normalise_label(str(blk["t"])))
            continue
        if not isinstance(blk, str):
            continue
        for line in blk.split("\n"):
            m = re.match(r"\s{0,3}(#{2,4})\s+(.+?)\s*$", line)
            if m:
                title = re.sub(r"\s*\{#[\w-]+\}\s*$", "", m.group(2))
                out.add(_normalise_label(title))
    out.discard("")
    return out


_kit_token_cache: dict[str, frozenset[str]] = {}


def _kit_css_tokens(kit_dir: Path) -> frozenset[str]:
    """Every `--custom-property` the kit's own stylesheet defines.

    Read from the kit being CHECKED, not from this repo: a globally
    installed `oku` carries its own copy, and the whole point of the
    check below is to catch a page written against a newer kit than the
    tool holds.
    """
    key = str(kit_dir)
    if key not in _kit_token_cache:
        css = kit_dir / "chrome.css"
        try:
            text = css.read_text(encoding="utf-8")
        except OSError:
            text = ""
        _kit_token_cache[key] = frozenset(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", text))
    return _kit_token_cache[key]


def _presentation_issues(
    page: dict, tree_defaults: dict, kit_dir: Path | None = None
) -> list[tuple[str, str, str, str]]:
    """(severity, code, where, message) for the presentation rules.

    Each rule is decidable without judgement. Anything needing a reader
    — whether the diagram carries the point — stays out of here on
    purpose; a check that guesses trains authors to ignore checks.
    """
    out: list[tuple[str, str, str, str]] = []
    meta = _page_meta(page)
    derived = set(meta.get("_derived") or ())

    def authored(key: str):
        return meta.get(key) if key not in derived else None

    subtitle, summary = authored("subtitle"), meta.get("summary")
    if subtitle and summary and str(subtitle).strip() == str(summary).strip():
        out.append(
            (
                "warning",
                "redundant-meta",
                "meta.subtitle",
                "`subtitle` repeats `summary` verbatim. Drop it — the cover falls back to "
                "`summary` when no subtitle is set.",
            )
        )

    date, updated = authored("date"), authored("updated")
    if date and updated and str(date).strip() == str(updated).strip():
        out.append(
            (
                "warning",
                "redundant-meta",
                "meta.updated",
                "`updated` repeats `date`. Two hand-maintained dates drift; drop `updated` and "
                "the build supplies the last commit date.",
            )
        )

    for key, value in tree_defaults.items():
        if authored(key) is not None and str(meta.get(key)).strip() == str(value).strip():
            out.append(
                (
                    "info",
                    "redundant-meta",
                    f"meta.{key}",
                    f"`{key}` repeats the tree default in kit.json. Drop it.",
                )
            )

    for key, whence in _DERIVABLE_META.items():
        if authored(key) is not None:
            out.append(
                (
                    "info",
                    "hand-set-derivable",
                    f"meta.{key}",
                    f"`{key}` is set by hand where the build derives it from {whence}. "
                    "Keep it only when the derived value is wrong — a hand-set one goes stale silently.",
                )
            )

    for title, paragraphs, visuals in _section_shapes(page):
        if paragraphs >= 3 and visuals == 0:
            out.append(
                (
                    "warning",
                    "prose-only-section",
                    f"section '{title}'",
                    f"{paragraphs} paragraphs and nothing for the eye — no table, chart, diagram, "
                    "card grid or code block. Either the figure is missing or the section is doing "
                    "two jobs.",
                )
            )

    headings = _page_headings(page)
    # A primitive used three or more times on one page is an index
    # element, and the relationship the reader is reading lives between
    # the instances rather than inside any one of them — docs/charts.md
    # indexes nine chart families that way, and one family happens to
    # have a single member. Exempt the series; keep the rule sharp on
    # the lone grid, which is the shape the rule is actually about.
    kinds = collections.Counter(
        str(b.get("k")) for b in (page.get("b") or []) if isinstance(b, dict) and b.get("k")
    )
    for i, blk in enumerate(page.get("b") or []):
        if not isinstance(blk, dict):
            continue
        kind = str(blk.get("k") or "")
        field, need = _GROUP_PRIMITIVES.get(kind, (None, None))
        if field is not None and kinds[kind] < 3:
            members = blk.get(field)
            if isinstance(members, list) and len(members) == 1:
                out.append(
                    (
                        "warning",
                        "group-of-one",
                        f"b[{i}] {kind}",
                        f"one entry in `{field}`. This primitive draws the relationship between "
                        f"its members, and there is no relationship without {need}. Add the "
                        "second member, or write the single point as prose.",
                    )
                )
        if kind == "diagram":
            hand = [
                ln.strip()
                for ln in str(blk.get("src") or "").split("\n")
                if _MERMAID_STYLE_LINE_RE.match(ln) and _RAW_COLOUR_RE.search(ln)
            ]
            if hand:
                out.append(
                    (
                        "warning",
                        "island-hand-styled",
                        f"b[{i}] diagram",
                        f"{len(hand)} mermaid style line(s) carry their own colours, starting "
                        f"`{hand[0][:60]}`. A hex freezes the figure to one theme, so the diagram "
                        "keeps light fills on a dark page. Use the kit's tokens — "
                        "fill:var(--series-N-soft), stroke:var(--series-N), color:var(--text), "
                        "with N in 1..10 — and the kit substitutes the computed value at every "
                        "hand-off, so the colours follow the theme. The -soft tokens exist for "
                        "this: Mermaid's grammar takes CSS values and not CSS functions, so "
                        "color-mix() will not parse.",
                    )
                )
        if kind == "diagram":
            # A `var(--x)` Mermaid can see is a diagram that does not
            # draw. `__okuResolveCssVars` substitutes the computed value
            # before Mermaid parses, and deliberately leaves a token that
            # resolves to nothing exactly as written — so an undefined
            # one reaches a grammar with no production for `(` and the
            # whole figure becomes a parse-error card. Reported here
            # because the browser's message names the punctuation and not
            # the token, and because the usual cause is a page written
            # against a newer kit than the installed tool carries.
            defined = _kit_css_tokens(kit_dir or KIT_DIR)
            if defined:
                used = sorted(
                    {
                        name
                        for ln in str(blk.get("src") or "").split("\n")
                        if _MERMAID_STYLE_LINE_RE.match(ln)
                        for name in re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)", ln)
                    }
                )
                missing = [name for name in used if name not in defined]
                if missing:
                    out.append(
                        (
                            "warning",
                            "diagram-unknown-token",
                            f"b[{i}] diagram",
                            f"mermaid style line(s) use {', '.join(missing)}, which this kit does "
                            "not define. The kit substitutes a token's computed value before "
                            "Mermaid parses and leaves an unresolvable one as written, so Mermaid "
                            "meets `var(` — a grammar with no production for it — and the diagram "
                            "renders as a parse-error card. Check `oku --version` against the kit "
                            "you wrote the page for; `./ctl deploy` in the kit repo updates it.",
                        )
                    )
        if kind == "diagram" and headings:
            labels = {_normalise_label(x) for x in _MERMAID_LABEL_RE.findall(str(blk.get("src") or ""))}
            labels.discard("")
            hit = labels & headings
            if len(labels) >= 3 and len(hit) * 3 >= len(labels) * 2:
                out.append(
                    (
                        "warning",
                        "figure-restates-headings",
                        f"b[{i}] diagram",
                        f"{len(hit)} of {len(labels)} node labels are this page's own section "
                        f"titles ({', '.join(sorted(hit)[:3])}…). A figure has to add a relationship "
                        "the headings do not already show — otherwise it is the table of contents, "
                        "drawn.",
                    )
                )

    for i, blk in enumerate(page.get("b") or []):
        if not isinstance(blk, str):
            continue
        for chunk in _md_chunks(blk):
            if not _HTML_ISLAND_RE.match(chunk) or not _ISLAND_STYLE_RE.search(chunk):
                continue
            out.append(
                (
                    "warning",
                    "island-hand-styled",
                    f"b[{i}]",
                    "HTML island carries its own colours or a <style> block. Build on the kit's "
                    "classes and CSS variables (var(--accent), var(--surface), .okt-* ) so the "
                    "island follows the page accent and the light/dark theme. Drawing an SVG? "
                    "The vocabulary is .okt-diag-node / -edge / -arrow / -label / -group, each "
                    "with ok / warn / fail / accent / soft / mono modifiers, plus "
                    ".okt-diag-fill-1..10 for the chart ramp.",
                )
            )
            break

    return out


def _md_chunks(text: str) -> list[str]:
    """Blank-line-separated blocks, with fenced regions kept whole."""
    chunks: list[str] = []
    buf: list[str] = []
    fence: re.Pattern | None = None
    for line in text.split("\n"):
        if fence is not None:
            buf.append(line)
            if fence.match(line):
                fence = None
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m:
            if buf and not "".join(buf).strip():
                buf = []
            fence = _fence_close_re(m.group(1))
            buf.append(line)
            continue
        if not line.strip():
            if any(x.strip() for x in buf):
                chunks.append("\n".join(buf).strip("\n"))
            buf = []
            continue
        buf.append(line)
    if any(x.strip() for x in buf):
        chunks.append("\n".join(buf).strip("\n"))
    return chunks


def _section_shapes(page: dict) -> list[tuple[str, int, int]]:
    """(section title, paragraph count, visual count) per `##` section.

    A callout is not a visual. That is the whole point of the rule: a
    coloured box around a paragraph reads as decorated text, and
    counting it would let a page pass by adding one.
    """
    sections: list[list] = []

    def current() -> list:
        if not sections:
            sections.append(["(before the first heading)", 0, 0])
        return sections[-1]

    for blk in page.get("b") or []:
        if isinstance(blk, dict):
            # Every typed block is a visual except the text-shaped ones.
            if blk.get("k") not in ("insight", "tldr"):
                current()[2] += 1
            continue
        if not isinstance(blk, str):
            continue
        for chunk in _md_chunks(blk):
            head = chunk.lstrip()
            if head.startswith("## ") and not head.startswith("###"):
                title = re.sub(r"\s*\{#[\w-]+\}\s*$", "", head.split("\n", 1)[0][3:]).strip()
                sections.append([title, 0, 0])
                continue
            if head.startswith("#"):
                continue
            sec = current()
            if head.startswith(("|", "```", "~~~")) or _HTML_ISLAND_RE.match(chunk):
                sec[2] += 1
            elif head.startswith((">", "-", "*", "+", ":")) or re.match(r"\d+[.)]\s", head):
                continue
            else:
                sec[1] += 1
    return [(str(t), int(p), int(v)) for t, p, v in sections]


def _format_issue(issue: dict, root: Path) -> str:
    """Single-line human-readable rendering of one issue."""
    try:
        rel = issue["path"].relative_to(root)
    except ValueError:
        rel = issue["path"]
    icon = {"error": "✗", "warning": "!", "info": "·"}.get(issue["severity"], "·")
    # `file:line` first, in the shape every editor and every tool that
    # reads compiler output already knows how to jump to. The block
    # locator stays after it — it is what the message talks about.
    line = f":{issue['line']}" if issue.get("line") else ""
    return f"  {icon} {rel}{line}:{issue['where']} [{issue['code']}] {issue['message']}"


def find_unparseable_json(root: Path) -> list[tuple[Path, str]]:
    """Scan every .json under root and return (path, parse-error)
    pairs for files that fail to parse. find_json_pages silently
    catches JSONDecodeError to avoid breaking the build on a stray
    `package.json` sibling — but for the lint surface, an authored
    page that no longer parses is exactly the bug to surface.

    Excludes the same well-known sidecars that find_json_pages
    excludes (kit.json, site-manifest.json, package.json, tsconfig).
    """
    bad: list[tuple[Path, str]] = []
    extra = project_skip_dirs(root)
    for p in iter_repo_files(root, (".json",), extra_skip=extra):
        if p.name in ("kit.json", "site-manifest.json", "package.json", "tsconfig.json"):
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            bad.append((p, f"{err.msg} at line {err.lineno} col {err.colno}"))
        except OSError as err:
            bad.append((p, f"read failed: {err}"))
    return bad


def ignored_paths_note(root: Path) -> str | None:
    """One line naming what git kept out of the walk, or None.

    Only ever non-None for a project that opted in with
    ``skip_gitignored``. Even there the symptom of a wrong prune is a
    page missing from the build with nothing said about it — the failure
    this repo keeps writing rules about — so the mechanism names itself
    rather than going quiet. A count with two examples: a full list
    would be its own noise.
    """
    ignored = git_ignored_paths(root)
    if not ignored:
        return None
    # Only what git contributed. `.idea`, `.pytest_cache` and `dist` are
    # already skipped by the dot-prefix rule and SKIP_DIRS, so naming
    # them here says nothing about why a page is missing — and a line
    # that is mostly noise is one nobody reads when it finally matters.
    skip = SKIP_DIRS | project_skip_dirs(root)
    names = sorted(
        rel
        for rel in (os.path.relpath(x, str(root)) for x in ignored)
        if not any(part.startswith(".") or part in skip for part in Path(rel).parts)
    )
    if not names:
        return None
    shown = ", ".join(names[:2])
    more = f", +{len(names) - 2} more" if len(names) > 2 else ""
    return f"· {len(names)} path(s) not walked — git ignores them ({shown}{more})"


def apply_path_chip_fixes(issues: list[dict], root: Path) -> list[tuple[Path, list[str]]]:
    """Rewrite the sources `path-in-code-span` named, and say what moved.

    Defined as "apply what the check reported", not as a second walk of
    the tree: which pages qualify is a question with several answers
    already baked into the check — a materialised README is exempt, a
    reference reaching outside the project does not resolve, a page
    behind `skip_gitignored` was never walked — and a fix that asked
    those questions again is a fix that eventually answers one of them
    differently from the report the author is looking at.

    One file is read, rewritten and written once, however many issues it
    carried. Nothing is written when nothing changed, so a clean tree is
    not restamped.
    """
    fixed: list[tuple[Path, list[str]]] = []
    for page in sorted({i["path"] for i in issues if i["code"] == "path-in-code-span"}):
        src, _line = _locate(page, None)
        if src.suffix != ".md" or not src.is_file():
            continue
        try:
            before = src.read_text(encoding="utf-8")
        except OSError:
            continue
        after, moved = _rewrite_code_span_paths(before, lambda t: resolve_file_ref(t, src)[1] == "ok")
        if not moved or after == before:
            continue
        src.write_text(after, encoding="utf-8")
        fixed.append((src, moved))
    return fixed


def cmd_check(args: argparse.Namespace) -> int:
    """`oku check` — comprehensive doctree lint.

    Runs schema validation plus a suite of structural / content checks
    (deprecated kinds, duplicate anchors, glossary + ext-ref resolution,
    forbidden process language, chart shape sanity, …). Fast — designed
    to be the oku skill's auto-verify step.

    Exit codes:
      0 — clean (no errors; warnings allowed unless --strict).
      1 — at least one error (or any warning when --strict).
    """
    root = Path.cwd()
    # Unparseable JSON has to be surfaced BEFORE find_json_pages drops
    # it — otherwise an authored page with a misplaced comma silently
    # disappears from the nav and check still reports "all clean".
    bad_json = find_unparseable_json(root)
    pages = find_json_pages(root)
    if not pages:
        print(f"✗ No page-JSON files found under {root}", file=sys.stderr)
        return 1

    issues = check_pages(pages, root)
    for p, err in bad_json:
        issues.append(
            {
                "path": p,
                "severity": "error",
                "code": "json-parse-failed",
                "where": "(file)",
                "message": err,
            }
        )

    if getattr(args, "fix", False):
        # Rewrite first, then fall through and check the tree AS
        # REWRITTEN — the report an author reads after `--fix` is the
        # state of their files now, never the state that produced the
        # edits. A second pass is cheap and a stale report is not.
        moved = apply_path_chip_fixes(issues, root)
        if moved:
            total = sum(len(paths) for _src, paths in moved)
            print(f"✎ rewrote {total} path(s) into #f/ chips in {len(moved)} file(s):")
            for src, paths in moved:
                shown = ", ".join(sorted(set(paths))[:3])
                more = f", +{len(set(paths)) - 3} more" if len(set(paths)) > 3 else ""
                try:
                    rel = src.relative_to(root)
                except ValueError:
                    rel = src
                print(f"  ✎ {rel} — {shown}{more}")
            _PAGE_SOURCE_OF.clear()
            _PAGE_BLOCK_LINES.clear()
            pages = find_json_pages(root)
            issues = check_pages(pages, root)
        else:
            print("✎ nothing to rewrite")

    # Shadowed sources — a real .json page next to a .md source
    # silently WINS in discovery and serving, so the
    # rendered page stops following the source the author edits. This
    # exact failure (a stale global `oku init` materialising v1 .json
    # shadows over every docs/*.md) once broke a whole review pass —
    # it must never again be silent.
    for p, _data in pages:
        if p.suffix != ".json" or not p.exists():
            continue
        for sib in (_source_sibling(p),):
            if sib.exists():
                issues.append(
                    {
                        "path": p,
                        "severity": "error",
                        "code": "shadowed-source",
                        "where": "(file)",
                        "message": f"Real page-JSON shadows the {sib.name} source — the rendered page "
                        f"ignores the source file. Delete the .json (it is derived) or the source.",
                    }
                )
                break

    if args.json:
        # Emit a machine-parseable stream. Path is serialised relative
        # to root so consumers don't have to strip absolute prefixes.
        payload = []
        for it in issues:
            try:
                rel = str(it["path"].relative_to(root))
            except ValueError:
                rel = str(it["path"])
            entry = {
                "path": rel,
                "severity": it["severity"],
                "code": it["code"],
                "where": it["where"],
                "message": it["message"],
            }
            if it.get("line"):
                entry["line"] = it["line"]
            payload.append(entry)
        print(json.dumps({"page_count": len(pages), "issues": payload}, ensure_ascii=False, indent=2))
    else:
        # Group by severity for the terminal report.
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]
        infos = [i for i in issues if i["severity"] == "info"]

        if errors:
            print(f"✗ {len(errors)} error(s):")
            for it in errors:
                print(_format_issue(it, root))
        if warnings and not args.errors_only:
            print(f"! {len(warnings)} warning(s):")
            for it in warnings:
                print(_format_issue(it, root))
        if infos and args.verbose:
            print(f"· {len(infos)} info note(s):")
            for it in infos:
                print(_format_issue(it, root))
        elif infos:
            # One line, not the notes themselves. An info note is a
            # suggestion, and a suggestion printed in full on every run
            # trains an author to stop reading the report — but a note
            # nothing ever mentions is one nobody knows to ask for, and
            # `path-in-code-span` exists precisely to tell an author
            # about a primitive they have not met.
            codes = sorted({i["code"] for i in infos})
            shown = ", ".join(codes[:3]) + ("…" if len(codes) > 3 else "")
            print(f"· {len(infos)} info note(s) ({shown}) — print them with --verbose")

        if not _HAS_JSONSCHEMA:
            # Never print a tick for a pass that did not run. This exact
            # line once read "✓ 2 page(s) clean" for a page whose table
            # and step-flow payloads the renderer could not read at all,
            # because the installed tool had no jsonschema and the
            # schema pass silently returned []. jsonschema is a hard
            # dependency now, so reaching here means a broken install —
            # say so, and fail.
            print(
                "✗ schema validation did not run — jsonschema is missing from this install.\n"
                "  Only the structural checks ran, and they cannot see a malformed block\n"
                "  payload. Reinstall with `uv tool install --force --no-cache --from . oku`.",
                file=sys.stderr,
            )
            return 1
        if not errors and not warnings:
            print(f"✓ {len(pages)} page(s) clean (schema + structural + content)")
        elif not errors:
            print(f"✓ {len(pages)} page(s) — no errors (warnings present)")
        note = ignored_paths_note(root)
        if note:
            print(f"  {note}")

    has_errors = any(i["severity"] == "error" for i in issues)
    has_warnings = any(i["severity"] == "warning" for i in issues)
    if has_errors:
        return 1
    if args.strict and has_warnings:
        return 1
    return 0


# Repo-meta files still render as pages (reachable by direct URL) but are
# not documentation, so they're kept OUT of the reader-facing site tree —
# otherwise README (whose H1 here is "oku") and CLAUDE.md crowd the top of
# the sidebar next to the real docs. Matched by stem at the repo ROOT only;
# a CHANGELOG deliberately placed inside docs/ stays in the nav.
_NAV_EXCLUDE_STEMS = frozenset(
    {
        "readme",
        "changelog",
        "claude",
        "agents",
        "license",
        "contributing",
        "code_of_conduct",
        "security",
        "notice",
        "authors",
    }
)


def declared_languages(root: Path) -> tuple[list[str], str]:
    """The site's language codes and its default, from kit.json.

    Returns ([], "") for a monolingual site — which is every site that
    does not ask for otherwise, so the whole feature costs nothing until
    a `languages` key appears.

    `languages` accepts either bare codes or objects carrying a label
    for the switch: ["en", "tr"] or [{"code": "tr", "label": "Türkçe"}].
    """
    kit_path = find_kit_json(root)
    if kit_path is None:
        return [], ""
    try:
        data = json.loads(kit_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], ""
    raw = data.get("languages") or []
    codes = [item.get("code") if isinstance(item, dict) else item for item in raw]
    codes = [c for c in codes if isinstance(c, str) and c]
    if len(codes) < 2:
        return [], ""
    default = data.get("defaultLanguage") or codes[0]
    return codes, (default if default in codes else codes[0])


def split_language_suffix(stem: str, codes: list[str]) -> tuple[str, str | None]:
    """`("reference.tr", ["en","tr"])` → `("reference", "tr")`.

    Only a DECLARED code counts. Without that check `format-comparison`
    would split into base `format` with language `comparison`, and a
    page would vanish from the tree the day someone declared a language
    whose code collided with a filename's last dotted part.
    """
    at = stem.rfind(".")
    if at <= 0:
        return stem, None
    suffix = stem[at + 1 :]
    return (stem[:at], suffix) if suffix in codes else (stem, None)


def nav_sort_key(entry: dict) -> tuple:
    """The one order the site tree is in: folder, then `order`, then title.

    Three things consume it — the sidebar tree, `llms.txt`, and
    `_pick_open_target` when it decides which page `oku serve` opens —
    and for a while each carried its own idea of the answer. The manifest
    was emitted in path order while a comment two thousand lines away
    asserted it was already sorted, so `pages[0]` was the alphabetically
    first page rather than the tree's first row. It went unnoticed here
    only because this repo commits one HTML stub: the loop found nothing
    to match until it reached `index.html`.

    `order` defaults to 1000, which parks an unordered page after
    everything explicit. Title is the tie-break, lowercased so `Zebra`
    and `apple` do not sort by case. `chrome.js` mirrors this rule at
    render time and `test_manifest_order.py` holds the two together.
    """
    return (
        entry.get("parent") or "",
        entry.get("order", 1000),
        (entry.get("title") or entry.get("path") or "").lower(),
    )


def compute_manifest(root: Path, *, pages: list | None = None) -> dict:
    """Walk JSON pages under root, return the site manifest dict.

    Entries: { path, source, title, parent, order?, summary? }. Folder
    hierarchy is implicit in the path; the runtime tree-builder groups
    siblings under their common ancestor path.

    When `pages` is supplied, the walk + parse is skipped — used by
    cmd_build to avoid re-parsing every JSON page on each manifest /
    markdown / llms.txt pass.
    """
    if pages is None:
        pages = find_json_pages(root)
    entries = []
    for p, data in pages:
        rel = p.relative_to(root)
        # Repo-meta files at the root are pages but not nav entries.
        if rel.parent == Path(".") and rel.stem.lower() in _NAV_EXCLUDE_STEMS:
            continue
        nav_path = rel.with_suffix(".html").as_posix()
        path_parent = _url_path(rel.parent.as_posix()) if rel.parent != Path(".") else None
        meta = _page_meta(data)
        # `p` is always a .json virtual path. For .md-derived pages the
        # .json file doesn't exist on disk; the real source is the
        # sibling .md. Report whichever is real so the manifest's source
        # field matches what a reader can open in their editor.
        source_rel = rel
        if not p.exists():
            for sib in (_source_sibling(p),):
                if sib.exists():
                    source_rel = sib.relative_to(root)
                    break
        # `path_parent` is already in URL space; an author's own `parent`
        # is not, and encoding it twice is how `sub#dir` became
        # `sub%2523dir` and lost every row under it.
        parent = meta["parent"] if "parent" in meta else path_parent
        if parent is not path_parent and isinstance(parent, str) and parent:
            parent = _url_path(parent)
        entry = {
            "path": _url_path(nav_path),
            "source": source_rel.as_posix(),
            "title": _page_title(data) or p.stem,
            "parent": parent,
        }
        if "order" in meta:
            entry["order"] = meta["order"]
        if "summary" in meta:
            entry["summary"] = meta["summary"]
        entries.append(entry)
    entries = _fold_language_variants(entries, root)
    entries.sort(key=nav_sort_key)
    return {
        "schema_version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "root": ".",
        # The manifest is the carrier for build provenance because it is
        # the one thing that already reaches every page in all three
        # modes — fetched under `oku serve` and in dist/site, inlined in
        # a standalone file. What goes in it: `_build_block`.
        "build": _build_block(root),
        "pages": entries,
    }


def _build_block(root: Path) -> dict:
    """What this artifact was made from, and how to make it again.

    `oku` + `kit` are the same two fields `oku --version` prints, under
    the same names, so the footer and the terminal can be compared
    without translating between them. `cmd` is the only field naming a
    machine, so it is the only one a
    project can turn off (`rebuild_command: false` in kit.json). The
    other two are the same pair `oku --version` prints, under the same
    names, so the footer and the terminal can be compared without
    translating between them.
    """
    out = {"oku": _PKG_VERSION, "kit": _kit_build_stamp()}
    if project_shows_rebuild_command(root):
        out["cmd"] = _rebuild_command(root)
    return out


def _url_path(rel: str) -> str:
    """A tree-relative path as it has to appear inside a URL.

    Every manifest `path` becomes an href, and every href is compared
    against `location.pathname`, which the browser hands back
    percent-encoded. Left raw, a file called `notes#1.md` built into
    `notes#1.html` and the href pointed at `notes` with the fragment
    `1` — the page existed, was written, was indexed, and nothing in
    the tree could reach it. `?` did the same thing with a query
    string, and a space ended the target of the markdown link in
    llms.txt, turning the rest of the filename into a link title.

    Per segment, so the separators survive. A name with no special
    character encodes to itself, which is why this can be applied to
    every path in the manifest rather than only the awkward ones —
    including `parent`, since a path and the parent it is grouped
    under have to be spelled the same way or the tree loses the row.
    """
    return "/".join(quote(seg, safe="") for seg in rel.split("/"))


def _fold_language_variants(entries: list[dict], root: Path) -> list[dict]:
    """Collapse `page.md` + `page.tr.md` into ONE nav entry that knows
    where its translations live.

    A translation is the same page in another language, not another
    page. Left as its own entry it appears in the site tree beside the
    original — so a ten-page site in two languages reads as twenty
    pages, and every reader sees both halves of a tree they can only
    read half of.

    So the base keeps the entry and gains `lang` plus a `variants` map
    (which includes itself, so the switch has no special case for
    "where do I go back to"). The translations leave the tree. Their
    HTML is still built and still indexed for search — `iter_page_stubs`
    emits pages independently of this — they are simply reached by
    switching rather than by browsing.

    A monolingual site takes the early return and nothing below runs.
    """
    codes, default = declared_languages(root)
    if not codes:
        return entries

    by_path = {}
    groups: dict[str, dict[str, str]] = {}
    titles: dict[str, dict[str, str]] = {}
    summaries: dict[str, dict[str, str]] = {}
    for entry in entries:
        rel = PurePosixPath(entry["path"])
        base, lang = split_language_suffix(rel.stem, codes)
        base_path = rel.with_name(base + ".html").as_posix()
        code = lang or default
        entry["_base"] = base_path
        entry["_lang"] = code
        by_path[entry["path"]] = entry
        groups.setdefault(base_path, {})[code] = entry["path"]
        # The tree shows one row per page, so that row has to be able to
        # say the page's name in whichever language the reader is in.
        # Without this the drawer on a Turkish page listed English
        # titles pointing at English pages — the reader switched
        # language and the navigation stayed behind.
        titles.setdefault(base_path, {})[code] = entry["title"]
        if entry.get("summary"):
            summaries.setdefault(base_path, {})[code] = entry["summary"]

    kept = []
    for entry in entries:
        variants = groups.get(entry["_base"], {})
        lang = entry.pop("_lang")
        base_path = entry.pop("_base")
        # A translation whose base is missing is not a translation — it
        # is a page whose name happens to end in a language code, and
        # dropping it would delete it from the tree with no way to reach
        # it. Keep it, and let it carry its own language.
        is_translation = entry["path"] != base_path and base_path in by_path
        entry["lang"] = lang
        if len(variants) > 1:
            entry["variants"] = dict(sorted(variants.items()))
            entry["titles"] = dict(sorted(titles.get(base_path, {}).items()))
            group_summaries = summaries.get(base_path, {})
            if group_summaries:
                entry["summaries"] = dict(sorted(group_summaries.items()))
        if not is_translation:
            kept.append(entry)
    return kept


def build_manifest(root: Path, *, out_dir: Path | None = None, pages: list | None = None) -> Path:
    """Walk root for pages, write site-manifest.json to out_dir
    (defaults to root for legacy / test callsites). The build pipeline
    passes a dist path for out_dir so source dirs stay clean.

    The runtime loader has three resolution paths (chrome.js
    `loadManifest`): inline `window.__okuManifest` first
    (standalone HTMLs ship this), then `fetch('site-manifest.json')`
    (the site build's sidecar), then a final inline fallback. The
    historical `.js` companion file is no longer emitted — it was a
    fourth fallback for `<script src=site-manifest.js>` setups that
    no template wires anymore.
    """
    manifest = compute_manifest(root, pages=pages)
    out_dir = out_dir or root
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "site-manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


# ---------- LLM-friendly markdown twin per JSON page ----------
def compute_llms_txt(root: Path, *, pages: list | None = None) -> str:
    """Return the llms.txt body (llmstxt.org convention) — sitemap for
    LLM consumers. One line per page: link + summary. No body copy
    (HTML is the source of truth)."""
    if pages is None:
        pages = find_json_pages(root)
    project_name = root.name
    description = ""
    kit_json = find_kit_json(root)
    if kit_json is not None:
        try:
            kit_data = json.loads(kit_json.read_text(encoding="utf-8"))
            project_name = kit_data.get("name", project_name)
            description = kit_data.get("description", "")
        except (json.JSONDecodeError, OSError):
            pass

    lines = ["# " + project_name, ""]
    if description:
        lines += ["> " + description, ""]
    lines += ["## Pages", ""]
    entries = []
    for p, data in pages:
        rel = p.relative_to(root)
        nav_path = rel.with_suffix(".html").as_posix()
        meta = _page_meta(data)
        entries.append(
            {
                "path": _url_path(nav_path),
                "title": _page_title(data) or p.stem,
                "parent": _url_path(rel.parent.as_posix()) if rel.parent != Path(".") else "",
                "order": meta.get("order", 1000),
                "summary": meta.get("summary", ""),
            }
        )
    entries.sort(key=nav_sort_key)
    for e in entries:
        line = "- [" + e["title"] + "](" + e["path"] + ")"
        if e["summary"]:
            line += ": " + e["summary"]
        lines.append(line)
    lines.append("")

    return "\n".join(lines)


def build_llms_txt(root: Path, *, out_dir: Path | None = None, pages: list | None = None) -> Path:
    """Walk root for pages, write llms.txt to out_dir (defaults to root
    for legacy / test callsites). The build pipeline passes a dist path
    so source dirs stay clean."""
    out_dir = out_dir or root
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "llms.txt"
    out.write_text(compute_llms_txt(root, pages=pages), encoding="utf-8")
    return out


# ---------- Pagefind search index ----------
def _pagefind_cmd(site_dir: Path) -> list[str] | None:
    """Pick the most self-contained pagefind invocation available.

    Resolution order (prefer the one with no system-level prerequisite):
      1. python -m pagefind  — bundled binary from the PyPI `pagefind[bin]`
         extra. Self-contained inside the project's virtualenv.
      2. system `pagefind`   — brew / cargo / manual install on PATH.
      3. npx pagefind        — fall back through Node if available.

    Returns None when nothing is reachable; the caller logs once and
    skips the search step (the rest of the build still completes).
    """
    try:
        probe = subprocess.run(
            [sys.executable, "-m", "pagefind", "--version"],
            capture_output=True,
            timeout=15,
        )
        if probe.returncode == 0:
            return [sys.executable, "-m", "pagefind", "--site", str(site_dir)]
    except (OSError, subprocess.TimeoutExpired):
        pass
    if shutil.which("pagefind"):
        return ["pagefind", "--site", str(site_dir)]
    if shutil.which("npx"):
        return ["npx", "--yes", "pagefind", "--site", str(site_dir)]
    return None


def pagefind_index(site_dir: Path) -> bool:
    """Run Pagefind over an HTML site directory.

    Returns True if pagefind ran successfully, False if absent or failed.
    Pagefind is treated as an optional dependency — search degrades
    gracefully if it's not installed.
    """
    if not site_dir.exists():
        return False
    cmd = _pagefind_cmd(site_dir)
    if cmd is None:
        print("! pagefind not available; skipping search index.")
        print("  Install:  uv pip install 'pagefind[bin]'  (preferred — bundled binary)")
        print("            or  brew install pagefind  /  npm i -g pagefind")
        return False
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True
        print(f"! pagefind failed (exit {result.returncode})")
        if result.stderr.strip():
            print("  stderr:", result.stderr.strip().splitlines()[0])
        return False
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"! pagefind exec error: {e}")
        return False


_PAGE_TEXT_KEYS = ("title", "summary", "lead", "caption", "content", "def", "label", "name", "text")
_PAGE_TEXT_LISTS = (
    "bullets",
    "blocks",
    "items",
    "rows",
    "steps",
    "tiles",
    "columns",
    "cards",
    "series",
    "data",
)


def extract_page_text(page_json: dict) -> str:
    """Walk a JSON page tree and return concatenated plain text for indexing.

    Includes paragraph content, glossary-term / ext-ref labels, callout
    titles and bodies, etc. Skips structural-only fields. Strips inline
    HTML tags that might appear in def/summary strings.
    """
    parts = []

    title = _page_title(page_json)
    if title:
        parts.append(title)
    meta = _page_meta(page_json)
    for k in ("subtitle", "summary", "eyebrow"):
        if isinstance(meta.get(k), str):
            parts.append(meta[k])

    def walk(node):
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            for k in _PAGE_TEXT_KEYS:
                if k in node and not isinstance(node[k], (list, dict)):
                    walk(node[k])
            for k in _PAGE_TEXT_KEYS:
                if k in node and isinstance(node[k], list):
                    walk(node[k])
            for k in _PAGE_TEXT_LISTS:
                if k in node:
                    walk(node[k])

    # `b` is where a v2/v3 page keeps its blocks; `blocks` is the v1 name.
    # Reading only the v1 key meant every page authored since the format
    # changed indexed as its title plus its summary and nothing else —
    # charts.md, 118 blocks, extracted 182 characters. Pagefind then built
    # a title index, so a search for any word in any page body returned
    # nothing and the UI fell back to "this page only" as though the index
    # were missing. The unit tests fed it v1 pages, which is why they were
    # green the whole time.
    blocks = page_json.get("b")
    if blocks is None:
        blocks = page_json.get("blocks", [])
    walk(blocks)
    # Strip inline HTML that may live in glossary defs etc.
    raw = " ".join(parts)
    # A v2 block is a markdown string, so the typed fences come with it —
    # and their bodies are JSON payloads. Index the prose, not `{"type":
    # "bar","rows":[…]}`. Plain code fences stay: a reader searching for a
    # function name they saw in a sample is searching for real content.
    raw = re.sub(r"```oku-[a-z-]+\n.*?```", " ", raw, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_BODY_CLOSE_RE = re.compile(r"</body>", re.I)


def inject_pagefind_body(html: str, text: str, title: str) -> str:
    """Embed plain-text content in a hidden element for Pagefind to index.

    data-pagefind-body restricts indexing to the marked element; everything
    else is ignored. data-pagefind-meta carries the title.
    """
    # Escape just enough for safety; full HTML escape is fine since this
    # element is hidden from users.
    safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    block = (
        "<div hidden data-pagefind-body>"
        f'<h1 data-pagefind-meta="title">{safe_title}</h1>'
        f"<p>{safe_text}</p>"
        "</div>"
    )
    if _BODY_CLOSE_RE.search(html):
        return _BODY_CLOSE_RE.sub(lambda m: block + "\n</body>", html, count=1)
    return html + block


# `<script>window.__okuManifest={…};</script>` as `_stub_for` emits it.
# Anchored on the closing tag rather than the first `};` so a summary
# containing that pair cannot end the match early.
_INLINE_MANIFEST_RE = re.compile(r"window\.__okuManifest\s*=\s*\{.*?\};\s*</script>", re.S)


def build_site(srcs, out_dir: Path, src_root: Path, *, manifest: dict | None = None) -> None:
    """Build a self-contained multi-page site at out_dir/.

    Layout:
      dist/site/
        _oku/              ← chrome.{css,js}, chrome-boot.js, renderer.js,
                             glossary/, extrefs/, schema/
        kit.json           ← copied from src_root if present
        site-manifest.json ← copied from src_root
        llms.txt           ← copied from src_root if present
        *.html             ← each source HTML, kept as-is
        *.json             ← page JSON for the runtime renderer to fetch

    For each HTML, if a sibling page-JSON exists, inject its extracted
    text into a hidden data-pagefind-body element so the static
    Pagefind index has real content to chew on.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    kit_out = out_dir / "_oku"
    kit_out.mkdir(exist_ok=True)

    # Runtime chrome files → _oku/
    for f in KIT_FILES:
        shutil.copy(KIT_DIR / f, kit_out / f)
    # The stylesheet lands beside `_oku/vendor/`, so its own relative
    # font URLs already resolve — but only if the fonts were fetched.
    # Passing an empty base leaves them untouched in that case and drops
    # the rules in the other, so this tree never asks for a file it did
    # not ship either.
    if not vendor_fonts_present():
        css_out = kit_out / "chrome.css"
        css_out.write_text(_retarget_font_urls(css_out.read_text(encoding="utf-8"), ""), encoding="utf-8")
    # Shared registry directories → _oku/<name>/
    for d in ("glossary", "extrefs", "schema", "i18n"):
        src_dir = KIT_DIR / d
        if src_dir.exists():
            dst_dir = kit_out / d
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)

    # mermaid + Prism, the same shared copy build_standalone lays down.
    # This was standalone-only, so a dist/site deployed anywhere without
    # internet — an intranet, an air-gapped host, a laptop on a plane —
    # drew no diagrams and highlighted no code, after 404ing on
    # `_oku/vendor/…` first. Measured on this repo's own site build with
    # the CDNs blocked: 0 of 6 diagrams drawn, 0 highlight tokens, while
    # the standalone tree of the same pages had all 6 and 598. The loader
    # falls back to the CDN, so the failure only appears where nobody is
    # watching, which is the point of vendoring in the first place.
    src_vendor = vendor_dir()
    if src_vendor.is_dir():
        shutil.copytree(src_vendor, kit_out / "vendor", dirs_exist_ok=True)

    # Project-level files that pages depend on at runtime. site-manifest
    # and llms.txt are derived; cmd_build writes them into the dist
    # tree's docs_dir directly after this call, NOT into source.
    kit_json = find_kit_json(src_root)
    if kit_json is not None:
        shutil.copy(kit_json, out_dir / "kit.json")
    else:
        # Every page asks for kit.json at load. A project that never wrote
        # one is a normal project, not a broken one — but the browser
        # still prints "404 (File not found)" on every page of the
        # deployed site, and a console that cries wolf on every load is
        # one nobody reads when something real happens. An empty object
        # is what "no project config" means anyway.
        (out_dir / "kit.json").write_text("{}\n", encoding="utf-8")

    # Page sources (HTML stubs + JSON content) — preserve directory structure.
    # For nested pages, rewrite `_oku/...` URLs in the stub to climb the
    # right number of levels up to the dist's single _oku/ at out_dir/.
    for src, html, page_data in srcs:
        rel = src.relative_to(src_root)
        dest_html = out_dir / rel
        dest_html.parent.mkdir(parents=True, exist_ok=True)
        depth = len(rel.parts) - 1  # parts excludes filename via -1
        html = _retarget_kit_urls(html, depth)

        json_sibling = src.with_suffix(".json")
        page = page_data
        if page is None and json_sibling.exists():
            try:
                page = json.loads(json_sibling.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                page = None
        if page is not None:
            json_rel = json_sibling.relative_to(src_root)
            dest_json = out_dir / json_rel
            dest_json.parent.mkdir(parents=True, exist_ok=True)
            if json_sibling.exists():
                shutil.copy(json_sibling, dest_json)
            else:
                # Synthesized from .md — write the converted page dict.
                dest_json.write_text(
                    json.dumps(page, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            if _is_page(page):
                text = extract_page_text(page)
                title = _page_title(page) or src.stem
                html = inject_pagefind_body(html, text, title)

        # The .md source travels with the page. It is the canonical
        # authoring surface (llms.txt points readers at it) and it is
        # what the markdown viewer fetches when a page links to a .md
        # over HTTP — without it, a published site is the one place the
        # viewer cannot read its own tree, while `oku serve` and the
        # standalone build both can.
        md_sibling = src.with_suffix(".md")
        if md_sibling.exists():
            dest_md = out_dir / md_sibling.relative_to(src_root)
            dest_md.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(md_sibling, dest_md)

        # The files the page points at, at the paths its own hrefs use.
        # A page and its image were built as if only the page mattered:
        # the reference survived, the file was copied nowhere, and the
        # build said nothing. The author never sees it, because a
        # preview served from the source directory resolves the image
        # and only the handed-over artifact is missing it.
        assets, outside_tree = collect_page_assets(page, src, src_root)
        for href, target in assets.items():
            dest_asset = out_dir / target.relative_to(src_root.resolve())
            dest_asset.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(target, dest_asset)
        for href in outside_tree:
            target = (src.parent / unquote(href)).resolve()
            carried = target.is_file() and asset_within_project(target, src)
            print(
                f"  ⚠ {src.relative_to(src_root)}: {href} is above the tree being built — "
                + (
                    "not copied into dist/site (the standalone page inlines it)"
                    if carried
                    else "and outside the project; neither tree carries it"
                )
            )

        # A stub `oku init` wrote carries the manifest of the day it was
        # written. The site fetches the real one for its sidebar, so the
        # two disagreed IN THE SAME PAGE: the front page of a delivered
        # tree listed three pages in its body under a sidebar listing
        # four, because the body list is rendered from the inline copy.
        # A built page carries the build's manifest or none at all.
        if manifest is not None:
            fresh = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).replace(
                "</script", "<\\/script"
            )
            html = _INLINE_MANIFEST_RE.sub(lambda m: f"window.__okuManifest={fresh};</script>", html, count=1)
        dest_html.write_text(_mark_built(html), encoding="utf-8")


_BUILT_MARKER = "<script>window.__okuBuilt=1;</script>"
_HEAD_OPEN_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)


def _mark_built(html: str) -> str:
    """Stamp a page as build output rather than dev-server output.

    A site stub and a dev-server stub are otherwise byte-identical, and
    chrome.js can only see that it is on localhost — so previewing
    ``dist/site/`` with any static server made every page open an
    EventSource against ``/__reload``, which that server does not have.
    One 404 per page load, in the console of a shipped artifact, on the
    exact path the build's own output line invites the reader to take.
    """
    if _BUILT_MARKER in html:
        return html
    m = _HEAD_OPEN_RE.search(html)
    if m:
        return html[: m.end()] + "\n" + _BUILT_MARKER + html[m.end() :]
    return _BUILT_MARKER + "\n" + html


def build_kit_bundle(src_root: Path) -> str | None:
    """Assemble the project's kit.json + active domain glossary/extref files
    into one JSON blob for inlining into standalone builds. Returns None
    if no kit.json is present (no glossary to inline).
    """
    kit_json_path = find_kit_json(src_root)
    if kit_json_path is None:
        return None
    try:
        kit_data = json.loads(kit_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    domains = kit_data.get("domains") or []
    glossary = {}
    extrefs = {}

    for domain in domains:
        g_path = KIT_DIR / "glossary" / f"{domain}.json"
        if g_path.exists():
            try:
                g_data = json.loads(g_path.read_text(encoding="utf-8"))
                if g_data.get("entries"):
                    glossary[domain] = g_data["entries"]
            except (json.JSONDecodeError, OSError):
                pass
        e_path = KIT_DIR / "extrefs" / f"{domain}.json"
        if e_path.exists():
            try:
                e_data = json.loads(e_path.read_text(encoding="utf-8"))
                if e_data.get("entries"):
                    extrefs[domain] = e_data["entries"]
            except (json.JSONDecodeError, OSError):
                pass

    bundle = {
        "kit": kit_data,
        "glossary": glossary,
        "extrefs": extrefs,
    }
    return json.dumps(bundle, ensure_ascii=False)


# A standalone file is meant to be sent as a file. A linked .md that is
# itself book-length would double the artifact for a document the reader
# may never open, so there is a ceiling — and it is reported, not silent.
MAX_INLINE_DOC_BYTES = 512 * 1024

# The two link shapes that still say `.md` by the time the reader clicks.
#
# A RELATIVE markdown link (`[x](notes/plan.md)`) is deliberately absent:
# renderLink in renderer.js rewrites it to `notes/plan.html`, because that
# file is a page in this tree and the whole page beats a file viewer. What
# it leaves alone is a root-absolute destination and anything inside an
# HTML island — those reach the DOM as `.md` and open the viewer, so those
# are the ones a file:// build has to carry.
_ROOT_ABS_MD_LINK_RE = re.compile(r"\]\((/[^)\s]+?\.md)(?:#[^)\s]*)?\)")
_ISLAND_MD_HREF_RE = re.compile(r"""href\s*=\s*["']([^"'\s]+?\.md)(?:#[^"']*)?["']""")


_FENCE_RE = re.compile(r"(?:^|\n)(`{3,}|~{3,})[^\n]*\n.*?\n\1[ \t]*(?=\n|$)", re.S)


def _strip_code(text: str) -> str:
    """Prose with its code samples and code spans removed.

    An href inside backticks is a QUOTATION of a link, not a link: the
    renderer never turns it into an anchor, so the build has nothing to
    inline for it. Without this, documenting the markdown viewer made
    the build warn about the very examples that explain it —
    `<a href="notes/plan.md">` in a table cell became a missing file.
    """
    return _INLINE_CODE_RE.sub(" ", _FENCE_RE.sub("\n", text))


def _iter_strings(node):
    """Every string anywhere in a page dict. Typed blocks carry prose in
    fields of their own (an insight's `b`, a table cell, a callout body),
    so a link can sit outside the top-level `b[]` strings."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from _iter_strings(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _iter_strings(value)


# A page's own files — the image beside it above all. Three spellings
# reach the DOM as a request for a file: markdown's `![alt](path)`, an
# attribute inside an HTML island, and the `src` of an `image` block on
# a JSON page. All three shipped as broken references, because the build
# carried the page and left the file behind.
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s<>]+?)>?(?:\s+[\"'(][^\n]*?)?\s*\)")
_HTML_ASSET_ATTR_RE = re.compile(r"""\b(?:src|poster)\s*=\s*["']([^"'\s]+)["']""", re.I)
_HTML_SRCSET_RE = re.compile(r"""\bsrcset\s*=\s*["']([^"']+)["']""", re.I)

# Past this, a standalone page stops inlining and copies the file beside
# itself instead. A 20 MB screenshot base64s to 27 MB, in every page
# that shows it; one file you can send is the point of that tree, and a
# file nobody can mail is not one.
MAX_INLINE_ASSET_BYTES = 2 * 1024 * 1024


def _asset_hrefs(page_data) -> list[str]:
    """Every local file this page asks the browser to fetch, in the
    spelling the author used — which is the string a rewrite has to
    match and the path a copy has to land on."""
    hrefs: list[str] = []
    seen: set[str] = set()

    def add(href: str) -> None:
        href = href.strip()
        if not href or href in seen:
            return
        seen.add(href)
        hrefs.append(href)

    def walk(node) -> None:
        if isinstance(node, str):
            text = _strip_code(node)
            for m in _MD_IMAGE_RE.finditer(text):
                add(m.group(1))
            for m in _HTML_ASSET_ATTR_RE.finditer(text):
                add(m.group(1))
            for m in _HTML_SRCSET_RE.finditer(text):
                for candidate in m.group(1).split(","):
                    parts = candidate.split()
                    if parts:
                        add(parts[0])
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            # An `image` block carries a bare path under `src`, which no
            # prose regex can see. It is reachable only from a JSON page,
            # and those keep rendering forever.
            if node.get("k") == "image" and isinstance(node.get("src"), str):
                add(node["src"])
            for value in node.values():
                walk(value)

    walk(page_data)
    return hrefs


def collect_page_assets(page_data, src: Path, src_root: Path) -> tuple[dict[str, Path], list[str]]:
    """Local files this page points at, keyed by the href AS AUTHORED.

    Returns (assets, outside). `outside` holds hrefs that resolve to a
    real file above the tree being built: the site cannot copy one
    without inventing a path for it, so it says so instead. A href that
    resolves to nothing is neither — `oku check` already reports it as
    an unresolved link, and saying it twice trains authors to read
    neither message.
    """
    assets: dict[str, Path] = {}
    outside: list[str] = []
    if page_data is None:
        return assets, outside

    root = src_root.resolve()
    for href in _asset_hrefs(page_data):
        if re.match(r"^[a-z][a-z0-9+.-]*:|^//|^#", href, re.I):
            continue  # someone else's origin, a data: URI, or an anchor
        base = root if href.startswith("/") else src.parent
        target = (base / unquote(href.lstrip("/"))).resolve()
        if not target.is_file():
            continue
        try:
            target.relative_to(root)
        except ValueError:
            outside.append(href)
            continue
        assets[href] = target
    return assets, outside


def asset_within_project(target: Path, src: Path) -> bool:
    """Whether a page may publish the bytes of a file it points at.

    The same fence a `#f/` reference answers to, for the same reason:
    the build reads the file and copies its bytes into an artifact that
    gets sent to people, so a reference reaching into another project —
    or into a home directory — hands those bytes over with it. An image
    had no fence at all. `collect_page_assets` reports anything above
    the tree being BUILT, which is a different question: a repo whose
    docs live in `docs/` legitimately shows `../screenshots/x.png`, and
    a standalone page can carry it because it carries bytes rather than
    paths. That is inside the project. `../../other-repo/x.png` is not.
    """
    try:
        target.relative_to(project_root_for(src.parent))
        return True
    except ValueError:
        return False


def _data_uri(path: Path) -> str:
    kind, _ = mimetypes.guess_type(path.name)
    return f"data:{kind or 'application/octet-stream'};base64," + base64.b64encode(path.read_bytes()).decode(
        "ascii"
    )


def _code_spans(text: str) -> list[tuple[int, int]]:
    """Where the code samples are. A page that documents figures shows
    the markdown for one, and a sample rewritten into a 40 KB data: URI
    stops being a sample."""
    spans = [m.span() for m in _FENCE_RE.finditer(text)]
    for m in _INLINE_CODE_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in spans):
            spans.append(m.span())
    spans.sort()
    return spans


def _rewrite_assets(node, uris: dict[str, str]):
    """A copy of the page with every carried href replaced by its data:
    URI. Rewriting goes through the same three patterns that found the
    href, never plain string replacement — `tiny.png` is also ordinary
    prose — and never inside code, which is a quotation of a reference
    rather than one.
    """
    if isinstance(node, str):

        def sub_group(m):
            uri = uris.get(m.group(1).strip())
            return m.group(0) if uri is None else m.group(0).replace(m.group(1), uri, 1)

        def sub_srcset(m):
            out = []
            for candidate in m.group(1).split(","):
                parts = candidate.split()
                if not parts:
                    continue
                out.append(" ".join([uris.get(parts[0], parts[0])] + parts[1:]))
            return m.group(0).replace(m.group(1), ", ".join(out), 1)

        def rewrite(chunk: str) -> str:
            chunk = _MD_IMAGE_RE.sub(sub_group, chunk)
            chunk = _HTML_ASSET_ATTR_RE.sub(sub_group, chunk)
            return _HTML_SRCSET_RE.sub(sub_srcset, chunk)

        out: list[str] = []
        pos = 0
        for start, end in _code_spans(node):
            out.append(rewrite(node[pos:start]))
            out.append(node[start:end])
            pos = end
        out.append(rewrite(node[pos:]))
        return "".join(out)
    if isinstance(node, list):
        return [_rewrite_assets(item, uris) for item in node]
    if isinstance(node, dict):
        out = {k: _rewrite_assets(v, uris) for k, v in node.items()}
        if node.get("k") == "image" and isinstance(node.get("src"), str):
            out["src"] = uris.get(node["src"], node["src"])
        return out
    return node


def collect_local_docs(page_data, src: Path, src_root: Path) -> tuple[dict[str, str], list[str]]:
    """Read every local .md this page links to, keyed by the href AS
    AUTHORED — which is exactly what the viewer looks up at runtime
    (`a.getAttribute('href')`), so the two sides cannot drift apart by
    disagreeing about how to normalise a path.

    Returns (docs, skipped). A miss is never fatal: the link keeps working
    over HTTP, and over file:// the viewer says why it cannot read it.
    """
    docs: dict[str, str] = {}
    skipped: list[str] = []
    if page_data is None:
        return docs, skipped

    hrefs: list[str] = []
    for text in _iter_strings(page_data):
        if ".md" not in text:
            continue
        text = _strip_code(text)
        hrefs.extend(_ROOT_ABS_MD_LINK_RE.findall(text))
        hrefs.extend(_ISLAND_MD_HREF_RE.findall(text))

    for href in hrefs:
        if href in docs or href in skipped:
            continue
        if re.match(r"^[a-z][a-z0-9+.-]*:|^//", href, re.I):
            continue  # someone else's origin — not ours to inline
        # A root-absolute href means "from the root of what is served",
        # which at build time is the tree being built.
        base = src_root if href.startswith("/") else src.parent
        target = (base / href.lstrip("/")).resolve()
        try:
            target.relative_to(src_root.resolve())
        except ValueError:
            skipped.append(href)  # outside the tree — not ours to ship
            continue
        if not target.is_file():
            skipped.append(href)
            continue
        if target.stat().st_size > MAX_INLINE_DOC_BYTES:
            skipped.append(href)
            continue
        try:
            docs[href] = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped.append(href)
    return docs, skipped


# ------------------------------------------------------------------ #
# Inline file references — the `filepath` primitive.
#
# A document that mentions a file writes its path, and a path in a code
# span is a dead end: the reader has to leave the page, find the file
# and come back. `[label](#f/<path>)` keeps the mention and adds the
# file — hover for a preview, click for the whole thing, and the path
# stays copyable either way.
#
# The bytes have to TRAVEL WITH THE PAGE, and that is the constraint
# every decision below comes from. None of the three delivery modes can
# fetch the file at read time: `oku serve` and `dist/site` serve the
# docs tree, and the interesting references point outside it (`../src`,
# a sibling repo, an absolute path); `dist/standalone` is opened over
# file://, where fetch is refused before a request is made. So the
# payload is computed once, at the point a page dict is made, and rides
# in `m._files` — which is the one thing all three modes already carry.
# ------------------------------------------------------------------ #

_MD_FILE_REF_RE = re.compile(r"\]\(#f/([^)\n]+?)\)")

# Two caps because the two contents travel differently: text rides as
# text, bytes ride as base64 at 4/3 their size.
MAX_FILE_TEXT_BYTES = MAX_INLINE_DOC_BYTES
MAX_FILE_BINARY_BYTES = MAX_INLINE_ASSET_BYTES

_FILE_KIND_BY_SUFFIX = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".avif": "image",
    ".svg": "image",
    ".bmp": "image",
    ".ico": "image",
    ".mp4": "video",
    ".webm": "video",
    ".mov": "video",
    ".m4v": "video",
    ".ogv": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".ogg": "audio",
    ".m4a": "audio",
    ".flac": "audio",
    ".pdf": "pdf",
}

# Prism's own language ids, so the popup highlights a file the way the
# page highlights a fence of the same language.
_FILE_LANG_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".css": "css",
    ".scss": "scss",
    ".html": "markup",
    ".xml": "markup",
    ".svg": "markup",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".sql": "sql",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".scala": "scala",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".ini": "ini",
    ".conf": "ini",
    ".diff": "diff",
    ".patch": "diff",
    ".md": "markdown",
    ".markdown": "markdown",
}

_project_root_cache: dict[Path, Path] = {}


def project_root_for(page_dir: Path) -> Path:
    """The fence a file reference may not reach past.

    Nearest ancestor holding `.git`, else nearest holding `kit.json`,
    else the page's own directory. `.git` is asked first on purpose:
    this repo has `docs/kit.json`, and a docs-rooted fence would refuse
    `../src/oku/cli.py` — the reference an author most wants to make.

    The fence is not about trust in the author, who typed the path. It
    is about what a page PUBLISHES: the build reads these files and
    copies their bytes into the artifact, so a reference reaching into
    `~/.ssh` or another project would hand them to whoever the document
    is sent to.
    """
    page_dir = page_dir.resolve()
    hit = _project_root_cache.get(page_dir)
    if hit is not None:
        return hit
    kit_root = None
    for parent in [page_dir, *page_dir.parents]:
        if (parent / ".git").exists():
            _project_root_cache[page_dir] = parent
            return parent
        if kit_root is None and (parent / "kit.json").is_file():
            kit_root = parent
    root = kit_root or page_dir
    _project_root_cache[page_dir] = root
    return root


def resolve_file_ref(href: str, page_src: Path) -> tuple[Path | None, str]:
    """Where a `#f/` reference points, and whether the page may carry it.

    Status is one of `ok`, `missing`, `outside`. Returns the resolved
    path alongside `outside` too — the message names where it landed,
    which is the whole diagnosis.

    Two bases, tried in that order: the page's own directory, then the
    project root. The page comes first because that is what a relative
    path means everywhere else in a markdown file — an image, a link to
    a sibling page — and a reference that resolves there must not change
    meaning because a file of the same name appeared at the root.

    The root is the fallback because prose does not write paths that
    way. A sentence about `src/oku/cli.py` says it from the root of the
    project, which is how the reader would type it into an editor; from
    `docs/reference.md` that path resolves nowhere, so the chip rendered
    and its preview never opened. Measured on this repo's own docs, 10
    of 803 inline code spans named a file the page-relative rule could
    find; the paths people actually write are root-relative.

    The fallback is strictly additive — it only runs where the answer
    was already `missing` or `outside` — and when it fails, the reported
    status is the PAGE-relative one, because that is what the author
    wrote.
    """
    raw = unquote(href).strip()
    if not raw:
        return None, "missing"
    try:
        expanded = Path(raw).expanduser()
    except RuntimeError:
        # `~someone/notes.md` where no such user exists, and `~~~` — a
        # path the OS cannot expand is a file that is not there, which
        # this function already has a word for. Letting it out crashes
        # `oku check` and `oku build` with a traceback on a page whose
        # only fault is a typo in a link.
        expanded = Path(raw)
    root = project_root_for(page_src.parent)

    def _from(base: Path) -> tuple[Path | None, str]:
        target = expanded if expanded.is_absolute() else (base / expanded)
        try:
            target = target.resolve()
        except OSError:
            return None, "missing"
        try:
            target.relative_to(root)
        except ValueError:
            return target, "outside"
        if not target.is_file():
            return target, "missing"
        return target, "ok"

    target, status = _from(page_src.parent)
    if status == "ok" or expanded.is_absolute():
        return target, status
    alt_target, alt_status = _from(root)
    if alt_status == "ok":
        return alt_target, alt_status
    return target, status


def _file_kind(target: Path) -> tuple[str, str]:
    """(kind, mime) for a resolved file. `kind` is what the reader gets:
    a preview they can look at, or a line saying what the file is."""
    suffix = target.suffix.lower()
    mime, _ = mimetypes.guess_type(target.name)
    kind = _FILE_KIND_BY_SUFFIX.get(suffix)
    if kind:
        return kind, mime or "application/octet-stream"
    return "text", mime or "text/plain"


def _file_ref_payload(href: str, page_src: Path) -> dict:
    """What the page hands the browser for one `#f/` reference.

    Always carries the path, the name and the status; carries content
    only when it resolved, is inside the fence and fits the cap. A chip
    with no content still copies its path, which is what the author had
    before the primitive existed — the failure mode is a preview that
    does not open, never a page that loses a reference.
    """
    target, status = resolve_file_ref(href, page_src)
    out: dict = {"path": href, "name": Path(unquote(href)).name or href, "status": status}
    if status != "ok" or target is None:
        if target is not None:
            out["resolved"] = str(target)
        return out
    kind, mime = _file_kind(target)
    size = target.stat().st_size
    out.update({"kind": kind, "mime": mime, "bytes": size})
    if kind in ("markdown", "text"):
        if size > MAX_FILE_TEXT_BYTES:
            out["status"] = "over-cap"
            out["cap"] = MAX_FILE_TEXT_BYTES
            return out
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Not text after all — a `.dat` full of bytes, or a file the
            # reader cannot see anyway. Say what it is instead of
            # guessing at its contents.
            out["kind"] = "binary"
            return out
        out["text"] = text
        out["lines"] = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        lang = _FILE_LANG_BY_SUFFIX.get(target.suffix.lower())
        if lang:
            out["lang"] = lang
        return out
    if kind in ("image", "video", "audio"):
        if size > MAX_FILE_BINARY_BYTES:
            out["status"] = "over-cap"
            out["cap"] = MAX_FILE_BINARY_BYTES
            return out
        out["url"] = _data_uri(target)
        return out
    # pdf and everything else: named, sized, not previewed. An <embed>
    # or <iframe> pointed at a data: URI is blocked by the browser, and
    # a preview pane that renders nothing is worse than a line saying
    # what the file is.
    return out


def collect_file_refs(page_data, src: Path) -> dict[str, dict]:
    """Every `#f/` reference on this page, keyed by the path AS AUTHORED.

    The key is what the runtime looks up (`el.getAttribute('path')`), so
    the two sides cannot drift apart by disagreeing about how to
    normalise a path — the same rule `collect_local_docs` follows.
    """
    refs: dict[str, dict] = {}
    if page_data is None:
        return refs
    for text in _iter_strings(page_data):
        if "#f/" not in text:
            continue
        for href in _MD_FILE_REF_RE.findall(_strip_code(text)):
            href = href.strip()
            if href and href not in refs:
                refs[href] = _file_ref_payload(href, src)
    return refs


def build_standalone(srcs, out_dir: Path, src_root: Path, *, manifest: dict | None = None) -> None:
    """Inline kit CSS/JS + the page's JSON content into each HTML.

    Produces single self-contained files that render offline, with no
    network fetches beyond Google Fonts (and Mermaid if a <diagram>
    block is present). autoBoot picks up the inline JSON automatically.

    Output preserves the source's directory structure under out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    # One shared copy of the runtime dependencies beside the pages, not a
    # copy inside each of them. Offline does not require a single file —
    # it requires the bytes to be reachable without a network.
    src_vendor = vendor_dir()
    if src_vendor.is_dir():
        shutil.copytree(src_vendor, out_dir / "_oku" / "vendor", dirs_exist_ok=True)

    def _safe_js(s: str) -> str:
        # Prevent </script> in code (e.g. inside regexes or strings) from
        # closing the inline <script> early.
        return s.replace("</script", "<\\/script")

    css = (KIT_DIR / "chrome.css").read_text(encoding="utf-8")
    boot = _safe_js((KIT_DIR / "chrome-boot.js").read_text(encoding="utf-8"))
    main = _safe_js((KIT_DIR / "chrome.js").read_text(encoding="utf-8"))
    renderer = _safe_js((KIT_DIR / "renderer.js").read_text(encoding="utf-8"))
    kit_bundle = build_kit_bundle(src_root)  # may be None

    for src, html, page_data in srcs:
        # Page data goes in FIRST, while `html` is still the thin stub with
        # exactly one </body>. Inlining the kit first would drag chrome.js's
        # own source into the document — and its layout-skeleton comment
        # contains the literal text "<body></body>", which _BODY_CLOSE_RE
        # matches before the real one. The page JSON then lands mid-script
        # and its closing tag terminates the inlined chrome.js early, so the
        # rest of the kit renders as visible text.
        # Inline the JSON page content so autoBoot finds it offline.
        json_sibling = src.with_suffix(".json")
        page = page_data
        if page is None and json_sibling.exists():
            try:
                page = json.loads(json_sibling.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                page = None
        # The bytes of every file this page shows travel INSIDE it. A
        # copy beside the page is a copy the reader does not receive —
        # the promise of this tree is one file you can send, and an
        # image left behind is the one part of the page that fails
        # silently, in the artifact nobody re-opens before sending.
        # Past the cap the file is copied instead and the build says so.
        uris: dict[str, str] = {}
        page_assets, outside_tree = collect_page_assets(page, src, src_root)
        for href, target in page_assets.items():
            if target.stat().st_size <= MAX_INLINE_ASSET_BYTES:
                uris[href] = _data_uri(target)
                continue
            dest_asset = out_dir / target.relative_to(src_root.resolve())
            dest_asset.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(target, dest_asset)
            print(
                f"  ⚠ {src.relative_to(src_root)}: {href} not inlined "
                f"(over {MAX_INLINE_ASSET_BYTES // 1024}K) — it was copied beside the page, "
                f"so this page is no longer a single file"
            )
        # A file above the tree has no path the site could copy it to,
        # but a standalone page carries bytes, not paths, so it can
        # simply hold it — as long as the project owns it. Past the
        # project fence the page would publish somebody else's bytes to
        # whoever it is sent to, and it did so without a word.
        for href in outside_tree:
            target = (src.parent / unquote(href)).resolve()
            if not target.is_file():
                continue
            if not asset_within_project(target, src):
                print(
                    f"  ⚠ {src.relative_to(src_root)}: {href} resolves to {target}, outside the "
                    f"project ({project_root_for(src.parent)}) — not carried into the standalone "
                    "page. `oku check` reports it as image-outside."
                )
                continue
            if target.stat().st_size <= MAX_INLINE_ASSET_BYTES:
                uris[href] = _data_uri(target)
        data_text = None
        if uris and page is not None:
            data_text = json.dumps(_rewrite_assets(page, uris), ensure_ascii=False, indent=2)
        elif page_data is not None:
            data_text = json.dumps(page_data, ensure_ascii=False, indent=2)
        elif json_sibling.exists():
            data_text = json_sibling.read_text(encoding="utf-8")
        # Everything below except the page data itself belongs to any page
        # in the tree, source or not. It used to sit inside `if data_text:`,
        # so the ENTRY STUB — the one page in a tree that legitimately has
        # no .md behind it — received none of it: no manifest (its site
        # tree stayed frozen at whatever `oku init` last wrote, missing
        # every page added since), no vendor base, no kit bundle for
        # tooltips, no string table, no inlined .md sources. The front door
        # of a delivered tree was the one page built from a different
        # recipe than the pages behind it.
        inline = ""
        if data_text:
            # Escape </script in the JSON to be safe inside an inline script.
            safe = data_text.replace("</script", "<\\/script")
            inline += f'<script type="application/json" id="__oku_page__">{safe}</script>'
        # A standalone page is opened over file://, where the only
        # manifest chrome.js can reach is an inline one — fetch is
        # blocked before it is made. Only the entry stub `oku init`
        # wrote carried one, so every OTHER page in the tree opened
        # with no site tree and no language switch, which is not
        # what "self-contained" is supposed to mean.
        if manifest is not None:
            safe_manifest = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).replace(
                "</script", "<\\/script"
            )
            inline += f"\n<script>window.__okuManifest={safe_manifest};</script>"
        # Where this page finds mermaid and Prism. A standalone page
        # carries no `_oku/` link tag, so __okuDocsRoot has nothing to
        # derive a root from — the base is computed here, relative to
        # where this page sits in the output tree. The dependencies
        # are NOT inlined: mermaid alone is 3.3 MB against a 1.1 MB
        # page, and every page in the tree would carry its own copy.
        # One shared directory beside them costs it once.
        # `__okuVendoredPrism` used to ride along here as the loader's
        # signal that local Prism components exist. Only this build set
        # it, so the two server-backed modes were told there were none
        # however complete the copy beside them was. The loader decides
        # from the source that actually served prism.min.js now, which is
        # true in all three modes and cannot go stale in a built page.
        depth = len(src.relative_to(src_root).parent.parts)
        vendor_base = ("../" * depth) + "_oku/vendor/"
        inline += f"\n<script>window.__okuVendorBase={json.dumps(vendor_base)};</script>"
        # Inline the kit bundle (project kit.json + active domain
        # glossary/extref entries) so tooltips work offline.
        if kit_bundle:
            safe_bundle = kit_bundle.replace("</script", "<\\/script")
            inline += f'\n<script type="application/json" id="__oku_kit_bundle__">{safe_bundle}</script>'
        # The kit's own strings for THIS page's language. A page on
        # a file:// origin cannot fetch the table, and its chrome
        # would otherwise be English inside a translated document.
        page_lang = _page_language(src.with_suffix(".md"))
        i18n_path = KIT_DIR / "i18n" / f"{page_lang}.json"
        if page_lang and i18n_path.is_file():
            safe_i18n = i18n_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
            inline += f'\n<script type="application/json" id="__oku_i18n__">{safe_i18n}</script>'

        # Every .md this page links to, so the markdown viewer has
        # something to read over file:// — where fetch() cannot reach
        # the file sitting right next to this one.
        local_docs, skipped_docs = collect_local_docs(page_data, src, src_root)
        if local_docs:
            safe_docs = json.dumps(local_docs, ensure_ascii=False, separators=(",", ":")).replace(
                "</script", "<\\/script"
            )
            inline += f'\n<script type="application/json" id="__oku_local_docs__">{safe_docs}</script>'
        for href in skipped_docs:
            # Not an error — the link still resolves over HTTP. But a
            # standalone file that quietly cannot open one of its own
            # links is exactly the kind of gap that reads as a kit bug.
            print(
                f"  ⚠ {src.relative_to(src_root)}: {href} not inlined "
                f"(missing, outside the tree, or over {MAX_INLINE_DOC_BYTES // 1024}K) — "
                f"the viewer will not open it over file://"
            )
        # Lambda replacement avoids re.sub interpreting \n in the JSON
        # content as a backslash escape and turning it into a newline.
        if inline:
            html = _BODY_CLOSE_RE.sub(lambda m: inline + "\n</body>", html, count=1)

        # chrome.css names its font files relative to ITSELF; inlined,
        # they would resolve against the page instead. Same `vendor_base`
        # the kit's own loaders get, so both point at the one copy this
        # tree carries.
        page_css = _retarget_font_urls(css, vendor_base)
        html = LINK_TO_KIT_CSS.sub(lambda m: f"<style>\n{page_css}\n</style>", html, count=1)
        html = SCRIPT_TO_KIT_BOOT.sub(lambda m: f"<script>\n{boot}\n</script>", html, count=1)
        html = SCRIPT_TO_KIT_MAIN.sub(lambda m: f"<script>\n{main}\n</script>", html, count=1)
        html = SCRIPT_TO_KIT_RENDERER.sub(lambda m: f"<script>\n{renderer}\n</script>", html, count=1)

        # Preserve directory structure relative to src_root.
        rel = src.relative_to(src_root)
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")


def cmd_build(args: argparse.Namespace) -> int:
    root = Path.cwd()
    # Read before anything overwrites it — this is the only reading of
    # the outgoing artifact there will be.
    prior_stamp = _artifact_kit_stamp(root / "dist")
    # Fetch the shared dependencies the first time they are needed rather
    # than making the author discover a command. Once per installation,
    # then never again; a failure here is not a build failure, because
    # every loader still falls back to the CDN.
    if not getattr(args, "no_vendor", False) and not vendor_is_complete():
        print("  fetching mermaid + Prism once so pages render offline …")
        fetched, _ = fetch_vendor(quiet=True)
        if fetched:
            print(f"  ✓ vendored {fetched} file(s) into {vendor_dir()}")
        else:
            print("  ! could not vendor — pages will use the CDN (run `oku vendor` later)")
    # Single walk + parse — every downstream consumer (iter_page_stubs,
    # check, manifest, markdown twins, llms.txt) accepts a pre-computed
    # pages list. Avoids ~5 redundant rglob-parse passes over the tree.
    json_pages = find_json_pages(root)
    srcs = iter_page_stubs(root, json_pages=json_pages)
    if not srcs and not json_pages:
        print(f"✗ No .html or page-JSON files found in {root}", file=sys.stderr)
        return 1

    # Schema validation + structural lint — runs the same checks as
    # `oku check` so the build never produces a doctree that the
    # standalone linter would have rejected. Soft-fails without
    # jsonschema (the structural checks still run).
    if json_pages:
        check_issues = check_pages(json_pages, root)
        errors = [i for i in check_issues if i["severity"] == "error"]
        warnings = [i for i in check_issues if i["severity"] == "warning"]
        if errors:
            print(f"! Doctree check: {len(errors)} error(s):")
            for it in errors:
                print(_format_issue(it, root))
            # The contract every consumer reads is "the build refuses to
            # ship if it errors", and the build printed these and shipped
            # anyway with exit code 0 — so CI went green on a tree
            # carrying a page the linter had rejected, and the reader got
            # the page. A schema error is not cosmetic: it names a
            # payload the renderer will draw wrong or not at all.
            if not getattr(args, "allow_errors", False):
                print(
                    "\n✗ Not building. Fix the errors above, or pass --allow-errors to ship anyway.\n"
                    "  `oku check` prints the full report, warnings included.",
                    file=sys.stderr,
                )
                return 1
            print("  (--allow-errors: building anyway)")
        elif warnings:
            print(
                f"✓ Doctree check: {len(json_pages)} page(s) clean (errors); {len(warnings)} warning(s) — run `oku check` for the full report."
            )
        else:
            print(f"✓ Doctree check: {len(json_pages)} page(s) clean")
        note = ignored_paths_note(root)
        if note:
            print(f"  {note}")
        if not _HAS_JSONSCHEMA:
            print(
                "  (schema validation skipped — `pip install jsonschema` to enable; structural checks still ran)"
            )

    if not srcs:
        return 0

    dist = root / "dist"
    # Build BESIDE the previous output, swap when it is whole.
    #
    # The old order removed every tree first and wrote the new pages into
    # the hole. Anything that failed in between — a full disk, a
    # permission on one directory, an interrupt — left the reader's copy
    # deleted and the replacement half-written; measured on a 12 MB disk
    # image, `dist/standalone` ended with one 0-byte page and nothing
    # else, and the previous build was gone. That is the one failure this
    # tool must not have, because the thing destroyed is the artifact
    # somebody already had.
    staging = dist / f".build-{os.getpid()}"
    standalone = staging / "standalone"
    site = staging / "site"
    final_standalone = dist / "standalone"
    final_site = dist / "site"

    # One manifest, computed once, used by both trees: the site fetches
    # it as a sidecar, the standalone pages carry it inline.
    # Every write below lands in staging, and the one statement that
    # touches the previous output is the swap at the end. An OSError
    # anywhere in between — the disk filling, a read-only directory, a
    # name the filesystem refuses — therefore costs the reader nothing
    # but the new build.
    try:
        dist_manifest = compute_manifest(root, pages=json_pages)
        build_standalone(srcs, standalone, root, manifest=dist_manifest)
        build_site(srcs, site, root, manifest=dist_manifest)

        # Each tree carries only what its audience needs:
        #   standalone/  humans, file:// — every HTML inlines its own
        #                window.__okuManifest, so no sidecar is needed.
        #   site/        humans, HTTP — chrome.js fetches site-manifest.json
        #                from the docs root; llms.txt at the docs root
        #                serves AI/LLM consumers (the .md SOURCES are the
        #                canonical AI surface — no twin tree needed).
        # In the SITE tree the docs root is the site root: build_site copies
        # the kit to dist/site/_oku/ once, and chrome.js derives the docs root
        # by stripping back to whichever directory holds _oku/. Writing the
        # manifest anywhere else — e.g. under dist/site/docs/ for a project
        # whose pages all live in docs/ — leaves every built page fetching a
        # manifest that isn't there, and the site tree renders with an empty
        # site-tree nav. Page paths are therefore relative to the project
        # root, which is exactly the layout inside dist/site/.
        build_manifest(root, out_dir=site, pages=json_pages)
        print(f"✓ Wrote dist/site/site-manifest.json ({len(json_pages)} JSON page(s))")

        build_llms_txt(root, out_dir=site, pages=json_pages)
        print("✓ Wrote dist/site/llms.txt")

        # Synthesized stubs (from .json or .md sources with no on-disk
        # .html sibling) are emitted inline by build_site / build_standalone
        # via iter_page_stubs — no separate pass needed.
        synth_count = sum(1 for _, _, d in srcs if d is not None)
        if synth_count:
            print(f"✓ Synthesized {synth_count} stub(s) for pages without on-disk .html")

        # Pagefind search index — soft-fail if pagefind isn't installed.
        # Runs against the staged tree, before the swap: its output lives
        # inside `site/pagefind/` and moves with it.
        if pagefind_index(site):
            print("✓ Pagefind index built: dist/site/pagefind/")

        # The swap. Everything above wrote into staging, so this is the first
        # moment the previous output is touched at all.
        _swap_build_trees(dist, staging)
    except OSError as e:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"\n✗ Build failed: {e}", file=sys.stderr)
        print("  Nothing under dist/ was changed — the previous build still stands.", file=sys.stderr)
        return 1
    standalone, site = final_standalone, final_site

    print(f"✓ Built {len(srcs)} HTML file(s):")
    if prior_stamp and prior_stamp != _kit_build_stamp():
        # The drift, named at the one moment both numbers are in the
        # same process. A page can show what it was built with and how
        # old that is; only the tool that replaces it can say what it
        # was replaced BY.
        print(f"  kit {prior_stamp} → {_kit_build_stamp()}")
    print()
    print("  standalone (inline, send-as-file):")
    for src, _, _ in srcs:
        report("", standalone / src.relative_to(root))
    print()
    print("  site (shared assets, multi-page):")
    report("site root:", site)
    for src, _, _ in srcs:
        report("", site / src.relative_to(root))
    return 0


# ---------- clean ----------
# The only directories under dist/ this tool writes, and therefore the
# only ones it may remove. `markdown` is not written any more — the .md
# sources are the canonical AI surface — but older builds left one, so
# it is cleaned rather than orphaned. `_search` is the serve-time
# Pagefind index; it is here because nothing else removes it, and a
# stale one keeps answering for pages the source no longer has.
BUILD_TREES = ("standalone", "site", "markdown", "_search")


def _swap_build_trees(dist: Path, staging: Path) -> None:
    """Put the finished trees where the previous ones were.

    Called once, after every byte has been written into `staging`. Each
    tree moves in two renames — old aside, new into place — so the window
    in which the final path does not exist is a rename apart rather than
    a whole build long, and a failure on the second rename puts the old
    one back rather than leaving nothing.

    The trees `BUILD_TREES` names but this build did not produce are
    removed here too. That is the stale-artifact sweep the old code did
    up front: `dist/_search` outliving the pages it indexed, a
    `dist/markdown` tree from a version that still wrote one. Doing it at
    swap time rather than at the start is what makes a failed build cost
    nothing.
    """
    dist.mkdir(parents=True, exist_ok=True)
    built = set()
    for name in sorted(p.name for p in staging.iterdir()) if staging.is_dir() else []:
        new = staging / name
        final = dist / name
        old = dist / f".old-{name}-{os.getpid()}"
        if final.exists() or final.is_symlink():
            final.rename(old)
        try:
            new.rename(final)
        except OSError:
            if old.exists():
                old.rename(final)
            raise
        finally:
            shutil.rmtree(old, ignore_errors=True)
        built.add(name)
    for name in BUILD_TREES:
        if name in built:
            continue
        stale = dist / name
        if stale.is_dir() and not stale.is_symlink():
            shutil.rmtree(stale, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)


def cmd_clean(args: argparse.Namespace) -> int:
    """Remove the trees `oku build` writes under dist/, and nothing else.

    It used to be `shutil.rmtree(dist)`. `dist/` is a conventional name,
    not one this tool owns: a project can put a deploy script, a client's
    notes or a checked-in data file in there, and `oku clean` deleted all
    of it with a one-line success message and no way back. Removing only
    what the build writes costs one loop, and the difference is
    somebody's file.
    """
    root = Path.cwd()
    dist = root / "dist"
    if dist.is_symlink():
        # rmtree refuses a symlink with a raw OSError, which reads as a
        # crash rather than as the safe outcome it is.
        print(f"✓ Nothing removed — {dist} is a symlink; delete it yourself if you meant to.")
        return 0
    if not dist.exists():
        print(f"✓ Nothing to clean — {dist} does not exist.")
        return 0
    removed: list[str] = []
    for name in BUILD_TREES:
        tree = dist / name
        if not tree.exists():
            continue
        try:
            shutil.rmtree(tree)
        except OSError as err:
            print(f"✗ Could not remove {tree}: {err.strerror or err}", file=sys.stderr)
            return 1
        removed.append(name)
    kept = sorted(x.name for x in dist.iterdir()) if dist.exists() else []
    if not kept:
        dist.rmdir()
        print(f"✓ Removed {dist}")
        return 0
    if removed:
        print(f"✓ Removed {', '.join('dist/' + r for r in removed)}")
    else:
        print(f"✓ Nothing to clean — {dist} holds no built trees.")
    # Naming them is the point: a file here is either something the
    # project put there on purpose, or an old build product this version
    # no longer knows about, and only the author can tell which.
    print(f"  Kept {len(kept)} entr{'y' if len(kept) == 1 else 'ies'} oku did not write: {', '.join(kept)}")
    return 0


# ---------- serve ----------
def find_project_root(start: Path) -> Path:
    """Walk up to find the directory containing _oku; fallback to start."""
    cur = start.resolve()
    for ancestor in [cur, *cur.parents]:
        if (ancestor / "docs" / "_oku").exists():
            return ancestor
    return start


# ---------- Serve-time search index (best-effort) ----------
def _common_docs_dir(root: Path, pages: list[tuple[Path, dict]]) -> Path:
    """Find the closest common parent of all JSON pages — the natural
    'docs root' for serving search and other per-project assets.

    Most projects have all JSON pages in one directory (typically
    ``docs/``); a few nest deeper. Returns the project root as a safe
    fallback when pages live in scattered places.
    """
    if not pages:
        return root
    parents = [str(p.parent) for p, _ in pages]
    common = Path(os.path.commonpath(parents))
    try:
        common.relative_to(root)
    except ValueError:
        return root
    return common


def _build_serve_search_index(root: Path) -> bool:
    """Build a Pagefind index against the current docs and link it into
    the docs root so chrome.js's existing search-loader picks it up
    without needing a full ``oku build`` first.

    Best-effort: returns False (silently) if pagefind isn't on PATH or
    if any step fails. The user gets a notice; the rest of serve still
    works.
    """
    pages = find_json_pages(root)
    if not pages:
        return False
    if _pagefind_cmd(root) is None:
        print(
            "! Search disabled — install with  uv pip install 'pagefind[bin]'  "
            "(bundled binary, no system prereq), or pass --no-search to silence "
            "this notice."
        )
        return False
    docs_dir = _common_docs_dir(root, pages)
    htmls = [s for s in iter_page_stubs(docs_dir) if "dist" not in s[0].parts]
    if not htmls:
        return False
    target = root / "dist" / "_search" / "site"
    if target.exists():
        shutil.rmtree(target)
    try:
        build_site(htmls, target, docs_dir)
    except OSError:
        return False
    if not pagefind_index(target):
        return False
    # Surface the index at <docs-dir>/pagefind/ via symlink so the
    # runtime path __okuDocsRoot + 'pagefind/pagefind.js' resolves.
    pf_src = target / "pagefind"
    pf_link = docs_dir / "pagefind"
    if pf_src.exists():
        try:
            if pf_link.is_symlink() or pf_link.exists():
                if pf_link.is_symlink():
                    pf_link.unlink()
                elif pf_link.is_dir():
                    shutil.rmtree(pf_link)
            pf_link.symlink_to(pf_src.resolve())
            print(f"✓ Search index ready: {pf_link.relative_to(root)} ({len(htmls)} page(s))")
            return True
        except OSError as e:
            print(f"! Search index built but link failed: {e}")
    return False


# ---------- Live-reload (SSE + filesystem watcher) ----------
_SSE_CLIENTS: list = []
_SSE_LOCK = threading.Lock()


def _sse_broadcast(msg: str = "change") -> None:
    """Push a message to every connected SSE client. Best-effort — slow or
    disconnected clients are silently dropped on the next sweep when the
    handler thread observes the broken socket."""
    with _SSE_LOCK:
        for q in list(_SSE_CLIENTS):
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass


_WATCH_SKIP = {
    "dist",
    "_oku",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    "target",
    "build",
    ".gradle",
    "out",
}
_WATCH_SKIP_SUFFIX = {".pyc", ".swp", ".tmp", ".bak", ".log"}
_WATCH_SKIP_NAMES = {".DS_Store", "site-manifest.json", "llms.txt"}  # avoid feedback loop
# Whitelist of file types the renderer actually cares about. Anything
# else changing (Python source, IDE indexer scratch files, build
# artefacts the IDE writes alongside source) must NOT trigger a
# reload — otherwise the page flickers every time the IDE pokes a
# .py / .iml / .lock file. Previously we walked everything and any
# mtime drift caused a reload; the user reported this as "periodic
# refresh / flicker."
_WATCH_INCLUDE_SUFFIX = {
    ".json",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".css",
    ".js",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".avif",
}


def _snapshot_tree(root: Path) -> dict:
    """Map every renderable file under root → mtime, skipping generated /
    VCS / IDE dirs. Restricted to the suffix whitelist so IDE writes to
    unrelated files (e.g. .py, .iml, lock files) do not trigger reloads.
    Excludes site-manifest.json + llms.txt to avoid the rebuild→change
    loop."""
    state = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = p.parts
        if any(part in _WATCH_SKIP for part in parts):
            continue
        if p.suffix in _WATCH_SKIP_SUFFIX or p.name in _WATCH_SKIP_NAMES:
            continue
        if p.suffix.lower() not in _WATCH_INCLUDE_SUFFIX:
            continue
        try:
            state[str(p)] = p.stat().st_mtime
        except OSError:
            continue
    return state


def _watcher_loop(root: Path, stop: threading.Event) -> None:
    """Polling watcher (no external deps). Detects adds/deletes/modifies
    every ~400ms, debounces bursts within 200ms, rebuilds site-manifest +
    llms.txt, then broadcasts to SSE clients. Uses os.stat — light enough
    for the kinds of repo sizes oku targets (≤ a few hundred files)."""
    last = _snapshot_tree(root)
    while not stop.is_set():
        if stop.wait(0.4):
            break
        cur = _snapshot_tree(root)
        if cur == last:
            continue
        # Debounce — pause briefly, re-sample to let an editor finish a
        # multi-file save.
        time.sleep(0.2)
        cur = _snapshot_tree(root)
        last = cur
        # No source-side regeneration. The dev server synthesizes
        # site-manifest.{json,js} and llms.txt in memory on each request
        # via _serve_generated_artifact, so the watcher only needs to
        # tell connected clients to reload.
        _sse_broadcast("change")


def _make_serve_handler(root: Path):
    """Subclass SimpleHTTPRequestHandler with a /__reload SSE endpoint and
    quiet logging for the keepalive ticks."""

    # Resolved once, here, because every containment check below compares
    # a resolved filesystem path against this one. Handed a directory
    # reached through a symlink — `/var/...` on macOS, `~/code` pointing
    # into another tree, a worktree linked beside its repo — the two sides
    # disagree, `_serve_synthesized` decides the request is outside the
    # root, and every page answers 404 for its own JSON. The kit still
    # loads, so the reader gets the chrome, an empty column and no error.
    root = Path(root).resolve()

    class _Handler(http.server.SimpleHTTPRequestHandler):
        # Serve from the captured root regardless of process cwd changes
        # later in the lifetime.
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def handle(self) -> None:
            # Browsers drop SSE / kept-alive sockets unceremoniously
            # on tab navigation, sleep, or reload. The base class lets
            # the resulting ConnectionResetError / BrokenPipeError bubble
            # up to socketserver, which logs a noisy multi-line traceback
            # for every disconnect. Suppress here — these are normal,
            # not actionable.
            try:
                super().handle()
            except (ConnectionResetError, BrokenPipeError):
                pass

        def do_GET(self) -> None:  # noqa: N802 — base API
            if self.path == "/__reload":
                self._serve_reload_stream()
                return
            if self.path == "/favicon.ico":
                # Browsers auto-request /favicon.ico from every origin;
                # answering with a 1x1 empty PNG avoids a console 404 on
                # every page load without polluting the source tree with
                # a real favicon binary.
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                return
            # Synthesize stubs / JSON on the fly so `oku serve` previews
            # markdown- and json-authored sources without a build step:
            #   /<name>.html  + .md sibling  → md→page→stub
            #   /<name>.json  + .md sibling  → md→page JSON
            #   /<name>.html  + .json sibling → stub from json's title
            # Runtime expects .html (the kit-loading shell) + .json (the
            # renderer fetches this sibling). Authoring only the .json (or
            # .md) keeps source dirs free of boilerplate stubs (D5).
            if self._serve_kit_asset():
                return
            if self._serve_synthesized():
                return
            super().do_GET()

        def _serve_kit_asset(self) -> bool:
            """Serve any `…/_oku/<asset>` request from the kit directory
            when no such file exists on disk.

            `oku init` drops the _oku symlink in one directory — usually
            docs/. A page ANYWHERE else (a root README.md, a nested
            examples/ tree, a sibling notes/ folder) references _oku/
            relative to itself and gets a 404, which means no chrome.css,
            no chrome.js, no renderer: the page renders blank. Six of this
            repo's own 32 pages did exactly that. A real symlink still
            wins; this is the fallback.
            """
            url_path = unquote(self.path.split("?", 1)[0])
            marker = "/_oku/"
            idx = url_path.find(marker)
            if idx < 0:
                return False
            tail = url_path[idx + len(marker) :]
            if not tail or ".." in tail.split("/"):
                return False
            on_disk = (root / url_path.lstrip("/")).resolve()
            if on_disk.exists():
                return False  # a real _oku/ here — let the static handler serve it
            assets = _kit_assets_dir()
            try:
                target = (assets / tail).resolve()
                target.relative_to(assets.resolve())
            except (OSError, ValueError):
                return False
            if not target.is_file():
                return False
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(str(target)))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return True

        def _serve_synthesized(self) -> bool:
            """Synthesize generated artifacts in memory so source dirs
            stay clean. Returns True if the response was sent.

            Handles four shapes:
              /<name>.html  + .md sibling   → stub from md→page title
              /<name>.json  + .md sibling   → md→page JSON
              /<name>.html  + .json sibling → stub from json's title
              /<docs>/site-manifest.json / llms.txt
                                            → fresh from compute_manifest
                                              / compute_llms_txt
            Real-file-on-disk always wins (returns False, letting the
            static handler serve it).
            """
            # Percent-DECODE before the path touches the filesystem: a
            # browser encodes every non-ASCII byte and every space, so
            # "ölçüm raporu.md" arrives as %C3%B6l%C3%A7%C3%BCm%20raporu
            # and no synthesis site would ever find its source.
            url_path = unquote(self.path.split("?", 1)[0])
            # Generated docs-root artifacts: synthesize from the docs dir
            # without writing anything to source.
            if self._serve_generated_artifact(url_path):
                return True
            if not (url_path.endswith(".html") or url_path.endswith(".json")):
                return False
            try:
                # Translate the URL path to a filesystem path. Resolve
                # manually relative to `root` — SimpleHTTPRequestHandler's
                # translate_path doesn't honour `directory=` consistently
                # across Python versions.
                rel = url_path.lstrip("/")
                fs = (root / rel).resolve()
                if root not in fs.parents and fs != root:
                    return False
            except (OSError, ValueError):
                return False
            if fs.exists():
                return False

            source_path = None
            for cand in (_source_sibling(fs),):
                if cand.exists():
                    source_path = cand
                    break
            json_path = fs.with_suffix(".json")
            body: bytes | None = None
            content_type: str | None = None

            def _synth_stub(title: str) -> bytes:
                stub = _stub_for(title)
                # Nested pages need their _oku/ references walked back
                # up — to the NEAREST ancestor that holds the _oku kit
                # dir (dev layouts carry the symlink per docs root,
                # e.g. docs/_oku and examples/_oku), falling back to
                # the serve root. Applies to EVERY synthesized stub —
                # source-derived and json-derived alike.
                depth = 0
                anc = fs.parent
                while anc != root and not (anc / "_oku").exists():
                    anc = anc.parent
                    depth += 1
                if not (anc / "_oku").exists():
                    depth = len(fs.relative_to(root).parts) - 1
                if depth > 0:
                    stub = _retarget_kit_urls(stub, depth)
                return stub.encode("utf-8")

            if source_path is not None:
                page = _page_from_source_file(source_path)
                if page is None:
                    return False
                if url_path.endswith(".json"):
                    body = json.dumps(page, ensure_ascii=False, indent=2).encode("utf-8")
                    content_type = "application/json; charset=utf-8"
                else:
                    body = _synth_stub(_page_title(page) or fs.stem)
                    content_type = "text/html; charset=utf-8"
            elif url_path.endswith(".html") and json_path.exists():
                # The .json file IS on disk; only the .html shell is missing.
                # Synthesize the stub from the json's title (D5).
                try:
                    page = json.loads(json_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    return False
                if not _is_page(page):
                    return False
                body = _synth_stub(_page_title(page) or json_path.stem)
                content_type = "text/html; charset=utf-8"
            else:
                return False

            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return True

        def _serve_generated_artifact(self, url_path: str) -> bool:
            """Synthesize site-manifest.json or llms.txt for any URL
            ending with one of those filenames. The docs root is the
            URL's parent directory: GET /docs/site-manifest.json
            means "manifest of pages under root/docs". Returns True if
            the request was handled."""
            artifact_name = url_path.rsplit("/", 1)[-1]
            if artifact_name not in (
                "site-manifest.json",
                "llms.txt",
                "kit.json",
            ):
                return False
            if artifact_name == "kit.json":
                # The project has ONE kit.json (glossary domains, language),
                # usually in docs/. chrome.js asks for it at whatever docs
                # root the page resolved to, so a page outside that folder
                # would lose its glossary entirely. Serve the project's copy
                # wherever it is asked for; a real file on disk still wins.
                if (root / url_path.lstrip("/")).exists():
                    return False
                found = find_kit_json(root)
                if found is None:
                    return False
                body = found.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return True
            try:
                rel_dir = url_path.lstrip("/").rsplit("/", 1)[0] if "/" in url_path.lstrip("/") else ""
                docs_root = (root / rel_dir).resolve() if rel_dir else root
                if docs_root != root and root not in docs_root.parents:
                    return False
                if not docs_root.exists():
                    return False
            except (OSError, ValueError):
                return False
            if artifact_name == "llms.txt":
                body = compute_llms_txt(docs_root).encode("utf-8")
                content_type = "text/plain; charset=utf-8"
            else:
                manifest = compute_manifest(docs_root)
                body = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                content_type = "application/json; charset=utf-8"
            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return True

        def _serve_reload_stream(self) -> None:
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                return
            q: queue.Queue = queue.Queue(maxsize=8)
            with _SSE_LOCK:
                _SSE_CLIENTS.append(q)
            try:
                self.wfile.write(b": hello\n\n")
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=25)
                        self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # keepalive comment — many proxies drop idle SSE
                        # connections after 30s; 25s is well inside that.
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with _SSE_LOCK:
                    if q in _SSE_CLIENTS:
                        _SSE_CLIENTS.remove(q)

        def log_message(self, fmt: str, *args) -> None:  # noqa: N802
            # Suppress the per-request log for /__reload — it spams once
            # per second from the keepalive when a tab is open.
            try:
                first = args[0] if args else ""
                if "/__reload" in str(first):
                    return
            except Exception:
                pass
            super().log_message(fmt, *args)

    return _Handler


def _pick_open_target(htmls: list[Path], user_cwd: Path, root: Path) -> Path | None:
    """Choose the page to auto-open. Preference order:
    1. First page in the site tree (`nav_sort_key` order) — this is what
       the sidebar shows as "page 1", so the user lands on real content
       instead of an empty index.
    2. <user_cwd>/index.html if it's on disk under the user's directory.
    3. Fallbacks: first index.html under user_cwd, first HTML, etc.
    """
    if not htmls:
        return None
    try:
        rel_user = user_cwd.resolve().relative_to(root.resolve())
    except ValueError:
        rel_user = Path(".")
    user_prefix = (root / rel_user).resolve()
    html_set = {h.resolve() for h in htmls}

    # Primary: the first page in the manifest, which compute_manifest
    # sorts with `nav_sort_key` — so pages[0] IS the tree's first row,
    # the one a user would open first if browsing the sidebar.
    try:
        manifest = compute_manifest(root)
        entries = manifest.get("pages") or []
        for entry in entries:
            cand = (root / entry["path"]).resolve()
            if cand in html_set:
                # Prefer pages under the user's cwd when one matches,
                # so `cd subdir && oku serve` opens that subdir's first.
                if user_prefix in cand.parents or cand == user_prefix:
                    return cand
        # No user-cwd-local match; fall through to the first entry.
        for entry in entries:
            cand = (root / entry["path"]).resolve()
            if cand in html_set:
                return cand
    except (OSError, ValueError, KeyError):
        pass

    # Fallback chain — same as before, in case manifest computation
    # fails or returns nothing.
    direct = user_prefix / "index.html"
    if direct.exists():
        return direct
    under_user = [h for h in htmls if str(h.resolve()).startswith(str(user_prefix))]
    for h in under_user:
        if h.name == "index.html":
            return h
    if under_user:
        return under_user[0]
    skipped = {"_internal", "examples"}
    public = [h for h in htmls if not (set(h.relative_to(root).parts) & skipped)]
    if public:
        return public[0]
    return htmls[0]


def _is_loopback(host: str) -> bool:
    """Whether an address reaches only this machine.

    Kept as a function rather than a `host == "127.0.0.1"` comparison
    because `::1`, `localhost` and the whole 127.0.0.0/8 block are all
    loopback, and a warning that fires on `127.0.0.2` is one people
    learn to ignore. An empty host is the WILDCARD, not loopback — that
    conflation is the defect this replaces.
    """
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def cmd_serve(args: argparse.Namespace) -> int:
    """Start an HTTP server at the project root and print HTTP URLs for every HTML.

    Why: file:// has browser-specific restrictions (symlink resolution, CORS-like
    rules, cross-directory script loading). Serving via HTTP makes all references
    resolve reliably across Chrome, Safari, Firefox.

    By default, also starts a filesystem watcher and an SSE channel at
    /__reload — chrome.js opens an EventSource to it and reloads the
    tab when source changes. Disable with --no-watch.
    """
    cwd = Path.cwd()
    root = find_project_root(cwd)
    user_cwd = cwd  # capture before chdir so we can prefer pages near where the user was
    os.chdir(root)
    handler_cls = _make_serve_handler(root)

    # Loopback by default. The previous bind was `("", port)` — every
    # interface — while the line printed underneath said `localhost`,
    # so the one place a reader could check said the opposite of what
    # happened. What is published is not a doc tree: `_make_serve_handler`
    # serves the PROJECT root, which is the working copy, `.env` and all,
    # to anyone who can route to this machine. On a café or hotel network
    # that is everyone on it.
    host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
    port = 9876
    httpd = None
    while True:
        try:
            httpd = http.server.ThreadingHTTPServer((host, port), handler_cls)
            break
        except OSError:
            port += 1
            if port > 9900:
                print("✗ Could not find a free port in 9876–9900", file=sys.stderr)
                return 1
    assert httpd is not None
    httpd.daemon_threads = True  # let Ctrl-C terminate hung SSE threads cleanly

    # Source dirs stay clean: site-manifest.{json,js} and llms.txt are
    # synthesized in memory by _serve_generated_artifact on each request.
    # Markdown twins, the build's pagefind index, and dist outputs all
    # land under dist/ via `oku build`.

    htmls = sorted(p for p in root.rglob("*.html") if not any(part in SKIP_DIRS for part in p.parts))

    # Serve-time Pagefind index (background, best-effort) so search works
    # without requiring the user to run `oku build` first.
    search_enabled = not getattr(args, "no_search", False)
    if search_enabled:
        threading.Thread(
            target=_build_serve_search_index, args=(root,), name="oku-search", daemon=True
        ).start()

    # Filesystem watcher → SSE broadcast → in-browser reload.
    watch_enabled = not getattr(args, "no_watch", False)
    watcher_stop = threading.Event()
    watcher_thread = None
    if watch_enabled:
        watcher_thread = threading.Thread(
            target=_watcher_loop,
            args=(root, watcher_stop),
            name="oku-watcher",
            daemon=True,
        )
        watcher_thread.start()

    # Print what was actually bound, not a friendly constant.
    bound_host, bound_port = httpd.server_address[0], httpd.server_address[1]
    loopback = _is_loopback(bound_host)
    display = "localhost" if loopback else bound_host
    print(f"✓ Serving {root} on http://{display}:{bound_port}  (bound {bound_host})")
    if not loopback:
        print(
            f"  ⚠ Reachable from the network. Everything under {root} is readable "
            "by anyone who can route to this machine, with no password."
        )
    if watch_enabled:
        print("  Live reload: on  (SSE at /__reload — disable with --no-watch)")
    else:
        print("  Live reload: off")
    print("  Stop with Ctrl-C.")
    print()
    target = _pick_open_target(htmls, user_cwd, root)
    if htmls:
        print("  HTML files:")
        for h in htmls:
            rel = h.relative_to(root)
            marker = "  ←" if target is not None and h == target else ""
            print(f"    http://{display}:{bound_port}/{rel}{marker}")
        if target is not None:
            webbrowser.open(f"http://{display}:{bound_port}/{target.relative_to(root)}")
    print()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Stopped.")
        watcher_stop.set()
        httpd.shutdown()
        httpd.server_close()
    return 0


def _page_content_fingerprint(page: dict) -> tuple[str, str, str]:
    """Title, typed blocks and prose of a page, in a form that survives
    markdown emission. Two pages with the same fingerprint render the
    same content — used to prove a migration is lossless before the
    source JSON is deleted."""
    v2 = _v1_to_v2(page) if (page.get("kind") == "page" and not page.get("k")) else page
    body = v2.get("b") or []
    typed = json.dumps([b for b in body if isinstance(b, dict)], sort_keys=True, ensure_ascii=False)
    prose = re.sub(r"\s+", " ", " ".join(b for b in body if isinstance(b, str))).strip()
    return (str(v2.get("t") or ""), typed, prose, _comparable_meta(v2))


def _comparable_meta(page: dict) -> str:
    """The front-matter a migration must carry across, as one string.

    The fingerprint used to be title + typed blocks + prose, and `m` was
    not in it — so a value the emitter could not write came back missing
    or changed, the round trip was declared lossless, and the source
    JSON was deleted. Measured on a page carrying four ordinary keys:
    a multi-line `summary` vanished, `tags: ["a","b"]` came back as the
    literal string `"['a', 'b']"`, `order: "007"` as the int 7 and
    `flag: "true"` as a bool. All four passed as lossless.

    Private and derived keys are excluded because they are meant not to
    survive: `_derived` names what the build works out again on the
    next run, and re-emitting those into a source is what freezes them
    stale.
    """
    meta = page.get("m") or {}
    derived = set(meta.get("_derived") or ())
    keep = {k: v for k, v in meta.items() if not k.startswith("_") and k not in derived}
    return json.dumps(keep, sort_keys=True, ensure_ascii=False, default=str)


# ---------- main ----------
# ---------- vendored runtime dependencies ----------
#
# Two libraries are fetched from a CDN at RUNTIME: mermaid draws the
# diagrams, Prism colours the code. Measured on the built
# docs/architecture.html with the CDN blocked: 6 of 6 diagrams fail and
# 598 syntax tokens become 0. Line numbers survive — they were made
# independent of the CDN earlier.
#
# Inlining mermaid into each page is the obvious fix and the wrong one:
# it is 3,337,857 bytes against a 1.1 MB page, and a doc tree pays that
# per page that draws anything. The files are identical across every
# document, so they are fetched ONCE into the installed kit and shared —
# which also stops a reader's browser re-fetching 3.3 MB per cold page
# load. The CDN stays as the fallback for a file that travels alone.
_PRISM_VERSION = "1.29.0"
_MERMAID_VERSION = "10"
_PRISM_CDN = f"https://cdn.jsdelivr.net/npm/prismjs@{_PRISM_VERSION}/"
_MERMAID_CDN = f"https://cdn.jsdelivr.net/npm/mermaid@{_MERMAID_VERSION}/dist/mermaid.min.js"
# The five the loader preloads, plus the languages this kit's own pages
# and its likely consumers actually use. An unlisted language falls back
# to no highlighting offline, which is the same degradation as today.
# `regex` is here for a reason the others are not: nothing tags a block
# with it. Prism's own JavaScript grammar gives a regex literal's source
# the alias `language-regex`, and the autoloader then goes looking for a
# component the kit did not vendor — one 404 in the reader's console per
# page carrying a JS regex, with the page otherwise fine. Vendoring it
# turns that request into the highlighting it was asking for.
_PRISM_LANGS = (
    "javascript css bash json yaml python typescript jsx tsx java go rust sql markup "
    "diff toml ini docker kotlin scala c cpp csharp php ruby swift graphql markdown mermaid "
    "regex"
).split()


# The two families chrome.css asks for, as variable woff2 — one file per
# family per subset, every weight inside. Fontsource publishes the same
# files Google Fonts serves, under the same OFL-1.1 licence, at a URL
# that does not change per request.
#
# latin-ext is not optional here: Turkish `ş` and `ğ` live in it, and
# this kit ships Turkish pages. Without it those two letters fall back to
# the system font mid-word.
_FONTSOURCE = "https://cdn.jsdelivr.net/npm/@fontsource-variable/"
_VENDOR_FONTS = (
    ("inter-latin-wght-normal.woff2", "inter"),
    ("inter-latin-ext-wght-normal.woff2", "inter"),
    ("jetbrains-mono-latin-wght-normal.woff2", "jetbrains-mono"),
    ("jetbrains-mono-latin-ext-wght-normal.woff2", "jetbrains-mono"),
)


def vendor_fonts_present() -> bool:
    """True when every face chrome.css declares is on disk.

    All or nothing on purpose: half the faces present means a page that
    renders Latin in Inter and Turkish in the system font, which reads as
    a rendering bug rather than as a missing dependency.
    """
    root = vendor_dir() / "fonts"
    return all((root / name).exists() for name, _pkg in _VENDOR_FONTS)


def _vendor_files() -> list[tuple[str, str]]:
    """(path under vendor/, source URL) for every shared dependency."""
    out = [
        ("mermaid.min.js", _MERMAID_CDN),
        ("prism/prism.min.js", _PRISM_CDN + "prism.min.js"),
        (
            "prism/plugins/autoloader/prism-autoloader.min.js",
            _PRISM_CDN + "plugins/autoloader/prism-autoloader.min.js",
        ),
    ]
    out += [
        (f"prism/components/prism-{lang}.min.js", f"{_PRISM_CDN}components/prism-{lang}.min.js")
        for lang in _PRISM_LANGS
    ]
    out += [(f"fonts/{name}", f"{_FONTSOURCE}{pkg}/files/{name}") for name, pkg in _VENDOR_FONTS]
    return out


def vendor_dir() -> Path:
    return _kit_assets_dir() / "vendor"


def vendor_is_complete() -> bool:
    root = vendor_dir()
    return all((root / rel).exists() for rel, _url in _vendor_files())


def fetch_vendor(*, update: bool = False, quiet: bool = False) -> tuple[int, int]:
    """Download missing (or all, with update) dependencies. Returns
    (fetched, skipped). Never raises on a network failure: the CDN
    fallback still works, so a failed vendor is a slower page, not a
    broken one."""
    import urllib.error
    import urllib.request

    root = vendor_dir()
    fetched = skipped = 0
    for rel, url in _vendor_files():
        dest = root / rel
        if dest.exists() and not update:
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - pinned https CDN
                data = r.read()
        except (urllib.error.URLError, OSError, ValueError) as e:
            if not quiet:
                print(f"  ! {rel}: {e}", file=sys.stderr)
            continue
        dest.write_bytes(data)
        fetched += 1
    return fetched, skipped


def cmd_vendor(args: argparse.Namespace) -> int:
    """`oku vendor` — fetch the shared runtime dependencies once."""
    root = vendor_dir()
    fetched, skipped = fetch_vendor(update=args.update)
    total = sum(f.stat().st_size for f in root.rglob("*") if f.is_file()) if root.exists() else 0
    print(f"✓ vendor: {fetched} fetched, {skipped} already present — {total / 1_000_000:.1f} MB in {root}")
    if not vendor_is_complete():
        # Two different fallbacks, so the line says which one applies.
        # mermaid and Prism have a CDN behind them; the fonts do not, by
        # design — reaching a font host is the defect vendoring them
        # fixed, so their absence is a typeface change, not a slow page.
        missing_fonts = not vendor_fonts_present()
        note = "pages fall back to the CDN for whatever is missing"
        if missing_fonts:
            note += "; without the fonts, pages render in the system stack"
        print(f"  ! incomplete — {note}", file=sys.stderr)
        return 1
    return 0


_examples_cache: dict | None = None


def _load_examples() -> dict:
    """Lazy-load and cache the shipped payload examples."""
    global _examples_cache
    if _examples_cache is not None:
        return _examples_cache
    path = KIT_DIR / "schema" / "examples.json"
    try:
        _examples_cache = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _examples_cache = {}
    return _examples_cache


def _spec_entry(name: str) -> dict | None:
    """Resolve a name to what an author would paste.

    Not every block kind is a typed fence. `code`, `image` and `svg` are
    real `$defs` entries reachable from a JSON page, but a v3 markdown
    page writes them as a plain code fence, an `![alt](src)`, and an HTML
    island — `_FENCE_KINDS` does not lift them, so printing an
    ```oku-code fence would print something that stays literal text.
    Those kinds carry their authoring form instead.

    Block kinds win a tie against chart types, and `test_spec_examples`
    asserts there is never a tie to win.
    """
    ex = _load_examples()
    blocks = ex.get("blocks") or {}
    charts = ex.get("charts") or {}
    markdown = ex.get("markdown") or {}
    inline = ex.get("inline") or {}
    if name in inline:
        entry = inline[name]
        return {
            "payload": entry,
            "fence": None,
            "markdown": entry.get("markdown"),
            "note": entry.get("note"),
            "inline": True,
        }
    if name in blocks:
        return {
            "payload": blocks[name],
            "fence": f"oku-{name}" if name in _FENCE_KINDS else None,
            "markdown": markdown.get(name),
        }
    if name in charts:
        return {"payload": charts[name], "fence": "oku-chart", "markdown": None}
    return None


def cmd_spec(args: argparse.Namespace) -> int:
    """Print the payload an author would otherwise go hunting for.

    The hunt was the expensive part. `docs/reference.md` and
    `docs/charts.md` carry every shape, but neither ships in the wheel —
    the force-include list is assets only — so from any project that
    installed the tool, the sole local source of truth was
    `page.schema.json`: 11.6k tokens, 75 chart properties, 29 `allOf`
    branches, and no worked example of any of them. The realistic
    alternatives were to guess and let `oku check` referee, or to read the
    schema. Both cost more than this prints, and the first also risks a
    wrong-but-valid payload, which validates clean and renders empty.
    """
    ex = _load_examples()
    if not ex:
        print(f"! no examples file at {KIT_DIR / 'schema' / 'examples.json'}", file=sys.stderr)
        return 1

    blocks = ex.get("blocks") or {}
    charts = ex.get("charts") or {}

    if not args.name:
        fenced = sorted(k for k in blocks if k in _FENCE_KINDS)
        plain = sorted(k for k in blocks if k not in _FENCE_KINDS)
        print(f"block kinds ({len(fenced)}) — fence is ```oku-<kind>")
        # Every name here is hyphenated (`calendar-heatmap`, `kpi-grid`) and
        # is meant to be copied, so the wrapper must never break on a hyphen.
        wrap = {
            "width": 76,
            "initial_indent": "  ",
            "subsequent_indent": "  ",
            "break_on_hyphens": False,
            "break_long_words": False,
        }
        print(textwrap.fill(" ".join(fenced), **wrap))
        if plain:
            print(f"\nwritten as plain markdown ({len(plain)}) — no oku- fence")
            print(textwrap.fill(" ".join(plain), **wrap))
        print(f'\nchart types ({len(charts)}) — fence is ```oku-chart with "type"')
        print(textwrap.fill(" ".join(sorted(charts)), **wrap))
        # Written inside a sentence, so they belong to no fence and were
        # listed nowhere. An author reading this list concluded the kit
        # had 70 primitives and none of them for a path.
        inline = ex.get("inline") or {}
        if inline:
            print(f"\ninline ({len(inline)}) — written as a link, inside a sentence")
            print(
                textwrap.fill(" ".join(f"{k} {v}" for k, v in _INLINE_KINDS.items() if k in inline), **wrap)
            )
        # Listed with the rest, because a discoverability feature nobody
        # can discover is the failure this command exists to fix.
        print("\nalso: front-matter — every page-level key, with what it does")
        print("\noku spec <name>   one ready-to-paste payload")
        return 0

    # Not a block kind: the other thing every page has, and the one an
    # author cannot infer from the body they are writing. 7 of the 10
    # keys were named nowhere in the briefing.
    if args.name in ("front-matter", "frontmatter", "meta"):
        schema = _load_schema()
        props = ((schema.get("$defs") or {}).get("meta") or {}).get("properties") or {}
        rows = {"title": {"type": "string", "description": "Page title. Required."}, **props}
        if args.json:
            print(json.dumps(rows, ensure_ascii=False))
            return 0
        derived = set(_DERIVABLE_META)
        print("---")
        for key, spec in rows.items():
            kind = spec.get("type", "string")
            note = spec.get("description", "")
            mark = f" # DERIVED from {_DERIVABLE_META[key]} — do not hand-set" if key in derived else ""
            print(f"{key}: <{kind}>{mark or ((' # ' + note) if note else '')}")
        print("---")
        print("\nAny other key is accepted and ignored; one that resembles these is flagged.")
        return 0

    entry = _spec_entry(args.name)
    if entry is None:
        known = sorted(set(blocks) | set(charts) | set(ex.get("inline") or {}))
        near = difflib.get_close_matches(args.name, known, n=3, cutoff=0.5)
        print(f"! unknown name {args.name!r}", file=sys.stderr)
        if near:
            print(f"  did you mean: {', '.join(near)}", file=sys.stderr)
        else:
            print("  `oku spec` with no argument lists every name", file=sys.stderr)
        return 1

    if entry.get("inline"):
        if args.json:
            print(json.dumps(entry["payload"], ensure_ascii=False))
            return 0
        print(entry["markdown"])
        # The syntax alone answers "how"; an author reaching for a
        # primitive is asking "when", and that is the half that decides
        # whether it gets used at all.
        print("\n" + textwrap.fill(entry["note"] or "", width=76))
        return 0

    body = json.dumps(entry["payload"], separators=(",", ":"), ensure_ascii=False)
    if args.json:
        print(body)
    elif entry["fence"]:
        print(f"```{entry['fence']}\n{body}\n```")
    else:
        print(entry["markdown"])
    return 0


# What a browser can decide about a built page, and a linter cannot.
# `oku check` reads the source; this reads the RESULT, which is where
# the failures it cannot see live: a payload that validates and draws
# nothing, a figure that overflows the column, a diagram whose source
# parsed and whose renderer then failed, a block the renderer replaced
# with an error card, a disclosure that opens onto nothing.
_VERIFY_PROBE = """() => {
  const bad = [];
  document.querySelectorAll('oku-diagram').forEach((d, i) => {
    if (/Parse error|Syntax error/i.test(d.textContent)) bad.push('diagram ' + (i + 1) + ' failed to parse');
    else if (!d.querySelector('svg')) bad.push('diagram ' + (i + 1) + ' drew no svg');
  });
  const PAINT = 'svg rect, svg path, svg circle, svg line, svg polygon, canvas, img,'
    + ' .bar-track, .kpi, .step-card, .compare-card, .okt-tl-item, aside.insight,'
    + ' details.info-tip, td, th, pre code, .okt-diag-node';
  document.querySelectorAll('oku-chart, .bar-chart, .okt-table-wrap, .kpi-grid,'
    + ' .step-flow, .compare-grid, .okt-timeline, .okt-chart-grid').forEach((fig) => {
    // A comparison card's preview is a CLONE of a figure that is itself
    // checked, deliberately miniature — 203x104 with marks of a few
    // square pixels. Judging it by the same threshold reports every one
    // of them as empty, which is how this probe first behaved. The rail
    // skips them for the same reason.
    if (fig.closest('.okt-compare-preview')) return;
    // Total ink, not the largest mark: a dense chart is hundreds of tiny
    // paths and no single one of them is big.
    const ink = [...fig.querySelectorAll(PAINT)].reduce((sum, e) => {
      const r = e.getBoundingClientRect();
      return sum + r.width * r.height;
    }, 0);
    if (ink <= 100) bad.push((fig.tagName.toLowerCase() + '.' + (fig.className || '')).slice(0, 40)
      + ' rendered an empty box');
  });
  // The renderer already draws a card where a block it cannot read
  // should have been. Nothing outside the browser was reading them, so
  // a page could carry a contract violation in plain sight and still
  // verify clean.
  document.querySelectorAll('.okt-block-error').forEach((card) => {
    bad.push('block error: ' + (card.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 90));
  });
  // A disclosure holding only its summary. The ink check above cannot
  // see it — the summary is painted, and that IS a closed <details>'s
  // rendered state — so an empty body reads as a healthy figure.
  document.querySelectorAll('details.info-tip').forEach((d, i) => {
    if (d.childElementCount < 2) bad.push('disclosure ' + (i + 1) + ' opens onto nothing');
  });
  const doc = document.documentElement;
  if (doc.scrollWidth > window.innerWidth + 1) {
    const wide = [...document.querySelectorAll('main *')].filter((e) => {
      const r = e.getBoundingClientRect();
      return r.right > window.innerWidth + 1 && getComputedStyle(e).overflowX !== 'auto';
    })[0];
    bad.push('page scrolls sideways' + (wide ? ' — ' + wide.tagName.toLowerCase() + '.' + (wide.className || '') : ''));
  }
  return bad;
}"""


def cmd_verify(args: argparse.Namespace) -> int:
    """`oku verify` — open the built pages and report what a linter cannot see.

    Four of the skill's manual browser steps, run for real: console
    errors, diagrams that failed to draw, figures that render an empty
    box, and sideways scroll. Each was prose asking an author to look,
    and a step you have to remember is a step that gets skipped —
    especially the one that catches the wrong-but-valid payload, which
    is the failure no source-level check can reach.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "✗ oku verify needs playwright: uv tool install 'oku[verify]' "
            "(then `playwright install chromium`)",
            file=sys.stderr,
        )
        return 2

    root = Path.cwd()
    standalone = sorted((root / "dist" / "standalone").rglob("*.html"))
    site_dir = root / "dist" / "site"
    if not standalone:
        print(
            f"✗ nothing built under {root / 'dist' / 'standalone'} — run `oku build` first", file=sys.stderr
        )
        return 1

    failures: list[str] = []

    def check(browser, url: str, rel: str, widths: list[int]) -> None:
        """Open one page and record everything a source check cannot see.

        A FRESH page per document, deliberately. The listeners below were
        attached inside the loop on one shared page, so every document
        added another set that never came off — and any state a page
        stored (a pinned drawer, a theme, a width) carried into the next
        one, which is the state that hid a crash for a whole release.
        """
        page = browser.new_page()
        errors: list[str] = []
        missing: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)[:120]))
        # A failed request reports as a generic "Failed to load
        # resource" on the console, with no URL — useless for saying
        # WHAT is missing, so the request itself is what gets
        # recorded and the console duplicate is dropped.
        page.on(
            "console",
            lambda m: (
                errors.append(m.text[:120])
                if m.type == "error" and "Failed to load resource" not in m.text
                else None
            ),
        )
        page.on("requestfailed", lambda r: missing.append(r.url))
        page.on("response", lambda r: missing.append(r.url) if r.status == 404 else None)
        try:
            for width in widths:
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(url)
                try:
                    page.wait_for_function("() => window.__okuRendered === true", timeout=20000)
                    page.wait_for_function(
                        "() => [...document.querySelectorAll('oku-diagram')]"
                        ".every((d) => d._rendered || /Parse error/i.test(d.textContent))",
                        timeout=30000,
                    )
                except Exception:  # noqa: BLE001 - a page that never finishes IS the finding
                    failures.append(f"{rel} @{width}px: never finished rendering")
                    continue
                for problem in page.evaluate(_VERIFY_PROBE):
                    failures.append(f"{rel} @{width}px: {problem}")
            for err in dict.fromkeys(errors):
                failures.append(f"{rel}: console — {err}")
            for url_missing in dict.fromkeys(missing):
                # Prism's markdown grammar probes for the language of any
                # fence nested inside a markdown sample, so a page that
                # documents this kit asks for `prism-oku-chart.min.js`.
                # That set is unbounded and a missing grammar degrades to
                # unhighlighted code, which is not a build failure.
                if "/prism/components/" in url_missing:
                    continue
                # A REMOTE origin failing is the network's state, not the
                # page's, and judging the page on it makes this command
                # fail for reasons the author cannot fix. A local one is
                # the page asking for something the build did not write,
                # which is precisely this command's job.
                if url_missing.startswith(("http://", "https://")) and "127.0.0.1" not in url_missing:
                    continue
                failures.append(f"{rel}: could not load {url_missing.rsplit('/', 1)[-1]}")
        finally:
            page.close()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for html in standalone:
            check(browser, html.as_uri(), str(html.relative_to(root)), [1440, 360])

        # dist/site is the OTHER tree the build ships, and this command
        # never opened it. Everything that only breaks there — the shared
        # `_oku/` assets, the fetched manifest, kit.json, the vendored
        # dependencies — was outside the gate by construction, so it was
        # found by opening a deployed page by hand instead. It needs a
        # server: those pages fetch, and file:// refuses.
        site_pages = sorted(site_dir.rglob("*.html")) if site_dir.is_dir() else []
        if site_pages:
            import functools
            import http.server
            import threading

            class _QuietHandler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *args):  # noqa: A003 - stdlib hook name
                    pass  # a verify run reports findings, not a request log

            handler = functools.partial(_QuietHandler, directory=str(site_dir))
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            try:
                for html in site_pages:
                    rel = html.relative_to(site_dir).as_posix()
                    # One width here: the CSS is the same file in both
                    # trees, so the narrow pass above already covered
                    # layout. What differs is what the page can REACH.
                    check(browser, f"{base}/{rel}", f"dist/site/{rel}", [1440])
            finally:
                httpd.shutdown()
        browser.close()

    if failures:
        print(f"✗ {len(failures)} problem(s) a source check cannot see:", file=sys.stderr)
        for f in failures[:40]:
            print(f"  ✗ {f}", file=sys.stderr)
        if len(failures) > 40:
            print(f"  … {len(failures) - 40} more", file=sys.stderr)
        return 1
    checked = len(standalone) + len(sorted(site_dir.rglob("*.html")) if site_dir.is_dir() else [])
    print(f"✓ {checked} page(s) render clean across both built trees (1440px and 360px)")
    return 0


def _lossy_detail(before: tuple, after: tuple) -> str:
    """Name the part that would not survive, so the message is a lead.

    "Report this page" alone gives the author nothing to look at, and
    the answer is usually one front-matter key they can rewrite in ten
    seconds.
    """
    labels = ("title", "typed blocks", "prose", "front-matter")
    changed = [labels[i] for i in range(min(len(before), len(after))) if before[i] != after[i]]
    if changed == ["front-matter"]:
        try:
            was, now = json.loads(before[3]), json.loads(after[3])
        except (json.JSONDecodeError, IndexError):
            return " Front-matter would change."
        keys = sorted(set(was) | set(now))
        lost = [k for k in keys if was.get(k) != now.get(k)]
        return " These front-matter keys would not survive: " + ", ".join(lost) + "."
    return (
        " Would change: " + ", ".join(changed) + "."
        if changed
        else " Report this page; the JSON still renders."
    )


def cmd_migrate(args: argparse.Namespace) -> int:
    """`oku migrate [path]` — convert page-JSON sources (v1 or v2) to
    v3 markdown.

    Each page `foo.json` becomes `foo.md` next to it and the JSON file
    is removed (`--keep-json` retains it; note a kept .json shadows the
    .md — the walkers prefer the real JSON sibling). The .html stub is
    untouched: it fetches `foo.json`, which `oku serve` and `oku build`
    synthesize from the .md source.

    The renderer accepts v1/v2 pages indefinitely, so migration is
    optional — run it when you want the on-disk source in the current
    authoring format.

    Exit codes:
      0 — done (zero or more files migrated; --dry-run also returns 0).
      1 — input path missing.
    """
    target = Path(args.path or ".").resolve()
    if not target.exists():
        print(f"✗ {target} not found", file=sys.stderr)
        return 1
    candidates: list[Path] = []
    if target.is_file():
        candidates = [target]
    else:
        for p in iter_repo_files(target, (".json",), extra_skip=project_skip_dirs(target)):
            if p.name in ("kit.json", "site-manifest.json", "package.json", "tsconfig.json"):
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if _is_page(data):
                candidates.append(p)
    if not candidates:
        print(f"✓ No page-JSON files found under {target}")
        return 0
    migrated = 0
    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  skip {p}: {e}", file=sys.stderr)
            continue
        if not _is_page(data):
            print(f"  skip {p.name}: not a page")
            continue
        md_path = p.with_suffix(".md")
        try:
            rel = p.relative_to(target if target.is_dir() else target.parent)
        except ValueError:
            rel = p
        if md_path.exists():
            print(f"  skip {rel}: {md_path.name} already exists")
            continue
        # Deleting the JSON is irreversible, so prove the round-trip first:
        # emit the markdown, parse it back, and compare content. A page
        # holding something the emitter cannot express keeps its JSON.
        md_text = page_to_md(data)
        back = md_to_v2_page(md_text, default_title=_page_title(data) or md_path.stem)
        before, after = _page_content_fingerprint(data), _page_content_fingerprint(back)
        if before != after:
            detail = _lossy_detail(before, after)
            print(
                f"  skip {rel}: markdown round-trip is not lossless — source kept.{detail}",
                file=sys.stderr,
            )
            continue
        if args.dry_run:
            print(f"  would migrate {rel} → {md_path.name}")
        else:
            md_path.write_text(md_text, encoding="utf-8")
            if not args.keep_json:
                p.unlink()
            print(f"  migrated {rel} → {md_path.name}")
        migrated += 1
    label = "Would migrate" if args.dry_run else "Migrated"
    print(f"\n{label} {migrated} page(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="oku",
        description="Shared HTML chrome kit. Init projects, build artifacts, serve locally.",
    )
    # Version prints the kit build stamp and the assets path too: an
    # installed tool carries its own copy of the kit, and "did my kit
    # change reach the tool?" is otherwise a filesystem hunt.
    parser.add_argument(
        "--version",
        action=_VersionAction,
        version=(
            f"oku {_PKG_VERSION} · kit {_kit_build_stamp()} · src {_tool_digest()}"
            f" · as of {_tool_dated()} · assets {_kit_assets_dir()}"
        ),
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser(
        "verify",
        help="open the built pages in a browser and report what a source check cannot see",
    )
    vendor_parser = sub.add_parser(
        "vendor",
        help="fetch mermaid + Prism once so pages render offline without re-downloading",
    )
    vendor_parser.add_argument(
        "--update",
        action="store_true",
        help="re-fetch even when a copy is already present (new upstream release)",
    )
    spec_parser = sub.add_parser(
        "spec",
        help="print a ready-to-paste payload for a block kind or chart type",
    )
    spec_parser.add_argument(
        "name",
        nargs="?",
        help="block kind (table, kpi-grid, …) or chart type (sankey, gantt, …); omit to list every name",
    )
    spec_parser.add_argument(
        "--json",
        action="store_true",
        help="print the bare payload instead of the fence that wraps it",
    )
    sub.add_parser("init", help="create an _oku symlink in the current directory")
    build_parser = sub.add_parser("build", help="build dist/{standalone,site}/ from current dir")
    build_parser.add_argument(
        "--no-vendor",
        action="store_true",
        help="skip fetching mermaid + Prism; pages fall back to the CDN",
    )
    build_parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="build even when the doctree check reports errors (they are still printed)",
    )
    sub.add_parser("clean", help="remove the trees oku built under dist/")
    migrate_parser = sub.add_parser(
        "migrate",
        help="convert page-JSON sources (v1/v2) to v3 markdown",
    )
    migrate_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="file or directory to migrate (defaults to cwd)",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list files that would change without writing",
    )
    migrate_parser.add_argument(
        "--keep-json",
        action="store_true",
        help="keep the source .json next to the emitted .md (it shadows the .md until removed)",
    )
    check_parser = sub.add_parser(
        "check",
        help="lint every page-JSON in the project (schema + structural + content)",
    )
    check_parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on warnings too (default exits 1 only on errors)",
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="emit issues as a JSON stream (for the oku skill's auto-verify step)",
    )
    check_parser.add_argument(
        "--verbose",
        action="store_true",
        help="show info-level nudges in addition to errors and warnings",
    )
    check_parser.add_argument(
        "--fix",
        action="store_true",
        help="rewrite what the check can fix mechanically (path-in-code-span → #f/ chips), then re-check",
    )
    check_parser.add_argument(
        "--errors-only",
        action="store_true",
        help="suppress warnings in the human-readable output (errors still shown; exit code unchanged)",
    )
    serve_parser = sub.add_parser(
        "serve",
        help="start local HTTP server so kit assets resolve correctly (live-reload by default)",
    )
    serve_parser.add_argument(
        "--no-watch",
        action="store_true",
        help="disable the filesystem watcher + auto-reload (serve static only)",
    )
    serve_parser.add_argument(
        "--no-search",
        action="store_true",
        help="skip background Pagefind index generation at startup",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "address to bind (default 127.0.0.1 — this machine only). "
            "Pass 0.0.0.0 to reach the preview from a phone or another "
            "machine on the same network; everything under the project "
            "root becomes readable to anyone who can route to this host."
        ),
    )

    args = parser.parse_args()
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "clean":
        return cmd_clean(args)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "migrate":
        return cmd_migrate(args)
    if args.cmd == "serve":
        return cmd_serve(args)
    if args.cmd == "spec":
        return cmd_spec(args)
    if args.cmd == "vendor":
        return cmd_vendor(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
