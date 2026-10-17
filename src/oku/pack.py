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


def _stub(pp: PackPage) -> str:
    lang = cli._lang_of_page(pp.page)
    html = cli._stub_for(cli._page_title(pp.page) or pp.src.stem, lang=lang)
    html = cli._retarget_kit_urls(html, len(pp.rel.parts) - 1)
    return cli._with_html_lang(cli._mark_built(html), lang)


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


def _write_tree(plan: Plan, staging: Path) -> tuple[dict[str, list[Path]], list[Finding]]:
    """Write the package into `staging`; return each file's sources.

    The sources are what a finding is reported against: the markdown the
    author edits, not the JSON the build derived from it.
    """
    entry = plan.pages[0]
    title, summary = _entry_title(entry)
    cli.copy_site_kit(staging)
    origins: dict[str, list[Path]] = {}
    findings: list[Finding] = []
    srcs = [pp.src for pp in plan.pages]
    for pp in plan.pages:
        _localize_files(pp, plan.root)
        texts = _text_sources(pp)
        _write(staging, pp.rel, _stub(pp))
        _write(staging, pp.json_rel, json.dumps(pp.page, ensure_ascii=False, indent=2))
        _write(staging, pp.md_rel, pp.src.read_bytes())
        for rel in (pp.rel, pp.json_rel, pp.md_rel):
            origins[rel.as_posix()] = [pp.src, *texts]
    for target in sorted(plan.files):
        rel = target.relative_to(plan.root).as_posix()
        # The package's own files sit at fixed names at its root; a carried
        # file there would be overwritten by them, or would replace them.
        taken = rel in _DERIVED_NAMES or rel.startswith("_oku/")
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
    _write(staging, INDEX_NAME, json.dumps(pack_index(staging, plan), indent=2, ensure_ascii=False) + "\n")
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


def pack_index(staging: Path, plan: Plan) -> dict:
    """`_pack.json`. Paths are package-relative POSIX paths, as on disk;
    a host quotes each segment to make a URL. `files` lists every file in
    the package but this one."""
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
    return {
        "pack": PACK_FORMAT,
        "entry": entry.rel.as_posix(),
        "title": title,
        "summary": summary,
        "pages": pages,
        "files": files,
    }


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
# What stops a build stops a pack.
# ------------------------------------------------------------------ #


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


def run(pages: list[str], out: str) -> int:
    try:
        entries, out_dir = _validate(pages, out)
    except PackUsageError as e:
        print(f"✗ {e}", file=sys.stderr)
        return EXIT_USAGE
    plan = plan_pack(entries)
    if not plan.pages:
        print(f"✗ {pages[0]}: not readable as a page", file=sys.stderr)
        return EXIT_USAGE
    findings = _vendor_findings(plan) + _check_findings(plan)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.pack-", dir=out_dir.parent))
    try:
        _origins, written = _write_tree(plan, staging)
        findings += written
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
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    return run(args.pages, args.out)
