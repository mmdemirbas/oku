"""A table leaves the page in the shape its destination reads.

TSV goes to a spreadsheet. GFM goes to a pull request, an issue, or
another markdown document — and that second destination had no button
at all, so the only way to get a table out of a page and into a review
comment was to retype it.

Both come off ONE reading of the live table, which is what makes the
load-bearing property assertable: a filtered table copies the rows the
reader can see, in either format, and the two never disagree about
which rows those are.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

# Alignment on every column, one cell holding the delimiter itself, and
# a numeric column — the three things a hand-rolled serialiser gets
# wrong. The escaped pipe renders as a bare `|`, so the copy has to put
# the backslash back or the table gains a column on paste.
#
# Ten rows because the toolbar's filter is a size rule: a small table
# ships no filter box, and the filter is what the last test exercises.
ROWS = "\n".join(f"| row{i} | {i} | a \\| b |" for i in range(10))
PAGE_MD = f"""---
title: Table
summary: A page carrying one table.
---

## Data {{#data}}

| Name | Count | Note |
|:---|---:|:---:|
{ROWS}
"""

HEAD = "| Name | Count | Note |\n| :--- | ---: | :---: |"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tablecopy") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Table"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def opened(built, browser):
    context = browser.new_context()
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page.wait_for_timeout(700)
    # The toolbar is quiet chrome: opacity 0 and pointer-events none
    # until the pointer is on the table. Nothing in it is clickable
    # before that, which is the design, so the test hovers like a reader.
    page.hover(".okt-table-wrap")
    page.wait_for_timeout(300)
    yield page
    context.close()


TSV = '[data-copy="tsv"]'
MD = '[data-copy="md"]'


def _copy(page, selector):
    page.click(f".okt-table-wrap {selector}")
    page.wait_for_timeout(200)
    return page.evaluate("() => navigator.clipboard.readText()")


def test_both_destinations_have_a_button(opened):
    """One button that guessed would be wrong half the time, and a menu
    hides the affordance behind a click that explains nothing."""
    buttons = opened.evaluate(
        """() => [...document.querySelectorAll('.okt-table-wrap [data-copy]')]
                 .map(b => [b.dataset.copy, b.getAttribute('title')])"""
    )
    assert buttons == [["tsv", "Copy data (TSV)"], ["md", "Copy as Markdown"]]


def test_the_second_button_is_the_same_size_as_the_first(opened):
    """The toolbar sizes its icons through `[data-copy]`, so a button
    named `data-copy-md` fell out of every rule in that list and
    rendered as a 22x10 box around a 0x0 icon. One attribute with a
    value is what keeps the next format from doing it again."""
    boxes = opened.evaluate(
        """() => [...document.querySelectorAll('.okt-table-wrap [data-copy]')].map(b => {
             const r = b.getBoundingClientRect();
             const s = b.querySelector('svg').getBoundingClientRect();
             return [Math.round(r.width), Math.round(r.height),
                     Math.round(s.width), Math.round(s.height)];
           })"""
    )
    assert boxes[0] == boxes[1], boxes
    assert boxes[1][2] >= 12 and boxes[1][3] >= 12, boxes


def test_the_markdown_copy_is_a_table_a_markdown_parser_reads(opened):
    text = _copy(opened, MD)
    assert text.startswith(HEAD), text
    assert text.endswith("| row9 | 9 | a \\| b |"), text
    assert len(text.splitlines()) == 12


def test_the_tsv_copy_still_goes_to_a_spreadsheet(opened):
    text = _copy(opened, TSV)
    assert text.startswith("Name\tCount\tNote\nrow0\t0\ta | b\n"), text
    assert len(text.splitlines()) == 11


def test_a_filtered_table_copies_what_is_on_screen(opened):
    """The clipboard reflects what the reader is looking at. A copy that
    quietly included the rows they had just filtered away would be
    discovered in the document they pasted it into."""
    opened.fill(".okt-table-wrap .okt-filter input", "row3")
    opened.wait_for_timeout(400)

    assert _copy(opened, MD) == f"{HEAD}\n| row3 | 3 | a \\| b |"
    assert _copy(opened, TSV) == "Name\tCount\tNote\nrow3\t3\ta | b"

    opened.fill(".okt-table-wrap .okt-filter input", "")
    opened.wait_for_timeout(400)


def test_the_button_says_whether_it_worked(opened):
    """The clipboard is not visible, so a copy that reported nothing
    would leave the reader clicking again to find out."""
    btn = opened.locator(f".okt-table-wrap {MD}")
    btn.click()
    opened.wait_for_timeout(150)
    assert "okt-flash-ok" in (btn.get_attribute("class") or "")
    opened.wait_for_timeout(1300)
    assert "okt-flash-ok" not in (btn.get_attribute("class") or "")
