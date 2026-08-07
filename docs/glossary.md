---
title: Glossary & external refs
eyebrow: Reference
subtitle: How the multi-domain, multi-language glossary registry works. File layout, project-level overrides, disambiguation, the resolution algorithm.
date: 2026-05-18
order: 30
summary: Multi-domain glossary architecture and how to extend it.
---

> [!TLDR]
> Glossary and ext-ref entries live in per-domain files under _oku/glossary/ and _oku/extrefs/. Each project's kit.json activates a subset of domains in priority order and can add local overrides. Resolution walks active domains, falls back through preferred languages, surfaces unknowns via the forward-compat warning indicator.
>
> - Per-domain files — separate ACID in data-platforms from ACID in chemistry, separate RSD in adhd from RSD in radio.
> - A page references an entry with a markdown link — [ACID](#g/ACID) for a glossary term, [Pagefind](#x/Pagefind) for an ext-ref.
> - Per-entry multi-language variants — { "en": {...}, "tr": {...} }. The canonical link can differ per language.
> - Project kit.json declares active domains + preferred language + project-local entries. Local entries always win on conflict.
> - Unknown terms surface in the forward-compat warning indicator; add the entry to project kit.json or push to central.

## File layout {#layout}

Central glossaries ship with the kit; projects extend via kit.json or by adding their own domain files.

```text
oku/                          # the kit repo
├── glossary/
│   ├── data-platforms.json
│   ├── web.json
│   ├── ai-llm.json
│   ├── adhd.json          (structural stub — populate as needed)
│   ├── doc-tooling.json   (structural stub)
│   ├── hadith.json        (structural stub)
│   └── voice.json         (structural stub)
├── extrefs/
│   ├── data-platforms.json
│   ├── doc-tooling.json
│   ├── web.json           (structural stub)
│   └── ai-llm.json        (structural stub)
└── ...

your-project/
└── docs/
    ├── _oku -> /path/to/oku   # symlink
    ├── kit.json                    # active domains + overrides
    ├── page-a.html / page-a.md
    └── ...

```

## Entry shape {#entry-shape}

Each entry is a dict of language → { def, link }. def supports inline HTML (strong, em, br, code) because it's rendered as the tooltip body. The trust boundary is documented in chrome.js — kit-controlled files only.

```json
// _oku/glossary/data-platforms.json
{
  "$schema": "https://raw.githubusercontent.com/mmdemirbas/html-doc/main/kit/schema/glossary.schema.json",
  "domain": "data-platforms",
  "version": 1,
  "entries": {
    "ACID": {
      "en": {
        "def": "<strong>Atomicity, consistency, isolation, durability.</strong> Transaction guarantees.",
        "link": "https://en.wikipedia.org/wiki/ACID"
      },
      "tr": {
        "def": "Veritabanı işlemlerinde atomiklik, tutarlılık, izolasyon, dayanıklılık garantileri."
      }
    }
  }
}
```

> [!NEUTRAL] ext-refs use the same shape
> _oku/extrefs/<domain>.json uses identical structure — each entry has language variants with name, summary, link. Same resolution algorithm, separate registry.

## Project configuration — kit.json {#project-config}

Each project's docs/kit.json declares which domains are active and in what priority order, the preferred language with fallback chain, and any local additions or overrides.

```json
// docs/kit.json — Iceberg-team project
{
  "name": "Spark+Iceberg notes",
  "domains": ["data-platforms", "web", "ai-llm"],
  "lang": "en",
  "lang_fallback": ["en"],
  "glossary": {
    "data-platforms": {
      "OurInternalTerm": {
        "en": { "def": "Defined in this project only." }
      }
    }
  }
}
```

```json
// docs/kit.json — personal-notes project in Turkish
{
  "name": "Notlar",
  "domains": ["adhd", "hadith", "voice"],
  "lang": "tr",
  "lang_fallback": ["en"]
}
```

> [!TIP] Local entries always win on conflict
> When the same term appears in both `kit.json`'s `glossary["data-platforms"]` AND in the central `_oku/glossary/data-platforms.json`, the project version is used. Merge happens after the central file loads, so a project override is never silently discarded by a later registry fetch.

## Referencing an entry from a page {#usage}

A markdown page cites a registry entry with an ordinary link whose href carries a kit prefix: `#g/` for the glossary, `#x/` for ext-refs. The label is the visible text, the id after the prefix is the registry key.

```text
Hover [ACID](#g/ACID) for the definition card.
Powered by [Pagefind](#x/Pagefind) — click the card to open the source.
```

`renderLink` rewrites those into `<glossary-term term="ACID">` and `<ext-ref name="Pagefind">`. Everything downstream — resolution, tooltip, the unknown-entry warning — is shared, so the two prefixes differ only in which registry they search.

JSON pages carry the same reference as an inline object inside a paragraph's `content` array:

```json
{ "kind": "paragraph", "content": [
  "Hover ",
  { "kind": "glossary-term", "term": "ACID", "text": "ACID" },
  " for the definition card."
] }
```

The v1 shim rewrites that object to `[ACID](#g/ACID)` before the renderer walks the page, so both forms land on the same element. `{ "kind": "ext-ref", "name": "Pagefind" }` is the ext-ref counterpart.

## Disambiguation — same term, different domains {#disambiguation}

When two active domains define the same term, the default is "first matching domain wins", and that is what a link-form reference asks for. Two attributes on the element qualify a single reference: `in` restricts lookup to one domain, `lang` overrides the project's preferred language for that instance — useful when one term in a TR-default project needs an English-source citation.

The link form carries the id alone, so a qualified reference writes the element itself in an HTML island:

```text
<p>Two senses of the same word:
<glossary-term term="ACID" in="data-platforms">ACID</glossary-term> and
<glossary-term term="ACID" in="chemistry">ACID</glossary-term>.</p>
```

The `in` attribute wins over domain order — it reaches a domain that is not first in the project's domains list.

## Resolution algorithm {#resolution}

Implemented in chrome.js as __okuKit.resolveGlossary and resolveExtRef.

```oku-step-flow
{"steps":[{"t":"Domain selection","b":"If the in attribute is set, lookup is restricted to that one domain. Otherwise walk the project's domains array in declared order."},{"t":"Per-domain lookup","b":"For each candidate domain, check project-local overrides first, then the central _oku/glossary/<domain>.json. First match wins."},{"t":"Language pick","b":"Try the preferred language (from lang attribute or kit.json's lang). If absent, walk kit.json's lang_fallback list. If still absent, use the first available language and mark data-lang-shown so the tooltip displays the actual language tag."},{"t":"Unknown — surface a warning","b":"If no entry found anywhere, emit an unknown-glossary-term (or unknown-ext-ref) warning event. The forward-compat indicator counts it; the element gets the .unknown class with amber-dotted styling."}]}
```

## Adding new entries {#extending}

Two paths — project-local for quick iteration, central PR when the term proves general.

```oku-compare-grid
{"cards":[{"t":"Project-local first","b":"Add to your project's docs/kit.json under glossary[<domain>][<term>]. Takes effect immediately. No commits to the kit needed. Works for project-specific terms and quick experimentation.","verdict":"good"},{"t":"Promote to central","b":"When a term proves general (used in two or three projects, or clearly belongs in the domain), commit it to _oku/glossary/<domain>.json. Remove the project-local copy when central lands.","verdict":"neutral"}]}
```

> [!SUCCESS] Forward-compat warning surfaces unknowns
> When the AI emits a term that's not in any active domain, the warning indicator lights up with code: "unknown-glossary-term". Click to see the missing entry name. Fast feedback that an addition is overdue.

## Bundled starter content {#starter}

Seven glossary domains ship with the kit. Three arrive populated with ten entries each; four are empty structural stubs ready to fill in.

```oku-compare-grid
{"cards":[{"t":"Populated — 10 entries each","b":"- data-platforms — ACID, MVCC, Iceberg, Spark, Flink, Paimon, Catalog, Snapshot, Compaction, Time travel (with TR translations on the most common)\n- web — Custom Elements, Shadow DOM, FOUC, Viewport, Visual Viewport, prefers-color-scheme, localStorage, History API, IntersectionObserver, CSS variable\n- ai-llm — RAG, Tokenization, Prompt cache, Context window, Embedding, Vector DB, Function calling, Hallucination, Few-shot, Top-k / Top-p","verdict":"in"},{"t":"Structural stubs — no entries yet","b":"- adhd — populate with RSD, hyperfocus, executive dysfunction, etc.\n- doc-tooling — populate with the kit's own vocabulary.\n- hadith — populate with isnad, matn, sahih, da'if, etc.\n- voice — populate with phoneme, prosody, formant, etc.\n- Add new domains by dropping a new <domain>.json file in glossary/ and listing it in your project's kit.json","verdict":"out"}]}
```

Ext-refs ship four domains on the same shape: `data-platforms` (7 entries) and `doc-tooling` (5) carry content; `web` and `ai-llm` are empty stubs.
