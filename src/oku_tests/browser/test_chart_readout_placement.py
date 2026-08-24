"""A number the renderer prints beside a mark does not land ON the mark.

Reported against a delivered document: a range-bar row whose `high` was
the domain maximum had its "120–220" readout drawn across the end of its
own band, so the two numbers that matter most on the chart sat on top of
a filled rectangle and the digits were unreadable.

The cause is one line of arithmetic, and it is the same shape as the
constant left gutter this repo already fixed: the readout is drawn at
`W - pad.right` with `text-anchor="end"`, which puts its GLYPHS to the
LEFT of that x. `pad.right` was a constant reserving nothing for them,
so the plot area and the readout column were the same pixels. Some row
always collides, because the domain is derived from the rows — the
widest bar ends exactly where the readout starts.

Two assertions, because the two families fail differently:

* **range-bar** draws the readout inside the box, so the failure is an
  OVERLAP with a `<rect>`; `test_chart_label_fit.py` measures against
  the viewBox and cannot see it.
* **bullet** draws it outside the plot against a constant `right: 80`,
  so a wide value overruns the viewBox and the kit's generic fit pass
  rescues it the only way it knows: by SHORTENING it. That is right for
  a name and wrong for a number — the reader got `1234567…`, which
  reads as a different quantity rather than as a truncation. Provoked
  with a wide VALUE rather than a long label, the axis the label-fit
  sweep does not vary.

Screen rects throughout, never `getBBox()`: getBBox is pre-transform and
reports a rotated label as horizontal.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# First row's `high` IS the domain maximum and carries the widest
# readout of the set — the exact shape that shipped broken.
CHARTS = {
    "range": {
        "type": "range-bar",
        "title": "Readout placement",
        "ranges": [
            {"label": "reaches the maximum", "low": 120000, "mid": 170000, "high": 220000},
            {"label": "middle of the domain", "low": 85000, "mid": 120000, "high": 160000},
            {"label": "at the floor", "low": 32000, "mid": 41000, "high": 50000},
        ],
    },
    "bullet": {
        "type": "bullet",
        "title": "Wide readouts",
        "tracks": [
            {"label": "narrow", "value": 7, "max": 10},
            {"label": "wide", "value": 1234567890123, "max": 2000000000000},
        ],
    },
}

MEASURE = r"""() => {
  const out = [];
  document.querySelectorAll('svg.okc-svg').forEach((svg) => {
    const box = svg.getBoundingClientRect();
    if (!box.width) return;
    const marks = [...svg.querySelectorAll('rect.okc-range-band, rect.okc-bullet-value')]
      .map((m) => ({cls: m.getAttribute('class'), r: m.getBoundingClientRect()}));
    svg.querySelectorAll('text.okc-range-readout, text.okc-bullet-readout').forEach((t) => {
      const r = t.getBoundingClientRect();
      if (!r.width) return;
      const hit = marks.filter((m) =>
        r.left < m.r.right - 0.5 && r.right > m.r.left + 0.5 &&
        r.top < m.r.bottom - 0.5 && r.bottom > m.r.top + 0.5);
      out.push({
        cls: t.getAttribute('class') || '',
        text: t.textContent,
        clip: Math.round(Math.max(box.left - r.left, r.right - box.right) * 10) / 10,
        overlaps: hit.map((m) => m.cls),
      });
    });
  });
  return out;
}"""


def _page(payload: dict) -> str:
    return (
        "---\ntitle: Readout placement\nsummary: Numbers beside marks, measured.\n---\n\n"
        "## Chart {#chart}\n\nLead paragraph.\n\n"
        f"```oku-chart\n{json.dumps(payload)}\n```\n"
    )


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("readoutplacement").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "readout", "accent": "teal"}), encoding="utf-8")
    for name, payload in CHARTS.items():
        (d / f"{name}.md").write_text(_page(payload), encoding="utf-8")
        (d / f"{name}.html").write_text(
            cli._stub_for(name, inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
            encoding="utf-8",
        )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _read(browser, served, name):
    pg = browser.new_page(viewport={"width": 1440, "height": 1200})
    try:
        pg.goto(f"{served}/{name}.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        # Same two waits the fit pass takes: a measurement taken before
        # the webfont lands reads widths the reader never sees.
        pg.evaluate("() => document.fonts.ready")
        page_quiet(pg)
        return list(pg.evaluate(MEASURE))
    finally:
        pg.close()


def test_a_range_bar_readout_is_not_drawn_on_top_of_its_band(browser, served):
    rows = _read(browser, served, "range")
    assert rows, "no readouts measured — the fixture stopped rendering"
    hit = [r for r in rows if r["overlaps"]]
    assert not hit, "readouts drawn over their own marks: " + "; ".join(
        f"{r['text']!r} over {r['overlaps']}" for r in hit
    )


def test_a_wide_bullet_readout_is_neither_clipped_nor_shortened(browser, served):
    """A name may be shortened because the tail stays in a <title>. A
    number may not: `1234567…` is not a shorter way of writing the
    value, it is a different value, and the reader has no cue that
    anything was dropped."""
    rows = _read(browser, served, "bullet")
    assert rows, "no readouts measured — the fixture stopped rendering"
    clipped = [r for r in rows if r["clip"] > 0.5]
    assert not clipped, "readouts outside the viewBox: " + "; ".join(
        f"{r['text']!r} by {r['clip']}px" for r in clipped
    )
    trimmed = [r for r in rows if "\u2026" in r["text"]]
    assert not trimmed, "readout numbers shortened: " + "; ".join(repr(r["text"]) for r in trimmed)
