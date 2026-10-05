"""A served page asks for the central registry files the kit ships, and
for no other.

The loader fetched `_oku/glossary/<d>.json` AND `_oku/extrefs/<d>.json`
for every domain `kit.json` activates. A domain a project defines only in
its own kit.json has no central file, and four of the central domains
have a glossary and no ext-refs file, so each was a 404 on every page
load — in the reader's console, and as `could not load drone.json` from
`oku verify`, which fails the build. Found in dist/site of a delivered
project (dronosfer) whose whole glossary lives in its kit.json.

The lookup itself was never wrong: a 404 resolved to nothing and the local
entries were merged on top. The defect is the request.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

KIT_JSON = {
    "name": "requests",
    "domains": ["local-only", "adhd", "web"],
    "glossary": {"local-only": {"Drone": {"en": {"def": "local drone"}}}},
}

PAGE = """---
title: Requests
summary: Which registry files a page asks for.
---

## One {#one}

A [Drone](#g/Drone) term.
"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("requests").resolve() / "docs"
    d.mkdir()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps(KIT_JSON), encoding="utf-8")
    (d / "page.md").write_text(PAGE, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("Requests"), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


@pytest.fixture(scope="module")
def seen(browser, served):
    pg = browser.new_page()
    asked: dict[str, int] = {}
    pg.on(
        "response",
        lambda r: (
            asked.__setitem__(r.url.split("/_oku/", 1)[1], r.status)
            if "/_oku/glossary/" in r.url or "/_oku/extrefs/" in r.url
            else None
        ),
    )
    pg.goto(served)
    pg.wait_for_function("() => window.__okuRendered === true", timeout=20000)
    found = pg.evaluate(
        "() => __okuKit.whenReady().then(() => "
        "document.querySelector('glossary-term').getAttribute('data-def'))"
    )
    pg.close()
    return asked, found


def test_no_registry_request_misses(seen) -> None:
    asked, _ = seen
    # The listener has to have heard something, or this passes on silence.
    assert "glossary/adhd.json" in asked and "glossary/web.json" in asked, asked
    missed = {u: s for u, s in asked.items() if s != 200}
    assert missed == {}, missed


def test_a_local_only_domain_still_resolves(seen) -> None:
    _, found = seen
    assert found == "local drone"


def _shipped(kind: str) -> list[str]:
    return sorted(p.stem for p in (KIT / kind).glob("*.json"))


@pytest.mark.parametrize("kind", ["glossary", "extrefs"])
def test_the_list_the_runtime_reads_is_the_directory(kind: str) -> None:
    src = (KIT / "chrome.js").read_text(encoding="utf-8")
    start = src.index("var OKU_CENTRAL_REGISTRIES")
    block = src[start : src.index("};", start)]
    line = next(ln for ln in block.splitlines() if ln.strip().startswith(kind + ":"))
    listed = sorted(json.loads(line.split(":", 1)[1].strip().rstrip(",").replace("'", '"')))
    assert listed == _shipped(kind)
