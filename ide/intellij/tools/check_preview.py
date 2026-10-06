"""Open a page preview.py wrote, over file:// in headless Chromium, and say
what rendered. The plugin's JCEF panel is Chromium too, so this is the
browser half of the PoC measured without the IDE.

    uv run python ide/intellij/tools/check_preview.py tmp/ide-preview/reference.html
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROBE = """() => ({
  rendered: !!window.__okuRendered,
  theme: document.documentElement.dataset.theme,
  lang: document.documentElement.lang,
  sections: document.querySelectorAll('main section').length,
  charts: document.querySelectorAll('oku-chart').length,
  chartSvgs: document.querySelectorAll('oku-chart svg, oku-chart .okc-bar').length,
  diagrams: document.querySelectorAll('oku-diagram').length,
  diagramSvgs: document.querySelectorAll('oku-diagram svg').length,
  tables: document.querySelectorAll('main table').length,
  codeLines: document.querySelectorAll('.okt-code-line').length,
  tocLinks: document.querySelectorAll('page-toc a').length,
  treeRows: document.querySelectorAll('page-nav a').length,
  fileChips: document.querySelectorAll('oku-filepath').length,
  scrollY: window.scrollY,
  shim: !!window.__okuIdePreview,
})"""


def main() -> int:
    page_path = Path(sys.argv[1]).resolve()
    url = page_path.as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        failed: list[str] = []
        page.on("requestfailed", lambda r: failed.append(r.url))
        page.goto(url)
        page.wait_for_function("window.__okuRendered === true", timeout=15000)
        page.wait_for_timeout(2500)  # mermaid + charts settle
        first = page.evaluate(PROBE)
        # The plugin reloads on every edit; the shim must bring the reader
        # back to where they were.
        page.evaluate("window.scrollTo({top: 2400, behavior: 'instant'})")
        page.wait_for_timeout(300)
        page.reload()
        page.wait_for_function("window.__okuRendered === true", timeout=15000)
        page.wait_for_timeout(120)
        early = page.evaluate("window.scrollY")
        page.wait_for_timeout(800)
        after = page.evaluate("window.scrollY")
        browser.close()
    print(
        json.dumps(
            {
                "first": first,
                "scrollY_after_reload": [early, after],
                "console_errors": errors[:8],
                "failed_requests": failed[:8],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
