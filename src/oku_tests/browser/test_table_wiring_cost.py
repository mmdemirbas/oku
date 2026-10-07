"""Wiring a page's tables costs the same however many columns they have.

The column-resize pass asked each header cell for its computed
`position` right after appending the previous cell's handle, and a
style read after a write recomputes the style of the whole document.
On a delivered 211 KB page that was 220 forced style passes and 346 ms
of its load, measured with a Chromium trace; the first paint came at
848-912 ms and comes at 468-516 ms with every cell read before any is
written to.

The sticky header's ghost had the same shape three times over: each
real header cell was measured right after the previous copy was
written, 1080 forced passes over ten 12-column tables.

The invariant is stated so that it does not care which function forces
a pass: two pages with the same tables, six columns against twelve, must
force about the same number of style passes. Both pages' tables are
wider than the column, so both get the ghost and the only difference
between them is the number of header cells. Before either fix the
difference was in the hundreds.
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

TABLES = 10


def _page(title: str, columns: int) -> str:
    # One unbreakable word per label, under the 20 characters at which
    # a long token takes joints, so six columns already overflow.
    head = "| " + " | ".join(f"Measurementvalue{c:02d}" for c in range(columns)) + " |"
    rule = "|" + "---|" * columns
    row = "| " + " | ".join(f"value {c}" for c in range(columns)) + " |"
    sections = [f"## Table {t} {{#t{t}}}\n\n{head}\n{rule}\n{row}\n{row}\n" for t in range(TABLES)]
    return f"---\ntitle: {title}\nsummary: Ten tables.\n---\n\n" + "\n".join(sections)


# An author's island can override the sticky header cell; the handle
# still needs a positioning context there.
STATIC_ISLAND = """
## Island {#island}

<table>
<thead><tr><th style="position: static">Step</th><th>Command</th></tr></thead>
<tbody><tr><td>fetch</td><td>curl</td></tr></tbody>
</table>
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tablecost") / "docs"
    docs.mkdir(parents=True)
    pages = {
        "six": _page("Six", 6),
        "twelve": _page("Twelve", 12),
        "island": "---\ntitle: Island\nsummary: An author's table.\n---\n" + STATIC_ISLAND,
    }
    for name, md in pages.items():
        (docs / f"{name}.md").write_text(md, encoding="utf-8")
        (docs / f"{name}.html").write_text(cli._stub_for(name), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone"


def _forced_style_passes(browser, html: Path) -> int:
    context = browser.new_context(viewport={"width": 800, "height": 900})
    pg = context.new_page()
    browser.start_tracing(
        page=pg, categories=["devtools.timeline", "disabled-by-default-devtools.timeline.stack"]
    )
    pg.goto(html.as_uri(), wait_until="load")
    page_quiet(pg)
    trace = json.loads(browser.stop_tracing())
    # Both pages take the wide-table path (the ghost header), or the
    # comparison would be between two kinds of table, not two widths.
    fits = pg.evaluate("[...document.querySelectorAll('.okt-table-scroll')].map(s => s.dataset.fit).join('')")
    context.close()
    assert fits == "0" * TABLES, f"{html.name}: every table should be wider than the column, data-fit {fits}"
    events = trace["traceEvents"] if isinstance(trace, dict) else trace
    # A pass with a JS stack is one a script forced; the frame's own
    # passes carry none.
    return sum(
        1
        for e in events
        if e.get("name") == "UpdateLayoutTree"
        and e.get("ph") == "X"
        and (e.get("args", {}).get("beginData") or {}).get("stackTrace")
    )


def test_wiring_tables_does_not_cost_a_style_pass_per_column(built, browser):
    six = _forced_style_passes(browser, built / "six.html")
    twelve = _forced_style_passes(browser, built / "twelve.html")
    # The trace has to have seen forced passes at all, or the comparison
    # below would hold on a trace that recorded nothing.
    assert six > 0, "the trace recorded no forced style pass"
    # Sixty more header cells: one pass per cell would add 60 at least.
    assert twelve - six < 15, f"{six} forced style passes with 6 columns, {twelve} with 12"


def test_an_authors_static_header_cell_still_holds_its_handle(built, browser):
    context = browser.new_context(viewport={"width": 1100, "height": 900})
    pg = context.new_page()
    pg.goto((built / "island.html").as_uri(), wait_until="load")
    page_quiet(pg)
    got = pg.evaluate(
        """() => {
          const th = [...document.querySelectorAll('thead th')].find(t => t.textContent.trim().startsWith('Step'));
          const handle = th && th.querySelector(':scope > .okt-col-resize');
          return th && {position: getComputedStyle(th).position, held: !!handle && handle.offsetParent === th};
        }"""
    )
    context.close()
    assert got == {"position": "relative", "held": True}
