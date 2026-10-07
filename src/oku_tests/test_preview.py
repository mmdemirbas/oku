"""`oku preview` renders one page for an editor's preview panel.

It is the contract the IntelliJ plugin (ide/intellij) is written against,
and the JSON it prints is that contract: where the page went, which tree it
belongs to, and — in `--serve` mode — a greeting naming the protocol. The
plugin used to reach the same result by importing private helpers of
`oku.cli` from a bridge script, which is the coupling this command removes.

Two properties carry the weight. The preview is what the build ships, so a
page here is compared with the same page out of `oku build`. And the
long-running mode keeps a tree's manifest between requests, which is the
cache `oku serve` once kept past a kit.json edit
(test_serve_forgets_tree_state.py): a tree that changed must be read again.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from oku import cli


def _tree(tmp_path: Path) -> Path:
    """A project with a docs tree of two pages; returns the docs dir."""
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    docs = project / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name": "p", "accent": "teal"}', encoding="utf-8")
    (docs / "a.md").write_text(
        "---\ntitle: A\n---\n\n## On disk {#disk}\n\nwritten to disk\n", encoding="utf-8"
    )
    (docs / "b.md").write_text("---\ntitle: B\n---\n\n## B {#b}\n\nsecond page\n", encoding="utf-8")
    return docs


def _oku(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "oku.cli", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def _inline_json(html: str, element_id: str) -> dict:
    m = re.search(rf'<script type="application/json" id="{element_id}">(.*?)</script>', html, re.S)
    assert m, f"no #{element_id} in the page"
    return json.loads(m.group(1).replace("<\\/script", "</script"))


def _manifest(html: str) -> dict:
    m = re.search(r"<script>window\.__okuManifest=(\{.*?\});</script>", html, re.S)
    assert m, "no inline manifest"
    return json.loads(m.group(1))


# ---------- one page ----------


def test_a_page_lands_in_its_trees_directory(tmp_path: Path) -> None:
    docs = _tree(tmp_path)
    out = tmp_path / "out"
    done = _oku("preview", str(docs / "a.md"), "--out", str(out))
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["protocol"] == cli.PREVIEW_PROTOCOL
    assert result["root"] == docs.resolve().as_posix()
    html = Path(result["html"])
    # One directory per tree, so the site tree's relative links reach the
    # siblings and an editor can map a link back to its source.
    assert html.parent == Path(result["out"])
    assert html.parent.parent == out.resolve()
    assert html.name == "a.html"
    assert _inline_json(html.read_text(encoding="utf-8"), "__oku_page__")["t"] == "A"


def test_the_buffer_wins_over_the_file(tmp_path: Path) -> None:
    docs = _tree(tmp_path)
    buffer = "---\ntitle: A\n---\n\n## Unsaved {#unsaved}\n\ntyped and not saved\n"
    done = _oku("preview", str(docs / "a.md"), "--out", str(tmp_path / "out"), "--stdin", stdin=buffer)
    assert done.returncode == 0, done.stderr
    text = Path(json.loads(done.stdout)["html"]).read_text(encoding="utf-8")
    assert "typed and not saved" in text
    assert "written to disk" not in text


def test_the_preview_is_what_the_build_ships(tmp_path: Path) -> None:
    docs = _tree(tmp_path)
    done = _oku("preview", str(docs / "a.md"), "--out", str(tmp_path / "out"))
    assert done.returncode == 0, done.stderr
    previewed = _inline_json(
        Path(json.loads(done.stdout)["html"]).read_text(encoding="utf-8"), "__oku_page__"
    )

    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    built = _inline_json(
        (docs / "dist" / "standalone" / "a.html").read_text(encoding="utf-8"), "__oku_page__"
    )
    # The one difference is deliberate: where each block starts in the
    # source, for the editor beside the preview. A built page has no editor.
    lines = previewed["m"].pop("_lines")
    assert len(lines) == len(previewed["b"]) and all(isinstance(n, int) for n in lines)
    assert previewed == built


def test_the_theme_is_seeded_only_when_asked(tmp_path: Path) -> None:
    docs = _tree(tmp_path)
    dark = _oku("preview", str(docs / "a.md"), "--out", str(tmp_path / "dark"), "--theme", "dark")
    plain = _oku("preview", str(docs / "a.md"), "--out", str(tmp_path / "plain"))
    dark_html = Path(json.loads(dark.stdout)["html"]).read_text(encoding="utf-8")
    plain_html = Path(json.loads(plain.stdout)["html"]).read_text(encoding="utf-8")
    assert 'var theme = "dark";' in dark_html
    assert "var theme = null;" in plain_html
    # Before the kit: chrome-boot.js reads `theme-pref` on its first line
    # of work, and a seed written after it is a theme that flashes.
    boot = (cli.KIT_DIR / "chrome-boot.js").read_text(encoding="utf-8").strip().splitlines()[0]
    assert dark_html.index('var theme = "dark";') < dark_html.index(boot)


def test_the_page_beside_the_html_is_the_one_it_inlines(tmp_path: Path) -> None:
    """An editor that updates the page in place hands it this file, so it
    must be the page a reload would show — after the asset rewrite."""
    docs = _tree(tmp_path)
    (docs / "dot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    (docs / "a.md").write_text("---\ntitle: A\n---\n\n![dot](dot.svg)\n", encoding="utf-8")
    done = _oku("preview", str(docs / "a.md"), "--out", str(tmp_path / "out"))
    result = json.loads(done.stdout)
    page = json.loads(Path(result["page"]).read_text(encoding="utf-8"))
    assert page == _inline_json(Path(result["html"]).read_text(encoding="utf-8"), "__oku_page__")
    assert "data:image/svg+xml" in json.dumps(page)


@pytest.mark.parametrize(
    ("name", "says"),
    [("notes.txt", "is not a markdown page"), ("missing.md", "does not exist")],
)
def test_a_page_it_cannot_render_is_refused_with_the_reason(tmp_path: Path, name: str, says: str) -> None:
    docs = _tree(tmp_path)
    (docs / "notes.txt").write_text("x", encoding="utf-8")
    done = _oku("preview", str(docs / name), "--out", str(tmp_path / "out"))
    assert done.returncode == 1
    assert says in done.stderr
    assert done.stdout == ""


# ---------- --serve ----------


class _Session:
    """`oku preview --serve` driven one line at a time, with a deadline on
    every read so a hung process fails the test instead of the run."""

    def __init__(self, out: Path) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "oku.cli", "preview", "--serve", "--out", str(out)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._lines: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)

    def read(self) -> dict:
        return json.loads(self._lines.get(timeout=60).decode("utf-8"))

    def ask(self, request: dict | str) -> dict:
        line = request if isinstance(request, str) else json.dumps(request)
        assert self.proc.stdin is not None
        self.proc.stdin.write(line.encode("utf-8") + b"\n")
        self.proc.stdin.flush()
        return self.read()

    def close(self) -> int:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        return self.proc.wait(timeout=60)


@pytest.fixture
def session(tmp_path: Path):
    s = _Session(tmp_path / "out")
    try:
        yield s
    finally:
        if s.proc.poll() is None:
            s.proc.kill()


def test_the_session_opens_by_naming_its_protocol(session: _Session) -> None:
    hello = session.read()
    assert hello == {"protocol": cli.PREVIEW_PROTOCOL, "oku": cli._PKG_VERSION, "kit": cli._kit_build_stamp()}
    assert session.close() == 0


def test_each_request_renders_the_text_it_carries(session: _Session, tmp_path: Path) -> None:
    docs = _tree(tmp_path)
    session.read()
    page = str(docs / "a.md")
    first = session.ask({"id": 1, "path": page, "text": "---\ntitle: A\n---\n\nfirst draft\n"})
    second = session.ask({"id": 2, "path": page, "text": "---\ntitle: A\n---\n\nsecond draft\n"})
    assert (first["id"], second["id"]) == (1, 2)
    assert first["html"] == second["html"]
    text = Path(second["html"]).read_text(encoding="utf-8")
    assert "second draft" in text and "first draft" not in text
    # Without `text` the file on disk is the page.
    third = session.ask({"id": 3, "path": page})
    assert "written to disk" in Path(third["html"]).read_text(encoding="utf-8")
    assert session.close() == 0


def test_a_bad_request_is_answered_and_the_session_goes_on(session: _Session, tmp_path: Path) -> None:
    docs = _tree(tmp_path)
    session.read()
    assert "one JSON object per line" in session.ask("not json")["error"]
    assert "is not a markdown page" in session.ask({"id": 2, "path": str(docs / "kit.json")})["error"]
    assert "`theme`" in session.ask({"id": 3, "path": str(docs / "a.md"), "theme": "sepia"})["error"]
    good = session.ask({"id": 4, "path": str(docs / "a.md")})
    assert good["id"] == 4 and "error" not in good
    assert session.close() == 0


def test_a_tree_that_changed_is_read_again(session: _Session, tmp_path: Path) -> None:
    docs = _tree(tmp_path)
    session.read()
    page = str(docs / "a.md")
    before = Path(session.ask({"id": 1, "path": page})["html"]).read_text(encoding="utf-8")
    assert [e["title"] for e in _manifest(before)["pages"]] == ["A", "B"]
    assert _inline_json(before, "__oku_page__")["m"]["accent"] == "teal"

    (docs / "c.md").write_text("---\ntitle: C\n---\n\nthird page\n", encoding="utf-8")
    (docs / "kit.json").write_text('{"name": "p", "accent": "rose"}', encoding="utf-8")
    after = Path(session.ask({"id": 2, "path": page})["html"]).read_text(encoding="utf-8")
    assert [e["title"] for e in _manifest(after)["pages"]] == ["A", "B", "C"]
    assert _inline_json(after, "__oku_page__")["m"]["accent"] == "rose"
    assert session.close() == 0


def test_the_shell_changes_only_when_more_than_the_page_does(session: _Session, tmp_path: Path) -> None:
    """Same `shell`, and the page is all that changed: an editor may update
    in place. Anything else the HTML carries has to move it, or the panel
    keeps a stale tree, accent, theme or set of linked files."""
    docs = _tree(tmp_path)
    session.read()
    page = str(docs / "a.md")

    def shell(text: str, **extra: str) -> str:
        reply = session.ask({"id": 1, "path": page, "text": text, **extra})
        assert "error" not in reply, reply
        return reply["shell"]

    first = shell("---\ntitle: A\n---\n\nfirst draft\n")
    assert shell("---\ntitle: A\n---\n\nsecond draft, longer\n") == first
    assert shell("---\ntitle: A\n---\n\nfirst draft\n", theme="dark") != first
    # A root-absolute .md link puts that file in the HTML for the viewer.
    assert shell("---\ntitle: A\n---\n\nsee [b](/b.md)\n") != first
    # Saving changes the tree's snapshot; unless the save changed what the
    # tree shows a reader, it must not change the shell.
    (docs / "a.md").write_text("---\ntitle: A\n---\n\nsaved\n", encoding="utf-8")
    assert shell("---\ntitle: A\n---\n\nsaved\n") == first
    (docs / "b.md").write_text("---\ntitle: B renamed\n---\n\nsecond page\n", encoding="utf-8")
    renamed = shell("---\ntitle: A\n---\n\nfirst draft\n")
    assert renamed != first
    (docs / "kit.json").write_text('{"name": "p", "accent": "rose"}', encoding="utf-8")
    assert shell("---\ntitle: A\n---\n\nfirst draft\n") not in (first, renamed)
    assert session.close() == 0
