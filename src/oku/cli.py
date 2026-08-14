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
import collections
import datetime
import difflib
import hashlib
import http.server
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import webbrowser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


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
    HelpFormatter, which wraps it at terminal width. `./run install`
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
    """
    h = hashlib.sha256()
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
    for f in files:
        try:
            h.update(f.name.encode())
            h.update(f.read_bytes())
        except OSError:
            return "unknown"
    return h.hexdigest()[:12]


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
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # In-place mutation is the documented way to prune os.walk.
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        for fn in filenames:
            for suf in suffixes:
                if fn.endswith(suf):
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


def _md_slug(text: str) -> str:
    """ATX-heading style id: lowercase, non-alnum → '-', trimmed."""
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "section"


def _strip_md_front_matter(text: str) -> tuple[str, dict]:
    """Pull a leading ``---\\n...\\n---\\n`` YAML block off the front of a
    markdown source and return ``(remaining_text, meta_dict)``. Parser
    is minimal — handles ``key: value`` lines only; nested mappings or
    flow style fall through as raw strings. The first ``title`` value
    (if present) is hoisted to the page title at the call site."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text, {}
    meta: dict = {}
    j = 1
    while j < len(lines) and lines[j].strip() != "---":
        line = lines[j]
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key, raw = m.group(1), m.group(2).strip()
            # Quoted string — strip the wrapping quotes.
            if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                raw = raw[1:-1]
            # Best-effort numeric / bool coercion.
            if raw.lower() in {"true", "false"}:
                meta[key] = raw.lower() == "true"
            else:
                try:
                    meta[key] = int(raw)
                except ValueError:
                    try:
                        meta[key] = float(raw)
                    except ValueError:
                        meta[key] = raw
        j += 1
    if j >= len(lines):
        # Unterminated front-matter — back off and keep the text intact.
        return text, {}
    return "\n".join(lines[j + 1 :]), meta


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
    out: str | None = None
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", p.name],
            cwd=p.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.stdout.strip()):
            out = r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = None
    _git_date_cache[key] = out
    return out


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
    s = str(v)
    # The reader strips wrapping quotes; quote only when the raw form
    # would coerce or trim differently than intended.
    if s != s.strip() or s.lower() in {"true", "false"}:
        return '"' + s + '"'
    return s


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


_MD_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s*\{#([A-Za-z][\w-]*)\})?\s*$")
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
_FOREIGN_HREF_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#g/|#x/)", re.I)
_MD_SETEXT_EQ_RE = re.compile(r"^=+\s*$")
_MD_HR_RE = re.compile(r"^-{3,}\s*$")
_MD_HTML_ISLAND_RE = re.compile(r"^</?([a-zA-Z][\w-]*)(?:[\s/>]|$)")
# Inline-level tags never open an island — mirrors INLINE_HTML_TAGS in
# renderer.js: a paragraph that starts with one of these stays prose.
_INLINE_HTML_TAGS = {
    "a",
    "abbr",
    "br",
    "code",
    "del",
    "em",
    "ins",
    "kbd",
    "mark",
    "samp",
    "span",
    "strong",
    "sub",
    "sup",
}
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _md_island_tag(line: str) -> str | None:
    """Tag name when the line opens a block-level HTML island, else None."""
    m = _MD_HTML_ISLAND_RE.match(line)
    if not m:
        return None
    tag = m.group(1).lower()
    return None if tag in _INLINE_HTML_TAGS else tag


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
    text: str, *, skip_prose: bool
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
    for lineno, line in prose:
        stripped = line.strip()
        if not stripped:
            prev_nonblank = None
            prev_blank = True
            in_island = False
            continue
        island_tag = None if in_island else _md_island_tag(line)
        if island_tag:
            issues.append(
                (
                    "info",
                    "html-island",
                    f"line {lineno}",
                    f"Raw HTML island <{island_tag}> — renders fully in the kit, stripped by external markdown viewers.",
                )
            )
            in_island = True
        if in_island:
            prev_nonblank = line
            prev_blank = False
            continue
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
            heading_ids.append((lineno, hm.group(3) or _md_slug(hm.group(2))))
        if not skip_prose:
            for pat in _FORBIDDEN_PROSE_PATTERNS:
                m = pat.search(line)
                if m:
                    issues.append(
                        (
                            "warning",
                            "process-breadcrumb",
                            f"line {lineno}",
                            f"Prose contains process/history reference {m.group(0)!r}; the kit documents current behaviour only.",
                        )
                    )
                    break
            # "Word-search for placeholders before delivering" was a step
            # in the skill's manual checklist, which is the wrong place
            # for anything a regex can do — a checklist step is skipped
            # silently and a check is not.
            ph = _PLACEHOLDER_RE.search(line)
            if ph:
                issues.append(
                    (
                        "warning",
                        "placeholder-text",
                        f"line {lineno}",
                        f"Prose still carries the placeholder {ph.group(0)!r}. "
                        "Replace it or delete the sentence before delivering.",
                    )
                )
        prev_nonblank = line
        prev_blank = False

    # Inline code spans hold convention samples (`[label](#g/term-id)`)
    # — never real references; strip before collecting.
    prose_text = _INLINE_CODE_RE.sub("", "\n".join(line for _, line in prose))
    gloss = _MD_GLOSS_REF_RE.findall(prose_text)
    x_refs = _MD_EXTREF_REF_RE.findall(prose_text)
    return issues, heading_ids, gloss, x_refs


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

        seen_ids: dict[str, int] = {}
        gloss_refs: list[tuple[str, str, int | None]] = []
        extref_refs: list[tuple[str, str, int | None]] = []
        link_refs: list[tuple[str, str, int | None]] = []
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

            if isinstance(blk, str):
                # 3. Markdown-string passes: strict-GFM subset, HTML
                # island audit, unlifted fences, process prose.
                str_issues, heading_ids, gloss, x_refs = _lint_md_string(blk, skip_prose=is_materialised)
                str_issues = str_issues + _lint_md_reference_forms(blk, fn_defs, link_defs)
                for severity, code, loc, message in str_issues:
                    m_line = re.search(r"\bline (\d+)", loc or "")
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
                scrubbed = _INLINE_CODE_RE.sub("", blk)
                for m in _MD_LINK_TARGET_RE.finditer(scrubbed):
                    link_refs.append((where, m.group(1), _abs(scrubbed[: m.start()].count("\n") + 1)))
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
                if not is_materialised:
                    for pat in _FORBIDDEN_PROSE_PATTERNS:
                        m = pat.search(s)
                        if m:
                            add(
                                p,
                                "warning",
                                "process-breadcrumb",
                                where,
                                f"Prose contains process/history reference {m.group(0)!r}; the kit documents current behaviour only.",
                            )
                            break

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

        # 9. Page-level metadata sanity. The no-summary nudge applies
        # only to hand-authored kit pages — materialised repo markdown
        # (README, CLAUDE, notes/ …) has no front-matter to carry one.
        meta = _page_meta(page)
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
            for issue in _presentation_issues(page, _tree_defaults(p)):
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


def _presentation_issues(page: dict, tree_defaults: dict) -> list[tuple[str, str, str, str]]:
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
        path_parent = rel.parent.as_posix() if rel.parent != Path(".") else None
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
        parent = meta.get("parent", path_parent)
        entry = {
            "path": nav_path,
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
    return {
        "schema_version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "root": ".",
        # What this artifact was made from, and how to make it again.
        # The manifest is the carrier because it is the one thing that
        # already reaches every page in all three modes — fetched under
        # `oku serve` and in dist/site, inlined in a standalone file.
        # `oku` + `kit` are the same two fields `oku --version` prints,
        # under the same names, so the footer and the terminal can be
        # compared without translating between them.
        "build": {"oku": _PKG_VERSION, "kit": _kit_build_stamp(), "cmd": _rebuild_command(root)},
        "pages": entries,
    }


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
    # Sort by parent (folder), then order, then title.
    entries = []
    for p, data in pages:
        rel = p.relative_to(root)
        nav_path = rel.with_suffix(".html").as_posix()
        meta = _page_meta(data)
        entries.append(
            {
                "path": nav_path,
                "title": _page_title(data) or p.stem,
                "parent": rel.parent.as_posix() if rel.parent != Path(".") else "",
                "order": meta.get("order", 1000),
                "summary": meta.get("summary", ""),
            }
        )
    entries.sort(key=lambda e: (e["parent"], e["order"], e["title"].lower()))
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

    walk(page_json.get("blocks", []))
    # Strip inline HTML that may live in glossary defs etc.
    raw = " ".join(parts)
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


def build_site(srcs, out_dir: Path, src_root: Path) -> None:
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
    # Shared registry directories → _oku/<name>/
    for d in ("glossary", "extrefs", "schema", "i18n"):
        src_dir = KIT_DIR / d
        if src_dir.exists():
            dst_dir = kit_out / d
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)

    # Project-level files that pages depend on at runtime. site-manifest
    # and llms.txt are derived; cmd_build writes them into the dist
    # tree's docs_dir directly after this call, NOT into source.
    kit_json = find_kit_json(src_root)
    if kit_json is not None:
        shutil.copy(kit_json, out_dir / "kit.json")

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
_INLINE_CODE_RE = re.compile(r"(`+)(?:.|\n)*?\1")


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
        data_text = None
        if page_data is not None:
            data_text = json.dumps(page_data, ensure_ascii=False, indent=2)
        elif json_sibling.exists():
            data_text = json_sibling.read_text(encoding="utf-8")
        if data_text:
            # Escape </script in the JSON to be safe inside an inline script.
            safe = data_text.replace("</script", "<\\/script")
            inline = f'<script type="application/json" id="__oku_page__">{safe}</script>'
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
            depth = len(src.relative_to(src_root).parent.parts)
            vendor_base = ("../" * depth) + "_oku/vendor/"
            inline += (
                f"\n<script>window.__okuVendorBase={json.dumps(vendor_base)};"
                f"window.__okuVendoredPrism={json.dumps(vendor_is_complete())};</script>"
            )
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
            html = _BODY_CLOSE_RE.sub(lambda m: inline + "\n</body>", html, count=1)

        html = LINK_TO_KIT_CSS.sub(lambda m: f"<style>\n{css}\n</style>", html, count=1)
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
        elif warnings:
            print(
                f"✓ Doctree check: {len(json_pages)} page(s) clean (errors); {len(warnings)} warning(s) — run `oku check` for the full report."
            )
        else:
            print(f"✓ Doctree check: {len(json_pages)} page(s) clean")
        if not _HAS_JSONSCHEMA:
            print(
                "  (schema validation skipped — `pip install jsonschema` to enable; structural checks still ran)"
            )

    if not srcs:
        return 0

    dist = root / "dist"
    standalone = dist / "standalone"
    site = dist / "site"
    legacy_markdown = dist / "markdown"

    # Clean previous outputs to avoid stale files (legacy_markdown is
    # gone as a build product — sources are markdown; remove leftovers
    # from older builds so the tree doesn't linger half-stale).
    for tree in (standalone, site, legacy_markdown):
        if tree.exists():
            shutil.rmtree(tree)

    # One manifest, computed once, used by both trees: the site fetches
    # it as a sidecar, the standalone pages carry it inline.
    dist_manifest = compute_manifest(root, pages=json_pages)
    build_standalone(srcs, standalone, root, manifest=dist_manifest)
    build_site(srcs, site, root)

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
    if pagefind_index(site):
        print("✓ Pagefind index built: dist/site/pagefind/")

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
def cmd_clean(args: argparse.Namespace) -> int:
    """Remove the dist/ tree under the current project root. No-op if
    dist/ doesn't exist. Source dirs and the _oku symlink are left
    alone — only generated artifacts are removed."""
    root = Path.cwd()
    dist = root / "dist"
    if not dist.exists():
        print(f"✓ Nothing to clean — {dist} does not exist.")
        return 0
    shutil.rmtree(dist)
    print(f"✓ Removed {dist}")
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
    1. First page in the site tree (manifest order: parent, meta.order,
       title) — this is what the sidebar would show as "page 1", so the
       user lands on real content instead of an empty index.
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

    # Primary: the first page in the manifest. compute_manifest already
    # sorts by (parent, meta.order, title.lower()), so manifest[0] is
    # the natural top-of-tree page — the one a user would open first if
    # browsing the sidebar.
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

    port = 9876
    httpd = None
    while True:
        try:
            httpd = http.server.ThreadingHTTPServer(("", port), handler_cls)
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

    print(f"✓ Serving {root} on http://localhost:{port}")
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
            print(f"    http://localhost:{port}/{rel}{marker}")
        if target is not None:
            webbrowser.open(f"http://localhost:{port}/{target.relative_to(root)}")
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
    return (str(v2.get("t") or ""), typed, prose)


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
_PRISM_LANGS = (
    "javascript css bash json yaml python typescript jsx tsx java go rust sql markup "
    "diff toml ini docker kotlin scala c cpp csharp php ruby swift graphql markdown mermaid"
).split()


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
        print("  ! incomplete — pages fall back to the CDN for whatever is missing", file=sys.stderr)
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
        known = sorted(set(blocks) | set(charts))
        near = difflib.get_close_matches(args.name, known, n=3, cutoff=0.5)
        print(f"! unknown name {args.name!r}", file=sys.stderr)
        if near:
            print(f"  did you mean: {', '.join(near)}", file=sys.stderr)
        else:
            print("  `oku spec` with no argument lists every name", file=sys.stderr)
        return 1

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
    pages = sorted((root / "dist" / "standalone").rglob("*.html"))
    if not pages:
        print(
            f"✗ nothing built under {root / 'dist' / 'standalone'} — run `oku build` first", file=sys.stderr
        )
        return 1

    widths = [1440, 360]
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for html in pages:
            rel = html.relative_to(root)
            errors: list[str] = []
            missing: list[str] = []
            page.on("pageerror", lambda e, s=errors: s.append(str(e)[:120]))
            # A failed request reports as a generic "Failed to load
            # resource" on the console, with no URL — useless for saying
            # WHAT is missing, so the request itself is what gets
            # recorded and the console duplicate is dropped.
            page.on(
                "console",
                lambda m, s=errors: (
                    s.append(m.text[:120])
                    if m.type == "error" and "Failed to load resource" not in m.text
                    else None
                ),
            )
            page.on("requestfailed", lambda r, s=missing: s.append(r.url))
            for width in widths:
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(html.as_uri())
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
            for url in dict.fromkeys(missing):
                # Prism's markdown grammar probes for the language of any
                # fence nested inside a markdown sample, so a page that
                # documents this kit asks for `prism-oku-chart.min.js`.
                # That set is unbounded and a missing grammar degrades to
                # unhighlighted code, which is not a build failure.
                if "/prism/components/" in url:
                    continue
                # A remote origin failing is the network's state, not the
                # page's. Judging the page on it makes this command fail
                # intermittently for reasons the author cannot fix, which
                # is how a verification step stops being believed. What
                # the page IS responsible for is its own local files —
                # `test_vendor_offline.py` is where the no-network case
                # is asserted properly.
                if url.startswith(("http://", "https://")):
                    continue
                failures.append(f"{rel}: could not load {url.rsplit('/', 1)[-1]}")
        browser.close()

    if failures:
        print(f"✗ {len(failures)} problem(s) a source check cannot see:", file=sys.stderr)
        for f in failures[:40]:
            print(f"  ✗ {f}", file=sys.stderr)
        if len(failures) > 40:
            print(f"  … {len(failures) - 40} more", file=sys.stderr)
        return 1
    print(f"✓ {len(pages)} page(s) render clean at {' and '.join(f'{w}px' for w in widths)}")
    return 0


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
        lossless = _page_content_fingerprint(back) == _page_content_fingerprint(data)
        if not lossless:
            print(
                f"  skip {rel}: markdown round-trip is not lossless — source kept. "
                f"Report this page; the JSON still renders.",
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
            f" · assets {_kit_assets_dir()}"
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
    sub.add_parser("clean", help="remove dist/ from the current project")
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
