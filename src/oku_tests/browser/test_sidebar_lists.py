"""The sidebar's two lists each keep their room, say which file a row is, and filter as you type.

Asked for by a reader, in three parts:

  - The site tree and the page's contents shared one scroll region, so
    a long tree pushed the contents out of sight. Measured on a delivered
    research page: the contents began at y=1993 in a 900px window. Each
    list scrolls on its own now, and the contents claim height first.
  - Rows showed titles only, and near-same titles could not be told
    apart. Each row carries its file's name under the title.
  - Neither list could be searched. One filter narrows both as you type:
    folded for case and accents (Turkish dotted and dotless i included),
    fuzzy only when compact, matched letters marked, counts shown.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser


def _page(title: str, sections: list[str], lang: str = "", order: int | None = None) -> str:
    fm = f"---\ntitle: {title}\nsummary: {title}.\n" + (f"lang: {lang}\n" if lang else "")
    fm += (f"order: {order}\n" if order is not None else "") + "---\n\n"
    body = ""
    for i, s in enumerate(sections):
        body += f"## {s} {{#s{i}}}\n\n" + f"Paragraph for {s}.\n\n" * 4
        body += f"### {s} details {{#s{i}-d}}\n\nMore.\n\n"
    return fm + body


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("sidebar") / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "a").mkdir()
    (docs / "b").mkdir()
    pages = {}
    for i in range(50):
        pages[f"notes/note-{i:02d}"] = _page(f"Note {i:02d}", ["One"], order=i)
    # Two pages with the same title; only the file tells them apart.
    pages["a/plan"] = _page("Plan", ["One"], order=60)
    pages["b/plan-v2"] = _page("Plan", ["One"], order=61)
    sections = [f"Bölüm {i}" for i in range(12)] + ["Türkiye manzarası", "Tüketici rehberi"]
    pages["zz-rehber"] = _page("Işık rehberi", sections, lang="tr", order=999)
    pages["short"] = _page("Short", ["Only one", "And two"], order=0)
    for stem, md in pages.items():
        (docs / f"{stem}.md").write_text(md, encoding="utf-8")
        (docs / f"{stem}.html").write_text(cli._stub_for(stem), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone"


def _open(browser, built, stem="zz-rehber", width=1440, height=900):
    context = browser.new_context(viewport={"width": width, "height": height})
    pg = context.new_page()
    pg.goto((built / f"{stem}.html").as_uri(), wait_until="load")
    page_quiet(pg)
    pg.click(".drawer-toggle")
    pg.wait_for_function("() => document.body.classList.contains('drawer-open')")
    pg.wait_for_timeout(350)
    return context, pg


@pytest.fixture()
def page(browser, built):
    context, pg = _open(browser, built)
    yield pg
    context.close()


GEOM = """() => { const nav = document.querySelector('page-nav');
  const r = e => e.getBoundingClientRect();
  const tree = nav.querySelector('.page-nav-panel'), toc = nav.querySelector('page-toc'),
        list = nav.querySelector('.toc-list'), scroll = nav.querySelector('.page-nav-scroll');
  const active = nav.querySelector('.page-nav-tree li.active > a');
  return { tocTop: r(toc).top, firstEntryBottom: r(list.querySelector('a')).bottom, vh: innerHeight,
    treeH: r(tree).height, colH: r(scroll).height, treeScrolls: tree.scrollHeight > tree.clientHeight,
    listScrolls: list.scrollHeight > list.clientHeight,
    activeInTree: r(active).top >= r(tree).top - 1 && r(active).bottom <= r(tree).bottom + 1 }; }"""


def test_the_contents_are_in_view_however_long_the_tree(page):
    """The reported case: 54 documents above a 14-section outline."""
    g = page.evaluate(GEOM)
    assert g["tocTop"] < g["vh"] * 0.45, f"the contents start at y={g['tocTop']:.0f} of {g['vh']}"
    assert g["firstEntryBottom"] < g["vh"], "the first contents entry is below the fold"
    assert g["treeScrolls"], "the fixture's tree should be too long for its share"


def test_each_list_scrolls_on_its_own(page):
    before = page.evaluate(GEOM)["tocTop"]
    moved = page.evaluate(
        "() => { const t = document.querySelector('page-nav .page-nav-panel'); t.scrollTop = 0;"
        " t.scrollTop = 400; return t.scrollTop; }"
    )
    assert moved > 0, "the tree is not a scroller of its own"
    assert page.evaluate(GEOM)["tocTop"] == before, "scrolling the tree moved the contents"


def test_the_page_being_read_is_scrolled_into_the_tree(page):
    """It is last in the fixture's order — below the tree's fold."""
    g = page.evaluate(GEOM)
    assert g["treeScrolls"], "nothing to reveal: the tree fits"
    assert g["activeInTree"]


def test_a_short_outline_leaves_the_tree_the_rest(browser, built):
    context, pg = _open(browser, built, stem="short")
    try:
        g = pg.evaluate(GEOM)
        assert g["treeH"] > g["colH"] * 0.6, g
    finally:
        context.close()


def test_every_row_names_its_file(page):
    rows = page.evaluate(
        """() => [...document.querySelectorAll('page-nav .page-nav-tree a')].map(a => [
          a.querySelector('.page-nav-title').textContent, a.querySelector('.page-nav-file').textContent])"""
    )
    plans = sorted(f for t, f in rows if t == "Plan")
    assert plans == ["plan-v2.md", "plan.md"], plans
    assert ["Işık rehberi", "zz-rehber.md"] in rows


FILTER = """() => { const nav = document.querySelector('page-nav');
  const vis = sel => [...nav.querySelectorAll(sel)].filter(e => e.getClientRects().length);
  return { tree: vis('.page-nav-tree a .page-nav-title').map(e => e.textContent),
    toc: vis('.toc-list a').map(e => e.textContent),
    marks: [...nav.querySelectorAll('mark.okt-hit')].map(m => m.textContent),
    counts: [...nav.querySelectorAll('.page-nav-count')].map(c => c.textContent),
    none: !nav.querySelector('.page-nav-none').hidden }; }"""


def _filter(page, q):
    page.fill(".page-nav-filter-input", q)
    return page.evaluate(FILTER)


def test_the_filter_folds_case_and_turkish_letters(page):
    got = _filter(page, "turkiye")
    # The section and its subsection: both carry the word.
    assert got["toc"] == ["Türkiye manzarası", "Türkiye manzarası details"], got["toc"]
    assert "Türkiye" in got["marks"]
    got = _filter(page, "ISIK")
    assert got["tree"] == ["Işık rehberi"], got["tree"]
    assert got["counts"][0] == "1/54"


def test_a_fuzzy_match_must_be_compact(page):
    assert _filter(page, "tkt")["toc"] == ["Tüketici rehberi", "Tüketici rehberi details"]
    assert _filter(page, "nzz")["toc"] == [], "n, z, z scattered across a title is not a match"


def test_every_word_has_to_match_and_the_file_name_counts(page):
    got = _filter(page, "plan v2")
    assert got["tree"] == ["Plan"], got["tree"]
    assert "v2" in got["marks"]


def test_clearing_puts_every_row_back_as_it_was(page):
    before = page.evaluate(FILTER)
    _filter(page, "manzara")
    after = _filter(page, "")
    assert after["tree"] == before["tree"] and after["toc"] == before["toc"]
    assert after["marks"] == [] and after["counts"] == ["", ""]


def test_no_match_says_so(page):
    got = _filter(page, "qqqzzz")
    assert got["tree"] == [] and got["toc"] == [] and got["none"]


def test_the_keyboard_walks_the_results(page):
    _filter(page, "bölüm 1")
    page.focus(".page-nav-filter-input")
    page.keyboard.press("ArrowDown")
    first = page.evaluate("() => document.activeElement.textContent")
    page.keyboard.press("ArrowDown")
    second = page.evaluate("() => document.activeElement.textContent")
    assert (first, second) == ("Bölüm 1", "Bölüm 1 details"), (first, second)
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")
    assert page.evaluate("() => document.activeElement.classList.contains('page-nav-filter-input')")


def test_enter_follows_the_first_match(page):
    _filter(page, "tüketici")
    page.keyboard.press("Enter")
    page.wait_for_function("() => location.hash === '#s13'")


def test_escape_clears_first_and_closes_second(browser, built):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = context.new_page()
    try:
        pg.goto((built / "zz-rehber.html").as_uri(), wait_until="load")
        page_quiet(pg)
        pg.hover(".drawer-toggle")
        pg.wait_for_function("() => document.body.classList.contains('drawer-peek')")
        pg.fill(".page-nav-filter-input", "bölüm")
        # Typing is reading the panel: the pointer wandering off does not end the peek.
        pg.mouse.move(1000, 500)
        assert pg.evaluate("() => document.body.classList.contains('drawer-peek')")
        pg.keyboard.press("Escape")
        assert pg.input_value(".page-nav-filter-input") == ""
        assert pg.evaluate("() => document.body.classList.contains('drawer-peek')")
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.body.classList.contains('drawer-open')")
    finally:
        context.close()


def test_the_words_are_the_pages_language(page):
    got = page.evaluate(
        """() => ({ ph: document.querySelector('.page-nav-filter-input').placeholder,
                   label: document.querySelector('.page-nav-label span').textContent })"""
    )
    assert got == {"ph": "Süz…", "label": "Belgeler"}, got


def test_at_phone_width_no_corner_button_covers_the_filter(browser, built):
    """At 360px the search and menu buttons stand over the panel's top
    row; measured before, the search button sat on the filter."""
    context, pg = _open(browser, built, width=360, height=740)
    try:
        hits = pg.evaluate(
            """() => { const f = document.querySelector('.page-nav-filter-input').getBoundingClientRect();
              return [...document.querySelectorAll('.ctrl-btn')].filter(b => b.getClientRects().length)
                .filter(b => { const r = b.getBoundingClientRect();
                  return r.left < f.right && r.right > f.left && r.top < f.bottom && r.bottom > f.top; })
                .map(b => b.className); }"""
        )
        assert hits == [], hits
        g = pg.evaluate(GEOM)
        assert g["firstEntryBottom"] < g["vh"]
    finally:
        context.close()


def test_each_render_replaces_the_scroll_spy_rather_than_adding_one(browser, built):
    """buildTOC runs on every render, and every run added a window
    `scroll` listener that nothing removed: a reader moving between
    pages carried one scroll-spy per visit, each reading headings on
    every scroll frame. Counted here as live scroll listeners on
    `window` -- those registered without a signal, or with one that has
    not been aborted."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    context.add_init_script(
        """(() => {
          const live = window.__okuScrollListeners = [];
          const add = EventTarget.prototype.addEventListener;
          EventTarget.prototype.addEventListener = function (type, fn, opts) {
            if (this === window && type === 'scroll') live.push((opts && opts.signal) || null);
            return add.call(this, type, fn, opts);
          };
        })()"""
    )
    pg = context.new_page()
    pg.goto((built / "zz-rehber.html").as_uri(), wait_until="load")
    page_quiet(pg)
    count = "() => window.__okuScrollListeners.filter(s => !s || !s.aborted).length"
    before = pg.evaluate(count)
    for _ in range(4):
        pg.evaluate("() => window.dispatchEvent(new Event('oku:rendered'))")
    pg.wait_for_timeout(150)
    after = pg.evaluate(count)
    context.close()
    assert after == before, (before, after)
