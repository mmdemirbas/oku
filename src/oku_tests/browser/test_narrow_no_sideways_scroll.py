"""One long word must not make the whole page scroll sideways.

A `1fr` grid track carries `min-width: auto`, so it refuses to shrink
below its content's longest unbreakable run. Put a class name in inline
code inside a step-flow — `BatchDataScanGroupReader`, which is ordinary
prose in a document about a codebase — and at 360px the track sizes
itself to that word, the card overflows its own border, and the page
gains a horizontal scrollbar. Found by `oku verify` on a delivered tree,
not by a reader, which is the point of running the gate on both.

Fifteen templates in chrome.css used a bare `1fr`. They take
`minmax(0, 1fr)` now, so a column may be narrower than its longest word
and the word wraps instead. The assertion is the page-level one —
document.scrollWidth against innerWidth — because that is what a reader
feels, and it holds no matter which primitive is at fault.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

# One long unbreakable token, in every primitive that lays out a grid.
LONG = "BatchDataScanGroupReaderDeduplicateMergeFunctionFactory"

PAGE_MD = f"""---
title: Narrow
summary: Long tokens in every grid the kit lays out.
---

> [!TLDR]
> A `{LONG}` in a callout.

## Step flow {{#steps}}

```oku-step-flow
{{"steps":[{{"t":"Read `{LONG}`","b":"It calls `{LONG}` first, hardcoded."}},
{{"t":"Then merge","b":"`{LONG}` merges the runs."}}]}}
```

## Comparison {{#compare}}

```oku-compare-grid
{{"cards":[{{"t":"`{LONG}`","body":"left"}},{{"t":"Other","body":"`{LONG}` on the right"}}]}}
```

## Numbers {{#kpi}}

```oku-kpi-grid
{{"tiles":[{{"num":"12","label":"`{LONG}`"}},{{"num":"3","label":"rows"}}]}}
```

## Table {{#table}}

```oku-table
{{"headers":["name","note"],"rows":[["`{LONG}`","long"],["`{LONG}`","also long"]]}}
```

## Prose {{#prose}}

A paragraph mentioning `{LONG}` in the middle of a sentence, and a table:

| name | note |
|---|---|
| `{LONG}` | long |
"""


@pytest.fixture(scope="module")
def narrow_page(tmp_path_factory):
    docs = tmp_path_factory.mktemp("narrow") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Narrow"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return docs / "dist" / "standalone" / "page.html"


OVERFLOW = """() => {
  const scrolls = e => {
    for (let p = e.parentElement; p; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll') return true;
    }
    return false;
  };
  const out = [];
  document.querySelectorAll('main *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width > 0 && r.right > window.innerWidth + 1 && !scrolls(e)) {
      const cls = (typeof e.className === 'string' ? e.className : '').split(/\\s+/)[0];
      out.push(e.tagName.toLowerCase() + (cls ? '.' + cls : '') + ' →' + Math.round(r.right));
    }
  });
  return {
    docWidth: document.documentElement.scrollWidth,
    inner: window.innerWidth,
    over: out.slice(0, 6),
  };
}"""


@pytest.mark.parametrize("width", [360, 320])
def test_a_long_token_does_not_widen_the_page(page, narrow_page, width):
    page.set_viewport_size({"width": width, "height": 800})
    page.goto(narrow_page.as_uri(), wait_until="load")
    page.wait_for_timeout(2000)
    got = page.evaluate(OVERFLOW)

    assert got["docWidth"] <= got["inner"] + 1, (
        f"the page scrolls sideways at {width}px ({got['docWidth']} vs {got['inner']}): {got['over']}"
    )


def test_nothing_escapes_its_column_at_360(page, narrow_page):
    """The page-level check above can be satisfied by a stray clip. This
    one names the element, which is what an author needs to fix it."""
    page.set_viewport_size({"width": 360, "height": 800})
    page.goto(narrow_page.as_uri(), wait_until="load")
    page.wait_for_timeout(2000)
    got = page.evaluate(OVERFLOW)

    assert got["over"] == [], f"elements outside the viewport with no scroller: {got['over']}"
