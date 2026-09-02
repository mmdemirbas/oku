# BUGS.md — open defects

A log of confirmed defects, newest first. One entry per defect.

Each entry carries: **symptom**, **minimal reproduction**, **expected vs
actual**, **where the failure was localised**, and — separately — what was
*observed* versus what was *inferred from reading source*. Do not collapse
those two: a mechanism read out of code is a hypothesis until it is executed.

Close an entry by deleting it once the fix is committed. The commit message
carries the record, including what was measured before and after.

---

## Prism's autoloader asks for components the kit never vendors, one 404 per page

**Symptom.** Every built page that highlights JavaScript, and every page holding
an `oku-chart` fence, logs a failed request in the browser console:

```
net::ERR_FILE_NOT_FOUND .../_oku/vendor/prism/components/prism-regex.min.js
net::ERR_FILE_NOT_FOUND .../_oku/vendor/prism/components/prism-oku-chart.min.js
```

The page renders and most code still highlights, so nothing about the build
says anything is wrong. `regex` is a real Prism component that the kit does not
vendor; `oku-chart` is not a Prism language at all — it is one of the kit's own
fence names being handed to the autoloader as if it were one.

**Minimal reproduction.** No new page needed; the kit's own docs already do it.

```bash
$ oku build
$ node -e '(async()=>{const{chromium}=require("playwright");
const b=await chromium.launch();const p=await b.newPage();
p.on("requestfailed",r=>console.log(r.failure().errorText,r.url()));
await p.goto("file://'"$PWD"'/docs/dist/standalone/reference.html");
await p.waitForTimeout(6000);
console.log(await p.evaluate(()=>Prism.plugins.autoloader.languages_path));
await b.close()})()'
net::ERR_FILE_NOT_FOUND file://…/_oku/vendor/prism/components/prism-oku-chart.min.js
_oku/vendor/prism/components/
```

`docs/dist/standalone/architecture.html` and `cli.html` come up clean, so it is
the page's content that decides it, not the build. A page with a JavaScript
fence containing a regex literal produces the `prism-regex` line instead.

**Expected vs actual.** Expected: the autoloader is only asked for languages the
kit vendors, and kit fence names are never treated as Prism languages. Actual:
`languages_path` is pointed at a directory holding 29 components, and the
autoloader is left free to ask it for anything it finds in the DOM — including
`oku-chart`, which can never exist there.

**Where it was localised.** `kit/chrome.js:13434-13446` sets
`languages_path` to the vendored directory and preloads
`javascript, css, bash, json, yaml`; nothing after that constrains what the
autoloader may request. `kit/vendor/prism/components/` holds 29 files and
neither `prism-regex.min.js` nor `prism-oku-chart.min.js` is among them.

**Observed vs inferred.** *Observed:* the two failed request URLs, in a real
browser, on `docs/dist/standalone/reference.html` in this repo and on a
standalone page built elsewhere; `languages_path` read from the live page;
`language-oku-chart` present once in the built HTML of `reference.html`; the
29-file component listing with both names absent; `architecture.html` and
`cli.html` clean. *Inferred from reading, not executed:* that Prism's own
`javascript` grammar is what names `regex` — the vendored autoloader's
dependency map contains no `regex` entry, so the name has to be arriving from
the highlighted DOM. Also not measured: whether a JavaScript regex literal is
visibly less highlighted as a result, or only differently tokenised.

---

## A typed fence inside an HTML island makes the island report as unclosed

**Symptom.** A `<details>` island whose body contains a typed `oku-*` fence
raises `island-unclosed` as an **error**, so `oku check` exits 1 and `oku build`
refuses the whole tree. The island is correctly closed; the tags are balanced
and both sit at column 0. Replacing the typed fence with a plain ```` ```bash ````
fence and changing nothing else makes the page clean.

**Minimal reproduction.** Two pages in an empty tree, differing only in the kind
of fence inside the island:

```markdown
## S {#s}

<details class="card"><summary>Open me</summary>

Some prose inside the island.

```oku-insight
{"b":"A typed fence living inside an HTML island."}
```

</details>

Text after the island.
```

```
$ oku init && oku check
✗ 1 error(s):
  ✗ a-fence-in-island.md:8:b[0] line 8 [island-unclosed] HTML island <details>
    is never closed in this page. …
$ echo $?
1
```

The control page — same island, ```` ```bash ```` inside instead — reports no
error. Both have exactly one `<details>` and one `</details>`, at column 0.

**Expected vs actual.** Expected: an island holding a typed fence closes like any
other. Actual: it is reported unclosed, at error severity, which blocks the build
of every other page in the tree as well.

**Where it was localised.** `src/oku/cli.py:2606-2674`. `open_els` is per
prose-block, and the finding names `b[0]` — the block the island *opens* in.

**Observed vs inferred.** *Observed:* the two-page reproduction, the error and
its `b[0]` label, the clean control, balanced column-0 tags, and the same failure
on a real 200-line document. *Inferred from reading, not executed:* that lifting
the typed fence splits the surrounding prose into separate blocks, so the
`</details>` is scanned in a later block than the one holding `open_els`, and the
close is therefore never balanced against the open. The fix shape is not
attempted here — carrying island state across the blocks of one page, or
balancing before the split, are both plausible and I have not tested either.

**Impact seen in practice.** One 200-line document in an unrelated project; the
document is correct and the workaround is to move the fence out of the island,
which degrades a good page to satisfy a wrong check.

---

No other open defects.

The three that were here are closed:

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
23rd, an `island-unclosed`, turned out to be the kit bug now open at the top of
this file — this paragraph originally claimed all 23 were author-side and that
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
