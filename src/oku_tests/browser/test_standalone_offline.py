"""A standalone artifact must be fully usable opened straight off disk.

`dist/standalone/` exists to be mailed, dropped in a chat, or opened by
double-clicking — no server. That path has failure modes an http-served
page never shows: `fetch` and dynamic `import` against a `file://` URL
are blocked as cross-origin, so anything the kit reaches for at runtime
has to be inlined or skipped.

These tests open the built file over file:// and require that the page
asks for nothing it cannot get: zero failed requests to its own
resources, zero console errors, every primitive rendered. Requests to
the two CDNs the kit uses (Prism, Mermaid, the webfonts) are excluded —
their absence is a network condition, not a defect in the artifact.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

CDN = re.compile(r"jsdelivr|googleapis|gstatic", re.IGNORECASE)

PAGE_MD = """---
title: Offline
summary: Opened straight off disk.
---

> [!TLDR]
> Everything below has to work with no server.

## Tables and code {#surfaces}

| col | val |
|---|---|
| a | 1 |
| b | 2 |

```python
def f(x):
    return x + 1
```

## More {#more}

Plain prose with `code` and *emphasis*.
"""


@pytest.fixture(scope="module")
def standalone_file(tmp_path_factory):
    docs = tmp_path_factory.mktemp("offline") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Offline"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    out = docs / "dist" / "standalone" / "page.html"
    assert out.exists(), "standalone build produced no page"
    return out


def _load(page, url):
    console, failed = [], []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed.append(r.url))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(url, wait_until="load")
    page.wait_for_timeout(2500)
    return (
        [c for c in console if not CDN.search(c)],
        [f for f in failed if not CDN.search(f)],
    )


def test_standalone_over_file_url_asks_for_nothing_it_cannot_get(page, standalone_file):
    console, failed = _load(page, standalone_file.as_uri())
    assert failed == [], f"failed requests over file://: {failed}"
    assert console == [], f"console errors over file://: {console}"


def test_standalone_renders_its_primitives_off_disk(page, standalone_file):
    page.goto(standalone_file.as_uri(), wait_until="load")
    page.wait_for_timeout(2500)
    got = page.evaluate(
        """() => ({
        sections:  document.querySelectorAll('section').length,
        tables:    document.querySelectorAll('.okt-table-wrap').length,
        codeLines: document.querySelectorAll('pre code > .okt-code-line').length,
        drawer:    !!document.querySelector('.ctrl-btn.drawer-toggle'),
        navLinks:  document.querySelectorAll('page-nav a').length,
    })"""
    )
    assert got["sections"] >= 2, got
    assert got["tables"] == 1, got
    assert got["codeLines"] >= 2, got
    assert got["drawer"] is True, got
    assert got["navLinks"] >= 2, got


def test_standalone_search_falls_back_to_this_file(page, standalone_file):
    """No site index can exist inside one self-contained file, so search
    is page-scoped — and must say so as the normal state, not as a
    missing-index fault."""
    page.goto(standalone_file.as_uri(), wait_until="load")
    page.wait_for_timeout(2000)
    got = page.evaluate(
        """async () => {
        document.querySelector('.ctrl-btn[class*=search]').click();
        await new Promise(r => setTimeout(r, 400));
        const i = document.querySelector('.search-input');
        i.value = 'prose';
        i.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(r => setTimeout(r, 1200));
        return { results: document.querySelectorAll('.search-results li').length,
                 status: (document.querySelector('.search-status') || {}).textContent || '' };
    }"""
    )
    assert got["results"] >= 1, got
    assert "this file only" in got["status"], got
    assert "unavailable" not in got["status"].lower(), got


# ---------- the entry stub ----------
#
# `oku init` writes `index.html` on every run but `index.md` only when
# the tree has no page source yet — so a docs tree whose pages already
# existed gets an entry stub with nothing behind it. It carries the site
# manifest inline for the drawer; rendering nothing else left the front
# door of the tree blank, with a fetch error in the console, and the
# reader had to guess the Contents button held the site.

ENTRY_MANIFEST = {
    "schema_version": 1,
    "root": ".",
    "pages": [
        {
            "path": "one.html",
            "source": "one.md",
            "title": "First page",
            "parent": None,
            "summary": "What the first page covers.",
        },
        {"path": "two.html", "source": "two.md", "title": "Second page", "parent": None},
        {"path": "index.html", "source": None, "title": "Documentation", "parent": None},
    ],
}


@pytest.fixture(scope="module")
def entry_tree(tmp_path_factory):
    docs = tmp_path_factory.mktemp("entry") / "docs"
    docs.mkdir()
    (docs / "_oku").symlink_to(Path(__file__).resolve().parents[3] / "kit", target_is_directory=True)
    for name in ("one", "two"):
        (docs / f"{name}.md").write_text(
            f"---\ntitle: {name}\n---\n\n## Body {{#body}}\n\nText.\n", encoding="utf-8"
        )
    (docs / "index.html").write_text(
        cli._stub_for("Documentation", inline_manifest=ENTRY_MANIFEST), encoding="utf-8"
    )
    return docs


def test_entry_stub_renders_the_page_list_off_disk(page, entry_tree):
    console = []
    page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
    page.goto((entry_tree / "index.html").as_uri(), wait_until="load")
    page.wait_for_timeout(2000)

    got = page.evaluate(
        """() => ({
        heading: (document.querySelector('#pages h2, h2') || {}).textContent || null,
        links: [...document.querySelectorAll('main a[href$=".html"]')].map(a => a.getAttribute('href')),
        text: (document.querySelector('main') || {}).textContent || '',
    })"""
    )
    assert got["links"] == ["one.html", "two.html"], got
    assert "What the first page covers." in got["text"], got
    # The index links to the pages, not to itself.
    assert "index.html" not in got["links"], got
    assert [c for c in console if not CDN.search(c)] == [], console


def test_missing_page_source_still_reports_on_a_content_page(page, entry_tree):
    """The page-list fallback is scoped to the index. Anywhere else a
    missing page source is a real failure and has to say so, rather than
    quietly showing a table of contents in its place."""
    stray = entry_tree / "one.html"
    stray.write_text(cli._stub_for("First page", inline_manifest=ENTRY_MANIFEST), encoding="utf-8")
    console = []
    page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
    page.goto(stray.as_uri(), wait_until="load")
    page.wait_for_timeout(1500)

    reported = [c for c in console if "page-source-unreachable" in c]
    assert reported, f"a missing page source was not reported: {console}"
    listed = page.evaluate("""[...document.querySelectorAll('main a[href$=".html"]')].length""")
    assert listed == 0, "the index fallback rendered on a content page"
