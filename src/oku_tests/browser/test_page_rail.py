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

# A figure that is none of the three named shapes — it must land on the
# hollow fallback rather than borrowing the table's square.
KPI = (
    "```oku-kpi-grid\n"
    '{"tiles":[{"num":"12","label":"Files per minute"},'
    '{"num":"5","label":"Second checkpoint interval"}]}\n'
    "```"
)


CHART = '```oku-chart\n{"type":"bar","rows":[{"label":"a","value":6},{"label":"b","value":9}]}\n```'

# A chart wrapped in a generic container. docs/charts.md is built entirely
# out of these, and the wrapper used to claim the position a few pixels
# above the chart it contains — so the thinner dropped every chart and a
# page of 48 of them drew no chart shape at all.
WRAPPED_CHART = (
    "```oku-example\n"
    '{"code":{"k":"code","src":"{\\"type\\":\\"bar\\"}","lang":"json"},'
    '"output":{"k":"chart","type":"bar","rows":[{"label":"a","value":6},'
    '{"label":"b","value":9}]}}\n'
    "```"
)


def _section(n: int, body: str) -> str:
    return f"## Section {n} {{#s{n}}}\n\n{PARA * 6}\n\n{body}\n\n### Detail {n}\n\n{PARA * 6}\n"


LONG_MD = (
    "---\ntitle: Rail\nsummary: Landmarks on the progress strip.\n---\n\n"
    + _section(1, TABLE)
    + _section(2, "```mermaid\nflowchart LR\n  A[write] --> B[read]\n```")
    + _section(3, CHART)
    + _section(4, CODE + "\n\n" + KPI)
    # The wrapped chart needs prose on both sides: the thinner drops a
    # figure that lands within 6px of a neighbour, and the point of the
    # test is which of the two overlapping CLAIMS wins, not thinning.
    + _section(5, TABLE + "\n\n" + PARA * 6 + "\n\n" + WRAPPED_CHART)
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


@pytest.fixture(autouse=True)
def _pointer_parked(rendered):
    """The page is module-scoped and the rail now reacts to hover, so a
    test that leaves the pointer on the strip changes the state the next
    test measures. Park it over the document before each one."""
    rendered.mouse.move(700, 600)
    rendered.wait_for_timeout(250)


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
    """The rail OPENS on hover — 12px of hairline becomes 28px of legible
    map. "Thicker, without drifting the UI" is the whole constraint, and
    it is satisfied by the direction of the growth: the strip is fixed
    with a fixed top edge, so it can only grow downward, and every mark
    keeps its x, its width and its top. Nothing the pointer is aiming at
    moves, and nothing in the document moves at all."""
    before = rendered.evaluate(BOXES)
    before_main = rendered.evaluate(
        """() => Math.round(document.querySelector('main').getBoundingClientRect().top)"""
    )
    rendered.hover(".okt-rail-mark >> nth=2")
    rendered.wait_for_timeout(350)
    after = rendered.evaluate(BOXES)
    after_main = rendered.evaluate(
        """() => Math.round(document.querySelector('main').getBoundingClientRect().top)"""
    )

    # x, y, width: identical. Height: the rail and its targets grow.
    assert [b[:3] for b in before["marks"]] == [a[:3] for a in after["marks"]], (
        "a mark moved or changed width under the pointer"
    )
    assert before["rail"][:3] == after["rail"][:3], "the strip moved under the pointer"
    assert before["rail"][3] == 12, before["rail"]
    assert after["rail"][3] == 32, after["rail"]
    assert after["marks"][0][3] > before["marks"][0][3], "the targets did not grow with the strip"
    assert before_main == after_main, "the page content moved when the rail opened"


def test_nothing_moves_on_focus(rendered):
    """Same growth for the keyboard: a 3px mark you cannot see is not a
    target, so focus opens the rail too — and moves nothing."""
    before = rendered.evaluate(BOXES)
    rendered.evaluate("""() => document.querySelectorAll('.okt-rail-mark')[2].focus()""")
    rendered.wait_for_timeout(350)
    after = rendered.evaluate(BOXES)
    rendered.evaluate("""() => document.activeElement.blur()""")
    rendered.wait_for_timeout(300)
    assert [b[:3] for b in before["marks"]] == [a[:3] for a in after["marks"]], (
        "a mark moved or changed width on focus"
    )
    assert before["rail"][:3] == after["rail"][:3], "the strip moved on focus"
    assert after["rail"][3] == 32, after["rail"]


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


# ---------- what kind of thing is at this position ----------


def test_marks_are_shaped_by_what_they_point_at(rendered):
    """A 4px mark can carry a silhouette; it cannot carry an alphabet.
    The three kinds a reader hunts for by name get one each — a square
    for a table, a round for a chart, an angle for a diagram — and
    every other figure gets the hollow fallback, so none of the three
    is ever confused with something else."""
    got = rendered.evaluate(
        """() => {
        const out = {};
        for (const m of document.querySelectorAll('.okt-rail-mark')) {
            const key = m.dataset.kind + '/' + m.dataset.shape;
            out[key] = (out[key] || 0) + 1;
        }
        return out;
    }"""
    )
    assert got.get("section/bar") == 6, got
    assert got.get("figure/square", 0) == 2, got  # the two tables, and only those
    assert got.get("figure/round", 0) >= 1, got  # the chart
    assert got.get("figure/angle", 0) >= 1, got  # the mermaid diagram
    assert got.get("figure/hollow", 0) >= 1, got  # the KPI grid — not a square


def test_a_table_a_chart_and_a_diagram_never_share_a_silhouette(rendered):
    """ "So I can find what I'm looking for at a glance" is only true if
    the three shapes are actually distinguishable geometry, not three
    names for one 4px box. Border-radius separates square from round;
    the diamond's rotation separates it from both; the hollow fallback
    has no fill at all."""
    got = rendered.evaluate(
        """() => {
        const of = shape => {
            const m = document.querySelector(`.okt-rail-mark[data-shape="${shape}"]`);
            if (!m) return null;
            const s = getComputedStyle(m, '::before');
            return { radius: s.borderTopLeftRadius, transform: s.transform,
                     bg: s.backgroundColor, ring: s.boxShadow };
        };
        return { square: of('square'), round: of('round'),
                 angle: of('angle'), hollow: of('hollow') };
    }"""
    )
    assert got["square"]["radius"] != got["round"]["radius"], got
    # A 4x4 box with a 50% radius is a circle; 1px is a square.
    assert got["round"]["radius"] in ("50%", "2px"), got["round"]
    # The diamond carries a rotation the others do not — matrix(a,b,c,d…)
    # with a non-zero b is a rotated box.
    assert got["angle"]["transform"] != got["square"]["transform"], got
    assert "none" not in got["angle"]["transform"], got["angle"]
    # Hollow is a ring, not a fill.
    assert got["hollow"]["bg"] in ("rgba(0, 0, 0, 0)", "transparent"), got["hollow"]
    assert "inset" in got["hollow"]["ring"], got["hollow"]


def test_a_wrapped_chart_still_reads_as_a_chart(rendered):
    """One dot per position, and the kind that wins is the specific one.
    Every chart in docs/charts.md sits inside an example pair; the pair
    starts a few pixels above the chart, so with both claiming a mark the
    thinner kept the pair and dropped the chart — 48 charts, no chart
    shape, and a tooltip that said "Example" where the reader was looking
    for "Chart". RAIL_FIGURES order decides it now, and overlap is
    rejected in both nesting directions."""
    got = rendered.evaluate(
        """() => {
        const pair = document.querySelector('#s5 .example-pair');
        const chart = pair && pair.querySelector('oku-chart, .bar-chart');
        const marks = [...document.querySelectorAll('.okt-rail-mark')];
        const near = el => {
            const top = el.getBoundingClientRect().top + scrollY;
            const h = document.documentElement;
            const pct = (top / (h.scrollHeight - h.clientHeight)) * 100;
            return marks.filter(m => Math.abs(parseFloat(m.style.left) - pct) < 1.5)
                        .map(m => m.dataset.shape + ':' + m.getAttribute('aria-label'));
        };
        return { hasPair: !!pair, hasChart: !!chart, at: chart ? near(chart) : [] };
    }"""
    )
    assert got["hasPair"] and got["hasChart"], f"the fixture grew no wrapped chart: {got}"
    assert len(got["at"]) == 1, f"the wrapper and its chart both claimed a mark: {got}"
    assert got["at"][0].startswith("round:"), got
    assert "Chart" in got["at"][0] and "Example" not in got["at"][0], got


def test_heading_depth_is_visible_in_the_rail(rendered):
    """A page of six sections and a page of six sections with thirty
    sub-headings must not draw the same picture. Depth is carried by
    BOTH the bar's height and its thickness — the title is the thickest
    bar, a section is thinner, a sub-heading thinner still — so the
    level reads without measuring one bar against its neighbour."""
    got = rendered.evaluate(
        """() => {
        const dim = sel => {
            const m = document.querySelector(sel);
            if (!m) return null;
            const s = getComputedStyle(m, '::before');
            return { h: parseFloat(s.height), w: parseFloat(s.width) };
        };
        return { title: dim('.okt-rail-mark[data-kind="title"]'),
                 section: dim('.okt-rail-mark[data-kind="section"]'),
                 sub: dim('.okt-rail-mark[data-kind="sub"]'),
                 subCount: document.querySelectorAll('.okt-rail-mark[data-kind="sub"]').length };
    }"""
    )
    assert got["subCount"] >= 2, f"the fixture grew no sub-headings: {got}"
    assert got["title"] is not None, f"the page title earned no mark: {got}"
    assert got["sub"]["h"] < got["section"]["h"] < got["title"]["h"], got
    assert got["sub"]["w"] < got["section"]["w"] < got["title"]["w"], got


# ---------- the swell ----------


def test_the_pointer_swells_its_neighbourhood(rendered):
    """The dock behaviour: marks near the pointer scale up on a cosine
    falloff, marks beyond the radius do not move at all."""
    got = rendered.evaluate(
        """async () => {
        const rail = document.getElementById('oku-rail');
        const marks = [...document.querySelectorAll('.okt-rail-mark')];
        const target = marks[Math.floor(marks.length / 2)];
        const x = target.getBoundingClientRect().x + 7;
        rail.dispatchEvent(new PointerEvent('pointermove',
            { clientX: x, clientY: 5, bubbles: true, pointerType: 'mouse' }));
        await new Promise(r => setTimeout(r, 250));
        const mags = marks.map(m => parseFloat(m.style.getPropertyValue('--okt-mag') || '1'));
        const dists = marks.map(m => Math.abs(m.getBoundingClientRect().x + 7 - x));
        return { at: mags[marks.indexOf(target)],
                 far: mags.filter((_, i) => dists[i] > 60),
                 swollen: mags.filter(v => v > 1.02).length };
    }"""
    )
    assert got["at"] > 1.4, f"the mark under the pointer barely moved: {got}"
    assert got["swollen"] >= 1, got
    assert all(abs(v - 1) < 0.001 for v in got["far"]), f"marks beyond the radius were magnified: {got}"


def test_the_swell_moves_nothing(rendered):
    """The whole reason this is safe where a real dock is not: the scale
    is a transform on the ::before, so no button box moves and the mark
    you were aiming at is still where you decided to aim."""
    got = rendered.evaluate(
        """async () => {
        const box = e => { const b = e.getBoundingClientRect();
                           return [Math.round(b.x), Math.round(b.y),
                                   Math.round(b.width), Math.round(b.height)]; };
        const rail = document.getElementById('oku-rail');
        const marks = [...document.querySelectorAll('.okt-rail-mark')];
        const before = marks.map(box);
        const mainTop = Math.round(document.querySelector('main').getBoundingClientRect().top);
        for (const x of [200, 400, 600, 800]) {
            rail.dispatchEvent(new PointerEvent('pointermove',
                { clientX: x, clientY: 5, bubbles: true, pointerType: 'mouse' }));
            await new Promise(r => setTimeout(r, 90));
        }
        return { same: JSON.stringify(before) === JSON.stringify(marks.map(box)),
                 mainMoved: Math.round(document.querySelector('main').getBoundingClientRect().top) !== mainTop,
                 railH: Math.round(rail.getBoundingClientRect().height) };
    }"""
    )
    assert got["same"], "a mark box moved while the pointer swept the rail"
    assert not got["mainMoved"], "the page content moved while the rail was hovered"
    assert got["railH"] == 12, got


def _worst_reach(page, swell):
    """Tallest point any mark can reach, in strip coordinates, given the
    rail's current open scale and `swell` as the dock multiplier. The
    transform is anchored at the ::before's own top, so the reach is
    top + height * railScale * swell, not (top + height) * scale."""
    return page.evaluate(
        """(swell) => {
        const rail = document.getElementById('oku-rail');
        const scale = parseFloat(getComputedStyle(rail).getPropertyValue('--okt-rail-scale')) || 1;
        let worst = 0;
        for (const m of document.querySelectorAll('.okt-rail-mark')) {
            const s = getComputedStyle(m, '::before');
            worst = Math.max(worst,
                parseFloat(s.top || 0) + parseFloat(s.height || 0) * scale * swell);
        }
        return { railH: rail.getBoundingClientRect().height, scale, worst };
    }""",
        swell,
    )


def test_a_swollen_mark_stays_inside_the_strip(rendered):
    """The strip is opaque and the marks have to stay in it — a mark
    that grows past the bottom edge is drawn over whatever prose is
    scrolling underneath, which is the illegibility the strip's height
    exists to prevent.

    Two multipliers compound now, and they compound in exactly one
    state. The dock swell only ever runs while the pointer is ON the
    rail, which is the same condition that opens it — so the closed
    strip is checked without the swell, and the open one with it at
    maximum. Checking the closed strip against a swell it can never
    receive is what makes a 9px title bar look like a 14.4px overflow."""
    at_rest = _worst_reach(rendered, 1)
    assert at_rest["scale"] == 1, at_rest
    assert at_rest["railH"] == 12, at_rest
    assert at_rest["worst"] <= at_rest["railH"] + 1, at_rest

    rendered.hover(".okt-rail-mark >> nth=2")
    rendered.wait_for_timeout(350)
    hovered = _worst_reach(rendered, 1.6)
    assert hovered["scale"] > 1, "the rail did not open on hover"
    assert hovered["railH"] == 32, hovered
    assert hovered["worst"] <= hovered["railH"] + 1, hovered


def test_touch_does_not_trigger_the_swell(rendered):
    """There is no pointer to follow on a touch screen, and a swell
    that fires on tap would move the target out from under the finger
    between touchstart and touchend."""
    got = rendered.evaluate(
        """async () => {
        const rail = document.getElementById('oku-rail');
        const marks = [...document.querySelectorAll('.okt-rail-mark')];
        rail.dispatchEvent(new PointerEvent('pointerleave', { bubbles: true }));
        await new Promise(r => setTimeout(r, 120));
        const x = marks[3].getBoundingClientRect().x + 7;
        rail.dispatchEvent(new PointerEvent('pointermove',
            { clientX: x, clientY: 5, bubbles: true, pointerType: 'touch' }));
        await new Promise(r => setTimeout(r, 200));
        return marks.map(m => parseFloat(m.style.getPropertyValue('--okt-mag') || '1'));
    }"""
    )
    assert all(abs(v - 1) < 0.001 for v in got), f"touch magnified the rail: {got}"


def test_reduced_motion_flattens_the_swell(rail_url, browser):
    """The stylesheet's `prefers-reduced-motion` block collapses
    transition and animation durations, and it cannot reach the swell:
    that is a transform this code writes on every pointermove, which is
    neither. A reader who asked the OS for less movement still got a
    scale tracking their pointer.

    The rail must still WORK — it opens, the marks are still buttons,
    the tooltip still names them. Reduced motion means no animation, not
    no feature; only the pointer-tracking scale goes.
    """
    page = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    try:
        page.goto(f"{rail_url}/long.html")
        page.wait_for_timeout(2200)
        got = page.evaluate(
            """async () => {
            const rail = document.getElementById('oku-rail');
            const marks = [...document.querySelectorAll('.okt-rail-mark')];
            const x = marks[3].getBoundingClientRect().x + 7;
            rail.dispatchEvent(new PointerEvent('pointermove',
                { clientX: x, clientY: 5, bubbles: true, pointerType: 'mouse' }));
            await new Promise(r => setTimeout(r, 250));
            return {
                mags: marks.map(m => parseFloat(m.style.getPropertyValue('--okt-mag') || '1')),
                marks: marks.length,
                clickable: marks.every(m => m.tagName === 'BUTTON'),
                queryMatches: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
            };
        }"""
        )
        assert got["queryMatches"], "the browser was not emulating reduced motion"
        assert got["marks"] > 3, got
        assert all(abs(v - 1) < 0.001 for v in got["mags"]), f"reduced motion still magnified: {got}"
        assert got["clickable"], "the marks stopped being buttons"
    finally:
        page.close()


# ---------- the preview ----------


def test_a_diagram_mark_previews_the_diagram(rendered):
    """A rendered SVG clones inertly — no scripts, no custom-element
    lifecycle — so the tooltip can show the figure's real silhouette
    rather than a description of one."""
    got = rendered.evaluate(
        """async () => {
        const m = document.querySelector('.okt-rail-mark[data-kind="figure"][data-shape="angle"]');
        if (!m) return { skipped: true };
        const origId = (m._okuMark.el.querySelector('svg') || {}).id || null;
        m.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
        await new Promise(r => setTimeout(r, 300));
        const tip = document.querySelector('.okt-rail-tip');
        const thumb = tip.querySelector('.okt-rail-tip-thumb svg');
        const b = tip.getBoundingClientRect();
        return {
            hasThumb: !!thumb,
            origId,
            cloneId: thumb ? thumb.id : null,
            duplicates: origId ? document.querySelectorAll('[id="' + origId + '"]').length : 0,
            insideViewport: b.left >= 0 && b.right <= window.innerWidth,
        };
    }"""
    )
    if got.get("skipped"):
        pytest.skip("no diagram on the fixture page")
    assert got["hasThumb"], got
    assert got["insideViewport"], got
    # The clone must be renamed. page-chrome precedes <main>, so a
    # duplicate id would make document.getElementById return the
    # THUMBNAIL instead of the real diagram.
    if got["origId"]:
        assert got["duplicates"] == 1, got
        assert got["cloneId"] != got["origId"], got


def test_a_table_mark_previews_its_size(rendered):
    """No SVG to clone, so the preview is the next most useful thing
    about a table you are trying to find again: how big it is."""
    got = rendered.evaluate(
        """async () => {
        const m = [...document.querySelectorAll('.okt-rail-mark[data-kind="figure"]')]
                    .find(x => (x.getAttribute('aria-label') || '').includes('Table'));
        if (!m) return { skipped: true };
        m.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
        await new Promise(r => setTimeout(r, 300));
        const p = document.querySelector('.okt-rail-tip .okt-rail-tip-preview');
        return { text: p ? p.textContent.trim() : null };
    }"""
    )
    if got.get("skipped"):
        pytest.skip("no table on the fixture page")
    assert got["text"] and "×" in got["text"], got
