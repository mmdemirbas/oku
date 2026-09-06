"""A delivered page never asks for a Prism component that is not there.

Two failed requests were reported, one 404 per page load, on pages that
otherwise render and mostly highlight — so nothing about the build said
anything was wrong:

    net::ERR_FILE_NOT_FOUND .../components/prism-oku-chart.min.js
    net::ERR_FILE_NOT_FOUND .../components/prism-regex.min.js

They have different causes and different fixes, and both come from a
GRAMMAR naming a language out of the document's own content rather than
from anything an author wrote as a language tag:

  - `oku-chart` is one of the KIT's fence names. Prism's markdown
    grammar reads a fence's info string inside a markdown sample and
    calls `autoloader.loadLanguages(thatString)` itself, from a `wrap`
    hook — so a page DOCUMENTING this kit asks for a grammar that can
    never exist. The call goes through the plugin's own property, which
    is where it is now refused. Neither the autoloader's `complete` hook
    nor the kit's nested-language pass is on that path; both were tried
    first, and the stack trace is what settled it.
  - `regex` is a real Prism component that the kit simply did not
    vendor. Prism's JavaScript grammar gives a regex literal's source
    the alias `language-regex`, so any page with a regex in a JS block
    asked for it. It is vendored now, so the request is served.

The asymmetry is deliberate and is the point of the pair: a name that
CAN be served is served, and only a name that never could is refused.
Refusing by prefix is safe because `oku-` can never be a Prism language;
refusing by allow-list would silently stop highlighting every alias
nobody remembered to list.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

from . import _wait

pytestmark = pytest.mark.browser

# One page carrying both triggers: a markdown sample whose inner fence is
# a kit primitive, and a JavaScript block with a regex literal in it.
PAGE_MD = """---
title: Prism triggers
summary: A markdown sample naming a kit fence, and a JS regex literal.
---

## A markdown sample {#sample}

````markdown
## A section

```oku-chart
{"type":"bar","rows":[{"label":"a","value":1}]}
```
````

## A regex literal {#regex}

```javascript
const re = /^[a-z]+\\d{2,4}$/gi;
console.log(re.test("abc123"));
```
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("prismreq") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Prism triggers"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        # Vendored on purpose: the whole question is what the delivered
        # tree carries, and `no_vendor` would answer a different one.
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def traffic(built, browser):
    page = browser.new_page()
    failed: list[str] = []
    served: list[tuple[str, int]] = []
    page.on("requestfailed", lambda r: failed.append(r.url.split("/")[-1]))
    page.on(
        "response",
        lambda r: served.append((r.url.split("/")[-1], r.status)) if "/components/" in r.url else None,
    )
    page.goto(built.as_uri(), wait_until="load")
    # There is no event for "nothing more will be requested", which is
    # why this was a 6 s sleep — the longest in the suite, paid on every
    # run to catch a request that arrives in about 300 ms.
    #
    # Both triggers ARE observable, so the wait is on them and not on a
    # clock. The markdown grammar's `wrap` hook is what asks for a fence
    # name, and it cannot have run before the sample is highlighted; the
    # JavaScript grammar's regex alias is asked for in the same pass.
    # Once both blocks carry tokens, every request this test is about has
    # been made — and then the traffic itself has to stop moving, since
    # the assertion is about a set of requests rather than about the DOM.
    _wait.until(
        page,
        "() => !!document.querySelector('code.language-markdown .token')"
        " && !!document.querySelector('code.language-javascript .token')",
        what="Prism highlighted both the markdown sample and the JS block",
    )
    _wait.settled(lambda: (len(served), len(failed)), what="the component requests stopped arriving")
    yield page, failed, served
    page.close()


def test_no_request_for_a_component_the_page_does_not_carry(traffic):
    """The reported symptom, as a whole-page property rather than as two
    names — a third grammar inventing a third name would land here."""
    _page, failed, _served = traffic
    assert [f for f in failed if "prism-" in f] == [], (
        f"the page asked for Prism components it does not carry: {sorted(set(failed))}"
    )


def test_the_kit_fence_name_is_refused_rather_than_fetched(traffic):
    """Refused, not renamed and not served. A request that 404s and a
    request that is never made look identical in the rendered page and
    completely different in the reader's console, which is the entire
    defect."""
    _page, _failed, served = traffic
    assert [n for n, _ in served if n.startswith("prism-oku-")] == [], served


def test_the_refusal_is_actually_exercised(traffic):
    """A test that asserts an absence has to show the mechanism ran, or
    it degrades into a test of a page with no markdown sample on it.

    The page carries the trigger — a markdown block Prism highlighted,
    holding an `oku-chart` fence — so the grammar had something to name.
    """
    page, _failed, _served = traffic
    got = page.evaluate("""() => ({
      markdownBlocks: document.querySelectorAll('code.language-markdown').length,
      markdownHighlighted: !!document.querySelector('code.language-markdown .token'),
      fenceTextPresent: /oku-chart/.test(document.querySelector('main').textContent),
    })""")
    assert got["markdownBlocks"] >= 1, got
    assert got["markdownHighlighted"], f"Prism never highlighted the sample: {got}"
    assert got["fenceTextPresent"], got


def test_a_real_component_is_served_rather_than_refused(traffic):
    """The other half, and the reason the refusal is by prefix and not by
    allow-list: `regex` is a name a grammar invents too, and it is one
    the kit CAN serve. It is vendored, so the request succeeds."""
    _page, _failed, served = traffic
    regex = [(n, s) for n, s in served if n == "prism-regex.min.js"]
    assert regex, f"the JS regex literal did not trigger the request: {served}"
    assert all(status == 200 for _n, status in regex), regex


def test_regex_is_in_the_vendored_set():
    """Nothing tags a block `regex`, so it would never be added by the
    usual route of 'an author asked for this language'."""
    assert "regex" in cli._PRISM_LANGS, cli._PRISM_LANGS


def test_the_vendored_components_are_all_present(built):
    """The delivered tree carries a file for every language the kit says
    it vendors — the condition the reported 404 was the absence of."""
    comp = built.parent / "_oku" / "vendor" / "prism" / "components"
    missing = sorted(lang for lang in cli._PRISM_LANGS if not (comp / f"prism-{lang}.min.js").exists())
    assert missing == [], f"vendored set names components the build did not carry: {missing}"
    assert json.dumps(sorted(cli._PRISM_LANGS))  # the list is serialisable, ie. plain strings
