---
title: Diagrams
eyebrow: Reference · Mermaid
subtitle: diagram primitive + the Mermaid v10 type catalog the kit ships with.
audience: Author
order: 23
summary: diagram primitive + the Mermaid v10 type catalog the kit ships with.
parent: reference
accent: teal
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
