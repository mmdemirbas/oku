# Changelog

## v2.0.0 — 2026-05-17 (unreleased)

Major version bump. Repositions the project from "single-page chrome
kit" to an opinionated **interactive knowledge platform** for
AI-emitted documentation and learning notes.

### Format

- **JSON pages** replace authored HTML as the source of truth.
  Each page is a `*.json` file under `docs/`, paired with a tiny
  `*.html` stub that bootstraps the runtime renderer.
- `renderer.js` — client-side tree walker that maps JSON nodes to
  Custom-Element DOM at load time. No build step for content.
- `schema/page.schema.json` — JSON Schema authoring contract. Editors
  with JSON Schema support get autocomplete.

### Primitives

- `<glossary-term>` — inline term with the new tooltip behavior:
  hover with 300ms bridge (tooltip survives mouse traversing toward
  it; text inside is selectable), click pins, Esc closes, touch
  devices click-only.
- `<ext-ref>` — inline external reference. Hover summary; click
  expands a card with the canonical link.
- `<callout>`, `<insight>`, `<info-tip>`, `<kpi-grid>`,
  `<compare-grid>`, `<scope-grid>` — content blocks.
- `<bar-chart>` — row-per-item horizontal bars (layout-safe).
- `<html-doc-chart type="scatter|line">` — generic data-driven SVG
  chart with axes, ticks, multi-series legend, optional point labels.
- `<html-doc-diagram>` — Mermaid wrapper, lazy-loaded from CDN,
  re-renders on theme toggle.
- `<html-doc-snippet>` — editable HTML/CSS/JS textarea + sandboxed
  iframe preview with debounce and reset.

### Chrome

- **Visual Viewport API tracker** keeps fixed-position chrome buttons
  anchored to the user-visible viewport during trackpad / touch
  pinch-zoom (Safari, Chrome on touch). Buttons translate by
  `--vv-left` / `--vv-top` CSS variables synced from
  `window.visualViewport`.
- **Three-column layout** when both `<page-nav>` and `<page-toc>` are
  present: nav left, main centre, section TOC right. Each sidebar
  carries its own edge-tab toggle on the inner edge (proximity rule).
- **Search button** in the top-right system cluster opens a modal
  search powered by Pagefind. Cmd/Ctrl+K shortcut.
- **Forward-compat warning indicator** in the system cluster lights
  up when `window.error`, `unhandledrejection`, an unknown node
  kind, a schema mismatch, or an unknown glossary term/ext-ref
  fires. Click opens a list panel with a per-session Dismiss.

### Glossary & ext-ref registry

- **Multi-domain** files under `glossary/<domain>.json` and
  `extrefs/<domain>.json`. Ships starter content for `data-platforms`,
  `web`, `ai-llm`. Empty structural stubs for `adhd`, `hadith`,
  `voice` ready for the user to populate.
- **Multi-language** entries — each term carries `en`, `tr`, etc.
  with per-language `def` and `link`.
- **Project config** in `docs/kit.json` declares active domains,
  preferred language, fallback chain, and project-local overrides.
- **Disambiguation** via `in="<domain>"` attribute when two active
  domains define the same term.

### Build pipeline

- `html-doc build` now also:
  - Walks `*.json` page files and emits `site-manifest.json`
    (consumed by `<page-nav>` at runtime).
  - Emits `llms.txt` — sitemap for LLM consumers, one line per page
    (llmstxt.org convention). HTML is the single source of truth;
    no per-page MD duplication.
  - Runs Pagefind over `dist/site/` if `pagefind` is on `PATH` or
    `npx` is available. Soft-fails if absent.
- `html-doc serve` refreshes manifest + llms.txt on startup.
- Three demo pages in `_internal/demo-page/` exercise every
  primitive end-to-end.

### Design principles graduate to system-level

- Four principles (proximity, hierarchy, schema, grouping) codified
  at `~/.claude/rules/design-principles.md` with explicit visual,
  content, and code layer applications. The html-doc skill applies
  them when generating any artifact.

### Templates

- `templates/starter.html` now bootstraps the v2 renderer.
- `templates/starter.json` is the page-content starting point.

### Breaking changes from v1

- Pages are authored as JSON, not HTML. v1 pages don't render under
  v2 chrome.js without a re-author.
- `<page-toc>` is now the right-side sidebar in the v2 three-column
  layout. The top-left `.ctrl-btn .toc-toggle` is hidden in v2
  layouts (edge tabs supersede it).
- Project must include a `docs/kit.json` declaring active glossary
  domains for `<glossary-term>` and `<ext-ref>` lookups to resolve.

## v1.1.0 — 2026-05-15

- `html-doc serve` — start a local HTTP server at the project root (the dir
  containing `docs/_kit/`), print HTTP URLs for every HTML, open the first
  in the default browser. Resolves the `file://` browser-restriction problem
  where symlinked kit assets fail to load silently.

## v1.0.0 — 2026-05-15

Initial release. Extracted from inline chrome used in early karar HTML docs
(odak project) and modernized.

- `chrome.css` — token system (light/dark), layout, TOC sidebar with
  76px top padding to clear the top-left ctrl-btn, reading aids, reusable
  components, print stylesheet.
- `chrome-boot.js` — synchronous pre-paint theme + TOC state from
  `localStorage`. Three-mode theme key: `theme-pref` ∈ {`light`, `dark`,
  absent = system}.
- `chrome.js` — `<page-chrome>` and `<page-toc>` Web Components,
  three-mode theme cycler (`system → light → dark → system`), TOC builder
  with scroll-spy, permalinks, progress bar, back-to-top, copy-to-clipboard,
  glossary tap support.
- `bin/html-doc` — CLI with `init` (creates `docs/_kit` symlink in current
  project) and `build` (always produces both `dist/standalone/` inline
  files and `dist/site/` with shared assets; zero flags). Prints output
  paths with `file://` prefix.
- `templates/starter.html` — minimal HTML scaffold referencing the kit.

### Decisions captured

- Per-project link via symlink (`docs/_kit -> ~/dev/mmdemirbas/html-doc`).
- Build always produces both standalone + site outputs; no mode flag.
- Per-page accent override via CSS variables, not template forking.
