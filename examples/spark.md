---
title: Spark integration
eyebrow: Engine · demo
subtitle: Second page in the demo knowledge base — used to verify <page-nav> renders the tree and active-page highlighting works.
audience: Spark+Iceberg team
date: 2026-05-17
read_time: ~3 min read
order: 20
summary: Iceberg's most mature engine integration.
accent: teal
---

> [!TLDR]
> Spark is the deepest Iceberg integration: full read/write/maintenance with the IcebergSource API and procedures for rewrite/expire/snapshot management.
>
> - Use Iceberg's Spark catalog for transactional table operations.
> - MERGE INTO, schema evolution, and partition evolution all supported.
> - Procedures: rewrite_data_files, expire_snapshots, remove_orphan_files.
> - Structured streaming reads/writes work out of the box.

## Catalog configuration {#catalog}

Iceberg's Spark catalog is the integration entry point. Configure it once; all table operations route through it.

Set the catalog as a `spark.sql.catalog.*` configuration. The catalog handles snapshot atomicity, schema evolution, and time-travel queries transparently.

```scala
spark.conf.set("spark.sql.catalog.icehouse",
  "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.icehouse.type", "hadoop")
spark.conf.set("spark.sql.catalog.icehouse.warehouse",
  "s3a://my-bucket/icehouse")
```

## Maintenance procedures {#procedures}

Iceberg ships Spark stored procedures for the common maintenance operations. Schedule them as periodic jobs.

- `CALL icehouse.system.rewrite_data_files` — merge small files into larger ones.
- `CALL icehouse.system.expire_snapshots` — drop snapshots older than a retention threshold.
- `CALL icehouse.system.remove_orphan_files` — garbage-collect files no longer referenced by any snapshot.

## Next {#next}

See the [Iceberg overview](iceberg.html) page for the format-level details. Click around the site tree on the left to navigate.
