"""The warning indicator says something is wrong with THIS document.

Three delivered documents came back from a reader carrying an alarm
badge. Behind it: `ResizeObserver loop completed with undelivered
notifications` twice on two of them, and `Script error. @ ?:0` on the
third. Nothing was wrong with any of the three.

Neither line is a document defect. A ResizeObserver notice is the
browser saying it deferred the rest of a delivery pass to the next
frame — the spec's own wording, nothing threw, the layout settles. And
an error with no filename and no error object is the cross-origin
sanitised form, which the page is not allowed to read: over file://
that is the kit's own vendored bundles, and everywhere it is a script
a browser extension injected. The reader can act on neither, and an
indicator that cries wolf is the one nobody opens when a diagram
really does fail to parse.

So both go to the console instead, once per distinct message, and the
badge keeps what it can attribute. Each case below is paired with its
opposite: the same channel carrying something real must still badge,
or this file would pass on a kit whose indicator never fires at all.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet, until

pytestmark = pytest.mark.browser

PAGE_MD = """---
title: Indicator
summary: A page with nothing wrong with it.
---

## Section {#section}

Ordinary prose, one table, nothing that should raise a warning.

| a | b |
|:--|--:|
| x | 1 |
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("indicator") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Indicator"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture()
def page(built, browser):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    # Our own listener, registered before the kit's, so a test can tell
    # "the browser never fired it" from "the indicator ignored it".
    page.add_init_script(
        "window.__seen = []; window.addEventListener('error', function (e) { window.__seen.push(e.message); });"
    )
    warned: list[str] = []
    page.on("console", lambda m: warned.append(m.text) if m.type == "warning" else None)
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    page.__warned = warned  # type: ignore[attr-defined]
    yield page
    context.close()


BADGE = ".ctrl-btn.warning-indicator"


def _badge(page) -> tuple[bool, str]:
    return tuple(  # type: ignore[return-value]
        page.evaluate(
            "() => { const b = document.querySelector('.ctrl-btn.warning-indicator');"
            " return [!!b && getComputedStyle(b).display !== 'none', (b && b.getAttribute('data-count')) || '']; }"
        )
    )


def test_a_page_with_nothing_wrong_shows_no_badge(page):
    """The floor. Everything below measures a change from here."""
    shown, _count = _badge(page)
    assert shown is False


def test_a_real_resize_observer_loop_is_fired_by_the_browser(page):
    """Not vacuous: the condition the next test says is ignored has to
    be one this browser actually raises."""
    page.evaluate(
        "() => { const d = document.createElement('div'); d.style.width = '100px';"
        " d.textContent = 'x'; document.body.appendChild(d); let w = 100;"
        " new ResizeObserver(() => { w = w === 100 ? 200 : 100; d.style.width = w + 'px'; }).observe(d); }"
    )
    until(
        page,
        "() => window.__seen.some(m => /^ResizeObserver loop/.test(m))",
        what="the browser never fired the notice",
    )


def test_a_resize_observer_notice_does_not_badge(page):
    page.evaluate(
        "() => { const d = document.createElement('div'); d.style.width = '100px';"
        " d.textContent = 'x'; document.body.appendChild(d); let w = 100;"
        " new ResizeObserver(() => { w = w === 100 ? 200 : 100; d.style.width = w + 'px'; }).observe(d); }"
    )
    until(
        page,
        "() => window.__seen.some(m => /^ResizeObserver loop/.test(m))",
        what="the browser never fired the notice",
    )
    shown, _count = _badge(page)
    assert shown is False, "a delivery notice raised an alarm on a document with nothing wrong with it"
    assert any("ResizeObserver" in line for line in page.__warned), "dropped without a word to the console"


def test_an_unattributable_script_error_does_not_badge(page):
    """`Script error.` with no filename and no error object: the browser
    has already refused to say what threw."""
    page.evaluate(
        "() => window.dispatchEvent(new ErrorEvent('error',"
        " { message: 'Script error.', filename: '', lineno: 0, colno: 0 }))"
    )
    shown, _count = _badge(page)
    assert shown is False
    assert any("Script error." in line for line in page.__warned)


def test_an_error_the_page_can_name_still_badges(page):
    """The opposite case, in the same channel: a throw the kit can point
    at a file and a line for is exactly what the indicator is for."""
    page.evaluate(
        "() => window.dispatchEvent(new ErrorEvent('error',"
        " { message: 'Boom', filename: 'chrome.js', lineno: 42, error: new Error('Boom') }))"
    )
    until(
        page,
        "() => { const b = document.querySelector('.ctrl-btn.warning-indicator');"
        " return !!b && getComputedStyle(b).display !== 'none'; }",
        what="an attributable error was dropped with the noise",
    )
    _shown, count = _badge(page)
    assert count == "1"


def test_a_document_warning_still_badges(page):
    """The channel the kit's own subsystems push on — a mermaid parse
    failure, an unresolved reference — is untouched."""
    page.evaluate(
        "() => window.dispatchEvent(new CustomEvent('oku:warnings',"
        " { detail: [{ code: 'mermaid-parse', msg: 'diagram 2 did not parse', level: 'error' }] }))"
    )
    until(
        page,
        "() => { const b = document.querySelector('.ctrl-btn.warning-indicator');"
        " return !!b && getComputedStyle(b).display !== 'none'; }",
        what="a document warning did not reach the indicator",
    )
    page.click(BADGE)
    assert "did not parse" in page.evaluate("() => document.body.innerText")
