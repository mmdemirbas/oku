"""What each request the plugin makes on an edit costs, and what a
completion waits when it lands behind a check.

The plugin keeps two `oku preview --serve` sessions: one renders, the other
answers everything else — the check on every pause in typing, the registry
for `#g/` / `#x/` completion and hover, the fix, an anchor's line. One
session answers one request at a time, so a completion asked while a check
is running waits for the rest of the check first.

This opens one session the way the plugin opens its check session, sends
each kind of request RUNS times per page with the page's own text as the
unsaved buffer, and prints the median wall time of each. Then it measures
the queue: a check and a registry request written back to back, the
registry's reply timed from the moment it was sent.

    uv run python ide/intellij/tools/hot_paths.py OKU PAGE.md [PAGE.md …]

OKU is the program to measure: `oku` as installed, or `.venv/bin/oku` for
this checkout. Reads only; the session writes nothing but its --out
directory, a temporary one.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNS = 7


class Session:
    def __init__(self, oku: str, out: Path) -> None:
        self.proc = subprocess.Popen(
            [oku, "preview", "--serve", "--out", str(out)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.next_id = 0
        self.read()  # the greeting

    def read(self) -> dict:
        assert self.proc.stdout is not None
        return json.loads(self.proc.stdout.readline())

    def send(self, fields: dict) -> int:
        assert self.proc.stdin is not None
        self.next_id += 1
        self.proc.stdin.write((json.dumps({"id": self.next_id, **fields}) + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        return self.next_id

    def ask(self, fields: dict) -> tuple[float, dict]:
        start = time.perf_counter()
        self.send(fields)
        reply = self.read()
        if "error" in reply:
            raise SystemExit(f"{fields}: {reply['error']}")
        return (time.perf_counter() - start) * 1000, reply

    def close(self) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        self.proc.wait(timeout=60)


def first_anchor(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("## ") and "{#" in line:
            return line.split("{#", 1)[1].split("}", 1)[0]
    return "nowhere"


def measure(session: Session, page: Path) -> dict[str, float]:
    text = page.read_text(encoding="utf-8")
    base = {"path": str(page), "text": text}
    kinds = {
        "render": {**base, "theme": "light"},
        "check": {**base, "check": True},
        "registry": {**base, "registry": True},
        "fix": {**base, "fix": True},
        "anchor": {**base, "anchor": first_anchor(text)},
    }
    out: dict[str, float] = {}
    for name, fields in kinds.items():
        session.ask(fields)  # the first one converts the tree; an editor pays it once
        out[name] = statistics.median(session.ask(fields)[0] for _ in range(RUNS))
    # The queue: the registry written right behind a check, timed from its own send.
    waits = []
    for _ in range(RUNS):
        session.send(kinds["check"])
        start = time.perf_counter()
        session.send(kinds["registry"])
        session.read()
        session.read()
        waits.append((time.perf_counter() - start) * 1000)
    out["registry behind a check"] = statistics.median(waits)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    oku, pages = argv[1], [Path(p).resolve() for p in argv[2:]]
    with tempfile.TemporaryDirectory() as out:
        session = Session(oku, Path(out))
        try:
            rows = [(page, measure(session, page)) for page in pages]
        finally:
            session.close()
    names = list(rows[0][1])
    width = max(len(n) for n in names)
    print(f"median of {RUNS} warm requests, ms")
    for page, got in rows:
        print(f"\n{page}")
        for name in names:
            print(f"  {name:<{width}}  {got[name]:8.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
