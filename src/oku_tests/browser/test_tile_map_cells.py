"""Every region on the tile map gets its own cell.

The grid was a hand-written `{code: [col, row]}` map and 14 of its
cells held more than one country: AR over CL, NO over SE over DK, CZ
over SK over HU over RO. 18 of the 59 regions were drawn at the same
coordinates as another and painted over by it — the value was in the
chart, the tooltip answered for it, and the reader had no way to know
the tile was there. Found by `tools/text_fit_audit.py`, which reported
23 pairs of labels drawn on top of each other and was right.

The map is written as a picture now, one token per cell, so two
regions cannot share one. This asks the rendered result rather than the
source, because the question is what the reader sees: every code drawn
once, and no two codes at the same point.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

from .._examples import examples
from ._wait import page_quiet

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tilemap") / "docs"
    docs.mkdir(parents=True)
    payload = examples()["charts"]["geo"]
    (docs / "page.md").write_text(
        "---\ntitle: Tiles\nsummary: One tile map.\n---\n\n## Map {#c}\n\n"
        "```oku-chart\n" + json.dumps(payload, separators=(",", ":")) + "\n```\n",
        encoding="utf-8",
    )
    (docs / "page.html").write_text(cli._stub_for("Tiles"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture()
def tiles(built, browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    got = page.evaluate(
        """() => [...document.querySelectorAll('#c svg text.okc-geo-code, #c svg text.okc-geo-code-off')]
             .map((t) => { const r = t.getBoundingClientRect();
               return { code: t.textContent.trim(),
                        x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
                        on: t.classList.contains('okc-geo-code') }; })"""
    )
    yield got
    context.close()


def test_the_map_draws_its_whole_grid(tiles):
    """Not vacuous: the assertions below are about a map that is there."""
    assert len(tiles) >= 50, f"only {len(tiles)} tiles drawn"


def test_no_two_regions_share_a_cell(tiles):
    seen: dict[tuple[int, int], str] = {}
    clashes = []
    for t in tiles:
        # Cells are 54x36, so a 6px grid is far finer than one cell and
        # still immune to sub-pixel drift.
        key = (round(t["x"] / 6), round(t["y"] / 6))
        if key in seen:
            clashes.append(f"{seen[key]} and {t['code']} at {t['x']},{t['y']}")
        seen[key] = t["code"]
    assert clashes == [], f"regions drawn on top of each other: {clashes}"


def test_every_region_is_drawn_once(tiles):
    from collections import Counter

    twice = [c for c, n in Counter(t["code"] for t in tiles).items() if n > 1]
    assert twice == [], f"drawn more than once: {twice}"


def test_every_region_in_the_payload_gets_a_coloured_tile(tiles):
    want = {r["id"] for r in examples()["charts"]["geo"]["regions"]}
    got = {t["code"] for t in tiles if t["on"]}
    assert want <= got, f"in the data and not on the map: {sorted(want - got)}"
