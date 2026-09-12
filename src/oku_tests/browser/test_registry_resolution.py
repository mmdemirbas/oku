"""Which registry entry a reference lands on, measured in both delivery
modes.

`docs/glossary.md` makes four claims about resolution and nothing held
any of them: domains are searched in the order `kit.json` lists them
and the first hit wins; the preferred `lang` is tried first, then the
`lang_fallback` chain in order, then whatever language the entry has;
a project's own entries in `kit.json` win over the central registry
file for the same key; and the same rules run for ext-refs. The check
now mirrors that lookup (`test_check.py`, the glossary section), which
makes it worth pinning what the lookup actually does.

Two branches of `load()` in chrome.js do this work — the fetch path
under `oku serve` and `dist/site`, and the inlined bundle a standalone
page carries — and they merge the local entries in separate code. The
personalization defect was a branch that forgot; this reads the result
off both.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# `tr` preferred, then `de`, then `en`. Every term below is built to
# land on a DIFFERENT rung of that ladder, so a lookup that skipped a
# rung — or walked the chain in the wrong order — changes an answer.
KIT_JSON = {
    "name": "resolution",
    "domains": ["data-platforms", "web"],
    "lang": "tr",
    "lang_fallback": ["de", "en"],
    "glossary": {
        "data-platforms": {
            # The central `ACID` carries `en` AND `tr`. A local entry
            # replaces the whole term, so `tr` is gone and the chain
            # has to run — which is what makes this one case say both
            # "local wins" and "the chain runs".
            "ACID": {"en": {"def": "local ACID"}},
            "Chain": {"de": {"def": "de via chain"}, "en": {"def": "en would lose"}},
            "OnlyEn": {"en": {"def": "en via chain"}},
            "OnlyFr": {"fr": {"def": "fr via any"}},
            "Native": {"tr": {"def": "tr direct"}, "en": {"def": "en would lose"}},
            "Shared": {"en": {"def": "data-platforms first"}},
        },
        "web": {"Shared": {"en": {"def": "web second"}}},
    },
    "extrefs": {
        "data-platforms": {
            "Apache Iceberg": {
                "en": {"name": "Apache Iceberg", "summary": "local Iceberg", "link": "https://x.test"}
            },
            "Both": {"en": {"name": "Both", "summary": "data-platforms first", "link": "https://x.test"}},
        },
        "web": {"Both": {"en": {"name": "Both", "summary": "web second", "link": "https://x.test"}}},
    },
}

TERMS = ["ACID", "Chain", "OnlyEn", "OnlyFr", "Native", "Shared"]
REFS = ["Apache Iceberg", "Both"]

PAGE = (
    "---\ntitle: Resolution\nsummary: One reference per rule.\n---\n\n## Terms {#terms}\n\n"
    + " ".join(f"[{t}](#g/{t})" for t in TERMS)
    + "\n\n## Refs {#refs}\n\n"
    + " ".join(f"[{r}](#x/{r})" for r in REFS)
    + "\n"
)

# (def, the language the card says it is showing — None when it is the
# preferred one and the card says nothing).
EXPECTED_TERMS = {
    "ACID": ("local ACID", "en"),
    "Chain": ("de via chain", "de"),
    "OnlyEn": ("en via chain", "en"),
    "OnlyFr": ("fr via any", "fr"),
    "Native": ("tr direct", None),
    "Shared": ("data-platforms first", "en"),
}
EXPECTED_REFS = {
    "Apache Iceberg": "local Iceberg",
    "Both": "data-platforms first",
}


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("resolution").resolve() / "docs"
    d.mkdir()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps(KIT_JSON), encoding="utf-8")
    (d / "page.md").write_text(PAGE, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("Resolution"), encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def served(tree):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(tree))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


@pytest.fixture(scope="module")
def standalone(tree) -> str:
    cwd = Path.cwd()
    os.chdir(tree)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return (tree / "dist" / "standalone" / "page.html").as_uri()


# The resolution result, as the element records it: `data-def` is what
# the card will say, `data-lang-shown` is set only when the language
# shown is not the preferred one. Read after the kit settles rather than
# after a hover — the card is built from these, and reading the source
# of the card is one step closer to the lookup than reading the card.
READ = """() => __okuKit.whenReady().then(() => ({
  terms: Object.fromEntries([...document.querySelectorAll('glossary-term')].map((e) => [
    e.getAttribute('term'),
    [e.getAttribute('data-def'), e.getAttribute('data-lang-shown'), e.classList.contains('unknown')],
  ])),
  // An ext-ref records the whole citation card in `data-def`, so the
  // summary is read out of the card's markup rather than off its own
  // attribute — which is one step FURTHER from the lookup than the
  // glossary read above, and the reason the card is parsed rather than
  // string-searched: a summary that appears in the card's link title
  // as well would match twice.
  refs: Object.fromEntries([...document.querySelectorAll('ext-ref')].map((e) => {
    const card = document.createElement('div');
    card.innerHTML = e.getAttribute('data-def') || '';
    const summary = card.querySelector('.okt-cite-summary');
    return [e.getAttribute('name'), [summary ? summary.textContent.trim() : null, e.classList.contains('unknown')]];
  })),
}))"""


def _read(browser, url: str) -> dict:
    pg = browser.new_page()
    try:
        pg.goto(url, wait_until="load")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        page_quiet(pg)
        return pg.evaluate(READ)
    finally:
        pg.close()


@pytest.fixture(scope="module")
def results(browser, served, standalone) -> dict[str, dict]:
    return {"served": _read(browser, served), "standalone": _read(browser, standalone)}


@pytest.mark.parametrize("mode", ["served", "standalone"])
def test_every_reference_resolved(results, mode):
    """Vacuity guard for the rest: an element the kit never resolved
    carries no `data-def`, and the per-term cases below would then
    compare `None` against an expectation and say the rule is broken
    when the fixture is."""
    got = results[mode]
    assert sorted(got["terms"]) == sorted(TERMS), got
    assert sorted(got["refs"]) == sorted(REFS), got
    assert [t for t, (d, _l, unknown) in got["terms"].items() if not d or unknown] == [], got["terms"]


@pytest.mark.parametrize("mode", ["served", "standalone"])
@pytest.mark.parametrize("term", TERMS)
def test_a_term_lands_where_the_docs_say(results, mode, term):
    definition, lang = EXPECTED_TERMS[term]
    got_def, got_lang, _unknown = results[mode]["terms"][term]
    assert got_def == definition, (term, mode, results[mode]["terms"][term])
    assert got_lang == (f"lang: {lang}" if lang else None), (term, mode, results[mode]["terms"][term])


@pytest.mark.parametrize("mode", ["served", "standalone"])
@pytest.mark.parametrize("ref", REFS)
def test_an_ext_ref_follows_the_same_rules(results, mode, ref):
    got_summary, unknown = results[mode]["refs"][ref]
    assert not unknown, (ref, mode)
    assert got_summary == EXPECTED_REFS[ref], (ref, mode, results[mode]["refs"][ref])


def test_the_two_delivery_modes_agree(results):
    """The claim that matters most, stated as one comparison: whatever
    each branch of the loader does, a reader is handed the same
    definitions whichever file they open."""
    assert results["served"] == results["standalone"]
