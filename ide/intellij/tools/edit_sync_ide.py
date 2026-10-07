"""Edit pages on disk, make the sandbox IDE sync, and time each preview.

The IDE reads external changes when its window is activated or a tab opens
(not while it sits in the background), so after writing, this brings the
sandbox IDE to the front, and the activation is what syncs. Focus goes back
to whichever app had it, between the edit and the revert and at the end. Typing in the editor does not
need any of this; it changes the Document directly.

Every file named gets the marker; the first is the tab in front, the rest
show what happens to a preview in a background tab.

    uv run python ide/intellij/tools/edit_sync_ide.py IDE_PID /abs/front.md [/abs/background.md ...]
"""

from __future__ import annotations

import json
import sys
import time
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

from probe_ide import ADDED, CDP, MARKER, name, preview_pages, wait


def osa(script: str) -> str:
    done = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return (done.stderr or done.stdout).strip()


def front_app() -> str:
    return osa('tell application "System Events" to get name of (first process whose frontmost is true)')


def front_pid() -> int:
    return int(
        osa('tell application "System Events" to get unix id of (first process whose frontmost is true)')
    )


def screen_locked() -> bool:
    """A locked screen moves focus nowhere, so the IDE is never activated and
    syncs on its background schedule instead: every time measured is then
    10-15 s and says nothing about the preview."""
    done = subprocess.run(["ioreg", "-n", "Root", "-d1"], capture_output=True, text=True)
    return '"CGSSessionScreenIsLocked"=Yes' in done.stdout


def sync(pid: int) -> str:
    """Bring the sandbox IDE to the front; activation is what syncs."""
    return (
        osa(
            f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true'
        )
        or "ok"
    )


def give_back(app: str) -> None:
    osa(f'tell application "{app}" to activate')


def main() -> int:
    pid = int(sys.argv[1])
    files = [Path(a) for a in sys.argv[2:]]
    originals = {f: f.read_bytes() for f in files}
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        pages = {name(pg.url): pg for pg in preview_pages(browser)}
        report["targets"] = sorted(pages)
        if screen_locked():
            print(
                "the screen is locked: focus cannot move, so nothing measured here would mean anything",
                file=sys.stderr,
            )
            return 2
        # Never "give back" to the sandbox itself: activating it before the
        # revert is written means the sync after it is no activation at all.
        user_app = "Finder" if front_pid() == pid else front_app()
        # The IDE syncs on ACTIVATION: one already in front never activates,
        # and a freshly started sandbox usually is in front.
        give_back("Finder")
        time.sleep(0.3)
        report["handed_away"] = front_pid() != pid
        # A reload throws this away; an update in place keeps it.
        for pg in pages.values():
            pg.evaluate("() => { window.__okuSameDocument = true; }")
        try:
            for f in files:
                f.write_bytes(originals[f] + ADDED.encode())
            report["sync_status"] = sync(pid)
            for f in files:
                pg = pages.get(f.with_suffix(".html").name)
                report[f.name] = (
                    None
                    if pg is None
                    else wait(
                        lambda pg=pg: pg.evaluate(f"document.body.innerText.includes('{MARKER}')"), timeout=15
                    )
                )
                if pg is not None:
                    report[f.name + " reloaded"] = pg.evaluate("() => !window.__okuSameDocument")
        finally:
            give_back(user_app)
            for f in files:
                f.write_bytes(originals[f])
        time.sleep(0.5)
        report["handed_away_for_revert"] = front_pid() != pid
        sync(pid)
        report["reverted_" + files[0].name] = wait(
            lambda: (
                not pages[files[0].with_suffix(".html").name].evaluate(
                    f"document.body.innerText.includes('{MARKER}')"
                )
            ),
            timeout=15,
        )
        give_back(user_app)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
