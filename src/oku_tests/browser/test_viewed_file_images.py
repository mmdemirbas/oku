"""A viewed file shows its own images, in every delivery mode.

The build half is `test_viewed_file_images.py` beside this package. This
half is the reader's: a note opened from a chip, and a file opened from
the note, each showing the picture that sits beside IT. The page and
the note both hold an `img/dot.svg`, 10 and 30 pixels wide, so a viewer
that resolves the note's reference against the page shows a picture
rather than a broken one, and only its width says it is the wrong file.
That is what every mode did: standalone through the page-wide rewrite,
the two served modes by resolving the relative `src` against the page's
URL.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from .. import test_viewed_file_images as build_half
from ._wait import page_quiet

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("viewedimages")
    root = build_half.make_project(tmp)
    docs = root / "docs"
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return root


def _static(directory: Path):
    handler = type(
        "H",
        (http.server.SimpleHTTPRequestHandler,),
        {
            "__init__": lambda s, *a, **k: http.server.SimpleHTTPRequestHandler.__init__(
                s, *a, directory=str(directory), **k
            ),
            "log_message": lambda *a: None,
        },
    )
    return handler


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
        yield page
    finally:
        context.close()
        if httpd:
            httpd.shutdown()


def _open_chip(page, name: str, inside_viewer: bool = False) -> None:
    scope = ".okt-mdview-body " if inside_viewer else "main "
    chip = next(
        el
        for el in page.query_selector_all(f"{scope}.okt-fp[data-status='ok'] .okt-fp-label")
        if el.inner_text().strip() == name and el.is_visible()
    )
    chip.click()
    page.wait_for_function(
        "(n) => { const w = document.querySelector('.okt-mdview');"
        " return w && [...w.querySelectorAll('.okt-viewer-crumbs li')].pop().textContent.trim() === n; }",
        arg=name,
    )


# The images in the file the viewer is showing: the rendered view of the
# newest item in its trail, the only one on screen.
IMAGES = """() => {
  const w = document.querySelector('.okt-mdview');
  const shown = w && [...w.querySelectorAll('.okt-mdview-rendered')].filter((n) => n.offsetParent !== null).pop();
  return shown ? [...shown.querySelectorAll('img')].map((i) => ({
    alt: i.alt, done: i.complete, width: i.naturalWidth })) : [];
}"""


def _images(page) -> dict[str, dict]:
    # `complete` is true for a picture that failed too; the width says which.
    page.wait_for_function(
        f"() => {{ const s = ({IMAGES})(); return s.length > 0 && s.every((i) => i.done); }}"
    )
    return {i["alt"]: i for i in page.evaluate(IMAGES)}


def test_a_viewed_note_shows_the_picture_beside_it(opened):
    _open_chip(opened, "note.md")
    shown = _images(opened)
    assert shown["note dot"]["width"] == 30, shown


def test_the_source_view_shows_the_file_as_written(opened):
    _open_chip(opened, "note.md")
    source = opened.evaluate(
        "() => [...document.querySelectorAll('.okt-mdview-source code')].pop().textContent"
    )
    assert "![note dot](img/dot.svg)" in source
    # The rewrite put an image's bytes where its path was; neither the
    # page's dot nor the note's may be in the text.
    for svg in (build_half.PAGE_DOT, build_half.NOTE_DOT):
        assert base64.b64encode(svg.encode()).decode() not in source


def test_a_file_opened_from_the_note_shows_its_own_picture(opened):
    """deeper.md's image sits above the docs tree, where no served mode
    can reach it and only the carried bytes can."""
    _open_chip(opened, "note.md")
    _open_chip(opened, "deeper.md", inside_viewer=True)
    shown = _images(opened)
    assert shown["deep"]["width"] == 50, shown


def test_a_srcset_is_read_the_way_the_browser_reads_it(opened):
    """A relative candidate finds the carried image; an authored data:
    URI, whose comma a split on commas would cut, is left whole."""
    _open_chip(opened, "note.md")
    shown = _images(opened)
    assert shown["set"]["width"] == 30, shown
    assert shown["inline"]["width"] == 50, shown
