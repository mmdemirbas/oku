"""The kit does not break the document outline it renders.

`##` opens a `<section>` with an `h2`, so every figure and callout on a
page sits under one. Their titles were emitted as `h4`, which skips a
level — six breaks on docs/architecture.html, and every one of them
produced by the kit rather than by the author.

`oku check` cannot see this. It lints the markdown SOURCE, where a
callout title is not a heading at all and a chart title does not exist
yet. The defect only exists in the rendered output, which is why the
assertion has to be made in a browser.

h3 is not the fix. `buildTOC` collects every h3 in a section, so
promoting these would list 43 card titles in the on-page contents of
docs/charts.md. A card title labels a box; it is not a section of the
document. So it is a `<p>`, and the box carries the name through
`aria-labelledby`.
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

# One of every kit primitive that carries a title, all inside a single
# `##` section, so each one gets the chance to skip a level.
MD = """---
title: Outline
summary: Every titled primitive under one section heading.
---

## Only section {#only}

Lead paragraph.

> [!NOTE] A callout with a title
> Body text for the callout.

```oku-step-flow
{"steps":[{"t":"First step","b":"Body."},{"t":"Second step","b":"Body."}]}
```

```oku-compare-grid
{"cards":[{"t":"Card one","b":"Body.","verdict":"good"},{"t":"Card two","b":"Body.","verdict":"bad"}]}
```

```oku-chart
{"type":"bar","title":"A bar chart title","rows":[{"label":"a","value":3},{"label":"b","value":6}]}
```

```oku-chart
{"type":"stacked-bar","title":"A stacked title","categories":["x"],"series":[{"label":"one","values":[2]},{"label":"two","values":[4]}]}
```

### A real sub-heading {#sub}

Prose under a genuine h3.
"""

OUTLINE = """() => {
  const hs = [...document.querySelectorAll('main h1,main h2,main h3,main h4,main h5,main h6')];
  const levels = hs.map(h => +h.tagName[1]);
  let skips = [];
  for (let i = 1; i < levels.length; i++) {
    if (levels[i] - levels[i - 1] > 1) skips.push('h' + levels[i - 1] + '->h' + levels[i]);
  }
  const titled = [...document.querySelectorAll('.callout-title, .okt-card-title, .bar-chart-title')];
  return {
    levels,
    skips,
    headingTexts: hs.map(h => (h.innerText || '').replace(/#$/, '').trim()),
    titles: titled.length,
    titlesThatAreHeadings: titled.filter(e => /^H[1-6]$/.test(e.tagName)).length,
    labelledCallouts: document.querySelectorAll('.callout[role="note"][aria-labelledby]').length,
    callouts: document.querySelectorAll('.callout').length,
  };
}"""


@pytest.fixture(scope="module")
def outline_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("outline")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.md").write_text(MD, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("Outline"), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def outline(browser, outline_url):
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    pg.goto(f"{outline_url}/page.html")
    page_quiet(pg)
    yield pg.evaluate(OUTLINE)
    pg.close()


def test_no_heading_level_is_skipped(outline):
    assert outline["skips"] == [], (
        f"the kit skipped a heading level: {outline['skips']} in {outline['levels']}"
    )


def test_the_outline_is_only_the_authors_headings(outline):
    """A reader navigating by heading should get the document's sections
    — the cover title, the section, its sub-heading — and nothing the
    kit drew inside a figure."""
    assert outline["levels"] == [1, 2, 3], outline
    assert "A callout with a title" not in outline["headingTexts"], outline
    assert "Card one" not in outline["headingTexts"], outline
    assert "A bar chart title" not in outline["headingTexts"], outline


def test_every_figure_title_still_exists(outline):
    """Not a heading is not the same as not there — the words are still
    on the page, and removing them would be a different bug."""
    assert outline["titles"] >= 6, outline
    assert outline["titlesThatAreHeadings"] == 0, outline


def test_a_titled_callout_is_a_named_region(outline):
    """The title stops being a heading, so it has to name its box some
    other way or assistive tech loses it entirely."""
    assert outline["callouts"] >= 1, outline
    assert outline["labelledCallouts"] == outline["callouts"], outline
