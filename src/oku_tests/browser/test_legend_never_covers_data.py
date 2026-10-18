"""A chart's legend is never drawn over its data.

The Cartesian charts (scatter, line, area, bubble, quadrant) drew their
series legend INSIDE the plot, at its top-right corner, on an opaque
backing whose comment said it existed to "occlude any data dot rendered
behind it". The kit's own scatter example has a point there: `S2-inline`
at (6, 8) sat under the backing, invisible and unreachable by the
pointer at every width. A corner chosen to avoid the data would not
hold either, because a pan or a zoom moves the data under it. So the
legend is a row above the plot, as the quadrant labels already are.

The row is the shared series legend, and three charts that already used
it reserved its room by a copy of its wrap rule: sunburst with an older
character width, marimekko and stream with one row whatever the labels.
A second row was painted over the plot. The room is now asked of the
same layout that paints it.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import measured, page_quiet

pytestmark = pytest.mark.browser

EXAMPLES = json.loads(
    (Path(__file__).resolve().parents[3] / "kit" / "schema" / "examples.json").read_text(encoding="utf-8")
)
CHARTS = EXAMPLES["charts"]

# Every chart type whose example draws Cartesian dots under a labelled
# series legend — derived, so a type added tomorrow is covered.
CARTESIAN = sorted(
    t
    for t, ex in CHARTS.items()
    if t in ("scatter", "line", "area", "bubble", "quadrant")
    and any(s.get("label") for s in ex.get("series", []))
)

LONG = "a series label long enough to need a row of its own"


def _many(ex: dict, key: str) -> dict:
    """The example with eight series, each labelled at length, so the
    legend row has to wrap."""
    out = copy.deepcopy(ex)
    base = out[key]
    out[key] = [dict(copy.deepcopy(base[i % len(base)]), label=f"{LONG} {i}") for i in range(8)]
    return out


def _many_sunburst(ex: dict) -> dict:
    out = copy.deepcopy(ex)
    kids = out["tree"]["children"]
    out["tree"]["children"] = [
        dict(copy.deepcopy(kids[i % len(kids)]), label=f"{LONG} {i}") for i in range(8)
    ]
    return out


def _radar(n: int) -> dict:
    """The radar example with `n` axes. The lowest spoke label falls with
    the axis count, and an even count points one straight down."""
    out = copy.deepcopy(CHARTS["radar"])
    out["axes"] = [{"label": f"criterion {i}"} for i in range(n)]
    for s in out["series"]:
        s["values"] = [(s["values"][i % len(s["values"])]) for i in range(n)]
    return out


# Every shipped example, and the radar at every axis count from 3 to 8:
# the sweep below asks each of them whether a legend lands on anything.
EVERY = {f"x-{t}": ex for t, ex in sorted(CHARTS.items())}
EVERY.update({f"x-radar-{n}": _radar(n) for n in range(3, 9)})

ROWED = {
    "marimekko": _many(CHARTS["marimekko"], "series"),
    "stream": _many(CHARTS["stream"], "series"),
    "sunburst": _many_sunburst(CHARTS["sunburst"]),
}


def _fence(payload: dict) -> str:
    return "```oku-chart\n" + json.dumps(payload) + "\n```"


PAGE_MD = (
    "---\ntitle: Legends\nsummary: A legend is never drawn over its data.\n---\n\n"
    + "\n\n".join(f"## {t} {{#c-{t}}}\n\n{_fence(CHARTS[t])}" for t in CARTESIAN)
    + "\n\n"
    + "\n\n".join(f"## {t} wrapped {{#w-{t}}}\n\n{_fence(p)}" for t, p in ROWED.items())
    + "\n\n"
    + "\n\n".join(f"## {k} {{#{k}}}\n\n{_fence(p)}" for k, p in EVERY.items())
    + "\n"
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("legends") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module", params=[1280, 360])
def page(request, built, browser):
    context = browser.new_context(viewport={"width": request.param, "height": 900})
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")
    yield page
    context.close()


def _chart(anchor: str) -> str:
    return f"document.getElementById({anchor!r}).closest('section').querySelector('oku-chart')"


def test_the_cartesian_examples_are_covered():
    assert "scatter" in CARTESIAN, CARTESIAN


@pytest.mark.parametrize("kind", CARTESIAN)
def test_every_dot_is_the_thing_under_its_own_centre(page, kind):
    """Not a legend chip, not a backing: a reader pointing at a point
    reaches the point. A dot may sit on another dot — two points at one
    coordinate — and that is still a dot."""
    covered = measured(
        page,
        f"""() => {{ const c = {_chart("c-" + kind)}; c.scrollIntoView({{ block: 'center' }});
          return [...c.querySelectorAll('.okc-dot')].map(d => {{ const r = d.getBoundingClientRect();
            const h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            return (h && h.classList.contains('okc-dot')) ? null : (d.getAttribute('data-point-label') || d.getAttribute('data-x')) + ' under ' + (h ? h.getAttribute('class') : 'nothing');
          }}).filter(Boolean); }}""",
    )
    assert covered == [], f"{kind}: points covered by something else: {covered}"


@pytest.mark.parametrize("kind", CARTESIAN)
def test_the_legend_sits_outside_the_plot(page, kind):
    """Inside the plot a legend covers whatever a pan or a zoom brings
    under it, wherever it starts."""
    got = measured(
        page,
        f"""() => {{ const c = {_chart("c-" + kind)};
          // The axes, not the clip rect: an element inside <clipPath> is
          // never rendered, so its box is all zeros and nothing is inside it.
          const ax = [...c.querySelectorAll('svg > line.okc-axis')].map(e => e.getBoundingClientRect());
          const clip = {{ left: Math.min(...ax.map(r => r.left)), right: Math.max(...ax.map(r => r.right)),
                         top: Math.min(...ax.map(r => r.top)), bottom: Math.max(...ax.map(r => r.bottom)) }};
          return [...c.querySelectorAll('.okc-legend-chip')].map(e => {{ const r = e.getBoundingClientRect();
            return {{ label: e.textContent.trim(), inside: r.bottom > clip.top + 0.5 && r.top < clip.bottom && r.right > clip.left && r.left < clip.right }}; }}); }}""",
    )
    assert got, f"{kind}: the example's series legend is not drawn"
    inside = [g["label"] for g in got if g["inside"]]
    assert inside == [], f"{kind}: legend chips inside the plot: {inside}"


@pytest.mark.parametrize("kind", sorted(ROWED))
def test_a_wrapped_legend_row_has_its_room(page, kind):
    """Eight long labels wrap the row; every row must end above the
    first mark the chart draws."""
    got = measured(
        page,
        f"""() => {{ const c = {_chart("w-" + kind)};
          const leg = c.querySelector('.okc-series-legend');
          const chips = [...leg.querySelectorAll('.okc-legend-chip')].map(e => e.getBoundingClientRect());
          const marks = [...c.querySelectorAll('svg [data-hover-payload]')].map(e => e.getBoundingClientRect()).filter(r => r.height > 0);
          return {{ rows: new Set(chips.map(r => Math.round(r.top))).size,
                   legendBottom: Math.max(...chips.map(r => r.bottom)),
                   marksTop: Math.min(...marks.map(r => r.top)), marks: marks.length }}; }}""",
    )
    assert got["marks"] > 0, f"{kind}: no marks found to measure against"
    assert got["rows"] > 1, f"{kind}: the legend did not wrap, so this case asserts nothing"
    assert got["legendBottom"] <= got["marksTop"] + 0.5, (
        f"{kind}: {got['rows']} legend rows end at {got['legendBottom']:.1f}, the chart starts at {got['marksTop']:.1f}"
    )


# Every legend the kit draws, by the class its renderer gives it.
LEGENDS = (
    ".okc-legend-chip, .okc-radar-legend, .okc-donut-legend, .okc-waffle-legend, "
    ".okc-gauge-zone-chip, .bar-chart-legend"
)


@pytest.mark.parametrize("key", sorted(EVERY))
def test_no_legend_lands_on_a_label_or_a_mark(page, key):
    """Swept over every shipped example: a legend chip may not overlap
    any text the chart draws or any mark the reader can point at. The
    radar's row sat at a fixed height and seven axes put two spoke
    labels under it."""
    hits = measured(
        page,
        f"""() => {{ const sec = document.getElementById({key!r}).closest('section');
          const c = sec.querySelector('oku-chart, .bar-chart'); if (!c) return null;
          const LEG = {LEGENDS!r};
          const legs = [...c.querySelectorAll(LEG)].filter(e => !e.parentElement.closest(LEG));
          const others = [...c.querySelectorAll('text, [data-hover-payload], .okc-dot, .okc-point-label, .bar-label, .bar-value')]
            .filter(e => !e.closest(LEG) && !e.closest('.okt-bar'));
          const out = [];
          for (const l of legs) {{ const a = l.getBoundingClientRect(); if (!a.width) continue;
            for (const o of others) {{ const b = o.getBoundingClientRect(); if (!b.width || !b.height) continue;
              const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
              const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
              if (ix > 1 && iy > 1) out.push((o.getAttribute('class') || o.tagName) + ' "' + (o.textContent || '').trim().slice(0, 24) + '"');
            }} }}
          return [...new Set(out)]; }}""",
    )
    assert hits is not None, f"{key}: no chart drawn"
    assert hits == [], f"{key}: a legend lands on {hits}"
