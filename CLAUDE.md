# CLAUDE.md — html-doc kit

Onboarding notes for a fresh Claude Code session in this repo.
Read this before touching code. Skip nothing — every rule below was
the answer to a real bug the user pointed out.

## What this repo is

A shared HTML chrome kit + a Python CLI (`html-doc`) that authors
single-source JSON pages and renders them in the browser via Custom
Elements. No build step for content; the kit is loaded as static
assets and `renderer.js` walks the JSON tree at page load.

Authoring shape: `docs/<page>.json` (data) + `docs/<page>.html` (thin
stub that loads the kit and the page JSON). `html-doc build` produces
`dist/standalone/` (self-contained single files) and `dist/site/`
(shared-assets multi-page site with Pagefind search).

## Top-level files

| File | Owns |
|---|---|
| `chrome.js` | Custom Elements, init-time DOM enhancement (table chrome, code fold, line numbers, sidebar wiring), Prism/Mermaid lazy loaders, tooltip controller. ~3.9k LoC. |
| `chrome.css` | All visual tokens (light/dark), layout grid, every primitive's styling. ~2.4k LoC. |
| `renderer.js` | JSON → DOM mapping. `_renderTable`, `_renderTldr`, etc. ~700 LoC. |
| `schema/page.schema.json` | JSON-schema for page sources. Every `docs/*.json` validates against it; the optional `jsonschema` dep makes the check active. |
| `src/html_doc/cli.py` | `html-doc init / build / serve` plus the `_md_block` markdown twin emitter. |
| `bin/html-doc` | PEP 723 shim — runs without install via `uv run bin/html-doc …`. |
| `docs/` | The kit's own documentation, authored via the kit. Use these as canonical examples. |
| `templates/starter.json` | Template emitted by `html-doc init`. |

## Develop / verify

```bash
uv sync --extra dev           # pulls pytest, ruff, jsonschema
html-doc build                # writes dist/standalone/ + dist/site/
html-doc serve --no-watch     # local server (live-reload on by default)
uv run pytest -q              # 125+ tests; should all pass
uv run ruff check . && uv run ruff format --check .
```

After ANY change to chrome.js / chrome.css: hard-reload the browser
(`location.reload(true)` from the page console, or close the tab and
re-open). The dev server doesn't cache aggressively, but Chrome
itself often holds the prior script in memory and the symptom looks
like "my change didn't take effect" — it did; the runtime is stale.

## Rules the user has set down

**Single LEFT sidebar.** `page-nav` adopts `page-toc` as a child at
boot so site-tree + on-page TOC stack in one column. NO dual-pane,
NO right-side TOC, NO mid-edge collapse tab. The top-left chrome
button (`.ctrl-btn.toc-toggle`) toggles `body.sidebar-collapsed`,
which shrinks the column to a 24px rail with a chevron. Clicking
anywhere on the rail re-expands. The sidebar is `position: sticky`
with its own scroll — main scrolls under it.

**Neutral count visual language.** Stats counter / chip badges /
group count badges render bare numerals ("5" or "3/5"), never
English words. The page can flip to TR or EN without touching kit
code.

**No demo sibling pages.** Every example for a primitive lives
inside `docs/primitives.json` next to the primitive's heading: code
sample + rendered block. Don't create `docs/<thing>-demo.{html,json}`
— `tests/test_content_regression.py::TestNoStrayDemoPages` enforces.

**No process/round/historical references in docs.** "Round-N",
"v2 review", "fixed in round 5" etc. are forbidden in `docs/*.json`.
Refer to current behaviour, not how it got here. Past sessions left
this kind of breadcrumb in many places; `git grep -i round docs/`
should return nothing relevant.

**Tables read as one card.** `.hdt-table-wrap` carries a border +
padding so two consecutive tables don't bleed into each other. The
filter input + stats counter sit together on the left; chip rack is
a two-column grid (label, chips) directly under the controls bar.
Group count badges go FIRST in the group header (before the title)
so the numbers line up at a consistent x.

**Code blocks: line numbers + language pill + brace folds.** Every
`<pre><code>` gets a gray gutter with line numbers (`.hdt-code-gutter`,
`user-select: none` so copy excludes them). When a language class is
present, a small label appears at top-right of the pre. JS / TS /
JSON / CSS code blocks gain a fold marker on every line ending with
`{`, `(`, or `[`; click hides lines until the matching closer at
the same indent. The fold pass is hooked into Prism's `complete`
event because the autoloader replaces innerHTML asynchronously per
block — a `.then()` chain after `highlightAll()` races and loses.

**Add a regression test with every fix.** The user has explicitly
called out that bugs keep recurring because tests don't cover the
surface. For Python CLI behaviour use pytest under `tests/`. For
JSON-content regressions use `tests/test_content_regression.py` (walk
the doc tree, assert on shape). For runtime browser behaviour add
Playwright tests under `tests/browser/` (not yet wired — install
`pytest-playwright` + `playwright install` first). Whatever the
layer, the rule is: a bug found by the user must have a test that
fails before the fix and passes after.

## Common pitfalls

- **Stale chrome.js in the browser.** The CDN-loaded Prism autoloader
  fires `complete` twice per block (once before the language module
  arrives, once after). The line-wrap / fold pass guards against the
  second pass via `code.querySelector('.hdt-code-line')` — DO NOT
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

1. `html-doc build` (validates schema + emits artifacts).
2. `html-doc serve --no-watch --no-search`.
3. Open the changed surface in a browser.
4. Force a hard reload (`Cmd+Shift+R` / `Ctrl+Shift+R`) — soft reloads
   keep the prior chrome.js in memory.
5. Walk the user-facing path (filter, group-by, chip toggle, fold,
   collapse, etc.) and verify; not just look at the screenshot.
6. Encode the verification as a content-regression test (or a future
   Playwright test).

## What NOT to do

- Don't introduce a `docs/<thing>-demo.{html,json}` page. Fold demos
  into `docs/primitives.json`.
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
