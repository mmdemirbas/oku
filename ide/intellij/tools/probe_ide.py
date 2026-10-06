"""Measure the preview INSIDE a running sandbox IDE, over CDP.

`./gradlew runIde` starts the IDE with `ide.browser.jcef.debug.port=9222`, so
its embedded Chromium is reachable the way a test reaches any browser:

    uv run python ide/intellij/tools/probe_ide.py probe [shot.png]
    uv run python ide/intellij/tools/probe_ide.py targets
    uv run python ide/intellij/tools/probe_ide.py click '<css selector>'
"""

from __future__ import annotations

import json
import sys
import time

from playwright.sync_api import sync_playwright

from check_preview import PROBE

CDP = "http://127.0.0.1:9222"

# What the edit checks append to a page, and look for in its preview.
MARKER = "PoC-MARKER-4711"
ADDED = f"\n## IDE canlı güncelleme denemesi {{#ide-live}}\n\nBu paragraf {MARKER} diskten eklendi.\n"


def preview_pages(browser):
    return [pg for ctx in browser.contexts for pg in ctx.pages if "oku-preview" in pg.url]


def name(url: str) -> str:
    """`index.html` for `file:///…/index.html?r=3#tldr`: the plugin adds a
    query per render and the kit rewrites the hash as the reader scrolls."""
    return url.split("#", 1)[0].split("?", 1)[0].rsplit("/", 1)[-1]


def wait(fn, timeout=20.0):
    """Seconds until `fn()` is true, or None."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            if fn():
                return round(time.monotonic() - start, 2)
        except Exception:  # a page mid-reload
            pass
        time.sleep(0.1)
    return None


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        pages = preview_pages(browser)
        if cmd == "targets":
            print(json.dumps([pg.url for pg in pages], indent=1))
            return 0
        if not pages:
            print("no preview page")
            return 1
        page = pages[-1]
        if cmd == "probe":
            out = page.evaluate(PROBE)
            out["url"] = page.url
            out["viewport"] = page.evaluate("[innerWidth, innerHeight]")
            print(json.dumps(out, indent=1))
            if len(sys.argv) > 2:
                page.screenshot(path=sys.argv[2])
        elif cmd == "click":
            page.click(sys.argv[2])
            print("clicked", sys.argv[2])
        elif cmd == "eval":
            print(json.dumps(page.evaluate(sys.argv[2]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
