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
    replacement rather than the name of a feature."""
    root = _project(tmp_path)
    got = _spans(root, root / "docs" / "page.md", "The code is in `src/app.py`, see `src/app.py`.")
    assert len(got) == 1, got
    assert "#f/src/app.py" in got[0]["message"], got
    assert got[0]["severity"] == "info", got


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
