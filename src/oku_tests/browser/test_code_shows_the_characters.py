"""A code block shows the characters that are in the code.

JetBrains Mono ligates `!=` into `≠`, `->` into `→`, `>=` into `≥`.
That is a good default in an editor, where the author knows what they
typed, and the wrong one in a document about code, which a reader
retypes from what they see — `≠` is not an operator in any language the
kit highlights, and the copy button hands over the real text, so the
page said one thing and the clipboard held another.

Measured on two delivered documents before the fix: a Kotlin guide
drawing 118 `->`, 14 `!=`, 12 `?:`, 6 `>=` and 3 `===`, and an Iceberg
guide drawing 36 `->` and 3 `=>`.

The assertion is at the pixel level, because the ligature is invisible
to every cheaper one: JetBrains Mono is monospaced and its ligatures
keep the advance, so the box is the same width either way, and
`textContent` never changed. The first case is what keeps this honest —
it renders the same span with ligatures forced ON and requires the two
drawings to DIFFER. Without it the whole file would pass on a machine
with no JetBrains Mono, asserting nothing.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

# Every sequence JetBrains Mono ligates that a reader could retype
# wrongly, in the languages this kit's own documents are written about.
LIGATING = "fun f(a: Int?): Boolean = a != null && a >= 0 && a === b || x ->  y => z ?: w"

PAGE_MD = f"""---
title: Operators
summary: A code block whose operators must read as themselves.
---

## Code {{#code}}

```kotlin
{LIGATING}
```

Inline too: `a != b` and `x -> y`.
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("ligatures") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Operators"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture()
def page(built, browser):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    # The vendored face has to be the one drawing, or there is no
    # ligature to switch off and nothing here means anything. The
    # first test asserts that outcome directly; this names the cause
    # when it fails.
    assert "JetBrains Mono" in page.evaluate(
        "() => getComputedStyle(document.querySelector('pre code')).fontFamily"
    )
    yield page
    context.close()


def _shot(page, sel: str, css: str | None) -> bytes:
    el = page.query_selector(sel)
    page.evaluate(
        "([sel, css]) => { const e = document.querySelector(sel);"
        " e.style.cssText = css === null ? '' : css; }",
        [sel, css],
    )
    el.scroll_into_view_if_needed()
    return el.screenshot()


SEL = "pre code"


def test_the_ligature_would_form_here(page):
    """Not vacuous: with contextual alternates forced on, the same span
    is drawn differently. A machine without the face fails this first."""
    plain = _shot(page, SEL, "font-variant-ligatures: none; font-feature-settings: 'zero'")
    ligated = _shot(page, SEL, "font-variant-ligatures: contextual; font-feature-settings: 'calt', 'zero'")
    assert plain != ligated, "the font draws `!=` and `->` the same either way — nothing to assert"


def test_the_delivered_page_draws_the_characters(page):
    """What the kit ships equals the ligature-free drawing, pixel for
    pixel, and differs from the ligated one."""
    as_delivered = _shot(page, SEL, None)
    plain = _shot(page, SEL, "font-variant-ligatures: none; font-feature-settings: 'zero'")
    ligated = _shot(page, SEL, "font-variant-ligatures: contextual; font-feature-settings: 'calt', 'zero'")
    assert as_delivered == plain
    assert as_delivered != ligated


def test_both_switches_are_set(page):
    """Two switches over one feature: a bare `font-feature-settings:
    'zero'` leaves `calt` at its default on, and `font-variant-ligatures:
    none` alone loses to an explicit `'calt'` in feature settings."""
    got = page.evaluate(
        "() => { const cs = getComputedStyle(document.querySelector('pre code'));"
        " return [cs.fontVariantLigatures, cs.fontFeatureSettings]; }"
    )
    assert got[0] == "none"
    assert "calt" not in got[1]
    # The slashed zero survives: it distinguishes 0 from O without
    # changing which character is on the page.
    assert "zero" in got[1]


def test_an_inline_code_span_follows(page):
    """`code` and `pre` take the same rule, so a paragraph naming an
    operator does not disagree with the block below it."""
    got = page.evaluate(
        "() => { const cs = getComputedStyle(document.querySelector('p code'));"
        " return [cs.fontVariantLigatures, cs.fontFeatureSettings]; }"
    )
    assert got[0] == "none" and "calt" not in got[1]


def test_the_text_itself_is_unchanged(page):
    """The characters were always right in the DOM — which is why no
    text assertion could have caught this, and why the copy button was
    handing over something the page did not show."""
    assert "!=" in page.evaluate("() => document.querySelector('pre code').textContent")
    assert "->" in page.evaluate("() => document.querySelector('pre code').textContent")
