# oku

> Turkish imperative — "read!". Formerly distributed as **html-doc**;
> the legacy name remains a working alias through the dual-brand
> window. Both `oku` and `html-doc` install as console scripts and
> resolve to the same CLI.
>
> **Sunset for the html-doc alias:** `html-doc` keeps working
> without warning through 0.x and 1.0. From 1.1 it prints a
> deprecation note on every invocation. 2.0 removes the
> console-script entry entirely. Migrate scripts and shell
> aliases to `oku` before then.

A documentation kit. Authors write pages in JSON (or Markdown — both
are first-class); the browser renders them via Custom Elements; the
CLI builds a multi-page site, a search index, and standalone single-
file copies for offline reading.

## What's in the box

- **Sources:** `*.json` (kit schema) or `*.md`. Markdown drops in
  unchanged — relative `.md` links retarget to `.html`, code fences
  highlight, fenced ` ```mermaid ` becomes a live diagram. The
  converter handles nested lists, footnotes, definition lists,
  reference-style links, YAML front-matter, and a sanitised inline
  HTML allowlist.
- **Primitives:** paragraph / heading / list / code / annotated-code,
  callout (8 types, each with a symbol badge), insight, info-tip,
  tldr, kpi-grid, table (sort, filter, chip-rack, view-toggle
  Table / List / Cards / Board with kanban lanes), compare-grid,
  step-flow (click-targetable card cards), chart (28 render
  modes — see below), diagram (Mermaid), live-snippet, glossary
  tooltips, citation cards.
- **28 chart types in one primitive.** scatter · line · area · bubble
  · quadrant · bar · stacked-bar · grouped-bar · donut · heatmap ·
  sparkline · waffle · gauge · radar · box-plot · bullet · slope ·
  histogram · calendar-heatmap · treemap · ridgeline · funnel ·
  sankey · network · scatter-matrix · parallel-coordinates · chord
  · geo (tile cartogram). Every chart shares one hover-tooltip
  controller (click to pin, Escape to close), expands into a
  fullscreen pan/zoom overlay, and tracks the light / dark theme
  tokens.
- **Chrome:** single left sidebar with site-tree + on-page TOC
  stacked, drag-to-resize edge handle + off-canvas drawer on
  mobile, sticky section TOC with scroll-spy, three-mode theme
  cycler, four-mode content-width cycler (narrow → comfortable →
  wide → max), full-text search (Pagefind), forward-compat warning
  indicator, reader-side placeholder personalization.
- **Wide-screen ready.** Asymmetric bleed — prose blocks clamp at
  `--prose-width` (720px line length); visual primitives expand
  to `--content-width`. On screens >1600px the content width
  widens further so charts and tables breathe.
- **CLI:** `init` symlinks the kit + writes an index stub; `build`
  emits `dist/site/` (multi-page + Pagefind), `dist/standalone/`
  (single file with inline page JSON), and `dist/markdown/`
  (`page.md` twins + `llms.txt` for LLM consumers); `clean` drops
  `dist/`; `check` lints the doctree (schema + structural +
  content); `serve` runs a local HTTP server with live reload.

## Install

```bash
git clone git@github.com:mmdemirbas/html-doc.git
cd html-doc
uv tool install .                # 'oku' and 'html-doc' both on PATH
```

Or run in-tree without installing:

```bash
uv run bin/oku serve             # PEP 723 inline metadata pulls deps
python3 bin/oku serve            # plain Python works too (no extras)
# bin/html-doc still works for back-compat
```

## Quick start

```bash
mkdir -p my-project/docs && cd my-project/docs
oku init                         # _kit symlink + index.html in cwd
# author *.json or *.md pages anywhere under the docs root
oku serve                        # http://localhost:9876 with live reload
```

`oku init` treats the **current directory** as the docs root —
there is no implicit `docs/` subdir. Run it wherever you want pages
to live.

Existing Markdown docs need no conversion: drop `.md` files into the
tree and they appear in the site tree alongside JSON pages.

## Authoring model

Each page is a `*.json` file at any depth under your docs root. A thin
HTML stub next to it (`*.html`, copy of `src/html_doc/templates/starter.html`)
bootstraps the renderer. Authors only ever edit the JSON.

```jsonc
{
  "$schema": "https://raw.githubusercontent.com/mmdemirbas/html-doc/main/kit/schema/page.schema.json",
  "kind": "page",
  "title": "Iceberg storage layer",
  "meta": {
    "eyebrow": "Architecture",
    "summary": "Open table format with ACID guarantees.",
    "updated": "2026-05-19",
    "order": 10
  },
  "blocks": [
    { "kind": "tldr", "summary": "...", "bullets": [...] },
    { "kind": "section", "id": "overview", "title": "Overview", "blocks": [
      { "kind": "paragraph", "content": [
        "Iceberg gives ",
        { "kind": "glossary-term", "term": "ACID", "text": "ACID" },
        " transactions over object stores."
      ]},
      { "kind": "callout", "type": "note", "title": "Heads up", "content": "..." }
    ]}
  ]
}
```

Full schema in `schema/page.schema.json`. Editors that understand JSON
Schema (VS Code, Cursor, IntelliJ) get autocomplete for every node
kind.

## CLI

Five commands, all run from the project root or a subdirectory.
Either `oku` or `html-doc` works as the front:

```bash
oku init                         # one-time, runs in cwd: _kit symlink + index.html stub
oku check                        # lint the doctree (schema + structural + content)
oku check --strict               # exit 1 on warnings too
oku build                        # dist/standalone/ + dist/site/ + dist/markdown/ + search index
oku clean                        # remove dist/ from the current project
oku serve                        # local HTTP, live reload, Pagefind in background
oku serve --no-watch             # disable filesystem watcher
oku serve --no-search            # skip background Pagefind index
```

`build` writes three single-purpose trees under `dist/`:

- `dist/standalone/` — every HTML inlines kit + page JSON +
  `window.__htmldocManifest`. Open via `file://`, attach to email.
- `dist/site/` — multi-page site with shared `_kit/` assets and a
  Pagefind index. One `site-manifest.json` sits at the docs root for
  the runtime page-nav fetch. Drop on any static host.
- `dist/markdown/` — one `<name>.md` twin per JSON page plus a single
  `llms.txt` sitemap. Single canonical home for LLM consumers; not
  duplicated across the human trees.

`serve` synthesizes `site-manifest.json` and `llms.txt` in memory on
each request so source dirs stay clean.

## Primitives

| Element / kind | Purpose |
|---|---|
| `<glossary-term term="...">` | Inline term. Hover → tooltip; click pins. Multi-domain registry. |
| `<ext-ref name="...">` · `<html-doc-cite>` | Citation card with type theming (paper / rfc / release / blog / other). Auto-infers type from link domain. |
| `<callout type="note\|tip\|info\|caution\|warn\|danger\|success\|neutral">` | Block-level themed note. |
| `<insight>` | Pull-quote for a key takeaway. |
| `kpi-grid` · `compare-grid` · `step-flow` | Layout primitives, all layout-safe by structure. `compare-grid` carries verdict variants `good` / `bad` / `neutral` (quality contrast) and `in` / `out` (scope contrast); cards accept either a rich `content` body, an `items` bullet list, or both. |
| `<chart type="...">` | Single primitive, 28 render modes grouped by family: Categorical (bar / stacked-bar / grouped-bar / waffle), Distribution (histogram / box-plot / ridgeline), Time series (line / area / sparkline / slope / calendar-heatmap), Hierarchy (donut / treemap), Relationship (scatter / bubble / quadrant / radar / heatmap), Goal (bullet / gauge), Conversion (funnel), Flow (sankey), Graph (network), Multivariate (scatter-matrix / parallel-coordinates), Circular (chord), Geographic (geo). Shared rich hover tooltip with click-to-pin, click-outside / Esc to close. Cartesian SVG charts add pan / zoom / log scale / legend toggle / PNG export. Every type shares the expand toolbar (copy data / PNG / fullscreen pan + zoom) and the extended series-colour palette (10 distinguishable tokens, light + dark theme); no third-party chart library. |
| `<diagram>` | Mermaid wrapper. Lazy-loads from CDN. Re-renders on theme toggle. Has Copy-source, Copy-SVG, Screenshot buttons. |
| `<live-snippet>` | Editable HTML/CSS/JS textarea + sandboxed iframe preview. |
| `annotated-code` | Code block with numbered `(1)`(2) chips that sync with a side panel of annotations. |
| `table` (flat or grouped) | Rich tables with sort, filter, view-switcher (Table/List/Cards), sticky headers, full-width toggle. |
| `data-bind="X"` | Any two elements with the same key flash together on hover/focus. Stripe-class prose↔code sync. |

Layout / chrome: `<page-chrome>` (theme toggle, search button, warning
indicator, personalization gear), `<page-nav>` (site-tree sidebar with
edge-clickable rail), `<page-toc>` (section TOC sidebar, mirror).

## Inline placeholder personalization

Declare keys in `kit.json`:

```json
{
  "personalization": [
    { "key": "apiKey",    "label": "API Key",    "default": "sk_test_..." },
    { "key": "projectId", "label": "Project ID" }
  ]
}
```

Snippets that contain `{{apiKey}}` swap in the reader's value at render
time. A gear icon in the top-right cluster opens the panel; values
persist in `localStorage`. No server, no account.

## Design principles

Four load-bearing rules. They apply to visual style **and** to content
design — every artifact respects them at both layers.

1. **Proximity.** Related things go together. Site-tree toggle on the
   site-tree sidebar's edge. Caveat next to the claim it qualifies.
2. **Hierarchy.** Three weights of heading, two of body, one accent.
   Top-level conclusion before nested reasoning.
3. **Schema.** Every page kind has predictable parts (cover, TL;DR,
   sections, references).
4. **Grouping.** Visual cues bind related items. Bullets for parallel,
   numbered for ordered, indentation for nested.

## Multi-domain glossary + citations

Glossaries are per-domain, each with multi-language entries:

```
_kit/glossary/
  data-platforms.json    # Iceberg, Spark, Flink, ACID, MVCC, ...
  web.json               # Custom Elements, Shadow DOM, FOUC, ...
  ai-llm.json            # RAG, tokenization, embedding, ...
```

`docs/kit.json` declares the active domains, preferred language, and
per-project overrides:

```json
{
  "domains": ["data-platforms", "web", "ai-llm"],
  "lang": "en",
  "lang_fallback": ["en"],
  "glossary": {
    "data-platforms": {
      "ProjectInternalTerm": { "en": { "def": "..." } }
    }
  }
}
```

Disambiguation when two domains define the same term:

```json
{ "kind": "glossary-term", "term": "ACID", "in": "chemistry" }
```

External references in `_kit/extrefs/<domain>.json` carry the same
shape with an optional `type` (paper / rfc / release / blog / other),
`author`, and `published` for citation-card metadata.

## Forward-compat warning indicator

Top-right warning button (with count badge) surfaces when:

- `window.error` or `unhandledrejection` fires.
- The renderer hits an unknown JSON node `kind`.
- The manifest or `kit.json` has a `schema_version` newer than the
  kit understands.
- A glossary term or citation isn't in any active domain.
- A manifest fetch fails (with HTTP status, where applicable).

Click opens a panel listing entries; Dismiss closes it for the session.

## Tests

```bash
uv run pytest -q                            # ~249 tests, runs in under a second
uv run html-doc check --strict              # schema + structural + content lint
```

Covers the pure converter (Markdown front-matter, nested lists,
footnotes, definition lists, reference-style links, sanitised inline
HTML), schema validation on every published page, the build helpers
(`build_manifest`, `build_llms_txt`, `build_markdown_twins`,
`extract_page_text`, `inject_pagefind_body`) via `tmp_path`
fixtures, and content-regression tests that lock the chrome.js /
chrome.css markers the user has called out as load-bearing.

## Versioning

Tags follow semver. Symlink users get HEAD; pull when you want updates.
CDN consumers should pin to a tag — e.g.
`https://cdn.jsdelivr.net/gh/mmdemirbas/html-doc@v0.2.0/chrome.css`.

History lives in the git log (`git log --oneline`).

## Roadmap

The project is mid-rename to **oku** for the 1.0 push; see
`docs/roadmap.json` (or the live page at `docs/index.html#roadmap.html`)
for the closed-out backlog, locked design decisions, and the small
amount of follow-up tracked for the 1.1 / 2.0 cuts.

## Companion files

- `src/html_doc/templates/starter.html` + `src/html_doc/templates/starter.json` — copy to start a new page.
- `kit/schema/page.schema.json` — the page schema; editors pick this up via the `$schema` field.
- `docs/` — the project's own docs (built with the kit, dogfood).
- `docs/roadmap.json` — phase tracker.
