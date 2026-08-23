# BUGS.md — open defects

A log of confirmed defects, newest first. One entry per defect.

Each entry carries: **symptom**, **minimal reproduction**, **expected vs
actual**, **where the failure was localised**, and — separately — what was
*observed* versus what was *inferred from reading source*. Do not collapse
those two: a mechanism read out of code is a hypothesis until it is executed.

Close an entry by deleting it once the fix is committed. The commit message
carries the record, including what was measured before and after.

---

No open defects.

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

A third was verified and is not a defect. `oku build` refusing the whole tree
when any page has errors is documented behaviour: it prints `Not building. Fix
the errors above, or pass --allow-errors to ship anyway`, emits zero `file:///`
URLs and writes nothing, so a refused build cannot be mistaken for a successful
one. Measured on a three-page tree with one schema-invalid page — refused run
exit 1 / 0 URLs / no `dist`; `--allow-errors` exit 0 / 9 URLs / 4 files.

A second was not a kit defect either. `var(--series-N-soft)` in a mermaid
`classDef`, reported as "the skill documents it and the kit does not ship
it": the repo has shipped those tokens since kit `2026-08-14-r62`, and the
reporting tool read `kit 2026-08-20-r50`. That is stale-tool drift, and
`./run install` is the fix. `oku check` now says `diagram-unknown-token` and
names `oku --version`, so the next one arrives as a build warning rather than
as a parse-error card in a browser.

A third was not a kit defect, and it is worth recording because the symptom
looks alarming. A doctree of 31 pages reported **23 errors** and `oku build`
refused the whole tree, including pages with no findings of their own. All 23
were author-side, in three documents written months earlier: 12
`fence-not-lifted` and 1 `shadowed-source` from a stale page-JSON left beside
its migrated `.md` (the walkers prefer the `.json`, so it shadows the source —
documented `--keep-json` behaviour), 7 `schema` from v1 block payloads whose
keys the schema has since renamed (`title`/`content`/`num`/`meta` → `t`/`b`),
2 `duplicate-anchor`, 1 `island-unclosed`.

The kit's behaviour was correct at every stage, which is the part worth
keeping: `oku check` named each one with `file:line` and the offending key;
`oku build` refused and printed `Not building … or pass --allow-errors`,
emitting **zero** `file:///` URLs and writing nothing, so a refused build
cannot be misread as a successful one; and when forced through with
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
