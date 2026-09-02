"""One button in the corner, and every presentation choice behind it.

The flex row fixed the corner's arithmetic — a button that is absent
takes no space, so no offset table has to be re-derived. It did not fix
the COUNT. Six buttons wanted that corner and a seventh (text size) was
next, and six 44px boxes over the top of the reading column is a toolbar
the reader has to read before every click, five sixths of which they set
once and never touch again.

What stays outside is what a reader uses WHILE reading: search, and the
warning indicator, which is not a control at all but an alarm. What moves
inside is what they set once.

These are the properties that has to hold:

  - the corner carries at most three boxes, and never a preference
  - the panel opens, and closes on Escape, on an outside click, and on
    the button again — but NOT on a control inside it, because stepping
    the text size is a thing a reader does three times in a row
  - every row that used to be a corner button still works, including the
    two whose rules the kit states in prose: the width control has three
    stops, and the theme control has two with the OS dot on the pressed
    one
  - a row that has nowhere to go does not appear — language on a page
    with no translation, placeholders on a page with no snippet
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import _wait
from ._menu import BUTTON, MENU, open_menu, set_width

DESKTOP = {"width": 1280, "height": 900}

CORNER = """() => [...document.querySelectorAll('#oku-chrome-cluster .ctrl-btn')]
  .filter((b) => b.offsetParent !== null || getComputedStyle(b).display !== 'none')
  .map((b) => b.className.replace('ctrl-btn', '').trim())"""


def _open(page, site_url, path="docs/index.html"):
    page.set_viewport_size(DESKTOP)
    page.goto(f"{site_url}/{path}")
    page.wait_for_selector("main")
    _wait.page_quiet(page)
    return page


def test_the_corner_holds_three_boxes_and_no_preference(page, site_url):
    _open(page, site_url)
    names = page.evaluate(CORNER)
    assert set(names) <= {"search-toggle", "warning-indicator", "menu-toggle"}, (
        f"the corner carries {names}. Search and the warning indicator are used while "
        "reading; everything else is a preference and belongs in the menu."
    )
    assert "menu-toggle" in names


def test_the_panel_opens_and_closes_the_three_ways(page, site_url):
    _open(page, site_url)
    panel = open_menu(page)
    assert panel.is_visible()
    assert page.get_attribute(BUTTON, "aria-expanded") == "true"

    # The button again.
    page.click(BUTTON)
    page.wait_for_selector(MENU, state="hidden")
    assert page.get_attribute(BUTTON, "aria-expanded") == "false"

    # Escape, and focus comes back to the button that opened it.
    open_menu(page)
    page.keyboard.press("Escape")
    page.wait_for_selector(MENU, state="hidden")
    assert page.evaluate("() => document.activeElement.classList.contains('menu-toggle')")

    # A click on the page behind it.
    open_menu(page)
    page.mouse.click(400, 600)
    page.wait_for_selector(MENU, state="hidden")


def test_escape_closes_the_menu_and_leaves_the_drawer_alone(page, site_url):
    """One press, one dismissal — the topmost thing.

    Both handlers live on `document`, and the drawer's was registered
    first, so a bubble-phase listener here runs second and
    `stopPropagation` cannot reach a sibling on the node it is already
    on: Escape closed the menu AND the Contents drawer under it. The menu
    listens in the CAPTURE phase, which runs before every bubble listener
    on the same node, so stopping propagation there genuinely means "this
    press was mine".
    """
    # Below 900px the drawer opens MODAL, which is the state Escape is
    # supposed to close. Pinned is deliberately Escape-proof (a pinned
    # panel is not a dialog), so it could not tell the two behaviours
    # apart — a passing test there would prove nothing.
    page.set_viewport_size({"width": 800, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main")
    _wait.page_quiet(page)
    page.click(".ctrl-btn.drawer-toggle")
    page.wait_for_timeout(300)
    drawer_open = page.evaluate("() => document.body.className")
    assert "drawer-modal" in drawer_open, f"the drawer did not open modal: {drawer_open!r}"

    open_menu(page)
    page.keyboard.press("Escape")
    page.wait_for_selector(MENU, state="hidden")
    assert page.evaluate("() => document.body.className") == drawer_open, (
        "Escape took the drawer with the menu; the menu is the thing on top "
        "and the only thing the reader aimed at"
    )

    # A second press, with the menu already closed, is the drawer's.
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    assert "drawer-open" not in page.evaluate("() => document.body.className")


def test_the_panel_stays_open_while_the_text_size_is_stepped(page, site_url):
    """The reason it is a panel and not five popovers. Finding the size
    that suits you is three clicks; a menu that closed on the first would
    make it nine."""
    _open(page, site_url)
    open_menu(page)
    for _ in range(3):
        page.click(f'{MENU} [data-step="1"]')
        assert page.locator(MENU).is_visible(), "the panel closed under the reader mid-adjustment"
    assert page.evaluate("() => parseFloat(document.documentElement.dataset.textScale)") == 1.5


def test_the_width_control_still_has_three_stops_and_shows_which(page, site_url):
    """Three stops, and — this is what the corner could not do — the one
    you are in is visible without hovering anything. The icon version
    announced its stops in a `title`."""
    _open(page, site_url)
    open_menu(page)
    stops = page.eval_on_selector_all(f"{MENU} [data-width]", "els => els.map(e => e.dataset.width)")
    assert stops == ["narrow", "comfortable", "max"], stops

    for mode in stops:
        set_width(page, mode)
        assert page.evaluate("() => document.body.dataset.contentWidth") == mode
        pressed = page.eval_on_selector_all(
            f"{MENU} [data-width]",
            "els => els.filter(e => e.getAttribute('aria-pressed') === 'true').map(e => e.dataset.width)",
        )
        assert pressed == [mode], f"in {mode} the pressed segment is {pressed}"


@pytest.mark.parametrize("os_theme", ["light", "dark"])
def test_the_theme_control_has_two_stops_and_the_dot_marks_following(page, site_url, os_theme):
    """The rule the corner button held, in its new home. Two stops;
    following the OS is not a third one you click into, it is where the
    page rests — so picking the theme the OS is already in hands the
    choice back, and the dot on the pressed segment says so."""
    page.emulate_media(color_scheme=os_theme)
    _open(page, site_url)
    open_menu(page)

    choices = page.eval_on_selector_all(
        f"{MENU} [data-theme-choice]", "els => els.map(e => e.dataset.themeChoice)"
    )
    assert choices == ["light", "dark"], choices

    def dot_opacity():
        return page.eval_on_selector(
            f'{MENU} [data-theme-choice][aria-pressed="true"]',
            "el => parseFloat(getComputedStyle(el, '::after').opacity)",
        )

    # Fresh: following the OS, dot lit, and the pressed segment is the
    # theme the OS put us in.
    assert page.evaluate("() => document.documentElement.dataset.theme") == os_theme
    assert page.get_attribute(f'{MENU} [data-theme-choice="{os_theme}"]', "aria-pressed") == "true"
    assert dot_opacity() == 1

    # Pinned against the OS: dot out.
    other = "light" if os_theme == "dark" else "dark"
    page.click(f'{MENU} [data-theme-choice="{other}"]')
    assert page.evaluate("() => document.documentElement.dataset.theme") == other
    assert page.get_attribute(f'{MENU} [data-theme-choice="{other}"]', "aria-pressed") == "true"
    assert dot_opacity() == 0

    # Choosing the theme the OS is in is how a reader hands it back.
    page.click(f'{MENU} [data-theme-choice="{os_theme}"]')
    assert page.evaluate("() => document.documentElement.dataset.themeMode") == "system"
    assert dot_opacity() == 1


PLAIN_PAGE = """---
title: One page, one language
---

## Nothing to switch to

A page with no counterpart beside it and no snippet placeholders.
"""


@pytest.fixture(scope="module")
def plain_url(tmp_path_factory):
    """A one-page site with no `languages` key. Every page in this repo's
    own docs has a `.tr` counterpart, so the absent case cannot be
    demonstrated there — and the absent case is the property."""
    import http.server
    import json
    import threading

    from oku import cli

    kit = Path(__file__).resolve().parents[3] / "kit"
    d = tmp_path_factory.mktemp("plainmenu")
    (d / "_oku").symlink_to(kit, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "plain", "accent": "teal"}), encoding="utf-8")
    (d / "p.md").write_text(PLAIN_PAGE, encoding="utf-8")
    (d / "p.html").write_text(
        cli._stub_for("Plain", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_the_rows_that_are_always_there_are_the_first_three(page, site_url):
    _open(page, site_url, "docs/index.html")
    open_menu(page)
    rows = page.eval_on_selector_all(f"{MENU} .okt-menu-row", "els => els.map(e => e.dataset.row)")
    assert rows[:3] == ["text-scale", "width", "theme"], rows
    # This repo's index.html has a .tr counterpart, so the switch is here.
    assert "language" in rows
    assert page.eval_on_selector_all(
        f"{MENU} [data-lang]", "els => els.map(e => e.textContent.trim()).sort()"
    ) == ["EN", "TR"]
    # …and nothing on this page declares a placeholder.
    assert "personalize" not in rows


def test_a_row_with_nowhere_to_go_does_not_appear(browser, plain_url):
    """Language registers only where the manifest offers a variant, and
    placeholders only where a snippet declared some. A row that never
    registers costs nothing and leaves no gap — the same property the
    flex row in the corner has, for the same reason."""
    pg = browser.new_page(viewport=DESKTOP)
    try:
        pg.goto(f"{plain_url}/p.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=20000)
        open_menu(pg)
        rows = pg.eval_on_selector_all(f"{MENU} .okt-menu-row", "els => els.map(e => e.dataset.row)")
        assert rows == ["text-scale", "width", "theme"], (
            f"a page with one language and no placeholders shows {rows}"
        )
    finally:
        pg.close()


def test_every_control_in_the_panel_is_reachable_by_keyboard(page, site_url):
    """No focus trap and no roving tabindex — the panel is not a modal,
    the page behind it is live. What it does need is for every control to
    be a real button, which is what Tab proves."""
    _open(page, site_url)
    open_menu(page)
    controls = page.eval_on_selector_all(
        f"{MENU} button", "els => els.filter(e => e.getAttribute('aria-disabled') !== 'true').length"
    )
    assert controls >= 8, f"the panel exposes {controls} operable buttons"

    reached = set()
    for _ in range(controls + 2):
        page.keyboard.press("Tab")
        hit = page.evaluate(
            "() => { const a = document.activeElement;"
            " return a && a.closest('.okt-chrome-menu') ? a.className + '|' + (a.dataset.width || a.dataset.themeChoice || a.dataset.step || a.dataset.lang || '') : null; }"
        )
        if hit:
            reached.add(hit)
    assert len(reached) >= controls - 1, f"Tab reached {len(reached)} of {controls} controls in the panel"
