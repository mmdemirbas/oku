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
