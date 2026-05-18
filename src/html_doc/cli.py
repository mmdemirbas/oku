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
import socketserver
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
      force-include packs chrome.{css,js}, chrome-boot.js, renderer.js,
      schema/, glossary/, extrefs/, templates/ into
      ``<site-packages>/html_doc/assets/``. This is the canonical layout
      once the package is on PATH.
    - **Development** (cloned repo, no install): the assets live at the
      repo root next to ``src/``. Walk up from ``cli.py`` until we find
      a directory containing both ``chrome.css`` and ``schema/``.

    The two-layout selector means ``html-doc init`` keeps working from
    either invocation path. Returns the resolved directory; the caller
    is responsible for handling missing files within it.
    """
    here = Path(__file__).resolve()
    pkg_assets = here.parent / "assets"
    if (pkg_assets / "chrome.css").exists():
        return pkg_assets
    # Walk upward looking for the dev layout (repo root marker).
    for ancestor in [here.parent, *here.parents]:
        if (ancestor / "chrome.css").exists() and (ancestor / "schema").exists():
            return ancestor
    # Fallback to the two-parents-up legacy assumption.
    return here.parent.parent


KIT_ROOT = _kit_assets_dir()
KIT_FILES = ['chrome.css', 'chrome.js', 'chrome-boot.js', 'renderer.js']
SKIP_DIRS = {'dist', '_kit', 'node_modules', '.git', 'venv', '.venv', '__pycache__'}

try:
    import jsonschema as _jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


# ---------- file:// printer ----------
def file_url(p: Path) -> str:
    return f'file://{p.resolve()}'


def report(label: str, path: Path) -> None:
    print(f'  {label:<14} {file_url(path)}')


# ---------- init ----------
def cmd_init(args: argparse.Namespace) -> int:
    """Create docs/_kit -> KIT_ROOT symlink in the current project."""
    project = Path.cwd()
    docs = project / 'docs'
    docs.mkdir(exist_ok=True)
    target = docs / '_kit'

    if target.exists() or target.is_symlink():
        if target.is_symlink() and Path(os.readlink(target)) == KIT_ROOT:
            print(f'✓ Already linked: {target} -> {KIT_ROOT}')
            print(f'  Open kit:     {file_url(KIT_ROOT)}')
            return 0
        print(f'✗ Path exists and is not the expected symlink: {target}', file=sys.stderr)
        print(f'  Current target: {os.readlink(target) if target.is_symlink() else "(not a symlink)"}', file=sys.stderr)
        return 1

    target.symlink_to(KIT_ROOT)
    print(f'✓ Linked {target} -> {KIT_ROOT}')
    print()
    print('  Reference the kit in your HTML <head>:')
    print('    <script src="_kit/chrome-boot.js"></script>')
    print('    <link rel="stylesheet" href="_kit/chrome.css">')
    print('    <script src="_kit/chrome.js" defer></script>')
    print()
    print('  Then run `html-doc build` to produce dist/standalone/ + dist/site/.')
    return 0


# ---------- build ----------
LINK_TO_KIT_CSS = re.compile(r'<link\s+rel="stylesheet"\s+href="_kit/chrome\.css"\s*/?>', re.I)
SCRIPT_TO_KIT_BOOT = re.compile(r'<script\s+src="_kit/chrome-boot\.js"\s*></script>', re.I)
SCRIPT_TO_KIT_MAIN = re.compile(r'<script\s+src="_kit/chrome\.js"\s+defer\s*></script>', re.I)
SCRIPT_TO_KIT_RENDERER = re.compile(r'<script\s+src="_kit/renderer\.js"\s+defer\s*></script>', re.I)


def find_html_files(root: Path):
    """Find HTML files recursively under root, skipping generated dirs."""
    out = []
    for p in root.rglob('*.html'):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            out.append(p)
    return sorted(out, key=lambda x: str(x).lower())


# ---------- JSON pages + site manifest ----------
def find_json_pages(root: Path):
    """Recursively find *.json files where the root object has kind == 'page'.

    Returns list of (path, parsed-data) tuples sorted by path.
    """
    pages = []
    for p in root.rglob('*.json'):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name in ('kit.json', 'site-manifest.json', 'package.json', 'tsconfig.json'):
            continue
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and data.get('kind') == 'page':
            pages.append((p, data))
    return sorted(pages, key=lambda x: str(x[0]).lower())


_schema_cache = None


def _load_schema():
    """Lazy-load and cache the page schema."""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache
    schema_path = KIT_ROOT / 'schema' / 'page.schema.json'
    if schema_path.exists():
        try:
            _schema_cache = json.loads(schema_path.read_text(encoding='utf-8'))
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
            field = '.'.join(str(x) for x in e.absolute_path) or '(root)'
            errors.append((p, f'{field}: {e.message}'))
        except _jsonschema.SchemaError:
            # Schema itself bad — abort validation entirely
            return []
    return errors


def build_manifest(root: Path) -> Path:
    """Walk JSON pages under root, emit site-manifest.json at root.

    Manifest entries: { path, title, parent, order?, summary? }. Folder
    hierarchy is implicit in the path; the runtime tree-builder groups
    siblings under their common ancestor path.
    """
    pages = find_json_pages(root)
    entries = []
    for p, data in pages:
        rel = p.relative_to(root)
        # The navigable URL is the sibling HTML stub: page.json → page.html.
        nav_path = rel.with_suffix('.html').as_posix()
        # Parent = directory part, or null if at root.
        parent = rel.parent.as_posix() if rel.parent != Path('.') else None
        meta = data.get('meta') or {}
        entry = {
            'path': nav_path,
            'source': rel.as_posix(),
            'title': data.get('title') or p.stem,
            'parent': parent,
        }
        if 'order' in meta:
            entry['order'] = meta['order']
        if 'summary' in meta:
            entry['summary'] = meta['summary']
        entries.append(entry)
    manifest = {
        'schema_version': 1,
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'),
        'root': '.',
        'pages': entries,
    }
    out = root / 'site-manifest.json'
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    # Companion JS file lets the runtime load the manifest via <script src>
    # when fetch() is blocked (file:// CORS) or returns 404 (IntelliJ's
    # built-in server gates non-token GETs). chrome.js attempts fetch first
    # and falls back to the script tag on failure.
    js_out = root / 'site-manifest.js'
    js_payload = (
        '/* Auto-generated by html-doc. Sets window.__htmldocManifest for the\n'
        '   runtime when a fetch() of site-manifest.json is impossible (file://\n'
        '   CORS) or unauthorized (IDE built-in servers). Safe to load multiple\n'
        '   times — last definition wins. */\n'
        'window.__htmldocManifest = ' + json.dumps(manifest, ensure_ascii=False) + ';\n'
    )
    js_out.write_text(js_payload, encoding='utf-8')
    return out


# ---------- LLM-friendly markdown twin per JSON page ----------
def _flatten_inline(content) -> str:
    """Walk a rich-string (string / list / dict node) into plain markdown."""
    if content is None:
        return ''
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(_flatten_inline(c) for c in content)
    if isinstance(content, dict):
        kind = content.get('kind') or content.get('type')
        body = content.get('text') or content.get('content', '')
        body = _flatten_inline(body)
        href = content.get('href') or content.get('link', '')
        if kind in ('em', 'i'):       return '*' + body + '*'
        if kind in ('strong', 'b'):   return '**' + body + '**'
        if kind == 'code':            return '`' + body + '`'
        if kind == 'link':            return f'[{body}]({href})' if href else body
        if kind == 'ext-ref':         return f'[{body}]({href})' if href else body
        if kind == 'glossary-term':   return body
        if kind == 'br':              return '\n'
        return body
    return str(content)


def _md_block(block: dict, depth: int = 0) -> list[str]:
    """Render a JSON content block as a list of markdown lines.

    Best-effort — known kinds get semantic markdown; unknown / visually-
    rich kinds (charts, diagrams) get a parenthetical placeholder so the
    consuming LLM still sees the structure. Empty list means "skip"."""
    if not isinstance(block, dict):
        return []
    kind = block.get('kind', '')
    out: list[str] = []

    if kind == 'section':
        title = _flatten_inline(block.get('title') or '')
        if title:
            out.append('## ' + title)
            out.append('')
        for child in block.get('blocks', []):
            out.extend(_md_block(child, depth + 1))
            out.append('')
        return out

    if kind == 'heading':
        level = max(2, int(block.get('level', 2)))
        out.append('#' * level + ' ' + _flatten_inline(block.get('text', '')))
        return out

    if kind == 'paragraph':
        out.append(_flatten_inline(block.get('content', '')))
        return out

    if kind in ('callout', 'tldr', 'insight', 'info-tip'):
        type_label = (block.get('type') or kind).upper()
        body = _flatten_inline(block.get('content') or block.get('lead', '') or block.get('body', ''))
        title = _flatten_inline(block.get('title') or '')
        header = f'> **{type_label}: {title}**' if title else f'> **{type_label}**'
        out.append(header)
        for line in body.split('\n'):
            out.append('> ' + line if line else '>')
        return out

    if kind == 'list':
        items = block.get('items') or block.get('bullets') or []
        ordered = block.get('ordered') is True
        for i, item in enumerate(items, 1):
            text = _flatten_inline(item if not isinstance(item, dict) else (item.get('text') or item.get('content') or ''))
            prefix = f'{i}. ' if ordered else '- '
            out.append(prefix + text)
        return out

    if kind == 'code':
        lang = block.get('language') or block.get('lang') or ''
        body = block.get('source') or block.get('content') or block.get('code', '')
        out.append('```' + lang)
        out.append(body)
        out.append('```')
        return out

    if kind == 'annotated-code':
        lang = block.get('language') or ''
        body = block.get('source') or ''
        out.append('```' + lang)
        out.append(body)
        out.append('```')
        annos = block.get('annotations') or []
        if annos:
            out.append('')
            for a in annos:
                if not isinstance(a, dict):
                    continue
                aid = a.get('id', '')
                # Strip inline HTML for markdown — keep the structure but
                # avoid raw <code> / <strong> tags in the .md.
                content = re.sub(r'<[^>]+>', '', a.get('content', ''))
                out.append(f'{aid}. {content}')
        return out

    if kind == 'table':
        headers = [_flatten_inline(h) for h in (block.get('headers') or [])]
        if headers:
            out.append('| ' + ' | '.join(headers) + ' |')
            out.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        def emit_row(row):
            cells = row.get('cells') if isinstance(row, dict) else row
            md_cells = [_flatten_inline(c).replace('|', '\\|').replace('\n', ' ') for c in (cells or [])]
            out.append('| ' + ' | '.join(md_cells) + ' |')
        if block.get('groups'):
            for g in block['groups']:
                title = _flatten_inline(g.get('title') or '')
                if title:
                    out.append('')
                    out.append('### ' + title)
                    if headers:
                        out.append('')
                        out.append('| ' + ' | '.join(headers) + ' |')
                        out.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
                for row in (g.get('rows') or []):
                    emit_row(row)
        else:
            for row in (block.get('rows') or []):
                emit_row(row)
        return out

    if kind == 'kpi-grid':
        for item in (block.get('tiles') or block.get('items') or []):
            num = item.get('num', '')
            label = _flatten_inline(item.get('label', ''))
            out.append(f'- **{num}** — {label}')
        return out

    if kind == 'bar-chart':
        title = _flatten_inline(block.get('title') or 'Bar chart')
        out.append('### ' + title)
        for row in (block.get('rows') or block.get('data') or []):
            label = _flatten_inline(row.get('label', ''))
            value = row.get('value', '')
            out.append(f'- {label}: {value}')
        return out

    if kind in ('compare-grid', 'scope-grid'):
        for card in (block.get('cards') or block.get('cols') or block.get('items') or []):
            t = _flatten_inline(card.get('title', ''))
            body = _flatten_inline(card.get('content') or card.get('summary') or '')
            if t:    out.append('### ' + t)
            if body: out.append(body)
        return out

    if kind == 'step-flow':
        for i, step in enumerate(block.get('steps') or [], 1):
            t = _flatten_inline(step.get('title', ''))
            body = _flatten_inline(step.get('content') or step.get('summary') or '')
            out.append(f'{i}. **{t}**')
            if body:
                for line in body.split('\n'):
                    out.append('   ' + line)
        return out

    if kind in ('chart', 'diagram'):
        title = _flatten_inline(block.get('title') or block.get('caption') or kind)
        out.append(f'_[{kind}: {title}]_')
        return out

    if kind == 'live-snippet':
        out.append('_[interactive snippet]_')
        return out

    # Unknown — emit a placeholder so the structure isn't lost.
    out.append(f'_[{kind or "block"}]_')
    return out


def render_page_markdown(page_json: dict) -> str:
    """Render a JSON page as semantic markdown for the /page.md LLM twin."""
    lines: list[str] = []
    title = page_json.get('title') or ''
    if title:
        lines.append('# ' + title)
        lines.append('')
    meta = page_json.get('meta') or {}
    subtitle = _flatten_inline(meta.get('subtitle') or '')
    if subtitle:
        lines.append('*' + subtitle + '*')
        lines.append('')
    bits: list[str] = []
    for key in ('date', 'audience', 'read_time'):
        if meta.get(key):
            bits.append(str(meta[key]))
    if meta.get('updated'):
        bits.append('Updated: ' + str(meta['updated']))
    if bits:
        lines.append('> ' + ' · '.join(bits))
        lines.append('')
    for block in page_json.get('blocks', []):
        lines.extend(_md_block(block))
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def build_markdown_twins(root: Path) -> int:
    """For each JSON page under root, emit a sibling <name>.md. Returns count."""
    n = 0
    for p, data in find_json_pages(root):
        rel = p.relative_to(root)
        out_path = root / rel.with_suffix('.md')
        try:
            out_path.write_text(render_page_markdown(data), encoding='utf-8')
            n += 1
        except OSError:
            continue
    return n


def build_llms_txt(root: Path) -> Path:
    """Emit llms.txt — sitemap for LLM consumers (llmstxt.org convention).

    One line per page: link + summary. No body copy (HTML is the source
    of truth — LLM consumers fetch the HTML if they need more).
    """
    pages = find_json_pages(root)
    project_name = root.name
    description = ''
    kit_json = root / 'kit.json'
    if kit_json.exists():
        try:
            kit_data = json.loads(kit_json.read_text(encoding='utf-8'))
            project_name = kit_data.get('name', project_name)
            description = kit_data.get('description', '')
        except (json.JSONDecodeError, OSError):
            pass

    lines = ['# ' + project_name, '']
    if description:
        lines += ['> ' + description, '']
    lines += ['## Pages', '']
    # Sort by parent (folder), then order, then title.
    entries = []
    for p, data in pages:
        rel = p.relative_to(root)
        nav_path = rel.with_suffix('.html').as_posix()
        meta = data.get('meta') or {}
        entries.append({
            'path': nav_path,
            'title': data.get('title') or p.stem,
            'parent': rel.parent.as_posix() if rel.parent != Path('.') else '',
            'order': meta.get('order', 1000),
            'summary': meta.get('summary', ''),
        })
    entries.sort(key=lambda e: (e['parent'], e['order'], e['title'].lower()))
    for e in entries:
        line = '- [' + e['title'] + '](' + e['path'] + ')'
        if e['summary']:
            line += ': ' + e['summary']
        lines.append(line)
    lines.append('')

    out = root / 'llms.txt'
    out.write_text('\n'.join(lines), encoding='utf-8')
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
    if not shutil.which('pagefind'):
        # Try npx as a fallback so the binary doesn't have to be installed globally.
        if shutil.which('npx'):
            cmd = ['npx', '--yes', 'pagefind', '--site', str(site_dir)]
        else:
            print('! pagefind not on PATH; skipping search index.')
            print('  Install: brew install pagefind  OR  npm i -g pagefind')
            return False
    else:
        cmd = ['pagefind', '--site', str(site_dir)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True
        print(f'! pagefind failed (exit {result.returncode})')
        if result.stderr.strip():
            print('  stderr:', result.stderr.strip().splitlines()[0])
        return False
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f'! pagefind exec error: {e}')
        return False


_PAGE_TEXT_KEYS = ('title', 'summary', 'lead', 'caption', 'content', 'def', 'label', 'name', 'text')
_PAGE_TEXT_LISTS = ('bullets', 'blocks', 'items', 'rows', 'steps', 'tiles', 'columns', 'cards', 'series', 'data')


def extract_page_text(page_json: dict) -> str:
    """Walk a JSON page tree and return concatenated plain text for indexing.

    Includes paragraph content, glossary-term / ext-ref labels, callout
    titles and bodies, etc. Skips structural-only fields. Strips inline
    HTML tags that might appear in def/summary strings.
    """
    parts = []

    if isinstance(page_json.get('title'), str):
        parts.append(page_json['title'])
    meta = page_json.get('meta') or {}
    for k in ('subtitle', 'summary', 'eyebrow'):
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

    walk(page_json.get('blocks', []))
    # Strip inline HTML that may live in glossary defs etc.
    raw = ' '.join(parts)
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


_BODY_CLOSE_RE = re.compile(r'</body>', re.I)


def inject_pagefind_body(html: str, text: str, title: str) -> str:
    """Embed plain-text content in a hidden element for Pagefind to index.

    data-pagefind-body restricts indexing to the marked element; everything
    else is ignored. data-pagefind-meta carries the title.
    """
    # Escape just enough for safety; full HTML escape is fine since this
    # element is hidden from users.
    safe_text = (text
                 .replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;'))
    safe_title = (title
                  .replace('&', '&amp;')
                  .replace('<', '&lt;')
                  .replace('>', '&gt;'))
    block = (
        '<div hidden data-pagefind-body>'
        f'<h1 data-pagefind-meta="title">{safe_title}</h1>'
        f'<p>{safe_text}</p>'
        '</div>'
    )
    if _BODY_CLOSE_RE.search(html):
        return _BODY_CLOSE_RE.sub(lambda m: block + '\n</body>', html, count=1)
    return html + block


def build_site(srcs, out_dir: Path, src_root: Path) -> None:
    """Build a self-contained multi-page site at out_dir/.

    Layout:
      dist/site/
        _kit/              ← chrome.css, chrome.js, chrome-boot.js, renderer.js,
                              glossary/, extrefs/
        kit.json           ← copied from src_root if present
        site-manifest.json ← copied from src_root
        llms.txt           ← copied from src_root if present
        *.html             ← each source HTML, kept as-is (refs stay '_kit/...')
        *.json             ← page JSON for the runtime renderer to fetch

    For each HTML, if a sibling page-JSON exists, inject its extracted
    text into a hidden data-pagefind-body element so the static
    Pagefind index has real content to chew on.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    kit_out = out_dir / '_kit'
    kit_out.mkdir(exist_ok=True)

    # Kit chrome files
    for f in KIT_FILES:
        shutil.copy(KIT_ROOT / f, kit_out / f)
    # Kit registry directories
    for d in ('glossary', 'extrefs', 'schema'):
        src_dir = KIT_ROOT / d
        if src_dir.exists():
            dst_dir = kit_out / d
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)

    # Project-level files that pages depend on at runtime
    for f in ('kit.json', 'site-manifest.json', 'site-manifest.js', 'llms.txt'):
        sp = src_root / f
        if sp.exists():
            shutil.copy(sp, out_dir / f)

    # Page sources (HTML stubs + JSON content) — preserve directory structure.
    for src in srcs:
        html = src.read_text(encoding='utf-8')
        rel = src.relative_to(src_root)
        dest_html = out_dir / rel
        dest_html.parent.mkdir(parents=True, exist_ok=True)

        json_sibling = src.with_suffix('.json')
        if json_sibling.exists():
            json_rel = json_sibling.relative_to(src_root)
            dest_json = out_dir / json_rel
            dest_json.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(json_sibling, dest_json)
            try:
                data = json.loads(json_sibling.read_text(encoding='utf-8'))
                if isinstance(data, dict) and data.get('kind') == 'page':
                    text = extract_page_text(data)
                    title = data.get('title') or src.stem
                    html = inject_pagefind_body(html, text, title)
            except (json.JSONDecodeError, OSError):
                pass
        dest_html.write_text(html, encoding='utf-8')


def build_kit_bundle(src_root: Path) -> str | None:
    """Assemble the project's kit.json + active domain glossary/extref files
    into one JSON blob for inlining into standalone builds. Returns None
    if no kit.json is present (no glossary to inline).
    """
    kit_json_path = src_root / 'kit.json'
    if not kit_json_path.exists():
        return None
    try:
        kit_data = json.loads(kit_json_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None

    domains = kit_data.get('domains') or []
    glossary = {}
    extrefs = {}

    for domain in domains:
        g_path = KIT_ROOT / 'glossary' / f'{domain}.json'
        if g_path.exists():
            try:
                g_data = json.loads(g_path.read_text(encoding='utf-8'))
                if g_data.get('entries'):
                    glossary[domain] = g_data['entries']
            except (json.JSONDecodeError, OSError):
                pass
        e_path = KIT_ROOT / 'extrefs' / f'{domain}.json'
        if e_path.exists():
            try:
                e_data = json.loads(e_path.read_text(encoding='utf-8'))
                if e_data.get('entries'):
                    extrefs[domain] = e_data['entries']
            except (json.JSONDecodeError, OSError):
                pass

    bundle = {
        'kit': kit_data,
        'glossary': glossary,
        'extrefs': extrefs,
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
        return s.replace('</script', '<\\/script')

    css = (KIT_ROOT / 'chrome.css').read_text(encoding='utf-8')
    boot = _safe_js((KIT_ROOT / 'chrome-boot.js').read_text(encoding='utf-8'))
    main = _safe_js((KIT_ROOT / 'chrome.js').read_text(encoding='utf-8'))
    renderer = _safe_js((KIT_ROOT / 'renderer.js').read_text(encoding='utf-8'))
    kit_bundle = build_kit_bundle(src_root)  # may be None

    for src in srcs:
        html = src.read_text(encoding='utf-8')
        html = LINK_TO_KIT_CSS.sub(lambda m: f'<style>\n{css}\n</style>', html, count=1)
        html = SCRIPT_TO_KIT_BOOT.sub(lambda m: f'<script>\n{boot}\n</script>', html, count=1)
        html = SCRIPT_TO_KIT_MAIN.sub(lambda m: f'<script>\n{main}\n</script>', html, count=1)
        html = SCRIPT_TO_KIT_RENDERER.sub(lambda m: f'<script>\n{renderer}\n</script>', html, count=1)

        # Inline the JSON page content so autoBoot finds it offline.
        json_sibling = src.with_suffix('.json')
        if json_sibling.exists():
            data_text = json_sibling.read_text(encoding='utf-8')
            # Escape </script in the JSON to be safe inside an inline script.
            safe = data_text.replace('</script', '<\\/script')
            inline = f'<script type="application/json" id="__htmldoc_page__">{safe}</script>'
            # Inline the kit bundle (project kit.json + active domain
            # glossary/extref entries) so tooltips work offline.
            if kit_bundle:
                safe_bundle = kit_bundle.replace('</script', '<\\/script')
                inline += f'\n<script type="application/json" id="__htmldoc_kit_bundle__">{safe_bundle}</script>'
            # Lambda replacement avoids re.sub interpreting \n in the JSON
            # content as a backslash escape and turning it into a newline.
            html = _BODY_CLOSE_RE.sub(lambda m: inline + '\n</body>', html, count=1)

        # Preserve directory structure relative to src_root.
        rel = src.relative_to(src_root)
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding='utf-8')


def cmd_build(args: argparse.Namespace) -> int:
    root = Path.cwd()
    srcs = find_html_files(root)
    json_pages = find_json_pages(root)
    if not srcs and not json_pages:
        print(f'✗ No .html or page-JSON files found in {root}', file=sys.stderr)
        return 1

    # Always regenerate manifest + llms.txt + markdown twins so <page-nav>
    # + AI consumers see fresh state. Write them at the docs root (the
    # closest common parent of JSON pages) so chrome.js's fetch URL —
    # __htmldocDocsRoot + 'site-manifest.json' — resolves naturally.
    docs_dir = _common_docs_dir(root, json_pages)
    manifest_path = build_manifest(docs_dir)
    llms_path = build_llms_txt(docs_dir)
    md_count = build_markdown_twins(docs_dir)
    print(f'✓ Wrote {manifest_path.relative_to(root)} ({len(json_pages)} JSON page(s))')
    print(f'✓ Wrote {llms_path.relative_to(root)} (sitemap for LLM consumers)')
    if md_count:
        print(f'✓ Wrote {md_count} page.md twin(s) (LLM-readable markdown per page)')

    # Schema validation — soft-fails without jsonschema.
    if _HAS_JSONSCHEMA:
        schema_errors = validate_pages(json_pages)
        if schema_errors:
            print(f'! Schema validation: {len(schema_errors)} issue(s):')
            for p, msg in schema_errors:
                print(f'    {p.relative_to(root)} — {msg}')
        else:
            print(f'✓ Schema validation: {len(json_pages)} page(s) clean')
    elif json_pages:
        print('  (schema validation skipped — `pip install jsonschema` to enable)')

    if not srcs:
        return 0

    dist = root / 'dist'
    standalone = dist / 'standalone'
    site = dist / 'site'

    # Clean previous outputs to avoid stale files
    if standalone.exists():
        shutil.rmtree(standalone)
    if site.exists():
        shutil.rmtree(site)

    build_standalone(srcs, standalone, root)
    build_site(srcs, site, root)

    # Pagefind search index — soft-fail if pagefind isn't installed.
    if pagefind_index(site):
        print(f'✓ Pagefind index built: dist/site/pagefind/')

    print(f'✓ Built {len(srcs)} HTML file(s):')
    print()
    print('  standalone (inline, send-as-file):')
    for src in srcs:
        report('', standalone / src.name)
    print()
    print('  site (shared assets, multi-page):')
    report('site root:', site)
    for src in srcs:
        report('', site / src.name)
    return 0


# ---------- serve ----------
def find_project_root(start: Path) -> Path:
    """Walk up to find the directory containing docs/_kit; fallback to start."""
    cur = start.resolve()
    for ancestor in [cur, *cur.parents]:
        if (ancestor / 'docs' / '_kit').exists():
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
    has_bin = bool(shutil.which('pagefind') or shutil.which('npx'))
    if not has_bin:
        print('! Search disabled — install pagefind (brew install pagefind) '
              'or pass --no-search to silence this notice.')
        return False
    docs_dir = _common_docs_dir(root, pages)
    htmls = [p for p in find_html_files(docs_dir) if 'dist' not in p.parts]
    if not htmls:
        return False
    target = root / 'dist' / '_search' / 'site'
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
    pf_src = target / 'pagefind'
    pf_link = docs_dir / 'pagefind'
    if pf_src.exists():
        try:
            if pf_link.is_symlink() or pf_link.exists():
                if pf_link.is_symlink():
                    pf_link.unlink()
                elif pf_link.is_dir():
                    shutil.rmtree(pf_link)
            pf_link.symlink_to(pf_src.resolve())
            print(f'✓ Search index ready: {pf_link.relative_to(root)} ({len(htmls)} page(s))')
            return True
        except OSError as e:
            print(f'! Search index built but link failed: {e}')
    return False


# ---------- Live-reload (SSE + filesystem watcher) ----------
_SSE_CLIENTS: list = []
_SSE_LOCK = threading.Lock()


def _sse_broadcast(msg: str = 'change') -> None:
    """Push a message to every connected SSE client. Best-effort — slow or
    disconnected clients are silently dropped on the next sweep when the
    handler thread observes the broken socket."""
    with _SSE_LOCK:
        for q in list(_SSE_CLIENTS):
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass


_WATCH_SKIP = {'dist', '_kit', '.git', 'node_modules', '.venv', 'venv', '__pycache__', '.idea'}
_WATCH_SKIP_SUFFIX = {'.pyc', '.swp', '.tmp'}
_WATCH_SKIP_NAMES = {'.DS_Store', 'site-manifest.json', 'llms.txt'}  # avoid feedback loop


def _snapshot_tree(root: Path) -> dict:
    """Map every file under root → mtime, skipping generated / VCS dirs.
    Excludes site-manifest.json + llms.txt to avoid the rebuild→change loop."""
    state = {}
    for p in root.rglob('*'):
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
        try:
            # Write generated artifacts at the docs root (same logic as the
            # one-shot path in cmd_serve), not at the project root.
            pages_now = find_json_pages(root)
            docs_dir = _common_docs_dir(root, pages_now)
            build_manifest(docs_dir)
            build_llms_txt(docs_dir)
            build_markdown_twins(docs_dir)
        except OSError:
            pass
        _sse_broadcast('change')


def _make_serve_handler(root: Path):
    """Subclass SimpleHTTPRequestHandler with a /__reload SSE endpoint and
    quiet logging for the keepalive ticks."""

    class _Handler(http.server.SimpleHTTPRequestHandler):
        # Serve from the captured root regardless of process cwd changes
        # later in the lifetime.
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def do_GET(self) -> None:  # noqa: N802 — base API
            if self.path == '/__reload':
                self._serve_reload_stream()
                return
            super().do_GET()

        def _serve_reload_stream(self) -> None:
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache, no-transform')
                self.send_header('Connection', 'keep-alive')
                self.send_header('X-Accel-Buffering', 'no')
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                return
            q: queue.Queue = queue.Queue(maxsize=8)
            with _SSE_LOCK:
                _SSE_CLIENTS.append(q)
            try:
                self.wfile.write(b': hello\n\n')
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=25)
                        self.wfile.write(f'data: {msg}\n\n'.encode('utf-8'))
                        self.wfile.flush()
                    except queue.Empty:
                        # keepalive comment — many proxies drop idle SSE
                        # connections after 30s; 25s is well inside that.
                        self.wfile.write(b': keepalive\n\n')
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
                first = args[0] if args else ''
                if '/__reload' in str(first):
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
        rel_user = Path('.')
    user_prefix = (root / rel_user).resolve()

    direct = user_prefix / 'index.html'
    if direct.exists():
        return direct
    under_user = [h for h in htmls if str(h.resolve()).startswith(str(user_prefix))]
    for h in under_user:
        if h.name == 'index.html':
            return h
    if under_user:
        return under_user[0]
    skipped = {'_internal', 'templates', 'examples'}
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
            httpd = http.server.ThreadingHTTPServer(('', port), handler_cls)
            break
        except OSError:
            port += 1
            if port > 9900:
                print('✗ Could not find a free port in 9876–9900', file=sys.stderr)
                return 1
    assert httpd is not None
    httpd.daemon_threads = True  # let Ctrl-C terminate hung SSE threads cleanly

    # Generated artifacts (site-manifest, llms.txt, page.md twins) belong
    # at the docs root — the directory the runtime's __htmldocDocsRoot
    # resolves to — not at the chdir'd project root. Writing at the
    # project root would pollute git status and produce a manifest at the
    # wrong URL prefix for chrome.js's fetch.
    pages_for_root = find_json_pages(root)
    docs_dir = _common_docs_dir(root, pages_for_root)
    try:
        manifest_path = build_manifest(docs_dir)
        llms_path = build_llms_txt(docs_dir)
        md_count = build_markdown_twins(docs_dir)
        print(f'✓ Refreshed site-manifest: {manifest_path.relative_to(root)}')
        print(f'✓ Refreshed llms.txt:       {llms_path.relative_to(root)}')
        if md_count:
            print(f'✓ Refreshed page.md twins: {md_count} file(s)')
    except OSError as e:
        print(f'! Could not write manifest/llms.txt: {e}', file=sys.stderr)

    htmls = sorted(p for p in root.rglob('*.html') if 'dist' not in p.parts and 'node_modules' not in p.parts)

    # Serve-time Pagefind index (background, best-effort) so search works
    # without requiring the user to run `html-doc build` first.
    search_enabled = not getattr(args, 'no_search', False)
    if search_enabled:
        threading.Thread(target=_build_serve_search_index, args=(root,),
                         name='html-doc-search', daemon=True).start()

    # Filesystem watcher → SSE broadcast → in-browser reload.
    watch_enabled = not getattr(args, 'no_watch', False)
    watcher_stop = threading.Event()
    watcher_thread = None
    if watch_enabled:
        watcher_thread = threading.Thread(
            target=_watcher_loop, args=(root, watcher_stop), name='html-doc-watcher', daemon=True,
        )
        watcher_thread.start()

    print(f'✓ Serving {root} on http://localhost:{port}')
    if watch_enabled:
        print(f'  Live reload: on  (SSE at /__reload — disable with --no-watch)')
    else:
        print(f'  Live reload: off')
    print(f'  Stop with Ctrl-C.')
    print()
    target = _pick_open_target(htmls, user_cwd, root)
    if htmls:
        print('  HTML files:')
        for h in htmls:
            rel = h.relative_to(root)
            marker = '  ←' if target is not None and h == target else ''
            print(f'    http://localhost:{port}/{rel}{marker}')
        if target is not None:
            webbrowser.open(f'http://localhost:{port}/{target.relative_to(root)}')
    print()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n✓ Stopped.')
        watcher_stop.set()
        httpd.shutdown()
        httpd.server_close()
    return 0


# ---------- main ----------
def main() -> int:
    parser = argparse.ArgumentParser(
        prog='html-doc',
        description='Shared HTML chrome kit. Init projects, build artifacts, serve locally.',
    )
    sub = parser.add_subparsers(dest='cmd')
    sub.add_parser('init', help='create docs/_kit symlink in the current project')
    sub.add_parser('build', help='build dist/standalone/ + dist/site/ from current dir')
    serve_parser = sub.add_parser(
        'serve',
        help='start local HTTP server so kit assets resolve correctly (live-reload by default)',
    )
    serve_parser.add_argument(
        '--no-watch', action='store_true',
        help='disable the filesystem watcher + auto-reload (serve static only)',
    )
    serve_parser.add_argument(
        '--no-search', action='store_true',
        help='skip background Pagefind index generation at startup',
    )

    args = parser.parse_args()
    if args.cmd == 'init':
        return cmd_init(args)
    if args.cmd == 'build':
        return cmd_build(args)
    if args.cmd == 'serve':
        return cmd_serve(args)
    parser.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
