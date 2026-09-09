#!/usr/bin/env python3
"""Measure what every chart type offers a reader, and print the table.

The cell values in `docs/roadmap.md`'s interactivity table come from
this. `test_authority_agreement.py` holds the table's ROWS against the
chart types the kit ships — that is a set comparison and it is cheap —
but whether a given chart fades its siblings on hover is a browser
measurement, so the cells are refreshed by running this and pasting the
result. Run it when a chart type lands or an interaction changes:

    uv run python tools/chart_capabilities.py

Two things about the method are load-bearing, both learned by getting it
wrong first. **One chart per page, and one page LOAD per chart** — the
first version hovered charts on a shared 53-chart page and returned
different answers on different runs, because an earlier hover, pin or
focus was still in effect. And **every hover is confirmed to have
landed** before anything is read off it, rather than measured after a
fixed wait.

Reproducibility is the property the first version lacked, so it is the
one to check after changing anything here: two consecutive runs of this
script produce byte-identical `capabilities.json`. If they do not, the
table it feeds is not worth writing down.

The cursor detector matches any class the kit calls a cursor. Reading
only `.okc-generic-cursor` and `.okc-cartesian-cursor` — the two the
generic helper uses, of the seven that exist — reported ridgeline,
sparkline, gauge and the three DIV bar charts as having none, which are
exactly the charts the old footnote named as the sweep-axis ones.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from oku import cli  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
EX = json.loads((ROOT / "kit/schema/examples.json").read_text())["charts"]
CHROME = (ROOT / "kit/chrome.js").read_text()
MARKS = ", ".join(re.findall(r"\brich\('([^']+)'", CHROME) + [".okc-dot"])

docs = (ROOT / "tmp/capsweep").resolve() / "docs"
docs.mkdir(parents=True, exist_ok=True)
for n in EX:
    (docs / f"{n}.md").write_text(
        f"---\ntitle: {n}\nsummary: One {n} chart.\n---\n\n## {n} " + "{#c}" + "\n\n"
        "```oku-chart\n" + json.dumps(EX[n], separators=(",", ":")) + "\n```\n",
        encoding="utf-8",
    )
cwd = pathlib.Path.cwd()
os.chdir(docs)
try:
    assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
finally:
    os.chdir(cwd)

SIG = """() => [...document.querySelectorAll('#c svg *, #c .bar-chart *, #c .bar-chart-multi *')]
  .map((e) => (e.getAttribute('class') || '') + '|' + getComputedStyle(e).opacity
              + '|' + getComputedStyle(e).fillOpacity).join(';')"""
TIP = """() => { const t = [...document.querySelectorAll('#c .okc-tooltip')]
  .find((e) => e.classList.contains('visible'));
  return t ? { text: (t.textContent || '').trim(), hint: /click to pin/.test(t.textContent),
               pinned: t.classList.contains('pinned') } : null; }"""
FIND = """(sel) => { const els = [...document.querySelectorAll('#c ' + sel)];
  for (const e of els.slice(0, 12)) { const r = e.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    for (let fy = 0.3; fy < 1; fy += 0.2) for (let fx = 0.3; fx < 1; fx += 0.2) {
      const x = r.left + r.width * fx, y = r.top + r.height * fy;
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
      const hit = document.elementFromPoint(x, y);
      if (hit === e || e.contains(hit)) return { x, y };
    } } return null; }"""
CURSOR_PT = """(sel) => { const svg = document.querySelector('#c svg.okc-svg');
  const line = svg && svg.querySelector('.okc-generic-cursor, .okc-cartesian-cursor');
  if (!line) return null;
  const r = svg.getBoundingClientRect();
  const marks = [...document.querySelectorAll('#c ' + sel)];
  for (let fx = 0.35; fx < 0.72; fx += 0.05) for (let f = 0.2; f < 0.85; f += 0.1) {
    const x = r.left + r.width * fx, y = r.top + r.height * f;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
    const hit = document.elementFromPoint(x, y);
    if (hit && marks.some((m) => m === hit || m.contains(hit))) continue;
    if (!svg.contains(hit)) continue;
    return { x, y };
  } return null; }"""


def settle(pg, expr, samples=3, tries=120):
    last, hits = None, 0
    for _ in range(tries):
        now = pg.evaluate(expr)
        hits = hits + 1 if now == last else 0
        last = now
        if hits >= samples:
            return True
        pg.wait_for_timeout(40)
    return False


rows = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for n in sorted(EX):
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        try:
            pg.goto((docs / "dist" / "standalone" / f"{n}.html").as_uri(), wait_until="load")
            pg.wait_for_function("() => window.__okuRendered === true", timeout=30000)
            settle(pg, "() => document.querySelector('#c').innerHTML.length")
            settle(pg, SIG)
            rec = {
                # Any element the kit calls a cursor, not the two classes
                # the generic helper happens to use. There are five more
                # (`okc-bar-cursor`, `okc-gauge-cursor`,
                # `okc-ridge-cursor`, `okc-sparkline-cursor` and their
                # parts), and reading only the first two reported
                # ridgeline, sparkline, gauge and the three DIV bar
                # charts as having no cursor -- the four the roadmap's
                # own footer names as the sweep-axis charts.
                "cursor": pg.evaluate(
                    "() => [...document.querySelectorAll('#c *')]"
                    ".some((e) => /(^| )okc-[a-z-]*cursor( |$)/.test(e.getAttribute('class') || ''))"
                ),
                "fullscreen": pg.evaluate(
                    "() => !!document.querySelector(\"#c [aria-label='Expand to fullscreen']\")"
                ),
            }
            base = pg.evaluate(SIG)
            pt = pg.evaluate(FIND, MARKS)
            rec["via"] = "mark" if pt else ("cursor" if pg.evaluate(CURSOR_PT, MARKS) else "none")
            if not pt:
                pt = pg.evaluate(CURSOR_PT, MARKS)
            if pt:
                pg.mouse.move(pt["x"] - 16, pt["y"] - 16)
                pg.mouse.move(pt["x"], pt["y"], steps=6)
                # The hover LANDED before anything is read off it.
                ok = False
                for _ in range(60):
                    if pg.evaluate(TIP):
                        ok = True
                        break
                    pg.wait_for_timeout(40)
                rec["tooltip"] = ok
                settle(pg, SIG, samples=2, tries=30)
                after = pg.evaluate(SIG)
                rec["highlight"] = after != base
                tip = pg.evaluate(TIP) or {}
                rec["offersPin"] = bool(tip.get("hint"))
                if rec["offersPin"]:
                    pg.mouse.click(pt["x"], pt["y"])
                    held = False
                    for _ in range(60):
                        t = pg.evaluate(TIP)
                        if t and t["pinned"]:
                            held = True
                            break
                        pg.wait_for_timeout(40)
                    pg.mouse.move(4, 4)
                    pg.wait_for_timeout(200)
                    t = pg.evaluate(TIP)
                    rec["pin"] = held and bool(t and t["pinned"])
                else:
                    rec["pin"] = False
            else:
                rec.update(tooltip=False, highlight=False, offersPin=False, pin=False)
        finally:
            pg.close()
        rows[n] = rec
    b.close()

(ROOT / "tmp/capabilities.json").write_text(json.dumps(rows, indent=2, sort_keys=True))
print(f"{'type':22} {'tip':5} {'pin':5} {'hilite':6} {'cursor':6} {'full':5} via")
for n in sorted(rows):
    r = rows[n]
    print(
        f"{n:22} {str(r['tooltip']):5} {str(r['pin']):5} {str(r['highlight']):6} "
        f"{str(r['cursor']):6} {str(r['fullscreen']):5} {r['via']}"
    )
