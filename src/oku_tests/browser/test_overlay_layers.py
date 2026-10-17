"""What the kit draws inside an overlay is drawn on top of it, at its own size.

The lightbox is a fixed layer at z-index 1000 — the markdown viewer and
every expanded table, chart and diagram live in it. Three things drawn
for a reader inside it were not seen:

- A hover card (file chip, glossary term, ext-ref) is mounted on
  `<body>` at z-index 300, so a card for a trigger inside the overlay
  opened UNDER it: the trigger highlighted and no card, in the viewer
  and in an expanded table.
- An expanded table's controls row kept the `z-index: 3` it carries on
  the page and painted over the lightbox's close button, which sits in
  the same corner: the reader saw the table's expand icon where the ×
  should be.
- A chart's reading inside the pan/zoom stage is inside the stage's
  transform, so it was drawn at the stage's scale — from a quarter of
  its size to twelve times it.

Each is asserted from the reader's side: what is under the pointer at
the thing's own corners, and how big it is drawn.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import measured, page_quiet, until

pytestmark = pytest.mark.browser

COLS = 9
TABLE = "\n".join(
    [
        "| " + " | ".join(f"col{c}" for c in range(COLS)) + " |",
        "|" + "---|" * COLS,
        *(
            "| [`notes.md`](#f/../src/notes.md) | "
            + " | ".join(f"value {r}-{c}" for c in range(1, COLS))
            + " |"
            for r in range(6)
        ),
    ]
)

PAGE_MD = f"""---
title: Overlays
summary: What is drawn inside an overlay is drawn on top of it.
---

## Files {{#files}}

A file to open: [`viewed.md`](#f/../src/viewed.md), and one to preview: [`notes.md`](#f/../src/notes.md).

## Table {{#tbl}}

{TABLE}

## Chart {{#chart}}

```oku-chart
{{"type": "line", "title": "Latency", "x_label": "Day", "y_label": "ms", "series": [{{"label": "a", "data": [{{"x": 1, "y": 142}}, {{"x": 2, "y": 155}}, {{"x": 3, "y": 138}}, {{"x": 4, "y": 161}}]}}]}}
```
"""

VIEWED_MD = """# Viewed

A chip inside the viewed file: [`notes.md`](notes.md) is beside it, as [`notes.md`](#f/notes.md).
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("overlays") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "viewed.md").write_text(VIEWED_MD, encoding="utf-8")
    (root / "src" / "notes.md").write_text("# Notes\n\n" + "A line of notes.\n\n" * 20, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


def _open(browser, built, width: int = 1280):
    context = browser.new_context(viewport={"width": width, "height": 800})
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    return context, page


# Who is under the pointer at the card's centre and two corners.
CARD_ON_TOP = """() => {
  const c = [...document.querySelectorAll('body > .oku-tooltip')].pop();
  if (!c) return null;
  const b = c.getBoundingClientRect();
  return [[b.left + b.width / 2, b.top + b.height / 2], [b.left + 4, b.top + 4], [b.right - 4, b.bottom - 4]]
    .map(([x, y]) => { const h = document.elementFromPoint(x, y); return h ? (c.contains(h) ? 'card' : h.className || h.tagName) : 'off'; });
}"""


def _hover(page, locator) -> None:
    b = locator.bounding_box()
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    page.mouse.move(x - 20, y + 20)
    page.mouse.move(x, y, steps=5)
    until(page, "() => !!document.querySelector('body > .oku-tooltip')", what="a hover card opened")


def test_a_card_on_the_page_is_on_top(built, browser):
    """The control: the same card from the page."""
    context, page = _open(browser, built)
    try:
        _hover(page, page.locator("main .okt-fp", has_text="notes.md").first)
        assert measured(page, CARD_ON_TOP) == ["card"] * 3
    finally:
        context.close()


def test_a_card_from_inside_the_viewer_is_on_top(built, browser):
    context, page = _open(browser, built)
    try:
        page.locator("main .okt-fp .okt-fp-label", has_text="viewed.md").first.click()
        until(page, "() => !!document.querySelector('.okt-mdview-rendered .okt-fp')")
        _hover(page, page.locator(".okt-mdview-rendered .okt-fp").first)
        assert measured(page, CARD_ON_TOP) == ["card"] * 3, "the card opened under the viewer"
    finally:
        context.close()


def _expand_table(page) -> None:
    wrap = page.locator("#tbl").locator("xpath=ancestor-or-self::section").locator(".okt-table-wrap").first
    wrap.scroll_into_view_if_needed()
    wrap.hover()
    wrap.locator("button[title*='xpand'], button[aria-label*='xpand']").first.click(force=True)
    until(page, "() => !!document.querySelector('.okt-lightbox.open .okt-table-wrap')")


def test_a_card_from_inside_an_expanded_table_is_on_top(built, browser):
    context, page = _open(browser, built)
    try:
        _expand_table(page)
        _hover(page, page.locator(".okt-lightbox.open .okt-fp").first)
        assert measured(page, CARD_ON_TOP) == ["card"] * 3, "the card opened under the expanded table"
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280, 360])
def test_the_close_button_of_an_expanded_table_is_on_top_and_clear(built, browser, width):
    context, page = _open(browser, built, width)
    try:
        _expand_table(page)
        got = measured(
            page,
            """() => { const lb = document.querySelector('.okt-lightbox.open');
              const x = lb.querySelector('.okt-lightbox-close'); const b = x.getBoundingClientRect();
              const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
              const overlap = [...lb.querySelectorAll('.okt-table-controls button, .okt-table-controls input')]
                .filter(e => { const r = e.getBoundingClientRect(); return r.width && r.left < b.right && r.right > b.left && r.top < b.bottom && r.bottom > b.top; })
                .map(e => e.getAttribute('title') || e.className);
              return { onTop: !!hit && x.contains(hit), overlap }; }""",
        )
        assert got["onTop"], "the lightbox's close button is painted under the table's controls"
        assert got["overlap"] == [], f"controls drawn in the close button's corner: {got['overlap']}"
    finally:
        context.close()


def _reading_size(page, dot) -> float:
    b = dot.bounding_box()
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    page.mouse.move(x - 3, y)
    page.mouse.move(x, y)
    until(page, "() => !!document.querySelector('.okc-tooltip.visible')")
    return measured(
        page,
        "() => [...document.querySelectorAll('.okc-tooltip.visible')].pop().getBoundingClientRect().height",
    )


@pytest.mark.parametrize("presses", [0, 2, 4])
def test_an_expanded_charts_reading_is_drawn_at_its_own_size(built, browser, presses):
    context, page = _open(browser, built)
    try:
        chart = page.locator("oku-chart", has=page.locator(".okc-dot")).first
        chart.scroll_into_view_if_needed()
        on_page = _reading_size(page, chart.locator(".okc-dot").nth(1))
        page.mouse.move(5, 5)
        chart.evaluate("c => c.querySelector('button[title=\"Expand to fullscreen\"]').click()")
        until(page, "() => !!document.querySelector('.okt-lightbox .okc-dot')")
        for _ in range(presses):
            page.keyboard.press("+")
        page.wait_for_timeout(300)
        nth = page.evaluate(
            """() => { const st = document.querySelector('.okt-lightbox-pz').getBoundingClientRect();
              const mx = (st.left + st.right) / 2, my = (st.top + st.bottom) / 2; let best = -1, bd = 1e9;
              document.querySelectorAll('.okt-lightbox .okc-dot').forEach((d, i) => { const r = d.getBoundingClientRect();
                const dd = Math.hypot(r.left + r.width / 2 - mx, r.top + r.height / 2 - my); if (dd < bd) { bd = dd; best = i; } });
              return best; }"""
        )
        expanded = _reading_size(page, page.locator(".okt-lightbox .okc-dot").nth(nth))
        assert abs(expanded / on_page - 1) < 0.03, (
            f"after {presses} zoom steps the reading is {expanded:.0f}px tall, {on_page:.0f}px on the page"
        )
    finally:
        context.close()
