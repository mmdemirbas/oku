"""Who can reach `oku serve`.

The server hands out the PROJECT root — the working copy, not a built
doc tree — so the bind address decides whether a preview is a local
convenience or a file share. It bound `("", port)`, which is every
interface, and printed `http://localhost:…` underneath, so the one
place a reader could check said the opposite of what happened.
"""

from __future__ import annotations

import http.server
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from oku import cli


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("127.0.0.2", True),
        ("::1", True),
        ("localhost", True),
        ("", False),
        ("0.0.0.0", False),
        ("::", False),
        ("192.168.1.20", False),
    ],
)
def test_loopback_is_decided_by_the_address_not_by_one_spelling(host: str, expected: bool) -> None:
    assert cli._is_loopback(host) is expected


def _routable_address() -> str | None:
    """This machine's LAN address, without a DNS lookup — `gethostname`
    does not resolve on a Mac that is off a network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET-1: routed nowhere, no packet sent
        addr = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return None if cli._is_loopback(addr) else addr


def test_the_default_bind_refuses_a_connection_from_a_routable_address(tmp_path: Path) -> None:
    """The binary question, asked of a live socket rather than a string."""
    lan = _routable_address()
    if lan is None:
        pytest.skip("no routable address on this machine to try")
    handler = cli._make_serve_handler(tmp_path)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with socket.socket() as s:
            s.settimeout(2)
            with pytest.raises(OSError):
                s.connect((lan, port))
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_wildcard_bind_is_still_available_and_does_reach(tmp_path: Path) -> None:
    """The control for the test above: the same assertion inverts when
    the bind is the one `--host 0.0.0.0` asks for, so a pass is about the
    bind and not about the machine having no network."""
    lan = _routable_address()
    if lan is None:
        pytest.skip("no routable address on this machine to try")
    handler = cli._make_serve_handler(tmp_path)
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", 0), handler)  # noqa: S104 - the control case
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with socket.socket() as s:
            s.settimeout(2)
            s.connect((lan, port))
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_flag_names_what_it_costs(repo_root: Path) -> None:
    """A wildcard bind is a decision, and the help text is where it gets
    made — so it says what becomes readable, not just the syntax."""
    out = subprocess.run(
        [sys.executable, str(repo_root / "bin" / "oku"), "serve", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    assert "--host" in out
    assert "127.0.0.1" in out
    assert "network" in out
