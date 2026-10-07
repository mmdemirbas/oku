"""Edit a page on disk and wait for the sandbox's preview, without touching focus.

`edit_sync_ide.py` times an edit by activating the sandbox, which is what
makes the IDE read a file changed on disk at once. This one never moves
focus, so it can run while someone is using the machine: it waits for the
IDE's own background refresh instead (10-15 s measured), so the time it
reports says nothing about the plugin's speed. What it does say is whether
an edit reaches the preview at all, and whether it arrived without a reload.

    uv run python ide/intellij/tools/quiet_edit_ide.py /abs/page.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from probe_ide import ADDED, CDP, MARKER, name, preview_pages, wait

SHOWS = f"document.body.innerText.includes('{MARKER}')"


def main() -> int:
    page_md = Path(sys.argv[1]).resolve()
    original = page_md.read_bytes()
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        pages = [pg for pg in preview_pages(browser) if name(pg.url) == page_md.with_suffix(".html").name]
        if not pages:
            print("no preview of", page_md.name)
            return 1
        pg = pages[0]
        # A reload throws this away; an update in place keeps it.
        pg.evaluate("() => { window.__okuSameDocument = true; }")
        try:
            page_md.write_bytes(original + ADDED.encode())
            report["edit_shown_s"] = wait(lambda: pg.evaluate(SHOWS), timeout=45)
            report["reloaded"] = pg.evaluate("() => !window.__okuSameDocument")
        finally:
            page_md.write_bytes(original)
        report["revert_shown_s"] = wait(lambda: not pg.evaluate(SHOWS), timeout=45)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
