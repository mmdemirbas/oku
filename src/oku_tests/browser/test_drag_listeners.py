"""What a drag binds, and where the reader has to aim to start one.

Three drags in the kit bound `mousemove` + `mouseup` on `window` or
`document` permanently, at the moment the thing became draggable rather
than at the moment a drag started. Two of them ran per-instance, so the
count grew with the page and with the session:

* the lightbox pan/zoom stage is built on EVERY open — measured 1 -> 11
  `window:mousemove` over ten open/close cycles, each retained handler
  holding that open's stage and its cloned figure;
* a zoomable chart bound one pair per chart — 10 `document:mousemove`
  on this repo's own charts page before the reader touched anything;
* a resizable table bound one pair per COLUMN — 14 on the tables page,
  and the same pass runs again for every table in a file opened in the
  markdown viewer, whose tables then go away.

None of it is visible: the handlers return early when nothing is being
dragged. What it costs is a handler dispatch per pointer move for the
life of the document, and a retained subtree per lightbox open.

Both halves are asserted here. A drag that no longer leaks but no
longer works is not a fix, so each count assertion is paired with the
behaviour it protects.

The last test is a different property of the same feature, found while
aiming the column drag: the grab zone has to be inside its own cell.
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

# Counting the FUNCTIONS registered, not +1/-1: `removeEventListener`
# for something never added is a no-op in the DOM, and a naive counter
# reports negative totals for it.
COUNTER = """
(() => {
  const add = EventTarget.prototype.addEventListener;
  const rem = EventTarget.prototype.removeEventListener;
  const live = new Map();
  const key = (t, type) => t === window ? 'window:' + type : t === document ? 'document:' + type : null;
  window.__okuListenerCount = () => {
    const o = {};
    for (const [k, s] of live) o[k] = s.size;
    return o;
  };
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    const k = key(this, type);
    if (k) { if (!live.has(k)) live.set(k, new Set()); live.get(k).add(fn); }
    return add.call(this, type, fn, opts);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, opts) {
    const k = key(this, type);
    if (k && live.has(k)) live.get(k).delete(fn);
    return rem.call(this, type, fn, opts);
  };
})();
"""

WATCHED = ("window:mousemove", "window:mouseup", "document:mousemove", "document:mouseup")

CHART = json.dumps(
    {
        "type": "line",
        "series": [
            {
                "label": "rps",
                "color": "accent",
                "data": [{"x": i, "y": 10 + (i % 5) * 3} for i in range(1, 12)],
            }
        ],
    }
)

TABLE = json.dumps(
    {
        "headers": ["Engine", "Note"],
        "rows": [["Spark", "One"], ["Flink", "Two"], ["Trino", "Three"]],
    }
)

PAGE = f"""---
title: Drags
summary: A chart to pan, a table to resize, a figure to expand.
---

## Figures {{#figures}}

```oku-chart
{CHART}
```

```oku-table
{TABLE}
```
"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("drags").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (d / "page.md").write_text(PAGE, encoding="utf-8")
    (d / "page.html").write_text(
        cli._stub_for("page", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def counted(browser, served):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(COUNTER)
    pg = ctx.new_page()
    pg.goto(f"{served}/page.html")
    pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    pg.wait_for_selector("oku-chart svg", timeout=30000)
    pg.wait_for_selector("table th .okt-col-resize", timeout=30000)
    try:
        yield pg
    finally:
        ctx.close()


def counts(pg) -> dict:
    live = pg.evaluate("() => window.__okuListenerCount()")
    return {k: live.get(k, 0) for k in WATCHED}


def test_the_counter_is_actually_wrapping_something(counted) -> None:
    """Everything below compares dictionaries. An init script that never
    ran yields two empty ones, which compare equal."""
    live = counted.evaluate("() => window.__okuListenerCount()")
    assert live, "the counter recorded no global listener at all — it is not installed"


def test_a_page_at_rest_holds_no_drag_handler_per_figure(counted) -> None:
    """The steady-state cost. Measured before: 10 `document:mousemove`
    on this repo's charts page, 14 `window:mousemove` on its tables
    page. One zoomable chart and one resizable table are enough to show
    it — the count is per instance."""
    # The ceilings are 1, not 0, and neither survivor is a drag:
    # Playwright installs its own `window` mouse set for bookkeeping,
    # and the kit keeps ONE `document:mousemove` — the last-move stamp
    # the tooltip controller reads to tell a pointer that arrived from
    # a layer that went away.
    at_rest = counts(counted)
    assert at_rest["document:mousemove"] <= 1, at_rest
    assert at_rest["document:mouseup"] == 0, at_rest
    assert at_rest["window:mousemove"] <= 1, at_rest
    assert at_rest["window:mouseup"] <= 1, at_rest


def test_opening_the_lightbox_ten_times_leaves_nothing_behind(counted) -> None:
    before = counts(counted)
    for _ in range(10):
        counted.evaluate(
            "() => window.__okuLightbox.open(document.querySelector('svg').cloneNode(true), { title: 'probe' })"
        )
        counted.wait_for_selector(".okt-lightbox-pz", timeout=10000)
        counted.evaluate("() => window.__okuLightbox.close()")
        counted.wait_for_timeout(60)
    assert counts(counted) == before


def test_a_lightbox_drag_interrupted_by_close_still_releases(counted) -> None:
    """Escape closes the lightbox mid-drag, and the mouseup that would
    have released the pair lands on a stage that is gone."""
    before = counts(counted)
    counted.evaluate(
        "() => window.__okuLightbox.open(document.querySelector('svg').cloneNode(true), { title: 'probe' })"
    )
    stage = counted.wait_for_selector(".okt-lightbox-pz", timeout=10000)
    box = stage.bounding_box()
    counted.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    counted.mouse.down()
    counted.mouse.move(box["x"] + box["width"] / 2 + 40, box["y"] + box["height"] / 2 + 20)
    assert counts(counted)["window:mousemove"] == before["window:mousemove"] + 1, (
        "the drag never bound anything"
    )
    counted.keyboard.press("Escape")
    counted.wait_for_timeout(150)
    counted.mouse.up()
    assert counts(counted) == before


def test_the_lightbox_still_pans(counted) -> None:
    counted.evaluate(
        "() => window.__okuLightbox.open(document.querySelector('svg').cloneNode(true), { title: 'probe' })"
    )
    stage = counted.wait_for_selector(".okt-lightbox-pz", timeout=10000)
    page_quiet(counted)
    inner = counted.query_selector(".okt-lightbox-pz-inner")
    before = counted.evaluate("el => getComputedStyle(el).transform", inner)
    box = stage.bounding_box()
    counted.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    counted.mouse.down()
    counted.mouse.move(box["x"] + box["width"] / 2 + 60, box["y"] + box["height"] / 2 + 30, steps=4)
    counted.mouse.up()
    after = counted.evaluate("el => getComputedStyle(el).transform", inner)
    assert after != before, f"the stage did not move: {before} -> {after}"
    counted.evaluate("() => window.__okuLightbox.close()")


def test_a_column_still_resizes_and_gives_its_handlers_back(counted) -> None:
    handle = counted.query_selector("table th .okt-col-resize")
    handle.scroll_into_view_if_needed()
    counted.wait_for_timeout(120)
    before = counts(counted)
    box = handle.bounding_box()
    y = box["y"] + box["height"] / 2
    counted.mouse.move(box["x"] + box["width"] / 2, y)
    counted.mouse.down()
    counted.mouse.move(box["x"] + box["width"] / 2 + 90, y, steps=4)
    during = counts(counted)
    width = counted.evaluate("() => document.querySelector('table colgroup col').style.width")
    counted.mouse.up()
    counted.wait_for_timeout(60)

    assert during["window:mousemove"] == before["window:mousemove"] + 1, during
    assert width, "the column took no width — the drag did nothing"
    assert counts(counted) == before


def test_a_chart_still_pans_and_gives_its_handlers_back(counted) -> None:
    chart = counted.query_selector("oku-chart svg")
    chart.scroll_into_view_if_needed()
    counted.wait_for_timeout(120)
    before = counts(counted)
    view_before = counted.evaluate("() => JSON.stringify(document.querySelector('oku-chart')._view)")
    box = chart.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    counted.mouse.move(cx, cy)
    counted.mouse.down()
    counted.mouse.move(cx - 70, cy, steps=4)
    during = counts(counted)
    counted.mouse.up()
    counted.wait_for_timeout(60)
    view_after = counted.evaluate("() => JSON.stringify(document.querySelector('oku-chart')._view)")

    assert during["document:mousemove"] == before["document:mousemove"] + 1, during
    assert view_after != view_before, "the chart did not pan"
    assert counts(counted) == before


def test_the_whole_resize_handle_answers_the_pointer(counted) -> None:
    """The grab zone has to be inside its own cell. Straddling the
    column boundary (`right: -3px`) reads as the obvious way to write
    it — the reader is aiming at a line between two columns — and it
    does not work: a `th` is positioned, later siblings paint over
    earlier ones, so the next cell covered the outer two-thirds.

    Measured before: of six visible pixels, two answered, and the grip
    line the reader can see was in the dead part, where a click sorted
    the NEXT column instead of resizing this one.
    """
    handle = counted.query_selector("table th .okt-col-resize")
    handle.scroll_into_view_if_needed()
    counted.wait_for_timeout(120)
    measured = counted.evaluate("""() => {
      const h = document.querySelector('table th .okt-col-resize');
      const own = h.parentElement;
      const r = h.getBoundingClientRect();
      const at = [];
      for (let dx = 1; dx < Math.round(r.width); dx++) {
        const e = document.elementFromPoint(r.x + dx, r.y + r.height / 2);
        at.push(e === h ? 'handle' : e === own ? 'own th' : e ? e.tagName : 'nothing');
      }
      const grip = getComputedStyle(h, '::after');
      return { width: Math.round(r.width), at, gripRight: grip.right };
    }""")
    assert measured["width"] >= 8, f"the grab zone is {measured['width']}px wide"
    dead = [i + 1 for i, v in enumerate(measured["at"]) if v != "handle"]
    assert dead == [], f"px {dead} of {measured['width']} do not reach the handle: {measured['at']}"
