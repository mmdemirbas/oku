"""Browser-level regression tests.

These pin the UI invariants from CLAUDE.md as numeric Playwright
assertions — pytest alone can't see spatial overlap, off-canvas
geometry, or script execution. They run against the REAL serve
handler (markdown→page synthesis included) on an ephemeral port,
in headless chromium.

The whole package auto-skips when the chromium binary isn't
installed (`uv run playwright install chromium` to enable).
"""

from __future__ import annotations

import http.server
import os
import threading
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from oku import cli  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _require_chromium():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        exe = Path(p.chromium.executable_path)
    if exe.exists():
        return
    # Locally, a missing browser is a setup detail and skipping is right.
    # In CI it is the difference between "the UI suite passed" and "the
    # UI suite never ran", which reads identically in a green summary —
    # so CI sets OKU_REQUIRE_BROWSER=1 and this fails loudly instead.
    message = "chromium not installed — run `playwright install chromium`"
    if os.environ.get("OKU_REQUIRE_BROWSER"):
        pytest.fail(f"OKU_REQUIRE_BROWSER is set but {message}")
    pytest.skip(message)


@pytest.fixture(scope="session")
def site_url():
    """The repo served by the real dev-server handler on an ephemeral
    port — same markdown→page synthesis path `oku serve` uses."""
    root = Path(__file__).resolve().parents[3]
    handler = cli._make_serve_handler(root)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
