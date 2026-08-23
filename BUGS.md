# BUGS.md — open defects

A log of confirmed defects, newest first. One entry per defect.

Each entry carries: **symptom**, **minimal reproduction**, **expected vs
actual**, **where the failure was localised**, and — separately — what was
*observed* versus what was *inferred from reading source*. Do not collapse
those two: a mechanism read out of code is a hypothesis until it is executed.

Close an entry by deleting it once the fix is committed. The commit message
carries the record, including what was measured before and after.

---

## `process-breadcrumb` fires on a report that legitimately cites a dated prior round

**Symptom.** A hand-authored measurement report whose whole subject is
correcting an earlier published round cannot cite that round by name. Every
sentence naming it raises a warning, and `oku check --strict` exits 1. Observed
on a real document at 29 warnings, all from the same rule, all on correct prose.

**Minimal reproduction.** Two pages in an otherwise empty tree, identical
except for four characters of prose:

```markdown
---
title: Breadcrumb repro
summary: A measurement report citing a dated prior report by round number.
---

## Findings {#f}

The round 3 report measured 2.5x more compactions. This document corrects it.
```

```
$ oku init && oku check --strict
! 1 warning(s):
  ! breadcrumb.md:14:b[0] line 14 [process-breadcrumb] Prose contains
    process/history reference 'round 3'; the kit documents current behaviour only.
✓ 2 page(s) — no errors (warnings present)
$ echo $?
1
```

The control page, differing only in `The 08-17 report measured …`, is clean.

**Expected vs actual.** Expected: a document that is *about* the history of a
measurement can name the rounds of that measurement. Actual: the only way to
pass `--strict` is to rewrite every citation into a date, which loses the
reference the reader needs.

**Where it was localised.** `src/oku/cli.py:2704-2713` raises it. The scoping
decision is at `src/oku/cli.py:3205-3210`, and its own comment states the
intent:

> Pages materialised from repo markdown without front-matter (README, CHANGELOG,
> CLAUDE and friends) carry author-owned prose verbatim; the process-breadcrumb
> rule is meant for **hand-authored kit pages**, so it is skipped for those.

So the rule already knows it should not apply to every page — it just uses
`_materialised_by == "oku-init"` as the test. A report, an audit or a review is
hand-authored and is not a kit documentation page, and the skill lists exactly
those as supported outputs, so it has no escape.

**Observed vs inferred.** *Observed:* the reproduction above, the warning text,
the `--strict` exit code, and the source lines quoted. *Inferred, not executed:*
that `skip_prose=True` (exercised at `src/oku_tests/test_pure.py:355-356`) is the
existing seam a fix would hang off — the flag was read, not traced to its
callers, and no fix was attempted.

**Not filed alongside it.** `oku build` refusing the whole tree when any page
has errors is documented behaviour, not a defect: it prints `Not building. Fix
the errors above, or pass --allow-errors to ship anyway`, emits **zero**
`file:///` URLs and writes nothing, so a refused build cannot be mistaken for a
successful one. Verified on a three-page tree (one schema-invalid page): refused
run exit 1 / 0 URLs / no `dist`; `--allow-errors` exit 0 / 9 URLs / 4 files.

---

No other open defects.

The two that were here are closed:

- **`oku serve` bound every interface, and no version string said whether
  yours did.** The bind was fixed in `f785d1d`; what stayed open was that a
  build made before it could not be told apart from one made after. Closed in
  `725e477` — `oku --version` now prints `src sha256:<12>` (a prefix, so
  nobody runs `git cat-file` on it again) and `as of <date>`, the newest
  mtime among the files the digest covers. A digest compares; a date orders,
  which is the question a reader in another project is actually asking. Held
  by `test_tool_digest.py`.

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
