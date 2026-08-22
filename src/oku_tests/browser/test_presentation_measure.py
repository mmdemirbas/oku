"""One column, one right edge.

Every block in a section — paragraph, list, blockquote, callout, the
TL;DR panel, a code block, a diagram — ends at the same x. That is the
whole rule, and it is the one a reader can see without being told.

It was broken by trying to make paragraphs easier to read. Body prose
runs long at the comfortable width — a 77-83 character median when the
cap was proposed — so `--prose-width` was applied to running prose. It
worked on the paragraph and failed on the page: the text stopped
~200px short of the cover, the code blocks and the diagrams above and
below it. Reported twice, the second time with arrows drawn on the
screenshot — "the text is still narrower than the other elements."

So the measure belongs to `--content-width`, and the reader shortens it
with the width toggle, which moves every block together.
`--prose-width` stays declared and unapplied for a caller that wants a
per-block cap; the kit does not use it.

The tests below are the guard against reopening this a third time.
"""

from __future__ import annotations

from ._wait import page_quiet

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
title: One column
summary: Every block in a section ends at the same x.
---

> [!TLDR]
> {PARA}

## Prose and its frames {{#prose}}

{PARA} {PARA} {PARA}

> [!IMPORTANT]
> {PARA}

- {PARA}

> {PARA}

```python
value = "a line of code that is not especially long"
```

```mermaid
flowchart LR
  A[write] --> B[compact]
  B --> C[read]
```

{PARA}
"""


@pytest.fixture(scope="module")
def measure_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("measure")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.md", "title": "One column", "parent": None}],
    }
    (d / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("One column", inline_manifest=manifest), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def rendered(measure_url, browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{measure_url}/page.html")
    page_quiet(page)
    yield page
    page.close()


# Every direct child of a section, labelled by what it is, with its
# right edge. A blockquote carries a left rule and its own inset, so it
# is measured on the outer box like everything else.
EDGES = """() => {
  const out = [];
  for (const el of document.querySelector('#prose').children) {
    const r = el.getBoundingClientRect();
    if (r.width < 1) continue;
    out.push({ tag: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
               right: Math.round(r.right), width: Math.round(r.width) });
  }
  return out;
}"""


def test_every_block_in_a_section_ends_at_the_same_x(rendered):
    """The reported defect, stated as a number. Before: paragraphs at
    870, callout at 951, code and diagram at 1356."""
    blocks = rendered.evaluate(EDGES)
    assert len(blocks) >= 6, f"the fixture did not render enough block kinds: {blocks}"
    edges = {b["right"] for b in blocks}
    assert max(edges) - min(edges) <= 1, "blocks in one section end at different x: " + ", ".join(
        f"{b['tag']}@{b['right']}" for b in blocks
    )


def test_the_tldr_panel_ends_where_the_section_does(rendered):
    """It is the block the report pointed at, and it sits outside the
    section, so the rule above does not cover it."""
    got = rendered.evaluate(
        """() => {
        const r = s => { const e = document.querySelector(s);
                         return e ? Math.round(e.getBoundingClientRect().right) : null; };
        return { tldr: r('.tldr'), cover: r('header.cover'), para: r('main > section > p') };
    }"""
    )
    assert got["tldr"] and got["cover"] and got["para"], got
    assert abs(got["tldr"] - got["para"]) <= 1, got
    assert abs(got["tldr"] - got["cover"]) <= 1, got


@pytest.mark.parametrize("mode", ["narrow", "comfortable", "max"])
def test_one_edge_holds_at_every_width(rendered, mode):
    """The width toggle moves the column. It must not open a gap
    between the block kinds inside it."""
    rendered.evaluate("(m) => document.body.setAttribute('data-content-width', m)", mode)
    rendered.wait_for_timeout(200)
    blocks = rendered.evaluate(EDGES)
    rendered.evaluate("() => document.body.setAttribute('data-content-width', 'comfortable')")
    edges = {b["right"] for b in blocks}
    assert max(edges) - min(edges) <= 1, f"{mode}: " + ", ".join(f"{b['tag']}@{b['right']}" for b in blocks)


def test_nothing_applies_the_prose_cap(rendered):
    """`--prose-width` stays declared for a caller that wants it. The
    moment the kit applies it to a block, the edges diverge again — so
    assert the computed max-width rather than trusting the stylesheet
    to have stayed the way it reads."""
    got = rendered.evaluate(
        """() => {
        const m = s => { const e = document.querySelector(s);
                         return e ? getComputedStyle(e).maxWidth : null; };
        return { declared: getComputedStyle(document.body).getPropertyValue('--prose-width').trim(),
                 para: m('main > section > p'), callout: m('.callout'), tldr: m('.tldr'),
                 list: m('main > section > ul'), quote: m('main > section > blockquote') };
    }"""
    )
    assert got["declared"], "--prose-width was deleted; it is kept for callers that want a cap"
    for key in ("para", "callout", "tldr", "list", "quote"):
        assert got[key] == "none", f"{key} is capped at {got[key]} — the edges will diverge"


def test_the_width_toggle_still_moves_the_measure(rendered):
    """Removing the cap does not remove the reader's control over line
    length; it moves it to the toggle, which acts on the whole column,
    so the edges stay aligned at every setting.

    Width is the assertion, not characters-per-line. Both estimators
    available in headless are unreliable here: `text.length / lines` is
    inflated by the partial last line, and canvas `measureText` falls
    back to a different font than the one the paragraph renders in —
    they disagreed by 20% on the same paragraph. Width is exact and
    proves the same thing."""
    seen = {}
    for mode in ("narrow", "comfortable", "max"):
        rendered.evaluate("(m) => document.body.setAttribute('data-content-width', m)", mode)
        rendered.wait_for_timeout(200)
        seen[mode] = rendered.evaluate(
            """() => {
            const p = document.querySelector('main > section > p');
            const lh = parseFloat(getComputedStyle(p).lineHeight);
            return { width: Math.round(p.getBoundingClientRect().width),
                     lines: Math.round(p.getBoundingClientRect().height / lh) };
        }"""
        )
    rendered.evaluate("() => document.body.setAttribute('data-content-width', 'comfortable')")
    assert seen["narrow"]["width"] < seen["comfortable"]["width"] < seen["max"]["width"], seen
    # More lines for the same text is the same statement, arrived at
    # independently of the width: narrow really does wrap sooner.
    assert seen["narrow"]["lines"] > seen["max"]["lines"], seen
