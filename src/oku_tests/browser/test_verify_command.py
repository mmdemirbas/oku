"""`oku verify` finds what a source check cannot.

The skill's delivery checklist asked an author to open the page, watch
for console errors, resize to a narrow viewport and confirm the figures
drew. Every one of those is mechanical, and a step you have to remember
is a step that gets skipped — most of all the one that catches a
wrong-but-valid payload, which is the failure no source-level check can
reach by construction.

So they are a command. The page below lints clean and is visibly broken:
`oku check` passes it, `oku verify` does not.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


from oku import cli


BROKEN_MD = """---
title: Verify probe
summary: Lints clean, renders wrong.
---

## One {#one}

Lead paragraph.

<div style="width:3000px">An island wider than any viewport.</div>
"""

SOUND_MD = """---
title: Sound
summary: Nothing wrong with it.
---

## One {#one}

Lead paragraph.

```oku-chart
{"type":"bar","rows":[{"label":"a","value":60},{"label":"b","value":80}]}
```
"""


def _project(tmp_path: Path, body: str) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "p.md").write_text(body, encoding="utf-8")
    (docs / "p.html").write_text(cli._stub_for("Probe"), encoding="utf-8")
    return docs


def _run(docs: Path, cmd) -> int:
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        return cmd()
    finally:
        os.chdir(cwd)


def test_a_page_that_lints_clean_can_still_fail_verify(tmp_path: Path, capsys) -> None:
    docs = _project(tmp_path, BROKEN_MD)

    lint = _run(
        docs,
        lambda: cli.cmd_check(argparse.Namespace(strict=True, json=False, verbose=False, errors_only=False)),
    )
    assert lint == 0, "the fixture is meant to satisfy the source checks"

    _run(docs, lambda: cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)))
    capsys.readouterr()
    rc = _run(docs, lambda: cli.cmd_verify(argparse.Namespace()))
    err = capsys.readouterr().err

    assert rc == 1, "sideways scroll went unreported"
    assert "scrolls sideways" in err, err
    assert "@360px" in err and "@1440px" in err, "both widths are checked"


def test_a_sound_page_passes(tmp_path: Path, capsys) -> None:
    docs = _project(tmp_path, SOUND_MD)
    _run(docs, lambda: cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)))
    capsys.readouterr()

    rc = _run(docs, lambda: cli.cmd_verify(argparse.Namespace()))
    captured = capsys.readouterr()
    out = captured.out

    assert rc == 0, captured.err or out
    assert "render clean" in out


def test_it_says_what_to_do_when_nothing_is_built(tmp_path: Path, capsys) -> None:
    docs = _project(tmp_path, SOUND_MD)

    rc = _run(docs, lambda: cli.cmd_verify(argparse.Namespace()))
    err = capsys.readouterr().err

    assert rc == 1
    assert "oku build" in err, err
