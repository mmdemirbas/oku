---
title: Why the source format is markdown
accent: amber
eyebrow: Reference
date: 2026-06-13
order: 95
summary: Five source formats were measured on tokens, converter weight and
  ecosystem fit. Markdown won and the other three were deleted. What the
  measurement said, kept so the decision is not re-argued from memory.
---

> [!TLDR]
> **HTML is the output.** Every page ships as HTML whatever its source —
> that was never the question. The question was what an author *types*,
> and five answers were measured on two identical pages. Markdown,
> AsciiDoc and djot came within 1.2% of each other on tokens; JSON cost
> +6%; authoring in HTML cost +52%. Markdown won on the axes that were
> not close: it is the register an AI writes in natively, and it renders
> in GitHub, Obsidian and every editor without the kit.

## What shipped {#shipped}

Two source formats, and the second exists only for pages that predate
the first.

| Format | What it is | Status |
|---|---|---|
| `.md` | Front-matter + strict-GFM body. What an author writes. | The format |
| `.json` | v1 / v2 page dicts written before `.md` existed | Renders forever; `oku migrate` converts one on demand |
| `.src.html` | Authoring the *source* in HTML | Deleted |
| `.adoc` | AsciiDoc subset | Deleted |
| `.dj` | djot subset | Deleted |

Deleting the three removed ~820 lines of converter, three corpus
directories and their round-trip tests. Nothing else changed: every
format always converted to the same v2 dict, and lint, build, serve and
the renderer only ever saw v2.

**Wanting raw HTML inside a page is a different want**, and it is
already served — a block-level HTML tag at column 0 passes through
untouched, with no restrictions. That is the escape hatch, and it is
what authors reach for, rather than writing a whole page in HTML.

## What the measurement said {#measured}

The corpus was generated rather than hand-written: one canonical v2
page dict emitted into each format and parsed back, with round-trip
equality enforced by tests, so the only variable was the format itself.
Tokens are `cl100k_base`.

```oku-chart
{"type":"bar","title":"Source tokens — two-page corpus (cl100k)","rows":[{"label":"markdown","value":679},{"label":"asciidoc","value":682},{"label":"djot","value":688},{"label":"json (v2)","value":720},{"label":"html-first","value":1034}]}
```

| Format | Total tokens | vs markdown | Bytes |
|---|---|---|---|
| markdown (v3) | 679 | 100.0% | 2396 |
| asciidoc | 682 | 100.4% | 2429 |
| djot | 688 | 101.3% | 2410 |
| json (v2) | 720 | 106.0% | 2475 |
| html-first | 1034 | 152.3% | 3539 |

Tokens did not decide it — three formats tied inside 1.2%. The deciding
axes were the ones with a wide spread.

| Axis | markdown | asciidoc / djot | html-first |
|---|---|---|---|
| AI edit accuracy | native output register | low training-data presence | tag discipline, verbose diffs |
| External rendering | GitHub, Obsidian, editors; mermaid native | GitHub partial / none | browser only |
| Python parser | shipped | none exists — subset only | stdlib |

> [!NOTE] What the subsets meant
> The AsciiDoc and djot converters only ever covered the corpus
> constructs — headings, paragraphs, lists, tables, fences,
> admonitions. Full-spec support needed parsers that do not exist in
> Python, and that tooling gap was itself the datum.

## See them rendered {#rendered}

The two surviving formats, same content, same pipeline:

- Guide: [markdown](../examples/format-comparison/markdown/sample-guide.html) · [json](../examples/format-comparison/json/sample-guide.html)
- Dashboard: [markdown](../examples/format-comparison/markdown/sample-viz.html) · [json](../examples/format-comparison/json/sample-viz.html)
