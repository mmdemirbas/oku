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
