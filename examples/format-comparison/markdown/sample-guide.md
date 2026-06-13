---
title: Sample — operations guide
accent: teal
order: 90
summary: Prose-heavy comparison sample — sections, lists, table, code, callouts.
---

> [!TLDR] Operations guide
> How the ingest pipeline is operated day to day.
> - Three environments, one promotion path
> - Rollback is a config flip, not a deploy

## Environments {#environments}

Promotion flows **dev** to *staging* to `prod`. Every change lands in [the runbook](#g/iceberg) before it reaches production traffic.

- dev — synthetic load only
- staging — mirrored sample of production topics
- prod — full traffic, paged on-call

| Environment | Brokers | Retention |
|---|---|---|
| dev | 3 | 1 day |
| staging | 6 | 7 days |
| prod | 24 | 30 days |

## Rollback {#rollback}

Rollback never redeploys. The router consults a single flag:

```js
const active = flags.get('ingest-v2') ? v2Pipeline : v1Pipeline;
```

> [!WARNING] Flag debt
> A flag older than two releases is an incident waiting to happen.
> Delete flags at the release after their flip.

## Escalation {#escalation}

Page the data-platform rotation first. The broker team owns hardware; everything above the socket is ours.
