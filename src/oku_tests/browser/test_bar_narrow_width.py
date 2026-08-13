"""A bar keeps a length worth comparing, at every width.

Reported from a delivered document at a 360px viewport: every bar in a
six-row chart measured between 1px and 4px, the longest one 4px. The
rows, the labels and the values all rendered; the one thing the chart
exists to show was gone.

The cause is a track-sizing detail with a blunt consequence. The chart's
columns were `minmax(40px, max-content) minmax(0, 1fr) auto`, and a
max-content column does not shrink — when the row runs short of space it
is the `1fr` track that gives, because `1fr` floors at 0. So the label
column is served first and in full, and the bar is paid out of what is
left. Measured at 360px before the fix: label 143px, value 49px, gaps
24px, track 106px of a 316px chart; a slightly longer label takes the
track to single digits.

Two changes, and this file pins both. The label column is capped at 42%
so a track always keeps its share, and below 340px of CHART width the
row becomes two lines — label and value, then the track full-width
beneath. The trigger is the chart's width, not the viewport's: the same
collapse happens in a narrow grid cell on a wide screen.

The invariant is one number. A track under ~120px cannot encode a
comparison, so no track may be narrower than that at any width where the
chart is shown at all.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

TRACK_FLOOR = 120

# The chart from the report, labels included — they are what makes the
# label column wide enough to matter.
ROWS = [
    {"label": "Free", "value": 26.9, "display": "26.9 GB"},
    {"label": "Wired (kernel + pinned)", "value": 10.4, "display": "10.4 GB"},
    {"label": "Inactive (reclaimable)", "value": 9.2, "display": "9.2 GB"},
    {"label": "Active (working set)", "value": 9.0, "display": "9.0 GB"},
    {"label": "Compressor", "value": 6.6, "display": "6.6 GB"},
    {"label": "Speculative", "value": 0.2, "display": "0.2 GB"},
]

# Longer than any sane gutter guess. Without the cap this column takes
# whatever it asks for and the track takes the remainder, which is how
# the 4px bar happened.
LONG_ROWS = [
    {"label": "Wired kernel pages plus everything pinned by a driver", "value": 26.9},
    {"label": "Inactive but still reclaimable under pressure", "value": 10.4},
    {"label": "Active working set as of the last sample", "value": 9.2},
]

PAGE = f"""---
title: Narrow bars
summary: A bar keeps a readable length at every width.
---

## Memory {{#memory}}

Lead paragraph.

```oku-chart
{json.dumps({"type": "bar", "title": "Memory pressure", "rows": ROWS})}
```

## Long labels {{#long}}

Lead paragraph.

```oku-chart
{json.dumps({"type": "bar", "title": "Long labels", "rows": LONG_ROWS})}
```
"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("barnarrow")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "p.md").write_text(PAGE, encoding="utf-8")
    (d / "p.html").write_text(
        cli._stub_for("Narrow bars", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


GEOMETRY = """() => [...document.querySelectorAll('.bar-chart')].map(chart => ({
  chartW: chart.getBoundingClientRect().width,
  rows: [...chart.querySelectorAll('.bar-row')].map(r => {
    const box = s => { const e = r.querySelector(s); if (!e) return null;
      const b = e.getBoundingClientRect();
      return {w: b.width, left: b.left, top: b.top, bottom: b.bottom}; };
    return {label: box('.bar-label'), track: box('.bar-track'),
            fill: box('.bar-fill'), value: box('.bar-value')};
  })
}))"""


def _at(browser, url, width):
    pg = browser.new_page(viewport={"width": width, "height": 1200})
    pg.goto(url + "/p.html")
    pg.wait_for_function("() => window.__okuRendered === true", timeout=30000)
    pg.wait_for_timeout(250)
    charts = pg.evaluate(GEOMETRY)
    pg.close()
    return charts


@pytest.mark.parametrize("width", [360, 430, 768, 1280])
def test_a_bar_track_is_never_squeezed_below_the_width_it_needs(served, browser, width):
    """The whole defect in one assertion. 106px was the measurement that
    still looked plausible; 4px was the one that got reported."""
    for ci, chart in enumerate(_at(browser, served, width)):
        for ri, row in enumerate(chart["rows"]):
            assert row["track"]["w"] >= TRACK_FLOOR, (
                f"chart {ci} row {ri} at {width}px: track {row['track']['w']:.0f}px "
                f"in a {chart['chartW']:.0f}px chart — under the {TRACK_FLOOR}px floor"
            )


def test_at_360_the_row_is_two_lines_with_the_track_beneath(served, browser):
    """Label and value share the first line; the track has the second to
    itself. Stated as positions, because 'stacks on mobile' is not
    something a test can check."""
    for ci, chart in enumerate(_at(browser, served, 360)):
        for ri, row in enumerate(chart["rows"]):
            lab, val, track = row["label"], row["value"], row["track"]
            assert val["top"] < track["top"], f"chart {ci} row {ri}: the value is not on the label's line"
            assert track["top"] >= lab["bottom"] - 1, (
                f"chart {ci} row {ri}: the track starts at y={track['top']:.0f}, "
                f"above the label's bottom at {lab['bottom']:.0f} — still one line"
            )
            assert track["w"] >= chart["chartW"] - 1, (
                f"chart {ci} row {ri}: the track is {track['w']:.0f}px of a "
                f"{chart['chartW']:.0f}px chart — not full width"
            )


@pytest.mark.parametrize("width", [768, 1280])
def test_above_the_stop_the_row_is_one_line_again(served, browser, width):
    """The two-line shape is for the width that needs it, not a new
    default. A regression that stacks everywhere would pass the floor
    assertion above on its own."""
    for ci, chart in enumerate(_at(browser, served, width)):
        for ri, row in enumerate(chart["rows"]):
            assert row["track"]["top"] < row["label"]["bottom"], (
                f"chart {ci} row {ri} at {width}px: the track is on its own line"
            )


@pytest.mark.parametrize("width", [768, 1280])
def test_a_long_label_cannot_take_more_than_its_share_of_the_row(served, browser, width):
    """`fit-content(42%)` is what stops a label column from being served
    first and in full. The long-label chart is the second one."""
    chart = _at(browser, served, width)[1]
    for ri, row in enumerate(chart["rows"]):
        share = row["label"]["w"] / chart["chartW"]
        assert share <= 0.45, f"long-label row {ri} at {width}px: the label takes {share:.0%} of the chart"


def test_the_bars_still_share_an_origin_and_a_scale(served, browser):
    """Two properties the two-line shape must not cost: every bar starts
    at the same x, and the longest one still fills its track."""
    for width in (360, 1280):
        for ci, chart in enumerate(_at(browser, served, width)):
            lefts = {round(r["fill"]["left"]) for r in chart["rows"]}
            assert len(lefts) == 1, (
                f"chart {ci} at {width}px: bars start at {sorted(lefts)}, not a shared origin"
            )
            widest = max(r["fill"]["w"] for r in chart["rows"])
            track = chart["rows"][0]["track"]["w"]
            assert widest >= track - 1, (
                f"chart {ci} at {width}px: the longest bar is {widest:.0f}px "
                f"of a {track:.0f}px track — the scale no longer reaches the end"
            )
