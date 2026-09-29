"""The reader chooses how cells wrap, and the panel speaks the page's language.

Asked for by a reader: a way to override how a table's cells wrap,
"without making the table complicated". One row in the Configure
panel, three stops, the same shape as the View row above it, and per
table rather than per column — a control for every column is a table
of controls.

  - Wrap text (default): a phrase wraps, a token keeps its line. The
    rule `test_table_cells_fit_their_column.py` holds.
  - Fit to width: break anywhere, so the table holds its column. The
    one case the default cannot rescue is a single token with no
    whitespace — a URL, a path — because keeping a token whole is the
    default's whole point.
  - One line: nothing wraps and the table scrolls, for a reader who
    would rather scan one row per line.

The author's `okt-nowrap` sets where it starts, as `data-default-view`
sets the view, and both are the same class on the table — so the
author's choice and the reader's cannot drift apart.

The second half is a defect found while building the first. The panel
is built on open, which is AFTER the page's one-shot localize pass, so
on a Turkish page the whole panel was English — title, row labels,
subtitle, placeholder — although three of them had entries in the
table. The coverage test was green throughout, because it holds the
TABLE. And on a served page the words built when the table is wired
(view and cell buttons, group-by options) predate the string table
itself, which standalone inlines — so the same code was right in one
delivery mode and wrong in the other. Both modes are measured here.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

LONG_TOKEN = (
    "s3://warehouse-prod-eu-central-1/iceberg/db/events/data/partition=2026-09-28/00000-0-a1b2c3d4.parquet"
)

PAGE_MD = f"""---
title: Table cells control
summary: A table carrying a token too long for any column.
---

## Files {{#files}}

| Table | Snapshot | Path | Rows |
|---|---|---|---|
| `events` | `8744736658442914487` | `{LONG_TOKEN}` | 1200 |
| `users` | `1920384756473829101` | `s3://w/u.parquet` | 40 |

## Pinned {{#pinned}}

<table class="okt-nowrap">
<thead><tr><th>Key</th><th>Value</th></tr></thead>
<tbody><tr><td>a</td><td>one two three four five six seven eight nine ten</td></tr>
<tr><td>b</td><td>x</td></tr></tbody>
</table>
"""

TR_MD = """---
title: Tablo
summary: Türkçe bir sayfada tablo.
lang: tr
---

## Veriler {#veriler}

| View | Ad | Group by |
|---|---|---|
| `a` | 1 | x |
| `b` | 2 | y |
"""


def _build(tmp_path_factory, name: str, md: str) -> Path:
    docs = tmp_path_factory.mktemp(name) / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(md, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Page"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return _build(tmp_path_factory, "cellsctl", PAGE_MD)


@pytest.fixture(scope="module")
def built_tr(tmp_path_factory):
    return _build(tmp_path_factory, "cellstr", TR_MD)


@pytest.fixture()
def page(built, browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    pg.goto((built / "standalone" / "page.html").as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    context.close()


def _open(pg, idx: int = 0) -> None:
    pg.evaluate(
        "(i) => document.querySelectorAll('.okt-table-wrap')[i].querySelector('.okt-table-controls button[data-cfg]').click()",
        idx,
    )
    pg.wait_for_selector(".okt-config-popover:not([hidden]) [data-cells]")


def _choose(pg, mode: str) -> None:
    pg.evaluate(
        "(m) => document.querySelector('.okt-config-popover:not([hidden]) [data-cells=\"' + m + '\"]').click()",
        mode,
    )
    pg.wait_for_timeout(250)


SHAPE = """(i) => {
  const wrap = document.querySelectorAll('.okt-table-wrap')[i];
  const scroll = wrap.querySelector('.okt-table-scroll');
  const table = scroll.querySelector('table');
  const cells = [...table.querySelectorAll('tbody td')];
  const multi = cells.filter(td => {
    const lh = parseFloat(getComputedStyle(td).lineHeight) || 20;
    const pad = parseFloat(getComputedStyle(td).paddingTop) + parseFloat(getComputedStyle(td).paddingBottom);
    return (td.getBoundingClientRect().height - pad) > lh * 1.6;
  }).length;
  return {sideways: scroll.scrollWidth - scroll.clientWidth,
          fit: table.classList.contains('okt-fit'), nowrap: table.classList.contains('okt-nowrap'),
          multiLineCells: multi,
          pressed: [...document.querySelectorAll('.okt-config-popover:not([hidden]) [data-cells]')]
              .filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.cells)};
}"""


def test_the_default_keeps_a_long_token_whole_and_scrolls(page):
    """Not vacuous: the default really does leave this table wider than
    its column, which is the case the other two stops exist for."""
    _open(page)
    got = page.evaluate(SHAPE, 0)
    assert got["pressed"] == ["wrap"]
    assert got["sideways"] > 50, f"only {got['sideways']}px of overflow — the fixture stopped being too wide"


def test_fit_to_width_holds_the_table_in_its_column(page):
    _open(page)
    _choose(page, "fit")
    got = page.evaluate(SHAPE, 0)
    assert got["fit"] and not got["nowrap"]
    assert got["pressed"] == ["fit"]
    assert got["sideways"] <= 1, f"{got['sideways']}px of sideways scroll with Fit to width on"


def test_one_line_wraps_nothing(page):
    _open(page)
    _choose(page, "nowrap")
    got = page.evaluate(SHAPE, 0)
    assert got["nowrap"] and not got["fit"]
    assert got["pressed"] == ["nowrap"]
    assert got["multiLineCells"] == 0, f"{got['multiLineCells']} cell(s) still wrap on One line"


def test_the_stops_are_exclusive_and_the_default_comes_back(page):
    _open(page)
    _choose(page, "fit")
    _choose(page, "nowrap")
    _choose(page, "wrap")
    got = page.evaluate(SHAPE, 0)
    assert not got["fit"] and not got["nowrap"], "a class from an earlier stop survived"
    assert got["pressed"] == ["wrap"]


def test_the_authors_nowrap_is_where_the_control_starts(page):
    """`okt-nowrap` on the table is both the author's default and the
    reader's One line, so the panel has to open on it."""
    _open(page, 1)
    got = page.evaluate(SHAPE, 1)
    assert got["nowrap"], "the author's class was lost"
    assert got["pressed"] == ["nowrap"], f"the control opened on {got['pressed']}"


# ---- the panel's language, in both delivery modes -------------------

READ = """() => {
  const pop = document.querySelector('.okt-config-popover:not([hidden])');
  return {title: pop.querySelector('.okc-cfg-title').textContent,
          labels: [...pop.querySelectorAll('.okt-cfg-label')].map(l => l.textContent),
          subtitle: pop.querySelector('.okt-cfg-subtitle').textContent,
          placeholder: pop.querySelector('.okt-cfg-colfilter').placeholder,
          viewTitles: [...pop.querySelectorAll('[data-view]')].map(b => b.title),
          cellTitles: [...pop.querySelectorAll('[data-cells]')].map(b => b.title),
          noGrouping: pop.querySelector('select option[value="none"]').textContent,
          options: [...pop.querySelectorAll('select option')].map(o => o.textContent)};
}"""

ENGLISH = {
    "Configure table",
    "View",
    "Group by",
    "Cells",
    "Filter columns",
    "contains…",
    "Table view",
    "List view",
    "Cards view",
    "Board view",
    "Wrap text",
    "Fit to width",
    "One line",
    "— no grouping —",
}


def _read_tr(browser, url: str) -> dict:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    try:
        pg.goto(url, wait_until="load")
        page_quiet(pg)
        pg.evaluate("() => document.querySelector('.okt-table-controls button[data-cfg]').click()")
        pg.wait_for_selector(".okt-config-popover:not([hidden]) [data-cells]")
        return pg.evaluate(READ)
    finally:
        context.close()


def _served(root: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))

    class Quiet(handler.func):  # type: ignore[misc,valid-type]
        def log_message(self, *a):  # noqa: D401
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture(scope="module")
def served_tr(built_tr):
    srv = _served(built_tr / "site")
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


@pytest.mark.parametrize("mode", ["standalone", "site"])
def test_no_kit_word_in_the_panel_is_english_on_a_turkish_page(mode, built_tr, served_tr, browser):
    url = (built_tr / "standalone" / "page.html").as_uri() if mode == "standalone" else served_tr
    got = _read_tr(browser, url)
    shown = {
        got["title"],
        got["subtitle"],
        got["placeholder"],
        got["noGrouping"],
        *got["labels"],
        *got["viewTitles"],
        *got["cellTitles"],
    }
    # The author's own column names are allowed to be anything, and two
    # of them are spelled like kit words on purpose; they are checked
    # separately below.
    shown -= {"View", "Group by", "Ad"}
    left = sorted(shown & ENGLISH)
    assert not left, f"{mode}: English kit words on a Turkish page: {left}"
    assert got["title"] == "Tabloyu ayarla", got["title"]
    assert got["cellTitles"] == ["Metni kaydır", "Genişliğe sığdır", "Tek satır"], got["cellTitles"]
    assert got["viewTitles"][0] == "Tablo görünümü", got["viewTitles"]


@pytest.mark.parametrize("mode", ["standalone", "site"])
def test_the_authors_column_names_are_never_looked_up(mode, built_tr, served_tr, browser):
    """The reason the panel is not localized as a subtree. This page
    names two columns `View` and `Group by` — words the kit has keys
    for — and they must come through as the author wrote them, both as
    filter-row labels and as group-by options."""
    url = (built_tr / "standalone" / "page.html").as_uri() if mode == "standalone" else served_tr
    got = _read_tr(browser, url)
    filter_labels = got["labels"][3:]
    assert filter_labels == ["View", "Ad", "Group by"], filter_labels
    assert got["options"][1:] == ["View", "Ad", "Group by"], got["options"]


def test_the_panel_says_which_view_is_on(page):
    """A defect in the View row found while wiring the Cells row beside
    it. The popover MOVES the buttons out of the toolbar while it is
    open, and `setView` looked them up in the toolbar at click time, so
    it found none. Measured on the shipped kit: clicking List switched
    the table to list view and left Table highlighted and
    `aria-pressed` — the panel reporting a view that was no longer on
    screen, to a screen reader as much as to the eye."""
    _open(page)
    got = page.evaluate(
        """() => {
      const pop = document.querySelector('.okt-config-popover:not([hidden])');
      pop.querySelector('[data-view="list"]').click();
      return {view: document.querySelector('.okt-table-wrap').dataset.view,
              pressed: [...pop.querySelectorAll('[data-view]')]
                  .filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.view),
              active: [...pop.querySelectorAll('[data-view].active')].map(b => b.dataset.view)};
    }"""
    )
    assert got["view"] == "list", "the click did not change the view at all"
    assert got["pressed"] == ["list"], f"aria-pressed says {got['pressed']} while the table shows list"
    assert got["active"] == ["list"], f"the highlight says {got['active']} while the table shows list"
