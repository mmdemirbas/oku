"""A copy region hands over what it shows, in the format that was asked for.

The primitive exists for one job: telling a reader "replace THIS with
THAT" in a document they are about to edit. Everything worth asserting
follows from that job.

- The three formats must differ, and each must be right for its
  destination. Markdown is the author's source **verbatim** — a
  re-serialised DOM would give back *a* markdown, not *the* one, and the
  round trip is the whole reason the format is offered. Plain is the
  text with the syntax gone. Rich is semantic HTML with none of this
  page's classes, ids or inline styles on it.
- What is copied must be what is *shown*, minus the kit's own chrome.
  The line-number gutter, the fold markers and the diff marks all live
  inside the rendered region; a copy that read the DOM would carry them.
- The diff must mark only the words that changed. A diff that marks a
  whole paragraph tells the reader nothing they did not already have.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

# The two differ in three words of the first sentence and nowhere
# else. Everything after it is there so the diff has something it
# must NOT mark, across a block boundary and inside a link.
TAIL = "\n\n- see [the ticket](https://example.org/x)\n- rerun the job"
BEFORE = "The fix landed in the next release." + TAIL
BODY = "The fix landed in Apache main." + TAIL

PAGE_MD = f"""---
title: Copy
summary: A page carrying copy regions.
---

## Paired {{#paired}}

```oku-copy
{{"t":"Section 2.2, second paragraph","before":{json.dumps(BEFORE)},"b":{json.dumps(BODY)}}}
```

## Alone {{#alone}}

```oku-copy
{{"formats":["markdown"],"b":"Just the one block."}}
```

## Opted out {{#plain}}

```oku-copy
{{"diff":false,"before":{json.dumps(BEFORE)},"b":{json.dumps(BODY)}}}
```
"""

SHAPE = """() => {
  const regions = [...document.querySelectorAll('.okt-copy')];
  return regions.map(r => ({
    diffed: r.classList.contains('okt-copy-diffed'),
    head: (r.querySelector('.okt-copy-head') || {}).textContent || null,
    parts: [...r.querySelectorAll('.okt-copy-region')].map(s => ({
      variant: s.className.replace('okt-copy-region ', ''),
      role: (s.querySelector('.okt-copy-role') || {}).textContent || null,
      buttons: [...s.querySelectorAll('.okt-copy-btn')].map(b => ({
        format: b.getAttribute('data-copy-format'),
        label: (b.querySelector('.okt-copy-label') || {}).textContent,
        title: b.getAttribute('title'),
        icons: b.querySelectorAll('.okt-copy-icon svg').length,
      })),
      del: [...s.querySelectorAll('del.okt-copy-del')].map(d => d.textContent),
      ins: [...s.querySelectorAll('ins.okt-copy-ins')].map(d => d.textContent),
    })),
  }));
}"""

READ_HTML = """async () => {
  const items = await navigator.clipboard.read();
  for (const it of items) {
    if (it.types.includes('text/html')) {
      return await (await it.getType('text/html')).text();
    }
  }
  return null;
}"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("copyregion") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Copy"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def opened(built, browser):
    context = browser.new_context()
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page.wait_for_timeout(700)
    yield page
    context.close()


@pytest.fixture(scope="module")
def shape(opened):
    return opened.evaluate(SHAPE)


def test_a_pair_says_which_half_is_which(shape):
    """Two unlabelled quotations side by side are ambiguous in exactly
    the direction that matters: which one goes into the document."""
    pair = shape[0]
    assert pair["head"] == "Section 2.2, second paragraph"
    assert [p["variant"] for p in pair["parts"]] == ["okt-copy-was", "okt-copy-now"]
    assert [p["role"] for p in pair["parts"]] == ["Replace", "With"]


def test_the_old_half_offers_only_plain_text(shape):
    """It is there to be *found* in the target document, and neither
    Cmd+F nor a wiki search box takes rich text."""
    was = shape[0]["parts"][0]
    assert [b["format"] for b in was["buttons"]] == ["plain"]
    # One choice is no choice, so the button says what it does, not
    # which of several formats it is.
    assert was["buttons"][0]["label"] == "Copy"


def test_the_new_half_offers_all_three_in_a_fixed_order(shape):
    now = shape[0]["parts"][1]
    assert [b["format"] for b in now["buttons"]] == ["rich", "markdown", "plain"]
    assert [b["label"] for b in now["buttons"]] == ["Rich", "Markdown", "Plain"]
    assert [b["title"] for b in now["buttons"]] == [
        "Copy as rich text",
        "Copy as Markdown",
        "Copy as plain text",
    ]
    # chrome.js prepends the clipboard glyph; without it the buttons are
    # three words in a row and read as prose, not as controls.
    assert [b["icons"] for b in now["buttons"]] == [1, 1, 1]


def test_only_the_changed_words_are_marked(shape):
    """The point of the diff is subtraction. Marking the sentence marks
    nothing — the reader still has to find the edit themselves."""
    was, now = shape[0]["parts"]
    # Contiguous changed words are ONE mark, not one per word: three
    # abutting boxes with hairlines between them read as three separate
    # edits, and the reader then looks for three.
    assert was["del"] == ["the next release"]
    assert was["ins"] == []
    assert now["ins"] == ["Apache main"]
    assert now["del"] == []


def test_an_author_can_turn_the_diff_off(shape):
    """A region whose two halves are unrelated — a rewrite, not an edit —
    gets a diff that is noise, so `diff: false` is part of the payload."""
    opted_out = shape[2]
    assert opted_out["diffed"] is False
    assert all(p["del"] == [] and p["ins"] == [] for p in opted_out["parts"])
    assert shape[0]["diffed"] is True


def test_a_lone_region_has_no_role_word(shape):
    """`With` only means something opposite a `Replace`."""
    alone = shape[1]
    assert len(alone["parts"]) == 1
    assert alone["parts"][0]["role"] is None
    assert [b["format"] for b in alone["parts"][0]["buttons"]] == ["markdown"]


def _button(page, region, fmt):
    return page.locator(".okt-copy").nth(region).locator(f".okt-copy-btn[data-copy-format='{fmt}']")


def test_markdown_is_the_source_verbatim(opened):
    _button(opened, 0, "markdown").click()
    opened.wait_for_timeout(250)
    assert opened.evaluate("() => navigator.clipboard.readText()") == BODY


def test_plain_text_is_the_syntax_gone(opened):
    _button(opened, 0, "plain").last.click()
    opened.wait_for_timeout(250)
    text = opened.evaluate("() => navigator.clipboard.readText()")
    assert text == (
        "The fix landed in Apache main.\n\n- see the ticket (https://example.org/x)\n- rerun the job"
    )
    # The mark-up is gone and so are the diff marks, but the URL is not:
    # a link that arrives as bare words has lost the only part of itself
    # the reader cannot reconstruct.
    assert "**" not in text and "[" not in text


def test_rich_text_carries_structure_and_none_of_this_page(opened):
    _button(opened, 0, "rich").click()
    opened.wait_for_timeout(250)
    html = opened.evaluate(READ_HTML)
    assert html is not None, "nothing on the clipboard offered text/html"
    assert "<ul>" in html and "<li>" in html
    assert '<a href="https://example.org/x">the ticket</a>' in html
    # Every attribute this page uses to style itself is stripped: the
    # target applies its own, and `class="okt-card"` there is text that
    # looks pasted in and follows no theme at all.
    for leak in ("class=", "style=", "id=", "okt-", "okucopy-", "okt-copy-ins"):
        assert leak not in html, f"{leak!r} survived into the clipboard: {html}"


def test_a_copy_reports_whether_it_worked(opened):
    """The failure is silent by construction — the clipboard is not
    visible — so the button has to say something."""
    btn = _button(opened, 0, "plain").last
    btn.click()
    opened.wait_for_timeout(150)
    assert "is-copied" in (btn.get_attribute("class") or "")
    # And it goes back, or the next copy has no signal left to give.
    opened.wait_for_timeout(1500)
    assert "is-copied" not in (btn.get_attribute("class") or "")


def test_the_buttons_are_large_enough_to_hit(opened):
    """24px is the floor for a pointer target. At three pixels of
    vertical padding they measured 22 — the size a control ends up when
    it is styled as a label that happens to be clickable."""
    boxes = opened.evaluate(
        """() => [...document.querySelectorAll('.okt-copy-btn')].map(b => {
             const r = b.getBoundingClientRect();
             return [Math.round(r.width), Math.round(r.height)];
           })"""
    )
    assert boxes, "no copy buttons rendered"
    assert all(w >= 24 and h >= 24 for w, h in boxes), boxes


def test_grey_means_one_thing_inside_the_card(opened):
    """The recessed surface marks the half being replaced. A head band
    sharing it made the card read as three stripes of ambiguous rank
    instead of a caption over a pair."""
    got = opened.evaluate(
        """() => {
             const r = document.querySelector('.okt-copy');
             const bg = s => getComputedStyle(r.querySelector(s)).backgroundColor;
             return { card: getComputedStyle(r).backgroundColor,
                      head: bg('.okt-copy-head'),
                      was: bg('.okt-copy-was'),
                      now: bg('.okt-copy-now') };
           }"""
    )
    transparent = ("rgba(0, 0, 0, 0)", "transparent")
    assert got["head"] in transparent or got["head"] == got["card"], got
    assert got["now"] in transparent or got["now"] == got["card"], got
    assert got["was"] not in transparent and got["was"] != got["card"], got
