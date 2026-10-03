"""Two GFM inline rules the parser did not follow.

Link text may hold brackets as long as they balance. The label pattern
refused `]`, so `[AJSLP 2025 **[özet]**](url)` was not a link at all —
the whole construct stayed on the page as typed, square brackets and
URL included. Measured on two delivered research pages of another
project: 48 links parsed out of 220, the other 172 on 136 lines shown
as source.

And a bare URL is a link (GFM's extended autolink). Prose that names an
address without angle brackets left the reader to select and copy it.
The spec's edges are the point of the cases below: trailing punctuation
belongs to the sentence, a closing parenthesis belongs to the URL only
when the URL opened one, the host needs a dot, the URL must start at a
boundary, and an address inside another link's words is not a second
link — an <a> inside an <a> is invalid and the browser splits it.

Served as a v2 page from a tmp dir with an `_oku` symlink to the live
kit/; the package auto-skips when chromium isn't installed.
"""

from __future__ import annotations

import http.server
import json
import threading
from functools import partial
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

X = "https://example.com/x"
Y = "https://example.com/y"

PARAS = {
    "nested": f"Kaynak: [AJSLP 2025 **[özet]**]({X}) burada.",
    "balanced": f"Bir de [a [b] c]({Y}) var.",
    "unbalanced": "Açık kalan [a[b](https://example.com/b) ayrılır.",
    "alt": "Görsel: ![şekil [1]](missing.png) sonu.",
    "bare": "Adres https://example.com/a/b. Sonraki cümle.",
    "paren": "(bkz. https://en.wikipedia.org/wiki/Foo_(bar)) diye yazılmış.",
    "www": "Ya da www.example.org adresine bakın.",
    "local": "Yerel http://localhost:8080 bağlantı olmaz.",
    "label": f"Etiketin içinde [bkz. https://example.com/inner]({X}) tek bağlantıdır.",
    "boundary": "Bitişik foo:https://example.com/glued bağlantı olmaz.",
    "bold": "Kalın **https://example.com/z** bağlantı olur.",
    "angle": "Açılı <https://example.com/q> tek bağlantıdır.",
    "code": "Kod `https://example.com/code` kod kalır.",
    "email": "Yazın: ad.soyad+oku@example.com.tr. Sonraki cümle.",
    "emailAngle": "Açılı <kisi@example.org> tek bağlantıdır.",
    "emailLineStart": "<kisi@example.org> satır başında da bağlantıdır, ada değil.",
    "emailScheme": "Önekli mailto:kisi@example.org de bağlantıdır.",
    "emailNoDot": "Noktasız kisi@localhost bağlantı olmaz.",
    "emailTail": "Sonu tireli kisi@example.org- bağlantı olmaz.",
    "emailGlued": "Kelimeye yapışık çağrı.ad@example.org yarım bağlanmaz.",
    "emailInUrl": "Kullanıcılı https://kisi@example.org/yol yarım bağlanmaz.",
    "emailCode": "Kod `kisi@example.org` kod kalır.",
}

PAGE = {
    "k": "page",
    "t": "Bağlantılar",
    "b": [
        "## Test {#t}\n\n"
        + "".join(f'<p data-case="{k}">\n\n{v}\n\n</p>\n\n' for k, v in PARAS.items())
        + "| Kaynak | Not |\n|---|---|\n| https://example.com/cell | hücrede |\n"
    ],
}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("links")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.json").write_text(json.dumps(PAGE, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.json", "title": PAGE["t"], "parent": None}],
    }
    (d / "page.html").write_text(cli._stub_for(PAGE["t"], inline_manifest=manifest), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


@pytest.fixture
def cases(page, served):
    page.goto(served)
    page_quiet(page)
    return page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('[data-case]')].map(p => [p.dataset.case, {
             text: p.innerText.trim(),
             links: [...p.querySelectorAll('a')].map(a => [a.getAttribute('href'), a.innerText.trim()]),
             nested: p.querySelectorAll('a a').length,
             alts: [...p.querySelectorAll('img')].map(i => i.getAttribute('alt')),
             strongLinks: p.querySelectorAll('a strong, strong a').length,
           }]))"""
    )


def test_balanced_brackets_stay_inside_the_link(cases):
    c = cases["nested"]
    assert c["links"] == [[X, "AJSLP 2025 [özet]"]], c
    assert c["strongLinks"] == 1, c
    assert "](" not in c["text"], c
    assert cases["balanced"]["links"] == [[Y, "a [b] c"]], cases["balanced"]


def test_an_unbalanced_bracket_is_text_before_the_link(cases):
    c = cases["unbalanced"]
    assert c["links"] == [["https://example.com/b", "b"]], c
    assert c["text"].startswith("Açık kalan [a"), c


def test_an_image_alt_may_hold_brackets(cases):
    assert cases["alt"]["alts"] == ["şekil [1]"], cases["alt"]


def test_a_bare_url_is_a_link_and_the_full_stop_is_not_part_of_it(cases):
    c = cases["bare"]
    assert c["links"] == [["https://example.com/a/b", "https://example.com/a/b"]], c
    assert c["text"].endswith("a/b. Sonraki cümle."), c


def test_a_closing_parenthesis_belongs_to_the_url_only_when_it_opened_one(cases):
    c = cases["paren"]
    assert c["links"] == [["https://en.wikipedia.org/wiki/Foo_(bar)"] * 2], c
    assert c["text"].startswith("(bkz. https://en.wikipedia.org/wiki/Foo_(bar)) diye"), c


def test_www_gets_a_scheme(cases):
    assert cases["www"]["links"] == [["http://www.example.org", "www.example.org"]], cases["www"]


def test_a_host_without_a_dot_is_not_a_link(cases):
    assert cases["local"]["links"] == [], cases["local"]


def test_an_address_inside_a_links_words_is_not_a_second_link(cases):
    c = cases["label"]
    assert c["links"] == [[X, "bkz. https://example.com/inner"]], c
    assert c["nested"] == 0, c


def test_a_url_glued_to_a_word_is_not_a_link(cases):
    assert cases["boundary"]["links"] == [], cases["boundary"]


def test_bold_angle_and_code_forms(cases):
    assert cases["bold"]["links"] == [["https://example.com/z"] * 2], cases["bold"]
    assert cases["bold"]["strongLinks"] == 1, cases["bold"]
    assert cases["angle"]["links"] == [["https://example.com/q"] * 2], cases["angle"]
    assert cases["code"]["links"] == [], cases["code"]


def test_a_bare_email_address_is_a_mailto_link(cases):
    """GFM's extended email autolink. The full stop is the sentence's, as
    it is for a URL, and `+` is part of the local part."""
    c = cases["email"]
    assert c["links"] == [["mailto:ad.soyad+oku@example.com.tr", "ad.soyad+oku@example.com.tr"]], c
    assert c["text"].endswith(".com.tr. Sonraki cümle."), c
    assert cases["emailAngle"]["links"] == [["mailto:kisi@example.org", "kisi@example.org"]], cases[
        "emailAngle"
    ]
    assert cases["emailScheme"]["links"] == [["mailto:kisi@example.org"] * 2], cases["emailScheme"]
    # At the start of a line `<kisi` could read as a tag opening an HTML
    # island; `@` is not a tag-name character, so it is a paragraph.
    assert cases["emailLineStart"]["links"] == [["mailto:kisi@example.org", "kisi@example.org"]], cases[
        "emailLineStart"
    ]


def test_what_is_not_an_address_stays_text(cases):
    for case in ("emailNoDot", "emailTail", "emailGlued", "emailCode"):
        assert cases[case]["links"] == [], (case, cases[case])
    assert cases["emailGlued"]["text"] == PARAS["emailGlued"], cases["emailGlued"]
    # A URL carrying a user part was never a link here (its host is not a
    # host), and the address inside it must not be picked out as half of
    # one: the run stays one piece of text.
    c = cases["emailInUrl"]
    assert c["links"] == [], c
    assert c["text"] == PARAS["emailInUrl"], c


def test_a_bare_url_in_a_table_cell_is_a_link(page, served):
    page.goto(served)
    page_quiet(page)
    assert page.locator('main .okt-table-scroll table td a[href="https://example.com/cell"]').count() == 1
