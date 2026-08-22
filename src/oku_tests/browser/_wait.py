"""Wait for the thing you are waiting for.

The browser suite held 205 s of `wait_for_timeout(...)` across 212
calls. A fixed sleep is wrong in both directions at once: it is dead
time on every run where the work finished in 80 ms, and it is a flake
on the one run where the machine was busy — and the flake arrives as a
failure in an assertion that has nothing to do with timing, which is
the expensive part.

Every helper here waits on a CONDITION and raises naming what it was
waiting for. `timeout` is a ceiling, not a duration: a passing run pays
one polling interval, not the ceiling.
"""

from __future__ import annotations

import json

DEFAULT_TIMEOUT = 20000
POLL = 50


def until(page, expression: str, *, timeout: int = DEFAULT_TIMEOUT, what: str = "") -> None:
    """Wait until a JS expression is truthy.

    `expression` is function source — `() => …` — the same shape
    `page.evaluate` takes.
    """
    try:
        page.wait_for_function(expression, timeout=timeout, polling=POLL)
    except Exception as exc:  # noqa: BLE001 - re-raised naming the condition
        raise AssertionError(f"never became true: {what or expression}") from exc


def until_changed(page, expression: str, before, *, timeout: int = DEFAULT_TIMEOUT, what: str = "") -> None:
    """Wait until a JS expression stops returning `before`.

    The shape a re-render needs. A theme flip replaces an SVG whose
    selector is unchanged, so "is it there" answers yes throughout and
    only "is it different" is the question being asked.

    The comparison is baked into the expression rather than passed as
    an argument: Playwright serialises arguments as data, so a function
    cannot travel that way, and rebuilding one with `eval` inside the
    page is refused by the CSP a built page carries.
    """
    until(
        page,
        f"() => {{ const v = ({expression})(); return v !== {json.dumps(before)}; }}",
        timeout=timeout,
        what=what or f"{expression} changed from {before!r}",
    )


def diagram_drawn(page, selector: str = "oku-diagram", *, timeout: int = 30000) -> None:
    """Mermaid is lazy-loaded and renders asynchronously, which is why
    every diagram assertion in the suite sat behind a 4 s sleep.

    A parse error counts as drawn: it is the outcome several of these
    tests are measuring, and waiting the full ceiling for an SVG that
    is never coming turns one assertion failure into a timeout.
    """
    until(
        page,
        f"() => {{ const d = document.querySelector({json.dumps(selector)});"
        " return !!d && (!!d.querySelector('svg') || /Parse error/.test(d.textContent)); }",
        timeout=timeout,
        what=f"{selector} drew an svg (or reported a parse error)",
    )


def highlighted(page, selector: str = "pre code", *, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Prism fetches its grammar and rewrites the block when it
    arrives."""
    until(
        page,
        f"() => {{ const c = document.querySelector({json.dumps(selector)});"
        " return !!c && !!c.querySelector('.token, .okt-code-line'); }",
        timeout=timeout,
        what=f"{selector} was highlighted",
    )


def stable(
    page, expression: str, *, samples: int = 3, timeout: int = DEFAULT_TIMEOUT, what: str = ""
) -> None:
    """Wait until a JS expression returns the same value `samples`
    polls running.

    For the settles that have no single event to hang off: a CSS
    transition, a scroll coming to rest, a render pass that keeps
    appending. `window.__okuRendered` says the walk finished, and the
    charts, the lightbox and Prism all keep working after it — which is
    why those sleeps were there and why deleting them without a
    replacement would trade dead time for a flake.

    A passing run pays `samples` polling intervals, not the ceiling.
    """
    page.evaluate("() => { window.__okuWaitSig = undefined; window.__okuWaitHits = 0; }")
    until(
        page,
        "() => {"
        f" const sig = JSON.stringify(({expression})());"
        " if (window.__okuWaitSig === sig) window.__okuWaitHits++;"
        " else { window.__okuWaitSig = sig; window.__okuWaitHits = 0; }"
        f" return window.__okuWaitHits >= {samples}; }}",
        timeout=timeout,
        what=what or f"{expression} stopped changing",
    )


def box_stable(page, *selectors: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Every named element's box stopped moving — a transition finished.

    Measuring a box mid-transition reports a real number for a layout
    that does not exist yet, which is how a geometry assertion fails on
    a loaded machine and nowhere else.

    Pass EVERY element the assertion measures. Waiting on one of them
    and asserting about two is the same bug in a new place: pinning the
    drawer at 1600px moves the panel and leaves `main` exactly where it
    was, so a wait on `main` alone returns while the panel is still
    sliding and the test reads its position mid-transition.
    """
    assert selectors, "box_stable needs something to watch"
    stable(
        page,
        f"() => {json.dumps(list(selectors))}.map((sel) => {{"
        " const el = document.querySelector(sel); if (!el) return null;"
        " const r = el.getBoundingClientRect();"
        " return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })",
        timeout=timeout,
        what=f"{', '.join(selectors)} stopped moving",
    )


def scroll_stable(page, *, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Smooth scrolling came to rest."""
    stable(page, "() => Math.round(window.scrollY)", timeout=timeout, what="the page stopped scrolling")


def page_quiet(page, *, timeout: int = DEFAULT_TIMEOUT) -> None:
    """The render pass stopped adding to the document.

    `window.__okuRendered` marks the end of the renderer's walk, not
    the end of the page: charts size themselves, Prism rewrites blocks
    when a grammar lands, and the rail builds its marks. The height and
    the element count together catch all three.
    """
    stable(
        page,
        "() => [document.body.scrollHeight, document.querySelectorAll('*').length]",
        timeout=timeout,
        what="the page stopped changing size",
    )
