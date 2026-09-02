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

from ._menu import flip_theme
from ._wait import diagram_drawn, until_changed

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
    diagram_drawn(page, "#probe oku-diagram")
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

    flip_theme(page)
    _await_reflip(page, light["fill"])
    dark = page.evaluate(STATE)

    assert not dark["failed"], dark
    assert dark["fill"], dark
    assert dark["fill"] != light["fill"], f"--surface-2 rendered identically in both themes: {light['fill']}"


# ---------- the soft plates ----------
#
# `fill:var(--series-3)` under `color:var(--text)` parses fine and is
# unreadable: the ramp above is for marks, and a node is a plate with a
# label on it. --series-N-soft is the tint of the same hue, so the pair
# reads in both themes. test_colour_contrast.py computes the ratios from
# the stylesheet; this measures what a node actually renders, which is
# the half arithmetic cannot see — the substitution has to reach the
# fence, survive the parse, and re-run on the theme flip.

SOFT_SRC = (
    "flowchart LR\n"
    '  A["one"] --> B["two"]\n'
    "  classDef cat fill:var(--series-3-soft),stroke:var(--series-3),color:var(--text)\n"
    "  class A,B cat\n"
)

SOFT_STATE = """() => {
  const d = document.querySelector('#probe oku-diagram');
  const node = d.querySelector('svg .node rect, svg .node path');
  const label = d.querySelector('svg .node .nodeLabel, svg .node foreignObject span, svg .node text');
  const cs = node ? getComputedStyle(node) : null;
  return {
    failed: /Parse error/.test(d.textContent),
    fill: cs ? cs.fill : null,
    stroke: cs ? cs.stroke : null,
    label: label ? getComputedStyle(label).color : null,
  };
}"""


FILL = (
    "() => { const n = document.querySelector('#probe oku-diagram svg .node rect,"
    " #probe oku-diagram svg .node path'); return n ? getComputedStyle(n).fill : null; }"
)


def _await_reflip(page, before):
    """A theme flip re-renders the diagram, and the selector is the
    same before and after — so the question is not "is there an svg"
    but "is it the other theme's svg yet"."""
    until_changed(page, FILL, before, what="the diagram re-rendered in the other theme")


def _mount_soft(page, site_url):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.evaluate(MOUNT, SOFT_SRC)
    diagram_drawn(page, "#probe oku-diagram")
    return page.evaluate(SOFT_STATE)


def test_a_soft_plate_carries_its_label_in_both_themes(page, site_url):
    """The defect the tokens replaced: nine hardcoded pale fills kept
    their pale on a dark page, so every label sat light-on-light."""
    from ._colour import composite, contrast

    light = _mount_soft(page, site_url)
    assert not light["failed"], light
    assert light["fill"] and light["label"], light

    flip_theme(page)
    _await_reflip(page, light["fill"])
    dark = page.evaluate(SOFT_STATE)
    assert not dark["failed"], dark
    assert dark["fill"] and dark["label"], dark

    assert dark["fill"] != light["fill"], f"the plate rendered identically in both themes: {light['fill']}"

    for theme, state in (("light", light), ("dark", dark)):
        ratio = contrast(composite(state["label"], state["fill"]), composite(state["fill"], state["fill"]))
        assert ratio >= 4.5, (
            f"the node label is {ratio:.2f}:1 on its own plate in the {theme} theme "
            f"(label {state['label']} on fill {state['fill']})"
        )


def test_the_stroke_is_visible_on_the_plate_it_encloses(page, site_url):
    """The pair is authored together, so the border has to read against
    the fill and not only against the page."""
    from ._colour import composite, contrast

    state = _mount_soft(page, site_url)
    assert state["stroke"] and state["fill"], state
    ratio = contrast(composite(state["stroke"], state["fill"]), composite(state["fill"], state["fill"]))
    assert ratio >= 3.0, f"stroke {state['stroke']} on fill {state['fill']} is {ratio:.2f}:1"
