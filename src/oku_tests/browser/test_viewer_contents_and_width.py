"""A markdown file in the viewer uses the frame it is given.

The viewer fills the screen and set a viewed document in the page's
reading column: 900px in a 1424px frame at 1440, 262px of nothing on
each side, about 500px at 1920. A reader called it a block in the middle
with a lot of wasted space. The column is a rule (one right edge, a
reading measure), so the answer is not to widen the prose:

  - the file's own headings go in the left gutter, sticky, marking the
    section being read and jumping to one on a click — a 1,088-line spec
    opened with no way to move through it but scrolling;
  - the page's width control is in the viewer's bar, because the
    presentation menu is under the overlay. It is the page's setting,
    not a second one: changing it here changes the page.

The contents go only where they fit. Where the gutter is too narrow,
they are not drawn at all rather than drawn over the text.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

SECTIONS = ["Start here", "Scope", "Data model", "Interface", "Failure modes", "Open questions"]


def _long_md() -> str:
    para = (
        "A paragraph long enough to take a few lines of the column, so a section has some height to it. " * 3
    )
    out = ["# Long spec", "", "An opening paragraph under the title.", ""]
    for i, name in enumerate(SECTIONS):
        out += [f"## {name}", ""] + [para, ""] * 6
        if i % 2 == 0:
            out += [f"### Detail of {name.lower()}", ""] + [para, ""] * 3
    return "\n".join(out)


HEADINGS = [h for i, n in enumerate(SECTIONS) for h in ([n, f"Detail of {n.lower()}"] if i % 2 == 0 else [n])]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("viewer") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "long.md").write_text(_long_md(), encoding="utf-8")
    (root / "src" / "short.md").write_text("# Short\n\n## Only\n\nOne section.\n", encoding="utf-8")
    (root / "src" / "tool.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "---\ntitle: Viewer\nsummary: The viewer's frame.\n---\n\n## Files {#files}\n\n"
        "A long one [`long.md`](#f/../src/long.md), a short one [`short.md`](#f/../src/short.md), "
        "and code [`tool.py`](#f/../src/tool.py).\n",
        encoding="utf-8",
    )
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("index"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return root / "docs" / "dist" / "standalone" / "index.html"


def _open(browser, built, label: str, width: int = 1440, height: int = 900, scale: float | None = None):
    context = browser.new_context(viewport={"width": width, "height": height})
    if scale:
        context.add_init_script(f"localStorage.setItem('oku-text-scale', '{scale}')")
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    page.locator("main .okt-fp .okt-fp-label", has_text=label).first.click()
    page.wait_for_selector(".okt-mdview-rendered section, .okt-mdview pre", state="attached")
    page.wait_for_timeout(300)
    return context, page


GEO = """() => { const w = document.querySelector('.okt-mdview'); if (!w) return null;
  const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect();
    const shown = getComputedStyle(e).display !== 'none' && r.width > 0;
    return shown ? { left: r.left, right: r.right, top: r.top, width: r.width } : null; };
  const toc = w.querySelector('.okt-viewer-toc');
  return { toc: box(toc), rendered: box(w.querySelector('.okt-mdview-rendered')),
           body: box(w.querySelector('.okt-mdview-body')),
           entries: toc ? [...toc.querySelectorAll('a')].map(a => a.textContent.trim()) : [],
           current: toc ? [...toc.querySelectorAll('a')].findIndex(a => a.getAttribute('aria-current') === 'true') : -1,
           widths: [...w.querySelectorAll('.okt-mdview-actions [data-width]')].map(b => [b.dataset.width, b.getAttribute('aria-pressed')]),
           mode: document.body.getAttribute('data-content-width') }; }"""


def test_the_gutter_holds_the_files_contents(browser, built) -> None:
    context, page = _open(browser, built, "long.md")
    try:
        g = page.evaluate(GEO)
        assert g["toc"], g
        assert g["entries"] == HEADINGS, g["entries"]
        # In the gutter, beside the column — never over it.
        assert g["toc"]["right"] <= g["rendered"]["left"] - 8, g
        assert g["toc"]["left"] >= g["body"]["left"], g
        assert g["current"] == 0, g
    finally:
        context.close()


def test_the_contents_follow_the_reader_and_take_them_to_a_section(browser, built) -> None:
    context, page = _open(browser, built, "long.md")
    try:
        page.evaluate(
            """() => { const b = document.querySelector('.okt-mdview-body');
                 const h = [...document.querySelectorAll('.okt-mdview-rendered section > h2')][3];
                 b.scrollTop += h.getBoundingClientRect().top - b.getBoundingClientRect().top - 4; }"""
        )
        page.wait_for_timeout(250)
        g = page.evaluate(GEO)
        assert g["entries"][g["current"]] == SECTIONS[3], g
        # The stuck list is still beside the column after a scroll.
        assert g["toc"] and g["toc"]["top"] >= g["body"]["top"] - 1, g

        hash_before = page.evaluate("location.hash")
        page.locator(".okt-viewer-toc a", has_text=SECTIONS[5]).click()
        page.wait_for_timeout(250)
        top = page.evaluate(
            """() => { const b = document.querySelector('.okt-mdview-body').getBoundingClientRect().top;
                 const h = [...document.querySelectorAll('.okt-mdview-rendered section > h2')][5];
                 return h.getBoundingClientRect().top - b; }"""
        )
        assert 0 <= top <= 80, top
        assert page.evaluate("location.hash") == hash_before
        assert page.evaluate(GEO)["entries"][page.evaluate(GEO)["current"]] == SECTIONS[5]
    finally:
        context.close()


def test_the_width_control_is_the_pages_own(browser, built) -> None:
    context, page = _open(browser, built, "long.md")
    try:
        g = page.evaluate(GEO)
        assert [w for w, _ in g["widths"]] == ["narrow", "comfortable", "max"], g
        assert dict(g["widths"])[g["mode"]] == "true", g

        page.locator(".okt-mdview-actions [data-width='narrow']").click()
        g = page.evaluate(GEO)
        assert g["mode"] == "narrow" and dict(g["widths"])["narrow"] == "true", g
        assert g["rendered"]["width"] <= 761, g
        assert g["toc"] and g["toc"]["right"] <= g["rendered"]["left"] - 8, g

        page.locator(".okt-mdview-actions [data-width='max']").click()
        g = page.evaluate(GEO)
        assert g["mode"] == "max", g
        # Max gives the gutter to the text, and the contents go with it.
        assert g["rendered"]["width"] >= g["body"]["width"] - 2 * 24 - 2, g
        assert g["toc"] is None, g
        assert page.evaluate("localStorage.getItem('htmldoc-content-width')") == "max"
    finally:
        context.close()


def test_where_the_gutter_is_too_narrow_the_contents_are_not_drawn(browser, built) -> None:
    for width, scale in ((1100, None), (1440, 1.5)):
        context, page = _open(browser, built, "long.md", width=width, scale=scale)
        try:
            g = page.evaluate(GEO)
            assert g["rendered"], g
            if g["toc"]:
                assert g["toc"]["right"] <= g["rendered"]["left"] - 8, (width, scale, g)
            if width == 1100:
                assert g["toc"] is None, g
        finally:
            context.close()


def test_the_source_view_and_files_without_sections_have_no_contents(browser, built) -> None:
    context, page = _open(browser, built, "long.md")
    try:
        page.locator(".okt-mdview-view[data-view='source']").click()
        assert page.evaluate(GEO)["toc"] is None
    finally:
        context.close()
    context, page = _open(browser, built, "short.md")
    try:
        assert page.evaluate(GEO)["toc"] is None
    finally:
        context.close()


def test_a_code_file_has_no_width_control(browser, built) -> None:
    """A code file already reads edge to edge; three stops would do nothing."""
    context, page = _open(browser, built, "tool.py")
    try:
        assert page.evaluate(GEO)["widths"] == []
    finally:
        context.close()
