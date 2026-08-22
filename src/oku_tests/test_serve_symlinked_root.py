"""A served page renders from a directory reached through a symlink.

`_serve_synthesized` translates a URL to a filesystem path, resolves it,
and refuses anything outside the serve root. The root itself was kept as
handed in — so when it arrived through a symlink the two sides described
the same directory with different strings, the containment check said
"outside", and every page 404'd on its own JSON.

The failure is quiet in the worst way: `.html` is a real file and the
kit loads, so the reader gets the rail, the sidebar and the theme button
around an empty column, with no error anywhere.

macOS makes it the default rather than the edge case — `/var` is a
symlink to `/private/var`, so every temp directory is affected, which is
how it was found. A user-made link (`~/code` into another tree, a
worktree beside its repo) does the same on any platform.
"""

from __future__ import annotations

import http.client
import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

PAGE = """---
title: Alpha
summary: One page, served from behind a link.
---

## Body {#body}

A paragraph.
"""


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    real = (tmp_path / "real").resolve()
    real.mkdir()
    (real / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (real / "alpha.md").write_text(PAGE, encoding="utf-8")
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    return tmp_path


def _get(root: Path, path: str) -> tuple[int, bytes]:
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(root))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        conn.request("GET", path)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        httpd.shutdown()


def test_the_page_json_is_synthesized_behind_a_symlink(tree: Path) -> None:
    status, body = _get(tree / "link", "/alpha.json")
    assert status == 200, f"served {status} — the page renders as empty chrome"
    assert json.loads(body)["t"] == "Alpha"


def test_the_stub_is_synthesized_behind_a_symlink(tree: Path) -> None:
    status, body = _get(tree / "link", "/alpha.html")
    assert status == 200, status
    # The stub is the kit-loading shell; the renderer fetches the JSON
    # sibling by name at runtime, so the stub itself only has to carry
    # the kit.
    assert b"_oku/chrome.js" in body, body[:200]
    assert b"<title>Alpha</title>" in body, body[:300]


def test_the_direct_path_still_works(tree: Path) -> None:
    """The control: same tree, no link in the way."""
    status, body = _get(tree / "real", "/alpha.json")
    assert status == 200, status
    assert json.loads(body)["t"] == "Alpha"


def test_a_path_outside_the_root_is_still_refused(tree: Path) -> None:
    """The check being fixed is a containment check, so the failure this
    fix could introduce is letting something through. `..` in a URL is
    normalised by the client, so this asks the server directly."""
    (tree / "secret.md").write_text(PAGE, encoding="utf-8")
    status, _ = _get(tree / "link", "/../secret.json")
    assert status != 200, "a page outside the served root was synthesized"
