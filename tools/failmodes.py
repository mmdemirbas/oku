#!/usr/bin/env python3
"""Exercise oku build/clean failure modes, each in a throwaway tree."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "tmp/audit/fail"
PY = REPO / ".venv/bin/python"

PAGE = """---
title: {title}
summary: A page for failure-mode testing.
---

## Section {{#s-{n}}}

Body text for {title}.
"""


def fresh(name: str) -> Path:
    d = BASE / name
    if d.exists():
        for p in d.rglob("*"):
            try:
                p.chmod(0o755)
            except OSError:
                pass
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    kit = json.loads((REPO / "docs/kit.json").read_text())
    kit.pop("languages", None)
    kit.pop("defaultLanguage", None)
    (d / "kit.json").write_text(json.dumps(kit))
    return d


def page(d: Path, fname: str, title: str, n: int = 1) -> None:
    (d / fname).write_text(PAGE.format(title=title, n=n))


def run(d: Path, *argv: str):
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    r = subprocess.run(
        [str(PY), "-c", "from oku.cli import main; import sys; sys.exit(main())", *argv],
        cwd=d,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    return r


def report(name: str, r, extra: str = "") -> None:
    tb = "Traceback (most recent call last)" in r.stderr
    exc = ""
    if tb:
        lines = [ln for ln in r.stderr.strip().splitlines() if ln and not ln.startswith(" ")]
        exc = lines[-1][:120] if lines else ""
    tail = [ln for ln in (r.stdout + r.stderr).strip().splitlines() if ln.strip()][-2:]
    print(f"\n--- {name}")
    print(f"    exit={r.returncode}  traceback={tb}  {('exc=' + exc) if exc else ''}")
    for ln in tail:
        print(f"    | {ln[:150]}")
    if extra:
        print(f"    {extra}")


def case_output_is_dir():
    d = fresh("c1_out_is_dir")
    page(d, "index.md", "Index")
    run(d, "build")
    tgt = d / "dist/standalone/index.html"
    tgt.unlink()
    tgt.mkdir()
    (tgt / "inner.txt").write_text("x")
    r = run(d, "build")
    report(
        "C1  output file path already exists as a DIRECTORY",
        r,
        f"left behind: standalone has {len(list((d / 'dist/standalone').glob('*')))} entries",
    )


def case_tree_is_file():
    d = fresh("c2_tree_is_file")
    page(d, "index.md", "Index")
    (d / "dist").mkdir()
    (d / "dist/standalone").write_text("i am a file, not a directory")
    r = run(d, "build")
    report(
        "C2  dist/standalone exists as a regular FILE",
        r,
        f"dist/standalone still a file: {(d / 'dist/standalone').is_file()}",
    )


def case_readonly_dist():
    d = fresh("c3_readonly")
    page(d, "index.md", "Index")
    (d / "dist").mkdir()
    (d / "dist").chmod(0o555)
    r = run(d, "build")
    (d / "dist").chmod(0o755)
    report("C3  dist/ is read-only (0555)", r)


def case_readonly_mid_build():
    d = fresh("c3b_readonly_mid")
    for i in range(6):
        page(d, f"p{i}.md", f"Page {i}", i)
    run(d, "build")
    # Make the site tree unwritable AFTER standalone exists -> half-written tree
    (d / "dist/site").chmod(0o555)
    r = run(d, "build")
    (d / "dist/site").chmod(0o755)
    sa = len(list((d / "dist/standalone").glob("*.html"))) if (d / "dist/standalone").exists() else -1
    st = len(list((d / "dist/site").glob("*.html"))) if (d / "dist/site").exists() else -1
    report(
        "C3b dist/site becomes read-only between builds",
        r,
        f"left behind: standalone={sa} html, site={st} html  (HALF-WRITTEN TREE)",
    )


def case_weird_names():
    d = fresh("c4_names")
    page(d, "with space.md", "With Space", 1)
    page(d, "üniçode-ödev.md", "Unicode", 2)
    page(d, "emoji-📊-page.md", "Emoji", 3)
    page(d, "a#hash.md", "Hash", 4)
    page(d, "q?mark.md", "Question", 5)
    r = run(d, "build")
    out = (
        sorted(p.name for p in (d / "dist/standalone").glob("*")) if (d / "dist/standalone").exists() else []
    )
    report("C4  filenames with space / unicode / emoji / # / ?", r, f"standalone outputs: {out}")
    site = sorted(p.name for p in (d / "dist/site").glob("*.html")) if (d / "dist/site").exists() else []
    print(f"    site html: {site}")


def case_symlink_outside():
    d = fresh("c5_symlink_out")
    outside = BASE / "c5_outside"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "secret.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"S" * 400)
    os.symlink(outside / "secret.png", d / "linked.png")
    (d / "index.md").write_text(
        "---\ntitle: Sym\nsummary: Asset via a symlink out of the tree.\n---\n\n"
        "## S {#s}\n\n![shot](linked.png)\n"
    )
    r = run(d, "build")
    sa = (d / "dist/standalone/index.html").read_text() if (d / "dist/standalone/index.html").exists() else ""
    site_copy = (d / "dist/site/linked.png").exists()
    report(
        "C5  asset is a symlink resolving OUTSIDE the project",
        r,
        f"standalone inlined as data: URI = {'data:image' in sa}; "
        f"site copied the file = {site_copy}; "
        f"standalone still references linked.png = {'linked.png' in sa}",
    )


def case_same_output_name():
    d = fresh("c6_collision")
    page(d, "report.md", "From Markdown", 1)
    (d / "report.json").write_text(
        json.dumps(
            {
                "k": "page",
                "t": "From JSON",
                "m": {"summary": "The JSON twin."},
                "b": ["## Section {#j}", "JSON body."],
            }
        )
    )
    r = run(d, "build")
    html = (
        (d / "dist/standalone/report.html").read_text()
        if (d / "dist/standalone/report.html").exists()
        else ""
    )
    which = "JSON" if "From JSON" in html else ("MARKDOWN" if "From Markdown" in html else "neither")
    report(
        "C6  report.md and report.json -> same report.html",
        r,
        f"winner = {which}; any warning about the shadowed page = "
        f"{'report' in r.stdout.lower() and ('shadow' in r.stdout.lower() or 'skip' in r.stdout.lower())}",
    )


def case_clean_user_file():
    d = fresh("c7_clean")
    page(d, "index.md", "Index")
    run(d, "build")
    (d / "dist/NOTES-FROM-THE-CLIENT.md").write_text("hand-written, not generated")
    (d / "dist/deploy.sh").write_text("#!/bin/sh\nrsync ...\n")
    (d / "dist/keepme").mkdir()
    (d / "dist/keepme/data.csv").write_text("a,b\n1,2\n")
    before = sorted(p.name for p in (d / "dist").iterdir())
    r = run(d, "clean")
    report(
        "C7  oku clean with user files inside dist/",
        r,
        f"dist existed with {before}; dist now exists = {(d / 'dist').exists()}; "
        f"user files survived = {(d / 'dist/NOTES-FROM-THE-CLIENT.md').exists()}",
    )


def case_clean_symlinked_dist():
    d = fresh("c8_clean_symlink")
    real = BASE / "c8_real_output"
    if real.exists():
        shutil.rmtree(real)
    real.mkdir(parents=True)
    (real / "prior.txt").write_text("published artifacts live here")
    page(d, "index.md", "Index")
    os.symlink(real, d / "dist")
    r = run(d, "clean")
    report(
        "C8  oku clean when dist/ is a SYMLINK to a real directory",
        r,
        f"symlink still present = {(d / 'dist').is_symlink()}; "
        f"target dir still present = {real.exists()}; "
        f"target contents = {sorted(p.name for p in real.iterdir()) if real.exists() else 'GONE'}",
    )


def case_build_symlinked_dist():
    d = fresh("c9_build_symlink")
    real = BASE / "c9_real_output"
    if real.exists():
        shutil.rmtree(real)
    real.mkdir(parents=True)
    page(d, "index.md", "Index")
    os.symlink(real, d / "dist")
    run(d, "build")
    # second build: dist/standalone now exists as a real dir under the symlink
    r = run(d, "build")
    report(
        "C9  oku build twice when dist/ is a SYMLINK",
        r,
        f"pages built = {len(list((real / 'standalone').glob('*.html'))) if (real / 'standalone').exists() else 0}",
    )


if __name__ == "__main__":
    BASE.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:]
    cases = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
    for c in cases:
        if only and not any(o in c.__name__ for o in only):
            continue
        try:
            c()
        except Exception as e:  # noqa: BLE001
            print(f"\n--- {c.__name__} HARNESS ERROR: {type(e).__name__}: {e}")
