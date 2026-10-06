"""Time what one preview render costs, phase by phase, and print the chart.

Runs `oku preview` the two ways there are: once per render (a process per
edit, as the proof of concept did) and as the `--serve` session the plugin
keeps. Each reply carries its phase timings in `ms`; whatever the wall clock
spends outside them is interpreter start-up, imports and I/O, which the
session pays once. The median of RUNS warm runs per page and mode goes into
an `oku-chart` stacked-bar payload, which is what docs/index.md carries —
re-run this to refresh it.

    uv run python ide/intellij/tools/measure_render.py docs/index.md docs/charts.md docs/reference.md

The `oku` on PATH is what is measured, as the plugin would find it; set OKU
to measure another (`OKU=".venv/bin/python -m oku.cli"` for this checkout —
not `uv run`, whose own start-up would land in the first series).
"""

from __future__ import annotations

import json
import os
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNS = 5
OKU = shlex.split(os.environ.get("OKU", "oku"))


def _phases(reply: dict) -> tuple[float, float, float]:
    if "error" in reply:
        raise SystemExit(f"oku preview: {reply['error']}")
    ms = reply["ms"]
    return ms["convert"], ms["manifest"], ms["standalone"]


def one_shot(page: Path, out: Path) -> tuple[float, float, float, float]:
    start = time.perf_counter()
    done = subprocess.run(
        [*OKU, "preview", str(page), "--out", str(out), "--theme", "dark", "--stdin"],
        input=page.read_bytes(),
        capture_output=True,
    )
    wall = 1000 * (time.perf_counter() - start)
    if done.returncode != 0:
        raise SystemExit(done.stderr.decode())
    return (wall, *_phases(json.loads(done.stdout)))


class Session:
    def __init__(self, out: Path) -> None:
        self.proc = subprocess.Popen(
            [*OKU, "preview", "--serve", "--out", str(out)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        hello = json.loads(self._line())
        print(
            f"session: oku {hello['oku']}, kit {hello['kit']}, protocol {hello['protocol']}", file=sys.stderr
        )
        self.next_id = 0

    def _line(self) -> bytes:
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        if not line:
            raise SystemExit("oku preview --serve closed its output")
        return line

    def render(self, page: Path) -> tuple[float, float, float, float]:
        assert self.proc.stdin is not None
        self.next_id += 1
        request = {
            "id": self.next_id,
            "path": str(page),
            "text": page.read_text(encoding="utf-8"),
            "theme": "dark",
        }
        start = time.perf_counter()
        self.proc.stdin.write(json.dumps(request).encode() + b"\n")
        self.proc.stdin.flush()
        reply = json.loads(self._line())
        wall = 1000 * (time.perf_counter() - start)
        return (wall, *_phases(reply))

    def close(self) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        self.proc.wait(timeout=60)


def _row(label: str, runs: list[tuple[float, float, float, float]]) -> dict:
    wall, convert, manifest, standalone = (statistics.median(col) for col in zip(*runs))
    return {
        "page": label,
        "rest": round(wall - convert - manifest - standalone),
        "convert": round(convert),
        "manifest": round(manifest),
        "standalone": round(standalone),
        "wall": round(wall),
    }


def main() -> int:
    pages = [Path(a).resolve() for a in sys.argv[1:]]
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        session = Session(out)
        try:
            for page in pages:
                name = f"{page.name} ({round(page.stat().st_size / 1024)} KB)"
                one_shot(page, out)  # warm the file cache and the git lookups
                rows.append(_row(f"{name} · süreç başına", [one_shot(page, out) for _ in range(RUNS)]))
                session.render(page)  # the session's first render reads the tree
                rows.append(_row(f"{name} · --serve", [session.render(page) for _ in range(RUNS)]))
        finally:
            session.close()
    for r in rows:
        print(json.dumps(r, ensure_ascii=False), file=sys.stderr)
    chart = {
        "type": "stacked-bar",
        "title": f"Bir yeniden çizimin dönüştürme maliyeti, ms (sıcak, {RUNS} koşunun ortancası)",
        "categories": [r["page"] for r in rows],
        "series": [
            {"label": "Python başlangıcı, içe aktarma, G/Ç", "values": [r["rest"] for r in rows]},
            {"label": "md → sayfa sözlüğü", "values": [r["convert"] for r in rows]},
            {"label": "site manifesti", "values": [r["manifest"] for r in rows]},
            {"label": "standalone HTML", "values": [r["standalone"] for r in rows]},
        ],
    }
    print(json.dumps(chart, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
