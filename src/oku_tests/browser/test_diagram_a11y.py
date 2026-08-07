"""A rendered diagram has a name, and hands out no anonymous tab stops.

Three defects sat on every diagram at once, and all three are invisible
unless you arrive with a keyboard or a screen reader:

- `.okd-render` is labelled `Diagram loading` before mermaid runs, and
  nothing replaced the label afterwards. The diagram announced itself as
  loading for the rest of the session.
- the `<svg>` carries `role="graphics-document document"` with no
  accessible name, while the caption naming it sits right underneath.
- mermaid marks its node groups `tabindex="0"`. Measured on the built
  docs/architecture.html: 10 stops per diagram, 60 on the page, every
  one unnamed and none of them doing anything — the kit gives those
  groups no keyboard behaviour.

Reachable and anonymous is worse than either alone, which is why the
tab-stop half is asserted rather than left as a nicety.
"""

from __future__ import annotations

SRC = 'flowchart LR\n  A["write"] --> B["read"]\n  B --> C["archive"]\n'

MOUNT = """(src) => {
  const host = document.createElement('div');
  host.id = 'a11y-probe';
  const el = document.createElement('oku-diagram');
  el.setAttribute('caption', 'How a page reaches its reader');
  const s = document.createElement('script');
  s.type = 'text/x-mermaid';
  s.textContent = src;
  el.appendChild(s);
  host.appendChild(el);
  document.querySelector('main').appendChild(host);
}"""

STATE = """() => {
  const d = document.querySelector('#a11y-probe oku-diagram');
  const render = d.querySelector(':scope > .okd-render');
  const svg = d.querySelector('svg');
  return {
    failed: /Parse error/.test(d.textContent),
    nodes: d.querySelectorAll('svg .node').length,
    wrapperLabel: render ? render.getAttribute('aria-label') : null,
    svgLabel: svg ? svg.getAttribute('aria-label') : null,
    anonymousTabStops: d.querySelectorAll('g[tabindex="0"]').length,
    totalTabStops: d.querySelectorAll('[tabindex="0"]').length,
  };
}"""


def _mount(page, site_url):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.evaluate(MOUNT, SRC)
    # Wait for the render to FINISH, not for a number of milliseconds.
    # Mermaid arrives from a CDN, so a timeout long enough on an idle
    # machine is not long enough on a loaded one — and a half-rendered
    # diagram has the SVG in the DOM before the post-render passes have
    # run over it, which is exactly the state that made this flake.
    # `_rendered` is the element's own "all passes done" flag.
    page.wait_for_function(
        "() => { const d = document.querySelector('#a11y-probe oku-diagram');"
        "        return !!d && (d._rendered || /Parse error/.test(d.textContent)); }",
        timeout=30000,
    )
    return page.evaluate(STATE)


def test_a_rendered_diagram_carries_its_caption_as_its_name(page, site_url):
    state = _mount(page, site_url)

    assert not state["failed"], state
    assert state["nodes"] == 3, state
    assert state["wrapperLabel"] == "How a page reaches its reader", (
        f"the wrapper kept its pre-render label: {state}"
    )
    assert state["svgLabel"] == "How a page reaches its reader", (
        f"the svg has a graphics-document role and no name: {state}"
    )


def test_a_diagram_hands_out_no_anonymous_tab_stops(page, site_url):
    """The kit gives mermaid's node groups no keyboard behaviour, so a
    stop on one costs a reader a press and returns nothing."""
    state = _mount(page, site_url)

    assert not state["failed"], state
    assert state["anonymousTabStops"] == 0, f"mermaid's node groups are still focusable: {state}"
