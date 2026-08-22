"""A file the page points at has to travel with the page.

`![tiny](tiny.png)` beside its `.md` built clean and shipped broken: the
reference survived into the page, the file was copied nowhere, and the
build printed nothing. `oku check` passed, because the image was there —
in the SOURCE directory, which is the one place a preview resolves it
from. The artifact that gets handed over is the one that is missing it,
and that is the output nobody re-opens before sending.

Both trees now carry what a page references. `dist/site` copies the file
and keeps its path, so the relative href still points at it. A standalone
page inlines it as a `data:` URI, because the whole promise of that tree
is one file you can send — an image copied beside it is an image the
reader does not receive.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
from pathlib import Path

import pytest

from oku import cli

# 1x1 and 8x8 PNGs — real files, so mimetype detection is exercised.
PNG_8 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4"
    "AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII="
)

PAGE_MD = """---
title: Figures
summary: A page that points at files beside it.
---

## Beside the page {#beside}

![tiny](tiny.png)

## In a subdirectory {#sub}

![shot](img/shot.png)

## In an island {#island}

<figure class="okt-card">
<img src="img/shot.png" alt="in an island">
</figure>

## Somebody else's host {#remote}

![remote](https://example.invalid/not-ours.png)
"""

NESTED_MD = """---
title: Nested
summary: A page one level down pointing back up.
---

## Up one {#up}

![tiny](../tiny.png)
"""


def _tree(root: Path) -> Path:
    docs = root / "docs"
    (docs / "img").mkdir(parents=True)
    (docs / "sub").mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "sub" / "nested.md").write_text(NESTED_MD, encoding="utf-8")
    (docs / "tiny.png").write_bytes(PNG_8)
    (docs / "img" / "shot.png").write_bytes(PNG_8)
    (docs / "page.html").write_text(cli._stub_for("Figures"), encoding="utf-8")
    (docs / "sub" / "nested.html").write_text(cli._stub_for("Nested"), encoding="utf-8")
    return docs


def _build(docs: Path) -> None:
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)


@pytest.fixture
def built(tmp_path: Path) -> Path:
    docs = _tree(tmp_path)
    _build(docs)
    return docs / "dist"


# ---------- the site tree keeps the file and its path ----------


def test_the_site_tree_carries_the_asset(built: Path) -> None:
    """The reproduction from BUGS.md, at its smallest: after a build,
    `find dist -name '*.png'` was empty."""
    assert (built / "site" / "tiny.png").read_bytes() == PNG_8


def test_the_site_tree_keeps_the_path_the_href_uses(built: Path) -> None:
    """A copy under a flattened name is a copy the relative href in the
    page does not point at."""
    assert (built / "site" / "img" / "shot.png").read_bytes() == PNG_8


def test_a_page_one_level_down_resolves_its_own_relative_href(built: Path) -> None:
    """`../tiny.png` from `sub/nested.md` is the same file as `tiny.png`
    from `page.md` — one copy, at the path both hrefs reach."""
    assert (built / "site" / "tiny.png").exists()
    assert not (built / "site" / "sub" / "tiny.png").exists()


# ---------- the standalone tree carries the BYTES ----------


def test_the_standalone_page_inlines_the_asset(built: Path) -> None:
    html = (built / "standalone" / "page.html").read_text(encoding="utf-8")
    assert "data:image/png;base64," in html
    assert base64.b64encode(PNG_8).decode() in html


def test_the_standalone_page_no_longer_points_at_a_file_beside_it(built: Path) -> None:
    """The point of the tree is one file you can send. A `src` naming a
    sibling is a promise the reader's copy cannot keep."""
    html = (built / "standalone" / "page.html").read_text(encoding="utf-8")
    body = html.split('id="__oku_page__"', 1)[1]
    assert not re.search(r'"[^"]*\bimg/shot\.png"', body), "a page-relative asset href survived"
    assert "](tiny.png)" not in body


def test_an_island_img_is_inlined_too(built: Path) -> None:
    """An island is the escape hatch, not an exemption — its `<img>` is
    the same reference by a different spelling."""
    html = (built / "standalone" / "page.html").read_text(encoding="utf-8")
    assert 'src=\\"img/shot.png\\"' not in html and 'src="img/shot.png"' not in html


def test_somebody_elses_host_is_left_alone(built: Path) -> None:
    html = (built / "standalone" / "page.html").read_text(encoding="utf-8")
    assert "https://example.invalid/not-ours.png" in html


# ---------- the cap, and what happens past it ----------


def test_an_asset_over_the_cap_is_copied_beside_the_page(tmp_path, monkeypatch, capsys) -> None:
    """Inlining a 20 MB screenshot into every page that shows it is not
    a service to anyone. Past the cap the file is copied and the build
    says so, because the page has stopped being one file."""
    monkeypatch.setattr(cli, "MAX_INLINE_ASSET_BYTES", 64)
    docs = _tree(tmp_path)
    _build(docs)
    out = capsys.readouterr().out

    assert (docs / "dist" / "standalone" / "tiny.png").read_bytes() == PNG_8
    html = (docs / "dist" / "standalone" / "page.html").read_text(encoding="utf-8")
    assert "data:image/png;base64," not in html
    assert "tiny.png" in out and "not inlined" in out


def test_the_site_tree_does_not_care_about_the_cap(tmp_path, monkeypatch) -> None:
    """A site serves its files; only the send-as-file tree has a reason
    to inline, so the cap must not decide what the site carries."""
    monkeypatch.setattr(cli, "MAX_INLINE_ASSET_BYTES", 1)
    docs = _tree(tmp_path)
    _build(docs)
    assert (docs / "dist" / "site" / "tiny.png").read_bytes() == PNG_8


# ---------- the collector, directly ----------


def test_an_asset_outside_the_tree_is_reported_not_copied(tmp_path) -> None:
    """Copying it into the site would have to invent a path for it, and
    a silently invented path is how two files end up disagreeing about
    which one the page shows."""
    docs = _tree(tmp_path)
    (tmp_path / "outside.png").write_bytes(PNG_8)
    (docs / "outsider.md").write_text(
        "---\ntitle: Outsider\nsummary: Points above the tree.\n---\n\n## X {#x}\n\n![up](../outside.png)\n",
        encoding="utf-8",
    )
    page = cli.md_to_v2_page((docs / "outsider.md").read_text(encoding="utf-8"))
    assets, outside = cli.collect_page_assets(page, docs / "outsider.md", docs)
    assert assets == {}
    assert outside == ["../outside.png"]


def test_a_missing_asset_is_not_a_carried_one(tmp_path) -> None:
    docs = _tree(tmp_path)
    page = cli.md_to_v2_page("---\ntitle: T\nsummary: s\n---\n\n## X {#x}\n\n![gone](gone.png)\n")
    assets, outside = cli.collect_page_assets(page, docs / "p.md", docs)
    assert assets == {}
    assert outside == []  # `oku check` already reports it as an unresolved link


def test_a_code_sample_of_an_image_reference_is_left_alone(tmp_path) -> None:
    """A page that documents figures shows the markdown for one. Turning
    that sample into a 40 KB data: URI is how a reference page stops
    being readable — and the same href is usually a real figure two
    paragraphs down, which is what makes it reachable at all."""
    docs = _tree(tmp_path)
    (docs / "doc.md").write_text(
        "---\ntitle: Doc\nsummary: s\n---\n\n## X {#x}\n\n"
        "Write it as `![tiny](tiny.png)`, which renders:\n\n![tiny](tiny.png)\n",
        encoding="utf-8",
    )
    (docs / "doc.html").write_text(cli._stub_for("Doc"), encoding="utf-8")
    _build(docs)

    html = (docs / "dist" / "standalone" / "doc.html").read_text(encoding="utf-8")
    body = html.split('id="__oku_page__"', 1)[1].split("</script>", 1)[0]
    assert "`![tiny](tiny.png)`" in body, "the code sample was rewritten"
    assert "data:image/png;base64," in body, "the real figure was not inlined"


# ---------- the project fence ----------
#
# "Above the tree being built" and "outside the project" are different
# questions, and only the first had an answer. A repo whose docs live in
# `docs/` legitimately shows `../screenshots/x.png`, and a standalone
# page can hold it because it carries bytes rather than paths. A
# reference reaching PAST the project publishes somebody else's file to
# whoever the page is sent to — the same reason `#f/` has a fence — and
# it did so with nothing printed and a clean `oku check`.


def _fenced(tmp_path: Path) -> Path:
    """A project with a docs subtree, one image inside the project and
    above the docs root, and one outside the project entirely."""
    cli._project_root_cache.clear()
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / "shots").mkdir()
    (proj / "shots" / "inside.png").write_bytes(PNG_8)
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "outside.png").write_bytes(PNG_8)
    docs = proj / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name": "fenced"}', encoding="utf-8")
    (docs / "page.md").write_text(
        "---\ntitle: Fenced\nsummary: Two images, one fence.\n---\n\n"
        "## Inside the project {#in}\n\n![in](../shots/inside.png)\n\n"
        "## Outside it {#out}\n\n![out](../../elsewhere/outside.png)\n",
        encoding="utf-8",
    )
    (docs / "page.html").write_text(cli._stub_for("Fenced"), encoding="utf-8")
    return docs


def _check(docs: Path) -> list[dict]:
    cli._project_root_cache.clear()
    src = docs / "page.md"
    page = cli._page_from_source_file(src)
    assert page is not None
    return cli.check_pages([(src, page)], docs)


def test_an_image_outside_the_project_is_reported(tmp_path: Path) -> None:
    issues = _check(_fenced(tmp_path))
    hit = [i for i in issues if i["code"] == "image-outside"]
    assert len(hit) == 1, [i["code"] for i in issues]
    assert hit[0]["severity"] == "warning"
    assert "../../elsewhere/outside.png" in hit[0]["where"]


def test_an_image_inside_the_project_is_not_reported(tmp_path: Path) -> None:
    """The fence is the project, not the tree being built. Reporting
    `../shots/x.png` would make the check useless in every repo that
    keeps its screenshots beside its docs rather than inside them."""
    named = [i["where"] for i in _check(_fenced(tmp_path)) if i["code"] == "image-outside"]
    assert not any("inside.png" in w for w in named), named


def test_the_standalone_page_does_not_carry_the_outsider(tmp_path: Path, capsys) -> None:
    docs = _fenced(tmp_path)
    _build(docs)
    out = capsys.readouterr().out
    html = (docs / "dist" / "standalone" / "page.html").read_text(encoding="utf-8")

    assert html.count("data:image/png;base64,") == 1, "one image is inside the project, one is not"
    assert "../../elsewhere/outside.png" in html, (
        "the reference is kept — the page never loses what the author wrote"
    )
    assert "outside.png" in out and "outside the project" in out


def test_the_standalone_page_still_carries_the_insider(tmp_path: Path) -> None:
    docs = _fenced(tmp_path)
    _build(docs)
    html = (docs / "dist" / "standalone" / "page.html").read_text(encoding="utf-8")
    assert "../shots/inside.png" not in html, "an image inside the project travels with the page"


def test_an_island_src_past_the_fence_is_caught_too(tmp_path: Path) -> None:
    """The check reads hrefs through the same scanner the build carries
    them with, so an island attribute cannot be the one spelling that
    slips past."""
    docs = _fenced(tmp_path)
    (docs / "page.md").write_text(
        "---\ntitle: Fenced\nsummary: An island points out of the project.\n---\n\n"
        "## X {#x}\n\n"
        '<figure class="okt-card">\n<img src="../../elsewhere/outside.png" alt="out">\n</figure>\n',
        encoding="utf-8",
    )
    hit = [i for i in _check(docs) if i["code"] == "image-outside"]
    assert len(hit) == 1, hit


def test_somebody_elses_host_is_not_outside_the_project(tmp_path: Path) -> None:
    """A remote URL is nobody's local file. The build already leaves it
    alone; a warning here would fire on every page that shows a logo."""
    docs = _fenced(tmp_path)
    (docs / "page.md").write_text(
        "---\ntitle: Fenced\nsummary: Remote only.\n---\n\n"
        "## X {#x}\n\n![remote](https://example.invalid/x.png)\n",
        encoding="utf-8",
    )
    assert [i for i in _check(docs) if i["code"] == "image-outside"] == []
