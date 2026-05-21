"""
html-doc · CLI for the shared HTML chrome kit.

This module is the canonical CLI implementation. Two ways to invoke:

- `uv tool install .` puts `html-doc` on PATH; subsequent `html-doc
  serve` etc. just work from anywhere.
- `bin/html-doc serve` (the PEP 723-annotated shim) runs `main()` from
  here without any install — handy for in-tree work.

Commands:
  html-doc init    — create docs/_kit symlink to the kit repo in the current project
  html-doc build   — build all HTMLs in current dir into dist/standalone/ + dist/site/
  html-doc serve   — start a local HTTP server in the project root so symlinked
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


def _kit_assets_dir() -> Path:
    """Locate the kit's asset directory.

    Two layouts are valid:

    - **Installed** (uv tool install / pip install): hatchling's
      force-include packs everything into
      ``<site-packages>/html_doc/assets/`` — chrome.{css,js},
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
        "at the repo root, or html_doc/assets/ from a wheel install."
    )


KIT_DIR = _kit_assets_dir()
KIT_FILES = ["chrome.css", "chrome.js", "chrome-boot.js", "renderer.js"]


_DEFAULT_STUB_BODY_RE = re.compile(r'<body\s*>\s*</body>', re.IGNORECASE)


def _is_default_shaped_stub(content: str) -> bool:
    """True if the stub looks like one we generated — empty <body>.

    `html-doc init` re-writes default-shaped stubs to refresh the kit
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
# Project-meta filenames excluded from the .md-as-page walk. These
# carry README / CHANGELOG / LICENSE-style content that the package
# manager / forge displays separately; pulling them into the site tree
# would surface noise (and often paths that don't render cleanly).
_PROJECT_META_MD = {
    "README.md", "CLAUDE.md", "CHANGELOG.md", "AGENTS.md",
    "LICENSE.md", "LICENCE.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
    "SECURITY.md",
}

SKIP_DIRS = {
    "dist", "_kit", "node_modules", ".git", "venv", ".venv",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".idea",
    # templates/ ships the starter pair for `html-doc init` (now under
    # src/html_doc/templates/). Walking it earlier produced stray
    # starter.{md,html} pages in every build.
    "templates",
    # _internal/ holds session / scratch docs the user explicitly keeps
    # out of the published site.
    "_internal",
}

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
    typically ``cd docs && html-doc init``. The command never creates
    or descends into a "docs" subdir; cwd IS the docs root.
    """
    root = Path.cwd()
    kit_link = root / "_kit"

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
    print("  Open index.html in your IDE, or run `html-doc serve` from the")
    print("  project root for a live-reloading dev server.")
    return 0


# ---------- build ----------
# The href/src may carry an optional ?v=<n> cache-buster — match it
# greedily so the standalone-build inliner can swap the tag whether or
# not the stub generator stamped a version on it.
LINK_TO_KIT_CSS = re.compile(r'<link\s+rel="stylesheet"\s+href="_kit/chrome\.css(?:\?[^"]*)?"\s*/?>', re.I)
SCRIPT_TO_KIT_BOOT = re.compile(r'<script\s+src="_kit/chrome-boot\.js(?:\?[^"]*)?"\s*></script>', re.I)
SCRIPT_TO_KIT_MAIN = re.compile(r'<script\s+src="_kit/chrome\.js(?:\?[^"]*)?"\s+defer\s*></script>', re.I)
SCRIPT_TO_KIT_RENDERER = re.compile(r'<script\s+src="_kit/renderer\.js(?:\?[^"]*)?"\s+defer\s*></script>', re.I)


def find_html_files(root: Path):
    """Find kit-rendered HTML files under root, skipping generated dirs.

    Files that don't reference the kit boot or renderer (scratch pages,
    foreign HTML) are skipped — processing them would overwrite real
    pages in the dist output.
    """
    out = []
    for p in root.rglob("*.html"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:2048]
        except OSError:
            continue
        if "_kit/chrome.js" not in head and "_kit/chrome-boot.js" not in head:
            continue
        out.append(p)
    return sorted(out, key=lambda x: str(x).lower())


def iter_page_stubs(root: Path):
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
    for json_path, page in find_json_pages(root):
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
# Not a full CommonMark parser — author-driven coverage. Edge cases
# left out: nested lists, footnotes, definition lists, HTML in
# markdown, reference-style links. If a real .md file hits one of
# those, the converter degrades to text-with-anchors-stripped rather
# than producing invalid kit JSON.

_MD_INLINE_RE = re.compile(
    r"(\*\*([^*]+)\*\*"          # **bold**
    r"|\*([^*]+)\*"              # *italic*
    r"|__([^_]+)__"              # __bold__
    r"|_([^_]+)_"                # _italic_
    r"|`([^`]+)`"                # `code`
    r"|\[([^\]]+)\]\(([^)\s]+)\)"  # [text](url)
    r")"
)


_MD_REL_LINK_RE = re.compile(r"^(?!\w+:|//|#|/)(.+?)\.md(#[^\s]*)?$", re.IGNORECASE)


def _md_link_href(href: str) -> str:
    """Rewrite a markdown link href so `.md` extensions point at the
    rendered `.html` page. Absolute URLs (http://, https://, mailto:),
    fragment-only refs (`#foo`), and absolute paths (`/x`) pass
    through untouched — only relative `.md` paths get retargeted. A
    trailing fragment is preserved so `[X](foo.md#section)` becomes
    `foo.html#section`."""
    if not href:
        return href
    m = _MD_REL_LINK_RE.match(href)
    if not m:
        return href
    return m.group(1) + ".html" + (m.group(2) or "")


def _md_inline(text: str) -> list:
    """Split a markdown text fragment into the kit's inline-content
    array: a sequence of plain strings and inline-block objects
    ({kind: code|em|strong|link}). Returns a flat list. Falls back to
    a single string when no inline markers are present.
    """
    if not text:
        return [""]
    parts: list = []
    pos = 0
    for m in _MD_INLINE_RE.finditer(text):
        if m.start() > pos:
            parts.append(text[pos:m.start()])
        if m.group(2) is not None:
            parts.append({"kind": "strong", "text": m.group(2)})
        elif m.group(3) is not None:
            parts.append({"kind": "em", "text": m.group(3)})
        elif m.group(4) is not None:
            parts.append({"kind": "strong", "text": m.group(4)})
        elif m.group(5) is not None:
            parts.append({"kind": "em", "text": m.group(5)})
        elif m.group(6) is not None:
            parts.append({"kind": "code", "text": m.group(6)})
        elif m.group(7) is not None:
            parts.append({"kind": "link", "text": m.group(7), "href": _md_link_href(m.group(8))})
        pos = m.end()
    if pos < len(text):
        parts.append(text[pos:])
    if len(parts) == 1 and isinstance(parts[0], str):
        return parts
    return parts


def _md_slug(text: str) -> str:
    """ATX-heading style id: lowercase, non-alnum → '-', trimmed."""
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "section"


def md_to_page(text: str, default_title: str = "Untitled") -> dict:
    """Parse markdown text into a kit page-JSON dict.

    Returns ``{"kind": "page", "title": ..., "blocks": [section, ...]}``.

    The kit's schema requires top-level blocks to be sections (or tldr
    / kpi-grid). md_to_page enforces that shape:
    - First H1 (or default_title) → page title.
    - Each H2 starts a new section with the H2 text as title + slug id.
    - Content before the first H2 lands in an implicit "intro" section.
    - Sub-headings (H3+), paragraphs, code, lists, blockquotes,
      tables, hr's all nest inside the active section's `blocks`.
    """
    lines = text.split("\n")
    i = 0
    title = default_title

    def take_paragraph(start: int) -> tuple[int, dict]:
        buf: list = []
        j = start
        while j < len(lines) and lines[j].strip() != "" and not _is_block_start(lines[j]):
            buf.append(lines[j].strip())
            j += 1
        content = _md_inline(" ".join(buf))
        return j, {"kind": "paragraph", "content": content}

    def take_code_fence(start: int) -> tuple[int, dict]:
        m = re.match(r"^```(\S*)\s*$", lines[start])
        lang = (m.group(1) if m else "").lower()
        body: list = []
        j = start + 1
        while j < len(lines) and not re.match(r"^```\s*$", lines[j]):
            body.append(lines[j])
            j += 1
        source = "\n".join(body)
        if lang == "mermaid":
            return j + 1, {"kind": "diagram", "source": source}
        block: dict = {"kind": "code", "source": source}
        if lang:
            block["language"] = lang
        return j + 1, block

    def take_list(start: int) -> tuple[int, dict]:
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[start])
        ordered = bool(m and re.match(r"\d+\.", m.group(2)))
        items: list = []
        j = start
        while j < len(lines):
            mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[j])
            if not mm or lines[j].strip() == "":
                break
            items.append(_md_inline(mm.group(3)))
            j += 1
        return j, {"kind": "list", "style": "numbered" if ordered else "bullet", "items": items}

    def take_blockquote(start: int) -> tuple[int, dict]:
        buf: list = []
        j = start
        while j < len(lines) and lines[j].startswith(">"):
            buf.append(lines[j].lstrip("> ").rstrip())
            j += 1
        content = " ".join(buf).strip()
        return j, {"kind": "callout", "type": "note", "content": _md_inline(content)}

    def take_table(start: int) -> tuple[int, dict] | tuple[int, None]:
        # GFM pipe table — first line headers, second line --- separator,
        # rest are rows. Bail out unless the second line is the sep.
        if start + 1 >= len(lines) or not re.match(r"^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?\s*$", lines[start + 1]):
            return start, None
        def cells(line: str) -> list:
            line = line.strip().strip("|")
            return [c.strip() for c in line.split("|")]
        headers = cells(lines[start])
        rows = []
        j = start + 2
        while j < len(lines) and "|" in lines[j] and lines[j].strip() != "":
            rows.append([_md_inline(c) for c in cells(lines[j])])
            j += 1
        return j, {"kind": "table", "headers": headers, "rows": rows}

    def _is_block_start(line: str) -> bool:
        s = line.strip()
        return bool(
            re.match(r"^#{1,6}\s", line)
            or re.match(r"^```", line)
            or re.match(r"^[-*]\s+", line)
            or re.match(r"^\d+\.\s+", line)
            or s.startswith(">")
            or re.match(r"^-{3,}\s*$", line)
            or s.startswith("|")
        )

    # Top-level state: each H2 opens a new section. Content before the
    # first H2 lives in an implicit "intro" section so the page always
    # validates against the schema (which requires top blocks to be
    # sections / tldr / kpi-grid).
    sections: list = []
    current_section: dict | None = None
    used_ids: set = set()

    def _unique_id(slug: str) -> str:
        if slug not in used_ids:
            used_ids.add(slug)
            return slug
        n = 2
        while f"{slug}-{n}" in used_ids:
            n += 1
        out = f"{slug}-{n}"
        used_ids.add(out)
        return out

    def open_section(slug: str, heading_text: str) -> None:
        nonlocal current_section
        section_id = _unique_id(slug)
        current_section = {
            "kind": "section",
            "id": section_id,
            "title": heading_text,
            "blocks": [],
        }
        sections.append(current_section)

    def add_block(block: dict) -> None:
        nonlocal current_section
        if current_section is None:
            open_section("intro", "Intro")
        current_section["blocks"].append(block)

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s == "":
            i += 1
            continue
        if re.match(r"^-{3,}\s*$", line):
            add_block({"kind": "hr"})
            i += 1
            continue
        if line.startswith("|"):
            j, table = take_table(i)
            if table:
                add_block(table)
                i = j
                continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if h:
            level = len(h.group(1))
            heading_text = h.group(2)
            if level == 1 and title == default_title:
                title = heading_text
                i += 1
                continue
            if level == 2:
                open_section(_md_slug(heading_text), heading_text)
                i += 1
                continue
            # H3 and deeper land as heading blocks inside the active section.
            add_block(
                {
                    "kind": "heading",
                    "level": level,
                    "id": _unique_id(_md_slug(heading_text)),
                    "title": heading_text,
                }
            )
            i += 1
            continue
        if re.match(r"^```", line):
            i, block = take_code_fence(i)
            add_block(block)
            continue
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            i, block = take_list(i)
            add_block(block)
            continue
        if s.startswith(">"):
            i, block = take_blockquote(i)
            add_block(block)
            continue
        # Default — paragraph (consumes until blank line / block start).
        i, block = take_paragraph(i)
        add_block(block)

    return {"kind": "page", "title": title, "blocks": sections}


def find_markdown_pages(root: Path) -> list[tuple[Path, dict]]:
    """Walk *.md files under root, return (md_path, synthesized_page_dict).

    Skips README.md and anything under SKIP_DIRS. Files that fail to
    convert are silently omitted (the converter is permissive — only an
    unreadable file would trigger this).
    """
    out: list[tuple[Path, dict]] = []
    for p in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        # Repo-root .md files are project meta (README, CLAUDE), not
        # docs pages. Only files under at least one subdir become pages.
        if p.parent == root:
            continue
        try:
            text = p.read_text(encoding="utf-8")
            page = md_to_page(text, default_title=p.stem)
        except (OSError, ValueError):
            continue
        out.append((p, page))
    return sorted(out, key=lambda x: str(x[0]).lower())


def _stub_for(title: str, *, inline_manifest: dict | None = None) -> str:
    """Minimal HTML stub for a page. Authored on disk by `html-doc init`
    (for the entry stub), synthesized in-memory by the dev server, and
    written to dist/ by the build.

    Everything the page needs at runtime — fonts, the body skeleton
    (page-chrome + layout + nav + main + toc), and the autoBoot call
    — is owned by the kit's CSS and JS. The stub stays small so
    authors who customise it have little to read or maintain.

    When ``inline_manifest`` is supplied, the dict is embedded as a
    ``window.__htmldocManifest`` script before the kit loads — so the
    site-tree sidebar populates even when the page is opened via a
    static file server (IDE, file://) that can't reach the dev-time
    manifest synthesis.
    """
    v = _kit_version()
    manifest_block = ""
    if inline_manifest is not None:
        manifest_json = json.dumps(inline_manifest, ensure_ascii=False, separators=(',', ':'))
        manifest_block = f'<script>window.__htmldocManifest={manifest_json};</script>\n'
    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<title>{html_escape(title)}</title>\n'
        f'{manifest_block}'
        f'<script src="_kit/chrome-boot.js?v={v}"></script>\n'
        f'<link rel="stylesheet" href="_kit/chrome.css?v={v}">\n'
        f'<script src="_kit/chrome.js?v={v}" defer></script>\n'
        f'<script src="_kit/renderer.js?v={v}" defer></script>\n'
        '</head>\n<body></body>\n</html>\n'
    )


def _init_time_manifest(root: Path) -> dict:
    """Manifest snapshot for the init-time stub.

    Drops ``generated_at`` (which would otherwise differ on every run
    and trigger a needless re-write) and trims to the fields the
    runtime sidebar actually consumes. The result is what gets
    embedded as window.__htmldocManifest in docs/index.html.
    """
    manifest = compute_manifest(root)
    manifest.pop("generated_at", None)
    return manifest




def html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_KIT_URL_RE = re.compile(r'((?:src|href)=")(_kit/)', re.I)


def _retarget_kit_urls(html: str, depth: int) -> str:
    """Rewrite ``_kit/`` URLs in a stub for a page nested ``depth``
    levels deep (depth 0 = top-level dist page).

    Pages at e.g. dist/site/examples/storage/iceberg-detail.html need
    `_kit/chrome.js` to resolve to `dist/site/_kit/chrome.js` —
    that's two levels up. This rewriter prefixes the kit URL with the
    right number of `../`.
    """
    if depth <= 0:
        return html
    prefix = "../" * depth
    return _KIT_URL_RE.sub(lambda m: m.group(1) + prefix + m.group(2), html)


def find_json_pages(root: Path):
    """Recursively find *.json files where the root object has kind == 'page'.

    ALSO converts .md files into synthesized page dicts. The returned
    path uses a .json suffix (the in-memory virtual path) so downstream
    code that does `path.with_suffix(".html")` still works.

    Returns list of (path, parsed-data) tuples sorted by path.
    """
    pages = []
    for p in root.rglob("*.json"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name in ("kit.json", "site-manifest.json", "package.json", "tsconfig.json"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and data.get("kind") == "page":
            pages.append((p, data))
    # Also walk .md files — convert each into a synthesized page dict
    # via md_to_page. The "path" returned uses .json so consumers that
    # do path.with_suffix(".html") still derive the right stub URL.
    # A small set of well-known project-meta filenames is excluded
    # wherever they appear (a top-level docs/README.md is NOT meta —
    # it's a page the user expects to see in the site tree).
    for p in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name in _PROJECT_META_MD:
            continue
        try:
            text = p.read_text(encoding="utf-8")
            page = md_to_page(text, default_title=p.stem)
        except (OSError, ValueError):
            continue
        synth_path = p.with_suffix(".json")
        # Don't shadow a real .json sibling if both exist.
        if any(real == synth_path for real, _ in pages):
            continue
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


def validate_pages(pages) -> list:
    """Validate each parsed page against the schema. Returns a list of
    (path, error_message) tuples. Empty list = clean.

    Soft-fails: if jsonschema isn't installed, returns [] without error.
    Hint printed once at module import time.
    """
    if not _HAS_JSONSCHEMA:
        return []
    schema = _load_schema()
    if not schema:
        return []
    errors = []
    for p, data in pages:
        try:
            _jsonschema.validate(data, schema)
        except _jsonschema.ValidationError as e:
            # Trim long paths; report deepest field
            field = ".".join(str(x) for x in e.absolute_path) or "(root)"
            errors.append((p, f"{field}: {e.message}"))
        except _jsonschema.SchemaError:
            # Schema itself bad — abort validation entirely
            return []
    return errors


# ---------- html-doc check (doctree linter) ----------
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
# stream for the html-doc skill's auto-verify step.
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
    "section", "paragraph", "heading", "callout", "insight", "info-tip",
    "list", "code", "annotated-code", "table", "tldr", "kpi-grid",
    "step-flow", "compare-grid", "chart", "diagram", "live-snippet",
}

_KNOWN_INLINE_KINDS = {"glossary-term", "ext-ref", "code", "em", "strong", "link"}

# Phrases that signal process / round breadcrumbs in prose — the kit
# documents current behaviour, never how it got there. Matched
# case-insensitively, word-boundary-anchored where it matters.
_FORBIDDEN_PROSE_PATTERNS = [
    re.compile(r"\bround[- ]\d+\b", re.IGNORECASE),
    re.compile(r"\bv\d+ review\b", re.IGNORECASE),
    re.compile(r"\bfixed in round\b", re.IGNORECASE),
    re.compile(r"\bsince round\b", re.IGNORECASE),
]


def _walk_blocks(blocks, path=("blocks",)):
    """Yield (path_tuple, block_dict) for every block in a JSON page,
    descending into sections, info-tip content, table groups, and so on.
    Path tuple is a sequence of (key, index) hops suitable for joining
    into a JSONPath-like locator.
    """
    if not isinstance(blocks, list):
        return
    for i, blk in enumerate(blocks):
        if not isinstance(blk, dict):
            continue
        here = path + (i,)
        yield here, blk
        # Recurse into structural containers.
        if blk.get("kind") == "section":
            yield from _walk_blocks(blk.get("blocks") or [], here + ("blocks",))
        elif blk.get("kind") == "info-tip":
            yield from _walk_blocks(blk.get("content") or [], here + ("content",))


def _walk_rich(rich):
    """Yield every inline-node dict embedded in a rich-string (either a
    plain string, or an array mixing strings with inline objects)."""
    if isinstance(rich, str):
        return
    if not isinstance(rich, list):
        return
    for item in rich:
        if isinstance(item, dict):
            yield item


def _walk_all_rich(page):
    """Yield every rich-string container's content from a parsed page.
    Used by inline-resolution checks (glossary terms, ext-refs).

    Block kinds whose `content` field is a sequence of *block dicts*
    (info-tip is the only one today) are NOT descended into here —
    `_walk_blocks` already covers them. Otherwise rich-string content
    looks like a list of strings and inline-objects (`glossary-term`,
    `ext-ref`, `code`, `em`, `strong`, `link`)."""
    BLOCK_CONTENT_KINDS = {"info-tip"}  # `content` is list-of-blocks, not rich
    for _, blk in _walk_blocks(page.get("blocks") or []):
        kind = blk.get("kind")
        if kind not in BLOCK_CONTENT_KINDS:
            if "content" in blk:
                yield from _walk_rich(blk["content"])
        if isinstance(blk.get("bullets"), list):
            for b in blk["bullets"]:
                yield from _walk_rich(b)
        if isinstance(blk.get("items"), list):
            for it in blk["items"]:
                yield from _walk_rich(it)
        # compare-grid cards
        for card in blk.get("cards") or []:
            if isinstance(card, dict):
                if "content" in card:
                    yield from _walk_rich(card["content"])
                for it in card.get("items") or []:
                    yield from _walk_rich(it)
        # step-flow steps
        for step in blk.get("steps") or []:
            if isinstance(step, dict) and "content" in step:
                yield from _walk_rich(step["content"])
        # table cells (rows + groups)
        rows = blk.get("rows") or []
        for r in rows:
            if isinstance(r, dict):
                r = r.get("cells") or []
            for cell in r:
                if isinstance(cell, dict) and "value" in cell:
                    yield from _walk_rich(cell["value"])
                else:
                    yield from _walk_rich(cell)
        for grp in blk.get("groups") or []:
            if isinstance(grp, dict):
                yield from _walk_rich(grp.get("title"))
                for r in grp.get("rows") or []:
                    if isinstance(r, dict):
                        r = r.get("cells") or []
                    for cell in r:
                        if isinstance(cell, dict) and "value" in cell:
                            yield from _walk_rich(cell["value"])
                        else:
                            yield from _walk_rich(cell)


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


def _flatten_text(rich) -> str:
    """Concatenate all plain text from a rich-string for prose
    scanning. Inline objects contribute their `text`/`name`/`term` fields
    so author-emitted code/term content gets scanned too."""
    if rich is None:
        return ""
    if isinstance(rich, str):
        return rich
    if not isinstance(rich, list):
        return ""
    parts: list[str] = []
    for it in rich:
        if isinstance(it, str):
            parts.append(it)
        elif isinstance(it, dict):
            for key in ("text", "name", "term"):
                v = it.get(key)
                if isinstance(v, str):
                    parts.append(v)
    return " ".join(parts)


def check_pages(pages: list, root: Path, kit_dir: Path | None = None) -> list[dict]:
    """Run the full lint pass and return a list of issue dicts.

    Each issue: {path: Path, severity: str, code: str, where: str, message: str}
    severity is one of 'error' | 'warning' | 'info'.
    """
    if kit_dir is None:
        kit_dir = KIT_DIR
    issues: list[dict] = []

    def add(p: Path, severity: str, code: str, where: str, message: str) -> None:
        issues.append({
            "path": p,
            "severity": severity,
            "code": code,
            "where": where,
            "message": message,
        })

    # 1. Schema validation — surfaces shape errors before anything else.
    if _HAS_JSONSCHEMA:
        for p, err in validate_pages(pages):
            add(p, "error", "schema", "(root)", err)

    # Load glossary + extref registries once.
    glossary = _load_registry(kit_dir, "glossary")
    extrefs = _load_registry(kit_dir, "extrefs")

    # 2. Stray demo pages — `<thing>-demo.{html,json}` is forbidden;
    # primitive examples live inline in primitives.json.
    for p, _data in pages:
        stem = p.stem
        if stem.endswith("-demo") and stem != "markdown-demo":
            add(p, "error", "stray-demo", "(filename)",
                f"Demo page '{p.name}' is forbidden — fold the example into docs/primitives.json instead.")

    # Per-page passes.
    for p, page in pages:
        page_blocks = page.get("blocks") or []

        # 3. Forbidden prose / process breadcrumbs — applies to every
        # rich-string in the page.
        for blk_path, blk in _walk_blocks(page_blocks):
            where_prefix = "/".join(str(x) for x in blk_path) + f":kind={blk.get('kind','?')}"
            for key in ("lead", "title", "summary", "content"):
                v = blk.get(key)
                if v is None:
                    continue
                text = _flatten_text(v) if not isinstance(v, str) else v
                for pat in _FORBIDDEN_PROSE_PATTERNS:
                    m = pat.search(text)
                    if m:
                        add(p, "warning", "process-breadcrumb",
                            where_prefix + f".{key}",
                            f"Prose contains process/history reference {m.group(0)!r}; the kit documents current behaviour only.")
                        # One issue per (block, key) is enough — overlapping
                        # patterns would otherwise pile up on the same line.
                        break

            # 4. Deprecated kinds — flag with migration pointer.
            kind = blk.get("kind")
            if kind in _DEPRECATED_KINDS:
                add(p, "error", "deprecated-kind", where_prefix,
                    f"Block kind '{kind}' is no longer supported. Migrate to: {_DEPRECATED_KINDS[kind]}.")
            elif kind and kind not in _KNOWN_BLOCK_KINDS:
                add(p, "error", "unknown-kind", where_prefix,
                    f"Unknown block kind '{kind}'. Known: {sorted(_KNOWN_BLOCK_KINDS)}.")

            # 5. Code blocks should declare a language (Prism + the language
            # pill need it).
            if kind == "code" and not blk.get("language"):
                add(p, "info", "code-no-language", where_prefix,
                    "Code block has no `language` field; Prism syntax highlighting and the language pill are skipped.")

            # 6. Chart shape sanity by type.
            if kind == "chart":
                ctype = blk.get("type")
                if ctype == "bar":
                    if not blk.get("rows"):
                        add(p, "error", "chart-bar-missing-rows", where_prefix,
                            "chart with type:bar requires a `rows` array.")
                elif ctype in ("scatter", "line", "area", "bubble", "quadrant"):
                    if not blk.get("series"):
                        add(p, "error", "chart-cartesian-missing-series", where_prefix,
                            f"chart with type:{ctype} requires a `series` array.")
                    if ctype == "quadrant" and not blk.get("quadrants"):
                        add(p, "error", "chart-quadrant-missing-quadrants", where_prefix,
                            "chart with type:quadrant requires a `quadrants` object ({x, y, labels?}).")
                elif ctype in ("stacked-bar", "grouped-bar"):
                    if not blk.get("categories"):
                        add(p, "error", "chart-multi-bar-missing-categories", where_prefix,
                            f"chart with type:{ctype} requires a `categories` array.")
                    if not blk.get("series"):
                        add(p, "error", "chart-multi-bar-missing-series", where_prefix,
                            f"chart with type:{ctype} requires a `series` array.")
                elif ctype == "donut":
                    if not blk.get("slices"):
                        add(p, "error", "chart-donut-missing-slices", where_prefix,
                            "chart with type:donut requires a `slices` array.")
                elif ctype is not None:
                    add(p, "error", "chart-unknown-type", where_prefix,
                        f"chart type '{ctype}' is not supported. Use scatter, line, area, bubble, quadrant, bar, stacked-bar, grouped-bar, or donut.")

        # 7. Duplicate section IDs within a page — anchors must be unique.
        seen_ids: dict[str, int] = {}
        for blk_path, blk in _walk_blocks(page_blocks):
            if blk.get("kind") in ("section", "heading"):
                sid = blk.get("id")
                if not sid:
                    continue
                if sid in seen_ids:
                    where = "/".join(str(x) for x in blk_path)
                    add(p, "error", "duplicate-anchor", where,
                        f"Section / heading id '{sid}' already used in this page.")
                seen_ids[sid] = seen_ids.get(sid, 0) + 1

        # 8. Glossary + ext-ref resolution — every inline reference must
        # land on an entry the kit knows about.
        for inline in _walk_all_rich(page):
            if inline.get("kind") == "glossary-term":
                term = inline.get("term") or inline.get("text")
                if term and term.lower() not in glossary:
                    add(p, "warning", "unresolved-glossary",
                        f"glossary-term:{term!r}",
                        f"Glossary term '{term}' not found in any kit/glossary/*.json registry.")
            elif inline.get("kind") == "ext-ref":
                name = inline.get("name")
                if name and name.lower() not in extrefs:
                    add(p, "warning", "unresolved-extref",
                        f"ext-ref:{name!r}",
                        f"External reference '{name}' not found in any kit/extrefs/*.json registry.")
            elif inline.get("kind") and inline.get("kind") not in _KNOWN_INLINE_KINDS:
                add(p, "warning", "unknown-inline",
                    f"inline:{inline.get('kind')!r}",
                    f"Unknown inline kind '{inline.get('kind')}'.")

        # 9. Page-level metadata sanity.
        meta = page.get("meta") or {}
        if not meta.get("summary"):
            add(p, "info", "no-summary", "meta.summary",
                "Page has no meta.summary — site-manifest tooltips + llms.txt lose the one-line description.")
        if not page.get("title"):
            add(p, "error", "no-title", "title",
                "Page has no title; the document <title> and cover <h1> will be empty.")

    return issues


def _format_issue(issue: dict, root: Path) -> str:
    """Single-line human-readable rendering of one issue."""
    try:
        rel = issue["path"].relative_to(root)
    except ValueError:
        rel = issue["path"]
    icon = {"error": "✗", "warning": "!", "info": "·"}.get(issue["severity"], "·")
    return f"  {icon} {rel}:{issue['where']} [{issue['code']}] {issue['message']}"


def cmd_check(args: argparse.Namespace) -> int:
    """`html-doc check` — comprehensive doctree lint.

    Runs schema validation plus a suite of structural / content checks
    (deprecated kinds, duplicate anchors, glossary + ext-ref resolution,
    forbidden process language, chart shape sanity, …). Fast — designed
    to be the html-doc skill's auto-verify step.

    Exit codes:
      0 — clean (no errors; warnings allowed unless --strict).
      1 — at least one error (or any warning when --strict).
    """
    root = Path.cwd()
    pages = find_json_pages(root)
    if not pages:
        print(f"✗ No page-JSON files found under {root}", file=sys.stderr)
        return 1

    issues = check_pages(pages, root)

    if args.json:
        # Emit a machine-parseable stream. Path is serialised relative
        # to root so consumers don't have to strip absolute prefixes.
        payload = []
        for it in issues:
            try:
                rel = str(it["path"].relative_to(root))
            except ValueError:
                rel = str(it["path"])
            payload.append({
                "path": rel,
                "severity": it["severity"],
                "code": it["code"],
                "where": it["where"],
                "message": it["message"],
            })
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


def compute_manifest(root: Path) -> dict:
    """Walk JSON pages under root, return the site manifest dict.

    Entries: { path, source, title, parent, order?, summary? }. Folder
    hierarchy is implicit in the path; the runtime tree-builder groups
    siblings under their common ancestor path.
    """
    pages = find_json_pages(root)
    entries = []
    for p, data in pages:
        rel = p.relative_to(root)
        nav_path = rel.with_suffix(".html").as_posix()
        parent = rel.parent.as_posix() if rel.parent != Path(".") else None
        meta = data.get("meta") or {}
        # `p` is always a .json virtual path. For .md-derived pages the
        # .json file doesn't exist on disk; the real source is the
        # sibling .md. Report whichever is real so the manifest's source
        # field matches what a reader can open in their editor.
        source_rel = rel
        if not p.exists():
            md_sibling = p.with_suffix(".md")
            if md_sibling.exists():
                source_rel = md_sibling.relative_to(root)
        entry = {
            "path": nav_path,
            "source": source_rel.as_posix(),
            "title": data.get("title") or p.stem,
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


def manifest_to_js(manifest: dict) -> str:
    """Wrap the manifest dict as a window-global assignment so chrome.js
    can load it via <script src> when fetch() is blocked (file:// CORS)
    or returns 404 (IDE built-in servers gating non-token GETs)."""
    return (
        "/* Auto-generated by html-doc. Sets window.__htmldocManifest for the\n"
        "   runtime when a fetch() of site-manifest.json is impossible (file://\n"
        "   CORS) or unauthorized (IDE built-in servers). Safe to load multiple\n"
        "   times — last definition wins. */\n"
        "window.__htmldocManifest = " + json.dumps(manifest, ensure_ascii=False) + ";\n"
    )


def build_manifest(root: Path, *, out_dir: Path | None = None) -> Path:
    """Walk root for pages, write site-manifest.json + .js to out_dir
    (defaults to root for legacy / test callsites). The build pipeline
    passes a dist path for out_dir so source dirs stay clean."""
    manifest = compute_manifest(root)
    out_dir = out_dir or root
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "site-manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "site-manifest.js").write_text(manifest_to_js(manifest), encoding="utf-8")
    return out


# ---------- LLM-friendly markdown twin per JSON page ----------
def _flatten_inline(content) -> str:
    """Walk a rich-string (string / list / dict node) into plain markdown."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_flatten_inline(c) for c in content)
    if isinstance(content, dict):
        kind = content.get("kind") or content.get("type")
        body = content.get("text") or content.get("content", "")
        body = _flatten_inline(body)
        href = content.get("href") or content.get("link", "")
        if kind in ("em", "i"):
            return "*" + body + "*"
        if kind in ("strong", "b"):
            return "**" + body + "**"
        if kind == "code":
            return "`" + body + "`"
        if kind == "link":
            return f"[{body}]({href})" if href else body
        if kind == "ext-ref":
            return f"[{body}]({href})" if href else body
        if kind == "glossary-term":
            return body
        if kind == "br":
            return "\n"
        return body
    return str(content)


def _md_block(block: dict, depth: int = 0) -> list[str]:
    """Render a JSON content block as a list of markdown lines.

    Best-effort — known kinds get semantic markdown; unknown / visually-
    rich kinds (charts, diagrams) get a parenthetical placeholder so the
    consuming LLM still sees the structure. Empty list means "skip"."""
    if not isinstance(block, dict):
        return []
    kind = block.get("kind", "")
    out: list[str] = []

    if kind == "section":
        title = _flatten_inline(block.get("title") or "")
        if title:
            out.append("## " + title)
            out.append("")
        for child in block.get("blocks", []):
            out.extend(_md_block(child, depth + 1))
            out.append("")
        return out

    if kind == "heading":
        level = max(2, int(block.get("level", 2)))
        # Schema uses `title`; some legacy authored pages emit `text` —
        # accept either so the twin stays useful across both.
        text = block.get("title") or block.get("text", "")
        out.append("#" * level + " " + _flatten_inline(text))
        return out

    if kind == "paragraph":
        out.append(_flatten_inline(block.get("content", "")))
        return out

    if kind in ("callout", "tldr", "insight", "info-tip"):
        type_label = (block.get("type") or kind).upper()
        body = _flatten_inline(block.get("content") or block.get("lead", "") or block.get("body", ""))
        title = _flatten_inline(block.get("title") or "")
        header = f"> **{type_label}: {title}**" if title else f"> **{type_label}**"
        out.append(header)
        for line in body.split("\n"):
            out.append("> " + line if line else ">")
        return out

    if kind == "list":
        items = block.get("items") or block.get("bullets") or []
        ordered = block.get("ordered") is True
        for i, item in enumerate(items, 1):
            text = _flatten_inline(
                item if not isinstance(item, dict) else (item.get("text") or item.get("content") or "")
            )
            prefix = f"{i}. " if ordered else "- "
            out.append(prefix + text)
        return out

    if kind == "code":
        lang = block.get("language") or block.get("lang") or ""
        body = block.get("source") or block.get("content") or block.get("code", "")
        out.append("```" + lang)
        out.append(body)
        out.append("```")
        return out

    if kind == "annotated-code":
        lang = block.get("language") or ""
        body = block.get("source") or ""
        out.append("```" + lang)
        out.append(body)
        out.append("```")
        annos = block.get("annotations") or []
        if annos:
            out.append("")
            for a in annos:
                if not isinstance(a, dict):
                    continue
                aid = a.get("id", "")
                # Strip inline HTML for markdown — keep the structure but
                # avoid raw <code> / <strong> tags in the .md.
                content = re.sub(r"<[^>]+>", "", a.get("content", ""))
                out.append(f"{aid}. {content}")
        return out

    if kind == "table":

        def _header_label(h):
            # Object form: { label, filter: "chips", values: [...] }.
            if isinstance(h, dict):
                return _flatten_inline(h.get("label") or "")
            return _flatten_inline(h)

        def _cell_text(c):
            # Object form: { value?, values: [...] }. Prefer explicit `value`;
            # fall back to the comma-joined chip values.
            if isinstance(c, dict) and "values" in c:
                if c.get("value") is not None:
                    return _flatten_inline(c["value"])
                return ", ".join(c.get("values") or [])
            return _flatten_inline(c)

        headers = [_header_label(h) for h in (block.get("headers") or [])]
        if headers:
            out.append("| " + " | ".join(headers) + " |")
            out.append("| " + " | ".join(["---"] * len(headers)) + " |")

        def emit_row(row):
            cells = row.get("cells") if isinstance(row, dict) else row
            md_cells = [_cell_text(c).replace("|", "\\|").replace("\n", " ") for c in (cells or [])]
            out.append("| " + " | ".join(md_cells) + " |")

        if block.get("groups"):
            for g in block["groups"]:
                title = _flatten_inline(g.get("title") or "")
                if title:
                    out.append("")
                    out.append("### " + title)
                    if headers:
                        out.append("")
                        out.append("| " + " | ".join(headers) + " |")
                        out.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for row in g.get("rows") or []:
                    emit_row(row)
        else:
            for row in block.get("rows") or []:
                emit_row(row)
        return out

    if kind == "kpi-grid":
        for item in block.get("tiles") or block.get("items") or []:
            num = item.get("num", "")
            label = _flatten_inline(item.get("label", ""))
            out.append(f"- **{num}** — {label}")
        return out

    if kind == "compare-grid":
        for card in block.get("cards") or []:
            t = _flatten_inline(card.get("title", ""))
            body = _flatten_inline(card.get("content") or "")
            if t:
                out.append("### " + t)
            if body:
                out.append(body)
            for it in card.get("items") or []:
                out.append("- " + _flatten_inline(it))
        return out

    if kind == "step-flow":
        for i, step in enumerate(block.get("steps") or [], 1):
            t = _flatten_inline(step.get("title", ""))
            body = _flatten_inline(step.get("content") or step.get("summary") or "")
            out.append(f"{i}. **{t}**")
            if body:
                for line in body.split("\n"):
                    out.append("   " + line)
        return out

    if kind == "chart":
        title = _flatten_inline(block.get("title") or "chart")
        # Bar-chart shape emits as a definition list so the markdown
        # twin still carries the label/value pairs; scatter / line are
        # rendered as a placeholder line (no useful textual form).
        if block.get("type") == "bar":
            out.append("### " + title)
            for row in block.get("rows") or []:
                label = _flatten_inline(row.get("label", ""))
                value = row.get("value", "")
                display = row.get("display")
                out.append(f"- {label}: {display if display is not None else value}")
            return out
        out.append(f"_[chart: {title}]_")
        return out

    if kind == "diagram":
        title = _flatten_inline(block.get("caption") or "diagram")
        out.append(f"_[diagram: {title}]_")
        return out

    if kind == "live-snippet":
        out.append("_[interactive snippet]_")
        return out

    # Unknown — emit a placeholder so the structure isn't lost.
    out.append(f"_[{kind or 'block'}]_")
    return out


def render_page_markdown(page_json: dict) -> str:
    """Render a JSON page as semantic markdown for the /page.md LLM twin."""
    lines: list[str] = []
    title = page_json.get("title") or ""
    if title:
        lines.append("# " + title)
        lines.append("")
    meta = page_json.get("meta") or {}
    subtitle = _flatten_inline(meta.get("subtitle") or "")
    if subtitle:
        lines.append("*" + subtitle + "*")
        lines.append("")
    bits: list[str] = []
    for key in ("date", "audience", "read_time"):
        if meta.get(key):
            bits.append(str(meta[key]))
    if meta.get("updated"):
        bits.append("Updated: " + str(meta["updated"]))
    if bits:
        lines.append("> " + " · ".join(bits))
        lines.append("")
    for block in page_json.get("blocks", []):
        lines.extend(_md_block(block))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_markdown_twins(root: Path, dest_root: Path | None = None) -> int:
    """For each JSON page under root, emit <name>.md (LLM-readable twin).

    By default writes under ``dest_root`` (defaults to ``root`` for
    backward compat). Pass ``dest_root=dist/site/`` to keep generated
    .md files out of the source dirs — the user-stated policy is
    "generated files live under a well-known path (dist/), not mixed
    with the original .json content".
    """
    n = 0
    target_root = dest_root if dest_root is not None else root
    for p, data in find_json_pages(root):
        rel = p.relative_to(root)
        out_path = target_root / rel.with_suffix(".md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_path.write_text(render_page_markdown(data), encoding="utf-8")
            n += 1
        except OSError:
            continue
    return n


def compute_llms_txt(root: Path) -> str:
    """Return the llms.txt body (llmstxt.org convention) — sitemap for
    LLM consumers. One line per page: link + summary. No body copy
    (HTML is the source of truth)."""
    pages = find_json_pages(root)
    project_name = root.name
    description = ""
    kit_json = root / "kit.json"
    if kit_json.exists():
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
        meta = data.get("meta") or {}
        entries.append(
            {
                "path": nav_path,
                "title": data.get("title") or p.stem,
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


def build_llms_txt(root: Path, *, out_dir: Path | None = None) -> Path:
    """Walk root for pages, write llms.txt to out_dir (defaults to root
    for legacy / test callsites). The build pipeline passes a dist path
    so source dirs stay clean."""
    out_dir = out_dir or root
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "llms.txt"
    out.write_text(compute_llms_txt(root), encoding="utf-8")
    return out


# ---------- Pagefind search index ----------
def pagefind_index(site_dir: Path) -> bool:
    """Run Pagefind over an HTML site directory.

    Returns True if pagefind ran successfully, False if absent or failed.
    Pagefind is treated as an optional dependency — search degrades
    gracefully if it's not installed.
    """
    if not site_dir.exists():
        return False
    if not shutil.which("pagefind"):
        # Try npx as a fallback so the binary doesn't have to be installed globally.
        if shutil.which("npx"):
            cmd = ["npx", "--yes", "pagefind", "--site", str(site_dir)]
        else:
            print("! pagefind not on PATH; skipping search index.")
            print("  Install: brew install pagefind  OR  npm i -g pagefind")
            return False
    else:
        cmd = ["pagefind", "--site", str(site_dir)]
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

    if isinstance(page_json.get("title"), str):
        parts.append(page_json["title"])
    meta = page_json.get("meta") or {}
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
        _kit/              ← chrome.{css,js}, chrome-boot.js, renderer.js,
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
    kit_out = out_dir / "_kit"
    kit_out.mkdir(exist_ok=True)

    # Runtime chrome files → _kit/
    for f in KIT_FILES:
        shutil.copy(KIT_DIR / f, kit_out / f)
    # Shared registry directories → _kit/<name>/
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
    for f in ("kit.json",):
        sp = src_root / f
        if sp.exists():
            shutil.copy(sp, out_dir / f)

    # Page sources (HTML stubs + JSON content) — preserve directory structure.
    # For nested pages, rewrite `_kit/...` URLs in the stub to climb the
    # right number of levels up to the dist's single _kit/ at out_dir/.
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
            if isinstance(page, dict) and page.get("kind") == "page":
                text = extract_page_text(page)
                title = page.get("title") or src.stem
                html = inject_pagefind_body(html, text, title)
        dest_html.write_text(html, encoding="utf-8")


def build_kit_bundle(src_root: Path) -> str | None:
    """Assemble the project's kit.json + active domain glossary/extref files
    into one JSON blob for inlining into standalone builds. Returns None
    if no kit.json is present (no glossary to inline).
    """
    kit_json_path = src_root / "kit.json"
    if not kit_json_path.exists():
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
        html = LINK_TO_KIT_CSS.sub(lambda m: f"<style>\n{css}\n</style>", html, count=1)
        html = SCRIPT_TO_KIT_BOOT.sub(lambda m: f"<script>\n{boot}\n</script>", html, count=1)
        html = SCRIPT_TO_KIT_MAIN.sub(lambda m: f"<script>\n{main}\n</script>", html, count=1)
        html = SCRIPT_TO_KIT_RENDERER.sub(lambda m: f"<script>\n{renderer}\n</script>", html, count=1)

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
            inline = f'<script type="application/json" id="__htmldoc_page__">{safe}</script>'
            # Inline the kit bundle (project kit.json + active domain
            # glossary/extref entries) so tooltips work offline.
            if kit_bundle:
                safe_bundle = kit_bundle.replace("</script", "<\\/script")
                inline += (
                    f'\n<script type="application/json" id="__htmldoc_kit_bundle__">{safe_bundle}</script>'
                )
            # Lambda replacement avoids re.sub interpreting \n in the JSON
            # content as a backslash escape and turning it into a newline.
            html = _BODY_CLOSE_RE.sub(lambda m: inline + "\n</body>", html, count=1)

        # Preserve directory structure relative to src_root.
        rel = src.relative_to(src_root)
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")


def cmd_build(args: argparse.Namespace) -> int:
    root = Path.cwd()
    srcs = iter_page_stubs(root)
    json_pages = find_json_pages(root)
    if not srcs and not json_pages:
        print(f"✗ No .html or page-JSON files found in {root}", file=sys.stderr)
        return 1

    # site-manifest.{json,js} + llms.txt are derived from the JSON pages
    # on every fetch. They land under dist/ in the build (alongside the
    # pages they describe) and are synthesized in memory by the dev
    # server — never written into source dirs. Source stays
    # authored-content-only.
    docs_dir = _common_docs_dir(root, json_pages)

    # Schema validation + structural lint — runs the same checks as
    # `html-doc check` so the build never produces a doctree that the
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
            print(f"✓ Doctree check: {len(json_pages)} page(s) clean (errors); {len(warnings)} warning(s) — run `html-doc check` for the full report.")
        else:
            print(f"✓ Doctree check: {len(json_pages)} page(s) clean")
        if not _HAS_JSONSCHEMA:
            print("  (schema validation skipped — `pip install jsonschema` to enable; structural checks still ran)")

    if not srcs:
        return 0

    dist = root / "dist"
    standalone = dist / "standalone"
    site = dist / "site"

    # Clean previous outputs to avoid stale files
    if standalone.exists():
        shutil.rmtree(standalone)
    if site.exists():
        shutil.rmtree(site)

    build_standalone(srcs, standalone, root)
    build_site(srcs, site, root)

    # Manifest + llms.txt are derived from json_pages; emit them into
    # each dist tree's docs_dir (NOT into source). chrome.js's runtime
    # fetch resolves them at the same URL it would expect from source.
    rel_docs = docs_dir.relative_to(root)
    for dist_tree in (standalone, site):
        build_manifest(docs_dir, out_dir=dist_tree / rel_docs)
        build_llms_txt(docs_dir, out_dir=dist_tree / rel_docs)
    rel_display = "" if rel_docs == Path(".") else rel_docs.as_posix() + "/"
    print(f"✓ Wrote site-manifest + llms.txt under dist/{{standalone,site}}/{rel_display} ({len(json_pages)} JSON page(s))")

    # Markdown twins land in BOTH dist trees (standalone + site) — never
    # in the source dirs. Consumers fetch them from the dist they
    # actually serve.
    md_standalone = build_markdown_twins(docs_dir, dest_root=standalone / rel_docs)
    md_site = build_markdown_twins(docs_dir, dest_root=site / rel_docs)
    if md_site:
        print(f"✓ Wrote {md_site} page.md twin(s) under dist/site/ + dist/standalone/")

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


# ---------- serve ----------
def find_project_root(start: Path) -> Path:
    """Walk up to find the directory containing docs/_kit; fallback to start."""
    cur = start.resolve()
    for ancestor in [cur, *cur.parents]:
        if (ancestor / "docs" / "_kit").exists():
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
    without needing a full ``html-doc build`` first.

    Best-effort: returns False (silently) if pagefind isn't on PATH or
    if any step fails. The user gets a notice; the rest of serve still
    works.
    """
    pages = find_json_pages(root)
    if not pages:
        return False
    has_bin = bool(shutil.which("pagefind") or shutil.which("npx"))
    if not has_bin:
        print(
            "! Search disabled — install pagefind (brew install pagefind) "
            "or pass --no-search to silence this notice."
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
    # runtime path __htmldocDocsRoot + 'pagefind/pagefind.js' resolves.
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


_WATCH_SKIP = {"dist", "_kit", ".git", "node_modules", ".venv", "venv", "__pycache__", ".idea"}
_WATCH_SKIP_SUFFIX = {".pyc", ".swp", ".tmp"}
_WATCH_SKIP_NAMES = {".DS_Store", "site-manifest.json", "llms.txt"}  # avoid feedback loop


def _snapshot_tree(root: Path) -> dict:
    """Map every file under root → mtime, skipping generated / VCS dirs.
    Excludes site-manifest.json + llms.txt to avoid the rebuild→change loop."""
    state = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = p.parts
        if any(part in _WATCH_SKIP for part in parts):
            continue
        if p.suffix in _WATCH_SKIP_SUFFIX or p.name in _WATCH_SKIP_NAMES:
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
    for the kinds of repo sizes html-doc targets (≤ a few hundred files)."""
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

        def do_GET(self) -> None:  # noqa: N802 — base API
            if self.path == "/__reload":
                self._serve_reload_stream()
                return
            # Synthesize stubs / JSON on the fly so `html-doc serve` previews
            # markdown- and json-authored sources without a build step:
            #   /<name>.html  + .md sibling  → md→page→stub
            #   /<name>.json  + .md sibling  → md→page JSON
            #   /<name>.html  + .json sibling → stub from json's title
            # Runtime expects .html (the kit-loading shell) + .json (the
            # renderer fetches this sibling). Authoring only the .json (or
            # .md) keeps source dirs free of boilerplate stubs (D5).
            if self._serve_synthesized():
                return
            super().do_GET()

        def _serve_synthesized(self) -> bool:
            """Synthesize generated artifacts in memory so source dirs
            stay clean. Returns True if the response was sent.

            Handles four shapes:
              /<name>.html  + .md sibling   → stub from md→page title
              /<name>.json  + .md sibling   → md→page JSON
              /<name>.html  + .json sibling → stub from json's title
              /<docs>/site-manifest.json / .js / llms.txt
                                            → fresh from compute_manifest
                                              / compute_llms_txt
            Real-file-on-disk always wins (returns False, letting the
            static handler serve it).
            """
            url_path = self.path.split("?", 1)[0]
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

            md_path = fs.with_suffix(".md")
            json_path = fs.with_suffix(".json")
            body: bytes | None = None
            content_type: str | None = None

            if md_path.exists():
                try:
                    text = md_path.read_text(encoding="utf-8")
                    page = md_to_page(text, default_title=md_path.stem)
                except (OSError, ValueError):
                    return False
                if url_path.endswith(".json"):
                    body = json.dumps(page, ensure_ascii=False, indent=2).encode("utf-8")
                    content_type = "application/json; charset=utf-8"
                else:
                    body = _stub_for(page.get("title") or md_path.stem).encode("utf-8")
                    content_type = "text/html; charset=utf-8"
            elif url_path.endswith(".html") and json_path.exists():
                # The .json file IS on disk; only the .html shell is missing.
                # Synthesize the stub from the json's title (D5).
                try:
                    page = json.loads(json_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    return False
                if not (isinstance(page, dict) and page.get("kind") == "page"):
                    return False
                body = _stub_for(page.get("title") or json_path.stem).encode("utf-8")
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
            """Synthesize site-manifest.{json,js} or llms.txt for any
            URL ending with one of those filenames. The docs root is
            the URL's parent directory: GET /docs/site-manifest.json
            means "manifest of pages under root/docs". Returns True if
            the request was handled."""
            artifact_name = url_path.rsplit("/", 1)[-1]
            if artifact_name not in (
                "site-manifest.json",
                "site-manifest.js",
                "llms.txt",
            ):
                return False
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
                if artifact_name == "site-manifest.json":
                    body = (
                        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
                    ).encode("utf-8")
                    content_type = "application/json; charset=utf-8"
                else:  # site-manifest.js
                    body = manifest_to_js(manifest).encode("utf-8")
                    content_type = "application/javascript; charset=utf-8"
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
    1. <user_cwd>/index.html (the user ran serve from a docs dir).
    2. First index.html anywhere under user_cwd.
    3. First HTML directly under user_cwd.
    4. First HTML in the repo, ignoring internal/scaffolding dirs.
    5. First HTML anywhere.
    """
    if not htmls:
        return None
    try:
        rel_user = user_cwd.resolve().relative_to(root.resolve())
    except ValueError:
        rel_user = Path(".")
    user_prefix = (root / rel_user).resolve()

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
    # land under dist/ via `html-doc build`.

    htmls = sorted(
        p for p in root.rglob("*.html")
        if not any(part in SKIP_DIRS for part in p.parts)
    )

    # Serve-time Pagefind index (background, best-effort) so search works
    # without requiring the user to run `html-doc build` first.
    search_enabled = not getattr(args, "no_search", False)
    if search_enabled:
        threading.Thread(
            target=_build_serve_search_index, args=(root,), name="html-doc-search", daemon=True
        ).start()

    # Filesystem watcher → SSE broadcast → in-browser reload.
    watch_enabled = not getattr(args, "no_watch", False)
    watcher_stop = threading.Event()
    watcher_thread = None
    if watch_enabled:
        watcher_thread = threading.Thread(
            target=_watcher_loop,
            args=(root, watcher_stop),
            name="html-doc-watcher",
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


# ---------- main ----------
def main() -> int:
    parser = argparse.ArgumentParser(
        prog="html-doc",
        description="Shared HTML chrome kit. Init projects, build artifacts, serve locally.",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init", help="create docs/_kit symlink in the current project")
    sub.add_parser("build", help="build dist/standalone/ + dist/site/ from current dir")
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
        help="emit issues as a JSON stream (for the html-doc skill's auto-verify step)",
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
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "serve":
        return cmd_serve(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
