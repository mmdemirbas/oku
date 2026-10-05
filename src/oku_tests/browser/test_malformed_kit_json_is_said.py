"""A kit.json the browser cannot parse is said, not swallowed.

The runtime fetches `kit.json` from the docs root and reads `lang`,
`domains` and `personalization` from it. `r.json()` failing became
`null` in a `.catch`, so a trailing comma turned off the glossary, the
ext-refs and the reader placeholders for every served page with nothing
in the console and nothing on the warning indicator. `oku build` refuses
a malformed kit.json, so this is the `oku serve` path — the one an
author is looking at while editing it.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"


def test_a_malformed_kit_json_reaches_the_console(browser, tmp_path: Path) -> None:
    (tmp_path / "_oku").symlink_to(KIT, target_is_directory=True)
    (tmp_path / "kit.json").write_text('{"name": "p", "domains": ["web"],}', encoding="utf-8")
    (tmp_path / "page.md").write_text("---\ntitle: P\nsummary: s\n---\n\n## A {#a}\n\nx\n", encoding="utf-8")
    (tmp_path / "page.html").write_text(cli._stub_for("P"), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(tmp_path))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    page = browser.new_page()
    said: list[str] = []
    page.on("console", lambda m: said.append(m.text))
    try:
        page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/page.html", wait_until="load")
        page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        page_quiet(page)
        assert any("kit.json" in s for s in said), said
    finally:
        page.close()
        httpd.shutdown()
        httpd.server_close()
