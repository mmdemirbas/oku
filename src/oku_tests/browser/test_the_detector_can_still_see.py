"""The text-fit detector's two negative rules, each with its opposite.

`tools/text_fit_audit.py` learned two things to stay quiet about, and
both were learned from a false report it had already made:

  - a scroller between the text and a clipping box means the text is
    off screen and reachable, not lost (the live-snippet editor is a
    `pre` at `overflow: auto` inside a wrap at `overflow: hidden`, and
    reading only for `hidden` called 54 Prism tokens clipped);
  - visibility is inherited in effect, so an element's own three
    properties do not decide it (an annotated-code tooltip is
    `display: none` at rest and every token inside it computes
    visible, which reported three tooltips of text as cut).

A rule that says "no finding" is only worth what its opposite proves,
so each case here is paired with the shape it must still report. The
detector runs against a hand-built DOM rather than a kit page: what is
under test is the rule, and a kit page brings a renderer's worth of
other reasons for the count to move.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("_text_fit_audit", ROOT / "tools" / "text_fit_audit.py")
_audit = importlib.util.module_from_spec(_spec)
sys.modules["_text_fit_audit"] = _audit
_spec.loader.exec_module(_audit)

WORD = "Bir_cok_karakterden_olusan_kesilmeye_aday_uzun_bir_etiket_metni"

BOX = "width:60px;white-space:nowrap;font:14px sans-serif"

CASES = {
    # id: (html inside #c, how many clipped-html findings it must give)
    "hidden-box-cuts": (f'<div style="{BOX};overflow:hidden"><span>{WORD}</span></div>', 1),
    "scroller-does-not": (f'<div style="{BOX};overflow:auto"><span>{WORD}</span></div>', 0),
    "scroller-inside-hidden": (
        f'<div style="{BOX};overflow:hidden">'
        f'<div style="{BOX};overflow:auto"><span>{WORD}</span></div></div>',
        0,
    ),
    "hidden-inside-scroller-still-cuts": (
        f'<div style="{BOX};overflow:auto">'
        f'<div style="{BOX};overflow:hidden"><span>{WORD}</span></div></div>',
        1,
    ),
    "display-none-ancestor": (
        f'<div style="{BOX};overflow:hidden"><div style="display:none"><span>{WORD}</span></div></div>',
        0,
    ),
    "visibility-hidden-ancestor": (
        f'<div style="{BOX};overflow:hidden"><div style="visibility:hidden"><span>{WORD}</span></div></div>',
        0,
    ),
    "zero-opacity-ancestor": (
        f'<div style="{BOX};overflow:hidden"><div style="opacity:0"><span>{WORD}</span></div></div>',
        0,
    ),
}


@pytest.fixture()
def probe(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    def run(html: str) -> list[dict]:
        page.set_content(f'<body style="margin:0"><div id="c">{html}</div></body>')
        got = page.evaluate(_audit.AUDIT, "#c")
        assert "error" not in got, got
        return [f for f in got["findings"] if f["cls"] == "clipped-html"]

    yield run
    context.close()


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_rule_and_its_opposite(probe, case):
    html, want = CASES[case]
    got = probe(html)
    assert len(got) == want, f"{case}: wanted {want} clipped-html, got {got}"
