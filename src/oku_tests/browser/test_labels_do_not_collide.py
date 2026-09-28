"""A figure's labels stay readable when the labels are real length.

Reported by a reader: charts and diagrams still cut text, and some of
it becomes impossible to read. `tools/text_fit_audit.py` measured it
across every figure the kit draws — this holds the ones that were
fixed, so the next renderer change cannot quietly put them back.

The detector is imported from the tool rather than copied: two
implementations of "is this label cut" drift, and the one in the test
is the copy that stops matching what the audit reports.

Only the wordy variant is asserted here, and only for the figures the
audit named: a full sweep is 134 pages and belongs in the tool, which
is where a new chart type gets measured on the day it lands.
"""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("_text_fit_audit", ROOT / "tools" / "text_fit_audit.py")
_audit = importlib.util.module_from_spec(_spec)
sys.modules["_text_fit_audit"] = _audit
_spec.loader.exec_module(_audit)

# Every figure the audit reported a collision, a clip or a collapse in,
# and which was then fixed. A name comes off this list only with a
# measurement saying the defect is gone for a different reason.
FIXED = [
    "stream",
    "bump",
    "horizon",
    "waterfall",
    "marimekko",
    "heatmap",
    "radar",
    "slope",
    "sankey",
    "geo",
    "quadrant",
    "bubble",
    "scatter",
    "plot",
    "parallel-coordinates",
    "population-pyramid",
    "scatter-matrix",
    "connected-scatter",
    "dumbbell",
    "network",
    "gauge",
    "treemap",
]

# Findings that mean the reader cannot read something. `ellipsis` is
# not among them: shortening with the full string in a <title> is the
# designed behaviour, and it is reported by the tool with the fraction
# that survived so an author can judge it.
BREAKS = {"overlap", "clipped-svg", "clipped-clip", "clipped-html", "plot-starved", "lost-marks"}


@pytest.fixture(scope="module")
def swept(tmp_path_factory):
    out = tmp_path_factory.mktemp("labelfit")
    pages = _audit.build_pages(FIXED, out)
    return out, pages


@pytest.mark.parametrize("width", [1280, 360])
def test_no_label_is_hidden_by_another_or_by_the_frame(swept, browser, width):
    out, pages = swept
    findings: list[dict] = []
    looked = 0
    context = browser.new_context(viewport={"width": width, "height": 900})
    try:
        for name in sorted(pages):
            if not name.endswith("~wordy"):
                continue
            page = context.new_page()
            try:
                page.goto(
                    (out / "docs" / "dist" / "standalone" / f"{_audit._slug(name)}.html").as_uri(),
                    wait_until="load",
                )
                page.wait_for_function("() => window.__okuRendered === true", timeout=30000)
                page.wait_for_timeout(600)
                got = page.evaluate(_audit.AUDIT, "#c")
                looked += got.get("texts", 0) + got.get("marks", 0)
                for f in got.get("findings", []):
                    if f["cls"] in BREAKS:
                        findings.append({"figure": name, **f})
            finally:
                page.close()
    finally:
        context.close()

    # Not vacuous: the detector has to have had something to look at.
    assert looked > 100, f"only {looked} texts and marks seen across {len(pages)} pages"
    assert findings == [], (
        f"{len(findings)} unreadable labels at {width}px: "
        f"{Counter((f['figure'], f['cls']) for f in findings).most_common(6)}\n"
        + "\n".join(
            f"  {f['figure']} {f['cls']} {f.get('where')} :: {f.get('text', '')[:60]}" for f in findings[:8]
        )
    )
