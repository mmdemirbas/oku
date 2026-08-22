"""A section in the contents panel folds from the keyboard.

The fold control was a `<span class="chevron">` with the click handler
on the header row. The only keyboard-reachable thing in a section
header was the link, and the link navigates — so a reader on a keyboard
could open a section and never fold one, on a panel whose whole job is
choosing what to look at. Nothing announced the state either: no
`aria-expanded`, so a screen reader read a section as a link with a
list under it, folded or not.

The control is a real `<button>` wherever there is something to fold,
and a plain span where there is not: a disabled button in that slot
would be a tab stop that goes nowhere, and the slot exists only to keep
the numbers lined up.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

FILLER = "\n\n".join(f"Paragraph {i} of body text, long enough to scroll." for i in range(1, 9))

PAGE = f"""---
title: Contents
summary: Two sections with subsections and one without.
---

## Deep section {{#deep}}

{FILLER}

### First sub {{#deep-a}}

{FILLER}

### Second sub {{#deep-b}}

{FILLER}

## Flat section {{#flat}}

{FILLER}

## Another deep section {{#deep2}}

{FILLER}

### Third sub {{#deep2-a}}

{FILLER}
"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("tockb").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (d / "page.md").write_text(PAGE, encoding="utf-8")
    (d / "page.html").write_text(
        cli._stub_for("page", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def page(browser, served):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"{served}/page.html")
    pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    pg.wait_for_selector('.toc-list li.toc-h2[data-target="deep"]', timeout=30000)
    try:
        yield pg
    finally:
        pg.close()


def test_the_panel_has_both_kinds_of_section(page) -> None:
    """The guard: this file asserts about a section that folds and one
    that does not, and a panel holding only one kind would pass half of
    it for the wrong reason."""
    shape = page.evaluate("""() => ({
      withSubs: [...document.querySelectorAll('.toc-list li.toc-h2')]
        .filter(li => li.querySelector('.toc-sub li')).map(li => li.dataset.target),
      withoutSubs: [...document.querySelectorAll('.toc-list li.toc-h2')]
        .filter(li => !li.querySelector('.toc-sub li')).map(li => li.dataset.target),
    })""")
    assert shape["withSubs"] == ["deep", "deep2"], shape
    assert shape["withoutSubs"] == ["flat"], shape


def test_a_foldable_section_carries_a_button_that_says_its_state(page) -> None:
    got = page.evaluate("""() => {
      const li = document.querySelector('.toc-list li.toc-h2[data-target="deep"]');
      const chev = li.querySelector('.toc-head > .chevron');
      const sub = li.querySelector('.toc-sub');
      return {
        tag: chev.tagName,
        type: chev.getAttribute('type'),
        expanded: chev.getAttribute('aria-expanded'),
        expandedClass: li.classList.contains('expanded'),
        controls: chev.getAttribute('aria-controls'),
        subId: sub ? sub.id : null,
        label: chev.getAttribute('aria-label'),
        disabled: chev.disabled === true,
        tabindex: chev.getAttribute('tabindex'),
      };
    }""")
    assert got["tag"] == "BUTTON", got
    assert got["type"] == "button", got
    # Not "false": the scroll-spy has already run and the first section
    # is active on load. The invariant is agreement, not a value.
    assert got["expanded"] == str(got["expandedClass"]).lower(), got
    assert got["controls"] and got["controls"] == got["subId"], got
    assert got["label"] and "Deep section" in got["label"], got
    assert got["disabled"] is False and got["tabindex"] is None, got


def test_a_section_with_nothing_to_fold_is_not_a_tab_stop(page) -> None:
    got = page.evaluate("""() => {
      const li = document.querySelector('.toc-list li.toc-h2[data-target="flat"]');
      const chev = li.querySelector('.toc-head > .chevron');
      const cs = getComputedStyle(chev);
      return { tag: chev.tagName, hidden: chev.getAttribute('aria-hidden'),
               width: Math.round(chev.getBoundingClientRect().width),
               visibility: cs.visibility };
    }""")
    assert got["tag"] == "SPAN", got
    assert got["hidden"] == "true", got
    # The slot still holds its column, which is the only reason it is
    # rendered at all.
    assert got["width"] == 10, got
    assert got["visibility"] == "hidden", got


def test_the_titles_still_line_up_across_both_kinds(page) -> None:
    xs = page.evaluate("""() => [...document.querySelectorAll('.toc-list li.toc-h2 .toc-head > a')]
        .map(a => Math.round(a.getBoundingClientRect().x))""")
    assert len(set(xs)) == 1, xs


def test_the_keyboard_reaches_the_fold_control(page) -> None:
    """Tab order, not a `focus()` call: the chevron sits before the link
    in the header, so from the link Shift+Tab must land on it."""
    page.evaluate("""() => document.querySelector(
      '.toc-list li.toc-h2[data-target="deep"] .toc-head > a').focus()""")
    page.keyboard.press("Shift+Tab")
    where = page.evaluate("""() => {
      const a = document.activeElement;
      return { tag: a.tagName, cls: a.className, section: a.closest('li.toc-h2') ? a.closest('li.toc-h2').dataset.target : null };
    }""")
    assert where["tag"] == "BUTTON" and "chevron" in where["cls"], where
    assert where["section"] == "deep", where


@pytest.mark.parametrize("key", ["Enter", "Space"])
def test_the_fold_control_answers_enter_and_space(page, key) -> None:
    read = """() => {
      const li = document.querySelector('.toc-list li.toc-h2[data-target="deep"]');
      const chev = li.querySelector('.toc-head > .chevron');
      return { expandedClass: li.classList.contains('expanded'), aria: chev.getAttribute('aria-expanded') };
    }"""
    page.evaluate("""() => document.querySelector(
      '.toc-list li.toc-h2[data-target="deep"] .toc-head > .chevron').focus()""")
    before = page.evaluate(read)
    page.keyboard.press(key)
    page.wait_for_timeout(120)
    after = page.evaluate(read)

    assert after["expandedClass"] != before["expandedClass"], (key, before, after)
    assert after["aria"] == str(after["expandedClass"]).lower(), (key, after)


def test_the_state_the_button_reports_is_the_state_the_page_is_in(page) -> None:
    """The scroll-spy folds sections as the reader moves, and it used to
    set the class directly. Two writers, one of them silent, is how the
    announced state and the real one drift."""
    page.evaluate("() => document.getElementById('deep2').scrollIntoView()")
    page.wait_for_timeout(700)
    state = page.evaluate("""() => [...document.querySelectorAll('.toc-list li.toc-h2')].map(li => {
      const chev = li.querySelector('.toc-head > .chevron');
      return {
        section: li.dataset.target,
        cls: li.classList.contains('expanded'),
        aria: chev.tagName === 'BUTTON' ? chev.getAttribute('aria-expanded') : null,
      };
    })""")
    for row in state:
        if row["aria"] is None:
            continue
        assert row["aria"] == str(row["cls"]).lower(), state
    assert any(r["cls"] for r in state), f"the scroll-spy expanded nothing: {state}"
