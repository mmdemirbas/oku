"""A grouped bar compares its series side by side; it does not add them.

The multi-series renderer wrote the same reading for both modes: the row's
end label was the sum of its bars and every tooltip gave the bar's share of
that sum. For a stacked bar that is the point — the parts make the whole.
For a grouped bar the series are separate measurements, and the sum is a
number nobody can use: a before/after pair of 10 and 8 warnings read "18",
and the kit's own `oku spec grouped-bar` example (latency per region and
percentile) summed three latencies into one. Found while building a report
that compared two runs of the same check.
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


def _chart(kind: str) -> str:
    payload = {
        "type": kind,
        "categories": ["a", "b"],
        "series": [{"label": "before", "values": [10, 19]}, {"label": "after", "values": [8, 17]}],
    }
    return "```oku-chart\n" + json.dumps(payload) + "\n```\n"


PAGE = (
    "---\ntitle: Bars\nsummary: grouped and stacked\n---\n\n"
    "## Grouped {#grouped}\n\n"
    + _chart("grouped-bar")
    + "\n## Stacked {#stacked}\n\n"
    + _chart("stacked-bar")
)

READ = """(sel) => [...document.querySelectorAll(sel + ' .bar-row')].map((row) => ({
  value: row.querySelector('.bar-value').textContent,
  payloads: [...row.querySelectorAll('.bar-fill')].map((f) => JSON.parse(f.getAttribute('data-hover-payload'))),
}))"""


@pytest.fixture(scope="module")
def rows(browser, tmp_path_factory):
    d = tmp_path_factory.mktemp("bars").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "bars.md").write_text(PAGE, encoding="utf-8")
    (d / "bars.html").write_text(cli._stub_for("Bars"), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    pg = browser.new_page()
    try:
        pg.goto(f"http://127.0.0.1:{httpd.server_address[1]}/bars.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=20000)
        return {
            "grouped": pg.evaluate(READ, ".bar-chart-grouped-bar"),
            "stacked": pg.evaluate(READ, ".bar-chart-stacked-bar"),
        }
    finally:
        pg.close()
        httpd.shutdown()


def test_a_grouped_row_shows_its_values_not_their_sum(rows) -> None:
    got = [r["value"] for r in rows["grouped"]]
    assert got == ["10 · 8", "19 · 17"], got


def test_a_grouped_bar_reads_no_share_of_a_sum(rows) -> None:
    for row in rows["grouped"]:
        for p in row["payloads"]:
            assert [kv["k"] for kv in p["kv"]] == ["value"], p
            assert not p.get("footer"), p


def test_a_stacked_row_still_reads_its_total_and_shares(rows) -> None:
    """The control: stacking IS a whole, so the sum and the shares stay."""
    assert [r["value"] for r in rows["stacked"]] == ["18", "36"]
    kinds = {kv["k"] for r in rows["stacked"] for p in r["payloads"] for kv in p["kv"]}
    assert "share" in kinds
