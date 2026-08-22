"""A row in the tree reaches the page it names, whatever the file is
called.

The Python side of this is `test_url_safe_paths.py`, which holds the
manifest's shape. This is the half that arithmetic cannot see: the href
the tree builds from that path, the request the browser makes with it,
and the file the server hands back.

`notes#1.html` as an href points at `notes` with the fragment `1`. The
page is built, indexed and listed; the row just goes somewhere else,
and nothing anywhere reports it.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PAGE = "---\ntitle: {title}\nsummary: A page with an awkward name.\n---\n\n## Body {{#body}}\n\n{title} body text.\n"

# One per URL delimiter that has bitten: fragment, query, space.
AWKWARD = {"notes#1.md": "Hash", "what?.md": "Query", "a b.md": "Space"}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("awkward").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (d / "index.md").write_text(PAGE.format(title="Index"), encoding="utf-8")
    for name, title in AWKWARD.items():
        (d / name).write_text(PAGE.format(title=title), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


ROWS = """() => {
  const nav = document.querySelector('page-nav');
  return [...nav.querySelectorAll('.page-nav-level a[href]')].map(a => ({
    text: a.textContent.trim(),
    href: a.getAttribute('href'),
    resolved: a.href,
  }));
}"""


@pytest.fixture(scope="module")
def rows(browser, served):
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        pg.goto(f"{served}/index.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        pg.wait_for_selector("page-nav .page-nav-level a", timeout=20000)
        yield pg.evaluate(ROWS)
    finally:
        pg.close()


def test_every_row_has_a_row(rows) -> None:
    assert len(rows) >= 4, rows


@pytest.mark.parametrize("title", sorted(AWKWARD.values()))
def test_the_row_href_names_one_resource(rows, title: str) -> None:
    """A `#` in an href is a fragment and a `?` is a query — either one
    means the browser asks for a different page than the row names."""
    hit = [r for r in rows if r["text"] == title]
    assert len(hit) == 1, rows
    href = hit[0]["href"]
    assert "#" not in href and "?" not in href and " " not in href, href


@pytest.mark.parametrize("title", sorted(AWKWARD.values()))
def test_clicking_the_row_opens_that_page(browser, served, rows, title: str) -> None:
    """The end of the chain: href → request → the server's unquote →
    the file. Every link in it has to agree about the spelling."""
    hit = [r for r in rows if r["text"] == title][0]
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        response = pg.goto(hit["resolved"])
        assert response is not None and response.status == 200, hit
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        heading = pg.evaluate("() => (document.querySelector('main h1, main h2') || {}).textContent || ''")
        body = pg.evaluate("() => document.body.textContent")
        assert title in heading or (title + " body text") in body, (title, heading[:80])
    finally:
        pg.close()
