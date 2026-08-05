"""The rail: where you are, what shape the page is, and one click back.

The progress bar knew how far down the page you were and nothing else.
The rail adds the two things a reader of a long document keeps asking
for — the shape of the page, and a way back to the figure they
remember. Headings are ticks, figures are dots, both are buttons.

The governing constraint is in the brief: **no UI drift during
interaction**. A control at the very top of the page, where a mis-click
costs a scroll position, must not move under the pointer. So hover,
focus and the current-position highlight change colour and opacity
only, and the label is absolutely positioned and pointer-transparent.
Several tests below do nothing but compare bounding boxes across
states.

The second constraint is "do not make it annoying", which is mostly
about density: 49 landmarks on a 390px rail measured 0px apart, which
is a smear rather than a map. Marks are thinned, and the thinning is
asserted rather than eyeballed.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PARA = (
    "Every checkpoint flushes whatever the writer has buffered, and a five-second "
    "checkpoint interval on a modestly sized topic produces twelve files per minute "
    "per bucket, none of them anywhere near the target size. "
)

TABLE = "\n".join(
    ["| Stage | Input | Output |", "|---|---|---|"] + [f"| row {i} | {i} | x |" for i in range(1, 9)]
)

CODE = "```python\nvalue = 'a plain code block, which earns no mark'\n```"


def _section(n: int, body: str) -> str:
    return f"## Section {n} {{#s{n}}}\n\n{PARA * 6}\n\n{body}\n\n{PARA * 6}\n"


LONG_MD = (
    "---\ntitle: Rail\nsummary: Landmarks on the progress strip.\n---\n\n"
    + _section(1, TABLE)
    + _section(2, "```mermaid\nflowchart LR\n  A[write] --> B[read]\n```")
    + _section(
        3, '```oku-chart\n{"type":"bar","rows":[{"label":"a","value":6},{"label":"b","value":9}]}\n```'
    )
    + _section(4, CODE)
    + _section(5, TABLE)
    + _section(6, CODE)
)

# Shorter than one viewport: nothing to report, nothing to navigate.
SHORT_MD = "---\ntitle: Short\nsummary: Fits on one screen.\n---\n\n## Only {#only}\n\nOne line.\n"

PAGES = {"long": LONG_MD, "short": SHORT_MD}


@pytest.fixture(scope="module")
def rail_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("rail")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": f"{s}.html", "source": f"{s}.md", "title": s, "parent": None} for s in PAGES],
    }
    for stem, md in PAGES.items():
        (d / f"{stem}.md").write_text(md, encoding="utf-8")
        (d / f"{stem}.html").write_text(cli._stub_for(stem, inline_manifest=manifest), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def rendered(rail_url, browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{rail_url}/long.html")
    page.wait_for_timeout(2200)
    yield page
    page.close()


BOXES = """() => {
  const box = e => { const b = e.getBoundingClientRect();
                     return [Math.round(b.x), Math.round(b.y),
                             Math.round(b.width), Math.round(b.height)]; };
  const rail = document.getElementById('oku-rail');
  return { rail: box(rail),
           marks: [...document.querySelectorAll('.okt-rail-mark')].map(box) };
}"""


# ---------- it shows the page ----------


def test_the_rail_marks_headings_and_figures(rendered):
    got = rendered.evaluate(
        """() => {
        const marks = [...document.querySelectorAll('.okt-rail-mark')];
        const kinds = {};
        marks.forEach(m => { kinds[m.dataset.kind] = (kinds[m.dataset.kind] || 0) + 1; });
        return { kinds, labels: marks.map(m => m.getAttribute('aria-label')) };
    }"""
    )
    assert got["kinds"].get("section") == 6, got
    assert got["kinds"].get("figure", 0) >= 4, got
    assert any("Table" in x for x in got["labels"]), got["labels"]
    assert any("Diagram" in x for x in got["labels"]), got["labels"]
    assert any("Chart" in x for x in got["labels"]), got["labels"]


def test_a_plain_code_block_earns_no_mark(rendered):
    """Code is dense in a technical page. Marking every block turns the
    rail into a dotted line, which is the annoyance this is avoiding —
    so `<pre>` is deliberately not a landmark kind."""
    n = rendered.evaluate(
        """() => [...document.querySelectorAll('.okt-rail-mark')]
                 .filter(m => /code|snippet/i.test(m.getAttribute('aria-label'))).length"""
    )
    assert n == 0, f"{n} plain code blocks were marked"


def test_a_mark_sits_where_the_fill_will_reach_it(rendered):
    """Marks and the fill share one scale, so the fill edge arrives at a
    mark exactly when that landmark reaches the top of the viewport. If
    they diverge the highlight contradicts the bar beside it."""
    got = rendered.evaluate(
        """async () => {
        const m = [...document.querySelectorAll('.okt-rail-mark')][3];
        const pct = parseFloat(m.style.left);
        const h = document.documentElement;
        window.scrollTo(0, (h.scrollHeight - h.clientHeight) * pct / 100);
        // `html { scroll-behavior: smooth }` animates scrollTo, so a
        // fixed wait samples mid-flight. Settle first.
        let last = -1;
        for (let i = 0; i < 60 && last !== window.scrollY; i++) {
          last = window.scrollY;
          await new Promise(r => setTimeout(r, 50));
        }
        return { markPct: pct, fillPct: parseFloat(document.getElementById('progress-bar').style.width) };
    }"""
    )
    assert abs(got["markPct"] - got["fillPct"]) <= 0.5, got


def test_the_current_mark_follows_the_fill(rendered):
    got = rendered.evaluate(
        """async () => {
        const h = document.documentElement;
        window.scrollTo(0, (h.scrollHeight - h.clientHeight) * 0.55);
        await new Promise(r => setTimeout(r, 400));
        const cur = document.querySelector('.okt-rail-mark.is-current');
        const fill = parseFloat(document.getElementById('progress-bar').style.width);
        const after = [...document.querySelectorAll('.okt-rail-mark')]
          .filter(m => parseFloat(m.style.left) > fill + 0.01).length;
        return { current: cur ? parseFloat(cur.style.left) : null, fill,
                 marksPastTheFill: after };
    }"""
    )
    assert got["current"] is not None, got
    assert got["current"] <= got["fill"] + 0.01, got
    assert got["marksPastTheFill"] > 0, "nothing left ahead — the sample scrolled too far"


def test_a_page_that_fits_on_one_screen_has_no_rail(rail_url, browser):
    """No position to report and nothing to navigate to."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"{rail_url}/short.html")
        page.wait_for_timeout(1200)
        got = page.evaluate(
            """() => {
            const rail = document.getElementById('oku-rail');
            return { scrollable: rail.getAttribute('data-scrollable'),
                     display: getComputedStyle(rail).display,
                     marks: document.querySelectorAll('.okt-rail-mark').length };
        }"""
        )
        assert got["scrollable"] == "0", got
        assert got["display"] == "none", got
        assert got["marks"] == 0, got
    finally:
        page.close()


# ---------- it navigates ----------


def test_clicking_a_mark_lands_the_landmark_below_the_chrome(rendered):
    """80px matches the `:target` scroll-margin, so a rail jump and an
    anchor jump put the heading in the same place."""
    got = rendered.evaluate(
        """async () => {
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 300));
        const m = [...document.querySelectorAll('.okt-rail-mark[data-kind="section"]')][4];
        m.click();
        await new Promise(r => setTimeout(r, 1000));
        return { top: Math.round(m._okuMark.el.getBoundingClientRect().top),
                 scrolled: Math.round(window.scrollY) };
    }"""
    )
    assert got["scrolled"] > 0, got
    assert abs(got["top"] - 80) <= 4, got


def test_the_label_appears_on_hover_and_cannot_push_anything(rendered):
    got = rendered.evaluate(
        """() => {
        const tip = document.querySelector('.okt-rail-tip');
        return { pointer: getComputedStyle(tip).pointerEvents,
                 position: getComputedStyle(tip).position,
                 restOpacity: getComputedStyle(tip).opacity };
    }"""
    )
    assert got["pointer"] == "none", got
    assert got["position"] == "absolute", got
    assert got["restOpacity"] == "0", got

    rendered.hover('.okt-rail-mark[data-kind="figure"] >> nth=0')
    rendered.wait_for_timeout(300)
    shown = rendered.evaluate(
        """() => {
        const tip = document.querySelector('.okt-rail-tip');
        const r = tip.getBoundingClientRect();
        return { visible: tip.classList.contains('visible'),
                 opacity: getComputedStyle(tip).opacity,
                 text: tip.textContent.trim(),
                 left: Math.round(r.left), right: Math.round(r.right),
                 vw: window.innerWidth };
    }"""
    )
    assert shown["visible"] and shown["opacity"] == "1", shown
    assert shown["text"], "the label rendered empty"
    assert shown["left"] >= 0 and shown["right"] <= shown["vw"], (
        f"the label runs outside the viewport: {shown}"
    )


def test_the_rail_is_one_tab_stop_with_arrow_keys_inside(rendered):
    """One stop, not one per landmark — fifty extra stops at the top of
    every page would make the keyboard path through the document worse.
    But the figures are reachable ONLY here, so the marks cannot simply
    be hidden from the keyboard either."""
    tabbable = rendered.evaluate(
        """() => [...document.querySelectorAll('.okt-rail-mark')].filter(m => m.tabIndex === 0).length"""
    )
    assert tabbable == 1, f"{tabbable} marks are in the tab order"

    got = rendered.evaluate(
        """() => {
        const marks = [...document.querySelectorAll('.okt-rail-mark')];
        marks[0].focus();
        const before = marks.indexOf(document.activeElement);
        marks[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
        const after = marks.indexOf(document.activeElement);
        marks[after].dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
        const end = marks.indexOf(document.activeElement);
        document.activeElement.blur();
        return { before, after, end, total: marks.length };
    }"""
    )
    assert got["before"] == 0, got
    assert got["after"] == 1, got
    assert got["end"] == got["total"] - 1, got


# ---------- it does not move ----------


def test_nothing_moves_on_hover(rendered):
    before = rendered.evaluate(BOXES)
    rendered.hover(".okt-rail-mark >> nth=2")
    rendered.wait_for_timeout(350)
    after = rendered.evaluate(BOXES)
    assert before == after, "the rail or its marks moved under the pointer"


def test_nothing_moves_on_focus(rendered):
    before = rendered.evaluate(BOXES)
    rendered.evaluate("""() => document.querySelectorAll('.okt-rail-mark')[2].focus()""")
    rendered.wait_for_timeout(350)
    after = rendered.evaluate(BOXES)
    rendered.evaluate("""() => document.activeElement.blur()""")
    assert before == after, "the rail or its marks moved on focus"


def test_nothing_moves_when_the_current_mark_changes(rendered):
    """The highlight travels the whole rail as the reader scrolls. If it
    resized the mark it would ripple the row on every scroll tick."""
    got = rendered.evaluate(
        """async () => {
        const box = e => { const b = e.getBoundingClientRect();
                           return [Math.round(b.x), Math.round(b.y),
                                   Math.round(b.width), Math.round(b.height)]; };
        const marks = [...document.querySelectorAll('.okt-rail-mark')];
        const h = document.documentElement;
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 350));
        const before = marks.map(box);
        window.scrollTo(0, (h.scrollHeight - h.clientHeight) * 0.7);
        await new Promise(r => setTimeout(r, 400));
        const highlighted = !!document.querySelector('.okt-rail-mark.is-current');
        return { same: JSON.stringify(before) === JSON.stringify(marks.map(box)), highlighted };
    }"""
    )
    assert got["highlighted"], "no mark was marked current — the check proves nothing"
    assert got["same"], "a mark changed size when the current highlight moved"


# ---------- it stays legible ----------


def test_the_rail_is_opaque_so_marks_read_over_scrolled_content(rendered):
    """The marks hang below the track. At 3px tall the strip could not
    contain them and they were drawn over whatever prose was scrolling
    underneath, where a 2px tick is a speck rather than a landmark."""
    got = rendered.evaluate(
        """() => {
        const rail = document.getElementById('oku-rail');
        const cs = getComputedStyle(rail);
        const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
        const probe = document.createElement('div');
        probe.style.color = bg; document.body.appendChild(probe);
        const bgRgb = getComputedStyle(probe).color; probe.remove();
        const tallest = Math.max(...[...document.querySelectorAll('.okt-rail-mark')].map(m => {
            const b = getComputedStyle(m, '::before');
            return parseFloat(b.top || 0) + parseFloat(b.height || 0);
        }));
        return { height: parseFloat(cs.height), bg: cs.backgroundColor, expect: bgRgb,
                 tallestMark: tallest };
    }"""
    )
    assert got["bg"] == got["expect"], got
    assert got["height"] >= got["tallestMark"], (
        f"marks reach {got['tallestMark']}px inside a {got['height']}px strip"
    )


@pytest.mark.parametrize(("width", "expect_figures"), [(1440, True), (390, False)])
def test_marks_never_collide_at_any_width(rail_url, browser, width, expect_figures):
    """49 landmarks on a 390px rail measured 0px apart. Sections are
    always kept — they are the shape of the page — and figures are
    placed only where they clear their neighbours, or not at all on a
    rail too narrow to separate them (and with no pointer to hover)."""
    page = browser.new_page(viewport={"width": width, "height": 844})
    try:
        page.goto(f"{rail_url}/long.html")
        page.wait_for_timeout(2200)
        got = page.evaluate(
            """() => {
            const marks = [...document.querySelectorAll('.okt-rail-mark')];
            const xs = marks.map(m => m.getBoundingClientRect().x + 7).sort((a, b) => a - b);
            let min = Infinity;
            for (let i = 1; i < xs.length; i++) min = Math.min(min, xs[i] - xs[i - 1]);
            const kinds = {};
            marks.forEach(m => { kinds[m.dataset.kind] = (kinds[m.dataset.kind] || 0) + 1; });
            return { kinds, minGap: min, total: marks.length };
        }"""
        )
        assert got["kinds"].get("section") == 6, got
        assert (got["kinds"].get("figure", 0) > 0) is expect_figures, got
        assert got["minGap"] >= 6, f"marks {got['minGap']}px apart at {width}px: {got}"
    finally:
        page.close()
