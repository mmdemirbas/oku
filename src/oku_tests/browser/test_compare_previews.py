"""A comparison card that links to a figure shows that figure.

`docs/charts.md` offers 43 chart types as 43 cards and has told the
reader, since before the markdown migration, that "each card has a tiny
live preview". Nothing ever drew one. The cards rendered as 200x220
boxes holding a single word, and every check the repo runs passed: the
schema validates, the structural lint is clean, the tests were green. An
empty box is well-formed. Only opening the page finds it.

So these assert what a rendered page looks like, in numbers:

- a card that links to a figure has a preview, and the preview has
  measurable ink in it;
- the reduction leaves no writing behind;
- the clone stays a decoration — no duplicate ids, no rail landmark, no
  hijacked layout.

Each of the geometry tests below failed before its fix and passes after.
The failures were not subtle: 9px of bar chart in a 170px box, a black
square where a scatter-matrix should be, and one comparison grid losing
its place on the rail to a clone of a chart.
"""

from __future__ import annotations

import pytest

CHARTS = "/docs/charts.html"

# A preview whose box is smaller than this is the defect this file
# exists to catch, not a small chart. The narrowest legitimate figure
# here is the three-row bar chart at 17px tall.
MIN_INK_W = 40
MIN_INK_H = 12


def _wait(page):
    page.wait_for_selector(".compare-grid[data-oku-preview] .compare-card")
    # The pass runs on oku:rendered; poll for the flag it sets rather
    # than sleeping, so a loaded machine does not turn this flaky.
    page.wait_for_function(
        "() => [...document.querySelectorAll("
        "'.compare-grid[data-oku-preview] .compare-card[href^=\"#\"]')]"
        ".every(c => c._okuPreviewBuilt || !document.getElementById(c.getAttribute('href').slice(1)))"
    )


@pytest.fixture
def charts(page, site_url):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}{CHARTS}")
    _wait(page)
    return page


def test_every_card_that_links_to_a_figure_draws_one(charts):
    """The reported bug, stated as a number: 43 cards, 43 previews, and
    none of them an empty box."""
    out = charts.evaluate(
        """() => {
          const cards = [...document.querySelectorAll(
            '.compare-grid[data-oku-preview] .compare-card[href^="#"]')];
          const rows = cards.map(c => {
            const ink = c.querySelector('.okt-compare-preview svg, .okt-compare-preview .bar-chart');
            const b = ink && ink.getBoundingClientRect();
            return {href: c.getAttribute('href'), w: b ? b.width : 0, h: b ? b.height : 0};
          });
          return {total: cards.length, rows};
        }"""
    )
    assert out["total"] >= 43, out["total"]
    empty = [r for r in out["rows"] if r["w"] < MIN_INK_W or r["h"] < MIN_INK_H]
    assert empty == [], f"{len(empty)} card(s) render an empty box: {empty[:6]}"


def test_the_reduction_leaves_no_writing_behind(charts):
    """A figure laid out for ~710px is shown at ~190px, so a label lands
    near 3px — dirt on the card rather than writing. The gauge readout
    and the row labels on dot-plot, lollipop and dumbbell all survived a
    class-list approach; this asserts the outcome, not the mechanism."""
    visible = charts.evaluate(
        """() => {
          const out = [];
          for (const p of document.querySelectorAll('.okt-compare-preview')) {
            for (const t of p.querySelectorAll('text, .bar-label, .bar-value, .bar-chart-title')) {
              const cs = getComputedStyle(t);
              const b = t.getBoundingClientRect();
              if (cs.display !== 'none' && cs.visibility !== 'hidden' && b.width > 0 && b.height > 0) {
                out.push((t.textContent || '').trim().slice(0, 30));
              }
            }
          }
          return out;
        }"""
    )
    assert visible == [], f"{len(visible)} label(s) still painted in previews: {visible[:8]}"


def test_a_clone_never_takes_a_colour_the_original_did_not_have(charts):
    """197 rules in chrome.css are scoped `oku-chart .okc-…`. A chart
    lifted out of its host matches none of them and every fill falls
    back to the initial value, which is BLACK — scatter-matrix rendered
    as a black square on a white card, and the sparkline's area went
    from teal to black. The clone is re-parented into an inert
    <oku-chart> shell so the rules still apply."""
    out = charts.evaluate(
        """() => {
          const bad = [];
          for (const p of document.querySelectorAll('.okt-compare-preview')) {
            const kind = p.getAttribute('data-oku-figure') || '?';
            for (const el of p.querySelectorAll('rect, circle, path, polygon, ellipse')) {
              const b = el.getBoundingClientRect();
              // A zero-area node paints nothing whatever its fill; the
              // cartesian plots each carry one such rect in the source too.
              if (b.width < 1 || b.height < 1) continue;
              if (getComputedStyle(el).fill === 'rgb(0, 0, 0)') {
                bad.push(kind + ' ' + el.tagName + '.' + (el.getAttribute('class') || ''));
              }
            }
          }
          return bad;
        }"""
    )
    assert out == [], f"{len(out)} node(s) fell back to an unstyled black fill: {out[:6]}"


def test_a_preview_is_never_a_landmark_on_the_rail(charts):
    """`oku-chart` and `.bar-chart` outrank `.compare-grid` in
    RAIL_FIGURES, and the rail rejects an overlapping figure in either
    nesting direction — so a clone inside a card claimed the position
    and the grid lost its mark. Measured before the fix as 7 Comparison
    marks against 8 grids, with one mark reading 'Chart'."""
    out = charts.evaluate(
        """() => {
          const marks = [...document.querySelectorAll('.okt-rail-mark, [class*="rail-mark"]')];
          return marks.filter(m => m._okuMark && m._okuMark.el && m._okuMark.el.closest &&
                                   m._okuMark.el.closest('.okt-compare-preview'))
                      .map(m => m._okuMark.tipKind + ' / ' + m._okuMark.label);
        }"""
    )
    assert out == [], f"the rail took {len(out)} landmark(s) from a preview clone: {out}"


def test_a_clone_brings_no_duplicate_ids_into_the_page(charts):
    """`url(#name)` resolves through getElementById and takes the FIRST
    match in the document. The previews sit above <main>'s figures, so a
    straight clone would hand the real chart the thumbnail's gradients
    and clip paths — the defect the rail's own thumbnail rewrites away."""
    dupes = charts.evaluate(
        """() => {
          const seen = new Set(), dup = new Set();
          for (const el of document.querySelectorAll('[id]')) {
            if (seen.has(el.id)) dup.add(el.id); else seen.add(el.id);
          }
          return [...dup];
        }"""
    )
    assert dupes == [], f"duplicate id(s) in the document: {dupes[:10]}"


def test_the_bar_family_fills_its_box_and_refits_when_the_box_changes(charts):
    """Two bugs in one shape. The bar family has no viewBox, so it is
    fitted by transform — and it must first be allowed to lay out at its
    natural width, which `main .bar-chart { max-width: 100% }` prevented
    (9px of ink in a 170px box). Then the fit has to survive a change of
    box: a window-resize listener is not enough, because the width
    control and the pinned drawer both re-measure the column without
    resizing the window."""
    # Measure the TRACK, not the chart element. The chart keeps filling
    # its box either way — it is the `1fr` column between the label and
    # the value that collapses, so an outer-box assertion passes on the
    # broken rule and proves nothing. Real ratio is 618/740; collapsed
    # it was 40/740.
    read = """() => ['#chart-bar', '#chart-stacked', '#chart-grouped'].map(h => {
      const c = document.querySelector('.compare-card[href="' + h + '"]');
      const w = c.querySelector('.okt-compare-preview');
      const chart = w.querySelector('.bar-chart');
      const track = chart.querySelector('.bar-track');
      return {h, ink: Math.round(chart.getBoundingClientRect().width),
              box: w.clientWidth,
              trackRatio: track.getBoundingClientRect().width / chart.getBoundingClientRect().width};
    })"""
    wide = charts.evaluate(read)
    assert wide, "no bar-family preview found"
    for r in wide:
        assert abs(r["ink"] - r["box"]) <= 2, f"{r['h']} does not fill its box: {r}"
        assert r["trackRatio"] >= 0.5, (
            f"{r['h']} bar track collapsed to {r['trackRatio']:.1%} of the chart — "
            "the label and value columns were taken out of the flow"
        )

    charts.set_viewport_size({"width": 360, "height": 760})
    charts.wait_for_function(
        '(prev) => { const c = document.querySelector(\'.compare-card[href="#chart-bar"] '
        ".okt-compare-preview'); return c && Math.abs("
        "c.querySelector('.bar-chart').getBoundingClientRect().width - c.clientWidth) <= 2 "
        "&& c.clientWidth !== prev; }",
        arg=wide[0]["box"],
    )
    narrow = charts.evaluate(read)
    for r in narrow:
        assert abs(r["ink"] - r["box"]) <= 2, f"{r['h']} did not re-fit when narrowed: {r}"
    assert narrow[0]["box"] != wide[0]["box"], "the box never actually changed, so nothing was proven"


def test_a_grid_that_did_not_ask_for_previews_gets_none(charts):
    """Opt-in per grid. Every compare-grid in the kit links somewhere;
    switching this on globally would grow a thumbnail under cards whose
    author never asked for one."""
    out = charts.evaluate(
        """() => [...document.querySelectorAll('.compare-grid:not([data-oku-preview])')]
                 .reduce((n, g) => n + g.querySelectorAll('.okt-compare-preview').length, 0)"""
    )
    assert out == 0, f"{out} preview(s) appeared in a grid that did not opt in"


def test_the_page_does_not_scroll_sideways_at_phone_width(page, site_url):
    """The clones are laid out at their natural width and scaled down.
    A fit that failed would push a 740px bar chart into a 316px card."""
    page.set_viewport_size({"width": 360, "height": 760})
    page.goto(f"{site_url}{CHARTS}")
    _wait(page)
    out = page.evaluate("() => ({doc: document.documentElement.scrollWidth, win: window.innerWidth})")
    assert out["doc"] <= out["win"] + 1, out


def test_a_preview_is_not_reachable_by_keyboard(charts):
    """aria-hidden AND focusable is worse than either alone: the keyboard
    lands on something the screen reader has been told is not there. The
    source figures are interactive — a scatter-matrix gives every cell
    `tabindex="0"` — and the clone inherited all of it. `pointer-events:
    none` covers the mouse and nothing else."""
    out = charts.evaluate(
        """() => [...document.querySelectorAll('.okt-compare-preview [tabindex], '
                 + '.okt-compare-preview[tabindex]')]
                 .map(e => e.tagName + '.' + (e.getAttribute('class') || ''))"""
    )
    assert out == [], f"{len(out)} focusable node(s) inside an aria-hidden preview: {out[:6]}"


def test_a_preview_shell_never_answers_for_a_real_chart(charts):
    """The clone is re-parented into an <oku-chart> so the chart's own
    rules apply — and the shells sit ABOVE the worked examples in
    document order. Carrying `type` on them made `oku-chart[type="line"]`
    resolve to a decoration: the hover landed on a preview, the toolbar
    never opened, and the fullscreen click timed out. No rule keys on
    `oku-chart[type=…]`, so the attribute bought nothing."""
    out = charts.evaluate(
        """() => {
          const shells = [...document.querySelectorAll('oku-chart[data-oku-preview-shell]')];
          const typed = shells.filter(s => s.hasAttribute('type'));
          // What a caller selecting by type actually gets back.
          const first = document.querySelector('oku-chart[type="line"]');
          return {
            shells: shells.length,
            typedShells: typed.length,
            firstLineIsAPreview: !!(first && first.closest('.okt-compare-preview')),
            unmarked: [...document.querySelectorAll('.okt-compare-preview oku-chart')]
                        .filter(s => !s.hasAttribute('data-oku-preview-shell')).length,
          };
        }"""
    )
    assert out["shells"] > 0, "no preview shell found — the test is not exercising anything"
    assert out["typedShells"] == 0, f"{out['typedShells']} shell(s) still carry `type`"
    assert out["unmarked"] == 0, f"{out['unmarked']} shell(s) are not marked as previews"
    assert not out["firstLineIsAPreview"], (
        "oku-chart[type='line'] resolves to a preview clone rather than the real chart"
    )
