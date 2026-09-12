"""Custom elements must survive being MOVED in the DOM.

`connectedCallback` fires again on every reparent. Each of the source-
consuming elements (diagram, snippet, annotated-code, chart) replaces its
own `innerHTML` on init, which destroys the `<script>` node the source
came from — so a second pass reads an empty source and blanks (or, for a
diagram, error-cards) the block.

The user-visible path is the diagram's "Expand to fullscreen" button: it
moves the LIVE host into the lightbox and back on close. Before the guard
that shipped with these tests, one click produced

    Diagram source (failed to render)
    No diagram type detected matching given configuration for text:

in the lightbox AND in the page after closing, plus one bogus
`mermaid-render-failed` warning per move.

The diagram test needs the Mermaid CDN (as the other diagram tests here
do). The snippet / annotated-code test is offline — it moves the host
directly.
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

FLOWCHART = (
    "flowchart LR\n"
    '  subgraph before["before compaction"]\n'
    '    A["file 1"]\n'
    '    B["file 2"]\n'
    "  end\n"
    '  before --> R{{"read: merge on key"}}\n'
    '  R --> O["key 7"]\n'
)

PAGE = {
    "k": "page",
    "t": "Reparent",
    "b": [
        "## Blocks {#blocks}\n",
        {"k": "diagram", "caption": "Merge on read.", "src": FLOWCHART},
        {
            "k": "live-snippet",
            "label": "Playground",
            "lang": "html-css-js",
            "src": "<p id='hello'>hi</p>",
        },
        {
            "k": "annotated-code",
            "lang": "python",
            "src": "def f(x):  # (1)\n    return x\n",
            "annotations": [{"id": 1, "content": "the function"}],
        },
    ],
}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("reparent")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.json").write_text(json.dumps(PAGE, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.json", "title": "Reparent", "parent": None}],
    }
    (d / "page.html").write_text(cli._stub_for("Reparent", inline_manifest=manifest), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


@pytest.mark.parametrize("width", [1280, 360])
def test_diagram_survives_fullscreen_round_trip(page, served, width):
    """Expand → close leaves the rendered SVG intact, at its original
    inline size, with no error card and no warning fired."""
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(served)
    page.wait_for_selector("oku-diagram .okd-render svg", timeout=15000)

    result = page.evaluate(
        """async () => {
        const d = document.querySelector('oku-diagram');
        const bb = el => el ? (b => ({ w: Math.round(b.width), h: Math.round(b.height) }))(
                                el.getBoundingClientRect()) : null;
        const warnings = [];
        window.addEventListener('oku:warnings', e => warnings.push(e.detail));

        const inline = { svg: bb(d.querySelector('.okd-render svg')),
                         err: !!d.querySelector('.okd-error') };

        d.querySelector('button[title="Expand to fullscreen"]').click();
        await new Promise(r => setTimeout(r, 900));
        const full = {
          stage: bb(document.querySelector('.okt-lightbox-pz')),
          host: bb(d),
          svg: bb(d.querySelector('.okd-render svg')),
          err: !!d.querySelector('.okd-error'),
          inLightbox: !!document.querySelector('.okt-lightbox-content oku-diagram'),
        };

        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        await new Promise(r => setTimeout(r, 900));
        const back = {
          svg: bb(d.querySelector('.okd-render svg')),
          err: !!d.querySelector('.okd-error'),
          inLightbox: !!document.querySelector('.okt-lightbox-content oku-diagram'),
        };
        return { inline, full, back, warnings: warnings.length };
    }"""
    )

    assert result["inline"]["err"] is False
    assert result["inline"]["svg"]["w"] > 0

    # In the lightbox: still the diagram, not the parse-error card, and it
    # fills the stage instead of collapsing to its inline width.
    assert result["full"]["inLightbox"] is True
    assert result["full"]["err"] is False, "fullscreen replaced the diagram with the error card"
    assert result["full"]["svg"] is not None
    stage_w = result["full"]["stage"]["w"]
    assert result["full"]["host"]["w"] >= stage_w - 2, result["full"]
    assert result["full"]["svg"]["w"] > result["inline"]["svg"]["w"], result["full"]

    # Back in the page: unchanged from before the round trip.
    assert result["back"]["inLightbox"] is False
    assert result["back"]["err"] is False, (
        "closing fullscreen replaced the inline diagram with the error card"
    )
    assert result["back"]["svg"] == result["inline"]["svg"], result

    assert result["warnings"] == 0, "reparenting fired a bogus mermaid-render-failed warning"


def test_source_consuming_hosts_survive_a_move(page, served):
    """Moving a snippet / annotated-code host keeps its rendered body.

    Offline counterpart to the diagram test: any future feature that
    relocates a host (a drawer, a tab panel, another lightbox surface)
    hits the same re-init path.
    """
    page.goto(served)
    page.wait_for_selector("oku-snippet .okt-snippet-editor", timeout=15000)
    page.wait_for_selector("oku-annotated-code .okc-anno-list", timeout=15000)

    result = page.evaluate(
        """() => {
        // Measure the rendered CONTENT, not just the presence of the
        // wrapper: a re-init against a consumed <script> rebuilds the
        // same empty shell, so counting elements would pass either way.
        const probes = {
          snippet: () => {
            const el = document.querySelector('oku-snippet');
            const ta = el.querySelector('.okt-snippet-editor');
            return (ta && ta.value.trim().length) || 0;
          },
          annotated: () => {
            const el = document.querySelector('oku-annotated-code');
            const code = el.querySelector('pre code');
            return (code && code.textContent.trim().length) || 0;
          },
        };
        const out = {};
        for (const [key, probe] of Object.entries(probes)) {
          const el = document.querySelector(key === 'snippet' ? 'oku-snippet' : 'oku-annotated-code');
          const before = probe();
          const holder = document.createElement('div');
          document.body.appendChild(holder);
          holder.appendChild(el);            // disconnect + reconnect
          const moved = probe();
          document.body.appendChild(el);     // move once more
          out[key] = { before, moved, after: probe() };
        }
        return out;
    }"""
    )

    for key, sizes in result.items():
        assert sizes["before"] > 0, (key, sizes)
        assert sizes["moved"] == sizes["before"], f"{key} lost its body on the first move: {sizes}"
        assert sizes["after"] == sizes["before"], f"{key} lost its body on the second move: {sizes}"
