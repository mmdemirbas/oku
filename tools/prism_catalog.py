#!/usr/bin/env python3
"""Regenerate `src/oku/prism_catalog.json` from Prism's own components.json.

The CLI needs three facts about the Prism release the kit serves, and
none of them can be derived from the vendor directory:

- which names are grammars at all (`hcl` is, `text` is not);
- which name a grammar answers to (`adoc` is asciidoc, `rb` is ruby) —
  the autoloader resolves aliases itself before it builds a URL, so a
  check reading the directory alone reports every alias as missing;
- what a grammar requires (cpp needs c, tsx needs jsx and typescript) —
  fetching a component without its dependencies vendors a file that
  still cannot highlight.

Generated rather than hand-written, and committed rather than fetched at
runtime, so `oku check` answers the same on a fresh clone with no vendor
directory and no network. Re-run it when `_PRISM_CDN` moves to a new
Prism release; `test_prism_catalog.py` holds the file against the version
the CLI pins, and against the vendored copy when one is present.

    uv run tools/prism_catalog.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "oku" / "prism_catalog.json"


def pinned_version() -> str:
    src = (ROOT / "src" / "oku" / "cli.py").read_text(encoding="utf-8")
    m = re.search(r'_PRISM_VERSION = "([^"]+)"', src)
    if not m:
        raise SystemExit("could not find the pinned prismjs version in cli.py")
    return m.group(1)


def build(version: str) -> dict:
    url = f"https://cdn.jsdelivr.net/npm/prismjs@{version}/components.json"
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 - pinned https CDN
        data = json.loads(r.read())
    langs = {k: v for k, v in data["languages"].items() if k != "meta"}

    def listed(value) -> list[str]:
        if not value:
            return []
        return [value] if isinstance(value, str) else list(value)

    aliases: dict[str, str] = {}
    requires: dict[str, list[str]] = {}
    bundled: set[str] = set()
    for lang, spec in langs.items():
        for a in listed(spec.get("alias")):
            aliases[a] = lang
        req = listed(spec.get("require"))
        if req:
            requires[lang] = req
        # `option: default` is Prism's own mark for a grammar compiled
        # into prism.min.js. Those have no component file and the
        # autoloader never asks for one.
        if spec.get("option") == "default":
            bundled.add(lang)
    bundled |= {a for a, lang in aliases.items() if lang in bundled}
    return {
        "prism": version,
        "ids": sorted(langs),
        "bundled": sorted(bundled),
        "aliases": dict(sorted(aliases.items())),
        "requires": {k: requires[k] for k in sorted(requires)},
    }


def main() -> int:
    version = pinned_version()
    cat = build(version)
    OUT.write_text(json.dumps(cat, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(
        f"✓ {OUT.relative_to(ROOT)} — prism {version}: "
        f"{len(cat['ids'])} grammars, {len(cat['aliases'])} aliases, "
        f"{len(cat['bundled'])} in the core bundle"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
