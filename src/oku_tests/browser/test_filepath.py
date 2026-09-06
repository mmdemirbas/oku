"""A path in a document is a thing the reader can look inside.

Documents mention files constantly, and a path in a code span is a dead
end: the reader leaves the page, finds the file, comes back. The chip
keeps the mention and adds the file — hover for a preview, click for the
whole thing, copy the path either way.

Everything asserted here follows from one constraint: **the bytes travel
with the page**. No delivery mode can fetch the file at read time —
`oku serve` and `dist/site` serve the docs tree while the interesting
references point outside it, and a standalone page is opened over
file://, where fetch is refused before a request is made. So this file
runs against the standalone build, the mode with the least to work with.
A preview that opens there opens everywhere.

The other half is what happens when a reference does NOT resolve. The
failure mode of this primitive has to be "the preview does not open",
never "the page lost the reference the author wrote" — so a missing file
still renders a chip, and that chip still copies.
"""

from __future__ import annotations

from . import _wait
from ._wait import page_quiet

import argparse
import base64
import os
import subprocess
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

# An 8x8 PNG. Small enough to inline, real enough that a browser
# decoding it reports a naturalWidth.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAHUlEQVR4nGP8//8/"
    "AzZgYsCjaVTiPyMj47//2CQAcaMHAWfJDQwAAAAASUVORK5CYII="
)

PROGRAM = 'def hello(name):\n    """Say hello."""\n    return f"hello {name}"\n'

NOTE_MD = """---
title: The Note
summary: A file reached through a path chip.
---

## Inside {#inside}

The note's own body.
"""

PAGE_MD = """---
title: Paths
summary: A page that points at files.
---

## Files {#files}

The program is [`../src/hello.py`](#f/../src/hello.py), the note is
[`notes.md`](#f/notes.md), and the shot is [`tiny.png`](#f/tiny.png).

Nothing is at [`nope.txt`](#f/nope.txt).
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """A real project, because the fence the resolver applies is the
    project root: `.git` decides how far a reference may reach, and a
    tree without one would test a different rule than the one that
    ships."""
    root = tmp_path_factory.mktemp("filepath")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / "src").mkdir()
    (root / "src" / "hello.py").write_text(PROGRAM, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "tiny.png").write_bytes(TINY_PNG)
    (docs / "notes.md").write_text(NOTE_MD, encoding="utf-8")
    (docs / "notes.html").write_text(cli._stub_for("The Note"), encoding="utf-8")
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Paths"), encoding="utf-8")
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
    yield page
    context.close()


def chip(page, path):
    return page.locator(f'oku-filepath[path="{path}"]')


def _open(page, path):
    """Click a chip's path and wait for the frame.

    The lightbox is one long-lived overlay that toggles an `open` class,
    not an element that comes and goes — so `.okt-lightbox` alone is
    always there and asserting on its presence would assert nothing."""
    page.click(f'oku-filepath[path="{path}"] .okt-fp-label')
    # Two outcomes, and the wait has to admit both: a chip with a file
    # behind it opens the frame, one with nothing pins its card instead.
    # Waiting only for the frame would hang the whole ceiling on the
    # missing-file case, which is a test this file has.
    _wait.until(
        page,
        "() => !!document.querySelector('.okt-lightbox.open') || !!document.querySelector('.oku-tooltip')",
        what="the chip opened the frame or pinned its card",
    )


def _close(page):
    """Escape closes both the frame and a pinned card, and this asserts
    both are gone. A chip with nothing to open pins its card instead —
    which is the right behaviour and would otherwise sit over the next
    chip a test reaches for."""
    page.keyboard.press("Escape")
    _wait.until(
        page,
        "() => !document.querySelector('.okt-lightbox.open') && !document.querySelector('.oku-tooltip')",
        what="Escape closed both the frame and any pinned card",
    )
    assert page.locator(".okt-lightbox.open").count() == 0
    assert page.locator(".oku-tooltip").count() == 0


def _card(page, path):
    """Hover a chip and return the tooltip's text, then leave."""
    # Clear whatever is up first. "Is there a card" answers yes while
    # the PREVIOUS chip's card is still on screen, so a wait on presence
    # alone reads the last test's tooltip and passes — which is what this
    # helper did the moment its fixed sleep came out, on a module where
    # the test before it hovers and never leaves.
    page.mouse.move(2, 2)
    _wait.until(
        page,
        "() => !document.querySelector('.oku-tooltip')",
        what="any card left by an earlier hover went away",
    )
    page.hover(f'oku-filepath[path="{path}"] .okt-fp-label')
    _wait.until(
        page,
        "() => { const t = document.querySelector('.oku-tooltip');"
        " return !!t && t.textContent.trim().length > 0; }",
        what="the chip's card appeared with something written on it",
    )
    text = page.locator(".oku-tooltip").inner_text()
    page.mouse.move(2, 2)
    _wait.until(
        page,
        "() => !document.querySelector('.oku-tooltip')",
        what="the card went away when the pointer left",
    )
    return text


def test_every_reference_became_a_chip(opened):
    """Including the one that resolved to nothing. A reference the author
    wrote is a reference the page keeps."""
    got = opened.evaluate(
        """() => [...document.querySelectorAll('oku-filepath')].map(el => [
             el.getAttribute('path'), el.getAttribute('data-status'),
             el.getAttribute('data-kind'),
             el.querySelector('.okt-fp-label').textContent,
           ])"""
    )
    assert got == [
        ["../src/hello.py", "ok", "text", "../src/hello.py"],
        ["notes.md", "ok", "markdown", "notes.md"],
        ["tiny.png", "ok", "image", "tiny.png"],
        ["nope.txt", "missing", "unknown", "nope.txt"],
    ]


def test_the_chip_does_not_push_the_line_apart(opened):
    """It sits where a code span sat. A control tall enough to grow the
    line box would make every mention of a file the loudest thing in its
    paragraph, which is the opposite of what the author meant by writing
    a path."""
    box = chip(opened, "notes.md").bounding_box()
    line = opened.evaluate(
        """() => {
             const p = document.querySelector('oku-filepath').closest('p');
             return parseFloat(getComputedStyle(p).lineHeight);
           }"""
    )
    assert box["height"] <= line + 6, (box, line)


def test_the_copy_target_is_bigger_than_the_glyph(opened):
    """12px of icon, because the line cannot afford more; 26px of target,
    because a pointer cannot afford less. The pseudo-element is what
    separates the two, so the check is what the browser hits at the
    corners, not what the box measures."""
    hit = opened.evaluate(
        """() => {
             const btn = document.querySelector('oku-filepath .okt-fp-copy');
             const r = btn.getBoundingClientRect();
             const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
             return [[cx - 11, cy - 11], [cx + 11, cy + 11]].map(([x, y]) => {
               const el = document.elementFromPoint(x, y);
               return !!(el && el.closest('.okt-fp-copy'));
             });
           }"""
    )
    assert hit == [True, True]


def test_hovering_a_program_shows_the_top_of_it(opened):
    text = _card(opened, "../src/hello.py")
    assert "hello.py" in text
    assert "def hello(name):" in text
    # Kind, size and length — the three things that decide whether the
    # reader wants the popup at all.
    assert "Text" in text and "3 lines" in text


def test_hovering_an_image_shows_the_image(opened):
    opened.hover('oku-filepath[path="tiny.png"] .okt-fp-label')
    # The image has to have DECODED, not just been inserted — the
    # assertion below reads naturalWidth, which is 0 until it has.
    _wait.until(
        opened,
        "() => { const i = document.querySelector('.oku-tooltip img.okt-fp-media');"
        " return !!i && i.naturalWidth > 0; }",
        what="the card's image loaded",
    )
    shown = opened.evaluate(
        """() => {
             const img = document.querySelector('.oku-tooltip img.okt-fp-media');
             return img ? [img.naturalWidth, img.naturalHeight] : null;
           }"""
    )
    opened.mouse.move(2, 2)
    assert shown == [8, 8]


def test_a_reference_that_resolved_to_nothing_says_so(opened):
    """And says it on hover, where the reader already is — not by
    doing nothing when they click."""
    text = _card(opened, "nope.txt")
    assert "No file at this path" in text


def test_clicking_a_program_opens_the_whole_file(opened):
    _open(opened, "../src/hello.py")
    body = opened.locator(".okt-lightbox.open .okt-fp-view-pre").inner_text()
    # Not an equality against the file: the block picks up the kit's
    # line-number gutter, and the gutter is in `inner_text` even though
    # `user-select: none` keeps it out of a copy.
    for line in PROGRAM.strip().split("\n"):
        assert line.strip() in body, (line, body)
    # Prism ran, and the language came off the extension.
    assert opened.locator(".okt-lightbox.open .okt-fp-view-pre code.language-python").count() == 1
    _close(opened)


def test_clicking_a_markdown_file_opens_the_viewer(opened):
    """Not a <pre> of markdown source. The kit renders markdown, the
    viewer is where it does it, and a .md reached through a path chip
    should be the same experience as one reached through a link."""
    _open(opened, "notes.md")
    view = opened.locator(".okt-lightbox.open .okt-mdview")
    assert view.count() == 1
    assert view.locator(".okt-mdview-title").inner_text() == "The Note"
    assert view.locator(".okt-mdview-rendered h2").inner_text().startswith("Inside")
    _close(opened)


def test_clicking_an_image_opens_it_full_size(opened):
    _open(opened, "tiny.png")
    got = opened.evaluate(
        """() => {
             const img = document.querySelector('.okt-lightbox.open img.okt-fp-media');
             return img ? img.naturalWidth : 0;
           }"""
    )
    assert got == 8
    _close(opened)


def test_a_missing_file_does_not_open_an_empty_frame(opened):
    """There is nothing to show, and a popup that shows nothing reads as
    a broken control rather than an absent file."""
    _open(opened, "nope.txt")
    assert opened.locator(".okt-lightbox.open").count() == 0
    # The click still does something: the card pins, so the reason the
    # preview is absent stays on screen instead of the click reading as
    # a control that did nothing.
    assert opened.locator(".oku-tooltip.pinned").count() == 1
    _close(opened)


def test_the_copy_button_copies_the_path_and_nothing_opens(opened):
    """The path is what the reader pastes into a terminal, and the chip
    is also a click target — so the button has to be the one thing on it
    that does not open the file."""
    btn = chip(opened, "../src/hello.py").locator(".okt-fp-copy")
    btn.click()
    flash = ".okt-fp-copy"
    _wait.until(
        opened,
        f"() => [...document.querySelectorAll({flash!r})].some((b) => b.classList.contains('okt-flash-ok'))",
        what="the copy button flashed",
    )
    assert opened.evaluate("() => navigator.clipboard.readText()") == "../src/hello.py"
    assert opened.locator(".okt-lightbox.open").count() == 0
    _wait.until(
        opened,
        f"() => [...document.querySelectorAll({flash!r})].every((b) => !b.classList.contains('okt-flash-ok'))",
        what="the flash went back off",
    )
    assert "okt-flash-ok" not in (btn.get_attribute("class") or "")


def test_closing_the_popup_leaves_nothing_under_the_cursor(opened):
    """`mouseenter` fires when a layer above an element goes away — the
    cursor has not moved, but what is under it has. So closing the popup
    a chip opened put that chip's own card back under a stationary
    pointer: the thing the reader had just dismissed, returning as a
    tooltip. The controller now wants a `mousemove` behind the enter.
    """
    _open(opened, "tiny.png")
    assert opened.locator(".okt-lightbox.open").count() == 1
    opened.keyboard.press("Escape")
    # The one fixed wait in this file that has to stay one. Everything
    # else here waits for something to APPEAR; this waits to prove
    # something never does, and an absence cannot be waited for — a
    # stability poll starting at zero returns while the show delay is
    # still running and passes without testing anything. Outlasting both
    # delays is the assertion.
    opened.wait_for_timeout(700)
    assert opened.locator(".oku-tooltip").count() == 0


def test_the_chip_opens_from_the_keyboard(opened):
    """`role="button"` on anything that is not a `<button>` promises
    keyboard activation the browser does not provide: Enter and Space
    fire click on a real button and on nothing else. The chip was
    reachable by Tab and could not be opened."""
    opened.focus('oku-filepath[path="../src/hello.py"] .okt-fp-label')
    opened.keyboard.press("Enter")
    _wait.until(
        opened,
        "() => !!document.querySelector('.okt-lightbox.open .okt-fp-view-pre')",
        what="Enter opened the file the way a click does",
    )
    assert opened.locator(".okt-lightbox.open .okt-fp-view-pre").count() == 1
    _close(opened)


def test_a_chip_costs_two_tab_stops_and_not_three(opened):
    """The tooltip controller makes its trigger focusable, and the chip
    is the trigger — so a chip whose label is already a control had
    three stops in it, and a paragraph mentioning four files cost a
    keyboard reader twelve presses to read past.

    The two that remain are the two actions: open the file, copy the
    path. A chip with nothing to open keeps its own stop instead, since
    the card is then the only thing it has.
    """
    got = opened.evaluate(
        """() => {
             const stops = el => [el, ...el.querySelectorAll('*')]
               .filter(n => n.hasAttribute('tabindex') || n.tagName === 'BUTTON')
               .map(n => n.className || n.tagName.toLowerCase());
             return {
               ok: stops(document.querySelector('oku-filepath[path="tiny.png"]')),
               missing: stops(document.querySelector('oku-filepath[path="nope.txt"]')),
             };
           }"""
    )
    assert got["ok"] == ["okt-fp-label", "okt-fp-copy"], got
    assert got["missing"] == ["okt-fp", "okt-fp-copy"], got
