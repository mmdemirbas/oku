"""A chart answers the pointer, and the answer is the chart's own.

One tooltip element per chart, two writers: the per-mark anchors, and
the vertical cursor that a dozen renderers wire. Both call the same
element up and down, and neither knew about the other.

Measured on beeswarm, bump and horizon before the fix: hovering a mark
built the tooltip with the right content — `Berlin · 2020 rank #1 value
80` on bump — and it never got `visible`. The anchor saw mouseover and
mouseenter and no leave, the tooltip is `pointer-events: none` and did
not overlap the mark, so nothing about the pointer explained it.

What did: `_wireGenericVerticalCursor` calls `_hideCursorTip()` on the
same branch where it hides its own line — a mousemove outside the plot
band, on either axis — and a data mark can sit outside the band its own
chart declares. Measured in viewBox units against the band the cursor
line spans: beeswarm's leftmost dot at x=22 and horizon's first hit rect
at x=65 are left of `pad.left`, and bump's top dot at y=34 is above a
band top of 36. The cursor line reads `hidden` at each of those three
points and `visible` at the middle of the same plot, which is what says
the branch rather than the pointer is the cause.

Whoever showed the tooltip owns it now, and only its owner may hide it.

A sweep rather than a list of three names, because the defect is a shape
— a renderer that wires both paths — and the next chart to take it
should fail here on the day it lands. Both selector sets are derived:
the chart types from `kit/schema/examples.json`, the mark families from
the `rich(...)` calls in `kit/chrome.js`, so a fifth family arrives as a
failure rather than as a hole.

The two cases at the bottom pin what a single-owner rule can break in
the other direction: leaving a mark must still take its reading away,
and the cursor must still hide what the cursor itself showed.

The file's second subject is what the reading OFFERS. Every tooltip in
the kit prints "click to pin", from three writers — `rich()` for the
anchors, `_showCursorTip` for the SVG cursors, and `showCrossing` for
the DIV-rendered bar charts — and only two of them had a click bound.
Measured on density and bump: the hint rendered, a click pinned nothing,
and moving the pointer away took the reading down. There is one case per
writer rather than one per chart, because that is the shape the failures
came in, and because the 53-case version was flaky — it hovers whichever
mark it can reach on a 53-chart page, and on `arc` that answer moved
between runs while arc pinned correctly three times out of three on a
page of its own.

The sweep skips nothing. It used to skip two, and the skip is what
found them: `density` and `violin` tagged no mark with a reading at all
and wired a line-only cursor — measured, density had 0 payloads and 0
native `<title>` elements, violin 0 payloads and 3 titles, and neither
showed a `.okc-tooltip` anywhere in the plot. So a chart with no mark
now falls through to its own cursor and has to read out there, which
turns "this chart's anchors work" into "this chart says something to a
reader who points at it". The last two cases assert what each of those
two says, rather than only that it says something: a tooltip carrying
the wrong median is worse than one carrying nothing, because the reader
believes it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet, scroll_stable, stable, until

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = json.loads((ROOT / "kit" / "schema" / "examples.json").read_text(encoding="utf-8"))["charts"]

CHROME = (ROOT / "kit" / "chrome.js").read_text(encoding="utf-8")

# What the kit binds a per-mark reading to, read out of the wiring pass
# rather than written down here. `[data-hover-payload]` is the generic
# one; the others are shapes the pass still binds by name.
#
# Two binders, because there are two. `rich(...)` covers the anchor
# path; the Cartesian dot has its own `showTip` pass bound by class, and
# leaving it out is what made this sweep skip bar, line, scatter, plot
# and eight more as "no mark carrying a reading" — the twelve most
# ordinary chart types on the page, silently exempt from the file
# asserting they answer the pointer.
MARK_FAMILIES = re.findall(r"\brich\('([^']+)'", CHROME)
assert len(MARK_FAMILIES) >= 4, MARK_FAMILIES
DOT_FAMILY = ".okc-dot"
# The same drift protection the regex gives the others: renaming the
# class fails here rather than turning every dot chart back into a skip.
assert f"querySelectorAll('{DOT_FAMILY}')" in CHROME, DOT_FAMILY
# Not scoped to `svg`. The kit's own binders are not — and a bar
# chart is HTML: `.okt-bar` divs carrying `data-hover-payload`, three
# of them on the shipped example. An `svg ` prefix here exempted bar,
# stacked-bar and grouped-bar from their own regression test while
# reporting it as "draws no mark carrying a reading".
MARKS = ", ".join([*MARK_FAMILIES, DOT_FAMILY])


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("hoverread") / "docs"
    docs.mkdir()
    body = ["---", "title: Hover", "summary: One of every chart type.", "---", ""]
    for name in sorted(EXAMPLES):
        body += [
            f"## {name} " + "{#" + name + "}",
            "",
            "```oku-chart",
            json.dumps(EXAMPLES[name], separators=(",", ":")),
            "```",
            "",
        ]
    (docs / "page.md").write_text("\n".join(body), encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Hover"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def page(built, browser):
    pg = browser.new_page(viewport={"width": 1280, "height": 1000})
    pg.goto(built.as_uri(), wait_until="load")
    page_quiet(pg)
    # Every chart has drawn. `page_quiet` waits for the document to stop
    # growing, and a chart that has not sized itself yet offers marks
    # with a zero-width box — which this file would report as "no point
    # on screen" for a chart that is merely late.
    until(
        pg,
        "() => document.querySelectorAll('svg.okc-svg').length"
        " === document.querySelectorAll('oku-chart').length",
        what="every chart drew its svg",
    )
    yield pg
    pg.close()


# A point ON the painted shape, asked of the browser rather than assumed
# to be the bounding-box centre. For an arc, a ring, or an L-shaped hit
# area that centre is frequently not on the mark at all, which is how a
# sweep like this reports a working chart as silent.
FIND_POINT = """([id, sel]) => {
  const sec = document.getElementById(id);
  const els = [...sec.querySelectorAll(sel)];
  const inventory = (n) => 'marks=' + n
    + ' cursors=' + sec.querySelectorAll('.okc-generic-cursor, .okc-cartesian-cursor').length
    + ' titles=' + sec.querySelectorAll('svg title').length;
  for (const e of els.slice(0, 12)) {
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    for (let fy = 0.3; fy < 1; fy += 0.2) {
      for (let fx = 0.3; fx < 1; fx += 0.2) {
        const x = r.left + r.width * fx, y = r.top + r.height * fy;
        if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
        const hit = document.elementFromPoint(x, y);
        if (hit === e || e.contains(hit)) return { x, y, marks: els.length, inventory: inventory(els.length) };
      }
    }
  }
  return { x: null, y: null, marks: els.length, inventory: inventory(els.length) };
}"""

# Scoped to the section. `document.querySelector('.okc-tooltip')` answers
# with the FIRST chart's tooltip, so an unscoped read reports every type
# but the alphabetically-first one as having none.
SHOWN = """(id) => {
  const t = [...document.getElementById(id).querySelectorAll('.okc-tooltip')]
    .find((e) => e.classList.contains('visible'));
  return t ? (t.textContent || '').trim() : null;
}"""


def _visible(chart: str, *, negate: bool = False) -> str:
    """A condition on the tooltip inside one section.

    `until` takes no argument to pass through, so the id is spliced in.
    """
    return (
        f"() => {'!' if negate else ''}[...document.getElementById('{chart}')"
        ".querySelectorAll('.okc-tooltip')].some((t) => t.classList.contains('visible'))"
    )


# A point inside the cursor's own band and on none of the marks — the
# only place the CURSOR is the writer. Hovering the middle of a plot is
# not enough: on a filled chart the middle is a mark, and the tooltip
# there belongs to the anchor.
CURSOR_ONLY_POINT = """([id, sel]) => {
  const sec = document.getElementById(id);
  const svg = sec.querySelector('svg.okc-svg');
  const line = svg.querySelector('.okc-generic-cursor');
  if (!line) return null;
  const r = svg.getBoundingClientRect();
  const vb = svg.viewBox.baseVal;
  const top = r.top + (+line.getAttribute('y1') / vb.height) * r.height;
  const bottom = r.top + (+line.getAttribute('y2') / vb.height) * r.height;
  const marks = [...sec.querySelectorAll(sel)];
  for (let fx = 0.35; fx < 0.7; fx += 0.05) {
    for (let f = 0.15; f < 0.9; f += 0.1) {
      const x = r.left + r.width * fx, y = top + (bottom - top) * f;
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
      const hit = document.elementFromPoint(x, y);
      if (hit && marks.some((m) => m === hit || m.contains(hit))) continue;
      if (!svg.contains(hit)) continue;
      return { x, y, belowBand: bottom + 30, leftOfBand: r.left + 2 };
    }
  }
  return null;
}"""


def _settle(page, chart: str) -> None:
    """The scroll has come to rest AND the chart has stopped moving
    under it.

    Two separate motions, and only the first is obvious. The kit scrolls
    smoothly, so a rect read mid-flight names a point the pointer will
    never be at. The second one cost a whole test: `network` runs a
    force layout, and a node picked while it was still relaxing had
    drifted out from under the pointer by the time the click landed —
    measured, the click's `composedPath` began at `svg.okc-svg`, with
    the node nowhere in it. That read as "the network refuses to pin"
    and was the mark walking away.
    """
    page.evaluate("(id) => document.getElementById(id).scrollIntoView({block: 'center'})", chart)
    scroll_stable(page)
    stable(
        page,
        "(id) => [...document.getElementById(id).querySelectorAll('svg *')].slice(0, 40)"
        ".map((e) => { const r = e.getBoundingClientRect();"
        "              return [Math.round(r.x), Math.round(r.y)]; })",
        arg=chart,
        what=f"{chart} stopped moving",
    )


def _hover_a_mark(page, chart: str):
    _settle(page, chart)
    pt = page.evaluate(FIND_POINT, [chart, MARKS])
    if not pt["marks"]:
        # Not this function's call what that means — a chart with no
        # mark may still have a cursor, and the caller decides.
        return pt
    assert pt["x"] is not None, f"{chart}: {pt['marks']} marks and none reachable on screen"
    # Arrive from off the mark: the anchor path is wired to mouseover,
    # and a pointer teleported onto the shape can land without one.
    page.mouse.move(pt["x"] - 14, pt["y"] - 14)
    page.mouse.move(pt["x"], pt["y"], steps=6)
    return pt


@pytest.mark.parametrize("chart", sorted(EXAMPLES))
def test_hovering_shows_a_reading(page, chart):
    """The sweep. A chart that tags a mark with a payload has promised a
    reading; a chart that draws a cursor and no marks has promised one
    too, and the cursor is the only place it can come from.

    Both branches, in that order, so the assertion is "this chart says
    something to a reader who points at it" rather than "this chart's
    anchors work". The second branch is what turned two standing skips
    into a requirement: density draws one curve and no marks, and its
    cursor swept the plot reporting nothing.
    """
    pt = _hover_a_mark(page, chart)
    if not pt["marks"]:
        spot = page.evaluate(CURSOR_ONLY_POINT, [chart, MARKS])
        if spot is None:
            # Self-reporting: the counts say whether this is a chart
            # with genuinely nothing to read, or one whose marks
            # stopped being found because a family was renamed out from
            # under the sweep.
            pytest.skip(f"{chart} tags no mark and draws no cursor ({pt['inventory']})")
        page.mouse.move(spot["x"] - 14, spot["y"] - 14)
        page.mouse.move(spot["x"], spot["y"], steps=6)
    until(page, _visible(chart), what=f"{chart} showed a reading under the pointer")
    text = page.evaluate(SHOWN, chart)
    # "click to pin" is the hint every reading carries. On its own it is
    # an empty tooltip wearing a footer, which would satisfy `visible`.
    assert text and text.replace("click to pin", "").strip(), f"{chart}: the reading is only the hint"
    page.mouse.move(4, 4)


def test_leaving_the_mark_takes_the_reading_away(page):
    """The half a single-owner rule is most likely to break. If the
    anchor kept ownership after the pointer left, the reading would stay
    up and no cursor could clear it."""
    _hover_a_mark(page, "beeswarm")
    until(page, _visible("beeswarm"), what="the reading appeared")
    page.mouse.move(4, 4)
    until(page, _visible("beeswarm", negate=True), what="the reading went when the pointer left the mark")


def test_the_cursor_still_hides_what_the_cursor_showed(page):
    """The other half. `bump` registers a `seriesLookup`, so its cursor
    writes a reading of its own at any x inside the band — and that one
    is still the cursor's to take down when the pointer leaves. A rule
    that only ever protected the anchor would strand it on screen."""
    _settle(page, "bump")
    pt = page.evaluate(CURSOR_ONLY_POINT, ["bump", MARKS])
    assert pt, "no point inside bump's cursor band that is off every mark"
    page.mouse.move(pt["x"], pt["y"], steps=4)
    until(page, _visible("bump"), what="the cursor wrote a reading inside the plot band")
    # Out of the band on the axis the guard is watching.
    page.mouse.move(pt["x"], pt["belowBand"], steps=4)
    until(page, _visible("bump", negate=True), what="the cursor took its own reading down outside the band")


# The violin's own arithmetic, so the assertion below is about the
# chart's reading and not about a string the chart happened to produce.
# Linear interpolation between order statistics — the same definition
# the renderer uses, written out here rather than imported, because a
# test that borrows the implementation cannot disagree with it.
def _five_number(values: list[float]) -> dict[str, str]:
    vs = sorted(values)

    def q(p: float) -> float:
        pos = (len(vs) - 1) * p
        i = int(pos)
        return vs[i] + (pos - i) * ((vs[i + 1] if i + 1 < len(vs) else vs[i]) - vs[i])

    def fixed(n: float, places: int) -> str:
        """`Number.prototype.toFixed`, which is not Python's `format`.

        JS rounds a tie AWAY FROM ZERO; Python rounds half to even. The
        difference is not exotic here — it is every other quartile of a
        four-value distribution. The example's `us-east` has a median of
        126.5 and a q3 of 128.5, which the kit renders as 127 and 129
        and `f"{126.5:.0f}"` renders as 126.
        """
        q = Decimal(repr(n)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        return f"{q:f}"

    def fmt(n: float) -> str:
        a = abs(n)
        if a >= 1000:
            return fixed(n / 1000, 1).removesuffix(".0") + "k"
        if a >= 10:
            return fixed(n, 0)
        if a >= 1:
            return fixed(n, 1).removesuffix(".0")
        return fixed(n, 2)

    return {
        "n": str(len(vs)),
        "min": fmt(vs[0]),
        "q1": fmt(q(0.25)),
        "median": fmt(q(0.5)),
        "q3": fmt(q(0.75)),
        "max": fmt(vs[-1]),
    }


@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
def test_a_violin_names_the_summary_its_shape_draws(browser, tmp_path_factory, orientation):
    """A violin draws a median line and an IQR box and names neither.
    Both orientations carry the five-number summary now, and both are
    asserted because they are two renderers that share nothing — the
    value runs along x in one and up y in the other, and the shipped
    example only reaches the first.

    The reading is checked against the payload's own values rather than
    against "some text appeared": a tooltip that says the wrong median
    is worse than one that says nothing, because the reader believes it.
    """
    payload = dict(EXAMPLES["violin"])
    if orientation == "vertical":
        payload["orientation"] = "vertical"
    docs = tmp_path_factory.mktemp(f"violin{orientation}") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "---\ntitle: Violin\nsummary: One violin.\n---\n\n## v {#v}\n\n"
        "```oku-chart\n" + json.dumps(payload, separators=(",", ":")) + "\n```\n",
        encoding="utf-8",
    )
    (docs / "page.html").write_text(cli._stub_for("Violin"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)

    pg = browser.new_page(viewport={"width": 1280, "height": 1000})
    try:
        pg.goto((docs / "dist" / "standalone" / "page.html").as_uri(), wait_until="load")
        page_quiet(pg)
        got = pg.evaluate(
            """() => [...document.querySelectorAll('.okc-violin-body')].map((b) => ({
                 payload: JSON.parse(b.getAttribute('data-hover-payload') || 'null'),
                 title: (b.querySelector('title') || {}).textContent || '',
                 focusable: b.getAttribute('tabindex'),
               }))"""
        )
        dists = EXAMPLES["violin"]["distributions"]
        assert len(got) == len(dists), got
        for body, dist in zip(got, dists, strict=True):
            assert body["focusable"] == "0", body
            assert body["payload"]["label"] == dist["label"], body
            kv = {row["k"]: row["v"] for row in body["payload"]["kv"]}
            assert kv == _five_number(dist["values"]), (dist["label"], kv)
            # The native title is the same reading for anyone who never
            # gets a `mouseenter` — a touch reader, or a page whose
            # script did not run.
            assert dist["label"] in body["title"], body
            assert kv["median"] in body["title"], body

        # And it is reachable by keyboard, which is the half that is
        # invisible to anyone using a pointer.
        pg.evaluate("() => document.querySelector('.okc-violin-body').focus()")
        until(
            pg,
            "() => [...document.querySelectorAll('#v .okc-tooltip')]"
            ".some((t) => t.classList.contains('visible'))",
            what="focusing a violin showed its summary",
        )
    finally:
        pg.close()


def test_a_density_plot_reads_out_the_curve_under_the_cursor(page):
    """Density draws one curve and no marks, so the cursor is the only
    reading it can have. Both numbers describe the drawn picture rather
    than the KDE's units — the height as a share of the peak, which is
    literally what `yOf` plots, and the share of observations at or
    below, which is what a distribution is usually consulted for.

    Asserted at two positions, because a lookup that ignores its
    argument returns the same thing everywhere and would pass a
    single-point check.
    """
    _settle(page, "density")
    box = page.evaluate(
        """() => { const r = document.querySelector('#density svg.okc-svg').getBoundingClientRect();
                   const l = document.querySelector('#density .okc-generic-cursor');
                   const vb = document.querySelector('#density svg.okc-svg').viewBox.baseVal;
                   const y = r.top + ((+l.getAttribute('y1') + +l.getAttribute('y2')) / 2 / vb.height) * r.height;
                   return { y, left: r.left + r.width * 0.3, right: r.left + r.width * 0.7 }; }"""
    )
    readings = []
    for x in (box["left"], box["right"]):
        page.mouse.move(x, box["y"], steps=4)
        until(page, _visible("density"), what=f"the density cursor read out at x={x:.0f}")
        readings.append(page.evaluate(SHOWN, "density"))

    for text in readings:
        assert "% of peak" in text, text
        assert "at or below" in text, text
    assert readings[0] != readings[1], readings
    # The share at or below only ever grows to the right; a lookup that
    # inverted the axis would still differ at two points and be wrong.
    shares = [int(t.split("at or below")[1].split("%")[0].strip()) for t in readings]
    assert shares[0] < shares[1], (shares, readings)


PIN_STATE = """(id) => {
  const t = [...document.getElementById(id).querySelectorAll('.okc-tooltip')]
    .find((e) => e.classList.contains('visible'));
  return t ? { hint: /click to pin/.test(t.textContent), pinned: t.classList.contains('pinned') }
           : { hint: null, pinned: false };
}"""


def _pin_state(page, chart: str) -> dict:
    return page.evaluate(
        """(id) => {
             const t = [...document.getElementById(id).querySelectorAll('.okc-tooltip')]
               .find((e) => e.classList.contains('visible'));
             return t ? { hint: /click to pin/.test(t.textContent),
                          pinned: t.classList.contains('pinned'),
                          text: (t.textContent || '').trim() }
                      : { hint: false, pinned: false, text: null };
           }""",
        chart,
    )


def _pin_holds(page, chart: str, x: float, y: float) -> None:
    """Click, and require the reading to outlive the pointer.

    "Gained a class" is not the promise. The pin exists so a reader can
    select the text or hold a value while looking somewhere else, so
    what is asserted is that the reading survives the pointer leaving —
    which is the half that was broken twice here, in two different
    places, after the click itself already worked.
    """
    page.mouse.click(x, y)
    until(
        page,
        f"() => [...document.getElementById('{chart}').querySelectorAll('.okc-tooltip')]"
        ".some((t) => t.classList.contains('visible') && t.classList.contains('pinned'))",
        what=f"{chart} pinned the reading its tooltip offered to pin",
    )
    page.mouse.move(4, 4)
    assert _pin_state(page, chart)["pinned"], f"{chart} lost the pin when the pointer left"
    page.mouse.click(x, y)
    until(page, _visible(chart, negate=True), what=f"{chart} let the pin go on a second click")
    page.mouse.move(4, 4)


# One case per writer of that string, not one per chart type. `rich()`
# prints it for every anchor, `_showCursorTip` for every SVG cursor, and
# the div bar chart's `showCrossing` for the three DIV-rendered types --
# three implementations, and the sweep that found the defect showed the
# failures cluster by writer rather than by chart. A 53-case version of
# this existed first and was flaky: it picks whichever mark it can reach
# on a 53-chart page, and on `arc` that answer moved between runs while
# arc pinned correctly 3 times out of 3 on a page of its own. A flaky
# test is worse than no test, and the rule being asserted is about the
# writers anyway.
def test_a_mark_reading_pins(page):
    """`rich()` -- the path that already worked, pinned here so it keeps
    working now that three writers share the element and a pin."""
    pt = _hover_a_mark(page, "donut")
    until(page, _visible("donut"), what="the slice showed its reading")
    assert _pin_state(page, "donut")["hint"], "the slice's reading makes no pin offer"
    _pin_holds(page, "donut", pt["x"], pt["y"])


def test_the_cursor_reading_pins(page):
    """`_showCursorTip` -- the writer that printed the offer into five
    call sites with no click bound anywhere. Density is the honest
    subject: it draws one curve and no marks, so the cursor's reading is
    the only one it has and there is no anchor to fall back on."""
    _settle(page, "density")
    pt = page.evaluate(CURSOR_ONLY_POINT, ["density", MARKS])
    assert pt, "no point inside density's cursor band"
    page.mouse.move(pt["x"] - 14, pt["y"] - 14)
    page.mouse.move(pt["x"], pt["y"], steps=6)
    until(page, _visible("density"), what="the density cursor showed a reading")
    assert _pin_state(page, "density")["hint"], "the cursor's reading makes no pin offer"
    _pin_holds(page, "density", pt["x"], pt["y"])


def test_a_bar_chart_reading_pins(page):
    """`showCrossing` -- the third writer. Bar, stacked-bar and
    grouped-bar are DIV-rendered outside the `oku-chart` element
    lifecycle and carry their own tooltip, their own cursor and their
    own pin, so nothing the other two writers do covers them."""
    pt = _hover_a_mark(page, "bar")
    until(page, _visible("bar"), what="the bar showed a reading")
    assert _pin_state(page, "bar")["hint"], "the bar's reading makes no pin offer"
    _pin_holds(page, "bar", pt["x"], pt["y"])


def test_a_cursor_reading_survives_the_dot_under_the_pointer(page):
    """The case that took two fixes, and neither is visible from the
    outside.

    On a Cartesian chart the reading under the pointer is the CURSOR's
    cross-series readout, and the pointer is sitting on a dot while it
    reads. Clicking focused that dot, whose `focus` handler replaced the
    readout with the single point's coordinates -- measured on scatter,
    'Engineering cost \u2248 4 / Showstoppers + High 9' became
    'Showstoppers + High / H3 / (4, 9)' between the mouse going down and
    coming up -- so the click found a tooltip nobody had offered to pin.
    With that fixed the click pinned and then leaving the dot took the
    pin down, because the dot's `hideTip` hid whatever was there.
    """
    pt = _hover_a_mark(page, "scatter")
    until(page, _visible("scatter"), what="scatter showed a reading")
    before = _pin_state(page, "scatter")
    assert before["hint"], "the reading under the pointer makes no pin offer"
    page.mouse.click(pt["x"], pt["y"])
    until(
        page,
        "() => [...document.getElementById('scatter').querySelectorAll('.okc-tooltip')]"
        ".some((t) => t.classList.contains('visible') && t.classList.contains('pinned'))",
        what="the click pinned the reading it was offered",
    )
    # The content is the one that was on screen when the offer was made.
    assert _pin_state(page, "scatter")["text"] == before["text"]
    page.mouse.move(4, 4)
    assert _pin_state(page, "scatter")["pinned"], "leaving the dot took the pinned reading with it"
    page.mouse.click(pt["x"], pt["y"])
    until(page, _visible("scatter", negate=True), what="the second click let go")
    page.mouse.move(4, 4)


def test_a_draggable_mark_makes_no_offer_it_cannot_keep(page):
    """A network node is dragged, and the drag calls
    `svg.setPointerCapture` on pointerdown -- so every event after that
    goes to the SVG and the node never sees a mousedown, a mouseup or a
    click. Measured: `elementFromPoint` names the node's own `<circle>`
    and the click arrives at `svg.okc-svg`, with capture-phase listeners
    on the node group recording nothing at all.

    So the pin could never fire there, and the answer is not to bolt one
    on -- the gesture is spoken for -- but to stop printing an offer the
    interaction cannot keep. Asserted rather than skipped, because "this
    tooltip makes no offer" is the fix.
    """
    _hover_a_mark(page, "network")
    until(page, _visible("network"), what="the node showed its reading")
    got = _pin_state(page, "network")
    assert got["text"], got
    assert not got["hint"], f"a node that cannot be clicked still offers a pin: {got['text']!r}"
    page.mouse.move(4, 4)


def test_a_dot_still_shows_its_reading_to_the_keyboard(page):
    """The guard on narrowing the dot's focus handler to
    `:focus-visible`.

    A mouse click focuses a dot, which is why the handler had to stop
    answering plain `focus` — but Tab focuses it too, and that is a
    reader with no other way in. Reached by pressing Tab rather than by
    calling `.focus()`, because the two are not the same question:
    Chromium matches `:focus-visible` on keyboard navigation and a
    programmatic focus after mouse activity does not match, so a test
    that called `.focus()` would fail against a kit that works.
    """
    _settle(page, "scatter")
    # Start from a known place inside the section, then walk in.
    page.evaluate(
        "() => document.getElementById('scatter').querySelector('h2').setAttribute('tabindex', '-1')"
    )
    page.evaluate("() => document.getElementById('scatter').querySelector('h2').focus()")
    landed = None
    for _ in range(60):
        page.keyboard.press("Tab")
        where = page.evaluate(
            """() => { const a = document.activeElement;
                       return a && a.classList && a.classList.contains('okc-dot')
                              ? (a.getAttribute('data-point-key') || 'dot') : null; }"""
        )
        if where:
            landed = where
            break
    assert landed, "Tab never reached a data point on the scatter"
    until(
        page,
        "() => [...document.getElementById('scatter').querySelectorAll('.okc-tooltip')]"
        ".some((t) => t.classList.contains('visible') && (t.textContent || '').trim())",
        what="a dot reached by Tab showed its reading",
    )
    page.keyboard.press("Escape")
    page.mouse.move(4, 4)


def _pin_the_cursor(page, chart: str) -> dict:
    _settle(page, chart)
    pt = page.evaluate(CURSOR_ONLY_POINT, [chart, MARKS])
    assert pt, f"no point inside {chart}'s cursor band"
    page.mouse.move(pt["x"] - 14, pt["y"] - 14)
    page.mouse.move(pt["x"], pt["y"], steps=6)
    until(page, _visible(chart), what=f"{chart} showed a cursor reading")
    page.mouse.click(pt["x"], pt["y"])
    until(
        page,
        f"() => [...document.getElementById('{chart}').querySelectorAll('.okc-tooltip')]"
        ".some((t) => t.classList.contains('visible') && t.classList.contains('pinned'))",
        what=f"{chart} pinned the cursor's reading",
    )
    return pt


def _still_reads(page, chart: str, pt: dict) -> bool:
    """The chart answers the pointer again — which is the thing a stuck
    pin flag silently takes away, since every cursor returns early on
    `_tipPinned` and nothing on screen says why."""
    page.mouse.move(4, 4)
    page.mouse.move(pt["x"] - 40, pt["y"], steps=4)
    page.mouse.move(pt["x"] - 20, pt["y"], steps=4)
    try:
        until(page, _visible(chart), timeout=4000, what=f"{chart} read out again")
        return True
    except AssertionError:
        return False


@pytest.mark.parametrize("release", ["close-button", "escape"])
def test_a_pinned_cursor_reading_can_be_let_go(page, release):
    """Both advertised ways out, and both were broken by the pin itself.

    The close button called `unpinRich`, which clears the ANCHOR pin and
    not the cursor's — so it hid the tooltip and left `_tipPinned` true
    forever. Measured on density: click the ×, and the chart never
    answers the pointer again, with nothing on screen saying why. That is
    worse than a control that does nothing.

    Escape did nothing at all. The host's keydown only fires with focus
    inside the host; the anchor path gets that free because a click
    focuses the mark, and an `<svg>` is not focusable, so a cursor pin
    focused nothing. The button's own title says `Close (Esc)`.
    """
    pt = _pin_the_cursor(page, "density")
    if release == "close-button":
        page.click("#density .okc-tt-close")
    else:
        page.keyboard.press("Escape")
    until(page, _visible("density", negate=True), what=f"{release} let the pinned reading go")
    assert _still_reads(page, "density", pt), f"{release} left the chart unable to read out"


def test_the_close_button_still_releases_an_anchor_pin(page):
    """The path `unpinAny` had to keep working. It is the older of the
    two and the one with a `.okc-pinned` marker on the mark itself, so
    the assertion covers the marker as well as the tooltip."""
    pt = _hover_a_mark(page, "donut")
    until(page, _visible("donut"), what="the slice showed its reading")
    page.mouse.click(pt["x"], pt["y"])
    until(
        page,
        "() => [...document.getElementById('donut').querySelectorAll('.okc-tooltip')]"
        ".some((t) => t.classList.contains('visible') && t.classList.contains('pinned'))",
        what="the slice pinned",
    )
    assert page.evaluate("() => document.querySelectorAll('#donut .okc-pinned').length") == 1
    page.click("#donut .okc-tt-close")
    until(page, _visible("donut", negate=True), what="the close button let the slice go")
    assert page.evaluate("() => document.querySelectorAll('#donut .okc-pinned').length") == 0
    page.mouse.move(4, 4)
