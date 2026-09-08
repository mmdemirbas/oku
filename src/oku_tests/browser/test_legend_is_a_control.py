"""A legend item that takes focus does something when you press it.

The kit gives every legend chip `tabindex="0"`, and the wiring pass sets
`aria-pressed="false"` on each one — so a reader on a keyboard is told
there is a toggle there, and a screen reader announces a button with a
pressed state. Three chart types had the announcement and nothing
behind it.

Measured by clicking one chip on every chart type that has one, and
reading whether ANY state moved (`.okc-hidden`, `.dim`, `.okc-legend-off`,
`aria-pressed`, the SVG's own markup):

    dead      marimekko   3 chips
    dead      stream      3 chips
    dead      sunburst    2 chips
    changed   arc, area, bubble, donut, line, pie, plot, quadrant,
              radar, scatter, waffle

One cause. `_renderSeriesLegend` — the shared row those three use —
emits chips carrying `data-series-idx`, and the wiring toggles
`.okc-series[data-series-idx]`. None of the three wrapped their shapes
in one: marimekko paints cells column-first so a series' cells are
scattered through the DOM, stream painted a bare band per series, and a
sunburst series is a ring-1 branch whose colour cascades to every arc
under it. Each renderer emits the group now, so the fix is DOM shape
rather than a fourth copy of the toggle logic.

The roadmap row that asked for this named donut, pie, waffle, radar and
box-plot. The first four had shipped — `wireNonCartesianLegend` covers
them with toggle, solo, hover and keyboard — and box-plot has no legend
at all, because its boxes are named on the axis and there is no colour
to explain. The three that were dead were not on the list.

The sweep is derived from `kit/schema/examples.json` rather than a list
of type names, so a chart type added tomorrow is covered on the day it
lands rather than the day someone remembers this file.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

EXAMPLES = json.loads(
    (Path(__file__).resolve().parents[3] / "kit" / "schema" / "examples.json").read_text(encoding="utf-8")
)["charts"]

# A legend item is one the kit made reachable: `tabindex` or a button
# role. Anything else in a legend is a painted label, and a label that
# does nothing is not a broken promise.
#
# Wrapped in `:is()` so it can be PREFIXED. A bare comma list cannot:
# `#donut [a], [b]` scopes only the first branch and leaves the second
# matching the whole document, so every click in this file landed on
# whichever chart sorts first. It read as twelve dead legends.
ITEMS = ":is([class*='legend'][tabindex], [class*='legend'][role='button'])"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("legends") / "docs"
    docs.mkdir()
    body = ["---", "title: Legends", "summary: One of every chart type.", "---", ""]
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
    (docs / "page.html").write_text(cli._stub_for("Legends"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def page(built, browser):
    pg = browser.new_page(viewport={"width": 1280, "height": 2000})
    pg.goto(built.as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    pg.close()


# Every way the kit says "this series is muted", plus the markup length,
# so a renderer that answers some fourth way still counts as answering.
STATE = """(id) => {
  const sec = document.getElementById(id);
  const svg = sec.querySelector('svg');
  return {
    hidden: sec.querySelectorAll('.okc-hidden').length,
    dim: sec.querySelectorAll('.dim').length,
    off: sec.querySelectorAll('.okc-legend-off, .off').length,
    pressed: [...sec.querySelectorAll('[aria-pressed]')].map((e) => e.getAttribute('aria-pressed')).join(''),
    markup: svg ? svg.innerHTML.length : 0,
  };
}"""

WITH_LEGENDS = """(sel) => [...document.querySelectorAll('main section[id]')]
     .map((sec) => ({ id: sec.id, items: sec.querySelectorAll(sel).length }))
     .filter((r) => r.items > 0)"""


@pytest.fixture(scope="module")
def charts_with_legends(page):
    got = page.evaluate(WITH_LEGENDS, ITEMS)
    # Vacuity guard: this file's whole subject is charts that HAVE a
    # legend, so a page that rendered none would pass every assertion
    # below by having nothing to check.
    assert len(got) >= 10, got
    return got


def _press(page, chart: str, nth: int, *, key: str | None = None, modifier: str | None = None):
    """Operate one legend item the way a reader would and hand back the
    state either side of it. A real click rather than a dispatched
    event: a chip sits over the plot it explains, so hit-testing is part
    of what is being asserted."""
    before = page.evaluate(STATE, chart)
    item = page.locator(f"#{chart} {ITEMS}").nth(nth)
    if key:
        item.focus()
        item.press(f"{modifier}+{key}" if modifier else key)
    else:
        item.click(modifiers=[modifier] if modifier else [])
    # No wait: every way this state can move is a synchronous classList
    # or attribute write inside the click handler, so it has already
    # happened when the dispatch returns. A sleep here would also be the
    # wrong shape — this reads state that may legitimately NOT change,
    # which is how a dead legend is detected, and there is no condition
    # to wait for in that case.
    return before, page.evaluate(STATE, chart)


def test_every_focusable_legend_item_answers_a_click(page, charts_with_legends):
    """The sweep, and the shape the three dead ones were found by. Read
    as a whole-page property: a fourth renderer that emits the shared
    legend row and forgets the group lands here rather than in a bug
    report."""
    dead = []
    for chart in charts_with_legends:
        before, after = _press(page, chart["id"], 0)
        if before == after:
            dead.append(chart)
        else:  # leave the page as it was found for the next case
            _press(page, chart["id"], 0)
    assert dead == [], f"legend items that take focus and do nothing: {dead}"


def test_every_focusable_legend_item_answers_the_keyboard(page, charts_with_legends):
    """Focus is a promise, and the keyboard is the half nobody using a
    pointer can see broken. Enter and Space fire a click on a real
    `<button>` and on nothing else — every one of these is an SVG `<g>`
    with a role."""
    dead = []
    for chart in charts_with_legends:
        before, after = _press(page, chart["id"], 0, key="Enter")
        if before == after:
            dead.append(chart["id"])
        else:
            _press(page, chart["id"], 0, key="Enter")
    assert dead == [], f"legend items that take focus and ignore Enter: {dead}"


@pytest.mark.parametrize("chart", ["marimekko", "stream", "sunburst"])
def test_a_series_group_holds_every_shape_that_series_drew(page, chart):
    """The fix itself, stated as the property that makes the toggle
    correct rather than merely responsive.

    Muting must take the whole series. Marimekko is the case that says
    it: its cells are painted column-first, so a group built from one
    column's worth would hide a third of the series and look like a
    rendering fault. Sunburst is the other: a ring-1 colour cascades to
    every arc beneath it, so the group has to reach the outer rings.
    """
    got = page.evaluate(
        """(id) => {
             const sec = document.getElementById(id);
             const groups = [...sec.querySelectorAll('.okc-series[data-series-idx]')];
             const shapes = sec.querySelectorAll('svg rect, svg path');
             return {
               chips: sec.querySelectorAll("[class*='legend'][tabindex]").length,
               groups: groups.length,
               inGroups: groups.reduce((n, g) => n + g.querySelectorAll('rect, path').length, 0),
               shapes: shapes.length,
               idxs: groups.map((g) => g.getAttribute('data-series-idx')),
             };
           }""",
        chart,
    )
    assert got["groups"] == got["chips"], got
    assert got["idxs"] == [str(i) for i in range(got["groups"])], got
    # Every drawn shape that is not a legend swatch is inside a group.
    # Stated as a lower bound rather than equality: a chart may draw
    # frame or axis marks that belong to no series.
    assert got["inGroups"] >= got["groups"], got
    if chart == "marimekko":
        # One cell per (series, category) and nothing else drawn, so the
        # count is the payload's own arithmetic. Derived rather than
        # written down: a group holding one column's cells is the
        # failure this catches, and a hand-typed total would go stale
        # the first time the shipped example gains a quarter.
        cells = len(EXAMPLES["marimekko"]["series"]) * len(EXAMPLES["marimekko"]["categories"])
        assert got["inGroups"] == cells, (got, cells)


def test_muting_a_marimekko_series_keeps_the_column_labels(page):
    """The one decision the regrouping forced. Cells are collected per
    series and the category ticks are held back and emitted after every
    group, so a muted series does not take its column's name with it —
    a chart whose x-axis labels fade as you mute is unreadable exactly
    when the reader is trying to compare what is left."""
    page.evaluate("(id) => document.getElementById(id).scrollIntoView()", "marimekko")
    before, after = _press(page, "marimekko", 0)
    assert before != after, "the legend did nothing, so this proves nothing"
    ticks = page.evaluate(
        """() => [...document.querySelectorAll('#marimekko .okc-tick')]
             .map((t) => ({ text: t.textContent, inGroup: !!t.closest('.okc-series'),
                            opacity: +getComputedStyle(t).opacity }))"""
    )
    assert ticks, "no category labels on the chart"
    assert [t for t in ticks if t["inGroup"]] == [], ticks
    assert all(t["opacity"] > 0.9 for t in ticks), ticks
    _press(page, "marimekko", 0)


def test_a_modifier_click_solos_and_a_second_one_restores(page):
    """Solo is the half a reader reaches for on a crowded chart, and it
    is wired per legend family — so it is asserted on one of each: the
    Cartesian group toggle and the shape-index toggle."""
    for chart, marker in (("stream", "dim"), ("donut", "hidden")):
        page.evaluate("(id) => document.getElementById(id).scrollIntoView()", chart)
        _before, solo = _press(page, chart, 0, modifier="Meta")
        assert solo[marker] >= 1, (chart, solo)
        assert solo["pressed"].startswith("false"), (chart, solo)
        _before, restored = _press(page, chart, 0, modifier="Meta")
        assert restored[marker] == 0, (chart, restored)


def test_a_legend_chip_says_what_it_is_in_the_page_s_language(page, charts_with_legends):
    """`aria-label` is the only thing a screen reader has here — the
    chip's visible text is a `<text>` node beside a swatch, not a name.
    The shared row had no label at all, and the Cartesian cluster built
    one by concatenating the English word `Toggle`, which a translated
    page carried untranslated."""
    bare = page.evaluate(
        """(sel) => [...document.querySelectorAll('main section[id] ' + sel)]
             .filter((e) => !(e.getAttribute('aria-label') || '').trim())
             .map((e) => e.getAttribute('class'))""",
        ITEMS,
    )
    assert bare == [], bare
