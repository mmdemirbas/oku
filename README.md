# html-doc

An opinionated **interactive knowledge platform** for AI-emitted
documentation, learning notes, and reviews. JSON pages, a tiny runtime
renderer, a curated library of rich primitives — glossary tooltips with
hover-bridge and click-pin, expandable external references, charts,
Mermaid diagrams, editable code snippets — plus a multi-page navigation
tree, full-text search, and a forward-compat warning indicator. No build
step for content. No Markdown.

## What this is and isn't

It is **not** a documentation generator. It is not a wiki. It is not a
static-site generator competing with MkDocs or Starlight.

It is a **reader-first interactive surface** for the use case where an AI
emits a long, rich response and a human wants to absorb it deeply
without leaving the page — hover an unknown term to see a definition,
click an external reference to expand a card with a canonical link,
browse a connected corpus of past answers as a knowledge base, search
across it. The platform makes consumption feel like a guided tour, not
a wall of text.

Format: **HTML5 with a curated library of Custom Elements**, and a
**JSON source-of-truth** that the runtime renderer maps to that DOM. The
AI read / write loop is the load-bearing constraint; structured JSON
wins it cleanly.

## Install

```bash
git clone git@github.com:mmdemirbas/html-doc.git ~/dev/mmdemirbas/html-doc
ln -sf ~/dev/mmdemirbas/html-doc/bin/html-doc ~/.local/bin/html-doc
chmod +x ~/dev/mmdemirbas/html-doc/bin/html-doc
```

Make sure `~/.local/bin` is on your `PATH`.

## Quick start — new project

```bash
mkdir my-knowledge-base && cd my-knowledge-base
html-doc init                            # creates docs/_kit -> kit symlink
cp ../html-doc/templates/starter.json docs/index.json
cp ../html-doc/templates/starter.html docs/index.html
# edit docs/index.json to taste
html-doc serve                           # opens in the browser
```

## Authoring model

Each page is a `*.json` file at any depth under your docs root. A tiny
HTML stub next to it (`*.html`, copy of `templates/starter.html`)
bootstraps the renderer. Authors — and AIs — only ever edit the JSON.

```jsonc
// docs/architecture/iceberg.json
{
  "$schema": "https://html-doc.dev/schema/page-v1.json",
  "kind": "page",
  "title": "Iceberg storage layer",
  "accent": "teal",
  "meta": { "eyebrow": "Architecture", "summary": "Open table format ...", "order": 10 },
  "blocks": [
    { "kind": "tldr", "summary": "...", "bullets": [...] },
    { "kind": "section", "id": "overview", "title": "Overview", "blocks": [
      { "kind": "paragraph", "content": [
        "Iceberg gives ",
        { "kind": "glossary-term", "term": "ACID", "text": "ACID" },
        " transactions over object stores."
      ]},
      { "kind": "callout", "type": "warn", "title": "Caveat", "content": "..." }
    ]}
  ]
}
```

The full schema is in `schema/page.schema.json`. Editors that understand
JSON Schema (VS Code, Cursor) get autocomplete for every node kind.

## Run the build

```bash
cd docs/                                  # or wherever your pages live
html-doc build
```

`build` produces, in order:

1. `site-manifest.json` — page tree consumed by `<page-nav>` at runtime.
2. `llms.txt` — one-line-per-page sitemap for AI consumers
   ([llmstxt.org](https://llmstxt.org) convention).
3. `dist/standalone/*.html` — each page inlined into a single
   self-contained HTML for emailing / archiving.
4. `dist/site/` — shared assets and pages for serving as a website.
5. `dist/site/pagefind/` — static full-text search index, if
   [Pagefind](https://pagefind.app) is on `PATH` (`brew install pagefind`
   or `npm i -g pagefind`). Soft-fails if absent.

Always produces all of these (no mode flag). Pick whichever suits the
share scenario.

## Local preview

```bash
html-doc serve
```

Walks up from the current dir to find `docs/_kit/`, starts an HTTP
server on the first free port from 9876, refreshes `site-manifest.json`
+ `llms.txt`, and opens the first page in the browser. Press Ctrl-C to
stop.

**Why HTTP, not `file://`:** browsers apply different rules to local
files than to HTTP — symlink resolution, fetch, and ES-module imports
fail silently or differently on `file://`. The local HTTP server
sidesteps that.

## What's in v2

Eleven primitive Custom Elements out of the box. All degrade to plain
HTML if JS fails to load.

| Element | Purpose |
|---|---|
| `<glossary-term term="...">` | Inline term. Hover → tooltip with bridge-hover (tooltip survives mouse traversing toward it). Click pins until clicked again or another term is opened. Touch devices use click only. Resolves against multi-domain `_kit/glossary/<domain>.json` with EN/TR fallbacks. |
| `<ext-ref name="...">` | Inline external reference. Hover summary; click expands a card with full description + canonical link. Same registry mechanism. |
| `<callout type="warn\|danger\|success\|neutral">` | Block-level themed note. |
| `<insight>` | Pull-quote for a key takeaway. |
| `<kpi-grid>` + tiles | Headline-number tiles. |
| `<compare-grid>` + cards | Side-by-side comparison cards with status borders. |
| `<scope-grid>` + cols | In / out columns with semantic borders. |
| `<bar-chart>` + rows | Row-per-item horizontal bar chart (layout-safe by structure). |
| `<chart>` (`type: scatter \| line`) | Generic data-driven SVG chart with axes, ticks, optional point labels, multi-series legend. |
| `<diagram>` | Mermaid wrapper. Library lazy-loads from CDN on first use. Re-renders on theme toggle. |
| `<live-snippet>` | Editable HTML/CSS/JS textarea + sandboxed iframe preview. 220ms debounce. Reset button restores original. |

Plus the layout / chrome elements: `<page-chrome>` (system cluster
top-right: search, warning indicator, theme cycler), `<page-nav>`
(site-tree sidebar on the left with its own edge-tab toggle),
`<page-toc>` (section-TOC sidebar on the right with its edge-tab on
the side facing main).

## Design principles

Four load-bearing rules. They apply to visual style **and** to content
design — every artifact generated through the html-doc skill respects
them at both layers. Codified at
`~/.claude/rules/design-principles.md`.

1. **Proximity.** Related things go together. The site-tree toggle
   lives on the site-tree sidebar's edge. The caveat sits next to the
   claim it qualifies. Helpers above the function that uses them.
2. **Hierarchy.** Three weights of heading, two of body, one accent.
   Top-level conclusion before nested reasoning. Most important
   sentence first or last, never buried.
3. **Schema.** Every page kind has predictable parts. The kit knows
   about cover, TL;DR, sections, references.
4. **Grouping.** Visual cues bind related items. Bullets for parallel,
   numbered for ordered, indentation for nested.

## Multi-domain glossary

Glossaries are per-domain, each with multi-language entries:

```
_kit/glossary/
  data-platforms.json    # Iceberg, Spark, Flink, ACID, MVCC, ...
  web.json               # Custom Elements, Shadow DOM, FOUC, ...
  ai-llm.json            # RAG, tokenization, embedding, ...
  adhd.json              # populate as needed
  hadith.json
  voice.json
```

Each project's `docs/kit.json` declares which domains are active, the
preferred language, the fallback chain, and any project-local
overrides:

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

Unknown terms surface in the forward-compat warning indicator. Add
the entry; the warning clears.

## Pinch-zoom stability

Fixed-position chrome buttons follow the **visual viewport** during
trackpad / touch pinch-zoom on Safari and Chrome (Visual Viewport API).
Buttons stay anchored to the corner the user sees, not the corner of
the layout viewport that has drifted out of view.

## Forward-compat warning indicator

Top-right system cluster surfaces a warning button (with count badge)
when:

- `window.error` or `unhandledrejection` fires.
- The renderer hits an unknown JSON node `kind`.
- The manifest or `kit.json` has a `schema_version` newer than the
  kit understands.
- A glossary term or ext-ref isn't in any active domain.

Click opens a panel listing entries with code, message, and a Dismiss
button (per-session). One indicator regardless of error count.

## Versioning

Tags follow semver: `v1.0.0`, `v2.0.0`. Symlink users get HEAD; pull
when you want updates. CDN consumers should pin to a tag — e.g.
`https://cdn.jsdelivr.net/gh/mmdemirbas/html-doc@v2/chrome.css`.

See `CHANGELOG.md`.

## Companion docs

- `SPEC.md` — full spec for v2, including the multi-domain glossary
  resolution algorithm, design-principle mappings, and the build
  sequence that produced this codebase.
- `templates/starter.html` + `templates/starter.json` — copy these to
  start a new page.
