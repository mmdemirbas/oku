---
title: oku
eyebrow: Documentation kit · oku
subtitle: Renders Markdown pages in the browser. Single-source content, no build step for authoring, multi-page site with full-text search when you want one.
order: 1
summary: What the kit is, how it's organised, where the documentation lives.
---

> [!TLDR]
> Pages are Markdown. The browser renders them via Custom Elements; no build step needed to read. Run oku build to emit a multi-page site (with Pagefind search) or a standalone single file for offline reading.
>
> - Source: <name>.md — GitHub-flavored markdown, minus a short list of constructs the kit's linter rejects. Page-JSON sources predate the format and keep rendering.
> - Runtime: chrome.js + renderer.js load from a _oku symlink. No copies, no version drift.
> - Primitives: callout, kpi-grid, table, compare-grid, step-flow, chart, diagram, live-snippet, annotated-code, glossary tooltips, citation cards.
> - Output: dist/site/ (multi-page + Pagefind) and dist/standalone/ (single file with inline page JSON for email / archive).

## Documentation {#docs}

Nine pages beside this one. Cards link straight to each — Reference covers core primitives; Charts / Tables / Diagrams break out the heavy ones; Glossary / Architecture / CLI / Format comparison go deeper.

```oku-step-flow
{"ordered":false,"steps":[{"t":"Reference","b":"Project setup, page anatomy, Markdown sources, the prose / emphasis / structured-layout primitives, per-page metadata, build outputs.","meta":"start here · prose, layout, inline","href":"reference.html"},{"t":"Tables","b":"table primitive — flat rows, grouped rows, chip filters, board / kanban view, sticky headers, drag-resize columns, word-wrap by default.","meta":"flat · grouped · chips · board","href":"tables.html"},{"t":"Charts","b":"Every chart variant with a tiny live sample, grouped by what you're trying to show (compare · trend · distribution · composition · relationship · hierarchy · flow · location) plus rich hover, click-to-pin, pan/zoom fullscreen, and the live configure popover.","meta":"53 types · 8 function groups","href":"charts.html"},{"t":"Diagrams","b":"diagram primitive + every Mermaid v10 type the kit forwards (flowchart, sequence, state, ER, class, gantt, pie, journey, mindmap, timeline, sankey-beta, ...). Theme tokens flow through.","meta":"Mermaid catalog","href":"diagrams.html"},{"t":"Glossary & ext-refs","b":"File layout, multi-language entries, project overrides, disambiguation syntax, resolution algorithm.","meta":"multi-domain registry","href":"glossary.html"},{"t":"Architecture","b":"How the kit fits together at runtime — render flow, tooltip controller, kit loader, build pipeline, standalone bundle. Read this when extending or debugging the kit itself.","meta":"internals · developer audience","href":"architecture.html"},{"t":"CLI reference","b":"Six commands. What each does, what output to expect, the doctree linter's severity table, and the two dependencies — jsonschema required, pagefind opt-in.","meta":"init · build · clean · migrate · check · serve","href":"cli.html"},{"t":"Why markdown","b":"Five source formats measured on tokens, converter weight and ecosystem fit. What the measurement said, kept so the decision is not re-argued from memory.","meta":"the source-format decision","href":"format-comparison.html"},{"t":"Roadmap","b":"Open and in-flight work, chart interactivity per variant, recent landings, the locked decisions, and the principles every change honours.","meta":"what's next · oku 1.0","href":"roadmap.html"}]}
```

## What a page looks like {#shape}

Markdown is what an author types; HTML is what ships. Page-JSON is the second format the walkers still accept — it predates the markdown source and keeps rendering. Code on the left, the actual rendered output on the right.

### JSON source {#shape-json}

Hand-authored or AI-emitted. Every block declares its kind explicitly; nothing has to be guessed. Validated against the kit schema before it ships.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"info\",\n  \"title\": \"Heads up\",\n  \"content\": \"Callouts carry one of nine tones: info, note, tip, warn, caution, danger, success, neutral, important.\"\n}","lang":"json"},"output":"> [!INFO] Heads up\n> Callouts carry one of nine tones: info, note, tip, warn, caution, danger, success, neutral, important."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"kpi-grid\",\n  \"tiles\": [\n    { \"num\": \"53\",   \"label\": \"chart types\" },\n    { \"num\": \"JSON\", \"label\": \"single source\" },\n    { \"num\": \"0\",    \"label\": \"build steps for content\" }\n  ]\n}","lang":"json"},"output":{"k":"kpi-grid","tiles":[{"num":"53","label":"chart types"},{"num":"JSON","label":"single source"},{"num":"0","label":"build steps for content"}]}}
```

### Markdown source {#shape-md}

Drop existing .md files into the docs root. ATX headings, code fences (mermaid included), lists, tables, blockquotes, inline formatting all convert. Relative .md links retarget to .html. README / CHANGELOG and friends are surfaced as pages too.

The subset is strict, and `oku check` names each thing outside it. A setext (`===` underline) heading is an error. A four-space-indented block after a blank line, a blockquote line continued without its `>`, and a `---` sitting directly under a text line are warnings — each is a construct CommonMark and the kit read differently, so the linter asks you to disambiguate rather than guessing.

```oku-example
{"code":{"k":"code","src":"> Blockquotes become neutral callouts.\n>\n> Multiple lines stay grouped inside the same callout body.","lang":"markdown"},"output":"> [!NEUTRAL]\n> Blockquotes become neutral callouts.\n> \n> Multiple lines stay grouped inside the same callout body."}
```

```oku-example
{"code":{"k":"code","src":"- *emphasis* and **strong** work inline\n- `inline code` renders with the kit's monospace font\n- bullets and numbered lists fold straight in","lang":"markdown"},"output":"- *emphasis* and **strong** work inline\n- `inline code` renders with the kit's monospace font\n- bullets and numbered lists fold straight in"}
```

```oku-example
{"code":{"k":"code","src":"```mermaid\nflowchart LR\n  A[\"Markdown\"] --> B[\"oku\"]\n  B --> C[\"Rendered diagram\"]\n```","lang":"markdown"},"output":{"k":"diagram","src":"flowchart LR\n  A[\"Markdown\"] --> B[\"oku\"]\n  B --> C[\"Rendered diagram\"]\n"}}
```

## Quickstart {#quickstart}

Two commands. Adopt the kit for an existing docs/ directory without rewriting anything.

```bash
cd path/to/your-project/docs
oku init     # creates _oku symlink + index.html
oku serve    # http://localhost:9876 with live reload
```

After `init`, any `.md` or `.json` file in the docs tree is a page. The sidebar lists them; the on-page TOC builds from H2 / H3; full-text search builds with `oku build` when pagefind is available — install it with the `oku[search]` extra, or have `pagefind` on PATH.
