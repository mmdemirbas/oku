"""The image is on the page the reader opens, in both delivered trees.

`naturalWidth === 0` is what a broken `<img>` reports, and it is the
only signal there is: the page 200s, the layout holds, the alt text sits
where the figure should be, and a reader who has not seen the original
has no reason to think anything is missing. That is how a page carrying
a screenshot was built, opened and delivered before anyone noticed the
figure was blank.

The file-existence half is covered by `test_build_carries_assets.py`.
This is the half that matters: a decoded image, in the artifact, at the
size it was authored.
"""

from __future__ import annotations

from ._wait import page_quiet

import argparse
import base64
import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

# 8x8 red PNG — the dimensions are the assertion, so they must be real.
PNG_8 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4"
    "AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII="
)

PAGE_MD = """---
title: Figure
summary: A page whose figure sits beside it.
---

## Markdown image {#md}

![tiny](art/tiny.png)

## Island image {#island}

<figure class="okt-card">
<img id="in-island" src="art/tiny.png" alt="in an island">
</figure>
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("figure") / "docs"
    (docs / "art").mkdir(parents=True)
    (docs / "art" / "tiny.png").write_bytes(PNG_8)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Figure"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist"


@pytest.fixture(scope="module")
def site_server(built):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(built / "site"))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


MEASURE = """() => [...document.querySelectorAll('main img')].map(i => ({
  src: i.getAttribute('src').slice(0, 24),
  w: i.naturalWidth,
  h: i.naturalHeight,
}))"""


def _open(page, url):
    missing = []
    page.on("response", lambda r: missing.append(r.url) if r.status == 404 else None)
    page.goto(url, wait_until="load")
    page_quiet(page)
    return page.evaluate(MEASURE), missing


def test_the_standalone_page_shows_its_figure(page, built):
    """Over file://, where nothing beside the page can be fetched."""
    imgs, _ = _open(page, (built / "standalone" / "page.html").as_uri())
    assert len(imgs) == 2, imgs
    assert all(i["w"] == 8 and i["h"] == 8 for i in imgs), imgs
    assert all(i["src"].startswith("data:image/png") for i in imgs), imgs


def test_the_site_page_shows_its_figure(page, site_server):
    """Over HTTP, where the file has to be at the path the href names."""
    imgs, missing = _open(page, f"{site_server}/page.html")
    assert len(imgs) == 2, imgs
    assert all(i["w"] == 8 and i["h"] == 8 for i in imgs), imgs
    assert [u for u in missing if u.endswith(".png")] == [], missing
