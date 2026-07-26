"""Render-side regression for the new kit features, pinned as Playwright
assertions (pytest can't see computed colour or <details> semantics):

- `callout` type=danger renders `.callout.danger` with the red --danger
  border (previously fell back to neutral 'note').
- `info-tip` renders a collapsible `<details class="info-tip">` — closed
  by default, with a clickable summary (real "reveal" for self-checks).
- `image` renders `<figure class="okt-figure"><img>`.
- `svg` renders `<figure class="okt-figure okt-svg">` with the inline
  <svg> present (scripts stripped).

Served as a v1 JSON page (the legacy shape convertV1Block handles) from a
tmp dir with an `_oku` symlink to the live kit/. Uses the pytest-playwright
`page` fixture; the package auto-skips when chromium isn't installed.
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

PAGE = {
    "kind": "page",
    "title": "Yeni bloklar",
    "blocks": [
        {
            "kind": "section",
            "id": "s1",
            "title": "Test",
            "blocks": [
                {"kind": "callout", "type": "danger", "title": "Kritik", "content": "kırmızı olmalı"},
                {
                    "kind": "info-tip",
                    "summary": "Kendini sına — soru?",
                    "content": [{"kind": "paragraph", "content": "gizli cevap"}],
                },
                {
                    "kind": "image",
                    "src": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                    "alt": "tek piksel",
                    "caption": "resim",
                },
                {
                    "kind": "svg",
                    "source": "<svg viewBox='0 0 10 10'><rect width='10' height='10'/></svg>",
                    "label": "şema",
                },
                {
                    "kind": "chart",
                    "type": "bar",
                    "title": "Karşılaştırma",
                    "rows": [
                        {"label": "Kısa", "value": 80},
                        {"label": "Çok daha uzun bir etiket başlığı", "value": 30},
                        {"label": "Orta uzunlukta", "value": 55},
                    ],
                },
                {
                    "kind": "diagram",
                    "source": 'flowchart TD\n    A["Uzun bir başlangıç düğümü etiketi"] --> B{"Daha uzun bir karar düğümü metni"}\n    B -->|"Evet"| C["Sonuç bir"]\n    B -->|"Hayır"| D["İkinci sonuç"]',
                },
                {
                    "kind": "compare-grid",
                    "cards": [
                        {"verdict": "good", "title": "İyi", "content": "olur"},
                        {"verdict": "warn", "title": "Dikkat", "content": "dikkatli ol"},
                        {"verdict": "bad", "title": "Kötü", "content": "olmaz"},
                        {"verdict": "neutral", "title": "Nötr", "content": "bilgi"},
                    ],
                },
                {
                    "kind": "kpi-grid",
                    "tiles": [
                        {"icon": "weight", "num": "249 g", "label": "ağırlık"},
                        {"icon": "wind", "num": "12 m/s", "label": "rüzgâr"},
                        {"num": "10 km", "label": "ikonsuz tile"},
                    ],
                },
            ],
        }
    ],
}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("newblocks")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.json").write_text(json.dumps(PAGE, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.json", "title": "Yeni bloklar", "parent": None}],
    }
    (d / "page.html").write_text(cli._stub_for("Yeni bloklar", inline_manifest=manifest), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


def test_new_blocks_render(page, served):
    page.goto(served)
    page.wait_for_timeout(1200)

    # danger callout — present and red border (not the neutral fallback)
    danger = page.locator(".callout.danger")
    assert danger.count() == 1
    border = danger.evaluate("el => getComputedStyle(el).borderLeftColor")
    assert border not in ("rgba(0, 0, 0, 0)", ""), border

    # info-tip — collapsible <details>, closed by default, answer hidden
    det = page.locator("details.info-tip")
    assert det.count() == 1
    assert det.evaluate("el => el.tagName.toLowerCase()") == "details"
    assert det.evaluate("el => el.open") is False
    assert det.locator("summary").count() == 1

    # image — figure + img
    assert page.locator("figure.okt-figure img").count() == 1
    # svg — figure.okt-svg with inline svg
    assert page.locator("figure.okt-svg svg").count() == 1


def test_bar_chart_shares_origin(page, served):
    """All bars in a horizontal bar chart must start at the same x —
    otherwise lengths are not visually comparable. Labels of very
    different widths previously pushed each bar to a different origin."""
    page.goto(served)
    page.wait_for_timeout(800)
    lefts = page.eval_on_selector_all(
        ".bar-chart .bar-row .bar-track",
        "els => els.map(e => Math.round(e.getBoundingClientRect().left))",
    )
    assert len(lefts) == 3, lefts
    assert len(set(lefts)) == 1, f"bar tracks must share a left origin, got {lefts}"


def test_compare_grid_verdict_icons(page, served):
    """Each compare-card shows a verdict icon (check / triangle / cross /
    ring) so the grid reads at a glance instead of as a pile of text.
    The icon is coloured by verdict — good ≠ bad ≠ warn — and even a
    judgment-free `neutral` card carries a (quiet) marker."""
    page.goto(served)
    page.wait_for_timeout(800)
    for verdict in ("good", "warn", "bad", "neutral"):
        sel = f".compare-card.{verdict} .compare-card-icon svg"
        assert page.locator(sel).count() == 1, sel
    # the title sits inside the icon header (icon precedes the h4)
    assert page.locator(".compare-card.good .compare-card-head h4").count() == 1
    # verdict drives the icon colour — good/bad/warn must differ
    colors = {
        v: page.eval_on_selector(f".compare-card.{v} .compare-card-icon", "el => getComputedStyle(el).color")
        for v in ("good", "bad", "warn")
    }
    assert len(set(colors.values())) == 3, colors


def test_kpi_grid_icons(page, served):
    """A kpi tile with an `icon` renders a semantic glyph above the number
    (turns a wall of numbers into a scannable spec sheet); a tile without
    `icon` renders no glyph — back-compatible."""
    page.goto(served)
    page.wait_for_timeout(800)
    tiles = page.locator(".kpi-grid .kpi")
    assert tiles.count() == 3, tiles.count()
    # two tiles carry an icon, one (10 km) does not
    assert page.locator(".kpi-grid .kpi .kpi-icon svg").count() == 2
    # the icon is non-empty (has path/shape children) and accent-coloured
    first = page.locator(".kpi-grid .kpi .kpi-icon").first
    assert first.evaluate("el => el.querySelector('svg').children.length") > 0
    color = first.evaluate("el => getComputedStyle(el).color")
    assert color not in ("", "rgba(0, 0, 0, 0)"), color


def test_mermaid_fits_container(page, served):
    """A rendered diagram never overflows its host (it scales down to
    the column instead of clipping / horizontal-scrolling)."""
    page.goto(served)
    page.wait_for_timeout(2500)
    fit = page.eval_on_selector(
        "oku-diagram",
        """el => {
            const svg = el.querySelector('svg');
            const host = el.querySelector('.okd-render');
            if (!svg || !host) return {ok:false, reason:'no svg/host'};
            return {ok: svg.getBoundingClientRect().width <= host.getBoundingClientRect().width + 1,
                    svgW: svg.getBoundingClientRect().width, hostW: host.getBoundingClientRect().width};
        }""",
    )
    assert fit["ok"], f"diagram overflows host: {fit}"
