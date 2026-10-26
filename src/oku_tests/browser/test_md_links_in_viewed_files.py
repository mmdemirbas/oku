"""A `.md` link inside a viewed file, clicked, in every delivery mode.

The build half is `test_md_links_in_viewed_files.py` beside this package.
The note sits outside the docs tree and the page has a `sib.md` and an
`island.md` of its own, so a link resolved against the page does not
fail: it shows the page's file, and only the title says it is the wrong
one. Before the fix a click on the note's `sib` left the page, to the
page's own sibling or, where there was none, to an error page.
"""

from __future__ import annotations

import argparse
import http.server
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from .. import test_md_links_in_viewed_files as build_half
from ._wait import page_quiet

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    root = build_half.make_project(tmp_path_factory.mktemp("mdlinks"))
    cwd = Path.cwd()
    os.chdir(root / "docs")
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return root


def _static(directory: Path):
    return type(
        "H",
        (http.server.SimpleHTTPRequestHandler,),
        {
            "__init__": lambda s, *a, **k: http.server.SimpleHTTPRequestHandler.__init__(
                s, *a, directory=str(directory), **k
            ),
            "log_message": lambda *a: None,
        },
    )


@pytest.fixture(params=["standalone", "site", "serve"])
def opened(request, project, browser):
    docs = project / "docs"
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    httpd = None
    if request.param == "standalone":
        url = (docs / "dist" / "standalone" / "index.html").as_uri()
    else:
        handler = (
            _static(docs / "dist" / "site") if request.param == "site" else cli._make_serve_handler(docs)
        )
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    try:
        page.goto(url, wait_until="load")
        page_quiet(page)
        _open_note(page)
        yield page
    finally:
        context.close()
        if httpd:
            httpd.shutdown()


def _crumbs_end(page, name: str) -> None:
    page.wait_for_function(
        "(n) => { const w = document.querySelector('.okt-mdview');"
        " return w && [...w.querySelectorAll('.okt-viewer-crumbs li')].pop().textContent.trim() === n; }",
        arg=name,
    )


def _open_note(page) -> None:
    chip = next(
        el
        for el in page.query_selector_all("main .okt-fp[data-status='ok'] .okt-fp-label")
        if el.inner_text().strip() == "note.md"
    )
    chip.click()
    _crumbs_end(page, "note.md")


def _click_in_note(page, text: str) -> None:
    page.locator(".okt-mdview-rendered a", has_text=text).first.click()


SHOWN = """() => {
  const w = document.querySelector('.okt-mdview');
  const body = w && [...w.querySelectorAll('.okt-mdview-rendered')].filter((n) => n.offsetParent !== null).pop();
  return { title: body && (body.querySelector('.okt-mdview-title') || {}).textContent || null,
           failed: !!(body && body.querySelector('.okt-mdview-fail')), url: location.href };
}"""


def test_a_sibling_opens_beside_the_note_and_the_page_stays(opened):
    start = opened.url
    _click_in_note(opened, "sib")
    _crumbs_end(opened, "sib.md")
    shown = opened.evaluate(SHOWN)
    assert shown["title"] == "Note sibling", shown
    assert shown["url"] == start


def test_an_island_link_opens_the_file_beside_the_note(opened):
    """The page links an `island.md` of its own, which the standalone page
    carries keyed by that href; the note's must not be looked up there."""
    _click_in_note(opened, "island")
    _crumbs_end(opened, "island.md")
    assert opened.evaluate(SHOWN)["title"] == "Note island"


def test_a_file_only_the_note_names_opens_too(opened):
    _click_in_note(opened, "only")
    _crumbs_end(opened, "only-note.md")
    assert opened.evaluate(SHOWN)["title"] == "Only the note"


def test_a_page_of_the_tree_opens_as_that_page_at_its_heading(opened):
    _click_in_note(opened, "guide")
    opened.wait_for_function("() => /guide\\.html#part$/.test(location.href)")
    page_quiet(opened)
    assert opened.title().startswith("Guide")


def test_a_link_to_nothing_says_so_and_the_page_stays(opened):
    start = opened.url
    _click_in_note(opened, "gone")
    _crumbs_end(opened, "missing.md")
    opened.wait_for_function(f"() => ({SHOWN})().failed")
    assert opened.url == start
