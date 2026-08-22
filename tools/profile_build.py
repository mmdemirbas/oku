#!/usr/bin/env python3
"""Time and profile `oku build` over trees of different page counts.

usage: profile_build.py <tree> [--profile] [--no-pagefind]
"""

import argparse
import cProfile
import io
import os
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from oku import cli  # noqa: E402

if __name__ == "__main__":
    tree = Path(sys.argv[1]).resolve()
    profile = "--profile" in sys.argv
    npages = len(list(tree.glob("*.md")))
    label = tree.name

    if "--no-pagefind" in sys.argv:
        cli.pagefind_index = lambda site_dir: False

    os.chdir(tree)
    args = argparse.Namespace(no_vendor=True, no_search="--no-pagefind" in sys.argv, allow_errors=True)
    real = sys.stdout
    sys.stdout = io.StringIO()
    pr = cProfile.Profile() if profile else None
    t0 = time.perf_counter()
    if pr:
        pr.enable()
    rc = cli.cmd_build(args)
    if pr:
        pr.disable()
    wall = time.perf_counter() - t0
    sys.stdout = real

    tag = "no-pagefind" if "--no-pagefind" in sys.argv else "full"
    print(
        f"TREE={label} pages={npages} mode={tag} rc={rc} wall={wall:.2f}s per_page={wall / max(npages, 1) * 1000:.0f}ms"
    )
    if pr:
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(30)
        for line in s.getvalue().splitlines():
            t = line.strip()
            if t.startswith(("ncalls", "Ordered")) or ("(" in t and ")" in t and t[:1].isdigit()):
                print("   ", t[:150])
