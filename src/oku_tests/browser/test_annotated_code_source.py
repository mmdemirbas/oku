"""`oku-annotated-code` must not print its annotations as code.

The element takes its program from `<script type="text/x-code">` and its
annotations from either `<script type="application/json">` or a child
`<ol class="okc-anno-source">`. When the x-code script is absent it falls
back to the host's own text — and `textContent` does not skip `<script>`
or the annotation list, so the annotation payload was appended to the
program and rendered twice: once as code, once in the side panel.

The markdown fence path always emits an x-code script and never hit
this; the HTML-island path, where an author writes the code as plain
text, hits it every time.

The islands here carry no `language`, so the element builds synchronously
and Prism never runs. That is deliberate: with a language set, a separate
open defect (Prism's second autoloader pass re-highlighting from a DOM
that already holds the marker chips and tooltips) bakes the annotation
text into the code on its own, and would mask what these assert.
"""

from __future__ import annotations

import json

import pytest

CODE = "def load(path):\n    data = read(path)   (1)\n    return parse(data)  (2)"
ANNOS = [
    {"id": 1, "content": "Reads the whole file into memory."},
    {"id": 2, "content": "Parsing is where the schema is enforced."},
]

# The two island shapes an author can write without an x-code script.
ISLANDS = {
    "json-script": (
        "<oku-annotated-code>\n"
        + CODE
        + '\n<script type="application/json">'
        + json.dumps(ANNOS)
        + "</script></oku-annotated-code>"
    ),
    "anno-source-list": (
        "<oku-annotated-code>\n"
        + CODE
        + '\n<ol class="okc-anno-source">'
        + "".join("<li>%s</li>" % a["content"] for a in ANNOS)
        + "</ol></oku-annotated-code>"
    ),
}

PROBE = """(html) => {
  const host = document.createElement('div');
  host.innerHTML = html;
  document.querySelector('main').appendChild(host);
  return new Promise(r => setTimeout(() => {
    const el = host.querySelector('oku-annotated-code');
    const code = el.querySelector('pre code');
    // The hover tooltips are legitimately parented inside the code
    // element (one per line gutter slot, position: fixed, 0x0 until
    // hovered), so raw textContent would report them as code. Read the
    // program from a clone with the tips removed.
    let program = null;
    if (code) {
      const clone = code.cloneNode(true);
      clone.querySelectorAll('.okc-anno-tip').forEach(n => n.remove());
      program = clone.textContent;
    }
    r({
      code: program,
      panel: [...el.querySelectorAll('.okc-anno-item .okc-anno-body')]
               .map(n => n.textContent.trim()),
    });
  }, 600));
}"""


@pytest.mark.parametrize("shape", sorted(ISLANDS))
def test_annotations_reach_the_panel_and_not_the_code(page, site_url, shape):
    """The program is the program. Every annotation body belongs in the
    side panel exactly once, and none of it belongs in the code."""
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.wait_for_timeout(600)
    out = page.evaluate(PROBE, ISLANDS[shape])

    assert out["panel"] == [a["content"] for a in ANNOS], out["panel"]
    for anno in ANNOS:
        assert anno["content"] not in out["code"], (shape, out["code"])
    # The JSON envelope leaks even when the bodies happen not to — the
    # whole `<script>` text lands in the code when textContent is taken
    # raw, keys and punctuation included.
    assert '"id"' not in out["code"], out["code"]
    assert "def load(path):" in out["code"], out["code"]


@pytest.mark.parametrize("shape", sorted(ISLANDS))
def test_the_program_keeps_its_own_line_count(page, site_url, shape):
    """Three lines in, three lines out. The regression showed up as a
    code block taller than its program — the symptom that reached us
    was a page inflated by the annotation text it had swallowed."""
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.wait_for_timeout(600)
    out = page.evaluate(PROBE, ISLANDS[shape])
    assert out["code"].strip().count("\n") + 1 == 3, out["code"]
