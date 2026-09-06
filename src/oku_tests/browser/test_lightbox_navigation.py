"""An expanded figure can be moved around by the reader who opened it.

The lightbox already had the parts: drag to pan, wheel and pinch to
zoom, a three-button toolbar, `+` / `-` / `0` and arrow keys, and a
picture-in-picture minimap whose viewport rect tracks the visible
region and can be dragged to pan. The roadmap asked for that minimap
and it had shipped.

What had not shipped is reaching any of it from the keyboard. `open()`
sent focus to `.okt-lightbox-content`, and every key the stage listens
for is bound to the STAGE, which sits inside that holder — so a keydown
on the holder bubbles up and away from the listener. Measured: open a
chart, press `+`, and the transform stayed `translate(0px, 0px)
scale(1)`. One Tab first and the same key zoomed. Nothing on the page
said a Tab was needed.

Focus goes to the stage when there is one. Escape is unaffected — it is
bound on `document` — and this file asserts the focus order either
side of the change, because moving where focus starts is exactly what
quietly breaks a dialog.

Asserting it found a second defect, older than the first. The overlay
carries `aria-modal="true"` and this module's own header says focus is
trapped until the reader closes it. It was not: the close button is
drawn BEFORE the content inside the frame, so tabbing forward from the
content walked past the frame and into the page behind — 39 presses on
a 20-point chart, with the close button reachable only by Shift+Tab.
Tab now wraps at both ends.

The other half of that roadmap row was a scrollbar, and it stays
unbuilt on purpose: the stage is a transform, not a scroll container,
and a scrollbar over a figure the reader is panning by drag would be a
second mechanism for the same job. The minimap is what says where you
are.
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


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("lightbox") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "---\ntitle: Lightbox\nsummary: One chart to expand.\n---\n\n"
        "## A chart {#chart}\n\n```oku-chart\n"
        + json.dumps(EXAMPLES["line"], separators=(",", ":"))
        + "\n```\n",
        encoding="utf-8",
    )
    (docs / "page.html").write_text(cli._stub_for("Lightbox"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


STATE = """() => {
  const stage = document.querySelector('.okt-lightbox-pz');
  const inner = document.querySelector('.okt-lightbox-pz-inner');
  const pip = document.querySelector('.okt-lightbox-pip');
  const vp = document.querySelector('.okt-lightbox-pip-viewport');
  const ae = document.activeElement;
  const m = inner && /scale\\(([\\d.]+)\\)/.exec(inner.style.transform || '');
  const t = inner && /translate\\((-?[\\d.]+)px, *(-?[\\d.]+)px\\)/.exec(inner.style.transform || '');
  return {
    open: !!document.querySelector('.okt-lightbox.open'),
    scale: m ? +m[1] : null,
    tx: t ? +t[1] : null,
    ty: t ? +t[2] : null,
    active: ae ? ae.className || ae.tagName : null,
    stageFocused: !!stage && ae === stage,
    stageName: stage ? stage.getAttribute('aria-label') : null,
    pipVisible: !!pip && pip.classList.contains('visible'),
    pipThumb: !!document.querySelector('.okt-lightbox-pip-inner svg'),
    vpLeft: vp ? vp.style.left : null,
    vpWidth: vp ? vp.style.width : null,
  };
}"""


@pytest.fixture
def opened(built, browser):
    """A fresh page per test: the subject is what happens on OPEN, and a
    shared page would carry the previous test's focus and transform into
    the next one's first assertion."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    page.hover("#chart oku-chart")
    page.click("#chart [aria-label='Expand to fullscreen']")
    page.wait_for_selector(".okt-lightbox.open .okt-lightbox-pz")
    page.wait_for_timeout(150)
    yield page
    page.close()


def test_the_first_zoom_key_zooms(opened):
    """The defect, stated as the reader's first action. Someone who
    expands a figure to look closer presses `+` — and got nothing, on
    every chart, on every page."""
    before = opened.evaluate(STATE)
    assert before["scale"] == 1, before
    opened.keyboard.press("+")
    opened.wait_for_timeout(200)
    after = opened.evaluate(STATE)
    assert after["scale"] > before["scale"], (before, after)


def test_the_first_arrow_key_pans(opened):
    """The same gap on the other set of keys, and the one that matters
    more: zoom has three toolbar buttons, and panning has no button at
    all. Without the keys a reader who cannot drag has no way to reach
    the part of the figure they zoomed in for."""
    opened.keyboard.press("+")
    opened.keyboard.press("+")
    opened.wait_for_timeout(200)
    before = opened.evaluate(STATE)
    opened.keyboard.press("ArrowRight")
    opened.wait_for_timeout(200)
    after = opened.evaluate(STATE)
    assert after["tx"] < before["tx"], (before, after)
    assert after["ty"] == before["ty"], (before, after)


def test_focus_lands_on_the_stage_and_it_has_a_name(opened):
    """A focusable element with no accessible name is announced as
    nothing. It is also the only place the shortcuts are written down —
    the toolbar's three buttons cover zoom and say nothing about
    panning."""
    got = opened.evaluate(STATE)
    assert got["stageFocused"], got
    assert got["stageName"], got
    assert "Arrow" in got["stageName"], got


def test_escape_still_closes(opened):
    """The thing the change could break. Escape is bound on `document`
    rather than on the holder that used to hold focus, so moving focus
    inwards leaves it working — asserted rather than reasoned, because a
    modal the reader cannot dismiss is worse than one whose keys need a
    Tab."""
    opened.keyboard.press("Escape")
    opened.wait_for_timeout(250)
    assert opened.evaluate(STATE)["open"] is False


def test_focus_stays_inside_the_dialog_and_every_control_is_reachable(opened):
    """Moving initial focus is how a dialog's focus order quietly
    breaks, so both halves are asserted: focus never leaves the overlay,
    and all four controls can still be reached by Tab.

    The distance is not one Tab and this does not pretend otherwise:
    measured on this fixture, the three zoom buttons sit 21, 22 and 23
    presses in, because the live chart node is MOVED into the lightbox
    and each of its 20 data points is focusable and precedes the toolbar
    in DOM order. That predates focus starting on the stage and is
    unchanged by it — recorded rather than fixed, since the dots are
    focusable on purpose and reordering the stage against its own
    toolbar is a separate decision. What is fixed is the leak past the
    end: the loop asserts on EVERY press that focus is still inside the
    overlay, so a trap that stops wrapping fails here on the press it
    stops.
    """
    seen = {}
    for i in range(80):
        opened.keyboard.press("Tab")
        who = opened.evaluate(
            """() => { const a = document.activeElement;
                       if (!a) return null;
                       return { role: a.getAttribute('data-pz')
                                      || (a.classList && a.classList.contains('okt-lightbox-close') ? 'close' : null),
                                inLightbox: !!a.closest('.okt-lightbox') }; }"""
        )
        assert who and who["inLightbox"], f"focus left the dialog after {i + 1} tab(s): {who}"
        if who["role"] and who["role"] not in seen:
            seen[who["role"]] = i + 1
        if len(seen) == 4:
            break
    assert set(seen) == {"out", "reset", "in", "close"}, seen


def test_the_minimap_appears_only_once_there_is_something_to_navigate(opened):
    """Already shipped, pinned here because the keyboard path is now the
    fastest way to reach it. Hidden at rest so the chrome stays quiet:
    at scale 1 the viewport IS the figure and a minimap would be a box
    saying "all of it"."""
    assert opened.evaluate(STATE)["pipVisible"] is False
    for _ in range(4):
        opened.keyboard.press("+")
        opened.wait_for_timeout(80)
    got = opened.evaluate(STATE)
    assert got["pipVisible"], got
    assert got["pipThumb"], "the minimap is an empty box — no thumbnail of the figure"


def test_the_minimap_says_where_the_reader_is_and_takes_them_elsewhere(opened):
    """Both directions, because a minimap that only reports is half a
    control. The rect tracks the transform, and dragging it moves the
    stage under it."""
    for _ in range(5):
        opened.keyboard.press("+")
        opened.wait_for_timeout(80)
    before = opened.evaluate(STATE)
    opened.keyboard.press("ArrowRight")
    opened.wait_for_timeout(150)
    tracked = opened.evaluate(STATE)
    assert float(tracked["vpLeft"].rstrip("%")) > float(before["vpLeft"].rstrip("%")), (before, tracked)
    assert tracked["vpWidth"] == before["vpWidth"], (before, tracked)

    box = opened.evaluate(
        """() => { const v = document.querySelector('.okt-lightbox-pip-viewport');
                   const r = v.getBoundingClientRect();
                   return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }"""
    )
    opened.mouse.move(box["x"], box["y"])
    opened.mouse.down()
    opened.mouse.move(box["x"] + 20, box["y"] + 10, steps=6)
    opened.mouse.up()
    opened.wait_for_timeout(200)
    dragged = opened.evaluate(STATE)
    assert (dragged["tx"], dragged["ty"]) != (tracked["tx"], tracked["ty"]), (tracked, dragged)
