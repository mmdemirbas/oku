# BUGS.md — open defects

A log of confirmed defects, newest first. One entry per defect.

Each entry carries: **symptom**, **minimal reproduction**, **expected vs
actual**, **where the failure was localised**, and — separately — what was
*observed* versus what was *inferred from reading source*. Do not collapse
those two: a mechanism read out of code is a hypothesis until it is executed.

Close an entry by deleting it once the fix is committed. The commit message
carries the record, including what was measured before and after.

---

## A dot-plot whose values are years labels its top tick `1.4k`

- **Symptom.** A `dot-plot` with `min` 400 and `max` 1450 (Hijri death
  years) prints its x-axis ticks as `400`, `925`, `1.4k`. The last label is
  compact and also wrong: the tick sits at 1450, not 1400. Setting
  `"tick_format": "number"` on the block changes nothing.
- **Minimal reproduction.**

  ````markdown
  ```oku-chart
  {"type":"dot-plot","title":"Vefat yılı","x_label":"Hicrî yıl","tick_format":"number","min":400,"max":1450,"rows":[{"label":"A","value":537},{"label":"B","value":911},{"label":"C","value":1311}]}
  ```
  ````

  `oku build`, then read `svg.okc-dot-plot text.okc-tick` in
  `dist/standalone/<page>.html`.
- **Expected vs actual.** Expected `400 925 1450`. Actual `400 925 1.4k`.
- **Where.** Inferred from source: `_renderDotPlot` labels its three ticks
  (min, midpoint, max) through `fmtTicks`. `fmtTicks` keeps `fmtNum`'s
  labels when each one is within a tenth of a step of its tick. Here the
  step is 525, and `1.4k` reads as 1400, which is 50 away from 1450 and
  inside the 52.5 tolerance, so the compact label stands. The fix in
  3edb687 targeted repeated labels; one rounded `k` label passes its test.
  `tick_format` is declared for every chart (`$defs/chart/properties` in
  `page.schema.json`) and passes `oku check --strict`, but renderer.js
  forwards it only into the gantt extras, and only the gantt tick code
  reads it.
- **Observed.** The tick text above, read with Playwright (oku 0.6.5,
  kit 2026-10-18-r131, repo 0200385, 2026-10-19). Found in atolye
  `raporlar/2026-10-14-evrad-duzeltme.md`; the workaround there puts the
  year into each row label.

## In print, a table that breaks across pages hides the top of the continuing row under its header

- **Symptom.** When a table breaks across a page in a printed page, the
  header row repeated at the top of the next page is painted over the row
  that continues from the previous page. The first lines of that row cannot
  be read.
- **Minimal reproduction.** Not reduced yet. Seen on atolye
  `raporlar/2026-10-14-evrad-duzeltme.md` (the witness table in section 3),
  built with `oku build` and printed from `dist/standalone/` with
  Playwright: `emulate_media(media="print")`, then
  `page.pdf(format="A4", print_background=True)`. A six-row table that fits
  on one page does not show it.
- **Expected vs actual.** Expected the repeated header to sit above the
  continuing row. Actual: in the report's PDF, page 10, the header covers
  the first five lines of the `Bihârü'l-Envâr` row; only its last two lines
  show.
- **Where.** `thead th` keeps `position: sticky; top: 0` in print. The
  `@media print` block in chrome.css does not reset it; the computed
  `position` of a `th` under print media is `sticky`. Inferred: Chromium
  paints the sticky cells at the top of the continuation fragment, on top
  of the row. `.okt-table-ghost` in print was not checked.
- **Observed.** Adding
  `@media print { th, thead, thead tr { position: static !important; top: auto !important } }`
  at print time makes the row print whole. A pixel diff of the 30-page
  PDF with and without that rule shows changes on pages 9–11 only. Page 1
  also differed, for an unrelated reason: one of the two builds had a
  `Last updated` line. Also, under print media with the window scrolled
  past a table, the `th` top is within 5 px of the last row's top (−632 vs
  −637). So printing from the browser after scrolling down may put the
  header on the last row. That is inferred; browser print was not tested.
  Kit 2026-10-18-r131, Playwright Chromium, 2026-10-19.
- **Workaround in use.** atolye `bin/dizgi/oku-pdf.py` injects the rule
  above at print time. Remove it there once this is fixed.

## Arabic text on an LTR page: an all-Arabic paragraph runs left-to-right, and an inline quote can reorder

- **Symptom.** Two cases on a `lang: tr` page that quotes Arabic.
  (a) A paragraph that is entirely Arabic gets `direction: ltr`. Its
  opening `«` sits at the left end of the first line, which is the end of
  the line for a right-to-left reader, and its last line is left-aligned.
  (b) In a Turkish sentence, `«الأمين» → «الأمان»` is displayed with
  `«الأمان»` on the left and `«الأمين»` on the right. The bidi algorithm
  makes the two Arabic quotes and the arrow one right-to-left run, so the
  arrow points the wrong way and the sentence says the opposite.
- **Minimal reproduction.**

  ```markdown
  > «بِسْمِ اللّٰهِ الرَّحْمٰنِ الرَّحِيمِ. إِلٰهِي أَنْتَ الرَّبُّ وَأَنَا الْعَبْدُ، وَأَنْتَ الْخَالِقُ وَأَنَا الْمَخْلُوقُ، وَأَنْتَ الرَّازِقُ وَأَنَا الْمَرْزُوقُ، وَأَنْتَ الْمَالِكُ وَأَنَا الْمَمْلُوكُ»

  Cümle içinde: «الأمين» → «الأمان» isteniyor.
  ```

- **Expected vs actual.** Expected: (a) the paragraph runs right-to-left,
  with `«` at the right edge and the last line right-aligned; (b) the
  quotes keep their written order around the arrow. Actual: (a) the
  computed `direction` is `ltr`; on a 732 px line, `«` is at x=0 and the
  first Arabic letter at x=694. (b) The x positions are `الأمين` 466, the
  arrow 435, `الأمان` 385.
- **Where.** The rendered `p`, `li`, `td` and `blockquote` elements carry
  no `dir`, and markdown has no way to set one. The workarounds used were
  a raw HTML island, `<p dir="rtl" lang="ar">`, for (a), which `oku check`
  reports as `html-island` and in which markdown is not parsed. For (b),
  U+2067 … U+2069 (RLI … PDI) around every inline Arabic quote.
- **Inferred, untested.** `dir="auto"` on block elements would make a block
  right-to-left when its first strong character is Arabic and leave
  Turkish blocks left-to-right. Text inside isolates does not count for
  `dir="auto"`, so a block that starts with an isolated quote stays
  left-to-right. For (b), wrapping each run of RTL script in `<bdi>` at
  render time would keep the written order.
- **Observed.** The measurements above, read with Playwright (kit
  2026-10-18-r131, 2026-10-19). The evrad report needed 144 isolate pairs
  and 4 raw HTML blocks to print correctly.

Open, found by the 2026-10-05 bug hunt and deliberately not fixed in it.
Each says why.

- **Two lint regexes are quadratic on a long line with no whitespace.**
  Observed: `_MD_LINK_TARGET_RE` over `"[a](b" * n` took 0.73 s at 10 KB,
  3.4 s at 20 KB, 10.8 s at 40 KB; `_HTML_TAG_RE` took 1.7 s over 36 KB of
  `<a href="`. A realistic 29 KB table row with spaces took 0.0 s.
  Deferred: the input is the author's own page. Fix when touched: bound
  the target length (`{1,2048}`) or skip lines over a few KB.

- **Every `.json` under the root is read and parsed in full, twice per
  build** (`find_json_pages`, `find_unparseable_json`). Inferred from
  source, not measured. A data repo with a large JSON pays it on every
  check. Fix: skip by size, or sniff the first bytes for `"k"`/`"kind"`.

- **The page tree sorts titles by `title.lower()` (Python) and
  `localeCompare` with no locale (chrome.js).** A Turkish tree orders
  `ılıca` after `İzmir`. Not changed alone, because `test_manifest_order`
  holds the two sides equal and Python has no locale collation without a
  new dependency (PyICU). Table sorting was fixed separately (page
  language collator).

- **Table group keys and filter values keep HTML entities.** Inferred:
  `stripHtml(td.innerHTML)` leaves `&amp;`, so grouping by a column
  holding `A & B` shows `A &amp; B` and a column filter typed `a & b`
  matches nothing. Fix: carry the cell's `textContent` beside its HTML.
  Not via a detached `innerHTML` decode, which would load `<img>` sources.

- **A viewer render that throws falls back to the Source view without a
  word** (chrome.js, the `renderMarkdownInto` catch in the viewer).
  Inferred; no trigger found. Fix: `console.error` and disable the
  Rendered button as the no-renderer branch does.

- **Offline first build reports the wrong thing about Prism, and copies
  empty vendor directories.** Observed: with the vendor cache empty and
  no network, the build printed "no grammar for hcl, python — those
  blocks render as plain text", while with the Prism core unvendored the
  CDN supplies every grammar; and empty `vendor/fonts/` and
  `vendor/prism/` were copied into dist. `oku serve` also keeps the
  `@font-face` rules when the fonts are absent (eight 404s), where both
  builds drop them. Mitigated: `./ctl deploy` now refills the cache.

- **`./ctl setup docs` links a project's `_oku` at the repo checkout**,
  because it scaffolds through `uv run --project $REPO`. That project
  then serves this repo's working copy, uncommitted changes included,
  instead of the installed kit. Inferred from source.

- **The `updated` date is the committer's local date (`%cs`), not UTC.**
  A commit just after midnight at UTC+3 shows the previous UTC day.
  Inferred; arguably what an author expects, so not changed.

No other open defects.

The six that were here before are closed:

- **A `muted` series in a bar chart was filled with the accent colour,
  while its legend swatch was grey.** Closed in the commit that removed
  this entry. The fill rules covered `warn`, `danger` and `success`; a
  muted fill kept the base `.bar-row .bar-fill` background. Measured
  before on every bar shape (single, stacked, grouped; horizontal and
  vertical): muted fills computed to `--accent`, rgb(99, 102, 241) light
  and rgb(165, 180, 252) dark, against `--text-soft`, rgb(84, 80, 73) and
  rgb(200, 194, 183). After: every fill and swatch of every tone equals
  its token in both themes. Held by
  `browser/test_bar_tone_matches_its_swatch.py`.

- **A typed fence inside an HTML island made the island report as
  unclosed — and the renderer had already dropped what it held.** One
  cause, two failures, and the report named only the loud one. A lifted
  `oku-*` fence splits the prose around it into two `b[]` strings, and
  both the renderer's open-element stack and the lint's were per-string,
  so the `</details>` was scanned in a later block than the `<details>`.
  Closed in `2959d36`. The half nobody saw, measured before the fix on an
  island holding a paragraph, an `oku-insight` fence and a second
  paragraph: `{figureInside: false, paragraphsInside: 1, tailOutside:
  true}` — the figure and everything after it rendered as siblings of the
  island. After: `{figureInside: true, paragraphsInside: 2, tailOutside:
  false}`. Both stacks now outlive one block and both reset at `##`, so an
  island that genuinely never closes still errors and still names the line
  that opened it. Held by `test_check.py::TestATypedFenceInsideAnIsland`
  and the `typed` case in `browser/test_html_island_spans_blank_lines.py`.

- **Prism's autoloader asked for components the kit never vendors, one
  404 per page.** Closed in `6ddd373`. Both names come from a GRAMMAR
  reading the document's own content, not from anything an author tagged,
  and they get opposite fixes. `oku-chart` reached the autoloader because
  Prism's markdown grammar calls `loadLanguages()` on a fence's info
  string inside a markdown SAMPLE — refused now, by prefix, at the
  property the grammar actually calls. `regex` reached it because Prism's
  JavaScript grammar aliases a regex literal's source; that one is
  vendored, so the request is served. The entry's own guess was half
  right: it inferred the JavaScript grammar for `regex` and correctly
  marked that as read rather than executed, but it read the `oku-chart`
  request as the autoloader being "left free to ask for anything in the
  DOM", which is one layer above the caller. Before: `failed:
  ['prism-oku-chart.min.js']` with the wrap removed, `failed:
  ['prism-regex.min.js']` with the component removed. After: `failed:
  []`, seven components at 200. Held by
  `browser/test_prism_asks_only_for_what_it_has.py`.

- **`oku serve` bound every interface, and no version string said whether
  yours did.** The bind was fixed in `f785d1d`; what stayed open was that a
  build made before it could not be told apart from one made after. Closed in
  `725e477` — `oku --version` now prints `src sha256:<12>` (a prefix, so
  nobody runs `git cat-file` on it again) and `as of <date>`, the newest
  mtime among the files the digest covers. A digest compares; a date orders,
  which is the question a reader in another project is actually asking. Held
  by `test_tool_digest.py`.

- **`process-breadcrumb` fired on a report that legitimately cited a dated
  prior round.** The rule scoped itself by who WROTE the prose — pages
  materialised from repo markdown were exempt — which is the wrong question for
  a hand-authored measurement report correcting an earlier round. Observed at 29
  warnings on one document, all on correct prose, with `oku check --strict`
  exiting 1 and no way past it but rewriting each citation into a date. Closed
  in `3cfef3e` — `documents_history: true` in a page's front-matter exempts that
  one rule on that one page. Deliberately not folded into `skip_prose`, which
  would have taken `placeholder-text` with it, and deliberately not a kit.json
  switch, which would exempt pages written later from a file nobody opens while
  writing prose. Held by `test_check.py::TestAPageWhoseSubjectIsAHistory` (6
  failed before, 8 pass after).

- **An accent token the front-matter spec documents killed every diagram on
  the page.** Four of the seven documented tokens were missing from the
  renderer's palette map; `rose` and `slate` are not CSS named colours, so
  `--accent` computed to the literal string and Mermaid refused it. Closed in
  `2f7f2c8` — all seven carry a light and a dark family, a value outside the
  map is resolved by the browser before anything is written, and an
  unresolvable one keeps the default accent and says so. `oku check` gains
  `accent-unknown`. Held by `browser/test_accent_palette.py` (11 failed
  before, 20 pass after) and `test_colour_contrast.py`.

Three earlier ones — a page-adjacent image reaching neither dist output, an
HTML island cut at its first blank line, and code in an island that could not
both render and copy — are fixed in kit `2026-08-20-r44`. Each reproduction
now runs green as a test: `test_build_carries_assets.py`,
`browser/test_image_delivery.py`, and
`browser/test_html_island_spans_blank_lines.py`.

One thing recorded here was NOT a defect. A page named `index.md` in a tree
whose `index.html` came from `oku init` builds correctly, in either order —
`oku build` carries the page body into `dist/standalone/index.html` and
`dist/site/index.json` both times, measured on r44. The trap was in reading
the artifact, not in writing it.

A second was not a kit defect either. `var(--series-N-soft)` in a mermaid
`classDef`, reported as "the skill documents it and the kit does not ship
it": the repo has shipped those tokens since kit `2026-08-14-r62`, and the
reporting tool read `kit 2026-08-20-r50`. That is stale-tool drift, and
`./ctl deploy` is the fix. `oku check` now says `diagram-unknown-token` and
names `oku --version`, so the next one arrives as a build warning rather than
as a parse-error card in a browser.

A third was **mostly** not a kit defect, and it is worth recording because the
symptom looks alarming. A doctree of 31 pages reported **23 errors** and `oku
build` refused the whole tree, including pages with no findings of their own.
**22 of the 23** were author-side, in three documents written months earlier; the
23rd, an `island-unclosed`, turned out to be the kit bug closed above in
`2959d36` — this paragraph originally claimed all 23 were author-side and that
was wrong. The 22: 12
`fence-not-lifted` and 1 `shadowed-source` from a stale page-JSON left beside
its migrated `.md` (the walkers prefer the `.json`, so it shadows the source —
documented `--keep-json` behaviour), 7 `schema` from v1 block payloads whose
keys the schema has since renamed (`title`/`content`/`num`/`meta` → `t`/`b`),
and 2 `duplicate-anchor`.

The kit's behaviour was correct at every stage, which is the part worth
keeping: `oku check` named each one with `file:line` and the offending key;
`oku build` refused and printed `Not building … or pass --allow-errors`,
emitting **zero** `file:///` URLs and writing nothing, so a refused build
cannot be misread as a successful one — independently measured on a
three-page tree with one schema-invalid page, refused run exit 1 / 0 URLs / no
`dist` against `--allow-errors` exit 0 / 9 URLs / 4 files; and when forced
through with
`--allow-errors`, the renderer replaced each failed block with a visible
`div.okd-error-card.okt-block-err` naming the missing field, plus a precise
`block-contract` console warning. Verified in a browser on kit
`2026-08-23-r67`: the failing block's payload sits only in the page's
`display:none` source `<script>`, is not visible anywhere in the body, and the
reader gets the error card instead — content degrades loudly, never silently.

What this episode does suggest, as a **feature request rather than a defect**:
`oku migrate` converts a page from JSON to markdown but does not migrate v1
block payload keys to v2, so a document written against the old shape fails
with no mechanical path forward. The failure is loud and specific, so nothing
is lost — it is hand work that a codemod could do.
