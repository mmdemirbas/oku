"""No chart label is cut off by the edge of its own SVG.

Reported against a delivered document: a bullet chart's track names
arrived as ".0 tests, as configured" and "lent, spark-extensions" — the
first half of every long name missing, with no ellipsis, no scrollbar
and nothing to hover. An <svg> clips at its viewBox, so a label wider
than the gutter the renderer guessed is simply not there, and the guess
was a constant (`pad.left = 140`) written when the labels were words.

`test_chart_label_legibility.py` covers the same defect for the row-label
family it was written for, one chart type at a time. This module is the
sweep: every chart type in the schema's example set, rendered twice —
once as authored, once with every author-supplied string lengthened by
40 characters — measuring every <text> against the viewBox it lives in.
The long variant is what makes it a test rather than a screenshot: most
of these renderers hold up fine on a three-word label and fail on a
sentence, which is what authors write.

Measurement notes, both load-bearing:

* Screen rects, not `getBBox()`. getBBox ignores the element's own
  transform, so every rotated label (heatmap columns, pareto categories)
  measures as if it were horizontal and reads as a false overflow.
* Nothing is measured until `document.fonts.ready`. The kit's pages load
  Inter from a CDN, and the SAME string measures about 5% narrower in
  the fallback face — measured 271px vs 284px on a donut legend label,
  identical computed style at both readings. A pass that measures before
  the font lands agrees with itself about a width the reader never sees.
"""

from __future__ import annotations

from ._wait import page_quiet

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"
EXAMPLES = json.loads((KIT / "schema" / "examples.json").read_text(encoding="utf-8"))["charts"]

# Keys whose string values are labels an author writes. Lengthened
# consistently, so cross-references (sankey links, network edges) still
# resolve to their nodes.
LABEL_KEYS = {
    "label",
    "name",
    "categories",
    "col_labels",
    "row_labels",
    "labels",
    "id",
    "source",
    "target",
    "from",
    "to",
}
SUFFIX = " — Ankara staging replica, as configured"


def _lengthen(node, inside_label_key: bool = False):
    if isinstance(node, dict):
        return {k: _lengthen(v, k in LABEL_KEYS) for k, v in node.items()}
    if isinstance(node, list):
        return [_lengthen(v, inside_label_key) for v in node]
    if isinstance(node, str) and inside_label_key:
        return node + SUFFIX
    return node


def _page(payloads: dict) -> str:
    body = "\n\n".join(
        f"## {name} {{#{name.replace('-', '')}}}\n\nLead paragraph.\n\n"
        f"```oku-chart\n{json.dumps(payload)}\n```"
        for name, payload in payloads.items()
    )
    return f"---\ntitle: Chart label fit\nsummary: Every chart type, measured.\n---\n\n{body}\n"


# Every <text> in every chart, with how far it leaves its viewBox (user
# units, positive means outside) and what it currently reads.
MEASURE = """() => {
  const out = [];
  document.querySelectorAll('svg.okc-svg').forEach(svg => {
    const host = svg.closest('oku-chart');
    const vb = svg.viewBox.baseVal, m = svg.getScreenCTM();
    if (!vb || !vb.width || !m) return;
    const corner = (x, y) => { const p = svg.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(m); };
    const a = corner(vb.x, vb.y), c = corner(vb.x + vb.width, vb.y + vb.height);
    const box = {left: Math.min(a.x, c.x), right: Math.max(a.x, c.x),
                 top: Math.min(a.y, c.y), bottom: Math.max(a.y, c.y)};
    const scale = Math.abs(m.a) || 1;
    svg.querySelectorAll('text').forEach(t => {
      const r = t.getBoundingClientRect();
      if (!r.width && !r.height) return;
      const over = Math.max(box.left - r.left, r.right - box.right,
                            box.top - r.top, r.bottom - box.bottom) / scale;
      const shown = [...t.childNodes]
        .filter(n => n.nodeType === 3 || n.nodeName === 'tspan')
        .map(n => n.textContent).join(' ');
      out.push({
        chart: host ? host.getAttribute('data-probe') : '?',
        cls: t.getAttribute('class') || '',
        shown: shown,
        full: (t.querySelector('title') || {}).textContent || '',
        over: Math.round(over * 10) / 10
      });
    });
  });
  return out;
}"""

TAG_CHARTS = """() => document.querySelectorAll('oku-chart').forEach(c => {
  const s = c.closest('section, .okd-section') || c.parentElement;
  const h = s && s.querySelector('h2');
  c.setAttribute('data-probe', h ? h.textContent.trim().replace('#', '') : '?');
})"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("chartlabelfit").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    for variant, payloads in (("plain", EXAMPLES), ("long", {k: _lengthen(v) for k, v in EXAMPLES.items()})):
        (d / f"{variant}.md").write_text(_page(payloads), encoding="utf-8")
        (d / f"{variant}.html").write_text(
            cli._stub_for(variant, inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
            encoding="utf-8",
        )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _measure(browser, served, variant):
    pg = browser.new_page(viewport={"width": 1440, "height": 2000})
    try:
        pg.goto(f"{served}/{variant}.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        # The fit pass waits for the webfont and then for idle time; the
        # measurement has to wait for the same things or it reads a page
        # mid-fit and fails on labels that are about to be corrected.
        pg.evaluate("() => document.fonts.ready")
        page_quiet(pg)
        pg.evaluate(TAG_CHARTS)
        return pg.evaluate(MEASURE)
    finally:
        pg.close()


@pytest.fixture(scope="module")
def plain(browser, served):
    return _measure(browser, served, "plain")


@pytest.fixture(scope="module")
def long_labels(browser, served):
    return _measure(browser, served, "long")


# By SECTION, not by <oku-chart>: the bar family is rendered as plain
# DOM by renderer.js and never becomes a custom element, so a check that
# walks chart hosts reports it missing when it drew correctly.
DREW_SOMETHING = """() => [...document.querySelectorAll('h2')].map(h => {
  const sec = h.closest('section, .okd-section') || h.parentElement;
  return [h.textContent.trim().replace('#', ''),
          !!(sec && sec.querySelector('svg.okc-svg, .bar-chart, oku-chart table'))];
})"""


def test_every_chart_type_in_the_example_set_renders(browser, served):
    """A payload that stops rendering draws nothing, and a sweep that
    measures what is drawn passes on an empty page. The bar family is
    HTML rather than SVG and sparkline has no text at all, so the check
    is "something came out", not "text came out"."""
    pg = browser.new_page(viewport={"width": 1440, "height": 2000})
    try:
        pg.goto(f"{served}/plain.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        page_quiet(pg)
        drawn = dict(pg.evaluate(DREW_SOMETHING))
    finally:
        pg.close()
    missing = sorted(name for name in EXAMPLES if not drawn.get(name))
    assert not missing, f"chart types that rendered nothing: {missing}"


def test_no_label_is_clipped_by_its_own_viewbox(plain):
    """The reference payloads. Nothing here is longer than a few words,
    which is why the clipping in this family shipped: 'Mon' losing its M
    and 'v5' losing its 5 do not look like a systematic defect until
    they are measured."""
    over = [r for r in plain if r["over"] > 0.5]
    assert not over, "labels outside their viewBox: " + "; ".join(
        f"{r['chart']}/{r['cls']} {r['shown']!r} by {r['over']}px" for r in over[:12]
    )


def test_no_label_is_clipped_when_the_author_writes_a_sentence(long_labels):
    """Every label 40 characters longer. A renderer that sizes its gutter
    from a constant fails here and nowhere else."""
    over = [r for r in long_labels if r["over"] > 0.5]
    assert not over, "labels outside their viewBox with long names: " + "; ".join(
        f"{r['chart']}/{r['cls']} {r['shown']!r} by {r['over']}px" for r in over[:12]
    )


# A name that cannot fit is shortened rather than clipped, and the whole
# of it stays in a <title>. The one place a REFERENCE label still gets
# shortened is a treemap cell: 'Markdown' is wider than the rectangle it
# names, and widening the cell would misreport the value it encodes.
REFERENCE_TRIM_ALLOWED = {("treemap", "okc-treemap-label")}


def test_a_reference_payload_label_is_not_shortened(plain):
    """The gutter estimates are per-chart and have to match the size the
    CSS actually renders. They did not: the bullet chart's labels are
    12px and its gutter was computed for 11px, so 'Revenue ($M)' — three
    words, the kit's own example — came out as 'Revenue ($…'."""
    trimmed = [r for r in plain if "…" in r["shown"] and (r["chart"], r["cls"]) not in REFERENCE_TRIM_ALLOWED]
    assert not trimmed, "reference labels shortened: " + "; ".join(
        f"{r['chart']}/{r['cls']} {r['shown']!r} of {r['full']!r}" for r in trimmed[:12]
    )


def test_a_shortened_label_keeps_the_whole_of_itself_in_a_title(long_labels):
    """Shortening is only acceptable because the tail stays reachable."""
    shortened = [r for r in long_labels if "…" in r["shown"]]
    assert shortened, "nothing was shortened — the long-label fixture stopped being long"
    naked = [r for r in shortened if not r["full"]]
    assert not naked, "shortened with no <title> to recover the rest: " + "; ".join(
        f"{r['chart']}/{r['cls']} {r['shown']!r}" for r in naked[:12]
    )


# The reported chart, with its own labels. A bullet chart's rows are
# named in sentences ("Observed: 8 forks resident, spark-extensions"),
# and a 42px row has space for two lines of them.
REPORTED_BULLET = {
    "type": "bullet",
    "title": "Test-JVM ceiling vs. the VM that has to hold it (GB)",
    "tracks": [
        {"label": "iceberg-spark-4.0 tests, as configured", "value": 31.6, "target": 12.66, "max": 34},
        {"label": "Observed: 8 forks resident, spark-extensions", "value": 11.6, "target": 12.66, "max": 34},
        {"label": "Old container limit", "value": 12.0, "target": 12.66, "max": 34},
    ],
}

# Two zones, one named with a word and one with a phrase, so the legend
# needs a second row it used to walk off the right edge instead.
WRAPPING_GAUGE = {
    "type": "gauge",
    "title": "SLO budget",
    "value": 62,
    "max": 100,
    "zones": [
        {"from": 0, "to": 70, "tone": "success", "label": "within the monthly error budget"},
        {"from": 70, "to": 100, "tone": "danger", "label": "burning next month's budget"},
    ],
}

BULLET_LINES = """() => [...document.querySelectorAll('text.okc-bullet-label')].map(t => ({
  lines: [...t.childNodes].filter(n => n.nodeType === 3 || n.nodeName === 'tspan').map(n => n.textContent),
  title: (t.querySelector('title') || {}).textContent || ''
}))"""

SVG_BOX = """() => {
  const svg = document.querySelector('svg.okc-svg');
  const vb = svg.viewBox.baseVal;
  const chips = svg.querySelectorAll('.okc-gauge-zone-chip');
  return {height: vb.height, chips: chips.length};
}"""


def _one_chart_page(browser, tmp_path_factory, payload, script):
    """A single chart on its own page, measured after the fit settles."""
    d = tmp_path_factory.mktemp("onechart").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "p.md").write_text(
        "---\ntitle: One chart\nsummary: Measured on its own.\n---\n\n"
        "## Chart {#chart}\n\nLead paragraph.\n\n```oku-chart\n" + json.dumps(payload) + "\n```\n",
        encoding="utf-8",
    )
    (d / "p.html").write_text(
        cli._stub_for("One chart", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    pg = browser.new_page(viewport={"width": 1440, "height": 1200})
    try:
        pg.goto(f"http://127.0.0.1:{httpd.server_address[1]}/p.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        pg.evaluate("() => document.fonts.ready")
        page_quiet(pg)
        return pg.evaluate(script)
    finally:
        pg.close()
        httpd.shutdown()


def test_a_bullet_track_name_wraps_instead_of_losing_its_front(browser, tmp_path_factory):
    """The reported defect, with the payload that reported it: every
    name whole, the long ones over two lines, none of them ellipsised."""
    rows = _one_chart_page(browser, tmp_path_factory, REPORTED_BULLET, BULLET_LINES)
    assert len(rows) == len(REPORTED_BULLET["tracks"])
    for row, track in zip(rows, REPORTED_BULLET["tracks"]):
        assert " ".join(row["lines"]) == track["label"], (
            f"track name did not survive: {row['lines']} for {track['label']!r}"
        )
        assert row["title"] == track["label"], "the whole name must stay in a <title>"
    wrapped = [r for r in rows if len(r["lines"]) > 1]
    assert wrapped, "no name wrapped — the fixture's long names stopped being long"


def test_a_gauge_legend_that_needs_two_rows_gets_a_taller_svg(browser, tmp_path_factory):
    """Chips used to be laid end to end on one row whatever the width,
    so a zone named with a phrase walked the row off the right edge —
    318px past it for the reference payload, most of a second chart's
    width. The height has to pay for the wrap, or the rows overlap the
    dial instead."""
    box = _one_chart_page(browser, tmp_path_factory, WRAPPING_GAUGE, SVG_BOX)
    assert box["chips"] == len(WRAPPING_GAUGE["zones"]), "every labelled zone needs a chip"
    assert box["height"] > 230, (
        f"viewBox height {box['height']} — a two-row legend must be taller than the one-row 230"
    )
