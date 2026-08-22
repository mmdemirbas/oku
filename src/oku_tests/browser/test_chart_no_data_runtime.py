"""A chart with nothing to plot says so, wherever the page came from.

`oku check` has caught this since the one-rule pass — a chart with no
populated collection anywhere cannot draw, whatever its type. The check
runs at build time. The renderer runs wherever a page is opened, and
the two exposures the check cannot cover are real: a JSON page edited
by hand, and a tree built by an older tool.

What the reader used to get is the failure that is hardest to read: a
titled box with axes and tick labels and no marks. The generic
empty-block guard passes it, because `_hasVisibleContent` finds an
`<svg>` and a wall of text. It looks like the kit broke, and it is a
payload with no data in it.

The two rules are held against each other here rather than compared as
strings: the same payloads go through `check_pages` and through the
browser, and every one must be rejected by both or accepted by both.
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

# label → chart block. The empty ones span the shapes the 53 types use
# to carry data: an array of rows, an array of series, a keyed object.
CASES = {
    "bar-with-rows": {"k": "chart", "type": "bar", "rows": [{"label": "a", "value": 3}]},
    "line-with-series": {
        "k": "chart",
        "type": "line",
        "series": [{"label": "rps", "data": [{"x": 1, "y": 2}, {"x": 2, "y": 5}]}],
    },
    "bar-empty-rows": {"k": "chart", "type": "bar", "rows": []},
    "bar-no-rows-at-all": {"k": "chart", "type": "bar", "title": "Throughput"},
    "line-empty-series": {"k": "chart", "type": "line", "series": [], "x_label": "t"},
    "heatmap-empty-object": {"k": "chart", "type": "heatmap", "data": {}, "title": "Load"},
    "scalars-only": {"k": "chart", "type": "gauge", "value": 42, "title": "Gauge"},
}


def _page(blocks: list) -> dict:
    return {"k": "page", "t": "Charts", "m": {"summary": "Charts with and without data."}, "b": blocks}


@pytest.fixture(scope="module")
def cli_verdicts(tmp_path_factory) -> dict:
    """What `oku check` says about each payload, one page per case so a
    rejection cannot be attributed to the wrong block."""
    root = tmp_path_factory.mktemp("chartcli").resolve()
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    verdicts = {}
    for name, block in CASES.items():
        path = root / f"{name}.json"
        codes = {i["code"] for i in cli.check_pages([(path, _page([block]))], root)}
        verdicts[name] = "chart-no-data" in codes
    return verdicts


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("chartruntime").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    # One page holding every case, each block preceded by a heading that
    # names it — so a card can be attributed without depending on order.
    blocks = []
    for name, block in CASES.items():
        blocks.append(f"## {name} {{#{name}}}")
        blocks.append(block)
    (d / "page.json").write_text(json.dumps(_page(blocks)), encoding="utf-8")
    (d / "page.html").write_text(
        cli._stub_for("page", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def rendered(browser, served) -> dict:
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        pg.goto(f"{served}/page.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        pg.wait_for_timeout(1200)
        return pg.evaluate(
            """(names) => {
          const out = {};
          for (const name of names) {
            const sec = document.getElementById(name);
            out[name] = sec ? {
              card: !!sec.querySelector('.okt-block-error'),
              svg: !!sec.querySelector('svg'),
              bars: sec.querySelectorAll('.okt-bar').length,
              text: (sec.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
            } : null;
          }
          return out;
        }""",
            list(CASES),
        )
    finally:
        pg.close()


def test_every_case_reached_the_page(rendered) -> None:
    """The guard: a section that never rendered would satisfy "no empty
    frame" by not existing."""
    missing = [n for n, v in rendered.items() if v is None]
    assert missing == [], missing


def test_the_check_still_rejects_what_it_always_did(cli_verdicts) -> None:
    """The control side of the agreement. If this ever goes all-False
    the comparison below passes by measuring nothing."""
    assert cli_verdicts["bar-empty-rows"] is True, cli_verdicts
    assert cli_verdicts["bar-with-rows"] is False, cli_verdicts


@pytest.mark.parametrize("name", list(CASES))
def test_the_renderer_and_the_check_agree(name, cli_verdicts, rendered) -> None:
    assert rendered[name]["card"] == cli_verdicts[name], (
        f"{name}: check says no-data={cli_verdicts[name]}, "
        f"the page {'drew a card' if rendered[name]['card'] else 'drew a chart'} — {rendered[name]}"
    )


def test_a_chart_with_data_still_draws(rendered) -> None:
    assert rendered["bar-with-rows"]["bars"] > 0, rendered["bar-with-rows"]
    assert rendered["line-with-series"]["svg"], rendered["line-with-series"]


def test_the_card_says_what_to_do(rendered) -> None:
    text = rendered["bar-empty-rows"]["text"]
    assert "oku check" in text, text
