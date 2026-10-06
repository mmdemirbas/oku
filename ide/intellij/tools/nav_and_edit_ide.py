"""Two checks against a running sandbox IDE that shows docs/index.md.

1. A link to another page, clicked in the preview, opens that page's .md in
   the IDE — observed as a second preview target appearing over CDP.
2. An edit made on disk reaches the open preview. The IDE syncs external
   changes when a tab opens, so the edit is written BEFORE the click and the
   new tab is what makes the IDE notice it.

    uv run python ide/intellij/tools/nav_and_edit_ide.py /abs/oku/docs
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from probe_ide import ADDED, CDP, MARKER, name, preview_pages, wait


def main() -> int:
    docs = Path(sys.argv[1])
    index = docs / "index.md"
    original = index.read_bytes()
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        before = {name(pg.url) for pg in preview_pages(browser)}
        report["targets_before"] = sorted(before)
        index_page = next(pg for pg in preview_pages(browser) if name(pg.url) == "index.html")
        index_page.evaluate("window.scrollTo({top: 600, behavior: 'instant'})")
        time.sleep(0.4)
        try:
            index.write_bytes(original + ADDED.encode())
            # A page not open yet, so its tab is something the click made.
            href = index_page.evaluate(
                "(open) => { const a = [...document.querySelectorAll('page-nav a')]"
                ".find(a => a.href.endsWith('.html') && !open.includes(a.href.split('/').pop()));"
                " a.click(); return a.href; }",
                sorted(before),
            )
            report["clicked"] = href.rsplit("/", 1)[-1]
            report["new_target_seconds"] = wait(
                lambda: {name(pg.url) for pg in preview_pages(browser)} - before
            )
            report["targets_after"] = sorted(name(pg.url) for pg in preview_pages(browser))
            report["index_preview_still_index"] = name(index_page.url) == "index.html"
            report["edit_seconds_after_click"] = wait(
                lambda: index_page.evaluate(f"document.body.innerText.includes('{MARKER}')")
            )
            report["index_scroll_after_edit"] = index_page.evaluate("scrollY")
        finally:
            index.write_bytes(original)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
