"""A diagram takes its colour from the kit's tokens, like every other
hand-drawn figure.

Mermaid's classDef/style grammar takes CSS *values*, not CSS
*functions* — it has no production for `(`, so

    classDef fmt fill:var(--surface-2),stroke:var(--border)

dies with `Expecting 'SEMI', 'NEWLINE', … got '(-'` and the whole
diagram is replaced by a parse-error card. Reported from another
project, on a standalone build.

That put the kit at odds with its own instruction: every hand-drawn
figure is told to drive its colours from tokens so it follows the accent
and both themes, and a Mermaid diagram was the one place that advice did
not work. The tokens are resolved at hand-off to Mermaid — not in the
source cleaning — so a re-render on `oku:theme-changed` re-reads them
and the colour tracks the theme instead of freezing at first paint.
"""

from __future__ import annotations

SRC = (
    "flowchart LR\\n"
    '  A["one"] --> B["two"]\\n'
    "  classDef fmt fill:var(--surface-2),stroke:var(--border)\\n"
    "  class A,B fmt\\n"
)

MOUNT = """(src) => {
  const host = document.createElement('div');
  host.id = 'probe';
  const el = document.createElement('oku-diagram');
  const s = document.createElement('script');
  s.type = 'text/x-mermaid';
  s.textContent = src;
  el.appendChild(s);
  host.appendChild(el);
  document.querySelector('main').appendChild(host);
}"""

STATE = """() => {
  const d = document.querySelector('#probe oku-diagram');
  const node = d.querySelector('svg .node rect, svg .node path');
  return {
    failed: /Parse error/.test(d.textContent),
    nodes: d.querySelectorAll('svg .node').length,
    fill: node ? getComputedStyle(node).fill : null,
  };
}"""


def _mount(page, site_url):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.evaluate(MOUNT, SRC.replace("\\n", "\n"))
    page.wait_for_timeout(4000)
    return page.evaluate(STATE)


def test_a_kit_token_in_a_classdef_does_not_break_the_parse(page, site_url):
    state = _mount(page, site_url)

    assert not state["failed"], "the diagram was replaced by a parse-error card"
    assert state["nodes"] == 2, state


def test_the_resolved_colour_follows_the_theme(page, site_url):
    """Resolved at hand-off rather than baked into the source, so the
    re-render every diagram does on a theme flip picks up the other
    theme's value. Baked in, the diagram would keep the outgoing
    palette — the defect the announceTheme rule exists to prevent."""
    light = _mount(page, site_url)
    assert light["fill"], light

    page.evaluate("() => document.querySelector('.theme-toggle').click()")
    page.wait_for_timeout(4000)
    dark = page.evaluate(STATE)

    assert not dark["failed"], dark
    assert dark["fill"], dark
    assert dark["fill"] != light["fill"], f"--surface-2 rendered identically in both themes: {light['fill']}"
