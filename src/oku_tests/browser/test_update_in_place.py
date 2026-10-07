"""`OkuRenderer.update(page)` re-renders the page on screen without a reload.

An editor's preview hands the page over on every edit. A reload, or a plain
second `render()`, rebuilds every block: an open <details> closes, a table
forgets its filter, every diagram is drawn again, and the reader is put back
at the top or a pixel offset that no longer points at what they were reading.
`update` keeps the live node of every block whose markup did not change, so
all of that survives an edit elsewhere, and it puts the block the reader was
looking at back at the same height on the screen.

The two versions of the page come from `oku preview`, which is how the
IntelliJ plugin gets them: the page JSON it writes beside the HTML is what
gets handed to `update`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ._wait import page_quiet

SECTIONS = 24
LONG = "A paragraph of text that takes up some room. " * 30


def _body(
    *, inserted: str = "", s5: str = "The fifth section, as first written.", h7: str = "Section 7"
) -> str:
    parts = ["---\ntitle: Update\n---\n"]
    for i in range(SECTIONS):
        title = h7 if i == 7 else f"Section {i}"
        parts.append(f"## {title} {{#s{i}}}\n\n{LONG}\n")
        if i == 2:
            parts.append(f"{inserted}\n")
            parts.append(
                "<details id='kept-open'>\n<summary>More</summary>\n\nHidden until opened.\n\n</details>\n"
            )
            parts.append(
                "| Name | Kind |\n|---|---|\n| alpha | one |\n| beta | two |\n| gamma | three |\n| delta | four |\n"
            )
        if i == 5:
            parts.append(f"{s5}\n")
    return "\n".join(parts)


@pytest.fixture(scope="module")
def versions(tmp_path_factory) -> dict:
    """Four versions of one page out of one `oku preview --serve` session,
    the buffer changing and the file on disk not — an editor's case."""
    root = tmp_path_factory.mktemp("update")
    (root / ".git").mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name": "u"}', encoding="utf-8")
    md = docs / "update.md"
    md.write_text(_body(), encoding="utf-8")
    texts = {
        "first": _body(),
        "edited": _body(s5="The fifth section, rewritten while the reader was elsewhere."),
        "longer_above": _body(inserted=LONG * 3),
        "renamed": _body(h7="Section seven, renamed"),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "oku.cli", "preview", "--serve", "--out", str(root / "out")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdout.readline()  # the greeting
    pages: dict = {}
    first: dict = {}
    try:
        for name, text in texts.items():
            proc.stdin.write(json.dumps({"id": name, "path": str(md), "text": text}) + "\n")
            proc.stdin.flush()
            reply = json.loads(proc.stdout.readline())
            assert "error" not in reply, reply
            if name == "first":
                # Every render of the page writes the same two files, so the
                # first version's HTML is kept as a copy beside them, where its
                # relative paths still resolve.
                html = Path(reply["html"])
                kept = html.with_name("update-first.html")
                kept.write_text(html.read_text(encoding="utf-8"), encoding="utf-8")
                first = {**reply, "html": str(kept)}
                pages["first"] = first
                continue
            # The fixture's premise: these differ from the first only in the page.
            assert reply["shell"] == first["shell"], name
            pages[name] = json.loads(Path(reply["page"]).read_text(encoding="utf-8"))
    finally:
        proc.stdin.close()
        proc.wait(timeout=60)
    return pages


def _open(browser, versions: dict):
    context = browser.new_context(viewport={"width": 1100, "height": 900})
    page = context.new_page()
    page.goto(Path(versions["first"]["html"]).as_uri(), wait_until="load")
    page_quiet(page)
    return context, page


def _update(page, new_page: dict) -> dict:
    return page.evaluate(
        """(p) => {
          let fired = 0;
          const count = () => { fired++; };
          window.addEventListener('oku:rendered', count);
          const result = new OkuRenderer({}).update(p);
          window.removeEventListener('oku:rendered', count);
          return { result, fired };
        }""",
        new_page,
    )


def test_an_edit_keeps_every_block_it_did_not_touch(browser, versions) -> None:
    context, page = _open(browser, versions)
    try:
        # What the reader did, and a mark on every block to see which survive.
        page.evaluate("() => { document.getElementById('kept-open').open = true; }")
        page.evaluate(
            """() => document.querySelectorAll('main section > *, main > :not(section)')
                 .forEach((el, i) => { el.__probe = i; })"""
        )
        marked = page.evaluate("() => document.querySelectorAll('main section > *').length")
        page.fill(".okt-table-wrap input[type=search]", "gam")
        rows_before = page.evaluate(
            "() => [...document.querySelectorAll('.okt-table-wrap tbody tr')].filter(r => r.offsetParent).length"
        )
        assert rows_before == 1

        out = _update(page, versions["edited"])
        assert out["fired"] == 1
        assert out["result"]["kept"] >= marked - 1, out
        assert "rewritten while the reader was elsewhere" in page.inner_text("#s5")
        assert "as first written" not in page.inner_text("#s5")
        # Every other block is the node it was, with what the reader did to it.
        lost = page.evaluate(
            """() => [...document.querySelectorAll('main section > *')]
                 .filter(el => el.__probe === undefined).map(el => el.textContent.slice(0, 40))"""
        )
        assert len(lost) == 1 and "rewritten" in lost[0], lost
        assert page.evaluate("() => document.querySelectorAll('main section > *').length") == marked
        assert page.evaluate("() => document.getElementById('kept-open').open") is True
        assert page.input_value(".okt-table-wrap input[type=search]") == "gam"
    finally:
        context.close()


def test_the_reader_stays_on_what_they_were_reading(browser, versions) -> None:
    context, page = _open(browser, versions)
    try:
        page.evaluate(
            "() => window.scrollTo({top: document.getElementById('s15').offsetTop + 120, behavior: 'instant'})"
        )
        page.wait_for_timeout(100)
        before = page.evaluate(
            "() => [window.scrollY, document.getElementById('s15').getBoundingClientRect().top]"
        )

        page.evaluate(
            "() => document.querySelectorAll('main section > *').forEach((el) => { el.__probe = 1; })"
        )
        out = _update(page, versions["longer_above"])
        built = page.evaluate(
            """() => [...document.querySelectorAll('main section > *')]
                 .filter(el => el.__probe === undefined).map(el => el.outerHTML.slice(0, 120))"""
        )
        # The inserted paragraph, and nothing else in the body. (The cover is
        # rebuilt too: its reading time grew with the page.)
        assert len(built) == 1 and "takes up some room" in built[0], built
        assert out["result"]["built"] <= 2, out
        page.wait_for_timeout(100)
        after = page.evaluate(
            "() => [window.scrollY, document.getElementById('s15').getBoundingClientRect().top]"
        )
        # The page grew above the reader by three long paragraphs...
        assert after[0] - before[0] > 500, (before, after)
        # ...and what they were reading did not move on the screen.
        assert abs(after[1] - before[1]) <= 1, (before, after)
    finally:
        context.close()


def test_a_renamed_heading_reaches_the_contents(browser, versions) -> None:
    context, page = _open(browser, versions)
    try:
        assert page.locator("page-toc").get_by_text("Section 7", exact=True).count() == 1
        _update(page, versions["renamed"])
        page.wait_for_timeout(100)
        assert page.locator("page-toc").get_by_text("Section seven, renamed", exact=True).count() == 1
        assert page.locator("page-toc").get_by_text("Section 7", exact=True).count() == 0
        # textContent of the heading's own text node: the kit hangs an anchor link off it.
        assert page.evaluate("() => document.querySelector('#s7 h2').firstChild.textContent") == (
            "Section seven, renamed"
        )
    finally:
        context.close()


def test_a_page_it_refuses_leaves_the_screen_as_it_was(browser, versions) -> None:
    context, page = _open(browser, versions)
    try:
        before = page.evaluate("() => document.querySelector('main').innerHTML.length")
        out = _update(page, {"k": "not-a-page"})
        assert out["result"] is None
        assert out["fired"] == 0
        assert page.evaluate("() => document.querySelector('main').innerHTML.length") == before
    finally:
        context.close()
