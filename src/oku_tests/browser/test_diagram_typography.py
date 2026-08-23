"""A curly quote in a diagram label is a character, not a delimiter.

`OkuDiagram` cleans its source before handing it to Mermaid, because a
fence's body arrives through the markdown pipeline HTML-escaped: `&lt;`
for `<`, `&amp;` for `&`. Two more rewrites had been added beside those
— `[“”]` → `"` and `[‘’]` → `'` — on the reading that a smart quote is
another escaping artefact.

It is not. Mermaid's lexer treats a curly quote as an ordinary
character, so `A["the “quoted” label"]` parses and draws. Rewritten, it
becomes `A["the "quoted" label"]`, whose straight quotes close the
string one word in: `Parse error on line 2`, and the whole figure is
replaced by the source card. Measured on a page whose author had done
nothing but write typographic prose inside a node.

The conversion could only ever turn a label Mermaid accepts into one it
does not, which is why it is gone rather than narrowed. The half that
IS an escaping artefact stays, and is measured here too — deleting both
would trade this defect for the one they were added for.
"""

from __future__ import annotations

from ._wait import page_quiet, until

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

NBSP = " "

# id → (mermaid source, a string that must appear in the drawn figure)
CASES = {
    "curly-inside": ('flowchart LR\n    A["the “quoted” label"] --> B[plain]', "“quoted”"),
    "curly-as-delimiters": ("flowchart LR\n    C[“a label”] --> D[plain]", "a label"),
    "curly-single": ('flowchart LR\n    E["it’s fine"] --> F[plain]', "it’s fine"),
    # The half the cleaning exists for: a fence's body arrives through
    # the markdown pipeline escaped, and `>` is structural — an arrow
    # left as `--&gt;` is a parse error, not a cosmetic one.
    "escaped-arrow": ("flowchart LR\n    G[start] --&gt; H[end]", "start"),
    "escaped-angle-in-a-label": ('flowchart LR\n    I["a &gt; b"] --> J[plain]', "a > b"),
    "escaped-amp": ('flowchart LR\n    K["read &amp; write"] --> L[plain]', "read & write"),
    "non-breaking-space": (f'flowchart LR\n    M["one{NBSP}two"] --> N[plain]', "one two"),
}


def _md() -> str:
    out = [
        """---
title: Diagram typography
summary: Characters a label may carry, and escapes a fence must undo.
---
"""
    ]
    for name, (src, _) in CASES.items():
        out.append(f"## {name} {{#{name}}}\n\n```mermaid\n{src}\n```\n")
    return "\n".join(out)


@pytest.fixture(scope="module")
def typography_page(tmp_path_factory) -> Path:
    docs = tmp_path_factory.mktemp("diagramtype") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(_md(), encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Diagram typography"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return docs / "dist" / "standalone" / "page.html"


READ = """(names) => {
  const out = {};
  for (const name of names) {
    const sec = document.getElementById(name);
    if (!sec) { out[name] = null; continue; }
    const svg = sec.querySelector('oku-diagram svg');
    out[name] = {
      width: svg ? Math.round(svg.getBoundingClientRect().width) : 0,
      error: !!sec.querySelector('.okd-error-card'),
      text: svg ? (svg.textContent || '').replace(/\\s+/g, ' ') : '',
    };
  }
  return out;
}"""


@pytest.fixture(scope="module")
def drawn(browser, typography_page) -> dict:
    pg = browser.new_page(viewport={"width": 1200, "height": 900})
    try:
        pg.goto(typography_page.as_uri(), wait_until="load")
        until(
            pg,
            "() => [...document.querySelectorAll('oku-diagram')]"
            ".every(d => d.querySelector('svg') || /Parse error|failed to render/i.test(d.textContent))",
            timeout=30000,
            what="every diagram finished (drew or reported)",
        )
        page_quiet(pg)
        return pg.evaluate(READ, list(CASES))
    finally:
        pg.close()


def test_every_case_reached_the_page(drawn) -> None:
    """The guard: a section that never rendered would satisfy every
    assertion below by not existing."""
    assert [n for n, v in drawn.items() if v is None] == [], drawn


@pytest.mark.parametrize("name", list(CASES))
def test_the_figure_draws(name, drawn) -> None:
    got = drawn[name]
    assert not got["error"], f"{name} was replaced by the source card"
    assert got["width"] > 50, f"{name} drew a {got['width']}px figure"


@pytest.mark.parametrize("name", list(CASES))
def test_the_label_survives_the_cleaning(name, drawn) -> None:
    """Drawing is not enough: an escape left undone renders `&lt;tag&gt;`
    as visible text, and a curly quote rewritten to a straight one is a
    figure that draws with the author's punctuation changed.

    `escaped-arrow` is the one that would fail if the cleaning were
    deleted outright rather than narrowed: `--&gt;` is not an arrow."""
    assert CASES[name][1] in drawn[name]["text"], (CASES[name][1], drawn[name]["text"])
