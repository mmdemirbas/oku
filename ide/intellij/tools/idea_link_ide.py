"""The kit's "open in editor" link, followed inside the IDE preview.

On macOS the kit's editor row emits `idea://open?file=…&line=…`
(chrome.js `__okuEditors`); the plugin intercepts it and opens the file in
the IDE instead of letting the panel navigate. Run against a sandbox IDE
whose preview shows docs/index.md; the target file must not be open yet.

    uv run python ide/intellij/tools/idea_link_ide.py /abs/oku/docs/glossary.md 20

The IDE log says `fileOpened <name>` when it worked; the new tab's preview
only appears over CDP once the tab is painted, so a background window
reports `tab_seconds: null` while the file is in fact open.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

from probe_ide import CDP, name, preview_pages, wait


def main() -> int:
    target = Path(sys.argv[1])
    line = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    link = f"idea://open?file={urllib.parse.quote(str(target), safe='')}&line={line}"
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        page = next(pg for pg in preview_pages(browser) if name(pg.url) == "index.html")
        before = page.url
        page.evaluate("(href) => { location.href = href; }", link)
        tab = wait(
            lambda: target.with_suffix(".html").name in {name(pg.url) for pg in preview_pages(browser)}
        )
        print(json.dumps({"link": link, "tab_seconds": tab, "panel_stayed": page.url == before}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
