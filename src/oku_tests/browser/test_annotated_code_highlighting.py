"""`oku-annotated-code` survives every Prism pass over it.

Prism highlights by reading `element.textContent` and writing
`element.innerHTML`. Once this element has built, the code element also
holds its marker chips and the hover tooltips carrying the annotation
bodies — so a second pass reads the commentary as program text,
highlights it as source, and wipes the chips on the way out. Reported
from another project as a page inflated by 25,000px.

More than one driver highlights a given block: the element does its own,
and the page-level sweep runs over the whole document on `oku:rendered`.
Neither can see the other's timing, so the guard lives in Prism's
`before-sanity-check` hook — the one point every path goes through.

The fixture uses **python**, and that is load-bearing. The kit eagerly
preloads the grammars most often nested in others (javascript, css,
bash, json, yaml), so a javascript block has its grammar in hand on the
first pass and never takes the second one. Every page in this repo's own
docs uses javascript, which is why the defect never showed up here.
"""

from __future__ import annotations

from ._wait import page_quiet

import json

import pytest

CODE = "def load(path):\n    data = read(path)   (1)\n    return parse(data)  (2)\n"
ANNOS = [
    {"id": 1, "content": "Reads the whole file into memory before anything else."},
    {"id": 2, "content": "Parsing is where the schema is enforced."},
]

ISLAND = (
    '<oku-annotated-code language="python">'
    '<script type="text/x-code">' + CODE + "</script>"
    '<script type="application/json">' + json.dumps(ANNOS) + "</script>"
    "</oku-annotated-code>"
)

# The program, read the way a reader reads it. Tooltips are legitimately
# parented inside the code element (one per gutter cell, position fixed,
# 0x0 until hovered), so raw textContent would report them as code.
STATE = """() => {
  const el = document.querySelector('#probe oku-annotated-code');
  const code = el.querySelector('pre code');
  const clone = code.cloneNode(true);
  clone.querySelectorAll('.okc-anno-tip').forEach(n => n.remove());
  return {
    program: clone.textContent,
    codeHeight: Math.round(code.getBoundingClientRect().height),
    lineHeight: Math.round(
      (code.querySelector(':scope > .okt-code-line') || code).getBoundingClientRect().height),
    lines: code.querySelectorAll(':scope > .okt-code-line').length,
    markers: el.querySelectorAll('.okc-anno-marker').length,
    tips: el.querySelectorAll('.okc-anno-tip').length,
    items: el.querySelectorAll('.okc-anno-item').length,
    highlighted: !!code.querySelector('.token'),
    built: !!el._okuMarkersBuilt,
  };
}"""


def _mount(page, site_url):
    page.set_viewport_size({"width": 1100, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.evaluate(
        """(html) => {
             const host = document.createElement('div');
             host.id = 'probe';
             host.innerHTML = html;
             document.querySelector('main').appendChild(host);
           }""",
        ISLAND,
    )
    page.wait_for_selector("#probe oku-annotated-code pre code")
    # Long enough for a CDN grammar fetch plus the autoloader's second
    # pass — the window the defect lived in.
    page_quiet(page)
    return page.evaluate(STATE)


def test_the_annotations_never_become_part_of_the_program(page, site_url):
    """The reported symptom. Every annotation body belongs in the side
    panel; none of it belongs in the code."""
    state = _mount(page, site_url)

    assert state["items"] == len(ANNOS), state["items"]
    for anno in ANNOS:
        assert anno["content"] not in state["program"], state["program"]
    assert state["program"].startswith("def load(path):"), state["program"]


def test_the_block_stays_the_height_of_its_program(page, site_url):
    """The defect presented as size, not as wrong text: a 3-line program
    came back 3366px tall, its own commentary highlighted as source.
    Three lines cannot exceed four line-heights."""
    state = _mount(page, site_url)

    assert state["lines"] in (3, 4), state["lines"]  # trailing newline may add one
    assert state["codeHeight"] <= state["lineHeight"] * 5, state


def test_a_marker_in_live_code_still_becomes_a_chip(page, site_url):
    """`(1)` sitting in code rather than in a comment.

    Prism tokenises `(`, `1` and `)` into three separate elements, so the
    marker spans three text nodes. Matching per text node found nothing
    and left `(1)` in the program as literal text with no chip anywhere —
    silently. It worked only where the author had put the marker inside a
    comment, which is one token and therefore one text node."""
    state = _mount(page, site_url)

    assert state["markers"] == len(ANNOS), state
    assert "(1)" not in state["program"], state["program"]
    assert "(2)" not in state["program"], state["program"]


def test_a_later_highlight_pass_leaves_the_built_block_alone(page, site_url):
    """The fix itself, exercised directly rather than waited for.

    Any driver may sweep the document again — the page-level highlightAll
    on `oku:rendered`, a re-render, the autoloader landing late. Once the
    block is built, Prism must return without touching it."""
    state = _mount(page, site_url)
    if not state["highlighted"]:
        pytest.skip("Prism did not load (no CDN reachable) — nothing to re-run")
    assert state["built"], "the element never marked itself built"

    after = page.evaluate(
        """() => {
             const code = document.querySelector('#probe oku-annotated-code pre code');
             window.Prism.highlightElement(code);
             const el = document.querySelector('#probe oku-annotated-code');
             const clone = code.cloneNode(true);
             clone.querySelectorAll('.okc-anno-tip').forEach(n => n.remove());
             return {
               program: clone.textContent,
               markers: el.querySelectorAll('.okc-anno-marker').length,
               tips: el.querySelectorAll('.okc-anno-tip').length,
               codeHeight: Math.round(code.getBoundingClientRect().height),
             };
           }"""
    )

    assert after["markers"] == state["markers"], after
    assert after["tips"] == state["tips"], after
    assert after["codeHeight"] == state["codeHeight"], after
    for anno in ANNOS:
        assert anno["content"] not in after["program"], after["program"]


def test_a_block_with_no_annotations_still_highlights(page, site_url):
    """The guard must not turn into "never highlight an annotated-code".
    A block that has not built yet is ordinary code and gets the ordinary
    treatment."""
    page.set_viewport_size({"width": 1100, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.evaluate(
        """(code) => {
             const host = document.createElement('div');
             host.id = 'plain';
             host.innerHTML =
               '<oku-annotated-code language="python">'
               + '<script type="text/x-code">' + code + '</script>'
               + '</oku-annotated-code>';
             document.querySelector('main').appendChild(host);
           }""",
        "def load(path):\n    return parse(read(path))\n",
    )
    page.wait_for_selector("#plain oku-annotated-code pre code")
    page_quiet(page)
    out = page.evaluate(
        """() => {
             const code = document.querySelector('#plain oku-annotated-code pre code');
             return { highlighted: !!code.querySelector('.token'), text: code.textContent };
           }"""
    )

    if not out["highlighted"]:
        pytest.skip("Prism did not load (no CDN reachable) — nothing to assert")
    assert "def load(path):" in out["text"], out["text"]
