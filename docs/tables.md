---
title: Tables
eyebrow: Reference · tables
subtitle: table primitive — flat rows, grouped rows, chip filters, board / kanban view, sticky headers, column resize.
audience: Author
order: 22
summary: table primitive — flat rows, grouped rows, chip filters, board / kanban view, sticky headers, column resize.
parent: reference
accent: teal
---

## Table primitive {#tables}

### table {#table}

First-class JSON table. Two shapes: flat `rows` or grouped `groups`. Renders into a real `<table>` plus a runtime control bar (filter input, stats counter, Table / List / Cards view toggle, sticky header, full-width auto-fit). Object-form headers and cells declare chip filters with multi-valued cells; groups are collapsible. A header's `status` map turns a column's values into colour-coded status pills (`good` / `warn` / `bad` / `info` / `neutral`) — the author maps their own values, so the colour language stays locale-neutral.

### Flat rows {#tables-flat}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\n    \"Stage\",\n    { \"label\": \"Status\",\n      \"status\": { \"done\": \"good\", \"in-progress\": \"warn\", \"queued\": \"neutral\" } },\n    \"Duration\"\n  ],\n  \"rows\": [\n    [\"Plan\",  \"done\",         \"1d\"],\n    [\"Build\", \"done\",         \"3d\"],\n    [\"Test\",  \"in-progress\",  \"2d\"],\n    [\"Ship\",  \"queued\",       \"—\"]\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Stage",{"label":"Status","status":{"done":"good","in-progress":"warn","queued":"neutral"}},"Duration"],"rows":[["Plan","done","1d"],["Build","done","3d"],["Test","in-progress","2d"],["Ship","queued","—"]]}}
```

### Grouped rows with per-group counts {#tables-grouped}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\"Engine\", \"Storage\", \"License\"],\n  \"groups\": [\n    { \"title\": \"Lakehouse formats\",\n      \"rows\": [\n        [\"Apache Iceberg\", \"Object store\", \"Apache 2.0\"],\n        [\"Delta Lake\",    \"Object store\", \"Apache 2.0\"]\n      ]\n    },\n    { \"title\": \"Query engines\",\n      \"rows\": [[\"Trino\", \"Pluggable\", \"Apache 2.0\"]]\n    }\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Engine","Storage","License"],"groups":[{"t":"Lakehouse formats","rows":[["Apache Iceberg","Object store","Apache 2.0"],["Apache Hudi","Object store","Apache 2.0"],["Delta Lake","Object store","Apache 2.0"]]},{"t":"Query engines","rows":[["Trino","Pluggable","Apache 2.0"],["Presto","Pluggable","Apache 2.0"]]}]}}
```

### Chip filters + multi-valued cells {#tables-chips}

Headers can declare a fixed chip set with `filter: "chips"`; cells use the object form `{ value, values }` to belong to one or more chip values. AND across columns, OR within a column. Combine with the text filter.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\n    \"Engine\",\n    { \"label\": \"Tags\", \"filter\": \"chips\",\n      \"values\": [\"lakehouse\", \"streaming\", \"query\"] },\n    { \"label\": \"Maturity\", \"filter\": \"chips\",\n      \"values\": [\"incubating\", \"ga\", \"experimental\"] }\n  ],\n  \"rows\": [\n    [\"Apache Iceberg\",\n      { \"values\": [\"lakehouse\"] },\n      { \"value\": \"GA\", \"values\": [\"ga\"] }],\n    [\"Apache Paimon\",\n      { \"values\": [\"lakehouse\", \"streaming\"] },\n      { \"value\": \"Incubating\", \"values\": [\"incubating\"] }],\n    [\"Trino\",\n      { \"values\": [\"query\"] },\n      { \"value\": \"GA\", \"values\": [\"ga\"] }]\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Engine",{"label":"Tags","filter":"chips","values":["lakehouse","streaming","query","metadata"]},{"label":"Maturity","filter":"chips","values":["incubating","ga","experimental"]}],"rows":[["Apache Iceberg",{"values":["lakehouse","metadata"]},{"value":"GA","values":["ga"]}],["Apache Hudi",{"values":["lakehouse","streaming"]},{"value":"GA","values":["ga"]}],["Delta Lake",{"values":["lakehouse"]},{"value":"GA","values":["ga"]}],["Apache Paimon",{"values":["lakehouse","streaming"]},{"value":"Incubating","values":["incubating"]}],["Trino",{"values":["query"]},{"value":"GA","values":["ga"]}],["Apache Flink",{"values":["streaming"]},{"value":"GA","values":["ga"]}],["Pulsar Functions",{"values":["streaming","metadata"]},{"value":"Experimental","values":["experimental"]}]]}}
```

### Board view: kanban lanes in declared order {#tables-board}

Set `view: "board"` on the table block to open in kanban lanes by default — rows become cards in one lane per unique value of the group column. Declare `boardOrder` on the column header to force the lane sequence; without it, lanes appear in first-occurrence order, which rarely matches the kanban flow you want. Values present in row data but missing from `boardOrder` render at the end so authors can spot the omission. The other views (Table / List / Cards) are still one click away in the view toggle.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"view\": \"board\",\n  \"headers\": [\n    \"Item\",\n    { \"label\": \"Status\",\n      \"boardOrder\": [\"queued\", \"in-progress\", \"blocked\", \"done\"] }\n  ],\n  \"rows\": [\n    [\"Cut release tag\",        \"queued\"],\n    [\"Wire CI matrix\",         \"in-progress\"],\n    [\"Vendor security review\", \"blocked\"],\n    [\"Migrate auth layer\",     \"done\"],\n    [\"Draft RFC\",              \"in-progress\"],\n    [\"Update changelog\",       \"queued\"]\n  ]\n}","lang":"json"},"output":{"k":"table","view":"board","headers":["Item",{"label":"Status","boardOrder":["queued","in-progress","blocked","done"]}],"rows":[["Cut release tag","queued"],["Wire CI matrix","in-progress"],["Vendor security review","blocked"],["Migrate auth layer","done"],["Draft RFC","in-progress"],["Update changelog","queued"]]}}
```

### Per-column wrap for multi-line cells {#tables-wrap}

Mark a column with `wrap: true` on the header object and cells in that column honour explicit newlines (`\n`) from the source. Use for narrative columns — design notes, trade-offs, error-message bodies — where the cell content reads as a short paragraph instead of a single line.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\n    \"Option\",\n    { \"label\": \"Trade-off\", \"wrap\": true }\n  ],\n  \"rows\": [\n    [\"Mock the DB\",\n     \"Fast in CI.\\nMisses real SQL errors.\\nLast quarter's migration regression slipped past mocks.\"],\n    [\"Testcontainers\",\n     \"Slower setup (~3s/test).\\nCatches schema + driver behaviour.\\nRequires Docker.\"]\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Option",{"label":"Trade-off","wrap":true}],"rows":[["Mock the DB","Fast in CI.\nMisses real SQL errors.\nLast quarter's migration regression slipped past mocks."],["Testcontainers","Slower setup (~3s/test).\nCatches schema + driver behaviour.\nRequires Docker."]]}}
```
