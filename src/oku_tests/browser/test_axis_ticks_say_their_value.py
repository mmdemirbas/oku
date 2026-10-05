"""An axis tick says the value of its gridline, however close the ticks sit.

`fmtNum` picks its precision from a number's MAGNITUDE — a `k` from 1000
up with one decimal, no decimals from 10 up — which suits one reading and
fails an axis whose ticks are closer together than that precision. A
gantt over the years 2024 to 2026.5 labelled every tick `2k`; a
candlestick of a share trading between 1010 and 1030 says `1k` five
times; a box plot of temperatures between 20 and 22 reads `20 21 21 22
22`. The marks are right and the axis says nothing, or says something
false.

The cases are derived, not listed: every shipped example in
`kit/schema/examples.json` moved to where the defect lives — shifted by
2000, which keeps its spread and puts it past the `k` threshold, and
squeezed into [10, 12], under the integer threshold. A chart type added
tomorrow is covered on the day it lands.

The question asked is the reader's: on one axis, do two numeric labels
read the same? Ticks share a row (an x axis) or a column (a y axis); a
category label is not a number and is not judged. Two charts put more
than one axis on a row, and are read the way they are drawn: a
population pyramid is two axes mirrored about its centre, and the labels
along the top or bottom of a parallel-coordinates plot belong to a
different axis each.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"
EXAMPLES = json.loads((KIT / "schema" / "examples.json").read_text(encoding="utf-8"))["charts"]


def _mapnum(obj, fn):
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        return fn(obj)
    if isinstance(obj, list):
        return [_mapnum(v, fn) for v in obj]
    if isinstance(obj, dict):
        return {k: _mapnum(v, fn) for k, v in obj.items()}
    return obj


def _numbers(obj) -> list[float]:
    out: list[float] = []
    _mapnum(obj, lambda n: out.append(n) or n)
    return out


def _squeeze(blk: dict) -> dict:
    nums = _numbers(blk) or [0]
    lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1
    return _mapnum(blk, lambda n: round(10 + 2 * (n - lo) / span, 4))


MOVES = {
    "shift": lambda b: _mapnum(b, lambda n: n + 2000),
    "squeeze": _squeeze,
}


def _cases() -> dict[str, dict]:
    out = {}
    for ctype in sorted(EXAMPLES):
        for name, fn in MOVES.items():
            blk = fn(dict(EXAMPLES[ctype]))
            # Restored rather than exempted, as in the degenerate sweep.
            blk["k"], blk["type"] = "chart", ctype
            out[f"{ctype}--{name}"] = blk
    out["gantt--years"] = {
        "k": "chart",
        "type": "gantt",
        "tasks": [
            {"label": "one", "start": 2024, "end": 2025},
            {"label": "two", "start": 2025, "end": 2026.5},
        ],
    }
    return out


CASES = _cases()

# How a row of labels maps to axes, where it is not one axis.
ROWS = {"population-pyramid": "halves", "parallel-coordinates": "none"}

AXES = """([names, rows]) => {
  const NUM = /^-?\\d+(\\.\\d+)?k?$/;
  const out = {};
  for (const name of names) {
    const sec = document.getElementById(name);
    if (!sec) { out[name] = null; continue; }
    const rowRule = rows[name.split('--')[0]];
    const svg = sec.querySelector('svg.okc-svg');
    const mid = svg ? svg.getBoundingClientRect().left + svg.getBoundingClientRect().width / 2 : 0;
    const groups = {};
    for (const t of sec.querySelectorAll('svg text.okc-tick')) {
      const label = t.textContent.trim();
      if (!NUM.test(label)) continue;
      const r = t.getBoundingClientRect();
      const half = rowRule === 'halves' ? (r.left + r.width / 2 < mid ? ' left' : ' right') : '';
      const row = rowRule === 'none' ? null : 'row ' + Math.round(r.top + r.height / 2) + half;
      const col = 'col ' + Math.round(t.getAttribute('text-anchor') === 'end' ? r.right
                                     : t.getAttribute('text-anchor') === 'start' ? r.left
                                     : r.left + r.width / 2);
      if (row) (groups[row] = groups[row] || []).push(label);
      (groups[col] = groups[col] || []).push(label);
    }
    const dup = [];
    for (const [axis, labels] of Object.entries(groups)) {
      if (labels.length < 2) continue;
      if (new Set(labels).size < labels.length) dup.push(axis + ': ' + labels.join(' '));
    }
    out[name] = dup;
  }
  return out;
}"""


@pytest.fixture(scope="module")
def axes(browser, tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("ticks").resolve()
    (root / "_oku").symlink_to(KIT, target_is_directory=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    blocks = []
    for name, blk in CASES.items():
        blocks.append(f"## {name} {{#{name}}}")
        blocks.append(blk)
    page_json = {"k": "page", "t": "Ticks", "m": {"summary": "Axis ticks."}, "b": blocks}
    (root / "page.json").write_text(json.dumps(page_json), encoding="utf-8")
    (root / "page.html").write_text(
        cli._stub_for("page", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(root))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/page.html")
        page.wait_for_function("() => window.__okuRendered === true", timeout=120000)
        page_quiet(page)
        return page.evaluate(AXES, [list(CASES), ROWS])
    finally:
        page.close()
        httpd.shutdown()


@pytest.mark.parametrize("name", sorted(CASES))
def test_no_two_ticks_on_an_axis_read_the_same(name, axes) -> None:
    assert axes[name] is not None, f"{name} did not render"
    assert axes[name] == [], axes[name]


@pytest.fixture(scope="module")
def kit_page(browser):
    page = browser.new_page()
    page.set_content("<html><body></body></html>")
    page.add_script_tag(path=str(KIT / "chrome.js"))
    yield page
    page.close()


@pytest.mark.parametrize(
    ("values", "labels"),
    [
        # The reported axes: the compact labels did not say the tick.
        ([2024, 2024.5, 2025, 2025.5, 2026], ["2024", "2024.5", "2025", "2025.5", "2026"]),
        ([10, 10.5, 11, 11.5, 12], ["10", "10.5", "11", "11.5", "12"]),
        ([1010, 1015, 1020, 1025, 1030], ["1010", "1015", "1020", "1025", "1030"]),
        # The common case keeps the labels it always had.
        ([0, 25, 50, 75, 100], None),
        ([0, 3000, 6000, 9000, 12000], None),
        ([0, 9.25, 18.5, 27.75, 37], None),
        ([1, 10, 100, 1000, 10000], None),
    ],
)
def test_fmt_ticks(kit_page, values, labels) -> None:
    got = kit_page.evaluate("(vals) => fmtTicks(vals)", values)
    expect = labels if labels is not None else kit_page.evaluate("(vals) => vals.map(fmtNum)", values)
    assert got == expect
