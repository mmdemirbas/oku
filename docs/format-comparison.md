---
title: Format comparison — measured
accent: amber
eyebrow: Reference
date: 2026-06-13
order: 95
summary: The same two pages authored in five formats, measured on tokens,
  bytes, converter weight and ecosystem fit. The decision surface for
  pruning formats.
---

> [!TLDR]
> Two identical pages (one prose-heavy, one primitive-heavy) live in
> all five formats under `examples/format-comparison/`. Markdown,
> AsciiDoc and djot are within 1.2% of each other on tokens; JSON
> costs +6%; HTML-first costs +52%. Every format renders through the
> same pipeline — pruning one deletes a converter, nothing else.

## Method {#method}

The corpus is GENERATED, not hand-written: each sample's canonical
form is the v2 page dict, emitted into every format by its
`page_to_<fmt>` emitter and parsed back by its `<fmt>_to_v2_page`
parser. Round-trip equality is enforced by tests, so the content is
provably identical — the only thing the numbers compare is the
format itself. Tokens use `cl100k_base`, the tokenizer behind real
AI billing.

## Tokens and bytes {#tokens}

```oku-chart
{"type":"bar","title":"Source tokens — two-page corpus (cl100k)","rows":[{"label":"markdown","value":679},{"label":"asciidoc","value":682},{"label":"djot","value":688},{"label":"json (v2)","value":720},{"label":"html-first","value":1034}]}
```

| Format | guide | viz | Total tokens | vs markdown | Bytes |
|---|---|---|---|---|---|
| markdown (v3) | 303 | 376 | 679 | 100.0% | 2396 |
| asciidoc | 303 | 379 | 682 | 100.4% | 2429 |
| djot | 309 | 379 | 688 | 101.3% | 2410 |
| json (v2) | 337 | 383 | 720 | 106.0% | 2475 |
| html-first (v4) | 523 | 511 | 1034 | 152.3% | 3539 |

JSON's penalty is small only because v2 keeps markdown strings inside
the JSON; the price shows up in editing (escaping), not reading.
HTML's +52% is pure markup overhead — every paragraph pays open/close
tags.

## Beyond tokens {#qualitative}

| Axis | markdown | json | html-first | asciidoc | djot |
|---|---|---|---|---|---|
| AI edit accuracy | native output register | newline/quote escaping in strings | tag discipline, verbose diffs | low training-data presence | very low training-data presence |
| External rendering | GitHub/Obsidian/editors, mermaid native | none | browser only | GitHub partial | none mainstream |
| Grammar ambiguity | linted strict subset | none | none | low | lowest |
| Converter weight | shipped (default) | none needed | ~340 LoC stdlib | ~190 LoC subset | ~150 LoC subset |
| Ecosystem libs | everywhere | everywhere | stdlib | no good Python lib (subset only) | no Python lib (subset only) |
| Typed primitives | fenced JSON | inline objects | JSON script child | delimited JSON block | fenced JSON |

> [!NOTE] Subset caveat
> The AsciiDoc and djot converters cover the comparison corpus
> constructs only (headings, paragraphs, lists, tables, fences,
> admonitions). Full-spec support would require parsers that don't
> exist in Python — that tooling gap is itself a comparison datum.

## See them rendered {#rendered}

Each page below is the SAME content through a different source
format — open side by side:

- Guide: [markdown](../examples/format-comparison/markdown/sample-guide.html) · [json](../examples/format-comparison/json/sample-guide.html) · [html-first](../examples/format-comparison/html/sample-guide.html) · [asciidoc](../examples/format-comparison/asciidoc/sample-guide.html) · [djot](../examples/format-comparison/djot/sample-guide.html)
- Dashboard: [markdown](../examples/format-comparison/markdown/sample-viz.html) · [json](../examples/format-comparison/json/sample-viz.html) · [html-first](../examples/format-comparison/html/sample-viz.html) · [asciidoc](../examples/format-comparison/asciidoc/sample-viz.html) · [djot](../examples/format-comparison/djot/sample-viz.html)

## Pruning {#pruning}

All five stay supported until the user records a pruning decision in
the roadmap. Removing a format deletes its emit/parse pair and its
corpus directory; the registry, pipeline and renderer are untouched.
