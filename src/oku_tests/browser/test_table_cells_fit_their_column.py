"""A table cell holds what it is given without pushing the table wider.

Reported by a reader with a screenshot: a comparison table whose
Iceberg column carried an exception message in a code span. The span
drew as one unbroken line, the table came out wider than its column,
and the last two columns were pushed out of sight — the reader could
not see the `Same?` and `Note` values at all, and the row was more
than twice as tall as its content because the off-screen Note column
was wrapping into many lines.

Two rules, and the second is the reason the first cannot be a blanket
`white-space: normal`:

  - a code span that is a PHRASE wraps inside its column;
  - a code span that is one TOKEN does not, so the column claims the
    width it needs while the table has slack to give.

Whitespace decides which, from the content. Measured against
`2026-12-31` in a 40px box: `hyphens: none`, `word-break: keep-all`
and `line-break: strict` all leave min-content at 36px, because the
hyphen is a break opportunity under UAX #14 and nothing but
`white-space: nowrap` suppresses it. A blanket `normal` therefore also
collapses a date column to five characters, the auto layout hands the
slack to the prose column, and every date renders as `2026-12- / 31`.
The fourth case here is that regression, stated as a measurement.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

ERROR = "UnsupportedOperationException: Cannot cast TIMESTAMP WITH LOCAL TIME ZONE to DATE for column ts_ltz"
PAGE_MD = f"""---
title: Table cells
summary: A table whose cells hold both tokens and phrases.
---

## Cases {{#cases}}

| Case | Spark | Flink | Iceberg | Same? | Note |
|---|---|---|---|---|---|
| `cast_ntz_to_date` | `2026-12-31` | `2026-12-31` | `2026-12-31` | yes | |
| `cast_ltz_to_date` | `2026-12-31` | `2026-12-31` | error: `{ERROR}` | no | Flink and Spark agree; Iceberg refuses the cast |
| `year_ntz` | `2026` | `2026` | `2026` | yes | |
| `month_ntz` | `12` | `12` | `12` | yes | |

## Long tokens {{#long}}

| Setting | Spark | Flink | Iceberg | Same? | Note |
|---|---|---|---|---|---|
| `spark.sql.iceberg.planning.preserve-data-grouping` | `true` | `false` | `true` | no | Flink has no such key |
| `resmi_zorla_calistirma_listesi` | `on` | `on` | `on` | yes | |

## Many columns {{#many}}

| Month | Active days | Turns | Cache write 5m | Cache write 1h | Cache read | Output | USD | Subagent $ |
|---|---|---|---|---|---|---|---|---|
| 2026-06 (incomplete) | 18 | 4,973 | 10.5 M | 41.0 M | 1,813 M | 7.1 M | 1,734 | 9% |
| 2026-07 | 31 | 8,120 | 12.9 M | 52.3 M | 2,410 M | 9.8 M | 2,215 | 11% |

## Dense {{#dense}}

| Month | Input | Output | Cache | Write | Agent | Total | Calls | Avg |
|---|---|---|---|---|---|---|---|---|
| 2026-06 | 105,025 | 9,411 | 77,902 | 1,204 | 12 | 193,554 | 311 | 622 |
| 2026-07 | 98,310 | 8,920 | 70,118 | 1,010 | 9 | 178,367 | 290 | 615 |
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tablecells") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Table cells"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture()
def page(built, browser):
    context = browser.new_context(viewport={"width": 1500, "height": 900})
    pg = context.new_page()
    pg.goto(built.as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    context.close()


# Every reading is of the #cases table. The page holds two more, and a
# document-wide selector mixed their rows into the row heights — worse,
# into `hiddenHeight`, which measured them against THIS table's edge.
MEASURE = """() => {
  const scroll = document.querySelector('main section#cases .okt-table-scroll');
  const table = scroll.querySelector('table');
  const cell = (t) => [...scroll.querySelectorAll('td code')]
      .filter(c => c.textContent.trim() === t)[0];
  const lines = (el) => el ? Math.round(el.getBoundingClientRect().height
      / parseFloat(getComputedStyle(el).lineHeight || 21)) : null;
  const phrase = [...scroll.querySelectorAll('td code')]
      .find(c => c.textContent.length > 40);
  return {
    tableW: Math.round(table.getBoundingClientRect().width),
    scrollW: Math.round(scroll.getBoundingClientRect().width),
    scrollRight: Math.round(scroll.getBoundingClientRect().right),
    sideways: scroll.scrollWidth - scroll.clientWidth,
    headers: [...scroll.querySelectorAll('thead th')]
        .map(th => ({text: th.textContent.trim().replace(/\\s+$/, ''),
                     right: Math.round(th.getBoundingClientRect().right)})),
    phraseMarked: phrase ? phrase.dataset.okuPhrase === '1' : null,
    phraseLines: lines(phrase),
    dateMarked: cell('2026-12-31') ? cell('2026-12-31').dataset.okuPhrase === '1' : null,
    dateLines: lines(cell('2026-12-31')),
    identLines: lines(cell('cast_ntz_to_date')),
    tallestRow: Math.max(...[...scroll.querySelectorAll('tbody tr')]
        .map(t => Math.round(t.getBoundingClientRect().height))),
    // How much taller each row is than the tallest cell the reader can
    // see in it: a row's height is its tallest cell's, so anything left
    // over came from a cell past the scroller's edge.
    hiddenHeight: Math.max(...[...scroll.querySelectorAll('tbody tr')].map(tr => {
      const edge = scroll.getBoundingClientRect().right + 1;
      const content = (c) => { const r = document.createRange(); r.selectNodeContents(c);
                               return r.getBoundingClientRect().height; };
      const cs = getComputedStyle(tr.cells[0]);
      const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
      const seen = [...tr.cells].filter(c => c.getBoundingClientRect().right <= edge).map(content);
      return Math.round(tr.getBoundingClientRect().height - pad - Math.max(0, ...seen));
    })),
  };
}"""


@pytest.fixture()
def m(page):
    return page.evaluate(MEASURE)


def test_a_phrase_in_a_code_span_wraps_inside_its_column(m):
    assert m["phraseMarked"] is True, "a code span holding whitespace is a phrase and has to be marked one"
    assert m["phraseLines"] >= 2, f"the message drew on {m['phraseLines']} line(s) — it did not wrap"


def test_the_table_does_not_outgrow_its_column(m):
    """The reader's actual complaint. Before: 1379px of table in a
    1086px scroller, 293px of forced sideways scrolling."""
    assert m["sideways"] == 0, (
        f"{m['sideways']}px of sideways scroll — table {m['tableW']}px in a {m['scrollW']}px scroller"
    )


def test_every_column_is_visible(m):
    """The two right-hand columns were off screen entirely, which is
    how a value goes missing without anything failing."""
    names = [h["text"].upper() for h in m["headers"]]
    assert names[:6] == ["CASE", "SPARK", "FLINK", "ICEBERG", "SAME?", "NOTE"], names
    over = [h["text"] for h in m["headers"] if h["right"] > m["scrollRight"] + 1]
    assert not over, f"columns past the right edge of the scroller at {m['scrollRight']}px: {over}"


def test_a_token_in_a_code_span_keeps_its_line(m):
    """The regression the phrase rule must not cause: a hyphen is a
    break opportunity, so a blanket `normal` renders every date as
    `2026-12- / 31`."""
    assert m["dateMarked"] is False, "a date is one token, not a phrase"
    assert m["dateLines"] == 1, f"`2026-12-31` drew on {m['dateLines']} lines"
    assert m["identLines"] == 1, f"`cast_ntz_to_date` drew on {m['identLines']} lines"


def test_a_row_is_as_tall_as_what_the_reader_can_see(m):
    """It was 177px for two lines of text, because the column that had
    been pushed off screen was wrapping into many lines out of sight.

    Stated against the visible cells rather than as a pixel ceiling: at
    the reading measure a 98-character message in a six-column table
    wraps onto several lines in plain view, and that row is tall for a
    reason the reader can see. What may not happen is height arriving
    from a cell past the edge."""
    # A few pixels are a code chip's own padding and the row's rule; the
    # defect measured 68 at this viewport.
    assert m["hiddenHeight"] <= 6, (
        f"a row is {m['hiddenHeight']}px taller than any cell in view (tallest row {m['tallestRow']}px)"
    )


def test_a_config_row_never_hangs_outside_the_panel(page):
    """The other half of the same report, and the same CSS rule one
    element over: `.okt-cfg-field` is the flex item the row sizes, and
    a flex item will not shrink below the intrinsic width of the
    `<input>` it holds — a search input sizes itself from its `size`
    attribute. The input already carried `min-width: 0`, one level too
    deep to help.

    Squeezed on purpose: the panel is content-sized between 280 and
    360px, so the overflow only shows once the intrinsic width exceeds
    the share the row can give. Without the squeeze this passes on a
    panel that was never under pressure."""
    page.hover(".okt-table-wrap")
    page.evaluate("() => document.querySelector('.okt-table-controls button[data-cfg]').click()")
    page.wait_for_timeout(400)
    page.add_style_tag(
        content=".okt-config-popover { min-width: 200px !important; max-width: 200px !important; }"
    )
    page.wait_for_timeout(300)
    got = page.evaluate("""() => {
      const pop = document.querySelector('.okt-config-popover:not([hidden])');
      const pr = pop.getBoundingClientRect();
      const rows = [...pop.querySelectorAll('.okt-cfg-row')].filter(r => r.querySelector('input[type=search]'));
      return {rows: rows.length,
              worst: Math.max(...rows.map(r => {
                const c = r.querySelector('input[type=search]');
                return Math.round(c.getBoundingClientRect().right - pr.right);
              })),
              overflow: Math.max(...rows.map(r => Math.round(r.scrollWidth - r.clientWidth)))};
    }""")
    assert got["rows"] >= 6, f"only {got['rows']} rows measured — the panel did not open"
    assert got["overflow"] == 0, f"a config row overflows by {got['overflow']}px"
    assert got["worst"] <= 0, f"a control hangs {got['worst']}px outside the panel"


TABLES = """() => Object.fromEntries([...document.querySelectorAll('main section')].map(sec => {
  const s = sec.querySelector('.okt-table-scroll'); if (!s) return null;
  const codes = [...s.querySelectorAll('td code')];
  return [sec.id, { sideways: s.scrollWidth - s.clientWidth,
    codes: codes.map(c => ({ text: c.textContent, wbr: c.querySelectorAll('wbr').length,
                             lines: Math.round(c.getBoundingClientRect().height / parseFloat(getComputedStyle(c).lineHeight)) })) }];
}).filter(Boolean))"""


def test_a_long_token_breaks_at_its_joints(page):
    """At the reading measure a 49-character config key held a six-column
    table open by itself. A token of 20 characters or more takes breaks
    at its dots, underscores, hyphens and camel humps — never inside a
    run of letters — and a short one keeps its line, so a date or a
    short identifier still reads as one word. The text is untouched:
    the breaks are `<wbr>`, which carry no character."""
    t = page.evaluate(TABLES)["long"]
    assert t["sideways"] == 0, f"{t['sideways']}px of sideways scroll"
    key = next(c for c in t["codes"] if c["text"].startswith("spark."))
    assert key["text"] == "spark.sql.iceberg.planning.preserve-data-grouping"
    assert key["wbr"] >= 4, key
    assert all(c["wbr"] == 0 and c["lines"] == 1 for c in t["codes"] if len(c["text"]) < 20), t["codes"]


def test_a_table_of_short_values_fits_however_many_columns(page):
    """Nine columns, most of them counts — the shape of a usage table in
    a delivered research tree, which scrolled sideways at the reading
    measure. A 9ch floor on every cell, left from when cells broke
    anywhere, held the `18` and `9%` columns at 9ch plus padding. The
    floor lives only where cells break anywhere now."""
    t = page.evaluate(TABLES)["many"]
    assert t["sideways"] == 0, f"{t['sideways']}px of sideways scroll"


def test_a_dense_table_sets_tighter_gutters(page):
    """Nine columns of numbers whose every column clears 9ch, so the
    floor is not what holds it: 28px of padding per column is. A table
    of six columns or more pads cells 10px a side, and the sticky
    header's ghost — which copies content widths — pads alike."""
    t = page.evaluate(TABLES)["dense"]
    assert t["sideways"] == 0, f"{t['sideways']}px of sideways scroll"
    pads = page.evaluate(
        """() => { const w = document.querySelector('#dense .okt-table-wrap');
          const p = (s) => { const e = w.querySelector(s); return e ? getComputedStyle(e).paddingLeft : null; };
          return { td: p('table td'), th: p('table th') }; }"""
    )
    assert pads["td"] == pads["th"] == "10px", pads
