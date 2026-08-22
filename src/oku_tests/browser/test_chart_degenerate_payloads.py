"""No chart payload makes the kit draw a mark the browser refuses.

A rect with a negative width is not clipped or drawn small — Chrome
drops it and logs `<rect> attribute width: A negative value is not
valid`. The chart keeps its title, its axes and its tick labels, so it
looks like the kit broke rather than like the data is unusual, and the
console names an attribute instead of a chart.

Two payload families reach it, and both arrive from real work rather
than from fuzzing:

- **Crowding.** A gap subtracted from a cell thinner than the gap. A
  900-bin histogram across a 576px plot gives each bin 0.64px, and the
  1px inter-bar gap takes the width to -0.36.
- **A pair the wrong way round.** `q3` below `q1`, `high` below `low`,
  `end` before `start` — the span is a difference of two scaled
  coordinates, and the difference is negative.

The cases are derived, not listed. Every shipped example in
`kit/schema/examples.json` is mutated four ways, so a chart type added
tomorrow is covered on the day it lands rather than the day someone
remembers this file. The hand-written set beside it carries the shapes
a mutation cannot reach: 300 columns, 900 bins, an inverted quartile.

`oku check` decides which payloads carry a runtime obligation, the same
division `test_chart_no_data_runtime.py` uses: a payload the check
rejects is one the author is told to fix, and the renderer owes it
nothing. What the check accepts must draw.
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


def _first_only(obj):
    """Every collection cut to one member — the shape that leaves a
    scale with no extent to divide by."""
    if isinstance(obj, list):
        return [_first_only(obj[0])] if obj else []
    if isinstance(obj, dict):
        return {k: _first_only(v) for k, v in obj.items()}
    return obj


MUTATIONS = {
    "flat": lambda b: _mapnum(b, lambda n: 5),
    "zeros": lambda b: _mapnum(b, lambda n: 0),
    "negative": lambda b: _mapnum(b, lambda n: -3),
    "single": _first_only,
}


def _example(ctype: str, **over) -> dict:
    blk = dict(EXAMPLES[ctype])
    blk["k"] = "chart"
    blk.update(over)
    return blk


def _derived_cases() -> dict[str, dict]:
    out = {}
    for ctype in sorted(EXAMPLES):
        for name, fn in MUTATIONS.items():
            blk = fn(_example(ctype))
            # The mutation runs over every number, so `type` and `k` are
            # restored rather than exempted — an exemption list is one
            # more thing to keep in step with the payload shapes.
            blk["k"], blk["type"] = "chart", ctype
            out[f"{ctype}--{name}"] = blk
    return out


HAND_WRITTEN = {
    # Crowding: more members than the plot has pixels.
    "heatmap-300-columns": _example(
        "heatmap",
        row_labels=["a", "b", "c"],
        col_labels=[str(i) for i in range(300)],
        cells=[[(i * 7 + r) % 50 for i in range(300)] for r in range(3)],
    ),
    "heatmap-200-rows": _example(
        "heatmap",
        row_labels=[f"r{i}" for i in range(200)],
        col_labels=["x", "y", "z"],
        cells=[[i % 40, i % 13, i % 7] for i in range(200)],
    ),
    "histogram-900-bins": _example(
        "histogram", bins=[{"lo": i, "hi": i + 1, "count": i % 17} for i in range(900)]
    ),
    "horizon-100-series": _example(
        "horizon",
        categories=["a", "b", "c", "d"],
        series=[{"label": f"s{i}", "values": [i, i + 3, i + 1, i + 8]} for i in range(100)],
    ),
    "waffle-120-segments": _example("waffle", segments=[{"label": f"s{i}", "count": 1} for i in range(120)]),
    "bar-400-rows": _example("bar", rows=[{"label": f"r{i}", "value": i % 30} for i in range(400)]),
    # A domain with no extent.
    "histogram-flat-domain": _example(
        "histogram", bins=[{"lo": 5, "hi": 5, "count": 12}, {"lo": 5, "hi": 5, "count": 3}]
    ),
    "histogram-one-bin": _example("histogram", bins=[{"lo": 0, "hi": 1, "count": 9}]),
    "line-one-point": _example("line", series=[{"label": "one", "data": [{"x": 1, "y": 2}]}]),
    "area-one-point": _example("area", series=[{"label": "one", "data": [{"x": 0, "y": 5}]}]),
    "waffle-zero-counts": _example(
        "waffle", segments=[{"label": "none", "count": 0}, {"label": "also none", "count": 0}]
    ),
    "arc-zero-slices": _example(
        "arc", slices=[{"label": "nothing", "value": 0}, {"label": "also", "value": 0}]
    ),
    "horizon-flat": _example("horizon", series=[{"label": "flat", "values": [0, 0, 0, 0]}]),
    "waterfall-all-zero": _example(
        "waterfall",
        steps=[
            {"label": "a", "value": 0, "kind": "start"},
            {"label": "b", "value": 0, "kind": "plus"},
            {"label": "c", "value": 0, "kind": "total"},
        ],
    ),
    "marimekko-zero-column": _example(
        "marimekko",
        categories=["Q1", "Q2"],
        series=[{"label": "x", "values": [0, 5]}, {"label": "y", "values": [0, 7]}],
    ),
    # Out of the track's own range.
    "bullet-negative-value": _example(
        "bullet", tracks=[{"label": "Drift", "value": -20, "target": 10, "max": 50}]
    ),
    "bullet-value-over-max": _example(
        "bullet", tracks=[{"label": "Over", "value": 500, "target": 10, "max": 50}]
    ),
    "bar-negative-row": _example("bar", rows=[{"label": "down", "value": -40}, {"label": "up", "value": 20}]),
}

# Written the wrong way round. `oku check` rejects each of these, so the
# runtime obligation is on the check rather than on the renderer — but
# the renderer draws them anyway, which is what the browser half asserts
# separately below.
INVERTED = {
    "boxplot-inverted": _example(
        "box-plot", boxes=[{"label": "bad", "min": 90, "q1": 70, "median": 50, "q3": 30, "max": 10}]
    ),
    "range-bar-inverted": _example("range-bar", ranges=[{"label": "flip", "low": 90, "mid": 60, "high": 30}]),
    "gantt-reversed": _example(
        "gantt",
        tasks=[{"label": "backwards", "start": 9, "end": 2}, {"label": "ok", "start": 0, "end": 4}],
    ),
    "candlestick-inverted": _example(
        "candlestick", entries=[{"date": "Mon", "open": 100, "high": 90, "low": 110, "close": 105}]
    ),
}

CASES = {**_derived_cases(), **HAND_WRITTEN, **INVERTED}


def _page(blocks: list) -> dict:
    return {
        "k": "page",
        "t": "Charts",
        "m": {"summary": "Degenerate, crowded and inverted chart payloads."},
        "b": blocks,
    }


@pytest.fixture(scope="module")
def accepted(tmp_path_factory) -> dict:
    """The payloads `oku check` lets through, one page per case so a
    rejection cannot be attributed to the wrong block."""
    root = tmp_path_factory.mktemp("degenerate-check").resolve()
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    out = {}
    for name, blk in CASES.items():
        issues = cli.check_pages([(root / f"{name}.json", _page([blk]))], root)
        out[name] = [i["code"] for i in issues if i["severity"] == "error"]
    return out


@pytest.fixture(scope="module")
def drawn(browser, accepted, tmp_path_factory) -> dict:
    """Every case on one page — including the ones the check rejects,
    because a rejected payload still reaches the renderer whenever a
    page was built by an older tool or edited by hand."""
    root = tmp_path_factory.mktemp("degenerate-draw").resolve()
    (root / "_oku").symlink_to(KIT, target_is_directory=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    blocks = []
    for name, blk in CASES.items():
        blocks.append(f"## {name} {{#{name}}}")
        blocks.append(blk)
    (root / "page.json").write_text(json.dumps(_page(blocks)), encoding="utf-8")
    (root / "page.html").write_text(
        cli._stub_for("page", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(root))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    console: list[str] = []
    page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console.append(str(e)))
    try:
        page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/page.html")
        page.wait_for_function("() => window.__okuRendered === true", timeout=120000)
        page_quiet(page)
        geometry = page.evaluate(
            """(names) => {
          // Attributes whose value the browser reads as a length. A
          // negative one is refused outright; NaN and undefined reach
          // the DOM and draw nothing, which is the quieter half of the
          // same defect.
          const SIZE = /^(width|height|r|rx|ry|stroke-width)$/;
          const COORD = /^(x|y|cx|cy|x1|y1|x2|y2|d|points|offset)$/;
          const out = {};
          for (const name of names) {
            const sec = document.getElementById(name);
            if (!sec) { out[name] = {missing: true}; continue; }
            const bad = [];
            let marks = 0;
            for (const el of sec.querySelectorAll('*')) {
              for (const a of el.attributes || []) {
                const sized = SIZE.test(a.name);
                if (!sized && !COORD.test(a.name)) continue;
                if (sized) marks++;
                if (/NaN|Infinity|undefined/.test(a.value)) {
                  bad.push(el.tagName.toLowerCase() + '@' + a.name + '=' + a.value.slice(0, 40));
                } else if (sized && parseFloat(a.value) < 0) {
                  bad.push(el.tagName.toLowerCase() + '@' + a.name + '=' + a.value);
                }
              }
            }
            out[name] = {bad: [...new Set(bad)].slice(0, 4), marks: marks, svg: !!sec.querySelector('svg')};
          }
          return out;
        }""",
            list(CASES.keys()),
        )
        return {"geometry": geometry, "console": console}
    finally:
        page.close()
        httpd.shutdown()


class TestTheCheckReportsAnInvertedRange:
    @pytest.mark.parametrize("name", sorted(INVERTED))
    def test_an_inverted_pair_is_an_error(self, name, accepted) -> None:
        assert "chart-inverted-range" in accepted[name], accepted[name]

    @pytest.mark.parametrize("name", ["box-plot--flat", "range-bar--flat", "gantt--flat", "histogram--flat"])
    def test_an_equal_pair_is_not_inverted(self, name, accepted) -> None:
        """Every number the same is degenerate, not backwards. A check
        that fires on `lo == hi` is one authors learn to ignore."""
        assert "chart-inverted-range" not in accepted[name], accepted[name]

    @pytest.mark.parametrize("name", ["box-plot", "range-bar", "gantt", "candlestick", "histogram"])
    def test_the_shipped_example_is_in_order(self, name, accepted) -> None:
        assert "chart-inverted-range" not in accepted[f"{name}--single"], accepted[f"{name}--single"]


class TestNoPayloadDrawsAMarkTheBrowserRefuses:
    def test_the_page_drew_enough_to_be_worth_asserting_on(self, drawn) -> None:
        """The assertions below are all negative — they pass on a page
        that rendered nothing at all. This one says the page rendered."""
        geo = drawn["geometry"]
        missing = [k for k, v in geo.items() if v.get("missing")]
        assert missing == [], missing
        marks = sum(v.get("marks", 0) for v in geo.values())
        # 19,919 sized attributes measured across the 234 cases. The
        # floor sits well below it so a new chart type does not move it,
        # and well above zero so a page that drew nothing still fails.
        assert marks > 15000, f"only {marks} sized attributes across {len(geo)} charts"
        drew = [k for k, v in geo.items() if v.get("svg")]
        assert len(drew) > len(CASES) * 0.8, f"{len(drew)} of {len(CASES)} drew an svg"

    def test_no_console_error(self, drawn) -> None:
        seen: dict[str, int] = {}
        for text in drawn["console"]:
            seen[text] = seen.get(text, 0) + 1
        assert seen == {}, sorted(seen.items(), key=lambda kv: -kv[1])[:6]

    def test_no_negative_or_non_finite_geometry(self, drawn) -> None:
        flagged = {k: v["bad"] for k, v in drawn["geometry"].items() if v.get("bad")}
        assert flagged == {}, flagged
