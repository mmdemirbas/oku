"""Time what one preview render costs, phase by phase, and print the chart.

Runs the bridge (src/main/resources/oku-preview/preview.py) under the
installed oku tool's Python, the way the plugin does, and reads the phase
timings it reports on stderr. Whatever the wall clock spends outside those
phases is interpreter start-up, imports and I/O. The median of RUNS warm
runs per page goes into an `oku-chart` stacked-bar payload, which is what
docs/index.md carries — re-run this to refresh it.

    uv run python ide/intellij/tools/measure_render.py docs/index.md docs/charts.md docs/reference.md
"""

from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parent / "src" / "main" / "resources" / "oku-preview" / "preview.py"
OKU_PYTHON = Path.home() / ".local" / "share" / "uv" / "tools" / "oku" / "bin" / "python"
RUNS = 5
PHASES = re.compile(r"convert (\d+)ms manifest (\d+)ms standalone (\d+)ms")


def one_run(page: Path, out: Path) -> tuple[float, int, int, int]:
    start = time.perf_counter()
    done = subprocess.run(
        [str(OKU_PYTHON), str(BRIDGE), "--path", str(page), "--out-base", str(out), "--theme", "dark"],
        input=page.read_bytes(),
        capture_output=True,
        check=True,
    )
    wall = 1000 * (time.perf_counter() - start)
    convert, manifest, standalone = map(int, PHASES.search(done.stderr.decode()).groups())
    return wall, convert, manifest, standalone


def main() -> int:
    pages = [Path(a).resolve() for a in sys.argv[1:]]
    rows = []
    with tempfile.TemporaryDirectory() as out:
        for page in pages:
            one_run(page, Path(out))  # warm the file cache and the git lookups
            runs = [one_run(page, Path(out)) for _ in range(RUNS)]
            wall, convert, manifest, standalone = (statistics.median(col) for col in zip(*runs))
            rows.append(
                {
                    "page": f"{page.name} ({round(page.stat().st_size / 1024)} KB)",
                    "start": round(wall - convert - manifest - standalone),
                    "convert": round(convert),
                    "manifest": round(manifest),
                    "standalone": round(standalone),
                    "wall": round(wall),
                }
            )
    for r in rows:
        print(json.dumps(r, ensure_ascii=False), file=sys.stderr)
    chart = {
        "type": "stacked-bar",
        "title": f"Bir yeniden çizimin dönüştürme maliyeti, ms (sıcak, {RUNS} koşunun ortancası)",
        "categories": [r["page"] for r in rows],
        "series": [
            {"label": "Python başlangıcı + içe aktarma", "values": [r["start"] for r in rows]},
            {"label": "md → sayfa sözlüğü", "values": [r["convert"] for r in rows]},
            {"label": "site manifesti", "values": [r["manifest"] for r in rows]},
            {"label": "standalone HTML", "values": [r["standalone"] for r in rows]},
        ],
    }
    print(json.dumps(chart, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
