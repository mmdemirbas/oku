"""Every edge in a rendered diagram touches what it connects.

Mermaid trims each edge at its source and target boundary. When the
endpoint is a SUBGRAPH the trim has been observed (in a reporter's
Chrome, not reproducible here) to stop short, leaving a line floating
beside the cluster it should leave. `_snapEdgeEndpoints` repairs that
after render.

Two properties, because only the pair is meaningful:

- On a correctly routed diagram it changes NOTHING — `data-okd-snapped`
  never appears. A repair that fires on healthy geometry would be worse
  than the defect.
- Given a gap, it closes it. The gap is synthesised here (move one
  edge's first point away from its shape) since the upstream cause is
  environment-dependent and does not occur in headless chromium.
"""

from __future__ import annotations

import http.server
import json
import threading
from functools import partial
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# The reporter's diagram: three edges leave a subgraph, which is the
# shape the upstream trim gets wrong.
FLOWCHART = (
    "flowchart LR\n"
    '  subgraph before["before compaction — bucket 0"]\n'
    "    A[\"file 1 · seq 1<br/>key 7 = 'first'\"]\n"
    "    B[\"file 2 · seq 2<br/>key 7 = 'second'\"]\n"
    "    C[\"file 3 · seq 3<br/>key 7 = 'third'\"]\n"
    "  end\n"
    '  before --> R{{"read: merge on key,<br/>highest seq wins"}}\n'
    "  R --> O[\"key 7 = 'third'\"]\n"
    "  before -.compaction.-> after\n"
    '  subgraph after["after compaction — bucket 0"]\n'
    "    D[\"file 4 · level 1<br/>key 7 = 'third'\"]\n"
    "  end\n"
    '  after --> R2{{"read: nothing to merge"}}\n'
    "  R2 --> O2[\"key 7 = 'third'\"]\n"
)

PAGE = {
    "k": "page",
    "t": "Edges",
    "b": [
        "## Edges {#edges}\n",
        {"k": "diagram", "caption": "Merge on read.", "src": FLOWCHART},
    ],
}

# Distance from each edge tip to the nearest node/cluster box, in screen
# px. Returns one entry per edge path.
GAPS_JS = """() => {
  const svg = document.querySelector('oku-diagram .okd-render svg');
  const boxes = [...svg.querySelectorAll('g.node, g.cluster')]
        .map(g => g.getBoundingClientRect()).filter(r => r.width > 0);
  const dist = (x, y) => Math.min(...boxes.map(r => Math.hypot(
        Math.max(r.left - x, 0, x - r.right), Math.max(r.top - y, 0, y - r.bottom))));
  return [...svg.querySelectorAll('.edgePaths path')].map(p => {
    const ctm = p.getScreenCTM();
    const at = l => { const q = svg.createSVGPoint(); const u = p.getPointAtLength(l);
                      q.x = u.x; q.y = u.y; return q.matrixTransform(ctm); };
    const L = p.getTotalLength();
    const a = at(0), b = at(L);
    return { id: p.id, head: dist(a.x, a.y), tail: dist(b.x, b.y) };
  });
}"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("edges")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.json").write_text(json.dumps(PAGE, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.json", "title": "Edges", "parent": None}],
    }
    (d / "page.html").write_text(cli._stub_for("Edges", inline_manifest=manifest), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


def test_edges_touch_their_endpoints(page, served):
    """Every edge starts on a node or cluster box.

    The far end is checked loosely: mermaid stops the stroke short of the
    target so the arrowhead — not the line — lands on the boundary, which
    measures as a few px of gap by design.
    """
    page.goto(served)
    page.wait_for_selector("oku-diagram .okd-render svg", timeout=15000)
    page.wait_for_timeout(600)

    gaps = page.evaluate(GAPS_JS)
    assert gaps, "no edges rendered"
    for edge in gaps:
        assert edge["head"] <= 5, f"{edge['id']} starts {edge['head']:.1f}px from any shape"
        assert edge["tail"] <= 12, f"{edge['id']} ends {edge['tail']:.1f}px from any shape"


def test_repair_is_a_no_op_on_healthy_geometry(page, served):
    """Mermaid routed these edges correctly, so nothing was rewritten."""
    page.goto(served)
    page.wait_for_selector("oku-diagram .okd-render svg", timeout=15000)
    page.wait_for_timeout(600)

    snapped = page.evaluate(
        "() => document.querySelector('oku-diagram .okd-render svg').getAttribute('data-okd-snapped')"
    )
    assert snapped is None, f"repair fired on a correctly routed diagram ({snapped} edges)"


def test_repair_closes_a_detached_edge(page, served):
    """Synthesised gap: move one edge's first point 40 units off its
    cluster, then re-run the repair and check it reconnects."""
    page.goto(served)
    page.wait_for_selector("oku-diagram .okd-render svg", timeout=15000)
    page.wait_for_timeout(600)

    result = page.evaluate(
        """() => {
        const host = document.querySelector('oku-diagram');
        const svg = host.querySelector('.okd-render svg');
        // 'L-before-R-0' leaves the subgraph — the shape the upstream
        // trim gets wrong.
        const p = svg.querySelector('#L-before-R-0') ||
                  svg.querySelector('.edgePaths path');
        const L = p.getTotalLength();
        const a = p.getPointAtLength(0), b = p.getPointAtLength(Math.min(6, L / 4));
        // Toward the target: that is how a short-trimmed edge fails —
        // the first stretch, the one that reached the source, is gone.
        let dx = b.x - a.x, dy = b.y - a.y;
        const mag = Math.hypot(dx, dy) || 1;
        dx /= mag; dy /= mag;
        const OFF = 40;
        // Detach: start the path 40 units further out, keeping the
        // original first point as the next vertex.
        const d0 = p.getAttribute('d');
        p.setAttribute('d',
          'M' + (a.x + dx * OFF) + ',' + (a.y + dy * OFF) + d0.replace(/^M/, 'L'));

        const boxes = [...svg.querySelectorAll('g.node, g.cluster')]
              .map(g => g.getBoundingClientRect()).filter(r => r.width > 0);
        const gap = () => {
          const ctm = p.getScreenCTM();
          const q = svg.createSVGPoint();
          const u = p.getPointAtLength(0); q.x = u.x; q.y = u.y;
          const s = q.matrixTransform(ctm);
          return Math.min(...boxes.map(r => Math.hypot(
            Math.max(r.left - s.x, 0, s.x - r.right),
            Math.max(r.top - s.y, 0, s.y - r.bottom))));
        };
        const detached = gap();
        svg.removeAttribute('data-okd-snapped');
        host._snapEdgeEndpoints(svg);
        return { detached, repaired: gap(), snapped: svg.getAttribute('data-okd-snapped') };
    }"""
    )

    assert result["detached"] > 10, f"the synthetic gap did not take: {result}"
    assert result["snapped"] == "1", f"repair did not fire: {result}"
    assert result["repaired"] <= 5, f"edge still {result['repaired']:.1f}px from any shape"


# ---------- hover emphasis ----------
#
# Hovering a node lights its incident subgraph and pushes the rest back.
# "Back" is not "gone": at 0.25 the dimmed half of a dark-theme diagram
# was no longer readable, which defeats the purpose — the reader is
# looking at the rest of the graph to place the part they are hovering.

HOVER_SRC = 'flowchart LR\n  A["start"] -- yes --> B["middle"]\n  B -- no --> C["end"]\n  C --> D["far"]\n'
HOVER_PAGE = {
    "k": "page",
    "t": "Hover",
    "b": ["## Hover {#hover}\n", {"k": "diagram", "caption": "h", "src": HOVER_SRC}],
}


@pytest.fixture(scope="module")
def hover_served(tmp_path_factory):
    d = tmp_path_factory.mktemp("hover")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.json").write_text(json.dumps(HOVER_PAGE, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.json", "title": "Hover", "parent": None}],
    }
    (d / "page.html").write_text(cli._stub_for("Hover", inline_manifest=manifest), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


HOVER_JS = """async () => {
  const svg = document.querySelector('oku-diagram .okd-render svg');
  svg.querySelector('g.node[data-id="A"]').dispatchEvent(new Event('mouseenter'));
  await new Promise(r => setTimeout(r, 400));   // let the 0.18s fade land
  const op = el => parseFloat(getComputedStyle(el).opacity);
  return {
    nodes: [...svg.querySelectorAll('g.node[data-id]')].map(n => ({
      id: n.getAttribute('data-id'), active: n.hasAttribute('data-okd-active'), op: op(n) })),
    labels: [...svg.querySelectorAll('.edgeLabels > g')]
      .filter(g => g.textContent.trim())
      .map(g => ({ text: g.textContent.trim(),
                   active: g.hasAttribute('data-okd-active'), op: op(g) })),
  };
}"""


def test_dimmed_elements_stay_readable(page, hover_served):
    page.goto(hover_served)
    page.wait_for_selector("oku-diagram .okd-render svg", timeout=15000)
    page.wait_for_timeout(400)

    r = page.evaluate(HOVER_JS)
    active = [n for n in r["nodes"] if n["active"]]
    dimmed = [n for n in r["nodes"] if not n["active"]]
    assert {n["id"] for n in active} == {"A", "B"}, r["nodes"]
    assert dimmed, "nothing was dimmed — the hover emphasis did not engage"
    for n in active:
        assert n["op"] == 1, n
    for n in dimmed:
        # Readable, not invisible. 0.5 is the floor; below it, dark-theme
        # labels stop resolving.
        assert n["op"] >= 0.5, f"{n['id']} dimmed to {n['op']} — below the readability floor"
        assert n["op"] < 1, f"{n['id']} was not dimmed at all"


def test_hovered_edges_keep_their_labels_lit(page, hover_served):
    """The one word explaining the hovered relation must not fade with
    the rest — it is the reason to hover in the first place."""
    page.goto(hover_served)
    page.wait_for_selector("oku-diagram .okd-render svg", timeout=15000)
    page.wait_for_timeout(400)

    labels = {lb["text"]: lb for lb in page.evaluate(HOVER_JS)["labels"]}
    assert set(labels) == {"yes", "no"}, labels
    assert labels["yes"]["active"] is True and labels["yes"]["op"] == 1, labels["yes"]
    assert labels["no"]["active"] is False and labels["no"]["op"] < 1, labels["no"]
