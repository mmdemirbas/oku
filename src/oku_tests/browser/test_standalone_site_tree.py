"""A standalone TREE keeps its site tree; a standalone PAGE has none.

`oku build` writes one self-contained HTML per page, side by side in
`dist/standalone/`, and inlines a manifest listing exactly those files.
The sidebar used to drop the site-tree panel whenever it saw inline page
data, on the reasoning that a single file has no site to navigate — true
of a one-page build, and false of every tree, where the sibling each row
points at is sitting in the same directory and the data to build the
tree was already inlined in the file.

The rows have to survive a page in a subfolder, which is where the base
matters: `__okuDocsRoot` falls back to the page's OWN directory in a
standalone build, so `sub/three.html` would have linked its siblings as
`sub/one.html`. Both the href and the active-row marking come from the
manifest suffix match instead — the same one the language switch uses.
"""

from __future__ import annotations

from . import _wait
from ._wait import page_quiet

import argparse
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

from oku import cli

pytestmark = pytest.mark.browser


def _page(title: str, order: int) -> str:
    return f"---\ntitle: {title}\norder: {order}\n---\n\n## Body {{#body}}\n\nText for {title}.\n"


TREE = {
    "index.md": _page("Home", 10),
    "one.md": _page("One", 20),
    "two.md": _page("Two", 30),
    "sub/three.md": _page("Three", 40),
}

ROWS = """() => {
  const nav = document.querySelector('page-nav');
  const rows = nav ? [...nav.querySelectorAll('.page-nav-tree a[href]')] : [];
  return {
    panel:  !!(nav && nav.querySelector('.page-nav-panel')),
    titles: rows.map(a => a.textContent),
    hrefs:  rows.map(a => a.href),
    active: rows.filter(a => a.getAttribute('aria-current') === 'page').map(a => a.textContent),
  };
}"""


def _build(tmp_path_factory, name: str, sources: dict[str, str]) -> Path:
    docs = tmp_path_factory.mktemp(name) / "docs"
    docs.mkdir()
    for rel, text in sources.items():
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("Home"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    return docs / "dist" / "standalone"


@pytest.fixture(scope="module")
def tree_out(tmp_path_factory):
    return _build(tmp_path_factory, "tree", TREE)


@pytest.fixture(scope="module")
def lone_out(tmp_path_factory):
    return _build(tmp_path_factory, "lone", {"index.md": _page("Home", 10)})


def _open(page, path: Path):
    page.goto(path.as_uri(), wait_until="load")
    page_quiet(page)
    return page.evaluate(ROWS)


def test_a_standalone_tree_lists_its_siblings(page, tree_out):
    got = _open(page, tree_out / "index.html")
    assert got["panel"], "the site-tree panel was removed from a multi-page build"
    assert got["titles"] == ["Home", "One", "Two", "Three"], got
    assert got["active"] == ["Home"], got


def test_every_row_points_at_a_file_that_exists(page, tree_out):
    """A row whose href 404s is worse than no row: the reader cannot tell
    the link is broken until they have lost their place."""
    got = _open(page, tree_out / "index.html")
    missing = [h for h in got["hrefs"] if not Path(unquote(urlparse(h).path)).exists()]
    assert not missing, f"tree rows pointing at nothing: {missing}"


def test_a_page_in_a_subfolder_links_from_the_tree_root(page, tree_out):
    """The base is the root the manifest was built from, not the folder
    the reader happens to be standing in."""
    got = _open(page, tree_out / "sub" / "three.html")
    missing = [h for h in got["hrefs"] if not Path(unquote(urlparse(h).path)).exists()]
    assert not missing, f"tree rows pointing at nothing from a subfolder: {missing}"
    assert got["active"] == ["Three"], got
    one = [h for h in got["hrefs"] if h.endswith("one.html")]
    assert one and "/sub/one.html" not in one[0], f"sibling resolved against the subfolder: {one}"


def test_clicking_a_row_opens_that_page(page, tree_out):
    """Each file is self-contained, so the browser's own navigation is
    the right one — no fetch of a JSON file:// will not serve."""
    page.goto((tree_out / "index.html").as_uri(), wait_until="load")
    page_quiet(page)
    # The reader's path: the drawer is closed on load, so open it first —
    # the rows are off-canvas until they do.
    page.click(".ctrl-btn.drawer-toggle")
    # The rows are off-canvas until the drawer has finished sliding, and
    # clicking a row that is still moving is how this test failed inside
    # a batch and nowhere else.
    _wait.box_stable(page, ".page-nav-tree")
    page.click(".page-nav-tree a[href$='two.html']")
    page.wait_for_load_state("load")
    _wait.until(
        page,
        "() => window.__okuRendered === true && /two\\.html$/.test(location.pathname)",
        what="the second page finished rendering",
    )
    assert page.url.endswith("two.html"), page.url
    assert "Text for Two." in page.inner_text("main")


def test_a_one_page_build_has_no_tree_to_show(page, lone_out):
    """A tree of one is noise, and this is the case the old branch was
    written for."""
    got = _open(page, lone_out / "index.html")
    assert not got["panel"], "a single-page build rendered a site-tree panel"
    assert got["titles"] == [], got
