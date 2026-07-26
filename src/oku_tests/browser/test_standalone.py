"""Numeric invariants for the standalone single-file build.

The standalone tree is the "send it as a file" surface — it has no
site-manifest, so `page-nav` takes a different boot path than the
served site. Two regressions lived on that path and neither was
visible to the Python tests: the page data terminated the inlined
chrome.js early, and the sidebar element hid itself while still
owning the layout's first grid track.
"""

from __future__ import annotations

import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

DESKTOP = {"width": 1280, "height": 900}
NARROW = {"width": 360, "height": 800}

_PAGE = {
    "k": "page",
    "t": "Standalone probe",
    "m": {"summary": "Fixture page for the standalone invariants."},
    "b": [
        "## Birinci bölüm {#bir}\n\nGövde metni.",
        "## İkinci bölüm {#iki}\n\nGövde metni.",
        "## Üçüncü bölüm {#uc}\n\nGövde metni.",
    ],
}


@pytest.fixture(scope="session")
def standalone_url(tmp_path_factory):
    """A built dist/standalone/ tree served over HTTP.

    HTTP rather than file:// so the fixture matches what CI can drive;
    the boot path under test keys off the inline page data, not the
    protocol.
    """
    from oku import cli

    src_root = tmp_path_factory.mktemp("standalone-src")
    out_dir = tmp_path_factory.mktemp("standalone-out")
    stub = (Path(cli.__file__).parent / "templates" / "starter.html").read_text(encoding="utf-8")
    stub = stub.replace("{{ TITLE }}", "Standalone probe")
    page_html = src_root / "probe.html"
    page_html.write_text(stub, encoding="utf-8")
    (src_root / "probe.json").write_text(json.dumps(_PAGE, ensure_ascii=False), encoding="utf-8")

    cli.build_standalone([(page_html, stub, _PAGE)], out_dir, src_root)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/probe.html"
    httpd.shutdown()


def _goto(page, url: str) -> None:
    page.goto(url)
    page.wait_for_selector("main section")


def test_kit_source_does_not_leak_into_the_page(page, standalone_url):
    """chrome.js must stay inside its script element.

    When the page data was injected into chrome.js's layout-skeleton
    comment, the closing tag ended the script and the remaining kit
    source rendered as visible body text.
    """
    page.set_viewport_size(DESKTOP)
    _goto(page, standalone_url)
    text = page.evaluate("() => document.body.innerText")
    assert "ensureLayoutSkeleton" not in text, "kit source is rendering as page text"
    assert "customElements.define" not in text, "kit source is rendering as page text"
    assert page.locator("main > section").count() == 3


def test_main_owns_the_wide_grid_track(page, standalone_url):
    """main must not be squeezed into the sidebar's column.

    page-nav used to set display:none in standalone builds. The grid
    keeps two explicit tracks, so main slid into the 280px sidebar
    track and every line wrapped.
    """
    page.set_viewport_size(DESKTOP)
    _goto(page, standalone_url)
    main = page.locator("main").bounding_box()
    nav = page.locator("page-nav").bounding_box()
    assert main is not None and nav is not None
    assert main["width"] > nav["width"], (
        f"main ({main['width']}) must be wider than the sidebar ({nav['width']})"
    )
    assert main["width"] >= DESKTOP["width"] * 0.5, (
        f"main width {main['width']} collapsed below half the viewport"
    )


def test_sidebar_keeps_the_page_toc_and_drops_the_site_tree(page, standalone_url):
    """Single-left-sidebar rule still holds without a site manifest."""
    page.set_viewport_size(DESKTOP)
    _goto(page, standalone_url)
    page.wait_for_selector("page-nav page-toc .toc-h2")
    assert page.locator("page-nav page-toc .toc-h2").count() == 3
    assert page.locator("page-nav .page-nav-tree").count() == 0, (
        "standalone has no site to navigate — the tree panel must be gone"
    )
    nav = page.locator("page-nav").bounding_box()
    assert nav is not None and abs(nav["height"] - DESKTOP["height"]) <= 1


def test_narrow_viewport_gives_main_the_full_width(page, standalone_url):
    page.set_viewport_size(NARROW)
    _goto(page, standalone_url)
    main = page.locator("main").bounding_box()
    assert main is not None
    assert main["width"] >= NARROW["width"] * 0.8, (
        f"main width {main['width']} too narrow at {NARROW['width']}px"
    )
