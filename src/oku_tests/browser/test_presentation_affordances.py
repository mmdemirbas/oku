"""What the page promises the reader, and whether it can keep it.

**Affordances with nothing behind them.** Every table row tinted under
the pointer, every card lifted, every mermaid node took a pointer
cursor — and none of them handled a click. A surface that invites a
click it will not answer makes the reader hesitate over the ones that
are real: "it makes me worry about clicking something wrong."

**Chrome in front of the content.** The table toolbar sat at 15%
opacity above the first row at all times, and the copy button had
landed between the filter and its own row counter.

**A boundary that cannot be found.** Card and list views painted
--surface cards on a --surface field, leaving a hairline as the whole
separation.

Measure divergence — the fourth report from the same round — has its
own file, test_presentation_measure.py.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PARA = (
    "Every checkpoint flushes whatever the writer has buffered, and a five-second "
    "checkpoint interval on a modestly sized topic produces twelve files per minute "
    "per bucket, none of them anywhere near the target size."
)

PAGE_MD = f"""---
title: Affordances
summary: One measure for running prose, and no promise the kit will not keep.
---

> [!TLDR]
> {PARA}

## Prose and its frames {{#prose}}

{PARA}

> [!IMPORTANT]
> {PARA}

{PARA}

## A table worth filtering {{#big}}

| Stage | Input | Output |
|---|---|---|
| a | 1 | x |
| b | 2 | x |
| c | 3 | x |
| d | 4 | x |
| e | 5 | x |
| f | 6 | x |
| g | 7 | x |
| h | 8 | x |

## A table whose rows go somewhere {{#links}}

<table>
<thead><tr><th>Stage</th><th>Input</th></tr></thead>
<tbody>
<tr data-href="#prose"><td>a</td><td>1</td></tr>
<tr data-href="#prose"><td>b</td><td>2</td></tr>
<tr data-href="#prose"><td>c</td><td>3</td></tr>
<tr data-href="#prose"><td>d</td><td>4</td></tr>
<tr data-href="#prose"><td>e</td><td>5</td></tr>
<tr data-href="#prose"><td>f</td><td>6</td></tr>
<tr data-href="#prose"><td>g</td><td>7</td></tr>
</tbody>
</table>

## A diagram nobody wired a click to {{#diagram}}

```mermaid
flowchart LR
  A[write] --> B[compact]
  B --> C[read]
```
"""


@pytest.fixture(scope="module")
def afford_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("afford")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.md", "title": "Affordances", "parent": None}],
    }
    (d / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("Affordances", inline_manifest=manifest), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def rendered(afford_url, browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{afford_url}/page.html")
    page.wait_for_timeout(1800)
    yield page
    page.close()


# ---------- table chrome ----------


def test_table_controls_are_invisible_and_inert_at_rest(rendered):
    """Same contract as the copy button on a code block. `opacity: 0`
    alone would leave an invisible control eating clicks, so the
    pointer-events half is part of the rule."""
    got = rendered.evaluate(
        """() => {
        const c = document.querySelector('#big .okt-table-controls');
        const s = getComputedStyle(c);
        return { opacity: s.opacity, pointer: s.pointerEvents };
    }"""
    )
    assert got["opacity"] == "0", got
    assert got["pointer"] == "none", got


def test_hovering_the_table_reveals_the_controls_without_moving_it(rendered):
    """The bar keeps its layout box while hidden — revealing it must not
    push the first row down."""
    # Offset from the wrap, not from the viewport — hover() scrolls the
    # target into view, which would move a viewport-relative reading for
    # a reason that has nothing to do with the controls.
    offset = """() => {
        const w = document.querySelector('#big .okt-table-wrap');
        const t = document.querySelector('#big table');
        return Math.round(t.getBoundingClientRect().top - w.getBoundingClientRect().top);
    }"""
    before = rendered.evaluate(offset)
    rendered.hover("#big tbody tr:first-child td:first-child")
    rendered.wait_for_timeout(300)
    got = rendered.evaluate(
        """() => {
        const c = document.querySelector('#big .okt-table-controls');
        const s = getComputedStyle(c);
        const w = document.querySelector('#big .okt-table-wrap');
        const t = document.querySelector('#big table');
        return { opacity: s.opacity, pointer: s.pointerEvents,
                 tableTop: Math.round(t.getBoundingClientRect().top - w.getBoundingClientRect().top) };
    }"""
    )
    assert got["opacity"] == "1", got
    assert got["pointer"] == "auto", got
    assert abs(got["tableTop"] - before) <= 1, (
        f"the table moved {got['tableTop'] - before}px when the controls appeared"
    )


def test_copy_sits_with_the_buttons_that_act_on_the_whole_table(rendered):
    """Copy used to land between the filter and its own row counter,
    splitting a pair that is read together ("I filtered — this many
    left"). It belongs with configure and expand."""
    xs = rendered.evaluate(
        """() => {
        const c = document.querySelector('#big .okt-table-controls');
        const x = sel => { const e = c.querySelector(sel);
                           return e ? Math.round(e.getBoundingClientRect().x) : null; };
        return { filter: x('.okt-filter'), stats: x('.okt-stats'),
                 copy: x('[data-copy]'), gear: x('[data-cfg]'), expand: x('[data-expand]') };
    }"""
    )
    assert xs["filter"] < xs["stats"] < xs["copy"] < xs["gear"] < xs["expand"], xs


def test_no_divider_before_the_gear(rendered):
    """The separator marked a boundary that stopped existing once copy
    moved across it."""
    n = rendered.evaluate("() => document.querySelectorAll('.okt-ctrl-sep-after').length")
    assert n == 0, f"{n} divider(s) still rendered"


# ---------- affordances that mean something ----------


def test_a_plain_row_does_not_light_up_under_the_pointer(rendered):
    """`table tr:hover td` tinted every row on every table. Nothing
    handled the click, so the reader learned to distrust the tint."""
    rendered.hover("#big tbody tr:nth-child(2) td:first-child")
    rendered.wait_for_timeout(200)
    got = rendered.evaluate(
        """() => {
        const td = document.querySelector('#big tbody tr:nth-child(2) td');
        return { bg: getComputedStyle(td).backgroundColor,
                 cursor: getComputedStyle(td.parentElement).cursor,
                 hovered: td.matches(':hover') };
    }"""
    )
    assert got["hovered"], "the test did not actually hover the row"
    assert got["bg"] in ("rgba(0, 0, 0, 0)", "transparent"), got
    assert got["cursor"] in ("auto", "default"), got


def test_a_row_that_does_go_somewhere_still_says_so(rendered):
    """The fix is scoped, not a deletion: a row carrying `data-href`
    keeps both the tint and the pointer."""
    rendered.hover("#links tbody tr:nth-child(2) td:first-child")
    rendered.wait_for_timeout(200)
    got = rendered.evaluate(
        """() => {
        const td = document.querySelector('#links tbody tr:nth-child(2) td');
        return { bg: getComputedStyle(td).backgroundColor,
                 cursor: getComputedStyle(td.parentElement).cursor,
                 hovered: td.matches(':hover') };
    }"""
    )
    assert got["hovered"], "the test did not actually hover the row"
    assert got["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"), got
    assert got["cursor"] == "pointer", got


def test_a_diagram_node_does_not_claim_to_be_clickable(rendered):
    """Every mermaid shape took `cursor: pointer` and an accent glow.
    Only a node the author bound with mermaid's `click` gets that, and
    this diagram binds none."""
    got = rendered.evaluate(
        """() => {
        const nodes = [...document.querySelectorAll('oku-diagram .okd-render svg .node')];
        return { n: nodes.length,
                 cursors: [...new Set(nodes.map(e => getComputedStyle(e).cursor))],
                 clickable: document.querySelectorAll('oku-diagram .okd-render svg .clickable').length };
    }"""
    )
    assert got["n"] >= 3, f"the diagram did not render: {got}"
    assert got["clickable"] == 0, got
    assert got["cursors"] == ["default"], got


# ---------- boundaries you can see ----------


def _rgb(s):
    return tuple(int(v) for v in s.replace("rgb(", "").replace("rgba(", "").rstrip(")").split(",")[:3])


def test_cards_sit_on_a_field_darker_than_the_cards(rendered):
    """Both were --surface, which left a 1px hairline as the only thing
    separating a card from the space around it."""
    rendered.evaluate("() => document.querySelector('#big [data-view=cards]').click()")
    rendered.wait_for_timeout(250)
    got = rendered.evaluate(
        """() => {
        const field = document.querySelector('#big .okt-table-cards');
        const card = document.querySelector('#big .okt-card');
        return { field: getComputedStyle(field).backgroundColor,
                 card: getComputedStyle(card).backgroundColor,
                 border: getComputedStyle(card).borderTopColor,
                 shadow: getComputedStyle(card).boxShadow };
    }"""
    )
    field, card = _rgb(got["field"]), _rgb(got["card"])
    assert field != card, f"the card and its field are the same colour: {got}"
    assert sum(card) - sum(field) >= 12, f"field/card separation is too small to see: {got}"
    assert got["shadow"] != "none", got


def test_a_card_sizes_to_its_own_content(rendered):
    """`align-items: start` — a stretched row leaves slack inside a card
    whose edge is now visible, and empty framed space reads as a fault."""
    hs = rendered.evaluate(
        """() => [...document.querySelectorAll('#big .okt-card')]
                 .map(c => Math.round(c.getBoundingClientRect().height))"""
    )
    assert hs, "no cards rendered"
    assert max(hs) - min(hs) <= 2 or len(set(hs)) > 1, hs
    align = rendered.evaluate(
        "() => getComputedStyle(document.querySelector('#big .okt-table-cards')).alignItems"
    )
    assert align == "start", align


def test_a_card_does_not_lift_under_a_pointer_that_cannot_click_it(rendered):
    """The hover transform said "button" on a card with no handler."""
    got = rendered.evaluate(
        """() => {
        const c = document.querySelector('#big .okt-card');
        return { cursor: getComputedStyle(c).cursor, transform: getComputedStyle(c).transform };
    }"""
    )
    assert got["cursor"] in ("auto", "default"), got
    rendered.hover("#big .okt-card")
    rendered.wait_for_timeout(250)
    after = rendered.evaluate("() => getComputedStyle(document.querySelector('#big .okt-card')).transform")
    assert after in ("none", got["transform"]), f"the card moved on hover: {after}"


def test_list_cards_carry_the_same_edge(rendered):
    """The list view has the same job and had the same defect."""
    rendered.evaluate("() => document.querySelector('#big [data-view=list]').click()")
    rendered.wait_for_timeout(250)
    got = rendered.evaluate(
        """() => {
        const field = document.querySelector('#big .okt-table-list');
        const card = document.querySelector('#big .okt-list-card');
        return { field: getComputedStyle(field).backgroundColor,
                 card: getComputedStyle(card).backgroundColor,
                 shadow: getComputedStyle(card).boxShadow };
    }"""
    )
    rendered.evaluate("() => document.querySelector('#big [data-view=table]').click()")
    assert _rgb(got["field"]) != _rgb(got["card"]), got
    assert got["shadow"] != "none", got
