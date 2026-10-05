#!/usr/bin/env python3
"""Capture the README's and the landing page's screenshots from the docs.

    uv run python tools/landing_shots.py [--no-build]

Builds docs/ with this checkout's kit, serves docs/dist/site on loopback
(search needs the HTTP tree: Pagefind fetches its index), and writes the
six PNGs into .github/assets/ (the README's) and site/assets/ (the landing
page's copies). Each shot puts the page in a stated state and measures it
before capturing — the drawer pinned, the menu open, a heading at a given
y — and prints those figures, so a re-run after a kit change shows the
same scene rather than whatever the page happened to be doing, and the
record of what was captured is the output of the run.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from oku import cli

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = ROOT / ".github" / "assets"
MIRROR = ROOT / "site" / "assets"
SCALE = 2


def _ready(page: Page) -> None:
    page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    page.evaluate("() => document.fonts.ready.then(() => true)")
    # Mermaid and the compare-card previews draw after the page says it
    # rendered; both are done once no node is still waiting on a frame.
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(900)


def _scroll_to(page: Page, selector: str, y: int) -> float:
    """Put the element's top at `y` and return where it actually landed."""
    page.evaluate(
        """([sel, y]) => { const el = document.querySelector(sel);
             window.scrollTo({top: el.getBoundingClientRect().top + scrollY - y, behavior: 'instant'}); }""",
        [selector, y],
    )
    page.wait_for_timeout(400)
    return page.evaluate("(sel) => document.querySelector(sel).getBoundingClientRect().top", selector)


def _box(page: Page, selector: str) -> list[int]:
    r = page.evaluate(
        """(sel) => { const r = document.querySelector(sel).getBoundingClientRect();
             return [r.left, r.top, r.width, r.height]; }""",
        selector,
    )
    return [round(v) for v in r]


def hero(page: Page, base: str) -> str:
    """The charts reference with the drawer pinned and the menu open."""
    page.goto(f"{base}/charts.html")
    _ready(page)
    # A script click: a pointer moved onto the button would peek first.
    page.evaluate("() => document.querySelector('.ctrl-btn.drawer-toggle').click()")
    page.wait_for_function("() => document.body.classList.contains('drawer-pinned')")
    page.wait_for_timeout(500)
    top = _scroll_to(page, "#chart-fn-composition", 110)
    page.evaluate("() => document.querySelector('.ctrl-btn.menu-toggle').click()")
    page.wait_for_function(
        "() => document.querySelector('.ctrl-btn.menu-toggle').getAttribute('aria-expanded') === 'true'"
    )
    page.wait_for_timeout(400)
    return f"composition h4 top {top:.0f}, page-nav {_box(page, 'page-nav')}, main {_box(page, 'main')}"


def table(page: Page, base: str) -> str:
    """A table fence beside what it renders to."""
    page.goto(f"{base}/tables.html")
    _ready(page)
    top = _scroll_to(page, "#tables-flat", 100)
    ex = page.evaluate(
        """() => { const h = document.querySelector('#tables-flat');
             let n = h.nextElementSibling; while (n && !n.matches('.example, [class*=example]')) n = n.nextElementSibling;
             const r = n.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom)]; }"""
    )
    return f"flat-rows heading top {top:.0f}, example {ex[0]}..{ex[1]} of {page.viewport_size['height']}"


def diagrams(page: Page, base: str) -> str:
    """A mermaid fence beside its diagram, in the dark theme."""
    page.goto(f"{base}/diagrams.html")
    _ready(page)
    page.wait_for_function(
        "() => document.querySelector('#diagram') && [...document.querySelectorAll('.okd-render svg')]"
        ".some(s => s.getBoundingClientRect().width > 100)"
    )
    top = _scroll_to(page, "#diagrams > h2, h2#diagrams", 84)
    ex = page.evaluate(
        """() => { const h = document.querySelector('#diagram');
             let n = h.nextElementSibling; while (n && !n.querySelector('.okd-render svg')) n = n.nextElementSibling;
             const r = n.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom)]; }"""
    )
    return f"section heading top {top:.0f}, first rendered example {ex[0]}..{ex[1]} of {page.viewport_size['height']}"


def search(page: Page, base: str) -> str:
    """Search open over the reference page."""
    page.goto(f"{base}/reference.html")
    _ready(page)
    page.evaluate("() => document.querySelector('.ctrl-btn[class*=search]').click()")
    page.wait_for_selector(".search-input", state="visible")
    page.fill(".search-input", "chart")
    page.wait_for_function(
        "() => /\\d/.test((document.querySelector('.search-status') || {}).textContent || '')"
    )
    page.wait_for_timeout(900)
    status = page.evaluate("() => document.querySelector('.search-status').textContent.trim()")
    return f"status '{status}'"


def mobile(page: Page, base: str) -> str:
    """The charts reference on a phone, at the top."""
    page.goto(f"{base}/charts.html")
    _ready(page)
    width = page.evaluate("() => document.documentElement.scrollWidth")
    return f"scrollWidth {width} of {page.viewport_size['width']}"


SHOTS = [
    # name, scene, viewport, colour scheme
    ("readme-light.png", hero, (1440, 900), "light"),
    ("readme-dark.png", hero, (1440, 900), "dark"),
    # Taller than the others: the fence wraps in a half-column, and the
    # heading has to clear the rail with the whole example below it.
    ("landing-table.png", table, (1080, 740), "light"),
    ("landing-diagrams-dark.png", diagrams, (1080, 675), "dark"),
    ("landing-search.png", search, (1080, 675), "light"),
    ("landing-charts-mobile.png", mobile, (390, 844), "light"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-build", action="store_true", help="capture the dist/site already built")
    args = ap.parse_args()
    if not args.no_build:
        subprocess.run([sys.executable, "-m", "oku.cli", "build"], cwd=DOCS, check=True)
    site = DOCS / "dist" / "site"
    handler = functools.partial(cli._VerifySiteHandler, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, scene, (w, h), scheme in SHOTS:
                ctx = browser.new_context(
                    viewport={"width": w, "height": h}, device_scale_factor=SCALE, color_scheme=scheme
                )
                page = ctx.new_page()
                note = scene(page, base)
                page.screenshot(path=str(OUT / name))
                ctx.close()
                if MIRROR.is_dir():
                    shutil.copy(OUT / name, MIRROR / name)
                print(f"{name:28} {w}x{h}@{SCALE} {scheme:5}  {note}")
            browser.close()
    finally:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
