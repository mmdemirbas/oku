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

from ._wait import measured, page_quiet, until

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
# Ten rows so the last test has rows to filter OUT — the copy has to
# carry the rows on screen, not the rows in the source.
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
    page_quiet(page)
    # The toolbar is quiet chrome: opacity 0 and pointer-events none
    # until the pointer is on the table. Nothing in it is clickable
    # before that, which is the design, so the test hovers like a reader.
    page.hover(".okt-table-wrap")
    # The toolbar fades in, and a button mid-fade is one Playwright will
    # decline to click. Its opacity settling is the end of that
    # transition, which has no event of its own.
    measured(
        page,
        "() => { const b = document.querySelector('.okt-table-wrap [data-copy=\"md\"]');"
        "        return b ? getComputedStyle(b).opacity : null; }",
    )
    yield page
    context.close()


TSV = '[data-copy="tsv"]'
MD = '[data-copy="md"]'


def _rows_settle(page, expected: int) -> None:
    """The filter runs on input and re-lays the table, so what a copy is
    about to read is the row set the filter left behind. Waiting for the
    COUNT rather than for a delay: the assertion that follows is about
    which rows reached the clipboard, and a copy taken mid-filter is the
    exact bug it would otherwise pass over.

    Two things about the count, both measured rather than assumed after
    two wrong guesses. The filter REMOVES rows from the DOM — it does not
    hide them — so a `:not(.okt-row-hidden)` count never changes. And
    `.okt-table-wrap` holds four renderings of the same rows (the table,
    a card stack, a list and a board), so ten rows are forty `tr`s; the
    scope is the table view, which is the one the copy path reads. The
    three exclusions are kept because they are how that path spells
    "visible", and a test with its own definition agrees with the button
    only by accident."""
    until(
        page,
        "() => [...document.querySelectorAll('.okt-table-wrap .okt-table-scroll tbody tr')]"
        ".filter((tr) => !tr.classList.contains('group-header')"
        "             && !tr.classList.contains('okt-row-hidden')"
        "             && !tr.hidden).length === " + str(expected),
        what=f"the table settled at {expected} row(s) on screen",
    )


def _copy(page, selector):
    """Click a copy button and hand back what actually reached the
    clipboard.

    The write is async, so the read has to wait for it — and the button
    says when it lands: the kit flashes `okt-flash-ok` on success. That
    is the same signal a reader gets, which makes it the honest thing to
    wait for; a fixed delay here would read the PREVIOUS format's text
    on a slow machine and pass, because both formats are plausible
    strings."""
    page.click(f".okt-table-wrap {selector}")
    until(
        page,
        f"() => document.querySelector('.okt-table-wrap {selector}').classList.contains('okt-flash-ok')",
        what=f"the {selector} button reported the copy landed",
    )
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


def test_the_markdown_button_wears_the_copy_icon(opened):
    """Two buttons that both copy have to read as a pair. The markdown
    one carried the Markdown logo mark instead — a wide rounded box, an
    M, and a descending arrow — and the arrow reads as download, which
    is the one thing neither button does.

    The rule is structural, so it is assertable rather than a matter of
    taste: every shape in the TSV icon appears in the markdown icon,
    which adds exactly one of its own for the format.
    """
    shapes = opened.evaluate(
        """() => [...document.querySelectorAll('.okt-table-wrap [data-copy]')].map(b =>
             [...b.querySelector('svg').children].map(el =>
               el.tagName.toLowerCase() + ':' + (el.getAttribute('d') ||
                 ['x', 'y', 'width', 'height'].map(a => el.getAttribute(a)).join(','))))"""
    )
    tsv, md = shapes
    assert len(tsv) == 2, tsv
    assert set(tsv) <= set(md), (tsv, md)
    assert len(set(md) - set(tsv)) == 1, (tsv, md)


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
    _rows_settle(opened, 1)

    assert _copy(opened, MD) == f"{HEAD}\n| row3 | 3 | a \\| b |"
    assert _copy(opened, TSV) == "Name\tCount\tNote\nrow3\t3\ta | b"

    opened.fill(".okt-table-wrap .okt-filter input", "")
    _rows_settle(opened, 10)


def test_the_button_says_whether_it_worked(opened):
    """The clipboard is not visible, so a copy that reported nothing
    would leave the reader clicking again to find out."""
    btn = opened.locator(f".okt-table-wrap {MD}")
    btn.click()
    until(
        opened,
        f"() => document.querySelector('.okt-table-wrap {MD}').classList.contains('okt-flash-ok')",
        what="the button flashed to say the copy landed",
    )
    assert "okt-flash-ok" in (btn.get_attribute("class") or "")
    # And it goes again on its own. The flash is a timed state, so this
    # half was 1300 ms of dead time on every run — the condition is the
    # class leaving, which is the same thing stated as a fact rather
    # than as a duration.
    until(
        opened,
        f"() => !document.querySelector('.okt-table-wrap {MD}').classList.contains('okt-flash-ok')",
        what="the flash cleared itself",
    )
    assert "okt-flash-ok" not in (btn.get_attribute("class") or "")
