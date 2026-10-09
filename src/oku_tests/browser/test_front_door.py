"""A tree's front door speaks the tree's language, and every page leads back to it.

The front door is the `index.html` `oku init` writes; with no index.md
behind it the runtime draws the tree's pages there. Measured on a
delivered Turkish tree before this: `<html lang="en">`, a title reading
`Documentation` (the shell's own `<title>`) over a list headed `Pages`,
and — from any page of the tree — no link back to it at all, since the
site tree lists pages and the front door is not one.

Three delivery modes, because each reaches the front door differently:
`oku serve` hands over the shell as it is on disk (here one written with
`lang="en"`, as every shell before this was), `dist/site` and
`dist/standalone` hand over the build's copy. The served mode is the one
that found the table bug: the site tree asked for the string table
before the front door said its language, and the answer was kept for
the life of the page.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

PAGE = """---
title: {title}
order: {order}
summary: {title} için notlar.
---

## Gövde {{#govde}}

{title} sayfasının metni.
"""


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> Path:
    docs = tmp_path_factory.mktemp("frontdoor") / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text(
        json.dumps(
            {
                "languages": [{"code": "tr", "label": "Türkçe"}, {"code": "en", "label": "English"}],
                "defaultLanguage": "tr",
                "description": "Görüşme hazırlıkları.",
            }
        ),
        encoding="utf-8",
    )
    for i, name in enumerate(("bir", "iki"), start=1):
        (docs / f"{name}.md").write_text(PAGE.format(title=name.title(), order=i * 10), encoding="utf-8")
    # The shell as every tree had it: English, and a manifest of the day
    # it was written.
    stale = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "bir.html", "source": "bir.md", "title": "Bir"}],
    }
    (docs / "index.html").write_text(cli._stub_for("Documentation", inline_manifest=stale), encoding="utf-8")
    assert '<html lang="en">' in (docs / "index.html").read_text(encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs


def _serve(handler) -> tuple[http.server.ThreadingHTTPServer, str]:
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


@pytest.fixture(scope="module", params=["served", "site", "standalone"])
def base(request, tree):
    if request.param == "standalone":
        yield (tree / "dist" / "standalone").as_uri()
        return
    if request.param == "served":
        handler = cli._make_serve_handler(tree)
    else:
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(tree / "dist" / "site")
        )
    httpd, url = _serve(handler)
    yield url
    httpd.shutdown()


def _open(page, url: str) -> list[str]:
    missing: list[str] = []
    page.on("response", lambda r: missing.append(r.url) if r.status == 404 else None)
    page.goto(url, wait_until="load")
    page_quiet(page)
    return missing


def _door(page) -> dict:
    return page.evaluate(
        """() => {
          const home = document.querySelector('page-nav .page-nav-home');
          return {
            lang: document.documentElement.lang,
            title: (document.querySelector('main h1') || {}).textContent || '',
            main: document.querySelector('main').innerText,
            links: [...document.querySelectorAll('main li a')].map(a => a.getAttribute('href')),
            home: home && {
              path: new URL(home.href).pathname.split('/').pop(),
              current: home.getAttribute('aria-current'),
              text: home.textContent.trim(),
              title: home.title,
            },
          };
        }"""
    )


def test_the_front_door_is_in_the_trees_language(page, base):
    missing = _open(page, f"{base}/index.html")
    door = _door(page)
    assert door["lang"] == "tr"
    assert door["title"].strip() == "Belgeler"
    assert "Görüşme hazırlıkları." in door["main"]
    for english in ("Documentation", "Pages"):
        assert english not in door["main"], f"{english!r} on a Turkish front door: {door['main'][:200]}"
    assert sorted(door["links"]) == ["bir.html", "iki.html"]
    assert [u for u in missing if u.endswith("index.json")] == []


def test_every_page_leads_back_to_the_front_door(page, base):
    _open(page, f"{base}/bir.html")
    home = _door(page)["home"]
    assert home == {"path": "index.html", "current": None, "text": "Belgeler", "title": "Giriş sayfası"}


def test_the_way_back_arrives_at_the_front_door(page, base):
    missing = _open(page, f"{base}/bir.html")
    # The drawer is closed at rest; the click is the reader's, wherever
    # they open it from.
    page.eval_on_selector("page-nav .page-nav-home", "a => a.click()")
    page.wait_for_function("() => (document.querySelector('main h1') || {}).textContent === 'Belgeler'")
    page_quiet(page)
    door = _door(page)
    assert sorted(door["links"]) == ["bir.html", "iki.html"]
    assert door["home"]["current"] == "page"
    assert [u for u in missing if u.endswith("index.json")] == [], missing


def test_a_named_tree_opens_under_its_name(page, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text(json.dumps({"name": "Mülakat notları"}), encoding="utf-8")
    (docs / "bir.md").write_text(PAGE.format(title="Bir", order=1), encoding="utf-8")
    (docs / "iki.md").write_text(PAGE.format(title="Iki", order=2), encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("Documentation"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    _open(page, (docs / "dist" / "standalone" / "index.html").as_uri())
    door = _door(page)
    assert door["title"].strip() == "Mülakat notları"
    assert page.title() == "Mülakat notları"
