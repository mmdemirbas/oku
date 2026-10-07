"""Where a preview page's load goes in Chromium, before and after it paints.

Opens each HTML file (what `oku preview` wrote; its path is in the reply's
`html`) in headless Chromium, four times, and prints from the last three:
when the kit announced the page drawn (`oku:rendered`), DOMContentLoaded,
the first contentful paint, `load`, and the total and longest main-thread
tasks. With `--forced` it also records a trace and lists the style and
layout passes a script forced, by the function and line that forced them —
a pass read straight after a write is how a loop over cells comes to
restyle the whole document once per cell.

    uv run python ide/intellij/tools/page_load.py [--forced] PAGE.html …

The embedded browser in the IDE is a Chromium too, but not this one, and
it draws off screen; these numbers rank the work, they are not the IDE's.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TIMES = """
window.__t = {};
addEventListener('DOMContentLoaded', () => __t.dcl = performance.now());
addEventListener('load', () => __t.load = performance.now());
addEventListener('oku:rendered', () => __t.rendered = performance.now());
new PerformanceObserver(l => { for (const e of l.getEntries()) {
  __t.tasks = (__t.tasks || 0) + e.duration; __t.longest = Math.max(__t.longest || 0, e.duration); } })
  .observe({type: 'longtask', buffered: true});
new PerformanceObserver(l => { for (const e of l.getEntries())
  if (e.name === 'first-contentful-paint') __t.fcp = e.startTime; }).observe({type: 'paint', buffered: true});
"""


def times(browser, html: Path) -> list[dict]:
    runs = []
    for _ in range(4):
        context = browser.new_context(viewport={"width": 700, "height": 900})
        pg = context.new_page()
        pg.add_init_script(TIMES)
        pg.goto(html.as_uri())
        pg.wait_for_function("window.__t && window.__t.rendered && window.__t.load", timeout=30000)
        pg.wait_for_timeout(300)
        runs.append({k: round(v) for k, v in pg.evaluate("window.__t").items()})
        context.close()
    return runs[1:]


def forced(browser, html: Path) -> None:
    pg = browser.new_page(viewport={"width": 700, "height": 900})
    browser.start_tracing(
        page=pg, categories=["devtools.timeline", "disabled-by-default-devtools.timeline.stack"]
    )
    pg.goto(html.as_uri(), wait_until="load")
    pg.wait_for_timeout(2000)
    trace = json.loads(browser.stop_tracing())
    pg.close()
    events = trace["traceEvents"] if isinstance(trace, dict) else trace
    by: dict[str, list] = collections.defaultdict(lambda: [0, 0.0])
    for e in events:
        if e.get("name") not in ("UpdateLayoutTree", "Layout") or e.get("ph") != "X":
            continue
        stack = (e.get("args", {}).get("beginData") or {}).get("stackTrace")
        if not stack:
            continue
        top = stack[0]
        key = (
            f"{e['name'][:6]} {top.get('functionName') or '(anonymous)'} line {top.get('lineNumber', 0) + 1}"
        )
        by[key][0] += 1
        by[key][1] += e.get("dur", 0) / 1000
    total = sum(v[1] for v in by.values())
    print(f"  forced: {sum(v[0] for v in by.values())} passes, {total:.0f} ms")
    for key, (n, ms) in sorted(by.items(), key=lambda kv: -kv[1][1])[:12]:
        print(f"    {ms:7.1f} ms {n:5d}x  {key}")


def main() -> None:
    args = sys.argv[1:]
    with_forced = "--forced" in args
    pages = [Path(a).resolve() for a in args if a != "--forced"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for html in pages:
            print(html.name, json.dumps(times(browser, html)))
            if with_forced:
                forced(browser, html)
        browser.close()


if __name__ == "__main__":
    main()
