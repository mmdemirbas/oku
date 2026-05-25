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
single-source JSON pages and renders them in the browser via Custom
Elements. No build step for content; the
kit is loaded as static assets and `renderer.js` walks the JSON
tree at page load.

Authoring shape: `docs/<page>.json` (data) + `docs/<page>.html` (thin
stub that loads the kit and the page JSON). `oku build` produces
three single-purpose trees under `dist/`:
- `dist/standalone/` — self-contained single files (humans, file://).
  Each HTML inlines kit + page JSON + `window.__okuManifest`.
- `dist/site/` — shared-assets multi-page site with Pagefind search
  (humans, HTTP). Holds the one `site-manifest.json` chrome.js fetches.
- `dist/markdown/` — `page.md` twins + `llms.txt` (AI/LLM consumers).
  Single canonical home; not duplicated across the human trees.

## Top-level files

| File | Owns |
|---|---|
| `chrome.js` | Custom Elements (chart with 28 render modes, diagram, live-snippet, annotated-code, glossary-term, ext-ref, page-chrome / page-nav / page-toc), init-time DOM enhancement (table chrome, code fold, line numbers, sidebar wiring, bar-chart hover/click-pin/legend toggle), Prism + Mermaid lazy loaders, glossary tooltip controller, lightbox with pan/zoom/pinch fullscreen. ~7k LoC. |
| `chrome.css` | All visual tokens (light/dark, --series-1..--series-10, --prose-width), layout grid (asymmetric bleed, four-mode content width), every primitive's styling. ~3k LoC. |
| `renderer.js` | JSON → DOM mapping. `_renderTable`, `_renderTldr`, `_renderExample`, `_renderBars`, `_renderMultiBars`, inline kinds including `html`. ~1k LoC. |
| `kit/schema/page.schema.json` | JSON-schema for page sources. Every `docs/*.json` validates against it; the optional `jsonschema` dep makes the check active. |
| `kit/{glossary,extrefs}/<domain>.json` | Central glossary + ext-ref registries by domain; fetched at runtime by chrome.js. |
| `src/oku/cli.py` | `oku init / build / clean / check / serve` plus the markdown converter (front-matter, nested lists, footnotes, def-lists, ref-links, sanitised inline HTML) and the `_md_block` markdown twin emitter. |
| `src/oku/templates/` | `starter.{json,html}` — pair to copy when starting a new page. |
| `bin/oku` | PEP 723 shim — run without install via `uv run bin/oku …`. Points at `oku.cli:main`. |
| `docs/` | The kit's own documentation, authored via the kit. Use these as canonical examples. `docs/roadmap.json` tracks open phases. |

## Develop / verify

```bash
uv sync --extra dev           # pulls pytest, ruff, jsonschema
oku check                     # schema + structural lint (the fast verify gate)
oku check --strict            # exit 1 on warnings too
oku build                     # writes dist/{standalone,site,markdown}/
oku serve --no-watch          # local server (live-reload on by default)
uv run pytest -q              # 249+ tests; should all pass
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

**Single LEFT sidebar.** `page-nav` adopts `page-toc` as a child at
boot so site-tree + on-page TOC stack in one column. NO dual-pane,
NO right-side TOC. The sidebar is `position: sticky` with its own
scroll — main scrolls under it.

Two affordances toggle / size it, both edge-anchored (no top-left
button on wide viewports):
- **Right-edge handle** (`.page-nav-edge`, full-height): click without
  drag → collapse to a 24px rail; drag → resize the sidebar width
  (persisted as `--sidebar-width` + `localStorage.sidebarWidth`).
- **Collapsed rail** (24px column, chevron pointing right): click
  anywhere on it → re-expand.

The two affordances are symmetric: full-edge expand AND full-edge
collapse. The old top-left `.ctrl-btn.toc-toggle` was removed.

On narrow viewports (`≤768px`) the column becomes an off-canvas
drawer (`body.drawer-open` slides it in, backdrop dims the page,
Escape or backdrop click closes). The `.ctrl-btn.drawer-toggle`
hamburger appears in the chrome strip only at this width — it's the
only top-left button on mobile. The right-edge handle is hidden in
drawer mode (the drawer IS the affordance).

**Neutral count visual language.** Stats counter / chip badges /
group count badges render bare numerals ("5" or "3/5"), never
English words. The page can flip to TR or EN without touching kit
code.

**No demo sibling pages.** Every example for a primitive lives
inside `docs/reference.json` next to the primitive's heading: code
sample + rendered block. Don't create `docs/<thing>-demo.{html,json}`
— `src/oku_tests/test_content_regression.py::TestNoStrayDemoPages` enforces.

**No process/round/historical references in docs.** "Round-N",
"v2 review", "fixed in round 5" etc. are forbidden in `docs/*.json`.
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
`src/oku_tests/`. For JSON-content regressions use
`src/oku_tests/test_content_regression.py` (walk the doc tree,
assert on shape). For runtime browser behaviour add Playwright tests
under `src/oku_tests/browser/` (not yet wired — install
`pytest-playwright` + `playwright install` first). Whatever the
layer, the rule is: a bug found by the user must have a test that
fails before the fix and passes after.

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
  into `docs/reference.json`.
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
