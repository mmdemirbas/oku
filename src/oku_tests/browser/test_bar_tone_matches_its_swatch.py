"""A bar is drawn in the tone its author named, the tone its legend shows.

The schema offers five tones for a series or a row — `accent`, `warn`,
`danger`, `success`, `muted` — and the bar family draws them with CSS
classes. Three fills had a rule; `muted` had a legend swatch rule and no
fill rule, so a muted series kept the base fill, the accent. Reported
from a real page: a stacked bar with an accent "Karma" series and a
muted "Başka" series drew both indigo while the legend showed indigo and
grey, so the reader could not tell the two apart and the legend pointed
at the wrong one.

Held for every bar shape (single, stacked, grouped; horizontal and
vertical) in both themes: each fill and each legend swatch computes to
the colour of the token its tone names. Comparing against the token, not
fill against swatch, is what catches a pair that agree with each other
and are both wrong.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

from ._menu import set_theme
from ._wait import page_quiet

pytestmark = pytest.mark.browser

TONES = ["accent", "warn", "danger", "success", "muted"]


def _series_chart(kind, orientation):
    return {
        "type": kind,
        "title": f"{kind} {orientation}",
        "orientation": orientation,
        "categories": ["a", "b"],
        "series": [{"label": t, "color": t, "values": [10 + i, 20 + i]} for i, t in enumerate(TONES)],
    }


CHARTS = [
    {
        "type": "bar",
        "title": "rows",
        "rows": [{"label": t, "value": 10 + i, "color": t} for i, t in enumerate(TONES)],
    },
    *(_series_chart(k, o) for k in ("stacked-bar", "grouped-bar") for o in ("horizontal", "vertical")),
]

PAGE_MD = (
    "---\ntitle: Tones\nsummary: Every bar shape in every tone.\n---\n\n## Bars {#bars}\n\n"
    + "\n\n".join(f"```oku-chart\n{json.dumps(c)}\n```" for c in CHARTS)
    + "\n"
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tones") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Page"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


PROBE = """(tones) => {
  const token = {accent: '--accent', warn: '--warning', danger: '--danger', success: '--success', muted: '--text-soft'};
  const out = { wrong: [], count: {} };
  for (const root of document.querySelectorAll('main .bar-chart')) {
    const want = {};
    for (const t of tones) {
      const p = document.createElement('span');
      p.style.background = `var(${token[t]})`;
      root.appendChild(p); want[t] = getComputedStyle(p).backgroundColor; p.remove();
    }
    const shape = root.className;
    const check = (el, t, what) => {
      const got = getComputedStyle(el).backgroundColor;
      out.count[what + ':' + t] = (out.count[what + ':' + t] || 0) + 1;
      if (got !== want[t]) out.wrong.push(`${shape} ${what} ${t}: ${got}, want ${want[t]}`);
    };
    for (const t of tones) {
      root.querySelectorAll('.bar-fill.' + t).forEach((f) => check(f, t, 'fill'));
      root.querySelectorAll('.bar-chart-legend-chip.' + t + ' .bar-chart-legend-swatch').forEach((s) => check(s, t, 'swatch'));
    }
  }
  return out;
}"""


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_bar_is_drawn_in_its_tone(built, browser, theme):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        page.goto(built.as_uri(), wait_until="load")
        page_quiet(page)
        set_theme(page, theme)
        assert page.evaluate("() => document.documentElement.getAttribute('data-theme')") == theme
        got = page.evaluate(PROBE, TONES)
        assert got["wrong"] == [], "\n".join(got["wrong"])
        # Vacuity: every tone was drawn as a fill on all five charts, and
        # as a swatch on the four that have a legend.
        for t in TONES:
            assert got["count"].get("fill:" + t, 0) >= 5, got["count"]
            assert got["count"].get("swatch:" + t, 0) == 4, got["count"]
    finally:
        context.close()
