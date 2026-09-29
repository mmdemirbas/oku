"""A URL or a path in a table cell breaks at its separators, and nowhere else.

Chrome does not break a URL at its slashes, so a cell holding one sets
the width of its whole column to the length of the address. Measured
on a delivered research tree: 31 of the 47 tables still pushed sideways
past their column after the phrase rule were held open by a URL or a
path, the widest a 99-character Wiktionary address drawn as a 539px
line in a 4-column table.

`overflow-wrap: anywhere` would release it and would also let every
word in the table break mid-letter, which is the reader's own "Fit to
width" and not a default. So `wireTable` inserts `<wbr>` where the
Chicago Manual of Style puts a URL break — after `//` and a colon,
before a single slash and `~ . , - _ ? # %`, on either side of `=` and
`&` — and only into tokens SHAPED like a path. `<wbr>` carries no
character, which is the other half of the rule: the address the reader
copies is the address the author wrote.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

URL = "https://en.wiktionary.org/wiki/Category:Turkish_terms_with_IPA_pronunciation"
CODE_URL = "webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content?token=n"
CODE_PATH = "kanit-12/sorunlar/tseglobal-portal-helal-sorgu.html"
PATHS = [URL, CODE_URL, CODE_PATH]

PAGE_MD = f"""---
title: Paths in cells
summary: A table whose cells carry addresses longer than any column.
---

## Sources {{#sources}}

| Source | Coverage | Access | Where |
|---|---|---|---|
| Wiktionary | 16,676 Turkish pages with IPA | Yes (dump) | [D] {URL} |
| EU sanctions list | Full list, daily | `{CODE_URL}` | CSV |
| Local copy | `2026-12-31` | Raw and/or summary | `{CODE_PATH}` |

## Island {{#island}}

<table>
<thead><tr><th>Step</th><th>Command</th></tr></thead>
<tbody><tr><td>fetch</td><td><pre><code>curl -O {URL}</code></pre></td></tr></tbody>
</table>
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tablepaths") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Paths in cells"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


def _open(built, browser, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    pg = context.new_page()
    pg.goto(built.as_uri(), wait_until="load")
    page_quiet(pg)
    return context, pg


@pytest.fixture(params=[1440, 360], ids=["desktop", "narrow"])
def page(request, built, browser):
    context, pg = _open(built, browser, request.param)
    yield pg
    context.close()


@pytest.fixture()
def desktop(built, browser):
    context, pg = _open(built, browser, 1440)
    yield pg
    context.close()


# Where each needle is drawn: the lines it takes, and for every line
# after the first, the characters either side of the break.
DRAWN = """(needles) => {
  const table = document.querySelector('.okt-table-scroll table');
  function locate(needle) {
    for (const td of table.querySelectorAll('td')) {
      const nodes = [];
      const w = document.createTreeWalker(td, NodeFilter.SHOW_TEXT);
      let n, text = '';
      while ((n = w.nextNode())) { nodes.push([n, text.length]); text += n.nodeValue; }
      const at = text.indexOf(needle);
      if (at === -1) continue;
      const chars = [];
      for (let i = at; i < at + needle.length; i++) {
        const [node, base] = nodes.filter(([, b]) => b <= i).pop();
        const r = document.createRange();
        r.setStart(node, i - base); r.setEnd(node, i - base + 1);
        chars.push(r.getBoundingClientRect());
      }
      const breaks = [];
      for (let i = 1; i < chars.length; i++) {
        if (chars[i].top > chars[i - 1].top + chars[i - 1].height / 2) {
          breaks.push(needle.slice(Math.max(0, i - 3), i) + '|' + needle.slice(i, i + 3));
        }
      }
      const tdR = td.getBoundingClientRect();
      return {lines: breaks.length + 1, breaks,
              past: Math.round(Math.max(...chars.map(c => c.right)) - tdR.right),
              text: td.textContent, wbr: td.querySelectorAll('wbr').length};
    }
    return null;
  }
  return needles.map(locate);
}"""

SIDEWAYS = """() => { const s = document.querySelector('.okt-table-scroll');
  return s.scrollWidth - s.clientWidth; }"""

BEFORE = set("/~.,-_?#%=&")
AFTER = set(":=&/-")


def test_the_table_holds_its_column(desktop):
    assert desktop.evaluate(SIDEWAYS) <= 1


def test_without_the_breaks_the_same_table_does_not(desktop):
    """Not vacuous: the fixture really is too wide unbroken. The marks
    and the break opportunities come out, and the overflow comes back."""
    got = desktop.evaluate(
        """() => { document.querySelectorAll('.okt-table-scroll wbr').forEach(w => w.remove());
          document.querySelectorAll('.okt-table-scroll [data-oku-path]')
            .forEach(c => delete c.dataset.okuPath);
          const s = document.querySelector('.okt-table-scroll');
          return s.scrollWidth - s.clientWidth; }"""
    )
    assert got > 50, f"only {got}px over without the breaks — the fixture stopped being too wide"


def test_every_address_breaks_at_a_separator(page):
    """Where it breaks is the point: `/wiki|/Category`, never
    `Categ|ory`. A line after the first starts ON a break-before
    character or right after a break-after one."""
    drawn = page.evaluate(DRAWN, PATHS)
    assert sum(len(got["breaks"]) for got in drawn) > 0, "nothing wrapped, so nothing was asked"
    for needle, got in zip(PATHS, drawn):
        for b in got["breaks"]:
            left, right = b.split("|")
            assert right[0] in BEFORE or left[-1] in AFTER, f"{needle!r} broke mid-segment at {b!r}"


def test_at_360px_every_address_wraps_inside_its_cell(built, browser):
    context, pg = _open(built, browser, 360)
    try:
        for needle, got in zip(PATHS, pg.evaluate(DRAWN, PATHS)):
            assert got["lines"] >= 2, f"{needle!r} drew on one line at 360px"
            assert got["past"] <= 1, f"{needle!r} ran {got['past']}px past its cell"
    finally:
        context.close()


def test_the_address_the_reader_takes_away_is_the_one_written(desktop):
    """`<wbr>` holds no character: the cell text, both table copies and
    a selection copied by hand all read the address as authored — the
    reason for `<wbr>` rather than a zero-width space."""
    got = desktop.evaluate(
        """(needles) => {
          const table = document.querySelector('.okt-table-scroll table');
          const sel = window.getSelection();
          const picked = [...table.querySelectorAll('td')]
            .filter(td => needles.some(n => td.textContent.includes(n)))
            .map(td => { sel.removeAllRanges(); const r = document.createRange();
                         r.selectNodeContents(td); sel.addRange(r); return sel.toString(); });
          return {tsv: __okuTableTsv(table), md: __okuTableMarkdown(table), picked,
                  text: table.textContent};
        }""",
        PATHS,
    )
    for needle in PATHS:
        assert needle in got["text"]
        assert needle in got["tsv"]
        assert needle in got["md"]
        assert any(needle in p for p in got["picked"]), f"a hand-copied selection lost {needle!r}"
    for blob in (got["tsv"], got["md"], *got["picked"]):
        assert "​" not in blob and "­" not in blob


def test_prose_and_tokens_that_are_not_paths_are_left_alone(page):
    """`and/or` is a word, and a date is a token: neither gets a break
    it did not have."""
    got = page.evaluate(
        """() => {
          const tds = [...document.querySelectorAll('.okt-table-scroll td')];
          const prose = tds.find(td => td.textContent.includes('and/or'));
          const date = [...document.querySelectorAll('.okt-table-scroll td code')]
            .find(c => c.textContent === '2026-12-31');
          const r = document.createRange(); r.selectNodeContents(date);
          const tops = new Set([...r.getClientRects()].map(x => Math.round(x.top)));
          return {proseWbr: prose.querySelectorAll('wbr').length,
                  dateMarked: 'okuPath' in date.dataset, dateLines: tops.size};
        }"""
    )
    assert got["proseWbr"] == 0
    assert got["dateMarked"] is False
    assert got["dateLines"] == 1


def test_a_code_block_in_a_cell_is_source_not_prose(desktop):
    """A `<pre>` in a cell is read back as program text by Prism and
    the line splitter, so the pass does not reach into it."""
    got = desktop.evaluate(
        """() => [...document.querySelectorAll('td pre')].map(p => p.querySelectorAll('wbr').length)"""
    )
    assert got and all(n == 0 for n in got), got


def test_one_line_still_means_one_line(built, browser):
    """The reader's One line is `okt-nowrap` on the table, and a path
    that learned to break must unlearn it there."""
    context, pg = _open(built, browser, 360)
    try:
        pg.evaluate("() => document.querySelector('.okt-table-scroll table').classList.add('okt-nowrap')")
        for needle, got in zip(PATHS, pg.evaluate(DRAWN, PATHS)):
            assert got["lines"] == 1, f"{needle!r} still wraps on One line: {got['breaks']}"
    finally:
        context.close()
