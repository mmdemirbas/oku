"""A label is drawn in the case its author wrote it in, in every view.

`test_label_case.py` holds the stylesheet. This holds what the reader
sees: a page whose column names, group values and chart labels carry
case that matters (`createdAt`, a Turkish `işlem`), walked through the
table's four views and a chart reading, with every element that draws
text asked for its computed `text-transform`. Computed, because SVG text
has no `innerText` to compare and a rule can arrive from anywhere —
the kit's sheet, a vendored one, an inline style.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

PARCOORD = {
    "type": "parallel-coordinates",
    "title": "Builds",
    "variables": [{"key": "pages", "label": "pageCount"}, {"key": "ms", "label": "işlem ms"}],
    "records": [{"pages": 10, "ms": 900}, {"pages": 40, "ms": 2100}],
}
LINE = {
    "type": "line",
    "title": "Latency",
    "series": [{"label": "apiGateway", "data": [{"x": 1, "y": 142}, {"x": 2, "y": 155}, {"x": 3, "y": 138}]}],
}
SLOPE = {
    "type": "slope",
    "title": "p95",
    "from_label": "before CDN",
    "to_label": "after CDN",
    "items": [{"label": "/home", "from": 1400, "to": 680}, {"label": "/api", "from": 900, "to": 1500}],
}

PAGE_MD = f"""---
title: Case
summary: Labels whose case matters.
---

## Rows {{#rows}}

| createdAt | işlem | userId |
|---|---|---|
| 2026-10-01 | açık | u1 |
| 2026-10-02 | kapalı | u2 |
| 2026-10-03 | açık | u3 |

## Charts {{#charts}}

```oku-chart
{json.dumps(PARCOORD, ensure_ascii=False)}
```

```oku-chart
{json.dumps(SLOPE, ensure_ascii=False)}
```

```oku-chart
{json.dumps(LINE, ensure_ascii=False)}
```
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("case") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Page"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


RECASED = """() => {
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('.okt-lang')) continue;          // a code, allowed
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
    if (!own) continue;
    const tt = getComputedStyle(el).textTransform;
    if (tt !== 'none') out.push(`${el.tagName.toLowerCase()}.${String(el.className.baseVal ?? el.className).split(' ')[0]} ${tt} ${JSON.stringify(own)}`);
  }
  return out;
}"""

DRAWN = """(sel) => [...document.querySelectorAll(sel)].map(e => e.innerText.trim())"""


@pytest.fixture()
def page(built, browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    pg.goto(built.as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    context.close()


def test_every_view_draws_the_authors_case(page):
    found = [f"table: {r}" for r in page.evaluate(RECASED)]
    drawn = {}
    for view, sel in (
        ("cards", ".okt-card-key"),
        ("list", ".okt-list-card th[scope='row']"),
        ("board", ".okt-board-card-key"),
    ):
        page.evaluate(f"() => document.querySelector('.okt-view-btn[data-view=\"{view}\"]').click()")
        page.wait_for_selector(sel, state="attached")
        drawn[view] = page.evaluate(DRAWN, sel)
        found += [f"{view}: {r}" for r in page.evaluate(RECASED)]
    assert found == [], "\n".join(found[:40])
    # Vacuity: each view drew the column names, and drew them as written.
    for view, names in drawn.items():
        assert {"createdAt", "işlem", "userId"} <= set(names), (view, names)


def test_a_chart_reading_draws_the_authors_case(page):
    # The line chart's cursor reading: the series name and its keys.
    svg = page.locator("oku-chart").nth(2).locator(".okc-svg")
    svg.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'instant'})")
    box = svg.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.5)
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5, steps=6)
    page.wait_for_selector(".okc-tooltip .okc-tt-pin-hint", state="attached", timeout=4000)
    found = page.evaluate(RECASED)
    assert found == [], "\n".join(found[:40])
    # Vacuity: the SVG labels the sweep asked about are there.
    assert page.locator(".okc-parcoord-label").count() >= 2
    assert page.locator(".okc-slope-col").count() == 2
