"""What the page looks like where nobody is hovering: paper, and a
finger.

Both are delivery surfaces the kit is used for — a report gets printed
or saved to PDF, and it gets opened on a phone — and both were reached
only by rules written for a mouse on a screen.

On paper the print block repainted `body`, the headings and links, and
could not reach anything token-driven, which is most of the page. A
reader with dark mode on therefore printed `pre` at #e8e6f5 on a white
body and cards painted #15122a with black text; measured contrast 1.23
and 1.15, so the code blocks came out blank. It also printed 318 pieces
of live chrome — language pills, fold markers, resize bars, a whole
table toolbar — and clipped four horizontally-scrolling boxes at the
paper edge, because paper does not scroll.

On a touch screen the wrap toggle was revealed only by
`.okt-pre-host:hover`, so it sat at opacity 0 and still took clicks. It
is the control that fixes a code block scrolling sideways, on the device
where that hurts most. `.copy-btn` had a rescue keyed off
`max-width: 768px` — a WIDTH proxy for a HOVER question, which covers a
phone and leaves a touch tablet at 1024px with neither button.
"""

from __future__ import annotations

from ._wait import measured, page_quiet, stable

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

TABLE = {
    "k": "table",
    "headers": ["Engine", {"label": "Tags", "filter": "chips", "values": ["fast", "slow"]}, "Notes"],
    "rows": [
        [
            "Spark",
            {"values": ["fast"]},
            "A long note so the table has something to lay out across the column.",
        ],
        ["Flink", {"values": ["slow"]}, "Another long note, long enough to make the row wrap on paper."],
    ],
}

PAGE = (
    "---\ntitle: Surfaces\nsummary: A page with code, a table and a callout.\n---\n\n"
    "## Code {#code}\n\n"
    "```python\ndef f(x):\n    return x * 2\n```\n\n"
    "## Table {#table}\n\n```oku-table\n" + json.dumps(TABLE) + "\n```\n\n"
    "> [!NOTE]\n> A callout, which paints its own surface.\n"
)

LUM = """(c) => {
  const m = String(c).match(/[\\d.]+/g).map(Number);
  const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]);
}"""

# WCAG 2.1 SC 1.4.3, the text threshold. Body text on paper is text.
MIN_TEXT_RATIO = 4.5


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("printtouch").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "page.md").write_text(PAGE, encoding="utf-8")
    (d / "page.html").write_text(
        cli._stub_for("page", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


PRINT_MEASURE = """(lumSrc) => {
  const lum = eval('(' + lumSrc + ')');
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const [h, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
                            return Math.round(((h + 0.05) / (lo + 0.05)) * 100) / 100; };
  const bodyBg = getComputedStyle(document.body).backgroundColor;
  const texts = [];
  document.querySelectorAll('pre, .callout, .okt-table-wrap, main p').forEach(el => {
    const st = getComputedStyle(el);
    const bg = st.backgroundColor === 'rgba(0, 0, 0, 0)' ? bodyBg : st.backgroundColor;
    texts.push({ sel: el.tagName + '.' + (el.className || '').split(' ')[0], ratio: ratio(st.color, bg) });
  });
  const live = [...document.querySelectorAll(
    '.okt-code-lang, .okt-fold-marker, .okt-col-resize, .okt-table-controls, .okt-chip-rack, .okt-view-switch, .ctrl-btn, .okt-rail')]
    .filter(e => getComputedStyle(e).display !== 'none').length;
  const clipped = [...document.querySelectorAll('*')].filter(e => {
    const st = getComputedStyle(e);
    return ['auto', 'scroll'].includes(st.overflowX) && e.scrollWidth > e.clientWidth + 2;
  }).length;
  return { bodyBg, bodyLum: lum(bodyBg), texts, live, clipped };
}"""


@pytest.fixture(scope="module")
def printed_dark(browser, served):
    pg = browser.new_page(viewport={"width": 794, "height": 1123})  # A4 at 96dpi
    try:
        pg.goto(f"{served}/page.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        pg.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
        # Two settles, and they are different things: the dark theme
        # painting, then the print stylesheet replacing it. Both are
        # transitions on the colours this fixture is about to measure.
        stable(
            pg,
            "() => getComputedStyle(document.body).backgroundColor",
            what="the dark theme finished painting",
        )
        pg.emulate_media(media="print")
        return measured(pg, PRINT_MEASURE, LUM)
    finally:
        pg.close()


def test_a_page_printed_from_dark_mode_is_readable(printed_dark) -> None:
    assert printed_dark["bodyLum"] > 0.8, f"paper should be light, body is {printed_dark['bodyBg']}"
    assert printed_dark["texts"], "nothing was measured — the probe page rendered no text surfaces"
    worst = min(printed_dark["texts"], key=lambda t: t["ratio"])
    assert worst["ratio"] >= MIN_TEXT_RATIO, f"{worst['sel']} prints at {worst['ratio']}:1"


def test_no_live_control_is_printed(printed_dark) -> None:
    assert printed_dark["live"] == 0, f"{printed_dark['live']} live control(s) printed onto paper"


def test_nothing_wide_is_clipped_at_the_paper_edge(printed_dark) -> None:
    assert printed_dark["clipped"] == 0, f"{printed_dark['clipped']} box(es) scroll horizontally on paper"


@pytest.mark.parametrize("width", [1024, 360])
def test_the_reveal_controls_are_visible_without_a_hover(browser, served, width: int) -> None:
    ctx = browser.new_context(viewport={"width": width, "height": 800}, has_touch=True)
    pg = ctx.new_page()
    cdp = ctx.new_cdp_session(pg)
    cdp.send(
        "Emulation.setEmulatedMedia",
        {"features": [{"name": "hover", "value": "none"}, {"name": "any-hover", "value": "none"}]},
    )
    try:
        pg.goto(f"{served}/page.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        page_quiet(pg)
        m = pg.evaluate("""() => {
          const op = e => +getComputedStyle(e).opacity;
          const w = [...document.querySelectorAll('.okt-wrap-btn')];
          const c = [...document.querySelectorAll('.copy-btn')];
          return { hoverNone: matchMedia('(hover: none)').matches,
                   wrap: w.length, wrapMin: w.length ? Math.min(...w.map(op)) : null,
                   copy: c.length, copyMin: c.length ? Math.min(...c.map(op)) : null };
        }""")
        assert m["hoverNone"], "the hover:none emulation did not take — this test proves nothing without it"
        assert m["wrap"], "no wrap toggle on the page to measure"
        assert m["wrapMin"] >= 0.9, f"{width}px touch: wrap toggle at opacity {m['wrapMin']}"
        assert m["copyMin"] >= 0.9, f"{width}px touch: copy button at opacity {m['copyMin']}"
    finally:
        pg.close()
        ctx.close()


def test_the_warning_count_can_be_read_in_both_themes(browser, served) -> None:
    """`--danger` inverts across themes and the literal `white` on top of
    it did not: 6.5:1 in light, 1.9:1 in dark. This is the one control
    exempt from the chrome-dimming floor, on the reasoning that an alert
    which dims itself is a bug."""
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        pg.goto(f"{served}/page.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        for theme in ("light", "dark"):
            m = pg.evaluate(
                """([lumSrc, theme]) => {
                  const lum = eval('(' + lumSrc + ')');
                  document.documentElement.setAttribute('data-theme', theme);
                  let btn = document.querySelector('.ctrl-btn.warning-indicator');
                  if (!btn) { btn = document.createElement('button');
                              btn.className = 'ctrl-btn warning-indicator';
                              document.body.appendChild(btn); }
                  btn.setAttribute('data-count', '3');
                  const st = getComputedStyle(btn, '::after');
                  const l1 = lum(st.backgroundColor), l2 = lum(st.color);
                  const [h, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
                  return { bg: st.backgroundColor, fg: st.color,
                           ratio: Math.round(((h + 0.05) / (lo + 0.05)) * 100) / 100 };
                }""",
                [LUM, theme],
            )
            assert m["ratio"] >= MIN_TEXT_RATIO, (
                f"{theme}: count badge is {m['ratio']}:1 ({m['fg']} on {m['bg']})"
            )
    finally:
        pg.close()
