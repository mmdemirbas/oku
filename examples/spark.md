# Spark integration

*Second page in the demo knowledge base — used to verify <page-nav> renders the tree and active-page highlighting works.*

> 2026-05-17 · Spark+Iceberg team · ~3 min read

> **TLDR**
>

## Catalog configuration

Set the catalog as a `spark.sql.catalog.*` configuration. The catalog handles snapshot atomicity, schema evolution, and time-travel queries transparently.

```scala
spark.conf.set("spark.sql.catalog.icehouse",
  "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.icehouse.type", "hadoop")
spark.conf.set("spark.sql.catalog.icehouse.warehouse",
  "s3a://my-bucket/icehouse")
```


## Maintenance procedures

- `CALL icehouse.system.rewrite_data_files` — merge small files into larger ones.
- `CALL icehouse.system.expire_snapshots` — drop snapshots older than a retention threshold.
- `CALL icehouse.system.remove_orphan_files` — garbage-collect files no longer referenced by any snapshot.


## Next

See the [Iceberg overview](iceberg.html) page for the format-level details. Click around the site tree on the left to navigate.
