"""The typography travels with the page, and reaches nowhere for it.

`chrome.css` opened with an `@import` of fonts.googleapis.com, so every
page of every built tree fetched two families from a third party on
load. Three costs, and the order matters:

* Every reader of every delivered document announced themselves — IP,
  referrer, page URL — to Google. This kit refuses to let a page phone
  home for its own build stamp; it should not do it for a typeface.
* A page opened with no network lost the typography its measure is set
  in, silently.
* 330 ms of render-blocking round trip, because an `@import` inside a
  render-blocking stylesheet is serial.

The repair is the one mermaid and Prism already use: fetch once into
`vendor/`, share one copy beside the built pages. Not inlined — 185 KB
of woff2 per page, on every page of every tree, buys back only the case
where a standalone file is forwarded away from its directory.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import re
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(cli.KIT_DIR)

PAGE_MD = """---
title: Typography
summary: A page in two alphabets, so both subsets are exercised.
---

## Latin {#latin}

The quick brown fox jumps over the lazy dog.

## Türkçe {#turkce}

Şu ağacın gölgesinde iğne aradık; çilingir çıkageldi.

```python
def f(x):
    return x + 1
```
"""


def _build(tmp_path_factory, name: str) -> Path:
    docs = tmp_path_factory.mktemp(name) / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Typography"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    return docs / "dist"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if not cli.vendor_fonts_present():
        pytest.skip("fonts not vendored — run `oku vendor`")
    return _build(tmp_path_factory, "fonts")


# `check(font, text)` answers "is a loaded face available that can render
# this text" — which is the reader's question, not "did a file arrive".
FONT_STATE = """async () => {
  await document.fonts.ready;
  return {
    inter: document.fonts.check('16px Inter'),
    mono: document.fonts.check('16px "JetBrains Mono"'),
    turkish: document.fonts.check('16px Inter', 'şğİıÇ'),
    loaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family),
    body: getComputedStyle(document.body).fontFamily,
  };
}"""


def _blocked_page(browser, url: str, allow_local: bool):
    """Open `url` with every non-local origin refused, counting both the
    refusals and the calls. The count is the point: a route pattern that
    matches nothing makes 'nothing reached a third party' true by never
    running, which is how this repo's offline suite passed for months
    against a live CDN."""
    pg = browser.new_page()
    reached: list[str] = []
    calls = [0]

    def route(r, request):
        calls[0] += 1
        external = request.url.startswith(("http://", "https://"))
        if not external or (allow_local and "127.0.0.1" in request.url):
            r.continue_()
            return
        reached.append(request.url)
        r.abort()

    pg.route("**/*", route)
    pg.goto(url)
    pg.wait_for_selector("main section")
    state = pg.evaluate(FONT_STATE)
    pg.close()
    return state, reached, calls[0]


@pytest.fixture(scope="module")
def standalone_state(browser, built):
    return _blocked_page(browser, (built / "standalone" / "page.html").as_uri(), allow_local=False)


@pytest.fixture(scope="module")
def site_state(browser, built):
    site = built / "site"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        return _blocked_page(
            browser, f"http://127.0.0.1:{httpd.server_address[1]}/page.html", allow_local=True
        )
    finally:
        httpd.shutdown()


# ---------- what the reader gets, in both delivered trees


def test_a_standalone_page_renders_in_inter_with_no_network(standalone_state) -> None:
    state, _, _ = standalone_state
    assert state["inter"], f"Inter did not load: {state}"
    assert state["mono"], f"JetBrains Mono did not load: {state}"


def test_a_site_page_renders_in_inter_with_no_network(site_state) -> None:
    """The tree that gets deployed was built from its own recipe, and
    that is exactly where the last vendoring defect lived."""
    state, _, _ = site_state
    assert state["inter"], f"Inter did not load: {state}"
    assert state["mono"], f"JetBrains Mono did not load: {state}"


@pytest.mark.parametrize("fixture", ["standalone_state", "site_state"])
def test_turkish_letters_come_from_the_same_face(fixture, request) -> None:
    """`ş` and `ğ` are in latin-ext, `ı` in latin. Ship only the first
    subset and a Turkish word changes typeface halfway through, which
    reads as a rendering bug rather than a missing file."""
    state, _, _ = request.getfixturevalue(fixture)
    assert state["turkish"], f"latin-ext did not load: {state}"


@pytest.mark.parametrize("fixture", ["standalone_state", "site_state"])
def test_no_page_asks_a_third_party_for_type(fixture, request) -> None:
    state, reached, calls = request.getfixturevalue(fixture)
    assert calls > 0, "the route never fired — this test proves nothing"
    hosts = [u for u in reached if "font" in u or "google" in u or "gstatic" in u]
    assert hosts == [], f"the page reached for a font: {hosts}"
    assert state["loaded"], "no webfont loaded at all — the page fell back to the system stack"


# ---------- where the bytes are


def test_the_fonts_are_shared_not_inlined(built) -> None:
    """185 KB of woff2 becomes 250 KB as base64, per page. The tree
    carries one copy, the same call vendoring already makes for mermaid.
    """
    page = built / "standalone" / "page.html"
    shared = built / "standalone" / "_oku" / "vendor" / "fonts"
    assert sorted(p.name for p in shared.glob("*.woff2")) == sorted(n for n, _pkg in cli._VENDOR_FONTS)
    assert "data:font" not in page.read_text(encoding="utf-8"), "a font got inlined"


def test_a_standalone_page_points_at_the_copy_beside_it(built) -> None:
    """Inlined into the page, `url("vendor/fonts/…")` resolves against
    the PAGE, so it names a directory that does not exist and the reader
    silently gets the system stack."""
    html = (built / "standalone" / "page.html").read_text(encoding="utf-8")
    urls = re.findall(r'url\("([^"]*fonts/[^"]+)"\)', html)
    assert len(urls) == 4, urls
    for u in urls:
        assert u.startswith("_oku/vendor/fonts/"), u
        assert (built / "standalone" / u).is_file(), u


def test_the_site_stylesheet_keeps_its_own_relative_urls(built) -> None:
    css = (built / "site" / "_oku" / "chrome.css").read_text(encoding="utf-8")
    urls = re.findall(r'url\("([^"]*fonts/[^"]+)"\)', css)
    assert len(urls) == 4, urls
    for u in urls:
        assert (built / "site" / "_oku" / u).is_file(), u


# ---------- the source rule, and the branch where nothing was fetched


def _rules_only(css: str) -> str:
    """Comments explain the rule; only declarations can break it — and
    the comment above these very rules names the host they replaced."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_no_kit_file_names_a_font_host() -> None:
    """A source-level guard, because the runtime one can only prove that
    a page did not reach out on the run that was watched."""
    named = []
    for f in cli.KIT_FILES:
        text = (KIT / f).read_text(encoding="utf-8")
        text = _rules_only(text) if f.endswith(".css") else text
        for host in ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit", "fontsource"):
            if host in text:
                named.append(f"{f}: {host}")
    assert named == [], named


def test_the_stylesheet_declares_every_face_it_vendors() -> None:
    css = _rules_only((KIT / "chrome.css").read_text(encoding="utf-8"))
    for name, _pkg in cli._VENDOR_FONTS:
        assert f'url("vendor/fonts/{name}")' in css, name
    assert css.count("@font-face") == len(cli._VENDOR_FONTS)


def test_without_the_fonts_the_rules_are_dropped_rather_than_repointed(monkeypatch) -> None:
    """A shipped @font-face whose file is absent costs a failed request
    per page for a fallback the font-family declarations already give."""
    css = (KIT / "chrome.css").read_text(encoding="utf-8")
    monkeypatch.setattr(cli, "vendor_fonts_present", lambda: False)
    out = _rules_only(cli._retarget_font_urls(css, "../_oku/vendor/"))
    css = _rules_only(css)
    assert "@font-face" not in out
    assert "vendor/fonts/" not in out
    # Everything else survives: this drops rules, it does not edit the
    # stylesheet.
    assert out.count("font-family") == css.count("font-family") - len(cli._VENDOR_FONTS)
    assert ":root" in out and "--accent" in out


def test_with_the_fonts_every_url_is_repointed(monkeypatch) -> None:
    css = (KIT / "chrome.css").read_text(encoding="utf-8")
    monkeypatch.setattr(cli, "vendor_fonts_present", lambda: True)
    out = cli._retarget_font_urls(css, "../../_oku/vendor/")
    assert out.count('url("../../_oku/vendor/fonts/') == len(cli._VENDOR_FONTS)
    assert 'url("vendor/fonts/' not in out


def test_half_a_font_set_counts_as_none(tmp_path, monkeypatch) -> None:
    """All or nothing: three faces present and one missing renders
    Turkish in a different typeface from the sentence around it."""
    monkeypatch.setattr(cli, "vendor_dir", lambda: tmp_path)
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    names = [n for n, _pkg in cli._VENDOR_FONTS]
    for n in names[:-1]:
        (fonts / n).write_bytes(b"wOF2")
    assert cli.vendor_fonts_present() is False
    (fonts / names[-1]).write_bytes(b"wOF2")
    assert cli.vendor_fonts_present() is True
