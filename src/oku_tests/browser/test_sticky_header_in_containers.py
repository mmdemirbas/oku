"""A table's header sticks to the box the reader scrolls, wherever the
table is put.

`position: sticky` sticks to the NEAREST scroll container, and its
inset is measured inside that box's padding. Two places broke one of
those and neither was visible in a test that only put a table in prose:

- A copy region clipped its rounded corners with `overflow: hidden`,
  which makes the card a scroll container. A table inside it stuck to
  the card — a box that never scrolls — so the header never followed
  the reader, and at rest the viewport's parking offset pushed it 11px
  down over the first row.
- The markdown viewer's scroll box has 28px of top padding, and the
  stuck header parked 28px below the box's edge with rows scrolling
  through the strip above it.

Both are asserted from the reader's side: at rest the header is the
table's first row, and scrolled past, the cell at the top of what the
reader scrolls is a header cell carrying the column's label.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import measured, page_quiet

pytestmark = pytest.mark.browser

ROWS = 60


def _table(tag: str, cols: int) -> str:
    head = "| " + " | ".join(f"{tag}col{c}" for c in range(cols)) + " |"
    align = "|" + "---|" * cols
    rows = ["| " + " | ".join(f"{tag}r{i}c{c}" for c in range(cols)) + " |" for i in range(ROWS)]
    return "\n".join([head, align, *rows])


def _copy(table: str, title: str = "") -> str:
    # Untitled, the table is the card's first child and sits inside the
    # parking offset — the shape where the header was pushed over a row.
    payload = {"t": title, "b": table} if title else {"b": table}
    return "```oku-copy\n" + json.dumps(payload) + "\n```"


TAIL = "\n\n".join("Paragraph after the tables, so the page scrolls on." for _ in range(60))
PAGE_MD = f"""---
title: Tables in containers
summary: Tables inside a copy region, and inside a viewed file.
---

## A fitting table in a copy region {{#copy-fit}}

{_copy(_table("cf", 3))}

## A wide table in a copy region {{#copy-wide}}

{_copy(_table("cw", 16), "Take this")}

## The viewed file {{#viewed}}

Open [`viewed.md`](#f/../src/viewed.md).

{TAIL}
"""

VIEWED_MD = f"""# Viewed

An opening paragraph.

## A fitting table

{_table("vf", 3)}

## A wide table

{_table("vw", 16)}

## A table in a copy region

{_copy(_table("vc", 3))}

## After

{TAIL}
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("containers") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "viewed.md").write_text(VIEWED_MD, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Tables in containers"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


def _open(browser, built, width: int, scale: float):
    context = browser.new_context(viewport={"width": width, "height": 800})
    if scale != 1:
        context.add_init_script(f"localStorage.setItem('oku-text-scale', '{scale}')")
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")
    return context, page


# The header the reader sees: the ghost when it is stuck, else the
# table's own. `host` is the .okt-table-wrap.
SHOWN = """(wrap) => { const g = wrap.querySelector('.okt-table-ghost');
  return (g && g.dataset.stuck === '1') ? g : wrap.querySelector('.okt-table-scroll thead th'); }"""

# What a reader finds at a given y in the table's first column.
FOUND_AT = f"""(wrap, y) => {{
  const th = wrap.querySelector('.okt-table-scroll thead th');
  const el = document.elementFromPoint(th.getBoundingClientRect().left + 6, y);
  const cell = el && el.closest('th, td');
  return {{ label: th.textContent.trim(), found: cell ? cell.textContent.trim() : null,
           tag: cell ? cell.tagName : null, top: ({SHOWN})(wrap).getBoundingClientRect().top }};
}}"""


def _page_wrap(sel: str) -> str:
    return f"document.querySelector({sel!r}).closest('section').querySelector('.okt-table-wrap')"


@pytest.mark.parametrize("sel", ["#copy-fit", "#copy-wide"])
@pytest.mark.parametrize("width", [1280, 360])
def test_a_table_in_a_copy_region_sits_on_its_own_table(built, browser, sel, width):
    context, page = _open(browser, built, width, 1)
    try:
        page.evaluate(
            f"() => {{ const r = {_page_wrap(sel)}.getBoundingClientRect(); window.scrollTo(0, scrollY + r.top - 300); }}"
        )
        geo = measured(
            page,
            f"""() => {{ const s = {_page_wrap(sel)}.querySelector('.okt-table-scroll');
              const th = s.querySelector('thead th').getBoundingClientRect();
              return {{ table: s.querySelector('table').getBoundingClientRect().top, th: th.top,
                        thBottom: th.bottom, row: s.querySelector('tbody tr').getBoundingClientRect().top }}; }}""",
        )
        assert abs(geo["th"] - geo["table"]) < 1, (
            f"header {geo['th'] - geo['table']:.1f}px below its table's top"
        )
        assert geo["row"] >= geo["thBottom"] - 1, (
            f"first row at {geo['row']:.1f} under a header ending {geo['thBottom']:.1f}"
        )
    finally:
        context.close()


@pytest.mark.parametrize("sel", ["#copy-fit", "#copy-wide"])
@pytest.mark.parametrize(("width", "scale"), [(1280, 1), (360, 1), (1280, 1.25)])
def test_a_table_in_a_copy_region_keeps_its_header_in_view(built, browser, sel, width, scale):
    context, page = _open(browser, built, width, scale)
    try:
        page.evaluate(
            f"() => {{ const r = {_page_wrap(sel)}.getBoundingClientRect(); window.scrollTo(0, scrollY + r.top + 600); }}"
        )
        floor = measured(
            page,
            f"() => parseFloat(getComputedStyle({_page_wrap(sel)}).getPropertyValue('--okt-sticky-top'))",
        )
        hit = measured(page, f"() => ({FOUND_AT})({_page_wrap(sel)}, {floor} + 8)")
        assert hit["found"] == hit["label"], (
            f"under the rail the reader finds {hit['found']!r} ({hit['tag']}), not the {hit['label']!r} header"
        )
        assert abs(hit["top"] - floor) < 1, f"the header parks at {hit['top']:.1f}, the floor is {floor:.1f}"
    finally:
        context.close()


@pytest.mark.parametrize("nth", [0, 1, 2], ids=["fitting", "wide", "copy-region"])
@pytest.mark.parametrize(("width", "scale"), [(1280, 1), (360, 1), (1280, 1.25)])
def test_a_table_in_the_viewer_sticks_to_the_viewers_edge(built, browser, nth, width, scale):
    context, page = _open(browser, built, width, scale)
    try:
        page.locator("main .okt-fp .okt-fp-label", has_text="viewed.md").first.click()
        page.wait_for_selector(".okt-mdview-rendered section", state="attached")
        wrap = f"document.querySelectorAll('.okt-mdview-body .okt-table-wrap')[{nth}]"
        page.evaluate(
            f"""() => {{ const body = document.querySelector('.okt-mdview-body');
              body.scrollTop += {wrap}.getBoundingClientRect().top - body.getBoundingClientRect().top + 600; }}"""
        )
        edge = measured(page, "() => document.querySelector('.okt-mdview-body').getBoundingClientRect().top")
        hit = measured(page, f"() => ({FOUND_AT})({wrap}, {edge} + 3)")
        assert hit["found"] == hit["label"], (
            f"at the viewer's top edge the reader finds {hit['found']!r} ({hit['tag']}), not the {hit['label']!r} header"
        )
        assert abs(hit["top"] - edge) < 1, (
            f"the header parks {hit['top'] - edge:.1f}px below the viewer's edge"
        )
    finally:
        context.close()
