"""How long an editor's check takes, through the path the plugin uses.

One `oku preview --serve` session, the installed oku, and `check` requests
carrying each page's own text as the unsaved buffer — four per page, so the
first (which converts the whole tree) and the warm ones can be told apart.
Reads only: the session writes nothing but its --out directory, and a check
writes nothing at all.

    uv run python ide/intellij/tools/check_time.py <page.md> [<page.md> …]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    pages = [Path(a).resolve() for a in sys.argv[1:]]
    if not pages:
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as out:
        p = subprocess.Popen(
            ["oku", "preview", "--serve", "--out", out],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert p.stdin and p.stdout
        greet = json.loads(p.stdout.readline())
        print(
            json.dumps({"oku": greet.get("oku"), "kit": greet.get("kit"), "protocol": greet.get("protocol")})
        )
        rid = 0
        for page in pages:
            text = page.read_text(encoding="utf-8")
            walls, reply = [], {}
            for _ in range(4):
                rid += 1
                started = time.perf_counter()
                p.stdin.write(json.dumps({"id": rid, "path": str(page), "text": text, "check": True}) + "\n")
                p.stdin.flush()
                reply = json.loads(p.stdout.readline())
                walls.append(round((time.perf_counter() - started) * 1000))
            print(
                json.dumps(
                    {
                        "page": page.name,
                        "kb": len(text.encode()) // 1024,
                        "wall_ms": walls,
                        "oku_ms_last": reply.get("ms"),
                        "issues": len(reply.get("issues") or []),
                        "error": reply.get("error"),
                    },
                    ensure_ascii=False,
                )
            )
        p.stdin.close()
        p.wait(timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
