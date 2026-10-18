"""`oku pack` — chosen pages, and everything they reach, as one directory.

`oku build` publishes a whole tree, and a page shared alone out of that
tree takes the rest of it along: the site manifest, llms.txt and the
search index name every page beside it, a carried markdown file can hold
an absolute path from the author's machine, and a PDF that a `#f/` chip
names is never carried at all. A pack is the other shape. The pages the
author names, every page their prose links reach, every file any of them
references carried as a real file, all under one root, and the result
checked for anything that would leave the machine with it before a byte
is placed at `--out`.

The package is a `dist/site` tree in miniature — the same kit, the same
stubs, the same page JSON — so it renders the way a site does, from any
path prefix, with no CDN. Two things are left out on purpose. Pagefind:
its worker and wasm need a looser CSP than a host should have to grant a
document, and a host searches `_pack.json`, which carries every page's
plain text. And the rebuild command, which names a directory on the
author's machine.

A host that serves many packages can keep ONE copy of the kit instead of
one per package: `oku kit export` writes exactly the files a page loads
from it, in layers named for their content (`core-<hex>`, `fonts-<hex>`,
`mermaid-<hex>`, `prism-<hex>`), the same bytes on every run; `oku pack
--kit <export> --kit-url /k/` then writes no `_oku/` and points every kit
reference at those layers under that address.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from oku import cli

PACK_FORMAT = 1
EXIT_FINDINGS = 1
EXIT_USAGE = 2
INDEX_NAME = "_pack.json"


class PackUsageError(Exception):
    """The command line names something a pack cannot be made from."""


@dataclass
class Finding:
    """One reason the package may not leave the machine, or one note.

    `source` is the file the author edits to fix it — the markdown that
    carried the text — and `outputs` the package files it reached.
    """

    severity: str  # "error" | "info"
    kind: str
    detail: str
    source: Path | None = None
    line: int | None = None
    outputs: set[str] = field(default_factory=set)


@dataclass
class PackPage:
    src: Path  # the resolved .md
    page: dict
    rel: PurePosixPath = PurePosixPath()  # the page's HTML, relative to the package root

    @property
    def json_rel(self) -> PurePosixPath:
        return self.rel.with_suffix(".json")

    @property
    def md_rel(self) -> PurePosixPath:
        return self.rel.with_suffix(".md")


@dataclass
class Plan:
    pages: list[PackPage]  # the first entry page first, then in the order links reached them
    files: set[Path]  # resolved files carried as themselves
    root: Path


# ------------------------------------------------------------------ #
# What a page references.
#
# Two kinds, because the renderer treats them differently: a markdown
# link or a payload `href` to `x.md` is rewritten to `x.html` (renderLink),
# so it names a PAGE; an HTML island attribute reaches the DOM exactly as
# written, so `<a href="x.md">` names the FILE and opens the viewer.
# ------------------------------------------------------------------ #

_ISLAND_REF_RE = re.compile(r"""\b(?:href|src|poster|data)\s*=\s*["']([^"'\s]+)["']""", re.I)
_NOT_LOCAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.I)
_PAGE_SUFFIXES = (".md", ".html")


def _local_refs(page: dict) -> list[tuple[str, str]]:
    """Every local reference in a page's body as `(href, how)`.

    `how` is "link" for the spellings renderLink rewrites (`.md` becomes
    `.html`) and "raw" for the ones that reach the DOM as written. Code
    is a quotation of a reference rather than one, so it is skipped, the
    way the build skips it.
    """
    refs: list[tuple[str, str]] = []
    for blk in page.get("b") or []:
        for s in cli._iter_block_strings(blk):
            text = cli._strip_code(s)
            refs += [(h, "link") for h in cli._MD_LINK_TARGET_RE.findall(text)]
            refs += [(h, "raw") for h in _ISLAND_REF_RE.findall(text)]
            for m in cli._HTML_SRCSET_RE.finditer(text):
                refs += [(c.split()[0], "raw") for c in m.group(1).split(",") if c.split()]
        if isinstance(blk, dict):
            refs += [(h, "link") for h in cli._iter_block_hrefs(blk)]
            if blk.get("k") == "image" and isinstance(blk.get("src"), str):
                refs.append((blk["src"], "raw"))
    out: list[tuple[str, str]] = []
    for href, how in refs:
        href = href.strip()
        if href and not _NOT_LOCAL_RE.match(href) and (href, how) not in out:
            out.append((href, how))
    return out


def _ref_path(href: str) -> str:
    """The file part of an href: no query, no fragment, percent-decoded."""
    return unquote(re.split(r"[?#]", href, maxsplit=1)[0])


def _page_target(href: str, how: str, src: Path) -> Path | None:
    """The `.md` page a link names, or None when it names no page."""
    if how != "link" or href.startswith("/"):
        return None
    target = (src.parent / _ref_path(href)).resolve()
    if target.suffix.lower() not in _PAGE_SUFFIXES:
        return None
    md = target if target.suffix.lower() == ".md" else target.with_suffix(".md")
    return md if md.is_file() else None


def _chip_targets(page: dict, src: Path) -> list[Path]:
    """The files the page's `#f/` chips carry, its own and its files' files."""
    meta = page.get("m") or {}
    root = cli.project_root_for(src.parent)
    out = []
    for key in ("_files", "_files_more"):
        for ref in (meta.get(key) or {}).values():
            if ref.get("status") in ("ok", "over-cap") and ref.get("rel"):
                out.append((root / ref["rel"]).resolve())
    return out


def plan_pack(entries: list[Path]) -> Plan:
    """The pages and files a pack holds, and the root they sit under.

    Pages are followed through links without a fence: the author linked
    them, and the contract is the closure of those links. Files answer to
    the same project fence `oku build` applies (`asset_within_project`),
    because carrying a file publishes its bytes; one past the fence stays
    behind, and the check reports the reference that names it.
    """
    pages: dict[Path, dict] = {}
    files: set[Path] = set()
    queue = list(entries)
    while queue:
        src = queue.pop(0)
        if src in pages:
            continue
        page = cli._page_from_source_file(src)
        if page is None:
            continue  # unreadable; the link to it is reported as dangling
        pages[src] = page
        for href, how in _local_refs(page):
            linked = _page_target(href, how, src)
            if linked is not None:
                queue.append(linked)
                continue
            if href.startswith("/"):
                continue
            target = (src.parent / _ref_path(href)).resolve()
            if target.is_file() and cli.asset_within_project(target, src):
                files.add(target)
        files.update(_chip_targets(page, src))
    if not pages:
        return Plan([], set(), Path.cwd())
    dirs = [str(p.parent) for p in pages] + [str(f.parent) for f in files]
    root = Path(os.path.commonpath(dirs))
    plan = Plan([PackPage(src, page) for src, page in pages.items()], files, root)
    for pp in plan.pages:
        pp.rel = PurePosixPath(cli._synth_json_path(pp.src).with_suffix(".html").relative_to(root).as_posix())
    return plan


# ------------------------------------------------------------------ #
# Writing the tree.
# ------------------------------------------------------------------ #


def _relative_url(from_dir: PurePosixPath, to: PurePosixPath) -> str:
    return cli._url_path(PurePosixPath(os.path.relpath(to.as_posix(), from_dir.as_posix() or ".")).as_posix())


def _localize_files(pp: PackPage, root: Path) -> None:
    """Point every carried chip at its file in the package.

    In a build a PDF is named and never carried, and an image rides as a
    data: URI. In a package each is a real file beside the page, so the
    payload gets the URL that reaches it from the page — which also
    makes a PDF chip openable (chrome.js opens it in a tab of its own).
    `resolved` goes: it is an absolute path on this machine.
    """
    meta = pp.page.get("m") or {}
    proj = cli.project_root_for(pp.src.parent)
    for key in ("_files", "_files_more"):
        for ref in (meta.get(key) or {}).values():
            ref.pop("resolved", None)
            if ref.get("status") not in ("ok", "over-cap") or not ref.get("rel"):
                continue
            target = (proj / ref["rel"]).resolve()
            ref["url"] = _relative_url(pp.rel.parent, PurePosixPath(target.relative_to(root).as_posix()))


def _text_sources(pp: PackPage) -> list[Path]:
    """The carried files whose text rides inside this page's JSON."""
    meta = pp.page.get("m") or {}
    proj = cli.project_root_for(pp.src.parent)
    out = []
    for key in ("_files", "_files_more"):
        for ref in (meta.get(key) or {}).values():
            if ref.get("text") is not None and ref.get("rel"):
                out.append((proj / ref["rel"]).resolve())
    return out


@dataclass(frozen=True)
class SharedKit:
    """An exported kit the package loads instead of carrying `_oku/`: the
    address it is served under, its layers by name (`core` →
    `core-<hex>`), and every file in it as `<layer>/<path>`."""

    url: str
    layers: dict[str, str]
    files: frozenset[str]


def _stub(pp: PackPage, kit: SharedKit | None) -> str:
    lang = cli._lang_of_page(pp.page)
    html = cli._stub_for(cli._page_title(pp.page) or pp.src.stem, lang=lang)
    depth = len(pp.rel.parts) - 1
    html = cli._retarget_kit_urls(html, depth) if kit is None else _at_shared_kit(html, kit, depth)
    return cli._with_html_lang(cli._mark_built(html), lang)


_STUB_KIT_TAG_RE = re.compile(r'((?:src|href)=")_oku/([^"?]+)(?:\?[^"]*)?"', re.I)


def _at_shared_kit(html: str, kit: SharedKit, depth: int) -> str:
    """Point a stub's kit tags at the core layer, and name every root.

    chrome.js finds the docs root by the `_oku/` in its own tags, the kit
    as `_oku/` under that root, and the vendored files under the kit.
    None of that holds once the tags name `/k/core-<hex>/`: the root falls
    back to the page's own directory (wrong for every page in a subfolder)
    and every lazy load — mermaid, Prism, i18n, the registries — went to
    an `_oku/` the package does not have. So the stub says each: the root
    relative to the page, so the package still works under any prefix;
    the core; and one base per vendor layer, which `__okuVendorPath(part)`
    reads. The fonts need none: the core's chrome.css names them.

    No `?v=` on the tags: the layer's name is its content, and a stamp
    that differs between two machines would make the same file two
    addresses, and every reader download it twice.
    """
    core = f"{kit.url}{kit.layers['core']}/"
    html = _STUB_KIT_TAG_RE.sub(lambda m: f'{m.group(1)}{core}{m.group(2)}"', html)
    root = "../" * depth or "./"
    metas = [f'<meta name="oku-docs-root" content="{root}">', f'<meta name="oku-kit-base" content="{core}">']
    metas += [
        f'<meta name="oku-vendor-{name}" content="{kit.url}{d}/">'
        for name, d in kit.layers.items()
        if name != "core"
    ]
    m = cli._HEAD_OPEN_RE.search(html)
    return html[: m.end()] + "\n" + "\n".join(metas) + "\n" + html[m.end() :]


def _manifest(plan: Plan, title: str, summary: str) -> dict:
    """The site manifest of the packed pages and nothing else.

    No `cmd`: it names the author's directory. No `home` unless it is a
    packed page: the source tree's front door is not in the package.
    """
    m = cli.compute_manifest(plan.root, pages=[(cli._synth_json_path(pp.src), pp.page) for pp in plan.pages])
    m.get("build", {}).pop("cmd", None)
    m["name"] = title
    if summary:
        m["description"] = summary
    else:
        m.pop("description", None)
    if m.get("home") not in {e["path"] for e in m["pages"]}:
        m.pop("home", None)
    return m


def _kit_config(plan: Plan, title: str, summary: str) -> dict:
    """The kit.json the package's pages fetch: the tree's own, titled as
    the package, with the rebuild command off."""
    data: dict = {}
    found = cli.find_kit_json(plan.root)
    if found is not None:
        try:
            loaded = json.loads(found.read_text(encoding="utf-8"))
            data = loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            data = {}
    data["name"] = title
    data.pop("description", None)
    if summary:
        data["description"] = summary
    data["rebuild_command"] = False
    return data


def _door(entry: PackPage, title: str) -> str:
    """`index.html`: a plain forward to the entry page, no script.

    A copy of the entry would need its own page JSON and would be a
    second page at a second URL; `<base>` would need a CSP `base-uri`.
    A refresh with a link under it works under any prefix and any CSP.
    """
    url = html_lib.escape(_relative_url(PurePosixPath(""), entry.rel), quote=True)
    t = html_lib.escape(title)
    lang = html_lib.escape(cli._lang_of_page(entry.page))
    return (
        f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<meta http-equiv="refresh" content="0; url={url}">\n<title>{t}</title>\n'
        f'</head>\n<body><p><a href="{url}">{t}</a></p></body>\n</html>\n'
    )


_DERIVED_NAMES = frozenset({"index.html", "site-manifest.json", "llms.txt", "kit.json", INDEX_NAME})


def _write(staging: Path, rel: str | PurePosixPath, data: str | bytes) -> None:
    dest = staging / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        dest.write_bytes(data)
    else:
        dest.write_text(data, encoding="utf-8")


def _write_tree(
    plan: Plan, staging: Path, kit: SharedKit | None = None
) -> tuple[dict[str, list[Path]], list[Finding]]:
    """Write the package into `staging`; return each file's sources.

    The sources are what a finding is reported against: the markdown the
    author edits, not the JSON the build derived from it. With `kit` the
    kit is not written: the host serves one copy at its address.
    """
    entry = plan.pages[0]
    title, summary = _entry_title(entry)
    if kit is None:
        cli.copy_site_kit(staging)
    origins: dict[str, list[Path]] = {}
    findings: list[Finding] = []
    srcs = [pp.src for pp in plan.pages]
    for pp in plan.pages:
        _localize_files(pp, plan.root)
        texts = _text_sources(pp)
        _write(staging, pp.rel, _stub(pp, kit))
        _write(staging, pp.json_rel, json.dumps(pp.page, ensure_ascii=False, indent=2))
        _write(staging, pp.md_rel, pp.src.read_bytes())
        for rel in (pp.rel, pp.json_rel, pp.md_rel):
            origins[rel.as_posix()] = [pp.src, *texts]
    for target in sorted(plan.files):
        rel = target.relative_to(plan.root).as_posix()
        # The package's own files sit at fixed names at its root; a carried
        # file there would be overwritten by them, or would replace them.
        taken = rel in _DERIVED_NAMES or (kit is None and rel.startswith("_oku/"))
        if taken or (rel in origins and origins[rel][0] != target):
            findings.append(
                Finding(
                    "error",
                    "path-collision",
                    f"{rel} is carried, and the package writes its own file there",
                    target,
                )
            )
            continue
        _write(staging, rel, target.read_bytes())
        origins[rel] = [target]
    pages = [(cli._synth_json_path(pp.src), pp.page) for pp in plan.pages]
    derived = {
        "site-manifest.json": json.dumps(_manifest(plan, title, summary), indent=2, ensure_ascii=False)
        + "\n",
        "llms.txt": cli.compute_llms_txt(plan.root, pages=pages, name=title, description=summary),
        "kit.json": json.dumps(_kit_config(plan, title, summary), indent=2, ensure_ascii=False) + "\n",
    }
    if "index.html" not in origins:
        derived["index.html"] = _door(entry, title)
    elif entry.rel.as_posix() != "index.html":
        findings.append(
            Finding("info", "door", "index.html is a packed page, so it opens that page, not the entry")
        )
    for rel, text in derived.items():
        _write(staging, rel, text)
        origins[rel] = srcs
    index = pack_index(staging, plan, kit)
    _write(staging, INDEX_NAME, json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    origins[INDEX_NAME] = srcs
    return origins, findings


def _entry_title(entry: PackPage) -> tuple[str, str]:
    summary = (entry.page.get("m") or {}).get("summary")
    return cli._page_title(entry.page) or entry.src.stem, summary if isinstance(summary, str) else ""


# ------------------------------------------------------------------ #
# _pack.json — what a host needs without opening a page.
# ------------------------------------------------------------------ #

_MIME = {
    ".html": "text/html",
    ".json": "application/json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".py": "text/x-python",
    ".csv": "text/csv",
    ".xml": "application/xml",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".toml": "application/toml",
}


def _mime(path: Path) -> str:
    """A fixed table first: `mimetypes` reads the host's own tables, so
    the same package would describe itself differently on two machines."""
    import mimetypes

    return _MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def pack_index(staging: Path, plan: Plan, kit: SharedKit | None = None) -> dict:
    """`_pack.json`. Paths are package-relative POSIX paths, as on disk;
    a host quotes each segment to make a URL. `files` lists every file in
    the package but this one. `kit` is there only when the pages load the
    kit from a shared address, which the host must then serve."""
    entry = plan.pages[0]
    title, summary = _entry_title(entry)
    pages = []
    for pp in plan.pages:
        meta = pp.page.get("m") or {}
        pages.append(
            {
                "path": pp.rel.as_posix(),
                "title": cli._page_title(pp.page) or pp.src.stem,
                "summary": meta.get("summary") if isinstance(meta.get("summary"), str) else "",
                "lang": cli._lang_of_page(pp.page),
                "text": page_plain_text(pp.page),
            }
        )
    files = []
    for f in sorted(
        p for p in staging.rglob("*") if p.is_file() and p.relative_to(staging).as_posix() != INDEX_NAME
    ):
        data = f.read_bytes()
        files.append(
            {
                "path": f.relative_to(staging).as_posix(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "type": _mime(f),
            }
        )
    index = {
        "pack": PACK_FORMAT,
        "entry": entry.rel.as_posix(),
        "title": title,
        "summary": summary,
    }
    if kit is not None:
        index["kit"] = {"url": kit.url, "layers": sorted(kit.layers.values())}
    return {**index, "pages": pages, "files": files}


# Plain text: what a search index needs and nothing it would have to strip.
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_QUOTE_RE = re.compile(r"^\s*(?:>\s?)+")
_ADMONITION_RE = re.compile(r"^\[![A-Za-z]+\][+-]?\s*")
_RULE_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$|^\s*([-*_])(?:\s*\1){2,}\s*$")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*(?:\{#[^}]*\})?\s*#*\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s+(?:\[[ xX]\]\s+)?|^\s*:\s+")
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
_CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1", re.S)
_INLINE_SUBS = (
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\[[^\]]*\]"), r"\1"),
    (re.compile(r"\[\^[^\]]+\]"), ""),
    (re.compile(r"<((?:https?|mailto):[^>\s]+)>"), r"\1"),
    (re.compile(r"<[^>]+>"), " "),
    (re.compile(r"\{#[^}]*\}"), ""),
    (re.compile(r"\*\*|__|~~"), ""),
    (re.compile(r"(?<![\w*])\*(?=\S)|(?<=\S)\*(?![\w*])"), ""),
    (re.compile(r"(?<!\w)_(?=\S)|(?<=\S)_(?!\w)"), ""),
    (re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])"), r"\1"),
)


def _inline_plain(s: str) -> str:
    """One line of markdown as the words a reader sees. Code spans keep
    their characters; everything else loses its markup."""
    out = []
    pos = 0
    for m in _CODE_SPAN_RE.finditer(s):
        out.append(_strip_inline(s[pos : m.start()]))
        out.append(m.group(2).strip())
        pos = m.end()
    out.append(_strip_inline(s[pos:]))
    return re.sub(r"\s+", " ", html_lib.unescape("".join(out))).strip()


def _strip_inline(s: str) -> str:
    for pattern, repl in _INLINE_SUBS:
        s = pattern.sub(repl, s)
    return s


def _markdown_lines(md: str) -> list[str]:
    """Headings, paragraphs, list items and table cells of one markdown
    chunk; fenced code and island scripts are not text a reader reads."""
    prose, _fences = cli._split_md_fences(_SCRIPT_STYLE_RE.sub(" ", md))
    out = []
    for _n, line in prose:
        line = _ADMONITION_RE.sub("", _QUOTE_RE.sub("", line))
        if _RULE_RE.match(line):
            continue
        if line.lstrip().startswith("|"):
            cells = [_inline_plain(c) for c in _CELL_SPLIT_RE.split(line.strip().strip("|"))]
            text = "\t".join(c for c in cells if c)
        else:
            heading = _HEADING_RE.match(line)
            text = _inline_plain(heading.group(1) if heading else _LIST_RE.sub("", line))
        if text:
            out.append(text)
    return out


def page_plain_text(page: dict) -> str:
    """A page body as plain text, one paragraph, heading, item or table
    row per line. Typed blocks give the words they draw (a table's cells,
    a step's body) through the same walk the search index uses."""
    lines: list[str] = []
    for blk in page.get("b") or []:
        if isinstance(blk, str):
            lines += _markdown_lines(blk)
        elif isinstance(blk, dict):
            text = _inline_plain(cli.extract_page_text({"k": "page", "b": [blk]}))
            if text:
                lines.append(text)
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# The leak check, on the built package.
# ------------------------------------------------------------------ #

# A path into somebody's home directory. Not preceded by a host-name
# character, so `https://example.com/home/news/` is a URL and not a home;
# `file:///Users/x/` still is one.
_HOME_RE = re.compile(
    rb"(?:(?<![\w.-])|(?<=\\[nrt]))(?:/Users|/home)/[^/\s\"'<>`|\\*]+/[^\s\"'<>`|\\*)\]]*"
    rb"|[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\)[^\\\s\"'<>]+"
)
_EXTERNAL_RE = re.compile(r"^(?:https?:)?//", re.I)
_EXTERNAL_TAG_RE = re.compile(
    r"<(?:script|img|iframe|frame|embed|object|video|audio|source|track|link|input|image|use)\b[^>]*?"
    r"\b(?:src|href|data|poster|srcset|xlink:href)\s*=\s*[\"']\s*((?:https?:)?//[^\"'\s]+)",
    re.I,
)
_EXTERNAL_CSS_RE = re.compile(r"""(?:url\(\s*["']?|@import\s+["'])\s*((?:https?:)?//[^"')\s]+)""", re.I)
_EXTERNAL_JS_RE = re.compile(
    r"""(?:\b(?:fetch|import|importScripts|EventSource|WebSocket|Worker|SharedWorker|sendBeacon)\s*\(|"""
    r"""\.src\s*=)\s*["'`]((?:https?:|wss?:)?//[^"'`\s]+)"""
)
_ANCHOR_RE = re.compile(r"""<a\b[^>]*?\bhref\s*=\s*["']((?:https?:)?//[^"'\s]+)""", re.I)
_LOAD_KEYS = ("src", "poster", "image", "img", "icon", "thumbnail")


def _home_findings(staging: Path, origins: dict[str, list[Path]], texts: dict[Path, str]) -> list[Finding]:
    """(a) Every home-directory path in any file of the package.

    Bytes, not text: a PDF's metadata is where a script's working
    directory ends up, and it is as much a part of what is sent as the
    page is. Each one is reported against the file the author edits.
    """
    home = str(Path.home()).encode()
    extra = None if home.startswith((b"/Users/", b"/home/")) else re.compile(re.escape(home) + rb"(?=/)")
    found: dict[tuple, Finding] = {}
    for f in sorted(p for p in staging.rglob("*") if p.is_file()):
        rel = f.relative_to(staging).as_posix()
        data = f.read_bytes()
        hits = [m.group(0) for m in _HOME_RE.finditer(data)]
        if extra is not None:
            hits += [m.group(0) for m in extra.finditer(data)]
        for raw in hits:
            token = raw.decode("utf-8", "replace").rstrip(".,;:")
            src, line = _locate(token, origins.get(rel, []), texts)
            key = (src, line, token) if src else (rel, token)
            found.setdefault(key, Finding("error", "home-path", token, src, line)).outputs.add(rel)
    return list(found.values())


def _locate(token: str, candidates: list[Path], texts: dict[Path, str]) -> tuple[Path | None, int | None]:
    """The first candidate source holding `token`, and the line it is on.

    Whole tokens first: `/a/b/` is also the head of `/a/b/c.py`, and a
    plain substring search reported the shorter path on the longer one's
    line, in the wrong file. Then any occurrence, then the account part
    (`/Users/name/`) for a token the build assembled rather than the
    author typed.
    """
    parts = token.split("/")
    searches = [re.compile(re.escape(token) + r"(?![^\s\"'<>`|\\*)\]])"), re.compile(re.escape(token))]
    if len(parts) > 3:
        searches.append(re.compile(re.escape("/".join(parts[:3]) + "/")))
    for pattern in searches:
        for c in candidates:
            if c not in texts:
                try:
                    texts[c] = c.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    texts[c] = ""
            m = pattern.search(texts[c])
            if m:
                return c, texts[c].count("\n", 0, m.start()) + 1
    return None, None


def _why_not_carried(href: str, src: Path) -> str:
    """Why the package lacks what a reference names, in the source's terms."""
    target = (src.parent / _ref_path(href)).resolve()
    if not target.exists():
        return "names nothing at the source"
    if target.is_dir():
        return "names a directory"
    if not cli.asset_within_project(target, src):
        return f"names a file outside the project ({cli.project_root_for(src.parent).name}), which is not carried"
    return "names a file the package does not carry"


def _dangling(href: str, how: str, base: Path, staging: Path) -> str | None:
    """What is wrong with a reference inside the built package, or None."""
    if href.startswith("/"):
        return "is root-absolute, so under a path prefix it leaves the package"
    path = _ref_path(href)
    if how == "link" and path.lower().endswith(".md"):
        path = path[:-3] + ".html"
    target = Path(os.path.normpath(base / path))
    if target != staging and staging not in target.parents:
        return "resolves outside the package"
    if target.is_dir():
        return None if (target / "index.html").is_file() else "names a directory"
    return None if target.is_file() else "missing"


def _ref_findings(
    staging: Path, plan: Plan, texts: dict[Path, str], kit: SharedKit | None = None
) -> list[Finding]:
    """(b) Every local reference a packed page makes, resolved against the
    package rather than the source: it must land on a file inside it.

    The one exception is the shared kit. A reference under its URL is
    root-absolute on purpose and lands on the host's copy, not in the
    package, so it is held to what the export holds instead."""
    out: list[Finding] = []
    for pp in plan.pages:
        page = json.loads((staging / pp.json_rel).read_text(encoding="utf-8"))
        base = (staging / pp.rel).parent
        for href, how in _local_refs(page):
            problem = _dangling(href, how, base, staging)
            if problem == "missing":
                problem = _why_not_carried(href, pp.src)
            if problem:
                src, line = _locate(href, [pp.src], texts)
                out.append(
                    Finding(
                        "error", "outside-package", f"{href} {problem}", src, line, {pp.json_rel.as_posix()}
                    )
                )
        out += _chip_findings(page, pp, staging, texts)
    for f in sorted(staging.rglob("*.html")):
        rel = f.relative_to(staging)
        if rel.parts[0] == "_oku":
            continue
        for href in _ISLAND_REF_RE.findall(f.read_text(encoding="utf-8")):
            if kit is not None and href.startswith(kit.url):
                problem = None if _ref_path(href[len(kit.url) :]) in kit.files else "names no file of the kit"
            else:
                problem = None if _NOT_LOCAL_RE.match(href) else _dangling(href, "raw", f.parent, staging)
            if problem:
                out.append(
                    Finding("error", "outside-package", f"{href} {problem}", None, None, {rel.as_posix()})
                )
    return out


_CHIP_STATUS = {
    "missing": "names nothing at the source",
    "outside": "names a file outside the project, which is not carried",
}


def _chip_status(status: str | None) -> str:
    return _CHIP_STATUS.get(status or "", f"is {status} at the source")


def _chip_findings(page: dict, pp: PackPage, staging: Path, texts: dict[Path, str]) -> list[Finding]:
    """The `#f/` half of (b): a chip whose file did not travel, on the page
    or inside a carried markdown file the viewer will open."""
    out: list[Finding] = []
    meta = page.get("m") or {}
    files, more = meta.get("_files") or {}, meta.get("_files_more") or {}
    for key, ref in files.items():
        status = ref.get("status")
        if status not in ("ok", "over-cap"):
            src, line = _locate(f"#f/{key}", [pp.src], texts)
            out.append(Finding("error", "outside-package", f"#f/{key} {_chip_status(status)}", src, line))
    for ref in [*files.values(), *more.values()]:
        problem = _dangling(ref["url"], "raw", (staging / pp.rel).parent, staging) if ref.get("url") else None
        if problem:
            out.append(
                Finding("error", "outside-package", f"#f/{ref.get('path')} → {ref['url']} {problem}", pp.src)
            )
    # The page's own source is in the package too, as its .md copy.
    store = {r.get("rel") for r in files.values()} | set(more) | {meta.get("_rel")}
    proj = cli.project_root_for(pp.src.parent)
    for carrier in [*files.values(), *more.values()]:
        if carrier.get("kind") != "markdown" or carrier.get("text") is None or not carrier.get("rel"):
            continue
        carrier_path = proj / carrier["rel"]
        for href in _chip_hrefs(carrier["text"], carrier_path):
            target, status, _key, _line, _end = cli.resolve_file_line(href, carrier_path)
            rel = target.relative_to(proj).as_posix() if status == "ok" and target else None
            if rel not in store:
                why = _chip_status(status) if status != "ok" else "was not carried (past the closure budget)"
                src, line = _locate(f"#f/{href}", [carrier_path], texts)
                out.append(Finding("error", "outside-package", f"#f/{href} {why}", src, line))
    return out


def _chip_hrefs(text: str, path: Path) -> list[str]:
    """The `#f/` references in a carried markdown file, found the way
    `collect_file_closure` finds them: the file made a page, every string
    walked."""
    try:
        page = cli.md_to_v2_page(text, default_title=path.stem)
    except Exception:  # noqa: BLE001 — a file that will not parse carries nothing further
        return []
    hrefs = []
    for s in cli._iter_strings(page):
        if "#f/" in s:
            hrefs += [h.strip() for h in cli._MD_FILE_REF_RE.findall(cli._strip_code(s)) if h.strip()]
    return list(dict.fromkeys(hrefs))


def _external(page: dict) -> tuple[list[str], list[str]]:
    """(loads, links): what the page would fetch from another origin, and
    the plain hyperlinks a reader may follow."""
    loads: list[str] = []
    links: list[str] = []
    for blk in page.get("b") or []:
        for s in cli._iter_block_strings(blk):
            text = cli._strip_code(s)
            images = {m.group(1) for m in cli._MD_IMAGE_RE.finditer(text)}
            loads += [h for h in images if _EXTERNAL_RE.match(h)]
            loads += (
                _EXTERNAL_TAG_RE.findall(text)
                + _EXTERNAL_CSS_RE.findall(text)
                + _EXTERNAL_JS_RE.findall(text)
            )
            links += [
                h for h in cli._MD_LINK_TARGET_RE.findall(text) if _EXTERNAL_RE.match(h) and h not in images
            ]
            links += _ANCHOR_RE.findall(text)
        if isinstance(blk, dict):
            loads += [v for v in _values_at(blk, _LOAD_KEYS) if _EXTERNAL_RE.match(v)]
            links += [h for h in cli._iter_block_hrefs(blk) if _EXTERNAL_RE.match(h)]
    return list(dict.fromkeys(loads)), list(dict.fromkeys(links))


def _values_at(node, keys: tuple[str, ...]):
    if isinstance(node, list):
        for x in node:
            yield from _values_at(x, keys)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in keys and isinstance(v, str):
                yield v.strip()
            else:
                yield from _values_at(v, keys)


def _external_findings(staging: Path, plan: Plan, texts: dict[Path, str]) -> list[Finding]:
    """(c) External resource loads are findings; plain links are notes.

    Scanned: every packed page, and every carried markdown file, because
    the viewer draws one the way a page draws its body (its images too).
    The kit under `_oku/` is not: its CDN fallbacks are code that never
    runs while the vendored copy is there, which the browser test holds.
    """
    out: list[Finding] = []
    bodies = [
        (json.loads((staging / pp.json_rel).read_text(encoding="utf-8")), pp.src, pp.json_rel)
        for pp in plan.pages
    ]
    for target in sorted(f for f in plan.files if f.suffix.lower() in (".md", ".markdown")):
        rel = PurePosixPath(target.relative_to(plan.root).as_posix())
        bodies.append(
            (
                cli.md_to_v2_page((staging / rel).read_text(encoding="utf-8"), default_title=target.stem),
                target,
                rel,
            )
        )
    seen: set[str] = set()
    for page, src, rel in bodies:
        loads, links = _external(page)
        for url, severity, kind in [(u, "error", "external-load") for u in loads] + [
            (u, "info", "external-link") for u in links
        ]:
            if severity == "info" and url in seen:
                continue
            seen.add(url)
            where, line = _locate(url, [src], texts)
            out.append(Finding(severity, kind, url, where, line, {rel.as_posix()}))
    return out


def _check_findings(plan: Plan) -> list[Finding]:
    """The errors `oku check` would stop `oku build` on, for the packed pages."""
    pages = [(cli._synth_json_path(pp.src), pp.page) for pp in plan.pages]
    out = []
    for issue in cli.check_pages(pages, plan.root):
        if issue["severity"] == "error":
            src = cli._source_sibling(issue["path"])
            out.append(
                Finding("error", "check", f"[{issue['code']}] {issue['message']}", src, issue.get("line"))
            )
    return out


def _vendor_findings(plan: Plan) -> list[Finding]:
    """mermaid, Prism and the fonts are fetched once per installation; a
    package without them would reach a CDN for every diagram."""
    if not cli.vendor_is_complete():
        cli.fetch_vendor(quiet=True)
    langs: list[str] = []
    for pp in plan.pages:
        langs += cli.page_code_langs(pp.page)
    cli.fetch_prism_langs(langs, quiet=True)
    if cli.vendor_is_complete():
        return []
    note = cli._vendor_incomplete_note() or "incomplete"
    return [Finding("error", "kit-incomplete", f"the kit's vendor copy is {note}; run `oku vendor`")]


def leak_check(
    staging: Path, plan: Plan, origins: dict[str, list[Path]], kit: SharedKit | None = None
) -> list[Finding]:
    texts: dict[Path, str] = {}
    return (
        _home_findings(staging, origins, texts)
        + _ref_findings(staging, plan, texts, kit)
        + _external_findings(staging, plan, texts)
    )


# ------------------------------------------------------------------ #
# The command.
# ------------------------------------------------------------------ #


def _validate(pages: list[str], out: str) -> tuple[list[Path], Path]:
    entries: list[Path] = []
    for raw in pages:
        p = Path(raw).expanduser()
        if not p.is_file():
            raise PackUsageError(f"{raw}: no such file")
        if p.suffix.lower() != ".md":
            raise PackUsageError(f"{raw}: not a markdown page (.md)")
        if p.resolve() not in entries:
            entries.append(p.resolve())
    out_dir = Path(out).expanduser().absolute()
    if out_dir.exists() and not out_dir.is_dir():
        raise PackUsageError(f"{out}: exists and is not a directory")
    if out_dir.is_dir() and any(out_dir.iterdir()) and not (out_dir / INDEX_NAME).is_file():
        raise PackUsageError(
            f"{out}: not empty and holds no {INDEX_NAME}; refusing to replace a directory oku did not pack"
        )
    if not out_dir.parent.is_dir():
        raise PackUsageError(f"{out}: its parent directory does not exist")
    return entries, out_dir


def _place(staging: Path, out_dir: Path) -> None:
    """The one statement that touches `--out`, after every check passed."""
    if not out_dir.exists():
        staging.rename(out_dir)
        return
    old = out_dir.with_name(f".{out_dir.name}.old-{os.getpid()}")
    out_dir.rename(old)
    try:
        staging.rename(out_dir)
    except OSError:
        old.rename(out_dir)
        raise
    shutil.rmtree(old, ignore_errors=True)


def _shown(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _format(f: Finding) -> str:
    icon = "✗" if f.severity == "error" else "·"
    where = (
        f"{_shown(f.source)}{f':{f.line}' if f.line else ''}" if f.source else ", ".join(sorted(f.outputs))
    )
    carried = ""
    if f.source and f.outputs and f.kind == "home-path":
        names = sorted(f.outputs)
        carried = f"  (in {', '.join(names[:3])}{f' +{len(names) - 3}' if len(names) > 3 else ''})"
    return f"  {icon} {where} [{f.kind}] {f.detail}{carried}"


# Root-relative, every segment non-empty, ending in `/`. Only characters
# that need no escaping in an HTML attribute, so the stub can carry the
# value as given and the leak check can match it as written.
_KIT_URL_FORM = re.compile(r"^/(?:(?:[A-Za-z0-9._~@:!$()*+,;=-]|%[0-9A-Fa-f]{2})+/)*$")


def _check_kit_url(url: str) -> None:
    if not _KIT_URL_FORM.match(url) or any(seg in (".", "..") for seg in url.split("/")):
        raise PackUsageError(
            f"--kit-url {url!r}: not a root-relative path ending in / (for example /k/); "
            "a scheme, a host, a query, a dot segment or an empty segment is refused"
        )


def _shared_kit(kit_dir: str, url: str) -> SharedKit:
    """The export at `kit_dir`, as this package will load it from `url`.

    Refused unless it is one this oku wrote: a core of another release
    would run this release's pages with that release's renderer."""
    root = Path(kit_dir).expanduser()
    if not root.is_dir():
        raise PackUsageError(
            f"--kit {kit_dir}: not a directory; write one with `oku kit export --out {kit_dir}`"
        )
    layers: dict[str, str] = {}
    for d in sorted(root.iterdir()):
        m = _LAYER_DIR.match(d.name)
        if not m or not d.is_dir() or m.group(1) in layers:
            raise PackUsageError(
                f"--kit {kit_dir}: holds {d.name}, which no kit export writes beside the layers"
            )
        layers[m.group(1)] = d.name
    if "core" not in layers:
        raise PackUsageError(
            f"--kit {kit_dir}: no core layer; write one with `oku kit export --out {kit_dir}`"
        )
    core = root / layers["core"]
    for name in ("chrome.js", "renderer.js", "chrome-boot.js"):
        f = core / name
        if not f.is_file() or f.read_text(encoding="utf-8") != cli.kit_file_text(name):
            raise PackUsageError(
                f"--kit {kit_dir}: its {name} is not this oku's (kit {cli._kit_build_stamp()}); export it again"
            )
    files = frozenset(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    return SharedKit(url, layers, files)


def run(pages: list[str], out: str, kit_url: str | None = None, kit_dir: str | None = None) -> int:
    kit: SharedKit | None = None
    try:
        entries, out_dir = _validate(pages, out)
        if (kit_url is None) != (kit_dir is None):
            raise PackUsageError(
                "--kit and --kit-url go together: the exported kit, and the address it is served under"
            )
        if kit_url is not None:
            _check_kit_url(kit_url)
            kit = _shared_kit(kit_dir, kit_url)
    except PackUsageError as e:
        print(f"✗ {e}", file=sys.stderr)
        return EXIT_USAGE
    plan = plan_pack(entries)
    if not plan.pages:
        print(f"✗ {pages[0]}: not readable as a page", file=sys.stderr)
        return EXIT_USAGE
    # The vendor copy matters only to a package that carries it; with a
    # shared kit, `oku kit export` is the command that answered for it.
    findings = ([] if kit is not None else _vendor_findings(plan)) + _check_findings(plan)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.pack-", dir=out_dir.parent))
    try:
        origins, written = _write_tree(plan, staging, kit)
        findings += written + leak_check(staging, plan, origins, kit)
        errors = [f for f in findings if f.severity == "error"]
        for f in errors + [f for f in findings if f.severity != "error"]:
            print(_format(f))
        if errors:
            print(
                f"✗ Not packed: {len(errors)} finding(s). Nothing was written to {out}; fix the sources.",
                file=sys.stderr,
            )
            return EXIT_FINDINGS
        count = sum(1 for p in staging.rglob("*") if p.is_file())
        _place(staging, out_dir)
    except OSError as e:
        print(f"✗ Pack failed: {e}. Nothing was written to {out}.", file=sys.stderr)
        return EXIT_FINDINGS
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    print(f"✓ Packed {len(plan.pages)} page(s), {count} file(s) into {out}")
    print(f"  entry: {plan.pages[0].rel.as_posix()}")
    if kit is not None:
        print(
            f"  kit:   {kit.url} + {', '.join(sorted(kit.layers.values()))} (not carried; serve the export there)"
        )
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    return run(args.pages, args.out, args.kit_url, args.kit)


# ------------------------------------------------------------------ #
# `oku kit export` — one copy of the kit for every package a host serves.
# ------------------------------------------------------------------ #

# What chrome.js loads from the kit besides the four files a stub names:
# `i18n/<lang>.json`, `glossary/<domain>.json`, `extrefs/<domain>.json`,
# and the vendor copy. `schema/` is left out: nothing a page runs fetches
# a schema or examples.json — the renderer carries the schema's
# `required` lists as a literal — and they exist for `oku check` and
# `oku spec`. The browser test asserts no page asks for one.
_EXPORT_DIRS = ("glossary", "extrefs", "i18n")

# The export is layers, each a directory named for its content,
# `<name>-<16 hex>`: the core (oku's own files: the four a stub names,
# i18n, the registries) and one per vendored dependency (fonts, mermaid,
# prism). A host that keeps each address for good — pano's /k/ — then
# takes an oku release that changed only oku's code as one new core
# layer, and readers download only that: mermaid's 3.3 MB, the fonts and
# the grammars keep their addresses and stay in every browser's cache.
_LAYER_DIR = re.compile(r"^([a-z0-9]{1,32})-([0-9a-f]{16})$")


def layer_id(files: dict[str, bytes]) -> str:
    """The 16 hex digits of a layer's name: the SHA-256 of its sorted
    "path<TAB>sha256" lines, paths inside the layer. pano computes the same
    (kitIdOf in its src/lib/server/publish.ts) and refuses a layer whose
    name is not its content's."""
    lines = sorted(f"{p}\t{hashlib.sha256(d).hexdigest()}\n" for p, d in files.items())
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()[:16]


def _layer_of(rel: str) -> tuple[str, str]:
    """(layer, path inside it) for a path of `_export_sources()`. A vendor
    file keeps its path under vendor/, so the kit's loaders find it at
    the layer's base exactly as they do under `vendor/`."""
    if not rel.startswith("vendor/"):
        return "core", rel
    inner = rel.removeprefix("vendor/")
    return inner.split("/", 1)[0].split(".", 1)[0], inner


def export_layers() -> dict[str, dict[str, bytes]]:
    """Every layer the export writes, by directory name, with its files."""
    parts: dict[str, dict[str, bytes]] = {}
    for rel, src in _export_sources().items():
        name, inner = _layer_of(rel)
        parts.setdefault(name, {})[inner] = src.encode("utf-8") if isinstance(src, str) else src.read_bytes()
    named = {name: f"{name}-{layer_id(files)}" for name, files in parts.items() if name != "core"}
    # chrome.css names its fonts beside itself, `vendor/fonts/…`; exported,
    # they are a sibling layer, so the stylesheet names that, and the
    # core's name follows the fonts': new fonts are a new core.
    core = parts["core"]
    if "fonts" in named:
        css = core["chrome.css"].decode("utf-8")
        core["chrome.css"] = cli._FONT_URL_RE.sub(f'url("../{named["fonts"]}/fonts/', css).encode("utf-8")
    named["core"] = f"core-{layer_id(core)}"
    return {named[name]: dict(sorted(files.items())) for name, files in sorted(parts.items())}


def _grammar_dir() -> Path:
    """Every grammar of the pinned Prism release, cached once per machine.

    Not the vendor directory. That one holds the grammars this machine's
    builds happened to need, so it grows, and an export copied from it
    changed bytes — and the host's kit id, so every reader re-fetched the
    whole kit — whenever any project used a language for the first time.
    An export made before the pack that fetched a grammar also lacked
    it, and that block drew as plain text. Not inside it either: every
    build copies the whole vendor directory into its tree.
    """
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "oku" / f"prism-{cli._PRISM_VERSION}" / "components"


def _all_grammars() -> list[str]:
    """The component files Prism's catalog has; the grammars compiled into
    prism.min.js have none."""
    cat = cli.prism_catalog()
    return sorted(cat["ids"] - cat["bundled"])


def _export_sources() -> dict[str, Path | str]:
    """Every file the export writes, by its path in the export, mapped to
    the file it is copied from (or, for carried.js, its text). A function
    of the installed oku alone, so two runs write the same bytes."""
    kit, vendor = cli.KIT_DIR, cli.vendor_dir()
    out: dict[str, Path | str] = {name: cli.kit_file_text(name) for name in cli.KIT_FILES}
    for d in _EXPORT_DIRS:
        out.update({f"{d}/{f.name}": f for f in (kit / d).glob("*.json")})
    for rel, _url in cli._vendor_files():
        if not rel.startswith("prism/components/"):
            out[f"vendor/{rel}"] = vendor / rel
    grammars = _all_grammars()
    out.update(
        {f"vendor/prism/components/prism-{g}.min.js": _grammar_dir() / f"prism-{g}.min.js" for g in grammars}
    )
    out["vendor/prism/carried.js"] = cli.prism_carried_js(grammars)
    return dict(sorted(out.items()))


def _fetch_grammar(ident: str) -> bool:
    import http.client
    import urllib.error
    import urllib.request

    dest = _grammar_dir() / f"prism-{ident}.min.js"
    try:
        with urllib.request.urlopen(f"{cli._PRISM_CDN}components/prism-{ident}.min.js", timeout=30) as r:  # noqa: S310 - pinned https CDN
            data = r.read()
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return False
    if not data:
        return False
    # Through a temporary name: a file cut short by an interrupted run
    # would otherwise count as present, and every later export carry it.
    part = dest.with_name(f".{dest.name}.{os.getpid()}.part")
    part.write_bytes(data)
    os.replace(part, dest)
    return True


def _fetch_grammars() -> list[str]:
    """Fill the grammar cache; return the grammars that could not be fetched."""
    from concurrent.futures import ThreadPoolExecutor

    need = [g for g in _all_grammars() if not (_grammar_dir() / f"prism-{g}.min.js").is_file()]
    if not need:
        return []
    _grammar_dir().mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=16) as pool:
        fetched = list(pool.map(_fetch_grammar, need))
    # One more pass, one at a time, for what failed. Measured on the first
    # fill of an empty cache: 15 of 285 failed in the opening wave of
    # parallel connections and every one fetched on the next run.
    return [g for g, ok in zip(need, fetched, strict=True) if not ok and not _fetch_grammar(g)]


def _validate_export_out(out: str) -> Path:
    out_dir = Path(out).expanduser().absolute()
    if out_dir.exists() and not out_dir.is_dir():
        raise PackUsageError(f"{out}: exists and is not a directory")
    if out_dir.is_dir():
        foreign = sorted(p.name for p in out_dir.iterdir() if not (_LAYER_DIR.match(p.name) and p.is_dir()))
        if foreign:
            raise PackUsageError(
                f"{out}: holds {foreign[0]}, which no kit export writes; "
                "refusing to replace a directory oku did not export"
            )
    if not out_dir.parent.is_dir():
        raise PackUsageError(f"{out}: its parent directory does not exist")
    return out_dir


def export_kit(out: str) -> int:
    try:
        out_dir = _validate_export_out(out)
    except PackUsageError as e:
        print(f"✗ {e}", file=sys.stderr)
        return EXIT_USAGE
    if not cli.vendor_is_complete():
        cli.fetch_vendor(quiet=True)
    if not cli.vendor_is_complete():
        note = cli._vendor_incomplete_note() or "incomplete"
        print(f"✗ Not exported: the kit's vendor copy is {note}; run `oku vendor`.", file=sys.stderr)
        return EXIT_FINDINGS
    failed = _fetch_grammars()
    if failed:
        print(
            f"✗ Not exported: {len(failed)} Prism grammar(s) could not be fetched into {_grammar_dir()}"
            f" ({', '.join(failed[:5])}{', …' if len(failed) > 5 else ''}). Nothing was written to {out}.",
            file=sys.stderr,
        )
        return EXIT_FINDINGS
    layers = export_layers()
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.kit-", dir=out_dir.parent))
    try:
        for layer, files in layers.items():
            for rel, data in files.items():
                _write(staging, f"{layer}/{rel}", data)
        _place(staging, out_dir)
    except OSError as e:
        print(f"✗ Export failed: {e}. Nothing was written to {out}.", file=sys.stderr)
        return EXIT_FINDINGS
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    count = sum(len(files) for files in layers.values())
    total = sum(len(d) for files in layers.values() for d in files.values())
    print(
        f"✓ Exported kit {cli._kit_build_stamp()}: {len(layers)} layers, {count} file(s), "
        f"{total / 1_000_000:.1f} MB into {out}"
    )
    for layer, files in layers.items():
        print(f"  {layer}  {len(files)} file(s), {sum(map(len, files.values())) / 1_000_000:.1f} MB")
    return 0


def cmd_kit_export(args: argparse.Namespace) -> int:
    return export_kit(args.out)
