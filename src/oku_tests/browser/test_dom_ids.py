"""An id is document-global, so no rendered page may hand out one twice.

`url(#name)` and `getElementById` resolve across the whole document and
return the FIRST match, whichever element asked. So a repeated id does
not fail — it silently answers with someone else's element, which is why
this class of defect reaches readers.

Observed on docs/diagrams.html before the fix: three diagrams each
defined `<marker id="arrowhead">` and nine arrows referenced it. The
sequence diagram's marker is 12x12 with markerUnits="userSpaceOnUse";
the journey and timeline ones are 6x4 in the default strokeWidth units.
All nine arrows drew the sequence diagram's, at the wrong size, purely
because it came first in the page. The mindmap and sankey diagrams
shared `node-1`..`node-5`, and the timeline emitted `node-undefined`
thirteen times.

The rule is asserted for the whole page rather than for diagrams,
because the next source of a colliding id will not be a diagram.
"""

from __future__ import annotations

from ._wait import page_quiet

import pytest

PAGES = [
    "index",
    "reference",
    "diagrams",
    "charts",
    "tables",
    "architecture",
    "cli",
    "glossary",
    "roadmap",
    "format-comparison",
]

# Duplicates, plus the two ways a reference can be wrong: pointing at
# nothing, or pointing INTO A DIFFERENT SVG. The second is the one that
# renders as a plausible-looking wrong picture rather than as an error.
PROBE = """() => {
  const byId = {};
  document.querySelectorAll('[id]').forEach(e => {
    (byId[e.id] = byId[e.id] || []).push(e);
  });
  const duplicates = Object.entries(byId)
    .filter(([, els]) => els.length > 1)
    .map(([id, els]) => `${id} x${els.length}`);

  const orphans = [];
  const crossed = [];
  document.querySelectorAll('svg *').forEach(el => {
    for (const attr of el.attributes) {
      let ref = null;
      const url = /url\\(#([^)]+)\\)/.exec(attr.value);
      if (url) ref = url[1];
      else if ((attr.name === 'href' || attr.name === 'xlink:href')
               && attr.value.startsWith('#')) ref = attr.value.slice(1);
      if (!ref) continue;
      const target = document.getElementById(ref);
      if (!target) orphans.push(`${attr.name}=${attr.value}`);
      else if (target.closest('svg') !== el.closest('svg')) {
        crossed.push(`${attr.name}=${attr.value}`);
      }
    }
  });
  return {
    duplicates,
    orphans: [...new Set(orphans)].slice(0, 8),
    crossed: [...new Set(crossed)].slice(0, 8),
    figures: document.querySelectorAll('oku-diagram, oku-chart').length,
  };
}"""


def _settle(page, site_url, name):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/{name}.html")
    page.wait_for_selector("main")
    # Diagrams arrive from a CDN-loaded Mermaid, so the ids that collide
    # do not exist until well after load.
    page_quiet(page)
    return page.evaluate(PROBE)


@pytest.mark.parametrize("name", PAGES)
def test_no_page_hands_out_an_id_twice(page, site_url, name):
    got = _settle(page, site_url, name)

    assert got["duplicates"] == [], f"{name}: {got['duplicates']}"


@pytest.mark.parametrize("name", ["diagrams", "charts"])
def test_every_svg_reference_resolves_inside_its_own_svg(page, site_url, name):
    """A reference that reaches into a neighbouring figure is the failure
    that looks like a rendering choice rather than a bug."""
    got = _settle(page, site_url, name)

    assert got["figures"] > 1, f"{name} has too few figures to collide: {got}"
    assert got["orphans"] == [], f"{name}: reference points at nothing: {got['orphans']}"
    assert got["crossed"] == [], f"{name}: reference reaches another figure: {got['crossed']}"


def test_ids_stay_unique_after_a_theme_flip(page, site_url):
    """Every diagram re-renders on `oku:theme-changed`, which is a second
    chance to mint the same ids — and re-rendering is what a reader does
    by clicking one button."""
    before = _settle(page, site_url, "diagrams")
    assert before["duplicates"] == [], before["duplicates"]

    page.evaluate("() => document.querySelector('.theme-toggle').click()")
    page.wait_for_timeout(3200)
    after = page.evaluate(PROBE)

    assert after["duplicates"] == [], after["duplicates"]
    assert after["orphans"] == [], after["orphans"]
    assert after["crossed"] == [], after["crossed"]
