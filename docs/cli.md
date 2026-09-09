---
title: CLI reference
eyebrow: Reference
subtitle: Nine commands: oku init, build, clean, spec, vendor, verify, migrate, check, serve. Designed so you mostly forget the CLI exists.
date: 2026-05-18
order: 50
summary: oku init / build / clean / spec / vendor / verify / migrate / check / serve — what each does.
---

> [!TLDR]
> init scaffolds the cwd as a docs root: _oku symlink + index.html entry stub. build emits two single-purpose trees — dist/standalone/ and dist/site/ (with manifest + llms.txt + Pagefind). clean wipes dist/. migrate converts page-JSON sources to v3 markdown. check lints every page. serve runs a local HTTP server and synthesizes the manifest, llms.txt and kit.json in memory — source dirs stay clean apart from the one entry stub.
>
> - init treats cwd as the docs root. Run it from wherever you want pages to live (typically cd into your docs/ subdir first).
> - Source dirs hold MD (or legacy JSON) plus a single index.html entry stub so IDE-served workflows work without the dev server running.
> - build is idempotent; safe to re-run. dist/standalone/ and dist/site/ are wiped each time.
> - clean removes dist/ entirely — no-op if it's already absent.
> - serve synthesizes the manifest fresh on each request — no source writes.
> - jsonschema is a required dependency (page validation); pagefind is the opt-in `oku[search]` extra (search index).

## oku init {#init}

One-time per docs root. Creates a _oku symlink so pages can reference _oku/chrome.js etc., and an index.html entry stub that IDE-served workflows open directly (IntelliJ's built-in HTTP server, Live Server, etc.). Both land in cwd — there is no implicit docs/ subdir.

```bash
cd ~/path/to/your-project/docs
oku init

# ✓ Linked /path/to/your-project/docs/_oku -> /path/to/oku/kit
# ✓ Created /path/to/your-project/docs/index.html
#
#   Author pages as <name>.md next to index.html (JSON still works).
#   Open index.html in your IDE, or run `oku serve` from the
#   project root for a live-reloading dev server.
```

> [!NEUTRAL] Idempotent + self-healing
> Re-running init is safe. If the symlink already resolves to the kit, it prints "already linked". If it points to a stale target (e.g. the kit repo moved), init transparently refreshes it. A non-symlink file at _oku is treated as user data and refused. An existing index.html is left untouched so your edits survive.

## oku build {#build}

Walks the current directory, produces every dist artifact. Run before deploying dist/site/, before sharing dist/standalone/ files, or any time a search index needs to refresh. Source dir is never written to.

```bash
cd ~/path/to/your-project
oku build

# ✓ Doctree check: 6 page(s) clean
# ✓ Wrote dist/site/site-manifest.json (6 JSON page(s))
# ✓ Wrote dist/site/llms.txt
# ✓ Synthesized 6 stub(s) for pages without on-disk .html
# ✓ Pagefind index built: dist/site/pagefind/
# ✓ Built 6 HTML file(s):
#
#   standalone (inline, send-as-file):
#                file:///.../dist/standalone/docs/index.html
#                ...
#
#   site (shared assets, multi-page):
#   site root:   file:///.../dist/site
#                ...
```

```oku-step-flow
{"steps":[{"t":"Walk *.json and *.md pages recursively","b":"Skips dist/, _oku/, node_modules/, .git/, venv/, __pycache__/, every dot-directory, and anything in kit.json's skip_dirs. A project may also add its .gitignore to that list with kit.json \"skip_gitignored\": true — off by default, because what a project keeps out of version control and what it keeps out of its site are two different questions. With it on, check and build say in one line what git pruned. Treats files with kind:\"page\" (and any .md) as pages."},{"t":"Schema validation","b":"Every page is checked against kit/schema/page.schema.json. Errors print with field paths. jsonschema is a required dependency, so an installed oku always runs this pass; the plain `python3 bin/oku` path can miss it, and there build prints a one-line hint and skips."},{"t":"build_standalone — single-file per page (humans, file://)","b":"For each page, synthesize the HTML stub in memory, inline chrome.css/.js, chrome-boot.js, renderer.js, the page JSON, the kit bundle, and the site-manifest seed (window.__okuManifest). One self-contained file per page; no sidecars. Output to dist/standalone/ with directory structure preserved."},{"t":"build_site — multi-page deployable (humans, HTTP)","b":"Write a per-page stub + copy the source JSON to dist/site/ with directory structure preserved. Copy the kit once into dist/site/_oku/. Write a single site-manifest.json at the site root, beside the copied kit (chrome.js resolves the docs root from wherever _oku/ sits and fetches it there at runtime). Inject extracted text into hidden data-pagefind-body for indexing."},{"t":"build_llms_txt (LLM consumers)","b":"Drop one llms.txt sitemap (llmstxt.org convention) at the site root, beside the manifest. The .md page sources are the canonical AI/LLM surface, so no twin tree is emitted."},{"t":"Pagefind index (optional)","b":"Run pagefind over dist/site/, preferring the bundled binary from the pagefind[bin] Python package (install it with the oku[search] extra), then a pagefind on PATH, then npx pagefind. Output to dist/site/pagefind/. Soft-fails with an install hint if none is available."}]}
```

> [!WARN] build stops on a check error
> The doctree check runs first, and an error ends the build with exit code 1 — a schema error names a payload the renderer will draw wrong or not at all, so shipping it puts the broken page in front of the reader. The errors print either way. `--allow-errors` builds anyway, for a tree with a legacy page you are not ready to fix; it says on the console that it took that path.

> [!NEUTRAL] build replaces its dist trees, it does not empty them first
> Every page is written into `dist/.build-<pid>/` and moved into place at the end, so a build that fails partway costs the new pages and nothing else — the previous dist/standalone/ and dist/site/ are still there, whole, and the error says so instead of raising a traceback. The swap is also where stale trees go: dist/markdown/ from an older version, and dist/_search/, the serve-time Pagefind index that nothing else removed — a stale one keeps answering for pages the source no longer has. Anything else you have parked under dist/ is left alone, by build and by oku clean alike.

### How do I know the page I am reading is current? {#build-provenance}

You cannot tell by looking at the content, which is how a fixed bug gets reported a second time from an old file. So every built page carries its own provenance in the sidebar footer, under the site tree:

```
oku v0.6.5 · kit 2026-08-14-r37
built 3 days ago                     [Rebuild]
```

`kit` is the same field `oku --version` prints, spelled the same way, so the footer and the terminal compare directly. The stamp carries its own date — that is what lets one number answer "how old is this file" without knowing what the current one is.

**Rebuild copies a command. It does not run one, and it cannot.** A page opened from a `file://` URL or off a static host has no channel to a shell. The one surface with a live server is `oku serve`, and there `_oku/` points at the installed kit, so a served page is never the stale one — a real rebuild button would work only where nothing needs it. Clicking reveals the command and copies it:

```bash
cd ~/code/notes && oku build
```

The `cd` is there because an artifact says nothing about where its source sits, and you are reading it from somewhere else. The path collapses to `~` under your home directory, and it is written only into `dist/` and the standalone files — never into the committed `index.html` stub.

**A page written to leave the machine can drop the command.** `~/code/notes` names a layout rather than an account, but a layout is still something the page hands to everyone it reaches. Set `"rebuild_command": false` in kit.json and the command goes, and the button with it — there is no disabled state, because the footer draws nothing when the field is absent:

```json
{"name": "notes", "rebuild_command": false}
```

Everything that is about the artifact rather than about where it was made stays: the version, the kit stamp, the build age, and the drift warning. On by default, because the failure this section exists for is a page that could not say how old it was — a page that should not say where it came from is the exception, and an exception is a thing a project asks for.

What the page cannot tell you is how far behind the installed kit it is. Learning that means asking the network, and a document should not call home because a colleague opened it. `oku build` prints that comparison instead, at the one moment it holds both numbers:

```
✓ Built 12 HTML file(s):
  kit 2026-08-11-r33 → 2026-08-14-r37
```

### What `oku --version` answers {#version-line}

The other end of the same question: not "how old is this page" but "does the tool that built it have the fix I am reading about".

```
oku 0.6.5 · kit 2026-08-23-r67 · src sha256:014095589d4b · as of 2026-08-23 09:15 · assets /Users/you/.local/share/uv/tools/oku/...
```

| Field | Reads | Answers |
|---|---|---|
| `oku` | the package version | which release |
| `kit` | the hand-bumped stamp in chrome.js | did the *kit* change |
| `src` | a sha256 over every file the wheel ships | is this build byte-identical to another one |
| `as of` | the newest mtime among those same files | is this build older or newer than a given date |
| `assets` | where the installed kit lives | which copy of the kit is being read |

`src` compares; it does not order. Two builds either match or they do not, and a digest cannot say which came first — printed as twelve bare hex characters it also reads as an abbreviated git commit, which is how a reader ended up running `git cat-file` on one and getting "Not a valid object name". The `sha256:` prefix is part of the value for that reason, and `as of` is the field that orders: a fix that landed on the 22nd at 16:38 is not in a build dated 11:53 the same day.

`uv tool install` writes every file at the moment it installs, so `as of` is the install time for an installed tool and the last edit for a checkout. Both are "the code as of", which is what the field is called.

## oku clean {#clean}

Remove the trees the build writes under dist/ — standalone/, site/, _search/ and a markdown/ left by an older build — and nothing else. Idempotent, and dist/ itself goes only when those were all it held. Source files and the _oku symlink are untouched.

```bash
oku clean

# ✓ Removed /path/to/your-project/dist

# With something of your own parked in there:
oku clean

# ✓ Removed dist/standalone, dist/site
#   Kept 2 entries oku did not write: NOTES.md, keepme

# Second run, nothing left:
oku clean

# ✓ Nothing to clean — /path/to/your-project/dist does not exist.
```

- Useful before publishing a release artifact, switching branches, or just to ensure a fresh build.
- Safe to chain: oku clean && oku build.
- Doesn't touch source pages, the _oku symlink, or kit.json. Only generated output.
- dist/ is a conventional name, not one this tool owns. It used to remove the whole directory, so a deploy script or a data file parked beside the build went with it; now the survivors are named in the output.

## oku spec {#spec}

Print a ready-to-paste payload for any block kind or chart type. The kit
has 14 block kinds, 53 chart types and 3 inline kinds, and the shape of
each is the one thing an author cannot infer from the page they are
writing.

```bash
oku spec                # every name, grouped
oku spec sankey         # the fence, ready to paste
oku spec table --json   # the payload alone, no fence
oku spec filepath       # an inline kind: the syntax, and when to use it
oku spec front-matter   # every page-level key, with what it does
oku spec kit            # every kit.json key, with what it does
```

The three inline kinds — [filepath](reference.md#filepath),
[glossary-term](reference.md#glossary-term) and
[ext-ref](reference.md#ext-ref) — are written as a link inside a
sentence rather than as a fence, which is why they were listed nowhere
until they were listed here. Each prints its syntax and a note saying
*when* to reach for it; the syntax alone answers how, and an author
deciding between a code span and a chip is asking when.

Two names in that list are not block kinds. `front-matter` prints every
page-level key; `kit` prints every key of the tree's `kit.json`. Both read
the schema they document rather than a list written beside it, so neither
can fall behind the tool — which is exactly how `kit.json` came to carry
five keys the tool read and its own schema refused.

```oku-table
{"headers":["Argument","Default","Effect"],"rows":[["`name`","—","A block kind (`table`, `kpi-grid`, …), a chart type (`sankey`, `gantt`, …) or one of the two topics, `front-matter` and `kit`. Omit it to list every name. An unknown name exits 1 and suggests the nearest matches."],["`--json`","off","Print the bare payload instead of the fence that wraps it. Useful when composing a payload programmatically."]]}
```

The examples ship inside the wheel, so this works from any project that
installed the tool — unlike [the reference page](reference.md), which
lives in the kit's own docs tree. Every example is asserted valid
against both the schema and the structural checks, so what it prints
passes `oku check` unchanged.

## oku verify {#verify}

Open the built pages in a headless browser and report what a source
check cannot see. `oku check` reads the source; this reads the result.

```bash
oku build && oku verify

# ✓ 38 page(s) render clean at 1440px and 360px
```

```oku-table
{"headers":["Checked","Why a source check cannot"],"rows":[["Diagrams drew","The source parses; the renderer is what fails, and only in a browser."],["No figure is an empty box","A wrong-but-valid payload validates and renders nothing. This is the failure the schema cannot reach by construction."],["No sideways scroll at 1440px or 360px","Overflow is geometry. It has no representation in the source."],["No console or page errors","An island's script throwing is invisible to every static check."]]}
```

Needs a browser: `uv tool install 'oku[verify]'` then
`playwright install chromium`. Without it the command says so and exits
2 rather than reporting a pass it did not get.

A failing request to a remote origin is ignored — that is the network's
state, not the page's, and a check that fails for reasons the author
cannot fix stops being believed. Local files missing IS reported.

## oku vendor {#vendor}

Fetch the shared runtime files once so built pages work with no network.
mermaid draws the diagrams, Prism colours the code, and four variable
woff2 files carry the two typefaces the layout is measured in — all of
which used to arrive from a third party on every page view.

```bash
oku vendor            # fetch what is missing
oku vendor --update   # re-fetch (a new upstream release)
```

```oku-table
{"headers":["Argument","Default","Effect"],"rows":[["`--update`","off","Re-fetch even when a copy is present. Use after pinning a new upstream version."],["(none)","—","Fetch only what is missing. `oku build` does this automatically the first time, so most projects never run the command."]]}
```

The files land in the installed kit's `vendor/` directory, so they are
fetched once per machine and shared by every project. `oku build` copies
one `_oku/vendor/` beside the output; every page reads that copy and
falls back to the CDN if it is not there.

The fonts have no CDN behind them, deliberately. A page that fetches a
typeface tells a third party who is reading it, which is the reason they
were vendored; without the vendored copy a page renders in the system
stack instead, and the build ships no `@font-face` rule at all rather
than a URL pointing at a file it did not carry. Both Latin subsets are
fetched: `ş` and `ğ` live in latin-ext, so shipping only latin changes
typeface in the middle of a Turkish word.

They are **not** inlined into each page. mermaid is 3.3 MB against a
1.1 MB standalone page, so a tree would carry one copy per page that
draws anything. Offline does not require a single file — it requires the
bytes to be reachable.

## oku migrate {#migrate}

Convert page-JSON sources (v1 or v2) to v3 markdown. Each `foo.json` becomes `foo.md` next to it and the JSON is removed. Migration is optional — the renderer accepts v1/v2 pages indefinitely — so run it when you want the on-disk source in the current authoring format.

```bash
cd ~/path/to/your-project/docs
oku migrate

#   migrated architecture.json → architecture.md
#
# Migrated 1 page(s).

# Nothing left to convert:
oku migrate

# ✓ No page-JSON files found under /path/to/your-project/docs
```

```oku-table
{"headers":["Argument","Default","Effect"],"rows":[["`path`","`.`","File or directory to migrate. A directory is walked recursively; kit.json, site-manifest.json, package.json and tsconfig.json are skipped, as is anything that is not a page."],["`--dry-run`","off","Print the files that would change and write nothing. Still exits 0."],["`--keep-json`","off","Leave the source .json in place beside the emitted .md. The walkers prefer the .json, so a kept file shadows the .md until you remove it."]]}
```

Two guards make the deletion safe. A page whose `.md` already exists is skipped rather than overwritten, and every conversion is round-tripped in memory before the JSON is unlinked — the emitted markdown is parsed back and fingerprinted against the source. A page that does not round-trip losslessly is skipped with its source kept and a message asking you to report it.

Exit code is 1 only when the input path does not exist; a run that migrates nothing still exits 0.

## oku check {#check}

Lint every page in the project — `.md` sources and page-JSON alike. Schema validation plus structural / content checks. Fast — runs in milliseconds. Designed as the oku skill's auto-verify step.

```bash
oku check

# ✓ 11 page(s) clean (schema + structural + content)
#
# oku check --strict       # exit 1 on warnings too
# oku check --json         # machine-parseable output
# oku check --verbose      # also surface info-level nudges
# oku check --errors-only  # suppress warnings in the report
# oku check --fix          # rewrite what can be fixed mechanically, then re-check
```

Issues land at three severities. Exit code is 1 if any error is present (or any warning under --strict); 0 otherwise. Info notes are suggestions, so the report prints them only with `--verbose` — but it always says how many there are and which codes they carry, because a note nothing ever mentions is one nobody knows to ask for. `--fix` applies the findings it can apply — today that is `path-in-code-span`, rewritten in prose, in GFM cells and inside `oku-*` payloads — then re-checks the tree as rewritten, so the report you read is the state of your files now.

```oku-table
{"headers":["Severity","Codes","What it catches"],"rows":[["**error**","`schema`, `deprecated-kind`, `unknown-kind`, `invalid-block`, `duplicate-anchor`, `chart-*`, `stray-demo`, `no-title`, `front-matter-malformed`, `shadowed-source`, `json-parse-failed`","Page shape problems, removed primitives still in use, a body entry that is neither a markdown string nor a typed object, duplicate section / heading IDs, malformed chart payloads, demo pages outside docs/reference.md, a page without a title, a .json shadowing the source you edit. A page whose front-matter opened with `---` and hit a line that is not `key: value` — the block is being read as body text."],["**error** · markdown","`fence-not-lifted`, `setext-heading`, `island-unclosed`","An `oku-*` fence whose body is not a single JSON object of a known kind, so it stayed a code block instead of becoming a typed block. A setext (`===` underline) heading — the strict-GFM subset takes ATX `#` headings only. An HTML island whose tag never closes: everything after it is written inside it, so it takes the rest of the section — reported at the page end and at every `##`, because a section boundary ends the run of blocks the renderer emits in one pass."],["**warning**","`process-breadcrumb`, `placeholder-text`, `unresolved-glossary`, `unresolved-extref`, `unresolved-link`, `unresolved-anchor`, `filepath-missing`, `filepath-outside`, `path-in-code-span`, `image-outside`, `unknown-meta-key`, `accent-unknown`, `translation-anchor-drift`, `kit-invalid`","Prose containing process/history references (round-N, vN-review, fixed-in-round; the kit documents current behaviour only) — in a paragraph, in a typed payload and inside an HTML island alike, since an island is markup the reader sees through. A page whose SUBJECT is a history — a report citing the round it corrects, an audit, a changelog — declares `documents_history: true` in its front-matter and is exempt from this one rule; every other check still applies to it. Prose still carrying a placeholder (`TODO`, `TBD`, `FIXME`, `XXX`, `lorem ipsum`, or an unfilled `{{ }}` template) — in a paragraph, in a typed payload and inside an HTML island alike, since a step body, a card and the text between a `<div>`'s tags are all prose an author writes. A `<pre>` or `<script>` body is not: that is code, and `// TODO: implement` in a sample is the sample. One inside a code span is the token being NAMED rather than left behind, so it is not flagged; this row spells its own four that way. Glossary terms and ext-refs that do not resolve against kit/glossary/ and kit/extrefs/. A link or image pointing at a file that does not exist relative to the page, or at a `#fragment` that is not a heading id on the page it names. A `#f/` file reference with no file at that path, or one resolving outside the project root — a page carries the bytes of the files it previews, so a reference reaching past the project would publish them, and that chip renders as a path to copy and nothing else. A code span naming a file that is really there — the reader has to leave the page and go and find it, where a `#f/` chip previews on hover, opens on click and copies the path; only a span holding a SEPARATOR is judged, so a bare `kit.json` — the file a sentence tells the READER to create — is left alone, and `oku check --fix` rewrites every one of them. A front-matter key the kit does not know, with the nearest one it does. An `accent:` that is a bare word and is neither one of the seven the kit tunes nor a CSS colour name — the browser cannot parse it, so the page keeps the default accent; only bare words are judged, since a hex or an `rgb(...)` is the browser's to read. A heading id present on one language of a page and not on its translation — the language switch carries the reader's fragment across, so it drops them at the top of a page they were deep inside. An image, `<img src>` or `srcset` candidate resolving to a real file outside the project root — a standalone page carries the bytes of everything it shows, so that reference would hand a file from outside the project to whoever the page is sent to, and neither build tree carries it. A `kit.json` key the kit does not read, named with the nearest one it does, or a value whose shape the schema refuses. Every setting in that file is read with a default behind it, so `personalisation` for `personalization` is not an error anywhere — it is every reader placeholder in the tree silently going unfilled, in the CLI, in the browser console and under `--strict` alike. `oku spec kit` prints the keys."],["**warning** · markdown","`ambiguous-hr`, `heading-level-skip`, `indented-code`, `lazy-continuation`, `undefined-footnote`, `undefined-link-reference`","A `---` directly under a text line: a setext heading in CommonMark, a thematic break in the kit — insert a blank line before it. A heading that jumps a level (`##` straight to `####`), which breaks the outline for screen readers and the on-page TOC. A four-space-indented block after a blank line, which CommonMark reads as a code block and the kit reads as a paragraph. A blockquote line continued without its `>`. A `[^id]` or `[label]` reference with no definition on the page — it renders as literal text with nothing else to signal it."],["**warning** · presentation","`redundant-meta`, `prose-only-section`, `island-hand-styled`, `diagram-unknown-token`, `group-of-one`, `figure-restates-headings`","A field that repeats another (`subtitle` verbatim from `summary`, `updated` from `date`). A section of three or more paragraphs with nothing for the eye — no table, chart, diagram, card grid or code block; a callout does not count. An HTML island carrying hardcoded colours or its own `<style>` instead of building on the kit's classes and CSS variables. A mermaid style line naming a `var(--token)` this kit does not define — the kit leaves an unresolvable token as written, so Mermaid meets `var(` and the whole figure becomes a parse-error card; the usual cause is a page written against a newer kit than the installed tool carries. A compare-grid / step flow / KPI grid / chart grid holding one member, where the primitive's whole job is the relationship between members. A diagram whose node labels are the page's own section titles."],["**info**","`code-no-language`, `no-summary`, `html-island`, `empty-table`, `hand-set-derivable`, `accent-divergence`, `filepath-not-carried`","Code blocks with no declared language. Pages with no meta.summary. HTML islands (they render in the kit, external markdown viewers strip them). A table with headers and no rows. A field set by hand where the build derives it. Three or more pages in one directory picking different accents with no default in kit.json. A `#f/` file too large to travel inside the page, so the chip names it and copies its path with no preview."]]}
```

> [!TIP] Adding to the oku skill flow
> Run oku check --strict before declaring an HTML artifact done. Use --json to surface findings programmatically. The linter is the fastest verification step in the auto-verify loop — no browser required.
>
> The presentation rules exist so the briefing does not have to carry them as prose. A style rule written in a guide decays, because nothing fails when it is ignored; a rule the linter applies does not. Only the decidable half lives here — whether the diagram carries the point is still a question for a reader.

## oku serve {#serve}

Local HTTP server in the project root. Synthesizes per-page .html stubs, site-manifest.json, and llms.txt in memory on each request — source dir stays clean. Picks the first free port from 9876.

```bash
oku serve

# ✓ Serving /path/to/your-project on http://localhost:9876
#   Stop with Ctrl-C.
#
#   HTML files:
#     http://localhost:9876/docs/index.html
#     http://localhost:9876/docs/reference.html
#     ...
```

- Walks up from cwd to find the directory containing docs/_oku; serves from there. Run from anywhere inside the project.
- First free port from 9876–9900. Caps at 9900 (if all taken, errors out).
- Synthesizes /<docs>/<name>.html stubs from sibling .json or .md files on the fly; same for site-manifest.json and llms.txt. No filesystem writes.
- Pagefind is not built by serve. Run oku build first if you need full-text search; serve falls back to in-page anchor search otherwise.
- Opens the first HTML it finds in the default browser. Ctrl-C to stop.

> [!TIP] Why HTTP, not file://
> Browsers apply different rules to local files than HTTP — symlink resolution, fetch, and ES module imports fail silently or behave inconsistently on file://. The local HTTP server sidesteps that. On macOS, opening a file:// URL also disables some same-origin policies that matter for the iframe sandbox in <live-snippet>. Always serve.

> [!NOTE] Optional flags
> <strong>--no-watch</strong> disables the filesystem watcher + live-reload (serve static only).<br><strong>--no-search</strong> skips the background Pagefind index generation at startup. Both default to on so the dev loop is rich; opt out if you want a leaner serve.<br><strong>--host</strong> is the address to bind, and it is <code>127.0.0.1</code> — this machine only. The server hands out the project root, working copy and all, so <code>--host 0.0.0.0</code> (to open the preview on a phone) makes every file under the root readable to anyone who can route to your machine, with no password. The startup line prints the address actually bound.

## Dependencies {#optional-deps}

One required, one opt-in.

```oku-compare-grid
{"cards":[{"t":"jsonschema — page validation, required","b":"Declared in the base `dependencies`, so every installed oku has it. It was optional once, and the consequence was a page `oku check` called clean while three of its blocks rendered as blank space — the installed tool had no jsonschema, the schema pass silently no-opped, and only the structural checks ran. The soft-fail branch survives for the one path that can still miss it: `python3 bin/oku` without uv. There, build prints a hint and skips validation.","verdict":"neutral"},{"t":"pagefind — search index, opt-in","b":"The `search` extra (`oku[search]`) pulls the `pagefind[bin]` package, which ships its own binary — no brew, npm or npx needed. A `pagefind` on PATH or `npx pagefind` also works; build tries the bundled binary first, then PATH, then npx. Without any of them: the search button still appears but says \"Search index not found\" when clicked. With one: build adds a ~50–100 KB pagefind/ directory to dist/site/.","verdict":"neutral"}]}
```

## Install + run {#future}

Worth noting because they're frequently asked.

Two ways to invoke the CLI.

### Installed via uv

```bash
uv tool install .
# Now `oku` is on PATH globally:
oku serve
```

Installs oku as a console script. The wheel packs chrome.{css,js}, schema/, glossary/, extrefs/ inside oku/assets/ and ships starter templates under oku/templates/, so init/build find everything without a git layout.

### In-tree without install

```bash
uv run bin/oku serve
# Or plain python3 — both work:
python3 bin/oku serve
```

[`bin/oku`](#f/bin/oku) is a thin shim that adds `src/` to sys.path and runs `oku.cli.main()`. PEP 723 inline metadata pulls jsonschema into an ephemeral venv when invoked via uv.
