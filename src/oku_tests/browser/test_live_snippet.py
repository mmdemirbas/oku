"""The playground does what `docs/reference.md` says it does.

Four claims in one paragraph — an editable source with a sandboxed
iframe preview, a 220 ms debounce on input, a Reset that restores the
original — and the kit-wide one every element inherits: its own strings
follow the page's language. Measured with a page that uses the fence
exactly as `oku spec live-snippet` prints it, in both delivery modes and
both languages, because a standalone page inlines its string table where
a served one fetches it.

The language claim is the one that failed. Every string the element
draws — `Reset`, `Reset to original`, `Code`, `Preview`, the default
label — was in `kit/i18n/tr.json`, so `test_i18n_coverage.py` was green;
the element built them under `hds-*` classes, the one prefix in the kit
that is not `okt-` / `okc-` / `okd-`, and the localize walk scopes on
those prefixes. A Turkish page fetched the table and rendered the
playground in English. The table test holds the TABLE; this holds the
DOM.

"Sandboxed" is held by trying: the snippet's own script reaches for
`window.parent.document` and has to be refused. An iframe with
`sandbox="allow-scripts"` and no `allow-same-origin` is an opaque origin,
which is what makes an author's playground safe to put on a page with a
reader's localStorage in it.
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

from ._wait import page_quiet, until

pytestmark = pytest.mark.browser

# The script inside tries to escape. `h` reports what happened, so the
# assertion reads a word rather than the absence of a side effect.
SOURCE = (
    "<style>body{margin:0}</style>"
    '<h1 id="h">Try the snippet</h1>'
    "<script>try{window.parent.document.title='PWNED';"
    "document.getElementById('h').textContent='reached parent'}"
    "catch(e){document.getElementById('h').textContent='blocked: '+e.name}</script>"
)

STRINGS = {
    "en": {"reset": "Reset", "resetAria": "Reset to original", "editor": "Code", "frame": "Preview"},
    "tr": {"reset": "Sıfırla", "resetAria": "Özgün haline sıfırla", "editor": "Kod", "frame": "Önizleme"},
}


def _page_md() -> str:
    body = json.dumps({"src": SOURCE, "label": "Edit me"}, ensure_ascii=False)
    return f"---\ntitle: Snippet\nsummary: The playground, used as documented.\n---\n\n## Play {{#play}}\n\n```oku-live-snippet\n{body}\n```\n"


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("snippet").resolve() / "docs"
    d.mkdir()
    (d / "kit.json").write_text(
        json.dumps({"languages": ["en", "tr"], "defaultLanguage": "en"}), encoding="utf-8"
    )
    for name in ("page.md", "page.tr.md"):
        (d / name).write_text(_page_md(), encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("Snippet"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(d)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return d


@pytest.fixture(scope="module")
def served(tree):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(tree))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _url(tree: Path, served: str, mode: str, lang: str) -> str:
    name = "page.html" if lang == "en" else "page.tr.html"
    if mode == "served":
        return f"{served}/{name}"
    return (tree / "dist" / "standalone" / name).as_uri()


READ = """() => {
  const el = document.querySelector('oku-snippet');
  const frame = el.querySelector('iframe');
  return {
    sandbox: frame.getAttribute('sandbox'),
    label: el.querySelector('.okt-snippet-label').textContent,
    reset: el.querySelector('.okt-snippet-reset').textContent.trim(),
    resetAria: el.querySelector('.okt-snippet-reset').getAttribute('aria-label'),
    editor: el.querySelector('textarea').getAttribute('aria-label'),
    frame: frame.getAttribute('aria-label'),
    title: document.title,
  };
}"""


@pytest.fixture(scope="module")
def opened(browser, tree, served):
    """One page per (mode, language), each read once. The playground is
    stateful — the edit and reset cases below drive it — so those run
    on the `en` served page and the other three answer the read-only
    questions."""
    pages = {}
    for mode in ("served", "standalone"):
        for lang in ("en", "tr"):
            pg = browser.new_page()
            pg.goto(_url(tree, served, mode, lang), wait_until="load")
            pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
            page_quiet(pg)
            pages[(mode, lang)] = pg
    yield pages
    for pg in pages.values():
        pg.close()


@pytest.mark.parametrize("mode", ["served", "standalone"])
@pytest.mark.parametrize("lang", ["en", "tr"])
def test_the_preview_is_an_opaque_origin(opened, mode, lang):
    """The snippet's script ran — the heading changed — and was refused
    the parent. Both halves matter: a frame that refused scripts would
    pass a weaker assertion for the wrong reason."""
    pg = opened[(mode, lang)]
    frames = [f for f in pg.frames if f != pg.main_frame]
    assert len(frames) == 1, [f.url for f in pg.frames]
    until(
        frames[0],
        "() => (document.getElementById('h') || {}).textContent !== 'Try the snippet'",
        what="the snippet's own script ran",
    )
    assert frames[0].evaluate("() => document.getElementById('h').textContent") == "blocked: SecurityError"
    got = pg.evaluate(READ)
    assert got["sandbox"] == "allow-scripts", got
    assert got["title"] == "Snippet", got


@pytest.mark.parametrize("mode", ["served", "standalone"])
@pytest.mark.parametrize("lang", ["en", "tr"])
def test_the_playground_speaks_the_page_s_language(opened, mode, lang):
    got = opened[(mode, lang)].evaluate(READ)
    assert got["label"] == "Edit me", got  # the author's word, in neither table
    for key, want in STRINGS[lang].items():
        assert got[key] == want, (key, lang, mode, got)


def test_an_edit_reaches_the_preview_after_the_debounce_and_not_before(opened):
    pg = opened[("served", "en")]
    got = pg.evaluate(
        """() => new Promise((res) => {
          const el = document.querySelector('oku-snippet');
          const frame = el.querySelector('iframe'), ta = el.querySelector('textarea');
          const before = frame.srcdoc;
          ta.value = '<p id="x">edited</p>';
          ta.dispatchEvent(new Event('input', { bubbles: true }));
          const immediately = frame.srcdoc === before;
          setTimeout(() => res({ immediately, after: frame.srcdoc }), 400);
        })"""
    )
    assert got["immediately"] is True, got
    assert got["after"] == '<p id="x">edited</p>', got


def test_reset_restores_the_original_source(opened):
    pg = opened[("served", "en")]
    got = pg.evaluate(
        """() => {
          const el = document.querySelector('oku-snippet');
          const frame = el.querySelector('iframe'), ta = el.querySelector('textarea');
          el.querySelector('.okt-snippet-reset').click();
          return { value: ta.value, srcdoc: frame.srcdoc };
        }"""
    )
    assert got["value"] == SOURCE, got
    assert got["srcdoc"] == SOURCE, got
