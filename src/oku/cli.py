"""
oku · CLI for the shared HTML chrome kit.

This module is the canonical CLI implementation. Two ways to invoke:

- `uv tool install .` puts `oku` on PATH; subsequent `oku
  serve` etc. just work from anywhere.
- `bin/oku serve` (the PEP 723-annotated shim) runs `main()` from
  here without any install — handy for in-tree work.

Commands:
  oku init    — create docs/_kit symlink to the kit repo in the current project
  oku build   — build all HTMLs in current dir into
                     dist/{standalone,site,markdown}/
  oku clean   — remove dist/ from the current project
  oku serve   — start a local HTTP server in the project root so symlinked
                     kit assets load (file:// has browser-specific restrictions)

All commands take zero flags. Output paths are printed with file:// or http://
prefix for click-to-open.
"""

import argparse
import datetime
import http.server
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import unquote


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


# ---------- init ----------
def cmd_init(args: argparse.Namespace) -> int:
    """Idempotently scaffold the CURRENT directory as a docs root.

    Creates two things in cwd if missing:

    - ``_kit`` → KIT_DIR symlink (kit JS/CSS + schema/glossary/extrefs).
      If a stale symlink already points somewhere else, it is replaced;
      a non-symlink path of the same name is left alone with an error.
    - ``index.html`` — entry stub. A single on-disk stub at the docs
      root is what makes IDE-served workflows work (IntelliJ's built-in
      HTTP server, Live Server, etc.); deeper pages stay JSON-only and
      rely on the dev server's in-memory synthesis.

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
    print("  Author pages as <name>.json (or .md) next to index.html.")
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
        if p.name.endswith(".src.html"):
            continue  # HTML-first page SOURCE, not a stub
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:2048]
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
    "compare-grid",
    "insight",
    "example",
    "live-snippet",
    "annotated-code",
    "diagram",
    "tldr",
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


def md_to_v2_page(text: str, default_title: str = "Untitled") -> dict:
    """Convert a markdown (v3) page source into a v2 page dict.

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

    lines = text.split("\n")
    n = len(lines)
    blocks: list = []
    buf: list[str] = []

    def flush() -> None:
        chunk = "\n".join(buf)
        buf.clear()
        if chunk.strip():
            blocks.append(chunk.strip("\n"))

    i = 0
    plain_fence_close: re.Pattern | None = None
    while i < n:
        line = lines[i]
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


def _page_from_source_file(p: Path) -> dict | None:
    """Read + convert one page source (any registered format); None
    when unreadable or not a recognised source.

    Markdown/djot sources whose front-matter carries a `title` are
    hand-authored kit pages and get the full lint. Markdown WITHOUT a
    front-matter title (README, CHANGELOG, CLAUDE, SKILL.md and
    friends) gets the `_materialised_by` tag so the linter's prose
    rules skip author-owned repo prose. AsciiDoc / HTML sources always
    carry explicit titles — never materialised.
    """
    parser = _source_parser_for(p)
    if parser is None:
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    page = parser(text, default_title=_source_stem_path(p).name)
    if parser is md_to_v2_page:
        _, front_meta = _strip_md_front_matter(text)
        if not front_meta.get("title"):
            page.setdefault("m", {}).setdefault("_materialised_by", "oku-init")
    return page


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
    fm: list[str] = ["---", f"title: {_front_matter_value(page.get('t', ''))}"]
    for key, v in meta.items():
        if key.startswith("_") or "\n" in str(v):
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


# ---------------------------------------------------------------------------
# Alternative source formats — emit/parse pairs for the side-by-side
# comparison (docs/format-comparison-spec.md). Every format converts
# to/from the v2 page dict; lint, build, serve and the renderer only
# ever see v2. Coverage is the comparison-corpus subset: front-matter,
# ATX headings with {#id}, paragraphs with inline markdown, flat
# bullet/ordered lists, GFM tables, plain + typed fences (oku-*,
# mermaid with italic caption), GFM admonitions. Constructs outside
# the subset round-trip as verbatim text; the comparison page reports
# coverage as a datum.
# ---------------------------------------------------------------------------

_MD_LIST_ITEM_RE = re.compile(r"^([-*]|\d+\.)\s+(.*)$")
_MD_TABLE_SEP_RE = re.compile(r"^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?\s*$")
_MD_INLINE_TOKEN_RE = re.compile(
    r"\*\*([\s\S]+?)\*\*|\*([^*\s][^*]*?)\*|`([^`]+?)`|\[([^\]]+?)\]\((#[gx]/[^)\n]+?|[^)\s]+?)\)"
)


def _md_segments(text: str):
    """Yield block segments from a (subset) markdown string:
    ('heading', level, text, id|None) · ('para', text) ·
    ('list', ordered, [items]) · ('table', headers, rows) ·
    ('admonition', type, title, [body lines]) · ('fence', lang, body) ·
    ('hr',). Driving loop for the non-markdown emitters."""
    lines = text.split("\n")
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m:
            close = _fence_close_re(m.group(1))
            body = []
            i += 1
            while i < n and not close.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            yield ("fence", (m.group(2) or "").lower(), "\n".join(body))
            continue
        hm = _MD_HEADING_LINE_RE.match(line)
        if hm:
            yield ("heading", len(hm.group(1)), hm.group(2), hm.group(3))
            i += 1
            continue
        if s.startswith(">"):
            block = []
            while i < n and lines[i].lstrip().startswith(">"):
                block.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            adm = re.match(r"^\[!([A-Z]+)\](?:\s+(.+))?$", block[0] if block else "")
            if adm:
                yield ("admonition", adm.group(1), adm.group(2) or "", block[1:])
            else:
                yield ("admonition", "QUOTE", "", block)
            continue
        if _MD_HR_RE.match(line):
            yield ("hr",)
            i += 1
            continue
        if "|" in line and i + 1 < n and _MD_TABLE_SEP_RE.match(lines[i + 1]):

            def cells(row):
                row = row.strip().strip("|")
                return [c.strip() for c in row.split("|")]

            headers = cells(line)
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1
            yield ("table", headers, rows)
            continue
        lm = _MD_LIST_ITEM_RE.match(s)
        if lm and not line.startswith("    "):
            ordered = lm.group(1)[0].isdigit()
            items = []
            while i < n:
                im = _MD_LIST_ITEM_RE.match(lines[i].strip())
                if not im or not lines[i].strip():
                    break
                items.append(im.group(2))
                i += 1
            yield ("list", ordered, items)
            continue
        para = []
        while i < n and lines[i].strip() and not _is_md_block_start(lines[i]):
            para.append(lines[i].strip())
            i += 1
        if not para:
            para = [s]
            i += 1
        yield ("para", " ".join(para))


def _is_md_block_start(line: str) -> bool:
    s = line.strip()
    return bool(
        _MD_HEADING_LINE_RE.match(line)
        or _FENCE_OPEN_RE.match(line)
        or s.startswith(">")
        or _MD_LIST_ITEM_RE.match(s)
        or _MD_HR_RE.match(line)
    )


def _inline_md_convert(text: str, repl: dict) -> str:
    """Rewrite inline markdown via per-construct templates. repl keys:
    strong/em/code/link — format strings with {t} (text) / {u} (url).

    Emphasis and link bodies recurse, so `**[a](b)**` and `[**a**](b)`
    keep their inner construct instead of emitting it as literal text.
    Only `code` keeps a literal body."""

    def sub(m):
        if m.group(1) is not None:
            return repl["strong"].format(t=_inline_md_convert(m.group(1), repl))
        if m.group(2) is not None:
            return repl["em"].format(t=_inline_md_convert(m.group(2), repl))
        if m.group(3) is not None:
            return repl["code"].format(t=m.group(3))
        return repl["link"].format(t=_inline_md_convert(m.group(4), repl), u=m.group(5))

    return _MD_INLINE_TOKEN_RE.sub(sub, text)


# ---------------- HTML-first (v4) ----------------

_HTML_INLINE = {
    "strong": "<strong>{t}</strong>",
    "em": "<em>{t}</em>",
    "code": "<code>{t}</code>",
    "link": '<a href="{u}">{t}</a>',
}


def _esc_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page_to_html(page: dict) -> str:
    """Emit an HTML-first (v4) source: real HTML elements for prose,
    custom elements with JSON script children for typed blocks."""
    if page.get("kind") == "page" and "k" not in page:
        page = _v1_to_v2(page)
    meta = page.get("m") or {}
    out = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>" + _esc_html(str(page.get("t", ""))) + "</title>",
    ]
    for key, v in meta.items():
        if key.startswith("_"):
            continue
        out.append('<meta name="oku-' + key + '" content="' + _esc_html(str(v)) + '">')
    out.append("</head>")
    out.append("<body>")
    open_section = False
    for blk in page.get("b") or []:
        if isinstance(blk, dict):
            kind = blk.get("k")
            payload = {kk: v for kk, v in blk.items() if kk != "k"}
            out.append(
                "<oku-"
                + str(kind)
                + '><script type="application/json">'
                + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                + "</script></oku-"
                + str(kind)
                + ">"
            )
            continue
        for seg in _md_segments(blk):
            tag = seg[0]
            if tag == "heading":
                level, txt, hid = seg[1], seg[2], seg[3]
                hid = hid or _md_slug(txt)
                if level == 2:
                    if open_section:
                        out.append("</section>")
                    out.append('<section id="' + hid + '">')
                    open_section = True
                    out.append("<h2>" + _inline_md_convert(txt, _HTML_INLINE) + "</h2>")
                else:
                    out.append(
                        "<h"
                        + str(level)
                        + ' id="'
                        + hid
                        + '">'
                        + _inline_md_convert(txt, _HTML_INLINE)
                        + "</h"
                        + str(level)
                        + ">"
                    )
            elif tag == "para":
                out.append("<p>" + _inline_md_convert(seg[1], _HTML_INLINE) + "</p>")
            elif tag == "list":
                lt = "ol" if seg[1] else "ul"
                out.append("<" + lt + ">")
                out.extend("<li>" + _inline_md_convert(it, _HTML_INLINE) + "</li>" for it in seg[2])
                out.append("</" + lt + ">")
            elif tag == "table":
                out.append(
                    "<table><thead><tr>"
                    + "".join("<th>" + _inline_md_convert(h, _HTML_INLINE) + "</th>" for h in seg[1])
                    + "</tr></thead><tbody>"
                )
                for row in seg[2]:
                    out.append(
                        "<tr>"
                        + "".join("<td>" + _inline_md_convert(c, _HTML_INLINE) + "</td>" for c in row)
                        + "</tr>"
                    )
                out.append("</tbody></table>")
            elif tag == "admonition":
                attrs = ' type="' + seg[1].lower() + '"'
                if seg[2]:
                    attrs += ' title="' + _esc_html(seg[2]) + '"'
                out.append("<oku-callout" + attrs + ">")
                for ln in seg[3]:
                    if ln.strip().startswith("- "):
                        out.append("<li>" + _inline_md_convert(ln.strip()[2:], _HTML_INLINE) + "</li>")
                    elif ln.strip():
                        out.append("<p>" + _inline_md_convert(ln.strip(), _HTML_INLINE) + "</p>")
                out.append("</oku-callout>")
            elif tag == "fence":
                out.append(
                    '<pre><code class="language-'
                    + (seg[1] or "text")
                    + '">'
                    + _esc_html(seg[2])
                    + "</code></pre>"
                )
            elif tag == "hr":
                out.append("<hr>")
    if open_section:
        out.append("</section>")
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


def html_to_v2_page(text: str, default_title: str = "Untitled") -> dict:
    """Parse an HTML-first (v4) source back into a v2 page dict."""
    from html.parser import HTMLParser

    _INLINE_BACK = {"strong": "**{t}**", "em": "*{t}*", "code": "`{t}`"}

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.title = default_title
            self.meta: dict = {}
            self.blocks: list = []
            self.buf: list = []  # markdown lines accumulating
            self.stack: list = []  # open tag context
            self.text: list = []  # inline text run
            self.json_payload: list = []
            self.cur_typed: str | None = None
            self.cur_callout: tuple | None = None
            self.table: list | None = None
            self.row: list | None = None
            self.list_tag: str | None = None
            self.heading: tuple | None = None

        def flush_md(self):
            chunk = "\n".join(self.buf).strip("\n")
            self.buf = []
            if chunk.strip():
                self.blocks.append(chunk)

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            self.stack.append(tag)
            if tag == "meta" and str(a.get("name", "")).startswith("oku-"):
                self.meta[a["name"][4:]] = a.get("content", "")
            elif tag.startswith("oku-") and tag != "oku-callout":
                self.flush_md()
                self.cur_typed = tag[4:]
                self.json_payload = []
            elif tag == "oku-callout":
                self.cur_callout = (a.get("type", "note"), a.get("title", ""), [])
            elif tag == "section":
                self._section_id = a.get("id")
            elif tag in ("h2", "h3", "h4"):
                self.heading = (int(tag[1]), a.get("id") or getattr(self, "_section_id", None))
                self.text = []
            elif tag in ("p", "li", "th", "td", "title"):
                self.text = []
            elif tag in ("ul", "ol"):
                self.list_tag = tag
            elif tag == "table":
                self.table = []
            elif tag == "tr":
                self.row = []
            elif tag == "pre":
                self.text = []
                self._code_lang = None
            elif tag == "code" and self.stack[-2:-1] == ["pre"]:
                cls = a.get("class", "")
                m = re.search(r"language-([\w-]+)", cls)
                self._code_lang = m.group(1) if m else None
            elif tag in ("strong", "em", "a"):
                self.text.append({"strong": "**", "em": "*", "a": "["}[tag])
                if tag == "a":
                    self._href = a.get("href", "")
            elif tag == "code":
                self.text.append("`")
            elif tag == "hr":
                self.buf.append("---")
                self.buf.append("")

        def handle_endtag(self, tag):
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
            txt = "".join(self.text).strip() if self.text else ""
            if tag.startswith("oku-") and tag != "oku-callout" and self.cur_typed:
                try:
                    payload = json.loads("".join(self.json_payload) or "{}")
                except json.JSONDecodeError:
                    payload = {}
                payload.pop("k", None)
                self.blocks.append({"k": self.cur_typed, **payload})
                self.cur_typed = None
            elif tag == "oku-callout" and self.cur_callout:
                typ, title, items = self.cur_callout
                head = "> [!" + typ.upper() + "]" + (" " + title if title else "")
                body = [head] + ["> " + it for it in items]
                self.buf.append("\n".join(body))
                self.buf.append("")
                self.cur_callout = None
            elif tag == "title":
                if txt:
                    self.title = txt
                self.text = []
            elif tag in ("h2", "h3", "h4") and self.heading:
                level, hid = self.heading
                line = "#" * level + " " + txt
                if hid and hid != _md_slug(txt):
                    line += " {#" + hid + "}"
                elif hid:
                    line += " {#" + hid + "}"
                self.buf.append(line)
                self.buf.append("")
                self.heading = None
            elif tag == "p":
                target = self.cur_callout[2] if self.cur_callout else None
                if target is not None:
                    target.append(txt)
                else:
                    self.buf.append(txt)
                    self.buf.append("")
            elif tag == "li":
                if self.cur_callout:
                    self.cur_callout[2].append("- " + txt)
                else:
                    self.buf.append("- " + txt)
            elif tag in ("ul", "ol"):
                self.buf.append("")
                self.list_tag = None
            elif tag in ("th", "td") and self.row is not None:
                self.row.append(txt)
            elif tag == "tr" and self.row is not None:
                self.table.append(self.row)
                self.row = None
            elif tag == "table" and self.table is not None:
                if self.table:
                    head, rows = self.table[0], self.table[1:]
                    self.buf.append("| " + " | ".join(head) + " |")
                    self.buf.append("|" + "---|" * len(head))
                    for r in rows:
                        self.buf.append("| " + " | ".join(r) + " |")
                    self.buf.append("")
                self.table = None
            elif tag == "pre":
                lang = getattr(self, "_code_lang", None)
                self.buf.append("```" + (lang or ""))
                self.buf.append("".join(self.text).strip("\n"))
                self.buf.append("```")
                self.buf.append("")
                self.text = []
            elif tag in ("strong", "em"):
                self.text.append({"strong": "**", "em": "*"}[tag])
            elif tag == "a":
                self.text.append("](" + getattr(self, "_href", "") + ")")
            elif tag == "code" and "pre" not in self.stack:
                self.text.append("`")

        def handle_data(self, data):
            if self.cur_typed is not None:
                self.json_payload.append(data)
            elif (
                self.text is not None
                and self.stack
                and self.stack[-1]
                in ("p", "li", "th", "td", "title", "h2", "h3", "h4", "strong", "em", "a", "code", "pre")
            ):
                self.text.append(data)

    p = P()
    p.handle_starttag = p.handle_starttag  # noqa: PLW0127 — keep reference
    p.feed(text)
    p.flush_md()
    page: dict = {"k": "page", "t": p.title, "b": p.blocks}
    meta = {k: (int(v) if isinstance(v, str) and v.isdigit() else v) for k, v in p.meta.items()}
    if meta:
        page["m"] = meta
    return page


# ---------------- AsciiDoc ----------------

_ADOC_INLINE = {"strong": "*{t}*", "em": "_{t}_", "code": "`{t}`", "link": "link:{u}[{t}]"}


def page_to_adoc(page: dict) -> str:
    """Emit an AsciiDoc source (comparison subset)."""
    if page.get("kind") == "page" and "k" not in page:
        page = _v1_to_v2(page)
    meta = page.get("m") or {}
    out = ["= " + str(page.get("t", ""))]
    for key, v in meta.items():
        if not key.startswith("_"):
            out.append(":oku-" + key + ": " + str(v))
    out.append("")
    for blk in page.get("b") or []:
        if isinstance(blk, dict):
            kind = blk.get("k")
            payload = {kk: v for kk, v in blk.items() if kk != "k"}
            if kind == "diagram" and set(blk) <= {"k", "src", "caption"}:
                if blk.get("caption"):
                    out.append("." + str(blk["caption"]))
                out.append("[mermaid]")
                out.append("----")
                out.append(str(blk.get("src", "")))
                out.append("----")
            else:
                out.append("[oku-" + str(kind) + "]")
                out.append("----")
                out.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                out.append("----")
            out.append("")
            continue
        for seg in _md_segments(blk):
            tag = seg[0]
            if tag == "heading":
                hid = seg[3] or _md_slug(seg[2])
                out.append("[#" + hid + "]")
                out.append("=" * seg[1] + " " + _inline_md_convert(seg[2], _ADOC_INLINE))
            elif tag == "para":
                out.append(_inline_md_convert(seg[1], _ADOC_INLINE))
            elif tag == "list":
                marker = "." if seg[1] else "*"
                out.extend(marker + " " + _inline_md_convert(it, _ADOC_INLINE) for it in seg[2])
            elif tag == "table":
                out.append("|===")
                out.append("".join("| " + _inline_md_convert(h, _ADOC_INLINE) + " " for h in seg[1]).rstrip())
                out.append("")
                for row in seg[2]:
                    out.append(
                        "".join("| " + _inline_md_convert(c, _ADOC_INLINE) + " " for c in row).rstrip()
                    )
                out.append("|===")
            elif tag == "admonition":
                out.append("[" + seg[1] + ("," + seg[2] if seg[2] else "") + "]")
                out.append("====")
                out.extend(_inline_md_convert(ln, _ADOC_INLINE) for ln in seg[3])
                out.append("====")
            elif tag == "fence":
                out.append("[source," + (seg[1] or "text") + "]")
                out.append("----")
                out.append(seg[2])
                out.append("----")
            elif tag == "hr":
                out.append("'''")
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


_ADOC_INLINE_BACK_RE = re.compile(r"\*([^*\s][^*]*?)\*|_([^_\s][^_]*?)_|link:([^\[\s]+)\[([^\]]*)\]")


def _adoc_inline_to_md(text: str) -> str:
    def sub(m):
        # Bodies recurse — an emphasis run wrapping a link (or the other
        # way round) has to keep the inner construct.
        if m.group(1) is not None:
            return "**" + _adoc_inline_to_md(m.group(1)) + "**"
        if m.group(2) is not None:
            return "*" + _adoc_inline_to_md(m.group(2)) + "*"
        return "[" + _adoc_inline_to_md(m.group(4)) + "](" + m.group(3) + ")"

    return _ADOC_INLINE_BACK_RE.sub(sub, text)


def adoc_to_v2_page(text: str, default_title: str = "Untitled") -> dict:
    """Parse an AsciiDoc source (comparison subset) into a v2 page."""
    lines = text.split("\n")
    title = default_title
    meta: dict = {}
    blocks: list = []
    buf: list = []

    def flush():
        chunk = "\n".join(buf).strip("\n")
        del buf[:]
        if chunk.strip():
            blocks.append(chunk)

    i, n = 0, len(lines)
    pending_caption = None
    while i < n:
        line = lines[i]
        s = line.strip()
        if i == 0 and s.startswith("= "):
            title = s[2:].strip()
            i += 1
            continue
        am = re.match(r"^:oku-([\w-]+):\s*(.*)$", s)
        if am:
            v = am.group(2).strip()
            meta[am.group(1)] = int(v) if v.isdigit() else v
            i += 1
            continue
        if s.startswith(".") and not s.startswith(".."):
            cm = re.match(r"^\.(\S.*)$", s)
            if cm and i + 1 < n and lines[i + 1].strip().startswith("["):
                pending_caption = cm.group(1)
                i += 1
                continue
        bm = re.match(r"^\[([A-Za-z][\w-]*)(?:,(.*))?\]$", s)
        if bm and i + 1 < n and lines[i + 1].strip() in ("----", "===="):
            tag, arg = bm.group(1), (bm.group(2) or "").strip()
            delim = lines[i + 1].strip()
            body = []
            i += 2
            while i < n and lines[i].strip() != delim:
                body.append(lines[i])
                i += 1
            i += 1
            joined = "\n".join(body)
            if tag == "mermaid":
                blk = {"k": "diagram", "src": joined}
                if pending_caption:
                    blk["caption"] = pending_caption
                flush()
                blocks.append(blk)
            elif tag.startswith("oku-"):
                try:
                    payload = json.loads(joined)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    payload.pop("k", None)
                    flush()
                    blocks.append({"k": tag[4:], **payload})
            elif tag == "source":
                buf.append("```" + (arg or ""))
                buf.append(joined)
                buf.append("```")
                buf.append("")
            else:
                head = "> [!" + tag.upper() + "]" + (" " + arg if arg else "")
                buf.append("\n".join([head] + ["> " + _adoc_inline_to_md(b) for b in body if b.strip()]))
                buf.append("")
            pending_caption = None
            continue
        hm = re.match(r"^\[#([\w-]+)\]$", s)
        if hm and i + 1 < n and re.match(r"^={2,6}\s", lines[i + 1]):
            lm = re.match(r"^(={2,6})\s+(.*)$", lines[i + 1].strip())
            buf.append(
                "#" * len(lm.group(1)) + " " + _adoc_inline_to_md(lm.group(2)) + " {#" + hm.group(1) + "}"
            )
            buf.append("")
            i += 2
            continue
        lm = re.match(r"^(={2,6})\s+(.*)$", s)
        if lm:
            buf.append("#" * len(lm.group(1)) + " " + _adoc_inline_to_md(lm.group(2)))
            buf.append("")
            i += 1
            continue
        if s == "|===":
            rows = []
            i += 1
            while i < n and lines[i].strip() != "|===":
                if lines[i].strip():
                    rows.append([c.strip() for c in lines[i].strip().lstrip("|").split("|")])
                i += 1
            i += 1
            if rows:
                head, body_rows = rows[0], rows[1:]
                buf.append("| " + " | ".join(_adoc_inline_to_md(h) for h in head) + " |")
                buf.append("|" + "---|" * len(head))
                for r in body_rows:
                    buf.append("| " + " | ".join(_adoc_inline_to_md(c) for c in r) + " |")
                buf.append("")
            continue
        im = re.match(r"^([.*])\s+(.*)$", s)
        if im:
            marker = "1." if im.group(1) == "." else "-"
            buf.append(marker + " " + _adoc_inline_to_md(im.group(2)))
            i += 1
            if i >= n or not re.match(r"^([.*])\s+", lines[i].strip()):
                buf.append("")
            continue
        if s == "'''":
            buf.append("---")
            buf.append("")
            i += 1
            continue
        if s:
            buf.append(_adoc_inline_to_md(s))
            if i + 1 >= n or not lines[i + 1].strip():
                buf.append("")
        i += 1
    flush()
    page: dict = {"k": "page", "t": title, "b": blocks}
    if meta:
        page["m"] = meta
    return page


# ---------------- djot ----------------

_DJOT_INLINE = {"strong": "*{t}*", "em": "_{t}_", "code": "`{t}`", "link": "[{t}]({u})"}
_DJOT_INLINE_BACK_RE = re.compile(r"\*([^*\s][^*]*?)\*|_([^_\s][^_]*?)_")


def page_to_djot(page: dict) -> str:
    """Emit a djot source (comparison subset). djot keeps markdown's
    fences/tables/links; differences: `_em_` / `*strong*`, attribute
    line `{#id}` BEFORE a heading, `:::` divs for admonitions."""
    if page.get("kind") == "page" and "k" not in page:
        page = _v1_to_v2(page)
    meta = page.get("m") or {}
    out = ["---", "title: " + _front_matter_value(page.get("t", ""))]
    out.extend(key + ": " + _front_matter_value(v) for key, v in meta.items() if not key.startswith("_"))
    out.append("---")
    out.append("")
    for blk in page.get("b") or []:
        if isinstance(blk, dict):
            kind = blk.get("k")
            if kind == "diagram" and set(blk) <= {"k", "src", "caption"}:
                out.append("```mermaid")
                out.append(str(blk.get("src", "")))
                out.append("```")
                if blk.get("caption"):
                    out.append("")
                    out.append("_" + str(blk["caption"]) + "_")
            else:
                payload = {kk: v for kk, v in blk.items() if kk != "k"}
                out.append("```oku-" + str(kind))
                out.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                out.append("```")
            out.append("")
            continue
        for seg in _md_segments(blk):
            tag = seg[0]
            if tag == "heading":
                hid = seg[3] or _md_slug(seg[2])
                out.append("{#" + hid + "}")
                out.append("#" * seg[1] + " " + _inline_md_convert(seg[2], _DJOT_INLINE))
            elif tag == "para":
                out.append(_inline_md_convert(seg[1], _DJOT_INLINE))
            elif tag == "list":
                out.extend(
                    ("1. " if seg[1] else "- ") + _inline_md_convert(it, _DJOT_INLINE) for it in seg[2]
                )
            elif tag == "table":
                out.append("| " + " | ".join(_inline_md_convert(h, _DJOT_INLINE) for h in seg[1]) + " |")
                out.append("|" + "---|" * len(seg[1]))
                for row in seg[2]:
                    out.append("| " + " | ".join(_inline_md_convert(c, _DJOT_INLINE) for c in row) + " |")
            elif tag == "admonition":
                if seg[2]:
                    out.append('{title="' + seg[2] + '"}')
                out.append("::: " + seg[1].lower())
                out.extend(_inline_md_convert(ln, _DJOT_INLINE) for ln in seg[3])
                out.append(":::")
            elif tag == "fence":
                out.append("```" + (seg[1] or ""))
                out.append(seg[2])
                out.append("```")
            elif tag == "hr":
                out.append("* * *")
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def _djot_inline_to_md(text: str) -> str:
    def sub(m):
        # Bodies recurse — djot links share markdown's syntax, but a
        # nested emphasis run still has to be rewritten.
        if m.group(1) is not None:
            return "**" + _djot_inline_to_md(m.group(1)) + "**"
        return "*" + _djot_inline_to_md(m.group(2)) + "*"

    return _DJOT_INLINE_BACK_RE.sub(sub, text)


def djot_to_v2_page(text: str, default_title: str = "Untitled") -> dict:
    """Parse a djot source (comparison subset) into a v2 page."""
    text, front_meta = _strip_md_front_matter(text)
    title = str(front_meta.pop("title", "")).strip() or default_title
    lines = text.split("\n")
    blocks: list = []
    buf: list = []

    def flush():
        chunk = re.sub(r"\n{3,}", "\n\n", "\n".join(buf)).strip("\n")
        del buf[:]
        if chunk.strip():
            blocks.append(chunk)

    i, n = 0, len(lines)
    pending_attr: dict = {}
    while i < n:
        line = lines[i]
        s = line.strip()
        fm = _FENCE_OPEN_RE.match(line)
        if fm:
            lang = (fm.group(2) or "").lower()
            close = _fence_close_re(fm.group(1))
            body = []
            i += 1
            while i < n and not close.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            joined = "\n".join(body)
            if lang == "mermaid":
                blk = {"k": "diagram", "src": joined}
                j = i
                while j < n and not lines[j].strip():
                    j += 1
                cap = re.match(r"^_([^_].*)_\s*$", lines[j]) if j < n else None
                if cap and (j + 1 >= n or not lines[j + 1].strip()):
                    blk["caption"] = cap.group(1).strip()
                    i = j + 1
                flush()
                blocks.append(blk)
            elif lang.startswith("oku-"):
                try:
                    payload = json.loads(joined)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    payload.pop("k", None)
                    flush()
                    blocks.append({"k": lang[4:], **payload})
            else:
                buf.append("```" + lang)
                buf.append(joined)
                buf.append("```")
                buf.append("")
            continue
        am = re.match(r'^\{(?:#([\w-]+))?(?:\s*title="([^"]*)")?\}$', s)
        if am and (am.group(1) or am.group(2)):
            if am.group(1):
                pending_attr["id"] = am.group(1)
            if am.group(2):
                pending_attr["title"] = am.group(2)
            i += 1
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", s)
        if hm:
            hid = pending_attr.pop("id", None)
            line_md = "#" * len(hm.group(1)) + " " + _djot_inline_to_md(hm.group(2))
            if hid:
                line_md += " {#" + hid + "}"
            buf.append(line_md)
            buf.append("")
            pending_attr = {}
            i += 1
            continue
        dm = re.match(r"^:{3,}\s+([\w-]+)\s*$", s)
        if dm:
            typ = dm.group(1)
            title_attr = pending_attr.pop("title", "")
            body = []
            i += 1
            while i < n and not re.match(r"^:{3,}\s*$", lines[i].strip()):
                body.append(lines[i])
                i += 1
            i += 1
            head = "> [!" + typ.upper() + "]" + (" " + title_attr if title_attr else "")
            buf.append("\n".join([head] + ["> " + _djot_inline_to_md(b) for b in body if b.strip()]))
            buf.append("")
            pending_attr = {}
            continue
        if s == "* * *":
            buf.append("---")
            buf.append("")
            i += 1
            continue
        if s:
            buf.append(_djot_inline_to_md(line.rstrip()))
        else:
            buf.append("")
        i += 1
    flush()
    page: dict = {"k": "page", "t": title, "b": blocks}
    meta = {k: v for k, v in front_meta.items()}
    if meta:
        page["m"] = meta
    return page


# ---------------- source registry ----------------

# Extension → parser. ".src.html" is matched by name suffix (two-dot
# extension) before the plain-suffix lookup so HTML SOURCES never
# collide with the per-page HTML stubs.
_PAGE_SOURCE_PARSERS = {
    ".md": md_to_v2_page,
    ".adoc": adoc_to_v2_page,
    ".dj": djot_to_v2_page,
}
_PAGE_SOURCE_EMITTERS = {
    "md": page_to_md,
    "html": page_to_html,
    "adoc": page_to_adoc,
    "dj": page_to_djot,
}
_SOURCE_SUFFIXES = (".md", ".adoc", ".dj", ".src.html")


def _source_parser_for(p: Path):
    """Parser callable for a page-source path, or None."""
    if p.name.endswith(".src.html"):
        return html_to_v2_page
    return _PAGE_SOURCE_PARSERS.get(p.suffix)


def _source_stem_path(p: Path) -> Path:
    """The path minus its SOURCE suffix — 'foo.src.html' → 'foo'."""
    if p.name.endswith(".src.html"):
        return p.parent / p.name[: -len(".src.html")]
    return p.with_suffix("")


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
    for p in iter_repo_files(root, (".md", ".adoc", ".dj", ".html"), extra_skip=extra):
        if p.suffix == ".html" and not p.name.endswith(".src.html"):
            continue  # per-page stubs are not sources
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
    """
    manifest = compute_manifest(root)
    manifest.pop("generated_at", None)
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
    for p in iter_repo_files(root, (".md", ".adoc", ".dj", ".html"), extra_skip=extra):
        if p.suffix == ".html" and not p.name.endswith(".src.html"):
            continue  # per-page stubs are not sources
        stem = _source_stem_path(p)
        synth_path = stem.with_suffix(".json")
        # Don't shadow a real .json sibling. When several source
        # formats coexist for one stem the first encountered wins —
        # the format-comparison corpus keeps each format in its own
        # directory, so this only guards against accidents.
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
    errors: list[tuple[Path, str]] = []
    for p, data in pages:
        # v1 pages still on disk validate against the v2 schema by
        # converting in-memory first. Migration to disk via `oku migrate`
        # is optional — this keeps `oku check` accurate for either shape.
        v2 = _v1_to_v2(data) if isinstance(data, dict) and data.get("k") != "page" else data
        for err in validator.iter_errors(v2):
            field = ".".join(str(x) for x in err.absolute_path) or "(root)"
            errors.append((p, f"{field}: {err.message}"))
            # Match the single-error-per-page behaviour the old
            # `validate()` wrapper had — it raised on the first failure
            # and never reported the rest. Keeps the report focused.
            break
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
    "step-flow",
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
            issues.append(
                (
                    "error",
                    "fence-not-lifted",
                    f"line {lineno}",
                    f"```{lang} fence did not lift to a typed block — the body must be a single JSON object and the kind one of {sorted(_FENCE_KINDS)}.",
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
        bad("chart-unknown-type", f"chart type '{ctype}' is not supported. Known: {', '.join(known)}.")
        return out
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

    def add(p: Path, severity: str, code: str, where: str, message: str) -> None:
        issues.append(
            {
                "path": p,
                "severity": severity,
                "code": code,
                "where": where,
                "message": message,
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
        gloss_refs: list[tuple[str, str]] = []
        extref_refs: list[tuple[str, str]] = []
        # Footnote / link-reference definitions resolve page-wide, so they
        # are collected before any string is linted.
        fn_defs, link_defs = _md_reference_definitions([b for b in body if isinstance(b, str)])

        for idx, blk in enumerate(body):
            where = f"b[{idx}]"
            if isinstance(blk, str):
                # 3. Markdown-string passes: strict-GFM subset, HTML
                # island audit, unlifted fences, process prose.
                str_issues, heading_ids, gloss, x_refs = _lint_md_string(blk, skip_prose=is_materialised)
                str_issues = str_issues + _lint_md_reference_forms(blk, fn_defs, link_defs)
                for severity, code, loc, message in str_issues:
                    add(p, severity, code, f"{where} {loc}", message)
                for lineno, hid in heading_ids:
                    if hid in seen_ids:
                        add(
                            p,
                            "error",
                            "duplicate-anchor",
                            f"{where} line {lineno}",
                            f"Section / heading id '{hid}' already used in this page.",
                        )
                    seen_ids[hid] = seen_ids.get(hid, 0) + 1
                gloss_refs.extend((where, t) for t in gloss)
                extref_refs.extend((where, x) for x in x_refs)
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
                    f"Unknown block kind '{kind}'. Known: {sorted(_KNOWN_BLOCK_KINDS)}.",
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

            # Prose nested inside typed payloads (step bodies, card
            # bodies, table cells, …) is markdown too — same glossary /
            # ext-ref resolution and process-prose rules.
            for s in _iter_block_strings(blk):
                s_refs = _INLINE_CODE_RE.sub("", s)
                gloss_refs.extend((where, t) for t in _MD_GLOSS_REF_RE.findall(s_refs))
                extref_refs.extend((where, x) for x in _MD_EXTREF_REF_RE.findall(s_refs))
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

        # 8. Glossary + ext-ref resolution — every inline reference
        # must land on an entry the kit knows about.
        for where, term in gloss_refs:
            if term.lower() not in glossary:
                add(
                    p,
                    "warning",
                    "unresolved-glossary",
                    f"{where} #g/{term}",
                    f"Glossary term '{term}' not found in any kit/glossary/*.json registry.",
                )
        for where, name in extref_refs:
            if name.lower() not in extrefs:
                add(
                    p,
                    "warning",
                    "unresolved-extref",
                    f"{where} #x/{name}",
                    f"External reference '{name}' not found in any kit/extrefs/*.json registry.",
                )

        # 9. Page-level metadata sanity. The no-summary nudge applies
        # only to hand-authored kit pages — materialised repo markdown
        # (README, CLAUDE, notes/ …) has no front-matter to carry one.
        meta = _page_meta(page)
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

    return issues


def _format_issue(issue: dict, root: Path) -> str:
    """Single-line human-readable rendering of one issue."""
    try:
        rel = issue["path"].relative_to(root)
    except ValueError:
        rel = issue["path"]
    icon = {"error": "✗", "warning": "!", "info": "·"}.get(issue["severity"], "·")
    return f"  {icon} {rel}:{issue['where']} [{issue['code']}] {issue['message']}"


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

    # Shadowed sources — a real .json page next to a .md/.adoc/.dj/
    # .src.html source silently WINS in discovery and serving, so the
    # rendered page stops following the source the author edits. This
    # exact failure (a stale global `oku init` materialising v1 .json
    # shadows over every docs/*.md) once broke a whole review pass —
    # it must never again be silent.
    for p, _data in pages:
        if p.suffix != ".json" or not p.exists():
            continue
        stem = p.with_suffix("")
        for sib in (
            stem.with_suffix(".md"),
            stem.with_suffix(".adoc"),
            stem.with_suffix(".dj"),
            stem.parent / (stem.name + ".src.html"),
        ):
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
            payload.append(
                {
                    "path": rel,
                    "severity": it["severity"],
                    "code": it["code"],
                    "where": it["where"],
                    "message": it["message"],
                }
            )
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
            stem = p.with_suffix("")
            for sib in (
                stem.with_suffix(".md"),
                stem.with_suffix(".adoc"),
                stem.with_suffix(".dj"),
                stem.parent / (stem.name + ".src.html"),
            ):
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
    return {
        "schema_version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "root": ".",
        "pages": entries,
    }


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
    for d in ("glossary", "extrefs", "schema"):
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
        dest_html.write_text(html, encoding="utf-8")


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


def build_standalone(srcs, out_dir: Path, src_root: Path) -> None:
    """Inline kit CSS/JS + the page's JSON content into each HTML.

    Produces single self-contained files that render offline, with no
    network fetches beyond Google Fonts (and Mermaid if a <diagram>
    block is present). autoBoot picks up the inline JSON automatically.

    Output preserves the source's directory structure under out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

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
            # Inline the kit bundle (project kit.json + active domain
            # glossary/extref entries) so tooltips work offline.
            if kit_bundle:
                safe_bundle = kit_bundle.replace("</script", "<\\/script")
                inline += f'\n<script type="application/json" id="__oku_kit_bundle__">{safe_bundle}</script>'
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

    build_standalone(srcs, standalone, root)
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
    dist/ doesn't exist. Source dirs and the _kit symlink are left
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
    """Walk up to find the directory containing docs/_kit; fallback to start."""
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
    ".adoc",
    ".dj",
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

            stem = fs.with_suffix("")
            source_path = None
            for cand in (
                stem.with_suffix(".md"),
                stem.with_suffix(".adoc"),
                stem.with_suffix(".dj"),
                stem.parent / (stem.name + ".src.html"),
            ):
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
                    body = _synth_stub(_page_title(page) or stem.name)
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
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init", help="create docs/_kit symlink in the current project")
    sub.add_parser("build", help="build dist/{standalone,site,markdown}/ from current dir")
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
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
