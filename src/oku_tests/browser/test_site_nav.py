"""Site-tree navigation regressions for the built `dist/site` layout.

The standard project shape — every page under `docs/`, nothing at the
root — used to render an empty sidebar reading "Run oku serve for full
site navigation" on a site whose manifest had loaded fine: the tree
builder indexed the root level's page bucket, which does not exist when
no page sits at the root, and the resulting TypeError was swallowed by
the manifest loader's catch. The repo's own docs never showed it because
its pages are scattered across the root.

The fixture mirrors what `oku build` writes: `_oku/` and
`site-manifest.json` at the site root, pages one directory down.
"""

from __future__ import annotations

import http.server
import json
import threading
from functools import partial
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PAGES = [
    {"path": "docs/index.html", "source": "docs/index.md", "title": "Giriş", "parent": "docs"},
    {
        "path": "docs/deep/nested.html",
        "source": "docs/deep/nested.md",
        "title": "Derin",
        "parent": "docs/deep",
    },
]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    d = tmp_path_factory.mktemp("site")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "site-manifest.json").write_text(
        json.dumps({"schema_version": 1, "root": ".", "pages": PAGES}, ensure_ascii=False),
        encoding="utf-8",
    )
    for entry in PAGES:
        html_path = d / entry["path"]
        html_path.parent.mkdir(parents=True, exist_ok=True)
        depth = len(Path(entry["path"]).parts) - 1
        html_path.write_text(cli._retarget_kit_urls(cli._stub_for(entry["title"]), depth), encoding="utf-8")
        page = {"k": "page", "t": entry["title"], "b": ["## Bölüm {#b}\n\nMetin.\n"]}
        html_path.with_suffix(".json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_site_tree_lists_pages_that_all_live_below_the_root(page, site):
    page.goto(f"{site}/docs/index.html")
    page.wait_for_timeout(1200)
    links = page.eval_on_selector_all(".page-nav-tree a", "els => els.map(e => e.textContent)")
    assert "Giriş" in links and "Derin" in links, links
    assert page.locator(".page-nav-empty").count() == 0


def test_site_tree_link_targets_are_reachable_paths(page, site):
    page.goto(f"{site}/docs/index.html")
    page.wait_for_timeout(1200)
    hrefs = page.eval_on_selector_all(".page-nav-tree a", "els => els.map(e => new URL(e.href).pathname)")
    assert "/docs/index.html" in hrefs
    assert "/docs/deep/nested.html" in hrefs


def test_deep_page_resolves_the_same_docs_root(page, site):
    """A page two levels down finds the same manifest — the docs root is
    wherever `_oku/` sits, not the page's own directory."""
    page.goto(f"{site}/docs/deep/nested.html")
    page.wait_for_timeout(1200)
    assert page.locator(".page-nav-empty").count() == 0
    assert page.locator(".page-nav-tree a").count() == len(PAGES)
