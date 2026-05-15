# html-doc

Shared visual chrome for long-form HTML artifacts — reviews, briefs, design
docs, study guides. One CSS + JS kit, referenced by every page across every
project. Update once, all pages get it.

## What you get

- Three-mode theme (system / light / dark), system by default; respects OS
  changes live when in system mode.
- Sticky TOC sidebar with scroll-spy and mobile drawer.
- Floating top-left TOC toggle, top-right theme cycler, bottom-right
  back-to-top — all frosted-glass `.ctrl-btn` style.
- Reading progress bar, anchor flash, section permalinks, copy-to-clipboard
  on every `<pre>`, glossary tooltips.
- Reusable components: callouts, pills, KPI tiles, comparison cards,
  expandable details, TL;DR box, cover header with radial accent glow.
- Print/PDF stylesheet, prefers-reduced-motion, focus-visible halos.

## Install

```bash
git clone git@github.com:mmdemirbas/html-doc.git ~/dev/mmdemirbas/html-doc
ln -sf ~/dev/mmdemirbas/html-doc/bin/html-doc ~/.local/bin/html-doc
chmod +x ~/dev/mmdemirbas/html-doc/bin/html-doc
```

Make sure `~/.local/bin` is on your `PATH`.

## Use in a project

```bash
cd ~/path/to/your-project
html-doc init     # creates docs/_kit -> ~/dev/mmdemirbas/html-doc symlink
```

In your HTML file's `<head>`:

```html
<script src="_kit/chrome-boot.js"></script>
<link rel="stylesheet" href="_kit/chrome.css">
<script src="_kit/chrome.js" defer></script>
```

In `<body>`:

```html
<page-chrome></page-chrome>
<div class="layout">
  <page-toc title="Contents"></page-toc>
  <main id="main-content">
    <header class="cover">...</header>
    <section id="overview"><h2>...</h2>...</section>
  </main>
</div>
```

The TOC auto-builds from `<main> > section > h2/h3`. Pre-paint theme init
prevents FOUC. Three-mode cycler is `system → light → dark → system`.

## Build outputs

```bash
cd ~/path/to/project/docs/some-area
html-doc build
```

Always produces both outputs (no mode flag):

```
dist/
├── standalone/     # each HTML inlined — send-as-file, e-mail attachment
└── site/           # shared dist/site/assets/ — public site, GitHub Pages
```

Pick whichever fits the share scenario at hand.

## Per-page accent override

Default accent is indigo. Override in a small `<style>` block on the page:

```html
<style>
  :root { --accent: #b45309; --accent-soft: #fef3c7; --accent-strong: #b45309; }
  :root[data-theme="dark"] { --accent: #fbbf24; --accent-soft: #422006; --accent-strong: #fcd34d; }
</style>
```

Everything else (chrome, scroll-spy active state, anchor flash, hero glow)
derives from these two tokens.

## Versioning

Tags follow semver: `v1.0.0`, `v1.1.0`. Symlink users get HEAD; pull when
you want updates. CDN consumers should pin to a tag — e.g.
`https://cdn.jsdelivr.net/gh/mmdemirbas/html-doc@v1/chrome.css`.

See `CHANGELOG.md`.
