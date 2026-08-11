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
    # The first section appearing is not the walk finishing. Tests that
    # count sections or watch for stray requests were reading a
    # half-built page and covering it with a fixed sleep, which holds on
    # an idle machine and fails on a loaded one.
    page.wait_for_function("() => window.__okuRendered === true", timeout=15000)


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


def test_no_stray_page_json_fetch(page, standalone_url):
    """The inline page data is the only source; nothing is fetched.

    render() returns nothing, so autoBoot used to read its undefined
    return as "inline path didn't run" and fetch <page>.json on top —
    a guaranteed 404 in a single file, and a hard failure over file://.
    """
    requested: list[str] = []
    page.on("request", lambda r: requested.append(r.url))
    _goto(page, standalone_url)
    # A stray fetch would be in flight or finished by the time the network
    # goes quiet, so wait for that rather than for a number that has to be
    # guessed high enough for the slowest machine.
    page.wait_for_load_state("networkidle")
    strays = [u for u in requested if u.endswith(".json") or u.endswith("/__reload")]
    assert strays == [], f"standalone must not reach the network: {strays}"


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


# ---------- parity with the served page ----------

_RICH_PAGE = {
    "k": "page",
    "t": "Zengin sayfa",
    "m": {"summary": "Parity probe"},
    "b": [
        "## Metin {#metin}\n\nParagraf, **kalın**, `kod`, [bağlantı](https://example.com) ve bir liste:\n\n- bir\n- iki\n",
        {"k": "chart", "type": "bar", "rows": [{"label": "a", "value": 60}, {"label": "b", "value": 80}]},
        {"k": "table", "headers": ["Ad", "Değer"], "rows": [["x", "1"], ["y", "2"]]},
        {"k": "kpi-grid", "tiles": [{"num": "12", "label": "ölçüm"}]},
        "## İkinci {#ikinci}\n\n> [!NOTE] Not\n> Gövde.\n\n```js\nconst a = 1;\n```\n",
    ],
}

_SHAPE = """() => ({
  sections: document.querySelectorAll('main section').length,
  paragraphs: document.querySelectorAll('main p').length,
  listItems: document.querySelectorAll('main li').length,
  tables: document.querySelectorAll('main .okt-table-wrap').length,
  rows: document.querySelectorAll('main .okt-table-wrap tbody tr').length,
  charts: document.querySelectorAll('oku-chart').length,
  barRows: document.querySelectorAll('main .bar-row').length,
  kpis: document.querySelectorAll('main .kpi').length,
  callouts: document.querySelectorAll('main .callout').length,
  codeBlocks: document.querySelectorAll('main pre code').length,
  links: document.querySelectorAll('main a[href^="https://"]').length,
  text: document.querySelector('main').innerText.replace(/\\s+/g, ' ').trim(),
})"""


@pytest.fixture(scope="session")
def parity_urls(tmp_path_factory):
    """The same page two ways: served (stub + sibling JSON) and built
    standalone (everything inlined). Also hands back the file:// URL of
    the standalone artifact, which is how it actually gets shared."""
    from oku import cli

    src = tmp_path_factory.mktemp("parity-src")
    out = tmp_path_factory.mktemp("parity-out")
    (src / "_oku").symlink_to(Path(__file__).resolve().parents[3] / "kit", target_is_directory=True)
    stub = cli._stub_for("Zengin sayfa")
    (src / "rich.html").write_text(stub, encoding="utf-8")
    (src / "rich.json").write_text(json.dumps(_RICH_PAGE, ensure_ascii=False), encoding="utf-8")
    cli.build_standalone([(src / "rich.html", stub, _RICH_PAGE)], out, src)

    servers = []
    for directory in (src, out):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
    yield {
        "served": f"http://127.0.0.1:{servers[0].server_address[1]}/rich.html",
        "standalone": f"http://127.0.0.1:{servers[1].server_address[1]}/rich.html",
        "file": (out / "rich.html").as_uri(),
    }
    for httpd in servers:
        httpd.shutdown()


def test_standalone_matches_the_served_page(page, parity_urls):
    """A standalone file is what gets emailed. Its DOM must match the
    served page block for block — same sections, same chart, same table
    rows, same text — or "send the HTML" quietly ships something else
    than what the author reviewed."""
    _goto(page, parity_urls["served"])
    page.wait_for_timeout(1200)
    served = page.evaluate(_SHAPE)

    _goto(page, parity_urls["standalone"])
    page.wait_for_timeout(1200)
    standalone = page.evaluate(_SHAPE)

    assert standalone == served, {k: (served[k], standalone[k]) for k in served if served[k] != standalone[k]}
    # The bar family renders as DIV rows rather than an <oku-chart> host,
    # so barRows is what proves the chart made it across.
    assert served["barRows"] == 2 and served["tables"] == 1, served


def test_standalone_renders_the_same_from_file_protocol(page, parity_urls):
    """No server at all — the file:// case the artifact exists for."""
    page.goto(parity_urls["file"])
    page.wait_for_selector("main section")
    page.wait_for_timeout(1200)
    shape = page.evaluate(_SHAPE)
    assert shape["sections"] == 2
    assert shape["barRows"] == 2
    assert shape["tables"] == 1 and shape["rows"] >= 2
    assert shape["kpis"] == 1 and shape["callouts"] == 1
    assert shape["codeBlocks"] == 1 and shape["links"] == 1
    assert "kalın" in shape["text"]
