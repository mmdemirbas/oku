"""The manifest is emitted in the order the tree is drawn in.

`compute_manifest` walks the filesystem, so its natural output is path
order. Everything downstream assumed otherwise: `llms.txt` re-sorted for
itself, `chrome.js` re-sorts at render time, and `_pick_open_target`
took `pages[0]` on the stated understanding that it was the tree's first
row. It was the alphabetically first page instead — `architecture.html`
(order 40) ahead of `index.html` (order 1).

It stayed invisible in this repo because only one HTML stub is committed,
so the loop found nothing to match until it reached that stub. A project
that commits its stubs — which is what `oku init` produces — opens on
whichever page happens to sort first by filename.

`nav_sort_key` is now the single rule. These tests hold the emitted order
against it, hold `_pick_open_target` against the emitted order, and hold
`chrome.js`'s render-time comparator against the Python one by running
both over the same list.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from oku import cli

KIT = cli.KIT_DIR / "chrome.js"

PAGE = """---
title: {title}
summary: A page.
{extra}---

## Body {{#body}}

Text.
"""


def _write(root: Path, name: str, title: str, order: int | None = None) -> None:
    extra = f"order: {order}\n" if order is not None else ""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.format(title=title, extra=extra), encoding="utf-8")
    path.with_suffix(".html").write_text(cli._stub_for(title), encoding="utf-8")


@pytest.fixture
def tree(tmp_path):
    """Filename order, `order` order and title order all disagree, which
    is the only shape that can tell the three rules apart."""
    root = tmp_path / "docs"
    root.mkdir()
    _write(root, "index.md", "Home", order=1)
    _write(root, "architecture.md", "Architecture", order=40)
    _write(root, "reference.md", "Reference", order=20)
    _write(root, "zebra.md", "Zebra")  # no order — parks at the end
    _write(root, "apple.md", "Apple")  # no order, sorts before Zebra
    _write(root, "guide/deep.md", "Deep", order=5)
    return root


def test_the_manifest_is_emitted_in_tree_order(tree):
    pages = cli.compute_manifest(tree)["pages"]
    assert [p["path"] for p in pages] == [
        "index.html",
        "reference.html",
        "architecture.html",
        "apple.html",
        "zebra.html",
        "guide/deep.html",
    ]


def test_the_first_page_is_the_one_serve_opens(tree):
    """`_pick_open_target` reads `pages[0]` and calls it the top of the
    tree. That sentence is only true if the manifest is sorted."""
    htmls = sorted(tree.rglob("*.html"))
    assert cli._pick_open_target(htmls, tree, tree) == (tree / "index.html").resolve()


def test_llms_txt_lists_the_same_order(tree):
    body = cli.compute_llms_txt(tree)
    listed = [line.split("](")[1].split(")")[0] for line in body.splitlines() if line.startswith("- [")]
    assert listed == [p["path"] for p in cli.compute_manifest(tree)["pages"]]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_sorts_it_the_same_way():
    """chrome.js re-sorts the manifest at render time — it has to, since
    a walked tree (no manifest at all) arrives unsorted. Two comparators
    that disagree would put `llms.txt` and the sidebar in different
    orders, which is the kind of drift nobody notices until an AI reader
    and a human reader describe the same site differently.

    It compares within one parent because that is the scope chrome.js
    sorts in: it groups by parent afterwards, so `parent` is not in its
    key. Same rows, same order, is the assertion.
    """
    probe = [
        {"path": "z.html", "title": "Zebra"},
        {"path": "a.html", "title": "Apple"},
        {"path": "r.html", "title": "Reference", "order": 20},
        {"path": "i.html", "title": "Home", "order": 1},
        {"path": "c.html", "title": "architecture", "order": 40},
    ]
    # Anchored on the comparator's own body, not on `pages.sort(` — the
    # walked-tree fallback a few hundred lines up sorts by path under
    # that same name, and matching it would test the wrong rule.
    src = KIT.read_text(encoding="utf-8")
    inner = src.index("var oa = a.order !== undefined")
    start = src.rindex("pages.sort(function (a, b) {", 0, inner)
    end = src.index("\n    });", start) + len("\n    });")
    body = textwrap.dedent(src[start:end]).replace("pages.sort", "rows.sort", 1)

    script = (
        "const rows = "
        + json.dumps(probe)
        + ";\n"
        + body
        + "\nconsole.log(JSON.stringify(rows.map(r => r.path)));\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout.strip()

    expected = [e["path"] for e in sorted(probe, key=cli.nav_sort_key)]
    assert json.loads(out) == expected
