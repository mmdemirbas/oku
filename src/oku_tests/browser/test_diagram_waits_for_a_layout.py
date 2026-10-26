"""A diagram in a document that has no layout yet waits for one.

Mermaid measures every label with `getBBox()` in a scratch element on
`<body>` while it lays a diagram out, so it can only draw in a document
that has a layout. A page loaded in a frame whose box is `display:none`
has none: `innerWidth` is 0, `<body>` has no box, and every label
measures 0 x 0. Mermaid then throws — "svg element not in render tree",
"Could not find a suitable point for the given distance", "The
element's path is empty" — and the kit put an error card in place of
each diagram and counted it on the warning indicator. The cards stayed
after the frame was shown.

Reported from a board that shows built pages in an iframe: ten of a
page's fourteen diagrams became error cards, and a reload made them go
away, because by then the frame was on screen. Nothing in the source
was wrong.
"""

from __future__ import annotations

from ._wait import until

COLLECT = """
window.__okuTestWarnings = [];
window.addEventListener('oku:warnings', function (e) {
  (e.detail || []).forEach(function (d) { window.__okuTestWarnings.push(d.code + ': ' + d.msg); });
});
"""

STATE = """() => ({
  diagrams: document.querySelectorAll('oku-diagram').length,
  drawn: document.querySelectorAll('oku-diagram .okd-render svg').length,
  cards: document.querySelectorAll('oku-diagram .okd-error').length,
  warnings: window.__okuTestWarnings.filter(w => /^(mermaid|diagram)-/.test(w)),
})"""


def test_a_diagram_in_a_hidden_frame_draws_once_the_frame_is_shown(page, site_url):
    page.add_init_script(COLLECT)
    page.set_content(
        '<div id="h" style="display:none">'
        f'<iframe src="{site_url}/docs/architecture.html" style="width:1200px;height:900px"></iframe>'
        "</div>"
    )
    frame = page.wait_for_selector("iframe", state="attached").content_frame()
    until(frame, "() => window.__okuRendered === true", what="the page rendered inside the hidden frame")

    # The precondition, asserted: inside this frame there is no layout.
    # Without it the test would pass on a frame that was never hidden.
    assert frame.evaluate("() => [innerWidth, document.body.getClientRects().length]") == [0, 0]

    # The window in which the defect acts: Mermaid loads and, before the
    # fix, lays every diagram out against a document with no layout.
    # Too short a window passes a broken kit; it cannot fail a fixed one.
    frame.evaluate("() => __mermaidLoader.load().then(() => new Promise(r => setTimeout(r, 1500)))")

    page.evaluate("() => { document.getElementById('h').style.display = 'block'; }")
    until(
        frame,
        "() => [...document.querySelectorAll('oku-diagram')].every(d => d.querySelector('.okd-render svg, .okd-error'))",
        timeout=30000,
        what="every diagram drew or failed after the frame was shown",
    )

    state = frame.evaluate(STATE)
    assert state["diagrams"] >= 2, state
    assert state["cards"] == 0, state
    assert state["drawn"] == state["diagrams"], state
    assert state["warnings"] == [], state
