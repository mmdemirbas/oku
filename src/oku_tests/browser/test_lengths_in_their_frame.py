"""A length measured in one frame is written in the frame it lands in.

`getBoundingClientRect()`, `clientX` and their kin report CLIENT pixels.
A length written into `style` or `scrollTop` is read in the frame of
the element it is written on, and two things make that frame differ:

- the reader's text scale is `zoom` on the reading column, the viewer's
  body and the sidebar, so inside them one CSS pixel covers `zoom`
  client pixels;
- a `position: fixed` element whose ancestor carries a `transform` is
  placed against that ancestor, not the viewport — the expanded chart's
  pan/zoom stage is one.

Each case below wrote a client measurement straight into one of those
frames. At text scale 1 and an untransformed stage the two frames are
the same and every number came out right, which is why nothing failed;
at 1.25 a bar chart's cursor sat 127px off the pointer, a column grew
by 107px for a 40px drag, a `#f/file:200` reference opened on the wrong
screen of the file, both sidebar lists scrolled their current entry out
of view, and an expanded chart's reading left the screen once zoomed.

Every case is run at 1 as well, as the control: the assertion is the
same at both scales, and only the frame differs.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import measured, page_quiet, until

pytestmark = pytest.mark.browser

SECTIONS = 40
SRC_LINES = 400
TREE_PAGES = 60

PAGE_MD = (
    """---
title: Frames
summary: Lengths written in the frame they land in.
order: 0
---

## Charts {#charts}

Line 200 of [`src.py`](#f/../src/src.py:200).

```oku-chart
{"type": "bar", "rows": [{"label": "Spark", "value": 95}, {"label": "Flink", "value": 80}, {"label": "Trino", "value": 75}]}
```

```oku-chart
{"type": "line", "title": "Latency", "x_label": "Day", "y_label": "ms", "series": [{"label": "a", "data": [{"x": 1, "y": 142}, {"x": 2, "y": 155}, {"x": 3, "y": 138}, {"x": 4, "y": 161}]}]}
```

## Previews {#prev}

```oku-compare-grid
{"cards": [{"t": "bar", "b": "", "href": "#chart-bar"}], "preview": true}
```

## Bar {#chart-bar}

```oku-chart
{"type": "bar", "rows": [{"label": "A fairly long label", "value": 95}, {"label": "Flink", "value": 80}, {"label": "Trino", "value": 75}]}
```

## Table {#tbl}

| Name | Kind | Value | Note |
|---|---|---|---|
"""
    + "\n".join(f"| row{i} | k{i} | {i * 7} | short note {i} |" for i in range(1, 9))
    + "\n\n"
    + "\n\n".join(f"## Section {i} {{#s{i}}}\n\nA paragraph for section {i}." for i in range(1, SECTIONS + 1))
    + "\n"
)

NOANIM = (
    "*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}"
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("frames") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "src.py").write_text(
        "\n".join(f"value_{i} = {i}  # line {i}" for i in range(1, SRC_LINES + 1)) + "\n", encoding="utf-8"
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    for i in range(1, TREE_PAGES + 1):
        (docs / f"p{i:02d}.md").write_text(
            f"---\ntitle: Page {i}\nsummary: s\norder: {i}\n---\n\n## One\n\nText.\n", encoding="utf-8"
        )
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone"


def _open(browser, built, scale: float, page_name: str = "page.html", width: int = 1280):
    context = browser.new_context(viewport={"width": width, "height": 800})
    context.add_init_script(f"localStorage.setItem('oku-text-scale', '{scale}')")
    page = context.new_page()
    page.goto((built / page_name).as_uri(), wait_until="load")
    page_quiet(page)
    page.add_style_tag(content=NOANIM)
    assert measured(page, "() => getComputedStyle(document.querySelector('main')).zoom") == str(scale)
    return context, page


def _box(locator) -> dict:
    return locator.evaluate(
        "e => { const b = e.getBoundingClientRect(); return {l: b.left, t: b.top, r: b.right, b: b.bottom, w: b.width, h: b.height}; }"
    )


SCALES = pytest.mark.parametrize("scale", [1, 1.25])


@SCALES
def test_the_bar_chart_cursor_is_under_the_pointer(built, browser, scale):
    context, page = _open(browser, built, scale)
    try:
        host = page.locator(".bar-chart").first
        host.scroll_into_view_if_needed()
        fill = _box(host.locator(".bar-fill").first)
        x, y = fill["l"] + fill["w"] / 2, fill["t"] + fill["h"] / 2
        page.mouse.move(x - 5, y)
        page.mouse.move(x, y)
        until(
            page,
            "() => getComputedStyle(document.querySelector('.bar-chart .okc-bar-cursor')).opacity === '1'",
        )
        cur = _box(host.locator(".okc-bar-cursor"))
        rows = host.locator(".bar-row")
        top, bottom = _box(rows.first)["t"], _box(rows.last)["b"]
        assert abs(cur["l"] - x) < 1.5, f"cursor at x={cur['l']:.1f}, pointer at {x:.1f}"
        assert abs(cur["t"] - top) < 1.5, f"cursor top {cur['t']:.1f}, plot top {top:.1f}"
        assert abs(cur["b"] - bottom) < 1.5, f"cursor bottom {cur['b']:.1f}, plot bottom {bottom:.1f}"
    finally:
        context.close()


@SCALES
def test_a_column_follows_the_drag(built, browser, scale):
    context, page = _open(browser, built, scale)
    try:
        th = page.locator("#tbl").locator("xpath=ancestor-or-self::section").locator("table thead th").first
        th.scroll_into_view_if_needed()
        th.hover()
        handle = _box(th.locator(".okt-col-resize"))
        w0 = _box(th)["w"]
        x, y = handle["l"] + handle["w"] / 2, handle["t"] + handle["h"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        pressed = _box(th)["w"]
        page.mouse.move(x + 40, y, steps=6)
        dragged = _box(th)["w"]
        page.mouse.up()
        assert abs(pressed - w0) < 1.5, f"pressing the grabber changed the column by {pressed - w0:.1f}px"
        assert abs(dragged - w0 - 40) < 2, f"a 40px drag grew the column by {dragged - w0:.1f}px"
    finally:
        context.close()


@SCALES
def test_a_reference_to_a_line_opens_on_that_line(built, browser, scale):
    context, page = _open(browser, built, scale)
    try:
        page.locator("main .okt-fp .okt-fp-label").first.click()
        until(page, "() => document.querySelectorAll('.okt-mdview .okt-line-hit').length > 0")
        page.wait_for_timeout(200)
        geo = measured(
            page,
            """() => { const body = document.querySelector('.okt-mdview-body'); const b = body.getBoundingClientRect();
              const hit = document.querySelector('.okt-mdview .okt-line-hit').getBoundingClientRect();
              return { off: hit.top - b.top, third: b.height / 3, inView: hit.top >= b.top && hit.bottom <= b.bottom }; }""",
        )
        assert geo["inView"], f"line 200 is {geo['off']:.0f}px from the viewer's top, out of view"
        assert abs(geo["off"] - geo["third"]) < 4, (
            f"line 200 at {geo['off']:.1f}px, a third down is {geo['third']:.1f}"
        )
    finally:
        context.close()


def _open_drawer(page) -> None:
    if not page.evaluate("() => document.body.classList.contains('drawer-open')"):
        page.click(".drawer-toggle")
    until(page, "() => document.body.classList.contains('drawer-open')")


@SCALES
def test_the_contents_keep_the_current_section_in_view(built, browser, scale):
    context, page = _open(browser, built, scale)
    try:
        _open_drawer(page)
        # The middle of the list: near either end the scroll clamps at its
        # limit and lands the entry in view whatever the arithmetic said.
        page.evaluate(f"() => document.getElementById('s{SECTIONS // 2}').scrollIntoView()")
        until(
            page,
            f"() => (document.querySelector('page-toc .toc-list .active') || {{}}).textContent?.includes('Section {SECTIONS // 2}')",
        )
        page.wait_for_timeout(300)
        geo = measured(
            page,
            """() => { const list = document.querySelector('page-nav page-toc .toc-list');
              const s = list.getBoundingClientRect(), r = list.querySelector('.active').getBoundingClientRect();
              return { inView: r.top >= s.top && r.bottom <= s.bottom, off: (r.top - s.top) - (s.height - r.height) / 2,
                       scrolled: list.scrollTop }; }""",
        )
        assert geo["scrolled"] > 0, "the list never needed to scroll, so this case asserts nothing"
        assert geo["inView"], (
            f"the current section's entry is {geo['off']:.0f}px from the list's centre, out of view"
        )
    finally:
        context.close()


@SCALES
def test_the_site_tree_keeps_the_current_page_in_view(built, browser, scale):
    context, page = _open(browser, built, scale, page_name=f"p{TREE_PAGES - 15}.html")
    try:
        _open_drawer(page)
        page.wait_for_timeout(300)
        geo = measured(
            page,
            """() => { const panel = document.querySelector('.page-nav-panel');
              const row = document.querySelector('.page-nav-tree li.active > a');
              const p = panel.getBoundingClientRect(), r = row.getBoundingClientRect();
              return { inView: r.top >= p.top && r.bottom <= p.bottom, off: (r.top - p.top) - (p.height - r.height) / 2,
                       scrolled: panel.scrollTop }; }""",
        )
        assert geo["scrolled"] > 0, "the tree never needed to scroll, so this case asserts nothing"
        assert geo["inView"], (
            f"the current page's row is {geo['off']:.0f}px from the tree's centre, out of view"
        )
    finally:
        context.close()


@SCALES
def test_a_preview_clone_is_laid_out_at_its_sources_width(built, browser, scale):
    context, page = _open(browser, built, scale)
    try:
        page.locator(".okt-compare-preview").first.scroll_into_view_if_needed()
        geo = measured(
            page,
            """() => { const src = document.getElementById('chart-bar').closest('section').querySelector('.bar-chart');
              const clone = document.querySelector('.okt-compare-preview .bar-chart');
              const track = (el) => el.querySelector('.bar-track').offsetWidth / el.offsetWidth;
              return { src: src.offsetWidth, clone: clone.offsetWidth, srcTrack: track(src), cloneTrack: track(clone) }; }""",
        )
        assert abs(geo["clone"] - geo["src"]) <= 1, (
            f"the clone is laid out {geo['clone']}px wide, its source {geo['src']}px"
        )
        assert abs(geo["cloneTrack"] - geo["srcTrack"]) < 0.01, (
            f"the clone's bars take {geo['cloneTrack']:.3f} of it, the source's {geo['srcTrack']:.3f}"
        )
    finally:
        context.close()


# The reading a dot shows, relative to the dot: where it sits on the page
# is where it must sit in the expanded chart, at any pan/zoom.
_READING = """([x, y]) => { const t = [...document.querySelectorAll('.okc-tooltip.visible')].pop();
  if (!t) return null; const b = t.getBoundingClientRect();
  // Seen means inside what clips it: the stage, in an expanded figure.
  const st = t.closest('.okt-lightbox-pz');
  const v = st ? st.getBoundingClientRect() : { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
  return { dx: (b.left + b.right) / 2 - x, bottom: b.bottom - y,
           onScreen: b.left >= v.left && b.right <= v.right && b.top >= v.top && b.bottom <= v.bottom }; }"""


def _hover_dot(page, dot) -> tuple[float, float]:
    b = _box(dot)
    x, y = b["l"] + b["w"] / 2, b["t"] + b["h"] / 2
    page.mouse.move(x - 3, y)
    page.mouse.move(x, y)
    until(page, "() => !!document.querySelector('.okc-tooltip.visible')")
    return x, y


@pytest.mark.parametrize("presses", [0, 2, 4])
def test_an_expanded_charts_reading_stays_on_its_mark(built, browser, presses):
    context, page = _open(browser, built, 1)
    try:
        chart = page.locator("oku-chart", has=page.locator(".okc-dot")).first
        chart.scroll_into_view_if_needed()
        on_page = measured(page, _READING, list(_hover_dot(page, chart.locator(".okc-dot").nth(1))))
        page.mouse.move(5, 5)
        chart.evaluate("c => c.querySelector('button[title=\"Expand to fullscreen\"]').click()")
        until(page, "() => !!document.querySelector('.okt-lightbox .okc-dot')")
        for _ in range(presses):
            page.keyboard.press("+")
        page.wait_for_timeout(300)
        # The dot nearest the middle of the stage, which stays on screen at any zoom.
        nth = page.evaluate(
            """() => { const st = document.querySelector('.okt-lightbox-pz').getBoundingClientRect();
              const mx = (st.left + st.right) / 2, my = (st.top + st.bottom) / 2;
              let best = -1, bd = 1e9;
              document.querySelectorAll('.okt-lightbox .okc-dot').forEach((d, i) => { const r = d.getBoundingClientRect();
                const dd = Math.hypot(r.left + r.width / 2 - mx, r.top + r.height / 2 - my); if (dd < bd) { bd = dd; best = i; } });
              return best; }"""
        )
        reading = measured(
            page, _READING, list(_hover_dot(page, page.locator(".okt-lightbox .okc-dot").nth(nth)))
        )
        assert reading["onScreen"], f"after {presses} zoom steps the reading is off screen: {reading}"
        assert abs(reading["dx"] - on_page["dx"]) < 2, (
            f"the reading is centred {reading['dx']:.1f}px from its dot; on the page {on_page['dx']:.1f}px"
        )
    finally:
        context.close()


# Each style that may or may not make an ancestor the containing block
# of a fixed descendant. The kit's answer is compared with where the
# browser actually puts a fixed child — the oracle — so the list in
# `__okuFixedContainer` cannot claim a property the engine ignores or
# miss one it honours. `zoom` and `container-type` are in it because
# they are the two a reader of this code would guess wrong.
FIXED_CB_STYLES = [
    "",
    "zoom: 1.25",
    "container-type: inline-size",
    "transform: translate(3px, 2px)",
    "translate: 3px 2px",
    "rotate: 0.001deg",
    "scale: 1.01",
    "perspective: 100px",
    "filter: blur(0)",
    "backdrop-filter: blur(1px)",
    "will-change: transform",
    "will-change: opacity",
    "contain: layout",
    "contain: paint",
    "contain: size",
    "contain: content",
    "content-visibility: auto",
]


@pytest.mark.parametrize("style", FIXED_CB_STYLES)
def test_the_fixed_container_rule_agrees_with_the_browser(built, browser, style):
    context, page = _open(browser, built, 1)
    try:
        got = page.evaluate(
            """(style) => {
              const host = document.createElement('div');
              host.setAttribute('style', 'position: absolute; left: 137px; top: 91px; width: 200px; height: 120px; ' + style);
              const child = document.createElement('div');
              child.setAttribute('style', 'position: fixed; left: 0; top: 0; width: 10px; height: 10px');
              host.appendChild(child);
              document.body.appendChild(host);
              const r = child.getBoundingClientRect();
              const browser = Math.abs(r.left) > 20;  // placed against the host, not the viewport
              const kit = __okuFixedContainer(child) === host;
              host.remove();
              return { browser, kit };
            }""",
            style,
        )
        assert got["kit"] == got["browser"], (
            f"`{style or '(none)'}`: the browser places a fixed child against "
            f"{'the host' if got['browser'] else 'the viewport'}, the kit says "
            f"{'the host' if got['kit'] else 'the viewport'}"
        )
    finally:
        context.close()


@SCALES
def test_a_reading_near_the_top_of_the_window_stays_in_it(built, browser, scale):
    """The line chart's top dot, with the plot's top edge 40px from the
    window's: the reading is anchored above the plot and has to come
    down into view. Both the dot and the cursor place it in one move,
    and the clamp used to measure the box where the other had put it."""
    context, page = _open(browser, built, scale)
    try:
        chart = page.locator("oku-chart", has=page.locator(".okc-dot")).first
        page.evaluate(
            "() => { const s = [...document.querySelectorAll('main oku-chart')].find(c => c.querySelector('.okc-dot'))"
            ".querySelector('svg.okc-svg'); scrollBy(0, s.getBoundingClientRect().top - 40); }"
        )
        measured(page, "() => Math.round(scrollY)")
        top = page.evaluate(
            """(c) => { let best = null; for (const d of c.querySelectorAll('.okc-dot')) { const r = d.getBoundingClientRect();
              const x = r.left + r.width / 2, y = r.top + r.height / 2;
              if (document.elementFromPoint(x, y) === d && (!best || y < best[1])) best = [x, y]; } return best; }""",
            chart.element_handle(),
        )
        page.mouse.move(top[0] - 30, top[1] + 30)
        page.mouse.move(top[0], top[1], steps=4)
        until(page, "() => !!document.querySelector('main oku-chart > .okc-tooltip.visible')")
        box = measured(
            page,
            "() => { const b = document.querySelector('main oku-chart > .okc-tooltip.visible').getBoundingClientRect(); return [b.top, b.bottom]; }",
        )
        assert box[0] >= 0 and box[1] <= 800, (
            f"the reading spans y={box[0]:.0f}..{box[1]:.0f}, outside the window"
        )
    finally:
        context.close()
