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
