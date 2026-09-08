"""A chart's row labels are readable in both themes, and fit their gutter.

Reported against a delivered document: a dot-plot's row names were
invisible in dark mode. The cause is one line long and it is an absence,
not a mistake — an SVG `<text>` with no `fill` paints BLACK, and eight
renderers emitted a labelled `<text>` for which no CSS rule was ever
written. In light mode black-on-white looks deliberate, so the whole
class shipped and stayed shipped.

Two lines had the same absence in the other direction: `<line>` with no
`stroke` defaults to none and never paints at all. Both carry a width in
the markup, which is how you can tell they were meant to be seen.

The same chart showed the second defect: the label gutter was a hardcoded
`pad.left`, so a row named longer than the guess ran off the left edge of
the viewBox and was clipped mid-string — no ellipsis, no scrollbar,
nothing to hover.

These are measurements, not class-presence assertions. A class can exist
with the wrong styles and a presence check still passes.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from ._wait import stable

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# Every renderer that draws a category label into its own gutter, plus
# the two that draw a guide line. One payload each, all on one page, so
# a renderer added to the family without a fill rule fails here.
ROWS = [
    {"label": "alpha", "value": -1.81, "color": "danger"},
    {"label": "beta", "value": 2.18, "color": "warn"},
]

# The label from the reported document, verbatim. 29 characters into a
# gutter that used to be a fixed 140px.
LONG_ROWS = [
    {"label": "3627520 | 8036211 — same film", "value": -1.81, "color": "danger"},
    {"label": "3629320 | 3629444 — DIFFERENT films", "value": 3.87, "color": "warn"},
]

CHARTS = {
    "dotplot": {"type": "dot-plot", "title": "Dot", "rows": ROWS},
    "longdot": {"type": "dot-plot", "title": "Long labels", "rows": LONG_ROWS},
    "lollipop": {"type": "lollipop", "title": "Lollipop", "rows": ROWS},
    "longlolli": {"type": "lollipop", "title": "Long labels", "rows": LONG_ROWS},
    "dumbbell": {
        "type": "dumbbell",
        "title": "Dumbbell",
        "rows": [
            {"label": "alpha", "from": 1, "to": 4},
            {"label": "3627520 | 8036211 — same film", "from": 2, "to": 3},
        ],
    },
    "violin": {
        "type": "violin",
        "title": "Violin",
        "distributions": [
            {"label": "alpha", "values": [1, 2, 2, 3, 4, 4, 5]},
            {"label": "3627520 | 8036211 — same film", "values": [2, 3, 3, 4, 5, 5, 6]},
        ],
    },
    "horizon": {
        "type": "horizon",
        "title": "Horizon",
        "categories": ["a", "b", "c", "d"],
        "series": [
            {"label": "alpha", "values": [1, -2, 3, -1]},
            {"label": "3627520 | 8036211 — same film", "values": [2, 1, -3, 2]},
        ],
    },
    "polar": {
        "type": "polar-area",
        "title": "Polar",
        "sectors": [{"label": "alpha", "value": 4}, {"label": "beta", "value": 7}],
    },
    "pyramid": {
        "type": "population-pyramid",
        "title": "Pyramid",
        "categories": ["0-9", "10-19"],
        "left": {"label": "men", "values": [4, 6]},
        "right": {"label": "women", "values": [5, 5]},
    },
    "connected": {
        "type": "connected-scatter",
        "title": "Connected",
        "series": [
            {
                "label": "product",
                "data": [
                    {"x": 20, "y": 1.2, "label": "v1"},
                    {"x": 35, "y": 1.6, "label": "v2"},
                    {"x": 68, "y": 2.4, "label": "v3"},
                ],
            }
        ],
    },
    "waterfall": {
        "type": "waterfall",
        "title": "Waterfall",
        "steps": [
            {"label": "start", "value": 10, "kind": "total"},
            {"label": "up", "value": 4},
            {"label": "down", "value": -3},
        ],
    },
}

PAGE = (
    "---\ntitle: Label legibility\nsummary: Every chart label readable in both themes.\n---\n\n"
    + "\n\n".join(
        f"## {name} {{#{name}}}\n\nLead paragraph.\n\n```oku-chart\n{json.dumps(payload)}\n```"
        for name, payload in CHARTS.items()
    )
    + "\n"
)

# Classes that must carry a theme-driven fill. Each is a category label
# drawn beside the thing it names.
LABEL_CLASSES = [
    "okc-dot-plot-label",
    "okc-violin-label",
    "okc-lollipop-label",
    "okc-dumbbell-label",
    "okc-polar-area-label",
    "okc-pop-cat",
    "okc-conn-label",
    "okc-horizon-label",
]
# Guide lines that must carry a stroke.
LINE_CLASSES = ["okc-dot-plot-track", "okc-waterfall-bridge"]


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("labellegibility")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "p.md").write_text(PAGE, encoding="utf-8")
    (d / "p.html").write_text(
        cli._stub_for("Label legibility", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


# Contrast of every instance of a class against the surface behind it.
# Walks up for the first non-transparent background rather than assuming
# the chart sits directly on the page — it does not.
CONTRAST = """(cls) => {
  const srgb = c => { c/=255; return c<=0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = p => 0.2126*srgb(p[0]) + 0.7152*srgb(p[1]) + 0.0722*srgb(p[2]);
  const parse = s => (s.match(/[\\d.]+/g) || []).slice(0,3).map(Number);
  const bgOf = el => {
    let n = el;
    while (n && n !== document.documentElement) {
      const b = getComputedStyle(n).backgroundColor;
      if (!/rgba\\(0, 0, 0, 0\\)|transparent/.test(b)) return parse(b);
      n = n.parentElement;
    }
    return parse(getComputedStyle(document.body).backgroundColor);
  };
  const els = [...document.querySelectorAll('.' + cls)];
  if (!els.length) return null;
  return els.map(el => {
    const f = parse(getComputedStyle(el).fill), b = bgOf(el);
    const [hi, lo] = [lum(f), lum(b)].sort((p,q)=>q-p);
    return {contrast: (hi + 0.05) / (lo + 0.05), fill: getComputedStyle(el).fill,
            fontSize: parseFloat(getComputedStyle(el).fontSize)};
  });
}"""

STROKES = """(cls) => [...document.querySelectorAll('.' + cls)].map(el => {
  const cs = getComputedStyle(el);
  return {stroke: cs.stroke, width: parseFloat(cs.strokeWidth)};
})"""

# An SVG <text> whose box starts left of x=0 is clipped by the viewBox.
OVERFLOW = """(cls) => [...document.querySelectorAll('.' + cls)].map(el => ({
  text: el.textContent, x: el.getBBox().x, title: (el.querySelector('title')||{}).textContent || ''
}))"""


@pytest.fixture(scope="module")
def page(served, browser):
    pg = browser.new_page(viewport={"width": 1440, "height": 2400})
    pg.goto(served + "/p.html")
    pg.wait_for_function("() => window.__okuRendered === true", timeout=30000)
    yield pg
    pg.close()


def _theme(pg, name):
    pg.evaluate(f"() => document.documentElement.setAttribute('data-theme', '{name}')")
    # Every colour this file measures is mid-transition until the theme
    # lands, and a ratio computed halfway is a real number for a page
    # that does not exist.
    stable(
        pg,
        "() => getComputedStyle(document.body).backgroundColor",
        what=f"the {name} theme finished painting",
    )


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("cls", LABEL_CLASSES)
def test_a_chart_label_is_readable_against_what_is_behind_it(page, cls, theme):
    """4.5:1 is the WCAG AA floor for body text. Black on the dark
    surface measured 1.21:1 — not a near miss."""
    _theme(page, theme)
    found = page.evaluate(CONTRAST, cls)
    assert found, f"{cls} renders nowhere on the probe page — the fixture stopped covering it"
    for i, m in enumerate(found):
        assert m["contrast"] >= 4.5, (
            f"{cls}[{i}] in {theme}: fill {m['fill']} gives contrast "
            f"{m['contrast']:.2f}:1, below the 4.5:1 floor"
        )


@pytest.mark.parametrize("cls", LABEL_CLASSES)
def test_a_chart_label_uses_the_gutter_font_not_the_svg_default(page, cls):
    """An unset font inherits the SVG default of 16px. The renderers
    size their gutters for 11px, so the default is both out of scale
    with every other label in the kit and too wide for its space."""
    _theme(page, "light")
    for i, m in enumerate(page.evaluate(CONTRAST, cls)):
        assert m["fontSize"] <= 12, f"{cls}[{i}] renders at {m['fontSize']}px — the gutter is sized for 11px"


@pytest.mark.parametrize("cls", LINE_CLASSES)
def test_a_guide_line_that_carries_a_width_also_carries_a_stroke(page, cls):
    _theme(page, "dark")
    found = page.evaluate(STROKES, cls)
    assert found, f"{cls} renders nowhere on the probe page"
    for i, m in enumerate(found):
        assert m["stroke"] not in ("none", ""), f"{cls}[{i}] has no stroke — it never paints"
        assert m["width"] > 0, f"{cls}[{i}] has stroke-width {m['width']}"


@pytest.mark.parametrize(
    "cls",
    [
        "okc-dot-plot-label",
        "okc-lollipop-label",
        "okc-dumbbell-label",
        "okc-violin-label",
        "okc-horizon-label",
    ],
)
def test_a_long_label_is_fitted_to_the_gutter_not_clipped_by_the_viewbox(page, cls):
    """The gutter is measured from the labels. A label too long for the
    widest gutter is ellipsised with the full string kept in a <title>,
    which is reachable; running off the viewBox edge is not."""
    _theme(page, "light")
    rows = page.evaluate(OVERFLOW, cls)
    assert rows, f"{cls} renders nowhere on the probe page"
    for r in rows:
        assert r["x"] >= 0, f"{cls} {r['text']!r} starts at x={r['x']:.0f}, clipped by the viewBox"
    # The long one is present and its full text survived in the title.
    assert any("3627520" in r["title"] for r in rows), f"{cls}: the full label is not reachable in a <title>"
