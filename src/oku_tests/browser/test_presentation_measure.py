"""Where the line breaks, in one column.

**One column, two measures.** `--prose-width` was applied to
section-level paragraphs only, so a callout wrapped at 1037px directly
under a paragraph wrapping at 626px. The reader does not read the
selector; they see the line break move, and a wrap point that moves
mid-column is the first thing the eye catches.

Reported by a reader, not found by a test, which is why the cap now
has one.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PARA = (
    "Every checkpoint flushes whatever the writer has buffered, and a five-second "
    "checkpoint interval on a modestly sized topic produces twelve files per minute "
    "per bucket, none of them anywhere near the target size."
)

PAGE_MD = f"""---
title: One measure
summary: Running prose wraps at one width, whatever frame it sits in.
---

> [!TLDR]
> {PARA}

## Prose and its frames {{#prose}}

{PARA}

> [!IMPORTANT]
> {PARA}

{PARA}

## A table worth filtering {{#big}}

| Stage | Input | Output |
|---|---|---|
| a | 1 | x |
| b | 2 | x |
| c | 3 | x |
| d | 4 | x |
| e | 5 | x |
| f | 6 | x |
| g | 7 | x |
| h | 8 | x |

"""


@pytest.fixture(scope="module")
def measure_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("measure")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.md", "title": "One measure", "parent": None}],
    }
    (d / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("One measure", inline_manifest=manifest), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def rendered(measure_url, browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{measure_url}/page.html")
    page.wait_for_timeout(1800)
    yield page
    page.close()


def _width(page, selector):
    return page.evaluate(
        """(sel) => {
        const e = document.querySelector(sel);
        return e ? Math.round(e.getBoundingClientRect().width) : null;
    }""",
        selector,
    )


# ---------- one column, one measure ----------

# The frames add their own padding back, and the compensation is in `ch`
# against a padding written in px, so it lands within a character or two
# rather than exactly. A reader notices a wrap point moving by a word,
# not by a character.
MEASURE_SLACK_PX = 14


def test_a_callout_wraps_where_the_paragraph_above_it_wraps(rendered):
    """Measured before the fix: 626px for the paragraph, 1037px for the
    callout body directly below it — a 66% jump inside one column."""
    para = _width(rendered, "main > section > p")
    body = _width(rendered, ".callout > p")
    assert para and body, (para, body)
    assert abs(body - para) <= MEASURE_SLACK_PX, (
        f"a callout wraps at {body}px where the prose around it wraps at {para}px"
    )


def test_the_tldr_wraps_where_prose_wraps(rendered):
    """Same divergence, on the block that opens most pages: 1046px."""
    para = _width(rendered, "main > section > p")
    body = _width(rendered, ".tldr > p")
    assert para and body, (para, body)
    assert abs(body - para) <= MEASURE_SLACK_PX, (
        f"the TL;DR wraps at {body}px where the prose around it wraps at {para}px"
    )


@pytest.mark.parametrize("mode", ["narrow", "comfortable", "wide"])
def test_framed_prose_tracks_the_width_toggle(rendered, mode):
    """The cap is one number per mode, so the frames have to move with
    it — a callout pinned to the comfortable measure would diverge
    again the moment the reader widened the page."""
    rendered.evaluate("(m) => document.body.setAttribute('data-content-width', m)", mode)
    rendered.wait_for_timeout(120)
    para = _width(rendered, "main > section > p")
    body = _width(rendered, ".callout > p")
    rendered.evaluate("() => document.body.setAttribute('data-content-width', 'comfortable')")
    assert abs(body - para) <= MEASURE_SLACK_PX, f"{mode}: callout {body}px vs prose {para}px"


def test_the_two_framed_blocks_share_a_right_edge(rendered):
    """A callout and the TL;DR panel are both tinted frames in the same
    column. At prose + 8ch and prose + 7ch they landed 11px apart, and
    a right edge that is almost-but-not-quite shared reads as a
    misalignment rather than a decision."""
    got = rendered.evaluate(
        """() => {
        const r = s => { const e = document.querySelector(s);
                         return e ? Math.round(e.getBoundingClientRect().right) : null; };
        return { callout: r('.callout'), tldr: r('.tldr') };
    }"""
    )
    assert got["callout"] and got["tldr"], got
    assert abs(got["callout"] - got["tldr"]) <= 1, got


def test_max_mode_drops_the_cap_on_framed_prose_too(rendered):
    """`max` means "use the window". Leaving a callout capped there
    would make it the only narrow thing on the page."""
    rendered.evaluate("() => document.body.setAttribute('data-content-width', 'max')")
    rendered.wait_for_timeout(120)
    got = rendered.evaluate(
        """() => ({
        callout: getComputedStyle(document.querySelector('.callout')).maxWidth,
        tldr: getComputedStyle(document.querySelector('.tldr')).maxWidth,
    })"""
    )
    rendered.evaluate("() => document.body.setAttribute('data-content-width', 'comfortable')")
    assert got["callout"] == "none", got
    assert got["tldr"] == "none", got
