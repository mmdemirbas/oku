"""Reaching the presentation menu from a test.

Theme, column width, text size, language and snippet placeholders left
the top-right corner for one panel behind one button. Every test that
used to click `.theme-toggle` opens that panel first, and it does it
through here rather than each file writing the same three lines — these
selectors belong to the kit, and one copy of them is the copy that gets
updated when they move.
"""

from __future__ import annotations

MENU = ".okt-chrome-menu"
BUTTON = ".ctrl-btn.menu-toggle"


def open_menu(page):
    """Open the panel and return a locator for it. Idempotent."""
    page.wait_for_selector(BUTTON, state="visible")
    if page.locator(f"{MENU}:not([hidden])").count() == 0:
        page.click(BUTTON)
    page.wait_for_selector(f"{MENU}:not([hidden])")
    return page.locator(MENU)


def close_menu(page):
    if page.locator(f"{MENU}:not([hidden])").count():
        page.keyboard.press("Escape")
        page.wait_for_selector(MENU, state="hidden")


def set_theme(page, choice: str):
    """Pick `system`, `light` or `dark` in the menu's theme row."""
    open_menu(page)
    page.click(f'{MENU} [data-theme-choice="{choice}"]')


def flip_theme(page):
    """Pin the theme the page is NOT painted in. Returns the theme landed
    on. Deliberately picks a pinned stop rather than System — a caller
    that flips the theme wants the page to have flipped, and System is a
    stop whose colour depends on the OS the test is emulating."""
    now = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    other = "light" if now == "dark" else "dark"
    set_theme(page, other)
    return other


def set_width(page, mode: str):
    open_menu(page)
    page.click(f'{MENU} [data-width="{mode}"]')


def step_text_scale(page, direction: int, times: int = 1):
    """Click the text-size stepper. The panel stays open between clicks,
    which is the point of it being a panel."""
    open_menu(page)
    selector = f'{MENU} [data-step="{direction}"]'
    for _ in range(times):
        page.click(selector)
    return page.evaluate("() => parseFloat(document.documentElement.dataset.textScale || 1)")
