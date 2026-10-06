"""Render one oku markdown buffer to a standalone page for the IDE preview.

PoC bridge between the IntelliJ plugin and the installed oku tool. It runs
under the Python that has oku installed (the uv tool environment) and goes
through the SAME functions `oku build` uses for a standalone page, so the
preview cannot disagree with what the build ships:

    <oku python> preview.py --path /abs/doc.md --out-base /cache/dir [--theme dark] < buffer

The markdown comes from stdin, not from the file: the editor's buffer may be
unsaved. The path still matters — kit.json, the page's language, `#f/`
references and images all resolve from where the file sits.

Each docs tree gets its own directory under --out-base, so the site tree's
relative links land on siblings rendered from the same tree. Prints one JSON
line on stdout — {"html", "root", "out"} — which is what the plugin needs to
map a link in the preview back to a source file; diagnostics go to stderr.

It calls private helpers of oku.cli (`_apply_meta_defaults`,
`_strip_md_front_matter`, ...). That coupling is the PoC's shortcut; the
plan replaces this file with an `oku preview` subcommand in the CLI.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
import time
from pathlib import Path

from oku import cli

# Runs before chrome-boot.js reads `theme-pref`, so the first paint is
# already in the IDE's theme. The scroll position survives the reload
# the plugin does on every edit: saved on scroll, restored after render.
SHIM = """<script>/* oku IDE preview */
(function () {
  var theme = __THEME__;
  try { if (theme) localStorage.setItem('theme-pref', theme); } catch (e) {}
  var key = 'oku-ide-scroll:' + location.pathname;
  try { history.scrollRestoration = 'manual'; } catch (e) {}
  // `instant`, because the kit sets `scroll-behavior: smooth` on <html>:
  // a plain scrollTo animates down from the top on every edit.
  function restore() {
    var y = 0;
    try { y = +sessionStorage.getItem(key) || 0; } catch (e) {}
    if (y) window.scrollTo({ top: y, behavior: 'instant' });
  }
  window.addEventListener('oku:rendered', function () {
    requestAnimationFrame(restore);
    setTimeout(restore, 250);
  }, { once: true });
  var t;
  window.addEventListener('scroll', function () {
    clearTimeout(t);
    t = setTimeout(function () {
      try { sessionStorage.setItem(key, String(window.scrollY)); } catch (e) {}
    }, 80);
  }, { passive: true });
  window.__okuIdePreview = true;
})();
</script>
"""


def docs_root_for(md: Path) -> Path:
    """The tree a page belongs to: the nearest kit.json at or below the
    project fence, else the page's own directory."""
    fence = cli.project_root_for(md.parent)
    for d in (md.parent, *md.parent.parents):
        if (d / "kit.json").is_file():
            return d
        if d == fence:
            break
    return md.parent


def page_from_buffer(md: Path, text: str) -> dict:
    """`cli._page_from_source_file`, reading the editor buffer instead of
    the file on disk."""
    page = cli.md_to_v2_page(text, default_title=cli._source_stem_path(md).name)
    _, front = cli._strip_md_front_matter(text)
    if not front.get("title"):
        page.setdefault("m", {}).setdefault("_materialised_by", "oku-init")
    cli._apply_meta_defaults(page, md)
    cli.carry_file_refs(page, md)
    return page


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, type=Path)
    ap.add_argument("--out-base", required=True, type=Path)
    ap.add_argument("--theme", choices=["light", "dark"], default=None)
    ap.add_argument("--no-manifest", action="store_true")
    args = ap.parse_args()

    t0 = time.perf_counter()
    md = args.path.resolve()
    text = sys.stdin.buffer.read().decode("utf-8")
    root = docs_root_for(md)
    out = args.out_base / hashlib.sha1(root.as_posix().encode()).hexdigest()[:12]
    page = page_from_buffer(md, text)
    t1 = time.perf_counter()

    manifest = None
    if not args.no_manifest:
        manifest = cli.compute_manifest(root)
        # The preview is the author's own machine — the same case in which
        # `oku serve` on loopback hands the viewer the tree's real path.
        manifest["root_abs"] = root.as_posix()
    t2 = time.perf_counter()

    rel_html = md.relative_to(root).with_suffix(".html")
    stub = cli._stub_for(page.get("t") or md.stem, lang=cli._lang_of_page(page))
    stub = stub.replace(
        '<script src="_oku/chrome-boot.js',
        SHIM.replace("__THEME__", json.dumps(args.theme)) + '<script src="_oku/chrome-boot.js',
        1,
    )

    # build_standalone narrates what it could not inline; keep stdout for
    # the one line the plugin reads.
    noise = io.StringIO()
    with contextlib.redirect_stdout(noise):
        cli.build_standalone([(root / rel_html, stub, page)], out, root, manifest=manifest)
    t3 = time.perf_counter()
    if noise.getvalue().strip():
        sys.stderr.write(noise.getvalue())
    sys.stderr.write(
        f"oku-preview: convert {1000 * (t1 - t0):.0f}ms manifest {1000 * (t2 - t1):.0f}ms "
        f"standalone {1000 * (t3 - t2):.0f}ms root={root}\n"
    )
    paths = {"html": (out / rel_html).as_posix(), "root": root.as_posix(), "out": out.as_posix()}
    print(json.dumps(paths, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
