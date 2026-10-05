"""A browser that drops a connection is not an error, on either server.

A browser leaves requests half-read all the time — a navigation, a media
range it no longer wants, a page closed under a load. socketserver turns
the BrokenPipeError / ConnectionResetError that follows into a multi-line
traceback on stderr. `oku serve`'s handler swallowed them for that reason;
the server `oku verify` starts for dist/site did not, so a clean verify
run (exit 0, every page clean) printed two tracebacks in the middle of
its report on a delivered tree, which reads as a crash.
"""

from __future__ import annotations

import functools
import http.server
import socket
import struct
import threading
import time
from pathlib import Path

import pytest

from oku import cli


def _serve(handler_factory):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_factory)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _drop_mid_response(port: int, path: str) -> None:
    s = socket.create_connection(("127.0.0.1", port))
    s.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".encode())
    s.recv(1024)  # the response has started
    # Close with a reset rather than a FIN, so the server's next write fails.
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    s.close()


@pytest.mark.parametrize("which", ["serve", "verify-site"])
def test_a_dropped_connection_prints_no_traceback(tmp_path: Path, capfd, which: str) -> None:
    (tmp_path / "big.bin").write_bytes(b"x" * (32 * 1024 * 1024))
    if which == "serve":
        factory = cli._make_serve_handler(tmp_path)
    else:
        factory = functools.partial(cli._VerifySiteHandler, directory=str(tmp_path))
    httpd = _serve(factory)
    try:
        for _ in range(3):
            _drop_mid_response(httpd.server_address[1], "/big.bin")
        time.sleep(1.0)
    finally:
        httpd.shutdown()
    err = capfd.readouterr().err
    assert "Traceback" not in err, err
