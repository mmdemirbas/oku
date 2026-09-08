"""Chrome the kit hangs off content must not become content.

Three separate places read a live element and handed what they found to
the reader — after some other pass had put its own furniture inside it.
Each renders as a plausible-looking wrong answer rather than an error,
which is why all three survived.
"""

from __future__ import annotations

from ._wait import measured, page_quiet, scroll_stable, until

import pytest


@pytest.fixture()
def clipboard_page(browser):
    """The copy button writes to the clipboard, which needs permission."""
    context = browser.new_context(
        viewport={"width": 1400, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = context.new_page()
    yield page
    context.close()


def test_copying_an_annotated_block_yields_the_program(clipboard_page, site_url):
    """`oku-annotated-code` puts its marker chips and its hover tooltips
    — the full annotation prose — inside `<code>`. The shared copy pass
    read `code.textContent` at click time, so what the reader pasted was
    the commentary interleaved with the source and did not parse:

        1const creates a block-scoped binding.const x = 1; //
        2Function body — hovering this chip…function greet(name) {

    The block publishes its own source now; everything else still reads
    the DOM."""
    page = clipboard_page
    page.goto(f"{site_url}/docs/reference.html")
    page.wait_for_selector("oku-annotated-code")
    page_quiet(page)
    page.evaluate("() => document.querySelector('oku-annotated-code').scrollIntoView()")
    scroll_stable(page)
    page.hover("oku-annotated-code .okt-pre-host")
    page.click("oku-annotated-code .okt-pre-host .copy-btn")
    # The write is async and the button says when it landed: this one
    # marks itself `copied` or `error` (the copy-REGION button next to it
    # in the same file uses `is-copied` / `is-failed` — two mechanisms,
    # and the first guess here waited for the other one's class).
    # Waiting for either outcome means a refused clipboard fails as a
    # refused clipboard rather than as an empty paste.
    until(
        page,
        "() => { const b = document.querySelector('oku-annotated-code .okt-pre-host .copy-btn');"
        "        return b.classList.contains('copied') || b.classList.contains('error'); }",
        what="the copy button reported an outcome",
    )
    assert page.evaluate(
        "() => document.querySelector('oku-annotated-code .okt-pre-host .copy-btn')"
        ".classList.contains('copied')"
    ), "the copy failed rather than landing"

    text = page.evaluate("() => navigator.clipboard.readText()")

    assert "const x = 1;" in text, text
    assert "block-scoped binding" not in text, text
    assert "hovering this chip" not in text, text
    # The inline `(1)` marker is part of the author's source and belongs
    # in the paste; the chip that replaced it on screen does not.
    assert text.strip().endswith("}"), text


@pytest.mark.parametrize("view", ["cards", "list", "board"])
def test_no_column_grabber_reaches_a_view_without_columns(page, site_url, view):
    """The table's header markup is cloned into the Cards, List and Board
    views as key labels. Read raw it carried a trailing
    `<span class="okt-col-resize">`, which is `position: absolute` with a
    `static` parent there — so it resolved against `.okt-table-wrap` and
    painted a full-height ew-resize bar down the right edge of a view
    that has no columns. 192 of them, and dead: a string clone carries
    none of the drag listeners."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{site_url}/docs/tables.html")
    page.wait_for_selector("main section")
    page_quiet(page)

    strays = page.evaluate(
        """(view) => {
            const btn = document.querySelector('.okt-view-btn[data-view="' + view + '"]');
            if (!btn) return null;
            btn.click();
            return document.querySelectorAll(
              '.okt-card-key .okt-col-resize,'
              + ' .okt-board-card-key .okt-col-resize,'
              + ' .okt-table-list th .okt-col-resize').length;
        }""",
        view,
    )

    assert strays is not None, f"no {view} view button on the page"
    assert strays == 0, f"{strays} column grabbers leaked into the {view} view"


def test_search_results_are_not_titled_with_the_permalink(page, site_url):
    """buildTOC appends `<a class="permalink">#</a>` to every heading.
    In-page search read `heading.textContent` straight off it, so every
    result was titled "Prose primitives#" — and a query of "#" reported
    one match per heading on the page."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{site_url}/docs/reference.html")
    page.wait_for_selector("main section")
    page_quiet(page)
    page.keyboard.press("Control+k")
    # The panel is built on first open, so the type below has nowhere to
    # go until its input exists and holds focus.
    until(
        page,
        "() => { const i = document.querySelector('.search-input');"
        "        return !!i && document.activeElement === i; }",
        what="the search panel opened and took focus",
    )
    page.keyboard.type("heading")

    # The query is debounced and the results are rendered in a pass of
    # their own, so the wait and the assertion read ONE expression: a
    # test that settled on the panel and measured the results could
    # measure them empty.
    trailing = measured(
        page,
        """() => [...document.querySelectorAll('[class*=search] *')]
             .map(e => e.textContent.trim())
             .filter(s => s && s.length < 60 && s.endsWith('#'))
             .slice(0, 6)""",
    )

    assert trailing == [], trailing


def test_the_heading_helper_strips_both_kinds_of_chrome(page, site_url):
    """Six places needed a heading's own words, and each grew its own
    copy of the same two removals — except search, which grew none, and
    the TOC's h3 entry, which patched the symptom with a trailing-hash
    regex. One helper now, so the next consumer inherits the rule."""
    page.goto(f"{site_url}/docs/reference.html")
    page.wait_for_selector("main section")
    page_quiet(page)

    got = page.evaluate(
        """() => {
            const h2 = document.querySelector('main section h2');
            return {
                raw: (h2.textContent || '').trim(),
                cleaned: _okuHeadingText(h2),
                hasPermalink: !!h2.querySelector('.permalink'),
            };
        }"""
    )

    assert got["hasPermalink"], "fixture heading carries no permalink to strip"
    assert got["raw"].endswith("#"), got["raw"]
    assert not got["cleaned"].endswith("#"), got["cleaned"]
    assert got["cleaned"] and got["cleaned"] in got["raw"]
