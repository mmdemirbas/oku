/* html-doc · chrome.js
 * Web Components, theme cycler, TOC builder, scroll-spy, reading aids.
 * Loaded with defer; chrome-boot.js handles pre-paint state.
 */

/* ──────────────────────────────────────────────────────────────────
 * html-doc · chrome.js
 *
 *   Web Components, theme cycler, TOC builder, scroll-spy, tooltips,
 *   site nav, charts, diagrams, snippets, warnings, search.
 *
 *   Loaded via `defer`; chrome-boot.js handles pre-paint state.
 *   Pairs with renderer.js (JSON → Custom-Element DOM walker).
 *
 *   Section map — line numbers in the source listing of this file:
 *     SVG icons                                ~6
 *     Theme cycler                            ~13
 *     TOC toggle (legacy v1)                  ~46
 *     <page-chrome>                           ~61
 *     <page-toc>                              ~91
 *     TOC builder + scroll-spy               ~130
 *     Reading aids (progress, copy buttons)  ~258
 *     Docs-root discovery                    ~341
 *     escapeHTML helper                      ~360
 *     Visual Viewport pinch-zoom tracker     ~369
 *     Tooltip controller                     ~388
 *     kit.json + glossary loader             ~513
 *     <glossary-term>                        ~685
 *     <ext-ref>                              ~725
 *     <html-doc-chart>                       ~756
 *     <html-doc-diagram> (Mermaid)           ~874
 *     <html-doc-snippet>                     ~971
 *     <page-nav>                            ~1013
 *     Forward-compat warning indicator      ~1187
 *     Pagefind search                       ~1275
 *     Event hookups (theme, render, warn)   ~1455
 *
 *   Conventions:
 *     - Custom Element classes:  class FooBar extends HTMLElement { ... }
 *     - Shared controllers:      var __htmldocFoo = (function () { ... })();
 *     - Public helpers:          plain top-level function
 *     - Internal helpers:        nested inside their controller IIFE
 * ────────────────────────────────────────────────────────────────── */

/* ============ SVG icon set ============ */
const ICON_MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>';
const ICON_SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/><line x1="4.5" y1="4.5" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.5" y2="19.5"/><line x1="4.5" y1="19.5" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.5" y2="4.5"/></svg>';
const ICON_MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
const ICON_SYSTEM = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>';
const ICON_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';
const ICON_WIDTH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="6" x2="3" y2="18"/><line x1="21" y1="6" x2="21" y2="18"/><polyline points="8 8 5 12 8 16"/><polyline points="16 8 19 12 16 16"/></svg>';
const ICON_CLIPBOARD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>';
const ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>';
const ICON_CROSS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>';
const ICON_BRACES = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2"/><path d="M16 3a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2"/></svg>';
const ICON_CAMERA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>';
const ICON_RESET = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15A9 9 0 1 0 6 5.3L1 10"/></svg>';
const ICON_GEAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
/* Wrap toggle icon: horizontal line with a return arrow — visual cue
   that long lines wrap to the next line instead of scrolling. */
const ICON_WRAP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 21 6"/><path d="M3 12h15a3 3 0 0 1 0 6h-4"/><polyline points="16 15 13 18 16 21"/><polyline points="3 18 10 18"/></svg>';
/* Expand-to-fullscreen icon (Feather: maximize). Used by image / chart /
   diagram / mermaid expand buttons — same affordance everywhere. */
const ICON_EXPAND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>';

/* ============ Lightbox / fullscreen overlay ============ *
 * A single shared overlay used by image, chart, diagram, and mermaid
 * expand buttons. Open with __htmldocLightbox.open(content, { title })
 * where `content` is an Element or HTML string. Returns immediately;
 * the overlay traps focus until closed via Escape, the close button,
 * or backdrop click. Same affordance everywhere — one mental model.
 * ---------------------------------------------------------------- */
var __htmldocLightbox = (function () {
  var overlay = null;
  var lastFocus = null;

  function build() {
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.className = 'hdt-lightbox';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Expanded view');
    overlay.innerHTML =
      '<div class="hdt-lightbox-backdrop"></div>' +
      '<div class="hdt-lightbox-frame">' +
      '  <button type="button" class="hdt-lightbox-close" aria-label="Close" title="Close (Esc)">' + ICON_CROSS + '</button>' +
      '  <div class="hdt-lightbox-content" tabindex="-1"></div>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('.hdt-lightbox-backdrop').addEventListener('click', close);
    overlay.querySelector('.hdt-lightbox-close').addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (!overlay.classList.contains('open')) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); }
    });
    return overlay;
  }

  function open(content, opts) {
    var el = build();
    var holder = el.querySelector('.hdt-lightbox-content');
    holder.innerHTML = '';
    if (content instanceof Node) holder.appendChild(content);
    else holder.innerHTML = String(content || '');
    if (opts && opts.title) el.setAttribute('aria-label', opts.title);
    lastFocus = document.activeElement;
    el.classList.add('open');
    document.documentElement.classList.add('hdt-lightbox-open');
    setTimeout(function () { holder.focus(); }, 0);
  }

  function close() {
    if (!overlay) return;
    overlay.classList.remove('open');
    document.documentElement.classList.remove('hdt-lightbox-open');
    var holder = overlay.querySelector('.hdt-lightbox-content');
    if (holder) holder.innerHTML = '';
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    lastFocus = null;
  }

  return { open: open, close: close };
})();

/* ============ Three-mode theme cycler (system → light → dark → system) ============ */
function getThemeMode() {
  return document.documentElement.getAttribute('data-theme-mode') || 'system';
}
function applyTheme(mode, persist) {
  var actual = mode === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : mode;
  document.documentElement.setAttribute('data-theme', actual);
  document.documentElement.setAttribute('data-theme-mode', mode);
  if (persist) {
    try {
      if (mode === 'system') localStorage.removeItem('theme-pref');
      else localStorage.setItem('theme-pref', mode);
    } catch (e) {}
  }
}
function cycleTheme() {
  var current = getThemeMode();
  var next = current === 'system' ? 'light' : current === 'light' ? 'dark' : 'system';
  applyTheme(next, true);
  // Notify subscribers (e.g., <html-doc-diagram> rerenders Mermaid).
  window.dispatchEvent(new CustomEvent('html-doc:theme-changed', {
    detail: { mode: next, theme: document.documentElement.getAttribute('data-theme') }
  }));
}
/* Follow OS changes while in system mode */
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
  if (getThemeMode() === 'system') {
    document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
  }
});

/* ============ Sidebar toggle (one button, one collapse class) ============ *
 * Toggles the unified left sidebar (page-nav + page-toc, stacked in the
 * same column). The class lives on <body> so layout CSS can collapse
 * the whole grid column with one rule. Mobile uses a drawer mode that
 * sits on the page-nav element.
 * ---------------------------------------------------------------- */
function toggleTOC() {
  if (window.innerWidth <= 920) {
    var nav = document.querySelector('page-nav, nav.toc, page-toc');
    if (nav) nav.classList.toggle('open');
    return;
  }
  document.body.classList.toggle('sidebar-collapsed');
  try {
    localStorage.setItem('sidebarCollapsed',
      document.body.classList.contains('sidebar-collapsed') ? '1' : '0');
  } catch (e) {}
}
// Restore persisted state ASAP so the layout doesn't flash open then collapse.
try {
  if (localStorage.getItem('sidebarCollapsed') === '1') {
    document.documentElement.classList.add('sidebar-preload-collapsed');
    document.addEventListener('DOMContentLoaded', function () {
      document.body.classList.add('sidebar-collapsed');
      document.documentElement.classList.remove('sidebar-preload-collapsed');
    });
  }
} catch (e) {}

/* Content-width mode (D3) — reader picks narrow / wide / max, persists.
 * narrow = 860px (optimal line length); wide = 1100px (more cards per
 * row, still readable prose); max = fill the grid cell (tables, code,
 * matrices in particular benefit on wide screens). State lives on
 * `<body data-content-width=...>`; CSS does the rest via --content-width. */
var WIDTH_MODES = ['narrow', 'wide', 'max'];
function cycleContentWidth() {
  var current = document.body.getAttribute('data-content-width') || 'narrow';
  var i = WIDTH_MODES.indexOf(current);
  var next = WIDTH_MODES[(i + 1) % WIDTH_MODES.length];
  document.body.setAttribute('data-content-width', next);
  try { localStorage.setItem('htmldoc-content-width', next); } catch (e) {}
}
try {
  var savedWidth = localStorage.getItem('htmldoc-content-width');
  if (savedWidth && WIDTH_MODES.indexOf(savedWidth) !== -1) {
    document.addEventListener('DOMContentLoaded', function () {
      document.body.setAttribute('data-content-width', savedWidth);
    });
  }
} catch (e) {}

/* ============ <page-chrome> Web Component ============ */
class PageChrome extends HTMLElement {
  connectedCallback() {
    var skipLabel = this.getAttribute('skip-label') || 'Skip to content';
    var tocLabel = this.getAttribute('toc-label') || 'Toggle table of contents';
    var themeLabel = this.getAttribute('theme-label') || 'Cycle theme (system / light / dark)';
    var widthLabel = this.getAttribute('width-label') || 'Cycle content width (narrow / wide / max)';
    var topLabel = this.getAttribute('top-label') || 'Back to top';

    this.innerHTML =
      '<a class="skip-link" href="#main-content">' + skipLabel + '</a>' +
      '<div class="progress-bar" id="progress-bar"></div>' +
      '<button class="ctrl-btn toc-toggle" type="button" aria-label="' + tocLabel + '" title="' + tocLabel + '">' + ICON_MENU + '</button>' +
      '<button class="ctrl-btn width-toggle" type="button" aria-label="' + widthLabel + '" title="' + widthLabel + '">' + ICON_WIDTH + '</button>' +
      '<button class="ctrl-btn theme-toggle" type="button" aria-label="' + themeLabel + '" title="' + themeLabel + '">' +
        '<span class="icon-system">' + ICON_SYSTEM + '</span>' +
        '<span class="icon-sun">' + ICON_SUN + '</span>' +
        '<span class="icon-moon">' + ICON_MOON + '</span>' +
      '</button>' +
      '<button class="ctrl-btn back-to-top" type="button" aria-label="' + topLabel + '" title="' + topLabel + '">' + ICON_UP + '</button>';

    this.querySelector('.toc-toggle').addEventListener('click', toggleTOC);
    this.querySelector('.width-toggle').addEventListener('click', cycleContentWidth);
    this.querySelector('.theme-toggle').addEventListener('click', cycleTheme);
    this.querySelector('.back-to-top').addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    initReadingAids();
  }
}
customElements.define('page-chrome', PageChrome);

/* ============ <page-toc> Web Component ============ *
 * Renders inside the single left sidebar as a section under the site
 * tree. No edge tab — the unified top-left ctrl-btn (toggleTOC) handles
 * collapsing the whole sidebar.
 * --------------------------------------------------------------- */
class PageToc extends HTMLElement {
  connectedCallback() {
    var title = this.getAttribute('title') || 'On this page';
    this.innerHTML =
      '<div class="page-toc-panel">' +
        '<div class="toc-header"><h2>' + title + '</h2></div>' +
        '<ol class="toc-list"></ol>' +
      '</div>';
    var self = this;
    // If <main> already has section content (pre-rendered HTML), build
    // the TOC now. For renderer-driven pages, html-doc:rendered will
    // trigger the build later — avoid the wasted empty first pass.
    if (document.querySelector('main > section')) {
      var list = self.querySelector('.toc-list');
      if (list) buildTOC(list);
    }
  }
}
customElements.define('page-toc', PageToc);

/* ============ TOC builder + scroll-spy ============ */
function slugify(text) {
  return text.toLowerCase()
    .replace(/[^a-z0-9çğıöşü]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function appendPermalink(heading, id, label) {
  if (heading.querySelector('.permalink')) return;
  var a = document.createElement('a');
  a.className = 'permalink';
  a.href = '#' + id;
  a.textContent = '#';
  a.setAttribute('aria-label', label || 'Permalink');
  heading.appendChild(a);
}

function buildTOC(tocList) {
  if (!tocList) return;
  var sections = document.querySelectorAll('main > section');
  if (sections.length === 0) return;
  tocList.innerHTML = '';

  // Count TOC-eligible sections separately so the numbering doesn't
  // jump when buildable sections precede in DOM order.
  var tocIndex = 0;
  sections.forEach(function (sec, i) {
    var h2 = sec.querySelector('h2');
    if (!h2) return;
    var headingText = h2.cloneNode(true);
    var pre = headingText.querySelector('.num'); if (pre) pre.remove();
    var pl0 = headingText.querySelector('.permalink'); if (pl0) pl0.remove();
    if (!headingText.textContent.trim()) return;
    if (!sec.id) sec.id = 'sec-' + i;

    appendPermalink(h2, sec.id);

    tocIndex++;
    var numEl = h2.querySelector('.num');
    var num = numEl ? numEl.textContent.trim() : tocIndex;
    var titleClone = h2.cloneNode(true);
    var n = titleClone.querySelector('.num'); if (n) n.remove();
    var pl = titleClone.querySelector('.permalink'); if (pl) pl.remove();
    var title = titleClone.textContent.trim();

    var li = document.createElement('li');
    li.className = 'toc-h2';
    li.dataset.target = sec.id;

    var head = document.createElement('div');
    head.className = 'toc-head';
    head.innerHTML =
      '<span class="chevron">▸</span>' +
      '<span class="num">' + num + '.</span>' +
      '<a href="#' + sec.id + '">' + title + '</a>';
    li.appendChild(head);

    var h3s = sec.querySelectorAll('h3');
    var subOl = document.createElement('ol');
    subOl.className = 'toc-sub';
    h3s.forEach(function (h3) {
      if (!h3.id) h3.id = sec.id + '-' + slugify(h3.textContent).slice(0, 40);
      appendPermalink(h3, h3.id);
      var subLi = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + h3.id;
      a.textContent = h3.textContent.replace(/#$/, '').trim();
      subLi.appendChild(a);
      subOl.appendChild(subLi);
    });

    if (h3s.length > 0) {
      li.appendChild(subOl);
      head.addEventListener('click', function (e) {
        if (e.target.tagName !== 'A') { e.preventDefault(); li.classList.toggle('expanded'); }
      });
    } else {
      head.querySelector('.chevron').classList.add('hidden');
    }

    tocList.appendChild(li);
  });

  /* Scroll-spy */
  var tocItems = tocList.querySelectorAll('.toc-h2');
  var idToItem = {};
  tocItems.forEach(function (it) { idToItem[it.dataset.target] = it; });
  var allSubLinks = tocList.querySelectorAll('ol.toc-sub a');
  var idToSubLink = {};
  allSubLinks.forEach(function (a) { idToSubLink[a.getAttribute('href').slice(1)] = a; });

  function setActive(sectionId, h3Id) {
    tocItems.forEach(function (it) { it.classList.remove('active'); });
    allSubLinks.forEach(function (a) { a.classList.remove('active'); });
    var item = idToItem[sectionId];
    if (item) {
      item.classList.add('active', 'expanded');
      tocItems.forEach(function (it) { if (it !== item) it.classList.remove('expanded'); });
    }
    if (h3Id && idToSubLink[h3Id]) idToSubLink[h3Id].classList.add('active');
  }

  var headings = [];
  sections.forEach(function (sec) {
    headings.push({ el: sec, sectionId: sec.id, h3Id: null });
    sec.querySelectorAll('h3').forEach(function (h3) {
      headings.push({ el: h3, sectionId: sec.id, h3Id: h3.id });
    });
  });

  function updateActive() {
    var y = window.scrollY + 150;
    var current = headings[0];
    for (var k = 0; k < headings.length; k++) {
      var rect = headings[k].el.getBoundingClientRect();
      var top = rect.top + window.scrollY;
      if (top <= y) current = headings[k]; else break;
    }
    if (current) setActive(current.sectionId, current.h3Id);
  }

  var ticking = false;
  window.addEventListener('scroll', function () {
    if (!ticking) { window.requestAnimationFrame(function () { updateActive(); ticking = false; }); ticking = true; }
  }, { passive: true });
  updateActive();

  /* Close mobile drawer on link click */
  tocList.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () {
      var nav = document.querySelector('page-toc, nav.toc');
      if (nav) nav.classList.remove('open');
    });
  });
}

/* ============ Reading aids: progress, back-to-top, copy-btn, glossary ============ */
// The once-only globals (scroll + keydown listeners) are registered the
// first time initReadingAids runs; subsequent calls only re-scan the DOM
// for new <pre> blocks needing copy buttons. Without this guard, every
// renderer-rendered event would attach a duplicate scroll + keydown
// closure that can't be removed.
var __htmldocAidsInited = false;

function initReadingAids() {
  if (!__htmldocAidsInited) {
    __htmldocAidsInited = true;

    /* Progress bar + back-to-top */
    (function () {
      var bar = document.getElementById('progress-bar');
      var btt = document.querySelector('.back-to-top');
      var ticking = false;
      function update() {
        var h = document.documentElement;
        var max = h.scrollHeight - h.clientHeight;
        if (bar) bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
        if (btt) btt.classList.toggle('visible', h.scrollTop > 600);
        ticking = false;
      }
      window.addEventListener('scroll', function () {
        if (!ticking) { window.requestAnimationFrame(update); ticking = true; }
      }, { passive: true });
      update();
    })();

    /* Escape closes mobile TOC */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        var nav = document.querySelector('page-toc, nav.toc');
        if (nav) nav.classList.remove('open');
      }
    });
  }

  /* Copy-to-clipboard on every <pre> block — re-runs safely; already
     guarded by `if (pre.querySelector('.copy-btn')) return`. Icon-only
     (clipboard → checkmark on success → cross on failure). */
  (function () {
    if (!navigator.clipboard) return;
    document.querySelectorAll('pre').forEach(function (pre) {
      if (pre.querySelector('.copy-btn')) return;
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.innerHTML = ICON_CLIPBOARD;
      btn.title = 'Copy code to clipboard';
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      pre.appendChild(btn);
      btn.addEventListener('click', function () {
        var code = pre.querySelector('code');
        var text = code ? code.textContent : pre.textContent;
        navigator.clipboard.writeText(text).then(function () {
          btn.innerHTML = ICON_CHECK;
          btn.classList.add('copied'); btn.classList.remove('error');
          setTimeout(function () {
            btn.innerHTML = ICON_CLIPBOARD;
            btn.classList.remove('copied');
          }, 1500);
        }).catch(function () {
          btn.innerHTML = ICON_CROSS;
          btn.classList.add('error'); btn.classList.remove('copied');
          setTimeout(function () {
            btn.innerHTML = ICON_CLIPBOARD;
            btn.classList.remove('error');
          }, 1500);
        });
      });
    });
  })();

  /* Expand affordance on content images. Hover reveals a small chip at
     the image's top-right; click opens the image in the shared lightbox
     overlay. Skip images inside hosts that own their own expand path
     (charts, diagrams, tooltips, custom snippets). */
  (function () {
    if (!window.__htmldocLightbox) return;
    var main = document.querySelector('#main-content') || document.body;
    main.querySelectorAll('img').forEach(function (img) {
      if (img.dataset.hdtExpandBound === '1') return;
      if (img.closest('html-doc-chart, html-doc-diagram, html-doc-live-snippet, .html-doc-tooltip, .hdt-lightbox, page-chrome, page-nav, page-toc')) return;
      if (img.width && img.width < 80) return;   // skip tiny inline glyphs
      img.dataset.hdtExpandBound = '1';
      // Wrap the image in a host so the chip can absolute-position over it.
      var host = document.createElement('span');
      host.className = 'hdt-img-host';
      img.parentNode.insertBefore(host, img);
      host.appendChild(img);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'hdt-img-expand';
      btn.innerHTML = ICON_EXPAND;
      btn.title = 'Expand image';
      btn.setAttribute('aria-label', 'Expand image');
      host.appendChild(btn);
      btn.addEventListener('click', function () {
        var big = document.createElement('img');
        big.src = img.currentSrc || img.src;
        big.alt = img.alt || '';
        big.className = 'hdt-lightbox-img';
        __htmldocLightbox.open(big, { title: img.alt || 'Expanded image' });
      });
    });
  })();

  /* Wrap toggle on every <pre> — same shape as copy button, sits to its
     left. Toggles a per-block .hdt-wrap class on the <pre>; CSS flips
     white-space: pre → pre-wrap and the horizontal scrollbar away.
     State is per-block on purpose: wrapping a 200-character SQL query
     to read it shouldn't also wrap a tight CSS sample on the same page. */
  (function () {
    document.querySelectorAll('pre').forEach(function (pre) {
      if (pre.querySelector('.hdt-wrap-btn')) return;
      // Skip blocks inside hosts that own their own toolbar (charts,
      // diagrams, live snippets, tooltips).
      if (pre.closest('html-doc-chart, html-doc-diagram, html-doc-live-snippet, .html-doc-tooltip')) return;
      var btn = document.createElement('button');
      btn.className = 'hdt-wrap-btn';
      btn.type = 'button';
      btn.innerHTML = ICON_WRAP;
      btn.title = 'Toggle line wrapping';
      btn.setAttribute('aria-label', 'Toggle line wrapping');
      btn.setAttribute('aria-pressed', 'false');
      pre.appendChild(btn);
      btn.addEventListener('click', function () {
        var wrapped = pre.classList.toggle('hdt-wrap');
        btn.classList.toggle('active', wrapped);
        btn.setAttribute('aria-pressed', wrapped ? 'true' : 'false');
      });
    });
  })();

  /* Prism syntax highlight — lazy CDN load; only triggers if at least
     one `<code class="language-...">` block exists on the page. The
     per-block line-wrap + fold pass is registered as a Prism
     `complete` hook (see __prismLoader.load) so it fires AFTER each
     block's final highlight, not before — the autoloader replaces
     innerHTML asynchronously and races a then() chain. */
  if (typeof __prismLoader !== 'undefined') {
    __prismLoader.highlightAll();
  }

  /* Line-number gutter on every <pre><code>. The gutter is an absolute-
     positioned sibling that lives inside the <pre> but BEFORE the
     <code>, so Prism's token rewriting (which touches <code>.innerHTML
     only) doesn't disturb it. user-select:none + pointer-events:none
     keep numbers out of copy-paste and out of click flow. Idempotent
     via data-hdt-numbered. */
  document.querySelectorAll('pre:not([data-hdt-numbered])').forEach(function (pre) {
    if (pre.closest('.html-doc-tooltip, html-doc-chart, html-doc-diagram, html-doc-live-snippet')) return;
    var code = pre.querySelector(':scope > code');
    if (!code) return;
    var text = code.textContent || '';
    // Trim trailing newline so the very last empty line doesn't get a number.
    if (text.endsWith('\n')) text = text.slice(0, -1);
    var lineCount = text.length ? text.split('\n').length : 1;
    if (lineCount < 1) return;
    pre.setAttribute('data-hdt-numbered', '1');
    pre.classList.add('hdt-line-numbered');
    // No standalone gutter element — number + fold cells are injected
    // into each per-line span by _hdtWrapCodeLines. This makes line
    // numbers ride along with their code line when word-wrap is on
    // (which absolute-positioned gutters cannot do).
  });
  // Code blocks that have no language-* class (and so never trigger
  // the Prism `complete` hook) still get line-wrapping so folds can
  // match anything brace-shaped that lands in them. Defer to the next
  // tick so the gutter pass above has finished attaching.
  setTimeout(function () {
    document.querySelectorAll('pre.hdt-line-numbered:not([data-hdt-lines-wrapped])').forEach(function (pre) {
      var code = pre.querySelector(':scope > code');
      if (!code) return;
      // Skip blocks Prism is responsible for — the hook will handle them.
      if (/language-[\w-]+/.test(code.className)) return;
      pre.setAttribute('data-hdt-lines-wrapped', '1');
      _hdtWrapCodeLines(code);
    });
  }, 0);

  /* Wide-table support: every plain <table> gets a scrollable wrapper,
     a "Table | Cards | List" view toggle, and a full-width expand button.
     Wrapper is idempotent — re-running initReadingAids leaves bound tables
     alone. Tables inside tooltips, callouts or chart/diagram elements
     are skipped. Cards and List views are only generated when the table
     has a <thead> to source keys from. */
  document.querySelectorAll('table:not([data-hdt-bound])').forEach(function (table) {
    if (table.closest('.hdt-table-scroll, .html-doc-tooltip, html-doc-chart, html-doc-diagram')) return;
    table.setAttribute('data-hdt-bound', '1');

    var headers = Array.prototype.map.call(table.querySelectorAll('thead th'), function (th) { return th.innerHTML; });
    var colCount = headers.length || (function () {
      var fr = table.querySelector('tr');
      return fr ? fr.children.length : 0;
    })();
    var rowEls  = Array.prototype.slice.call(table.querySelectorAll('tbody tr'));
    if (!rowEls.length) {
      rowEls = Array.prototype.slice.call(table.querySelectorAll('tr'));
    }

    /* Chip-filter columns are declared by the JSON renderer or by hand-
       authored HTML as `<th data-filter="chips" data-values="a|b|c">`.
       Cells in those columns may declare their own value set via
       `<td data-values="security|perf">` (multi-valued) — chrome.js
       reads both at init time so the chip rack and predicate use the
       same source of truth as the rendered DOM. */
    var chipCols = {};
    var chipColLabels = {};
    Array.prototype.forEach.call(table.querySelectorAll('thead th'), function (th, idx) {
      if (th.getAttribute('data-filter') !== 'chips') return;
      var raw = (th.getAttribute('data-values') || '').split('|').filter(Boolean);
      if (!raw.length) return;
      chipCols[idx] = { values: raw };
      chipColLabels[idx] = (th.textContent || '').trim();
    });
    var hasChipCols = Object.keys(chipCols).length > 0;

    /* Classify every <tr> as either a "group" header or a data "row".
       Group detection:
         - tr.classList contains 'group' / 'group-header' / 'subhead'
         - tr contains a single <th colspan="N"> spanning the table width
         - tr contains a single <td colspan="N"> spanning the table width
       Data row inherits clickability from the <tr> level so Cards / List
       views can re-create the same click/keyboard affordance:
         - tr.onclick / tr.dataset.href / tr.role / tr.tabIndex
         - or, if absent, the first <a href> inside the row */
    function classify(tr) {
      var classes = tr.className || '';
      var isGroupCls = /(^|\s)(group|group-header|subhead|table-group)(\s|$)/.test(classes);
      var cells = tr.children;
      var lone = (cells.length === 1) ? cells[0] : null;
      var spans = lone && lone.colSpan && lone.colSpan >= Math.max(1, colCount);
      var isGroup = isGroupCls || (lone && lone.tagName === 'TH' && cells.length === 1)
                                || (spans && (lone.tagName === 'TH' || lone.tagName === 'TD'));
      if (isGroup) {
        var title = lone ? lone.innerHTML : tr.innerHTML;
        return { type: 'group', title: title, classes: classes, el: tr };
      }
      var tdList = tr.querySelectorAll(':scope > td');
      if (!tdList.length) return null;
      var firstAnchor = tr.querySelector(':scope > td a[href]');
      var iv = {
        onclick: tr.getAttribute('onclick'),
        href: tr.getAttribute('data-href') || (firstAnchor ? firstAnchor.getAttribute('href') : null),
        role: tr.getAttribute('role'),
        tabindex: tr.getAttribute('tabindex'),
        target: tr.getAttribute('data-target') || (firstAnchor ? firstAnchor.getAttribute('target') : null),
        classes: classes,
      };
      var cellHtml = Array.prototype.map.call(tdList, function (td) { return td.innerHTML; });
      // Per-cell chip values from `<td data-values="a|b">`. Null entries
      // mean the cell did not declare a value set; the chip predicate
      // falls back to the stripped cell text in that case.
      var cellValues = Array.prototype.map.call(tdList, function (td) {
        var dv = td.getAttribute('data-values');
        return dv != null ? dv.split('|').filter(Boolean) : null;
      });
      // Keep a reference to the live <tr> so renderTable can preserve
      // author-attached event listeners and nested interactive content
      // by re-attaching the element (instead of cloning innerHTML).
      return { type: 'row', cells: cellHtml, cellValues: cellValues, iv: iv, el: tr };
    }

    var allClassified = rowEls.map(classify).filter(Boolean);
    var flatRows = allClassified.filter(function (e) { return e.type === 'row'; });
    var authorGroupTitles = allClassified.filter(function (e) { return e.type === 'group'; })
                                         .map(function (e) { return e.title; });
    var hasAuthorGroups = authorGroupTitles.length > 0;
    var rowCount = flatRows.length;
    var canPivot = headers.length > 0 && rowCount > 0;

    var wrap = document.createElement('div');
    // CSS-driven view switching: setting wrap.dataset.view to table/list/cards
    // (re)flows the three view containers via attribute selectors in the CSS.
    // Avoids the [hidden]-vs-display:grid conflict where the cards grid
    // remained visible behind the table.
    // Start narrow — auto-fit logic below toggles `expanded` only when the
    // table's natural width overflows the column. The first manual click
    // on the expand button pins state and stops auto-toggling.
    wrap.className = 'hdt-table-wrap';
    wrap.dataset.view = 'table';

    var ctrl = document.createElement('div');
    ctrl.className = 'hdt-table-controls';
    // Filter input on the left, stats counter immediately after it
    // (the two are read together: "I filtered, here is what remains").
    // View order: Table → List → Cards. Stats text is purely numeric
    // ("5" or "3/5") so the visual language stays neutral across doc
    // languages.
    var filterInputHTML = canPivot ? (
      '<label class="hdt-filter">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.6" y2="16.6"/></svg>' +
        '<input type="search" placeholder="Filter…" aria-label="Filter table rows">' +
      '</label>'
    ) : '';
    var statsHTML = canPivot ? '<span class="hdt-stats" aria-live="polite"></span>' : '';
    var groupByHTML = '';
    if (canPivot && headers.length > 1) {
      // Strip HTML tags from header text for the picker option label
      // so author-emitted <code> / inline formatting doesn't leak into
      // the dropdown choices.
      var stripHtml0 = function (s) { return String(s).replace(/<[^>]+>/g, '').trim(); };
      var opts = ['<option value="none">— no grouping —</option>'];
      if (hasAuthorGroups) opts.push('<option value="author" selected>Original groups</option>');
      headers.forEach(function (h, i) {
        opts.push('<option value="' + i + '">' + escapeXml(stripHtml0(h) || ('Column ' + (i + 1))) + '</option>');
      });
      groupByHTML =
        '<label class="hdt-groupby">' +
          '<span class="hdt-groupby-label" aria-hidden="true">Group:</span>' +
          '<select class="hdt-groupby-select" aria-label="Group by column">' + opts.join('') + '</select>' +
        '</label>';
    }
    var viewBtns = canPivot ? (
      '<button data-view="table" type="button" class="active" aria-pressed="true">Table</button>' +
      '<button data-view="list"  type="button" aria-pressed="false">List</button>' +
      '<button data-view="cards" type="button" aria-pressed="false">Cards</button>' +
      '<button data-view="board" type="button" aria-pressed="false">Board</button>' +
      '<span class="hdt-ctrl-sep" aria-hidden="true"></span>'
    ) : '';
    ctrl.innerHTML =
      filterInputHTML +
      statsHTML +
      groupByHTML +
      viewBtns +
      '<button data-expand type="button" aria-pressed="false" title="Toggle full-width / fit to column">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="4 14 4 20 10 20"/><polyline points="20 10 20 4 14 4"/><line x1="14" y1="10" x2="20" y2="4"/><line x1="10" y1="14" x2="4" y2="20"/></svg>' +
      '</button>';

    var scroll = document.createElement('div');
    scroll.className = 'hdt-table-scroll';

    table.parentNode.insertBefore(wrap, table);
    scroll.appendChild(table);
    wrap.appendChild(ctrl);
    wrap.appendChild(scroll);

    if (canPivot) {
      function applyRowInteractivity(el, iv) {
        if (iv.classes) {
          var keep = iv.classes
            .split(/\s+/)
            .filter(function (c) { return c && !/^(group|group-header|subhead|table-group)$/.test(c); });
          if (keep.length) el.className += ' ' + keep.join(' ');
        }
        if (iv.role)               el.setAttribute('role', iv.role);
        if (iv.tabindex != null)   el.setAttribute('tabindex', iv.tabindex);
        if (iv.onclick)            el.setAttribute('onclick', iv.onclick);
        if (iv.href) {
          el.setAttribute('href', iv.href);
          if (iv.target) el.setAttribute('target', iv.target);
        }
      }

      function stripHtml(s) { return String(s).replace(/<[^>]+>/g, '').trim(); }

      // Cards + List + Board containers (rebuilt by render()).
      var cards = document.createElement('div');
      cards.className = 'hdt-table-cards';
      wrap.appendChild(cards);
      var list = document.createElement('div');
      list.className = 'hdt-table-list';
      wrap.appendChild(list);
      var board = document.createElement('div');
      board.className = 'hdt-table-board';
      wrap.appendChild(board);

      // State
      var sortCol = -1;
      var sortDir = 0;       // 1 asc, -1 desc, 0 none
      var filterText = '';
      var tbody = table.querySelector('tbody') || table;
      // Group-by state: 'author' (use the JSON-declared groups), 'none'
      // (flat row list), or a stringified column index. Default to
      // 'author' when the JSON declared groups, else 'none'.
      var groupByCol = hasAuthorGroups ? 'author' : 'none';

      /* Collapsed-group state. Keyed by stripped group title so the
         same toggle state persists across all three views (table /
         list / cards). Collapse hides rows visually but does NOT
         affect the stats counter or the group's own count badge —
         the group is "folded", not "filtered". */
      var collapsedGroups = new Set();
      function groupKey(e) { return stripHtml(e.title); }
      function isGroupCollapsed(e) { return collapsedGroups.has(groupKey(e)); }
      function toggleGroup(e) {
        var k = groupKey(e);
        if (collapsedGroups.has(k)) collapsedGroups.delete(k);
        else collapsedGroups.add(k);
        render();
      }

      /* Chip state: per-column Set<value> of currently-active chips.
         A row passes a column iff the cell's value set intersects
         the active chip set (OR within column). Columns combine with
         AND. Standard faceted-filter semantics. */
      var chipsState = {};
      Object.keys(chipCols).forEach(function (c) { chipsState[c] = new Set(); });

      function hasActiveChips() {
        for (var c in chipsState) {
          if (chipsState[c] && chipsState[c].size > 0) return true;
        }
        return false;
      }

      function cellValuesFor(e, col) {
        var declared = e.cellValues && e.cellValues[col];
        if (declared) return declared;
        // Fallback: treat the rendered cell text as a single value.
        var txt = stripHtml(e.cells[col] || '').trim();
        return txt ? [txt] : [];
      }

      function rowMatchesChips(e) {
        for (var colS in chipsState) {
          var st = chipsState[colS];
          if (!st || st.size === 0) continue;
          var vals = cellValuesFor(e, +colS);
          var ok = false;
          for (var i = 0; i < vals.length; i++) {
            if (st.has(vals[i])) { ok = true; break; }
          }
          if (!ok) return false;
        }
        return true;
      }

      function rowMatchesText(e, needle) {
        if (!needle) return true;
        return e.cells.some(function (c) { return stripHtml(c).toLowerCase().indexOf(needle) !== -1; });
      }

      /* Build the current entry list based on groupByCol:
           - 'author' → reuse the JSON-declared groups verbatim
           - 'none'   → flat row list, no group entries
           - <colIdx> → bucket rows by their value(s) in that column
         Group entries always carry a fresh <tr class="group"> for the
         table-view path; collapse state survives across rebuilds via
         the title-based collapsedGroups Set. */
      function buildEntries() {
        if (groupByCol === 'author') return allClassified.slice();
        if (groupByCol === 'none') return flatRows.slice();
        var col = +groupByCol;
        if (!Number.isFinite(col)) return flatRows.slice();
        var buckets = new Map();
        flatRows.forEach(function (row) {
          var vals = cellValuesFor(row, col);
          var key = vals.length ? vals.join(', ') : '—';
          if (!buckets.has(key)) buckets.set(key, []);
          buckets.get(key).push(row);
        });
        // Sort group keys: numeric-aware locale compare for stable order.
        var keys = Array.from(buckets.keys()).sort(function (a, b) {
          return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
        });
        var out = [];
        keys.forEach(function (k) {
          var tr = document.createElement('tr');
          tr.className = 'group';
          var th = document.createElement('th');
          th.colSpan = Math.max(1, colCount);
          th.textContent = k;
          tr.appendChild(th);
          out.push({ type: 'group', title: k, el: tr, classes: 'group' });
          buckets.get(k).forEach(function (r) { out.push(r); });
        });
        return out;
      }

      function entriesMatchingFilter() {
        var entries = buildEntries();
        if (!filterText && !hasActiveChips()) return entries;
        var needle = filterText ? filterText.toLowerCase() : '';
        // Keep groups whose subsequent rows have at least one match.
        var visible = entries.map(function (e) {
          if (e.type === 'row') {
            return rowMatchesText(e, needle) && rowMatchesChips(e);
          }
          return null; // groups decided below
        });
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].type !== 'group') continue;
          var has = false;
          for (var j = i + 1; j < entries.length; j++) {
            if (entries[j].type === 'group') break;
            if (visible[j]) { has = true; break; }
          }
          visible[i] = has;
        }
        return entries.filter(function (_, i) { return visible[i]; });
      }

      function entriesSorted(visible) {
        if (sortCol < 0 || sortDir === 0) return visible;
        // Sort rows within each group block; preserve group order.
        var out = [];
        var bucket = [];
        function flush() {
          bucket.sort(function (a, b) {
            var av = stripHtml(a.cells[sortCol] || '');
            var bv = stripHtml(b.cells[sortCol] || '');
            var nA = parseFloat(av), nB = parseFloat(bv);
            var numeric = !isNaN(nA) && !isNaN(nB) &&
                          /^-?\$?[\d.,%]+\s*$/.test(av) && /^-?\$?[\d.,%]+\s*$/.test(bv);
            var cmp = numeric ? (nA - nB) : av.toLowerCase().localeCompare(bv.toLowerCase());
            return sortDir * cmp;
          });
          bucket.forEach(function (r) { out.push(r); });
          bucket = [];
        }
        visible.forEach(function (e) {
          if (e.type === 'group') { flush(); out.push(e); }
          else bucket.push(e);
        });
        flush();
        return out;
      }

      /* Count rows that follow each group header within the visible
         window. Returns { perGroup: Map<entry, number>, visibleRows }.
         Computed once per render() so all three views agree. */
      function entryCounts(visible) {
        var perGroup = new Map();
        var visibleRows = 0;
        var cursor = null;
        visible.forEach(function (e) {
          if (e.type === 'group') {
            cursor = e;
            perGroup.set(e, 0);
          } else {
            visibleRows++;
            if (cursor) perGroup.set(cursor, perGroup.get(cursor) + 1);
          }
        });
        return { perGroup: perGroup, visibleRows: visibleRows };
      }

      function fmtGroupCount(n) {
        // Bare numeral — the badge shape (pill) carries the meaning,
        // no language token needed.
        return String(n);
      }

      /* Build (or refresh) the chrome on a source-table group <tr>:
         leading chevron toggle, trailing count badge. Idempotent so
         re-runs from render() don't pile up extra spans. The chevron
         carries the click target; the row itself is also clickable for
         a generous hit target. */
      function dressGroupRow(tr, e, n) {
        if (!tr) return;
        var cell = tr.querySelector(':scope > th, :scope > td');
        if (!cell) return;
        var chev = cell.querySelector(':scope > .hdt-group-chevron');
        if (!chev) {
          chev = document.createElement('span');
          chev.className = 'hdt-group-chevron';
          chev.setAttribute('role', 'button');
          chev.setAttribute('aria-label', 'Toggle group');
          chev.setAttribute('tabindex', '0');
          chev.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 8 10 12 6"/></svg>';
          cell.insertBefore(chev, cell.firstChild);
          chev.addEventListener('click', function (ev) { ev.stopPropagation(); toggleGroup(e); });
          chev.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleGroup(e); }
          });
          tr.classList.add('hdt-collapsible');
          tr.addEventListener('click', function (ev) {
            // Avoid double-fire when the chevron itself was the target.
            if (ev.target.closest('.hdt-group-chevron')) return;
            toggleGroup(e);
          });
        }
        // Count badge sits between chevron and the author title so the
        // numbers line up at the same x across all group rows.
        var badge = cell.querySelector(':scope > .hdt-group-count');
        if (!badge) {
          badge = document.createElement('span');
          badge.className = 'hdt-group-count';
          cell.insertBefore(badge, chev.nextSibling);
        }
        badge.textContent = fmtGroupCount(n);
        var collapsed = isGroupCollapsed(e);
        tr.classList.toggle('hdt-collapsed', collapsed);
        chev.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      }

      function renderTable(visible, counts) {
        // Detach all existing rows from tbody; re-append in visible order.
        Array.prototype.slice.call(tbody.querySelectorAll(':scope > tr')).forEach(function (tr) {
          tr.parentNode.removeChild(tr);
        });
        var skip = false;
        visible.forEach(function (e) {
          if (e.type === 'group') {
            dressGroupRow(e.el, e, counts.perGroup.get(e) || 0);
            skip = isGroupCollapsed(e);
            tbody.appendChild(e.el);
          } else if (!skip && e.el) {
            tbody.appendChild(e.el);
          }
        });
      }

      function makeGroupHeader(tag, cls, e, count) {
        var h = document.createElement(tag);
        h.className = cls + ' hdt-collapsible';
        var chev = document.createElement('span');
        chev.className = 'hdt-group-chevron';
        chev.setAttribute('role', 'button');
        chev.setAttribute('aria-label', 'Toggle group');
        chev.setAttribute('tabindex', '0');
        chev.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 8 10 12 6"/></svg>';
        var title = document.createElement('span');
        title.className = 'hdt-group-title';
        title.innerHTML = e.title;
        var badge = document.createElement('span');
        badge.className = 'hdt-group-count';
        badge.textContent = fmtGroupCount(count);
        // Count badge sits second (chevron, count, title) so the
        // numbers line up at the same x across rows in cards/list view.
        h.appendChild(chev);
        h.appendChild(badge);
        h.appendChild(title);
        var collapsed = isGroupCollapsed(e);
        h.classList.toggle('hdt-collapsed', collapsed);
        chev.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        chev.addEventListener('click', function (ev) { ev.stopPropagation(); toggleGroup(e); });
        chev.addEventListener('keydown', function (ev) {
          if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleGroup(e); }
        });
        h.addEventListener('click', function (ev) {
          if (ev.target.closest('.hdt-group-chevron')) return;
          toggleGroup(e);
        });
        return h;
      }

      function renderCards(visible, counts) {
        cards.innerHTML = '';
        var skip = false;
        visible.forEach(function (e) {
          if (e.type === 'group') {
            cards.appendChild(makeGroupHeader('div', 'hdt-cards-group', e, counts.perGroup.get(e) || 0));
            skip = isGroupCollapsed(e);
            return;
          }
          if (skip) return;
          var card = document.createElement(e.iv.href ? 'a' : 'div');
          card.className = 'hdt-card';
          applyRowInteractivity(card, e.iv);
          e.cells.forEach(function (cell, i) {
            if (!headers[i]) return;
            var r = document.createElement('div');
            r.className = 'hdt-card-row';
            r.innerHTML =
              '<span class="hdt-card-key">' + headers[i] + '</span>' +
              '<span class="hdt-card-val">' + cell + '</span>';
            card.appendChild(r);
          });
          cards.appendChild(card);
        });
      }

      function renderList(visible, counts) {
        list.innerHTML = '';
        var skip = false;
        visible.forEach(function (e) {
          if (e.type === 'group') {
            list.appendChild(makeGroupHeader('h4', 'hdt-list-group', e, counts.perGroup.get(e) || 0));
            skip = isGroupCollapsed(e);
            return;
          }
          if (skip) return;
          /* Each row becomes its own 2-col <table class="hdt-list-card">.
             First column = header (<th scope="row">), second column = cell
             value (<td>). Makes the list view literally tabular per item
             rather than a styled definition list. */
          var inner = document.createElement('table');
          inner.className = 'hdt-list-card';
          var tb = document.createElement('tbody');
          e.cells.forEach(function (cell, i) {
            if (!headers[i]) return;
            var rowEl = document.createElement('tr');
            var th = document.createElement('th');
            th.setAttribute('scope', 'row');
            th.innerHTML = headers[i];
            var td = document.createElement('td');
            td.innerHTML = cell;
            rowEl.appendChild(th);
            rowEl.appendChild(td);
            tb.appendChild(rowEl);
          });
          inner.appendChild(tb);
          if (e.iv.href) {
            var a = document.createElement('a');
            a.className = 'hdt-list-row';
            applyRowInteractivity(a, e.iv);
            a.appendChild(inner);
            list.appendChild(a);
          } else if (e.iv.onclick || e.iv.role === 'button') {
            var btn = document.createElement('div');
            btn.className = 'hdt-list-row';
            applyRowInteractivity(btn, e.iv);
            btn.appendChild(inner);
            list.appendChild(btn);
          } else {
            var wrapEl = document.createElement('div');
            wrapEl.className = 'hdt-list-row hdt-list-row-static';
            wrapEl.appendChild(inner);
            list.appendChild(wrapEl);
          }
        });
      }

      /* Board view — kanban-style lanes, one per unique value in the
         active group column. Lane order: (a) honor the active column's
         data-board-order attribute when column-grouping (so the author
         can declare "next, doing, done" instead of getting whichever
         value first-occurs in the rows); (b) fall back to group
         iteration order otherwise (group_by_author preserves declared
         order; bare column-grouping keeps first-occurrence). Each row
         becomes a card in its lane. When no grouping is active, the
         board collapses to a single "All" lane (still useful as a card
         flow without group rules). */
      function renderBoard(visible, counts) {
        board.innerHTML = '';
        // Bucket rows by their active group key. `visible` is the same
        // alternating [group?, row, row, group, row, ...] sequence the
        // other views consume; we just need to re-bucket it.
        var lanes = new Map();
        var currentGroup = null;
        visible.forEach(function (e) {
          if (e.type === 'group') {
            currentGroup = e;
            if (!lanes.has(e)) lanes.set(e, []);
            return;
          }
          var key = currentGroup || '__all__';
          if (!lanes.has(key)) lanes.set(key, []);
          lanes.get(key).push(e);
        });
        // Apply boardOrder when column-grouping. Unknown values keep
        // first-occurrence order at the end so the author sees them.
        var laneOrder = null;
        if (groupByCol !== 'author' && groupByCol !== 'none') {
          var colIdx = +groupByCol;
          if (Number.isFinite(colIdx)) {
            var thsB = table.querySelectorAll('thead th');
            var orderAttr = thsB[colIdx] && thsB[colIdx].getAttribute('data-board-order');
            if (orderAttr) laneOrder = orderAttr.split('|');
          }
        }
        var laneEntries = Array.from(lanes.entries());
        if (laneOrder) {
          var laneKeyTitle = function (k) {
            if (k === '__all__') return '';
            return stripHtml((k.label || k.title || k.key || '').toString()).trim();
          };
          var laneRank = function (k) {
            var i = laneOrder.indexOf(laneKeyTitle(k));
            return i === -1 ? laneOrder.length : i;
          };
          laneEntries.sort(function (a, b) { return laneRank(a[0]) - laneRank(b[0]); });
        }
        // Render each lane as a column with a header + stacked cards.
        laneEntries.forEach(function (entry) {
          var key = entry[0];
          var rows = entry[1];
          var lane = document.createElement('div');
          lane.className = 'hdt-board-lane';
          var head = document.createElement('div');
          head.className = 'hdt-board-lane-head';
          if (key === '__all__') {
            head.innerHTML = '<span class="hdt-board-lane-title">All</span>' +
                             '<span class="hdt-board-lane-count">' + rows.length + '</span>';
          } else {
            var title = (key.label || key.title || key.key || '').toString();
            head.innerHTML =
              '<span class="hdt-board-lane-title">' + escapeXml(title) + '</span>' +
              '<span class="hdt-board-lane-count">' + rows.length + '</span>';
          }
          lane.appendChild(head);
          var laneBody = document.createElement('div');
          laneBody.className = 'hdt-board-lane-body';
          rows.forEach(function (e) {
            var card = document.createElement(e.iv.href ? 'a' : 'div');
            card.className = 'hdt-board-card';
            applyRowInteractivity(card, e.iv);
            e.cells.forEach(function (cell, i) {
              if (!headers[i]) return;
              var r = document.createElement('div');
              r.className = 'hdt-board-card-row';
              r.innerHTML =
                '<span class="hdt-board-card-key">' + headers[i] + '</span>' +
                '<span class="hdt-board-card-val">' + cell + '</span>';
              card.appendChild(r);
            });
            laneBody.appendChild(card);
          });
          lane.appendChild(laneBody);
          board.appendChild(lane);
        });
      }

      /* Stats element lives in the controls bar (right side). Updated on
         every render(); content depends on whether a filter (text or
         chips) is currently narrowing the result set. */
      var statsEl = ctrl.querySelector('.hdt-stats');
      function updateStats(counts) {
        if (!statsEl) return;
        var n = counts.visibleRows;
        var filtering = !!filterText || hasActiveChips();
        // Bare numerals: "N" at rest, "N/M" while filtering, "0/M" when
        // nothing matches. Language-neutral so the doc can be TR or EN
        // without touching the kit.
        if (!filtering) {
          statsEl.textContent = String(n);
          statsEl.classList.remove('hdt-stats-filtered', 'hdt-stats-empty');
        } else {
          statsEl.textContent = n + '/' + rowCount;
          statsEl.classList.add('hdt-stats-filtered');
          statsEl.classList.toggle('hdt-stats-empty', n === 0);
        }
      }

      function updateSortIndicators() {
        var ths = table.querySelectorAll('thead th');
        for (var i = 0; i < ths.length; i++) {
          var th = ths[i];
          th.removeAttribute('aria-sort');
          th.classList.remove('hdt-sort-asc', 'hdt-sort-desc');
          if (i === sortCol) {
            if (sortDir === 1)  { th.classList.add('hdt-sort-asc');  th.setAttribute('aria-sort', 'ascending'); }
            if (sortDir === -1) { th.classList.add('hdt-sort-desc'); th.setAttribute('aria-sort', 'descending'); }
          }
        }
      }

      function render() {
        var v = entriesSorted(entriesMatchingFilter());
        var counts = entryCounts(v);
        renderTable(v, counts);
        renderCards(v, counts);
        renderList(v, counts);
        renderBoard(v, counts);
        updateSortIndicators();
        updateStats(counts);
        updateChipCounts();
      }

      /* Chip rack — one chip-group per filterable column. Sits between
         the controls bar and the scroll viewport so it stays visible
         while the user explores. Each chip is a toggle; clicking it
         re-renders. Count badges show "if I add this chip alone (within
         my current other-column filters), how many rows survive?" so
         the user can see whether a chip will narrow or empty results. */
      var chipsRack = null;
      if (hasChipCols) {
        chipsRack = document.createElement('div');
        chipsRack.className = 'hdt-chips';
        Object.keys(chipCols)
          .sort(function (a, b) { return (+a) - (+b); })
          .forEach(function (colS) {
            var col = +colS;
            /* Two-cell layout: column 1 is the label cell, column 2 is
               the chips cell. Wrapping the chips in their own row makes
               the parent grid lay them out as a clean two-column table
               regardless of how many chips a column declares. */
            var grp = document.createElement('div');
            grp.className = 'hdt-chip-group';
            grp.dataset.col = colS;
            var lbl = document.createElement('span');
            lbl.className = 'hdt-chip-label';
            lbl.textContent = chipColLabels[col] + ':';
            grp.appendChild(lbl);
            var row = document.createElement('div');
            row.className = 'hdt-chip-row';
            grp.appendChild(row);
            chipCols[col].values.forEach(function (v) {
              var btn = document.createElement('button');
              btn.type = 'button';
              btn.className = 'hdt-chip';
              btn.dataset.value = v;
              btn.setAttribute('aria-pressed', 'false');
              var valSpan = document.createElement('span');
              valSpan.className = 'hdt-chip-val';
              valSpan.textContent = v;
              var cntSpan = document.createElement('span');
              cntSpan.className = 'hdt-chip-count';
              btn.appendChild(valSpan);
              btn.appendChild(cntSpan);
              btn.addEventListener('click', function () {
                var st = chipsState[col];
                if (st.has(v)) {
                  st.delete(v);
                  btn.classList.remove('active');
                  btn.setAttribute('aria-pressed', 'false');
                } else {
                  st.add(v);
                  btn.classList.add('active');
                  btn.setAttribute('aria-pressed', 'true');
                }
                grp.classList.toggle('has-active', st.size > 0);
                render();
              });
              row.appendChild(btn);
            });
            // Per-column clear button — sits with the chips; visible
            // only while any chip in the column is active.
            var clr = document.createElement('button');
            clr.type = 'button';
            clr.className = 'hdt-chip-clear';
            clr.textContent = '×';
            clr.setAttribute('aria-label', 'Clear');
            clr.addEventListener('click', function () {
              chipsState[col].clear();
              grp.querySelectorAll('.hdt-chip').forEach(function (b) {
                b.classList.remove('active');
                b.setAttribute('aria-pressed', 'false');
              });
              grp.classList.remove('has-active');
              render();
            });
            row.appendChild(clr);
            chipsRack.appendChild(grp);
          });
        wrap.insertBefore(chipsRack, scroll);
      }

      function updateChipCounts() {
        if (!chipsRack) return;
        var needle = filterText ? filterText.toLowerCase() : '';
        // Chip counts always reflect the underlying flat row population,
        // independent of the current grouping choice — switching how
        // rows are bucketed shouldn't change what each chip represents.
        chipsRack.querySelectorAll('.hdt-chip-group').forEach(function (grp) {
          var col = +grp.dataset.col;
          grp.querySelectorAll('.hdt-chip').forEach(function (btn) {
            var v = btn.dataset.value;
            var count = 0;
            for (var i = 0; i < flatRows.length; i++) {
              var e = flatRows[i];
              if (!rowMatchesText(e, needle)) continue;
              // Apply chip filters for OTHER columns only — so the count
              // reflects "what happens if I toggle this chip" rather than
              // "current rows that have this value".
              var pass = true;
              for (var otherCol in chipsState) {
                if (+otherCol === col) continue;
                var st = chipsState[otherCol];
                if (!st || st.size === 0) continue;
                var ov = cellValuesFor(e, +otherCol);
                var ok = false;
                for (var k = 0; k < ov.length; k++) {
                  if (st.has(ov[k])) { ok = true; break; }
                }
                if (!ok) { pass = false; break; }
              }
              if (!pass) continue;
              var vals = cellValuesFor(e, col);
              if (vals.indexOf(v) !== -1) count++;
            }
            var cnt = btn.querySelector('.hdt-chip-count');
            if (cnt) cnt.textContent = String(count);
            btn.classList.toggle('hdt-chip-empty', count === 0);
          });
        });
      }

      // Bind sort on every <th> in <thead>.
      var ths = table.querySelectorAll('thead th');
      Array.prototype.forEach.call(ths, function (th, idx) {
        th.classList.add('hdt-sortable');
        if (!th.hasAttribute('tabindex')) th.setAttribute('tabindex', '0');
        if (!th.hasAttribute('role'))     th.setAttribute('role', 'button');
        function toggleSort() {
          if (sortCol !== idx) { sortCol = idx; sortDir = 1; }
          else if (sortDir === 1) sortDir = -1;
          else { sortCol = -1; sortDir = 0; }
          render();
        }
        th.addEventListener('click', toggleSort);
        th.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSort(); }
        });
      });

      // Bind filter input.
      var filterInput = ctrl.querySelector('.hdt-filter input');
      if (filterInput) {
        filterInput.addEventListener('input', function () {
          filterText = filterInput.value;
          render();
        });
      }

      // Group-by select.
      var groupBySelect = ctrl.querySelector('.hdt-groupby-select');
      if (groupBySelect) {
        groupBySelect.addEventListener('change', function () {
          groupByCol = groupBySelect.value;
          // Different grouping → previously-collapsed groups don't carry
          // over by name. Start each fresh slice expanded.
          collapsedGroups.clear();
          render();
        });
      }

      // View-toggle handler — CSS-driven via wrap.dataset.view.
      ctrl.querySelectorAll('[data-view]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var view = btn.getAttribute('data-view');
          wrap.dataset.view = view;
          ctrl.querySelectorAll('[data-view]').forEach(function (b) {
            var active = b === btn;
            b.classList.toggle('active', active);
            b.setAttribute('aria-pressed', active ? 'true' : 'false');
          });
        });
      });

      render(); // initial: identity sort, no filter — preserves source order
    }

    // Full-width toggle. Default state is decided by the auto-fit check
    // below (expand iff the table overflows its column); the first manual
    // click pins state via wrap.dataset.fitPinned so resize events stop
    // overriding the user's choice.
    var expBtn = ctrl.querySelector('[data-expand]');
    function applyExpanded(expanded) {
      wrap.classList.toggle('expanded', expanded);
      expBtn.classList.toggle('active', expanded);
      expBtn.setAttribute('aria-pressed', expanded ? 'true' : 'false');
    }
    expBtn.addEventListener('click', function () {
      wrap.dataset.fitPinned = '1';
      applyExpanded(!wrap.classList.contains('expanded'));
    });

    /* Auto-fit: measure once collapsed; if the table's natural width
       exceeds the column, expand. Re-measure ONLY when the parent
       column resizes — observing the scroll viewport would create a
       feedback loop because the expand toggle changes its size, which
       fires the observer, which re-measures, ...
       Measurements are rAF-coalesced so a burst of column resizes
       (e.g. font loading, TOC toggle, window resize) settles to one
       call. The first call is double-rAF-deferred so initial layout
       (fonts, sticky headers, edge fades) is in. */
    var autoFitPending = false;
    function scheduleAutoFit() {
      if (autoFitPending) return;
      autoFitPending = true;
      requestAnimationFrame(function () {
        autoFitPending = false;
        autoFit();
      });
    }
    function autoFit() {
      if (wrap.dataset.fitPinned === '1') return;
      // Force collapsed for the measurement; if the scroll viewport
      // overflows in that state, we need the expanded mode.
      var wasExpanded = wrap.classList.contains('expanded');
      if (wasExpanded) wrap.classList.remove('expanded');
      // 2px hysteresis margin — sub-pixel rounding shouldn't trip the
      // toggle and re-fire the observer.
      var overflowing = scroll.scrollWidth - scroll.clientWidth > 2;
      if (overflowing !== wasExpanded) applyExpanded(overflowing);
      else if (wasExpanded) wrap.classList.add('expanded');
    }
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(function () { requestAnimationFrame(autoFit); });
    } else {
      setTimeout(autoFit, 0);
    }
    if (window.ResizeObserver && wrap.parentElement) {
      var fitRO = new ResizeObserver(scheduleAutoFit);
      // Only the column width matters; ignore the wrap's own size so
      // the toggle's layout effect doesn't loop back into the observer.
      fitRO.observe(wrap.parentElement);
    } else {
      window.addEventListener('resize', scheduleAutoFit);
    }
  });

  /* Glossary tooltip — legacy v1 .g-wrap mobile tap support. The new
     tooltip controller attaches its own listeners; this remains for
     hand-authored HTML using the legacy class. Per-element handler
     reattachment is harmless on re-run. */
  document.querySelectorAll('.g-wrap').forEach(function (el) {
    if (el.dataset.gwrapBound) return;
    el.dataset.gwrapBound = '1';
    el.addEventListener('click', function (e) {
      if (window.matchMedia('(hover: none)').matches) {
        e.preventDefault();
        document.querySelectorAll('.g-wrap.open').forEach(function (o) { if (o !== el) o.classList.remove('open'); });
        el.classList.toggle('open');
      }
    });
  });
}

/* ============ Docs-root discovery ============ *
 * Finds the project root by locating any kit reference in the document
 * and stripping the trailing path back to (and including) the directory
 * containing _kit/. Lets pages at any directory depth fetch kit.json
 * and site-manifest.json from the same place rather than guessing
 * based on the page's own path.
 * ---------------------------------------------------------------- */
/* Build stamp for debugging. Bump KIT_BUILD any time chrome.js gains a
   compatibility-affecting change so users can verify in DevTools that
   their browser/IDE isn't serving a stale cached copy:
       console look for: [html-doc] kit boot · build=...
   The console.info emits once per page load; cheap insurance. */
var __htmldocKitBuild = '2026-05-18-r10';

var __htmldocDocsRoot = (function () {
  // Explicit override wins. Use this for pages that live outside the
  // canonical docs/ tree (internal triage, examples, sandbox) but want
  // to share the same site-manifest / kit.json / glossary as the docs.
  // Value is resolved against the page URL so relative paths work.
  var metaOverride = document.querySelector('meta[name="html-doc-docs-root"]');
  if (metaOverride && metaOverride.getAttribute('content')) {
    try {
      var resolved = new URL(metaOverride.getAttribute('content'), window.location.href).href;
      if (resolved.charAt(resolved.length - 1) !== '/') resolved += '/';
      return resolved;
    } catch (e) { /* fall through */ }
  }
  var refs = document.querySelectorAll('link[href*="_kit/"], script[src*="_kit/"]');
  for (var i = 0; i < refs.length; i++) {
    var url = refs[i].href || refs[i].src || '';
    var idx = url.indexOf('/_kit/');
    if (idx >= 0) return url.slice(0, idx + 1); // includes trailing slash
  }
  // No kit reference found (probably standalone with everything inlined,
  // or an unusual layout). Fall back to page directory.
  return new URL('.', window.location.href).href;
})();

/* Boot stamp — emit once per page so a stale-cached chrome.js is obvious
   in DevTools. Tells the user which build, which docs-root, and whether
   _ijt token propagation is active. */
try {
  console.info(
    '[html-doc] kit boot · build=' + __htmldocKitBuild +
    ' · docsRoot=' + __htmldocDocsRoot +
    ' · authToken=' + (window.__htmldocWithAuth && window.__htmldocWithAuth('x') !== 'x' ? 'yes' : 'no')
  );
} catch (e) { /* ignore */ }

/* Prism `complete` hook target — fires after each block's FINAL
   highlight. The autoloader can trigger MORE than one complete pass
   per element (one before the language module arrives, one after) so
   we re-wrap whenever the lineWrap is missing, rather than guarding
   with a one-shot data attribute that the second pass would silently
   leave behind. Re-detecting folds is cheap and keeps markers in sync. */
function _hdtAfterPrismHighlight(env) {
  if (!env || !env.element || env.element.tagName !== 'CODE') return;
  var code = env.element;
  var pre = code.parentElement;
  if (!pre || pre.tagName !== 'PRE') return;
  if (!pre.classList.contains('hdt-line-numbered')) return;
  if (code.querySelector(':scope > .hdt-code-line')) return; // already wrapped, intact
  _hdtWrapCodeLines(code);
  pre.setAttribute('data-hdt-lines-wrapped', '1');
  // Clear any stale fold-marker state inside per-line cells so a fresh
  // detection pass attaches handlers to the current line's marker.
  Array.prototype.forEach.call(code.querySelectorAll(':scope > .hdt-code-line > .hdt-fold-marker'), function (marker) {
    marker.classList.remove('hdt-foldable', 'hdt-folded');
    marker.removeAttribute('role');
    marker.removeAttribute('tabindex');
    marker.removeAttribute('aria-expanded');
    marker.removeAttribute('data-fold-start');
    marker.removeAttribute('data-fold-end');
  });
  var lang = (code.className.match(/language-([\w-]+)/) || [0, ''])[1].toLowerCase();
  // Stamp a small language pill on the pre so the reader sees what
  // dialect they're looking at. Idempotent — re-runs replace the text
  // rather than appending duplicates.
  if (lang && lang !== 'plaintext' && lang !== 'text' && lang !== 'none') {
    var pill = pre.querySelector(':scope > .hdt-code-lang');
    if (!pill) {
      pill = document.createElement('span');
      pill.className = 'hdt-code-lang';
      pill.setAttribute('aria-hidden', 'true');
      pre.appendChild(pill);
    }
    pill.textContent = lang;
  }
  if (/^(js|javascript|ts|typescript|jsx|tsx|json|json5|css|scss|less)$/.test(lang)) {
    var folds = _hdtDetectBraceFolds(code);
    if (folds.length) _hdtApplyFolds(pre, code, folds);
  }
}

/* ============ Code-block line wrap + brace fold (module scope) ============ *
 * After Prism highlights, we walk the <code>'s child tree and group
 * everything by newlines into one <span class="hdt-code-line"> per
 * source line. Each line includes its own trailing '\n' so collapsing
 * a line via display:none also removes the blank gap it would leave
 * behind. Prism's token spans survive: tokens entirely within a line
 * are moved as-is; tokens that straddle newlines (multi-line strings,
 * block comments) are split into per-line clones — same className
 * preserves coloring across the split.
 * ------------------------------------------------------------------- */
function _hdtWrapCodeLines(code) {
  // Each .hdt-code-line is a grid row with three cells:
  //   [.hdt-code-ln (number)]  [.hdt-fold-marker]  [.hdt-code-content]
  //
  // Numbers + fold markers ride with their code line — when word-wrap
  // is enabled and a logical line spans multiple visual rows, the
  // number stays at the row's top (align-self: start) while the
  // content cell grows to its wrapped height. The absolute-positioned
  // gutter the previous design used couldn't do this (numbers froze
  // at the same y while wrapped content pushed code below).
  function makeLine(lineIdx) {
    var line = document.createElement('span');
    line.className = 'hdt-code-line';
    line.setAttribute('data-line', String(lineIdx));
    var num = document.createElement('span');
    num.className = 'hdt-code-ln';
    num.textContent = String(lineIdx);
    num.setAttribute('aria-hidden', 'true');
    var fold = document.createElement('span');
    fold.className = 'hdt-fold-marker';
    fold.setAttribute('aria-hidden', 'true');
    var content = document.createElement('span');
    content.className = 'hdt-code-content';
    line.appendChild(num);
    line.appendChild(fold);
    line.appendChild(content);
    return line;
  }

  var lines = [makeLine(1)];
  function activeContent() {
    return lines[lines.length - 1].querySelector(':scope > .hdt-code-content');
  }

  function pushChar(s) { activeContent().appendChild(document.createTextNode(s)); }
  function newline() {
    // Trailing newline lives in the CURRENT line so display:none also
    // hides the blank that would otherwise remain.
    activeContent().appendChild(document.createTextNode('\n'));
    lines.push(makeLine(lines.length + 1));
  }

  function emit(node) {
    if (node.nodeType === 3) { // Text
      var t = node.textContent;
      var i = 0;
      while (i < t.length) {
        var nl = t.indexOf('\n', i);
        if (nl === -1) { pushChar(t.slice(i)); break; }
        if (nl > i) pushChar(t.slice(i, nl));
        newline();
        i = nl + 1;
      }
    } else if (node.nodeType === 1) {
      var full = node.textContent;
      if (full.indexOf('\n') === -1) {
        // Whole element fits one line — move it intact, preserving any
        // descendant tokens Prism created.
        activeContent().appendChild(node.cloneNode(true));
      } else {
        // Multi-line element — split into per-line clones at the same
        // className. The descendants are reduced to plain text in each
        // clone (sufficient for strings / comments; complex nested
        // tokens across newlines are very rare).
        var segs = full.split('\n');
        for (var s = 0; s < segs.length; s++) {
          if (s > 0) newline();
          if (segs[s].length) {
            var clone = node.cloneNode(false);
            clone.textContent = segs[s];
            activeContent().appendChild(clone);
          }
        }
      }
    }
  }
  Array.prototype.slice.call(code.childNodes).forEach(emit);
  code.innerHTML = '';
  lines.forEach(function (line) { code.appendChild(line); });
}

/* Find brace-delimited foldable regions: each line ending with '{',
   '[', or '(' opens a fold; the matching closer at the same indent
   ends it. Single-line bodies (`function f() {}` on one source line
   already, or `{ foo: 1 }`) are skipped — folding them yields nothing.
   Indent matching is enough for well-formatted code in the languages
   we target (JS / TS / JSON / CSS) and avoids the cost of a full
   tokeniser. */
function _hdtDetectBraceFolds(code) {
  var lines = code.querySelectorAll('.hdt-code-line');
  if (lines.length < 3) return [];
  var folds = [];
  var stack = [];
  for (var i = 0; i < lines.length; i++) {
    var raw = lines[i].textContent.replace(/\n$/, '');
    var trimmedRight = raw.replace(/\s+$/, '');
    var lead = (raw.match(/^[ \t]*/) || [''])[0];
    var indent = lead.length;
    if (/[{(\[]\s*$/.test(trimmedRight)) {
      stack.push({ openIdx: i, indent: indent });
    } else if (/^\s*[)}\]]/.test(raw) && stack.length) {
      var m = stack.length - 1;
      while (m >= 0 && stack[m].indent !== indent) m--;
      if (m >= 0) {
        var open = stack.splice(m, 1)[0];
        if (i - open.openIdx > 1) folds.push({ start: open.openIdx, end: i });
        // Drop any orphan openers that never matched (mostly inside the
        // current closer's outer block) — keeps the matcher honest.
        stack.splice(m, stack.length - m);
      }
    }
  }
  return folds;
}

/* Wire fold toggles into the per-line fold markers. Foldable markers
   carry the fold range as data attrs (foldStart, foldEnd); a single
   delegated listener on the <code> handles clicks so Prism's
   re-highlight (which can replace <code>.innerHTML mid-flight) doesn't
   leave dangling handlers attached to detached line spans. */
function _hdtApplyFolds(pre, code, folds) {
  var lines = code.querySelectorAll(':scope > .hdt-code-line');
  folds.forEach(function (f) {
    var line = lines[f.start];
    if (!line) return;
    var marker = line.querySelector(':scope > .hdt-fold-marker');
    if (!marker) return;
    marker.classList.add('hdt-foldable');
    marker.setAttribute('role', 'button');
    marker.setAttribute('tabindex', '0');
    marker.setAttribute('aria-expanded', 'true');
    marker.dataset.foldStart = String(f.start);
    marker.dataset.foldEnd = String(f.end);
  });
  if (pre.dataset.hdtFoldDelegated === '1') return;
  pre.dataset.hdtFoldDelegated = '1';
  function handle(target) {
    if (!target.classList.contains('hdt-foldable')) return;
    var start = +target.dataset.foldStart;
    var end = +target.dataset.foldEnd;
    if (!(end > start)) return;
    var willCollapse = !target.classList.contains('hdt-folded');
    target.classList.toggle('hdt-folded', willCollapse);
    target.setAttribute('aria-expanded', willCollapse ? 'false' : 'true');
    var liveCode = pre.querySelector(':scope > code');
    var liveLines = liveCode ? liveCode.querySelectorAll(':scope > .hdt-code-line') : [];
    for (var i = start + 1; i < end; i++) {
      if (liveLines[i]) liveLines[i].classList.toggle('hdt-line-hidden', willCollapse);
    }
    pre.classList.toggle('hdt-has-folds', !!pre.querySelector('.hdt-fold-marker.hdt-folded'));
  }
  code.addEventListener('click', function (e) {
    var t = e.target.closest('.hdt-fold-marker.hdt-foldable');
    if (t) handle(t);
  });
  code.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var t = e.target.closest('.hdt-fold-marker.hdt-foldable');
    if (t) { e.preventDefault(); handle(t); }
  });
}

/* ============ HTML-escape helper (module scope) ============ */
function escapeHTML(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ============ Visual Viewport API — pinch-zoom stability ============ *
 * Position: fixed anchors to the layout viewport. On Safari (and Chrome
 * with touch trackpad), pinch-zoom moves the visual viewport
 * independently — fixed elements appear to drift out of the corner the
 * user sees. We translate the chrome buttons by the visual viewport's
 * offset so they stay anchored to where the user looks.
 * --------------------------------------------------------------------- */
(function () {
  var vv = window.visualViewport;
  if (!vv) return;
  function sync() {
    document.documentElement.style.setProperty('--vv-left', vv.offsetLeft + 'px');
    document.documentElement.style.setProperty('--vv-top',  vv.offsetTop  + 'px');
  }
  vv.addEventListener('scroll', sync);
  vv.addEventListener('resize', sync);
  // Browser zoom (Ctrl+/-) fires window.resize but not always
  // visualViewport.resize. Subscribe to both so fixed chrome stays put.
  window.addEventListener('resize', sync);
  sync();
})();

/* ============ Edge-tab proximity sync ============ *
 * Keeps each pane's edge tab glued to that pane's inner boundary as the
 * layout shifts (responsive resize, .nav-collapsed toggle, .toc-collapsed
 * toggle, max-width centering, browser zoom). Writes
 * --nav-tab-left / --toc-tab-right CSS variables that chrome.css reads
 * for the tab's `left` / `right`. Falls back to viewport edges at narrow
 * widths (where panes become drawers — see the @media block in CSS).
 *
 * Proximity rule (~/.claude/rules/design-principles.md): a control that
 * operates on a panel should live on or near that panel's edge — not at
 * the absolute viewport edge with a wide gap of unrelated content between.
 * ----------------------------------------------------------------------- */
(function () {
  // Tab is 22px wide; we want it to overlap the panel's inner edge by 11
  // (half its width) so the tab visually attaches to the panel.
  var OVERHANG = 11;
  var NARROW = 1024;
  var _ro = null;
  function update() {
    var nav = document.querySelector('page-nav');
    var toc = document.querySelector('.layout:has(page-nav) page-toc');
    var narrow = window.innerWidth <= NARROW;
    var rootStyle = document.documentElement.style;
    if (nav && !narrow) {
      var r = nav.getBoundingClientRect();
      rootStyle.setProperty('--nav-tab-left', Math.round(r.right - OVERHANG) + 'px');
    } else {
      rootStyle.setProperty('--nav-tab-left', '0px');
    }
    if (toc && !narrow) {
      var r2 = toc.getBoundingClientRect();
      rootStyle.setProperty('--toc-tab-right', Math.round(window.innerWidth - r2.left - OVERHANG) + 'px');
    } else {
      rootStyle.setProperty('--toc-tab-right', '0px');
    }
  }

  function attach() {
    update();
    var nav = document.querySelector('page-nav');
    var toc = document.querySelector('page-toc');
    // ResizeObserver tracks the panes' size across CSS transitions
    // (the 0.25s grid-template-columns animation when collapsing).
    if (window.ResizeObserver && !_ro) {
      _ro = new ResizeObserver(update);
      if (nav) _ro.observe(nav);
      if (toc) _ro.observe(toc);
    }
    // MutationObserver on the layout/body picks up state-class flips
    // (.nav-collapsed on .layout, .toc-collapsed on body, .open on each pane).
    var mo = new MutationObserver(update);
    var layout = document.querySelector('.layout');
    if (layout) mo.observe(layout, { attributes: true, attributeFilter: ['class'] });
    mo.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    if (nav) mo.observe(nav, { attributes: true, attributeFilter: ['class'] });
    if (toc) mo.observe(toc, { attributes: true, attributeFilter: ['class'] });
  }

  // Resize / zoom / pinch
  window.addEventListener('resize', update);
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', update);
    window.visualViewport.addEventListener('scroll', update);
  }
  // Renderer can swap layout mid-flight (JSON pages); rerun then.
  window.addEventListener('html-doc:rendered', update);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attach);
  } else {
    attach();
  }
})();

/* ============ Synced highlight: [data-bind] hover/focus pairs ============ *
 * Stripe-class micro-interaction: any element carrying data-bind="X"
 * pairs with all other elements sharing the same key. Hover or focus
 * any partner → all partners flash an accent highlight. Click any
 * partner → the others scroll into view (only when offscreen).
 *
 * Lifted from the design audit: synced prose↔code is the most-praised
 * dev-docs micro-interaction and the cheapest way to signal "this kit
 * was designed, not generated." Reuses the .hovered pattern from
 * UX2 (chart label↔dot) and UX6 / round-9 (annotation chip↔item).
 *
 * Global delegation: handlers attach to document so dynamically-
 * rendered content (renderer.js, custom elements) gets picked up
 * without re-binding.
 * --------------------------------------------------------------------- */
(function () {
  if (typeof document === 'undefined') return;
  if (document.__htmldocBindAttached) return;
  document.__htmldocBindAttached = true;

  function flash(key, on) {
    if (!key) return;
    document.querySelectorAll('[data-bind="' + key + '"]').forEach(function (el) {
      el.classList.toggle('bind-active', on);
    });
  }
  document.addEventListener('mouseover', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-bind]');
    if (!t) return;
    flash(t.getAttribute('data-bind'), true);
  });
  document.addEventListener('mouseout', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-bind]');
    if (!t) return;
    flash(t.getAttribute('data-bind'), false);
  });
  document.addEventListener('focusin', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-bind]');
    if (!t) return;
    flash(t.getAttribute('data-bind'), true);
  });
  document.addEventListener('focusout', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-bind]');
    if (!t) return;
    flash(t.getAttribute('data-bind'), false);
  });
  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-bind]');
    if (!t) return;
    var key = t.getAttribute('data-bind');
    if (!key) return;
    // Find a partner that is currently offscreen; scroll the first one in.
    var partners = document.querySelectorAll('[data-bind="' + key + '"]');
    for (var i = 0; i < partners.length; i++) {
      if (partners[i] === t) continue;
      var r = partners[i].getBoundingClientRect();
      if (r.top < 0 || r.bottom > window.innerHeight) {
        partners[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
        break;
      }
    }
  });
})();

/* ============ Live-reload (only when served via `html-doc serve`) ============ *
 * Opens an EventSource against /__reload — a Server-Sent Events stream
 * that the dev server pushes a message into whenever a watched file
 * changes. On message, the tab reloads. Only attempted when the page is
 * loaded from localhost/127.0.0.1 so production sites never try.
 * --------------------------------------------------------------------------- */
(function () {
  if (typeof window === 'undefined') return;
  var h = window.location && window.location.hostname;
  if (h !== 'localhost' && h !== '127.0.0.1' && h !== '::1') return;
  if (window.__htmldocReloadAttached) return;
  window.__htmldocReloadAttached = true;
  try {
    var es = new EventSource('/__reload');
    es.addEventListener('message', function () {
      try { es.close(); } catch (e) {}
      window.location.reload();
    });
    // Silently let the browser auto-reconnect on transient errors.
    es.addEventListener('error', function () { /* swallow */ });
  } catch (e) { /* SSE unsupported or blocked — no live reload */ }
})();

/* ============ Tooltip controller (used by <glossary-term> + <ext-ref>) ============ */
var __htmldocTooltip = (function () {
  var HIDE_DELAY = 300;
  var SHOW_DELAY = 120;
  // Re-evaluate on every attach so input-mode changes (e.g., user
  // attaches a mouse to a tablet) take effect on subsequently-rendered
  // elements. Existing attachments keep the wiring they had — acceptable
  // tradeoff vs. listening for matchMedia changes and re-binding.
  function isTouch() { return window.matchMedia('(hover: none)').matches; }
  var active = null; // { trigger, tooltip, pinned }
  var hideTimer = null;
  var showTimer = null;

  function clearTimers() {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    if (showTimer) { clearTimeout(showTimer); showTimer = null; }
  }

  function hideImmediate() {
    clearTimers();
    if (active) { active.tooltip.remove(); active = null; }
  }

  function scheduleHide() {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(hideImmediate, HIDE_DELAY);
  }

  function position(tooltip, trigger) {
    var r = trigger.getBoundingClientRect();
    tooltip.style.position = 'absolute';
    tooltip.style.top = '0px';
    tooltip.style.left = '0px';
    var tipH = tooltip.offsetHeight || 100;
    var tipW = tooltip.offsetWidth || 320;
    var top = r.top + window.scrollY - tipH - 10;
    if (top < window.scrollY + 8) top = r.bottom + window.scrollY + 10;
    var left = r.left + window.scrollX;
    if (left + tipW > window.innerWidth + window.scrollX - 12) {
      left = window.innerWidth + window.scrollX - tipW - 12;
    }
    if (left < 8) left = 8;
    tooltip.style.top  = top + 'px';
    tooltip.style.left = left + 'px';
  }

  // SECURITY: data-def is injected via innerHTML to render rich markup
  // (<strong>, <em>, <br>, inline <a>) inside tooltips. The trust
  // boundary is: data-def must only ever be set by code that reads from
  // kit-controlled sources — _kit/glossary/<domain>.json and
  // _kit/extrefs/<domain>.json. The GlossaryTerm and ExtRef
  // connectedCallback handlers are the only setters; both pull from the
  // kit resolver. Do NOT use this controller to render tooltips with
  // arbitrary author input.
  function build(trigger) {
    var body = trigger.getAttribute('data-def') || trigger.getAttribute('data-summary') || trigger.textContent;
    var link = trigger.getAttribute('data-link');
    var lang = trigger.getAttribute('data-lang-shown');
    var t = document.createElement('div');
    t.className = 'html-doc-tooltip';
    var html = '<div class="hdt-body">' + body + '</div>';
    if (lang) html += '<span class="hdt-lang">' + lang + '</span>';
    if (link) html += '<div class="hdt-link"><a href="' + link + '" target="_blank" rel="noopener">Learn more →</a></div>';
    html += '<span class="hdt-pin-hint">click to pin</span>';
    t.innerHTML = html;
    return t;
  }

  function show(trigger, pinned) {
    clearTimers();
    if (active && active.trigger === trigger) {
      if (pinned) { active.pinned = true; active.tooltip.classList.add('pinned'); }
      return;
    }
    hideImmediate();
    var tip = build(trigger);
    document.body.appendChild(tip);
    position(tip, trigger);
    if (pinned) tip.classList.add('pinned');

    tip.addEventListener('mouseenter', clearTimers);
    tip.addEventListener('mouseleave', function () {
      if (!active || !active.pinned) scheduleHide();
    });

    active = { trigger: trigger, tooltip: tip, pinned: !!pinned };
  }

  function attach(trigger) {
    if (!trigger.hasAttribute('tabindex')) trigger.setAttribute('tabindex', '0');
    if (!isTouch()) {
      trigger.addEventListener('mouseenter', function () {
        clearTimers();
        showTimer = setTimeout(function () { show(trigger, false); }, SHOW_DELAY);
      });
      trigger.addEventListener('mouseleave', function () {
        if (showTimer) { clearTimeout(showTimer); showTimer = null; }
        if (active && active.trigger === trigger && active.pinned) return;
        scheduleHide();
      });
      trigger.addEventListener('focus', function () { show(trigger, false); });
      trigger.addEventListener('blur', function () {
        if (!active || !active.pinned) scheduleHide();
      });
    }
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      if (active && active.trigger === trigger && active.pinned) {
        hideImmediate();
      } else {
        show(trigger, true);
      }
    });
  }

  document.addEventListener('click', function (e) {
    if (!e.target.closest('.html-doc-tooltip, [data-html-doc-tooltip-trigger]')) hideImmediate();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && active && active.pinned) hideImmediate();
  });

  return { attach: attach, hide: hideImmediate };
})();

/* ============ kit.json loader (multi-domain glossary + ext-refs) ============ */
var __htmldocKit = (function () {
  var kit = { glossary: {}, extrefs: {}, lang: 'en', lang_fallback: ['en'], domains: [], personalization: [] };
  var loaded = false;
  var waiters = [];

  function load() {
    if (loaded) return Promise.resolve(kit);
    // Standalone build — if the build inlined a kit bundle, hydrate from it.
    var bundleTag = document.getElementById('__htmldoc_kit_bundle__');
    if (bundleTag) {
      try {
        var bundle = JSON.parse(bundleTag.textContent || '{}');
        var bk = bundle.kit || {};
        if (bk.lang) kit.lang = bk.lang;
        if (bk.lang_fallback) kit.lang_fallback = bk.lang_fallback;
        if (bk.domains) kit.domains = bk.domains;
        if (bk.personalization) kit.personalization = bk.personalization;
        if (bundle.glossary) kit.glossary = bundle.glossary;
        if (bundle.extrefs) kit.extrefs = bundle.extrefs;
        // Project-local overrides from kit.json still apply on top.
        if (bk.glossary) {
          Object.keys(bk.glossary).forEach(function (d) {
            kit.glossary[d] = Object.assign({}, kit.glossary[d] || {}, bk.glossary[d]);
          });
        }
        if (bk.extrefs) {
          Object.keys(bk.extrefs).forEach(function (d) {
            kit.extrefs[d] = Object.assign({}, kit.extrefs[d] || {}, bk.extrefs[d]);
          });
        }
      } catch (e) {
        // Malformed bundle — fall through to empty kit.
      }
      loaded = true;
      waiters.forEach(function (w) { w(kit); });
      waiters = [];
      return Promise.resolve(kit);
    }
    // Standalone without a kit bundle: degrade silently.
    if (document.getElementById('__htmldoc_page__')) {
      loaded = true;
      waiters.forEach(function (w) { w(kit); });
      waiters = [];
      return Promise.resolve(kit);
    }
    // Project config lives at the docs root; domain files live in _kit/.
    var wa = (window.__htmldocWithAuth || function (u) { return u; });
    return fetch(wa(__htmldocDocsRoot + 'kit.json'), { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (data) {
        if (data) {
          if (data.lang) kit.lang = data.lang;
          if (data.lang_fallback) kit.lang_fallback = data.lang_fallback;
          if (data.domains) kit.domains = data.domains;
          if (data.personalization) kit.personalization = data.personalization;
        }
        // Load each domain file in parallel
        var promises = kit.domains.flatMap(function (d) {
          return [
            fetch(wa(__htmldocDocsRoot + '_kit/glossary/' + d + '.json'), { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .catch(function () { return null; })
              .then(function (j) {
                if (j && j.entries) kit.glossary[d] = j.entries;
              }),
            fetch(wa(__htmldocDocsRoot + '_kit/extrefs/' + d + '.json'), { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .catch(function () { return null; })
              .then(function (j) {
                if (j && j.entries) kit.extrefs[d] = j.entries;
              })
          ];
        });
        return Promise.all(promises).then(function () {
          // Apply project-level overrides AFTER central domain files
          // have loaded — otherwise the per-domain fetch .then runs
          // last and wholesale-replaces kit.glossary[d], wiping the
          // override entries.
          if (data && data.glossary) {
            Object.keys(data.glossary).forEach(function (d) {
              kit.glossary[d] = Object.assign({}, kit.glossary[d] || {}, data.glossary[d]);
            });
          }
          if (data && data.extrefs) {
            Object.keys(data.extrefs).forEach(function (d) {
              kit.extrefs[d] = Object.assign({}, kit.extrefs[d] || {}, data.extrefs[d]);
            });
          }
          loaded = true;
          // Personalization is a kit-level concept: kit.json declares the
          // keys, chrome.js renders the gear button + swaps {{key}} at
          // runtime. Hand-off to the personalization module so it can
          // attach its UI once the kit data is settled.
          if (typeof __htmldocPersonalization !== 'undefined') {
            try { __htmldocPersonalization.init((data && data.personalization) || kit.personalization || []); }
            catch (e) { /* ignore */ }
          }
          waiters.forEach(function (w) { w(kit); });
          waiters = [];
          return kit;
        });
      });
  }

  function resolveGlossary(term, opts) {
    opts = opts || {};
    var inDomain = opts.in;
    var lang = opts.lang || kit.lang;
    var domains = inDomain ? [inDomain] : kit.domains;
    for (var i = 0; i < domains.length; i++) {
      var d = domains[i];
      var entry = (kit.glossary[d] || {})[term];
      if (entry) {
        var hit = entry[lang];
        var shownLang = lang;
        if (!hit) {
          for (var j = 0; j < kit.lang_fallback.length; j++) {
            hit = entry[kit.lang_fallback[j]];
            if (hit) { shownLang = kit.lang_fallback[j]; break; }
          }
        }
        if (!hit) {
          var any = Object.keys(entry)[0];
          if (any) { hit = entry[any]; shownLang = any; }
        }
        if (hit) return { hit: hit, domain: d, lang: shownLang };
      }
    }
    return null;
  }

  function resolveExtRef(name, opts) {
    opts = opts || {};
    var inDomain = opts.in;
    var lang = opts.lang || kit.lang;
    var domains = inDomain ? [inDomain] : kit.domains;
    for (var i = 0; i < domains.length; i++) {
      var d = domains[i];
      var entry = (kit.extrefs[d] || {})[name];
      if (entry) {
        var hit = entry[lang];
        var shownLang = lang;
        if (!hit) {
          for (var j = 0; j < kit.lang_fallback.length; j++) {
            hit = entry[kit.lang_fallback[j]];
            if (hit) { shownLang = kit.lang_fallback[j]; break; }
          }
        }
        if (!hit) {
          var any = Object.keys(entry)[0];
          if (any) { hit = entry[any]; shownLang = any; }
        }
        if (hit) return { hit: hit, domain: d, lang: shownLang };
      }
    }
    return null;
  }

  function whenReady() {
    if (loaded) return Promise.resolve(kit);
    return new Promise(function (resolve) { waiters.push(resolve); });
  }

  // Defer the initial load until the document is parsed so the standalone
  // detection (looking for the inline page-data script) can see the tag
  // that gets parsed later in body.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }

  return {
    load: load,
    whenReady: whenReady,
    resolveGlossary: resolveGlossary,
    resolveExtRef: resolveExtRef,
    state: function () { return kit; }
  };
})();

/* ============ Inline placeholder personalization (Mintlify lift) ============ *
 * kit.json may declare:
 *   "personalization": [
 *     { "key": "apiKey",    "label": "API Key",    "default": "sk_test_..." },
 *     { "key": "projectId", "label": "Project ID", "default": "proj_demo"   }
 *   ]
 *
 * When present, chrome.js renders a gear icon in the top-right chrome
 * cluster. Clicking opens a small panel with text inputs for each key.
 * Values persist in localStorage under html-doc-personalization. Code
 * blocks (and anywhere else the reader expects swap-in) get {{key}}
 * substrings replaced at runtime with <span class="hdc-personalized">
 * wrappers. Hovering a personalized span shows which key it came from.
 *
 * Why this matters: Mintlify pioneered "set apiKey once, every snippet
 * on every page swaps to your values" — massively reduces tutorial
 * copy-paste friction. html-doc's no-build constraint means we do this
 * at runtime, not at build time; the localStorage-backed state is the
 * full extent of personalization (no accounts, no server, no SaaS).
 * --------------------------------------------------------------------- */
var __htmldocPersonalization = (function () {
  var STORAGE_KEY = 'html-doc-personalization';
  var keys = [];       // [{ key, label, default, type? }]
  var values = {};     // { key: currentValue }
  var btn = null;
  var panel = null;

  function load() {
    try { values = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
    catch (e) { values = {}; }
  }
  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(values)); }
    catch (e) { /* ignore */ }
  }
  function get(k) {
    if (values[k] !== undefined && values[k] !== '') return values[k];
    var spec = keys.filter(function (x) { return x.key === k; })[0];
    return spec && spec.default !== undefined ? spec.default : '';
  }
  function set(k, v) {
    values[k] = v;
    save();
    applyAll();
  }

  function applyAll() {
    // Update spans already wrapped, then look for new {{key}} occurrences.
    document.querySelectorAll('.hdc-personalized').forEach(function (span) {
      var k = span.getAttribute('data-key');
      span.textContent = get(k);
    });
    // Walk likely containers — code blocks, snippets, kbd, and a generic
    // .hdc-personalize-target opt-in for prose passages.
    var roots = document.querySelectorAll('pre, code, kbd, .hdc-personalize-target');
    var pattern = /\{\{(\w+)\}\}/g;
    roots.forEach(function (root) {
      var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      var textNodes = [];
      var n;
      while ((n = w.nextNode())) textNodes.push(n);
      textNodes.forEach(function (textNode) {
        var text = textNode.nodeValue;
        if (text.indexOf('{{') === -1) return;
        pattern.lastIndex = 0;
        var hasMatch = false;
        var test;
        while ((test = pattern.exec(text)) !== null) {
          if (keys.some(function (x) { return x.key === test[1]; })) { hasMatch = true; break; }
        }
        if (!hasMatch) return;
        pattern.lastIndex = 0;
        var frag = document.createDocumentFragment();
        var last = 0;
        var m;
        while ((m = pattern.exec(text)) !== null) {
          if (!keys.some(function (x) { return x.key === m[1]; })) continue;
          if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
          var span = document.createElement('span');
          span.className = 'hdc-personalized';
          span.setAttribute('data-key', m[1]);
          span.title = 'Personalized: ' + m[1];
          span.textContent = get(m[1]);
          frag.appendChild(span);
          last = m.index + m[0].length;
        }
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        textNode.parentNode.replaceChild(frag, textNode);
      });
    });
  }

  function buildButton() {
    var cluster = document.querySelector('page-chrome') || document.body;
    btn = document.createElement('button');
    btn.className = 'ctrl-btn personalize-toggle';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Personalize snippet placeholders');
    btn.title = 'Personalize snippet placeholders';
    btn.innerHTML = ICON_GEAR;
    btn.addEventListener('click', togglePanel);
    cluster.appendChild(btn);
  }

  function togglePanel() {
    if (panel && panel.parentNode) {
      panel.parentNode.removeChild(panel);
      panel = null;
      return;
    }
    panel = document.createElement('div');
    panel.className = 'personalize-panel';
    var html = '<header><strong>Personalize</strong>' +
               '<button type="button" class="personalize-close" aria-label="Close">×</button>' +
               '</header><p>Values you enter here swap into every <code>{{key}}</code> placeholder on the page. Stored only in your browser.</p>';
    html += '<div class="personalize-fields">';
    keys.forEach(function (k) {
      var current = get(k.key);
      html += '<label class="personalize-field">' +
                '<span class="personalize-label">' + escapeXml(k.label || k.key) + '</span>' +
                '<input type="' + (k.type === 'password' ? 'password' : 'text') +
                  '" data-key="' + k.key + '"' +
                  ' value="' + escapeXml(current) + '"' +
                  ' placeholder="' + escapeXml(k.default || '') + '">' +
              '</label>';
    });
    html += '</div>';
    html += '<footer><button type="button" class="personalize-reset">Reset all</button></footer>';
    panel.innerHTML = html;
    document.body.appendChild(panel);
    panel.querySelector('.personalize-close').addEventListener('click', togglePanel);
    panel.querySelector('.personalize-reset').addEventListener('click', function () {
      values = {};
      save();
      applyAll();
      togglePanel();
    });
    panel.querySelectorAll('input[data-key]').forEach(function (input) {
      input.addEventListener('input', function () { set(input.getAttribute('data-key'), input.value); });
    });
  }

  function init(decl) {
    keys = Array.isArray(decl) ? decl.filter(function (x) { return x && x.key; }) : [];
    if (!keys.length) return;
    load();
    // Seed defaults
    keys.forEach(function (k) {
      if (values[k.key] === undefined && k.default !== undefined) values[k.key] = k.default;
    });
    if (!btn) buildButton();
    applyAll();
    window.addEventListener('html-doc:rendered', applyAll);
  }

  return { init: init, get: get, set: set, applyAll: applyAll };
})();
// Standalone builds inline the page but not the glossary; in that mode
// we render the term inline without a tooltip rather than mark every
// term as "unknown". Detected via the inline page-data script.
var __htmldocStandalone = function () {
  return !!document.getElementById('__htmldoc_page__');
};

class GlossaryTerm extends HTMLElement {
  connectedCallback() {
    var self = this;
    this.setAttribute('data-html-doc-tooltip-trigger', '');
    this.classList.add('html-doc-gloss');
    __htmldocKit.whenReady().then(function () {
      var term = self.getAttribute('term') || self.textContent;
      var opts = { in: self.getAttribute('in') || undefined, lang: self.getAttribute('lang') || undefined };
      var r = __htmldocKit.resolveGlossary(term, opts);
      if (r) {
        self.setAttribute('data-def', r.hit.def || '');
        if (r.hit.link) self.setAttribute('data-link', r.hit.link);
        if (r.lang !== (opts.lang || __htmldocKit.state().lang)) {
          self.setAttribute('data-lang-shown', 'lang: ' + r.lang);
        }
        __htmldocTooltip.attach(self);
      } else if (__htmldocStandalone()) {
        // Standalone mode without inline glossary data — render text only.
        self.classList.remove('html-doc-gloss');
      } else {
        self.setAttribute('data-def', '<em>Unknown term:</em> ' + term);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'unknown-glossary-term', msg: 'No entry for "' + term + '"', level: 'warn' }]
        }));
        __htmldocTooltip.attach(self);
      }
    });
  }
}
if (!customElements.get('glossary-term')) customElements.define('glossary-term', GlossaryTerm);

/* ============ <ext-ref> Custom Element — Citation card ============ *
 * Per the design audit ("bold move"): treat every external reference as a
 * first-class citation card rather than a footnote-grade link. The element
 * inherits the tooltip-controller hover/click affordance but renders a
 * richer body: type-themed icon (paper / rfc / release / blog / other),
 * source-domain pill, optional author+date row, summary, "View canonical"
 * footer. The 4 source-type themes give visual context at a glance.
 *
 * Data shape (extrefs/<domain>.json entries):
 *   { name, summary, link, type?, author?, published? }
 * Inline overrides on the element take precedence:
 *   <ext-ref name="..." type="paper" author="..." published="2024">
 * --------------------------------------------------------------------- */

var __htmldocCiteIcons = {
  paper:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  rfc:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/></svg>',
  release: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
  blog:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>',
  other:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
};

function __htmldocCiteDomain(link) {
  if (!link) return '';
  try {
    var u = new URL(link, window.location.href);
    return u.hostname.replace(/^www\./, '');
  } catch (e) { return ''; }
}

function __htmldocCiteType(hit, element) {
  var type = (element.getAttribute('type') || hit.type || '').toLowerCase();
  if (__htmldocCiteIcons[type]) return type;
  // Infer from the link domain if not declared.
  var dom = __htmldocCiteDomain(hit.link || '');
  if (/arxiv|doi\.org|acm\.org|springer|sciencedirect|nature\.com|ieee/.test(dom)) return 'paper';
  if (/datatracker\.ietf|w3\.org|rfc-editor|tc39|whatwg/.test(dom))               return 'rfc';
  if (/github\.com\/.+\/releases|releases\.|changelog/.test((hit.link || '')))    return 'release';
  if (/blog|medium\.com|substack|dev\.to/.test(dom))                              return 'blog';
  return 'other';
}

function __htmldocBuildCitationBody(hit, name, element) {
  var type = __htmldocCiteType(hit, element);
  var icon = __htmldocCiteIcons[type] || __htmldocCiteIcons.other;
  var domain = __htmldocCiteDomain(hit.link || '');
  var author = element.getAttribute('author') || hit.author || hit.authors || '';
  var published = element.getAttribute('published') || hit.published || hit.date || '';

  var html = '<div class="hdt-cite" data-cite-type="' + type + '">';
  html +=   '<div class="hdt-cite-head">';
  html +=     '<span class="hdt-cite-icon">' + icon + '</span>';
  html +=     '<span class="hdt-cite-title">' + escapeXml(hit.name || name) + '</span>';
  html +=   '</div>';
  if (domain) html += '<div class="hdt-cite-domain">' + escapeXml(domain) + '</div>';
  if (author || published) {
    html += '<div class="hdt-cite-meta">';
    if (author)    html += '<span class="hdt-cite-author">' + escapeXml(author) + '</span>';
    if (published) html += '<span class="hdt-cite-date">' + escapeXml(published) + '</span>';
    html += '</div>';
  }
  if (hit.summary) html += '<div class="hdt-cite-summary">' + hit.summary + '</div>';
  html += '</div>';
  return html;
}

class ExtRef extends HTMLElement {
  connectedCallback() {
    var self = this;
    this.setAttribute('data-html-doc-tooltip-trigger', '');
    this.classList.add('html-doc-extref');
    __htmldocKit.whenReady().then(function () {
      var name = self.getAttribute('name') || self.textContent;
      var opts = { in: self.getAttribute('in') || undefined, lang: self.getAttribute('lang') || undefined };
      var r = __htmldocKit.resolveExtRef(name, opts);
      if (r) {
        self.setAttribute('data-def', __htmldocBuildCitationBody(r.hit, name, self));
        // Tag the element itself with the resolved type so authors can
        // theme the inline cite-text (different underline per type).
        var type = __htmldocCiteType(r.hit, self);
        self.setAttribute('data-cite-type', type);
        if (r.hit.link) self.setAttribute('data-link', r.hit.link);
        __htmldocTooltip.attach(self);
      } else if (__htmldocStandalone()) {
        self.classList.remove('html-doc-extref');
      } else {
        self.setAttribute('data-def', '<em>Unknown reference:</em> ' + name);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'unknown-ext-ref', msg: 'No entry for "' + name + '"', level: 'warn' }]
        }));
        __htmldocTooltip.attach(self);
      }
    });
  }
}
if (!customElements.get('ext-ref')) customElements.define('ext-ref', ExtRef);
// "<cite>" alias — same behavior as <ext-ref> so authors can use the
// semantically-correct HTML element when citing.
if (!customElements.get('html-doc-cite')) customElements.define('html-doc-cite', class extends ExtRef {});

/* ============ <html-doc-chart> Custom Element ============ *
 * Generic data-driven SVG chart. Scatter and line types.
 * Series data lives in a child <script type="application/json">.
 * For row-per-item horizontal bars, use the bar-chart block instead
 * (handled directly by the renderer for layout-stability reasons).
 * --------------------------------------------------------------- */
class HtmlDocChart extends HTMLElement {
  connectedCallback() {
    var dataNode = this.querySelector('script[type="application/json"]');
    var series = [];
    if (dataNode) {
      try { series = JSON.parse(dataNode.textContent || '[]'); } catch (e) { series = []; }
    }
    this._series  = series;
    this._type    = this.getAttribute('type') || 'scatter';
    this._title   = this.getAttribute('title') || '';
    this._xLabel  = this.getAttribute('x-label') || '';
    this._yLabel  = this.getAttribute('y-label') || '';
    this._xScale  = (this.getAttribute('x-scale') || 'linear').toLowerCase();
    this._yScale  = (this.getAttribute('y-scale') || 'linear').toLowerCase();

    this.innerHTML = '';
    if (dataNode) this.appendChild(dataNode);

    var allPoints = [];
    series.forEach(function (s) { (s.data || []).forEach(function (p) { allPoints.push(p); }); });
    if (allPoints.length === 0) {
      this.appendChild(document.createTextNode(''));
      return;
    }
    var xs = allPoints.map(function (p) { return p.x; });
    var ys = allPoints.map(function (p) { return p.y; });
    var xMin = Math.min.apply(null, xs), xMax = Math.max.apply(null, xs);
    var yMin = Math.min.apply(null, ys), yMax = Math.max.apply(null, ys);
    if (xMin === xMax) { xMin -= 1; xMax += 1; }
    if (yMin === yMax) { yMin -= 1; yMax += 1; }
    var xPad = (xMax - xMin) * 0.05;
    var yPad = (yMax - yMin) * 0.05;
    if (this._xScale !== 'log') { xMin -= xPad; xMax += xPad; }
    if (this._yScale !== 'log') { yMin -= yPad; yMax += yPad; }
    // Log scale requires positive values; clamp lower bound.
    if (this._xScale === 'log' && xMin <= 0) xMin = Math.max(1e-6, xs.filter(function (v) { return v > 0; })[0] || 1e-6);
    if (this._yScale === 'log' && yMin <= 0) yMin = Math.max(1e-6, ys.filter(function (v) { return v > 0; })[0] || 1e-6);

    this._W = 640; this._H = 360;
    this._pad = { top: this._title ? 32 : 16, right: 24, bottom: this._xLabel ? 50 : 32, left: this._yLabel ? 56 : 40 };
    this._plotW = this._W - this._pad.left - this._pad.right;
    this._plotH = this._H - this._pad.top  - this._pad.bottom;

    this._origView = { xMin: xMin, xMax: xMax, yMin: yMin, yMax: yMax };
    this._view = Object.assign({}, this._origView);

    this._render();
    this._attachToolbar();
    this._attachPanZoom();
  }

  _render() {
    var self = this;
    var v = this._view;
    var pad = this._pad, plotW = this._plotW, plotH = this._plotH;
    var W = this._W, H = this._H;
    var xLog = this._xScale === 'log', yLog = this._yScale === 'log';

    function sx(x) {
      if (xLog) {
        if (x <= 0) x = v.xMin;
        return pad.left + (Math.log(x / v.xMin) / Math.log(v.xMax / v.xMin)) * plotW;
      }
      return pad.left + ((x - v.xMin) / (v.xMax - v.xMin)) * plotW;
    }
    function sy(y) {
      if (yLog) {
        if (y <= 0) y = v.yMin;
        return pad.top + plotH - (Math.log(y / v.yMin) / Math.log(v.yMax / v.yMin)) * plotH;
      }
      return pad.top + plotH - ((y - v.yMin) / (v.yMax - v.yMin)) * plotH;
    }
    // Cache the inverse mappings for the pan/zoom logic.
    this._sx = sx; this._sy = sy;

    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };

    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + (this._title || (this._type + ' chart')) + '" class="hdc-svg">');
    // Clip rect so the plot doesn't bleed into the chrome when zoomed.
    parts.push('<defs><clipPath id="hdc-clip"><rect x="' + pad.left + '" y="' + pad.top + '" width="' + plotW + '" height="' + plotH + '"/></clipPath></defs>');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="hdc-title">' + escapeXml(this._title) + '</text>');
    // Axes
    parts.push('<line x1="' + pad.left + '" y1="' + (pad.top + plotH) + '" x2="' + (W - pad.right) + '" y2="' + (pad.top + plotH) + '" class="hdc-axis"/>');
    parts.push('<line x1="' + pad.left + '" y1="' + pad.top + '" x2="' + pad.left + '" y2="' + (pad.top + plotH) + '" class="hdc-axis"/>');
    if (this._xLabel) parts.push('<text x="' + (pad.left + plotW / 2) + '" y="' + (H - 14) + '" text-anchor="middle" class="hdc-axis-label">' + escapeXml(this._xLabel) + (xLog ? ' (log)' : '') + '</text>');
    if (this._yLabel) parts.push('<text x="' + 14 + '" y="' + (pad.top + plotH / 2) + '" text-anchor="middle" class="hdc-axis-label" transform="rotate(-90 14,' + (pad.top + plotH / 2) + ')">' + escapeXml(this._yLabel) + (yLog ? ' (log)' : '') + '</text>');
    // Ticks — log uses powers; linear uses 5 evenly-spaced.
    function logTicks(min, max) {
      var ticks = [];
      var lo = Math.floor(Math.log10(min));
      var hi = Math.ceil(Math.log10(max));
      for (var p = lo; p <= hi; p++) {
        var v = Math.pow(10, p);
        if (v >= min && v <= max) ticks.push(v);
      }
      // Add interior 2 / 5 / 10 multiples if the range is short.
      if (ticks.length < 4) {
        ticks = [];
        for (var p2 = lo; p2 <= hi; p2++) {
          [1, 2, 5].forEach(function (m) {
            var v = m * Math.pow(10, p2);
            if (v >= min && v <= max) ticks.push(v);
          });
        }
      }
      return ticks;
    }
    var xTicks = xLog ? logTicks(v.xMin, v.xMax) :
      (function () { var r = []; for (var i = 0; i <= 4; i++) r.push(v.xMin + (i / 4) * (v.xMax - v.xMin)); return r; })();
    var yTicks = yLog ? logTicks(v.yMin, v.yMax) :
      (function () { var r = []; for (var i = 0; i <= 4; i++) r.push(v.yMin + (i / 4) * (v.yMax - v.yMin)); return r; })();
    xTicks.forEach(function (val) {
      var pos = sx(val);
      parts.push('<line x1="' + pos + '" y1="' + (pad.top + plotH) + '" x2="' + pos + '" y2="' + (pad.top + plotH + 4) + '" class="hdc-axis"/>');
      parts.push('<text x="' + pos + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="hdc-tick">' + fmtNum(val) + '</text>');
    });
    yTicks.forEach(function (val) {
      var pos = sy(val);
      parts.push('<line x1="' + (pad.left - 4) + '" y1="' + pos + '" x2="' + pad.left + '" y2="' + pos + '" class="hdc-axis"/>');
      parts.push('<text x="' + (pad.left - 6) + '" y="' + (pos + 4) + '" text-anchor="end" class="hdc-tick">' + fmtNum(val) + '</text>');
    });

    // Plot region (clipped). All series + their dots / labels live here so
    // points that scroll past the axes don't leak.
    parts.push('<g clip-path="url(#hdc-clip)">');
    var plotMidX = pad.left + plotW / 2;
    this._series.forEach(function (s, i) {
      var color = palette[s.color] || palette.accent;
      parts.push('<g class="hdc-series" data-series-idx="' + i + '">');
      if (self._type === 'line') {
        var d = (s.data || []).map(function (p, idx) {
          return (idx === 0 ? 'M ' : 'L ') + sx(p.x) + ' ' + sy(p.y);
        }).join(' ');
        parts.push('<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2" class="hdc-line"/>');
      }
      (s.data || []).forEach(function (p, j) {
        var key = i + '-' + j;
        var dotLabel = escapeXml(String(p.label != null ? p.label : ''));
        var seriesLbl = escapeXml(String(s.label != null ? s.label : ''));
        var px = sx(p.x), py = sy(p.y);
        parts.push(
          '<circle cx="' + px + '" cy="' + py + '" r="4" fill="' + color +
          '" class="hdc-dot"' +
          ' data-point-key="' + key + '" data-x="' + p.x + '" data-y="' + p.y +
          '" data-point-label="' + dotLabel + '" data-series-label="' + seriesLbl + '"' +
          ' tabindex="0" role="img" aria-label="' +
            (seriesLbl ? seriesLbl + ': ' : '') + (dotLabel ? dotLabel + ' ' : '') +
            '(' + fmtNum(p.x) + ', ' + fmtNum(p.y) + ')' +
          '"/>'
        );
        if (p.label) {
          var goRight = px < plotMidX;
          var lx = goRight ? (px + 8) : (px - 8);
          var anchor = goRight ? 'start' : 'end';
          parts.push(
            '<text x="' + lx + '" y="' + (py + 4) +
            '" text-anchor="' + anchor + '"' +
            ' class="hdc-point-label" data-point-key="' + key + '" tabindex="0">' +
            escapeXml(p.label) + '</text>'
          );
        }
      });
      parts.push('</g>');
    });
    parts.push('</g>'); // /clip
    // Legend chips sit OUTSIDE the clip so they're always visible.
    this._series.forEach(function (s, i) {
      var color = palette[s.color] || palette.accent;
      if (!s.label) return;
      var lx = W - pad.right - 12;
      var ly = pad.top + 14 + i * 18;
      parts.push(
        '<g class="hdc-legend-chip" data-series-idx="' + i + '" tabindex="0" role="button" ' +
        'aria-label="Toggle ' + escapeXml(s.label) + ' series">' +
          '<rect x="' + (lx - 116) + '" y="' + (ly - 12) + '" width="120" height="20" rx="4" class="hdc-legend-bg"/>' +
          '<rect x="' + (lx - 110) + '" y="' + (ly - 9) + '" width="14" height="14" rx="2" fill="' + color + '" class="hdc-legend-swatch"/>' +
          '<text x="' + (lx - 92) + '" y="' + (ly + 2) + '" class="hdc-legend">' + escapeXml(s.label) + '</text>' +
        '</g>'
      );
    });
    parts.push('</svg>');

    var oldSvg = this.querySelector(':scope > .hdc-svg');
    if (oldSvg) oldSvg.remove();
    this.insertAdjacentHTML('beforeend', parts.join(''));
    this._wireInteractivity();
    // SVG must be in the DOM before getBBox() reports anything sane.
    // Defer to next frame so layout has a chance to settle.
    var self = this;
    requestAnimationFrame(function () { self._deconflictLabels(); });
  }

  /* Push overlapping point labels onto staggered y-offsets so they don't
     read as a single garbled run. If a label still has nowhere to go
     (too many neighbors), hide it — the existing dot-hover sync brings
     it back via the `.hovered` reveal rule in CSS. */
  _deconflictLabels() {
    var svg = this.querySelector(':scope > .hdc-svg');
    if (!svg) return;
    var labels = Array.prototype.slice.call(svg.querySelectorAll('.hdc-point-label'));
    if (labels.length < 2) return;
    // Reset any prior adjustments (re-render path: zoom/pan).
    labels.forEach(function (l) {
      l.classList.remove('hdc-label-hidden', 'hdc-label-shifted');
      if (l.dataset.origY) l.setAttribute('y', l.dataset.origY);
      else l.dataset.origY = l.getAttribute('y');
    });
    var boxes = [];
    for (var i = 0; i < labels.length; i++) {
      var bb;
      try { bb = labels[i].getBBox(); } catch (e) { continue; }
      if (!bb || !bb.width) continue;
      boxes.push({
        el: labels[i],
        x1: bb.x, x2: bb.x + bb.width,
        y1: bb.y, y2: bb.y + bb.height,
        h: bb.height,
      });
    }
    if (boxes.length < 2) return;
    boxes.sort(function (a, b) { return a.x1 - b.x1; });
    var lineH = boxes[0].h + 3;
    // Treat labels within GAP_PX of each other as crowded — pure bbox
    // overlap underestimates how cramped the chart reads, because two
    // labels separated by a few pixels still look like one run.
    // 16px ≈ one em at our 11px label font, which is the smallest
    // separation a reader reliably parses as two labels rather than one.
    var GAP_PX = 16;
    function clash(a, b) {
      return !(a.x2 + GAP_PX < b.x1 || b.x2 + GAP_PX < a.x1
            || a.y2 + 1 < b.y1 || b.y2 + 1 < a.y1);
    }
    var offsets = [0, -lineH, lineH, -2 * lineH, 2 * lineH];
    var placed = [];
    boxes.forEach(function (box) {
      var found = null;
      for (var k = 0; k < offsets.length; k++) {
        var oy = offsets[k];
        var cand = { x1: box.x1, x2: box.x2, y1: box.y1 + oy, y2: box.y2 + oy };
        var hit = false;
        for (var p = 0; p < placed.length; p++) {
          if (clash(placed[p], cand)) { hit = true; break; }
        }
        if (!hit) { found = oy; break; }
      }
      if (found !== null) {
        if (found !== 0) {
          var oy0 = parseFloat(box.el.dataset.origY) || parseFloat(box.el.getAttribute('y')) || 0;
          box.el.setAttribute('y', oy0 + found);
          box.el.classList.add('hdc-label-shifted');
        }
        placed.push({ x1: box.x1, x2: box.x2, y1: box.y1 + found, y2: box.y2 + found });
      } else {
        // Too crowded — hide. The existing dot-hover sync (.hovered)
        // reveals it on demand via the CSS reveal rule.
        box.el.classList.add('hdc-label-hidden');
      }
    });
  }

  _attachToolbar() {
    var self = this;
    var chartTitle = self._title || (self._type + '-chart');
    __htmldocVisualTools.makeToolbar(this, [
      {
        title: 'Reset zoom',
        icon: ICON_RESET,
        run: function (btn) { self.resetView(); __htmldocVisualTools.flash(btn, 'ok', ICON_RESET); }
      },
      {
        title: 'Copy data (TSV)',
        icon: ICON_CLIPBOARD,
        run: function (btn) {
          // Emit one TSV row per data point. Series label first so a
          // multi-series chart is still a single table; spreadsheet
          // tools (Google Sheets, Numbers, Excel) all import TSV
          // directly from clipboard.
          var lines = ['series\tx\ty\tlabel'];
          (self._series || []).forEach(function (s) {
            var sLabel = s.label != null ? String(s.label) : '';
            (s.data || []).forEach(function (p) {
              var pLabel = p.label != null ? String(p.label).replace(/[\t\n\r]+/g, ' ') : '';
              lines.push(sLabel + '\t' + p.x + '\t' + p.y + '\t' + pLabel);
            });
          });
          __htmldocVisualTools.copyText(btn, lines.join('\n'), ICON_CLIPBOARD);
        }
      },
      {
        title: 'Download as PNG',
        icon: ICON_CAMERA,
        run: function (btn) {
          var svg = self.querySelector('.hdc-svg');
          __htmldocVisualTools.svgToPng(svg, chartTitle)
            .then(function () { __htmldocVisualTools.flash(btn, 'ok', ICON_CAMERA); })
            .catch(function () { __htmldocVisualTools.flash(btn, 'fail', ICON_CAMERA); });
        }
      },
      {
        title: 'Expand to fullscreen',
        icon: ICON_EXPAND,
        run: function () {
          var svg = self.querySelector('.hdc-svg');
          if (!svg || !window.__htmldocLightbox) return;
          var copy = svg.cloneNode(true);
          // The cloned SVG has the chart's intrinsic dimensions; let the
          // lightbox CSS scale it via max-width/max-height + viewBox so
          // it fills the modal without overflowing.
          copy.removeAttribute('width');
          copy.removeAttribute('height');
          copy.style.width = '100%';
          copy.style.height = 'auto';
          __htmldocLightbox.open(copy, { title: chartTitle });
        }
      }
    ]);
  }

  resetView() {
    this._view = Object.assign({}, this._origView);
    this._render();
  }

  _attachPanZoom() {
    var self = this;
    var drag = null;
    var pinch = null;

    function getSvg() { return self.querySelector(':scope > .hdc-svg'); }

    // Map a clientX/Y to data coordinates via SVG viewBox.
    function dataAtPointer(clientX, clientY) {
      var svg = getSvg();
      if (!svg) return null;
      var rect = svg.getBoundingClientRect();
      var sxPos = ((clientX - rect.left) / rect.width)  * self._W;
      var syPos = ((clientY - rect.top)  / rect.height) * self._H;
      var pad = self._pad, plotW = self._plotW, plotH = self._plotH, v = self._view;
      // Clamp to plot area
      sxPos = Math.max(pad.left, Math.min(pad.left + plotW, sxPos));
      syPos = Math.max(pad.top,  Math.min(pad.top  + plotH, syPos));
      var xLog = self._xScale === 'log', yLog = self._yScale === 'log';
      var dx, dy;
      if (xLog) {
        var fx = (sxPos - pad.left) / plotW;
        dx = v.xMin * Math.pow(v.xMax / v.xMin, fx);
      } else {
        dx = v.xMin + ((sxPos - pad.left) / plotW) * (v.xMax - v.xMin);
      }
      if (yLog) {
        var fy = (pad.top + plotH - syPos) / plotH;
        dy = v.yMin * Math.pow(v.yMax / v.yMin, fy);
      } else {
        dy = v.yMin + ((pad.top + plotH - syPos) / plotH) * (v.yMax - v.yMin);
      }
      return { dx: dx, dy: dy };
    }

    function zoomAround(pt, factor) {
      if (!pt) return;
      var v = self._view;
      var xLog = self._xScale === 'log', yLog = self._yScale === 'log';
      if (xLog) {
        v.xMin = Math.exp(Math.log(pt.dx) - (Math.log(pt.dx) - Math.log(v.xMin)) * factor);
        v.xMax = Math.exp(Math.log(pt.dx) + (Math.log(v.xMax) - Math.log(pt.dx)) * factor);
      } else {
        v.xMin = pt.dx - (pt.dx - v.xMin) * factor;
        v.xMax = pt.dx + (v.xMax - pt.dx) * factor;
      }
      if (yLog) {
        v.yMin = Math.exp(Math.log(pt.dy) - (Math.log(pt.dy) - Math.log(v.yMin)) * factor);
        v.yMax = Math.exp(Math.log(pt.dy) + (Math.log(v.yMax) - Math.log(pt.dy)) * factor);
      } else {
        v.yMin = pt.dy - (pt.dy - v.yMin) * factor;
        v.yMax = pt.dy + (v.yMax - pt.dy) * factor;
      }
      self._render();
    }

    // Wheel zoom — preventDefault to stop page scroll over the chart.
    this.addEventListener('wheel', function (e) {
      if (e.target.closest('.hdt-bar, .hdc-legend-chip')) return;
      e.preventDefault();
      var factor = e.deltaY > 0 ? 1.12 : (1 / 1.12);
      zoomAround(dataAtPointer(e.clientX, e.clientY), factor);
    }, { passive: false });

    // Drag pan.
    this.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      if (e.target.closest('.hdt-bar, .hdc-legend-chip, .hdc-dot, .hdc-point-label')) return;
      var svg = getSvg(); if (!svg) return;
      drag = {
        startClientX: e.clientX,
        startClientY: e.clientY,
        startView: Object.assign({}, self._view),
        rect: svg.getBoundingClientRect(),
      };
      svg.style.cursor = 'grabbing';
      e.preventDefault();
    });
    function onMove(e) {
      if (!drag) return;
      var dxPx = e.clientX - drag.startClientX;
      var dyPx = e.clientY - drag.startClientY;
      var v0 = drag.startView, v = self._view;
      var xLog = self._xScale === 'log', yLog = self._yScale === 'log';
      // Convert pixel delta to data delta using the original view range.
      if (xLog) {
        var fx = -dxPx / drag.rect.width;
        var rx = Math.pow(v0.xMax / v0.xMin, fx);
        v.xMin = v0.xMin * rx; v.xMax = v0.xMax * rx;
      } else {
        var dxData = (dxPx / drag.rect.width) * (v0.xMax - v0.xMin);
        v.xMin = v0.xMin - dxData; v.xMax = v0.xMax - dxData;
      }
      if (yLog) {
        var fy = dyPx / drag.rect.height;
        var ry = Math.pow(v0.yMax / v0.yMin, fy);
        v.yMin = v0.yMin * ry; v.yMax = v0.yMax * ry;
      } else {
        var dyData = (dyPx / drag.rect.height) * (v0.yMax - v0.yMin);
        v.yMin = v0.yMin + dyData; v.yMax = v0.yMax + dyData;
      }
      self._render();
    }
    function onUp() {
      if (drag) {
        drag = null;
        var svg = getSvg();
        if (svg) svg.style.cursor = 'grab';
      }
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup',   onUp);

    // Touch — single finger pan, two finger pinch zoom.
    this.addEventListener('touchstart', function (e) {
      var svg = getSvg(); if (!svg) return;
      if (e.touches.length === 1) {
        drag = {
          startClientX: e.touches[0].clientX,
          startClientY: e.touches[0].clientY,
          startView: Object.assign({}, self._view),
          rect: svg.getBoundingClientRect(),
        };
      } else if (e.touches.length === 2) {
        var t1 = e.touches[0], t2 = e.touches[1];
        var midX = (t1.clientX + t2.clientX) / 2;
        var midY = (t1.clientY + t2.clientY) / 2;
        var dx = t1.clientX - t2.clientX, dy = t1.clientY - t2.clientY;
        pinch = {
          startDist: Math.sqrt(dx * dx + dy * dy),
          mid: { clientX: midX, clientY: midY },
          startView: Object.assign({}, self._view),
        };
        drag = null;
      }
    }, { passive: true });
    this.addEventListener('touchmove', function (e) {
      if (pinch && e.touches.length === 2) {
        var t1 = e.touches[0], t2 = e.touches[1];
        var dx = t1.clientX - t2.clientX, dy = t1.clientY - t2.clientY;
        var dist = Math.sqrt(dx * dx + dy * dy);
        var factor = pinch.startDist / dist;
        self._view = Object.assign({}, pinch.startView);
        zoomAround(dataAtPointer(pinch.mid.clientX, pinch.mid.clientY), factor);
        e.preventDefault();
      } else if (drag && e.touches.length === 1) {
        onMove(e.touches[0]);
        e.preventDefault();
      }
    }, { passive: false });
    this.addEventListener('touchend', function () { drag = null; pinch = null; });

    // Double-click resets.
    this.addEventListener('dblclick', function (e) {
      if (e.target.closest('.hdt-bar, .hdc-legend-chip')) return;
      self.resetView();
    });

    var svg = getSvg();
    if (svg) svg.style.cursor = 'grab';
  }

  _wireInteractivity() {
    var self = this;

    /* Hover tooltip — one shared element per chart, lazily created. */
    function ensureTip() {
      var t = self.querySelector(':scope > .hdc-tooltip');
      if (t) return t;
      t = document.createElement('div');
      t.className = 'hdc-tooltip';
      t.setAttribute('role', 'tooltip');
      t.setAttribute('aria-hidden', 'true');
      self.appendChild(t);
      return t;
    }
    function showTip(dot) {
      var tip = ensureTip();
      var seriesLbl = dot.getAttribute('data-series-label') || '';
      var pointLbl  = dot.getAttribute('data-point-label')  || '';
      var x = dot.getAttribute('data-x');
      var y = dot.getAttribute('data-y');
      var html = '';
      if (seriesLbl) html += '<div class="hdc-tt-series">' + escapeXml(seriesLbl) + '</div>';
      if (pointLbl)  html += '<div class="hdc-tt-label">'  + escapeXml(pointLbl)  + '</div>';
      html += '<div class="hdc-tt-coords">(' + fmtNum(parseFloat(x)) + ', ' + fmtNum(parseFloat(y)) + ')</div>';
      tip.innerHTML = html;
      tip.setAttribute('aria-hidden', 'false');
      var hostRect = self.getBoundingClientRect();
      var dotRect  = dot.getBoundingClientRect();
      var left = (dotRect.left - hostRect.left) + dotRect.width / 2;
      var top  = (dotRect.top  - hostRect.top)  - 8;
      tip.style.left = left + 'px';
      tip.style.top  = top  + 'px';
      tip.classList.add('visible');
    }
    function hideTip() {
      var tip = self.querySelector(':scope > .hdc-tooltip');
      if (tip) { tip.classList.remove('visible'); tip.setAttribute('aria-hidden', 'true'); }
    }
    /* Bidirectional hover/focus: a dot and its inline label share a
       data-point-key. Either being hovered or focused adds .hovered to
       both, so the user can hover the label and see the dot react (and
       vice versa) — a small detail signaling we take UX seriously. */
    function setHover(key, on) {
      if (!key) return;
      self.querySelectorAll('[data-point-key="' + key + '"]').forEach(function (el) {
        el.classList.toggle('hovered', on);
      });
    }
    this.querySelectorAll('.hdc-dot').forEach(function (dot) {
      var key = dot.getAttribute('data-point-key');
      dot.addEventListener('mouseenter', function () { setHover(key, true);  showTip(dot); });
      dot.addEventListener('mouseleave', function () { setHover(key, false); hideTip();   });
      dot.addEventListener('focus',      function () { setHover(key, true);  showTip(dot); });
      dot.addEventListener('blur',       function () { setHover(key, false); hideTip();   });
    });
    this.querySelectorAll('.hdc-point-label').forEach(function (label) {
      var key = label.getAttribute('data-point-key');
      label.addEventListener('mouseenter', function () {
        setHover(key, true);
        var dot = self.querySelector('.hdc-dot[data-point-key="' + key + '"]');
        if (dot) showTip(dot);
      });
      label.addEventListener('mouseleave', function () { setHover(key, false); hideTip(); });
      label.addEventListener('focus', function () {
        setHover(key, true);
        var dot = self.querySelector('.hdc-dot[data-point-key="' + key + '"]');
        if (dot) showTip(dot);
      });
      label.addEventListener('blur', function () { setHover(key, false); hideTip(); });
    });

    /* Legend chip — click or Enter/Space toggles `.dim` on the matching
       <g class="hdc-series"> so the user can mute series visually. */
    function toggleSeries(chip) {
      var idx = chip.getAttribute('data-series-idx');
      var series = self.querySelector('.hdc-series[data-series-idx="' + idx + '"]');
      if (!series) return;
      var on = series.classList.toggle('dim');
      chip.classList.toggle('off', on);
      chip.setAttribute('aria-pressed', on ? 'true' : 'false');
    }
    this.querySelectorAll('.hdc-legend-chip').forEach(function (chip) {
      chip.setAttribute('aria-pressed', 'false');
      chip.addEventListener('click', function () { toggleSeries(chip); });
      chip.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggleSeries(chip);
        }
      });
    });
  }
}
if (!customElements.get('html-doc-chart')) customElements.define('html-doc-chart', HtmlDocChart);

function escapeXml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function fmtNum(n) {
  if (n === undefined || n === null) return '';
  var abs = Math.abs(n);
  if (abs >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
  if (abs >= 10) return n.toFixed(0);
  if (abs >= 1) return n.toFixed(1).replace(/\.0$/, '');
  return n.toFixed(2);
}

/* ============ Visual-tools toolbar (diagrams + charts) ============ *
 * Shared helpers for icon-only Copy / Screenshot buttons on charts and
 * diagrams. Toolbar reveals on hover/focus-within; buttons flash green
 * (success) or red (failure) for 1.5s.
 * -------------------------------------------------------------------- */
var __htmldocVisualTools = (function () {
  function flash(btn, kind, restoreIcon) {
    var icon = kind === 'ok' ? ICON_CHECK : ICON_CROSS;
    var cls  = kind === 'ok' ? 'flash-ok' : 'flash-fail';
    btn.innerHTML = icon;
    btn.classList.add(cls);
    setTimeout(function () {
      btn.classList.remove(cls);
      btn.innerHTML = restoreIcon;
    }, 1500);
  }

  function copyText(btn, text, restoreIcon) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text)
      .then(function () { flash(btn, 'ok', restoreIcon); })
      .catch(function () { flash(btn, 'fail', restoreIcon); });
  }

  function slugifyFilename(s) {
    return String(s || 'diagram')
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 60) || 'diagram';
  }

  /* Render an SVG element to PNG and trigger a download.
     CSS variables don't survive serialization (they resolve against
     the document, not the cloned SVG), so we inline currentColor and
     a fixed --bg fallback. 2× DPR for crisp output. */
  function svgToPng(svgEl, filename) {
    if (!svgEl) { return Promise.reject(new Error('no svg')); }
    return new Promise(function (resolve, reject) {
      try {
        var bbox = svgEl.getBoundingClientRect();
        var w = bbox.width || (svgEl.viewBox && svgEl.viewBox.baseVal && svgEl.viewBox.baseVal.width)  || 800;
        var h = bbox.height || (svgEl.viewBox && svgEl.viewBox.baseVal && svgEl.viewBox.baseVal.height) || 600;

        // Clone so we don't mutate the live diagram.
        var clone = svgEl.cloneNode(true);
        if (!clone.getAttribute('xmlns')) {
          clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        }
        if (!clone.getAttribute('width'))  clone.setAttribute('width',  w);
        if (!clone.getAttribute('height')) clone.setAttribute('height', h);
        // Inline computed CSS so var(--token) usages resolve through the
        // browser before serialization.
        inlineComputedStyles(svgEl, clone);

        var xml = new XMLSerializer().serializeToString(clone);
        var bg  = getComputedStyle(document.body).backgroundColor || '#ffffff';
        var blob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var img = new Image();
        img.onload = function () {
          var scale = Math.max(window.devicePixelRatio || 1, 2);
          var canvas = document.createElement('canvas');
          canvas.width  = Math.round(w * scale);
          canvas.height = Math.round(h * scale);
          var ctx = canvas.getContext('2d');
          ctx.fillStyle = bg;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.setTransform(scale, 0, 0, scale, 0, 0);
          ctx.drawImage(img, 0, 0, w, h);
          URL.revokeObjectURL(url);
          canvas.toBlob(function (pngBlob) {
            if (!pngBlob) { reject(new Error('toBlob failed')); return; }
            var a = document.createElement('a');
            a.href = URL.createObjectURL(pngBlob);
            a.download = slugifyFilename(filename) + '.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(function () { URL.revokeObjectURL(a.href); }, 100);
            resolve();
          }, 'image/png');
        };
        img.onerror = function (e) { URL.revokeObjectURL(url); reject(e); };
        img.src = url;
      } catch (e) { reject(e); }
    });
  }

  /* Inline computed styles from a live element tree onto a clone so
     CSS-variable-driven colors survive serialization. Walks both trees
     in lockstep. Property list kept short; pulling all of getComputedStyle
     bloats the SVG and slows large diagrams. */
  var STYLE_PROPS = ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'font-family', 'font-size', 'font-weight', 'text-anchor', 'color', 'opacity'];
  function inlineComputedStyles(live, clone) {
    if (!live || !clone) return;
    if (live.nodeType === 1 && clone.nodeType === 1) {
      var cs = getComputedStyle(live);
      var s = '';
      for (var i = 0; i < STYLE_PROPS.length; i++) {
        var v = cs.getPropertyValue(STYLE_PROPS[i]);
        if (v && v !== 'normal' && v !== 'none' && v !== '') {
          s += STYLE_PROPS[i] + ':' + v + ';';
        }
      }
      if (s) {
        var existing = clone.getAttribute('style') || '';
        clone.setAttribute('style', s + existing);
      }
    }
    var lc = live.children, cc = clone.children;
    if (!lc || !cc) return;
    for (var j = 0; j < lc.length && j < cc.length; j++) {
      inlineComputedStyles(lc[j], cc[j]);
    }
  }

  function makeToolbar(host, actions) {
    if (!host) return null;
    var existing = host.querySelector(':scope > .hdt-bar');
    if (existing) existing.remove();
    host.classList.add('hdt-host');
    var bar = document.createElement('div');
    bar.className = 'hdt-bar';
    actions.forEach(function (a) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.title = a.title;
      btn.setAttribute('aria-label', a.title);
      btn.innerHTML = a.icon;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        try { a.run(btn); }
        catch (err) { flash(btn, 'fail', a.icon); }
      });
      bar.appendChild(btn);
    });
    host.appendChild(bar);
    return bar;
  }

  return { makeToolbar: makeToolbar, copyText: copyText, svgToPng: svgToPng, flash: flash };
})();

/* ============ Prism syntax highlighter (lazy CDN) ============ *
 * Loads Prism.js + autoloader on first call. Autoloader fetches
 * per-language components on demand, so this page-level script
 * stays small and Prism only pays for languages the page actually
 * uses. Tokens themed via chrome.css custom properties — no second
 * Prism theme stylesheet needed.
 * --------------------------------------------------------------- */
var __prismLoader = (function () {
  var loadPromise = null;
  var VERSION = '1.29.0';
  var CDN = 'https://cdn.jsdelivr.net/npm/prismjs@' + VERSION + '/';

  function ensureScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.crossOrigin = 'anonymous';
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error('failed to load ' + src)); };
      document.head.appendChild(s);
    });
  }

  function load() {
    if (loadPromise) return loadPromise;
    // Set the manual flag BEFORE prism.min.js runs so Prism doesn't
    // auto-highlight on DOMContentLoaded — we control the timing.
    window.Prism = window.Prism || {};
    window.Prism.manual = true;

    loadPromise = ensureScript(CDN + 'prism.min.js')
      .then(function () {
        return ensureScript(CDN + 'plugins/autoloader/prism-autoloader.min.js');
      })
      .then(function () {
        if (window.Prism && window.Prism.plugins && window.Prism.plugins.autoloader) {
          window.Prism.plugins.autoloader.languages_path = CDN + 'components/';
        }
        // Register the per-element post-process exactly once. The
        // autoloader replaces innerHTML asynchronously per block as
        // its language module arrives — wrapping in a .then() after
        // highlightAll() is racy. The `complete` hook fires after each
        // element's final highlight pass, which is the safe handoff.
        if (window.Prism && window.Prism.hooks && typeof _hdtAfterPrismHighlight === 'function') {
          window.Prism.hooks.add('complete', function (env) {
            _hdtAfterPrismHighlight(env);
          });
        }
        return window.Prism;
      });
    return loadPromise;
  }

  function highlightAll(root) {
    // Skip if no language-tagged blocks exist on the page — saves the
    // CDN round-trip for plain-text-only pages.
    var ctx = root || document;
    var blocks = ctx.querySelectorAll('code[class*="language-"]');
    if (!blocks.length) return Promise.resolve();
    return load().then(function (Prism) {
      if (Prism && typeof Prism.highlightAllUnder === 'function') {
        Prism.highlightAllUnder(ctx);
      } else if (Prism && typeof Prism.highlightAll === 'function') {
        Prism.highlightAll();
      }
    }).catch(function (e) {
      window.dispatchEvent(new CustomEvent('html-doc:warnings', {
        detail: [{ code: 'prism-load-failed', msg: 'Could not load Prism: ' + (e.message || e), level: 'info' }]
      }));
    });
  }
  return { load: load, highlightAll: highlightAll };
})();

/* ============ <html-doc-diagram> — Mermaid (lazy-loaded) ============ */
var __mermaidLoader = (function () {
  var loadPromise = null;
  // SUPPLY-CHAIN NOTE: this loads Mermaid from a CDN at runtime. The
  // @10 pin allows any 10.x update from jsDelivr — acceptable for a
  // personal tool, exposed for any hosted deployment. For strict
  // integrity, pin to a fully-qualified version and add an integrity
  // attribute. Procedure:
  //   1. Pick a version, e.g. mermaid@10.9.4
  //   2. Visit https://www.srihash.org/ — paste the jsDelivr URL,
  //      copy the sha384 hash
  //   3. Replace script.src below with the pinned URL
  //   4. Set script.integrity = 'sha384-...' (from step 2)
  //   5. Set script.crossOrigin = 'anonymous'  (required for SRI to work)

  /* Build the Mermaid initialize() payload from the page's resolved CSS
     tokens. Using `theme: 'base'` gives us full control over node /
     edge / actor colors so flowcharts and sequence diagrams pick up
     the page's accent + surface palette in both light and dark modes.
     Mermaid requires concrete hex/rgb values, not CSS var() refs, so
     we resolve via getComputedStyle. */
  function token(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }
  function buildConfig() {
    var accent       = token('--accent',         '#0f766e');
    var accentSoft   = token('--accent-soft',    '#ccfbf1');
    var accentStrong = token('--accent-strong',  '#115e59');
    var text         = token('--text',           '#1f1d2c');
    var textSoft     = token('--text-soft',      '#605d80');
    var textFaint    = token('--text-faint',     '#8b8aa0');
    var surface      = token('--surface',        '#ffffff');
    var surface2     = token('--surface-2',      '#f5f3ff');
    var border       = token('--border',         '#e6e2ef');
    var bg           = token('--bg',             '#fafaf9');
    return {
      startOnLoad: false,
      theme: 'base',
      fontFamily: 'Inter, -apple-system, sans-serif',
      themeVariables: {
        // Flowchart / generic
        background:       bg,
        primaryColor:     accentSoft,
        primaryTextColor: text,
        primaryBorderColor: accent,
        secondaryColor:   surface2,
        secondaryTextColor: text,
        secondaryBorderColor: border,
        tertiaryColor:    surface,
        tertiaryTextColor: text,
        tertiaryBorderColor: border,
        mainBkg:          surface,
        nodeBorder:       accent,
        clusterBkg:       surface2,
        clusterBorder:    border,
        lineColor:        textSoft,
        textColor:        text,
        titleColor:       text,
        edgeLabelBackground: bg,
        // Sequence
        actorBkg:         surface,
        actorBorder:      accent,
        actorTextColor:   text,
        actorLineColor:   textFaint,
        signalColor:      text,
        signalTextColor:  text,
        labelBoxBkgColor: accentSoft,
        labelBoxBorderColor: accent,
        labelTextColor:   accentStrong,
        loopTextColor:    text,
        noteBkgColor:     accentSoft,
        noteBorderColor:  accent,
        noteTextColor:    accentStrong,
        activationBkgColor: accentSoft,
        activationBorderColor: accent,
        sequenceNumberColor: bg,
        // State / class
        stateBkg:         surface,
        stateBorder:      accent,
        altBackground:    surface2,
        compositeBackground: surface2,
        compositeBorder:  border,
        compositeTitleBackground: bg,
        innerEndBackground: textSoft,
        // Gantt
        gridColor:        border,
        sectionBkgColor:  surface2,
        sectionBkgColor2: surface,
        taskBkgColor:     accentSoft,
        taskTextColor:    text,
        taskTextDarkColor: text,
        taskTextLightColor: text,
        taskTextOutsideColor: text,
        taskTextClickableColor: accentStrong,
        activeTaskBkgColor: accent,
        activeTaskBorderColor: accentStrong,
        doneTaskBkgColor: surface,
        doneTaskBorderColor: textFaint,
        critBkgColor:     '#fee2e2',
        critBorderColor:  '#dc2626',
      },
    };
  }
  function load() {
    if (loadPromise) return loadPromise;
    loadPromise = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
      script.async = true;
      // To enable SRI: set script.integrity = 'sha384-...';
      //                set script.crossOrigin = 'anonymous';
      script.onload = function () {
        try {
          window.mermaid.initialize(buildConfig());
          resolve(window.mermaid);
        } catch (e) { reject(e); }
      };
      script.onerror = function () { reject(new Error('Mermaid CDN load failed')); };
      document.head.appendChild(script);
    });
    return loadPromise;
  }
  // Re-initialize Mermaid on theme toggle so diagrams pick up dark/light tokens.
  function reset() {
    if (!loadPromise || !window.mermaid) return;
    window.mermaid.initialize(buildConfig());
  }
  return { load: load, reset: reset };
})();

class HtmlDocDiagram extends HTMLElement {
  connectedCallback() {
    var srcNode = this.querySelector('script[type="text/x-mermaid"]');
    var src = srcNode ? srcNode.textContent.trim() : '';
    var caption = this.getAttribute('caption') || '';
    this.classList.add('hdd-wrap');
    // Two stacked views: rendered SVG and the raw Mermaid source. The
    // toolbar's first button toggles between them. Source is wrapped
    // in a language-mermaid <code> so the existing Prism + line-number
    // pipeline picks it up.
    this.innerHTML =
      '<div class="hdd-render" aria-label="Diagram loading">Rendering…</div>' +
      '<pre class="hdd-source" hidden><code class="language-mermaid">' + escapeXml(src) + '</code></pre>' +
      (caption ? '<figcaption class="hdd-caption">' + escapeXml(caption) + '</figcaption>' : '');
    var renderHost = this.querySelector('.hdd-render');
    var self = this;
    this._src = src;
    __mermaidLoader.load()
      .then(function (mermaid) {
        var id = 'hdd-' + Math.random().toString(36).slice(2, 9);
        return mermaid.render(id, src).then(function (out) {
          renderHost.innerHTML = out.svg;
          self._rendered = true;
          self._attachToolbar();
        });
      })
      .catch(function (err) {
        renderHost.innerHTML = '<pre class="hdd-fallback">' + escapeXml(src) + '</pre>';
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'mermaid-render-failed', msg: String(err.message || err), level: 'warn' }]
        }));
      });
  }
  _attachToolbar() {
    var self = this;
    var caption = this.getAttribute('caption') || 'diagram';
    __htmldocVisualTools.makeToolbar(this, [
      {
        title: 'Toggle source / render',
        icon: ICON_BRACES,
        run: function (btn) {
          var showSource = !self.classList.contains('hdd-source-mode');
          self.classList.toggle('hdd-source-mode', showSource);
          var src = self.querySelector(':scope > .hdd-source');
          var ren = self.querySelector(':scope > .hdd-render');
          if (src) src.hidden = !showSource;
          if (ren) ren.hidden = showSource;
          btn.setAttribute('aria-pressed', showSource ? 'true' : 'false');
          btn.title = showSource ? 'Show rendered diagram' : 'Show diagram source';
        }
      },
      {
        title: 'Copy diagram source',
        icon: ICON_CLIPBOARD,
        run: function (btn) {
          __htmldocVisualTools.copyText(btn, self._src || '', ICON_CLIPBOARD);
        }
      },
      {
        title: 'Download as PNG',
        icon: ICON_CAMERA,
        run: function (btn) {
          var svg = self.querySelector('.hdd-render svg');
          __htmldocVisualTools.svgToPng(svg, caption || 'diagram')
            .then(function () { __htmldocVisualTools.flash(btn, 'ok', ICON_CAMERA); })
            .catch(function () { __htmldocVisualTools.flash(btn, 'fail', ICON_CAMERA); });
        }
      },
      {
        title: 'Expand to fullscreen',
        icon: ICON_EXPAND,
        run: function () {
          var svg = self.querySelector('.hdd-render svg');
          if (!svg || !window.__htmldocLightbox) return;
          var copy = svg.cloneNode(true);
          copy.removeAttribute('width');
          copy.removeAttribute('height');
          copy.style.width = '100%';
          copy.style.height = 'auto';
          __htmldocLightbox.open(copy, { title: caption || 'Diagram' });
        }
      }
    ]);
  }
  rerender() {
    if (!this._src) return;
    var renderHost = this.querySelector('.hdd-render');
    var self = this;
    __mermaidLoader.reset();
    __mermaidLoader.load().then(function (mermaid) {
      var id = 'hdd-' + Math.random().toString(36).slice(2, 9);
      return mermaid.render(id, self._src).then(function (out) {
        renderHost.innerHTML = out.svg;
        self._attachToolbar();
      });
    }).catch(function () { /* swallow */ });
  }
}
if (!customElements.get('html-doc-diagram')) customElements.define('html-doc-diagram', HtmlDocDiagram);

// Re-render every diagram on theme toggle so colors track the theme.
window.addEventListener('html-doc:theme-changed', function () {
  document.querySelectorAll('html-doc-diagram').forEach(function (d) {
    if (typeof d.rerender === 'function') d.rerender();
  });
});

/* ============ <html-doc-annotated-code> — MkDocs-Material-style annotations ============ *
 * Code block with numbered `(1)`, `(2)` markers that map to a side panel
 * of annotations. Hovering a marker brightens its annotation and vice
 * versa. Sources:
 *   - <script type="text/x-code"> code body (preserves whitespace, no escaping)
 *   - <script type="application/json"> [{ id: 1, content: "..." }, ...]
 *     OR a child <ol class="hdc-anno-source"> with one <li> per annotation
 *       (li index = id, content = li.innerHTML).
 * Renders into:
 *   <pre><code class="language-{lang}">...with .hdc-anno-marker chips...</code></pre>
 *   <ol class="hdc-anno-list">...<li class="hdc-anno-item">...</li></ol>
 * Prism highlights the code first; the marker replacement walks the
 * highlighted text-nodes so `(1)` chips survive syntax coloring.
 * --------------------------------------------------------------------- */
class HtmlDocAnnotatedCode extends HTMLElement {
  connectedCallback() {
    var srcNode = this.querySelector('script[type="text/x-code"]');
    var jsonNode = this.querySelector('script[type="application/json"]');
    var code = srcNode ? srcNode.textContent.replace(/^\n/, '') : (this.textContent || '');
    var annos = [];
    if (jsonNode) {
      try { annos = JSON.parse(jsonNode.textContent || '[]'); } catch (e) { annos = []; }
    } else {
      var ol = this.querySelector('ol.hdc-anno-source, ol.hdc-anno-list');
      if (ol) {
        annos = Array.prototype.map.call(ol.querySelectorAll(':scope > li'), function (li, i) {
          return { id: i + 1, content: li.innerHTML };
        });
      }
    }
    var lang = this.getAttribute('language') || this.getAttribute('lang') || '';

    this.innerHTML = '';
    this.classList.add('hdc-anno-wrap');

    var pre = document.createElement('pre');
    var codeEl = document.createElement('code');
    if (lang) codeEl.className = 'language-' + lang;
    codeEl.textContent = code;
    pre.appendChild(codeEl);
    this.appendChild(pre);

    if (annos.length) {
      var list = document.createElement('ol');
      list.className = 'hdc-anno-list';
      annos.forEach(function (a) {
        var li = document.createElement('li');
        li.className = 'hdc-anno-item';
        li.setAttribute('data-anno-id', String(a.id));
        li.setAttribute('tabindex', '0');
        var num = document.createElement('span');
        num.className = 'hdc-anno-num';
        num.textContent = String(a.id);
        var body = document.createElement('div');
        body.className = 'hdc-anno-body';
        body.innerHTML = a.content || '';
        li.appendChild(num);
        li.appendChild(body);
        list.appendChild(li);
      });
      this.appendChild(list);
    }

    var self = this;
    var validIds = annos.reduce(function (acc, a) { acc[String(a.id)] = true; return acc; }, {});

    function injectMarkers() {
      var c = self.querySelector('pre code');
      if (!c) return;
      var pattern = /\((\d+)\)/g;
      var textNodes = [];
      var walker = document.createTreeWalker(c, NodeFilter.SHOW_TEXT, null);
      var n;
      while ((n = walker.nextNode())) textNodes.push(n);
      textNodes.forEach(function (textNode) {
        var text = textNode.nodeValue;
        if (text.indexOf('(') === -1) return;
        pattern.lastIndex = 0;
        var hasMatch = false;
        var test;
        while ((test = pattern.exec(text)) !== null) {
          if (validIds[test[1]]) { hasMatch = true; break; }
        }
        if (!hasMatch) return;
        pattern.lastIndex = 0;
        var frag = document.createDocumentFragment();
        var last = 0;
        var m;
        while ((m = pattern.exec(text)) !== null) {
          if (!validIds[m[1]]) continue;
          if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
          var btn = document.createElement('button');
          btn.className = 'hdc-anno-marker';
          btn.type = 'button';
          btn.setAttribute('data-anno-id', m[1]);
          btn.setAttribute('aria-label', 'Annotation ' + m[1]);
          btn.textContent = m[1];
          frag.appendChild(btn);
          last = m.index + m[0].length;
        }
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        textNode.parentNode.replaceChild(frag, textNode);
      });
      bindSync();
    }

    function bindSync() {
      function setHover(id, on) {
        self.querySelectorAll('[data-anno-id="' + id + '"]').forEach(function (el) {
          el.classList.toggle('hovered', on);
        });
      }
      self.querySelectorAll('.hdc-anno-marker, .hdc-anno-item').forEach(function (el) {
        var id = el.getAttribute('data-anno-id');
        el.addEventListener('mouseenter', function () { setHover(id, true); });
        el.addEventListener('mouseleave', function () { setHover(id, false); });
        el.addEventListener('focus',      function () { setHover(id, true); });
        el.addEventListener('blur',       function () { setHover(id, false); });
        el.addEventListener('click', function () {
          var partner = el.classList.contains('hdc-anno-marker')
            ? self.querySelector('.hdc-anno-item[data-anno-id="' + id + '"]')
            : self.querySelector('.hdc-anno-marker[data-anno-id="' + id + '"]');
          if (partner) partner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
      });
    }

    /* Build the per-line annotation slot: each .hdt-code-line gets an
       extra cell that lives in its OWN grid column (not overlapping
       line numbers). Empty by default; populated by moveMarkersToSlots
       when an annotation marker for this line exists. */
    function prepareLineSlots() {
      var c = self.querySelector('pre code');
      if (!c) return;
      if (!c.querySelector(':scope > .hdt-code-line')) {
        _hdtWrapCodeLines(c);
      }
      var lines = c.querySelectorAll(':scope > .hdt-code-line');
      lines.forEach(function (line) {
        if (line.querySelector(':scope > .hdc-anno-line-marker')) return;
        var slot = document.createElement('span');
        slot.className = 'hdc-anno-line-marker';
        slot.setAttribute('aria-hidden', 'true');
        // Insert BEFORE the line-number cell so the annotation column
        // is the leftmost gutter cell. The CSS override (below) widens
        // .hdt-code-line's grid-template-columns to add a 4th column.
        line.insertBefore(slot, line.firstChild);
      });
      self.classList.add('hdc-anno-gutter-on');
    }

    /* After markers are injected inline (within the now per-line spans),
       MOVE each marker into its line's annotation slot AND attach a
       hover-tooltip carrying the annotation body so the reader can
       preview the explanation without scanning the list below. */
    function moveMarkersToSlots() {
      var inline = self.querySelectorAll('pre code .hdc-anno-marker');
      Array.prototype.forEach.call(inline, function (btn) {
        var line = btn.closest('.hdt-code-line');
        if (!line) return;
        var slot = line.querySelector(':scope > .hdc-anno-line-marker');
        if (!slot) return;
        if (btn.parentElement !== slot) slot.appendChild(btn);
        // Tooltip carrying the annotation body. Pull from the matching
        // list item's body so authored HTML survives.
        if (!slot.querySelector(':scope > .hdc-anno-tip')) {
          var id = btn.getAttribute('data-anno-id');
          var match = self.querySelector('.hdc-anno-item[data-anno-id="' + id + '"] .hdc-anno-body');
          if (match) {
            var tip = document.createElement('span');
            tip.className = 'hdc-anno-tip';
            tip.setAttribute('role', 'tooltip');
            tip.innerHTML = match.innerHTML;
            slot.appendChild(tip);
          }
        }
      });
    }

    /* Order matters: WRAP lines first, THEN inject markers + move into
       slots. The previous order (inject → wrap → move) lost button
       handlers because _hdtWrapCodeLines clones-then-clears the code's
       children; the new buttons in the wrapped lines would be cloneless
       copies with no listeners. */
    function buildMarkers() {
      prepareLineSlots();
      injectMarkers();        // walks text nodes inside per-line spans
      moveMarkersToSlots();
    }
    if (lang && typeof __prismLoader !== 'undefined') {
      __prismLoader.highlightAll(this).then(function () { setTimeout(buildMarkers, 0); });
    } else {
      buildMarkers();
    }
  }
}
if (!customElements.get('html-doc-annotated-code')) customElements.define('html-doc-annotated-code', HtmlDocAnnotatedCode);

/* ============ <html-doc-snippet> — editable HTML/CSS/JS playground ============ */
class HtmlDocSnippet extends HTMLElement {
  connectedCallback() {
    var srcNode = this.querySelector('script[type="text/plain"]');
    var source = srcNode ? srcNode.textContent : '';
    // Trim a single leading newline if present (common in JSON-encoded multi-line strings)
    source = source.replace(/^\n/, '');
    var label = this.getAttribute('label') || 'Editable code · live preview';
    var language = this.getAttribute('language') || 'html-css-js';
    // Prism token: html-css-js → markup (handles <style>/<script> embedded).
    var prismLang = language === 'html-css-js' ? 'markup' : language;

    this.classList.add('hds-wrap');
    this.innerHTML =
      '<div class="hds-header">' +
        '<span class="hds-label">' + escapeXml(label) + '</span>' +
        '<button type="button" class="hds-reset" aria-label="Reset to original">Reset</button>' +
      '</div>' +
      '<div class="hds-body">' +
        '<div class="hds-editor-wrap">' +
          '<pre class="hds-editor-shadow" aria-hidden="true"><code class="language-' + prismLang + '"></code></pre>' +
          '<textarea class="hds-editor" spellcheck="false" autocomplete="off" autocorrect="off" autocapitalize="off" aria-label="Code"></textarea>' +
        '</div>' +
        '<iframe class="hds-preview" sandbox="allow-scripts" aria-label="Preview"></iframe>' +
      '</div>';
    var editor = this.querySelector('.hds-editor');
    var shadow = this.querySelector('.hds-editor-shadow');
    var shadowCode = shadow.querySelector('code');
    var preview = this.querySelector('.hds-preview');
    var reset = this.querySelector('.hds-reset');
    var original = source;
    editor.value = source;

    function syncShadow() {
      // Trailing newline + space so the cursor at the end of the last
      // line has something to align over (otherwise Prism collapses).
      var t = editor.value;
      if (t.endsWith('\n')) t += ' ';
      shadowCode.textContent = t;
      if (typeof __prismLoader !== 'undefined') {
        __prismLoader.load().then(function () {
          if (window.Prism && typeof window.Prism.highlightElement === 'function') {
            window.Prism.highlightElement(shadowCode);
          }
        });
      }
    }
    function syncScroll() {
      shadow.scrollTop = editor.scrollTop;
      shadow.scrollLeft = editor.scrollLeft;
    }

    var t = null;
    function render() {
      preview.srcdoc = editor.value;
    }
    editor.addEventListener('input', function () {
      syncShadow();
      syncScroll();
      if (t) clearTimeout(t);
      t = setTimeout(render, 220);
    });
    editor.addEventListener('scroll', syncScroll);
    // Resizing the textarea changes the wrap height; re-sync padding.
    if (window.ResizeObserver) {
      new ResizeObserver(syncScroll).observe(editor);
    }
    reset.addEventListener('click', function () {
      editor.value = original;
      syncShadow();
      syncScroll();
      render();
    });
    syncShadow();
    render();
  }
}
if (!customElements.get('html-doc-snippet')) customElements.define('html-doc-snippet', HtmlDocSnippet);

/* ============ <page-nav> Custom Element ============ *
 * Loads site-manifest.json from the docs root and renders a collapsible
 * tree of pages. Active page highlighted from location.pathname. The
 * panel sits in the single left sidebar; the top-left ctrl-btn handles
 * sidebar collapse via the body.sidebar-collapsed class.
 *
 * If a <page-toc> sibling exists in the same .layout, page-nav adopts
 * it as its own child so both panels become one stacked flex column.
 * That keeps the layout grid simple (2 columns, single row), avoids
 * the row-span ordering gymnastics, and lets the whole sidebar share
 * one scroll context.
 * ----------------------------------------------------------------- */
class PageNav extends HTMLElement {
  connectedCallback() {
    var title = this.getAttribute('title') || 'Pages';
    this.innerHTML =
      '<div class="page-nav-panel">' +
        '<div class="page-nav-header"><h2>' + title + '</h2></div>' +
        '<ol class="page-nav-tree"><li class="page-nav-loading">Loading…</li></ol>' +
      '</div>';
    var self = this;
    // Adopt the page-toc into the sidebar so both panels share a single
    // column without DOM gymnastics. Deferred so the page-toc can finish
    // its own connectedCallback (renders its inner DOM).
    //
    // Prefer a page-toc inside the same .layout (the documented authoring
    // shape), but fall back to a document-level search so the kit stays
    // robust when an author drops page-toc outside .layout (e.g. as a
    // direct body child) — without this fallback that page-toc would
    // render at the page bottom, breaking the single-left-sidebar rule.
    var layout = this.closest('.layout');
    var adopt = function () {
      var siblingToc = null;
      if (layout) {
        siblingToc = layout.querySelector(':scope > page-toc, :scope > nav.toc');
      }
      if (!siblingToc) {
        siblingToc = document.querySelector('page-toc, nav.toc');
      }
      if (siblingToc && siblingToc.parentElement !== self) self.appendChild(siblingToc);
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', adopt);
    } else {
      Promise.resolve().then(adopt);
    }
    // Click-anywhere-on-the-rail to expand when collapsed. The whole
    // page-nav becomes the click target; the top-left chrome button
    // still toggles too. position: relative on the host so the ::after
    // chevron can absolute-position inside it.
    this.style.position = this.style.position || 'sticky';
    this.addEventListener('click', function (e) {
      if (!document.body.classList.contains('sidebar-collapsed')) return;
      // Avoid swallowing clicks on inner content (won't be reachable
      // anyway since visibility: hidden, but defensive).
      if (e.target && e.target.closest('a, button, input, select')) return;
      if (typeof toggleTOC === 'function') toggleTOC();
    });
    // Close mobile drawer on Esc
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') self.classList.remove('open');
    });

    // Defer until the document is fully parsed so we can reliably detect
    // the standalone-build inline page-data script (which sits at the
    // end of body, after <page-nav>).
    function start() {
      if (document.getElementById('__htmldoc_page__')) {
        self.style.display = 'none';
        return;
      }
      loadManifest()
        .then(function (manifest) { self._renderTree(manifest); })
        .catch(function (e) {
          self._renderTree(null);
          window.dispatchEvent(new CustomEvent('html-doc:warnings', {
            detail: [{
              code: 'manifest-fetch-failed',
              msg: 'Could not load site-manifest.json' +
                   (e && e.__htmldocManifestStatus ? ' (HTTP ' + e.__htmldocManifestStatus + ')' : '') +
                   ' — run `html-doc build` to regenerate it.',
              level: 'warn'
            }]
          }));
        });
    }

    /* Three-stage manifest loader.
       1) standalone inline (window.__htmldocManifest pre-populated)
       2) fetch JSON over HTTP (fast happy path; works whenever the page
          is served by an HTTP server that allows same-origin GETs)
       3) script-tag <site-manifest.js> fallback for environments where
          fetch is blocked (file:// CORS) or refused (IntelliJ's built-in
          server returns 404 for token-less GETs). The .js companion is
          emitted next to the .json by build_manifest() in bin/html-doc. */
    function loadManifest() {
      if (window.__htmldocManifest) return Promise.resolve(window.__htmldocManifest);
      var wa = (window.__htmldocWithAuth || function (u) { return u; });
      var fileProto = (window.location && window.location.protocol === 'file:');
      var fetchAttempt = fileProto
        ? Promise.reject(new Error('file:// — skipping fetch'))
        : fetch(wa(__htmldocDocsRoot + 'site-manifest.json'), { cache: 'no-cache' })
            .then(function (r) {
              if (r.ok) return r.json();
              var err = new Error('manifest http ' + r.status);
              err.__htmldocManifestStatus = r.status;
              throw err;
            });
      return fetchAttempt.catch(function (fetchErr) {
        return loadManifestViaScript().catch(function () {
          // Surface the more informative original fetch error.
          throw fetchErr;
        });
      });
    }

    function loadManifestViaScript() {
      if (window.__htmldocManifest) return Promise.resolve(window.__htmldocManifest);
      var wa = (window.__htmldocWithAuth || function (u) { return u; });
      return new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = wa(__htmldocDocsRoot + 'site-manifest.js');
        s.async = true;
        s.onload = function () {
          if (window.__htmldocManifest) resolve(window.__htmldocManifest);
          else reject(new Error('site-manifest.js loaded but did not set window.__htmldocManifest'));
        };
        s.onerror = function () { reject(new Error('site-manifest.js not reachable')); };
        document.head.appendChild(s);
      });
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', start);
    } else {
      start();
    }
  }

  _renderTree(manifest) {
    var tree = this.querySelector('.page-nav-tree');
    if (!tree) return;
    tree.innerHTML = '';
    if (!manifest) {
      // Fetch failed — the catch handler in start() already dispatched a
      // specific warning. Just show inline placeholder.
      tree.innerHTML = '<li class="page-nav-empty">No site-manifest.json found. Run <code>html-doc build</code>.</li>';
      return;
    }
    if (!Array.isArray(manifest.pages)) {
      tree.innerHTML = '<li class="page-nav-empty">site-manifest.json is malformed (no <code>pages</code> array). Run <code>html-doc build</code>.</li>';
      window.dispatchEvent(new CustomEvent('html-doc:warnings', {
        detail: [{ code: 'manifest-malformed', msg: 'site-manifest.json missing pages[]', level: 'warn' }]
      }));
      return;
    }
    if (manifest.schema_version && manifest.schema_version > 1) {
      window.dispatchEvent(new CustomEvent('html-doc:warnings', {
        detail: [{ code: 'manifest-schema-future', msg: 'site-manifest.schema_version=' + manifest.schema_version + ' newer than this kit (1)', level: 'warn' }]
      }));
    }

    var pages = manifest.pages.slice();
    pages.sort(function (a, b) {
      var oa = a.order !== undefined ? a.order : 1000;
      var ob = b.order !== undefined ? b.order : 1000;
      if (oa !== ob) return oa - ob;
      return (a.title || a.path).localeCompare(b.title || b.path);
    });

    // Group by parent folder, build a folder→pages map.
    var byParent = {};
    pages.forEach(function (p) {
      var key = p.parent || '';
      if (!byParent[key]) byParent[key] = [];
      byParent[key].push(p);
    });

    var here = window.location.pathname;
    function isActive(page) {
      // page.path is project-relative (e.g., "iceberg.html"); the URL
      // path may include a longer prefix. Endswith catches the common case.
      return here.endsWith('/' + page.path);
    }

    function renderLevel(parentKey, depth) {
      var ol = document.createElement('ol');
      ol.className = 'page-nav-level depth-' + depth;
      var items = byParent[parentKey] || [];
      items.forEach(function (page) {
        var li = document.createElement('li');
        li.className = 'page-nav-item';
        var anchor = document.createElement('a');
        anchor.href = relativizeHref(here, page.path);
        anchor.textContent = page.title || page.path;
        if (page.summary) anchor.title = page.summary;
        if (isActive(page)) {
          li.classList.add('active');
          anchor.setAttribute('aria-current', 'page');
        }
        li.appendChild(anchor);
        // Children are pages whose parent is the path-without-extension OR a folder ancestor.
        // We treat sub-folders: build a key based on this page's folder if any pages declare it.
        var childFolder = page.path.replace(/\.[^/]+$/, '');
        if (byParent[childFolder] && byParent[childFolder].length) {
          li.appendChild(renderLevel(childFolder, depth + 1));
        }
        ol.appendChild(li);
      });
      // Folders that have no own page but have children
      Object.keys(byParent).forEach(function (folder) {
        if (folder === parentKey || folder === '' || folder.indexOf(parentKey === '' ? '' : parentKey + '/') !== 0) return;
        // Direct child folder of parentKey
        var rest = parentKey === '' ? folder : folder.slice(parentKey.length + 1);
        if (rest.indexOf('/') !== -1) return; // not a direct child
        // Skip if already rendered as a page above
        if (byParent[parentKey].some(function (p) { return p.path.replace(/\.[^/]+$/, '') === folder; })) return;
        var li = document.createElement('li');
        li.className = 'page-nav-item folder';
        var label = document.createElement('div');
        label.className = 'page-nav-folder';
        label.textContent = rest;
        li.appendChild(label);
        li.appendChild(renderLevel(folder, depth + 1));
        ol.appendChild(li);
      });
      return ol;
    }

    var root = renderLevel('', 0);
    tree.appendChild(root);
  }
}
if (!customElements.get('page-nav')) customElements.define('page-nav', PageNav);

function relativizeHref(fromUrl, toPath) {
  // fromUrl is location.pathname like /a/b/c.html; toPath is the manifest entry like "spark.html" or "storage/iceberg.html".
  // Compute relative href from the directory of fromUrl to toPath.
  var fromDir = fromUrl.replace(/[^/]*$/, ''); // ends in '/'
  // Strip leading slash from fromDir for relative computation.
  // Use URL constructor for correctness:
  try {
    var base = new URL(fromDir, window.location.origin);
    var target = new URL(toPath, base);
    // Compute relative from base.pathname to target.pathname
    var fromParts = base.pathname.split('/');
    var toParts = target.pathname.split('/');
    fromParts.pop(); // last is empty
    var i = 0;
    while (i < fromParts.length && i < toParts.length && fromParts[i] === toParts[i]) i++;
    var up = fromParts.length - i;
    var rest = toParts.slice(i).join('/');
    return (up > 0 ? '../'.repeat(up) : './') + rest;
  } catch (e) {
    return toPath;
  }
}

/* ============ Forward-compat warning indicator ============ *
 * One indicator regardless of error count. Sits in the top-right
 * system cluster. Click reveals a panel listing entries with code +
 * message. Per-session dismiss; reappears on next load if errors
 * persist.
 * ----------------------------------------------------------------- */
var __htmldocWarnings = (function () {
  var list = [];
  var dismissed = false;
  var btn = null;
  var panel = null;

  function ensureBtn() {
    if (btn) return btn;
    btn = document.createElement('button');
    btn.className = 'ctrl-btn warning-indicator';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'View warnings');
    btn.title = 'View warnings';
    btn.style.display = 'none';
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    document.body.appendChild(btn);
    btn.addEventListener('click', function () {
      if (panel && panel.parentNode) {
        panel.parentNode.removeChild(panel);
        panel = null;
      } else {
        renderPanel();
      }
    });
    return btn;
  }

  function renderPanel() {
    panel = document.createElement('div');
    panel.className = 'warning-panel';
    var html = '<header><strong>' + list.length + ' warning' + (list.length === 1 ? '' : 's') + '</strong>' +
               '<button type="button" class="warning-panel-dismiss" aria-label="Dismiss for this session">Dismiss</button></header>';
    html += '<ul>';
    list.forEach(function (w) {
      var levelClass = (w.level === 'error') ? 'level-error' : 'level-warn';
      html += '<li class="' + levelClass + '"><code>' + (w.code || 'warn') + '</code> ' + escapeHTML(w.msg || '') + '</li>';
    });
    html += '</ul>';
    panel.innerHTML = html;
    document.body.appendChild(panel);
    panel.querySelector('.warning-panel-dismiss').addEventListener('click', function () {
      dismissed = true;
      hide();
      if (panel && panel.parentNode) { panel.parentNode.removeChild(panel); panel = null; }
    });
  }

  function refresh() {
    if (dismissed || list.length === 0) {
      hide();
      return;
    }
    ensureBtn();
    btn.style.display = 'flex';
    btn.setAttribute('data-count', String(list.length));
  }

  function hide() {
    if (btn) btn.style.display = 'none';
    if (panel && panel.parentNode) { panel.parentNode.removeChild(panel); panel = null; }
  }

  function push(entries) {
    entries.forEach(function (w) { list.push(w); });
    refresh();
  }

  // Capture standard error channels too
  window.addEventListener('error', function (e) {
    push([{ code: 'window-error', msg: (e.message || 'unknown') + ' @ ' + (e.filename || '?') + ':' + (e.lineno || 0), level: 'error' }]);
  });
  window.addEventListener('unhandledrejection', function (e) {
    push([{ code: 'unhandled-rejection', msg: String((e && e.reason && e.reason.message) || e.reason || 'unknown'), level: 'error' }]);
  });

  return { push: push };
})();

window.addEventListener('html-doc:warnings', function (e) {
  if (e && e.detail) __htmldocWarnings.push(e.detail);
});

/* ============ Pagefind search ============ *
 * Search button in the top-right system cluster opens a modal with
 * an input + result list. Pagefind is loaded lazily on first invoke;
 * if the bundle is absent (e.g., dev mode without a build) the modal
 * shows a graceful message.
 * ----------------------------------------------------------------- */
var __htmldocSearch = (function () {
  var pagefindPromise = null;
  var modal = null;
  var btn = null;

  function loadPagefind() {
    if (pagefindPromise) return pagefindPromise;
    // Resolve pagefind relative to the kit. _kit/../pagefind covers both
    // the standalone-build layout (where pagefind sits next to the HTML)
    // and a custom override.
    // ES dynamic import needs a relative-resolved URL ('./...') or absolute.
    // Pagefind index lives at the docs root (next to kit.json + site-manifest.json).
    var candidates = [
      __htmldocDocsRoot + 'pagefind/pagefind.js',
      __htmldocDocsRoot + '_kit/pagefind/pagefind.js'
    ];
    pagefindPromise = candidates.reduce(function (acc, abs) {
      return acc.catch(function () {
        return import(/* @vite-ignore */ abs).then(function (mod) {
          if (mod && mod.search) return mod;
          throw new Error('pagefind module shape unexpected');
        });
      });
    }, Promise.reject(new Error('init')));
    return pagefindPromise;
  }

  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement('div');
    modal.className = 'search-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'Search');
    modal.innerHTML =
      '<div class="search-backdrop"></div>' +
      '<div class="search-panel">' +
        '<header class="search-header">' +
          '<input type="search" class="search-input" placeholder="Search the site…" aria-label="Search query" autocomplete="off">' +
          '<button type="button" class="search-close" aria-label="Close">Esc</button>' +
        '</header>' +
        '<div class="search-status"></div>' +
        '<ul class="search-results"></ul>' +
      '</div>';
    document.body.appendChild(modal);
    var input = modal.querySelector('.search-input');
    var status = modal.querySelector('.search-status');
    var resultsEl = modal.querySelector('.search-results');

    var t = null;
    input.addEventListener('input', function () {
      if (t) clearTimeout(t);
      var query = input.value.trim();
      if (!query) {
        resultsEl.innerHTML = '';
        status.textContent = '';
        return;
      }
      t = setTimeout(function () { runSearch(query, status, resultsEl); }, 180);
    });
    modal.querySelector('.search-backdrop').addEventListener('click', hide);
    modal.querySelector('.search-close').addEventListener('click', hide);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('open')) hide();
    });

    // Focus trap — keep Tab / Shift-Tab inside the panel while the modal
    // is open. Keyboard-only and screen-reader users otherwise tab into
    // the document behind the backdrop.
    modal.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab' || !modal.classList.contains('open')) return;
      var focusables = modal.querySelectorAll(
        'input, button, a[href], [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });

    return modal;
  }

  /* In-page fallback search: when the Pagefind index is missing (IDE-
     served dev pages, no `html-doc build` has run yet), scan the
     current page's headings + paragraph text for the query. Returns a
     small list of section-anchored matches so the reader can at least
     navigate the page they're on, instead of getting a dead-end "index
     not found" toast. */
  function _inPageSearch(query) {
    var q = String(query || '').trim().toLowerCase();
    if (!q) return [];
    var main = document.querySelector('#main-content') || document.body;
    var sections = main.querySelectorAll('section[id], h2[id], h3[id]');
    var hits = [];
    var seen = new Set();
    sections.forEach(function (sec) {
      var id = sec.id;
      if (!id || seen.has(id)) return;
      var heading = sec.tagName.toLowerCase().startsWith('h')
        ? sec
        : sec.querySelector(':scope > h2, :scope > h3');
      if (!heading) return;
      var headingText = (heading.textContent || '').replace(/\s+/g, ' ').trim();
      // Walk the section's text and look for matches.
      var scopeEl = sec.tagName.toLowerCase().startsWith('h')
        ? (function () {
            // Headings without a section wrapper — collect following
            // siblings until the next heading.
            var parts = [];
            var n = sec.nextElementSibling;
            while (n && !/^H[1-6]$/.test(n.tagName)) {
              parts.push(n.textContent || '');
              n = n.nextElementSibling;
            }
            return parts.join(' ');
          })()
        : (sec.textContent || '');
      var body = scopeEl.replace(/\s+/g, ' ').trim();
      var lc = body.toLowerCase();
      var pos = lc.indexOf(q);
      var headingMatch = headingText.toLowerCase().indexOf(q) >= 0;
      if (pos < 0 && !headingMatch) return;
      seen.add(id);
      var excerpt = body;
      if (pos >= 0) {
        var start = Math.max(0, pos - 40);
        var end = Math.min(body.length, pos + q.length + 80);
        excerpt = (start > 0 ? '… ' : '') + body.slice(start, end) + (end < body.length ? ' …' : '');
        // Wrap match in <mark>.
        var rePos = excerpt.toLowerCase().indexOf(q);
        if (rePos >= 0) {
          excerpt =
            escapeHTML(excerpt.slice(0, rePos)) +
            '<mark>' + escapeHTML(excerpt.slice(rePos, rePos + q.length)) + '</mark>' +
            escapeHTML(excerpt.slice(rePos + q.length));
        } else {
          excerpt = escapeHTML(excerpt);
        }
      } else {
        excerpt = escapeHTML(excerpt.slice(0, 120) + (body.length > 120 ? ' …' : ''));
      }
      hits.push({
        url: '#' + id,
        title: headingText || id,
        excerpt: excerpt,
      });
    });
    return hits.slice(0, 20);
  }

  function _renderHits(hits, resultsEl) {
    resultsEl.innerHTML = '';
    hits.forEach(function (d) {
      var li = document.createElement('li');
      li.className = 'search-result';
      var url = escapeHTML(d.url || '');
      var title = escapeHTML(d.title || (d.url || ''));
      var excerpt = d.excerpt || '';
      li.innerHTML =
        '<a href="' + url + '">' +
          '<div class="search-result-title">' + title + '</div>' +
          '<div class="search-result-excerpt">' + excerpt + '</div>' +
        '</a>';
      resultsEl.appendChild(li);
    });
  }

  function runSearch(query, status, resultsEl) {
    status.textContent = 'Searching…';
    resultsEl.innerHTML = '';
    loadPagefind()
      .then(function (pagefind) {
        return pagefind.search(query);
      })
      .then(function (search) {
        if (!search.results.length) {
          // Pagefind ran but found nothing. Fall back to in-page so
          // the reader at least sees same-page matches.
          var localHits = _inPageSearch(query);
          if (localHits.length) {
            status.textContent = 'On this page: ' + localHits.length + ' match' + (localHits.length === 1 ? '' : 'es');
            _renderHits(localHits, resultsEl);
            return;
          }
          status.textContent = 'No results.';
          return;
        }
        status.textContent = search.results.length + ' result' + (search.results.length === 1 ? '' : 's');
        // Resolve top 10 results' data
        return Promise.all(search.results.slice(0, 10).map(function (r) { return r.data(); }))
          .then(function (datas) {
            var hits = datas.map(function (d) {
              return {
                url: d.url || '',
                title: (d.meta && d.meta.title) ? d.meta.title : (d.url || ''),
                excerpt: d.excerpt || '',
              };
            });
            _renderHits(hits, resultsEl);
          });
      })
      .catch(function (err) {
        // Pagefind index missing (IDE-served, no build yet). Don't
        // dead-end the user — fall back to in-page search so they can
        // at least navigate the current document.
        var localHits = _inPageSearch(query);
        if (localHits.length) {
          status.innerHTML = 'On this page: <strong>' + localHits.length +
            '</strong> match' + (localHits.length === 1 ? '' : 'es') +
            ' &middot; <em>site index unavailable</em>';
          _renderHits(localHits, resultsEl);
          return;
        }
        var msg = String((err && err.message) || err);
        if (/pagefind|404|Not Found|fetch/i.test(msg)) {
          status.innerHTML = 'Site index unavailable and no matches on this page. ' +
            'Run <code>html-doc build</code> + view from <code>dist/site/</code> for full-site search.';
        } else {
          status.textContent = 'Search error: ' + msg;
        }
      });
  }

  var _focusBeforeOpen = null;
  function show() {
    _focusBeforeOpen = document.activeElement;
    var m = ensureModal();
    m.classList.add('open');
    var input = m.querySelector('.search-input');
    setTimeout(function () { input.focus(); }, 20);
  }
  function hide() {
    if (modal) modal.classList.remove('open');
    if (_focusBeforeOpen && typeof _focusBeforeOpen.focus === 'function') {
      _focusBeforeOpen.focus();
      _focusBeforeOpen = null;
    }
  }

  function addButton() {
    if (btn) return;
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ctrl-btn search-toggle';
    btn.setAttribute('aria-label', 'Search (Cmd/Ctrl+K)');
    btn.title = 'Search (⌘K)';
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>';
    document.body.appendChild(btn);
    btn.addEventListener('click', show);
  }

  document.addEventListener('keydown', function (e) {
    var k = (e.key || '').toLowerCase();
    if ((e.metaKey || e.ctrlKey) && k === 'k') {
      e.preventDefault();
      show();
    }
  });

  return { addButton: addButton, show: show };
})();

document.addEventListener('DOMContentLoaded', function () { __htmldocSearch.addButton(); });

/* ============ Rebuild TOC after JSON renderer completes ============ */
window.addEventListener('html-doc:rendered', function () {
  var tocList = document.querySelector('page-toc .toc-list');
  if (tocList) buildTOC(tocList);
  initReadingAids();
});
