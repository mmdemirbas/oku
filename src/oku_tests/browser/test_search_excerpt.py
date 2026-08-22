"""The search excerpt marks the word that matched, not the one beside it.

`String.prototype.toLowerCase()` is not length-preserving. A Turkish `İ`
lowercases to `i` plus a combining dot, so a section holding one is a
character longer in lowercase than in the text, and every index past it
is off by one. The in-page search found the query in the lowered copy
and then sliced the ORIGINAL with that index — so the excerpt window
drifted one position per `İ` before the match, and the second search
that placed `<mark>` drifted with it or missed entirely.

Nothing about it looks broken from an English page, which is why it
lasted: the drift is exactly zero until a character whose lowercase is
longer than itself appears earlier in the same section. It shows up on
the pages whose author writes Turkish.

The fix maps both ends of the match back to the source before anything
is sliced, and computes the mark's offset inside the excerpt instead of
searching for it a second time.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet, until

pytestmark = pytest.mark.browser

NEEDLE = "kayıt"

# `İ` appears twice INSIDE the 40 characters that precede the needle and
# three times before them. The first three drift the excerpt window, the
# last two drift the mark inside it — the two halves of the same defect,
# and one text exercises both.
PAGE_MD = f"""---
title: Arama
summary: A section whose text lowercases longer than it is.
---

## Ölçüm {{#olcum}}

İstanbul ve İzmir arasında bir karşılaştırma yapıldı. İlk turda ölçüm
sonucu iyi bir eşikte kaldı ve İŞLEM sırasında her biri için bir {NEEDLE}
tutuldu, böylece sonradan hangi adımın ne kadar sürdüğü sayılabildi.

## Baseline {{#baseline}}

An English section, where lowercasing changes nothing, holding the same
word {NEEDLE} so both paths are measured on one page.
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("search") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Arama"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        # No search index, which is what puts the reader on the in-page
        # fallback this file is about.
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def marks(browser, built) -> list:
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    try:
        page.goto(built.as_uri(), wait_until="load")
        page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        page_quiet(page)
        page.keyboard.press("Control+k")
        # Focus, not presence: the modal is in the DOM before the input
        # takes the caret, and keystrokes sent in between go nowhere.
        until(
            page,
            "() => document.activeElement === document.querySelector('.search-input')",
            what="the search box has the caret",
        )
        page.keyboard.type(NEEDLE)
        until(
            page,
            "() => document.querySelectorAll('.search-results mark').length > 0",
            what="a marked result",
        )
        return page.evaluate(
            """() => [...document.querySelectorAll('.search-results mark')].map(m => {
                 const box = m.closest('.search-result-excerpt') || m;
                 const all = box.textContent;
                 return {
                   mark: m.textContent,
                   around: all,
                   before: all.slice(0, all.indexOf(m.textContent)),
                 };
               })"""
        )
    finally:
        page.close()


def test_both_sections_matched(marks) -> None:
    """The assertions below are about what the marks say, so this one
    says there are two — one from the section that lowercases longer and
    one from the section that does not."""
    assert len(marks) >= 2, marks


def test_every_mark_is_the_word_that_was_searched(marks) -> None:
    wrong = [m["mark"] for m in marks if m["mark"].lower() != NEEDLE]
    assert wrong == [], f"marked {wrong}, searched {NEEDLE!r}"


def test_every_excerpt_contains_the_word(marks) -> None:
    missing = [m["around"][:80] for m in marks if NEEDLE not in m["around"].lower()]
    assert missing == [], missing


def test_the_window_opens_forty_characters_before_the_match(marks) -> None:
    """The window is `start = match - 40`, so the text between the lead
    ellipsis and the mark is exactly 40 characters whenever the match is
    that far into the section. It is the drift itself, stated as a
    number: one character short per expanding character before the
    match, which is invisible to any assertion about what the excerpt
    contains."""
    leads = [m["before"] for m in marks if m["before"].startswith("… ")]
    assert leads, [m["before"][:40] for m in marks]
    for lead in leads:
        assert len(lead) - 2 == 40, f"{len(lead) - 2} characters of lead, not 40: {lead!r}"
