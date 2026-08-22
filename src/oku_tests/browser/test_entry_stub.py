"""The front door of a tree whose author never wrote an index.md.

`oku init` writes docs/index.html; writing index.md is optional, and a
tree of task notes usually skips it. That page then renders the site's
page list from the manifest, which is right — but it got there by
fetching `index.json`, taking a 404, and falling into the fallback from
the catch. So every reader who opened the front page of such a site saw
a red line on the console, and the one place a build error would show up
was already full of one that meant nothing.

The manifest lists every page the build wrote a source for. If it has
entries and this page is not among them, the fetch is known to fail
before it is made — the same reasoning the file:// branch has used all
along, one step earlier.
"""

from __future__ import annotations

from ._wait import page_quiet

import argparse
import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

PAGE = """---
title: {title}
order: {order}
summary: A page in a tree with no index of its own.
---

## Body {{#body}}

Text for {title}.
"""


@pytest.fixture(scope="module")
def sourceless_index(tmp_path_factory):
    docs = tmp_path_factory.mktemp("entry") / "docs"
    docs.mkdir()
    for i, name in enumerate(("one", "two"), start=1):
        (docs / f"{name}.md").write_text(PAGE.format(title=name, order=i * 10), encoding="utf-8")
    # index.html with NO index.md behind it, carrying the manifest of
    # the day `oku init` ran — before two.md existed. Both halves of the
    # bug live in that sentence.
    stale = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "one.html", "source": "one.md", "title": "one", "parent": None}],
    }
    (docs / "index.html").write_text(cli._stub_for("Documentation", inline_manifest=stale), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return docs / "dist"


@pytest.fixture(scope="module")
def site_url(sourceless_index):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(sourceless_index / "site")
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _open(page, url):
    missing: list[str] = []
    errors: list[str] = []
    page.on("response", lambda r: missing.append(r.url) if r.status == 404 else None)
    page.on("console", lambda m: errors.append(m.text[:120]) if m.type == "error" else None)
    page.goto(url, wait_until="load")
    page_quiet(page)
    return missing, errors


def test_the_front_page_asks_for_nothing_that_cannot_exist(page, site_url):
    missing, _ = _open(page, f"{site_url}/index.html")
    assert [u for u in missing if u.endswith("index.json")] == [], (
        f"the entry stub still fetches a page source it has none of: {missing}"
    )


def test_it_still_renders_the_page_list(page, site_url):
    """Skipping the fetch must not skip the fallback it was falling into."""
    _open(page, f"{site_url}/index.html")
    links = page.eval_on_selector_all('main a[href$=".html"]', "els => els.map(e => e.getAttribute('href'))")
    assert sorted(links) == ["one.html", "two.html"], links


def test_the_page_list_is_this_build_s_and_not_the_one_init_wrote(page, site_url):
    """The body list is rendered from the INLINE manifest, the sidebar
    from the fetched one, so a stale inline copy made a single page
    disagree with itself — measured on a delivered tree: three links in
    the body under a sidebar of four."""
    _open(page, f"{site_url}/index.html")
    body = page.eval_on_selector_all('main a[href$=".html"]', "els => els.map(e => e.getAttribute('href'))")
    tree = page.eval_on_selector_all(
        "page-nav .page-nav-tree a", "els => els.map(e => new URL(e.href).pathname.slice(1))"
    )
    assert sorted(body) == sorted(tree), f"body {sorted(body)} vs sidebar {sorted(tree)}"


def test_a_real_page_still_fetches_its_source(page, site_url):
    """The skip is scoped by the manifest, not by being an index."""
    missing, errors = _open(page, f"{site_url}/one.html")
    assert "Text for one." in page.inner_text("main")
    assert [u for u in missing if u.endswith("one.json")] == [], missing
