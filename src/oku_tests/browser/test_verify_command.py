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
import subprocess
import sys
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


# A disclosure whose body renders to nothing. Schema-valid — `content`
# has an item and the item is a string — and visually a box that opens
# onto blank space. This is the shape that shipped in a real document
# when `_renderInfoTip` dropped every markdown-authored item: the check
# was clean, the page was empty, and nothing in between said so.
HOLLOW_MD = """---
title: Hollow disclosure
summary: A box that opens onto nothing.
---

## One {#one}

Lead paragraph.

```oku-info-tip
{"summary":"Expand me","content":[""]}
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


def _verify(docs: Path) -> subprocess.CompletedProcess:
    """`oku verify` starts its own Playwright, and pytest-playwright is
    already holding one by the time the suite reaches this file — nesting
    two sync instances raises "Please use the Async API instead". So the
    command is run the way a user runs it, as a process. That also makes
    this a test of the CLI rather than of an internal function, which is
    what the file claims to be testing.

    It passed when this file ran alone, and only alone: nothing else had
    opened a browser yet. The same shape as the fixture bug in
    test_spec_examples_render.py, and invisible the same way.
    """
    return subprocess.run(
        [sys.executable, "-c", "from oku.cli import main; raise SystemExit(main())", "verify"],
        cwd=docs,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(cli.__file__).resolve().parents[2])},
    )


def test_a_page_that_lints_clean_can_still_fail_verify(tmp_path: Path) -> None:
    docs = _project(tmp_path, BROKEN_MD)

    lint = _run(
        docs,
        lambda: cli.cmd_check(argparse.Namespace(strict=True, json=False, verbose=False, errors_only=False)),
    )
    assert lint == 0, "the fixture is meant to satisfy the source checks"

    _run(docs, lambda: cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)))
    proc = _verify(docs)

    assert proc.returncode == 1, f"sideways scroll went unreported: {proc.stdout}{proc.stderr}"
    assert "scrolls sideways" in proc.stderr, proc.stderr
    assert "@360px" in proc.stderr and "@1440px" in proc.stderr, "both widths are checked"


def test_a_disclosure_that_opens_onto_nothing_fails_verify(tmp_path: Path) -> None:
    """The class the info-tip defect belongs to: a figure that paints
    something (a summary) and carries nothing. The ink check reads it as
    healthy, because a closed `<details>` painting only its summary is
    exactly what a closed `<details>` looks like."""
    docs = _project(tmp_path, HOLLOW_MD)

    lint = _run(
        docs,
        lambda: cli.cmd_check(argparse.Namespace(strict=True, json=False, verbose=False, errors_only=False)),
    )
    assert lint == 0, "the fixture is meant to satisfy the source checks"

    _run(docs, lambda: cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)))
    proc = _verify(docs)

    assert proc.returncode == 1, f"an empty disclosure verified clean: {proc.stdout}{proc.stderr}"
    assert "block error" in proc.stderr or "opens onto nothing" in proc.stderr, proc.stderr


def test_a_sound_page_passes(tmp_path: Path) -> None:
    docs = _project(tmp_path, SOUND_MD)
    _run(docs, lambda: cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)))
    proc = _verify(docs)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "render clean" in proc.stdout


def test_it_says_what_to_do_when_nothing_is_built(tmp_path: Path) -> None:
    docs = _project(tmp_path, SOUND_MD)

    proc = _verify(docs)

    assert proc.returncode == 1
    assert "oku build" in proc.stderr, proc.stderr
