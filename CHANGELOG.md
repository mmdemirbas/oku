# Changelog

## v1.0.0 — 2026-05-15

Initial release. Extracted from inline chrome used in early karar HTML docs
(odak project) and modernized.

- `chrome.css` — token system (light/dark), layout, TOC sidebar with
  76px top padding to clear the top-left ctrl-btn, reading aids, reusable
  components, print stylesheet.
- `chrome-boot.js` — synchronous pre-paint theme + TOC state from
  `localStorage`. Three-mode theme key: `theme-pref` ∈ {`light`, `dark`,
  absent = system}.
- `chrome.js` — `<page-chrome>` and `<page-toc>` Web Components,
  three-mode theme cycler (`system → light → dark → system`), TOC builder
  with scroll-spy, permalinks, progress bar, back-to-top, copy-to-clipboard,
  glossary tap support.
- `bin/html-doc` — CLI with `init` (creates `docs/_kit` symlink in current
  project) and `build` (always produces both `dist/standalone/` inline
  files and `dist/site/` with shared assets; zero flags). Prints output
  paths with `file://` prefix.
- `templates/starter.html` — minimal HTML scaffold referencing the kit.

### Decisions captured

- Per-project link via symlink (`docs/_kit -> ~/dev/mmdemirbas/html-doc`).
- Build always produces both standalone + site outputs; no mode flag.
- Per-page accent override via CSS variables, not template forking.
