# Iceberg deep dive

*Nested-page test for H3 fix. This page lives at storage/iceberg-detail.* — confirms the recursive build preserves directory structure.*

> 2026-05-17

## Subfolder page

This page exists at `_internal/demo-page/storage/iceberg-detail.json`. Its HTML stub lives next to it. Before H3, the build wrote the manifest entry but never copied the HTML stub to `dist/site/` — page-nav would link to a 404. After H3, the build preserves the storage/ subdirectory all the way through to dist/site/storage/iceberg-detail.html.
