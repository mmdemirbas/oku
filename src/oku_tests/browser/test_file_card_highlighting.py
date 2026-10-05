"""The hover card colours code the way the viewer does.

A chip naming a Python file opened in the viewer highlighted, and its
hover card showed the same lines as plain grey text: the card set
`textContent` and never asked Prism. Reported by a reader hovering a
`.py` chip on a delivered page; measured there, 0 tokens in the card and
61 in the viewer for the same file.

The line-window card is the harder half. Its rows are one element each
(so the named row can be marked across the full width), and a row
highlighted on its own loses the context a token spans — the middle line
of a docstring would be read as code. So the window is highlighted as
one block and split back into its rows, and the case that proves it is a
row inside a multi-line string.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

TOOL = '''"""Module doc.

Second line of the docstring.
"""


def area(r):
    return 3.14 * r * r
'''


# A docstring opening on line 1 and closing on line 33: the window around
# line 30 starts at row 28, inside it, with the opening quotes out of view.
LONG = '"""Doc.\n' + "".join(f"prose line {i}\n" for i in range(2, 33)) + '"""\n\n\ndef f():\n    return 1\n'


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("card") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "tool.py").write_text(TOOL, encoding="utf-8")
    (root / "src" / "long.py").write_text(LONG, encoding="utf-8")
    (root / "src" / "notes.txt").write_text("def is a word here\nnot code\n", encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "---\ntitle: Cards\nsummary: Hover cards.\n---\n\n## Files {#files}\n\n"
        "The file [`tool.py`](#f/../src/tool.py), a line of it [`tool.py:3`](#f/../src/tool.py:3), "
        "plain text [`notes.txt`](#f/../src/notes.txt), "
        "and a line far down a long docstring [`long.py:30`](#f/../src/long.py:30).\n",
        encoding="utf-8",
    )
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("index"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False)) == 0
    finally:
        os.chdir(cwd)
    return root


@pytest.fixture()
def page(built, browser):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.goto((built / "docs" / "dist" / "standalone" / "index.html").as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    pg.close()


def _hover(page, label: str) -> None:
    page.locator(
        "main .okt-fp .okt-fp-label", has_text=re.compile("^" + re.escape(label) + "$")
    ).first.hover()
    page.wait_for_selector(".oku-tooltip .okt-fp-card")


CARD = """() => { const c = document.querySelector('.oku-tooltip .okt-fp-card code'); if (!c) return null;
  return { text: c.textContent, keywords: [...c.querySelectorAll('.token.keyword')].map(t => t.textContent),
           tokens: c.querySelectorAll('.token').length }; }"""


def test_the_card_of_a_code_file_is_highlighted(page) -> None:
    _hover(page, "tool.py")
    page.wait_for_function(
        "() => document.querySelectorAll('.oku-tooltip .okt-fp-card .token').length > 0", timeout=10000
    )
    got = page.evaluate(CARD)
    assert "def" in got["keywords"], got
    # Colour is added; not one character of the file changes.
    assert got["text"].rstrip("\n") == TOOL.rstrip("\n"), got["text"]


def test_a_line_window_keeps_its_rows_and_the_context_across_them(page) -> None:
    _hover(page, "tool.py:3")
    page.wait_for_function(
        "() => document.querySelectorAll('.oku-tooltip .okt-fp-card-window .token').length > 0", timeout=10000
    )
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.oku-tooltip .okt-fp-card-row')].map(r => ({
             n: +r.dataset.n, hit: r.classList.contains('okt-fp-card-hit'), text: r.textContent,
             string: !!r.querySelector('.token.string, .token.triple-quoted-string') }))"""
    )
    lines = TOOL.rstrip("\n").split("\n")
    assert [r["n"] for r in rows] == list(range(1, len(lines) + 1)), rows
    assert [r["text"] for r in rows] == lines, rows
    assert [r["n"] for r in rows if r["hit"]] == [3], rows
    # Row 3 is the middle of a docstring. Highlighted on its own it would
    # be read as three Python names; highlighted with its neighbours it
    # is inside the string token that opened on row 1.
    assert rows[2]["string"], rows[2]


def test_a_file_with_no_grammar_stays_plain_text(page) -> None:
    """The control: nothing to highlight, so nothing is invented."""
    _hover(page, "notes.txt")
    page.wait_for_timeout(800)
    got = page.evaluate(CARD)
    assert got["tokens"] == 0, got
    assert got["text"].rstrip("\n") == "def is a word here\nnot code", got


def test_the_window_ends_at_the_files_last_line(page) -> None:
    """A file ends with a newline; that is not one more line.

    The window split the text on newlines and showed the empty string
    after the last one as a numbered row — row 9 of an 8-line file — while
    the viewer and the card's own `{n} lines` both said 8.
    """
    _hover(page, "tool.py:3")
    ns = page.evaluate(
        "() => [...document.querySelectorAll('.oku-tooltip .okt-fp-card-row')].map(r => +r.dataset.n)"
    )
    assert ns and ns[-1] == len(TOOL.rstrip("\n").split("\n")), ns


def test_a_window_inside_a_string_that_opened_above_it_is_still_a_string(page) -> None:
    _hover(page, "long.py:30")
    page.wait_for_function(
        "() => document.querySelectorAll('.oku-tooltip .okt-fp-card-window .token').length > 0", timeout=10000
    )
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.oku-tooltip .okt-fp-card-row')].map(r => ({
             n: +r.dataset.n, text: r.textContent,
             string: !!r.querySelector('.token.string, .token.triple-quoted-string'),
             keyword: !!r.querySelector('.token.keyword') }))"""
    )
    assert rows[0]["n"] < 30 < 33 <= rows[-1]["n"], rows
    inside = [r for r in rows if r["n"] < 33]
    assert inside and all(r["string"] for r in inside), inside
    assert any(r["keyword"] for r in rows if r["text"].startswith("def ")), rows
