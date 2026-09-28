#!/usr/bin/env python3
"""Find every figure whose text a reader cannot read, and say why.

"A label is fitted to the space it has" is a rule this kit already has
a test for, and a reader still reports labels cut off in charts and
diagrams. That test asks one chart one question; this asks every figure
the kit can draw, at the widths a reader uses, with labels the length
author text actually reaches.

    uv run python tools/text_fit_audit.py                # the sweep
    uv run python tools/text_fit_audit.py --kinds bar,sankey --keep
    uv run python tools/text_fit_audit.py --json out.json

Method, and the two parts of it that are load-bearing:

**One figure per page, one page LOAD per figure.** Measuring several
figures on a shared page returns different answers on different runs,
because an earlier hover, pin or focus is still in effect, and because
a chart sized from its container is sized differently when it shares
one. `tools/chart_capabilities.py` learned this the hard way.

**Two payloads per figure.** As shipped, and with a real label appended
to every string it carries — `_examples.longify`, the same helper the
narrow-viewport suite uses, so "which keys are enums" has one home. The
shipped examples carry short labels by design; a defect that only
appears at a realistic label length is invisible to every test that
uses them as they are.

Five findings, each measured rather than judged:

  clipped-svg   text whose box leaves its <svg>, which clips
  spill-svg     text outside its <svg> that the svg does NOT clip, so
                it is drawn over whatever is next to the figure
  clipped-html  an element whose text overflows a box with no scroller
  overlap       two labels drawn over each other, by area
  ellipsis      the kit shortened the label; how much survived

`ellipsis` is not automatically a defect — shortening with the whole
string in a `<title>` is the designed behaviour — so it is reported
with the fraction that survived. A label down to two characters is a
label the reader cannot use, whatever the tooltip holds.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from oku import cli  # noqa: E402
from oku_tests._examples import FENCE_OF, WORDY, examples, longify  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Every kind that draws text the reader has to read. `code`, `image`
# and `svg` are excluded: the first two carry no kit-drawn label, and
# the `svg` block is an author's own drawing, which the kit does not
# lay out.
SKIP_BLOCKS = {"code", "image", "svg"}

AUDIT = r"""(sel) => {
  const host = document.querySelector(sel);
  if (!host) return { error: 'no host' };
  const F = [];
  // NOT textContent: an SVG <text> carries its full string in a <title>
  // child, so textContent reads the shortened label AND the whole one
  // back as one string, and no shortening is ever detectable.
  const txt = (e) => {
    let out = '';
    const walk = (n) => {
      for (const k of n.childNodes) {
        if (k.nodeType === 3) { out += k.textContent; continue; }
        if (k.nodeType !== 1) continue;
        const t = k.tagName.toLowerCase();
        if (t === 'title' || t === 'desc' || t === 'metadata') continue;
        walk(k);
      }
    };
    walk(e);
    return out.replace(/\s+/g, ' ').trim();
  };
  const titleOf = (e) => {
    const holder = e.closest('text') || e;
    const t = holder.querySelector(':scope > title')
      || (holder.parentElement && holder.parentElement.querySelector(':scope > title'));
    return t ? (t.textContent || '').replace(/\s+/g, ' ').trim() : '';
  };
  // Visibility is INHERITED in effect, so the element's own three
  // properties do not answer it: an annotated-code tooltip is
  // `display: none` at rest and every token inside it computes
  // `display: inline`, `visibility: visible`, `opacity: 1`. Reading
  // only the element reported three tooltips' worth of text as cut by
  // the code block they hang off, which is text no reader can see.
  const shown = (e) => {
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (parseFloat(cs.opacity) === 0) return false;
    }
    return true;
  };
  const clips = (e) => {
    const cs = getComputedStyle(e);
    return /hidden|clip/.test(cs.overflow + cs.overflowX + cs.overflowY);
  };
  // A box the reader can scroll is not a box that cuts: the text is
  // off screen and reachable, which is the difference between a
  // defect and a scrollbar. Both axes, because either one alone makes
  // the content reachable in that direction.
  const scrolls = (e) => {
    const cs = getComputedStyle(e);
    const way = (v) => v === 'auto' || v === 'scroll';
    return (way(cs.overflowX) && e.scrollWidth > e.clientWidth + 1)
        || (way(cs.overflowY) && e.scrollHeight > e.clientHeight + 1);
  };
  const near = (e) => {
    for (let n = e; n && n !== host; n = n.parentElement) {
      const c = (n.getAttribute && n.getAttribute('class')) || '';
      const s = String(c).split(/\s+/).filter(Boolean);
      if (s.length) return s.find((x) => /^ok[ctd]-/.test(x)) || s[0];
    }
    return e.tagName.toLowerCase();
  };
  // A rect in screen space for an SVG node, going through the node's
  // own screen CTM — getBoundingClientRect returns zeros for anything
  // inside <clipPath>, which is never rendered.
  const screenBox = (node, ctmFrom) => {
    let bb;
    try { bb = node.getBBox(); } catch (e) { return null; }
    const m = (ctmFrom || node).getScreenCTM();
    if (!m) return null;
    const root = node.ownerSVGElement || node;
    const pt = (x, y) => { const p = root.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(m); };
    const ps = [pt(bb.x, bb.y), pt(bb.x + bb.width, bb.y), pt(bb.x, bb.y + bb.height), pt(bb.x + bb.width, bb.y + bb.height)];
    const xs = ps.map((p) => p.x), ys = ps.map((p) => p.y);
    return { left: Math.min(...xs), right: Math.max(...xs), top: Math.min(...ys), bottom: Math.max(...ys) };
  };
  // The clip in force on an element: its own clip-path or the nearest
  // ancestor's, as an attribute or as a computed property.
  const clipBox = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const raw = n.getAttribute && (n.getAttribute('clip-path') || '');
      const cs = getComputedStyle(n).clipPath;
      const v = (raw && raw !== 'none') ? raw : (cs && cs !== 'none' ? cs : '');
      if (!v) { if (n.tagName && n.tagName.toLowerCase() === 'svg') break; continue; }
      const id = (v.match(/url\(["']?#([^"')]+)/) || [])[1];
      if (!id) continue;
      const cp = document.getElementById(id);
      if (!cp) continue;
      let box = null;
      for (const kid of cp.children) {
        const b = screenBox(kid, n);
        if (!b) continue;
        box = box ? { left: Math.min(box.left, b.left), right: Math.max(box.right, b.right),
                      top: Math.min(box.top, b.top), bottom: Math.max(box.bottom, b.bottom) } : b;
      }
      if (box) return { box, on: near(n) };
      if (n.tagName && n.tagName.toLowerCase() === 'svg') break;
    }
    return null;
  };
  const outBy = (r, b) => Math.max(b.left - r.left, r.right - b.right, b.top - r.top, r.bottom - b.bottom);

  // ---- SVG text ---------------------------------------------------
  const leaves = [];
  for (const t of host.querySelectorAll('svg text')) {
    if (!txt(t) || !shown(t)) continue;
    if (t.closest('.okc-tooltip, .oku-tooltip, [hidden]')) continue;
    const spans = [...t.querySelectorAll('tspan')].filter((s) => txt(s));
    for (const leaf of (spans.length ? spans : [t])) {
      const r = leaf.getBoundingClientRect();
      if (r.width < 0.5 || r.height < 0.5) continue;
      leaves.push({ el: leaf, r, s: leaf.closest('svg') });
    }
  }
  for (const { el, r, s } of leaves) {
    if (s) {
      const out = outBy(r, s.getBoundingClientRect());
      if (out > 0.5) {
        F.push({ cls: clips(s) ? 'clipped-svg' : 'spill-svg', px: +out.toFixed(1),
                 where: near(el), text: txt(el).slice(0, 48) });
      }
    }
    const cb = clipBox(el);
    if (cb) {
      const out = outBy(r, cb.box);
      if (out > 0.5) {
        const visible = Math.max(0, Math.min(r.right, cb.box.right) - Math.max(r.left, cb.box.left));
        F.push({ cls: 'clipped-clip', px: +out.toFixed(1), where: near(el), on: cb.on,
                 kept: +(visible / r.width).toFixed(2), text: txt(el).slice(0, 48) });
      }
    }
  }

  // ---- labels the kit shortened in the DOM ------------------------
  for (const { el } of leaves) {
    const t = txt(el);
    if (!/[…]$|\.\.\.$/.test(t)) continue;
    const full = titleOf(el);
    const kept = t.replace(/[….]+$/, '').length;
    F.push({ cls: 'ellipsis', where: near(el), text: t.slice(0, 48),
             kept, full: full.length || null, titled: !!full,
             share: full ? +(kept / full.length).toFixed(2) : null });
  }

  // ---- two labels over each other ---------------------------------
  // A rotated label's axis-aligned rect is far bigger than its glyph
  // run — a -45deg heatmap column label has a box overlapping half the
  // figure and touches nothing. So where either label is rotated, the
  // pair is compared as ORIENTED boxes: the four corners of each
  // getBBox through its own screen CTM, separating-axis test between
  // them. Comparing a rotated label to an upright one as rectangles
  // reported a column label sitting clear above the grid as colliding
  // with the first row's label.
  const corners = (el) => {
    const m = el.getScreenCTM && el.getScreenCTM();
    if (!m) return null;
    let bb; try { bb = el.getBBox(); } catch (e) { return null; }
    const root = el.ownerSVGElement || el;
    const pt = (x, y) => { const q = root.createSVGPoint(); q.x = x; q.y = y; const r = q.matrixTransform(m); return [r.x, r.y]; };
    return [pt(bb.x, bb.y), pt(bb.x + bb.width, bb.y),
            pt(bb.x + bb.width, bb.y + bb.height), pt(bb.x, bb.y + bb.height)];
  };
  const rotated = (el) => {
    const m = el.getScreenCTM && el.getScreenCTM();
    return !!m && Math.abs(Math.atan2(m.b, m.a)) > 0.02;
  };
  const overlapArea = (A, B) => {
    // Separating axis: if any edge normal separates them, they do not
    // touch. Returns 0 when separated, else an approximate shared area
    // from the smaller box's extent along the least-separated axis.
    let worst = Infinity;
    for (const poly of [A, B]) {
      for (let i = 0; i < 4; i++) {
        const ax = poly[(i + 1) % 4][0] - poly[i][0];
        const ay = poly[(i + 1) % 4][1] - poly[i][1];
        const len = Math.hypot(ax, ay) || 1;
        const nx = -ay / len, ny = ax / len;
        let aMin = Infinity, aMax = -Infinity, bMin = Infinity, bMax = -Infinity;
        for (const q of A) { const d = q[0] * nx + q[1] * ny; aMin = Math.min(aMin, d); aMax = Math.max(aMax, d); }
        for (const q of B) { const d = q[0] * nx + q[1] * ny; bMin = Math.min(bMin, d); bMax = Math.max(bMax, d); }
        const gapAxis = Math.min(aMax, bMax) - Math.max(aMin, bMin);
        if (gapAxis <= 0.5) return 0;
        worst = Math.min(worst, gapAxis);
      }
    }
    return worst;
  };
  for (let i = 0; i < leaves.length; i++) {
    for (let j = i + 1; j < leaves.length; j++) {
      if (rotated(leaves[i].el) || rotated(leaves[j].el)) {
        const A = corners(leaves[i].el), B = corners(leaves[j].el);
        if (!A || !B) continue;
        const shared = overlapArea(A, B);
        if (shared <= 0.5) continue;
        F.push({ cls: 'overlap', px: +shared.toFixed(1), rotated: true, where: near(leaves[i].el),
                 text: (txt(leaves[i].el) + ' / ' + txt(leaves[j].el)).slice(0, 60) });
        continue;
      }
      const a = leaves[i].r, b = leaves[j].r;
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w <= 0.5 || h <= 0.5) continue;
      const share = (w * h) / Math.min(a.width * a.height, b.width * b.height);
      // Two rules, because one number does not cover both shapes of
      // collision. A big area share catches labels stacked on each
      // other. Same-LINE collisions are the ones that ruin a reading
      // and they can be small in area: a slope chart's two column
      // heads ran four characters into each other at a 12% share, and
      // a 35% floor called that clean. On one line, any real touch is
      // a collision.
      const sameLine = h >= 0.6 * Math.min(a.height, b.height) && w > 2;
      if (share < 0.35 && !sameLine) continue;
      F.push({ cls: 'overlap', share: +share.toFixed(2), px: +w.toFixed(1),
               line: sameLine, where: near(leaves[i].el),
               text: (txt(leaves[i].el) + ' / ' + txt(leaves[j].el)).slice(0, 60) });
    }
  }

  // ---- HTML text cut by a box with no scroller --------------------
  for (const e of host.querySelectorAll('*')) {
    if (e.closest('svg') || !shown(e)) continue;
    const direct = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!direct) continue;
    const cs = getComputedStyle(e);
    // The box that would cut it: itself or the nearest clipping parent.
    let cut = null;
    for (let n = e; n && n !== host.parentElement; n = n.parentElement) {
      // A scroller reached before any clipping box means the text is
      // off screen, not lost. The live-snippet editor is exactly that
      // shape: a `pre` at `overflow: auto` inside a wrap at
      // `overflow: hidden`, so a walk looking only for `hidden` sailed
      // past the scrollbar and called 54 Prism tokens clipped.
      if (scrolls(n)) break;
      if (clips(n)) { cut = n; break; }
    }
    const over = e.scrollWidth - e.clientWidth;
    if (cut === e && over > 1) {
      F.push({ cls: 'clipped-html', px: +over.toFixed(1), where: near(e), axis: 'x',
               ellipsis: cs.textOverflow === 'ellipsis' || cs.webkitLineClamp !== 'none',
               text: txt(e).slice(0, 48) });
      continue;
    }
    if (cut && cut !== e) {
      const out = outBy(e.getBoundingClientRect(), cut.getBoundingClientRect());
      if (out > 1) {
        F.push({ cls: 'clipped-html', px: +out.toFixed(1), where: near(e), axis: 'box',
                 ellipsis: cs.textOverflow === 'ellipsis', text: txt(e).slice(0, 48) });
      }
    }
  }

  // ---- the picture losing its own figure to the labels ------------
  // Per drawing surface, not per host: a chart's toolbar icons are
  // inline SVG inside the same element, and counting them reported a
  // sankey whose diagram had collapsed to one 20px column as using
  // 46% of its width.
  let markCount = 0;
  for (const svg of host.querySelectorAll('svg.okc-svg, svg.okd-svg, oku-diagram svg')) {
    const sb = svg.getBoundingClientRect();
    if (sb.width < 2) continue;
    let span = null;
    for (const m of svg.querySelectorAll('rect, path, circle, polygon, ellipse, line')) {
      if (m.closest('clipPath, defs, mask, marker, .okc-tooltip, button')) continue;
      if (!shown(m)) continue;
      const r = m.getBoundingClientRect();
      if (r.width < 1 && r.height < 1) continue;
      if (r.width >= sb.width - 2 && r.height >= sb.height - 2) continue;  // the plate
      markCount++;
      span = span ? { left: Math.min(span.left, r.left), right: Math.max(span.right, r.right) }
                  : { left: r.left, right: r.right };
    }
    if (!span) continue;
    const share = (span.right - span.left) / sb.width;
    if (share < 0.3) {
      F.push({ cls: 'plot-starved', share: +share.toFixed(2), where: near(svg),
               text: 'marks span ' + Math.round(span.right - span.left) + 'px of ' + Math.round(sb.width) });
    }
  }
  return { findings: F, texts: leaves.length, marks: markCount };
}"""


def build_pages(kinds: list[str], out: pathlib.Path) -> dict:
    ex = examples()
    pages: dict[str, tuple[str, str]] = {}
    docs = out / "docs"
    if docs.exists():
        shutil.rmtree(docs)
    docs.mkdir(parents=True)
    for kind, payload in sorted(ex["charts"].items()):
        if kinds and kind not in kinds:
            continue
        pages[f"chart-{kind}"] = ("oku-chart", json.dumps(payload, separators=(",", ":")))
        pages[f"chart-{kind}~wordy"] = (
            "oku-chart",
            json.dumps(longify(payload, WORDY), separators=(",", ":")),
        )
    for kind, payload in sorted(ex["blocks"].items()):
        if kind in SKIP_BLOCKS or kind not in FENCE_OF:
            continue
        if kinds and kind not in kinds:
            continue
        pages[f"block-{kind}"] = (FENCE_OF[kind], json.dumps(payload, separators=(",", ":")))
        pages[f"block-{kind}~wordy"] = (
            FENCE_OF[kind],
            json.dumps(longify(payload, WORDY), separators=(",", ":")),
        )
    for name, (fence, body) in pages.items():
        (docs / f"{_slug(name)}.md").write_text(
            f"---\ntitle: {name}\nsummary: One {name}.\n---\n\n## figure " + "{#c}" + "\n\n"
            f"```{fence}\n{body}\n```\n",
            encoding="utf-8",
        )
    cwd = pathlib.Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    if rc != 0:
        raise SystemExit(f"build failed ({rc}) — a lengthened payload the schema refuses?")
    return pages


def _slug(name: str) -> str:
    return name.replace("~", "--")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default="", help="comma list, else every figure")
    ap.add_argument("--widths", default="1280,360")
    ap.add_argument("--scales", default="1")
    ap.add_argument("--json", default="")
    ap.add_argument("--keep", action="store_true", help="leave the built pages in place")
    a = ap.parse_args()

    # Per run, not a fixed name: a sweep and a spot check started in
    # the same minute shared one build directory, and the second one's
    # rebuild deleted the pages the first was still loading.
    out = (ROOT / f"tmp/textfit-{os.getpid()}").resolve()
    kinds = [k for k in a.kinds.split(",") if k]
    pages = build_pages(kinds, out)
    widths = [int(w) for w in a.widths.split(",")]
    scales = [float(s) for s in a.scales.split(",")]

    rows: list[dict] = []
    drawn: dict = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name in sorted(pages):
            url = (out / "docs" / "dist" / "standalone" / f"{_slug(name)}.html").as_uri()
            for width in widths:
                for scale in scales:
                    pg = b.new_page(viewport={"width": width, "height": 900})
                    try:
                        pg.goto(url, wait_until="load")
                        pg.wait_for_function("() => window.__okuRendered === true", timeout=30000)
                        if scale != 1:
                            pg.evaluate(
                                "(s) => { document.documentElement.style.setProperty('--oku-text-scale', String(s));"
                                " document.documentElement.setAttribute('data-text-scale', String(s));"
                                " window.dispatchEvent(new CustomEvent('oku:text-scale-changed', { detail: { scale: s } })); }",
                                scale,
                            )
                        pg.wait_for_timeout(700)
                        got = pg.evaluate(AUDIT, "#c")
                        for f in got.get("findings", []):
                            rows.append({"figure": name, "width": width, "scale": scale, **f})
                        drawn[(name, width, scale)] = (got.get("marks", 0), got.get("texts", 0))
                    finally:
                        pg.close()
        b.close()

    # The cross-variant findings are computed from the whole sweep, so
    # they are added before anything is written: a JSON file missing
    # the class the sweep exists for is a file that reads as clean.
    rows += lost_marks(drawn)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    report(rows, pages, widths, scales)
    if a.keep:
        print(f"\npages kept in {out}")
    else:
        shutil.rmtree(out, ignore_errors=True)
    return 0


def lost_marks(drawn: dict) -> list[dict]:
    """A longer label may not cost the figure a mark.

    The check here that needs no model of any chart: the two variants
    carry the same payload shape and differ only in string length, so a
    mark present in one and gone from the other is the layout
    collapsing rather than a drawing decision. A sankey with long node
    names drew its four nodes at one x and not one link.
    """
    out = []
    for (name, width, scale), (marks, _texts) in sorted(drawn.items()):
        if name.endswith("~wordy"):
            continue
        other = drawn.get((f"{name}~wordy", width, scale))
        if other is None or marks == 0 or other[0] >= marks:
            continue
        out.append(
            {
                "figure": f"{name}~wordy",
                "width": width,
                "scale": scale,
                "cls": "lost-marks",
                "where": "figure",
                "px": marks - other[0],
                "text": f"{other[0]} marks with long labels, {marks} with the shipped ones",
            }
        )
    return out


def report(rows, pages, widths, scales) -> None:
    by_fig: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_fig[r["figure"]][r["cls"]] += 1
    print(f"\n{len(pages)} figures x {len(widths)} widths x {len(scales)} scales")
    print(
        f"{sum(len(v.values()) and sum(v.values()) for v in by_fig.values())} findings "
        f"in {len(by_fig)} figures\n"
    )
    order = [
        "lost-marks",
        "plot-starved",
        "clipped-clip",
        "clipped-svg",
        "spill-svg",
        "clipped-html",
        "overlap",
        "ellipsis",
    ]
    print(f"{'figure':<30} " + " ".join(f"{c[:9]:>10}" for c in order))
    for fig in sorted(by_fig, key=lambda f: -sum(by_fig[f][c] for c in order[:7])):
        c = by_fig[fig]
        if not sum(c.values()):
            continue
        print(f"{fig:<30} " + " ".join(f"{c[k] or chr(46):>10}" for k in order))
    print("\nby class:")
    for cls, n in Counter(r["cls"] for r in rows).most_common():
        worst = max((r for r in rows if r["cls"] == cls), key=lambda r: r.get("px", 0), default=None)
        extra = (
            f"  worst {worst.get('px')}px in {worst['figure']} ({worst['where']})"
            if worst and worst.get("px")
            else ""
        )
        print(f"  {cls:<14} {n:>5}{extra}")


if __name__ == "__main__":
    raise SystemExit(main())
