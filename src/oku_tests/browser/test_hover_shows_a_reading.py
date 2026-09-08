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

from ._wait import page_quiet, scroll_stable, until

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


def _hover_a_mark(page, chart: str):
    page.evaluate("(id) => document.getElementById(id).scrollIntoView({block: 'center'})", chart)
    # The kit scrolls smoothly, and a rect read mid-flight names a point
    # the pointer will never be at.
    scroll_stable(page)
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
    page.evaluate("(id) => document.getElementById(id).scrollIntoView({block: 'center'})", "bump")
    scroll_stable(page)
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
    page.evaluate("(id) => document.getElementById(id).scrollIntoView({block: 'center'})", "density")
    scroll_stable(page)
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
