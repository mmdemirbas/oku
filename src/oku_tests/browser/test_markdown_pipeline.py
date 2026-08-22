"""GFM conformance regressions for the block + inline markdown parser.

Every case here rendered wrongly at some point: the construct either came
out as literal source text, or it silently produced the wrong DOM. They
are grouped by the layer that owns them — inline (emphasis, escapes,
links, images) and block (fences, rules, lists, tables, headings).

One page is served for the whole module; each test asserts on its own
construct so a failure names the construct, not "markdown broke".
"""

from __future__ import annotations

from ._wait import page_quiet

import http.server
import json
import threading
from functools import partial
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

MD = """## Inline {#inline}

Escapes: \\*not em\\*, \\[not a link\\], \\`not code\\`, a\\_b.

Identifiers: snake_case_name and read_file_sync stay whole, but __init__ is bold.

Strike: ~~dropped~~ text.

Autolink: <https://example.com/auto> and <mailto:a@b.co>.

Image: ![a pixel](https://example.com/p.png)

Titled: [label](https://example.com/t "hover text")

Entities: AT&T &amp; co, &lt;tag&gt;, &mdash; and &#8594;.

Hard break line one\\
line two ends it.

Unsafe: [click](javascript:alert(1)) stays text.

Code spans: `` `code` and [a](b) `` and ``a ` b`` stay literal.

## Block {#block}

Rule below is three asterisks.

***

Rule below is three underscores.

___

~~~python
x = 1
~~~

### Closing hashes ###

3. three
4. four

- tight item
  - nested child
- item with two paragraphs

  second paragraph of that item

| left | right | mid |
|:-----|------:|:---:|
| a \\| b | `c|d` | e |
| short |
| 1 | 2 | 3 | 4 |

### Same title

### Same title

### References {#refs}

A footnote here[^n] and a second one[^long id]. A [reference link][site],
a [collapsed][] one, a [shortcut] one, and an [unknown][nope] one.

[^n]: The first note.
[^long id]: The second note,
  continued on the next line.
[site]: https://example.com/ref "Ref title"
[collapsed]: https://example.com/collapsed
[shortcut]: https://example.com/shortcut
"""

PAGE = {"k": "page", "t": "Markdown pipeline", "b": [MD]}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("mdpipeline")
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


@pytest.fixture(scope="module")
def rendered(served, browser):
    """Render once, hand every test the same page object."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(served)
    page_quiet(page)
    yield page
    page.close()


def _text(page):
    return page.eval_on_selector("main", "el => el.innerText")


# ---------- inline ----------


def test_backslash_escapes_produce_literal_characters(rendered):
    """`\\*` is the only way to write a literal asterisk. Without escape
    support the backslash showed up AND the emphasis still fired."""
    line = rendered.eval_on_selector("main p", "el => el.innerText")
    assert line == "Escapes: *not em*, [not a link], `not code`, a_b."
    assert rendered.locator("main p").first.locator("em, code, a").count() == 0


def test_intraword_underscores_are_not_emphasis(rendered):
    """snake_case identifiers are the single most common false positive
    in technical prose — `_` may only open emphasis at a word boundary."""
    body = _text(rendered)
    assert "snake_case_name" in body
    assert "read_file_sync" in body
    ems = rendered.eval_on_selector_all("main em", "els => els.map(e => e.textContent)")
    assert "case" not in ems
    # …while a delimiter run that stands free still emphasises.
    assert "init" in rendered.eval_on_selector_all("main strong", "els => els.map(e => e.textContent)")


def test_strikethrough_renders(rendered):
    assert rendered.locator("main del").count() >= 1
    assert rendered.locator("main del").first.inner_text() == "dropped"


def test_autolinks_render(rendered):
    assert rendered.locator('main a[href="https://example.com/auto"]').count() == 1
    assert rendered.locator('main a[href="mailto:a@b.co"]').count() == 1


def test_image_renders_as_img(rendered):
    img = rendered.locator('main img[src="https://example.com/p.png"]')
    assert img.count() == 1
    assert img.get_attribute("alt") == "a pixel"


def test_link_title_becomes_the_title_attribute(rendered):
    a = rendered.locator('main a[href="https://example.com/t"]')
    assert a.count() == 1
    assert a.get_attribute("title") == "hover text"


def test_character_references_are_decoded(rendered):
    body = _text(rendered)
    assert "AT&T & co" in body
    assert "<tag>" in body
    assert "—" in body and "→" in body
    assert "&amp;" not in body and "&#8594;" not in body


def test_hard_line_break_emits_br(rendered):
    assert rendered.locator("main p br").count() >= 1


def test_javascript_url_is_not_linkable(rendered):
    """An authored `javascript:` destination must not become a live link;
    the label survives as text."""
    assert rendered.locator('main a[href^="javascript:"]').count() == 0
    assert "click" in _text(rendered)


# ---------- block ----------


def test_all_three_thematic_break_markers(rendered):
    """`***` and `___` used to render as paragraphs of punctuation."""
    assert rendered.locator("main hr").count() >= 2
    body = _text(rendered)
    assert "\n***" not in body and "\n___" not in body


def test_tilde_fence_is_a_code_block(rendered):
    langs = rendered.eval_on_selector_all("main pre code", "els => els.map(e => e.className)")
    assert "language-python" in langs
    assert "~~~" not in _text(rendered)


def test_atx_closing_sequence_is_stripped(rendered):
    # firstChild skips the permalink anchor the chrome appends.
    titles = rendered.eval_on_selector_all("main h3", "els => els.map(e => e.firstChild.textContent)")
    assert "Closing hashes" in titles


def test_ordered_list_keeps_its_start_number(rendered):
    ol = rendered.locator("main ol").first
    assert ol.get_attribute("start") == "3"


def test_tight_item_has_no_paragraph_wrapper(rendered):
    """A tight list must stay <li>text</li> — a <p> inside every item
    doubles the vertical rhythm of every bullet list on every page."""
    first = rendered.locator("main ul > li").first
    assert first.evaluate("el => el.firstChild.nodeType") == 3


def test_nested_list_hangs_off_its_parent_item(rendered):
    assert rendered.locator("main ul > li > ul > li").count() >= 1


def test_list_item_keeps_its_second_paragraph(rendered):
    """The item used to end at the blank line, so the continuation became
    a sibling paragraph and the list was cut in two."""
    li = rendered.locator("main ul > li", has_text="item with two paragraphs").first
    assert li.locator("p").count() == 2
    assert "second paragraph of that item" in li.inner_text()


def test_table_alignment_from_the_separator_row(rendered):
    aligns = rendered.evaluate(
        "() => [...document.querySelector('main table').querySelectorAll('th')]"
        ".map(e => getComputedStyle(e).textAlign)"
    )
    assert aligns[:3] == ["left", "right", "center"]


def test_escaped_and_code_pipes_stay_inside_their_cell(rendered):
    # querySelector: document order, so this is the markdown table — the
    # chrome's config popover adds tables of its own further down.
    first = rendered.evaluate(
        "() => [...document.querySelector('main table').querySelectorAll('tbody tr')[0].children]"
        ".map(e => e.textContent)"
    )
    assert first == ["a | b", "c|d", "e"]


def test_ragged_rows_are_normalised_to_the_header_width(rendered):
    widths = rendered.evaluate(
        "() => [...document.querySelector('main table').querySelectorAll('tbody tr')]"
        ".map(e => e.children.length)"
    )
    assert set(widths) == {3}, widths


def test_repeated_headings_get_distinct_anchors(rendered):
    ids = rendered.eval_on_selector_all("main h3[id]", "els => els.map(e => e.id)")
    assert len(ids) == len(set(ids)), ids
    assert "same-title" in ids and "same-title-2" in ids


def test_page_has_no_duplicate_element_ids(rendered):
    dups = rendered.evaluate(
        """() => {
          const seen = new Set(), dup = [];
          document.querySelectorAll('[id]').forEach(e => {
            if (seen.has(e.id)) dup.push(e.id); else seen.add(e.id);
          });
          return dup;
        }"""
    )
    assert dups == [], dups


# ---------- page-scoped reference forms ----------


def test_footnotes_render_as_numbered_references(rendered):
    """`docs/reference.md` documented footnotes long before the renderer
    had them; the syntax used to ship to readers as literal text."""
    refs = rendered.eval_on_selector_all("main sup.okt-fn-ref a", "els => els.map(e => e.textContent)")
    assert refs == ["1", "2"]
    section = rendered.locator("section.okt-footnotes")
    assert section.count() == 1
    items = section.locator("li")
    assert items.count() == 2
    assert "The first note." in items.first.inner_text()
    # a definition continued on an indented line keeps its tail
    assert "continued on the next line." in items.nth(1).inner_text()


def test_footnote_reference_and_definition_link_to_each_other(rendered):
    assert rendered.locator('main sup.okt-fn-ref a[href="#fn-1"]').count() == 1
    assert rendered.locator('section.okt-footnotes li#fn-1 a[href="#fnref-1"]').count() == 1


def test_reference_links_resolve_in_all_three_forms(rendered):
    full = rendered.locator('main a[href="https://example.com/ref"]')
    assert full.count() == 1
    assert full.get_attribute("title") == "Ref title"
    assert rendered.locator('main a[href="https://example.com/collapsed"]').count() == 1
    assert rendered.locator('main a[href="https://example.com/shortcut"]').count() == 1


def test_undefined_reference_stays_literal_text(rendered):
    assert "[unknown][nope]" in _text(rendered)


def test_definition_lines_are_not_rendered(rendered):
    body = _text(rendered)
    assert "https://example.com/ref" not in body
    assert "[^n]:" not in body


# ---------- code spans ----------


def test_multi_backtick_code_spans(rendered):
    """A code span opens with N backticks and closes on the next run of
    exactly N. Only the single-backtick form used to parse, so the
    CommonMark ``…`` form — the one you need when the code itself holds
    a backtick — mis-paired and let markdown inside the span render:
    this repo's own reference table leaked a live link and four broken
    images out of a code cell that way."""
    spans = rendered.eval_on_selector_all("main code", "els => els.map(e => e.textContent)")
    assert "`code` and [a](b)" in spans
    assert "a ` b" in spans
    # …and nothing inside those spans became an element.
    assert rendered.locator("main code a, main code img").count() == 0


def test_code_span_strips_one_padding_space_each_side(rendered):
    spans = rendered.eval_on_selector_all("main code", "els => els.map(e => e.textContent)")
    assert not any(s.startswith(" ") and s.endswith(" ") for s in spans), spans
