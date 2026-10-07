"""Measure, in a running sandbox IDE, that the preview and its editor follow each other.

Two directions, both through the real IDE:

1. A heading in the page is double-clicked over CDP. The page must not move,
   and idea.log must show the reveal the plugin received (the line, the
   page's top line, and the editor's top line after it scrolled — the last
   two should agree). The reveal also puts keyboard focus in the editor,
   which is what the second half needs.
2. Page Down / Page Up are pressed in the sandbox — keys that move the caret
   and never change the text. After each, the page is read over CDP: the
   plugin leaves the editor's top line in `window.__okuFollow`, and
   `OkuRenderer.lineAt(0)` says which source line the page has at its top.
   They should agree, except where the page has reached its end.

The sandbox is brought to the front for the keys (System Events only sends
them to the front process), and the app that was in front is given focus
back afterwards. A locked screen moves focus nowhere, so the tool refuses.

    uv run python ide/intellij/tools/follow_ide.py <page.md>
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from edit_sync_ide import front_pid, osa, screen_locked
from probe_ide import CDP, name, preview_pages, wait

LOG = Path(__file__).resolve().parent.parent / ".intellijPlatform/sandbox"
PAGE_DOWN, PAGE_UP = 121, 116

READ = """() => ({
  follow: window.__okuFollow ?? null,
  top: window.OkuRenderer && OkuRenderer.lineAt ? OkuRenderer.lineAt(0) : null,
  y: Math.round(window.scrollY),
  height: document.documentElement.scrollHeight,
  max: document.documentElement.scrollHeight - innerHeight,
})"""


def idea_log() -> Path:
    return max(LOG.glob("**/idea.log"), key=lambda p: p.stat().st_mtime)


def sandbox_pid() -> int:
    """The IDE is the parent of the Chromium serving CDP on 9222."""
    lsof = subprocess.run(["lsof", "-nP", "-tiTCP:9222", "-sTCP:LISTEN"], capture_output=True, text=True)
    cef = int(lsof.stdout.split()[0])
    return int(subprocess.run(["ps", "-o", "ppid=", "-p", str(cef)], capture_output=True, text=True).stdout)


def bring_front(pid: int) -> None:
    osa(
        f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true'
    )


def key(code: int, ide: int) -> bool:
    """Press a key in the sandbox, or press nothing and say so.

    Checked before every key, not once: an app that takes focus back a
    second after the sandbox came forward (measured: Brave, every time)
    otherwise receives the keys meant for the editor.
    """
    front = front_pid()
    if front != ide:
        print(json.dumps({"stopped": f"focus left the sandbox for pid {front}; no key sent to it"}))
        return False
    osa(f'tell application "System Events" to key code {code}')
    return True


def reading(pg) -> dict:
    got = pg.evaluate(READ)
    got["at_end"] = got["y"] >= got["max"] - 1
    if got["follow"] is not None and got["top"] is not None:
        got["page_minus_editor"] = round(got["top"] - got["follow"], 3)
    return got


def main() -> int:
    if screen_locked():
        print("the screen is locked: focus goes nowhere and no key reaches the sandbox")
        return 1
    page_md = Path(sys.argv[1]).resolve()
    ide = sandbox_pid()
    before_front = front_pid()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        pages = [pg for pg in preview_pages(browser) if name(pg.url) == page_md.with_suffix(".html").name]
        if not pages:
            print("no preview of", page_md.name)
            return 1
        pg = pages[0]
        ready = wait(
            lambda: pg.evaluate("() => !!window.__okuRendered && OkuRenderer.lineAt(0) !== null"), 60
        )
        print(json.dumps({"rendered_with_lines_s": ready}))
        if ready is None:
            return 1
        try:
            bring_front(ide)
            time.sleep(0.5)
            # Not proven by an unlocked screen: with no GUI session on the
            # console the call returns and nothing comes forward.
            if front_pid() != ide:
                print("the sandbox did not come to the front; no key would reach it")
                return 1
            # 1. The page's double-click, a few headings down.
            pg.evaluate("() => window.scrollTo({top: innerHeight * 3, behavior: 'instant'})")
            time.sleep(0.5)
            target = pg.evaluate(
                """() => {
                  // The next heading below the window's top, brought to 200px.
                  const h = [...document.querySelectorAll('main section > h2')]
                    .find((h) => h.getBoundingClientRect().top > 0);
                  if (!h) return null;
                  window.scrollBy({ top: h.getBoundingClientRect().top - 200, behavior: 'instant' });
                  h.setAttribute('data-follow-probe', '1');
                  const r = h.getBoundingClientRect();
                  return { id: h.parentElement.id, top: Math.round(r.top), line: OkuRenderer.lineAt(r.top + 1) };
                }"""
            )
            if target is None:
                print("no heading in the window to double-click")
                return 1
            log = idea_log()
            mark = log.stat().st_size
            y0 = reading(pg)["y"]
            pg.dblclick("[data-follow-probe]", position={"x": 12, "y": 6})
            time.sleep(1.5)
            with log.open(encoding="utf-8", errors="replace") as f:
                f.seek(mark)
                seen = [ln.strip().split(" - ", 1)[-1] for ln in f if "oku preview: reveal" in ln]
            print(json.dumps({"double_clicked": target, "page_y": [y0, reading(pg)["y"]], "log": seen}))

            # 2. The editor's keys, the page following.
            # Read twice: a page that lands wrong and one that drifts after
            # landing (something above it changing height) need different fixes.
            for code in [PAGE_DOWN] * 4 + [PAGE_UP] * 2:
                if not key(code, ide):
                    return 1
                time.sleep(0.25)
                soon = reading(pg)
                time.sleep(1.0)
                later = reading(pg)
                print(
                    json.dumps({"key": "down" if code == PAGE_DOWN else "up", "soon": soon, "later": later})
                )
        finally:
            osa(
                f'tell application "System Events" to set frontmost of (first process whose unix id is {before_front}) to true'
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
