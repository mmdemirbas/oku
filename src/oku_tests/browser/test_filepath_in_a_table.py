"""A path in a table cell is a chip, at desktop and on a phone.

The reported complaint was that documents keep writing a path as a bare
code span "especially in tables", and the answer to that is a nudge plus
a rewrite (`path-in-code-span`, `oku check --fix`). Both of those are
worth nothing if the chip does not actually work where they send it, so
this is the premise the rest of that work rests on rather than a
decoration of it.

A table is not one rendering. The kit builds four from the same rows —
the table itself, a card stack for narrow viewports, a list-card view
and a board view — so a reference in one cell becomes four elements,
three of them hidden at any given width. That is the table's normal
structure and not something `#f/` introduced; what it means here is that
"the chip works" has to be asserted about the copy the reader can
actually see, at the width they are seeing it.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

PROGRAM = "def hello(name):\n    return f'hi {name}'\n"

PAGE_MD = """---
title: Paths in cells
summary: The same reference in a paragraph, a GFM table and an oku-table.
---

## In a paragraph {#prose}

The program is [`../src/hello.py`](#f/../src/hello.py).

## In a GFM table {#gfm}

| What | Where |
|---|---|
| The program | [`../src/hello.py`](#f/../src/hello.py) |
| Nothing | plain text |

## In an oku-table {#typed}

```oku-table
{"headers":["What","Where"],"rows":[["The program","[`../src/hello.py`](#f/../src/hello.py)"],["Nothing","plain text"]]}
```
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("fpcell")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / "src").mkdir()
    (root / "src" / "hello.py").write_text(PROGRAM, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Paths in cells"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def opened(built, browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    yield page
    context.close()


VISIBLE = """(sel) => [...document.querySelectorAll(sel + ' oku-filepath')]
  .filter((c) => c.getBoundingClientRect().width > 0)
  .map((c) => ({
    path: c.getAttribute('path'),
    status: c.getAttribute('data-status'),
    kind: c.getAttribute('data-kind'),
    inCell: !!c.closest('td, .okt-card-val'),
    copy: c.querySelectorAll('.okt-fp-copy').length,
  }))"""


@pytest.mark.parametrize("section", ["gfm", "typed"])
def test_the_cell_holds_one_visible_working_chip(opened, section):
    """Both table spellings, because they are two renderers: a GFM table
    is parsed out of a markdown string and an `oku-table` is a typed
    payload, and only the first would be covered by a test that used the
    markdown one alone."""
    got = opened.evaluate(VISIBLE, f"section#{section}")
    assert got == [
        {
            "path": "../src/hello.py",
            "status": "ok",
            "kind": "text",
            "inCell": True,
            "copy": 1,
        }
    ], got


@pytest.mark.parametrize("section", ["gfm", "typed"])
def test_hovering_a_cell_chip_shows_the_file(opened, section):
    """The whole reason to prefer the chip over a code span. A cell is
    inside a scroll container with its own stacking and overflow, which
    is exactly where a popup anchored to the pointer goes wrong."""
    opened.hover(f"section#{section} td oku-filepath .okt-fp-label")
    opened.wait_for_timeout(400)
    tip = opened.locator(".oku-tooltip")
    assert tip.count() == 1
    text = tip.first.inner_text()
    assert "hello.py" in text, text
    assert "return f'hi {name}'" in text, text
    opened.mouse.move(2, 2)
    opened.wait_for_timeout(400)


@pytest.mark.parametrize("section", ["gfm", "typed"])
def test_the_chip_does_not_make_its_row_taller(opened, section):
    """A control that grows the row would make every path the loudest
    thing in the table, which is the opposite of what an author means by
    mentioning a file. Measured against the sibling row, which carries
    plain text and nothing else."""
    rows = opened.evaluate(
        """(sel) => [...document.querySelectorAll(sel + ' .okt-table-scroll tbody tr')]
             .map((tr) => Math.round(tr.getBoundingClientRect().height))""",
        f"section#{section}",
    )
    assert len(rows) == 2, rows
    assert abs(rows[0] - rows[1]) <= 4, rows


def test_on_a_phone_the_chip_still_works_and_the_page_does_not_widen(built, browser):
    """360px, where a control inside a table is most likely to be the
    thing that sets the page's minimum width — a chip is an inline-flex
    box holding a path, which is exactly the shape the kit has a rule
    about.

    Which of the four copies is visible at this width is the table's
    decision and not this test's business, so it is read rather than
    assumed: measured here, the `<td>` is still the visible one at
    360px and the alternate views stay at zero width.
    """
    context = browser.new_context(viewport={"width": 360, "height": 800})
    page = context.new_page()
    try:
        page.goto(built.as_uri(), wait_until="load")
        page_quiet(page)
        got = page.evaluate(VISIBLE, "section#typed")
        assert [g["path"] for g in got] == ["../src/hello.py"], got
        assert got[0]["inCell"] and got[0]["status"] == "ok" and got[0]["copy"] == 1, got
        assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), (
            "the chip in the cell set the page's minimum width"
        )
    finally:
        context.close()
