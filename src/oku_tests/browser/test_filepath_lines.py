"""A file reference can name a line, and the reader lands on it.

`[`tool.py:120`](#f/src/tool.py:120)` — the form compilers print and
every editor takes. A path in a document very often means a place in a
file, and the chip used to open the top of it: the reader then scrolled
a 300-line file looking for what the sentence was about.

Held here, against the standalone build (the mode with the least to
work with):

  - the file is carried once however many of its lines are named;
  - the hover card shows the rows around the line, numbered, the named
    ones marked — not the top of the file;
  - the viewer marks the line (or the range) and scrolls it into view;
  - a line in a markdown file is a line of its SOURCE, so it opens there;
  - the editor link carries the line.
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

PLATFORM = """
  Object.defineProperty(Navigator.prototype, 'platform', { get: () => 'MacIntel' });
  Object.defineProperty(Navigator.prototype, 'userAgentData', { get: () => undefined });
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("lines") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "tool.py").write_text(
        "".join(f"value_{i} = {i}\n" for i in range(1, 301)), encoding="utf-8"
    )
    docs = root / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "notes" / "a.md").write_text(
        "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\n"
        + "\n\n".join(f"Paragraph {i}." for i in range(1, 30))
        + "\n",
        encoding="utf-8",
    )
    (docs / "index.md").write_text(
        "---\ntitle: Lines\nsummary: References to lines.\n---\n\n## Files {#files}\n\n"
        "One line [`tool.py:120`](#f/../src/tool.py:120), a range [`tool.py:200-204`](#f/../src/tool.py:200-204), "
        "and a line of a note's source [`a.md:12`](#f/notes/a.md:12).\n",
        encoding="utf-8",
    )
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("index"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return root


@pytest.fixture()
def page(built, browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    context.add_init_script(PLATFORM)
    pg = context.new_page()
    pg.goto((built / "docs" / "dist" / "standalone" / "index.html").as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    context.close()


def _chip(page, label):
    return page.locator("main .okt-fp .okt-fp-label", has_text=re.compile("^" + re.escape(label) + "$")).first


VIEW = """() => { const w = document.querySelector('.okt-mdview'); if (!w) return null;
  const body = w.querySelector('.okt-mdview-body'), b = body.getBoundingClientRect();
  const hits = [...w.querySelectorAll('.okt-line-hit')];
  const rows = (pre) => pre ? [...pre.querySelectorAll('code > .okt-code-line')] : [];
  const pre = hits.length ? hits[0].closest('pre') : null;
  return { hits: hits.map(h => rows(pre).indexOf(h) + 1),
           visible: hits.length ? (() => { const r = hits[0].getBoundingClientRect(); return r.top >= b.top && r.bottom <= b.bottom; })() : false,
           inSource: !!(pre && pre.classList.contains('okt-mdview-source')),
           view: w.getAttribute('data-view'),
           crumb: (w.querySelector('.okt-viewer-crumb-here') || {}).textContent }; }"""


def test_the_file_is_carried_once_for_all_its_lines(page):
    keys = page.evaluate("() => Object.keys(window.__okuFiles || {})")
    assert sorted(keys) == ["../src/tool.py", "notes/a.md"], keys
    assert page.locator("main .okt-fp[data-status='ok']").count() == 3


def test_the_card_previews_the_named_line(page):
    _chip(page, "tool.py:120").hover()
    page.wait_for_selector(".oku-tooltip .okt-fp-card-window")
    rows = page.evaluate(
        "() => [...document.querySelectorAll('.oku-tooltip .okt-fp-card-row')].map(r => [+r.dataset.n, r.classList.contains('okt-fp-card-hit'), r.textContent])"
    )
    assert [n for n, _, _ in rows] == list(range(118, 130)), rows
    assert [n for n, hit, _ in rows if hit] == [120], rows
    assert rows[2][2] == "value_120 = 120", rows


def test_the_viewer_marks_the_line_and_shows_it(page):
    _chip(page, "tool.py:120").click()
    page.wait_for_function("() => document.querySelectorAll('.okt-mdview .okt-line-hit').length > 0")
    got = page.evaluate(VIEW)
    assert got["hits"] == [120], got
    assert got["visible"], got
    assert got["crumb"] == "tool.py:120", got


def test_a_range_marks_every_line_in_it(page):
    _chip(page, "tool.py:200-204").click()
    page.wait_for_function("() => document.querySelectorAll('.okt-mdview .okt-line-hit').length > 0")
    got = page.evaluate(VIEW)
    assert got["hits"] == [200, 201, 202, 203, 204], got
    assert got["visible"], got


def test_a_line_of_a_markdown_file_opens_its_source(page):
    _chip(page, "a.md:12").click()
    page.wait_for_function("() => document.querySelectorAll('.okt-mdview .okt-line-hit').length > 0")
    got = page.evaluate(VIEW)
    assert got["view"] == "source" and got["inSource"], got
    assert got["hits"] == [12], got


def test_the_editor_link_carries_the_line(page, built):
    _chip(page, "tool.py:120").click()
    page.wait_for_selector(".okt-mdview .okt-mdview-editor-pick")
    page.click(".okt-mdview-editor-pick")
    hrefs = page.evaluate(
        "() => Object.fromEntries([...document.querySelectorAll('.okt-mdview-editor-item')].map(a => [a.dataset.editor, a.getAttribute('href')]))"
    )
    assert hrefs["vscode"].endswith("/src/tool.py:120"), hrefs
    assert hrefs["zed"].endswith("/src/tool.py:120"), hrefs
    assert hrefs["idea"].endswith("tool.py&line=120"), hrefs
