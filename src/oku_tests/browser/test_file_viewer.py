"""A file opened from a page fills the frame, says where it is, and can open the next file.

Asked for by a reader, in four parts, each held here:

  - A code file opened in a 1100 x 774 box in the middle of the screen,
    whatever the screen's size, with its own scrollbar for no reason the
    screen could see. A markdown file filled the frame. Now both fill it.
  - The preview could not be opened anywhere else and did not say where
    the file was. It shows the full path, copies it in one click, and
    opens the file — or its built page — in a new tab.
  - A file opened from a file replaced the first with no way back, and
    most chips inside a viewed file were dead: the page had carried the
    files IT named, not the ones they named. The build follows those
    references, and the frame keeps a trail with a back button.
  - None of that may put a machine's paths into the artifact. The full
    path is derived from where the page was opened, so the HTML names a
    layout and never an account.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

# Captured instead of the real clipboard: a file:// origin is opaque and
# clipboard permissions cannot be granted to it.
CLIPBOARD = """
  window.__copied = [];
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
    writeText: (t) => { window.__copied.push(t); return Promise.resolve(); } } });
"""

PROGRAM = "\n".join(f"line_{i} = {i}" for i in range(400)) + "\n"


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    root = tmp_path_factory.mktemp("viewerproj")
    (root / ".git").mkdir()
    (root / "src").mkdir()
    (root / "src" / "tool.py").write_text(PROGRAM, encoding="utf-8")
    (root / "c.txt").write_text("the third file\n", encoding="utf-8")
    docs = root / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "index.md").write_text(
        "---\ntitle: Viewer\nsummary: Files that open files.\n---\n\n"
        "## Files {#files}\n\n"
        "A note [`a.md`](#f/notes/a.md) and a program [`tool.py`](#f/../src/tool.py).\n",
        encoding="utf-8",
    )
    # b.md is named ONLY from inside a table fence in a.md: the page
    # itself never mentions it.
    (docs / "notes" / "a.md").write_text(
        "---\ntitle: Note A\nsummary: The first file.\n---\n\n## A {#a}\n\n"
        + "\n\n".join(f"Paragraph {i} of the first file." for i in range(60))
        + '\n\n```oku-table\n{"headers":["File"],"rows":[["[b.md](#f/b.md)"]]}\n```\n',
        encoding="utf-8",
    )
    (docs / "notes" / "b.md").write_text(
        "---\ntitle: Note B\nsummary: The second file.\n---\n\n## B {#b}\n\n"
        + "\n\n".join(f"Paragraph {i} of the second file." for i in range(80))
        + "\n\nAnd the third: [`c.txt`](#f/../../c.txt).\n",
        encoding="utf-8",
    )
    # The build footer's rebuild command names the build directory by
    # design, and has its own switch. Off here, so the last case can say
    # that NOTHING else in the artifact names a path on this machine.
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    for stem in ("index", "notes/a", "notes/b"):
        (docs / f"{stem}.html").write_text(cli._stub_for(stem), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return root


@pytest.fixture()
def page(project, browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    context.add_init_script(CLIPBOARD)
    pg = context.new_page()
    pg.goto((project / "docs" / "dist" / "standalone" / "index.html").as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    context.close()


STATE = """() => { const w = document.querySelector('.okt-mdview');
  if (!w || !w.isConnected) return null;
  const b = w.getBoundingClientRect();
  return { w: Math.round(b.width), h: Math.round(b.height), kind: w.dataset.kind,
    depth: +w.dataset.depth, crumbs: [...w.querySelectorAll('.okt-viewer-crumbs li')].map(l => l.textContent.trim()),
    back: !w.querySelector('.okt-viewer-back').hidden,
    path: w.querySelector('.okt-mdview-path').textContent,
    open: (w.querySelector('.okt-mdview-open') || {}).href || null,
    scroll: w.querySelector('.okt-mdview-body').scrollTop,
    title: (w.querySelector('.okt-mdview-body .okt-mdview-title') || {}).textContent || null }; }"""


def _chip(page, name, inside_viewer=False):
    scope = ".okt-mdview-body " if inside_viewer else "main "
    sel = f"{scope}.okt-fp[data-status='ok'] .okt-fp-label"
    for el in page.query_selector_all(sel):
        if el.inner_text().strip() == name and el.is_visible():
            return el
    raise AssertionError(f"no visible, resolved chip named {name!r} in {scope.strip()}")


def _open(page, name, inside_viewer=False):
    _chip(page, name, inside_viewer).click()
    page.wait_for_function(
        "(n) => { const w = document.querySelector('.okt-mdview');"
        " return w && [...w.querySelectorAll('.okt-viewer-crumbs li')].pop().textContent.trim() === n; }",
        arg=name,
    )
    return page.evaluate(STATE)


@pytest.mark.parametrize("viewport", [(1440, 900), (2560, 1440)], ids=["1440", "2560"])
def test_a_code_file_fills_the_frame(project, browser, viewport):
    """The reported case: a 1100 x 774 box in the middle of a screen
    with room for three of it."""
    context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    pg = context.new_page()
    try:
        pg.goto((project / "docs" / "dist" / "standalone" / "index.html").as_uri(), wait_until="load")
        page_quiet(pg)
        got = _open(pg, "tool.py")
        assert got["kind"] == "text"
        assert got["w"] >= viewport[0] - 16 and got["h"] >= viewport[1] - 16, got
    finally:
        context.close()


def test_the_full_path_is_shown_and_copied(project, page):
    got = _open(page, "tool.py")
    expected = (project / "src" / "tool.py").resolve().as_posix()
    assert got["path"] == expected
    page.click(".okt-viewer-copypath")
    assert page.evaluate("() => window.__copied") == [expected]


def test_a_new_tab_opens_the_page_or_the_file(project, page):
    """A markdown file that is a page of the tree opens as that page; any
    other file opens as itself."""
    docs = (project / "docs").resolve()
    got = _open(page, "a.md")
    assert got["open"] == (docs / "dist" / "standalone" / "notes" / "a.html").as_uri()
    page.keyboard.press("Escape")
    got = _open(page, "tool.py")
    assert got["open"] == (project / "src" / "tool.py").resolve().as_uri()
    with page.context.expect_page() as popup:
        page.click(".okt-mdview-open")
    tab = popup.value
    tab.wait_for_load_state()
    assert "line_399 = 399" in tab.inner_text("body")


def test_a_file_opened_from_a_file_opens_on_top_with_a_way_back(page):
    """b.md is named only inside a table fence in a.md — the case where
    a scan of the raw markdown found nothing and the chip stayed dead."""
    one = _open(page, "a.md")
    assert (one["depth"], one["back"], one["title"]) == (1, False, "Note A")
    page.evaluate("() => { document.querySelector('.okt-mdview-body').scrollTop = 600; }")
    two = _open(page, "b.md", inside_viewer=True)
    assert (two["depth"], two["crumbs"], two["back"], two["title"]) == (2, ["a.md", "b.md"], True, "Note B")
    three = _open(page, "c.txt", inside_viewer=True)
    assert (three["depth"], three["kind"], three["crumbs"]) == (3, "text", ["a.md", "b.md", "c.txt"])

    page.click(".okt-viewer-back")
    assert page.evaluate(STATE)["depth"] == 2
    # Alt+Left is back, inside the frame
    page.focus(".okt-viewer-back")
    page.keyboard.press("Alt+ArrowLeft")
    back = page.evaluate(STATE)
    assert (back["depth"], back["title"]) == (1, "Note A")
    assert back["scroll"] >= 590, "the first file did not keep its place"


def test_a_crumb_goes_back_and_a_new_file_drops_what_was_ahead(page):
    _open(page, "a.md")
    _open(page, "b.md", inside_viewer=True)
    _open(page, "c.txt", inside_viewer=True)
    page.click(".okt-viewer-crumb[data-at='0']")
    assert page.evaluate(STATE)["crumbs"] == ["a.md"]
    again = _open(page, "b.md", inside_viewer=True)
    assert again["crumbs"] == ["a.md", "b.md"]


def test_escape_closes_the_whole_trail(page):
    _open(page, "a.md")
    _open(page, "b.md", inside_viewer=True)
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.querySelector('.okt-lightbox.open')")
    fresh = _open(page, "tool.py")
    assert (fresh["depth"], fresh["crumbs"]) == (1, ["tool.py"])


def test_the_artifact_names_no_machine_path(project):
    """The page derives the full path from its own URL. Nothing in the
    built tree may carry it — a page is handed to other people. (The
    rebuild command is the one place that does, by design, and the
    fixture turns it off with the switch that exists for this.)"""
    home = str(project.resolve())
    for html in (project / "docs" / "dist").rglob("*.html"):
        assert home not in html.read_text(encoding="utf-8"), html
    for js in (project / "docs" / "dist").rglob("*.json"):
        assert home not in js.read_text(encoding="utf-8"), js


def test_at_phone_width_the_bar_fits_and_names_the_file_clear_of_close(project, browser):
    """At 360px the trail, the actions and the path cannot share a line.
    Measured before: the file's name ran under the close button and the
    size line ran off the right edge."""
    context = browser.new_context(viewport={"width": 360, "height": 740})
    pg = context.new_page()
    try:
        pg.goto((project / "docs" / "dist" / "standalone" / "index.html").as_uri(), wait_until="load")
        page_quiet(pg)
        _open(pg, "a.md")
        _open(pg, "b.md", inside_viewer=True)
        got = pg.evaluate(
            """() => { const w = document.querySelector('.okt-mdview');
              const here = w.querySelector('.okt-viewer-crumb-here').getBoundingClientRect();
              const close = document.querySelector('.okt-lightbox-close').getBoundingClientRect();
              const over = [...w.querySelectorAll('.okt-mdview-bar *, .okt-viewer-where *')]
                .filter(e => e.getClientRects().length && e.getBoundingClientRect().right > innerWidth + 0.5)
                .map(e => e.className.toString());
              const name = w.querySelector('.okt-viewer-crumb-here');
              return { over, clipped: name.scrollWidth > name.clientWidth + 1,
                       underClose: here.right > close.left && here.top < close.bottom && here.bottom > close.top,
                       sideways: document.documentElement.scrollWidth - innerWidth }; }"""
        )
        assert got["over"] == [], got["over"]
        assert not got["clipped"], "the file's name is cut"
        assert not got["underClose"], "the file's name runs under the close button"
        assert got["sideways"] <= 0
    finally:
        context.close()


def test_a_table_expanded_inside_a_viewed_file_closes_back_into_it(page):
    """The lightbox held one thing, and an open over an open one drained
    it: expanding a table inside a viewed file took the viewer's frame
    with it, the viewer's own close never ran, and the next file link the
    reader clicked drew into a frame that was no longer on the page. An
    open over an open one is a second overlay now, and Escape takes down
    only the one in front."""
    _chip(page, "a.md").click()
    page.wait_for_selector(".okt-mdview-body .okt-table-wrap [data-expand]", state="attached")
    btn = page.locator(".okt-mdview-body .okt-table-wrap [data-expand]").first
    # The button sits in the table's hover toolbar; the subject here is
    # what the lightbox does with a second open, not the toolbar's reveal.
    btn.evaluate("b => b.click()")
    page.wait_for_function("document.querySelectorAll('.okt-lightbox.open').length === 2")
    assert page.evaluate(
        "() => !!document.querySelectorAll('.okt-lightbox.open')[1].querySelector('.okt-table-wrap')"
    ), "the table is in the front overlay"

    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelectorAll('.okt-lightbox.open').length === 1")
    got = page.evaluate(STATE)
    assert got and got["title"] == "Note A", got
    assert page.locator(".okt-mdview-body .okt-table-wrap").count() == 1, "the table went back into the file"

    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelectorAll('.okt-lightbox.open').length === 0")
    _chip(page, "tool.py").click()
    page.wait_for_function("document.querySelectorAll('.okt-lightbox.open').length === 1")
    got = page.evaluate(STATE)
    assert got and got["kind"] != "md", got


def test_a_viewed_file_is_read_in_the_pages_own_voice(page):
    """The reading face was scoped to `.okt-mdview-body > section`, and a
    viewed file's sections sit two levels deeper, so every file opened
    from a page was set in the interface face while the page itself was
    in the reading face — measured: Inter at 16px against Literata at
    18px, under a comment saying the two are read the same way."""
    _chip(page, "a.md").click()
    page.wait_for_selector(".okt-mdview-rendered section p", state="attached")
    got = page.evaluate(
        """() => { const f = (s) => { const e = document.querySelector(s); const c = getComputedStyle(e);
                                      return [c.fontFamily.split(',')[0], c.fontSize]; };
          return { page: f('main section > p'), file: f('.okt-mdview-rendered section > p'),
                   pageH2: f('main section > h2')[0], fileH2: f('.okt-mdview-rendered section > h2')[0],
                   title: f('.okt-mdview-title')[0], cover: f('header.cover h1')[0] }; }"""
    )
    assert got["file"] == got["page"], got
    assert got["fileH2"] == got["pageH2"], got
    assert got["title"] == got["cover"], got
