"""On a translated page the kit's own furniture is translated too.

A reader who switched to Turkish used to get Turkish prose inside English
chrome: the Contents button, the search tooltip, the copy buttons, the
site tree, the "Last updated" line on the cover. The strings are keyed by
the English string, so a missing entry degrades to English rather than
breaking — which is safe and invisible, and invisible is why this is
asserted rather than eyeballed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._menu import open_menu
from ._wait import measured

PROBE = """() => {
  const attr = (s, a) => { const e = document.querySelector(s); return e ? e.getAttribute(a) : null; };
  const text = (s) => { const e = document.querySelector(s); return e ? e.textContent.trim() : null; };
  return {
    lang: document.documentElement.getAttribute('data-lang'),
    contents: attr('.ctrl-btn.drawer-toggle', 'aria-label'),
    search: attr('.ctrl-btn.search-toggle', 'aria-label'),
    menu: attr('.ctrl-btn.menu-toggle', 'aria-label'),
    // The two that moved into the panel. Read as row LABELS rather than
    // as button aria-labels: in the corner the whole control was one
    // button and its name had to carry the state; in a row the name is
    // the name and the state is which segment is pressed.
    theme: text('.okt-chrome-menu [data-row="theme"] .okt-menu-label'),
    width: text('.okt-chrome-menu [data-row="width"] .okt-menu-label'),
    textSize: text('.okt-chrome-menu [data-row="text-scale"] .okt-menu-label'),
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
    # The table is FETCHED, so the pass that applies it runs a turn
    # later. It cannot be waited for by looking for a translated string:
    # half these cases are English pages, where there is no table, no
    # fetch and nothing to change — and the other half assert on exactly
    # the strings a wait like that would have to read first.
    #
    # `load()` is the promise the kit's own localize callback is chained
    # to, and Playwright awaits a promise an `evaluate` returns, so this
    # resolves after that callback rather than after a guessed 2200 ms.
    page.evaluate("() => window.__okuI18n.load()")
    # The presentation menu builds its rows on first open, and each word
    # in them goes through okuT at that moment — so its strings do not
    # exist to be read until the panel has been opened once.
    open_menu(page)
    # Several passes localize: boot, the menu build, and the manifest
    # arriving. The probe settling is the one condition that covers all
    # of them without naming any.
    return measured(page, PROBE)


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
    assert got["copy"] == "Kodu panoya kopyala", got
    # The presentation menu's own vocabulary. These are `menu:`-prefixed
    # keys rather than bare words, because `Theme` and `Language` are
    # words an author writes and a bare key is matched against author
    # content — the same hazard the rail's words have.
    assert got["theme"] == "Tema", got
    assert got["width"] == "Sütun genişliği", got
    assert got["textSize"] == "Yazı boyutu", got


def test_a_composed_string_is_rebuilt_not_left_half_translated(page, site_url):
    """`Last updated 2026-08-07` is assembled from a template and a date,
    so it is not a table key and exact matching can never see it. The
    element carries its template for the pass to rebuild."""
    got = _open(page, site_url, "reference.tr.html")

    assert got["updated"].startswith("Son güncelleme"), got
    assert got["updated"].split()[-1].count("-") == 2, got  # the date survived


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
    # More than three marks is the rail having started, not finished —
    # it rebuilds them when the table lands, so what is waited for is
    # the set holding still.
    return measured(page, RAIL)


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


# ---------- the DOM, not the table ----------

# Every key with a translation that differs from the key. An identity
# entry (`TL;DR` → `TL;DR`) is a word the kit keeps in every language,
# and it cannot be told apart from an untranslated one by reading the
# page.
_TABLE = json.loads(
    (Path(__file__).resolve().parents[3] / "kit" / "i18n" / "tr.json").read_text(encoding="utf-8")
)
_KEYS = sorted(k for k, v in _TABLE.items() if v != k and "{0}" not in k)

SURVIVORS = """(keys) => {
  const set = new Set(keys); const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let el;
  while ((el = walker.nextNode())) {
    // Quoted content and code are the author's words, whatever they say.
    if (el.closest('[data-oku-verbatim], pre, code, script, style')) continue;
    const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join('');
    const cls = typeof el.className === 'string' ? el.className.split(' ')[0] : '';
    if (set.has(own)) out.push(`${el.tagName.toLowerCase()}.${cls} text=${JSON.stringify(own)}`);
    for (const a of ['aria-label', 'title', 'placeholder']) {
      const v = el.getAttribute(a);
      if (v && set.has(v)) out.push(`${el.tagName.toLowerCase()}.${cls} ${a}=${JSON.stringify(v)}`);
    }
  }
  return out;
}"""


@pytest.mark.parametrize("name", ["reference.tr.html", "charts.tr.html", "cli.tr.html"])
def test_no_table_key_survives_in_english_on_a_turkish_page(page, site_url, name):
    """`test_i18n_coverage.py` holds the TABLE: every string the kit
    composes has a Turkish entry. This holds the DOM: every one of those
    entries was applied. The two can disagree, and did — an element
    built under a class outside the kit's prefixes is outside the
    localize walk, and its words sit in the table, translated, unused.
    Measured before the fix on this repo's own reference page: 84
    example-column labels reading `Code` / `Output`, and a playground
    whose every control was English, on a page that had fetched the
    Turkish table.

    A sweep over the kit's own documentation rather than a fixture,
    because the documentation is the one page that uses every primitive
    — a fixture would cover the primitives somebody remembered."""
    got = _open(page, site_url, name)
    assert got["lang"] == "tr", got
    # Vacuity guard: the pass has to have RUN for an empty survivor list
    # to mean anything. The drawer button is localized at boot.
    assert got["contents"] == _TABLE["Contents"], got
    survivors = page.evaluate(SURVIVORS, _KEYS)
    assert survivors == [], "\n".join(survivors[:40])
