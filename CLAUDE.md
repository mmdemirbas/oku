# CLAUDE.md — oku

Onboarding notes for a fresh Claude Code session in this repo.
Read this before touching code. Skip nothing — every rule below was
the answer to a real bug the user pointed out.

The project is **oku** (Turkish imperative "read!"). Every layer
reads `oku`: the Python package (src/oku/), the CSS prefixes
(okt- / okc- / okd-), the JS globals (__oku*), the custom-event
names (oku:*), the data-attrs (data-oku-*), and the custom-element
tag names (oku-chart, oku-snippet, oku-diagram, oku-annotated-code,
oku-cite).

The only remaining mention of the legacy name "html-doc" is the
GitHub remote URL itself (`github.com/mmdemirbas/html-doc`) — used
by the schema `$id`, the `git clone` example, and the jsdelivr CDN
URL. Rename the GitHub repo and flip those when convenient; this
file is the catalog of the one exception.

## What this repo is

A shared HTML chrome kit + a Python CLI (`oku`) that authors
single-source **markdown pages** and renders them in the browser via
Custom Elements. No build step for content; the CLI converts each
`.md` source into a v2 page dict (`md_to_v2_page`) on the fly and
`renderer.js` walks it at page load.

Authoring shape: `docs/<page>.md` (source) + `docs/<page>.html` (thin
stub that loads the kit; it fetches `<page>.json`, which `oku serve` /
`oku build` synthesize from the .md).

### Page format (v3 — markdown-first)

A page is a `.md` file: YAML front-matter + a GFM body. The body is
**plain markdown**; kit primitives live in typed fences whose body is
ONE compact JSON object (same payload shapes as the schema `$defs`):

````markdown
---
title: Architecture
accent: teal
date: 2026-06-11
order: 40
summary: Runtime mental model + build pipeline.
---

> [!TLDR]
> Short summary.
>
> - bullet 1
> - bullet 2

## Section title {#anchor-id}

Lead paragraph with *emphasis* and `code`.

```oku-chart
{"type":"bar","rows":[{"label":"a","value":60},{"label":"b","value":80}]}
```

```mermaid
flowchart TB
  A --> B
```

*An italic line right after a mermaid fence becomes the caption.*
````

- Fence tags: `oku-chart`, `oku-table`, `oku-kpi-grid`, `oku-step-flow`,
  `oku-compare-grid`, `oku-example`, `oku-insight`, `oku-live-snippet`,
  `oku-annotated-code`, `oku-chart-grid`, `oku-tldr`, `oku-diagram` —
  plus plain `mermaid` (GitHub renders it natively).
- `##` opens a `<section>`, `###` is a sub-heading inside it. `{#id}`
  overrides the auto-slug. Glossary / ext-refs: `[label](#g/term-id)`,
  `[label](#x/source-id)`.
- Admonitions are GFM blockquotes: `NOTE`, `TIP`, `IMPORTANT`,
  `WARNING`, `CAUTION` + the kit's `TLDR`. `> [!NOTE] Title` carries
  an optional title.
- **Strict-GFM subset** (linted): no indented code blocks, no setext
  (`===`) headings, no lazy blockquote continuation. The subset is
  valid GFM, so GitHub/Obsidian render every page.
- **HTML islands**: a block-level HTML tag at column 0 (custom
  elements and `<script>`/`<style>` included) passes through to the
  DOM untouched — full capability, no restrictions. `oku check` lists
  every island as an info-level audit line; external markdown viewers
  strip islands. Inline HTML in prose stays literal text.
- Definition lists (`Term` / `: def`), task lists (`- [x]`), footnotes
  (`[^id]` + `[^id]: …`) and reference-style links (`[text][label]`,
  `[label][]`, `[label]` + `[label]: url "title"`) are supported.
  Both reference forms resolve **page-wide**, not per b[] string —
  `md_to_v2_page` splits a page at every typed fence, so a definition
  routinely lands in a different string than its reference. Footnotes
  render as numbered superscripts plus one "Footnotes" section at the
  end of the page. `oku check` warns on a reference with no definition
  (it would otherwise render as literal text with no other signal).

### Older pages (v1/v2 JSON)

JSON pages keep rendering indefinitely: v2 (`k/t/m/b`) natively,
v1 (`kind/title/blocks`) via the in-memory shim. Run
`oku migrate [path]` to convert any page-JSON to a v3 `.md` source
(deterministic, round-trips; the .json is removed).

### Alternative source formats (comparison phase)

Markdown is the default, but the pipeline accepts five source
formats through one registry (`_PAGE_SOURCE_PARSERS` /
`_PAGE_SOURCE_EMITTERS` in cli.py): `.md`, `.json` (v1/v2),
`.src.html` (HTML-first — the two-dot suffix keeps sources distinct
from stubs), `.adoc` (AsciiDoc subset), `.dj` (djot subset). Every
format converts to/from the v2 dict; lint/build/serve/renderer see
only v2. The measured comparison lives in `docs/format-comparison.md`
with its provably-identical corpus under `examples/format-comparison/`
(round-trip parity enforced by tests). Prune a format = delete its
emit/parse pair + corpus dir; the decision is recorded in the roadmap
when made.

### Build outputs

`oku build` produces two single-purpose trees under `dist/`:
- `dist/standalone/` — self-contained single files (humans, file://).
  Each HTML inlines kit + page JSON + `window.__okuManifest`.
- `dist/site/` — shared-assets multi-page site with Pagefind search
  (humans, HTTP). Holds the one `site-manifest.json` chrome.js fetches
  + `llms.txt` at the docs root.

There is no `dist/markdown/` tree: the `.md` sources ARE the canonical
AI/LLM surface.

## Top-level files

| File | Owns |
|---|---|
| `chrome.js` | Custom Elements (chart with 28 render modes, diagram, live-snippet, annotated-code, glossary-term, ext-ref, page-chrome / page-nav / page-toc), init-time DOM enhancement (table chrome, code fold, line numbers, sidebar wiring, bar-chart hover/click-pin/legend toggle), Prism + Mermaid lazy loaders, glossary tooltip controller, lightbox with pan/zoom/pinch fullscreen. ~7k LoC. |
| `chrome.css` | All visual tokens (light/dark, --series-1..--series-10, --prose-width), layout grid (asymmetric bleed, four-mode content width), every primitive's styling. ~3k LoC. |
| `renderer.js` | page JSON → DOM mapping. Walks `b[]`; strings parsed by the GFM block parser (headings → sections, paragraphs, lists, GFM tables, fences — `oku-*`/`mermaid` fences lift to typed blocks, def-lists, task-lists, HTML islands w/ executing scripts, admonitions); typed objects dispatched to typed renderers. v1→v2 shim keeps older pages rendering. ~1.6k LoC. |
| `kit/schema/page.schema.json` | JSON-schema for page payloads. Every page (converted from .md) validates against it; the optional `jsonschema` dep makes the check active. Chart `type` enum here is the single source of truth for known chart types. |
| `kit/{glossary,extrefs}/<domain>.json` | Central glossary + ext-ref registries by domain; fetched at runtime by chrome.js. |
| `src/oku/cli.py` | `oku init / build / clean / check / migrate / serve` plus the v3 converter pair (`md_to_v2_page` / `page_to_md`), the strict-GFM + island lint (`_lint_md_string`), and the v1→v2 page shim (`_v1_to_v2`). |
| `src/oku/templates/` | `starter.{md,html}` — pair to copy when starting a new page. |
| `bin/oku` | PEP 723 shim — run without install via `uv run bin/oku …`. Points at `oku.cli:main`. |
| `docs/` | The kit's own documentation, authored via the kit. Use these as canonical examples. `docs/roadmap.md` tracks open phases. |

## Installing the tool globally

Other projects reach the kit through a globally installed `oku`, which
carries its OWN COPY of `kit/` inside the wheel. Editing this repo does
not change what those projects build with until the tool is reinstalled:

```bash
uv tool install --force --no-cache --from . oku   # --no-cache is load-bearing
oku --version    # oku 0.4.0 · kit 2026-08-03-r13 · assets /…/site-packages/oku/assets
```

`--force` alone is NOT enough: uv reuses the cached wheel when the
version string in `pyproject.toml` has not changed, so the tool silently
stays on the old kit while reporting a successful install. Either bump
the version on a kit change, or pass `--no-cache`. `oku --version`
prints the kit build stamp (`__okuKitBuild` in chrome.js) — compare it
against the repo's to see whether a project is building with the current
kit. A page rendered by a stale tool is the usual cause of a "the kit
regressed" report; check the stamp inlined in the artifact first
(standalone HTML files carry it).

## Develop / verify

```bash
uv sync --extra dev           # pulls pytest, ruff, jsonschema
oku check                     # schema + structural lint (the fast verify gate)
oku check --strict            # exit 1 on warnings too
oku build                     # writes dist/{standalone,site}/
oku serve --no-watch          # local server (live-reload on by default)
uv run pytest -q              # 300+ tests; should all pass
uv run ruff check . && uv run ruff format --check .
```

`oku check` is the canonical verify step for any doc-content
change — it runs the schema + a suite of structural checks (deprecated
kinds, duplicate anchors, unresolved glossary terms / ext-refs,
forbidden process language, chart shape sanity per type — including
the Tier 3 chord / geo / sankey / network / scatter-matrix /
parallel-coordinates payload shapes). Run it before calling a doc
change done. `oku build` invokes the same checks internally and
refuses to ship if it errors.

After ANY change to chrome.js / chrome.css: hard-reload the browser
(`location.reload(true)` from the page console, or close the tab and
re-open). The dev server doesn't cache aggressively, but Chrome
itself often holds the prior script in memory and the symptom looks
like "my change didn't take effect" — it did; the runtime is stale.

## Rules the user has set down

**Contents drawer, centred content.** `page-nav` adopts `page-toc` as
a child at boot so site-tree + on-page TOC stack in one panel. NO
dual-pane, NO right-side TOC.

The panel is an **overlay drawer at every width** — parked off-canvas
at `left: -100%`, slid in by `body.drawer-open`, with a scrim, Escape
and outside-click to close. `main` is `margin-inline: auto`, so the
measure is centred and **never moves when the drawer opens**. On a wide
window the drawer lands in the empty gutter beside the column.

One affordance: the **`.ctrl-btn.drawer-toggle` in the top-left chrome
strip**, labelled "Contents" (icon + visible text, `aria-expanded`,
`aria-controls`). It is visible at every width.

Removed, do not bring back: the permanent sidebar grid column, the
full-height right-edge handle (`.page-nav-edge`) that doubled as
resize + collapse, the 24px collapsed rail, and the persisted
`sidebarCollapsed` / `sidebarWidth` state. A line down the page that
reflows the text every time it is used is what this replaced.

**Neutral count visual language.** Stats counter / chip badges /
group count badges render bare numerals ("5" or "3/5"), never
English words. The page can flip to TR or EN without touching kit
code.

**No demo sibling pages.** Every example for a primitive lives
inside `docs/reference.md` next to the primitive's heading: code
sample + rendered block. Don't create `docs/<thing>-demo.{html,json}`
— `src/oku_tests/test_content_regression.py::TestNoStrayDemoPages` enforces.

**No process/round/historical references in docs.** "Round-N",
"v2 review", "fixed in round 5" etc. are forbidden in `docs/*.md`.
Refer to current behaviour, not how it got here. Past sessions left
this kind of breadcrumb in many places; `git grep -i round docs/`
should return nothing relevant.

**Tables read as one card.** `.okt-table-wrap` carries a border +
padding so two consecutive tables don't bleed into each other. The
filter input + stats counter sit together on the left; chip rack is
a two-column grid (label, chips) directly under the controls bar.
Group count badges go FIRST in the group header (before the title)
so the numbers line up at a consistent x.

**Code blocks: line numbers + language pill + brace folds.** Every
`<pre><code>` gets a gray gutter with line numbers (`.okt-code-gutter`,
`user-select: none` so copy excludes them). When a language class is
present, a small label appears at top-right of the pre. JS / TS /
JSON / CSS code blocks gain a fold marker on every line ending with
`{`, `(`, or `[`; click hides lines until the matching closer at
the same indent. The fold pass is hooked into Prism's `complete`
event because the autoloader replaces innerHTML asynchronously per
block — a `.then()` chain after `highlightAll()` races and loses.

**Add a regression test with every fix.** The user has explicitly
called out that bugs keep recurring because tests don't cover the
surface. For Python CLI behaviour use pytest under
`src/oku_tests/`. For doc-content regressions use
`src/oku_tests/test_content_regression.py` (walk the doc tree,
assert on shape). For runtime browser behaviour add Playwright tests
under `src/oku_tests/browser/` — wired and running in the default
suite against the real serve handler in headless chromium
(`test_invariants.py` pins the numeric UI invariants below; the
package auto-skips where chromium isn't installed, enable with
`uv run playwright install chromium`). Whatever the layer, the rule
is: a bug found by the user must have a test that fails before the
fix and passes after.

## UI invariants — numeric, enforced

Four rules that prevent the regression class the user has had to
correct repeatedly. Each is phrased as a binary numeric invariant so
a test can assert it. "Looks right" is not an acceptable
formulation — if you can't state the rule as a `boundingBox` /
computed-style assertion, the rule isn't found yet.

1. **Sidebar surface always spans the visible viewport.** If a sidebar
   exists, its background+border extends from `y=0` to `y=innerHeight`
   at every scroll position and on every page. Content inside may
   overflow with its own scrollbar, but the surface never ends
   mid-page. Numeric: `page-nav.boundingBox.height === innerHeight`
   (±1px). Set `height: 100vh` AND `height: 100dvh` — `max-height`
   alone lets content shrink the element.

2. **Hidden modes have a visible reveal.** Collapsed sidebars, closed
   drawers, hidden details — every hidden state keeps a clickable
   affordance visible. No invisible-toggle states. Numeric: the rail
   (collapsed sidebar) is ≥ 18px wide and click-targetable; the
   reveal control's `boundingBox` is non-zero and inside the
   viewport.

3. **Layout invariants are numeric, not eyeball.** Anything you would
   state as "X should look right" can be phrased as a numeric
   assertion: bounding-box position, dimension, or computed style.
   If you can't phrase it numerically, you haven't found the rule
   yet. Don't ship a "fix" backed only by a screenshot — the
   screenshot is evidence, not the rule.

4. **Browser-verify before claiming "fixed".** Pytest is necessary,
   not sufficient. UI changes get opened in a real browser via
   Playwright at desktop AND ~360px width; the relevant
   `boundingBox` figures land in the commit message body as the
   verification record. The record is the proof — no record means
   no verification.

## Common pitfalls

- **Stale chrome.js in the browser.** The CDN-loaded Prism autoloader
  fires `complete` twice per block (once before the language module
  arrives, once after). The line-wrap / fold pass guards against the
  second pass via `code.querySelector('.okt-code-line')` — DO NOT
  guard with a one-shot `data-` attribute; the second Prism pass
  wipes the spans, and a one-shot guard then refuses to re-apply.

- **CSS rules silently dropped by Chrome.** A multi-line comment
  inside a rule body, containing certain Unicode punctuation, has
  been observed to make Chrome's parser drop the trailing
  declaration. If a rule that should win according to specificity
  ISN'T winning, move the comment outside the braces.

- **page-toc adoption is async.** `PageNav.connectedCallback` queues
  a microtask to adopt the sibling `page-toc`. If you query the
  sidebar shape during init you'll see them as separate elements
  until the microtask runs.

- **`tldr` is allowed inside contentBlock** (recent schema change).
  Don't refactor the schema to remove this — the primitives reference
  embeds a live tldr sample alongside its code example.

## Browser verification flow

1. `oku build` (validates schema + emits artifacts).
2. `oku serve --no-watch --no-search`.
3. Open the changed surface in a browser.
4. Force a hard reload (`Cmd+Shift+R` / `Ctrl+Shift+R`) — soft reloads
   keep the prior chrome.js in memory.
5. Walk the user-facing path (filter, group-by, chip toggle, fold,
   collapse, etc.) and verify; not just look at the screenshot.
6. Encode the verification as a content-regression test (or a future
   Playwright test).

## What NOT to do

- Don't introduce a `docs/<thing>-demo.{html,json}` page. Fold demos
  into `docs/reference.md`.
- Don't reintroduce the dual-pane sidebar / right-side TOC / mid-edge
  collapse tab. They were explicitly removed.
- Don't add English words to count badges or stats text. Numbers only.
- Don't say "since round N" / "fixed in round N" in docs.
- Don't claim a fix is done after only running pytest. The Python
  test surface doesn't cover the browser behaviour where most bugs
  hide.
- Don't add an `!important` to win a cascade fight before checking
  whether a sibling rule is dropping a declaration silently (see
  pitfalls above).
