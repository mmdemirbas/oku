---
title: Diagrams
eyebrow: Reference · Mermaid
order: 23
summary: diagram primitive + the Mermaid v10 type catalog the kit ships with.
parent: reference
---

## Diagram + Mermaid {#diagrams}

### diagram {#diagram}

Mermaid-rendered. Lazy-loads Mermaid 10 from the CDN on first `<diagram>` encountered on the page. `source` is any Mermaid syntax (flowchart, sequence, gantt, state, class). Re-renders on theme toggle so colors track light/dark.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"diagram\",\n  \"caption\": \"Optional caption below the diagram.\",\n  \"source\": \"flowchart LR\\n  A[JSON page] --> B(renderer)\\n  B --> C[DOM]\"\n}","lang":"json"},"output":{"k":"diagram","src":"flowchart LR\n    JSON[*.json pages] --> RJ[renderer.js]\n    RJ --> DOM[Custom Element DOM]\n    KIT[kit.json + glossary] --> CJ[chrome.js]\n    CJ --> DOM","caption":"Build pipeline at a glance."}}
```

### Supported Mermaid types {#mermaid-supported}

The diagram primitive forwards source to Mermaid v10 with theme:'base'; no diagram type is gated. Tested in this kit: flowchart, sequence, class, state, ER, journey, gantt, pie, requirement, gitGraph, c4, mindmap, timeline, quadrantChart, sankey-beta, xychart-beta, block-beta, packet-beta, architecture-beta. Each one inherits the page's accent / surface / text tokens via the kit's themeVariables map, so light/dark mode tracks automatically.

### sequence {#mermaid-sequence}

Actors / lifelines / signals — best for protocol or call flows.

```oku-example
{"code":{"k":"code","src":"sequenceDiagram\n  participant Reader\n  participant Renderer\n  Reader->>Renderer: open page\n  Renderer-->>Reader: hydrated DOM","lang":"mermaid"},"output":{"k":"diagram","src":"sequenceDiagram\n  participant Reader\n  participant Renderer\n  Reader->>Renderer: open page\n  Renderer-->>Reader: hydrated DOM"}}
```

### state {#mermaid-state}

Finite state machine — transitions trigger on events; great for editor / draft / published flows.

```oku-example
{"code":{"k":"code","src":"stateDiagram-v2\n  [*] --> Draft\n  Draft --> Review : submit\n  Review --> Draft : reject\n  Review --> Published : approve\n  Published --> [*]","lang":"mermaid"},"output":{"k":"diagram","src":"stateDiagram-v2\n  [*] --> Draft\n  Draft --> Review : submit\n  Review --> Draft : reject\n  Review --> Published : approve\n  Published --> [*]"}}
```

### ER (entity-relationship) {#mermaid-er}

Primary keys / cardinality. Mirrors what the schema-design skill emits.

```oku-example
{"code":{"k":"code","src":"erDiagram\n  PAGE ||--o{ BLOCK : contains\n  BLOCK ||--o{ INLINE : holds","lang":"mermaid"},"output":{"k":"diagram","src":"erDiagram\n  PAGE ||--o{ BLOCK : contains\n  BLOCK ||--o{ INLINE : holds"}}
```

### class {#mermaid-class}

UML-style class shape with attributes, methods, and inheritance arrows.

```oku-example
{"code":{"k":"code","src":"classDiagram\n  class OkuRenderer {\n    +render(json)\n    -_renderBlock(b)\n  }\n  class OkuChart\n  OkuRenderer --> OkuChart","lang":"mermaid"},"output":{"k":"diagram","src":"classDiagram\n  class OkuRenderer {\n    +render(json)\n    -_renderBlock(b)\n  }\n  class OkuChart\n  OkuRenderer --> OkuChart"}}
```

### gantt {#mermaid-gantt}

Tasks over time, with dependencies and the critical path.

```oku-example
{"code":{"k":"code","src":"gantt\n  title Q3 launch — content + ship\n  dateFormat YYYY-MM-DD\n  axisFormat %b %d\n  excludes weekends\n\n  section Discovery\n  Audit existing pages       :done,    a1, 2026-05-04, 5d\n  Customer interviews        :done,    a2, after a1, 6d\n  Define content pillars     :done,    a3, after a2, 3d\n\n  section Writing\n  Outline & approval         :active,  w1, after a3, 4d\n  Draft pillar pages         :         w2, after w1, 8d\n  Editorial review           :         w3, after w2, 4d\n\n  section Design & build\n  Page templates             :crit,    d1, after a3, 6d\n  Hero illustrations         :         d2, after d1, 5d\n  Build pages                :         d3, after w3, 7d\n\n  section Ship\n  QA across breakpoints      :crit,    s1, after d3, 3d\n  Soft launch                :milestone, s2, after s1, 0d\n  Public announcement        :milestone, s3, after s2, 1d","lang":"mermaid"},"output":{"k":"diagram","src":"gantt\n  title Q3 launch — content + ship\n  dateFormat YYYY-MM-DD\n  axisFormat %b %d\n  excludes weekends\n\n  section Discovery\n  Audit existing pages       :done,    a1, 2026-05-04, 5d\n  Customer interviews        :done,    a2, after a1, 6d\n  Define content pillars     :done,    a3, after a2, 3d\n\n  section Writing\n  Outline & approval         :active,  w1, after a3, 4d\n  Draft pillar pages         :         w2, after w1, 8d\n  Editorial review           :         w3, after w2, 4d\n\n  section Design & build\n  Page templates             :crit,    d1, after a3, 6d\n  Hero illustrations         :         d2, after d1, 5d\n  Build pages                :         d3, after w3, 7d\n\n  section Ship\n  QA across breakpoints      :crit,    s1, after d3, 3d\n  Soft launch                :milestone, s2, after s1, 0d\n  Public announcement        :milestone, s3, after s2, 1d"}}
```

### pie {#mermaid-pie}

Simple distribution — limit to ≤6 slices for readability.

```oku-example
{"code":{"k":"code","src":"pie title Where time goes\n  \"chrome.js\" : 40\n  \"chrome.css\" : 25\n  \"renderer.js\" : 15\n  \"cli.py\" : 12\n  \"docs\" : 8","lang":"mermaid"},"output":{"k":"diagram","src":"pie title Where time goes\n  \"chrome.js\" : 40\n  \"chrome.css\" : 25\n  \"renderer.js\" : 15\n  \"cli.py\" : 12\n  \"docs\" : 8"}}
```

### journey {#mermaid-journey}

User journey scoring across stages — quick triage of friction points.

```oku-example
{"code":{"k":"code","src":"journey\n  title Adopt the kit\n  section Setup\n    Discover repo : 4 : Author\n    Run init      : 5 : Author\n  section Author\n    Add a page    : 4 : Author\n    Build site    : 5 : Author","lang":"mermaid"},"output":{"k":"diagram","src":"journey\n  title Adopt the kit\n  section Setup\n    Discover repo : 4 : Author\n    Run init      : 5 : Author\n  section Author\n    Add a page    : 4 : Author\n    Build site    : 5 : Author"}}
```

### mindmap {#mermaid-mindmap}

Tree of related ideas radiating from a central node.

```oku-example
{"code":{"k":"code","src":"mindmap\n  root((oku))\n    Authoring\n      JSON\n      Markdown\n    Runtime\n      chrome.js\n      renderer.js\n    Build\n      site\n      standalone\n      markdown","lang":"mermaid"},"output":{"k":"diagram","src":"mindmap\n  root((oku))\n    Authoring\n      JSON\n      Markdown\n    Runtime\n      chrome.js\n      renderer.js\n    Build\n      site\n      standalone\n      markdown"}}
```

### timeline {#mermaid-timeline}

Linear sequence of events, grouped by section.

```oku-example
{"code":{"k":"code","src":"timeline\n  title oku roadmap\n  section Foundations\n    2026-05-24 : P0 cleanup\n    2026-05-24 : P1 components\n  section Charts\n    2026-05-24 : P2 interactivity\n  section Content\n    2026-05-24 : P3 reference\n    2026-05-24 : P4 markdown parity","lang":"mermaid"},"output":{"k":"diagram","src":"timeline\n  title oku roadmap\n  section Foundations\n    2026-05-24 : P0 cleanup\n    2026-05-24 : P1 components\n  section Charts\n    2026-05-24 : P2 interactivity\n  section Content\n    2026-05-24 : P3 reference\n    2026-05-24 : P4 markdown parity"}}
```

### sankey-beta {#mermaid-sankey}

Flow / share between stages. Use for funnels, energy, traffic.

```oku-example
{"code":{"k":"code","src":"sankey-beta\n\nVisitors,Signups,40\nVisitors,Bounced,60\nSignups,Activated,25\nSignups,Dropped,15","lang":"mermaid"},"output":{"k":"diagram","src":"sankey-beta\n\nVisitors,Signups,40\nVisitors,Bounced,60\nSignups,Activated,25\nSignups,Dropped,15"}}
```

## Drawing your own {#hand-drawn}

Mermaid covers topology. When the figure needs a real axis, a before /
after split, or a shape Mermaid has no grammar for, draw the SVG
yourself in an HTML island — the island has no restrictions.

The one thing you must not do is reach for a hex literal. A hardcoded
colour is how a figure ends up invisible in the theme nobody was
looking at: dark ink on the dark surface, a pale box on the pale one.
`oku check` says so as `island-hand-styled`. These classes are what it
is telling you to use — every one of them is driven by the same tokens
the rest of the page uses, so the figure follows the page accent and
both themes for free.

<figure class="okt-figure">
<svg viewBox="0 0 640 250" role="img" aria-label="The class vocabulary for a hand-drawn SVG: node fills, a group region, and three edge weights.">
<defs>
<marker id="oku-vocab-head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="okt-diag-arrow" d="M 0 0 L 10 5 L 0 10 z"/></marker>
<marker id="oku-vocab-head-strong" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="okt-diag-arrow strong" d="M 0 0 L 10 5 L 0 10 z"/></marker>
</defs>
<rect class="okt-diag-node" x="20" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node accent" x="144" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node ok" x="268" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node warn" x="392" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node fail" x="516" y="24" width="104" height="40" rx="9"/>
<text class="okt-diag-label" x="72" y="49" text-anchor="middle">node</text>
<text class="okt-diag-label accent" x="196" y="49" text-anchor="middle">accent</text>
<text class="okt-diag-label ok" x="320" y="49" text-anchor="middle">ok</text>
<text class="okt-diag-label warn" x="444" y="49" text-anchor="middle">warn</text>
<text class="okt-diag-label fail" x="568" y="49" text-anchor="middle">fail</text>
<text class="okt-diag-label mono" x="72" y="82" text-anchor="middle">.okt-diag-node</text>
<text class="okt-diag-label mono" x="196" y="82" text-anchor="middle">.accent</text>
<text class="okt-diag-label mono" x="320" y="82" text-anchor="middle">.ok</text>
<text class="okt-diag-label mono" x="444" y="82" text-anchor="middle">.warn</text>
<text class="okt-diag-label mono" x="568" y="82" text-anchor="middle">.fail</text>
<rect class="okt-diag-group" x="20" y="112" width="280" height="88" rx="12"/>
<rect class="okt-diag-node plain" x="40" y="140" width="110" height="34" rx="8"/>
<rect class="okt-diag-node plain" x="170" y="140" width="110" height="34" rx="8"/>
<text class="okt-diag-label soft" x="95" y="161" text-anchor="middle">reader</text>
<text class="okt-diag-label soft" x="225" y="161" text-anchor="middle">writer</text>
<text class="okt-diag-label mono" x="160" y="236" text-anchor="middle">.okt-diag-group</text>
<line class="okt-diag-edge" x1="345" y1="128" x2="465" y2="128" marker-end="url(#oku-vocab-head)"/>
<line class="okt-diag-edge dashed" x1="345" y1="160" x2="465" y2="160"/>
<line class="okt-diag-edge strong" x1="345" y1="192" x2="465" y2="192" marker-end="url(#oku-vocab-head-strong)"/>
<text class="okt-diag-label mono" x="478" y="132">.okt-diag-edge</text>
<text class="okt-diag-label mono" x="478" y="164">.dashed</text>
<text class="okt-diag-label mono" x="478" y="196">.strong</text>
</svg>
<figcaption>Five node fills, a group region, three edge weights. Every fill, stroke and text colour above is a CSS variable, so the same markup renders correctly in both themes and follows whatever accent the tree is set to.</figcaption>
</figure>

`.okt-diag-label` also takes `.strong`, `.soft`, `.faint` and `.mono`;
`.okt-diag-arrow` takes the same status modifiers as the edge, because
a `<marker>` paints with its own fill and the line's stroke colour never
reaches it. For a figure that encodes a category per shape,
`.okt-diag-fill-1` through `-10` are the chart ramp, so a hand-drawn
figure sits in the same palette as every chart around it.
