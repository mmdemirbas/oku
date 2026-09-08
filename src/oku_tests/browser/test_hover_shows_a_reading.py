"""A mark the kit tagged with a reading shows that reading on hover.

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

Two types skip, and the skip says which and why rather than reading as
an absence nobody looked at. `density` and `violin` tag no mark with a
reading at all: each wires a line-only vertical cursor — one of the
eleven `_wireGenericVerticalCursor` call sites that pass no
`seriesLookup` — so hovering the middle of the plot draws a line and
shows no numbers. Measured: density has 0 payloads and 0 native
`<title>` elements, violin has 0 payloads and 3 titles, and neither
shows a `.okc-tooltip`. That is a gap of its own and a different one
from this file's subject; it is on the board rather than fixed here,
because a chart that never promised a reading is not a chart breaking a
promise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


def _hover_a_mark(page, chart: str):
    page.evaluate("(id) => document.getElementById(id).scrollIntoView({block: 'center'})", chart)
    # The kit scrolls smoothly, and a rect read mid-flight names a point
    # the pointer will never be at.
    scroll_stable(page)
    pt = page.evaluate(FIND_POINT, [chart, MARKS])
    if not pt["marks"]:
        # Self-reporting: the counts say whether this is a chart with
        # nothing to read on a mark, or one whose marks stopped being
        # found because a family was renamed out from under the sweep.
        pytest.skip(f"{chart} tags no mark with a reading ({pt['inventory']})")
    assert pt["x"] is not None, f"{chart}: {pt['marks']} marks and none reachable on screen"
    # Arrive from off the mark: the anchor path is wired to mouseover,
    # and a pointer teleported onto the shape can land without one.
    page.mouse.move(pt["x"] - 14, pt["y"] - 14)
    page.mouse.move(pt["x"], pt["y"], steps=6)
    return pt


@pytest.mark.parametrize("chart", sorted(EXAMPLES))
def test_hovering_a_mark_shows_its_reading(page, chart):
    """The sweep. A chart that tags a mark with a payload has promised a
    reading; this asserts that promise where the reader stands."""
    _hover_a_mark(page, chart)
    until(page, _visible(chart), what=f"{chart} showed a reading for the mark under the pointer")
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
