"""A page inside an editor opens files in the editor: `window.__okuHost`.

The IntelliJ plugin's preview shows the kit in a panel beside the source.
A file chip there opened the kit's own viewer inside that narrow panel, and
reaching the real file took a second click, at line 1 whatever line the
reference named. The embedder now sets `window.__okuHost.openFile(path,
line)` and the kit asks it first, with the file's full path.

The full path is the other half. `oku preview` writes the page into the
editor's own directory, not under the tree's dist/, so the kit could not
derive where the project is and knew no full path at all: the viewer showed
the path as authored and offered no editor. The preview's inlined manifest
carries the tree's path (`root_abs`), and the page finds its own place in
it by the suffix of its URL.

Built with `oku preview`, which is what the plugin shows.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ._wait import page_quiet

PAGE = """---
title: Host
---

## Files {#files}

The loader is in [x.py](#f/src/x.py:3).

<div class="links">
<a href="notes.md">the notes</a>
<a class="at" href="notes.md#%C3%B6zet">the summary</a>
</div>
"""

RECORDING_HOST = """(answer) => {
  window.__okuHostCalls = [];
  window.__okuHost = {
    name: 'Test IDE',
    openFile: function (path, line, anchor) {
      window.__okuHostCalls.push([path, line, anchor]);
      if (answer === 'throw') throw new Error('no editor');
      return answer;
    },
  };
}"""


@pytest.fixture(scope="module")
def preview(tmp_path_factory) -> dict:
    project = tmp_path_factory.mktemp("host")
    (project / ".git").mkdir()
    (project / "src").mkdir()
    (project / "src" / "x.py").write_text(
        "".join(f"line_{i} = {i}\n" for i in range(1, 11)), encoding="utf-8"
    )
    docs = project / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name": "h"}', encoding="utf-8")
    (docs / "notes.md").write_text("---\ntitle: Notes\n---\n\nSome notes.\n", encoding="utf-8")
    (docs / "page.md").write_text(PAGE, encoding="utf-8")
    # No file chip: the page carries no files, and its place in the project
    # was written only beside them.
    (docs / "plain.md").write_text(
        '---\ntitle: Plain\n---\n\n<div class="links"><a href="notes.md#x">notes</a></div>\n',
        encoding="utf-8",
    )
    out = {
        "x": (project / "src" / "x.py").resolve().as_posix(),
        "notes": (docs / "notes.md").resolve().as_posix(),
    }
    for key, name in (("html", "page.md"), ("plain", "plain.md")):
        done = subprocess.run(
            [sys.executable, "-m", "oku.cli", "preview", str(docs / name), "--out", str(project / "out")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        assert done.returncode == 0, done.stderr
        out[key] = json.loads(done.stdout)["html"]
    return out


@pytest.fixture
def page(browser, preview):
    context = browser.new_context(viewport={"width": 1100, "height": 900})
    pg = context.new_page()
    pg.goto(Path(preview["html"]).as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    context.close()


def _viewer_open(page) -> bool:
    return page.evaluate("() => !!document.querySelector('.okt-mdview-path')")


def test_the_preview_knows_the_files_full_path(page, preview) -> None:
    page.click("oku-filepath .okt-fp-label")
    page.wait_for_selector(".okt-mdview-path")
    assert page.get_attribute(".okt-mdview-path", "title") == preview["x"]


def test_a_host_opens_the_chip_on_its_line_instead_of_the_viewer(page, preview) -> None:
    page.evaluate(RECORDING_HOST, True)
    page.click("oku-filepath .okt-fp-label")
    page.wait_for_timeout(200)
    assert page.evaluate("() => window.__okuHostCalls") == [[preview["x"], 3, None]]
    assert not _viewer_open(page)


def test_the_keyboard_reaches_the_host_too(page, preview) -> None:
    page.evaluate(RECORDING_HOST, True)
    page.focus("oku-filepath .okt-fp-label")
    page.keyboard.press("Enter")
    page.wait_for_timeout(200)
    assert page.evaluate("() => window.__okuHostCalls") == [[preview["x"], 3, None]]


@pytest.mark.parametrize("answer", [False, "throw"])
def test_a_host_that_cannot_open_it_leaves_the_kits_viewer(page, preview, answer) -> None:
    page.evaluate(RECORDING_HOST, answer)
    page.click("oku-filepath .okt-fp-label")
    page.wait_for_selector(".okt-mdview-path")
    assert page.evaluate("() => window.__okuHostCalls.length") == 1


def test_a_link_to_a_markdown_file_goes_to_the_host(page, preview) -> None:
    page.evaluate(RECORDING_HOST, True)
    page.click(".links a:not(.at)")
    page.wait_for_timeout(200)
    assert page.evaluate("() => window.__okuHostCalls") == [[preview["notes"], None, None]]
    assert not _viewer_open(page)


def test_a_link_to_a_heading_hands_the_host_its_id(page, preview) -> None:
    """`notes.md#özet` used to reach the host as the file alone, so the
    editor opened at the top of it. The id goes with it, decoded: the host
    asks oku which line carries it."""
    page.evaluate(RECORDING_HOST, True)
    page.click(".links a.at")
    page.wait_for_timeout(200)
    assert page.evaluate("() => window.__okuHostCalls") == [[preview["notes"], None, "özet"]]


def test_a_page_with_no_file_chip_hands_its_links_to_the_host_too(browser, preview) -> None:
    """The page's place in the project (`m._rel`) was written only on a page
    carrying `#f/` files, so a page without one knew no full path: a `.md`
    link there opened the kit's viewer in the editor's narrow panel, and the
    host was never asked. Found in the IntelliJ sandbox, on a page that
    linked another page and named no file."""
    context = browser.new_context(viewport={"width": 1100, "height": 900})
    pg = context.new_page()
    try:
        pg.goto(Path(preview["plain"]).as_uri(), wait_until="load")
        page_quiet(pg)
        pg.evaluate(RECORDING_HOST, True)
        pg.click(".links a")
        pg.wait_for_timeout(200)
        assert pg.evaluate("() => window.__okuHostCalls") == [[preview["notes"], None, "x"]]
        assert not _viewer_open(pg)
    finally:
        context.close()
