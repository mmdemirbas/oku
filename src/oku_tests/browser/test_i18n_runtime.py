"""On a translated page the kit's own furniture is translated too.

A reader who switched to Turkish used to get Turkish prose inside English
chrome: the Contents button, the search tooltip, the copy buttons, the
site tree, the "Last updated" line on the cover. The strings are keyed by
the English string, so a missing entry degrades to English rather than
breaking — which is safe and invisible, and invisible is why this is
asserted rather than eyeballed.
"""

from __future__ import annotations

import pytest

PROBE = """() => {
  const attr = (s, a) => { const e = document.querySelector(s); return e ? e.getAttribute(a) : null; };
  const text = (s) => { const e = document.querySelector(s); return e ? e.textContent.trim() : null; };
  return {
    lang: document.documentElement.getAttribute('data-lang'),
    contents: attr('.ctrl-btn.drawer-toggle', 'aria-label'),
    search: attr('.ctrl-btn.search-toggle', 'aria-label'),
    theme: attr('.ctrl-btn.theme-toggle', 'aria-label'),
    width: attr('.ctrl-btn.width-toggle', 'aria-label'),
    copy: attr('.copy-btn', 'aria-label'),
    updated: text('.meta-updated'),
    treeTitles: [...document.querySelectorAll('page-nav .page-nav-tree a')]
                  .slice(0, 4).map(a => a.textContent.trim()),
    treeHrefs: [...document.querySelectorAll('page-nav .page-nav-tree a')]
                  .slice(0, 4).map(a => a.getAttribute('href')),
  };
}"""


def _open(page, site_url, name):
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{site_url}/docs/{name}")
    page.wait_for_selector("main section")
    page.wait_for_function("() => document.querySelector('.ctrl-btn.drawer-toggle') !== null", timeout=8000)
    # The table is fetched, so the pass that applies it runs a turn later.
    page.wait_for_timeout(2200)
    return page.evaluate(PROBE)


def test_an_english_page_stays_english(page, site_url):
    """The fallback path: no entry means the English string, and an
    English page must not be touched by the mechanism at all."""
    got = _open(page, site_url, "reference.html")

    assert got["contents"] == "Contents", got
    assert got["copy"] == "Copy code to clipboard", got
    assert got["updated"].startswith("Last updated"), got


def test_a_turkish_page_gets_turkish_chrome(page, site_url):
    got = _open(page, site_url, "reference.tr.html")

    assert got["lang"] == "tr", got
    assert got["contents"] == "İçindekiler", got
    assert got["search"].startswith("Ara"), got
    assert got["theme"].startswith("Temayı"), got
    assert got["copy"] == "Kodu panoya kopyala", got


def test_a_composed_string_is_rebuilt_not_left_half_translated(page, site_url):
    """`Last updated 2026-08-07` is assembled from a template and a date,
    so it is not a table key and exact matching can never see it. The
    element carries its template for the pass to rebuild."""
    got = _open(page, site_url, "reference.tr.html")

    assert got["updated"].startswith("Son güncelleme"), got
    assert got["updated"].split()[-1].count("-") == 2, got  # the date survived
    assert got["width"].startswith("İçerik genişliği"), got


def test_the_site_tree_follows_the_page_language(page, site_url):
    """A translation is not a second row in the tree, so the row itself
    has to carry the counterpart — otherwise the drawer on a Turkish page
    lists English titles linking to English pages and the reader falls
    back out of the language on the first click."""
    en = _open(page, site_url, "reference.html")
    tr = _open(page, site_url, "reference.tr.html")

    assert "Reference" in en["treeTitles"], en["treeTitles"]
    assert "Başvuru" in tr["treeTitles"], tr["treeTitles"]
    assert all(".tr.html" not in h for h in en["treeHrefs"]), en["treeHrefs"]
    assert any(".tr.html" in h for h in tr["treeHrefs"]), tr["treeHrefs"]


@pytest.mark.parametrize("name", ["reference.html", "reference.tr.html"])
def test_the_pass_never_touches_the_document_body(page, site_url, name):
    """The mechanism replaces exact matches inside kit-owned elements.
    Author prose lives in <main> outside those scopes and must come
    through untouched in either language."""
    _open(page, site_url, name)
    leaked = page.evaluate(
        """() => {
             const h1 = document.querySelector('main h1');
             const p = document.querySelector('main section p');
             return { h1: h1 && h1.textContent.trim(), p: p && p.textContent.trim().slice(0, 40) };
           }"""
    )

    assert leaked["h1"], leaked
    assert leaked["p"], leaked


def test_an_english_page_asks_for_no_translation_table(page, site_url):
    """The kit's strings ARE English — the table keys are English
    sentences — so `en` has no table and never will. Asking for one 404s
    on every English page of a bilingual site, in the console a reader
    opens when something else has gone wrong. A language that declares
    itself and ships no table still 404s, and should: that one is a
    missing translation and worth saying out loud."""
    # `data-lang` has to be on <html> BEFORE chrome.js runs, which is the
    # condition a built site is in and `oku serve` is not: served pages
    # learn their language from the manifest, by which time load() has
    # already memoised an empty result and never asks for anything. The
    # 404 was observed in dist/site, so the test reproduces dist/site.
    page.add_init_script(
        "(() => { const set = () => document.documentElement "
        "&& document.documentElement.setAttribute('data-lang', 'en');"
        "if (!set()) new MutationObserver((_, o) => { if (set()) o.disconnect(); })"
        ".observe(document, {childList: true, subtree: true}); })()"
    )
    asked = []
    page.on("request", lambda r: asked.append(r.url) if "/i18n/" in r.url else None)
    failed = []
    page.on(
        "response",
        lambda r: failed.append((r.url, r.status)) if "/i18n/" in r.url and r.status >= 400 else None,
    )
    _open(page, site_url, "charts.html")
    assert page.evaluate("() => document.documentElement.getAttribute('data-lang')") == "en"

    assert [u for u in asked if u.endswith("/en.json")] == [], (
        f"the English page fetched a table for its own language: {asked}"
    )
    assert failed == [], f"a translation table 404'd: {failed}"


RAIL = """() => {
  const marks = [...document.querySelectorAll('.okt-rail-mark')];
  return {
    count: marks.length,
    labels: marks.map(m => m.getAttribute('aria-label')),
    kinds: [...new Set(marks.map(m => m._okuMark && m._okuMark.tipKind))],
  };
}"""


def _rail(page, site_url, name):
    _open(page, site_url, name)
    # The rail places its marks off measured geometry, so it needs a laid
    # out page — and the marks are rebuilt when the table lands.
    page.wait_for_function("() => document.querySelectorAll('.okt-rail-mark').length > 3", timeout=8000)
    page.wait_for_timeout(400)
    return page.evaluate(RAIL)


def test_the_rail_names_its_landmarks_in_the_page_language(page, site_url):
    """Every mark carries `Jump to <kind> in <label>`, and the kind was
    interpolated raw — so a Turkish page read `Jump to Chart in …` with
    the sentence around it translated and the noun inside it not."""
    tr = _rail(page, site_url, "reference.tr.html")

    assert tr["count"] > 3, tr
    assert all(lbl and lbl.endswith("ögesine git") for lbl in tr["labels"]), tr["labels"]
    assert "Bölüm" in tr["kinds"], tr["kinds"]
    # The English nouns are gone from the rail entirely, not merely
    # outnumbered: `Section`, `Chart`, `Table` are what a reader saw.
    assert not ({"Section", "Chart", "Table", "Title"} & set(tr["kinds"])), tr["kinds"]


def test_the_rail_stays_english_where_it_should(page, site_url):
    en = _rail(page, site_url, "reference.html")

    assert "Section" in en["kinds"], en["kinds"]
    assert all(lbl and lbl.startswith("Jump to ") for lbl in en["labels"]), en["labels"]


def test_a_rail_word_in_author_content_survives_the_pass(page, site_url):
    """The walk descends into every descendant of an `.okt-*` host, and
    author content lives there — a table cell, a heading, a label inside
    a diagram. So a rail word as a plain table key would rewrite the
    author's text: measured, `Charts` alone matches 18 places in this
    repo's docs. The `rail:` prefix is what makes that impossible, and
    this is the assertion that it holds.

    The probes are injected and the pass run by hand, because the real
    pass has already finished by the time a test can reach the page."""
    _open(page, site_url, "reference.tr.html")
    got = page.evaluate(
        """() => {
             const host = document.querySelector('.okt-table-wrap') ||
                          document.querySelector('[class^="okt-"]');
             const words = ['Charts', 'Chart', 'Table', 'Section', 'Figure', 'Example'];
             const made = words.map(w => {
               const el = document.createElement('span');
               el.textContent = w;
               host.appendChild(el);
               return el;
             });
             window.__okuI18n.localize(document);
             const after = made.map(el => el.textContent);
             made.forEach(el => el.remove());
             return { before: words, after: after,
                      hasTable: !!window.__okuI18n.table() };
           }"""
    )

    # Without a loaded table the pass is a no-op and would pass for the
    # wrong reason. The one thing this test must not do is agree quietly.
    assert got["hasTable"], "no tr table was loaded, so the pass did nothing"
    assert got["after"] == got["before"], got
