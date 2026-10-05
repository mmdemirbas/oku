"""A bar chart's wiring belongs to the chart, and a picture of one has none.

Two defects, one owner question:

- Each bar chart added its own `keydown` listener to `document` (Escape
  clears a pinned reading) and never removed it. The closure holds the
  chart, its cursor and its tooltip, so every in-place navigation left
  the previous page's charts reachable: four round trips took the count
  from 3 to 15.
- A compare-grid preview is a CLONE of a figure, and the comment beside
  it says the bar wiring must not adopt it. The code removed
  `data-hdc-bars-bound`, the very attribute the wiring's guard tests, so
  every clone was wired: two cursors drawn into each decoration, and one
  more `document` listener per clone.
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

BAR = {"type": "bar", "rows": [{"label": "a", "value": 3}, {"label": "b", "value": 5}]}
PAGE_MD = f"""---
title: Bars
summary: Three bar charts and a grid that previews them.
---

## Grid {{#grid}}

```oku-compare-grid
{json.dumps({"preview": True, "cards": [{"t": f"c{i}", "b": "", "href": f"#c{i}"} for i in range(3)]})}
```

""" + "\n".join(f"## C{i} {{#c{i}}}\n\n```oku-chart\n{json.dumps(BAR)}\n```\n" for i in range(3))

# Counts the document keydown listeners whose source is the bar chart's
# Escape handler, recognised by its body rather than by a name it does
# not have.
COUNT_INIT = """
window.__barKeydown = 0;
const add = Document.prototype.addEventListener;
Document.prototype.addEventListener = function (type, fn, opts) {
  if (type === 'keydown' && fn && /pinned/.test(String(fn)) && /cursor|_okuUnpin/.test(String(fn))) window.__barKeydown++;
  return add.call(this, type, fn, opts);
};
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("bars") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Bars"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture
def opened(browser, built):
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    context.add_init_script(COUNT_INIT)
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    page_quiet(page)
    for _ in range(2):
        page.evaluate("() => window.dispatchEvent(new Event('oku:rendered'))")
        page_quiet(page)
    yield page
    context.close()


def test_a_preview_clone_is_not_wired(opened) -> None:
    clones = opened.evaluate(
        """() => [...document.querySelectorAll('.okt-compare-preview, [class*="preview"]')]
             .filter((p) => p.querySelector('.bar-fill'))
             .map((p) => p.querySelectorAll('.okc-bar-cursor').length)"""
    )
    assert clones, "the grid drew no bar previews to inspect"
    assert set(clones) == {0}, f"cursors drawn into preview clones: {clones}"


def test_bar_charts_share_one_escape_listener(opened) -> None:
    count = opened.evaluate("() => window.__barKeydown")
    assert count <= 1, f"{count} document keydown listeners for three bar charts and their previews"


def test_escape_still_clears_a_pinned_reading(opened) -> None:
    opened.locator("#c0").scroll_into_view_if_needed()
    bar = opened.locator("#c0 .bar-fill").first
    bar.click()
    opened.wait_for_function("() => !!document.querySelector('#c0 .okc-tooltip.pinned, #c0 .pinned')")
    opened.keyboard.press("Escape")
    opened.wait_for_function("() => !document.querySelector('#c0 .okc-tooltip.pinned, #c0 .pinned')")
