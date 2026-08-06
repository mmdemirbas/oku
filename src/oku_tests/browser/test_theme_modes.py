"""The theme button has two stops, and following the OS is not one.

The cycler used to have three — system, light, dark — and two of them
rendered identically: with the OS on dark, `system` and `dark` are the
same pixels, so the only way to tell which one you were in was to read
the icon. That is the defect the width cycler shed when it went from
four stops to three.

Following the OS survives as a policy instead. It is where the page
rests, it is re-entered without being clicked, and a choice against it
expires the next time the OS flips. These tests pin the whole rule,
including the branch a matchMedia listener cannot cover: a flip that
happens while the tab is closed.
"""

from __future__ import annotations

import pytest

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
    page.wait_for_selector(".theme-toggle")
    return page.evaluate(STATE)


def _click(page):
    page.click(".theme-toggle")
    page.wait_for_timeout(120)
    return page.evaluate(STATE)


@pytest.mark.parametrize("os_theme", ["light", "dark"])
def test_a_fresh_reader_follows_the_os(page, site_url, os_theme):
    """Nothing stored: the page is whatever the OS says, and it is in
    the following state rather than pinned to that value."""
    state = _open(page, site_url, os_theme=os_theme)
    assert state["theme"] == os_theme
    assert state["mode"] == "system"
    assert state["pref"] is None


@pytest.mark.parametrize("os_theme", ["light", "dark"])
def test_the_cycle_has_exactly_two_stops(page, site_url, os_theme):
    """Four clicks visit two themes, alternating. A third stop would
    show up here as a repeat or a third value — which is what made the
    old cycler unreadable, and what a future fourth would do again."""
    _open(page, site_url, os_theme=os_theme)
    seen = [_click(page)["theme"] for _ in range(4)]
    other = "light" if os_theme == "dark" else "dark"
    assert seen == [other, os_theme, other, os_theme], seen


def test_choosing_against_the_os_is_an_override_that_is_stored(page, site_url):
    """OS light, reader picks dark: that contradicts the OS, so it is a
    real choice and it is written down with the OS value it was made
    against."""
    _open(page, site_url, os_theme="light")
    state = _click(page)
    assert state == {"theme": "dark", "mode": "dark", "pref": "dark@light"}


def test_choosing_what_the_os_already_shows_hands_control_back(page, site_url):
    """The second click lands on the OS's own theme. That is not an
    override of anything, so the key is dropped and the page is
    following again — which is also the route back to auto: two clicks,
    no hidden gesture, no third stop."""
    _open(page, site_url, os_theme="light")
    _click(page)
    state = _click(page)
    assert state == {"theme": "light", "mode": "system", "pref": None}


def test_an_override_expires_when_the_os_flips_under_a_live_tab(page, site_url):
    """The reader pinned dark against a light OS. Evening comes, the OS
    goes dark on its own, and the choice is spent — the page follows
    from here rather than staying pinned to a value that now agrees with
    the OS by accident."""
    _open(page, site_url, os_theme="light")
    assert _click(page)["mode"] == "dark"
    page.emulate_media(color_scheme="dark")
    page.wait_for_timeout(200)
    assert page.evaluate(STATE) == {"theme": "dark", "mode": "system", "pref": None}


def test_an_override_expires_across_a_flip_the_tab_never_saw(page, site_url):
    """The same rule, for the case that actually happens: the OS flips
    with the tab closed, so no matchMedia event is ever delivered. The
    stored OS value is what catches it at boot."""
    state = _open(page, site_url, os_theme="dark", pref="dark@light")
    assert state == {"theme": "dark", "mode": "system", "pref": None}


def test_an_override_survives_a_reload_while_the_os_holds_still(page, site_url):
    """The other half of the same test — expiry must be caused by the OS
    moving, not by every page load."""
    state = _open(page, site_url, os_theme="light", pref="dark@light")
    assert state == {"theme": "dark", "mode": "dark", "pref": "dark@light"}


def test_a_preference_from_an_older_kit_is_discarded_not_misread(page, site_url):
    """Kits before this rule stored a bare theme. Read as the new format
    it has no OS value to compare, so it cannot be honoured — it must be
    dropped cleanly rather than pinning a reader forever."""
    state = _open(page, site_url, os_theme="light", pref="dark")
    assert state == {"theme": "light", "mode": "system", "pref": None}


@pytest.mark.parametrize("os_theme", ["light", "dark"])
def test_the_icon_reports_the_theme_that_is_on(page, site_url, os_theme):
    """Sun while light, moon while dark, exactly one of them rendered.
    The icon answers "what am I looking at", not "what will the click
    do" — the width toggle's segments set that convention."""
    _open(page, site_url, os_theme=os_theme)
    for expected in (os_theme, "light" if os_theme == "dark" else "dark"):
        shown = page.evaluate(
            """() => ['sun', 'moon'].filter(n => {
                 const el = document.querySelector('.theme-toggle .icon-' + n);
                 return el && getComputedStyle(el).display !== 'none';
               })"""
        )
        assert shown == (["sun"] if expected == "light" else ["moon"]), (
            expected,
            shown,
        )
        _click(page)


def test_the_auto_dot_marks_following_and_goes_out_when_pinned(page, site_url):
    """The one mark that separates the two states the button cannot show
    by icon. It is lit while the page follows the OS and out once the
    reader has chosen against it — and it is paint only, so lighting it
    cannot move the button under the pointer."""
    dot = """() => {
      const b = document.querySelector('.theme-toggle');
      const s = getComputedStyle(b, '::after');
      const r = b.getBoundingClientRect();
      return {opacity: parseFloat(s.opacity), w: parseFloat(s.width),
              box: [Math.round(r.x), Math.round(r.y), r.width, r.height]};
    }"""
    _open(page, site_url, os_theme="light")
    following = page.evaluate(dot)
    assert following["opacity"] == 1
    assert following["w"] >= 4, following

    _click(page)
    pinned = page.evaluate(dot)
    assert pinned["opacity"] == 0, pinned
    assert pinned["box"] == following["box"], (following["box"], pinned["box"])
