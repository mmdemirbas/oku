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

The chip rack was the same shape one track over: `max-content` on the
label column sized the whole rack from the longest column NAME, which is
prose an author writes. `B: open-source Spark 3.5.4 + open-source
Iceberg 1.10.0` measured 381px against a 360px viewport, and `oku verify`
found it on a delivered tree. Below 560px the rack stacks — label above
its own chips — because side by side leaves neither enough room.

The page above is hand-written, so it covers the primitives someone
thought of. The second one is derived: every example in
`kit/schema/examples.json` with the long token appended to every string
it carries, which reaches the primitives nobody reported. Five more had
the same defect — the KPI numeral (an inline-block sizes to max-content,
and a value like `1.2M req/s` is not a bare numeral), the annotated-code
annotation, the timeline title and chip, and the live-snippet header.
The KPI tile put the page's scrollWidth at 1818 against a 1440px
viewport, which is why the derived page is measured at desktop as well:
a long token is not only a narrow-viewport problem, and the two tests
above would both have passed while a desktop reader scrolled sideways.
"""

from __future__ import annotations

from ._wait import page_quiet

import argparse
import json
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
{{"cards":[{{"t":"`{LONG}`","b":"left"}},{{"t":"Other","b":"`{LONG}` on the right"}}]}}
```

## Numbers {{#kpi}}

```oku-kpi-grid
{{"tiles":[{{"num":"12","label":"`{LONG}`"}},{{"num":"3","label":"rows"}}]}}
```

## Table {{#table}}

```oku-table
{{"headers":["name","note"],"rows":[["`{LONG}`","long"],["`{LONG}`","also long"]]}}
```

## Filterable table {{#chips}}

```oku-table
{{"headers":["file",{{"label":"B: open-source Spark 3.5.4 + open-source Iceberg 1.10.0","filter":"chips","values":["pass","fail"]}}],
  "rows":[["one",{{"values":["pass"],"value":"pass"}}],["two",{{"values":["fail"],"value":"fail"}}]]}}
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
    page_quiet(page)
    got = page.evaluate(OVERFLOW)

    assert got["docWidth"] <= got["inner"] + 1, (
        f"the page scrolls sideways at {width}px ({got['docWidth']} vs {got['inner']}): {got['over']}"
    )


def test_nothing_escapes_its_column_at_360(page, narrow_page):
    """The page-level check above can be satisfied by a stray clip. This
    one names the element, which is what an author needs to fix it."""
    page.set_viewport_size({"width": 360, "height": 800})
    page.goto(narrow_page.as_uri(), wait_until="load")
    page_quiet(page)
    got = page.evaluate(OVERFLOW)

    assert got["over"] == [], f"elements outside the viewport with no scroller: {got['over']}"


# Keys whose value is an enum the schema pins, so appending to them
# produces a page the build rejects rather than a page to measure.
_ENUM_KEYS = {
    "k",
    "type",
    "lang",
    "kind",
    "mode",
    "src",
    "id",
    "color",
    "status",
    "tone",
    "accent",
    "severity",
    "variant",
    "align",
    "filter",
    "view",
    "orientation",
    "position",
    "boardOrder",
    "values",
}

_FENCE_OF = {
    "chart": "oku-chart",
    "chart-grid": "oku-chart-grid",
    "compare-grid": "oku-compare-grid",
    "copy": "oku-copy",
    "diagram": "oku-diagram",
    "example": "oku-example",
    "info-tip": "oku-info-tip",
    "insight": "oku-insight",
    "kpi-grid": "oku-kpi-grid",
    "live-snippet": "oku-live-snippet",
    "step-flow": "oku-step-flow",
    "table": "oku-table",
    "timeline": "oku-timeline",
    "annotated-code": "oku-annotated-code",
}


def _longify(obj):
    """The long token appended to every string the example carries."""
    if isinstance(obj, str):
        return f"{obj} {LONG}" if obj else obj
    if isinstance(obj, list):
        return [_longify(v) for v in obj]
    if isinstance(obj, dict):
        return {k: (v if k in _ENUM_KEYS else _longify(v)) for k, v in obj.items()}
    return obj


def _every_primitive_md() -> str:
    kit = Path(__file__).resolve().parents[3] / "kit"
    blocks = json.loads((kit / "schema" / "examples.json").read_text(encoding="utf-8"))["blocks"]
    out = [
        f"""---
title: Every primitive {LONG}
summary: One long token in every primitive the kit ships an example for.
---

> [!TLDR]
> A `{LONG}` in a callout.

## Prose {{#prose}}

A paragraph naming `{LONG}`.

- a list item with `{LONG}`
  - nested with `{LONG}`

> A blockquote holding `{LONG}`.

- [ ] a task with `{LONG}`
"""
    ]
    for kind, example in sorted(blocks.items()):
        if kind not in _FENCE_OF:
            continue
        payload = _longify(dict(example))
        payload.pop("k", None)
        out.append(f"## {kind} {{#{kind}}}\n\n```{_FENCE_OF[kind]}\n{json.dumps(payload)}\n```\n")
    out.append(f"## mermaid {{#mermaid}}\n\n```mermaid\nflowchart TB\n  A[{LONG}] --> B[{LONG}]\n```\n")
    return "\n".join(out)


@pytest.fixture(scope="module")
def every_primitive_page(tmp_path_factory):
    docs = tmp_path_factory.mktemp("every-primitive") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(_every_primitive_md(), encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Every primitive"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0, "the derived page must build — an enum key gained the token"
    return docs / "dist" / "standalone" / "page.html"


class TestEveryPrimitiveTakesALongToken:
    """Derived from the shipped examples, so a primitive added later is
    measured on the day it lands rather than the day someone remembers
    this file."""

    def test_the_page_holds_every_primitive_with_an_example(self, every_primitive_page) -> None:
        """Every assertion below is a negative and would pass on a page
        that rendered nothing."""
        md = _every_primitive_md()
        for fence in _FENCE_OF.values():
            assert f"```{fence}" in md, fence
        assert md.count(LONG) > 40, md.count(LONG)

    @pytest.mark.parametrize("width", [1440, 360, 320])
    def test_no_primitive_widens_the_page(self, page, every_primitive_page, width) -> None:
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(every_primitive_page.as_uri(), wait_until="load")
        page_quiet(page)
        got = page.evaluate(OVERFLOW)

        assert got["docWidth"] <= got["inner"] + 1, (
            f"the page scrolls sideways at {width}px ({got['docWidth']} vs {got['inner']}): {got['over']}"
        )

    @pytest.mark.parametrize("width", [1440, 360])
    def test_nothing_escapes_its_column(self, page, every_primitive_page, width) -> None:
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(every_primitive_page.as_uri(), wait_until="load")
        page_quiet(page)
        got = page.evaluate(OVERFLOW)

        assert got["over"] == [], f"outside the viewport at {width}px with no scroller: {got['over']}"
