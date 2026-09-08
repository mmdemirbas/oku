"""Three stops — System, Light, Dark — and System is the only auto there is.

The control had two, Light and Dark, with following the OS surviving as
a *policy* rather than a stop: you re-entered it by picking whichever
theme the OS was already showing, a 4px dot said you were in it, and an
explicit choice EXPIRED at the next OS flip. All three of those existed
to fit the rule into one corner button that could show one of two icons.

The panel has room to draw three, so the reader gets the ordinary thing:
a stop for each, System included, and a pin that holds until they change
it. That reverses two behaviours, and both reversals are pinned here —
picking the theme the OS is already in is now a real pin rather than a
hand-back, and an OS flip no longer spends a choice.

The distinction the whole file turns on is that `data-theme-mode` is the
stop the reader chose and `data-theme` is what the page is painted in.
On System with a dark OS those are `system` and `dark`, so a control
keyed off the wrong one lights the wrong segment while looking correct
in every light-OS test.
"""

from __future__ import annotations

import pytest

from ._wait import until

from ._menu import MENU, open_menu

DESKTOP = {"width": 1280, "height": 900}

STATE = """() => ({
  theme: document.documentElement.dataset.theme,
  mode: document.documentElement.dataset.themeMode,
  pref: (() => { try { return localStorage.getItem('theme-pref'); } catch (e) { return null; } })(),
})"""


def _open(page, site_url, *, os_theme="light", pref=None):
    page.emulate_media(color_scheme=os_theme)
    page.set_viewport_size(DESKTOP)
    if pref is not None:
        page.add_init_script("try{localStorage.setItem('theme-pref',%r)}catch(e){}" % pref)
    page.goto(f"{site_url}/docs/index.html")
    open_menu(page)
    return page.evaluate(STATE)


def _pick(page, stop):
    page.click(f'{MENU} [data-theme-choice="{stop}"]')
    until(
        page,
        f"() => document.documentElement.dataset.themeMode === '{stop}'",
        what=f"the control moved to the {stop} stop",
    )
    return page.evaluate(STATE)


def _pressed(page):
    return page.eval_on_selector_all(
        f"{MENU} [data-theme-choice]",
        "els => els.filter(e => e.getAttribute('aria-pressed') === 'true')"
        "        .map(e => e.dataset.themeChoice)",
    )


@pytest.mark.parametrize("os_theme", ["light", "dark"])
def test_a_fresh_reader_is_on_system(page, site_url, os_theme):
    """Nothing stored: the page is whatever the OS says, the stop in
    force is System, and there is no key — the absence of one IS System,
    so a reader who has never touched the control and one who chose it
    back are the same state rather than two that can drift."""
    state = _open(page, site_url, os_theme=os_theme)
    assert state == {"theme": os_theme, "mode": "system", "pref": None}


@pytest.mark.parametrize("os_theme", ["light", "dark"])
def test_the_control_has_exactly_three_stops_each_with_a_glyph(page, site_url, os_theme):
    """System first, because it is where a reader starts and the other
    two are the departures from it."""
    _open(page, site_url, os_theme=os_theme)
    stops = page.eval_on_selector_all(
        f"{MENU} [data-theme-choice]", "els => els.map(e => e.dataset.themeChoice)"
    )
    assert stops == ["system", "light", "dark"], stops
    glyphs = page.eval_on_selector_all(f"{MENU} [data-theme-choice] .okt-menu-glyph svg", "els => els.length")
    assert glyphs == 3, f"each stop carries its own glyph; found {glyphs}"


@pytest.mark.parametrize("os_theme", ["light", "dark"])
def test_the_pressed_stop_is_the_one_the_reader_chose(page, site_url, os_theme):
    """The discriminating case, and the reason it is parametrised over
    the OS: on System the page is PAINTED light or dark, so a control
    keyed off `data-theme` presses Light or Dark here and looks right
    doing it. The reader has chosen System, so System is pressed."""
    _open(page, site_url, os_theme=os_theme)
    assert _pressed(page) == ["system"]
    for stop in ("light", "dark", "system"):
        _pick(page, stop)
        assert _pressed(page) == [stop], (stop, _pressed(page))


def test_a_choice_is_stored_bare_and_a_pin_is_a_pin(page, site_url):
    """Light against a dark OS is an override, and it is written down as
    the mode itself — no OS value travelling with it, because nothing
    expires any more."""
    _open(page, site_url, os_theme="dark")
    assert _pick(page, "light") == {"theme": "light", "mode": "light", "pref": "light"}


def test_choosing_the_theme_the_os_already_shows_is_a_real_pin(page, site_url):
    """The first of the two reversals. This used to be the gesture for
    handing control back — the key was dropped and the page went to
    following, which meant the way to auto was knowing that clicking a
    theme you were already in did something other than nothing.

    It now means what it says: the reader wants Light, whatever the OS
    does next."""
    _open(page, site_url, os_theme="light")
    assert _pick(page, "light") == {"theme": "light", "mode": "light", "pref": "light"}


def test_system_is_how_a_reader_hands_control_back(page, site_url):
    """…and it is drawn, so it can be aimed at."""
    _open(page, site_url, os_theme="light")
    _pick(page, "dark")
    assert _pick(page, "system") == {"theme": "light", "mode": "system", "pref": None}


def test_a_pin_survives_an_os_flip_under_a_live_tab(page, site_url):
    """The second reversal, and the one with a cost attached under the
    old rule: "always dark" could not be pinned past an OS flip, so a
    reader whose OS runs on a schedule re-picked it once a day."""
    _open(page, site_url, os_theme="light")
    assert _pick(page, "dark")["mode"] == "dark"
    page.emulate_media(color_scheme="dark")
    # The assertion below is that nothing moved, so what has to be
    # established first is that there was something to move FOR: the page
    # itself reporting the OS is dark now. A sleep never checked that —
    # an emulation that silently failed would have passed it.
    until(
        page,
        "() => window.matchMedia('(prefers-color-scheme: dark)').matches",
        what="the page saw the OS turn dark",
    )
    assert page.evaluate(STATE) == {"theme": "dark", "mode": "dark", "pref": "dark"}
    # …and it holds when the OS moves back, which is the half that would
    # pass by accident above: dark-pinned under a dark OS is the same
    # pixels either way.
    page.emulate_media(color_scheme="light")
    until(
        page,
        "() => window.matchMedia('(prefers-color-scheme: light)').matches",
        what="the page saw the OS turn light",
    )
    assert page.evaluate(STATE) == {"theme": "dark", "mode": "dark", "pref": "dark"}


def test_a_pin_survives_a_flip_the_tab_never_saw(page, site_url):
    """The case that actually happens — the OS flips with the tab closed,
    so no matchMedia event is ever delivered. Under the old rule the
    stored OS value expired the choice here; there is nothing to expire
    it against now, and nothing should."""
    state = _open(page, site_url, os_theme="dark", pref="light")
    assert state == {"theme": "light", "mode": "light", "pref": "light"}


def test_system_follows_a_live_os_flip(page, site_url):
    """The other side of the listener: a page that has NOT been pinned
    moves with the OS, and `announceTheme` fires so a Mermaid diagram
    re-renders on the incoming palette."""
    _open(page, site_url, os_theme="light")
    page.evaluate(
        "() => { window.__themeEvents = 0;"
        " window.addEventListener('oku:theme-changed', () => window.__themeEvents++); }"
    )
    page.emulate_media(color_scheme="dark")
    page.wait_for_function("() => document.documentElement.dataset.theme === 'dark'")
    assert page.evaluate(STATE) == {"theme": "dark", "mode": "system", "pref": None}
    assert page.evaluate("() => window.__themeEvents") >= 1


def test_a_preference_from_an_older_kit_is_honoured_and_rewritten(page, site_url):
    """Kits under the two-stop rule stored `<theme>@<os-at-choice>` and
    expired the choice once the OS moved on. There is no expiry now, so
    the first field is simply that reader's pin — honoured, and rewritten
    to the bare form so the migration happens once rather than on every
    load."""
    state = _open(page, site_url, os_theme="dark", pref="dark@light")
    assert state == {"theme": "dark", "mode": "dark", "pref": "dark"}


def test_a_stored_value_that_names_no_theme_falls_back_to_system(page, site_url):
    """Anything the kit cannot read is System, which is the state that
    needs no key — so a junk value cannot pin a reader to a theme they
    did not choose and cannot get out of."""
    state = _open(page, site_url, os_theme="light", pref="sepia")
    assert state == {"theme": "light", "mode": "system", "pref": None}


def test_the_stop_in_force_is_still_pressed_after_the_os_moves_it(page, site_url):
    """A panel left open while the OS flips: the page moved, so the
    control has to move with it. It syncs off `oku:theme-changed`, never
    off the click handler that happened to fire it — and the OS flip is
    the case that proves the difference, because no click was involved."""
    _open(page, site_url, os_theme="light")
    assert _pressed(page) == ["system"]
    page.emulate_media(color_scheme="dark")
    page.wait_for_function("() => document.documentElement.dataset.theme === 'dark'")
    assert page.locator(MENU).is_visible(), "the panel closed on an OS flip"
    assert _pressed(page) == ["system"], "System stopped being the pressed stop when the OS moved"
