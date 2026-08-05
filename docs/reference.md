---
title: Reference
eyebrow: Reference
subtitle: Everything an author needs in one page — project setup, page anatomy, every primitive with its JSON shape and a live example, per-page metadata, build outputs.
date: 2026-05-18
order: 20
summary: Project setup, page shape, every primitive with JSON shape + live example, metadata, build outputs.
---

> [!TLDR]
> Set up a project once, then write JSON pages. Every page is a tree of kind-tagged blocks; this page documents the kinds (inline, prose, emphasis, layout, visual), how to thread them together, per-page metadata, and the build outputs.
>
> - Setup · oku init creates _oku symlink + an index.html stub. One-time per project.
> - Page · kind:"page" → title + meta + blocks; blocks are sections (which contain content blocks) or top-level tldr / kpi-grid.
> - Inline · glossary-term, ext-ref, code, em, strong, link
> - Prose · paragraph, heading, list, code, annotated-code
> - Emphasis · callout, insight, info-tip
> - Layout · tldr, kpi-grid, table, compare-grid, step-flow
> - Visual · chart (scatter / line / area / bubble / quadrant / bar / stacked-bar / grouped-bar / donut), diagram, live-snippet
> - Build · oku build → dist/standalone/ (single files) and dist/site/ (+ manifest, llms.txt, Pagefind)

## Project setup {#setup}

One-time per project. Links the kit so pages can reference _oku/chrome.js and friends without copying anything.

```bash
cd path/to/your-project/docs
oku init     # creates _oku symlink + index.html in cwd

# Optional: drop a starter page into the docs root
# (The starter pair ships inside the html_doc package — for a
# git checkout it lives at src/html_doc/templates/starter.json.)

cd ..
oku serve    # http://localhost:9876 with live reload
```

After init, your project has a `docs/_oku/` symlink pointing at the kit repo. Every page references the kit via `<script src="_oku/chrome.js">` and `<link href="_oku/chrome.css">` — no copies, no version drift. Update the kit in one place and every project picks it up.

> [!NEUTRAL] kit.json — declare your project
> Each project's docs/kit.json picks which glossary domains to activate, the preferred language, and any project-local glossary or ext-ref overrides. The kit ships starter domains (data-platforms, web, ai-llm) — pick whichever fit. The glossary page covers domain selection in detail.

## Anatomy of a page {#anatomy}

Every JSON page is rooted at kind:"page" and has three pieces: title, meta, blocks.

```json
{
  "$schema": "https://raw.githubusercontent.com/mmdemirbas/html-doc/main/kit/schema/page.schema.json",
  "kind": "page",
  "schema_version": 1,
  "title": "My note",
  "accent": "teal",
  "meta": {
    "eyebrow": "Notes",
    "subtitle": "One-line subtitle below the H1.",
    "date": "2026-05-18",
    "order": 10,
    "summary": "One-line summary for nav tooltips and llms.txt."
  },
  "blocks": [
    { "kind": "tldr", "summary": "...", "bullets": ["..."] },
    { "kind": "section", "id": "overview", "title": "Overview", "blocks": [
      { "kind": "paragraph", "content": "Plain prose works as a string." }
    ]}
  ]
}
```

### Top-level fields {#top-level}

- `kind` — must be `"page"`. The renderer rejects anything else.
- `title` — required. Becomes the `<title>` and the H1 in the cover.
- `accent` — optional. Either a named token (`teal`, `amber`, `indigo`) or a CSS color value. Overrides the tree default from `kit.json` for this page only.
- `meta` — optional object. See Per-page metadata below; in a markdown source these are the front-matter keys. Only `summary` is worth writing on most pages.
- `blocks` — the content tree. Array of top-level blocks (tldr, kpi-grid, section).

> [!TIP] Why summary matters
> meta.summary is surfaced in four places: the page-nav tooltip on hover, the llms.txt sitemap line for AI consumers, the Pagefind search excerpt, and the cover subtitle. Keep it one tight sentence focused on what the page contains — not a teaser.

### Markdown sources {#markdown-sources}

Existing `.md` files anywhere under the docs root are first-class pages — they appear in the site tree, render with the kit's TOC + chrome, and survive `oku check / build / serve` alongside JSON pages. You don't have to convert anything before adopting the kit; existing Markdown documentation drops in unchanged.

#### Markdown → kit conversion

Every Markdown construct maps to a specific kit block or inline node. The table is the source of truth — same row order the converter walks the parse tree.

```oku-table
{"headers":["Markdown","Becomes"],"rows":[["YAML front-matter (`--- ... ---`)","`page.title` + `page.meta`"],["ATX heading H1","`page.title`"],["ATX heading H2","`section` (id auto-slugged from title)"],["ATX heading H3 / H4","`heading` block inside the active section"],["Paragraph with `**bold**` / `*italic*` / `~~strike~~` / `` `code` `` / `[text](url \"title\")` / `![alt](src)` / `<https://auto.link>`","`paragraph` + inline nodes"],["Backslash escape (`\\*`, `\\[`, `` \\` ``)","the literal character — emphasis does not fire"],["Character reference (`&amp;`, `&mdash;`, `&#8594;`)","the decoded character"],["Hard line break (two trailing spaces, or a trailing `\\`)","`<br>` inside the paragraph"],["Reference-style links `[text][label]` + `[label]: url`","link inline node"],["Footnotes `[^id]` + `[^id]: …`","Numbered superscript + a 'Footnotes' section"],["Definition list (`term\\n: definition`)","`<dl>` via html-inline"],["Inline HTML allowlist (`a, code, em, strong, span, sup, sub, br, mark, kbd, samp, del, ins, abbr`)","html-inline pass-through"],["Fenced code block (` ```lang `)","`code` (language preserved)"],["Fenced `mermaid` block","`diagram` (rendered via the kit's diagram primitive)"],["Unordered + ordered lists, nested","`list` (with html-inline children)"],["Blockquote (`>`)","`<blockquote>`; a GFM alert (`> [!NOTE]`, `[!TIP]`, `[!WARNING]`, `[!CAUTION]`, `[!IMPORTANT]`, plus the kit's `[!TLDR]`) becomes a `callout` of that type"],["GFM pipe table","`table`"],["Thematic break (`---`, `***`, `___`)","`<hr>`"]]}
```

> [!INFO] Relative .md links rewrite to .html
> `[overview](other.md#section)` in a Markdown page becomes `other.html#section` at render time, so links between .md pages work the same as between .json pages. Absolute URLs (http, https, mailto), fragment-only refs (`#section`), and absolute paths (`/x`) pass through unchanged.

> [!NEUTRAL] Every Markdown file is a page by default
> README.md, CHANGELOG.md, CLAUDE.md, AGENTS.md, LICENSE.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md and any other `.md` the walker reaches all surface as pages. Hide one by moving it under a SKIP_DIRS subdirectory (`dist/`, `_oku/`, `.git/`, `.venv/`, `node_modules/`, `templates/`, `_internal/`).

## Prose primitives {#prose}

paragraph, heading, list, code — the four building blocks of any prose section. Used together they cover ~80% of typical content.

### paragraph {#paragraph}

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"paragraph\", \"content\": [\n  \"Plain prose with a \",\n  { \"kind\": \"strong\", \"text\": \"bold token\" },\n  \" and a \",\n  { \"kind\": \"code\", \"text\": \"code\" },\n  \" span.\"\n] }","lang":"json"},"output":"Plain prose with a **bold token** and a `code` span."}
```

### heading {#heading}

Sub-headings inside a section. `level` is 3 or 4 (h1 = page title, h2 = section title — both produced automatically). Optional `id` for permalinks; auto-slugified if absent.

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"heading\", \"level\": 3, \"title\": \"Sub-heading\", \"id\": \"sub\" }","lang":"json"},"output":"### Sub-heading {#heading-sample-3}"}
```

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"heading\", \"level\": 4, \"title\": \"Sub-sub-heading\" }","lang":"json"},"output":"#### Sub-sub-heading {#heading-sample-4}"}
```

### list {#list}

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"list\", \"style\": \"bullet\", \"items\": [\n  \"Plain string item.\",\n  [\"Or an array with \", { \"kind\": \"code\", \"text\": \"inline\" }, \" nodes.\"]\n] }","lang":"json"},"output":"- Plain string item.\n- Or an array with `inline` nodes."}
```

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"list\", \"style\": \"numbered\", \"items\": [\"step 1\", \"step 2\", \"step 3\"] }","lang":"json"},"output":"1. step 1\n2. step 2\n3. step 3"}
```

### code {#code}

Code blocks. `language` is informational; the renderer puts a `language-*` class on the inner `<code>` so Prism (loaded lazily from CDN) highlights on demand. The runtime then adds a gray gutter with line numbers and — for brace languages — a click target on each foldable region's opening line.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"code\",\n  \"language\": \"python\",\n  \"source\": \"def hello():\\n    print('world')\"\n}","lang":"json"},"output":"```python\ndef hello():\n    print('world')\n```"}
```

### annotated-code {#annotated-code}

Numbered code annotations. Markers like `(1)` / `(2)` inside the source become circular accent chips, paired with a numbered side panel. Hovering a chip drops a tooltip BELOW the line (never blocking the code) and highlights the line it points at. Click to jump between chip and panel item.

Each annotation can also declare `lines` (a 1-based line spec — `"3"`, `"1-3"`, `"1,5-7"`) to mark a range or set, and / or `match` (string or array) to highlight specific substrings on hover. When `lines` is set and no inline `(N)` marker is present, the chip auto-places at the start of the first listed line — the source stays clean.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"annotated-code\",\n  \"language\": \"javascript\",\n  \"source\": \"const x = 1; // (1)\\nfunction greet(name) {\\n  return `Hello, ${name}!`;\\n}\",\n  \"annotations\": [\n    { \"id\": 1, \"content\": \"<code>const</code> creates a block-scoped binding.\" },\n    { \"id\": 2, \"content\": \"Function body — highlights lines 2-4.\", \"lines\": \"2-4\" },\n    { \"id\": 3, \"content\": \"Template-literal interpolation.\", \"match\": \"${name}\" }\n  ]\n}","lang":"json"},"output":{"k":"annotated-code","src":"const x = 1; // (1)\nfunction greet(name) {\n  return `Hello, ${name}!`;\n}","lang":"javascript","annotations":[{"id":1,"content":"<code>const</code> creates a block-scoped binding."},{"id":2,"content":"Function body — hovering this chip highlights lines 2-4 in the gutter.","lines":"2-4"},{"id":3,"content":"Template-literal interpolation — hovering this chip highlights the <code>${name}</code> substring.","match":"${name}"}]}}
```

## Emphasis primitives {#emphasis}

callout, insight, info-tip — three ways to highlight content with different weight. Match weight to reader signal.

### callout {#callout}

Block-level themed note. `type` picks the colour band: `warn` / `warning` / `caution` (amber), `danger` (red), `success` / `tip` (green), `info` / `note` (accent blue), `neutral` (gray, default). Optional `title`. `content` is richString. Optional `bind` pairs this callout with another block of the same bind key — hovering one flashes the other (see Cross-cutting › Synced hover pairs).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"warn\",\n  \"title\": \"Watch the lock\",\n  \"content\": \"Compaction holds a metadata lock; long jobs block writers.\"\n}","lang":"json"},"output":"> [!WARN] warn\n> Yellow-bordered, used for caveats."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"danger\",\n  \"title\": \"danger\",\n  \"content\": \"Red-bordered, used for breaking changes or risks.\"\n}","lang":"json"},"output":"> [!DANGER] danger\n> Red-bordered, used for breaking changes or risks."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"success\",\n  \"title\": \"success\",\n  \"content\": \"Green-bordered, used for confirmations.\"\n}","lang":"json"},"output":"> [!SUCCESS] success\n> Green-bordered, used for confirmations."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"neutral\",\n  \"title\": \"neutral\",\n  \"content\": \"Gray-bordered, used for general notes.\"\n}","lang":"json"},"output":"> [!NEUTRAL] neutral\n> Gray-bordered, used for general notes."}
```

### insight {#insight}

A pull-quote for a key takeaway. Larger and more visually distinct than a paragraph — used to mark the one sentence per section worth slowing down for.

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"insight\", \"content\": \"The catalog is the locking primitive. Snapshots are the multi-version mechanism.\" }","lang":"json"},"output":{"k":"insight","b":"The catalog is the locking primitive. Snapshots are the multi-version mechanism."}}
```

### info-tip {#info-tip}

Native `<details>` in disguise — collapsed by default, expand on click. Use to defer optional depth without disrupting the skim path. `content` accepts an array of content blocks (paragraphs, code, callouts, ..).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"info-tip\",\n  \"summary\": \"How the lock actually works\",\n  \"content\": [\n    { \"kind\": \"paragraph\", \"content\": \"Two writers race ...\" }\n  ]\n}","lang":"json"},"output":"> [!TIP] Click to expand a live info-tip\n> info-tip is the right primitive when the curious 5% of readers want the full story but the other 95% need to keep moving."}
```

## Structured-layout primitives {#layout}

tldr, kpi-grid, compare-grid, step-flow — when prose isn't the right shape.

### tldr {#tldr}

Top-level only. Highlighted opener box with optional `title`, a `summary` line, and `bullets` — each bullet is rich-text.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"tldr\",\n  \"summary\": \"One-sentence essence.\",\n  \"bullets\": [\n    \"Three to five concrete points.\",\n    \"Each bullet may include inline kinds like glossary terms.\"\n  ]\n}","lang":"json"},"output":"> [!TLDR] TL;DR (example)\n> One-sentence essence. The summary line is bigger than bullets and reads first.\n>\n> - Three to five concrete points.\n> - Each bullet may include inline kinds like glossary terms or links.\n> - Top-level placement is the canonical use; this one sits inline as a sample."}
```

### kpi-grid {#kpi-grid}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"kpi-grid\",\n  \"tiles\": [\n    { \"num\": \"17\",   \"label\": \"Primitives\" },\n    { \"num\": \"JSON\", \"label\": \"Source\" },\n    { \"num\": \"0\",    \"label\": \"Build steps for content\" }\n  ]\n}","lang":"json"},"output":{"k":"kpi-grid","tiles":[{"num":"17","label":"Primitives"},{"num":"JSON","label":"Source"},{"num":"0","label":"Build steps for content"}]}}
```

### compare-grid {#compare-grid}

Side-by-side cards. `verdict` is `good`, `bad`, or `neutral` — sets the top-border color.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"compare-grid\",\n  \"cards\": [\n    { \"verdict\": \"bad\",  \"title\": \"Before\", \"content\": \"...\" },\n    { \"verdict\": \"good\", \"title\": \"After\",  \"content\": \"...\" }\n  ]\n}","lang":"json"},"output":{"k":"compare-grid","cards":[{"t":"Authored HTML (v1)","b":"Hand-written tags. Tree-edits via string ops. AI tooling brittle.","verdict":"bad"},{"t":"Authored JSON","b":"Structured tree. Atomic edits. JSON.parse is the contract.","verdict":"good"}]}}
```

Scope variant — set `verdict` to `in` (green border) or `out` (muted), and use `items` for a bullet list inside the card. `content` and `items` can coexist — content renders first, items below.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"compare-grid\",\n  \"cards\": [\n    { \"verdict\": \"in\",  \"title\": \"v1\",     \"items\": [\"...\"] },\n    { \"verdict\": \"out\", \"title\": \"Future\", \"items\": [\"...\"] }\n  ]\n}","lang":"json"},"output":{"k":"compare-grid","cards":[{"t":"Ships now","b":"- JSON-source runtime rendering\n- Multi-domain glossary with EN/TR\n- Visual Viewport pinch-zoom fix\n- Pagefind search on built sites","verdict":"in"},{"t":"Out of scope","b":"- Markdown authoring path\n- Server-side rendering\n- Per-user authentication\n- Inline glossary editing UI","verdict":"out"}]}}
```

### step-flow {#step-flow}

Numbered cards for ordered actions, build steps, or migration paths.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"step-flow\",\n  \"steps\": [\n    { \"num\": \"1\", \"title\": \"Init\",  \"meta\": \"~1 min\", \"content\": \"oku init\" },\n    { \"num\": \"2\", \"title\": \"Author\", \"content\": \"Write the JSON page.\" }\n  ]\n}","lang":"json"},"output":{"k":"step-flow","steps":[{"t":"Init","b":"cd into your docs root, then oku init scaffolds the _oku symlink and an index.html stub there.","meta":"~1 min · one-time per project"},{"t":"Author","b":"Write a JSON page and an HTML stub side by side; the renderer fetches the JSON at load time.","meta":"iterative"},{"t":"Build","b":"oku build → dist/standalone/ (single-file HTMLs) and dist/site/ (shared-asset multi-page + manifest + llms.txt + Pagefind).","meta":"before deploy or before sharing standalone"}]}}
```

## live-snippet {#visual}

Editable HTML/CSS/JS textarea + sandboxed iframe preview.

### live-snippet {#live-snippet}

Editable HTML/CSS/JS with sandboxed iframe preview. 220ms debounce on input. `language` is currently `html-css-js` (the only v1 mode). The Reset button restores the original `source`.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"live-snippet\",\n  \"label\": \"Edit the gradient and message\",\n  \"source\": \"<style>...</style>\\n<div>...</div>\"\n}","lang":"json"},"output":{"k":"live-snippet","src":"<style>\n  body { margin:0; height:100vh; display:grid; place-items:center;\n         background: linear-gradient(135deg, #115e59, #2dd4bf);\n         font-family: system-ui; }\n  .box { background:white; padding:20px 28px; border-radius:12px;\n         box-shadow:0 8px 24px rgba(0,0,0,0.15); }\n  h1 { margin:0 0 6px; color:#0f766e; font-size:20px; }\n  p  { margin:0; color:#475569; font-size:14px; }\n</style>\n<div class=\"box\">\n  <h1>Try the snippet</h1>\n  <p>Edit the source on the left.</p>\n</div>","label":"Edit the markup — preview updates live"}}
```

## Inline kinds {#inline}

Used inside any richString — paragraph.content, list.items[*], callout.content, etc. Mix strings with these objects in an array.

### glossary-term {#glossary-term}

Hover for a tooltip with the definition; click to pin. Resolves the `term` attribute against the active glossary domains in priority order. `in` disambiguates when two domains use the same term. `lang` overrides the project language for that instance.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Hover \",\n    { \"kind\": \"glossary-term\", \"term\": \"ACID\", \"text\": \"ACID\" },\n    \" — click to pin; move toward the tooltip to keep it open.\"\n  ]\n}","lang":"json"},"output":"Hover [ACID](#g/ACID) — click to pin; move toward the tooltip to keep it open."}
```

### ext-ref {#ext-ref}

Like glossary-term but for external entities (tools, papers, people). Same hover-bridge-pin behavior. Reads from `_oku/extrefs/<domain>.json` (or project kit.json overrides). Each entry has a `summary` and a `link`; the tooltip shows the name + summary, with a Learn more button to the link.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Powered by \",\n    { \"kind\": \"ext-ref\", \"name\": \"Pagefind\", \"text\": \"Pagefind\" },\n    \" — hover for the card, click to pin, click the inline link to open in a new tab.\"\n  ]\n}","lang":"json"},"output":"Powered by [Pagefind](#x/Pagefind) — hover for the card, click to pin, click the inline link to open in a new tab."}
```

### code, em, strong, link {#code-em-strong-link}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Inline \",\n    { \"kind\": \"code\",   \"text\": \"build_manifest()\" },\n    \", \",\n    { \"kind\": \"em\",     \"text\": \"italic\" },\n    \", \",\n    { \"kind\": \"strong\", \"text\": \"bold\" },\n    \", and a \",\n    { \"kind\": \"link\",   \"text\": \"jsDelivr\", \"href\": \"https://cdn.jsdelivr.net\" },\n    \" link (opens in a new tab).\"\n  ]\n}","lang":"json"},"output":"Inline `build_manifest()`, *italic*, **bold**, and a [jsDelivr](https://cdn.jsdelivr.net) link (opens in a new tab)."}
```

Footnotes and reference-style links resolve across the whole page, so a definition can sit far from its use — at the end of the source, or in another block entirely. The paragraph below is live: a footnote[^ref-demo] and a [reference link][pagefind-site] rendered from the definitions at the bottom of this page.

```markdown
A claim that needs a source[^ref-demo] and a [reference link][pagefind-site].

[^ref-demo]: Definitions may appear anywhere on the page.
[pagefind-site]: https://pagefind.app "Pagefind"
```

Inline constructs nest in either order — a link inside emphasis, emphasis inside a link, a code span inside bold. Only a code span keeps a literal body, so markdown written inside backticks stays visible as source.

```oku-example
{"code":{"k":"code","src":"Nesting composes: **[a bold link](https://example.com)**, [**bold** inside a link](https://example.com), **`code` in bold**, and **bold with *italic* inside**. Inside backticks nothing is parsed: `**[a](b)**`.","lang":"markdown"},"output":"Nesting composes: **[a bold link](https://example.com)**, [**bold** inside a link](https://example.com), **`code` in bold**, and **bold with *italic* inside**. Inside backticks nothing is parsed: `**[a](b)**`."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Sanitised inline HTML pass-through: \",\n    { \"kind\": \"html\", \"text\": \"<kbd>Ctrl</kbd>\" },\n    \" + \",\n    { \"kind\": \"html\", \"text\": \"<kbd>C</kbd>\" },\n    \" copies a selection, with H<sub>2</sub>O as a chemistry footnote.\"\n  ]\n}","lang":"json"},"output":"Sanitised inline HTML pass-through: <kbd>Ctrl</kbd> + <kbd>C</kbd> copies a selection, with H<sub>2</sub>O as a chemistry footnote."}
```

## Per-page metadata {#metadata}

Two fields are yours to write: `title` and `summary`. Everything else
is either derived or inherited from the tree, and every one of them can
still be overridden per page when the default is wrong.

`summary` earns its place twice — it is the nav tooltip, the llms.txt
entry and the search excerpt, and it fills the cover subtitle when no
`subtitle` is set.

```oku-table
{"headers":["Field",{"label":"Who supplies it","filter":"chips","values":["Author writes","From kit.json","Derived","Optional"]},"Meaning"],"rows":[["`title`",{"value":"Author writes","values":["Author writes"]},"The page title. The only field with no sensible default."],["`summary`",{"value":"Author writes","values":["Author writes"]},"One line. Nav tooltip, llms.txt entry, search excerpt — and the cover subtitle when `subtitle` is absent."],["`order`",{"value":"Author writes","values":["Author writes"]},"Sort key in the site-tree nav. Lower sorts earlier; ties fall back to title."],["`parent`",{"value":"Author writes","values":["Author writes"]},"Page id of the parent — nests this page under it in the site tree."],["`accent`",{"value":"From kit.json","values":["From kit.json"]},"Named token (teal, amber, indigo, rose…) or any CSS colour. Set it once for the tree in `kit.json`; a page overrides only when it genuinely differs."],["`audience`",{"value":"From kit.json","values":["From kit.json"]},"Free-form reader label shown in the cover meta row. Tree-wide in `kit.json`; per-page override for the odd maintainer-facing page."],["`read_time`",{"value":"Derived","values":["Derived"]},"Estimated from the body at 220 words per minute, and omitted below two minutes. Set it to override; a hand-counted figure goes stale on the next edit."],["`updated`",{"value":"Derived","values":["Derived"]},"The file's last commit date. Deliberately not the filesystem mtime — a fresh clone would stamp the whole tree as updated today. Renders as a quiet italic line, and is suppressed when it equals `date`."],["`eyebrow`",{"value":"Optional","values":["Optional"]},"Small label above the H1. Leave it out unless it says something the nav does not already show."],["`subtitle`",{"value":"Optional","values":["Optional"]},"One paragraph under the H1. Only needed when the cover should say something other than `summary`."],["`date`",{"value":"Optional","values":["Optional"]},"Publication date, displayed verbatim — the kit never parses it."],["`lang`",{"value":"Optional","values":["Optional"]},"Locale code. Overrides the project default on this page only."]]}
```

> [!TIP] Where a default belongs
> A value that is the same on every page of a tree belongs in
> `kit.json`, not repeated in eleven front-matter blocks. A value the
> body already implies — how long the page takes to read, when it last
> changed — belongs to the build. `oku check` warns when a page sets a
> field it did not need to.

## Build outputs {#build}

oku build produces three trees under dist/, one per audience. Authors don't need to run it during dev — the runtime renderer fetches JSON directly — but build is required for search, the standalone single-file mode, and the llms.txt sitemap.

```oku-step-flow
{"steps":[{"t":"dist/site/","b":"Deployable multi-page site. Every HTML + JSON copied with directory structure preserved. Kit assets bundled at dist/site/_oku/. site-manifest.json sits at the site root, beside the copied kit — chrome.js resolves the docs root from wherever _oku/ sits and fetches it there. Drop on any static host.","meta":"humans, HTTP"},{"t":"dist/standalone/","b":"Single-file artifacts. Every HTML inlines kit JS, CSS, page JSON, glossary bundle, and the manifest as window.__okuManifest. One self-contained file per page that opens offline — email-as-attachment ready. No sidecar manifest or llms.txt needed.","meta":"humans, file://"},{"t":".md sources + dist/site/llms.txt","b":"No twin tree: the .md page sources ARE the canonical AI/LLM surface. The build drops one llms.txt sitemap (one line per page: URL + title + summary, convention from llmstxt.org) at the site root, beside the manifest.","meta":"AI / LLM consumers"}]}
```

> [!SUCCESS] Pagefind search — optional dependency
> If pagefind is on PATH (brew install pagefind, or npx pagefind), build also indexes dist/site/ into dist/site/pagefind/. Soft-fails without it. The search button in the chrome only works on built sites.

## Layout / chrome — not in the page JSON {#layout-chrome}

page-chrome, page-nav, page-toc are set in the HTML stub, not the page JSON. The stub copy-pastes from src/html_doc/templates/starter.html and you usually don't touch it.

```html
<page-chrome></page-chrome>

<div class="layout">
  <page-nav></page-nav>
  <main id="main-content"></main>
  <page-toc></page-toc>
</div>

<script>
  window.addEventListener('DOMContentLoaded', function () {
    OkuRenderer.autoBoot();
  });
</script>
```

- `<page-chrome>` — system cluster top-right (search, warning, theme cycler). Edge tabs for sidebars. Visual Viewport pinch-zoom tracker.
- `<page-nav>` — boxed site-tree at the top of the Contents drawer; reads site-manifest.json (or the inline window.__okuManifest in standalone builds). Marks the active page. The Contents button in the top-left chrome strip drives it, and what it does depends on how you use it: hover and the panel appears over the page until you pick a heading or move away, leaving the measure untouched; click and it pins, insetting the column so you can read with the outline beside you and the highlight following your position. Clicking a heading in a pinned panel navigates without closing it. Below 900px there is no room to inset, so a click opens it over the page as before. Footer at the bottom carries the kit version.
- `<page-toc>` — section-TOC stacked under the site tree inside the same left sidebar. Heading reflects the current page title; the list is built from main > section > h2/h3 after the renderer fires oku:rendered.

> [!TIP] Customizing the layout
> The kit defaults work for ~all KB pages. For one-off pages (a single-page artifact, no nav), drop the `<page-nav>` element from the stub. Without it the layout falls back to two-column (TOC on left, like v1). The renderer doesn't care; it only owns `<main>`.

## Cross-cutting features {#cross-cutting}

Behaviors that don't introduce a new block kind but change how an existing one renders.

### Citation cards via ext-ref {#ext-ref-cards}

Existing `ext-ref` entries auto-promote to type-themed citation cards (paper / rfc / release / blog / other). Type is read from the extref entry or inferred from the link domain. Inline cite text inherits the type's color on its dotted underline; the hover card carries a type-tinted icon, a mono domain pill, optional author + date row, and a summary.

Inline sample — hover any reference to see the card: see [Iceberg paper](#x/Iceberg paper) for the original snapshot-isolation argument, [RFC 9457](#x/RFC 9457) for the HTTP problem-details format, and the [Iceberg 1.4 release](#x/Iceberg 1.4 release) for cross-engine sort orders.

### Synced hover pairs · [data-bind] {#data-bind}

Add `bind: "step-3"` to any two blocks and they flash together when either is hovered or focused. Click one — the offscreen partner scrolls into view. One-line opt-in per pair; no kind change required.

Inline sample — hover or focus this paragraph and the callout below tints in sync. They share the same data-bind key.

> [!TIP] Paired callout
> Hovering the paragraph above lights this callout's border. Hovering this callout lights the paragraph. Same key, both directions.

### Last-updated line {#meta-updated}

`meta.updated` renders as a quiet italic line under the cover meta row. Pure trust signal — readers learn at a glance how fresh a page is.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"page\",\n  \"title\": \"My note\",\n  \"meta\": {\n    \"date\": \"2026-05-10\",\n    \"updated\": \"2026-05-18\",\n    \"read_time\": \"~3 min\"\n  },\n  \"blocks\": [ ... ]\n}","lang":"json"},"output":"<div style=\"padding:14px 16px; background:var(--surface-2); border:1px solid var(--border-soft); border-radius:10px; line-height:1.5;\"><div style=\"font:600 22px Inter,sans-serif; color:var(--text); margin-bottom:6px;\">My note</div><div style=\"font-size:12.5px; color:var(--text-soft); letter-spacing:0.02em;\">~3 min read · 2026-05-10</div><div style=\"margin-top:4px; font-size:11.5px; color:var(--text-faint); font-style:italic; letter-spacing:0.02em;\">Last updated 2026-05-18</div></div>"}
```

### Admonition vocab aliases {#admonition-aliases}

Callout `type` accepts both the kit's original names (`warn / warning / danger / success / neutral`) and the industry-standard aliases (`note / tip / info / caution`). Each row below is the same canonical styling reached from two different vocabularies.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"note\",\n  \"title\": \"note · alias of neutral\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!NOTE] note · alias of neutral\n> `type: \"note\"` reads the same as `type: \"neutral\"` — generic informational tint."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"tip\",\n  \"title\": \"tip · alias of success\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!TIP] tip · alias of success\n> `type: \"tip\"` matches `type: \"success\"` — green guidance accent for positive advice."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"info\",\n  \"title\": \"info\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!INFO] info · alias of neutral with informational tint\n> Same surface as neutral; reserved name keeps Docusaurus / Mintlify habits intact."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"caution\",\n  \"title\": \"caution · alias of warning\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!CAUTION] caution · alias of warning\n> Amber border + icon; same look as `type: \"warning\"`."}
```

[^ref-demo]: Definitions may appear anywhere on the page — the renderer collects them before it emits anything, then lists the referenced ones here.

[pagefind-site]: https://pagefind.app "Pagefind"
