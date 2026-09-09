"""The four buttons on a chart's own toolbar do what they say.

None of them was exercised by any test. That is how reader
personalization came to ship without ever running — a feature wired,
delivered and never once driven — and these four were fine only by
luck. Each is asserted on its EFFECT rather than on its presence: a
button that exists and does nothing is the failure this file is for.

`Expand to fullscreen` is the fifth and lives in
`test_lightbox_navigation.py`, which is about what happens after it.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet, until, until_changed

pytestmark = pytest.mark.browser

EXAMPLES = json.loads(
    (Path(__file__).resolve().parents[3] / "kit" / "schema" / "examples.json").read_text(encoding="utf-8")
)["charts"]

# What a zoom actually moves. Measured: the wheel leaves the `viewBox`
# alone and re-renders the plot's contents, so the first series path's
# own `d` is the signal — reading the viewBox would have compared a
# constant to itself and passed on a button wired to nothing.
PLOT = """() => { const p = document.querySelector('#c svg.okc-svg path');
  return p ? (p.getAttribute('d') || '').slice(0, 120) : null; }"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("toolbar") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "---\ntitle: Toolbar\nsummary: One chart.\n---\n\n## c {#c}\n\n```oku-chart\n"
        + json.dumps(EXAMPLES["line"], separators=(",", ":"))
        + "\n```\n",
        encoding="utf-8",
    )
    (docs / "page.html").write_text(cli._stub_for("Toolbar"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture
def opened(built, browser):
    """A context per test: the PNG case needs downloads accepted and the
    copy case needs the clipboard, and a shared page would carry one
    test's popover into the next one's click."""
    context = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900})
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    pg = context.new_page()
    pg.goto(built.as_uri(), wait_until="load")
    page_quiet(pg)
    # The toolbar is quiet chrome — it fades in on hover, and a button
    # mid-fade is one Playwright will decline to click.
    pg.hover("#c oku-chart")
    until(
        pg,
        "() => { const b = document.querySelector(\"#c [title='Copy data (TSV)']\");"
        "        return !!b && +getComputedStyle(b).opacity > 0.9; }",
        what="the chart toolbar faded in",
    )
    yield pg
    context.close()


def test_copy_data_hands_over_the_chart_s_own_numbers(opened):
    """A chart is a picture of a table the reader cannot otherwise
    reach. The header row is asserted because a copy without one lands
    in a spreadsheet as anonymous columns."""
    opened.click("#c [title='Copy data (TSV)']")
    until(
        opened,
        "() => navigator.clipboard.readText().then((t) => t.includes('\\t'))",
        what="something reached the clipboard",
    )
    text = opened.evaluate("() => navigator.clipboard.readText()")
    lines = text.strip().splitlines()
    assert lines[0].split("\t") == ["series", "x", "y", "label"], lines[0]
    series = {ln.split("\t")[0] for ln in lines[1:]}
    assert series == {s["label"] for s in EXAMPLES["line"]["series"]}, series
    # Every point, not a sample of them.
    assert len(lines) - 1 == sum(len(s["data"]) for s in EXAMPLES["line"]["series"])


def test_download_as_png_produces_an_image_named_after_the_chart(opened):
    """The one button whose whole output leaves the page, so nothing
    on screen would show it failing. The filename matters as much as the
    bytes: a reader who exports three charts gets three files, and
    `chart.png` three times is a worse answer than none."""
    with opened.expect_download(timeout=15000) as pending:
        opened.click("#c [title='Download as PNG']")
    download = pending.value
    assert download.suggested_filename.endswith(".png"), download.suggested_filename
    assert "latency" in download.suggested_filename, download.suggested_filename
    path = download.path()
    assert path is not None
    data = path.read_bytes()
    # A PNG, and not an empty canvas: the signature plus enough bytes
    # that the chart is actually in it.
    assert data[:8] == b"\x89PNG\r\n\x1a\n", data[:8]
    assert len(data) > 5000, len(data)


def test_configure_opens_the_chart_s_own_controls(opened):
    """The button that changes what the figure IS. It opens a popover
    rather than navigating, and the popover carries the chart's type, so
    a reader can see what they are about to change."""
    opened.click("#c [title='Configure chart']")
    until(
        opened,
        "() => !!document.querySelector('.okc-config-popover')",
        what="the configure popover opened",
    )
    # Queried document-wide, not inside the section: the popover is
    # appended to the document rather than to the chart it configures.
    # This page carries one chart, so there is no ambiguity about whose
    # it is — a page with two would need the anchor it was opened from.
    got = opened.evaluate(
        """() => { const sel = document.querySelector('select[data-cfg="type"]');
                   return sel ? { value: sel.value, options: sel.options.length } : null; }"""
    )
    assert got and got["value"] == "line", got
    assert got["options"] > 1, got


def test_reset_zoom_puts_the_view_back(opened):
    """`Reset zoom` has nothing to reset until the reader has zoomed, so
    this zooms first. Asserting the button against an unchanged view
    would pass on a button wired to nothing — the failure this file
    exists for."""
    before = opened.evaluate(PLOT)
    assert before, "the chart drew no viewBox to compare"
    box = opened.evaluate(
        """() => { const r = document.querySelector('#c svg.okc-svg').getBoundingClientRect();
                   return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }"""
    )
    opened.mouse.move(box["x"], box["y"])
    opened.mouse.wheel(0, -240)
    until_changed(opened, PLOT, before, what="the wheel zoomed the plot")

    opened.hover("#c oku-chart")
    zoomed = opened.evaluate(PLOT)
    opened.click("#c [title='Reset zoom']")
    # Wait for the redraw, then compare — rather than waiting ON the
    # comparison, so a reset that lands somewhere else reports where.
    until_changed(opened, PLOT, zoomed, what="the reset redrew the plot")
    assert opened.evaluate(PLOT) == before, (before, opened.evaluate(PLOT))
