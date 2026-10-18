"""A code block's language label stays in the block's corner.

The label was an absolutely positioned child of the `<pre>`, and the
`<pre>` is a scroll container: an absolute child of a scroller scrolls
with its content. A block that does not wrap — the author's
`okt-nowrap`, which is what a long command or a wide table in a code
block is written with — scrolled sideways took the label off its left
edge with the first column. The copy and wrap buttons had the same
defect once and live on `.okt-pre-host` for exactly this reason; the
label now lives there with them.

The host has no border and the `<pre>` has one, so the label is placed
inside the border — the corner it always sat in — and a code file in
the viewer, whose `<pre>` draws no border, puts it on the edge.

A page in one language dims its labels. That sweep ran at 0, 200 and
600 ms after render, and labels are stamped after Prism finishes or its
fallback timer fires — measured at 5.5 s with Prism from the CDN, which
is how this module builds — so the page never dimmed. It sweeps when a
label is stamped now.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import measured, page_quiet, until

pytestmark = pytest.mark.browser

LONG = "print(" + ", ".join(f"'column {i}'" for i in range(40)) + ")"

PAGE_MD = f"""---
title: Code
summary: The language label stays in its block's corner.
---

## Fenced {{#fenced}}

```python
def f():
    return 1
```

## Unwrapped {{#unwrapped}}

<pre class="okt-nowrap"><code class="language-python">{LONG}
{LONG}
</code></pre>

## File {{#file}}

The file: [`long.py`](#f/../src/long.py).
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("code-label") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "long.py").write_text("\n".join([LONG] * 30) + "\n", encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(params=[1280, 360])
def page(request, built, browser):
    context = browser.new_context(viewport={"width": request.param, "height": 800})
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    until(page, "() => document.querySelectorAll('.okt-code-lang').length >= 2", what="both labels drawn")
    yield page
    context.close()


# Where the label sits against its block's padding box, and how far the
# block has scrolled. `pre` is the block the label belongs to.
CORNER = """(pre) => {
  const host = pre.parentElement;
  const pill = host.querySelector(':scope > .okt-code-lang') || pre.querySelector(':scope > .okt-code-lang');
  if (!pill) return null;
  const p = pre.getBoundingClientRect(), l = pill.getBoundingClientRect();
  return { dx: l.left - (p.left + pre.clientLeft), dy: l.top - (p.top + pre.clientTop),
           inside: l.right <= p.right + 0.5 && l.left >= p.left - 0.5,
           scrolled: pre.scrollLeft, room: pre.scrollWidth - pre.clientWidth, text: pill.textContent };
}"""


def _block(anchor: str) -> str:
    return f"document.getElementById({anchor!r}).closest('section').querySelector('pre')"


def test_the_label_sits_in_the_corner_of_a_wrapped_block(page):
    got = measured(page, f"() => ({CORNER})({_block('fenced')})")
    assert got and got["text"] == "python", got
    assert abs(got["dx"]) <= 0.5 and abs(got["dy"]) <= 0.5, (
        f"label {got['dx']:.1f},{got['dy']:.1f} off the corner"
    )


def test_the_label_stays_when_an_unwrapped_block_is_scrolled_sideways(page):
    got = measured(
        page,
        f"""() => {{ const pre = {_block("unwrapped")}; pre.scrollIntoView({{ block: 'center' }});
          pre.scrollLeft = 400; return ({CORNER})(pre); }}""",
    )
    assert got and got["text"] == "python", got
    # Without room to scroll the case asserts nothing.
    assert got["room"] > 400 and got["scrolled"] == 400, f"the block did not scroll: {got}"
    assert abs(got["dx"]) <= 0.5 and abs(got["dy"]) <= 0.5, (
        f"scrolled 400px, the label moved {got['dx']:.1f}px off the corner"
    )
    assert got["inside"], "the label left its block"


def test_the_label_is_not_part_of_the_code(page):
    """Inside the `<pre>` the label's word was in its text, which is
    what a hand selection of the whole block and a screen reader read."""
    text = measured(page, f"() => {_block('fenced')}.textContent")
    assert "python" not in text, text


def test_a_single_language_page_dims_the_label_and_hover_shows_it(page):
    pre = page.locator("#fenced").locator("xpath=ancestor-or-self::section").locator("pre").first
    pre.scroll_into_view_if_needed()
    page.mouse.move(2, 2)
    until(
        page,
        "() => document.documentElement.hasAttribute('data-okt-single-lang')",
        what="single-language page",
    )
    opacity = """() => +getComputedStyle(document.getElementById('fenced').closest('section').querySelector('.okt-code-lang')).opacity"""
    until(page, f"() => ({opacity})() < 0.3", what="the label dimmed at rest")
    pre.hover()
    until(page, f"() => ({opacity})() > 0.99", what="the label shown on hover")


def test_a_code_file_in_the_viewer_has_its_label_on_the_edge(page):
    """The viewer's code view draws its block without a border, so the
    label's corner is the edge itself."""
    page.locator("main .okt-fp .okt-fp-label", has_text="long.py").first.click()
    until(page, "() => !!document.querySelector('.okt-mdview pre .okt-code-line')", what="the file opened")
    got = measured(page, f"() => ({CORNER})(document.querySelector('.okt-mdview pre'))")
    assert got and got["text"] == "python", got
    assert abs(got["dx"]) <= 0.5 and abs(got["dy"]) <= 0.5, (
        f"label {got['dx']:.1f},{got['dy']:.1f} off the corner"
    )
