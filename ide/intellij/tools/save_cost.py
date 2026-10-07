"""What a render costs right after another page of the same tree is saved.

`oku preview --serve` keeps a tree's site manifest between requests and
computes it again when any file in the tree changes, so in an editor the
first render after a save — an autosave, a switch to another app — pays
for the whole tree. This renders PAGE cold and warm, then moves OTHER's
mtime three times (a save that changes nothing, so the content is the
same) and renders PAGE after each. OTHER's mtime is put back at the end.

    uv run python ide/intellij/tools/save_cost.py OKU PAGE.md OTHER.md

OKU is the program to measure: `oku` as installed, or `.venv/bin/oku`
for this checkout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> None:
    oku, page, other = sys.argv[1], Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
    text = page.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as out:
        p = subprocess.Popen(
            [oku, "preview", "--serve", "--out", out],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        assert p.stdin is not None and p.stdout is not None
        p.stdout.readline()  # the greeting

        def render(rid: int) -> str:
            t = time.perf_counter()
            p.stdin.write(json.dumps({"id": rid, "path": str(page), "text": text}) + "\n")
            p.stdin.flush()
            reply = json.loads(p.stdout.readline())
            return f"{round(1000 * (time.perf_counter() - t))} ms wall, oku {reply.get('ms') or reply.get('error')}"

        print("first:", render(1))
        print("warm: ", render(2))
        st = other.stat()
        try:
            for i in range(3):
                os.utime(other, (st.st_atime, time.time()))
                print(f"after a save of {other.name}:", render(10 + i))
        finally:
            os.utime(other, (st.st_atime, st.st_mtime))
            p.stdin.close()
            p.wait()


if __name__ == "__main__":
    main()
