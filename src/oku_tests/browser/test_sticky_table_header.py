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

RAIL_H = 0  # nothing spans the top edge: the rail is a capsule in the buttons' row, measured with them

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
          // Where the header actually parks. Not a constant: it clears
          // the rail, and it clears any fixed chrome button standing
          // over this table's columns — which is most window widths,
          // not just a phone.
          const ghost = wrap.querySelector('.okt-table-ghost');
          const shown = (ghost && ghost.dataset.stuck === '1') ? ghost : ths[0];
          const top = shown.getBoundingClientRect().top;
          return ths.map((th) => {{
            const r = th.getBoundingClientRect();
            // A column the box clips is not on screen, whatever the viewport says.
            if (r.left < Math.max(0, box.left) || r.right > Math.min(innerWidth, box.right)) return null;
            const x = r.left + 6, y = top + h / 2;
            const el = document.elementFromPoint(x, y);
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


def _chrome_over_header(page, sel: str):
    """Fixed chrome buttons whose box intersects the parked header.

    The 44px buttons float over the top of the reading column at every
    scroll position, which is their rule and is fine for prose — a line
    passing under one is gone in a moment. A sticky header parked under
    one is a column label the reader never sees, at any scroll position.
    Measured before the header learned to clear them: at 1100px the
    search button covered the last column, and at 760px and below the
    Contents button covered the first while search and the menu covered
    the last."""
    return page.evaluate(
        rf"""() => {{
          const wrap = {_wrap(sel)};
          const ghost = wrap.querySelector('.okt-table-ghost');
          const th = wrap.querySelector('.okt-table-scroll thead th');
          const shown = (ghost && ghost.dataset.stuck === '1') ? ghost : th;
          const hdr = shown.getBoundingClientRect();
          return [...document.querySelectorAll('.ctrl-btn, .okt-chrome-cluster, .okt-rail')].filter((b) => {{
            const cs = getComputedStyle(b);
            if (cs.position !== 'fixed' || cs.display === 'none' || cs.visibility === 'hidden') return false;
            const r = b.getBoundingClientRect();
            return r.width > 0 && r.right > hdr.left && r.left < hdr.right
                && r.bottom > hdr.top && r.top < hdr.bottom;
          }}).map((b) => b.className.trim().split(/\s+/).pop() + '@' + Math.round(b.getBoundingClientRect().left));
        }}"""
    )


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
    assert _chrome_over_header(page, sel) == [], (
        f"a fixed chrome button covers the parked header: {_chrome_over_header(page, sel)}"
    )
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
    page.mouse.click(first["foundLeft"] + 20, first["foundTop"] + h / 2)
    page.mouse.click(first["foundLeft"] + 20, first["foundTop"] + h / 2)  # asc → desc
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
          const rail = document.getElementById('oku-rail');
          const below = rail ? rail.getBoundingClientRect().bottom : {RAIL_H};
          const el = document.elementFromPoint(innerWidth / 2, below + 20);
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


# --- What the observer writes, and when ----------------------------------
#
# Three delivered documents came back from a reader with `ResizeObserver
# loop completed with undelivered notifications` in the kit's own warning
# panel. That notice is the browser saying a callback resized something
# the delivery pass had already visited, so the rest was deferred a
# frame. It did not reproduce here on any of the three files, across
# viewport widths and heights, device pixel ratios 1 to 2, stored width /
# text-scale / pinned-drawer combinations and the page's own controls —
# but this is the one place in the kit that wrote layout from inside such
# a callback, and it wrote on every delivery whether or not anything had
# changed: measured on that 31-table page, 155 `--okt-sticky-top` writes
# of which 62 set the value already there, and 93 `data-fit` writes of
# which 91 did.
#
# So the rule is about the write, not about the notice: measure in the
# callback, write in the next frame, and skip a write that changes
# nothing.


@pytest.fixture()
def counted(built, browser):
    """A page that counts what the kit writes, and when."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.add_init_script(
        """
        window.__cb = 0; window.__inCallback = []; window.__props = { total: 0, same: 0 };
        window.__fit = { total: 0, same: 0 };
        (function () {
          const Real = window.ResizeObserver;
          window.ResizeObserver = function (cb) {
            return new Real(function (e, o) {
              window.__cb++;
              try { return cb.call(this, e, o); } finally { window.__cb--; }
            });
          };
          window.ResizeObserver.prototype = Real.prototype;
          const setProp = CSSStyleDeclaration.prototype.setProperty;
          CSSStyleDeclaration.prototype.setProperty = function (n, v, p) {
            if (n === '--okt-sticky-top') {
              window.__props.total++;
              if (this.getPropertyValue(n) === String(v)) window.__props.same++;
              if (window.__cb) window.__inCallback.push(n + ':' + v);
            }
            return setProp.call(this, n, v, p);
          };
        })();
        // `dataset.fit = x` does not pass through setAttribute, so the
        // redundant-write count for it is read off the mutation record.
        window.__watchFit = function () {
          document.querySelectorAll('.okt-table-scroll').forEach(function (s) {
            new MutationObserver(function (recs) {
              recs.forEach(function (r) {
                window.__fit.total++;
                if (r.oldValue === s.getAttribute('data-fit')) window.__fit.same++;
              });
            }).observe(s, { attributes: true, attributeFilter: ['data-fit'], attributeOldValue: true });
          });
        };
        """
    )
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    yield page
    context.close()


def _storm(page) -> None:
    for width in (1100, 940, 820, 700, 560, 380, 700, 1280):
        page.set_viewport_size({"width": width, "height": 800})
        page.wait_for_timeout(180)
    page.wait_for_timeout(400)


def _flip_the_fit(page) -> None:
    """Make a table that fits stop fitting, and fit again. A resize storm
    alone leaves both tables on the side of the threshold they started
    on, so without this the `data-fit` half of the next test would be
    counting an empty set."""
    page.evaluate("() => { document.querySelector('main table').style.width = '3000px'; }")
    page.wait_for_timeout(400)
    page.evaluate("() => { document.querySelector('main table').style.width = ''; }")
    page.wait_for_timeout(400)


def test_the_header_machinery_writes_nothing_it_does_not_change(counted):
    counted.evaluate("() => window.__watchFit()")
    _storm(counted)
    _flip_the_fit(counted)
    props = counted.evaluate("() => window.__props")
    fit = counted.evaluate("() => window.__fit")
    # Non-vacuous: both counters have to have seen the machinery run.
    assert props["total"] > 0, "no sticky-header measurement ran during the resize storm"
    assert fit["total"] >= 2, "the fit state never changed, so nothing was counted"
    assert props["same"] == 0, f"{props['same']} of {props['total']} --okt-sticky-top writes changed nothing"
    assert fit["same"] == 0, f"{fit['same']} of {fit['total']} data-fit writes changed nothing"


def test_the_layout_write_happens_outside_the_delivery_pass(counted):
    _storm(counted)
    assert counted.evaluate("() => window.__props.total") > 0
    assert counted.evaluate("() => window.__inCallback") == [], (
        "the sticky header wrote layout from inside a ResizeObserver callback"
    )


# --- Telling the header from the rows ------------------------------------
#
# Reported by a reader: with a long table scrolled, the sticky header
# and the rows under it are the same colour with no depth cue between
# them, so the labels and the data run together exactly when the header
# is doing its job. Measured before the fix: `th` and the rows both sat
# on --bg, and the only thing between them was a 2px rule.
#
# Two rules, because they answer two states. At rest the header is a
# BAND: a lightness step from the rows, which is what the eye reads as
# a different surface (a contrast ratio does not answer that question).
# While stuck it is also FLOATING, so it raises a shadow — and the
# shadow appears for both mechanisms, since which one is pinning the
# header is not the reader's business.


def _bg(page, sel: str) -> str:
    return page.evaluate(f"() => getComputedStyle(document.querySelector({sel!r})).backgroundColor")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_header_is_a_different_surface_from_its_rows(page, theme):
    from ._colour import lightness

    page.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)", theme)
    page.wait_for_timeout(120)
    head = _bg(page, "#fits table thead th")
    row = _bg(page, "#fits table tbody td")
    if row in ("rgba(0, 0, 0, 0)", "transparent"):
        row = _bg(page, "#fits .okt-table-scroll")
    step = abs(lightness(head) - lightness(row))
    assert step >= 4, f"{theme}: header {head} and rows {row} are {step:.1f} L* apart; they read as one field"


def test_the_stuck_header_raises_a_shadow_and_the_resting_one_does_not(page):
    wrap = "#fits .okt-table-wrap"
    assert page.evaluate(f"() => document.querySelector({wrap!r}).dataset.stuck") is None
    at_rest = page.evaluate(
        "() => getComputedStyle(document.querySelector('#fits table thead th')).boxShadow"
    )
    assert at_rest == "none", f"a header in its place is already raised: {at_rest}"

    _scroll_table_top_to(page, "#fits", -1500)
    until(
        page,
        f"() => document.querySelector({wrap!r}).dataset.stuck === '1'",
        what="the header stuck and nothing said so",
    )
    stuck = page.evaluate("() => getComputedStyle(document.querySelector('#fits table thead th')).boxShadow")
    assert stuck != "none", "a header floating over the rows has no shadow to separate it"


def test_the_wide_table_ghost_raises_the_same_shadow(page):
    wrap = "#wide .okt-table-wrap"
    _scroll_table_top_to(page, "#wide", -1500)
    until(
        page,
        f"() => document.querySelector({wrap!r}).dataset.stuck === '1'",
        what="the ghost stuck and the wrap did not say so",
    )
    stuck = page.evaluate(
        "() => getComputedStyle(document.querySelector('#wide .okt-table-ghost th')).boxShadow"
    )
    assert stuck != "none"
