"""A reading says the value, not a rounded stand-in for it.

The figure prints compact labels where room is short — `1.2k` on a
treemap cell — and that is fine. A reading is where the reader goes FOR
the number: the tooltip, a mark's `<title>`, its `aria-label`. Those went
through the same compact formatter, so a gantt bar over 2024 to 2025 read
`start 2k`, `end 2k`, and every value from 1000 up was rounded to a
hundred in every chart's tooltip. The bar charts' readings, drawn by
renderer.js, already said the value.

The cases are derived: every shipped example in
`kit/schema/examples.json` shifted by 2000, past the compact threshold.
Two kinds of reading are asked for. The ones already in the document —
hover payloads, `<title>`, `aria-label` — are read straight off it; the
ones a cursor builds on the fly are read off the tooltip after the
pointer moves to the middle of the plot.
"""

from __future__ import annotations

import http.server
import json
import re
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet, until
from .test_hover_shows_a_reading import _settle, _visible

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"
EXAMPLES = json.loads((KIT / "schema" / "examples.json").read_text(encoding="utf-8"))["charts"]

# What fmtNum makes of 1000 and up: `2k`, `2.1k`, `-1.5k`.
COMPACT = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?k(?!\w)")


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


def _cases() -> dict[str, dict]:
    out = {}
    for ctype in sorted(EXAMPLES):
        blk = _mapnum(dict(EXAMPLES[ctype]), lambda n: n + 2000)
        blk["k"], blk["type"] = "chart", ctype
        out[ctype] = blk
    out["gantt-years"] = {
        "k": "chart",
        "type": "gantt",
        "tasks": [
            {"label": "one", "start": 2024, "end": 2025},
            {"label": "two", "start": 2025, "end": 2026.5},
        ],
    }
    return out


CASES = _cases()

STATIC = """(names) => {
  const out = {};
  for (const name of names) {
    const sec = document.getElementById(name);
    if (!sec) { out[name] = null; continue; }
    const texts = [];
    for (const el of sec.querySelectorAll('[data-hover-payload]')) {
      try {
        const p = JSON.parse(el.getAttribute('data-hover-payload'));
        texts.push(p.label || '', p.footer || '', ...(p.kv || []).map(r => String(r.v)));
      } catch (e) { texts.push(el.getAttribute('data-hover-payload')); }
    }
    for (const t of sec.querySelectorAll('svg title')) texts.push(t.textContent);
    for (const el of sec.querySelectorAll('svg [aria-label]')) texts.push(el.getAttribute('aria-label'));
    out[name] = texts;
  }
  return out;
}"""


@pytest.fixture(scope="module")
def served(browser, tmp_path_factory):
    root = tmp_path_factory.mktemp("readings").resolve()
    (root / "_oku").symlink_to(KIT, target_is_directory=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    blocks = []
    for name, blk in CASES.items():
        blocks.append(f"## {name} {{#{name}}}")
        blocks.append(blk)
    page_json = {"k": "page", "t": "Readings", "m": {"summary": "Readings."}, "b": blocks}
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
        yield page
    finally:
        page.close()
        httpd.shutdown()


@pytest.fixture(scope="module")
def static_readings(served) -> dict:
    return served.evaluate(STATIC, list(CASES))


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_reading_in_the_document_says_the_value(name, static_readings) -> None:
    texts = static_readings[name]
    assert texts is not None, f"{name} did not render"
    assert [t for t in texts if COMPACT.search(t)] == []


# The middle of the plot band, read off the cursor's own bounds where the
# chart has them and the svg's middle where it does not.
MIDDLE = """(id) => {
  const s = document.getElementById(id).querySelector('svg.okc-svg');
  if (!s) return null;
  const r = s.getBoundingClientRect();
  return {x: r.left + r.width * 0.55, y: r.top + r.height * 0.5};
}"""

SHOWN = """(id) => [...document.getElementById(id).querySelectorAll('.okc-tooltip')]
  .filter((t) => t.classList.contains('visible')).map((t) => t.textContent)"""


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_reading_the_pointer_builds_says_the_value(name, served) -> None:
    """Whatever answers the pointer in the middle of the plot — a
    cursor's reading built on the fly, or a mark's. A chart where
    nothing answers there is not this test's question."""
    _settle(served, name)
    spot = served.evaluate(MIDDLE, name)
    if spot is None:
        pytest.skip(f"{name} draws no svg")
    served.mouse.move(spot["x"] - 14, spot["y"] - 14)
    served.mouse.move(spot["x"], spot["y"], steps=6)
    try:
        until(served, _visible(name), timeout=1500, what=f"{name} answered the pointer")
    except AssertionError:
        served.mouse.move(4, 4)
        pytest.skip(f"nothing answers the pointer in the middle of {name}")
    shown = served.evaluate(SHOWN, name)
    served.mouse.move(4, 4)
    assert [t for t in shown if COMPACT.search(t)] == []


def test_the_gantt_reading_names_the_years(static_readings) -> None:
    assert "2024" in static_readings["gantt-years"] and "2026.5" in static_readings["gantt-years"]


@pytest.fixture(scope="module")
def kit_page(browser):
    page = browser.new_page()
    page.set_content("<html><body></body></html>")
    page.add_script_tag(path=str(KIT / "chrome.js"))
    yield page
    page.close()


@pytest.mark.parametrize(
    ("call", "expect"),
    [
        ("fmtReading(2024.5)", "2024.5"),
        ("fmtReading(1234567)", "1234567"),
        # Float noise goes; what the author typed stays.
        ("fmtReading(26.9 + 10.4 + 9.2 + 9 + 6.6 + 0.2)", "62.3"),
        ("fmtReading(0.0043)", "0.0043"),
        ("fmtReading('')", ""),
        # The pointer is as precise as one unit of the drawing.
        ("fmtAt(2024.372911, 2.5 / 600)", "2024.373"),
        ("fmtAt(12.3456, 0.5)", "12.3"),
        ("fmtAt(1234.56, 20)", "1235"),
    ],
)
def test_the_formatters(kit_page, call, expect) -> None:
    assert kit_page.evaluate(f"() => {call}") == expect
