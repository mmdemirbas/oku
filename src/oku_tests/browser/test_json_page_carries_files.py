"""A page written as JSON carries the files its `#f/` references name.

The bytes of a referenced file travel inside the page, because no
delivery mode can fetch them when the reader clicks. Only a `.md` source
went through the one function that attaches them, so a page that is JSON
on disk — v2, or v1 written by a project's own generator — rendered
every chip with nothing behind it: `data-status="unknown"`, no preview,
nothing to open. `oku check` resolved the same references and reported
nothing, and its `path-in-code-span` nudge recommended the chip that
could not work there. Found on a delivered research page whose file table
was turned into chips and came out dead in all three modes.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

NOTE = "# Note\n\nA note the table points at.\n"
TOOL = "def f():\n    return 1\n"

V2 = {
    "k": "page",
    "t": "Version two",
    "b": ["## Files {#files}", "The tool is [`tool.py`](#f/../src/tool.py)."],
}

# The shape a generator writes: a v1 table whose cell is an inline link.
V1 = {
    "kind": "page",
    "title": "Version one",
    "blocks": [
        {
            "kind": "section",
            "id": "files",
            "title": "Files",
            "blocks": [
                {
                    "kind": "table",
                    "headers": ["File", "What"],
                    "rows": [
                        [[{"kind": "link", "href": "#f/../src/note.md", "text": "`note.md`"}], "a note"]
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    root = tmp_path_factory.mktemp("jsonfiles") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "note.md").write_text(NOTE, encoding="utf-8")
    (root / "src" / "tool.py").write_text(TOOL, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "v2.json").write_text(json.dumps(V2), encoding="utf-8")
    (docs / "v1.json").write_text(json.dumps(V1), encoding="utf-8")
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "_oku").symlink_to(Path(cli.__file__).resolve().parents[2] / "kit", target_is_directory=True)
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs


def _serve(root: Path, handler):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


CHIPS = """() => [...document.querySelectorAll('main .okt-fp')].map(c => ({
  path: c.getAttribute('path'), status: c.getAttribute('data-status'),
  text: ((window.__okuFiles || {})[c.getAttribute('path')] || {}).text || null }))"""


def _chips(browser, url: str):
    pg = browser.new_page()
    try:
        pg.goto(url, wait_until="load")
        page_quiet(pg)
        return pg.evaluate(CHIPS)
    finally:
        pg.close()


EXPECT = {"v2": ("../src/tool.py", TOOL), "v1": ("../src/note.md", NOTE)}


@pytest.mark.parametrize("name", ["v2", "v1"])
def test_standalone(browser, tree, name) -> None:
    got = _chips(browser, (tree / "dist" / "standalone" / f"{name}.html").as_uri())
    path, text = EXPECT[name]
    # A table cell is drawn again by each of the table's views; every copy
    # is the same chip and every one must resolve.
    assert got and all(c == {"path": path, "status": "ok", "text": text} for c in got), got


@pytest.mark.parametrize("name", ["v2", "v1"])
def test_site(browser, tree, name) -> None:
    import functools

    site = tree / "dist" / "site"
    httpd = _serve(site, functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site)))
    try:
        got = _chips(browser, f"http://127.0.0.1:{httpd.server_address[1]}/{name}.html")
    finally:
        httpd.shutdown()
    path, text = EXPECT[name]
    # A table cell is drawn again by each of the table's views; every copy
    # is the same chip and every one must resolve.
    assert got and all(c == {"path": path, "status": "ok", "text": text} for c in got), got


@pytest.mark.parametrize("name", ["v2", "v1"])
def test_serve(browser, tree, name) -> None:
    httpd = _serve(tree, cli._make_serve_handler(tree))
    try:
        got = _chips(browser, f"http://127.0.0.1:{httpd.server_address[1]}/{name}.html")
    finally:
        httpd.shutdown()
    path, text = EXPECT[name]
    # A table cell is drawn again by each of the table's views; every copy
    # is the same chip and every one must resolve.
    assert got and all(c == {"path": path, "status": "ok", "text": text} for c in got), got


def test_the_page_file_on_disk_is_not_rewritten(tree) -> None:
    """Carrying is done on the way out; the author's (or generator's)
    file is theirs."""
    assert json.loads((tree / "v1.json").read_text(encoding="utf-8")) == V1
    assert json.loads((tree / "v2.json").read_text(encoding="utf-8")) == V2
