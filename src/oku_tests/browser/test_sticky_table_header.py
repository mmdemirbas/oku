"""A long table keeps its column labels in view while the reader scrolls it.

Every `thead th` already carried `position: sticky`, and it stuck to
the wrong thing. A sticky element sticks to its nearest scroll
container, and `.okt-table-scroll` is one — `overflow-x: auto` makes
the y axis a scroll axis too — so the header was pinned to a box that
grows with the table and never scrolls vertically. Scroll a
two-hundred-row table and the labels left with the first row.

Two shapes, because the kit has two answers. A table that fits its
column gives up the scroll container and the header sticks to the
viewport natively. A table wider than its column keeps the scroll
container (the rows still need to scroll sideways) and a ghost header
outside it rides at the top, following the horizontal scroll.

Both are asserted the same way, from the reader's side: at the top of
the viewport, under the rail, there is a cell carrying this column's
label at this column's x. Which mechanism put it there is not the
reader's business, so it is not the test's either.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import measured, page_quiet, until

pytestmark = pytest.mark.browser

RAIL_H = 12  # the top rail at rest; opaque, so a header under it is hidden

ROWS = 160
LONG = "\n".join(f"| name{i:03d} | {i} | note {i} |" for i in range(ROWS))
WIDE_COLS = 14
WIDE_HEAD = "| " + " | ".join(f"column{c:02d}" for c in range(WIDE_COLS)) + " |"
WIDE_ALIGN = "|" + "---|" * WIDE_COLS
WIDE = "\n".join("| " + " | ".join(f"v{c:02d}r{i:03d}" for c in range(WIDE_COLS)) + " |" for i in range(ROWS))
# Enough prose after the last table that the page can scroll past it.
TAIL = "\n\n".join("Paragraph after the tables, so the page scrolls on." for _ in range(60))
PAGE_MD = f"""---
title: Long tables
summary: Two long tables, one narrow and one wide.
---

## Fits the column {{#fits}}

| Name | Count | Note |
|:---|---:|:---|
{LONG}

## Wider than the column {{#wide}}

{WIDE_HEAD}
{WIDE_ALIGN}
{WIDE}

## After the tables {{#after}}

{TAIL}
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("stickyhead") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Long tables"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture()
def page(built, browser):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    yield page
    context.close()


def _wrap(sel: str) -> str:
    """The `.okt-table-wrap` a section heading is followed by. The
    section wraps its blocks, so the heading's parent holds the table."""
    return f"document.querySelector({sel!r}).closest('section, main').querySelector('.okt-table-wrap')"


def _scroll_table_top_to(page, sel: str, y: float) -> None:
    """Scroll the window so the wrap's top edge sits at viewport y."""
    page.evaluate(
        f"(y) => {{ const r = {_wrap(sel)}.getBoundingClientRect();"
        " window.scrollTo(0, window.scrollY + r.top - y); }",
        y,
    )
    measured(page, "() => Math.round(window.scrollY)")


def _header_js(sel: str) -> str:
    """JS source: for every real header cell whose column is on screen,
    what cell a reader finds at the top of the viewport, in that column.

    Yields [{label, left, top, found, foundLeft, foundTop}] — `found` is
    the label of the `th` under the point (x = the column's centre,
    y = just under the rail), or None when nothing header-like is
    there. The real cell's own geometry rides along so the assertion
    can say by how much a found cell is out of its column.
    """
    return f"""() => {{
          const wrap = {_wrap(sel)};
          const box = wrap.querySelector('.okt-table-scroll').getBoundingClientRect();
          const ths = [...wrap.querySelectorAll('.okt-table-scroll thead th')];
          const h = ths[0].getBoundingClientRect().height;
          return ths.map((th) => {{
            const r = th.getBoundingClientRect();
            // A column the box clips is not on screen, whatever the viewport says.
            if (r.left < Math.max(0, box.left) || r.right > Math.min(innerWidth, box.right)) return null;
            const x = r.left + 6, y = {RAIL_H} + h / 2;
            // The fixed chrome buttons float over the column at phone
            // width, at the same y a stuck header parks at. That is their
            // rule — they float over every line that scrolls under them —
            // so a probe one of them takes says nothing about the header.
            const el = document.elementFromPoint(x, y);
            if (el && el.closest('.ctrl-btn, .okt-chrome-cluster')) return null;
            const cell = el && el.closest('th');
            const cr = cell && cell.getBoundingClientRect();
            return {{ label: th.textContent.trim(), left: r.left, top: r.top,
                      found: cell ? cell.textContent.trim() : null,
                      foundLeft: cr ? cr.left : null, foundTop: cr ? cr.top : null,
                      isReal: cell === th }};
          }}).filter(Boolean);
        }}"""


def _header_at_top(page, sel: str):
    return page.evaluate(_header_js(sel))


def _assert_header_in_view(page, sel: str, cells) -> None:
    # The first row of data has scrolled away, so a header at the top
    # is one that stayed behind rather than one that has not left yet.
    assert (
        page.evaluate(
            f"() => {_wrap(sel)}.querySelector('.okt-table-scroll tbody tr').getBoundingClientRect().top"
        )
        < 0
    )
    assert cells, "no column of the table is on screen"
    for c in cells:
        assert c["found"] == c["label"], (
            f"column {c['label']!r}: found {c['found']!r} at the top of the viewport"
        )
        assert abs(c["foundLeft"] - c["left"]) < 1, (
            f"column {c['label']!r}: header at x={c['foundLeft']:.1f}, column at x={c['left']:.1f}"
        )
        assert c["foundTop"] >= RAIL_H - 0.5, (
            f"column {c['label']!r}: header top {c['foundTop']:.1f} is under the rail"
        )


def test_a_fitting_table_keeps_its_header_in_view(page):
    _scroll_table_top_to(page, "#fits", -1500)
    _assert_header_in_view(page, "#fits", _header_at_top(page, "#fits"))


def test_a_wide_table_keeps_its_header_in_view(page):
    _scroll_table_top_to(page, "#wide", -1500)
    _assert_header_in_view(page, "#wide", _header_at_top(page, "#wide"))
    # The kit did not lose the sideways scroll to win the sticky header.
    assert page.evaluate(
        f"() => {{ const s = {_wrap('#wide')}.querySelector('.okt-table-scroll');"
        " return s.scrollWidth > s.clientWidth && getComputedStyle(s).overflowX === 'auto'; }"
    ), "the wide table no longer scrolls sideways"


def test_the_wide_header_follows_the_sideways_scroll(page):
    _scroll_table_top_to(page, "#wide", -1500)
    page.evaluate(f"() => {{ {_wrap('#wide')}.querySelector('.okt-table-scroll').scrollLeft = 150; }}")
    until(
        page,
        f"() => {_wrap('#wide')}.querySelector('.okt-table-scroll').scrollLeft === 150",
        what="the wide table scrolled sideways",
    )
    # The ghost follows the scroll on the scroll event, one frame behind
    # the assignment above — so the reading is taken once it holds still.
    _assert_header_in_view(page, "#wide", measured(page, _header_js("#wide")))


def test_scrolling_the_stuck_header_scrolls_the_rows(page):
    """The ghost is a scroller of its own, kept in step both ways — so
    a wheel over the stuck header moves the rows under it, rather than
    doing nothing on the one strip of the table that never leaves."""
    _scroll_table_top_to(page, "#wide", -1500)
    page.evaluate(f"() => {{ {_wrap('#wide')}.querySelector('.okt-table-ghost').scrollLeft = 200; }}")
    until(
        page,
        f"() => {_wrap('#wide')}.querySelector('.okt-table-scroll').scrollLeft === 200",
        what="the rows followed the header's sideways scroll",
    )
    _assert_header_in_view(page, "#wide", measured(page, _header_js("#wide")))


def test_at_rest_the_real_header_takes_the_pointer(page):
    """Nothing sits over the header the author wrote until it scrolls
    away — hover, sort and the column grabber all belong to it."""
    _scroll_table_top_to(page, "#wide", 200)
    hit = page.evaluate(
        f"""() => {{
          const th = {_wrap("#wide")}.querySelector('.okt-table-scroll thead th');
          const r = th.getBoundingClientRect();
          const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          return th === el || th.contains(el);
        }}"""
    )
    assert hit, "something other than the real header is under the pointer at rest"


def test_the_stuck_header_still_sorts(page):
    """A header that reads as the table's header has to act as one: a
    click on the stuck cell sorts the column it names."""
    _scroll_table_top_to(page, "#wide", -1500)
    cells = _header_at_top(page, "#wide")
    _assert_header_in_view(page, "#wide", cells)
    first = cells[0]
    before = page.evaluate(
        f"() => {_wrap('#wide')}.querySelector('.okt-table-scroll tbody tr td').textContent.trim()"
    )
    h = page.evaluate(
        f"() => {_wrap('#wide')}.querySelector('.okt-table-scroll thead th').getBoundingClientRect().height"
    )
    page.mouse.click(first["foundLeft"] + 20, RAIL_H + h / 2)
    page.mouse.click(first["foundLeft"] + 20, RAIL_H + h / 2)  # asc → desc
    until(
        page,
        f"() => {_wrap('#wide')}.querySelector('.okt-table-scroll tbody tr td').textContent.trim() !== {before!r}",
        what="the first row changed after sorting from the stuck header",
    )


def test_the_header_stops_at_the_end_of_its_table(page):
    """Past the table, nothing of it stays behind at the top."""
    page.evaluate(
        f"() => {{ const r = {_wrap('#wide')}.getBoundingClientRect();"
        " window.scrollTo(0, window.scrollY + r.bottom + 40); }"
    )
    measured(page, "() => Math.round(window.scrollY)")
    stray = page.evaluate(
        f"""() => {{
          const wrap = {_wrap("#wide")};
          const el = document.elementFromPoint(innerWidth / 2, {RAIL_H} + 20);
          return !!(el && el.closest('.okt-table-wrap') === wrap);
        }}"""
    )
    assert not stray, "part of the wide table is still at the top of the viewport below its own end"


@pytest.mark.parametrize("scale", ["1.25"])
def test_the_header_aligns_under_text_scale(built, browser, scale):
    """The reading column is `zoom`ed by the text-scale control, and
    a width copied from a viewport rect into a zoomed box is scaled
    twice. The header has to land on its column at every scale."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    context.add_init_script(f"try{{localStorage.setItem('oku-text-scale','{scale}')}}catch(e){{}}")
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    assert page.evaluate("() => getComputedStyle(document.querySelector('main')).zoom") == scale
    try:
        _scroll_table_top_to(page, "#wide", -1500)
        _assert_header_in_view(page, "#wide", _header_at_top(page, "#wide"))
        _scroll_table_top_to(page, "#fits", -1500)
        _assert_header_in_view(page, "#fits", _header_at_top(page, "#fits"))
    finally:
        context.close()


def test_narrow_viewport_keeps_the_header_and_no_sideways_scroll(built, browser):
    context = browser.new_context(viewport={"width": 360, "height": 640})
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    try:
        for sel in ("#fits", "#wide"):
            _scroll_table_top_to(page, sel, -1500)
            _assert_header_in_view(page, sel, _header_at_top(page, sel))
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
    finally:
        context.close()
