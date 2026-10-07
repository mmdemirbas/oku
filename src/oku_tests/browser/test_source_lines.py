"""The page beside an editor knows which source line each block came from.

The IntelliJ plugin shows the page next to its markdown. Scrolling one left
the other where it was, so a reader editing line 300 looked at the top of
the page, and a reader who found something on the page had to search the
source for it. `oku preview` now writes where each block starts
(`m._lines`), the kit binds that line to every block it draws, and two
functions answer the two directions: `OkuRenderer.scrollToLine(line)` puts
a source line at the top of the window, `OkuRenderer.lineAt(y)` says which
line is at a height. A double-click on the page hands that line to the
host's `revealLine`.

The lines must survive what the source does to them: a link definition is
removed before the markdown is parsed, so every line after it is counted in
a text that no longer has it; a typed fence becomes a block of its own; and
an edit above a block moves its line while `update()` keeps its node.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ._wait import page_quiet

LONG = "A paragraph of text that takes up some room. " * 12
# A line chart: drawn by <oku-chart>, which takes a double-click itself.
CHART = '{"type":"line","series":[{"label":"a","data":[{"x":1,"y":2},{"x":2,"y":3},{"x":3,"y":1}]}]}'


def _source(inserted: str = "") -> str:
    return "\n".join(
        [
            "---",
            "title: Lines",
            "---",
            "",
            f"{inserted}Opening paragraph. {LONG}",
            "",
            "## First {#first}",
            "",
            "[site]: https://example.org",
            "",
            f"After a [definition][site]. {LONG}",
            "",
            "```oku-chart",
            CHART,
            "```",
            "",
            "- one",
            "- two",
            "",
            "## Second {#second}",
            "",
            "```python",
            "print(1)",
            "print(2)",
            "```",
            "",
            f"Closing paragraph. {LONG}",
            "",
            *[f"## Filler {i}\n\n{LONG}\n" for i in range(8)],
        ]
    )


def _line_of(text: str, needle: str) -> int:
    return next(i for i, line in enumerate(text.split("\n"), start=1) if line.startswith(needle))


@pytest.fixture(scope="module")
def preview(tmp_path_factory) -> dict:
    """Two versions of one page from one `oku preview --serve` session; the
    second has four lines inserted at the top of the body."""
    root = tmp_path_factory.mktemp("lines")
    (root / ".git").mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name": "l"}', encoding="utf-8")
    md = docs / "lines.md"
    first, second = _source(), _source(inserted="Four\nlines\nabove\n\n")
    md.write_text(first, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "oku.cli", "preview", "--serve", "--out", str(root / "out")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdout.readline()  # the greeting
    out: dict = {"first": first, "second": second}
    try:
        for name, text in (("first", first), ("second", second)):
            proc.stdin.write(json.dumps({"id": name, "path": str(md), "text": text}) + "\n")
            proc.stdin.flush()
            reply = json.loads(proc.stdout.readline())
            assert "error" not in reply, reply
            if name == "first":
                html = Path(reply["html"])
                kept = html.with_name("lines-first.html")
                kept.write_text(html.read_text(encoding="utf-8"), encoding="utf-8")
                out["html"] = str(kept)
            else:
                out["page"] = json.loads(Path(reply["page"]).read_text(encoding="utf-8"))
    finally:
        proc.stdin.close()
        proc.wait(timeout=60)
    return out


@pytest.fixture
def page(browser, preview):
    context = browser.new_context(viewport={"width": 1100, "height": 700})
    pg = context.new_page()
    pg.goto(Path(preview["html"]).as_uri(), wait_until="load")
    page_quiet(pg)
    yield pg
    context.close()


# What to look for on the page, and the source line it starts on.
BLOCKS = {
    "opening": ("main > p", "Opening paragraph."),
    "first": ("#first > h2", "## First"),
    "after-definition": ("#first > p", "After a [definition]"),
    "chart": ("#first > oku-chart", "```oku-chart"),
    "list": ("#first > ul", "- one"),
    "second": ("#second > h2", "## Second"),
    "code": ("#second > .okt-pre-host", "```python"),
    "closing": ("#second > p", "Closing paragraph."),
}


def _line_at(page, selector: str) -> float | None:
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          return OkuRenderer.lineAt(el.getBoundingClientRect().top + 0.5);
        }""",
        selector,
    )


@pytest.mark.parametrize("name", list(BLOCKS))
def test_every_block_knows_the_line_it_starts_on(page, preview, name) -> None:
    selector, needle = BLOCKS[name]
    expected = _line_of(preview["first"], needle)
    page.evaluate(
        "(sel) => document.querySelector(sel).scrollIntoView({block: 'center', behavior: 'instant'})",
        selector,
    )
    got = _line_at(page, selector)
    assert got is not None and int(got) == expected, (name, got, expected)


@pytest.mark.parametrize("name", ["first", "chart", "second", "closing"])
def test_a_source_line_lands_at_the_top_of_the_window(page, preview, name) -> None:
    selector, needle = BLOCKS[name]
    assert page.evaluate("(l) => OkuRenderer.scrollToLine(l)", _line_of(preview["first"], needle)) is True
    top = page.evaluate("(sel) => document.querySelector(sel).getBoundingClientRect().top", selector)
    assert abs(top) <= 1, (name, top)


def test_between_two_blocks_the_page_moves_with_the_line(page, preview) -> None:
    """A long block scrolls through as its lines go by, rather than the page
    jumping once per block — and lineAt reads back the line that was asked."""
    start = _line_of(preview["first"], "Closing paragraph.")
    tops = []
    for line in (start, start + 0.5, start + 1, start + 1.5):
        page.evaluate("(l) => OkuRenderer.scrollToLine(l)", line)
        tops.append(page.evaluate("() => window.scrollY"))
        assert abs(page.evaluate("() => OkuRenderer.lineAt(0)") - line) < 0.05, line
    assert tops == sorted(tops) and len(set(tops)) == len(tops), tops


def test_an_edit_above_moves_the_lines_of_the_blocks_it_kept(page, preview) -> None:
    page.evaluate("() => document.querySelectorAll('main section > *').forEach((el) => { el.__probe = 1; })")
    page.evaluate("(p) => new OkuRenderer({}).update(p)", preview["page"])
    # The heading is the node it was, and it is four lines further down.
    assert page.evaluate("() => document.querySelector('#second > h2').__probe") == 1
    assert int(_line_at(page, "#second > h2")) == _line_of(preview["second"], "## Second")
    assert _line_of(preview["second"], "## Second") == _line_of(preview["first"], "## Second") + 4


def test_a_double_click_shows_the_line_in_the_hosts_editor(page, preview) -> None:
    page.evaluate(
        """() => {
          window.__okuReveals = [];
          window.__okuHost = { name: 'Test IDE', openFile: () => false,
                               revealLine: (line) => { window.__okuReveals.push(line); } };
        }"""
    )
    page.evaluate("() => document.querySelector('#second > h2').scrollIntoView({behavior: 'instant'})")
    page.dblclick("#second > h2", position={"x": 10, "y": 4})
    page.dblclick("#first > oku-chart", position={"x": 5, "y": 5})  # a chart's own double-click
    assert page.evaluate("() => window.__okuReveals") == [_line_of(preview["first"], "## Second")]


def test_a_page_built_for_reading_has_no_lines_to_follow(page) -> None:
    """Without `m._lines` — every page `oku build` ships — nothing is bound,
    and both directions say so instead of guessing."""
    page.evaluate(
        """() => {
          const page = JSON.parse(document.getElementById('__oku_page__').textContent);
          delete page.m._lines;
          new OkuRenderer({}).render(page);
        }"""
    )
    assert page.evaluate("() => OkuRenderer.scrollToLine(10)") is False
    assert page.evaluate("() => OkuRenderer.lineAt(10)") is None


# The way back: the reader scrolling the page moves the editor. The host
# records every line the page reports.
WITH_PAGE_TOP = """() => {
  window.__okuTops = [];
  window.__okuHost = { name: 'Test IDE', openFile: () => false, revealLine: () => {},
                       pageTop: (line) => { window.__okuTops.push(line); } };
}"""

# Resolves once scrollY has held still for three frames: a wheel scroll
# may be animated, and a report goes out on the frame after a scroll.
SETTLED = """() => new Promise((done) => {
  let last = -1, still = 0, frames = 0;
  const tick = () => {
    still = window.scrollY === last ? still + 1 : 0;
    last = window.scrollY;
    if (still >= 3 || ++frames > 240) done(window.scrollY); else requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
})"""


def _wheel(page, dy: int) -> None:
    page.mouse.move(400, 300)
    page.mouse.wheel(0, dy)
    page.evaluate(SETTLED)


def test_the_reader_scrolling_the_page_tells_the_host_the_line_at_its_top(page) -> None:
    page.evaluate(WITH_PAGE_TOP)
    _wheel(page, 600)
    tops = page.evaluate("() => window.__okuTops")
    assert tops, "a wheel scroll of the page reported nothing"
    assert abs(tops[-1] - page.evaluate("() => OkuRenderer.lineAt(0)")) < 0.01, tops


def test_a_page_the_host_placed_is_not_reported_back(page, preview) -> None:
    """The editor puts the page where it is; reporting that would move the
    editor to where the page landed, and the two would chase each other —
    even when the reader had just scrolled the page."""
    page.evaluate(WITH_PAGE_TOP)
    _wheel(page, 300)
    page.evaluate("() => { window.__okuTops = []; }")
    page.evaluate("(l) => OkuRenderer.scrollToLine(l)", _line_of(preview["first"], "## Second"))
    page.evaluate(SETTLED)
    assert page.evaluate("() => window.__okuTops") == []


def test_a_scroll_nobody_made_on_the_page_is_not_reported(page) -> None:
    page.evaluate(WITH_PAGE_TOP)
    page.evaluate("() => window.scrollTo({top: 500, behavior: 'instant'})")
    page.evaluate(SETTLED)
    assert page.evaluate("() => window.__okuTops") == []
    # Nor one long after the reader last touched the page: the kit keeping
    # the reader's place across an update is a scroll of the same kind.
    # The wait IS the condition under test (the page counts a second).
    _wheel(page, 200)
    page.wait_for_timeout(1300)
    page.evaluate("() => { window.__okuTops = []; window.scrollTo({top: 900, behavior: 'instant'}); }")
    page.evaluate(SETTLED)
    assert page.evaluate("() => window.__okuTops") == []


def test_after_the_host_placed_the_page_the_readers_same_line_is_reported_again(page, preview) -> None:
    page.evaluate(WITH_PAGE_TOP)
    _wheel(page, 600)
    first = page.evaluate("() => window.__okuTops.at(-1)")
    y = page.evaluate("() => window.scrollY")
    page.evaluate("(l) => OkuRenderer.scrollToLine(l)", _line_of(preview["first"], "Closing paragraph."))
    page.evaluate(SETTLED)
    page.evaluate("() => { window.__okuTops = []; }")
    _wheel(page, int(y - page.evaluate("() => window.scrollY")))
    assert page.evaluate("() => window.scrollY") == y
    assert page.evaluate("() => window.__okuTops") == [first]
