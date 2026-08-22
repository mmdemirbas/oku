"""An HTML island keeps the content written inside it.

CommonMark ends an HTML *block* at the first blank line. It does not
close the *element* — the `</div>` has not arrived yet, so everything
between belongs inside it, and that is exactly what a browser does with
the stream GitHub emits. The kit rendered each block as its own
fragment, which auto-closed the element, so the rest of the island
landed on the page as a sibling: an island holding an 82-line block
rendered with 403 characters in it and everything else outside, styled
as though it had never been part of the island. `oku check --strict`
was clean, and the page had been delivered twice.

The blank line is load-bearing, not an author's slip. It is what makes
markdown inside an island render as markdown — `<div>` / blank /
`**bold**` / blank / `</div>` is the idiom GitHub documents. So the fix
is not to swallow the blank line into a raw block: it is to keep the
element open and put what follows inside it, markdown-processed.

The code case is the same defect wearing different clothes. A `<pre>`
at column 0 already consumes to its `</pre>` whatever blank lines are
in between; it is a `<pre>` *nested in a `<div>`* that got cut, and the
only spelling left was `<br>` — which renders as three lines and copies
as one, because a `<br>` carries no newline character.
"""

from __future__ import annotations

from ._wait import page_quiet

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

PAGE_MD = """---
title: Islands
summary: Islands with blank lines in them.
---

## Two paragraphs {#two}

<div id="island-a" class="okt-card">
<p>first paragraph</p>

<p>second paragraph</p>
</div>

## Markdown inside {#md}

<div id="island-b" class="okt-card">

A paragraph with **bold** in it.

- one
- two

</div>

## Code inside {#code}

<div id="island-c" class="okt-card">
<p>before</p>

<pre><code>line one

line three</code></pre>

</div>

## Nesting {#nest}

<div id="island-d" class="okt-card">
<div id="island-d-inner">

inner text

</div>

outer text
</div>

## After {#after}

A paragraph that belongs to the page, not to any island.
"""


@pytest.fixture(scope="module")
def island_page(tmp_path_factory):
    docs = tmp_path_factory.mktemp("islands") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Islands"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def opened(island_page, browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(island_page.as_uri(), wait_until="load")
    page_quiet(page)
    yield page
    page.close()


def _texts(page, sel):
    return page.eval_on_selector_all(sel, "els => els.map(e => e.innerText.trim())")


def test_a_blank_line_does_not_end_the_island(opened):
    """The reported symptom, at its smallest: two paragraphs, one gap."""
    inside = _texts(opened, "#island-a > p")
    assert inside == ["first paragraph", "second paragraph"], inside


def test_nothing_the_island_holds_escapes_onto_the_page(opened):
    """The other half — the dropped content did not vanish, it became
    page content beside the island, which is why it looked deliberate."""
    stray = opened.eval_on_selector_all(
        "section#two > *",
        "els => els.filter(e => e.id !== 'island-a' && e.tagName !== 'H2')"
        ".map(e => e.tagName + ':' + e.innerText.trim().slice(0, 40))",
    )
    assert stray == [], f"content escaped the island onto the page: {stray}"


def test_markdown_after_the_blank_line_is_still_markdown(opened):
    """The blank line is what lets an author write markdown inside an
    island. Keeping the element open must not turn its body into raw
    text — `**bold**` is a `<strong>`, and the list is a `<ul>`."""
    assert opened.locator("#island-b strong").inner_text() == "bold"
    assert _texts(opened, "#island-b ul li") == ["one", "two"]
    assert "**bold**" not in opened.locator("#island-b").inner_text()


def test_code_in_an_island_keeps_its_newlines(opened):
    """`<br>` renders three lines and copies as one; a real `<pre>` does
    both. The nested `<pre>` must survive the blank line inside it."""
    code = opened.locator("#island-c pre code")
    text = code.evaluate("el => el.textContent")
    assert text.count("\n") == 2, f"newlines lost: {text!r}"
    assert text.startswith("line one"), text
    assert opened.locator("#island-c pre code br").count() == 0


def test_a_nested_island_closes_at_its_own_tag(opened):
    """The inner `</div>` must pop one level, not all of them: `outer
    text` belongs to the outer island and not to the inner one."""
    assert "inner text" in opened.locator("#island-d-inner").inner_text()
    assert "outer text" not in opened.locator("#island-d-inner").inner_text()
    assert "outer text" in opened.locator("#island-d").inner_text()


def test_the_island_does_not_swallow_the_rest_of_the_page(opened):
    """A stack that never pops is the failure this fix could introduce:
    every later section inside the last div."""
    assert opened.locator("#island-d section").count() == 0
    after = opened.locator("section#after p").inner_text()
    assert after.startswith("A paragraph that belongs to the page")


def test_the_copy_control_reaches_code_inside_an_island(opened):
    """The other half of the code case. Rendering three lines is no use
    if the clipboard gets one — the `<br>` spelling did exactly that,
    and a reader pasted a whole SQL block into another system as a
    single line. A real `<pre>` gets the kit's copy button and the
    button reads the newlines that are actually there."""
    btn = opened.locator("#island-c .copy-btn")
    assert btn.count() == 1, "no copy control on a <pre> inside an island"
    copied = opened.evaluate(
        """() => {
             const pre = document.querySelector('#island-c pre');
             return pre.querySelector('code').textContent;
           }"""
    )
    assert copied.count("\n") == 2, repr(copied)
