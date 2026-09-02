"""The reader can make the document bigger, and the document is all of it.

"Sometimes the font size feels too small" is not a request about the
body font. A reader who cannot read the prose cannot read a chart's axis
labels either, so a control that grew the paragraphs and left every
figure where it was would answer the easy half of the complaint and ship
looking finished.

The mechanism is `zoom` on the reading column. What that buys and what it
costs is argued in chrome.js under "Reader text scale"; what it has to be
TRUE for is here, as numbers:

  - text gets bigger, by the factor asked for
  - figures get bigger with it — a chart is drawn into a box that grows
  - the chrome does not move: 44px buttons stay 44px, the sidebar surface
    still spans the viewport (invariant 1), the rail keeps its strip
  - the sidebar's own text DOES scale, because the tree and the table of
    contents are text a reader reads
  - nothing scrolls sideways at any scale, at 1440px or at 360px, in any
    of the three width modes — `100vw` under zoom is 125% of the viewport
    and that is exactly how this would have shipped broken
  - a tooltip still lands on the thing it points at, which is the one
    behaviour `zoom` breaks on its own: a `position: fixed` descendant of
    a zoomed element takes the zoom with it
  - the choice survives a reload, and it is applied before first paint
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import _wait
from ._menu import MENU, open_menu, step_text_scale

DESKTOP = {"width": 1440, "height": 900}
NARROW = {"width": 360, "height": 800}

# A nowrap probe measures RENDERED glyph size, which is the thing under
# test. `getComputedStyle(...).fontSize` cannot see this at all: zoom does
# not change a computed length, it changes what that length draws as.
PROBE = """() => {
  const probe = document.createElement('span');
  probe.style.whiteSpace = 'nowrap';
  probe.style.font = 'inherit';
  probe.textContent = 'MMMMMMMMMM';
  document.querySelector('main').appendChild(probe);
  const w = probe.getBoundingClientRect().width;
  probe.remove();
  return w;
}"""

GEOMETRY = """() => {
  const box = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { w: r.width, h: r.height, x: r.x, y: r.y };
  };
  return {
    main: box('main'),
    chart: box('oku-chart svg'),
    nav: box('page-nav'),
    navLink: box('.page-nav-tree a'),
    menuBtn: box('.ctrl-btn.menu-toggle'),
    rail: box('.okt-rail'),
    scrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
    innerH: window.innerHeight,
    zoom: document.querySelector('main').currentCSSZoom,
  };
}"""


def _open(page, site_url, path="docs/charts.html", viewport=None):
    page.set_viewport_size(viewport or DESKTOP)
    page.goto(f"{site_url}/{path}")
    page.wait_for_selector("main")
    _wait.page_quiet(page)
    return page


def _set(page, scale):
    """Set the scale through the kit's own entry point and wait for the
    layout to settle, so a measurement is never taken mid-reflow."""
    page.evaluate("(v) => applyTextScale(v, false)", scale)
    _wait.box_stable(page, "main")


def test_the_text_gets_bigger_by_the_factor_asked_for(page, site_url):
    _open(page, site_url)
    at_one = page.evaluate(PROBE)
    for scale in (1.25, 1.5, 2):
        _set(page, scale)
        got = page.evaluate(PROBE)
        assert got == pytest.approx(at_one * scale, rel=0.02), (
            f"at scale {scale} the same string renders {got:.1f}px wide against "
            f"{at_one:.1f}px at 1.0 — a ratio of {got / at_one:.3f}"
        )


def test_a_chart_grows_with_the_text(page, site_url):
    """The half a font-size-only control would have missed. A chart is an
    SVG that fills its container, so it scales when the container does —
    and the container is the zoomed column."""
    _open(page, site_url)
    page.wait_for_selector("oku-chart svg")
    _wait.page_quiet(page)
    before = page.evaluate(GEOMETRY)["chart"]
    _set(page, 2)
    after = page.evaluate(GEOMETRY)["chart"]
    assert after["h"] > before["h"] * 1.3, (
        f"a chart is {after['h']:.1f}px tall at 2x against {before['h']:.1f}px at 1x. "
        "The figure has to grow with the words or the reader who needed this "
        "still cannot read the axis."
    )


def test_the_chrome_does_not_move(page, site_url):
    """The 44px buttons, the rail and the sidebar surface are the frame
    the document sits in. Four test files assert their geometry
    numerically; this is the one that says the text scale cannot reach
    them."""
    _open(page, site_url)
    before = page.evaluate(GEOMETRY)
    _set(page, 2)
    after = page.evaluate(GEOMETRY)

    assert after["menuBtn"]["w"] == pytest.approx(44, abs=1)
    assert after["menuBtn"]["h"] == pytest.approx(44, abs=1)
    assert after["menuBtn"]["x"] == pytest.approx(before["menuBtn"]["x"], abs=1)
    assert after["rail"]["h"] == pytest.approx(before["rail"]["h"], abs=1)
    # Invariant 1: the sidebar surface spans the visible viewport, at
    # every scale. A zoom on page-nav itself would take 100vh with it.
    assert after["nav"]["h"] == pytest.approx(after["innerH"], abs=1)
    assert after["nav"]["w"] == pytest.approx(before["nav"]["w"], abs=1)


def test_the_sidebar_text_scales_but_the_sidebar_does_not(page, site_url):
    _open(page, site_url)
    before = page.evaluate(GEOMETRY)
    _set(page, 1.5)
    after = page.evaluate(GEOMETRY)
    assert after["navLink"]["h"] == pytest.approx(before["navLink"]["h"] * 1.5, rel=0.06), (
        f"a tree row is {after['navLink']['h']:.1f}px tall at 1.5x against "
        f"{before['navLink']['h']:.1f}px — the tree is text a reader reads"
    )
    assert after["nav"]["w"] == pytest.approx(before["nav"]["w"], abs=1)


@pytest.mark.parametrize("viewport", [DESKTOP, NARROW], ids=["desktop", "narrow"])
@pytest.mark.parametrize("width_mode", ["narrow", "comfortable", "max"])
def test_nothing_scrolls_sideways_at_any_scale(page, site_url, viewport, width_mode):
    """`max` was `--content-width: 100vw`, and a viewport unit does not
    scale with zoom: at 1.25 the column asked for 125% of the viewport
    and the page scrolled sideways in the one mode meant for wide
    tables."""
    _open(page, site_url, viewport=viewport)
    page.evaluate("(m) => setContentWidth(m)", width_mode)
    for scale in (0.8, 1, 1.5, 2):
        _set(page, scale)
        got = page.evaluate(GEOMETRY)
        assert got["scrollW"] <= got["innerW"] + 1, (
            f"{width_mode} at {scale}x on a {viewport['width']}px viewport scrolls "
            f"sideways: scrollWidth {got['scrollW']} against {got['innerW']}"
        )


# A page of our own for the tooltip case. The docs' own charts answer
# the pointer in several different ways depending on family, and a test
# that skips when it lands on the wrong one proves nothing about the
# thing it was written for. A DIV bar chart always builds `.okc-tooltip`.
TIP_PAGE = """---
title: Cursor under zoom
---

## Bars

```oku-chart
{"type":"bar","rows":[{"label":"Free","value":26.9},{"label":"Wired","value":10.4},
{"label":"Inactive","value":9.2},{"label":"Active","value":9.0}]}
```
"""


@pytest.fixture(scope="module")
def tip_url(tmp_path_factory):
    import http.server
    import json
    import threading

    from oku import cli

    kit = Path(__file__).resolve().parents[3] / "kit"
    d = tmp_path_factory.mktemp("tipzoom")
    (d / "_oku").symlink_to(kit, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "p.md").write_text(TIP_PAGE, encoding="utf-8")
    (d / "p.html").write_text(
        cli._stub_for("Cursor under zoom", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


TIP_BOX = """() => {
  const t = document.querySelector('.okc-tooltip.visible');
  if (!t) return null;
  const r = t.getBoundingClientRect();
  return { x: r.x, w: r.width, mid: r.x + r.width / 2 };
}"""


@pytest.mark.parametrize("scale", [1, 1.25, 1.5, 2])
def test_a_chart_tooltip_still_lands_on_the_pointer(browser, tip_url, scale):
    """The one thing `zoom` breaks by itself, and it breaks silently.

    A `position: fixed` descendant of a zoomed element resolves its
    `left` in the ZOOMED coordinate space, while the coordinate written
    into it was read out of `getBoundingClientRect()`, which reports
    client space. Uncorrected the error is proportional to how far
    across the page the mark sits: at 1.5x a tooltip anchored to a bar
    600px in lands 300px past it, and at 2x it lands off the viewport.
    `__okuSetFixedPos` divides the coordinate back out.

    Parametrised over the ladder rather than run at one scale, because
    the defect IS the scale factor — a test at 1.0 alone passes against
    the broken code.
    """
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        pg.goto(f"{tip_url}/p.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=20000)
        pg.wait_for_selector(".bar-fill")
        pg.evaluate("(v) => applyTextScale(v, false)", scale)
        _wait.box_stable(pg, "main")

        bar = pg.locator(".bar-fill").first.bounding_box()
        cursor_x = bar["x"] + bar["width"] * 0.6
        cursor_y = bar["y"] + bar["height"] / 2
        # Two moves: the first arms the enhancer, the second carries a
        # real delta. One move can land as a synthetic enter with no
        # movement behind it, which the card controller ignores.
        pg.mouse.move(cursor_x - 4, cursor_y)
        pg.mouse.move(cursor_x, cursor_y)
        pg.wait_for_selector(".okc-tooltip.visible", timeout=5000)

        tip = pg.evaluate(TIP_BOX)
        assert tip, "no tooltip appeared under the cursor"
        assert abs(tip["mid"] - cursor_x) < 24, (
            f"at {scale}x the tooltip's centre is at x={tip['mid']:.0f} for a cursor "
            f"at x={cursor_x:.0f} — {abs(tip['mid'] - cursor_x):.0f}px away"
        )
    finally:
        pg.close()


def _walk_to_the_end(page, direction: int, limit: int = 12) -> float:
    """Click a stepper until it says it has nothing left, the way a
    reader does. `aria-disabled` is what it says with, and it is a real
    barrier — Playwright refuses to click through it, which is the same
    answer a screen reader gives its user."""
    selector = f'{MENU} [data-step="{direction}"]'
    for _ in range(limit):
        if page.get_attribute(selector, "aria-disabled") == "true":
            break
        page.click(selector)
    else:  # pragma: no cover - only reached if the ladder has no end
        raise AssertionError(f"the stepper never reached an end in {limit} clicks")
    return page.evaluate("() => parseFloat(document.documentElement.dataset.textScale)")


def test_the_ladder_has_ends_and_says_so(page, site_url):
    """The ends are stated rather than hidden: the button stays where it
    was, keeps its box, and reports that it is spent. A step that
    silently does nothing reads as a broken control."""
    _open(page, site_url)
    open_menu(page)
    box_before = page.locator(f'{MENU} [data-step="-1"]').bounding_box()

    assert _walk_to_the_end(page, -1) == 0.8
    assert page.get_attribute(f'{MENU} [data-step="1"]', "aria-disabled") == "false"
    assert _walk_to_the_end(page, 1) == 2
    assert page.get_attribute(f'{MENU} [data-step="-1"]', "aria-disabled") == "false"

    # Invariant 2's shape: a spent control is still a visible, sized box
    # in the place it was, not a hole in the row.
    box_after = page.locator(f'{MENU} [data-step="-1"]').bounding_box()
    assert box_after == box_before


def test_the_readout_reads_out_and_resets(page, site_url):
    _open(page, site_url)
    step_text_scale(page, 1, times=2)
    assert page.inner_text(f"{MENU} .text-scale-reset").strip() == "125%"
    page.click(f"{MENU} .text-scale-reset")
    assert page.inner_text(f"{MENU} .text-scale-reset").strip() == "100%"
    assert page.evaluate("() => parseFloat(document.documentElement.dataset.textScale)") == 1


def test_the_choice_survives_a_reload_and_beats_first_paint(page, site_url):
    """Stored by the menu, restored by chrome-boot.js — which is
    synchronous and in <head>, so the column is never drawn at one scale
    and re-drawn at another."""
    _open(page, site_url)
    step_text_scale(page, 1, times=2)
    assert page.evaluate("() => localStorage.getItem('oku-text-scale')") == "1.25"

    page.reload()
    page.wait_for_selector("main")
    # The attribute is set by the boot script, before chrome.js has run
    # and long before `oku:rendered`. Reading it right after the selector
    # resolves is what makes this an assertion about first paint.
    assert page.evaluate("() => document.documentElement.dataset.textScale") == "1.25"
    _wait.page_quiet(page)
    assert page.evaluate("() => document.querySelector('main').currentCSSZoom") == 1.25


def test_a_value_off_the_ladder_is_snapped_not_trusted(page, site_url):
    """localStorage is reader-writable and survives a kit that changed
    its ladder. `zoom: 0` renders nothing at all, and a page that renders
    nothing has no control left to fix it with."""
    page.add_init_script("try{localStorage.setItem('oku-text-scale','0')}catch(e){}")
    _open(page, site_url)
    assert page.evaluate("() => document.querySelector('main').currentCSSZoom") > 0
    assert page.evaluate("() => document.querySelector('main').getBoundingClientRect().width") > 0
