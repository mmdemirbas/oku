# html-doc

An opinionated **interactive knowledge platform** for AI-emitted
documentation, learning notes, and reviews. JSON pages, a tiny runtime
renderer, a curated library of rich primitives — glossary tooltips,
type-themed citation cards, syntax-highlighted code with annotations,
interactive charts with pan/zoom, Mermaid diagrams, sortable rich tables,
inline placeholder personalization — plus a multi-page navigation tree,
full-text search, live reload, and a forward-compat warning indicator.
No build step for content. No Markdown.

## What this is and isn't

It is **not** a documentation generator. It is not a wiki. It is not a
static-site generator competing with MkDocs or Starlight.

It is a **reader-first interactive surface** for the use case where a
long, rich, citation-dense answer needs to be absorbed deeply without
leaving the page — hover an unknown term to see its definition, hover a
citation to see who said it, hover one paragraph to flash the matching
code, drop in your own API key and watch every snippet on every page
swap to your value. The platform makes consumption feel like a guided
tour, not a wall of text.

Format: **HTML5 with a curated library of Custom Elements**, with a
**JSON source-of-truth** the runtime renderer maps to that DOM. The AI
read / write loop is the load-bearing constraint; structured JSON wins
it cleanly.

## Install

```bash
git clone git@github.com:mmdemirbas/html-doc.git
cd html-doc
uv tool install .                # html-doc available on PATH globally
```

Or run in-tree without installing:

```bash
uv run bin/html-doc serve        # PEP 723 inline metadata pulls deps
python3 bin/html-doc serve       # plain Python works too (no extras)
```

## Quick start — new project

```bash
mkdir my-knowledge-base && cd my-knowledge-base
html-doc init                    # creates docs/_kit + docs/index.html
cp ../html-doc/src/html_doc/templates/starter.json docs/index.json
# edit docs/index.json to taste
html-doc serve                   # opens in the browser, live-reloads on save
```

## Authoring model

Each page is a `*.json` file at any depth under your docs root. A thin
HTML stub next to it (`*.html`, copy of `src/html_doc/templates/starter.html`)
bootstraps the renderer. Authors only ever edit the JSON.

```jsonc
{
  "$schema": "https://html-doc.dev/schema/page-v1.json",
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

Three commands, all run from the project root or a subdirectory:

```bash
html-doc init                    # one-time: docs/_kit symlink + docs/index.html stub
html-doc build                   # dist/standalone/ + dist/site/ + search index
html-doc serve                   # local HTTP, live reload, Pagefind in background
html-doc serve --no-watch        # disable filesystem watcher
html-doc serve --no-search       # skip background Pagefind index
```

`serve` writes `site-manifest.json`, `site-manifest.js`, `llms.txt`,
and `<name>.md` twins at the closest common parent of your JSON pages
(typically `docs/`). The `.md` twins are LLM-readable renderings of
each page; the `.js` companion is for environments that block
same-origin `fetch()` (file://, IDE built-in servers).

## Primitives

| Element / kind | Purpose |
|---|---|
| `<glossary-term term="...">` | Inline term. Hover → tooltip; click pins. Multi-domain registry. |
| `<ext-ref name="...">` · `<html-doc-cite>` | Citation card with type theming (paper / rfc / release / blog / other). Auto-infers type from link domain. |
| `<callout type="note\|tip\|info\|caution\|warn\|danger\|success\|neutral">` | Block-level themed note. |
| `<insight>` | Pull-quote for a key takeaway. |
| `kpi-grid` · `compare-grid` · `scope-grid` · `bar-chart` · `step-flow` | Visual primitives, all layout-safe by structure. |
| `<chart type="scatter\|line">` | SVG chart with pan/zoom/reset, log scale, hover tooltips, legend toggle, screenshot button. |
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
uv run --with pytest --with jsonschema pytest tests/
```

61 tests, runs in under a second. Covers pure functions
(`render_page_markdown`, `_common_docs_dir`, `_pick_open_target`),
schema validation on every published page, and the build helpers
(`build_manifest`, `build_llms_txt`, `build_markdown_twins`,
`extract_page_text`, `inject_pagefind_body`) via `tmp_path` fixtures.

## Versioning

Tags follow semver. Symlink users get HEAD; pull when you want updates.
CDN consumers should pin to a tag — e.g.
`https://cdn.jsdelivr.net/gh/mmdemirbas/html-doc@v0.2.0/chrome.css`.

See `CHANGELOG.md`.

## Companion files

- `src/html_doc/templates/starter.html` + `src/html_doc/templates/starter.json` — copy to start a new page.
- `kit/schema/page.schema.json` — the page schema; editors pick this up via the `$schema` field.
- `docs/` — the project's own docs (built with the kit, dogfood).
