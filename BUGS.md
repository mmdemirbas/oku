# BUGS.md — open defects

A log of confirmed defects, newest first. One entry per defect.

Each entry carries: **symptom**, **minimal reproduction**, **expected vs
actual**, **where the failure was localised**, and — separately — what was
*observed* versus what was *inferred from reading source*. Do not collapse
those two: a mechanism read out of code is a hypothesis until it is executed.

Close an entry by deleting it once the fix is committed. The commit message
carries the record, including what was measured before and after.

---

## An HTML island is cut at the first blank line, and `check` does not notice

*Found 2026-08-14. oku 0.6.5, kit 2026-08-14-r38, src 42447c724eb4.*

**Symptom.** An HTML island that contains a blank line keeps only the content
above that line. Everything below it renders as ordinary page content, outside
the island, styled as if it had never been part of it. `oku check --strict`
reports no error.

**Minimal reproduction.** A page with one island and one blank line in it:

```markdown
## Case A {#sec-a}

<div id="island-a" style="border:1px solid var(--border)">
<p>first paragraph</p>

<p>second paragraph</p>
</div>
```

**Expected.** Both paragraphs inside `#island-a`, or an error naming the island.

**Actual.** `#island-a` has exactly one child, the first `<p>`. Its `innerText`
is `"first paragraph"`. The second paragraph is present on the page but outside
the island. `oku check --strict` exits 0.

**Where the failure was localised.** Not localised in this kit's source. The
behaviour matches the CommonMark rule that an HTML block ends at a blank line,
so the renderer is likely doing what the spec says and the defect is that
nothing warns. Treat that attribution as a hypothesis: see the observed and
inferred split below.

**Observed.**

- The DOM after a build, in a browser: `#island-a` has one `P` child;
  `document.body.innerText` contains "second paragraph"; the island's own text
  does not.
- `oku check --strict` exits 0 on that page.
- On a real page, an island holding an 82-line block rendered with 403
  characters in it and the rest of the block outside. The page had passed
  `oku check --strict` and was delivered twice before anyone opened it.

**Inferred, not verified.**

- That the cause is the CommonMark HTML-block rule. The kit's markdown pipeline
  was not read.
- That a lint could detect it by checking whether an island's opening tag has a
  matching close inside the same block. Plausible from the outside; the parser
  may not expose block boundaries at that point.

**Why it is worth a check rather than a documentation note.** The failure is
invisible in the source, invisible to the linter, and produces a page that looks
deliberate. It is the same shape as the `info-tip` string-payload case the skill
already warns about, where the body disappears and the check still passes.

---

## Code in an island cannot both render and copy

*Found 2026-08-14. Same versions as above. Related to the entry above.*

**Symptom.** There is no way to put multi-line code inside an HTML island so
that it both renders with its line breaks and copies with them. The two
available spellings each lose one of the two.

**Minimal reproduction.** Newlines carried as `<br>`, which is what the entry
above forces if the island is to survive:

```markdown
<div id="island-b" style="border:1px solid var(--border)"><pre><code>line one<br>line two<br>line three</code></pre></div>
```

The other spelling is a `<pre>` containing real newlines. Since code of any
length contains blank lines, that is the entry above.

**Expected.** Copying the block yields three lines.

**Actual.** It renders as three lines. `code.textContent` is
`"line oneline twoline three"`, with zero newline characters and two `<br>`
elements, so any copy that reads the text yields one concatenated line.

**Where the failure was localised.** Not localised. `<br>` genuinely carries no
newline character, so this is HTML semantics rather than a kit defect on its
own. What makes it a defect here is that it is the only route left once an
island cannot contain a blank line, and neither route is reported.

**Observed.**

- The DOM after a build: two `<br>` elements, `textContent` with no newline.
- The same shape on a real page, where the copy control returned the whole SQL
  block as one line and the reader pasted it into another system that way.

**Inferred, not verified.**

- That the copy control reads `textContent` or equivalent. Its implementation
  was not read. What is certain is that the element holds no newline character,
  so any text-based copy must produce one line.

**What is missing.** A way to mark a region as "copy this" that can hold prose,
a table and code together, rendered rather than escaped, so a reader can select
it and paste it into another system with formatting intact. Fenced blocks copy
correctly but carry no formatting; islands carry formatting but cannot hold
code. Every page that hands content to another system needs both at once.
