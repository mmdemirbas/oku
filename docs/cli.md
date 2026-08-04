---
title: CLI reference
eyebrow: Reference
subtitle: Three commands: oku init, oku build, oku serve. Zero flags. Designed so you mostly forget the CLI exists.
date: 2026-05-18
order: 50
summary: oku init / build / clean / check / serve — what each does.
---

> [!TLDR]
> init scaffolds the cwd as a docs root: _oku symlink + index.html entry stub. build emits two single-purpose trees — dist/standalone/ and dist/site/ (with manifest + llms.txt + Pagefind). clean wipes dist/. check lints every page. serve runs a local HTTP server and synthesizes the manifest, llms.txt and kit.json in memory — source dirs stay clean apart from the one entry stub.
>
> - init treats cwd as the docs root. Run it from wherever you want pages to live (typically cd into your docs/ subdir first).
> - Source dirs hold JSON (or MD) plus a single index.html entry stub so IDE-served workflows work without the dev server running.
> - build is idempotent; safe to re-run. dist/{standalone,site,markdown}/ are wiped each time.
> - clean removes dist/ entirely — no-op if it's already absent.
> - serve synthesizes the manifest fresh on each request — no source writes.
> - Optional deps: pagefind (search index), jsonschema (page validation). Both soft-fail.

## oku init {#init}

One-time per docs root. Creates a _oku symlink so pages can reference _oku/chrome.js etc., and an index.html entry stub that IDE-served workflows open directly (IntelliJ's built-in HTTP server, Live Server, etc.). Both land in cwd — there is no implicit docs/ subdir.

```bash
cd ~/path/to/your-project/docs
oku init

# ✓ Linked /path/to/your-project/docs/_oku -> /path/to/oku/kit
# ✓ Created /path/to/your-project/docs/index.html
#
#   Author pages as <name>.json (or .md) next to index.html.
#   Open index.html in your IDE, or run `oku serve` from the
#   project root for a live-reloading dev server.
```

> [!NEUTRAL] Idempotent + self-healing
> Re-running init is safe. If the symlink already resolves to the kit, it prints "already linked". If it points to a stale target (e.g. the kit repo moved), init transparently refreshes it. A non-symlink file at _oku is treated as user data and refused. An existing index.html is left untouched so your edits survive.

## oku build {#build}

Walks the current directory, produces every dist artifact. Run before deploying dist/site/, before sharing dist/standalone/ files, or any time a search index needs to refresh. Source dir is never written to.

```bash
cd ~/path/to/your-project
oku build

# ✓ Doctree check: 6 page(s) clean
# ✓ Wrote dist/site/site-manifest.json (6 JSON page(s))
# ✓ Wrote dist/site/llms.txt
# ✓ Synthesized 6 stub(s) for pages without on-disk .html
# ✓ Pagefind index built: dist/site/pagefind/
# ✓ Built 6 HTML file(s):
#
#   standalone (inline, send-as-file):
#                file:///.../dist/standalone/docs/index.html
#                ...
#
#   site (shared assets, multi-page):
#   site root:   file:///.../dist/site
#                ...
```

```oku-step-flow
{"steps":[{"t":"Walk *.json and *.md pages recursively","b":"Skips dist/, _oku/, node_modules/, .git/, venv/, __pycache__/. Treats files with kind:\"page\" (and any .md) as pages."},{"t":"Schema validation (optional)","b":"If jsonschema is installed (pip install jsonschema), every page is checked against kit/schema/page.schema.json. Errors print with field paths. Without jsonschema, prints a one-line hint and skips."},{"t":"build_standalone — single-file per page (humans, file://)","b":"For each page, synthesize the HTML stub in memory, inline chrome.css/.js, chrome-boot.js, renderer.js, the page JSON, the kit bundle, and the site-manifest seed (window.__okuManifest). One self-contained file per page; no sidecars. Output to dist/standalone/ with directory structure preserved."},{"t":"build_site — multi-page deployable (humans, HTTP)","b":"Write a per-page stub + copy the source JSON to dist/site/ with directory structure preserved. Copy the kit once into dist/site/_oku/. Write a single site-manifest.json at the site root, beside the copied kit (chrome.js resolves the docs root from wherever _oku/ sits and fetches it there at runtime). Inject extracted text into hidden data-pagefind-body for indexing."},{"t":"build_llms_txt (LLM consumers)","b":"Drop one llms.txt sitemap (llmstxt.org convention) at the site root, beside the manifest. The .md page sources are the canonical AI/LLM surface, so no twin tree is emitted."},{"t":"Pagefind index (optional)","b":"If pagefind is on PATH (brew install pagefind, or npx pagefind), run it over dist/site/. Output to dist/site/pagefind/. Soft-fails with install hint if absent."}]}
```

> [!WARN] build wipes its dist trees
> build removes dist/standalone/ and dist/site/ before rebuilding (plus dist/markdown/ if an older build left one) so stale files don't accumulate. Anything else you've parked under dist/ is left alone — use oku clean to wipe the entire dist/ tree.

## oku clean {#clean}

Remove the dist/ tree under the current project root. Idempotent — no-op when dist/ doesn't exist. Source files and the _oku symlink are untouched.

```bash
oku clean

# ✓ Removed /path/to/your-project/dist

# Second run, nothing left:
oku clean

# ✓ Nothing to clean — /path/to/your-project/dist does not exist.
```

- Useful before publishing a release artifact, switching branches, or just to ensure a fresh build.
- Safe to chain: oku clean && oku build.
- Doesn't touch source pages, the _oku symlink, or kit.json. Only generated output.

## oku check {#check}

Lint every page-JSON in the project. Schema validation plus structural / content checks. Fast — runs in milliseconds. Designed as the oku skill's auto-verify step.

```bash
oku check

# ✓ 11 page(s) clean (schema + structural + content)
#
# oku check --strict       # exit 1 on warnings too
# oku check --json         # machine-parseable output
# oku check --verbose      # also surface info-level nudges
# oku check --errors-only  # suppress warnings in the report
```

Issues land at three severities. Exit code is 1 if any error is present (or any warning under --strict); 0 otherwise.

```oku-table
{"headers":["Severity","Codes","What it catches"],"rows":[["**error**","`schema`, `deprecated-kind`, `unknown-kind`, `duplicate-anchor`, `chart-*`, `stray-demo`, `no-title`, `shadowed-source`, `json-parse-failed`","JSON shape problems, removed primitives still in use, duplicate section / heading IDs, malformed chart payloads, demo pages outside docs/reference.md, a page without a title, a .json shadowing the source you edit."],["**warning**","`process-breadcrumb`, `unresolved-glossary`, `unresolved-extref`, `unknown-inline`","Prose containing process/history references (round-N, vN-review, fixed-in-round; the kit documents current behaviour only). Glossary terms and ext-refs that do not resolve against kit/glossary/ and kit/extrefs/."],["**warning** · presentation","`redundant-meta`, `prose-only-section`, `island-hand-styled`","A field that repeats another (`subtitle` verbatim from `summary`, `updated` from `date`). A section of three or more paragraphs with nothing for the eye — no table, chart, diagram, card grid or code block; a callout does not count. An HTML island carrying hardcoded colours or its own `<style>` instead of building on the kit's classes and CSS variables."],["**info**","`code-no-language`, `no-summary`, `html-island`, `hand-set-derivable`, `accent-divergence`","Code blocks with no declared language. Pages with no meta.summary. HTML islands (they render in the kit, external markdown viewers strip them). A field set by hand where the build derives it. Three or more pages in one directory picking different accents with no default in kit.json."]]}
```

> [!TIP] Adding to the oku skill flow
> Run oku check --strict before declaring an HTML artifact done. Use --json to surface findings programmatically. The linter is the fastest verification step in the auto-verify loop — no browser required.
>
> The presentation rules exist so the briefing does not have to carry them as prose. A style rule written in a guide decays, because nothing fails when it is ignored; a rule the linter applies does not. Only the decidable half lives here — whether the diagram carries the point is still a question for a reader.

## oku serve {#serve}

Local HTTP server in the project root. Synthesizes per-page .html stubs, site-manifest.json, and llms.txt in memory on each request — source dir stays clean. Picks the first free port from 9876.

```bash
oku serve

# ✓ Serving /path/to/your-project on http://localhost:9876
#   Stop with Ctrl-C.
#
#   HTML files:
#     http://localhost:9876/docs/index.html
#     http://localhost:9876/docs/reference.html
#     ...
```

- Walks up from cwd to find the directory containing docs/_oku; serves from there. Run from anywhere inside the project.
- First free port from 9876–9900. Caps at 9900 (if all taken, errors out).
- Synthesizes /<docs>/<name>.html stubs from sibling .json or .md files on the fly; same for site-manifest.json and llms.txt. No filesystem writes.
- Pagefind is not built by serve. Run oku build first if you need full-text search; serve falls back to in-page anchor search otherwise.
- Opens the first HTML it finds in the default browser. Ctrl-C to stop.

> [!TIP] Why HTTP, not file://
> Browsers apply different rules to local files than HTTP — symlink resolution, fetch, and ES module imports fail silently or behave inconsistently on file://. The local HTTP server sidesteps that. On macOS, opening a file:// URL also disables some same-origin policies that matter for the iframe sandbox in <live-snippet>. Always serve.

> [!NOTE] Optional flags
> <strong>--no-watch</strong> disables the filesystem watcher + live-reload (serve static only).<br><strong>--no-search</strong> skips the background Pagefind index generation at startup. Both default to on so the dev loop is rich; opt out if you want a leaner serve.

## Optional dependencies {#optional-deps}

Two external tools the kit will use if present. Both soft-fail — install when you want the feature, skip when you don't.

```oku-compare-grid
{"cards":[{"t":"Pagefind — search index","b":"Install: `brew install pagefind`, or available via `npx pagefind`. Without it: search button still appears but says \"Search index not found\" when clicked. With it: build adds a ~50–100 KB pagefind/ directory to dist/site/; the search button works on the built site.","verdict":"neutral"},{"t":"jsonschema — page validation","b":"Install: `pip install jsonschema`. Without it: build prints a hint and skips validation. With it: every JSON page validates against schema/page.schema.json on build; errors print field path + message. Catches malformed JSON earlier than the runtime.","verdict":"neutral"}]}
```

## Install + run {#future}

Worth noting because they're frequently asked.

Two ways to invoke the CLI.

### Installed via uv

```bash
uv tool install .
# Now `oku` is on PATH globally:
oku serve
```

Installs oku as a console script. The wheel packs chrome.{css,js}, schema/, glossary/, extrefs/ inside html_doc/assets/ and ships starter templates under html_doc/templates/, so init/build find everything without a git layout.

### In-tree without install

```bash
uv run bin/oku serve
# Or plain python3 — both work:
python3 bin/oku serve
```

`bin/oku` is a thin shim that adds `src/` to sys.path and runs `html_doc.cli.main()`. PEP 723 inline metadata pulls jsonschema into an ephemeral venv when invoked via uv.
