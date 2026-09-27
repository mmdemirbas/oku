"""A code block gets the grammar it names, or the kit says nothing at all.

Measured before this existed, on a built page opened over file://: a
```hcl fence produced `prism-hcl.min.js :: net::ERR_FILE_NOT_FOUND`, the
block rendered with 0 tokens, and the only place anything said so was
the reader's console. `oku check` passed. The baseline list of vendored
grammars is hand-written, so it holds the languages somebody thought of;
what an author writes is open.

Two halves, and they are separate because they fix different failures.
The build reads the tree and fetches the grammars it uses, so hcl
highlights. And the loader asks only for what the vendor directory says
it carries, so a name that is no grammar at all — ```text, 16 times in
this repo's own docs — costs no request instead of one per fence.

Both delivery modes, because they are two recipes: `build_standalone`
inlines the kit and `build_site` copies it, and only one of them used to
carry the vendored directory at all.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

PAGE_MD = """---
title: Fences
summary: One carried grammar, one the baseline never named, one word.
---

## Blocks {#blocks}

```hcl
resource "aws_s3_bucket" "b" {
  bucket = "my-bucket"
}
```

```text
plain words, no grammar anywhere
```

```rb
puts 1
```

```python
x = 1
```
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("codelang") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Fences"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        # no_vendor stays FALSE on purpose: fetching the grammars this
        # tree uses is the behaviour under test. The baseline is already
        # on disk from the repo's own builds, so this is one small
        # request, and `hcl` survives in the shared cache afterwards.
        assert cli.cmd_build(argparse.Namespace(no_search=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist"


def _read(page, url: str):
    """Load a page, recording every request it makes and every one that
    failed. The failures alone are not enough: the point of the refusal
    is that the request is never made, and a test that only counts
    failures would pass on a kit that asks and quietly swallows."""
    asked: list[str] = []
    failed: list[str] = []
    page.on("request", lambda r: asked.append(r.url.rsplit("/", 1)[-1]))
    page.on("requestfailed", lambda r: failed.append(r.url.rsplit("/", 1)[-1]))
    page.goto(url, wait_until="load")
    page_quiet(page)
    tokens = page.evaluate(
        "() => Object.fromEntries([...document.querySelectorAll('pre code')].map((c) => ["
        "  (c.className.match(/language-([\\w-]+)/) || [0, '?'])[1],"
        "  c.querySelectorAll('.token').length]))"
    )
    return tokens, asked, failed


@pytest.fixture(params=["standalone", "site"])
def opened(request, built, browser):
    """Both trees, over the transport each is delivered on — file:// for
    the self-contained file, HTTP for the shared-assets site, whose
    pages fetch."""
    tree = built / request.param
    context = browser.new_context()
    page = context.new_page()
    if request.param == "standalone":
        yield page, (tree / "page.html").as_uri()
    else:
        import http.server
        import threading

        handler = type(
            "H",
            (http.server.SimpleHTTPRequestHandler,),
            {
                "__init__": lambda s, *a, **k: http.server.SimpleHTTPRequestHandler.__init__(
                    s, *a, directory=str(tree), **k
                ),
                "log_message": lambda *a: None,
            },
        )
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield page, f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
        finally:
            httpd.shutdown()
    context.close()


def test_a_grammar_the_baseline_never_named_still_highlights(opened):
    page, url = opened
    tokens, _asked, failed = _read(page, url)
    assert tokens.get("hcl", 0) > 0, "the hcl block has no syntax tokens"
    assert [f for f in failed if "prism-" in f] == []


def test_the_kit_does_not_ask_for_a_grammar_that_does_not_exist(opened):
    page, url = opened
    tokens, asked, _failed = _read(page, url)
    assert [a for a in asked if a.startswith("prism-text")] == [], (
        "the page asked for a component for ```text, which is not a Prism grammar"
    )
    assert tokens.get("text") == 0, "a block with no grammar renders as plain text"


def test_an_alias_still_reaches_its_grammar(opened):
    """The refusal resolves aliases the way the autoloader does. Reading
    the carried ids alone would refuse ```rb — ruby is carried, `rb` is
    not an id — and silently stop highlighting a block that worked."""
    page, url = opened
    tokens, _asked, _failed = _read(page, url)
    assert tokens.get("rb", 0) > 0
    assert tokens.get("python", 0) > 0


def test_the_page_says_which_grammars_it_can_serve(opened):
    page, url = opened
    _read(page, url)
    carried = page.evaluate("() => window.__okuPrismCarried")
    assert carried and "hcl" in carried["ids"], "the vendored directory does not declare hcl"
    # The declaration is the directory's, so the twelve grammars inside
    # prism.min.js are in it too — nothing fetches those and the loader
    # must not refuse them.
    assert {"javascript", "css", "markup", "js"} <= set(carried["ids"])
    assert carried["aliases"].get("rb") == "ruby"
