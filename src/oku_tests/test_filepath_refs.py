"""Where a `#f/` reference points, and what the lint says about it.

The primitive had browser coverage — the chip, the hover card, the
popup — and nothing at this layer, which is where the four answers are
decided: `ok`, `missing`, `outside`, and over the cap. Each carries a
different promise to the reader, and only the first one opens a
preview.

The fence is the project root (nearest ancestor with `.git`, else with
`kit.json`), not the docs root, so a page can point at the source it
documents.
"""

from __future__ import annotations

from pathlib import Path

from oku import cli


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "docs" / "notes.md").write_text("notes\n", encoding="utf-8")
    cli._project_root_cache.clear()
    return root


def _page(page_src: Path, *refs: str) -> tuple[Path, dict]:
    body = " ".join(f"[label]({r})" for r in refs)
    return page_src, {"k": "doc", "t": "Page", "m": {"summary": "s"}, "b": ["## S {#s}", body]}


# ---------- the resolver ----------


def test_a_sibling_file_resolves(tmp_path):
    root = _project(tmp_path)
    target, status = cli.resolve_file_ref("notes.md", root / "docs" / "page.md")
    assert status == "ok" and target == (root / "docs" / "notes.md").resolve()


def test_the_fence_is_the_project_root_not_the_docs_root(tmp_path):
    """`../src/app.py` is the reference an author most wants to make.
    A docs-rooted fence would refuse it."""
    root = _project(tmp_path)
    target, status = cli.resolve_file_ref("../src/app.py", root / "docs" / "page.md")
    assert status == "ok" and target == (root / "src" / "app.py").resolve()


def test_a_file_past_the_fence_is_outside_and_says_where_it_landed(tmp_path):
    """A page carries the bytes of what it previews, so a reference
    reaching past the project would publish them. The path comes back
    with the status because the message names it."""
    root = _project(tmp_path)
    outsider = tmp_path / "secret.txt"
    outsider.write_text("x", encoding="utf-8")
    target, status = cli.resolve_file_ref("../../secret.txt", root / "docs" / "page.md")
    assert status == "outside" and target == outsider.resolve()


def test_a_directory_is_not_a_file(tmp_path):
    root = _project(tmp_path)
    _target, status = cli.resolve_file_ref("../src", root / "docs" / "page.md")
    assert status == "missing"


def test_an_empty_reference_is_missing_rather_than_the_page_itself(tmp_path):
    root = _project(tmp_path)
    assert cli.resolve_file_ref("", root / "docs" / "page.md") == (None, "missing")


def test_a_home_that_cannot_be_expanded_is_a_missing_file_not_a_crash(tmp_path):
    """`~~~` and `~nobody/notes.md` raise RuntimeError out of
    `Path.expanduser()`. Uncaught, that ends `oku check` and `oku build`
    in a traceback over a page whose only fault is a typo in a link —
    found by a script that swept this repo's own code spans."""
    root = _project(tmp_path)
    for href in ("~~~", "~definitely-not-a-user-account/notes.md"):
        _target, status = cli.resolve_file_ref(href, root / "docs" / "page.md")
        assert status == "missing", href


def test_a_percent_encoded_space_resolves(tmp_path):
    """The href travels through markdown, where a space is escaped."""
    root = _project(tmp_path)
    (root / "docs" / "release notes.md").write_text("x", encoding="utf-8")
    _target, status = cli.resolve_file_ref("release%20notes.md", root / "docs" / "page.md")
    assert status == "ok"


# ---------- what the lint reports ----------


def _codes(root: Path, page_src: Path, *refs: str) -> list[str]:
    p, page = _page(page_src, *refs)
    return [i["code"] for i in cli.check_pages([(p, page)], root)]


def test_a_reference_that_resolves_is_reported_by_nothing(tmp_path):
    root = _project(tmp_path)
    assert "filepath-missing" not in _codes(root, root / "docs" / "page.md", "#f/notes.md")


def test_a_missing_file_is_a_warning_naming_the_href(tmp_path):
    root = _project(tmp_path)
    p, page = _page(root / "docs" / "page.md", "#f/nope.md")
    issues = [i for i in cli.check_pages([(p, page)], root) if i["code"] == "filepath-missing"]
    assert len(issues) == 1, issues
    assert "nope.md" in issues[0]["where"], issues


def test_a_file_outside_the_project_is_a_warning(tmp_path):
    root = _project(tmp_path)
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    codes = _codes(root, root / "docs" / "page.md", "#f/../../secret.txt")
    assert "filepath-outside" in codes, codes


def test_a_file_over_the_cap_says_the_preview_will_not_open(tmp_path):
    """Not a warning: the chip still names the file and copies the path.
    What the reader loses is the preview, and the page has to say so
    somewhere other than the reader's click."""
    root = _project(tmp_path)
    big = root / "docs" / "huge.txt"
    big.write_text("x" * (cli.MAX_FILE_TEXT_BYTES + 1), encoding="utf-8")
    p, page = _page(root / "docs" / "page.md", "#f/huge.txt")
    issues = [i for i in cli.check_pages([(p, page)], root) if i["code"] == "filepath-not-carried"]
    assert len(issues) == 1, issues
    assert issues[0]["severity"] == "info", issues


def test_a_root_relative_path_resolves_too(tmp_path):
    """Prose writes paths from the project root — a sentence about
    `src/app.py` says it the way the reader would type it into an
    editor. From `docs/page.md` that resolves nowhere, so the chip
    rendered and its preview never opened."""
    root = _project(tmp_path)
    target, status = cli.resolve_file_ref("src/app.py", root / "docs" / "page.md")
    assert status == "ok" and target == (root / "src" / "app.py").resolve()


def test_the_page_wins_when_both_bases_resolve(tmp_path):
    """A relative path in a markdown file means "beside this file"
    everywhere else — an image, a link to a sibling page. A file of the
    same name appearing at the root must not change what an existing
    reference points at."""
    root = _project(tmp_path)
    (root / "docs" / "src").mkdir()
    (root / "docs" / "src" / "app.py").write_text("beside the page\n", encoding="utf-8")
    target, _status = cli.resolve_file_ref("src/app.py", root / "docs" / "page.md")
    assert target == (root / "docs" / "src" / "app.py").resolve()


def test_a_path_that_resolves_from_neither_base_reports_the_page(tmp_path):
    """The status has to describe what the author wrote, not the last
    thing the resolver tried."""
    root = _project(tmp_path)
    target, status = cli.resolve_file_ref("nope/app.py", root / "docs" / "page.md")
    assert status == "missing"
    assert target == (root / "docs" / "nope" / "app.py"), target


# ---------- the nudge that makes the primitive findable ----------


def _spans(root: Path, page_src: Path, body: str) -> list[dict]:
    page = {"k": "doc", "t": "Page", "m": {"summary": "s"}, "b": ["## S {#s}", body]}
    return [i for i in cli.check_pages([(page_src, page)], root) if i["code"] == "path-in-code-span"]


def test_a_path_in_a_code_span_is_named_once_with_the_link_to_write(tmp_path):
    """A path in a code span is a dead end: the reader leaves the page,
    finds the file, comes back. The note is how an author who has never
    heard of the chip finds out it exists, so it has to carry the exact
    replacement rather than the name of a feature — and, now that the
    rewrite exists, the command that applies it."""
    root = _project(tmp_path)
    got = _spans(root, root / "docs" / "page.md", "The code is in `src/app.py`, see `src/app.py`.")
    assert len(got) == 1, got
    assert "#f/src/app.py" in got[0]["message"], got
    assert "oku check --fix" in got[0]["message"], got


def test_the_nudge_is_a_warning_and_therefore_gets_read(tmp_path):
    """It was an info note, and an info note is one summary line naming
    the code — which is how a primitive goes unused in the pages that
    document it. Measured before the raise: this repo's own reference
    page named `src/oku/cli.py` in prose and its glossary page named a
    registry file, ten spans across six pages, and nothing that ran on
    every build said so out loud.

    The raise is only honest because two other things are true. The gate
    is already the certain case — a separator is required and the file
    must resolve inside the project — and `oku check --fix` makes the
    remedy one command. A warning naming an afternoon of hand edits is
    a warning authors learn to pass `--errors-only` to.
    """
    root = _project(tmp_path)
    got = _spans(root, root / "docs" / "page.md", "The code is in `src/app.py`.")
    assert [i["severity"] for i in got] == ["warning"], got


def test_one_note_per_path_carries_how_many_times_it_appears(tmp_path):
    """Ten cells naming one file is one decision and ten edits. The note
    stays single — a report with one line per cell is one nobody reads —
    and says which number the reader is looking at."""
    root = _project(tmp_path)
    once = _spans(root, root / "docs" / "page.md", "Only `src/app.py` here.")
    assert "times on this page" not in once[0]["message"], once

    thrice = _spans(
        root,
        root / "docs" / "page.md",
        "`src/app.py`, then `src/app.py`, and again `src/app.py`.",
    )
    assert len(thrice) == 1, thrice
    assert "(3 times on this page)" in thrice[0]["message"], thrice


def test_a_page_the_kit_only_materialised_is_never_nudged(tmp_path):
    """A README or a CLAUDE.md renders through the kit and is also read
    on GitHub, where `#f/…` is a link to an anchor that does not exist.
    This is the one place the nudge would make the file worse, so it is
    the one place it does not fire — the same exemption the prose rules
    already take for author-owned repo markdown."""
    root = _project(tmp_path)
    page = {
        "k": "doc",
        "t": "Readme",
        "m": {"summary": "s", "_materialised_by": "oku-init"},
        "b": ["## S {#s}", "The code is in `src/app.py`."],
    }
    issues = cli.check_pages([(root / "README.md", page)], root)
    assert [i for i in issues if i["code"] == "path-in-code-span"] == []


def test_a_span_that_is_already_a_chip_is_not_reported(tmp_path):
    """The label of a `#f/` link is a code span sitting inside the chip
    the note would recommend."""
    root = _project(tmp_path)
    assert _spans(root, root / "docs" / "page.md", "See [`src/app.py`](#f/src/app.py).") == []


def test_a_path_inside_a_fenced_block_is_program_text(tmp_path):
    """A fence is a program, not prose about a file. Rewriting a path
    there would change what the reader is meant to run."""
    root = _project(tmp_path)
    body = "Run it:\n\n```bash\ncat src/app.py `src/app.py`\n```\n"
    assert _spans(root, root / "docs" / "page.md", body) == []


def test_a_code_span_that_is_not_a_path_is_never_stat_ed(tmp_path):
    """A page carries hundreds of code spans and two or three name
    files. The gate is what keeps the check from asking the filesystem
    about every flag and identifier on the page."""
    for text in ("--dry-run", "title", "k", "SELECT", "$HOME", "https://example.com/a.png"):
        assert not cli._looks_like_a_path(text), text
    for text in ("src/app.py", "../src/app.py", "docs/kit.json"):
        assert cli._looks_like_a_path(text), text


def test_a_bare_filename_is_not_a_path_to_this_project(tmp_path):
    """ "Add a `kit.json` to your project" names a file the READER is
    going to create. That this project has one of its own does not make
    it the file the sentence is about, and a chip pointing at it would
    send the reader to the wrong repository. The separator is what
    tells the two apart."""
    root = _project(tmp_path)
    (root / "docs" / "notes.md").write_text("x", encoding="utf-8")
    assert not cli._looks_like_a_path("kit.json")
    assert _spans(root, root / "docs" / "page.md", "Every project needs a `notes.md`.") == []


def test_a_path_that_names_no_file_is_not_a_suggestion(tmp_path):
    """The note claims the file is there. It has to be right about
    that, or it is a check that guesses — and an author who is nagged
    about a path they invented stops reading the report."""
    root = _project(tmp_path)
    assert _spans(root, root / "docs" / "page.md", "Put it in `src/nope.py`.") == []


def test_a_span_that_is_already_a_link_label_is_left_alone(tmp_path):
    """``[`src/app.py`](app.html)`` is a path the author has already
    made clickable, and the destination they chose may well be better
    than a preview of the file — a link to the rendered page rather than
    to its source."""
    root = _project(tmp_path)
    assert _spans(root, root / "docs" / "page.md", "See [`src/app.py`](notes.md) for it.") == []


# ---------- the rewrite the nudge names ----------
#
# Telling an author about a primitive is half of it. The other half is
# that converting forty code spans by hand is an afternoon, and an
# afternoon is what a nudge loses to. `oku check --fix` is what makes
# the warning above proportionate.


def _fix(root: Path, md: str, *, name: str = "page.md") -> tuple[str, list[str]]:
    src = root / "docs" / name
    src.write_text(md, encoding="utf-8")
    return cli._rewrite_code_span_paths(md, lambda t: cli.resolve_file_ref(t, src)[1] == "ok")


def test_prose_a_gfm_cell_and_a_typed_payload_are_all_rewritten(tmp_path):
    """The three places a path is written, in one page, because they take
    three different routes through the rewriter: a prose line, a table
    row that is also a prose line, and a JSON string inside a fence.

    The typed one is why the reported complaint is about tables — a
    table is where a path most often ends up as a bare code span, and a
    fix that stopped at prose would leave the case that prompted it.
    """
    root = _project(tmp_path)
    out, moved = _fix(
        root,
        "---\ntitle: T\n---\n\n## S {#s}\n\n"
        "The code is in `src/app.py`.\n\n"
        "| What | Where |\n|---|---|\n| The app | `src/app.py` |\n\n"
        '```oku-table\n{"headers":["What","Where"],"rows":[["The app","`src/app.py`"]]}\n```\n',
    )
    assert moved == ["src/app.py"] * 3, moved
    assert out.count("[`src/app.py`](#f/src/app.py)") == 3, out
    assert "`src/app.py`," not in out.replace("[`src/app.py`]", ""), out


def test_the_rewritten_typed_fence_is_still_the_json_it_was(tmp_path):
    """The rewrite inside a fence is textual, and it is safe for one
    reason: JSON has no backtick outside a string literal, so a matched
    span is inside one by construction and the replacement introduces no
    character JSON escapes. Asserted rather than argued."""
    import json

    root = _project(tmp_path)
    out, _moved = _fix(
        root,
        "---\ntitle: T\n---\n\n## S {#s}\n\n"
        '```oku-table\n{"headers":["A"],"rows":[["see `src/app.py` now"]]}\n```\n',
    )
    body = out.split("```oku-table\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(body)["rows"][0][0] == "see [`src/app.py`](#f/src/app.py) now"


def test_a_fence_whose_body_is_not_json_is_left_exactly_as_written(tmp_path):
    """A page with a malformed payload is one `oku check` already
    refuses, and `--fix` still runs on it. Rewriting inside a body that
    does not parse would turn one broken page into a differently broken
    one an author no longer recognises."""
    root = _project(tmp_path)
    md = (
        "---\ntitle: T\n---\n\n## S {#s}\n\n"
        '```oku-table\n{"headers":["A"],"rows":[["see `src/app.py`"],]}\n```\n'
    )
    out, moved = _fix(root, md)
    assert out == md, out
    assert moved == [], moved


def test_the_four_places_a_backtick_is_not_a_span_to_rewrite(tmp_path):
    """Front matter is YAML, a plain fence is a program, a raw-text
    island region is markup the reader sees, and a link construct is
    already clickable. Each on its own line so a failure names which."""
    root = _project(tmp_path)
    md = (
        "---\ntitle: A `src/app.py` title\n---\n\n## S {#s}\n\n"
        "```bash\ncat `src/app.py`\n```\n\n"
        '<div class="okt-card">\n\n<pre>\nrun `src/app.py`\n</pre>\n\n</div>\n\n'
        "Already done: [`src/app.py`](#f/src/app.py).\n"
    )
    out, moved = _fix(root, md)
    assert moved == [], moved
    assert out == md, out


def test_a_sentence_about_pre_does_not_silence_the_rest_of_the_page(tmp_path):
    """The raw-text suppression is counted on the MASKED line, for the
    reason the island lint states beside the same two regexes: prose
    writes "a `<pre>` inside a `<div>`" and that is a sentence, not an
    open tag.

    Measured while this was being built: counting the unmasked line
    armed a suppression that never lifted and silenced 8 of the 10
    rewrites on this repo's own docs, every one of them on a line of
    ordinary prose several paragraphs later.
    """
    root = _project(tmp_path)
    out, moved = _fix(
        root,
        "---\ntitle: T\n---\n\n## S {#s}\n\n"
        "Multi-line code in an island is a `<pre>`, never a `<br>`.\n\n"
        "The code is in `src/app.py`.\n",
    )
    assert moved == ["src/app.py"], moved
    assert "[`src/app.py`](#f/src/app.py)" in out


def test_only_a_path_that_resolves_is_rewritten(tmp_path):
    """The same predicate the check uses, injected rather than
    reimplemented — the fix is defined as applying what the report said,
    so the two cannot come to disagree about which spans qualify."""
    root = _project(tmp_path)
    out, moved = _fix(
        root,
        "---\ntitle: T\n---\n\n## S {#s}\n\n"
        "Real: `src/app.py`. Invented: `src/nope.py`. Bare: `kit.json`. Flag: `--dry-run`.\n",
    )
    assert moved == ["src/app.py"], moved
    assert "`src/nope.py`" in out and "`kit.json`" in out and "`--dry-run`" in out


def test_a_path_that_cannot_be_written_as_a_link_is_reported_and_not_rewritten(tmp_path):
    """`[`p`](#f/p)` ends at the first `)`, so a path holding one would
    leave the reader with broken markdown where they had a working code
    span. The nudge is still right about the file; only the mechanical
    rewrite declines."""
    root = _project(tmp_path)
    odd = root / "src" / "a(1).py"
    odd.write_text("x\n", encoding="utf-8")
    assert cli._looks_like_a_path("src/a(1).py")
    assert not cli._chippable_path("src/a(1).py")
    out, moved = _fix(root, "---\ntitle: T\n---\n\n## S {#s}\n\nSee `src/a(1).py`.\n")
    assert moved == [], moved
    assert "`src/a(1).py`" in out


def test_running_it_twice_changes_nothing_the_second_time(tmp_path):
    """A chip's label is a code span inside a link construct, so the
    rewrite's own output is a shape it declines to touch. Idempotence is
    what makes `--fix` safe to put in a pre-commit hook."""
    root = _project(tmp_path)
    once, first = _fix(root, "---\ntitle: T\n---\n\n## S {#s}\n\nIn `src/app.py`.\n")
    twice, second = _fix(root, once)
    assert first == ["src/app.py"]
    assert second == []
    assert twice == once


def test_the_command_writes_the_files_and_re_checks_the_tree(tmp_path, capsys, monkeypatch):
    """The wiring, not the rewrite: `--fix` edits on disk and then reports
    the tree AS REWRITTEN.

    That second pass is the point. A report printed from the issue list
    that produced the edits would name warnings the author has already
    had fixed for them, and they would go looking for spans that are no
    longer there.
    """
    import argparse

    root = _project(tmp_path)
    docs = root / "docs"
    # No kit.json beside the page: the project fence is the nearest
    # ancestor holding one, so a second copy here would move the root to
    # `docs/` and put the file the page names outside the project.
    (docs / "page.md").write_text(
        "---\ntitle: T\nsummary: s\n---\n\n## S {#s}\n\nThe code is in `src/app.py`.\n",
        encoding="utf-8",
    )
    (docs / "page.html").write_text(cli._stub_for("T"), encoding="utf-8")
    monkeypatch.chdir(docs)
    cli._project_root_cache.clear()
    cli._PAGE_SOURCE_OF.clear()
    cli._PAGE_BLOCK_LINES.clear()

    args = argparse.Namespace(strict=True, json=False, verbose=False, errors_only=False, fix=True)
    rc = cli.cmd_check(args)
    out = capsys.readouterr().out
    assert "rewrote 1 path(s)" in out, out
    assert "path-in-code-span" not in out, "the report still names what it just fixed"
    assert rc == 0, out
    assert "[`src/app.py`](#f/src/app.py)" in (docs / "page.md").read_text(encoding="utf-8")

    cli._PAGE_SOURCE_OF.clear()
    cli._PAGE_BLOCK_LINES.clear()
    assert cli.cmd_check(args) == 0
    assert "nothing to rewrite" in capsys.readouterr().out
