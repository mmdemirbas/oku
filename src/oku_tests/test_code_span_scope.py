"""Where a code span ends, and what depends on the answer.

Six passes strip code spans before they look at prose: asset collection,
link checking, glossary and ext-ref resolution, file references, the
process-prose rule. A span that is measured too LONG takes real content
out of all of them at once — which is how a lone backtick in a sentence
stopped an image from being carried into a delivered page, with the
build silent because the check that would have caught it was blinded by
the same character.

The rule, and it is CommonMark's: a span may wrap across one newline —
`joinParagraph` glues a paragraph's lines before the renderer parses
inline, so the two sides agree — and never reaches past a blank line.
"""

from __future__ import annotations

import time
from pathlib import Path

from oku import cli

PAGE = """---
title: Note
summary: A page with one stray backtick in its prose.
---

## Intro {#intro}

A backtick (`) opens a code span in markdown.

![diagram](tiny.png)

See [the plan](nope.md) too.

Use the `--limit` flag when you need it.
"""


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (root / "docs" / "note.md").write_text(PAGE, encoding="utf-8")
    (root / "docs" / "tiny.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    cli._project_root_cache.clear()
    return root


def test_only_one_definition_decides_where_a_code_span_ends(tmp_path):
    """It was two, and the second silently won at every call site."""
    src = Path(cli.__file__).read_text(encoding="utf-8")
    assert src.count("_INLINE_CODE_RE = re.compile") == 1


def test_a_stray_backtick_does_not_swallow_the_image_below_it(tmp_path):
    """The delivered consequence: `collect_page_assets` never saw the
    image, so `dist/site` copied nothing and the standalone page inlined
    nothing. The reader got a broken picture and the build printed no
    warning about it."""
    root = _project(tmp_path)
    page = cli._page_from_source_file(root / "docs" / "note.md")
    assets, _outside = cli.collect_page_assets(page, root / "docs" / "note.md", root / "docs")
    assert "tiny.png" in assets, assets


def test_a_stray_backtick_does_not_silence_the_link_check(tmp_path):
    """Same blindness, other pass: the broken link two paragraphs below
    the backtick stopped being reported."""
    root = _project(tmp_path)
    page = cli._page_from_source_file(root / "docs" / "note.md")
    codes = [i["code"] for i in cli.check_pages([(root / "docs" / "note.md", page)], root)]
    assert "unresolved-link" in codes, codes


def test_a_span_may_wrap_a_line_but_not_a_paragraph():
    """CommonMark's rule, and the renderer's — it joins a paragraph's
    lines before parsing inline, so a span that wraps is one span."""
    wrapped = cli._INLINE_CODE_RE.sub("", "Use the `--limit\nflag` here.")
    assert "--limit" not in wrapped, wrapped
    across = cli._INLINE_CODE_RE.sub("", "One (`) here.\n\n![i](p.png)\n\nAnd `--x` now.")
    assert "p.png" in across, across


def test_a_multi_backtick_span_is_one_span():
    assert cli._INLINE_CODE_RE.sub("", "x ``a ` b`` y") == "x  y"


def test_a_long_run_of_backticks_does_not_stall_the_build():
    """`(`+)` backtracks over every run length at every position: 8000
    backticks took 11.6 s, and the cross-line form took 17 s at 4000 —
    with no output, so `oku check` looked hung."""
    start = time.perf_counter()
    cli._strip_code("`" * 8000)
    assert time.perf_counter() - start < 1.0
