"""A sub-language inside a code block survives the line splitter.

Prism highlights nested languages on its own: its markdown grammar wraps
a fenced block in one `token code` spanning every line and puts a `token
code-block language-bash` inside it, and its markup grammar hands
`<script>` and `<style>` bodies to JavaScript and CSS. None of that
needed building.

What needed fixing is that the kit threw it away. The line splitter —
the pass that groups a block into one `.okt-code-line` per source line
so a line can be folded and numbered — handled an element straddling a
newline by cloning it per line and assigning `textContent`, which
flattens every descendant. Its comment called nested tokens across
newlines "very rare"; a fenced code block inside a markdown sample is
exactly that shape and this repo's own documentation is full of them.

Measured on a markdown sample holding a bash fence. Prism alone:

    <span class="token code-block language-bash">
      <span class="token builtin class-name">cd</span> /tmp
      <span class="token operator">&amp;&amp;</span> …

What reached the reader: three bare `token code` spans, no language, no
bash tokens. So it read as a missing feature and was a deletion.

The splitter is recursive now: it opens a shallow clone, walks the
children, and closes and reopens the whole open stack at each line
break, so nesting survives to any depth.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import highlighted, page_quiet

pytestmark = pytest.mark.browser

BASH = "cd /tmp && ls -la | grep foo"
JS = 'const el = document.getElementById("app");'

PAGE_MD = """---
title: Nested
summary: A sub-language inside a fenced block.
---

## HTML holding JS and CSS {#html}

```html
<div id="app"></div>
<script>
  %s
  el.textContent = "hi";
</script>
<style>
  #app { color: red; font-weight: 700; }
</style>
```

## Markdown holding bash {#md}

````markdown
Run it:

```bash
%s
```

Then read the notes.
````

## Markdown holding a fence Prism can never load {#refused}

````markdown
```oku-chart
{"type":"bar","rows":[{"label":"a","value":1}]}
```
````
""" % (JS, BASH)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("nested") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Nested"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        # Vendored, because the grammars have to be reachable: a page
        # that cannot fetch `prism-bash` has nothing to nest.
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def opened(built, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    highlighted(page, "section#md pre code")
    yield page
    page.close()


def _nested(page, section: str):
    return page.evaluate(
        """(sel) => {
             const code = document.querySelector(sel + ' pre code');
             return [...code.querySelectorAll('[class*="language-"]')]
               .filter((e) => e.tagName !== 'CODE')
               .map((e) => ({
                 lang: (e.className.match(/language-([\\w-]+)/) || [])[1],
                 tokens: e.querySelectorAll('.token').length,
                 text: e.textContent,
               }));
           }""",
        f"section#{section}",
    )


def test_a_bash_fence_inside_a_markdown_sample_is_bash(opened):
    """The reported half, and the one that was fully dead: no language
    span at all reached the page, so nothing downstream could colour it.

    The token COUNT is asserted, not merely the class. A `language-bash`
    span with nothing inside it is what a stripped clone would leave if
    the class survived and the children did not — which is the failure
    one door along from the one being fixed.
    """
    got = [n for n in _nested(opened, "md") if n["lang"] == "bash"]
    assert got, f"no bash inside the markdown sample: {_nested(opened, 'md')}"
    assert sum(n["tokens"] for n in got) >= 4, got
    assert BASH in "".join(n["text"] for n in got), got


def test_a_script_and_a_style_inside_html_keep_their_own_tokens(opened):
    """The half that appeared to work. It did — but only because the
    kit's nested pass was re-highlighting `.token.script` by hand after
    the splitter had flattened Prism's own `language-javascript` span.
    Both are asserted so a change that breaks one shows up as one."""
    got = _nested(opened, "html")
    langs = {n["lang"] for n in got}
    assert {"javascript", "css"} <= langs, got
    assert sum(n["tokens"] for n in got if n["lang"] == "javascript") >= 4, got
    assert sum(n["tokens"] for n in got if n["lang"] == "css") >= 4, got


@pytest.mark.parametrize("section", ["html", "md"])
def test_the_block_still_reads_as_its_own_source(opened, section):
    """The splitter's own contract, and the thing a recursive rewrite is
    most likely to break: the visible text has to be the program, exactly
    once, with its line breaks. The copy button reads this block, so a
    duplicated or dropped clone ships as a corrupted paste rather than as
    a rendering fault anyone would see."""
    got = opened.evaluate(
        """(sel) => {
             const code = document.querySelector(sel + ' pre code');
             const lines = [...code.querySelectorAll('.okt-code-line')];
             return {
               text: code.textContent,
               lineCount: lines.length,
               fromLines: lines.map((l) => l.querySelector('.okt-code-content').textContent).join(''),
             };
           }""",
        f"section#{section}",
    )
    needle = JS if section == "html" else BASH
    assert got["text"].count(needle) == 1, got["text"]
    # Every character is inside exactly one line wrapper — nothing was
    # emitted outside the structure the fold and number passes walk.
    assert got["fromLines"] == got["text"], (got["fromLines"], got["text"])
    assert got["lineCount"] == len(got["text"].split("\n")), got["lineCount"]


@pytest.mark.parametrize("section", ["html", "md"])
def test_every_line_is_numbered_once_and_in_order(opened, section):
    """The gutter is what the splitter exists for. A recursive walk that
    opened a line without closing it would show up here as a gap or a
    repeat, long before anyone noticed a colour was wrong."""
    got = opened.evaluate(
        """(sel) => [...document.querySelectorAll(sel + ' pre code .okt-code-line')]
             .map((l) => +l.getAttribute('data-line'))""",
        f"section#{section}",
    )
    assert got == list(range(1, len(got) + 1)), got


def test_no_empty_token_span_is_left_behind(opened):
    """A break landing on an element's own edge would reopen a clone with
    nothing in it. Harmless to look at and not harmless to walk: the fold
    pass and the copy path both traverse this tree."""
    empty = opened.evaluate(
        """() => [...document.querySelectorAll('pre code .token')]
             .filter((t) => !t.childNodes.length)
             .map((t) => t.className)"""
    )
    assert empty == [], empty


def test_no_shard_carries_prisms_own_handle(opened):
    """The defect the recursion introduced, and the reason the splitter
    strips `id` from every clone it makes.

    Prism's markdown grammar stamps `md-<time>-<rand>` on a `code-block`
    span whose language the autoloader has not loaded, so the callback it
    queues can find that element again. The splitter clones that span
    once per line — so the attribute lands on every line of the block at
    once, and `getElementById` answers with whichever one it reaches
    first. Before the flattening was fixed the span did not survive at
    all, which is why nothing had ever seen it.

    Measured where it showed up: the markdown viewer, rendering this
    repo's own reference page, carried `md-1788708479926-…` on a
    `token code-block language-oku-chart`. Ids are document-global, so an
    unprefixed one there can shadow the host page's — which is the defect
    the viewer's `okv-` prefix exists for, and Prism assigns these after
    that pass has run.

    The `#refused` section is the trigger, and the two conditions Prism
    branches on are asserted rather than assumed: a `code-block` span
    naming a language, and that language absent from `Prism.languages`.
    Without both, this test passes on a page that never reaches the
    branch.
    """
    got = opened.evaluate("""() => ({
      ids: [...document.querySelectorAll('pre code [id]')].map((e) => e.id),
      refusedBlocks: document.querySelectorAll(
        "section#refused pre code [class*='code-block'][class*='language-oku-chart']").length,
      grammarLoaded: !!(window.Prism && window.Prism.languages
        && window.Prism.languages['oku-chart']),
    })""")
    assert got["refusedBlocks"] >= 1, f"the trigger is not on the page: {got}"
    assert not got["grammarLoaded"], f"the grammar loaded, so Prism never stamps an id: {got}"
    assert got["ids"] == [], got
