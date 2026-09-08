"""The vertical cursor reads every bar it crosses, not one of them.

A bar chart draws a dashed vertical line under the pointer, spanning the
whole plot. That line is a statement about a position on the value axis:
these bars reach it, those do not. The tooltip beside it described a
single bar — whichever one the pointer happened to rest on — so the
reader was shown a line making a comparison and a number that ignored it.

The SVG chart families already did this: `_wireCartesianCursor` and the
generic cursor both build a per-series readout at the cursor's x. The
DIV-based bar family was the one that did not.

Also pinned here: the total in the footer. A sum of decimal values
carries binary float error, and `of 62.300000000000004` shipped in a
delivered document — a number no author wrote, next to the numbers they
did.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from ._wait import stable, until

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# The shape that produced the report: decimals whose sum is not exact in
# binary (26.9 + 10.4 + 9.2 + 9.0 + 6.6 + 0.2), each row a different
# length so the crossing set changes with the cursor.
ROWS = [
    {"label": "Free", "value": 26.9, "display": "26.9 GB"},
    {"label": "Wired", "value": 10.4, "display": "10.4 GB"},
    {"label": "Inactive", "value": 9.2, "display": "9.2 GB"},
    {"label": "Active", "value": 9.0, "display": "9.0 GB"},
    {"label": "Compressor", "value": 6.6, "display": "6.6 GB"},
    {"label": "Speculative", "value": 0.2, "display": "0.2 GB"},
]

STACKED = {
    "type": "stacked-bar",
    "title": "Stacked",
    "categories": ["alpha", "beta"],
    "series": [
        {"label": "one", "values": [4, 6]},
        {"label": "two", "values": [6, 4]},
    ],
}

PAGE = f"""---
title: Cursor read
summary: Every bar the cursor crosses.
---

## Single {{#single}}

Lead paragraph.

```oku-chart
{json.dumps({"type": "bar", "title": "Memory", "rows": ROWS})}
```

## Mixed {{#mixed}}

Lead paragraph.

```oku-chart
{
    json.dumps(
        {
            "type": "bar",
            "title": "Mixed units",
            "rows": [
                {"label": "Plain", "value": 6.6, "display": "6.6 GB of compressed pages"},
                {"label": "Unit", "value": 9.2, "display": "9.2 GB"},
            ],
        }
    )
}
```

## Stacked {{#stacked}}

Lead paragraph.

```oku-chart
{json.dumps(STACKED)}
```
"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("barcursor")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "p.md").write_text(PAGE, encoding="utf-8")
    (d / "p.html").write_text(
        cli._stub_for("Cursor read", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


# Geometry first: where each bar ends, so the test can put the cursor at
# a chosen threshold instead of guessing a pixel.
FILL_RECTS = """(sel) => [...document.querySelectorAll(sel + ' .bar-fill')].map((f) => {
  const r = f.getBoundingClientRect();
  const row = f.closest('.bar-row');
  return {
    label: (row.querySelector('.bar-label') || {}).textContent || '',
    left: r.left, right: r.right, top: r.top, bottom: r.bottom,
  };
})"""

TIP = """() => {
  const t = document.querySelector('.okc-tooltip.visible');
  if (!t) return null;
  const names = [...t.querySelectorAll('.okc-tt-name')].map((e) => e.textContent.trim());
  return {
    names,
    values: [...t.querySelectorAll('.okc-tt-val')].map((e) => e.textContent.trim()),
    shares: [...t.querySelectorAll('.okc-tt-share')].map((e) => e.textContent.trim()),
    cursor: [...t.querySelectorAll('.okc-tt-name.is-cursor')].map((e) => e.textContent.trim()),
    footer: (t.querySelector('.okc-tt-coords') || {}).textContent || '',
    box: (() => { const b = t.getBoundingClientRect();
                  return {left: Math.round(b.left), right: Math.round(b.right),
                          top: Math.round(b.top), bottom: Math.round(b.bottom)}; })(),
    swatches: t.querySelectorAll('.okc-tt-swatch').length,
    pinned: t.classList.contains('pinned'),
  };
}"""


@pytest.fixture(scope="module")
def chart_page(browser, served):
    pg = browser.new_page()
    pg.set_viewport_size({"width": 1280, "height": 1200})
    pg.goto(f"{served}/p.html")
    pg.wait_for_function("() => window.__okuRendered === true", timeout=20000)
    pg.wait_for_selector("#single .bar-fill")
    yield pg
    pg.close()


def _hover_at(page, sel: str, x: float, row_index: int):
    rects = page.evaluate(FILL_RECTS, sel)
    r = rects[row_index]
    page.mouse.move(x, (r["top"] + r["bottom"]) / 2)
    # The read is rebuilt as the pointer crosses bars, so what the
    # caller is about to evaluate is this expression holding still —
    # the same one, so the wait and the assertion cannot watch
    # different things.
    stable(page, TIP, what="the cursor read settled")


def test_the_tooltip_lists_every_bar_the_cursor_crosses(chart_page) -> None:
    rects = chart_page.evaluate(FILL_RECTS, "#single")
    assert [r["label"] for r in rects] == [r["label"] for r in ROWS], rects

    # Two pixels inside the end of the 9.0 bar: the four bars at or above
    # 9.0 reach it, the two below do not.
    x = rects[3]["right"] - 2
    _hover_at(chart_page, "#single", x, 3)

    tip = chart_page.evaluate(TIP)
    assert tip, "no tooltip appeared at the cursor"
    assert tip["names"] == ["Free", "Wired", "Inactive", "Active"], (
        f"the cursor at x={x:.0f} crosses four bars; the tooltip listed {tip['names']}"
    )
    assert tip["values"] == ["26.9 GB", "10.4 GB", "9.2 GB", "9.0 GB"], tip["values"]
    # The row under the pointer is marked, and it is one of the set —
    # not the only member of it.
    assert tip["cursor"] == ["Active"], tip["cursor"]
    # Every bar on a single-series chart is the accent, so a colour chip
    # column would be four identical squares taking width from the names.
    assert tip["swatches"] == 0, "a single-colour set needs no colour key"


def test_the_set_shrinks_as_the_cursor_moves_right(chart_page) -> None:
    rects = chart_page.evaluate(FILL_RECTS, "#single")
    seen = []
    for idx in (5, 4, 3, 1):
        _hover_at(chart_page, "#single", rects[idx]["right"] - 2, idx)
        seen.append(chart_page.evaluate(TIP)["names"])

    counts = [len(s) for s in seen]
    assert counts == sorted(counts, reverse=True), f"the crossing set must shrink rightwards: {seen}"
    assert seen[-1] == ["Free", "Wired"], seen[-1]
    # Past the longest bar nothing is crossed, and a tooltip listing
    # nothing is worse than none.
    chart_page.mouse.move(rects[0]["right"] + 6, (rects[0]["top"] + rects[0]["bottom"]) / 2)
    # An absence, but not one polled from zero: the loop above left a
    # read on screen, so this is a transition away from it and there is
    # something to wait for.
    until(
        chart_page,
        "() => !document.querySelector('.okc-tooltip.visible')",
        what="the read went away past the last bar",
    )
    assert chart_page.evaluate(TIP) is None, "a cursor past every bar must show no read"


def test_the_footer_states_the_total_without_float_noise(chart_page) -> None:
    """26.9 + 10.4 + 9.2 + 9.0 + 6.6 + 0.2 is 62.300000000000004 in
    binary floating point, and that string shipped in a document."""
    rects = chart_page.evaluate(FILL_RECTS, "#single")
    _hover_at(chart_page, "#single", rects[3]["right"] - 2, 3)
    tip = chart_page.evaluate(TIP)
    # And it carries the unit, because every row agrees on one.
    assert tip["footer"] == "of 62.3 GB", tip["footer"]


def test_the_unit_is_dropped_when_the_rows_disagree_about_it(chart_page) -> None:
    """The unit is read back off the rows' display strings. One row
    written as "6.6 GB of compressed pages" does not agree with "9.2 GB",
    and inventing a unit over a disagreement is worse than a bare
    number."""
    rects = chart_page.evaluate(FILL_RECTS, "#mixed")
    _hover_at(chart_page, "#mixed", rects[1]["right"] - 2, 1)
    tip = chart_page.evaluate(TIP)
    assert tip["footer"] == "of 15.8", tip["footer"]


def test_a_stacked_row_contributes_the_segment_the_line_falls_inside(chart_page) -> None:
    """The same rule, and it is the rule that makes it general: a bar is
    in the read when the cursor is within its horizontal extent. On a
    stacked row that is one segment, not the whole row — and at a given x
    the two rows can be inside different series, which is the read the
    old tooltip could not give at all."""
    rects = chart_page.evaluate(FILL_RECTS, "#stacked")
    assert len(rects) == 4, rects
    # Halfway across: alpha splits 4/6 so the line is in its second
    # series, beta splits 6/4 so the line is still in its first.
    row_left, row_right = rects[0]["left"], rects[1]["right"]
    x = row_left + (row_right - row_left) * 0.5
    chart_page.mouse.move(x, (rects[0]["top"] + rects[0]["bottom"]) / 2)
    stable(chart_page, TIP, what="the cursor read settled")

    tip = chart_page.evaluate(TIP)
    assert tip, "no tooltip on the stacked chart"
    assert tip["names"] == ["alpha \u00b7 two", "beta \u00b7 one"], tip["names"]
    assert tip["values"] == ["6", "6"], tip["values"]
    # Two series, two colours — here the chip is the key to which is
    # which, so it appears.
    assert tip["swatches"] == 2, "a two-colour read carries its colour key"
    # The rows disagree about what their shares are shares of, so the
    # footer is left out rather than stating one row's total over both.
    assert tip["footer"] == "", tip["footer"]


def test_clicking_pins_the_read_and_escape_releases_it(chart_page) -> None:
    rects = chart_page.evaluate(FILL_RECTS, "#single")
    x = rects[3]["right"] - 2
    y = (rects[3]["top"] + rects[3]["bottom"]) / 2
    chart_page.mouse.move(x, y)
    stable(chart_page, TIP, what="the cursor read settled")
    chart_page.mouse.click(x, y)
    until(
        chart_page,
        "() => !!document.querySelector('.okc-tooltip.visible.pinned')",
        what="the click pinned the read",
    )

    pinned = chart_page.evaluate(TIP)
    assert pinned and pinned["pinned"], "click did not pin the read"

    # Moving away leaves a pinned read alone — that is what pinning is.
    chart_page.mouse.move(rects[0]["right"] + 40, y)
    # The claim is that nothing happens, so the wait is for the read to
    # be given every chance to change and not do so.
    stable(chart_page, TIP, what="the pinned read stayed put")
    still = chart_page.evaluate(TIP)
    assert still and still["names"] == pinned["names"], "a pinned read followed the pointer"

    chart_page.keyboard.press("Escape")
    until(
        chart_page,
        "() => !document.querySelector('.okc-tooltip.visible')",
        what="Escape released the pin",
    )
    assert chart_page.evaluate(TIP) is None, "Escape did not release the pin"


def test_the_card_lands_beside_the_cursor_and_above_the_bars(chart_page) -> None:
    """`.okc-tooltip` is `position: fixed`, so its left/top are viewport
    coords. Passing host-relative ones — a number near zero — pinned the
    card to the viewport's left edge no matter which bar was read; that
    shipped once. A source-text check cannot tell the two apart, so it is
    measured: the card sits near the cursor's x and clear of the rows it
    is listing.
    """
    rects = chart_page.evaluate(FILL_RECTS, "#single")
    x = rects[3]["right"] - 2
    _hover_at(chart_page, "#single", x, 3)
    tip = chart_page.evaluate(TIP)
    box = tip["box"]

    assert box["left"] > 20, f"the card is pinned to the viewport edge: {box}"
    centre = (box["left"] + box["right"]) / 2
    assert abs(centre - x) <= box["right"] - box["left"], (
        f"the card centre {centre:.0f} is not near the cursor at x={x:.0f}: {box}"
    )
    # Clear of the plot: a four-row list hung off the pointer covers the
    # bars it just listed.
    assert box["bottom"] <= rects[0]["top"] + 2, (
        f"the card overlaps the first row it is reading: {box} vs bar top {rects[0]['top']:.0f}"
    )
