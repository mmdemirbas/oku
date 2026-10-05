"""A vendor fetch that half fails says so.

`oku build` fetches the shared dependencies the first time it needs them
and printed "✓ vendored N file(s)" whenever N was above zero — so a run
that got mermaid and Prism and lost the fonts (no CDN behind them, by
design) printed a tick, and both trees then shipped pages that render in
the system font stack. `oku vendor` already reported "incomplete"; the
build, which is where most fetches happen, did not.
"""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path

from oku import cli


def test_build_reports_a_vendor_fetch_that_lost_the_fonts(tmp_path: Path, monkeypatch, capsys) -> None:
    vendor = tmp_path / "vendor"
    monkeypatch.setattr(cli, "vendor_dir", lambda: vendor)

    def fake_urlopen(url, timeout=None):
        if "font" in url or url.endswith(".woff2"):
            raise OSError("font host unreachable")
        return io.BytesIO(b"// fetched\n")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(cli, "fetch_prism_langs", lambda names, quiet=False: ([], []))

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("---\ntitle: P\nsummary: s\n---\n\n## A {#a}\n\nx\n", encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False))
    finally:
        os.chdir(cwd)
    out = capsys.readouterr()
    text = out.out + out.err
    assert not cli.vendor_fonts_present()
    assert "incomplete" in text and "system" in text, text[:1500]
