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


# ---------- fenced blocks: the exclusion the old regex made by accident


FENCED = """---
title: Note
summary: A page showing markdown, and using it.
---

## Intro {#intro}

Here is what a page looks like:

````markdown
---
title: Storage engines
---

An [image](path.png) and a [link](nowhere.md) and a `docs/gone.md` span,
plus a [file]({fileref}) reference.

```oku-chart
{"type":"bar","rows":[{"label":"a","value":60}]}
```
````

And a real broken one: [the plan](nope.md).
"""


def _fenced_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (root / "docs" / "note.md").write_text(FENCED.replace("{fileref}", "#f/src/app.py"), encoding="utf-8")
    cli._project_root_cache.clear()
    return root


def _issues(root: Path):
    src = root / "docs" / "note.md"
    page = cli._page_from_source_file(src)
    return cli.check_pages([(src, page)], root)


def test_a_link_inside_a_fence_is_a_picture_of_markdown_not_markdown(tmp_path):
    """`docs/reference.md` shows the source of every primitive it draws.
    Checking the links in those examples reports the author for writing
    one."""
    issues = _issues(_fenced_project(tmp_path))
    bad = [i for i in issues if "path.png" in i["message"] or "nowhere.md" in i["message"]]
    assert bad == [], bad


def test_the_broken_link_after_the_fence_is_still_reported(tmp_path):
    """The exclusion must end where the fence does — otherwise it is the
    old blindness with a new cause."""
    issues = _issues(_fenced_project(tmp_path))
    assert [i for i in issues if "nope.md" in i["message"]]


def test_a_file_reference_inside_a_fence_is_not_resolved(tmp_path):
    issues = _issues(_fenced_project(tmp_path))
    assert [i for i in issues if i["code"].startswith("filepath-")] == []


def test_a_code_span_inside_a_fence_earns_no_path_nudge(tmp_path):
    issues = _issues(_fenced_project(tmp_path))
    assert [i for i in issues if i["code"] == "path-in-code-span"] == []


def test_an_inner_fence_with_an_info_string_does_not_close_the_outer_one():
    """A toggle reads ```oku-chart as the END of an enclosing block, and
    everything after it inverts: the outer example's tail is scanned as
    live prose while the real prose below is skipped."""
    masked = cli._md_fence_mask(FENCED)
    assert "oku-chart" not in masked
    assert "path.png" not in masked
    assert "the plan" in masked


def test_the_mask_keeps_the_line_numbers():
    md = "a\n\n```\nx\ny\n```\n\n[z](q.md)\n"
    masked = cli._md_fence_mask(md)
    assert masked.count("\n") == md.count("\n")
    assert masked.split("\n").index("[z](q.md)") == md.split("\n").index("[z](q.md)")


def test_a_tilde_fence_is_not_closed_by_backticks():
    md = "~~~\n```\nstill inside\n~~~\nout\n"
    assert "still inside" not in cli._md_fence_mask(md)
    assert "out" in cli._md_fence_mask(md)


# ---------- the other region where a backtick is not a span ----------

ISLAND = """---
title: An island holding a program
summary: The kit's documented idiom for multi-line code inside a card.
---

## S {#s}

Multi-line code in an island is a `<pre>`, never a `<br>`.

<div class="okt-card">

<pre>
python src/app.py --once
see `src/inner.py` for the flags
</pre>

</div>

The program is `src/app.py`.
"""


def _island_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    # A DIFFERENT real file inside the <pre>, so the two regions cannot
    # be told apart by a count alone: the nudge dedups per path, and with
    # the same path on both sides a scanner that suppressed nothing would
    # still report exactly one.
    (root / "src" / "inner.py").write_text("print('inner')\n", encoding="utf-8")
    (root / "docs" / "note.md").write_text(ISLAND, encoding="utf-8")
    cli._project_root_cache.clear()
    return root


def _island_nudges(root: Path):
    src = root / "docs" / "note.md"
    page = cli._page_from_source_file(src)
    return [i for i in cli.check_pages([(src, page)], root) if i["code"] == "path-in-code-span"]


def test_the_island_pre_is_skipped_and_the_prose_below_it_is_not(tmp_path):
    """One assertion, because the fixture is built so that exactly one
    answer is right and each way of being wrong gives a different one.

    Between `<pre>` and `</pre>` the renderer hands the region to the
    browser as markup, so a backtick there is something the reader SEES:
    there is no span to convert, and a chip could not render inside a
    `<pre>` anyway. It matters more since the nudge became a warning —
    `oku check --fix` declines to rewrite inside a raw-text region, so a
    report naming one would be a warning with no remedy behind it, which
    is the shape that teaches an author to stop reading the report.

    The three outcomes, measured:

    - correct → `['src/app.py']`, the paragraph below the island;
    - no suppression → `src/inner.py` as well, the one inside the `<pre>`
      (two different files, because the nudge dedups per path and the
      same path on both sides would report once either way);
    - the suppression armed by the SENTENCE above the island → nothing at
      all, since it would never close.
    """
    got = _island_nudges(_island_project(tmp_path))
    assert sorted(i["message"].split("'")[1] for i in got) == ["src/app.py"], [i["message"] for i in got]


def test_a_sentence_naming_pre_does_not_arm_the_suppression(tmp_path):
    """The line above the island writes "a `<pre>`, never a `<br>`" — a
    sentence, not an open tag. Counting it unmasked opens a region that
    never closes, and everything after it goes unread; measured while
    this was built, that silenced 8 of 10 rewrites on this repo's own
    docs. The test above would pass anyway if the suppression started at
    the island, so this one names the cause."""
    spans = [t for _line, t in cli._md_code_spans(ISLAND)]
    assert "src/app.py" in spans, spans
    assert "<pre>" in spans, "the sentence's own span is prose and still read"
