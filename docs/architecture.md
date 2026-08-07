---
title: Architecture
eyebrow: Internals
subtitle: How the kit fits together at runtime. Useful when something doesn't behave as expected, or when you want to extend a primitive.
audience: Maintainer
date: 2026-05-18
order: 40
summary: Runtime mental model + build pipeline.
---

> [!TLDR]
> A page dict is walked by renderer.js at load time and turned into Custom-Element DOM. The CLI converts each `.md` source into that dict; page-JSON sources are already in it. chrome.js owns the behavior of those Custom Elements plus the page-level chrome (TOC, search, theme, warnings, viewport tracking). The whole kit lives in three JS files + one CSS file + JSON registry files.
>
> - Format: `.md` source → page dict → renderer.js walks it → Custom Element DOM → chrome.js attaches behavior.
> - kit.json + per-domain glossary/extref JSON files are the registry; loaded once at page start, resolved per element.
> - Visual Viewport API keeps fixed-position chrome buttons anchored during pinch-zoom on Safari.
> - Build pipeline (oku CLI) emits two single-purpose trees under dist/: standalone/ (self-contained HTMLs) and site/ (multi-page + Pagefind + manifest + llms.txt). The .md sources are the AI/LLM surface, so no twin tree is emitted.

## Layered overview {#overview}

Author content sits on top; the kit runtime hydrates it; build outputs flow out the bottom. Same kit, two distribution shapes.

```mermaid
flowchart TB
    subgraph A[Authoring layer]
      direction LR
      MD["docs/*.md"]:::auth
      JSON["docs/*.json — legacy"]:::auth
      KITJ["kit.json"]:::auth
    end
    subgraph R[Kit runtime — single _oku/ symlink]
      direction TB
      RND["renderer.js — tree walker, ~2.6k LoC"]:::rt
      CHR["chrome.js — Custom Elements + chrome, ~13k LoC"]:::rt
      CSS["chrome.css — tokens + every primitive"]:::rt
      REG["glossary / extrefs — per-domain JSON"]:::reg
    end
    subgraph O[Build outputs — two trees]
      direction LR
      STA["dist/standalone/ — self-contained"]:::out
      SIT["dist/site/ — multi-page + Pagefind + llms.txt"]:::out
    end
    JSON --> RND
    MD --> RND
    KITJ --> CHR
    REG --> CHR
    RND -->|oku rendered event| CHR
    CSS --> CHR
    A -->|oku build| O
    classDef auth fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
    classDef rt fill:#ccfbf1,stroke:#0f766e,color:#115e59,stroke-width:2px
    classDef reg fill:#e0e7ff,stroke:#4338ca,color:#312e81
    classDef out fill:#dcfce7,stroke:#15803d,color:#14532d
```

*Author → kit → build at a single glance.*

## Files in the kit {#files}

The kit repo contains all the runtime plus the registry data plus the CLI.

```text
oku/
├── bin/oku                       # PEP 723 shim — run without install
├── src/oku/                      # CLI: init, build, clean, migrate, check, serve
│   └── templates/                # starter page pair for `oku init`
├── src/oku_tests/                # pytest suite
├── kit/                          # chrome.{js,css}, chrome-boot.js, renderer.js,
│                                 # schema/, glossary/, extrefs/
├── docs/                         # this site — .md sources + _oku symlink
├── examples/                     # tour pages — same shape as docs/
└── README.md, CLAUDE.md
```

> [!TIP] Single-file split rationale
> chrome.js is ~13k lines in one file. Splitting it would mean either more script tags in every stub (worse onboarding) or a build step (more complexity, defeating the no-build-for-content goal). The current bet: one file with a clear table of contents at the top (see the section banner there). Reviewed each time the design changes shape; still wins on author ergonomics.

## Runtime — when a page loads {#render-flow}

From the moment the browser receives the HTML stub to the moment the page is interactive.

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant H as HTML stub
    participant Boot as chrome-boot.js
    participant C as chrome.js
    participant R as renderer.js
    participant K as kit.json + glossary/*

    B->>H: GET page.html
    H-->>B: 1KB stub
    B->>Boot: synchronous — set data-theme pre-paint
    Note over B: paint cover + chrome buttons (no FOUC)
    B->>C: defer-load chrome.js
    B->>R: defer-load renderer.js
    C->>K: fetch kit.json (DOMContentLoaded)
    K-->>C: domains, lang, overrides
    C->>K: fetch glossary/<domain>.json (parallel)
    K-->>C: domain entries
    H->>R: autoBoot()
    R->>B: fetch page.json
    B-->>R: page tree
    R->>B: emit Custom Element DOM
    R->>C: dispatch oku:rendered
    C->>B: build TOC + init reading aids
    B->>C: each <glossary-term>.connectedCallback resolves data-def
    Note over B: tooltips ready, search button visible
```

*Lifecycle of a page load.*

## The renderer {#renderer}

renderer.js is a tree walker. It maps each node's kind to a Custom Element instantiation (for interactive primitives) or directly to a styled DOM subtree (for prose primitives), and parses the markdown strings in `b[]` with its own GFM block parser. It is ~2.6k lines.

```mermaid
classDiagram
  class HTMLElement
  class OkuChart {
    +type, +title
    +_extras
    -_renderScatter() -_renderBar() -_renderDonut()
    -_renderHeatmap() -_renderRidgeline() -_renderTreemap()
    -_renderSankey() -_renderNetwork() -_renderChord()
    -_renderGeo() -_renderScatterMatrix() -_renderParallelCoordinates()
    -_wireInteractivity()
    -_attachToolbar()
  }
  class OkuDiagram {
    -_loadMermaid()
    -_render()
    -_attachToolbar()
  }
  class OkuLiveSnippet {
    -iframe, -textarea
    -_debouncedRender()
  }
  class OkuAnnotatedCode {
    -_injectMarkers()
    -_injectSubstringMarks()
    -_bindSync()
    -_moveMarkersToSlots()
  }
  class GlossaryTerm
  class ExtRef
  class PageChrome
  class PageNav
  class PageToc
  HTMLElement <|-- OkuChart
  HTMLElement <|-- OkuDiagram
  HTMLElement <|-- OkuLiveSnippet
  HTMLElement <|-- OkuAnnotatedCode
  HTMLElement <|-- GlossaryTerm
  HTMLElement <|-- ExtRef
  HTMLElement <|-- PageChrome
  HTMLElement <|-- PageNav
  HTMLElement <|-- PageToc
```

*Custom Element class layout. Renderer instantiates these by tag; chrome.js owns their lifecycles.*

```mermaid
stateDiagram-v2
  [*] --> WaitDOM : autoBoot()
  WaitDOM --> Fetching : DOMContentLoaded
  Fetching --> Parsing : page JSON arrives
  Parsing --> Walking : kind is page
  Parsing --> Failed : schema mismatch
  Walking --> Walking : _renderContentBlock(block)
  Walking --> Emit : tree exhausted
  Emit --> Done : dispatch oku rendered event
  Failed --> Done : warning fired
  Done --> [*]
```

*Renderer state — single pass over the tree; emits a CustomEvent at the end so chrome.js post-processors can pick up the new DOM.*

- `render(page)` — sets document.title, picks up accent override, renders cover, walks blocks.
- `_renderTopBlock` / `_renderContentBlock` — switch on kind; each kind has a small _renderX function.
- `_renderRich` — walks paragraph.content arrays mixing strings (textContent) with inline nodes (createElement).
- For complex primitives (chart, diagram, snippet), the renderer creates the Custom Element with attributes and a JSON-payload script child. The Custom Element's connectedCallback parses the payload and renders its own DOM.

> [!NEUTRAL] Why JSON-payload-as-script-child for complex primitives
> Attribute values can't safely encode multi-line strings or nested objects. A child <script type="application/json"> sidesteps the encoding problem entirely — the Custom Element does JSON.parse on its textContent.

## Tooltip controller {#tooltip}

Single global controller, attached to both glossary-term and ext-ref elements. ~150 lines.

```mermaid
stateDiagram-v2
  [*] --> Hidden
  Hidden --> Showing : mouseenter
  Showing --> Visible : 120ms delay elapsed
  Showing --> Hidden : mouseleave (before delay)
  Visible --> Hiding : mouseleave
  Hiding --> Visible : mouse enters tooltip DOM (bridge)
  Hiding --> Hidden : 300ms timer fires
  Visible --> Pinned : click on trigger
  Pinned --> Hidden : click outside | Esc | re-click trigger
  Pinned --> Pinned : hover stays on, no auto-hide
```

*Tooltip lifecycle. Hover and click paths are explicit; pinned is a sticky state with two exits.*

```oku-step-flow
{"steps":[{"t":"Hover detection","b":"matchMedia('(hover: none)') gates the hover path — touch devices skip it and use click only. Re-evaluated per attach so input-mode changes mid-session take effect on later elements."},{"t":"Show with delay","b":"120ms delay on mouseenter before showing — prevents flicker when brushing past."},{"t":"Bridge-hover","b":"On mouseleave, start a 300ms hide timer. If the mouse enters the tooltip DOM during that window, the timer cancels — the tooltip stays so the user can select text or click links."},{"t":"Click to pin","b":"Clicking the term pins the tooltip — it stays open until clicked again or another term is opened. Visible 2px accent ring marks pinned."},{"t":"Click outside / Esc","b":"Click anywhere outside .gloss or .tooltip-popup unpins. Escape key also unpins. Touch devices have click-only — no hover path, so click toggles pinned."}]}
```

## Visual Viewport API — pinch-zoom {#viewport}

Fixed-position chrome anchored to the user-visible viewport rather than the layout viewport. Without this, pinch-zoom on Safari moves the visual viewport and the chrome buttons drift off-screen.

```js
// chrome.js — runs at module init
var vv = window.visualViewport;
function sync() {
  document.documentElement.style.setProperty('--vv-left', vv.offsetLeft + 'px');
  document.documentElement.style.setProperty('--vv-top',  vv.offsetTop  + 'px');
}
vv.addEventListener('scroll', sync);
vv.addEventListener('resize', sync);

// chrome.css
.ctrl-btn { transform: translate(var(--vv-left,0), var(--vv-top,0)); }
```

Two CSS variables, one event handler. `?.` optional chaining gates the whole thing on Visual Viewport API support — graceful degrade on browsers without it (buttons stay at layout-viewport corners, same as v1).

## kit.json + glossary loader {#kit-loader}

Loads kit.json (project config) and per-domain glossary/extref files. Promise-based; returns a promise that resolves to the populated kit when all fetches complete.

```oku-step-flow
{"steps":[{"t":"Defer","b":"Initial load deferred to DOMContentLoaded — gives the standalone build a chance to inline the kit bundle before fetch tries to run."},{"t":"Standalone check","b":"If the page has an inline __oku_kit_bundle__ script (set by build_standalone), hydrate from it synchronously and skip all fetches."},{"t":"Standalone-but-no-bundle","b":"If __oku_page__ is present but no bundle (i.e., handwritten standalone), resolve with an empty kit — tooltips degrade to plain text rather than showing 'Unknown term' for everything."},{"t":"Dev / dist/site/ path","b":"Fetch kit.json + each domain's glossary/extref file in parallel. After Promise.all resolves, apply project-local overrides on top. Then resolve and unblock any waiters."}]}
```

## Docs-root discovery {#docs-root}

kit.json and site-manifest.json live at the docs root (the directory containing _oku/), not next to each page. The kit derives that root from any page depth so subdir pages resolve their assets without per-page configuration.

```js
// chrome.js — runs once at module init
var __okuDocsRoot = (function () {
  var refs = document.querySelectorAll('link[href*="_oku/"], script[src*="_oku/"]');
  for (var i = 0; i < refs.length; i++) {
    var url = refs[i].href || refs[i].src;
    var idx = url.indexOf('/_oku/');
    if (idx >= 0) return url.slice(0, idx + 1);  // ends with /
  }
  return new URL('.', window.location.href).href;  // fallback
})();
```

Any element referencing `_oku/` gives us a URL with the docs root as its prefix — strip everything from `/_oku/` onward. All kit.json, site-manifest.json, glossary/*.json, and pagefind/ fetches use this base, so subfolder pages work without per-page configuration.

## Build pipeline {#build}

`oku build` walks the project and emits two single-purpose dist/ trees, one per audience: standalone for a human reading one file, site for a human browsing a deployed tree. Pagefind is opt-in and soft-fails, so a project without it still builds.

```mermaid
flowchart LR
    subgraph IN[Project source]
      direction TB
      P["📄 *.json + *.md pages"]:::content
      H["🌐 *.html stubs"]:::content
      KJ["⚙ kit.json"]:::content
    end
    subgraph K[Kit — symlinked _oku/]
      direction TB
      KIT["🎨 chrome.css/js, renderer.js"]:::kit
      G["📖 glossary/*.json"]:::kit
      E["🔗 extrefs/*.json"]:::kit
    end
    BUILD(["⚒ oku build"]):::builder
    P --> BUILD
    H --> BUILD
    KJ --> BUILD
    G --> BUILD
    E --> BUILD
    KIT --> BUILD
    BUILD --> S["📦 dist/standalone/<br/>self-contained HTML"]:::output
    BUILD --> SI["🌍 dist/site/<br/>multi-page + manifest"]:::output
    BUILD -.-> PF["🔍 dist/site/pagefind/"]:::optional
    classDef content fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
    classDef kit fill:#ccfbf1,stroke:#0f766e,color:#115e59
    classDef builder fill:#fef3c7,stroke:#b45309,color:#78350f,stroke-width:2px
    classDef output fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef optional fill:#fef3c7,stroke:#b45309,color:#92400e,stroke-dasharray: 5 3
```

*Build inputs and the two dist trees. Colour codes: blue = author content; teal = kit runtime; green = build outputs; amber = optional dependency.*

1. walk the project recursively for *.md files plus JSON pages with `kind: "page"` (skipping project-meta files like README.md, CLAUDE.md).
2. validate every page against schema/page.schema.json; print errors with field paths. jsonschema is a required dependency, so this pass runs on any installed oku; the plain `python3 bin/oku` path can miss it and skips with a hint. Structural lint runs either way.
3. build_standalone: for each page, inline chrome.css + chrome.js + renderer.js + page JSON + kit bundle + window.__okuManifest seed into a single self-contained HTML. No external dependencies beyond Google Fonts and Mermaid CDN (when used).
4. build_site: copy every HTML stub + sibling JSON into dist/site/<rel-path>; copy _oku/ as dist/site/_oku/ once; embed extracted text via hidden data-pagefind-body div for indexing.
5. write a single site-manifest.json at the site root (dist/site/). chrome.js resolves the docs root by stripping back to whichever directory holds _oku/, and build_site copies the kit to dist/site/_oku/ once — so the manifest belongs beside it, with page paths relative to the project root.
6. build_llms_txt: emit one llms.txt sitemap at the site root, next to the manifest. The .md page sources are the canonical AI/LLM surface, so nothing is duplicated into a twin tree.
7. if pagefind is available — the bundled binary from the `oku[search]` extra first, then a `pagefind` on PATH, then `npx pagefind` — index dist/site/ to dist/site/pagefind/.

## Standalone kit bundle {#standalone-bundle}

build_standalone embeds the project's kit.json + active domain glossary + extref entries as one JSON script tag. The kit loader hydrates from it synchronously when present.

```html
<!-- dist/standalone/page.html — near the closing </body> -->
<script type="application/json" id="__oku_page__">{ ... page tree ... }</script>
<script type="application/json" id="__oku_kit_bundle__">{
  "kit": { "domains": ["data-platforms", ...], "lang": "en", ... },
  "glossary": { "data-platforms": { "ACID": { ... } }, ... },
  "extrefs":  { "data-platforms": { ... }, ... }
}</script>
```

> [!SUCCESS] Result — single-file offline tooltips
> A single HTML file you can email or archive. All Custom Elements work, tooltips resolve, the page renders. Network requirements: Google Fonts (graceful fallback if blocked) and Mermaid CDN (only if the page has a <diagram>). Everything else inlined.

## Internal architecture notes {#internal-architecture-notes}

Five behaviors worth knowing about if you're reading the kit code.

> [!NOTE] Kit assets resolver
> Two valid asset layouts: development (`kit/` in the repo) and installed (the same files inside `oku/assets/` in the wheel). `cli._kit_assets_dir()` picks whichever exists, so `oku init` works from a clone OR from `uv tool install .`. Hatchling `force-include` in pyproject packs the assets into the right place at wheel build time.

> [!NOTE] Generated artifacts live under dist/, never source
> `oku build` writes site-manifest.json and llms.txt at the site root (dist/site/), where build_site puts the shared _oku/ kit — that is the docs root chrome.js resolves at runtime, so page paths inside the manifest are relative to the project root. `oku serve` doesn't write at all — it synthesizes site-manifest.json, llms.txt and kit.json in memory on each request so source dirs stay authored-content-only.

> [!NOTE] Serve-time Pagefind
> `cmd_serve` spawns a background thread at startup that builds `dist/_search/site/` (just like `cmd_build`) and runs pagefind against it. Symlinks `<docs-dir>/pagefind` → that index so chrome.js's existing search-loader path resolves. Soft-fails if pagefind isn't installed. Opt out with `--no-search`.

> [!NOTE] Boot stamp
> chrome.js console.info()s `[oku] kit boot · build=<date> · docsRoot=… · authToken=yes/no` at startup. Bump `__okuKitBuild` whenever a compatibility-affecting change ships so a stale-cache user can confirm from DevTools whether their browser is on the right chrome.js.

> [!NOTE] IntelliJ _ijt token propagation
> chrome-boot.js plucks `_ijt` from `window.location.search` and exposes `window.__okuWithAuth(url)` that appends it to internal asset URLs (same-origin only — CDN URLs stay untouched). chrome.js and renderer.js wrap every fetch and script-src load through it so IntelliJ's built-in server stops 404'ing sub-resource requests.
