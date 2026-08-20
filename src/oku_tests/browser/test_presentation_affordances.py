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

## Cards the pointer will cross {{#cards}}

```oku-kpi-grid
{{"tiles":[{{"num":"12","label":"files per minute per bucket"}},
 {{"num":"5s","label":"checkpoint interval"}},
 {{"num":"1.24x","label":"decode cost, realtime"}}]}}
```

```oku-step-flow
{{"steps":[{{"t":"Write","b":"{PARA}","meta":"streaming"}},
 {{"t":"Compact","b":"{PARA}","meta":"batch"}}]}}
```

```oku-compare-grid
{{"cards":[{{"t":"Before","b":"{PARA}","verdict":"out"}},
 {{"t":"After","b":"{PARA}","verdict":"in"}}]}}
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


def test_table_controls_are_quiet_at_rest_and_never_invisible(rendered):
    """Quiet is a floor, not zero.

    At `opacity: 0` the toolbar was an invisible control: a reader who
    never happened to sweep the pointer across a table had no way to
    learn that a filter box, a row count, two copy buttons and a gear
    were sitting above it. That is the invisible-toggle state UI
    invariant 2 forbids, and here it cost the whole bar — which is how
    it was found, as "tables seem to have lost some features".

    `pointer-events: none` stays. The bar is inside the wrap, so a
    pointer moving onto it hovers the wrap and the controls arm before
    any click can land; what the rule prevents is a quiet control
    catching a click meant for the table."""
    got = rendered.evaluate(
        """() => {
        const c = document.querySelector('#big .okt-table-controls');
        const s = getComputedStyle(c);
        return { opacity: parseFloat(s.opacity), pointer: s.pointerEvents,
                 floor: parseFloat(getComputedStyle(document.documentElement)
                          .getPropertyValue('--chrome-floor')) };
    }"""
    )
    assert got["opacity"] == got["floor"], got
    assert 0.25 <= got["floor"] < 1, got
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
    # Wait for the fade to FINISH, not for 300ms. A fixed sleep long
    # enough on an idle machine is not long enough on a loaded one, and
    # this assertion is about where the table sits once the controls are
    # up — not about how fast they get there. Same fix already applied to
    # the theme-expiry and program-line-count tests.
    rendered.wait_for_function(
        "() => getComputedStyle(document.querySelector('#big .okt-table-controls')).opacity === '1'",
        timeout=10000,
    )
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


# ---------- chrome buttons ----------


def _ctrl(page, sel):
    return page.evaluate(
        """(sel) => {
        const b = document.querySelector(sel);
        const r = b.getBoundingClientRect();
        return { opacity: parseFloat(getComputedStyle(b).opacity),
                 box: [Math.round(r.x), Math.round(r.y),
                       Math.round(r.width), Math.round(r.height)] };
    }""",
        sel,
    )


def _approach(page, sel, gap=20):
    """Park the pointer `gap` px below the named button.

    Derived from the button's own rect, never a hardcoded corner. The
    fixed point these tests used to aim at was chosen when theme was the
    rightmost button in the cluster; the moment width took that slot,
    theme sat 36px away and read 0.97 — a passing test failing on a
    change it was never about. Outside the box, so `:hover` is not what
    is being measured: at 20px the cosine falloff gives 0.991, and only
    the proximity path can produce that."""
    box = _ctrl(page, sel)["box"]
    page.mouse.move(box[0] + box[2] / 2, box[1] + box[3] + gap)
    page.wait_for_timeout(300)


def test_chrome_buttons_quiet_down_when_the_pointer_is_elsewhere(rendered):
    """Four opaque 44px boxes float over the top of the reading column at
    every scroll position, competing with the cover for the first thing
    the eye lands on. They fade to a hint when nothing is reaching for
    them and come back up on approach — per button, so walking toward
    the theme cycler brings the theme cycler up.

    The floor is not zero and the box does not change: a control the
    reader cannot see is a control the reader cannot find, and a control
    that resizes as you approach is one you have to chase."""
    rendered.mouse.move(700, 700)
    rendered.wait_for_timeout(300)
    far = _ctrl(rendered, ".theme-toggle")

    _approach(rendered, ".theme-toggle")
    near = _ctrl(rendered, ".theme-toggle")

    rendered.mouse.move(700, 700)
    rendered.wait_for_timeout(300)

    assert 0.2 < far["opacity"] < 0.5, f"dimmed out of existence, or not dimmed: {far}"
    assert near["opacity"] > 0.98, f"the button did not come back on approach: {near}"
    assert far["box"] == near["box"], "the button moved or resized as the pointer approached"


def test_approaching_one_cluster_leaves_the_other_alone(rendered):
    """Proximity is per button, measured to the button's BOX. A single
    top-of-page threshold would light the whole strip whenever the
    pointer crossed y=100, which is every scroll gesture."""
    _approach(rendered, ".theme-toggle")
    got = {
        "theme": _ctrl(rendered, ".theme-toggle")["opacity"],
        "drawer": _ctrl(rendered, ".drawer-toggle")["opacity"],
    }
    rendered.mouse.move(700, 700)
    rendered.wait_for_timeout(300)
    assert got["theme"] > 0.98, got
    assert got["drawer"] < 0.5, f"the far cluster lit up too: {got}"


def test_the_dimming_never_arms_without_a_pointer(afford_url, browser):
    """A touch device has no approach to detect, and a browser where the
    script never ran has no proximity at all. Both must see full-strength
    controls — the attribute the stylesheet keys off is set only once a
    fine pointer has actually moved."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        page.goto(f"{afford_url}/page.html")
        page.wait_for_timeout(1500)
        page.tap(".drawer-toggle")
        page.wait_for_timeout(300)
        got = page.evaluate(
            """() => ({
            armed: document.body.getAttribute('data-ctrl-proximity'),
            theme: parseFloat(getComputedStyle(document.querySelector('.theme-toggle')).opacity),
        })"""
        )
        assert got["armed"] is None, f"touch armed the proximity dimming: {got}"
        assert got["theme"] > 0.98, got
    finally:
        page.close()
        ctx.close()


def test_touch_keeps_the_controls_reachable(afford_url, browser):
    """Hover-to-reveal has no meaning without a pointer. On a device
    reporting `hover: none` the bar must stay visible, or filtering and
    expanding a table become unreachable — the failure the desktop
    measurement above cannot see."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    try:
        page.goto(f"{afford_url}/page.html")
        page.wait_for_timeout(1500)
        got = page.evaluate(
            """() => {
            const c = document.querySelector('#big .okt-table-controls');
            const s = getComputedStyle(c);
            return { hoverNone: matchMedia('(hover: none)').matches,
                     opacity: s.opacity, pointer: s.pointerEvents };
        }"""
        )
        assert got["hoverNone"], f"the context did not emulate a touch device: {got}"
        assert got["opacity"] == "1", got
        assert got["pointer"] == "auto", got
    finally:
        page.close()
        ctx.close()


# ---------- hovering a card ----------

CARDS = [
    (".kpi", ".num"),
    (".step-card", ".step-num"),
    (".compare-card", ".compare-card-title, h3, h4"),
]


@pytest.mark.parametrize(("card", "inner"), CARDS, ids=[c[0].lstrip(".") for c in CARDS])
def test_hovering_a_card_does_not_move_what_is_written_on_it(rendered, card, inner):
    """A card answers the pointer with light, never with position.

    Every card kind used to hover with `transform: translateY(-2px)`,
    which takes the card's content up with it. Two pixels is too small
    to read as an effect and exactly the right size to read as a
    rendering fault, and it fired on every card the pointer crossed on
    its way somewhere else.

    So: the card's box, and the box of the text on it, are identical at
    rest and under the pointer — to the pixel, not to a tolerance. A
    tolerance is what a 2px nudge hides in."""
    # Scroll first, measure second. `hover()` scrolls its target into
    # view, and a viewport-relative reading taken across that scroll
    # reports a move that has nothing to do with the hover.
    rendered.locator(card).first.scroll_into_view_if_needed()
    # x=2 is left of the reading column at every width, so parking there
    # is off every card whatever scrolled into view.
    rendered.mouse.move(2, 450)
    rendered.wait_for_timeout(300)
    probe = """([card, inner]) => {
        const el = document.querySelector(card);
        const t = el.querySelector(inner) || el;
        const r = e => { const b = e.getBoundingClientRect();
                         return [b.x, b.y, b.width, b.height].map(v => Math.round(v * 100) / 100); };
        return { card: r(el), text: r(t), shadow: getComputedStyle(el).boxShadow };
    }"""
    before = rendered.evaluate(probe, [card, inner])

    rendered.hover(card)
    rendered.wait_for_timeout(400)
    during = rendered.evaluate(probe, [card, inner])

    rendered.mouse.move(2, 450)
    rendered.wait_for_timeout(250)

    assert during["card"] == before["card"], f"{card} moved or resized under the pointer: {before} → {during}"
    assert during["text"] == before["text"], (
        f"the text on {card} moved under the pointer: {before} → {during}"
    )
    # And the raise still happens — a test that only pins stillness
    # passes just as well on a card that stopped responding at all.
    assert during["shadow"] != before["shadow"], f"{card} no longer answers the pointer: {during['shadow']}"


def test_hovering_a_contents_entry_does_not_slide_its_label(rendered):
    """Same rule, applied where the pointer crosses the most items in a
    row. The tree entry used to grow its left padding 8px → 12px on
    hover, so every label the reader passed over on the way down the
    panel stepped right and back."""
    rendered.evaluate("() => document.querySelector('.drawer-toggle').click()")
    rendered.wait_for_timeout(400)
    link = rendered.locator("page-nav .page-nav-item > a").first
    before = link.bounding_box()
    link.hover()
    rendered.wait_for_timeout(300)
    during = link.bounding_box()
    got = rendered.evaluate(
        "() => getComputedStyle(document.querySelector('page-nav .page-nav-item > a')).backgroundColor"
    )
    rendered.keyboard.press("Escape")
    rendered.wait_for_timeout(300)
    assert before and during
    assert during["x"] == before["x"] and during["width"] == before["width"], (
        f"the tree label slid under the pointer: {before} → {during}"
    )
    assert got, "the entry needs some hover cue left after the padding shift was removed"


# ---------- timeline ----------

TIMELINE_MD = """---
title: Timeline
summary: An ordered sequence where each entry carries a state.
---

## What happened {#story}

```oku-timeline
{"events":[
 {"status":"open","label":"claim #1","t":"First reading","b":"Plausible, and unverified."},
 {"status":"dropped","label":"corrected","t":"Over-stated","b":"Swung the other way. Also premature."},
 {"status":"done","label":"verified","t":"Pinned it","b":"Instrumented the path. Fixed."},
 {"t":"A plain entry with no status"}
]}
```
"""


@pytest.fixture(scope="module")
def timeline_page(tmp_path_factory, browser):
    d = tmp_path_factory.mktemp("tl")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.md", "title": "Timeline", "parent": None}],
    }
    (d / "page.md").write_text(TIMELINE_MD, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("Timeline", inline_manifest=manifest), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/page.html")
    page.wait_for_timeout(1500)
    yield page
    page.close()
    httpd.shutdown()


def test_a_timeline_renders_every_event_in_order(timeline_page):
    """The fence lifts to a typed block and the block reaches the DOM.
    Four events in, four items out, in source order — a primitive whose
    payload the renderer cannot read renders a band of white space, and
    the reader gets no clue which block it was."""
    got = timeline_page.evaluate(
        """() => {
        const l = document.querySelector('ol.okt-timeline');
        if (!l) return null;
        return [...l.querySelectorAll('li')].map(li => ({
            cls: li.className,
            chip: (li.querySelector('.okt-tl-chip') || {}).textContent || null,
            title: (li.querySelector('.okt-tl-title') || {}).textContent || null,
            body: !!li.querySelector('.okt-tl-body'),
        }));
    }"""
    )
    assert got, "the oku-timeline fence produced no ol.okt-timeline"
    assert [e["title"] for e in got] == [
        "First reading",
        "Over-stated",
        "Pinned it",
        "A plain entry with no status",
    ], got
    assert [e["chip"] for e in got] == ["claim #1", "corrected", "verified", None], got
    # An event with no status falls back to `note`, never to no class at
    # all — an unclassed item takes the rail's default dot and silently
    # stops being distinguishable from a settled one.
    assert [e["cls"].split()[-1] for e in got] == [
        "okt-tl-open",
        "okt-tl-dropped",
        "okt-tl-done",
        "okt-tl-note",
    ], got
    assert [e["body"] for e in got] == [True, True, True, False], got


def test_every_timeline_dot_sits_on_the_rail(timeline_page):
    """The rail and the dots are two independent CSS rules — the rail is
    positioned from the list, each dot from its own item — so nothing
    but a measurement keeps them on the same axis. They drift the moment
    the list's padding is tuned and the offset is not."""
    got = timeline_page.evaluate(
        """() => {
        const l = document.querySelector('ol.okt-timeline');
        const rail = getComputedStyle(l, '::before');
        const lx = l.getBoundingClientRect().x;
        const railLeft = lx + parseFloat(rail.left);
        const railMid = railLeft + parseFloat(rail.width) / 2;
        const dots = [...l.querySelectorAll('li')].map(li => {
            const s = getComputedStyle(li, '::before');
            const left = li.getBoundingClientRect().x + parseFloat(s.left);
            return Math.round((left + parseFloat(s.width) / 2) * 10) / 10;
        });
        return { railMid: Math.round(railMid * 10) / 10, dots };
    }"""
    )
    assert got["dots"], got
    for d in got["dots"]:
        assert abs(d - got["railMid"]) <= 0.5, f"a dot sits {d - got['railMid']}px off the rail: {got}"


def test_a_narrow_timeline_keeps_its_dots_on_the_rail(timeline_page):
    """The narrow-width override moves the list's padding AND the dot's
    offset. Moving one alone is the whole failure mode, and it only
    shows below 560px."""
    timeline_page.set_viewport_size({"width": 380, "height": 800})
    timeline_page.wait_for_timeout(300)
    got = timeline_page.evaluate(
        """() => {
        const l = document.querySelector('ol.okt-timeline');
        const rail = getComputedStyle(l, '::before');
        const railMid = l.getBoundingClientRect().x + parseFloat(rail.left) + parseFloat(rail.width) / 2;
        const li = l.querySelector('li');
        const s = getComputedStyle(li, '::before');
        const dotMid = li.getBoundingClientRect().x + parseFloat(s.left) + parseFloat(s.width) / 2;
        return { railMid: Math.round(railMid * 10) / 10, dotMid: Math.round(dotMid * 10) / 10,
                 overflows: document.documentElement.scrollWidth > document.documentElement.clientWidth };
    }"""
    )
    timeline_page.set_viewport_size({"width": 1440, "height": 900})
    timeline_page.wait_for_timeout(200)
    assert abs(got["dotMid"] - got["railMid"]) <= 0.5, got
    assert not got["overflows"], f"the timeline pushed the page sideways at 380px: {got}"
