"""A preview that failed comes back once the cause is fixed, without a restart.

Start the sandbox with an oku that fails (tools/broken_oku.sh) and two pages
open, then run this. It checks that every panel says what to update, fixes
oku, and then takes the two ways back: an edit re-renders the page in front,
and selecting the other tab — here by following its row in the site tree —
retries a tab nobody edited. That second one is the case a retry on edit
alone left on its error.

    touch ide/intellij/build/oku-broken
    ./gradlew runIde -PokuExecutable=$PWD/tools/broken_oku.sh -PopenPaths=/abs/docs,/abs/docs/index.md
    uv run python ide/intellij/tools/retry_ide.py <ide-pid> /abs/docs/index.md architecture
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from edit_sync_ide import front_app, front_pid, give_back, screen_locked, sync
from probe_ide import ADDED, CDP, MARKER, name, preview_pages, wait

FLAG = Path(__file__).resolve().parent.parent / "build" / "oku-broken"


def href(pg) -> str:
    # From the page: pg.url only moves while Playwright's loop runs, and
    # wait() sleeps without running it.
    try:
        return pg.evaluate("location.href")
    except Exception:
        return pg.url


def main() -> int:
    pid, front, other = int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)

        def panels() -> dict[str, object]:
            return {name(href(pg)): pg for pg in preview_pages(browser)}

        def says() -> list[str]:
            return [pg.inner_text("body") for pg in preview_pages(browser) if name(href(pg)) == "error.html"]

        report["errors"] = says()
        if not FLAG.exists() or len(report["errors"]) < 2:
            print(f"needs {FLAG} and two panels on their error page; see the docstring", file=sys.stderr)
            return 2
        if screen_locked():
            print("the screen is locked: the IDE cannot be activated to sync the edit", file=sys.stderr)
            return 2
        FLAG.unlink()

        user = "Finder" if front_pid() == pid else front_app()
        give_back("Finder")
        time.sleep(0.3)
        report["handed_away"] = front_pid() != pid
        original = front.read_bytes()
        try:
            front.write_bytes(original + ADDED.encode())
            sync(pid)
            report["edited_page_s"] = wait(lambda: front.with_suffix(".html").name in panels(), timeout=30)
        finally:
            front.write_bytes(original)
        time.sleep(0.5)
        sync(pid)
        page = panels()[front.with_suffix(".html").name]
        wait(lambda: not page.evaluate(f"document.body.innerText.includes('{MARKER}')"), timeout=20)

        # The drawer is closed at panel width, so the row is clicked in the DOM.
        page.locator(f'page-nav a[href*="/{other}.html"]').first.evaluate("a => a.click()")
        report["selected_tab_s"] = wait(lambda: f"{other}.html" in panels(), timeout=30)
        report["panels"] = sorted(panels())
        give_back(user)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if report["edited_page_s"] is not None and report["selected_tab_s"] is not None else 1


if __name__ == "__main__":
    sys.exit(main())
