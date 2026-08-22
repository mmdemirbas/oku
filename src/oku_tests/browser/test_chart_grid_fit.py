"""A small multiple stays big enough to read.

`cols` was pinned: `repeat(N, minmax(0, 1fr))` held four columns at
360px too, and each panel's chart measured 13x7 CSS pixels — present,
valid, and unreadable. Nothing failed, because "the block rendered" was
true.

`cols` is a maximum now: the track floor makes auto-fit drop to fewer
columns when N will not fit, and the per-track cap keeps it from
exceeding N when they do. Both halves are measured here, because a
floor alone would give a wide page one enormous column and a cap alone
is the defect.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PANELS = [
    {
        "title": name,
        "series": [
            {"label": "rps", "color": "accent", "data": [{"x": i, "y": 10 + i * step} for i in range(1, 7)]}
        ],
    }
    for name, step in (("eu-west", 4), ("us-east", -1), ("ap-south", 9), ("sa-east", 0))
]
GRID = {"k": "chart-grid", "title": "Four panels", "cols": 4, "child_type": "line", "panels": PANELS}

PAGE = (
    "---\ntitle: Grid\nsummary: chart-grid at several widths.\n---\n\n"
    "## Grid {#grid}\n\n```oku-chart-grid\n" + json.dumps(GRID) + "\n```\n"
)


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("chartgridfit").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "grid.md").write_text(PAGE, encoding="utf-8")
    (d / "grid.html").write_text(
        cli._stub_for("grid", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


MEASURE = """() => {
  const g = document.querySelector('.okt-chart-grid-cells');
  if (!g) return null;
  const cells = [...g.querySelectorAll('.okt-chart-grid-cell')];
  const tops = new Set(cells.map(c => Math.round(c.getBoundingClientRect().top)));
  const charts = cells.map(c => {
    const svg = c.querySelector('svg.okc-svg') || c.querySelector('svg');
    const r = svg ? svg.getBoundingClientRect() : {width: 0, height: 0};
    return {w: Math.round(r.width), h: Math.round(r.height)};
  });
  return {
    cells: cells.length,
    rows: tops.size,
    charts: charts,
    overflow: document.documentElement.scrollWidth - window.innerWidth,
  };
}"""


def _at(browser, served, width):
    pg = browser.new_page(viewport={"width": width, "height": 1400})
    try:
        pg.goto(f"{served}/grid.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        pg.evaluate("() => document.fonts.ready")
        pg.wait_for_timeout(500)
        return pg.evaluate(MEASURE)
    finally:
        pg.close()


def test_every_panel_is_drawn_at_every_width(browser, served) -> None:
    for width in (1440, 900, 600, 360):
        m = _at(browser, served, width)
        assert m is not None, f"no chart-grid rendered at {width}px"
        assert m["cells"] == 4, f"{width}px: {m['cells']} cells, expected 4"


def test_no_panel_shrinks_below_a_readable_size(browser, served) -> None:
    """The number that was 13x7. 100px is not a design target — it is
    the width under which a line chart stops carrying information."""
    for width in (1440, 900, 600, 360):
        m = _at(browser, served, width)
        smallest = min(c["w"] for c in m["charts"])
        assert smallest >= 100, f"{width}px: narrowest panel chart is {smallest}px wide — {m['charts']}"


def test_the_authors_column_count_is_honoured_when_it_fits(browser, served) -> None:
    """The cap half. Without it a floor alone gives a wide page one
    column per row, which throws away the comparison the primitive is
    for."""
    m = _at(browser, served, 1440)
    assert m["rows"] == 1, f"four panels should sit in one row at 1440px, got {m['rows']} rows"


def test_a_narrow_screen_drops_columns_instead_of_shrinking(browser, served) -> None:
    """Four columns is what the author asked for and what 360px cannot
    give: the grid wraps to more rows rather than dividing the width
    four ways. How many rows is the floor's business — measured, it is
    two columns of ~157px — so the assertion is that it stopped being
    one row, and that nothing scrolls sideways."""
    m = _at(browser, served, 360)
    assert m["rows"] >= 2, f"expected the grid to wrap at 360px, got {m['rows']} row(s): {m['charts']}"
    assert m["overflow"] <= 0, f"the page scrolls sideways by {m['overflow']}px"
