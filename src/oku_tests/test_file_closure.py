"""A carried file's own references travel with the page, keyed by their place.

The file viewer opens a file from a file, so the chips INSIDE a carried
markdown file have to resolve too. The page cannot look those up by the
path as authored — it is relative to a file the page did not write — so
the build follows them and carries each under `rel`, its path from the
project root. Breadth-first and under a budget, so a large tree drops
the references furthest from the page first.

Two facts ride beside them: the page's own `rel`, which the runtime sets
against its URL to work out the full path on disk, and — under `oku
serve` only, bound to loopback — the docs root on disk. A built
artifact carries neither machine path.
"""

from __future__ import annotations

import http.client
import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    (docs / "notes").mkdir(parents=True)
    (docs / "index.md").write_text(
        "---\ntitle: Index\n---\n\n## One {#one}\n\nSee [`a.md`](#f/notes/a.md).\n", encoding="utf-8"
    )
    # b.md is named only from inside a table FENCE in a.md.
    (docs / "notes" / "a.md").write_text(
        '---\ntitle: A\n---\n\n## A {#a}\n\n```oku-table\n{"headers":["F"],"rows":[["[b](#f/b.md)"]]}\n```\n',
        encoding="utf-8",
    )
    (docs / "notes" / "b.md").write_text(
        "---\ntitle: B\n---\n\n## B {#b}\n\nBack to [`a`](#f/a.md), on to [`c`](#f/../../c.txt), "
        "and the page itself [`index`](#f/../index.md).\n",
        encoding="utf-8",
    )
    (tmp_path / "c.txt").write_text("third\n", encoding="utf-8")
    return tmp_path


def _meta(project: Path) -> dict:
    return cli._page_from_source_file(project / "docs" / "index.md")["m"]


def test_every_resolved_file_says_its_place_in_the_project(project: Path) -> None:
    m = _meta(project)
    assert m["_files"]["notes/a.md"]["rel"] == "docs/notes/a.md"
    assert m["_rel"] == "docs/index.md"


def test_a_reference_inside_a_carried_file_travels_too(project: Path) -> None:
    """Including one written in a table fence, which a scan of the raw
    markdown never saw: the fence is stripped with the code."""
    more = _meta(project)["_files_more"]
    assert set(more) == {"docs/notes/b.md", "c.txt"}, sorted(more)
    assert more["docs/notes/b.md"]["path"] == "docs/notes/b.md"
    assert more["c.txt"]["text"] == "third\n"


def test_nothing_is_carried_twice_and_the_page_is_not_carried_at_all(project: Path) -> None:
    """b.md names a.md (already carried by the page) and the page itself."""
    m = _meta(project)
    rels = [r["rel"] for r in m["_files"].values()] + list(m["_files_more"])
    assert len(rels) == len(set(rels)), rels
    assert "docs/index.md" not in rels


def test_the_budget_drops_the_furthest_first(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    b_size = (project / "docs" / "notes" / "b.md").stat().st_size
    monkeypatch.setattr(cli, "MAX_FILE_CLOSURE_BYTES", b_size)
    more = _meta(project)["_files_more"]
    # b.md is one hop from what the page carries; c.txt is two.
    assert set(more) == {"docs/notes/b.md"}, sorted(more)


def _manifest(project: Path, *, local_only: bool) -> dict:
    handler = cli._make_serve_handler(project / "docs", local_only=local_only)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        conn.request("GET", "/site-manifest.json")
        r = conn.getresponse()
        assert r.status == 200, r.status
        return json.loads(r.read())
    finally:
        httpd.shutdown()


def test_the_live_server_says_where_the_tree_is_only_on_loopback(project: Path) -> None:
    assert _manifest(project, local_only=True)["root_abs"] == (project / "docs").resolve().as_posix()
    assert "root_abs" not in _manifest(project, local_only=False)


def test_the_flag_follows_the_bind(project: Path) -> None:
    """`--host 0.0.0.0` publishes the server; a path on disk must not go
    with it. The flag is computed from the same loopback test the bind
    warning uses."""
    assert cli._is_loopback("127.0.0.1") and cli._is_loopback("::1")
    assert not cli._is_loopback("0.0.0.0") and not cli._is_loopback("")
