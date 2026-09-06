"""A reader can pull a network graph apart, with a pointer or without one.

A force-directed layout packs a small graph into overlapping bundles, so
the figure needs the reader to be able to move a node and have the edges
follow. The pointer half shipped. The keyboard half did not, and the gap
was invisible because the node group carries `tabindex="0"` — Tab reached
every node in the graph and every key did nothing.

That is the `role="button"` defect the filepath chip had, in a different
element: focus is a promise. It is worse here, because untangling was the
whole point of the interaction and there was no other way to do it — a
reader on a keyboard could look at the tangle and nothing else.

There is no test here for the `preventDefault` on the arrow key. It was
written and then deleted: measured on a genuinely scrollable document
(3100px of scroll available, nothing hidden on `html` or `body`), a
Chromium `<g>` with `tabindex="0"` does not scroll the page on an arrow
key WITH or WITHOUT it — so the assertion passed either way and was a
test of the environment, which is the shape this repo has a rule about.
The call stays in the kit as the correct thing to do; nothing here
claims it was observed doing anything.

Both paths go through one mover, so the properties below are asserted
against whichever one moved the node. Three things have to change
together or the figure lies: the group's transform (where it is drawn),
its `data-x`/`data-y` (where the next move starts from), and every edge
that touches it (what it is connected to).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from . import _wait

pytestmark = pytest.mark.browser

PAGE_MD = """---
title: Network
summary: A graph small enough to tangle and worth untangling.
---

## Graph {#g}

```oku-chart
{"type":"network","title":"Services","nodes":[{"id":"a","label":"api"},{"id":"b","label":"db"},{"id":"c","label":"cache"},{"id":"d","label":"queue"},{"id":"e","label":"worker"}],"links":[{"source":"a","target":"b"},{"source":"a","target":"c"},{"source":"b","target":"d"},{"source":"d","target":"e"},{"source":"e","target":"a"}]}
```
"""

# Everything one move has to keep in step, read in one pass. A test that
# read them separately could pass while they disagreed.
STATE = """(id) => {
  const n = document.querySelector(`.okc-network-node[data-node-id="${id}"]`);
  if (!n) return null;
  const m = /translate\\(([-\\d.]+),([-\\d.]+)\\)/.exec(n.getAttribute('transform') || '');
  return {
    data: [+n.getAttribute('data-x'), +n.getAttribute('data-y')],
    drawn: m ? [+m[1], +m[2]] : null,
    edges: [...document.querySelectorAll('.okc-network line')]
      .filter((e) => e.getAttribute('data-source') === id || e.getAttribute('data-target') === id)
      .map((e) => [
        e.getAttribute('data-source') === id ? 'from' : 'to',
        +e.getAttribute(e.getAttribute('data-source') === id ? 'x1' : 'x2'),
        +e.getAttribute(e.getAttribute('data-source') === id ? 'y1' : 'y2'),
      ]),
  };
}"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("network") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Network"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture
def page_with_graph(built, browser):
    """Function-scoped: every test here moves a node, and a shared page
    would make each one depend on what the last one left behind."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.goto(built.as_uri(), wait_until="load")
    _wait.until(
        pg,
        "() => document.querySelectorAll('.okc-network-node').length === 5",
        what="the graph drew all five nodes",
    )
    yield pg
    ctx.close()


def _state(pg, node_id="a"):
    return pg.evaluate(STATE, node_id)


def _centre(pg, node_id="a"):
    box = pg.locator(f'.okc-network-node[data-node-id="{node_id}"]').bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _moved(before, after):
    """Every field that has to move together, as one answer."""
    return {
        "data": after["data"] != before["data"],
        "drawn": after["drawn"] != before["drawn"],
        "edges": [a[1:] != b[1:] for a, b in zip(after["edges"], before["edges"], strict=True)],
    }


def test_dragging_a_node_takes_its_edges_with_it(page_with_graph):
    """The pointer half, which shipped — pinned here because the
    keyboard half now shares its mover, and a refactor that fixed one
    could silently break the other."""
    pg = page_with_graph
    before = _state(pg)
    assert len(before["edges"]) == 3, before

    x, y = _centre(pg)
    pg.mouse.move(x, y)
    pg.mouse.down()
    pg.mouse.move(x + 90, y - 60, steps=8)
    pg.mouse.up()

    after = _state(pg)
    got = _moved(before, after)
    assert got == {"data": True, "drawn": True, "edges": [True, True, True]}, (before, after)
    # Drawn and recorded are the same place, or the next move starts
    # from somewhere the reader cannot see.
    assert after["drawn"] == pytest.approx(after["data"], abs=0.1)


def test_a_focused_node_moves_on_an_arrow_key(page_with_graph):
    """The half that was missing. `tabindex="0"` is already on the group,
    so the node took focus and then refused to do anything — measured
    before the fix: ArrowRight changed nothing at all."""
    pg = page_with_graph
    pg.locator('.okc-network-node[data-node-id="a"]').focus()
    assert pg.evaluate("() => document.activeElement.classList.contains('okc-network-node')")

    before = _state(pg)
    pg.keyboard.press("ArrowRight")
    after = _state(pg)

    assert after["data"][0] > before["data"][0], (before, after)
    assert after["data"][1] == pytest.approx(before["data"][1]), "ArrowRight moved it vertically"
    assert _moved(before, after)["edges"] == [True, True, True], (before, after)


@pytest.mark.parametrize(
    ("key", "axis", "sign"),
    [("ArrowRight", 0, 1), ("ArrowLeft", 0, -1), ("ArrowDown", 1, 1), ("ArrowUp", 1, -1)],
)
def test_each_arrow_goes_the_way_it_points(page_with_graph, key, axis, sign):
    """Four keys, four directions, and the axis that should NOT move is
    asserted too — a transposed pair passes any test that only checks
    that something changed."""
    pg = page_with_graph
    pg.locator('.okc-network-node[data-node-id="a"]').focus()
    before = _state(pg)
    pg.keyboard.press(key)
    after = _state(pg)

    other = 1 - axis
    assert (after["data"][axis] - before["data"][axis]) * sign > 0, (key, before, after)
    assert after["data"][other] == pytest.approx(before["data"][other]), (key, before, after)


def test_shift_moves_further_than_the_bare_key(page_with_graph):
    """One press has to be visible and crossing the figure must not take
    thirty of them, which is one step size for two jobs. Shift is the
    second, and it is the convention every canvas editor already uses."""
    pg = page_with_graph
    pg.locator('.okc-network-node[data-node-id="a"]').focus()

    start = _state(pg)["data"][0]
    pg.keyboard.press("ArrowRight")
    one = _state(pg)["data"][0] - start
    pg.keyboard.press("Shift+ArrowRight")
    shifted = _state(pg)["data"][0] - one - start

    assert one > 0 and shifted > one, (one, shifted)
    assert shifted == pytest.approx(one * 4, abs=0.2), (one, shifted)


def test_a_node_cannot_be_pushed_off_the_figure(page_with_graph):
    """Thirty presses of one key used to leave nothing on screen to aim
    at, and neither path had a bound. A pointer at least keeps hold of
    what it took away; a key does not, so the clamp lives in the shared
    mover rather than in one of them."""
    pg = page_with_graph
    pg.locator('.okc-network-node[data-node-id="a"]').focus()
    for _ in range(40):
        pg.keyboard.press("Shift+ArrowRight")
    for _ in range(40):
        pg.keyboard.press("Shift+ArrowUp")

    box = pg.evaluate(
        """() => {
             const svg = document.querySelector('.okc-network');
             const vb = svg.getAttribute('viewBox').split(/\\s+/).map(Number);
             const n = document.querySelector('.okc-network-node[data-node-id="a"]');
             return {vb, at: [+n.getAttribute('data-x'), +n.getAttribute('data-y')]};
           }"""
    )
    vx, vy, vw, vh = box["vb"]
    x, y = box["at"]
    assert vx <= x <= vx + vw, box
    assert vy <= y <= vy + vh, box
