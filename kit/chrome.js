/* oku · chrome.js
 * Web Components, theme cycler, TOC builder, scroll-spy, reading aids.
 * Loaded with defer; chrome-boot.js handles pre-paint state.
 */

/* ──────────────────────────────────────────────────────────────────
 * oku · chrome.js
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
 *     <oku-chart>                       ~756
 *     <oku-diagram> (Mermaid)           ~874
 *     <oku-snippet>                     ~971
 *     <page-nav>                            ~1013
 *     Forward-compat warning indicator      ~1187
 *     Pagefind search                       ~1275
 *     Event hookups (theme, render, warn)   ~1455
 *
 *   Conventions:
 *     - Custom Element classes:  class FooBar extends HTMLElement { ... }
 *     - Shared controllers:      var __okuFoo = (function () { ... })();
 *     - Public helpers:          plain top-level function
 *     - Internal helpers:        nested inside their controller IIFE
 * ────────────────────────────────────────────────────────────────── */

/* ============ Kit version ============ *
 * Surfaced in the sidebar footer (dimmed) so a reader can see at a
 * glance which build of oku rendered the page. Bump in lockstep
 * with pyproject.toml's [project] version. */
const KIT_VERSION = '0.2.0';

/* ============ SVG icon set ============ */
const ICON_MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>';
const ICON_SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/><line x1="4.5" y1="4.5" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.5" y2="19.5"/><line x1="4.5" y1="19.5" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.5" y2="4.5"/></svg>';
const ICON_MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
const ICON_SYSTEM = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>';
const ICON_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';
/* Three-segment width indicator. Outline boxes; CSS fills the active
   segment(s) based on body[data-content-width=...] so the icon doubles
   as a state readout: 1 box = narrow, 2 = wide, 3 = max. */
const ICON_WIDTH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect class="w-seg s1" x="3"    y="8" width="5" height="8" rx="1"/><rect class="w-seg s2" x="9.5"  y="8" width="5" height="8" rx="1"/><rect class="w-seg s3" x="16"   y="8" width="5" height="8" rx="1"/></svg>';
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
 * expand buttons. Open with __okuLightbox.open(content, { title })
 * where `content` is an Element or HTML string. Returns immediately;
 * the overlay traps focus until closed via Escape, the close button,
 * or backdrop click. Same affordance everywhere — one mental model.
 * ---------------------------------------------------------------- */
var __okuLightbox = (function () {
  var overlay = null;
  var lastFocus = null;
  var currentOpts = null;

  function build() {
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.className = 'okt-lightbox';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Expanded view');
    overlay.innerHTML =
      '<div class="okt-lightbox-backdrop"></div>' +
      '<div class="okt-lightbox-frame">' +
      '  <button type="button" class="okt-lightbox-close" aria-label="Close" title="Close (Esc)">' + ICON_CROSS + '</button>' +
      '  <div class="okt-lightbox-content" tabindex="-1"></div>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('.okt-lightbox-backdrop').addEventListener('click', close);
    overlay.querySelector('.okt-lightbox-close').addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (!overlay.classList.contains('open')) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); }
    });
    return overlay;
  }

  function open(content, opts) {
    var el = build();
    var holder = el.querySelector('.okt-lightbox-content');
    // Drain any leftover nodes from a previous open() that bypassed close()
    // (defensive — should not happen in normal flow).
    while (holder.firstChild) holder.removeChild(holder.firstChild);
    currentOpts = opts || {};
    // Pan/zoom wrapping — when caller asks for it, wrap the content
    // in a transformable stage with mouse / wheel / touch handlers
    // and a small inline toolbar (zoom in, zoom out, fit, 1:1). The
    // wrap is undone on close so the content returns to its origin
    // unmolested.
    if (currentOpts.panZoom !== false) {
      var stage = document.createElement('div');
      stage.className = 'okt-lightbox-pz';
      var inner = document.createElement('div');
      inner.className = 'okt-lightbox-pz-inner';
      if (content instanceof Node) inner.appendChild(content);
      else inner.innerHTML = String(content || '');
      stage.appendChild(inner);
      var toolbar = document.createElement('div');
      toolbar.className = 'okt-lightbox-pz-toolbar';
      toolbar.innerHTML =
        '<button type="button" data-pz="out"   title="Zoom out (-)"     aria-label="Zoom out">−</button>' +
        '<button type="button" data-pz="reset" title="Reset / fit (0)"  aria-label="Reset zoom">⤢</button>' +
        '<button type="button" data-pz="in"    title="Zoom in (+)"      aria-label="Zoom in">+</button>';
      stage.appendChild(toolbar);
      holder.appendChild(stage);
      __okuPanZoom.attach(stage, inner, toolbar);
    } else {
      if (content instanceof Node) holder.appendChild(content);
      else holder.innerHTML = String(content || '');
    }
    if (currentOpts.title) el.setAttribute('aria-label', currentOpts.title);
    lastFocus = document.activeElement;
    el.classList.add('open');
    document.documentElement.classList.add('okt-lightbox-open');
    setTimeout(function () { holder.focus(); }, 0);
  }

  function close() {
    if (!overlay) return;
    overlay.classList.remove('open');
    document.documentElement.classList.remove('okt-lightbox-open');
    var holder = overlay.querySelector('.okt-lightbox-content');
    // Unwrap pan/zoom stage so the caller's onClose sees the
    // original content node (and can return it to the page).
    var stage = holder && holder.querySelector(':scope > .okt-lightbox-pz');
    if (stage) {
      var inner = stage.querySelector('.okt-lightbox-pz-inner');
      if (inner) {
        while (inner.firstChild) holder.appendChild(inner.firstChild);
      }
      stage.remove();
    }
    // onClose runs BEFORE innerHTML clear so callers can move their own
    // nodes back into the page (e.g. table fullscreen). Anything still
    // in holder after the callback gets wiped.
    if (currentOpts && typeof currentOpts.onClose === 'function') {
      try { currentOpts.onClose(holder); } catch (e) {}
    }
    if (holder) holder.innerHTML = '';
    currentOpts = null;
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    lastFocus = null;
  }

  return { open: open, close: close };
})();

/* ============ Pan / zoom controller for the lightbox stage ============ *
 * Drag to pan. Wheel to zoom (anchored at the pointer so the content
 * under the cursor stays put). Pinch to zoom on touch. Double-click
 * resets. Buttons in the stage toolbar provide a discoverable path
 * for keyboard / mouse-only users. State lives on the stage so each
 * lightbox open() gets a fresh transform.
 * --------------------------------------------------------------------- */
var __okuPanZoom = (function () {
  function attach(stage, inner, toolbar) {
    var scale = 1, tx = 0, ty = 0;
    var min = 0.25, max = 12;
    // Picture-in-picture minimap — shows the inner content scaled
    // down with a viewport rect indicating the visible region of
    // the zoomed stage. Click-drag the rect to pan; the rest of
    // the minimap is non-interactive. Updates on every apply().
    var pip = document.createElement('div');
    pip.className = 'okt-lightbox-pip';
    pip.setAttribute('aria-hidden', 'true');
    var pipInner = document.createElement('div');
    pipInner.className = 'okt-lightbox-pip-inner';
    var pipViewport = document.createElement('div');
    pipViewport.className = 'okt-lightbox-pip-viewport';
    pip.appendChild(pipInner);
    pip.appendChild(pipViewport);
    stage.appendChild(pip);
    // Populate the minimap with a static clone of the inner SVG so
    // the reader sees a recognisable thumbnail (not just an empty
    // box). Deferred to the next frame so `inner` is already
    // populated by the caller. Cloning loses interactivity — that's
    // intentional; the live SVG is in the stage above.
    requestAnimationFrame(function () {
      var svg = inner.querySelector('svg');
      if (!svg) return;
      var copy = svg.cloneNode(true);
      copy.removeAttribute('width');
      copy.removeAttribute('height');
      copy.style.width = '100%';
      copy.style.height = '100%';
      copy.style.pointerEvents = 'none';
      pipInner.appendChild(copy);
    });
    function updatePip() {
      // The minimap only adds value when the content is zoomed in
      // enough that the viewport doesn't cover the whole stage.
      // Hide it at scale ≤ 1.1 so the chrome stays quiet during
      // normal reads.
      if (scale <= 1.1) { pip.classList.remove('visible'); return; }
      pip.classList.add('visible');
      var sRect = stage.getBoundingClientRect();
      if (!sRect.width || !sRect.height) return;
      // Inner's effective size after transform.
      var iw = sRect.width * scale;
      var ih = sRect.height * scale;
      // What fraction of the inner is currently visible inside the
      // stage's viewport? (Position = -tx, -ty in inner coords.)
      var vx = Math.max(0, Math.min(1, -tx / iw));
      var vy = Math.max(0, Math.min(1, -ty / ih));
      var vw = Math.max(0.05, Math.min(1, sRect.width / iw));
      var vh = Math.max(0.05, Math.min(1, sRect.height / ih));
      pipViewport.style.left   = (vx * 100) + '%';
      pipViewport.style.top    = (vy * 100) + '%';
      pipViewport.style.width  = (vw * 100) + '%';
      pipViewport.style.height = (vh * 100) + '%';
    }
    function apply() {
      inner.style.transform = 'translate(' + tx + 'px, ' + ty + 'px) scale(' + scale + ')';
      updatePip();
    }
    function zoomAt(cx, cy, factor) {
      var nextScale = Math.max(min, Math.min(max, scale * factor));
      var r = stage.getBoundingClientRect();
      var lx = cx - r.left;
      var ly = cy - r.top;
      // Anchor zoom so the point under the cursor stays under the cursor.
      tx = lx - (lx - tx) * (nextScale / scale);
      ty = ly - (ly - ty) * (nextScale / scale);
      scale = nextScale;
      apply();
    }
    function reset() { scale = 1; tx = 0; ty = 0; apply(); }
    // Wheel zoom — factor scales smoothly with deltaY so trackpad
    // and mouse-wheel both feel proportional. Earlier code used a
    // flat ×1.15 step per tick, which on a trackpad (many high-
    // frequency ticks) compounded to ×4-6 per gesture and made
    // precision impossible. Exponential mapping `exp(-deltaY *
    // 0.0025)` gives ~1.05 for a typical wheel notch and tiny
    // increments for trackpad scrolls.
    stage.addEventListener('wheel', function (ev) {
      ev.preventDefault();
      // Normalize deltaMode (lines vs pixels) to a pixel-ish quantity.
      var dy = ev.deltaY;
      if (ev.deltaMode === 1) dy *= 16; // line → px
      if (ev.deltaMode === 2) dy *= 100; // page → px
      // Cap per-event delta so a single huge wheel event doesn't
      // jump 2× — keeps the gesture feel predictable.
      dy = Math.max(-120, Math.min(120, dy));
      var factor = Math.exp(-dy * 0.0025);
      zoomAt(ev.clientX, ev.clientY, factor);
    }, { passive: false });
    // Drag to pan.
    var dragging = false, lastX = 0, lastY = 0;
    stage.addEventListener('mousedown', function (ev) {
      if (ev.button !== 0) return;
      if (ev.target.closest('.okt-lightbox-pz-toolbar')) return;
      dragging = true; lastX = ev.clientX; lastY = ev.clientY;
      stage.classList.add('panning');
      ev.preventDefault();
    });
    window.addEventListener('mousemove', function (ev) {
      if (!dragging) return;
      tx += ev.clientX - lastX;
      ty += ev.clientY - lastY;
      lastX = ev.clientX; lastY = ev.clientY;
      apply();
    });
    window.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      stage.classList.remove('panning');
    });
    // Touch — single-finger drag, two-finger pinch.
    var pointers = new Map();
    var pinchPrevDist = 0;
    stage.addEventListener('pointerdown', function (ev) {
      if (ev.pointerType !== 'touch') return;
      pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      if (pointers.size === 2) {
        var p = Array.from(pointers.values());
        var dx = p[1].x - p[0].x, dy = p[1].y - p[0].y;
        pinchPrevDist = Math.sqrt(dx * dx + dy * dy);
      }
    });
    stage.addEventListener('pointermove', function (ev) {
      if (ev.pointerType !== 'touch') return;
      if (!pointers.has(ev.pointerId)) return;
      var prev = pointers.get(ev.pointerId);
      pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      if (pointers.size === 1) {
        tx += ev.clientX - prev.x;
        ty += ev.clientY - prev.y;
        apply();
      } else if (pointers.size === 2) {
        var p = Array.from(pointers.values());
        var dx = p[1].x - p[0].x, dy = p[1].y - p[0].y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (pinchPrevDist > 0) {
          var cx = (p[0].x + p[1].x) / 2;
          var cy = (p[0].y + p[1].y) / 2;
          zoomAt(cx, cy, dist / pinchPrevDist);
        }
        pinchPrevDist = dist;
      }
    });
    stage.addEventListener('pointerup', function (ev) {
      pointers.delete(ev.pointerId);
      pinchPrevDist = 0;
    });
    stage.addEventListener('pointercancel', function (ev) {
      pointers.delete(ev.pointerId);
      pinchPrevDist = 0;
    });
    // Double-click resets.
    stage.addEventListener('dblclick', function () { reset(); });
    // Toolbar buttons.
    toolbar.addEventListener('click', function (ev) {
      var btn = ev.target.closest('button[data-pz]');
      if (!btn) return;
      var r = stage.getBoundingClientRect();
      var cx = r.left + r.width / 2;
      var cy = r.top + r.height / 2;
      var act = btn.getAttribute('data-pz');
      // Toolbar +/- buttons use a softer ×1.2 step so a casual
      // multi-click doesn't blow past the content's natural size.
      // Earlier the buttons used ×1.4 — felt like skipping zoom
      // ticks instead of stepping through them.
      if (act === 'in')         zoomAt(cx, cy, 1.2);
      else if (act === 'out')   zoomAt(cx, cy, 1 / 1.2);
      else if (act === 'reset') reset();
    });
    // Keyboard shortcuts while the stage is focused.
    stage.tabIndex = 0;
    stage.addEventListener('keydown', function (ev) {
      var r = stage.getBoundingClientRect();
      var cx = r.left + r.width / 2;
      var cy = r.top + r.height / 2;
      // +/- key zoom factor matched to the toolbar buttons.
      if (ev.key === '+' || ev.key === '=') { ev.preventDefault(); zoomAt(cx, cy, 1.2); }
      else if (ev.key === '-')              { ev.preventDefault(); zoomAt(cx, cy, 1 / 1.2); }
      else if (ev.key === '0')              { ev.preventDefault(); reset(); }
      else if (ev.key === 'ArrowLeft')      { ev.preventDefault(); tx += 40; apply(); }
      else if (ev.key === 'ArrowRight')     { ev.preventDefault(); tx -= 40; apply(); }
      else if (ev.key === 'ArrowUp')        { ev.preventDefault(); ty += 40; apply(); }
      else if (ev.key === 'ArrowDown')      { ev.preventDefault(); ty -= 40; apply(); }
    });
    apply();
  }
  return { attach: attach };
})();

/* ============ Chart-config popover ============ *
 * Opens a floating panel anchored to a chart's toolbar button.
 * Initial controls: type switch (compatible types derived from the
 * chart's data shape — no `compatible_with` field needed). Changing
 * the type rebuilds the chart in place by replacing the host with a
 * new <oku-chart> carrying the new attributes + same data scripts.
 *
 * Why a fresh host instead of re-running connectedCallback in place:
 * OkuChart's `_initialized` guard means a single host renders once.
 * The cleaner path is to swap the host so the new instance walks the
 * normal init path. The popover stays open and re-anchors.
 * --------------------------------------------------------------------- */
var __okuChartConfig = (function () {
  var popover = null;
  var currentHost = null;
  var anchorBtn = null;

  /* Derive the list of chart types that consume the host's data
     shape. Lives in code (per the design-review decision) rather
     than on each chart's schema. Returns a list of {type, label}. */
  function getCompatibleTypes(host) {
    var extras = host._extras || {};
    var series = host._series || [];
    // Slice-based shapes — pie / donut share a payload via extras.slices.
    if (extras.slices && extras.slices.length) {
      return [
        { type: 'donut', label: 'donut' },
        { type: 'pie',   label: 'pie' },
      ];
    }
    // Cartesian — series of {x, y} points. Every Cartesian shape
    // (scatter / line / area / bubble / quadrant) consumes the same
    // {x, y, ...} payload, so each is a valid alternative for the
    // others. Quadrant is included because it just adds dividing
    // lines + corner labels on top of the same scatter payload —
    // the user's complaint was that switching scatter → line lost
    // the round-trip to quadrant.
    var hasXY = series.length && (series[0].data || []).some(function (p) {
      return p && p.x != null && p.y != null;
    });
    if (hasXY) {
      var hasSize = (series[0].data || []).some(function (p) { return p && p.size != null; });
      var opts = [
        { type: 'scatter',  label: 'scatter' },
        { type: 'line',     label: 'line' },
        { type: 'area',     label: 'area' },
        { type: 'quadrant', label: 'quadrant' },
      ];
      if (hasSize) opts.unshift({ type: 'bubble', label: 'bubble' });
      return opts;
    }
    // Distribution-leaning shapes: extras.histogram and extras['box-plot']
    // each consume a different sub-payload but represent the same kind of
    // "one column of values" question. We don't auto-convert payloads
    // across them in v1 — list only the current type as compatible.
    if (extras.histogram)   return [{ type: 'histogram',   label: 'histogram' }];
    if (extras['box-plot']) return [{ type: 'box-plot',    label: 'box-plot' }];
    if (extras.ridgeline)   return [{ type: 'ridgeline',   label: 'ridgeline' }];
    if (extras.sparkline)   return [{ type: 'sparkline',   label: 'sparkline' }];
    if (extras.gauge)       return [{ type: 'gauge',       label: 'gauge' }];
    if (extras.bullet)      return [{ type: 'bullet',      label: 'bullet' }];
    if (extras.radar)       return [{ type: 'radar',       label: 'radar' }];
    if (extras.heatmap)     return [{ type: 'heatmap',     label: 'heatmap' }];
    if (extras['calendar-heatmap']) return [{ type: 'calendar-heatmap', label: 'calendar-heatmap' }];
    if (extras.treemap)     return [{ type: 'treemap',     label: 'treemap' }];
    if (extras.waffle)      return [{ type: 'waffle',      label: 'waffle' }];
    if (extras.funnel)      return [{ type: 'funnel',      label: 'funnel' }];
    if (extras.sankey)      return [{ type: 'sankey',      label: 'sankey' }];
    if (extras.network)     return [{ type: 'network',     label: 'network' }];
    if (extras.chord)       return [{ type: 'chord',       label: 'chord' }];
    if (extras['scatter-matrix']) return [{ type: 'scatter-matrix', label: 'scatter-matrix' }];
    if (extras['parallel-coordinates']) return [{ type: 'parallel-coordinates', label: 'parallel-coordinates' }];
    if (extras.geo)         return [{ type: 'geo',         label: 'geo' }];
    if (extras.slope)       return [{ type: 'slope',       label: 'slope' }];
    // Fallback: just the current type.
    return [{ type: host._type, label: host._type }];
  }

  function build() {
    if (popover) return popover;
    popover = document.createElement('div');
    popover.className = 'okc-config-popover';
    popover.setAttribute('role', 'dialog');
    popover.setAttribute('aria-modal', 'false');
    popover.setAttribute('aria-label', 'Chart configuration');
    popover.hidden = true;
    document.body.appendChild(popover);
    document.addEventListener('keydown', function (e) {
      if (popover.hidden) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); }
    });
    document.addEventListener('click', function (e) {
      if (popover.hidden) return;
      if (popover.contains(e.target)) return;
      if (anchorBtn && anchorBtn.contains(e.target)) return;
      close();
    }, true);
    window.addEventListener('resize', function () { if (!popover.hidden) position(); });
    window.addEventListener('scroll', function () { if (!popover.hidden) position(); }, true);
    return popover;
  }

  function position() {
    if (!anchorBtn || !popover) return;
    var r = anchorBtn.getBoundingClientRect();
    var pad = 8;
    var pr = popover.getBoundingClientRect();
    // Anchor below the button by default; flip to above if it would
    // overflow the viewport bottom.
    var top  = r.bottom + 6;
    var left = r.right - pr.width;
    if (top + pr.height > window.innerHeight - pad) top = r.top - pr.height - 6;
    if (left < pad) left = pad;
    if (left + pr.width > window.innerWidth - pad) left = window.innerWidth - pr.width - pad;
    if (top < pad) top = pad;
    popover.style.left = left + 'px';
    popover.style.top  = top  + 'px';
  }

  /* Populate the popover with the current chart's config — title,
     type dropdown, mode/marks if applicable. Bind handlers that
     mutate the chart on change. */
  function render(host) {
    if (!popover) return;
    var compat = getCompatibleTypes(host);
    var rows = [];
    rows.push(
      '<div class="okc-cfg-head">' +
        '<span class="okc-cfg-title">Configure chart</span>' +
        '<button type="button" class="okc-cfg-close" aria-label="Close">' + ICON_CROSS + '</button>' +
      '</div>'
    );
    if (compat.length > 1) {
      rows.push('<label class="okc-cfg-row">' +
        '<span class="okc-cfg-label">Type</span>' +
        '<select class="okc-cfg-select" data-cfg="type">' +
          compat.map(function (c) {
            var sel = c.type === host._type ? ' selected' : '';
            return '<option value="' + c.type + '"' + sel + '>' + c.label + '</option>';
          }).join('') +
        '</select>' +
      '</label>');
    } else {
      rows.push('<div class="okc-cfg-row okc-cfg-hint">' +
        'Type <code>' + host._type + '</code> has no shape-compatible alternatives yet.' +
      '</div>');
    }
    // Cartesian — marks combo. Bubble + quadrant share the same
    // Cartesian payload so marks also applies to them.
    if (host._type === 'scatter' || host._type === 'line' || host._type === 'area' || host._type === 'plot' || host._type === 'bubble' || host._type === 'quadrant') {
      var marks = host._marks || (host._type === 'scatter' ? ['dots'] : host._type === 'line' ? ['line'] : host._type === 'area' ? ['line', 'area'] : ['dots']);
      rows.push('<div class="okc-cfg-row">' +
        '<span class="okc-cfg-label">Marks</span>' +
        '<div class="okc-cfg-chips" data-cfg="marks">' +
          ['dots', 'line', 'area'].map(function (m) {
            var on = marks.indexOf(m) !== -1;
            return '<button type="button" class="okc-cfg-chip' + (on ? ' on' : '') + '" data-mark="' + m + '">' + m + '</button>';
          }).join('') +
        '</div>' +
      '</div>');
    }
    // Arc — mode + arc start/end.
    if (host._type === 'donut' || host._type === 'pie') {
      var mode = host._type === 'pie' ? 'pie' : 'donut';
      rows.push('<div class="okc-cfg-row">' +
        '<span class="okc-cfg-label">Mode</span>' +
        '<div class="okc-cfg-chips" data-cfg="arc-mode">' +
          ['pie', 'donut'].map(function (m) {
            var on = m === mode;
            return '<button type="button" class="okc-cfg-chip' + (on ? ' on' : '') + '" data-mode="' + m + '">' + m + '</button>';
          }).join('') +
        '</div>' +
      '</div>');
      rows.push('<div class="okc-cfg-row">' +
        '<span class="okc-cfg-label">Arc end (deg)</span>' +
        '<input type="number" class="okc-cfg-num" data-cfg="arc-end" min="-360" max="720" step="15" value="' + (host._arcEnd !== null && host._arcEnd !== undefined ? host._arcEnd : 360) + '">' +
      '</div>');
    }
    popover.innerHTML = rows.join('');
    wire(host);
  }

  function wire(host) {
    var closeBtn = popover.querySelector('.okc-cfg-close');
    if (closeBtn) closeBtn.addEventListener('click', close);
    var sel = popover.querySelector('select[data-cfg="type"]');
    if (sel) sel.addEventListener('change', function () { applyChange(host, { type: sel.value }); });
    popover.querySelectorAll('.okc-cfg-chip[data-mark]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var marks = Array.from(popover.querySelectorAll('.okc-cfg-chip[data-mark].on')).map(function (c) { return c.getAttribute('data-mark'); });
        var m = chip.getAttribute('data-mark');
        var idx = marks.indexOf(m);
        if (idx === -1) marks.push(m); else marks.splice(idx, 1);
        if (!marks.length) marks.push(m); // never empty
        applyChange(host, { marks: marks });
      });
    });
    popover.querySelectorAll('.okc-cfg-chip[data-mode]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        applyChange(host, { type: chip.getAttribute('data-mode') });
      });
    });
    var arcEnd = popover.querySelector('input[data-cfg="arc-end"]');
    if (arcEnd) arcEnd.addEventListener('input', function () {
      applyChange(host, { arcEnd: arcEnd.value });
    });
  }

  /* Apply a partial config delta by building a new oku-chart host
     with merged attributes + the same data <script> children, then
     swap it in place. The popover re-renders against the new host.

     Type vs marks coupling: a marks change implies a type switch
     because OkuChart's dispatcher maps `type=plot` + marks to one
     of scatter / line / area based on mark precedence (area > line
     > dots). So a marks delta is normalised to `type=plot` + the
     new marks attr. Conversely, a pure type change must DROP any
     prior `marks` attr — otherwise switching from line back to
     quadrant would carry the old marks="line" and OkuChart would
     re-resolve to type=line. */
  function applyChange(oldHost, delta) {
    var newHost = document.createElement('oku-chart');
    // Copy purely-presentation attrs that don't interact with
    // type / marks resolution.
    var copyAttrs = ['title', 'x-label', 'y-label', 'x-scale', 'y-scale', 'inner-radius', 'arc-start'];
    copyAttrs.forEach(function (a) {
      var v = oldHost.getAttribute(a);
      if (v !== null) newHost.setAttribute(a, v);
    });
    if (delta.marks) {
      // Marks change → canonical plot form, fresh marks list.
      newHost.setAttribute('type', 'plot');
      newHost.setAttribute('marks', delta.marks.join(','));
    } else if (delta.type !== undefined) {
      // Pure type change → fresh type, NO inherited marks.
      newHost.setAttribute('type', delta.type);
    } else {
      // Neither type nor marks in delta → preserve both as-is.
      newHost.setAttribute('type', oldHost.getAttribute('type'));
      var oldMarks = oldHost.getAttribute('marks');
      if (oldMarks) newHost.setAttribute('marks', oldMarks);
    }
    // Mode (arc / bar grouping) — carry through unless replaced.
    var oldMode = oldHost.getAttribute('mode');
    if (oldMode) newHost.setAttribute('mode', oldMode);
    // Arc-end can be overridden via delta or preserved.
    if (delta.arcEnd !== undefined) {
      newHost.setAttribute('arc-end', String(delta.arcEnd));
    } else {
      var oldArcEnd = oldHost.getAttribute('arc-end');
      if (oldArcEnd) newHost.setAttribute('arc-end', oldArcEnd);
    }
    // Carry over data + extras scripts.
    Array.from(oldHost.querySelectorAll('script[type="application/json"]')).forEach(function (s) {
      newHost.appendChild(s.cloneNode(true));
    });
    oldHost.parentNode.replaceChild(newHost, oldHost);
    currentHost = newHost;
    // Re-anchor the popover to the new toolbar's gear button after init.
    requestAnimationFrame(function () {
      var bar = newHost.querySelector(':scope > .okt-bar');
      var gear = bar && bar.querySelector('button[title="Configure chart"]');
      if (gear) anchorBtn = gear;
      render(newHost);
      position();
    });
  }

  function open(host, btn) {
    build();
    currentHost = host;
    anchorBtn = btn;
    popover.hidden = false;
    render(host);
    requestAnimationFrame(position);
  }

  function close() {
    if (!popover) return;
    popover.hidden = true;
    currentHost = null;
    anchorBtn = null;
  }

  return { open: open, close: close, getCompatibleTypes: getCompatibleTypes };
})();

/* ============ Table-config popover ============ *
 * Same pattern as the chart-config popover: gear button on a
 * table's toolbar opens a floating panel anchored to the gear.
 * The panel hosts the configuration knobs that don't need to be
 * always-visible — view mode, group-by, sort, per-column filters.
 *
 * Implementation note: instead of cloning the controls (which
 * would lose event listeners), the popover MOVES the live
 * elements from the stashed area in ctrl into itself. A marker
 * tracks where they belong; close restores them.
 * --------------------------------------------------------------------- */
var __okuTableConfig = (function () {
  var popover = null;
  var currentWrap = null;
  var anchorBtn = null;
  // [{ node, markerComment }] — what we moved out of ctrl.
  var movedNodes = [];

  function build() {
    if (popover) return popover;
    popover = document.createElement('div');
    popover.className = 'okt-config-popover';
    popover.setAttribute('role', 'dialog');
    popover.setAttribute('aria-modal', 'false');
    popover.setAttribute('aria-label', 'Table configuration');
    popover.hidden = true;
    document.body.appendChild(popover);
    document.addEventListener('keydown', function (e) {
      if (popover.hidden) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); }
    });
    document.addEventListener('click', function (e) {
      if (popover.hidden) return;
      if (popover.contains(e.target)) return;
      if (anchorBtn && anchorBtn.contains(e.target)) return;
      close();
    }, true);
    window.addEventListener('resize', function () { if (!popover.hidden) position(); });
    window.addEventListener('scroll', function () { if (!popover.hidden) position(); }, true);
    return popover;
  }

  function position() {
    if (!anchorBtn || !popover) return;
    var r = anchorBtn.getBoundingClientRect();
    var pad = 8;
    var pr = popover.getBoundingClientRect();
    var top  = r.bottom + 6;
    var left = r.right - pr.width;
    if (top + pr.height > window.innerHeight - pad) top = r.top - pr.height - 6;
    if (left < pad) left = pad;
    if (left + pr.width > window.innerWidth - pad) left = window.innerWidth - pr.width - pad;
    if (top < pad) top = pad;
    popover.style.left = left + 'px';
    popover.style.top  = top  + 'px';
  }

  /* Move a stashed inline control into a labelled popover row. */
  function moveInto(stashed, popoverRoot, label) {
    if (!stashed) return null;
    var marker = document.createComment('table-config-slot');
    stashed.parentNode.insertBefore(marker, stashed);
    var row = document.createElement('label');
    row.className = 'okt-cfg-row';
    if (label) {
      var lbl = document.createElement('span');
      lbl.className = 'okt-cfg-label';
      lbl.textContent = label;
      row.appendChild(lbl);
    }
    var holder = document.createElement('span');
    holder.className = 'okt-cfg-field';
    // Unhide the stashed element + drop its data-hidden flag now
    // that it's inside the popover.
    stashed.removeAttribute('hidden');
    holder.appendChild(stashed);
    row.appendChild(holder);
    popoverRoot.appendChild(row);
    movedNodes.push({ node: stashed, marker: marker });
    return row;
  }

  function open(wrap, btn) {
    build();
    currentWrap = wrap;
    anchorBtn = btn;
    popover.hidden = false;
    popover.innerHTML =
      '<div class="okc-cfg-head">' +
        '<span class="okc-cfg-title">Configure table</span>' +
        '<button type="button" class="okc-cfg-close" aria-label="Close">' + ICON_CROSS + '</button>' +
      '</div>';
    var closeBtn = popover.querySelector('.okc-cfg-close');
    closeBtn.addEventListener('click', close);
    // Pull the stashed controls out and into popover rows. View
    // toggle first (most common change), then group-by.
    var stash = wrap.querySelector('.okt-config-stashed');
    if (stash) {
      var viewGroup = stash.querySelector('.okt-view-group');
      var groupby   = stash.querySelector('.okt-groupby');
      // The empty .okt-ctrl-sep used inline between view and groupby
      // can stay in ctrl — only move the meaningful controls.
      moveInto(viewGroup, popover, 'View');
      moveInto(groupby,   popover, 'Group by');
    }
    // Per-column filters. Lives in code under wrap.__oktState so the
    // popover can write into the wrap's filter map + trigger a
    // re-render without coupling to its closures.
    var state = wrap.__oktState;
    if (state && state.headers && state.headers.length) {
      var section = document.createElement('div');
      section.className = 'okt-cfg-section';
      section.innerHTML = '<div class="okt-cfg-subtitle">Filter columns</div>';
      state.headers.forEach(function (label, idx) {
        var row = document.createElement('label');
        row.className = 'okt-cfg-row';
        var lbl = document.createElement('span');
        lbl.className = 'okt-cfg-label';
        lbl.textContent = label || ('Column ' + (idx + 1));
        var input = document.createElement('input');
        input.type = 'search';
        input.className = 'okt-cfg-colfilter';
        input.placeholder = 'contains…';
        input.value = state.columnFilters[idx] || '';
        input.addEventListener('input', function () {
          state.columnFilters[idx] = input.value;
          state.render();
        });
        var holder = document.createElement('span');
        holder.className = 'okt-cfg-field';
        holder.appendChild(input);
        row.appendChild(lbl);
        row.appendChild(holder);
        section.appendChild(row);
      });
      popover.appendChild(section);
    }
    requestAnimationFrame(position);
  }

  function close() {
    if (!popover || popover.hidden) return;
    // Put the moved nodes back where they came from.
    for (var i = movedNodes.length - 1; i >= 0; i--) {
      var m = movedNodes[i];
      if (m.marker && m.marker.parentNode) {
        m.node.setAttribute('hidden', '');
        m.marker.parentNode.insertBefore(m.node, m.marker);
        m.marker.parentNode.removeChild(m.marker);
      }
    }
    movedNodes = [];
    popover.hidden = true;
    currentWrap = null;
    anchorBtn = null;
  }

  function toggle(wrap, btn) {
    if (popover && !popover.hidden && currentWrap === wrap) {
      close();
    } else {
      if (popover && !popover.hidden) close();
      open(wrap, btn);
    }
  }

  return { open: open, close: close, toggle: toggle };
})();

/* ============ Three-mode theme cycler (system → light → dark → system) ============ */
function getThemeMode() {
  return document.documentElement.getAttribute('data-theme-mode') || 'system';
}
function applyTheme(mode, persist) {
  var actual = mode === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : mode;
  // Suppress every transition during the swap so the whole page
  // flips themes in one paint instead of cascading element-by-
  // element (each independent transition: color / background /
  // border the kit declares would otherwise animate independently
  // and produce a visible "part-by-part" wipe).
  var doc = document.documentElement;
  doc.classList.add('okt-theme-swapping');
  doc.setAttribute('data-theme', actual);
  doc.setAttribute('data-theme-mode', mode);
  // Force reflow so the class actually takes effect before the
  // theme repaint runs.
  void doc.offsetHeight;
  // Re-enable transitions after two frames — one for the paint,
  // one to be safe before subsequent transitions are honoured again.
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      doc.classList.remove('okt-theme-swapping');
    });
  });
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
  // Notify subscribers (e.g., <oku-diagram> rerenders Mermaid).
  window.dispatchEvent(new CustomEvent('oku:theme-changed', {
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
  if (window.innerWidth <= 768) {
    // Narrow viewport: drawer mode. body.drawer-open powers both the
    // slide-in animation on page-nav and the backdrop pseudo-element.
    document.body.classList.toggle('drawer-open');
    return;
  }
  // Wide viewport: column collapse via the persistent body class.
  document.body.classList.toggle('sidebar-collapsed');
  try {
    localStorage.setItem('sidebarCollapsed',
      document.body.classList.contains('sidebar-collapsed') ? '1' : '0');
  } catch (e) {}
}

// Close the mobile drawer on outside click or Escape.
document.addEventListener('click', function (e) {
  if (!document.body.classList.contains('drawer-open')) return;
  if (window.innerWidth > 768) return;
  var nav = document.querySelector('page-nav');
  var hamburger = document.querySelector('.ctrl-btn.drawer-toggle');
  if (nav && nav.contains(e.target)) return;
  if (hamburger && hamburger.contains(e.target)) return;
  document.body.classList.remove('drawer-open');
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') document.body.classList.remove('drawer-open');
});

/* ============ Hash-based SPA navigation ========================== *
 * `oku init` only writes docs/index.html on disk. Sub-pages
 * (architecture.html, etc.) live as JSON sources with no .html
 * sibling. For the sidebar to navigate AND for refresh + middle-
 * click + copy-link to all stay robust under static file servers
 * (IntelliJ :63342, file://, plain http.server), the URL's pathname
 * always stays at index.html and the fragment carries the page:
 *
 *   /docs/index.html              → renders index.json
 *   /docs/index.html#architecture.html
 *                                 → renders architecture.json
 *   /docs/index.html#architecture.html:perf
 *                                 → renders architecture.json, then
 *                                   scrolls to #perf
 *
 * Why hash: the URL's pathname always points at an on-disk file
 * (index.html) so reload never 404s, regardless of which page the
 * reader is on. The renderer doesn't have to coordinate with any
 * server-side rewrite.
 * ------------------------------------------------------------------- */

// Parse "<pagePath>" or "<pagePath>:<anchor>" out of a raw hash string.
function __okuParseHash(rawHash) {
  var raw = (rawHash || '').replace(/^#/, '');
  if (!raw) return { page: null, anchor: null };
  var sep = raw.indexOf(':');
  var page = sep >= 0 ? raw.slice(0, sep) : raw;
  var anchor = sep >= 0 ? raw.slice(sep + 1) : '';
  if (!page.endsWith('.html')) {
    // Looks like a plain in-page anchor (e.g., "#perf"). Let the
    // browser handle it natively — we just scroll, not re-render.
    return { page: null, anchor: page || null };
  }
  return { page: page, anchor: anchor || null };
}

function __okuScrollToAnchor(anchor) {
  if (!anchor) { window.scrollTo(0, 0); return; }
  requestAnimationFrame(function () {
    var target = document.getElementById(anchor) || document.querySelector('[id="' + anchor + '"]');
    if (target) target.scrollIntoView();
  });
}

function __okuRenderHash() {
  if (typeof OkuRenderer === 'undefined') return Promise.reject(new Error('renderer not loaded'));
  var parsed = __okuParseHash(window.location.hash);
  var current = window.__okuCurrentPage;
  // Anchor-only change while parked on a page (e.g., page-toc click on
  // a non-index page): the user wants to scroll within the current
  // page, NOT navigate back to index.
  if (!parsed.page) {
    if (current) {
      __okuScrollToAnchor(parsed.anchor);
      return Promise.resolve();
    }
    // No current page (cold boot with anchor-only hash) → render index
    // and scroll. autoBoot also covers the same case; this branch
    // mostly catches Back-button into a pre-page state.
    return __okuFetchAndRender('index.html', parsed.anchor);
  }
  // Same page, new anchor → scroll without re-render.
  if (current === parsed.page) {
    __okuScrollToAnchor(parsed.anchor);
    return Promise.resolve();
  }
  return __okuFetchAndRender(parsed.page, parsed.anchor);
}

function __okuFetchAndRender(pagePath, anchor) {
  var wa = (window.__okuWithAuth || function (u) { return u; });
  var jsonUrl = wa(__okuDocsRoot + pagePath.replace(/\.html$/, '.json'));
  return fetch(jsonUrl, { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (page) {
      // Set BEFORE calling render so the oku:rendered handlers
      // (buildTOC, etc.) see the right "current page" when they fire
      // — they need it to namespace TOC hrefs.
      window.__okuCurrentPage = pagePath;
      new OkuRenderer({}).render(page);
      __okuRefreshActiveLink(pagePath);
      __okuScrollToAnchor(anchor);
    });
}

function __okuRefreshActiveLink(pagePath) {
  document.querySelectorAll('page-nav .page-nav-item.active').forEach(function (li) {
    li.classList.remove('active');
    var a = li.querySelector('a');
    if (a) a.removeAttribute('aria-current');
  });
  document.querySelectorAll('page-nav a[href]').forEach(function (a) {
    var href = a.getAttribute('href') || '';
    var ref = __okuParseHash(href);
    var hrefPage = ref.page || '';
    var match = hrefPage === pagePath || (!hrefPage && pagePath === 'index.html');
    if (match) {
      var li = a.closest('.page-nav-item');
      if (li) li.classList.add('active');
      a.setAttribute('aria-current', 'page');
    }
  });
}

// Hashchange covers: native hash-link clicks (sidebar), explicit
// location.hash assignments from the interceptor below, and the
// browser's Back/Forward buttons (which fire hashchange when only
// the fragment changes).
window.addEventListener('hashchange', function () {
  // Tell the scroll-spy to pause its replaceState writes for a tick —
  // otherwise the scroll-driven hash update fights the click-driven one.
  try { window.dispatchEvent(new Event('oku:hash-routing')); } catch (e) { /* ignore */ }
  __okuRenderHash().catch(function (err) {
    console.warn('[oku] hash navigation failed', err);
  });
  document.body.classList.remove('drawer-open');
});

// Intercept clicks on internal .html links that DON'T already use
// the hash form (e.g., inline cross-page links written as plain
// "architecture.html" inside JSON content). Convert them to hash
// navigation so refresh-on-page stays robust.
document.addEventListener('click', function (e) {
  if (e.defaultPrevented) return;
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  if (e.button !== 0) return;
  var a = e.target && e.target.closest && e.target.closest('a[href]');
  if (!a) return;
  if (a.target && a.target !== '_self') return;
  if (a.hasAttribute('download')) return;
  var href = a.getAttribute('href');
  if (!href || href.charAt(0) === '#') return; // already hash — native handling
  var url;
  try { url = new URL(href, window.location.href); } catch (err) { return; }
  if (url.origin !== window.location.origin) return;
  if (!url.pathname.endsWith('.html')) return;
  // Compute pagePath relative to the docs root.
  var docsRootPath;
  try { docsRootPath = new URL(__okuDocsRoot, window.location.origin).pathname; } catch (e2) { docsRootPath = '/'; }
  var pagePath = url.pathname.indexOf(docsRootPath) === 0
    ? url.pathname.slice(docsRootPath.length)
    : url.pathname;
  e.preventDefault();
  var anchor = url.hash.replace(/^#/, '');
  var newHash = '#' + pagePath + (anchor ? ':' + anchor : '');
  if (window.location.hash === newHash) {
    // Same target — re-render anyway (scroll to top).
    __okuRenderHash().catch(function () {});
  } else {
    window.location.hash = newHash; // fires hashchange
  }
});
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
// P7 — Layout Option A. Default mode is the new 'comfortable' band
// (960px) — narrow stays available for prose-heavy reading; wide /
// max are opt-ins for tables, charts, and matrices. Cycle order
// goes narrow → comfortable → wide → max so a single tap moves up
// one notch each time.
var WIDTH_MODES = ['narrow', 'comfortable', 'wide', 'max'];
var DEFAULT_WIDTH = 'comfortable';
function _widthLabelFor(mode) {
  return 'Content width: ' + mode + ' — click to cycle (narrow → comfortable → wide → max)';
}
function _syncWidthToggleLabel(mode) {
  var btn = document.querySelector('.width-toggle');
  if (!btn) return;
  var lbl = _widthLabelFor(mode);
  btn.setAttribute('title', lbl);
  btn.setAttribute('aria-label', lbl);
}
function cycleContentWidth() {
  var current = document.body.getAttribute('data-content-width') || DEFAULT_WIDTH;
  var i = WIDTH_MODES.indexOf(current);
  var next = WIDTH_MODES[(i + 1) % WIDTH_MODES.length];
  document.body.setAttribute('data-content-width', next);
  try { localStorage.setItem('htmldoc-content-width', next); } catch (e) {}
  _syncWidthToggleLabel(next);
}
try {
  var savedWidth = localStorage.getItem('htmldoc-content-width');
  if (savedWidth && WIDTH_MODES.indexOf(savedWidth) !== -1) {
    document.addEventListener('DOMContentLoaded', function () {
      document.body.setAttribute('data-content-width', savedWidth);
      _syncWidthToggleLabel(savedWidth);
    });
  } else {
    document.addEventListener('DOMContentLoaded', function () {
      if (!document.body.getAttribute('data-content-width')) {
        document.body.setAttribute('data-content-width', DEFAULT_WIDTH);
      }
      _syncWidthToggleLabel(document.body.getAttribute('data-content-width'));
    });
  }
} catch (e) {}

/* Body skeleton injection. The per-page stub may carry as little as
 * <body></body> — chrome.js then fills in <page-chrome> + the layout
 * grid (page-nav, main, page-toc) on DOMContentLoaded. Authors who
 * want a custom layout can still write the elements themselves; this
 * function bails out the moment it sees an existing <page-chrome>. */
function ensureLayoutSkeleton() {
  if (document.querySelector('page-chrome')) return;
  var body = document.body;
  if (!body) return;
  body.insertAdjacentHTML('afterbegin',
    '<page-chrome></page-chrome>' +
    '<div class="layout">' +
      '<page-nav></page-nav>' +
      '<main id="main-content"></main>' +
      '<page-toc></page-toc>' +
    '</div>'
  );
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', ensureLayoutSkeleton);
} else {
  ensureLayoutSkeleton();
}

/* ============ <page-chrome> Web Component ============ */
class PageChrome extends HTMLElement {
  connectedCallback() {
    var skipLabel = this.getAttribute('skip-label') || 'Skip to content';
    var drawerLabel = this.getAttribute('drawer-label') || 'Open navigation';
    var themeLabel = this.getAttribute('theme-label') || 'Cycle theme (system / light / dark)';
    var widthLabel = this.getAttribute('width-label') || 'Cycle content width (narrow / comfortable / wide / max)';
    var topLabel = this.getAttribute('top-label') || 'Back to top';

    // .drawer-toggle is hidden via CSS on wide viewports — the right-
    // edge handle on page-nav is the collapse affordance there. On
    // narrow (≤768px) the sidebar becomes an off-canvas drawer and
    // this is its only toggle.
    this.innerHTML =
      '<a class="skip-link" href="#main-content">' + skipLabel + '</a>' +
      '<div class="progress-bar" id="progress-bar"></div>' +
      '<button class="ctrl-btn drawer-toggle" type="button" aria-label="' + drawerLabel + '" title="' + drawerLabel + '">' + ICON_MENU + '</button>' +
      '<button class="ctrl-btn width-toggle" type="button" aria-label="' + widthLabel + '" title="' + widthLabel + '">' + ICON_WIDTH + '</button>' +
      '<button class="ctrl-btn theme-toggle" type="button" aria-label="' + themeLabel + '" title="' + themeLabel + '">' +
        '<span class="icon-system">' + ICON_SYSTEM + '</span>' +
        '<span class="icon-sun">' + ICON_SUN + '</span>' +
        '<span class="icon-moon">' + ICON_MOON + '</span>' +
      '</button>' +
      '<button class="ctrl-btn back-to-top" type="button" aria-label="' + topLabel + '" title="' + topLabel + '">' + ICON_UP + '</button>';

    this.querySelector('.drawer-toggle').addEventListener('click', toggleTOC);
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
    // Header text mirrors the current page title — far less noise than
    // "On this page" and gives the reader a label when the sidebar is
    // visible on wide screens. Falls back to a custom attribute or
    // document.title if the renderer hasn't filled in either yet; an
    // oku:rendered listener below refreshes once the page mounts.
    var override = this.getAttribute('title');
    var initial = override || document.title || '';
    this.innerHTML =
      '<div class="page-toc-panel">' +
        '<div class="toc-header"><h2 class="page-toc-title"></h2></div>' +
        '<ol class="toc-list"></ol>' +
      '</div>';
    var self = this;
    var heading = self.querySelector('.page-toc-title');
    if (heading) heading.textContent = initial;
    function refreshTitle() {
      if (!heading) return;
      // The author-supplied attribute, if set, always wins.
      if (override) { heading.textContent = override; return; }
      var pageH1 = document.querySelector('main header.cover h1, main h1');
      heading.textContent = (pageH1 && pageH1.textContent.trim()) || document.title || '';
    }
    // The renderer dispatches oku:rendered on window after every
    // render (initial + each hash-nav re-render), which is exactly
    // when document.title and main's h1 are fresh.
    window.addEventListener('oku:rendered', refreshTitle);
    window.addEventListener('hashchange', function () {
      // Defensive: if a flow path swaps <main> faster than the
      // rendered event fires, the next microtask still picks up the
      // new title.
      setTimeout(refreshTitle, 0);
    });
    // If <main> already has section content (pre-rendered HTML), build
    // the TOC now. For renderer-driven pages, oku:rendered will
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
  // Page-aware so copy-link gives a URL that fully restores state.
  var current = window.__okuCurrentPage;
  var prefix = (current && current !== 'index.html') ? '#' + current + ':' : '#';
  var a = document.createElement('a');
  a.className = 'permalink';
  a.href = prefix + id;
  a.textContent = '#';
  a.setAttribute('aria-label', label || 'Permalink');
  heading.appendChild(a);
}

function buildTOC(tocList) {
  if (!tocList) return;
  var sections = document.querySelectorAll('main > section');
  if (sections.length === 0) return;
  tocList.innerHTML = '';

  // Page-aware hash prefix: under hash routing, plain "#sec-id" hrefs
  // would clobber the current page entry in the URL hash. Anchoring
  // each TOC entry to "<currentPage>:<sec-id>" keeps the page context
  // intact and makes copy-link work correctly. For index.html (no
  // current page or explicit index), the bare "#sec-id" is fine.
  var current = window.__okuCurrentPage;
  var hashPrefix = (current && current !== 'index.html') ? '#' + current + ':' : '#';

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
      '<a href="' + hashPrefix + sec.id + '">' + title + '</a>';
    li.appendChild(head);

    var h3s = sec.querySelectorAll('h3');
    var subOl = document.createElement('ol');
    subOl.className = 'toc-sub';
    h3s.forEach(function (h3) {
      if (!h3.id) h3.id = sec.id + '-' + slugify(h3.textContent).slice(0, 40);
      appendPermalink(h3, h3.id);
      var subLi = document.createElement('li');
      var a = document.createElement('a');
      a.href = hashPrefix + h3.id;
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

  // Page-aware hash prefix matches buildTOC above — so an in-flight
  // scroll past a section stamps a URL that fully restores state on
  // refresh / paste.
  var pageForHash = window.__okuCurrentPage;
  var hashPrefix = (pageForHash && pageForHash !== 'index.html') ? '#' + pageForHash + ':' : '#';
  var lastHash = null;
  // While the user is interacting with a hash-routed link (click on a
  // TOC entry, programmatic scroll triggered by the router), we let the
  // existing hash stand for one tick so we don't overwrite it before
  // the smooth scroll lands on the target.
  //
  // Start SUSPENDED: buildTOC is invoked from `oku:rendered`,
  // which fires after the renderer finishes but BEFORE the router has
  // scrolled to the deep-link section. If we let the first updateActive
  // fire eagerly it would see scrollY = 0 and clear the section anchor
  // from the URL — silently losing the deep link the reader pasted.
  // The 600 ms window matches the router's smooth-scroll budget.
  var suspendHashUpdate = true;
  setTimeout(function () { suspendHashUpdate = false; }, 600);
  window.addEventListener('oku:hash-routing', function () {
    suspendHashUpdate = true;
    setTimeout(function () { suspendHashUpdate = false; }, 600);
  });

  function updateActive() {
    // After hash-routing, buildTOC re-runs on `oku:rendered` and a
    // fresh scroll-spy is attached. The OLD scroll listener stays bound
    // to `window` (closure refs the previous page's headings + page).
    // Gate: only the scroll-spy for the CURRENT page should act —
    // otherwise the old one races the new one and overwrites the URL
    // with the previous page's prefix, breaking refresh-restores-page.
    if (pageForHash !== window.__okuCurrentPage) return;
    var y = window.scrollY + 150;
    var current = headings[0];
    for (var k = 0; k < headings.length; k++) {
      var rect = headings[k].el.getBoundingClientRect();
      var top = rect.top + window.scrollY;
      if (top <= y) current = headings[k]; else break;
    }
    if (!current) return;
    setActive(current.sectionId, current.h3Id);

    // URL hash mirrors the heading nearest the viewport top so a refresh
    // restores the same reading position. Uses replaceState so we don't
    // pollute history with every scroll wheel tick. Only fires when the
    // hash would actually change AND we're not in the middle of routing.
    if (suspendHashUpdate) return;
    var anchorId = current.h3Id || current.sectionId;
    if (!anchorId) return;
    // The page-prefix part of the hash drives hash-routing (which page
    // the renderer should fetch). The section part is what the scroll
    // spy manages. Keep the page-prefix intact across scroll-driven
    // updates so refreshing on a non-index page brings the reader back
    // to that page rather than to index.html.
    var pageBase = (pageForHash && pageForHash !== 'index.html') ? '#' + pageForHash : '';
    // At the very top of the page (no section in view yet), drop only
    // the section anchor. On non-index pages, the page-prefix stays;
    // on index the hash collapses to empty.
    if (window.scrollY < 80) {
      if (window.location.hash !== pageBase) {
        try { history.replaceState(null, '', window.location.pathname + window.location.search + pageBase); } catch (e) { /* ignore */ }
        lastHash = pageBase;
      }
      return;
    }
    var nextHash = hashPrefix + anchorId;
    if (nextHash === lastHash || nextHash === window.location.hash) {
      lastHash = nextHash;
      return;
    }
    try {
      history.replaceState(null, '', window.location.pathname + window.location.search + nextHash);
      lastHash = nextHash;
    } catch (e) { /* ignore in environments without history API */ }
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
var __okuAidsInited = false;

function initReadingAids() {
  if (!__okuAidsInited) {
    __okuAidsInited = true;

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

  /* Wrap every <pre> in an .okt-pre-host. The host is the non-scrolling
     containing block for the copy / wrap buttons; without it the
     buttons live INSIDE the scrolling pre, so a horizontal scroll
     pushes them off-screen with the content. Run before either button
     is injected so both attach to the host, not the pre. */
  function _hdtEnsurePreHost(pre) {
    if (!pre || !pre.parentNode) return pre.parentNode;
    var parent = pre.parentNode;
    if (parent.classList && parent.classList.contains('okt-pre-host')) return parent;
    // Skip pres that belong to a Custom Element rendering its own
    // toolbar (charts, diagrams, snippets, tooltip popovers).
    if (pre.closest('oku-chart, oku-diagram, oku-snippet, .oku-tooltip')) return parent;
    var host = document.createElement('div');
    host.className = 'okt-pre-host';
    parent.insertBefore(host, pre);
    host.appendChild(pre);
    return host;
  }

  /* Copy-to-clipboard on every <pre> block — re-runs safely; already
     guarded by `if (pre.querySelector('.copy-btn')) return`. Icon-only
     (clipboard → checkmark on success → cross on failure). */
  (function () {
    if (!navigator.clipboard) return;
    document.querySelectorAll('pre').forEach(function (pre) {
      // Skip pres inside Custom Elements that render their own
      // toolbar (charts, diagrams, snippets, tooltip popovers). The
      // closest() check inside _hdtEnsurePreHost already bails by
      // returning the original parent without wrapping; detect that
      // case here and skip attaching the copy button.
      if (pre.closest('oku-chart, oku-diagram, oku-snippet, .oku-tooltip')) return;
      var host = _hdtEnsurePreHost(pre);
      if (!host) return;
      if (host.querySelector(':scope > .copy-btn')) return;
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.innerHTML = ICON_CLIPBOARD;
      btn.title = 'Copy code to clipboard';
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      host.appendChild(btn);
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
    if (!window.__okuLightbox) return;
    var main = document.querySelector('#main-content') || document.body;
    main.querySelectorAll('img').forEach(function (img) {
      if (img.dataset.hdtExpandBound === '1') return;
      if (img.closest('oku-chart, oku-diagram, oku-snippet, .oku-tooltip, .okt-lightbox, page-chrome, page-nav, page-toc')) return;
      if (img.width && img.width < 80) return;   // skip tiny inline glyphs
      img.dataset.hdtExpandBound = '1';
      // Wrap the image in a host so the chip can absolute-position over it.
      var host = document.createElement('span');
      host.className = 'okt-img-host';
      img.parentNode.insertBefore(host, img);
      host.appendChild(img);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'okt-img-expand';
      btn.innerHTML = ICON_EXPAND;
      btn.title = 'Expand image';
      btn.setAttribute('aria-label', 'Expand image');
      host.appendChild(btn);
      btn.addEventListener('click', function () {
        var big = document.createElement('img');
        big.src = img.currentSrc || img.src;
        big.alt = img.alt || '';
        big.className = 'okt-lightbox-img';
        __okuLightbox.open(big, { title: img.alt || 'Expanded image' });
      });
    });
  })();

  /* Wrap toggle on every <pre> — same shape as copy button, sits to its
     left. Toggles a per-block .okt-wrap class on the <pre>; CSS flips
     white-space: pre → pre-wrap and the horizontal scrollbar away.
     State is per-block on purpose: wrapping a 200-character SQL query
     to read it shouldn't also wrap a tight CSS sample on the same page. */
  (function () {
    document.querySelectorAll('pre').forEach(function (pre) {
      // Skip blocks inside hosts that own their own toolbar (charts,
      // diagrams, live snippets, tooltips).
      if (pre.closest('oku-chart, oku-diagram, oku-snippet, .oku-tooltip')) return;
      var host = _hdtEnsurePreHost(pre);
      if (!host) return;
      if (host.querySelector(':scope > .okt-wrap-btn')) return;
      var btn = document.createElement('button');
      btn.className = 'okt-wrap-btn';
      btn.type = 'button';
      btn.innerHTML = ICON_WRAP;
      btn.title = 'Toggle line wrapping';
      btn.setAttribute('aria-label', 'Toggle line wrapping');
      btn.setAttribute('aria-pressed', 'false');
      host.appendChild(btn);
      btn.addEventListener('click', function () {
        var wrapped = pre.classList.toggle('okt-wrap');
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
     via data-okt-numbered. */
  document.querySelectorAll('pre:not([data-okt-numbered])').forEach(function (pre) {
    if (pre.closest('.oku-tooltip, oku-chart, oku-diagram, oku-snippet')) return;
    var code = pre.querySelector(':scope > code');
    if (!code) return;
    var text = code.textContent || '';
    // Trim trailing newline so the very last empty line doesn't get a number.
    if (text.endsWith('\n')) text = text.slice(0, -1);
    var lineCount = text.length ? text.split('\n').length : 1;
    if (lineCount < 1) return;
    pre.setAttribute('data-okt-numbered', '1');
    pre.classList.add('okt-line-numbered');
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
    document.querySelectorAll('pre.okt-line-numbered:not([data-okt-lines-wrapped])').forEach(function (pre) {
      var code = pre.querySelector(':scope > code');
      if (!code) return;
      // Skip blocks Prism is responsible for — the hook will handle them.
      if (/language-[\w-]+/.test(code.className)) return;
      pre.setAttribute('data-okt-lines-wrapped', '1');
      _hdtWrapCodeLines(code);
    });
  }, 0);

  /* Wide-table support: every plain <table> gets a scrollable wrapper,
     a "Table | Cards | List" view toggle, and a full-width expand button.
     Wrapper is idempotent — re-running initReadingAids leaves bound tables
     alone. Tables inside tooltips, callouts or chart/diagram elements
     are skipped. Cards and List views are only generated when the table
     has a <thead> to source keys from. */
  document.querySelectorAll('table:not([data-okt-bound])').forEach(function (table) {
    if (table.closest('.okt-table-scroll, .oku-tooltip, oku-chart, oku-diagram')) return;
    table.setAttribute('data-okt-bound', '1');

    // Column-resize handles. Each <th> in the thead gets a thin
    // right-edge grabber; on drag we apply explicit widths via a
    // <colgroup> + switch the table to table-layout: fixed so the
    // browser honours them. Auto-layout stays until the FIRST drag
    // — pages where the natural sizing is fine never pay the cost.
    (function wireColResize() {
      var ths = Array.prototype.slice.call(table.querySelectorAll('thead th'));
      if (!ths.length) return;
      // Build colgroup so dragged widths have a stable place to live.
      var existingColgroup = table.querySelector('colgroup');
      if (!existingColgroup) {
        var cg = document.createElement('colgroup');
        ths.forEach(function () { cg.appendChild(document.createElement('col')); });
        table.insertBefore(cg, table.firstChild);
      }
      ths.forEach(function (th, idx) {
        if (th.querySelector(':scope > .okt-col-resize')) return;
        // Make th a positioning context for the absolute handle.
        // Both `relative` and `sticky` qualify; only step in when the
        // cell is `static` (CSS default). Overriding sticky→relative
        // here would silently kill the sticky-header behaviour the
        // CSS already wires for every thead th.
        var pos = getComputedStyle(th).position;
        if (pos === 'static') th.style.position = 'relative';
        var handle = document.createElement('span');
        handle.className = 'okt-col-resize';
        handle.setAttribute('aria-hidden', 'true');
        th.appendChild(handle);
        var dragging = false, startX = 0, startW = 0, col;
        handle.addEventListener('mousedown', function (ev) {
          ev.preventDefault();
          dragging = true;
          startX = ev.clientX;
          startW = th.getBoundingClientRect().width;
          col = table.querySelectorAll('colgroup col')[idx];
          table.classList.add('okt-table-resizing');
          table.style.tableLayout = 'fixed';
          if (col && !col.style.width) col.style.width = startW + 'px';
        });
        window.addEventListener('mousemove', function (ev) {
          if (!dragging) return;
          var dx = ev.clientX - startX;
          var w = Math.max(48, startW + dx);
          if (col) col.style.width = w + 'px';
        });
        window.addEventListener('mouseup', function () {
          if (!dragging) return;
          dragging = false;
          table.classList.remove('okt-table-resizing');
        });
      });
    })();

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
    wrap.className = 'okt-table-wrap';
    wrap.dataset.view = 'table';

    var ctrl = document.createElement('div');
    ctrl.className = 'okt-table-controls';
    // Filter input on the left, stats counter immediately after it
    // (the two are read together: "I filtered, here is what remains").
    // View order: Table → List → Cards. Stats text is purely numeric
    // ("5" or "3/5") so the visual language stays neutral across doc
    // languages.
    var filterInputHTML = canPivot ? (
      '<label class="okt-filter">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.6" y2="16.6"/></svg>' +
        '<input type="search" placeholder="Filter…" aria-label="Filter table rows">' +
      '</label>'
    ) : '';
    var statsHTML = canPivot ? '<span class="okt-stats" aria-live="polite"></span>' : '';
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
      // No visible 'Group:' label — the dropdown's first option says
      // "— no grouping —" and the aria-label gives screen readers
      // the context. Saves toolbar width on narrow viewports.
      groupByHTML =
        '<label class="okt-groupby">' +
          '<select class="okt-groupby-select" aria-label="Group by column">' + opts.join('') + '</select>' +
        '</label>';
    }
    // Compact icon-only view toggle. Each button keeps its accessible
    // label (aria-label + title) so screen readers and tooltips
    // describe what each pivot does — only the visual chrome is
    // tighter, freeing horizontal space the older Table / List /
    // Cards / Board word-buttons consumed on narrow viewports.
    var VIEW_ICONS = {
      // Table: classic grid rows + cols.
      table: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2" width="12" height="12" rx="1.5"/><line x1="2" y1="6" x2="14" y2="6"/><line x1="2" y1="10" x2="14" y2="10"/><line x1="8" y1="2" x2="8" y2="14"/></svg>',
      // List: stacked horizontal lines (with bullet dots).
      list:  '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="3" cy="4" r="1" fill="currentColor"/><line x1="6" y1="4" x2="14" y2="4"/><circle cx="3" cy="8" r="1" fill="currentColor"/><line x1="6" y1="8" x2="14" y2="8"/><circle cx="3" cy="12" r="1" fill="currentColor"/><line x1="6" y1="12" x2="14" y2="12"/></svg>',
      // Cards: 2×2 grid of soft-rounded tiles.
      cards: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2" width="5.5" height="5.5" rx="1"/><rect x="8.5" y="2" width="5.5" height="5.5" rx="1"/><rect x="2" y="8.5" width="5.5" height="5.5" rx="1"/><rect x="8.5" y="8.5" width="5.5" height="5.5" rx="1"/></svg>',
      // Board: three vertical lanes (kanban).
      board: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2" width="3.5" height="12" rx="1"/><rect x="6.25" y="2" width="3.5" height="9" rx="1"/><rect x="10.5" y="2" width="3.5" height="6" rx="1"/></svg>',
    };
    function viewBtnHTML(key, label, isActive) {
      return '<button data-view="' + key + '" type="button" class="okt-view-btn' +
        (isActive ? ' active' : '') + '" aria-pressed="' + (isActive ? 'true' : 'false') +
        '" aria-label="' + label + ' view" title="' + label + ' view">' +
        VIEW_ICONS[key] + '</button>';
    }
    var viewBtns = canPivot ? (
      '<span class="okt-view-group" role="group" aria-label="View">' +
        viewBtnHTML('table', 'Table', true) +
        viewBtnHTML('list',  'List',  false) +
        viewBtnHTML('cards', 'Cards', false) +
        viewBtnHTML('board', 'Board', false) +
      '</span>' +
      '<span class="okt-ctrl-sep" aria-hidden="true"></span>'
    ) : '';
    // Order: filter → stats → gear → expand. The gear opens the
    // configuration popover (group-by, view mode, multi-column sort,
    // per-column filters). Filter + stats stay inline for instant
    // interaction; configuration knobs move into the popover so the
    // resting toolbar is two affordances, not seven.
    var gearBtnHTML = canPivot
      ? '<button data-cfg type="button" title="Configure table — group, view, sort, filter" aria-label="Configure table">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>' +
        '</button>'
      : '';
    // View-buttons and group-by select stay in ctrl so the existing
    // wiring binds to live DOM nodes. They're visually hidden in
    // resting state (CSS .okt-config-stashed) and physically moved
    // into the popover on gear click, then moved back on close —
    // same nodes, same listeners.
    // Visual order after CSS reflow: filter · stats · | · gear · expand.
    // The separator marker carries no semantic role; CSS draws the
    // 1px divider between the data-shaping controls (filter / stats)
    // and the chart-side affordances (gear / expand).
    // Charts have a "Copy data (TSV)" button; tables deserve the same.
    // Reads the visible <tr>'s cells (skipping group headers), tabs
    // between cells, newlines between rows, prepends the <thead>
    // labels — paste-ready into a spreadsheet or scratch doc.
    var copyBtnHTML =
      '<button data-copy type="button" title="Copy data (TSV)" aria-label="Copy data as TSV">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>' +
      '</button>';

    ctrl.innerHTML =
      filterInputHTML +
      statsHTML +
      '<span class="okt-ctrl-sep-after" aria-hidden="true"></span>' +
      copyBtnHTML +
      gearBtnHTML +
      '<button data-expand type="button" aria-pressed="false" title="Toggle full-width / fit to column">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="4 14 4 20 10 20"/><polyline points="20 10 20 4 14 4"/><line x1="14" y1="10" x2="20" y2="4"/><line x1="10" y1="14" x2="4" y2="20"/></svg>' +
      '</button>' +
      // Stashed area — group-by + view-toggle live here at rest but
      // visually hidden; the popover moves them into itself when open.
      '<span class="okt-config-stashed" hidden>' + viewBtns + groupByHTML + '</span>';

    var scroll = document.createElement('div');
    scroll.className = 'okt-table-scroll';

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
      cards.className = 'okt-table-cards';
      wrap.appendChild(cards);
      var list = document.createElement('div');
      list.className = 'okt-table-list';
      wrap.appendChild(list);
      var board = document.createElement('div');
      board.className = 'okt-table-board';
      wrap.appendChild(board);

      // State
      // Multi-column sort stack: [{ col, dir }, ...]. Click toggles
      // the primary (replaces stack). Shift-click adds/toggles a
      // secondary so the reader can sort by, e.g. owner asc + days
      // desc. Empty = source order.
      var sortStack = [];
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

      /* Per-column filter — separate from the global text filter and
         from the chip-rack filter. Map of col-index → substring; row
         passes if every active per-column filter matches its cell. */
      var columnFilters = {};
      function rowMatchesColumnFilters(e) {
        for (var col in columnFilters) {
          if (!Object.prototype.hasOwnProperty.call(columnFilters, col)) continue;
          var needle = (columnFilters[col] || '').trim().toLowerCase();
          if (!needle) continue;
          var cellText = stripHtml(e.cells[+col] || '').toLowerCase();
          if (cellText.indexOf(needle) === -1) return false;
        }
        return true;
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

      function hasActiveColumnFilters() {
        for (var col in columnFilters) {
          if (!Object.prototype.hasOwnProperty.call(columnFilters, col)) continue;
          if ((columnFilters[col] || '').trim()) return true;
        }
        return false;
      }
      function entriesMatchingFilter() {
        var entries = buildEntries();
        if (!filterText && !hasActiveChips() && !hasActiveColumnFilters()) return entries;
        var needle = filterText ? filterText.toLowerCase() : '';
        // Keep groups whose subsequent rows have at least one match.
        var visible = entries.map(function (e) {
          if (e.type === 'row') {
            return rowMatchesText(e, needle) && rowMatchesChips(e) && rowMatchesColumnFilters(e);
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
        if (!sortStack.length) return visible;
        // Sort rows within each group block; preserve group order.
        var out = [];
        var bucket = [];
        function compareCells(a, b) {
          for (var s = 0; s < sortStack.length; s++) {
            var entry = sortStack[s];
            var av = stripHtml(a.cells[entry.col] || '');
            var bv = stripHtml(b.cells[entry.col] || '');
            var nA = parseFloat(av), nB = parseFloat(bv);
            var numeric = !isNaN(nA) && !isNaN(nB) &&
                          /^-?\$?[\d.,%]+\s*$/.test(av) && /^-?\$?[\d.,%]+\s*$/.test(bv);
            var cmp = numeric ? (nA - nB) : av.toLowerCase().localeCompare(bv.toLowerCase());
            if (cmp !== 0) return entry.dir * cmp;
          }
          return 0;
        }
        function flush() {
          bucket.sort(compareCells);
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
        var chev = cell.querySelector(':scope > .okt-group-chevron');
        if (!chev) {
          chev = document.createElement('span');
          chev.className = 'okt-group-chevron';
          chev.setAttribute('role', 'button');
          chev.setAttribute('aria-label', 'Toggle group');
          chev.setAttribute('tabindex', '0');
          chev.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 8 10 12 6"/></svg>';
          cell.insertBefore(chev, cell.firstChild);
          chev.addEventListener('click', function (ev) { ev.stopPropagation(); toggleGroup(e); });
          chev.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleGroup(e); }
          });
          tr.classList.add('okt-collapsible');
          tr.addEventListener('click', function (ev) {
            // Avoid double-fire when the chevron itself was the target.
            if (ev.target.closest('.okt-group-chevron')) return;
            toggleGroup(e);
          });
        }
        // Count badge sits between chevron and the author title so the
        // numbers line up at the same x across all group rows.
        var badge = cell.querySelector(':scope > .okt-group-count');
        if (!badge) {
          badge = document.createElement('span');
          badge.className = 'okt-group-count';
          cell.insertBefore(badge, chev.nextSibling);
        }
        badge.textContent = fmtGroupCount(n);
        var collapsed = isGroupCollapsed(e);
        tr.classList.toggle('okt-collapsed', collapsed);
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
        h.className = cls + ' okt-collapsible';
        var chev = document.createElement('span');
        chev.className = 'okt-group-chevron';
        chev.setAttribute('role', 'button');
        chev.setAttribute('aria-label', 'Toggle group');
        chev.setAttribute('tabindex', '0');
        chev.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 8 10 12 6"/></svg>';
        var title = document.createElement('span');
        title.className = 'okt-group-title';
        title.innerHTML = e.title;
        var badge = document.createElement('span');
        badge.className = 'okt-group-count';
        badge.textContent = fmtGroupCount(count);
        // Count badge sits second (chevron, count, title) so the
        // numbers line up at the same x across rows in cards/list view.
        h.appendChild(chev);
        h.appendChild(badge);
        h.appendChild(title);
        var collapsed = isGroupCollapsed(e);
        h.classList.toggle('okt-collapsed', collapsed);
        chev.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        chev.addEventListener('click', function (ev) { ev.stopPropagation(); toggleGroup(e); });
        chev.addEventListener('keydown', function (ev) {
          if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleGroup(e); }
        });
        h.addEventListener('click', function (ev) {
          if (ev.target.closest('.okt-group-chevron')) return;
          toggleGroup(e);
        });
        return h;
      }

      function renderCards(visible, counts) {
        cards.innerHTML = '';
        var skip = false;
        visible.forEach(function (e) {
          if (e.type === 'group') {
            cards.appendChild(makeGroupHeader('div', 'okt-cards-group', e, counts.perGroup.get(e) || 0));
            skip = isGroupCollapsed(e);
            return;
          }
          if (skip) return;
          var card = document.createElement(e.iv.href ? 'a' : 'div');
          card.className = 'okt-card';
          applyRowInteractivity(card, e.iv);
          e.cells.forEach(function (cell, i) {
            if (!headers[i]) return;
            var r = document.createElement('div');
            r.className = 'okt-card-row';
            r.innerHTML =
              '<span class="okt-card-key">' + headers[i] + '</span>' +
              '<span class="okt-card-val">' + cell + '</span>';
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
            list.appendChild(makeGroupHeader('h4', 'okt-list-group', e, counts.perGroup.get(e) || 0));
            skip = isGroupCollapsed(e);
            return;
          }
          if (skip) return;
          /* Each row becomes its own 2-col <table class="okt-list-card">.
             First column = header (<th scope="row">), second column = cell
             value (<td>). Makes the list view literally tabular per item
             rather than a styled definition list. */
          var inner = document.createElement('table');
          inner.className = 'okt-list-card';
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
            a.className = 'okt-list-row';
            applyRowInteractivity(a, e.iv);
            a.appendChild(inner);
            list.appendChild(a);
          } else if (e.iv.onclick || e.iv.role === 'button') {
            var btn = document.createElement('div');
            btn.className = 'okt-list-row';
            applyRowInteractivity(btn, e.iv);
            btn.appendChild(inner);
            list.appendChild(btn);
          } else {
            var wrapEl = document.createElement('div');
            wrapEl.className = 'okt-list-row okt-list-row-static';
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
          lane.className = 'okt-board-lane';
          var head = document.createElement('div');
          head.className = 'okt-board-lane-head';
          if (key === '__all__') {
            head.innerHTML = '<span class="okt-board-lane-title">All</span>' +
                             '<span class="okt-board-lane-count">' + rows.length + '</span>';
          } else {
            var title = (key.label || key.title || key.key || '').toString();
            head.innerHTML =
              '<span class="okt-board-lane-title">' + escapeXml(title) + '</span>' +
              '<span class="okt-board-lane-count">' + rows.length + '</span>';
          }
          lane.appendChild(head);
          var laneBody = document.createElement('div');
          laneBody.className = 'okt-board-lane-body';
          rows.forEach(function (e) {
            var card = document.createElement(e.iv.href ? 'a' : 'div');
            card.className = 'okt-board-card';
            applyRowInteractivity(card, e.iv);
            e.cells.forEach(function (cell, i) {
              if (!headers[i]) return;
              var r = document.createElement('div');
              r.className = 'okt-board-card-row';
              r.innerHTML =
                '<span class="okt-board-card-key">' + headers[i] + '</span>' +
                '<span class="okt-board-card-val">' + cell + '</span>';
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
      var statsEl = ctrl.querySelector('.okt-stats');
      function updateStats(counts) {
        if (!statsEl) return;
        var n = counts.visibleRows;
        var filtering = !!filterText || hasActiveChips();
        // Bare numerals: "N" at rest, "N/M" while filtering, "0/M" when
        // nothing matches. Language-neutral so the doc can be TR or EN
        // without touching the kit.
        if (!filtering) {
          statsEl.textContent = String(n);
          statsEl.classList.remove('okt-stats-filtered', 'okt-stats-empty');
        } else {
          statsEl.textContent = n + '/' + rowCount;
          statsEl.classList.add('okt-stats-filtered');
          statsEl.classList.toggle('okt-stats-empty', n === 0);
        }
      }

      function updateSortIndicators() {
        var ths = table.querySelectorAll('thead th');
        for (var i = 0; i < ths.length; i++) {
          var th = ths[i];
          th.removeAttribute('aria-sort');
          th.classList.remove('okt-sort-asc', 'okt-sort-desc');
          th.removeAttribute('data-sort-rank');
          var stackIdx = -1;
          for (var s = 0; s < sortStack.length; s++) {
            if (sortStack[s].col === i) { stackIdx = s; break; }
          }
          if (stackIdx < 0) continue;
          var entry = sortStack[stackIdx];
          if (entry.dir === 1) {
            th.classList.add('okt-sort-asc');
            th.setAttribute('aria-sort', 'ascending');
          } else if (entry.dir === -1) {
            th.classList.add('okt-sort-desc');
            th.setAttribute('aria-sort', 'descending');
          }
          // Rank badge only meaningful when more than one column is
          // active — keeps the indicator quiet for the common case.
          if (sortStack.length > 1) th.setAttribute('data-sort-rank', String(stackIdx + 1));
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
        chipsRack.className = 'okt-chips';
        Object.keys(chipCols)
          .sort(function (a, b) { return (+a) - (+b); })
          .forEach(function (colS) {
            var col = +colS;
            /* Two-cell layout: column 1 is the label cell, column 2 is
               the chips cell. Wrapping the chips in their own row makes
               the parent grid lay them out as a clean two-column table
               regardless of how many chips a column declares. */
            var grp = document.createElement('div');
            grp.className = 'okt-chip-group';
            grp.dataset.col = colS;
            var lbl = document.createElement('span');
            lbl.className = 'okt-chip-label';
            lbl.textContent = chipColLabels[col] + ':';
            grp.appendChild(lbl);
            var row = document.createElement('div');
            row.className = 'okt-chip-row';
            grp.appendChild(row);
            chipCols[col].values.forEach(function (v) {
              var btn = document.createElement('button');
              btn.type = 'button';
              btn.className = 'okt-chip';
              btn.dataset.value = v;
              btn.setAttribute('aria-pressed', 'false');
              var valSpan = document.createElement('span');
              valSpan.className = 'okt-chip-val';
              valSpan.textContent = v;
              var cntSpan = document.createElement('span');
              cntSpan.className = 'okt-chip-count';
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
            clr.className = 'okt-chip-clear';
            clr.textContent = '×';
            clr.setAttribute('aria-label', 'Clear');
            clr.addEventListener('click', function () {
              chipsState[col].clear();
              grp.querySelectorAll('.okt-chip').forEach(function (b) {
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
        chipsRack.querySelectorAll('.okt-chip-group').forEach(function (grp) {
          var col = +grp.dataset.col;
          grp.querySelectorAll('.okt-chip').forEach(function (btn) {
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
            var cnt = btn.querySelector('.okt-chip-count');
            if (cnt) cnt.textContent = String(count);
            btn.classList.toggle('okt-chip-empty', count === 0);
          });
        });
      }

      // Bind sort on every <th> in <thead>.
      var ths = table.querySelectorAll('thead th');
      Array.prototype.forEach.call(ths, function (th, idx) {
        th.classList.add('okt-sortable');
        if (!th.hasAttribute('tabindex')) th.setAttribute('tabindex', '0');
        if (!th.hasAttribute('role'))     th.setAttribute('role', 'button');
        function findStackIdx() {
          for (var s = 0; s < sortStack.length; s++) {
            if (sortStack[s].col === idx) return s;
          }
          return -1;
        }
        function toggleSort(shift) {
          var existing = findStackIdx();
          if (shift) {
            // Shift-click: add or cycle a secondary sort. Each
            // subsequent column appends to the stack; clicking an
            // already-stacked column toggles asc → desc → remove.
            if (existing < 0) {
              sortStack.push({ col: idx, dir: 1 });
            } else if (sortStack[existing].dir === 1) {
              sortStack[existing].dir = -1;
            } else {
              sortStack.splice(existing, 1);
            }
          } else {
            // Plain click: collapse the stack to just this column,
            // cycling its direction independently of any prior state.
            if (existing < 0 || sortStack.length > 1) {
              sortStack = [{ col: idx, dir: 1 }];
            } else if (sortStack[0].dir === 1) {
              sortStack = [{ col: idx, dir: -1 }];
            } else {
              sortStack = [];
            }
          }
          render();
        }
        th.addEventListener('click', function (e) { toggleSort(e.shiftKey); });
        th.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSort(e.shiftKey); }
        });
      });

      // Bind filter input.
      var filterInput = ctrl.querySelector('.okt-filter input');
      if (filterInput) {
        filterInput.addEventListener('input', function () {
          filterText = filterInput.value;
          render();
        });
      }

      // Group-by select.
      var groupBySelect = ctrl.querySelector('.okt-groupby-select');
      if (groupBySelect) {
        groupBySelect.addEventListener('change', function () {
          groupByCol = groupBySelect.value;
          // Different grouping → previously-collapsed groups don't carry
          // over by name. Start each fresh slice expanded.
          collapsedGroups.clear();
          render();
        });
      }

      // Expose state hooks the table-config popover can call into:
      // column-filter mutations and a render trigger. Lives on the
      // wrap so the body-level popover finds them via the wrap it
      // anchors to.
      wrap.__oktState = {
        columnFilters: columnFilters,
        headers: headers.map(function (h) { return stripHtml(h); }),
        render: render,
      };
      // Gear button → open the table-config popover. The popover
       // moves the stashed view-toggle + group-by selects into
       // itself, leaves a marker, and on close moves them back —
       // same DOM nodes so the wiring keeps working.
      var gearBtn = ctrl.querySelector('button[data-cfg]');
      if (gearBtn) {
        gearBtn.addEventListener('click', function () {
          __okuTableConfig.toggle(wrap, gearBtn);
        });
      }
      // View-toggle handler — CSS-driven via wrap.dataset.view.
      function setView(view) {
        wrap.dataset.view = view;
        ctrl.querySelectorAll('[data-view]').forEach(function (b) {
          var active = b.getAttribute('data-view') === view;
          b.classList.toggle('active', active);
          b.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
      }
      ctrl.querySelectorAll('[data-view]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          setView(btn.getAttribute('data-view'));
        });
      });
      // Author-pinned initial view via `block.view` → table[data-default-view].
      // Only honoured when the requested view is one of the valid options.
      var pinned = table.getAttribute('data-default-view');
      if (pinned && ctrl.querySelector('[data-view="' + pinned + '"]')) {
        setView(pinned);
        // Board view needs a group column to be meaningful; when the
        // table didn't author groups but has a column with
        // data-board-order, pivot on that column automatically.
        // Without this, the board collapses to a single "All" lane
        // and the boardOrder declaration is dead weight.
        if (pinned === 'board' && groupByCol === 'none') {
          var ths = table.querySelectorAll('thead th');
          for (var ti = 0; ti < ths.length; ti++) {
            if (ths[ti].getAttribute('data-board-order')) {
              groupByCol = String(ti);
              if (groupBySelect) groupBySelect.value = groupByCol;
              break;
            }
          }
        }
      }

      render(); // initial: identity sort, no filter — preserves source order
    }

    /* Expand-to-fullscreen. Same affordance as image / chart / diagram:
       click moves the live wrap into the shared lightbox overlay; close
       moves it back. The wrap keeps its event listeners, filter state,
       and selected view, so the lightbox is a roomy mirror of the
       in-page table, not a static snapshot.
       Default in-page shape is contained + horizontally scrollable —
       no auto-bleed (that visual was heavy and clashed with the sidebar
       grid). The user opts in to fullscreen explicitly via this button. */
    // Copy data (TSV) — mirrors charts' "Copy data (TSV)" affordance.
    // Reads the current <thead> labels + every visible (non-hidden,
    // non-group-header) <tbody> row's textContent, tabs between cells,
    // newlines between rows. Hidden / filtered-out rows are skipped,
    // so the clipboard reflects what the user is actually looking at.
    var copyBtn = ctrl.querySelector('[data-copy]');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var headers = Array.prototype.map.call(
          table.querySelectorAll('thead th'),
          function (th) { return (th.textContent || '').trim().replace(/[\t\n\r]+/g, ' '); }
        );
        var rows = [headers.join('\t')];
        Array.prototype.forEach.call(
          table.querySelectorAll('tbody tr'),
          function (tr) {
            if (tr.classList.contains('group-header') ||
                tr.classList.contains('okt-row-hidden') ||
                tr.hidden) return;
            var cells = Array.prototype.map.call(tr.cells, function (td) {
              return (td.textContent || '').trim().replace(/[\t\n\r]+/g, ' ');
            });
            if (cells.length) rows.push(cells.join('\t'));
          }
        );
        var tsv = rows.join('\n');
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(tsv).then(
            function () { copyBtn.classList.add('okt-flash-ok'); setTimeout(function () { copyBtn.classList.remove('okt-flash-ok'); }, 1200); },
            function () { copyBtn.classList.add('okt-flash-fail'); setTimeout(function () { copyBtn.classList.remove('okt-flash-fail'); }, 1200); }
          );
        } else {
          // Pre-clipboard-API fallback: select a hidden textarea + execCommand.
          var ta = document.createElement('textarea');
          ta.value = tsv;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand('copy'); } catch (e) { /* noop */ }
          document.body.removeChild(ta);
        }
      });
    }
    var expBtn = ctrl.querySelector('[data-expand]');
    if (expBtn) {
      expBtn.title = 'Expand to fullscreen';
      expBtn.setAttribute('aria-label', 'Expand to fullscreen');
      expBtn.addEventListener('click', function () {
        if (!window.__okuLightbox) return;
        if (wrap.dataset.fullscreen === '1') {
          // Second click while in lightbox: close it (mirrors the Esc /
          // backdrop / close-button paths).
          __okuLightbox.close();
          return;
        }
        var placeholder = document.createComment('okt-table-home');
        wrap.parentNode.insertBefore(placeholder, wrap);
        wrap.dataset.fullscreen = '1';
        __okuLightbox.open(wrap, {
          title: 'Expanded table',
          // Tables manage their own scroll containers; the pan/zoom
          // wrapper would conflict with cell selection and sort
          // headers. Keep the lightbox passive here.
          panZoom: false,
          onClose: function () {
            delete wrap.dataset.fullscreen;
            if (placeholder.parentNode) {
              placeholder.parentNode.replaceChild(wrap, placeholder);
            }
          }
        });
      });
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
       console look for: [oku] kit boot · build=...
   The console.info emits once per page load; cheap insurance. */
var __okuKitBuild = '2026-05-18-r10';

var __okuDocsRoot = (function () {
  // Explicit override wins. Use this for pages that live outside the
  // canonical docs/ tree (internal triage, examples, sandbox) but want
  // to share the same site-manifest / kit.json / glossary as the docs.
  // Value is resolved against the page URL so relative paths work.
  var metaOverride = document.querySelector('meta[name="oku-docs-root"]');
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
    '[oku] kit boot · build=' + __okuKitBuild +
    ' · docsRoot=' + __okuDocsRoot +
    ' · authToken=' + (window.__okuWithAuth && window.__okuWithAuth('x') !== 'x' ? 'yes' : 'no')
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
  if (!pre.classList.contains('okt-line-numbered')) return;
  if (code.querySelector(':scope > .okt-code-line')) return; // already wrapped, intact
  _hdtWrapCodeLines(code);
  // After line wrap, walk each per-line `.token.script` /
  // `.token.style` shard and re-tokenise its text contents with the
  // embedded language. The wrap reduces multi-line elements to one
  // plain-text clone per line, so each shard is single-line and can
  // be tokenised independently. Running before wrap would lose the
  // nested tokens — the multi-line-clone path uses `textContent =`
  // which strips descendant spans.
  _hdtHighlightNestedLanguages(code);
  pre.setAttribute('data-okt-lines-wrapped', '1');
  // Clear any stale fold-marker state inside per-line cells so a fresh
  // detection pass attaches handlers to the current line's marker.
  Array.prototype.forEach.call(code.querySelectorAll(':scope > .okt-code-line > .okt-fold-marker'), function (marker) {
    marker.classList.remove('okt-foldable', 'okt-folded');
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
    var pill = pre.querySelector(':scope > .okt-code-lang');
    if (!pill) {
      pill = document.createElement('span');
      pill.className = 'okt-code-lang';
      pill.setAttribute('aria-hidden', 'true');
      pre.appendChild(pill);
    }
    pill.textContent = lang;
  }
  if (/^(js|javascript|ts|typescript|jsx|tsx|json|json5|css|scss|less)$/.test(lang)) {
    // Skip fold detection on short blocks. A 3-line shell command
    // doesn't benefit from fold markers in the gutter — the chrome
    // costs more attention than the affordance pays back. Threshold
    // matches the user's design-review proposal ("fold markers only
    // for ≥ 8-line blocks").
    var lineCount = code.querySelectorAll(':scope > .okt-code-line').length;
    if (lineCount >= 8) {
      var folds = _hdtDetectBraceFolds(code);
      if (folds.length) _hdtApplyFolds(pre, code, folds);
    }
  }
}

function _hdtHighlightNestedLanguages(code) {
  if (!window.Prism) return;
  // Two shapes to handle:
  //   (a) explicit `class="language-foo"` spans created by markdown
  //       fences inside markdown, or by author-supplied HTML;
  //   (b) Prism's `markup` grammar emitting `.token.script` (JS) and
  //       `.token.style` (CSS) for <script> / <style> contents inside
  //       a language-markup block. These do NOT carry a language-*
  //       class; the lazy autoloader can't see them.
  var targets = [];
  Array.prototype.forEach.call(code.querySelectorAll('[class*="language-"]'), function (el) {
    if (el.tagName === 'CODE') return;
    // Already tokenised? — has at least one .token child element.
    for (var j = 0; j < el.children.length; j++) {
      if (el.children[j].classList && el.children[j].classList.contains('token')) return;
    }
    var m = el.className.match(/language-([\w-]+)/);
    if (!m) return;
    var nestedLang = m[1].toLowerCase();
    if (/^(markup|html|plaintext|text|none)$/.test(nestedLang)) return;
    targets.push({ el: el, lang: nestedLang });
  });
  Array.prototype.forEach.call(code.querySelectorAll('.token.script'), function (el) {
    if (el.querySelector('.token')) return; // already tokenised
    targets.push({ el: el, lang: 'javascript' });
  });
  Array.prototype.forEach.call(code.querySelectorAll('.token.style'), function (el) {
    if (el.querySelector('.token')) return;
    targets.push({ el: el, lang: 'css' });
  });
  targets.forEach(function (t) {
    var target = t.el, langName = t.lang;
    function rehl() {
      try {
        var grammar = window.Prism.languages[langName];
        if (!grammar) return;
        // Use Prism.highlight on the raw text so we don't re-trigger
        // the outer block's `complete` hook (recursion risk).
        var raw = target.textContent;
        target.innerHTML = window.Prism.highlight(raw, grammar, langName);
      } catch (e) {}
    }
    if (window.Prism.languages && window.Prism.languages[langName]) {
      rehl();
      return;
    }
    if (window.Prism.plugins && window.Prism.plugins.autoloader) {
      try {
        window.Prism.plugins.autoloader.loadLanguages([langName], rehl);
      } catch (e) {}
    }
  });
}

/* ============ Code-block line wrap + brace fold (module scope) ============ *
 * After Prism highlights, we walk the <code>'s child tree and group
 * everything by newlines into one <span class="okt-code-line"> per
 * source line. Each line includes its own trailing '\n' so collapsing
 * a line via display:none also removes the blank gap it would leave
 * behind. Prism's token spans survive: tokens entirely within a line
 * are moved as-is; tokens that straddle newlines (multi-line strings,
 * block comments) are split into per-line clones — same className
 * preserves coloring across the split.
 * ------------------------------------------------------------------- */
function _hdtWrapCodeLines(code) {
  // Each .okt-code-line is a grid row with three cells:
  //   [.okt-code-ln (number)]  [.okt-fold-marker]  [.okt-code-content]
  //
  // Numbers + fold markers ride with their code line — when word-wrap
  // is enabled and a logical line spans multiple visual rows, the
  // number stays at the row's top (align-self: start) while the
  // content cell grows to its wrapped height. The absolute-positioned
  // gutter the previous design used couldn't do this (numbers froze
  // at the same y while wrapped content pushed code below).
  function makeLine(lineIdx) {
    var line = document.createElement('span');
    line.className = 'okt-code-line';
    line.setAttribute('data-line', String(lineIdx));
    var num = document.createElement('span');
    num.className = 'okt-code-ln';
    // Number rendered via ::before { content: attr(data-ln) } so it
    // does NOT contribute to code.textContent. Prism's autoloader can
    // fire `complete` twice (once before the language module arrives,
    // once after); the second pass re-reads textContent and would
    // otherwise see "1uv …" / "2# …" / "3htm …" baked in.
    num.setAttribute('data-ln', String(lineIdx));
    num.setAttribute('aria-hidden', 'true');
    var fold = document.createElement('span');
    fold.className = 'okt-fold-marker';
    fold.setAttribute('aria-hidden', 'true');
    var content = document.createElement('span');
    content.className = 'okt-code-content';
    line.appendChild(num);
    line.appendChild(fold);
    line.appendChild(content);
    return line;
  }

  var lines = [makeLine(1)];
  // Cache the content cell of the current line. Refreshed on newline().
  // Avoids a querySelector per text-segment / token append — which on
  // a 200-line Prism-tokenised block runs into the thousands of calls.
  var activeContent = lines[0].lastChild; // the .okt-code-content node
  function pushChar(s) { activeContent.appendChild(document.createTextNode(s)); }
  function newline() {
    // Trailing newline lives in the CURRENT line so display:none also
    // hides the blank that would otherwise remain.
    activeContent.appendChild(document.createTextNode('\n'));
    var nextLine = makeLine(lines.length + 1);
    lines.push(nextLine);
    activeContent = nextLine.lastChild;
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
        activeContent.appendChild(node.cloneNode(true));
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
            activeContent.appendChild(clone);
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
  var lines = code.querySelectorAll('.okt-code-line');
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
  var lines = code.querySelectorAll(':scope > .okt-code-line');
  folds.forEach(function (f) {
    var line = lines[f.start];
    if (!line) return;
    var marker = line.querySelector(':scope > .okt-fold-marker');
    if (!marker) return;
    marker.classList.add('okt-foldable');
    marker.setAttribute('role', 'button');
    marker.setAttribute('tabindex', '0');
    marker.setAttribute('aria-expanded', 'true');
    marker.dataset.foldStart = String(f.start);
    marker.dataset.foldEnd = String(f.end);
  });
  if (pre.dataset.hdtFoldDelegated === '1') return;
  pre.dataset.hdtFoldDelegated = '1';
  function handle(target) {
    if (!target.classList.contains('okt-foldable')) return;
    var start = +target.dataset.foldStart;
    var end = +target.dataset.foldEnd;
    if (!(end > start)) return;
    var willCollapse = !target.classList.contains('okt-folded');
    target.classList.toggle('okt-folded', willCollapse);
    target.setAttribute('aria-expanded', willCollapse ? 'false' : 'true');
    var liveCode = pre.querySelector(':scope > code');
    var liveLines = liveCode ? liveCode.querySelectorAll(':scope > .okt-code-line') : [];
    for (var i = start + 1; i < end; i++) {
      if (liveLines[i]) liveLines[i].classList.toggle('okt-line-hidden', willCollapse);
    }
    pre.classList.toggle('okt-has-folds', !!pre.querySelector('.okt-fold-marker.okt-folded'));
  }
  code.addEventListener('click', function (e) {
    var t = e.target.closest('.okt-fold-marker.okt-foldable');
    if (t) handle(t);
  });
  code.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var t = e.target.closest('.okt-fold-marker.okt-foldable');
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
  window.addEventListener('oku:rendered', update);

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
  if (document.__okuBindAttached) return;
  document.__okuBindAttached = true;

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

/* ============ Live-reload (only when served via `oku serve`) ============ *
 * Opens an EventSource against /__reload — a Server-Sent Events stream
 * that the dev server pushes a message into whenever a watched file
 * changes. On message, the tab reloads. Only attempted when the page is
 * loaded from localhost/127.0.0.1 so production sites never try.
 * --------------------------------------------------------------------------- */
(function () {
  if (typeof window === 'undefined') return;
  var h = window.location && window.location.hostname;
  if (h !== 'localhost' && h !== '127.0.0.1' && h !== '::1') return;
  if (window.__okuReloadAttached) return;
  window.__okuReloadAttached = true;
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
var __okuTooltip = (function () {
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
    t.className = 'oku-tooltip';
    var html = '<div class="okt-body">' + body + '</div>';
    if (lang) html += '<span class="okt-lang">' + lang + '</span>';
    if (link) html += '<div class="okt-link"><a href="' + link + '" target="_blank" rel="noopener">Learn more →</a></div>';
    html += '<span class="okt-pin-hint">click to pin</span>';
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
    if (!e.target.closest('.oku-tooltip, [data-oku-tooltip-trigger]')) hideImmediate();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && active && active.pinned) hideImmediate();
  });

  return { attach: attach, hide: hideImmediate };
})();

/* ============ kit.json loader (multi-domain glossary + ext-refs) ============ */
var __okuKit = (function () {
  var kit = { glossary: {}, extrefs: {}, lang: 'en', lang_fallback: ['en'], domains: [], personalization: [] };
  var loaded = false;
  var waiters = [];

  function load() {
    if (loaded) return Promise.resolve(kit);
    // Standalone build — if the build inlined a kit bundle, hydrate from it.
    var bundleTag = document.getElementById('__oku_kit_bundle__');
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
    if (document.getElementById('__oku_page__')) {
      loaded = true;
      waiters.forEach(function (w) { w(kit); });
      waiters = [];
      return Promise.resolve(kit);
    }
    // Project config lives at the docs root; domain files live in _kit/.
    var wa = (window.__okuWithAuth || function (u) { return u; });
    return fetch(wa(__okuDocsRoot + 'kit.json'), { cache: 'no-cache' })
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
            fetch(wa(__okuDocsRoot + '_kit/glossary/' + d + '.json'), { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .catch(function () { return null; })
              .then(function (j) {
                if (j && j.entries) kit.glossary[d] = j.entries;
              }),
            fetch(wa(__okuDocsRoot + '_kit/extrefs/' + d + '.json'), { cache: 'no-cache' })
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
          if (typeof __okuPersonalization !== 'undefined') {
            try { __okuPersonalization.init((data && data.personalization) || kit.personalization || []); }
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
 * Values persist in localStorage under oku-personalization. Code
 * blocks (and anywhere else the reader expects swap-in) get {{key}}
 * substrings replaced at runtime with <span class="okc-personalized">
 * wrappers. Hovering a personalized span shows which key it came from.
 *
 * Why this matters: Mintlify pioneered "set apiKey once, every snippet
 * on every page swaps to your values" — massively reduces tutorial
 * copy-paste friction. oku's no-build constraint means we do this
 * at runtime, not at build time; the localStorage-backed state is the
 * full extent of personalization (no accounts, no server, no SaaS).
 * --------------------------------------------------------------------- */
var __okuPersonalization = (function () {
  var STORAGE_KEY = 'oku-personalization';
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
    document.querySelectorAll('.okc-personalized').forEach(function (span) {
      var k = span.getAttribute('data-key');
      span.textContent = get(k);
    });
    // Walk likely containers — code blocks, snippets, kbd, and a generic
    // .okc-personalize-target opt-in for prose passages.
    var roots = document.querySelectorAll('pre, code, kbd, .okc-personalize-target');
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
          span.className = 'okc-personalized';
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
    window.addEventListener('oku:rendered', applyAll);
  }

  return { init: init, get: get, set: set, applyAll: applyAll };
})();
// Standalone builds inline the page but not the glossary; in that mode
// we render the term inline without a tooltip rather than mark every
// term as "unknown". Detected via the inline page-data script.
var __okuStandalone = function () {
  return !!document.getElementById('__oku_page__');
};

class GlossaryTerm extends HTMLElement {
  connectedCallback() {
    var self = this;
    this.setAttribute('data-oku-tooltip-trigger', '');
    this.classList.add('oku-gloss');
    __okuKit.whenReady().then(function () {
      var term = self.getAttribute('term') || self.textContent;
      var opts = { in: self.getAttribute('in') || undefined, lang: self.getAttribute('lang') || undefined };
      var r = __okuKit.resolveGlossary(term, opts);
      if (r) {
        self.setAttribute('data-def', r.hit.def || '');
        if (r.hit.link) self.setAttribute('data-link', r.hit.link);
        if (r.lang !== (opts.lang || __okuKit.state().lang)) {
          self.setAttribute('data-lang-shown', 'lang: ' + r.lang);
        }
        __okuTooltip.attach(self);
      } else if (__okuStandalone()) {
        // Standalone mode without inline glossary data — render text only.
        self.classList.remove('oku-gloss');
      } else {
        self.setAttribute('data-def', '<em>Unknown term:</em> ' + term);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('oku:warnings', {
          detail: [{ code: 'unknown-glossary-term', msg: 'No entry for "' + term + '"', level: 'warn' }]
        }));
        __okuTooltip.attach(self);
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

var __okuCiteIcons = {
  paper:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  rfc:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/></svg>',
  release: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
  blog:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>',
  other:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
};

function __okuCiteDomain(link) {
  if (!link) return '';
  try {
    var u = new URL(link, window.location.href);
    return u.hostname.replace(/^www\./, '');
  } catch (e) { return ''; }
}

function __okuCiteType(hit, element) {
  var type = (element.getAttribute('type') || hit.type || '').toLowerCase();
  if (__okuCiteIcons[type]) return type;
  // Infer from the link domain if not declared.
  var dom = __okuCiteDomain(hit.link || '');
  if (/arxiv|doi\.org|acm\.org|springer|sciencedirect|nature\.com|ieee/.test(dom)) return 'paper';
  if (/datatracker\.ietf|w3\.org|rfc-editor|tc39|whatwg/.test(dom))               return 'rfc';
  if (/github\.com\/.+\/releases|releases\.|changelog/.test((hit.link || '')))    return 'release';
  if (/blog|medium\.com|substack|dev\.to/.test(dom))                              return 'blog';
  return 'other';
}

function __okuBuildCitationBody(hit, name, element) {
  var type = __okuCiteType(hit, element);
  var icon = __okuCiteIcons[type] || __okuCiteIcons.other;
  var domain = __okuCiteDomain(hit.link || '');
  var author = element.getAttribute('author') || hit.author || hit.authors || '';
  var published = element.getAttribute('published') || hit.published || hit.date || '';

  var html = '<div class="okt-cite" data-cite-type="' + type + '">';
  html +=   '<div class="okt-cite-head">';
  html +=     '<span class="okt-cite-icon">' + icon + '</span>';
  html +=     '<span class="okt-cite-title">' + escapeXml(hit.name || name) + '</span>';
  html +=   '</div>';
  if (domain) {
    // Render the domain as a clickable link when a destination URL is
    // present. Previous behavior surfaced the URL as a code-chip pill
    // plus a redundant "Learn more →" row; the chip read as code and
    // doubled the click affordances. One link, clearly styled, is
    // enough.
    if (hit.link) {
      html += '<a class="okt-cite-domain" href="' + escapeXml(hit.link) +
              '" target="_blank" rel="noopener">' + escapeXml(domain) + ' ↗</a>';
    } else {
      html += '<div class="okt-cite-domain">' + escapeXml(domain) + '</div>';
    }
  }
  if (author || published) {
    html += '<div class="okt-cite-meta">';
    if (author)    html += '<span class="okt-cite-author">' + escapeXml(author) + '</span>';
    if (published) html += '<span class="okt-cite-date">' + escapeXml(published) + '</span>';
    html += '</div>';
  }
  if (hit.summary) html += '<div class="okt-cite-summary">' + hit.summary + '</div>';
  html += '</div>';
  return html;
}

class ExtRef extends HTMLElement {
  connectedCallback() {
    var self = this;
    this.setAttribute('data-oku-tooltip-trigger', '');
    this.classList.add('oku-extref');
    __okuKit.whenReady().then(function () {
      var name = self.getAttribute('name') || self.textContent;
      var opts = { in: self.getAttribute('in') || undefined, lang: self.getAttribute('lang') || undefined };
      var r = __okuKit.resolveExtRef(name, opts);
      if (r) {
        self.setAttribute('data-def', __okuBuildCitationBody(r.hit, name, self));
        // Tag the element itself with the resolved type so authors can
        // theme the inline cite-text (different underline per type).
        var type = __okuCiteType(r.hit, self);
        self.setAttribute('data-cite-type', type);
        // The destination URL is surfaced as a clickable link inside the
        // tooltip's citation card (see __okuBuildCitationBody). The
        // host <ext-ref> element itself is NOT a link — clicking it pins
        // the tooltip; the link inside the tooltip opens the source. A
        // single click action per element keeps the affordance honest.
        if (r.hit.link) {
          self.setAttribute('data-link', r.hit.link);
        }
        __okuTooltip.attach(self);
      } else if (__okuStandalone()) {
        self.classList.remove('oku-extref');
      } else {
        self.setAttribute('data-def', '<em>Unknown reference:</em> ' + name);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('oku:warnings', {
          detail: [{ code: 'unknown-ext-ref', msg: 'No entry for "' + name + '"', level: 'warn' }]
        }));
        __okuTooltip.attach(self);
      }
    });
  }
}

if (!customElements.get('ext-ref')) customElements.define('ext-ref', ExtRef);
// "<cite>" alias — same behavior as <ext-ref> so authors can use the
// semantically-correct HTML element when citing.
if (!customElements.get('oku-cite')) customElements.define('oku-cite', class extends ExtRef {});

/* ============ Shared chart palette helper ============
 * Resolves a series colour from either:
 *   * a named token (accent / warn / danger / success / muted) that
 *     maps to a top-level CSS variable, or
 *   * the rotating --series-N ramp (1..10) when the author didn't
 *     pin one. Renderers that have many series fall back via
 *     pickColor(series.color, seriesIdx).
 * --------------------------------------------------------------- */
var __okuChartPalette = {
  accent: 'var(--accent)',
  warn: 'var(--warning)',
  danger: 'var(--danger)',
  success: 'var(--success)',
  muted: 'var(--text-soft)'
};
function __okuPickColor(name, idx) {
  if (name && __okuChartPalette[name]) return __okuChartPalette[name];
  // Rotate through the 10-series ramp; CSS variables resolve to
  // the current theme's values at paint time.
  var i = ((idx || 0) % 10) + 1;
  return 'var(--series-' + i + ')';
}

/* ============ <oku-chart> Custom Element ============ *
 * Generic data-driven SVG chart. Scatter and line types.
 * Series data lives in a child <script type="application/json">.
 * For row-per-item horizontal bars, use the bar-chart block instead
 * (handled directly by the renderer for layout-stability reasons).
 * --------------------------------------------------------------- */
class OkuChart extends HTMLElement {
  connectedCallback() {
    // Guard against re-init when the host is moved (e.g., relocated
    // into the lightbox stage). connectedCallback fires on every
    // reparent; without this guard we'd wipe innerHTML and lose all
    // wired interactivity. The render only runs once per host.
    if (this._initialized) return;
    this._initialized = true;
    var dataNode = this.querySelector('script[type="application/json"]:not([data-extras])');
    var extrasNodes = this.querySelectorAll('script[data-extras]');
    var series = [];
    if (dataNode) {
      try { series = JSON.parse(dataNode.textContent || '[]'); } catch (e) { series = []; }
    }
    // Extras hold type-specific payloads that don't fit the `series`
    // shape — quadrant reference lines, donut slices, etc.
    var extras = {};
    Array.prototype.forEach.call(extrasNodes, function (n) {
      var key = n.getAttribute('data-extras');
      if (!key) return;
      try { extras[key] = JSON.parse(n.textContent || 'null'); } catch (e) { /* keep as undefined */ }
    });
    this._series   = series;
    this._extras   = extras;
    this._type     = this.getAttribute('type') || 'scatter';
    // Canonical-type → legacy-alias normalisation. The renderer.js
    // chart-block dispatcher does this same step before creating the
    // oku-chart element, but direct DOM creation (or any code that
    // sets type="plot"/"arc"/"bar" without going through the renderer)
    // would otherwise leave OkuChart's dispatcher without a matching
    // branch. Mirror the renderer.js logic so both entry points
    // converge on the same internal type.
    var _modeAttr = (this.getAttribute('mode') || '').toLowerCase();
    var _marksAttr = (this.getAttribute('marks') || '').toLowerCase();
    if (this._type === 'plot') {
      var marksList = _marksAttr ? _marksAttr.split(',').map(function (s) { return s.trim(); }) : ['dots'];
      if (marksList.indexOf('area') !== -1)      this._type = 'area';
      else if (marksList.indexOf('line') !== -1) this._type = 'line';
      else                                        this._type = 'scatter';
    } else if (this._type === 'arc') {
      this._type = _modeAttr === 'pie' ? 'pie' : 'donut';
    } else if (this._type === 'bar' && (_modeAttr === 'stacked' || _modeAttr === 'grouped')) {
      // Not actually rendered here (bar goes through renderer.js), but
      // keep the mapping consistent if someone reaches this branch.
      this._type = _modeAttr === 'stacked' ? 'stacked-bar' : 'grouped-bar';
    }
    this._title    = this.getAttribute('title') || '';
    this._xLabel   = this.getAttribute('x-label') || '';
    this._yLabel   = this.getAttribute('y-label') || '';
    this._xScale   = (this.getAttribute('x-scale') || 'linear').toLowerCase();
    this._yScale   = (this.getAttribute('y-scale') || 'linear').toLowerCase();
    // Chart-type unification overrides — read directly from the host
    // attributes the renderer sets when an author opts into canonical
    // shapes (type=plot/arc/bar) or overrides an alias preset (e.g.
    // type=pie + arc.end=270 → a 3/4 pie). All optional; undefined
    // falls back to the legacy renderer behaviour for the type.
    var marksAttr = this.getAttribute('marks');
    this._marks = marksAttr ? marksAttr.split(',').map(function (s) { return s.trim(); }) : null;
    this._mode = this.getAttribute('mode') || null;
    var arcStartAttr = this.getAttribute('arc-start');
    var arcEndAttr   = this.getAttribute('arc-end');
    this._arcStart = arcStartAttr !== null ? parseFloat(arcStartAttr) : null;
    this._arcEnd   = arcEndAttr   !== null ? parseFloat(arcEndAttr)   : null;
    var innerRadiusAttr = this.getAttribute('inner-radius');
    this._innerRadius = innerRadiusAttr !== null ? parseFloat(innerRadiusAttr) : null;
    // Curve shape for line/area connectors. "smooth" => Catmull-Rom
    // spline through the points; anything else falls back to linear.
    this._curve = (this.getAttribute('curve') || 'linear').toLowerCase();

    this.innerHTML = '';
    if (dataNode) this.appendChild(dataNode);
    Array.prototype.forEach.call(extrasNodes, function (n) { this.appendChild(n); }, this);

    // Non-Cartesian types branch off here — no axis derivation, no
    // pan/zoom. Each owns its own SVG layout; the shared toolbar
    // (copy / screenshot / lightbox) attaches the same way.
    var nonCartesian = {
      donut: '_renderDonut',
      pie:   '_renderDonut',
      heatmap: '_renderHeatmap',
      sparkline: '_renderSparkline',
      waffle: '_renderWaffle',
      gauge: '_renderGauge',
      radar: '_renderRadar',
      'box-plot': '_renderBoxPlot',
      bullet: '_renderBullet',
      slope: '_renderSlope',
      histogram: '_renderHistogram',
      'calendar-heatmap': '_renderCalendarHeatmap',
      treemap: '_renderTreemap',
      ridgeline: '_renderRidgeline',
      funnel: '_renderFunnel',
      sankey: '_renderSankey',
      network: '_renderNetwork',
      'scatter-matrix': '_renderScatterMatrix',
      'parallel-coordinates': '_renderParallelCoordinates',
      chord: '_renderChord',
      geo: '_renderGeo',
      // `tile-map` is the honest name for what this renderer actually
      // builds: a tile cartogram (one cell per region in a coarse 11×7
      // grid). `geo` stays an alias because every existing doc page
      // emits that type — no breakage. New pages should use tile-map.
      'tile-map': '_renderGeo',
      'dot-plot':   '_renderDotPlot',
      density:      '_renderDensity',
      candlestick:  '_renderCandlestick',
      sunburst:     '_renderSunburst',
      marimekko:    '_renderMarimekko',
      stream:       '_renderStream',
      violin:       '_renderViolin',
      beeswarm:     '_renderBeeswarm',
      waterfall:    '_renderWaterfall',
      lollipop:     '_renderLollipop',
      dumbbell:     '_renderDumbbell',
      'polar-area': '_renderPolarArea',
      gantt:        '_renderGantt',
      bump:         '_renderBump'
    };
    if (nonCartesian[this._type]) {
      this[nonCartesian[this._type]]();
      // Wire the shared rich-tooltip controller so non-Cartesian
      // charts (donut, pie, heatmap, treemap, funnel, waffle,
      // gauge, radar, box-plot, bullet, slope, histogram,
      // calendar-heatmap, ridgeline, sankey, network, scatter-
      // matrix, parallel-coordinates, chord, geo, sparkline) get
      // hover / pin / click-outside / Escape just like the
      // Cartesian charts. Each renderer above tags its anchors
      // with `data-hover-payload` (or the legacy `.okc-slice`,
      // `.okc-treemap-cell rect`, `.okc-funnel-band` shapes); the
      // generic `rich('[data-hover-payload]', …)` wrapper picks
      // them up. Without this call, ONLY scatter / line / area /
      // bubble / quadrant ever fired tooltips — the rest were
      // statically decorated and silent.
      this._wireInteractivity();
      this._attachToolbar();
      return;
    }

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
    // Quadrant charts need extra top/bottom padding so the corner
    // region labels (TL/TR/BL/BR) can sit OUTSIDE the plot bounds.
    // Earlier rounds placed them inside at the corners + faded them
    // on hover — a workaround. The right answer is to never put them
    // where data can land.
    var isQuadrant = this._type === 'quadrant';
    this._pad = {
      top: (this._title ? 32 : 16) + (isQuadrant ? 22 : 0),
      right: 24,
      bottom: (this._xLabel ? 50 : 32) + (isQuadrant ? 22 : 0),
      left: this._yLabel ? 56 : 40,
    };
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

    // Cartesian series colours come from __okuPickColor — see
    // the shared palette helper near the top of the chart section.

    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + (this._title || (this._type + ' chart')) + '" class="okc-svg">');
    // Clip rect so the plot doesn't bleed into the chrome when zoomed.
    parts.push('<defs><clipPath id="okc-clip"><rect x="' + pad.left + '" y="' + pad.top + '" width="' + plotW + '" height="' + plotH + '"/></clipPath></defs>');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Axes
    parts.push('<line x1="' + pad.left + '" y1="' + (pad.top + plotH) + '" x2="' + (W - pad.right) + '" y2="' + (pad.top + plotH) + '" class="okc-axis"/>');
    parts.push('<line x1="' + pad.left + '" y1="' + pad.top + '" x2="' + pad.left + '" y2="' + (pad.top + plotH) + '" class="okc-axis"/>');
    if (this._xLabel) parts.push('<text x="' + (pad.left + plotW / 2) + '" y="' + (H - 14) + '" text-anchor="middle" class="okc-axis-label">' + escapeXml(this._xLabel) + (xLog ? ' (log)' : '') + '</text>');
    if (this._yLabel) parts.push('<text x="' + 14 + '" y="' + (pad.top + plotH / 2) + '" text-anchor="middle" class="okc-axis-label" transform="rotate(-90 14,' + (pad.top + plotH / 2) + ')">' + escapeXml(this._yLabel) + (yLog ? ' (log)' : '') + '</text>');
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
      parts.push('<line x1="' + pos + '" y1="' + (pad.top + plotH) + '" x2="' + pos + '" y2="' + (pad.top + plotH + 4) + '" class="okc-axis"/>');
      parts.push('<text x="' + pos + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="okc-tick">' + fmtNum(val) + '</text>');
    });
    yTicks.forEach(function (val) {
      var pos = sy(val);
      parts.push('<line x1="' + (pad.left - 4) + '" y1="' + pos + '" x2="' + pad.left + '" y2="' + pos + '" class="okc-axis"/>');
      parts.push('<text x="' + (pad.left - 6) + '" y="' + (pos + 4) + '" text-anchor="end" class="okc-tick">' + fmtNum(val) + '</text>');
    });

    // Quadrant overlay: two reference lines underlay the data; corner
    // labels are deferred (rendered after the dots in `quadrantLabelParts`
    // below) so a dot that happens to sit at the corner can't garble the
    // label text. The reference lines are intentionally drawn BEFORE the
    // dots so the dots sit on top of them.
    var quadrantLabelParts = [];
    if (self._type === 'quadrant' && self._extras && self._extras.quadrants) {
      var q = self._extras.quadrants;
      if (typeof q.x === 'number') {
        var qx = sx(q.x);
        parts.push('<line x1="' + qx + '" y1="' + pad.top + '" x2="' + qx + '" y2="' + (pad.top + plotH) + '" class="okc-quadrant"/>');
      }
      if (typeof q.y === 'number') {
        var qy = sy(q.y);
        parts.push('<line x1="' + pad.left + '" y1="' + qy + '" x2="' + (W - pad.right) + '" y2="' + qy + '" class="okc-quadrant"/>');
      }
      if (Array.isArray(q.labels)) {
        var ql = q.labels;
        // Order: [TL, TR, BL, BR]. Labels sit OUTSIDE the plot
        // bounds: TL/TR above the top axis, BL/BR below the bottom
        // x-tick row. That guarantees no data point can ever land
        // on top of them — earlier rounds put them inside the
        // corners and tried to fade-on-hover, which still left
        // them occluding data at rest. Out-of-plot is the only
        // honest fix.
        function regionLabel(text, x, y, anchor) {
          quadrantLabelParts.push(
            '<text x="' + x + '" y="' + y + '" text-anchor="' + anchor + '" class="okc-quadrant-label">' +
            escapeXml(text) + '</text>'
          );
        }
        var topLabelY    = pad.top - 8;
        var bottomLabelY = pad.top + plotH + (self._xLabel ? 42 : 28);
        if (ql[0]) regionLabel(ql[0], pad.left,                topLabelY,    'start');
        if (ql[1]) regionLabel(ql[1], W - pad.right,           topLabelY,    'end');
        if (ql[2]) regionLabel(ql[2], pad.left,                bottomLabelY, 'start');
        if (ql[3]) regionLabel(ql[3], W - pad.right,           bottomLabelY, 'end');
      }
    }

    // Plot region (clipped). All series + their dots / labels live here so
    // points that scroll past the axes don't leak.
    parts.push('<g clip-path="url(#okc-clip)">');
    var plotMidX = pad.left + plotW / 2;
    var drawsConnector = (self._type === 'line' || self._type === 'area');
    var drawsFill = (self._type === 'area');
    var drawsBubble = (self._type === 'bubble');
    this._series.forEach(function (s, i) {
      // Author-named colour wins; otherwise rotate through the
      // extended --series-N palette so multi-series Cartesian
      // charts get distinct colours past the 5-name vocabulary.
      var color = __okuPickColor(s.color, i);
      parts.push('<g class="okc-series" data-series-idx="' + i + '">');
      if (drawsConnector) {
        var data = s.data || [];
        if (data.length) {
          // Curve style — author opts into "smooth" for Catmull-Rom
          // splines through the points; default is linear. The two
          // builders return a valid SVG `d` string starting with M.
          // Smooth path is computed only when there are ≥2 points
          // (a single-point connector has no shape to smooth).
          var d;
          if (self._curve === 'smooth' && data.length >= 2) {
            // Catmull-Rom → Cubic Bezier conversion. Tension=0.5
            // is the canonical default (matches d3.curveCatmullRom).
            // Endpoints reflect (P0 = P1; P_n = P_n-1) so the curve
            // starts/ends without a leading derivative kink.
            var pts = data.map(function (p) { return { x: sx(p.x), y: sy(p.y) }; });
            var n = pts.length;
            var dParts = ['M ' + pts[0].x + ' ' + pts[0].y];
            for (var k = 0; k < n - 1; k++) {
              var p0 = pts[k - 1 < 0 ? 0 : k - 1];
              var p1 = pts[k];
              var p2 = pts[k + 1];
              var p3 = pts[k + 2 >= n ? n - 1 : k + 2];
              var cp1x = p1.x + (p2.x - p0.x) / 6;
              var cp1y = p1.y + (p2.y - p0.y) / 6;
              var cp2x = p2.x - (p3.x - p1.x) / 6;
              var cp2y = p2.y - (p3.y - p1.y) / 6;
              dParts.push('C ' + cp1x.toFixed(2) + ' ' + cp1y.toFixed(2) +
                          ' ' + cp2x.toFixed(2) + ' ' + cp2y.toFixed(2) +
                          ' ' + p2.x.toFixed(2) + ' ' + p2.y.toFixed(2));
            }
            d = dParts.join(' ');
          } else {
            d = data.map(function (p, idx) {
              return (idx === 0 ? 'M ' : 'L ') + sx(p.x) + ' ' + sy(p.y);
            }).join(' ');
          }
          if (drawsFill) {
            // Close down to a baseline so the polygon is filled. Use
            // y=0 when the range straddles zero, otherwise the y-axis
            // minimum (which keeps the fill within the plot rect).
            var baseY = (v.yMin <= 0 && v.yMax >= 0) ? sy(0) : sy(v.yMin);
            var firstX = sx(data[0].x), lastX = sx(data[data.length - 1].x);
            var areaD = d + ' L ' + lastX + ' ' + baseY + ' L ' + firstX + ' ' + baseY + ' Z';
            parts.push('<path d="' + areaD + '" fill="' + color + '" fill-opacity="0.18" stroke="none" class="okc-area"/>');
          }
          parts.push('<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2" class="okc-line"/>');
        }
      }
      (s.data || []).forEach(function (p, j) {
        var key = i + '-' + j;
        var dotLabel = escapeXml(String(p.label != null ? p.label : ''));
        var seriesLbl = escapeXml(String(s.label != null ? s.label : ''));
        var px = sx(p.x), py = sy(p.y);
        // Bubble: radius from p.size (sqrt so dot area is proportional
        // to size). Clamp to a reasonable range so a single large
        // outlier doesn't fill the plot.
        var r = 4;
        if (drawsBubble && p.size != null) {
          var s2 = Math.abs(+p.size) || 0;
          r = Math.max(4, Math.min(28, Math.sqrt(s2) * 1.2));
        }
        parts.push(
          '<circle cx="' + px + '" cy="' + py + '" r="' + r + '" fill="' + color +
          (drawsBubble ? '" fill-opacity="0.55' : '') +
          '" class="okc-dot"' +
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
            ' class="okc-point-label" data-point-key="' + key + '" tabindex="0">' +
            escapeXml(p.label) + '</text>'
          );
        }
      });
      parts.push('</g>');
    });
    parts.push('</g>'); // /clip
    // Quadrant labels render LAST so they sit above any dot that
    // happens to share their corner — the opaque pill backing keeps
    // text legible. Their fixed-corner positioning is intentional
    // (the reader's eye scans corners for region labels).
    if (quadrantLabelParts.length) {
      parts.push(quadrantLabelParts.join(''));
    }
    // Legend chips sit OUTSIDE the clip so they're always visible.
    // For scatter/bubble/line/area/quadrant: cluster legend chips in
    // a vertical column near the top-right edge, with the column's
    // total height computed from the visible-series count so the
    // last chip never extends past the plot region. The fixed
    // top-right placement is what trips up dense bubble layouts (a
    // huge marker in the top-right collides with the legend); to
    // mitigate, the legend gets its own padded backing rectangle
    // that occludes any data dot rendered behind it.
    var legendSeries = this._series.filter(function (s) { return !!s.label; });
    if (legendSeries.length) {
      var lgWidth = 130;
      var lgRowH = 20;
      var lgX = W - pad.right - lgWidth + 8;
      var lgY = pad.top + 6;
      var lgH = legendSeries.length * lgRowH + 8;
      // Padded backing so data underneath the legend doesn't garble
      // the chip text. Slight rounded rect, lower opacity surface so
      // the chart visually retains its colour underneath.
      parts.push(
        '<rect x="' + (lgX - 6) + '" y="' + lgY + '" width="' + lgWidth + '" height="' + lgH + '" rx="6" class="okc-legend-backdrop"/>'
      );
      legendSeries.forEach(function (s, i) {
        var srcIdx = self._series.indexOf(s);
        var color = __okuPickColor(s.color, srcIdx >= 0 ? srcIdx : i);
        var rowY = lgY + 4 + i * lgRowH;
        parts.push(
          '<g class="okc-legend-chip" data-series-idx="' + (srcIdx >= 0 ? srcIdx : i) + '" tabindex="0" role="button" ' +
          'aria-label="Toggle ' + escapeXml(s.label) + ' series">' +
            '<rect x="' + lgX + '" y="' + rowY + '" width="14" height="14" rx="2" fill="' + color + '" class="okc-legend-swatch"/>' +
            '<text x="' + (lgX + 18) + '" y="' + (rowY + 11) + '" class="okc-legend">' + escapeXml(s.label) + '</text>' +
          '</g>'
        );
      });
    }
    // Synced cursor (vertical dashed line) — sits at the top of the
    // plot region and is shown/positioned by _wireCartesianCursor on
    // pointer-move. Gives the reader a single "where am I" indicator
    // across every series, with the tooltip listing each series's
    // value at the cursor's x. Skipped for quadrant because quadrant
    // axes carry semantic labels (e.g. "effort × value") that don't
    // benefit from a sweep.
    if (self._type !== 'quadrant') {
      parts.push('<line class="okc-cartesian-cursor" x1="0" y1="' + pad.top + '" x2="0" y2="' + (pad.top + plotH) + '" visibility="hidden" pointer-events="none"/>');
    }
    parts.push('</svg>');

    var oldSvg = this.querySelector(':scope > .okc-svg');
    if (oldSvg) oldSvg.remove();
    this.insertAdjacentHTML('beforeend', parts.join(''));
    this._wireInteractivity();
    if (self._type !== 'quadrant') {
      this._wireCartesianCursor({
        padLeft: pad.left, padRight: pad.right,
        padTop: pad.top, plotW: plotW, plotH: plotH,
        W: W, sx: sx, sy: sy
      });
    }
    // SVG must be in the DOM before getBBox() reports anything sane.
    // Defer to next frame so layout has a chance to settle.
    requestAnimationFrame(function () { self._deconflictLabels(); });
  }

  /* Synced cursor for Cartesian charts. Tracks the pointer's x
     (mapped back through the chart's x-scale), drops a vertical
     dashed line that spans the plot region, and updates the rich
     tooltip with one row per series — "at x = ?, series A is ?,
     series B is ?" — so the reader compares all series at the same
     x in a single glance. */
  /* Generic vertical cursor for any SVG chart with a numeric or
     categorical x-axis. Renders a dashed accent line that follows
     the pointer between the supplied plotBounds. Cheap to opt into
     from a renderer — pass the plot rectangle and the rest is
     wiring. Used by box-plot / histogram / candlestick / density /
     beeswarm / dot-plot. The richer Cartesian cursor (with nearest-
     point lookup + multi-series tooltip) is a separate method. */
  /* Emit a horizontal series-legend swatch row inside an SVG.
     Used by chart types whose multi-series colour-coding would
     otherwise be a guessing game (marimekko, stream, anything else
     that paints per-series fills without a built-in legend).

     opts:
       x, y       — top-left of the legend row (viewBox coords)
       width      — total horizontal room available
       idxAttr    — data-* suffix written on each chip, for legend-hover
                    wiring downstream (defaults to "series-idx")

     The row is auto-clipped: if `width` won't fit every label, the
     chips overflow to a second row on a 18-px stride. Each chip
     carries data-legend-hover so the existing legend-hover CSS
     reactions still apply. */
  _renderSeriesLegend(series, palette, opts) {
    if (!series || !series.length) return '';
    var x0 = opts.x, y0 = opts.y, width = opts.width;
    var idxAttr = opts.idxAttr || 'series-idx';
    var swatch = 11, gap = 6, rowH = 18, fontPx = 11;
    var html = '<g class="okc-series-legend" pointer-events="all">';
    var cx = x0, cy = y0;
    series.forEach(function (s, i) {
      if (!s || !s.label) return;
      var label = String(s.label);
      // Estimate label width — 5.6px per char at 11px font with a
      // little slack. Cheap heuristic; SVG doesn't tell us the real
      // measure until paint, so we over-estimate by ~10% to be safe.
      var labW = Math.max(20, Math.ceil(label.length * 5.6) + 2);
      var chipW = swatch + 4 + labW + gap;
      if (cx + chipW > x0 + width && cx > x0) {
        cx = x0; cy += rowH;
      }
      var color = palette[i % palette.length];
      html += '<g class="okc-legend-chip" tabindex="0" data-legend-hover="' + i + '" data-' + idxAttr + '="' + i + '">';
      html +=   '<rect x="' + cx + '" y="' + (cy + 1) + '" width="' + swatch + '" height="' + swatch + '" rx="2" fill="' + color + '"/>';
      html +=   '<text x="' + (cx + swatch + 4) + '" y="' + (cy + 9) + '" class="okc-legend" font-size="' + fontPx + '">' + escapeXml(label) + '</text>';
      html += '</g>';
      cx += chipW;
    });
    html += '</g>';
    return html;
  }

  _wireGenericVerticalCursor(plotBounds, opts) {
    var self = this;
    var svg = self.querySelector('svg.okc-svg');
    if (!svg) return;
    var existing = svg.querySelector('.okc-generic-cursor');
    if (existing) existing.remove();
    var cursor = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    cursor.setAttribute('class', 'okc-generic-cursor');
    cursor.setAttribute('y1', plotBounds.top);
    cursor.setAttribute('y2', plotBounds.bottom);
    cursor.setAttribute('visibility', 'hidden');
    cursor.setAttribute('pointer-events', 'none');
    svg.appendChild(cursor);
    function svgX(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var ctm = svg.getScreenCTM();
      return ctm ? pt.matrixTransform(ctm.inverse()).x : null;
    }
    var seriesLookup = opts && opts.seriesLookup;
    function svgY(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var ctm = svg.getScreenCTM();
      return ctm ? pt.matrixTransform(ctm.inverse()).y : null;
    }
    svg.addEventListener('mousemove', function (ev) {
      if (self._tipPinned) return;
      var x = svgX(ev), y = svgY(ev);
      // Constrain to the plot area on BOTH axes — earlier rounds
      // checked x only, so hovering the title row or the margin
      // above the plot still flashed the cursor. The user reported
      // that as "vertical cursor shows over the title".
      if (x === null || x < plotBounds.left || x > plotBounds.right ||
          y === null || y < plotBounds.top  || y > plotBounds.bottom) {
        cursor.setAttribute('visibility', 'hidden');
        if (self._hideCursorTip) self._hideCursorTip();
        return;
      }
      cursor.setAttribute('x1', x);
      cursor.setAttribute('x2', x);
      cursor.setAttribute('visibility', 'visible');
      // If the renderer registered a series-lookup callback, build a
      // per-series intersection tooltip — same shape as the Cartesian
      // cursor uses. Lets the reader read off values at the cursor's x
      // without hovering each individual point.
      if (seriesLookup && self._showCursorTip) {
        var payload = seriesLookup(x);
        if (payload && payload.kv && payload.kv.length) {
          self._showCursorTip(payload, ev.clientX, svg.getBoundingClientRect().top);
        }
      }
    });
    svg.addEventListener('mouseleave', function () {
      cursor.setAttribute('visibility', 'hidden');
      if (self._hideCursorTip && !self._tipPinned) self._hideCursorTip();
    });
  }

  _wireCartesianCursor(opts) {
    var self = this;
    var svg = self.querySelector('svg.okc-svg');
    if (!svg) return;
    var cursor = svg.querySelector('.okc-cartesian-cursor');
    if (!cursor) return;
    // Invert the x scale so a screen-space x maps back to the data
    // domain. For linear: just lerp the plot region. For log: same,
    // because sx() above already used the log basis — we use sx()
    // as the forward map and binary-invert.
    function pointerToViewBoxX(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var ctm = svg.getScreenCTM();
      if (!ctm) return null;
      return pt.matrixTransform(ctm.inverse()).x;
    }
    function move(ev) {
      if (self._tipPinned) return;
      var vx = pointerToViewBoxX(ev);
      if (vx === null || vx < opts.padLeft || vx > opts.padLeft + opts.plotW) {
        cursor.setAttribute('visibility', 'hidden');
        if (self._hideCursorTip) self._hideCursorTip();
        return;
      }
      // For each series, find the data point with the closest x to
      // the cursor. Some series sample irregularly — nearest-point
      // works for all without assuming sorted-by-x data.
      var bestX = null;
      var rows = [];
      (self._series || []).forEach(function (s, sIdx) {
        var pts = s.data || [];
        if (!pts.length) return;
        var nearest = pts[0];
        var bestDelta = Math.abs(opts.sx(nearest.x) - vx);
        for (var i = 1; i < pts.length; i++) {
          var d = Math.abs(opts.sx(pts[i].x) - vx);
          if (d < bestDelta) { bestDelta = d; nearest = pts[i]; }
        }
        if (bestX === null) bestX = nearest.x;
        rows.push({
          k: s.label || ('series ' + (sIdx + 1)),
          v: fmtNum(nearest.y) + (nearest.label ? ' (' + nearest.label + ')' : '')
        });
      });
      if (!rows.length) return;
      cursor.setAttribute('x1', vx);
      cursor.setAttribute('x2', vx);
      cursor.setAttribute('visibility', 'visible');
      if (self._showCursorTip) {
        self._showCursorTip({
          label: (self._xLabel ? self._xLabel + ' ≈ ' : 'x ≈ ') + fmtNum(bestX),
          kv: rows
        }, ev.clientX, svg.getBoundingClientRect().top);
      }
    }
    function leave() {
      cursor.setAttribute('visibility', 'hidden');
      if (self._hideCursorTip && !self._tipPinned) self._hideCursorTip();
    }
    svg.addEventListener('mousemove', move);
    svg.addEventListener('mouseleave', leave);
  }

  /* Push overlapping point labels onto staggered y-offsets so they don't
     read as a single garbled run. If a label still has nowhere to go
     (too many neighbors or it's sitting inside a no-fly zone like a
     quadrant corner pill OR the legend cluster), hide it — the
     existing dot-hover sync brings it back via the `.hovered` reveal
     rule in CSS. */
  _deconflictLabels() {
    var svg = this.querySelector(':scope > .okc-svg');
    if (!svg) return;
    var labels = Array.prototype.slice.call(svg.querySelectorAll('.okc-point-label'));
    if (labels.length < 1) return;
    // Reset any prior adjustments (re-render path: zoom/pan).
    labels.forEach(function (l) {
      l.classList.remove('okc-label-hidden', 'okc-label-shifted');
      if (l.dataset.origY) l.setAttribute('y', l.dataset.origY);
      else l.dataset.origY = l.getAttribute('y');
    });
    // No-fly zones: quadrant corner pills + legend cluster backdrop.
    // Any candidate label box that overlaps one of these gets pushed
    // off the corner (offset cycle below). If no offset clears, hide.
    var noFly = [];
    svg.querySelectorAll('.okc-quadrant-label-pill, .okc-legend-backdrop').forEach(function (rect) {
      var x = +rect.getAttribute('x') || 0;
      var y = +rect.getAttribute('y') || 0;
      var w = +rect.getAttribute('width') || 0;
      var h = +rect.getAttribute('height') || 0;
      noFly.push({ x1: x, x2: x + w, y1: y, y2: y + h });
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
    if (!boxes.length) return;
    boxes.sort(function (a, b) { return a.x1 - b.x1; });
    var lineH = (boxes[0] && boxes[0].h ? boxes[0].h : 14) + 3;
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
    var offsets = [0, -lineH, lineH, -2 * lineH, 2 * lineH, -3 * lineH, 3 * lineH];
    var placed = [];
    function hitsNoFly(cand) {
      for (var n = 0; n < noFly.length; n++) {
        var nf = noFly[n];
        if (!(cand.x2 < nf.x1 || nf.x2 < cand.x1 || cand.y2 < nf.y1 || nf.y2 < cand.y1)) {
          return true;
        }
      }
      return false;
    }
    boxes.forEach(function (box) {
      var found = null;
      for (var k = 0; k < offsets.length; k++) {
        var oy = offsets[k];
        var cand = { x1: box.x1, x2: box.x2, y1: box.y1 + oy, y2: box.y2 + oy };
        if (hitsNoFly(cand)) continue;
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
          box.el.classList.add('okc-label-shifted');
        }
        placed.push({ x1: box.x1, x2: box.x2, y1: box.y1 + found, y2: box.y2 + found });
      } else {
        // Too crowded OR every offset lands on a no-fly zone — hide.
        // The existing dot-hover sync (.hovered) reveals it on demand
        // via the CSS reveal rule.
        box.el.classList.add('okc-label-hidden');
      }
    });
  }

  /* Donut render — distribution over `slices: [{label, value, color?}]`.
     Skips the Cartesian render path entirely (no axes, no pan/zoom).
     Slice geometry: cumulative angles starting at -π/2 (top), each
     slice as an SVG arc path. A centre label shows the total. Legend
     chips on the right map colour to slice label.

     The arc-flag is set when the slice covers > 180° so the arc takes
     the long way around; otherwise SVG would short-circuit through
     the donut centre. */
  _renderDonut() {
    var slices = (this._extras && this._extras.slices) || [];
    var total = 0;
    for (var i = 0; i < slices.length; i++) total += Math.max(0, +slices[i].value || 0);
    if (total <= 0 || slices.length < 1) {
      this.appendChild(document.createTextNode(''));
      return;
    }
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var W = 420, H = 320;
    var cx = 140, cy = H / 2;
    var rOuter = 110;
    // type=pie renders with no inner hole; donut keeps the empty centre
    // for the total-readout. Author can override with the inner_radius
    // property (0-0.95 fraction of rOuter) — e.g. pie+inner_radius=0.3
    // for a thick ring without leaving the pie sugar form.
    var isPie = this._type === 'pie';
    var defaultInner = isPie ? 0 : 64;
    var rInner = this._innerRadius !== null && this._innerRadius !== undefined
      ? Math.round(rOuter * Math.max(0, Math.min(0.95, this._innerRadius)))
      : defaultInner;
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || (isPie ? 'Pie chart' : 'Donut chart')) + '" class="okc-svg okc-donut' + (isPie ? ' okc-pie' : '') + '">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');

    // Sweep angles: defaults to a full circle starting at 12 o'clock,
    // overridable by the arc.start / arc.end author fields (in degrees
    // clockwise from 12). end < start is treated as a counter-clockwise
    // arc by absolute value of the delta — the slices still progress
    // in declaration order.
    var DEG = Math.PI / 180;
    var sweepStartDeg = this._arcStart !== null && this._arcStart !== undefined ? this._arcStart : 0;
    var sweepEndDeg   = this._arcEnd   !== null && this._arcEnd   !== undefined ? this._arcEnd   : 360;
    var sweepRadians  = (sweepEndDeg - sweepStartDeg) * DEG;
    if (sweepRadians === 0) sweepRadians = Math.PI * 2;
    var angleStart = -Math.PI / 2 + sweepStartDeg * DEG;
    slices.forEach(function (slice, idx) {
      var value = Math.max(0, +slice.value || 0);
      if (value <= 0) return;
      var fraction = value / total;
      var angleEnd = angleStart + fraction * sweepRadians;
      // largeArc is on the slice's actual angular extent — not on
      // the fraction-of-total. For partial sweeps (e.g. a 3/4 pie)
      // a 50% slice covers 135° and should NOT use the long arc.
      var largeArc = Math.abs(fraction * sweepRadians) > Math.PI ? 1 : 0;
      var x1 = cx + rOuter * Math.cos(angleStart);
      var y1 = cy + rOuter * Math.sin(angleStart);
      var x2 = cx + rOuter * Math.cos(angleEnd);
      var y2 = cy + rOuter * Math.sin(angleEnd);
      var d;
      if (rInner <= 0) {
        // Pie geometry — close through the centre. A 0-radius inner
        // arc renders degenerate in browsers (the slice disappears),
        // so route the path back to the centre with an explicit L
        // segment and skip the inner arc entirely.
        d = 'M ' + x1 + ' ' + y1 +
            ' A ' + rOuter + ' ' + rOuter + ' 0 ' + largeArc + ' 1 ' + x2 + ' ' + y2 +
            ' L ' + cx + ' ' + cy +
            ' Z';
      } else {
        var ix1 = cx + rInner * Math.cos(angleEnd);
        var iy1 = cy + rInner * Math.sin(angleEnd);
        var ix2 = cx + rInner * Math.cos(angleStart);
        var iy2 = cy + rInner * Math.sin(angleStart);
        d = 'M ' + x1 + ' ' + y1 +
            ' A ' + rOuter + ' ' + rOuter + ' 0 ' + largeArc + ' 1 ' + x2 + ' ' + y2 +
            ' L ' + ix1 + ' ' + iy1 +
            ' A ' + rInner + ' ' + rInner + ' 0 ' + largeArc + ' 0 ' + ix2 + ' ' + iy2 +
            ' Z';
      }
      var color = palette[slice.color] || palette.accent;
      parts.push('<path d="' + d + '" fill="' + color + '" class="okc-slice"' +
                 ' data-slice-idx="' + idx + '"' +
                 ' data-slice-label="' + escapeXml(slice.label || '') + '"' +
                 ' data-slice-value="' + value + '"' +
                 ' data-slice-share="' + fraction.toFixed(4) + '"' +
                 ' data-slice-total="' + total + '"' +
                 ' tabindex="0" role="img" aria-label="' + escapeXml(slice.label || '') + ': ' + fmtNum(value) + ' (' + Math.round(fraction * 100) + '%)"/>');
      angleStart = angleEnd;
    });

    // Centre readout — total + caption. Donut has the empty centre
    // to fit the readout; pie covers the centre with slice geometry,
    // so the readout would overlay a slice. Skip it for pie.
    if (!isPie) {
      parts.push('<text x="' + cx + '" y="' + (cy - 4) + '" text-anchor="middle" class="okc-donut-total">' + escapeXml(fmtNum(total)) + '</text>');
      parts.push('<text x="' + cx + '" y="' + (cy + 16) + '" text-anchor="middle" class="okc-donut-caption">total</text>');
    }

    // Legend on the right side, one row per slice.
    var lx = 280;
    slices.forEach(function (slice, idx) {
      var color = palette[slice.color] || palette.accent;
      var ly = 64 + idx * 22;
      var pct = Math.round((Math.max(0, +slice.value || 0) / total) * 100);
      parts.push('<g class="okc-donut-legend" data-slice-idx="' + idx + '" tabindex="0" role="button" aria-pressed="false" aria-label="' + escapeXml('Toggle ' + (slice.label || 'slice')) + '">' +
                 '<rect x="' + lx + '" y="' + (ly - 10) + '" width="12" height="12" rx="2" fill="' + color + '"/>' +
                 '<text x="' + (lx + 18) + '" y="' + ly + '" class="okc-donut-legend-label">' +
                   escapeXml(slice.label || '') + ' · ' + pct + '%' +
                 '</text></g>');
    });
    parts.push('</svg>');
    var svg = document.createRange().createContextualFragment(parts.join(''));
    this.appendChild(svg);
  }

  /* ---- Tier-1 / Tier-3 extension renderers --------------------- *
   * Each is a self-contained SVG emitter that reads its payload from
   * this._extras[<type>], computes a viewBox-sized layout, and appends
   * the produced SVG fragment to the host. No pan/zoom; the shared
   * toolbar (copy / screenshot / lightbox) wires up after each.       */

  _renderHeatmap() {
    var x = (this._extras && this._extras.heatmap) || {};
    var cells = x.cells || [];
    if (!cells.length || !cells[0] || !cells[0].length) return;
    var rows = cells.length, cols = cells[0].length;
    var vmin = Infinity, vmax = -Infinity;
    for (var ri = 0; ri < rows; ri++) {
      for (var ci = 0; ci < cols; ci++) {
        var v = +cells[ri][ci];
        if (v < vmin) vmin = v;
        if (v > vmax) vmax = v;
      }
    }
    if (Array.isArray(x.domain) && x.domain.length === 2) {
      vmin = +x.domain[0]; vmax = +x.domain[1];
    }
    var diverging = x.scale === 'diverging';
    var cell = 34;
    // Reserve more vertical headroom when column labels are long — the
    // -45° rotation extends the label up and to the left of its column
    // anchor; without enough headroom the leftmost label clips the title
    // and the rest visually crowd into the cell rim. Same idea for row
    // labels: scale the left gutter with the longest label.
    var maxColLabelLen = (x.col_labels || []).reduce(function (m, s) { return Math.max(m, String(s || '').length); }, 0);
    var maxRowLabelLen = (x.row_labels || []).reduce(function (m, s) { return Math.max(m, String(s || '').length); }, 0);
    var labelLeft = (x.row_labels && x.row_labels.length) ? Math.max(96, maxRowLabelLen * 7 + 16) : 4;
    var labelTop  = (x.col_labels && x.col_labels.length) ? Math.max(64, maxColLabelLen * 5 + 28) : 4;
    var titleTop  = this._title ? 28 : 0;
    var W = labelLeft + cols * cell + 12;
    var H = titleTop + labelTop + rows * cell + 12;
    function tone(v) {
      if (diverging) return v >= 0 ? 'var(--accent)' : 'var(--danger)';
      return 'var(--accent)';
    }
    function alpha(v) {
      if (diverging) {
        var span = Math.max(Math.abs(vmin), Math.abs(vmax)) || 1;
        return Math.max(0.08, Math.min(1, Math.abs(v) / span));
      }
      var span2 = (vmax - vmin) || 1;
      var t = (v - vmin) / span2;
      return Math.max(0.08, Math.min(1, t));
    }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Heatmap') + '" class="okc-svg okc-heatmap">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    if (x.col_labels && x.col_labels.length) {
      for (var c = 0; c < cols; c++) {
        var cxp = labelLeft + c * cell + cell / 2;
        // Push the anchor 12px above the cell row so the rotated
        // label doesn't visually touch the cell's top edge.
        var cyp = titleTop + labelTop - 12;
        parts.push('<text x="' + cxp + '" y="' + cyp + '" text-anchor="end" class="okc-heatmap-label" transform="rotate(-45 ' + cxp + ',' + cyp + ')">' + escapeXml(String(x.col_labels[c] || '')) + '</text>');
      }
    }
    if (x.row_labels && x.row_labels.length) {
      for (var r = 0; r < rows; r++) {
        var ry = titleTop + labelTop + r * cell + cell / 2 + 4;
        parts.push('<text x="' + (labelLeft - 6) + '" y="' + ry + '" text-anchor="end" class="okc-heatmap-label">' + escapeXml(String(x.row_labels[r] || '')) + '</text>');
      }
    }
    for (var i = 0; i < rows; i++) {
      for (var j = 0; j < cols; j++) {
        var val = +cells[i][j];
        var px = labelLeft + j * cell;
        var py = titleTop + labelTop + i * cell;
        var rowLabel = (x.row_labels && x.row_labels[i]) || ('row ' + (i + 1));
        var colLabel = (x.col_labels && x.col_labels[j]) || ('col ' + (j + 1));
        var payload = JSON.stringify({
          label: rowLabel + ' × ' + colLabel,
          kv: [{ k: 'value', v: fmtNum(val) }]
        });
        parts.push('<rect x="' + px + '" y="' + py + '" width="' + (cell - 2) + '" height="' + (cell - 2) + '" rx="3" fill="' + tone(val) + '" fill-opacity="' + alpha(val).toFixed(3) + '" class="okc-heatmap-cell" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml(rowLabel + ' × ' + colLabel + ': ' + fmtNum(val)) + '</title></rect>');
      }
    }
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  _renderSparkline() {
    var x = (this._extras && this._extras.sparkline) || {};
    var values = (x.values || []).map(Number);
    if (!values.length) return;
    var variant = x.variant || 'line';
    var W = 120, H = 28, pad = 2;
    var minV = Math.min.apply(null, values);
    var maxV = Math.max.apply(null, values);
    if (minV === maxV) { minV -= 1; maxV += 1; }
    var plotW = W - pad * 2, plotH = H - pad * 2;
    function px(i) { return pad + (values.length === 1 ? plotW / 2 : (i / (values.length - 1)) * plotW); }
    function py(v) { return pad + plotH - ((v - minV) / (maxV - minV)) * plotH; }
    // Summary stats for the rich-hover tooltip — min / max / first /
    // last / mean. The cursor handles per-point readout via
    // _wireSparklineCursor; the tooltip on the SVG host covers the
    // overall-shape summary that the cursor can't.
    var sumV = 0;
    for (var sIdx = 0; sIdx < values.length; sIdx++) sumV += values[sIdx];
    var sparkPayload = JSON.stringify({
      label: this._title || 'sparkline',
      kv: [
        { k: 'min',   v: fmtNum(minV) },
        { k: 'max',   v: fmtNum(maxV) },
        { k: 'first', v: fmtNum(values[0]) },
        { k: 'last',  v: fmtNum(values[values.length - 1]) },
        { k: 'mean',  v: fmtNum(sumV / values.length) },
        { k: 'n',     v: String(values.length) }
      ]
    });
    var parts = [];
    parts.push('<span class="okc-sparkline-row"><svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'sparkline') + '" class="okc-svg okc-sparkline" tabindex="0" data-hover-payload="' + escapeXml(sparkPayload) + '">');
    if (variant === 'bar') {
      var barW = plotW / values.length - 1;
      for (var bi = 0; bi < values.length; bi++) {
        var bx = pad + bi * (plotW / values.length);
        var by = py(values[bi]);
        parts.push('<rect x="' + bx + '" y="' + by + '" width="' + Math.max(1, barW) + '" height="' + (pad + plotH - by) + '" class="okc-sparkline-bar"/>');
      }
    } else {
      var d = values.map(function (v, i) { return (i === 0 ? 'M ' : 'L ') + px(i).toFixed(2) + ' ' + py(v).toFixed(2); }).join(' ');
      if (variant === 'area') {
        var area = d + ' L ' + px(values.length - 1).toFixed(2) + ' ' + (pad + plotH) + ' L ' + px(0).toFixed(2) + ' ' + (pad + plotH) + ' Z';
        parts.push('<path d="' + area + '" class="okc-sparkline-area"/>');
      }
      parts.push('<path d="' + d + '" class="okc-sparkline-line"/>');
      // Endpoint dot — always on for line/area; bar variant has its own visual.
      parts.push('<circle cx="' + px(values.length - 1).toFixed(2) + '" cy="' + py(values[values.length - 1]).toFixed(2) + '" r="2.4" class="okc-sparkline-endpoint"/>');
    }
    // Parallel cursor + per-point readout — same pattern as
    // ridgeline. Pointer moves over the svg; the closest point gets
    // a highlight ring + tooltip.
    parts.push('<line class="okc-sparkline-cursor" x1="0" y1="' + pad + '" x2="0" y2="' + (pad + plotH) + '" visibility="hidden" pointer-events="none"/>');
    parts.push('<circle class="okc-sparkline-cursor-dot" cx="0" cy="0" r="3" visibility="hidden" pointer-events="none"/>');
    parts.push('</svg>');
    if (x.end_label) parts.push('<span class="okc-sparkline-end-label">' + escapeXml(String(x.end_label)) + '</span>');
    parts.push('</span>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireSparklineCursor(values, pad, plotW, plotH, px, py);
  }
  _wireSparklineCursor(values, pad, plotW, plotH, px, py) {
    var self = this;
    var svg = self.querySelector('svg.okc-sparkline');
    if (!svg) return;
    var cursor = svg.querySelector('.okc-sparkline-cursor');
    var dot = svg.querySelector('.okc-sparkline-cursor-dot');
    if (!cursor || !dot) return;
    function pointerToViewBoxX(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var ctm = svg.getScreenCTM();
      if (!ctm) return null;
      return pt.matrixTransform(ctm.inverse()).x;
    }
    function move(ev) {
      // Pinned tooltips do not follow the cursor.
      if (self._tipPinned) return;
      var vx = pointerToViewBoxX(ev);
      if (vx === null || vx < pad || vx > pad + plotW) {
        cursor.setAttribute('visibility', 'hidden');
        dot.setAttribute('visibility', 'hidden');
        if (self._hideCursorTip) self._hideCursorTip();
        return;
      }
      var t = Math.max(0, Math.min(values.length - 1, Math.round(((vx - pad) / plotW) * (values.length - 1))));
      var x = px(t), y = py(values[t]);
      cursor.setAttribute('x1', x); cursor.setAttribute('x2', x);
      cursor.setAttribute('visibility', 'visible');
      dot.setAttribute('cx', x); dot.setAttribute('cy', y);
      dot.setAttribute('visibility', 'visible');
      svg.setAttribute('aria-valuenow', String(values[t]));
      svg.setAttribute('aria-valuetext', 'sample ' + (t + 1) + ': ' + values[t]);
      // Surface the cursor value in the rich tooltip card. Sparkline
      // is tiny so the tooltip sits anchored at the cursor X, just
      // above the SVG's top edge — looks like it's labelled the
      // current sample.
      if (self._showCursorTip) {
        var svgRect = svg.getBoundingClientRect();
        self._showCursorTip({
          label: (self._title || 'sparkline') + ' · #' + (t + 1),
          kv: [
            { k: 'value', v: fmtNum(values[t]) },
            { k: 'index', v: (t + 1) + ' / ' + values.length }
          ]
        }, ev.clientX, svgRect.top);
      }
    }
    function leave() {
      cursor.setAttribute('visibility', 'hidden');
      dot.setAttribute('visibility', 'hidden');
      if (self._hideCursorTip && !self._tipPinned) self._hideCursorTip();
    }
    svg.addEventListener('mousemove', move);
    svg.addEventListener('mouseleave', leave);
  }

  _renderWaffle() {
    var x = (this._extras && this._extras.waffle) || {};
    var segments = x.segments || [];
    var gRows = x.grid_rows || 10;
    var gCols = x.grid_cols || 10;
    var total = x.total || (gRows * gCols);
    var totalCells = gRows * gCols;
    // Build a flat array of [tone] per cell, by walking segments in order.
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var fills = [];
    segments.forEach(function (seg, sIdx) {
      var cells = Math.round((Math.max(0, +seg.count || 0) / total) * totalCells);
      var color = palette[seg.color] || palette.accent;
      for (var k = 0; k < cells && fills.length < totalCells; k++) fills.push({ color: color, label: seg.label, segIdx: sIdx });
    });
    // Pad with empty (muted-tone, very faint) cells. -1 means "no
    // segment" — the legend ignores them when toggling.
    while (fills.length < totalCells) fills.push({ color: palette.muted, label: 'empty', empty: true, segIdx: -1 });
    var cell = 22, gap = 3;
    var W = gCols * (cell + gap) + 12 + 160; // grid + legend
    var H = (this._title ? 28 : 4) + gRows * (cell + gap) + 12;
    var titleTop = this._title ? 28 : 0;
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Waffle') + '" class="okc-svg okc-waffle">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    for (var r = 0; r < gRows; r++) {
      for (var c = 0; c < gCols; c++) {
        var idx = r * gCols + c;
        var item = fills[idx];
        var rx = 6 + c * (cell + gap);
        var ry = titleTop + 4 + r * (cell + gap);
        var op = item.empty ? '0.15' : '1';
        var wpay = JSON.stringify({
          label: item.label || (item.empty ? 'empty' : 'segment'),
          kv: [
            { k: 'cell',    v: (idx + 1) + ' / ' + totalCells },
            { k: 'percent', v: (Math.round(((idx + 1) / totalCells) * 100)) + '%' }
          ]
        });
        parts.push('<rect x="' + rx + '" y="' + ry + '" width="' + cell + '" height="' + cell + '" rx="3" fill="' + item.color + '" fill-opacity="' + op + '" class="okc-waffle-cell" data-segment-idx="' + item.segIdx + '" tabindex="0" data-hover-payload="' + escapeXml(wpay) + '"><title>' + escapeXml((item.label || 'cell') + ' · cell ' + (idx + 1) + '/' + totalCells) + '</title></rect>');
      }
    }
    // Legend on the right.
    var lx = gCols * (cell + gap) + 24;
    segments.forEach(function (seg, idx) {
      var ly = titleTop + 16 + idx * 22;
      var color = palette[seg.color] || palette.accent;
      parts.push('<g class="okc-waffle-legend" data-segment-idx="' + idx + '" tabindex="0" role="button" aria-pressed="false" aria-label="' + escapeXml('Toggle ' + (seg.label || 'segment')) + '"><rect x="' + lx + '" y="' + (ly - 10) + '" width="12" height="12" rx="2" fill="' + color + '"/><text x="' + (lx + 18) + '" y="' + ly + '" class="okc-waffle-legend-label">' + escapeXml(seg.label || '') + ' · ' + (Math.round((Math.max(0, +seg.count || 0) / total) * 100)) + '%</text></g>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  _renderGauge() {
    var x = (this._extras && this._extras.gauge) || {};
    var val = +x.value || 0;
    var mn = +x.min || 0;
    var mx = +x.max;
    if (typeof mx !== 'number' || mx <= mn) return;
    // Earlier rounds rendered zone labels (BREACHING / CAUTION /
    // HEALTHY) AROUND the arc rim at zone-midangle. The labels
    // routinely overlapped the arc band itself because text-anchor
    // middle on a left-half label always extends rightward into the
    // arc. Replaced with a stable horizontal legend ROW under the
    // arc — same row as the value readout, well-defined location,
    // no arc collision. H bumped to fit the row.
    var zones = (x.zones || []);
    var hasZoneLegend = zones.some(function (z) { return !!z.label; });
    var W = 320, H = hasZoneLegend ? 230 : 200;
    var cx = W / 2, cy = (hasZoneLegend ? H - 66 : H - 36), r = 110, sr = 88;
    function angleOf(v) {
      var t = Math.max(0, Math.min(1, (v - mn) / (mx - mn)));
      return Math.PI + t * Math.PI; // 180° = mn, 360° = mx (semicircular)
    }
    function arcPath(start, end) {
      var x1 = cx + r * Math.cos(start), y1 = cy + r * Math.sin(start);
      var x2 = cx + r * Math.cos(end),   y2 = cy + r * Math.sin(end);
      var ix1 = cx + sr * Math.cos(end), iy1 = cy + sr * Math.sin(end);
      var ix2 = cx + sr * Math.cos(start), iy2 = cy + sr * Math.sin(start);
      var sweep = end > start ? 1 : 0;
      return 'M ' + x1 + ' ' + y1 +
             ' A ' + r + ' ' + r + ' 0 0 ' + sweep + ' ' + x2 + ' ' + y2 +
             ' L ' + ix1 + ' ' + iy1 +
             ' A ' + sr + ' ' + sr + ' 0 0 ' + (1 - sweep) + ' ' + ix2 + ' ' + iy2 + ' Z';
    }
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Gauge') + ': ' + val + '" class="okc-svg okc-gauge">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Background arc — full semicircle.
    parts.push('<path d="' + arcPath(angleOf(mn), angleOf(mx)) + '" fill="var(--surface-soft, rgba(127,127,127,0.18))" class="okc-gauge-bg"/>');
    // Zone bands only — labels go in the row below the value
    // readout, never on / around the arc.
    zones.forEach(function (z) {
      parts.push('<path d="' + arcPath(angleOf(z.from), angleOf(z.to)) + '" fill="' + (palette[z.tone] || palette.muted) + '" fill-opacity="0.32" class="okc-gauge-zone"><title>' + escapeXml((z.label || z.tone || 'zone') + ': ' + fmtNum(z.from) + ' – ' + fmtNum(z.to)) + '</title></path>');
    });
    // Value arc — rich hover surfaces value / target / range.
    var zoneSummary = (x.zones || []).map(function (z) { return (z.label || z.tone) + ': ' + fmtNum(z.from) + '–' + fmtNum(z.to); }).join(', ');
    var gaugeKv = [
      { k: 'value', v: fmtNum(val) },
      { k: 'range', v: fmtNum(mn) + ' – ' + fmtNum(mx) }
    ];
    if (typeof x.target === 'number') gaugeKv.push({ k: 'target', v: fmtNum(x.target) });
    if (zoneSummary) gaugeKv.push({ k: 'zones', v: zoneSummary });
    var gaugePayload = JSON.stringify({
      label: x.label || (this._title || 'Gauge'),
      kv: gaugeKv
    });
    parts.push('<path d="' + arcPath(angleOf(mn), angleOf(val)) + '" fill="var(--accent)" class="okc-gauge-value" tabindex="0" data-hover-payload="' + escapeXml(gaugePayload) + '"><title>' + escapeXml((x.label ? x.label + ': ' : '') + fmtNum(val) + ' (range ' + fmtNum(mn) + '–' + fmtNum(mx) + ')') + '</title></path>');
    // Target tick.
    if (typeof x.target === 'number') {
      var ta = angleOf(x.target);
      var tx1 = cx + (r - 4) * Math.cos(ta), ty1 = cy + (r - 4) * Math.sin(ta);
      var tx2 = cx + (sr + 4) * Math.cos(ta), ty2 = cy + (sr + 4) * Math.sin(ta);
      parts.push('<line x1="' + tx1 + '" y1="' + ty1 + '" x2="' + tx2 + '" y2="' + ty2 + '" class="okc-gauge-target"/>');
    }
    // Centre readout.
    parts.push('<text x="' + cx + '" y="' + (cy - 12) + '" text-anchor="middle" class="okc-gauge-value-text">' + escapeXml(fmtNum(val)) + '</text>');
    if (x.label) parts.push('<text x="' + cx + '" y="' + (cy + 10) + '" text-anchor="middle" class="okc-gauge-label">' + escapeXml(x.label) + '</text>');
    // Zone legend row (when at least one zone has a label). Fixed
    // location at the bottom of the SVG — same shape as marimekko /
    // stream legends. No arc-rim collision because it lives in its
    // own row.
    if (hasZoneLegend) {
      var lgY = H - 24;
      var swatch = 11, gap = 14, fontPx = 11;
      var chips = zones.filter(function (z) { return !!z.label; });
      // Measure-and-centre: estimate total width, lay chips out
      // around cx.
      var charW = 5.6;
      var widths = chips.map(function (z) { return swatch + 4 + Math.ceil(z.label.length * charW); });
      var totalW = widths.reduce(function (s, w) { return s + w; }, 0) + (chips.length - 1) * gap;
      var rowX = Math.max(8, cx - totalW / 2);
      chips.forEach(function (z, i) {
        var w = widths[i];
        var color = palette[z.tone] || palette.muted;
        parts.push('<g class="okc-gauge-zone-chip">');
        parts.push('<rect x="' + rowX + '" y="' + (lgY) + '" width="' + swatch + '" height="' + swatch + '" rx="2" fill="' + color + '"/>');
        parts.push('<text x="' + (rowX + swatch + 4) + '" y="' + (lgY + swatch - 1) + '" font-size="' + fontPx + '" class="okc-legend">' + escapeXml(z.label) + '</text>');
        parts.push('</g>');
        rowX += w + gap;
      });
    }
    // Cursor-driven inspector: hover anywhere on the arc and the
    // tooltip surfaces the value at the cursor's angle, plus which
    // zone that value falls in. Lets the reader read "if we hit 65
    // we're in caution" without squinting at the ticks.
    parts.push('<circle class="okc-gauge-cursor" cx="' + cx + '" cy="' + cy + '" r="0" pointer-events="none" visibility="hidden"/>');
    parts.push('<line class="okc-gauge-cursor-line" x1="' + cx + '" y1="' + cy + '" x2="' + cx + '" y2="' + cy + '" pointer-events="none" visibility="hidden"/>');
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGaugeCursor(cx, cy, r, sr, mn, mx, angleOf, x.zones || []);
  }
  _wireGaugeCursor(cx, cy, rOuter, rInner, mn, mx, angleOf, zones) {
    var self = this;
    var svg = self.querySelector('svg.okc-gauge');
    if (!svg) return;
    var cursor = svg.querySelector('.okc-gauge-cursor');
    var cursorLine = svg.querySelector('.okc-gauge-cursor-line');
    if (!cursor || !cursorLine) return;
    function pointerToViewBoxPoint(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var ctm = svg.getScreenCTM();
      if (!ctm) return null;
      return pt.matrixTransform(ctm.inverse());
    }
    function move(ev) {
      if (self._tipPinned) return;
      var p = pointerToViewBoxPoint(ev);
      if (!p) return;
      var dx = p.x - cx, dy = p.y - cy;
      var dist = Math.sqrt(dx * dx + dy * dy);
      // Only react when the pointer is roughly over the arc.
      if (dy > 6 || dist < rInner - 12 || dist > rOuter + 18) {
        cursor.setAttribute('visibility', 'hidden');
        cursorLine.setAttribute('visibility', 'hidden');
        if (self._hideCursorTip) self._hideCursorTip();
        return;
      }
      var ang = Math.atan2(dy, dx);
      if (ang < Math.PI && ang > 0) ang = Math.PI; // clamp to top half
      if (ang < 0) ang += 2 * Math.PI; // 180..360 range
      var t = (ang - Math.PI) / Math.PI;
      t = Math.max(0, Math.min(1, t));
      var v = mn + t * (mx - mn);
      var px = cx + rOuter * Math.cos(ang);
      var py = cy + rOuter * Math.sin(ang);
      cursorLine.setAttribute('x1', cx + (rInner - 4) * Math.cos(ang));
      cursorLine.setAttribute('y1', cy + (rInner - 4) * Math.sin(ang));
      cursorLine.setAttribute('x2', cx + (rOuter + 4) * Math.cos(ang));
      cursorLine.setAttribute('y2', cy + (rOuter + 4) * Math.sin(ang));
      cursorLine.setAttribute('visibility', 'visible');
      cursor.setAttribute('cx', px);
      cursor.setAttribute('cy', py);
      cursor.setAttribute('r', 4);
      cursor.setAttribute('visibility', 'visible');
      var zoneHit = null;
      for (var i = 0; i < zones.length; i++) {
        var z = zones[i];
        if (v >= z.from && v <= z.to) { zoneHit = z; break; }
      }
      if (self._showCursorTip) {
        self._showCursorTip({
          label: 'value ≈ ' + fmtNum(v),
          kv: [
            { k: 'zone',  v: zoneHit ? (zoneHit.label || zoneHit.tone || 'zone') : '—' },
            { k: 'range', v: fmtNum(mn) + ' – ' + fmtNum(mx) }
          ]
        }, ev.clientX, svg.getBoundingClientRect().top);
      }
    }
    function leave() {
      cursor.setAttribute('visibility', 'hidden');
      cursorLine.setAttribute('visibility', 'hidden');
      if (self._hideCursorTip && !self._tipPinned) self._hideCursorTip();
    }
    svg.addEventListener('mousemove', move);
    svg.addEventListener('mouseleave', leave);
  }

  _renderRadar() {
    var x = (this._extras && this._extras.radar) || {};
    var axes = x.axes || [];
    var series = this._series || [];
    if (axes.length < 3 || !series.length) return;
    var W = 420, H = 360;
    var cx = W / 2, cy = (this._title ? 196 : 180), R = 130;
    // Shared scale: largest value across series + per-axis max (if any).
    var axMax = axes.map(function (a, i) {
      var m = +a.max || 0;
      series.forEach(function (s) { var v = +(s.values || [])[i] || 0; if (v > m) m = v; });
      return m || 1;
    });
    function point(axisIdx, val) {
      var t = Math.min(1, Math.max(0, val / axMax[axisIdx]));
      var ang = -Math.PI / 2 + axisIdx * (2 * Math.PI / axes.length);
      return [cx + Math.cos(ang) * R * t, cy + Math.sin(ang) * R * t];
    }
    function axisEnd(i) {
      var ang = -Math.PI / 2 + i * (2 * Math.PI / axes.length);
      return [cx + Math.cos(ang) * R, cy + Math.sin(ang) * R];
    }
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Radar') + '" class="okc-svg okc-radar">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Concentric rings (25/50/75/100%).
    for (var k = 1; k <= 4; k++) {
      var pts = axes.map(function (_, ai) {
        var ang = -Math.PI / 2 + ai * (2 * Math.PI / axes.length);
        return (cx + Math.cos(ang) * R * (k / 4)).toFixed(1) + ',' + (cy + Math.sin(ang) * R * (k / 4)).toFixed(1);
      }).join(' ');
      parts.push('<polygon points="' + pts + '" class="okc-radar-ring"/>');
    }
    // Axis lines + labels.
    axes.forEach(function (a, i) {
      var e = axisEnd(i);
      parts.push('<line x1="' + cx + '" y1="' + cy + '" x2="' + e[0].toFixed(1) + '" y2="' + e[1].toFixed(1) + '" class="okc-radar-axis"/>');
      var lx = cx + Math.cos(-Math.PI / 2 + i * (2 * Math.PI / axes.length)) * (R + 18);
      var ly = cy + Math.sin(-Math.PI / 2 + i * (2 * Math.PI / axes.length)) * (R + 18);
      parts.push('<text x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) + '" text-anchor="middle" class="okc-radar-label">' + escapeXml(a.label || '') + '</text>');
    });
    // Series polygons — each carries a rich-hover payload listing
    // its per-axis values so the reader can compare a series'
    // shape against the axis labels in the tooltip.
    series.forEach(function (s, si) {
      var color = palette[s.color] || palette.accent;
      var pts = (s.values || []).map(function (v, ai) {
        var p = point(ai, +v || 0);
        return p[0].toFixed(1) + ',' + p[1].toFixed(1);
      }).join(' ');
      var kv = axes.map(function (a, ai) {
        return { k: (a.label || ('axis ' + (ai + 1))), v: fmtNum(+(s.values || [])[ai] || 0) };
      });
      var radarPayload = JSON.stringify({
        series: s.label || ('Series ' + (si + 1)),
        kv: kv
      });
      parts.push('<polygon points="' + pts + '" fill="' + color + '" fill-opacity="0.22" stroke="' + color + '" stroke-width="1.6" class="okc-radar-series" data-series-idx="' + si + '" tabindex="0" data-hover-payload="' + escapeXml(radarPayload) + '"><title>' + escapeXml((s.label || 'series') + ' — ' + kv.map(function (e) { return e.k + ': ' + e.v; }).join(', ')) + '</title></polygon>');
    });
    // Legend.
    var lgY = H - 24;
    series.forEach(function (s, si) {
      var color = palette[s.color] || palette.accent;
      var lx = 16 + si * 130;
      parts.push('<g class="okc-radar-legend" data-series-idx="' + si + '" tabindex="0" role="button" aria-pressed="false" aria-label="' + escapeXml('Toggle ' + (s.label || 'series')) + '"><rect x="' + lx + '" y="' + (lgY - 8) + '" width="10" height="10" rx="2" fill="' + color + '"/><text x="' + (lx + 16) + '" y="' + lgY + '" class="okc-radar-legend-label">' + escapeXml(s.label || '') + '</text></g>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  _renderBoxPlot() {
    var x = (this._extras && this._extras['box-plot']) || {};
    var boxes = x.boxes || [];
    if (!boxes.length) return;
    var W = 640, H = 80 + boxes.length * 56;
    var pad = { top: this._title ? 36 : 16, bottom: 28, left: 140, right: 24 };
    var plotW = W - pad.left - pad.right;
    var rowH = (H - pad.top - pad.bottom) / boxes.length;
    var allVals = [];
    boxes.forEach(function (b) {
      allVals.push(+b.min, +b.q1, +b.median, +b.q3, +b.max);
      (b.outliers || []).forEach(function (o) { allVals.push(+o); });
    });
    var vmin = Math.min.apply(null, allVals);
    var vmax = Math.max.apply(null, allVals);
    if (vmin === vmax) { vmin -= 1; vmax += 1; }
    var span = vmax - vmin;
    function sx(v) { return pad.left + ((v - vmin) / span) * plotW; }
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Box plot') + '" class="okc-svg okc-boxplot">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    boxes.forEach(function (b, i) {
      var y = pad.top + i * rowH + rowH / 2;
      var color = palette[b.color] || palette.accent;
      parts.push('<text x="' + (pad.left - 10) + '" y="' + (y + 4) + '" text-anchor="end" class="okc-boxplot-label">' + escapeXml(b.label || '') + '</text>');
      // Whisker.
      parts.push('<line x1="' + sx(+b.min) + '" y1="' + y + '" x2="' + sx(+b.max) + '" y2="' + y + '" class="okc-boxplot-whisker"/>');
      parts.push('<line x1="' + sx(+b.min) + '" y1="' + (y - 7) + '" x2="' + sx(+b.min) + '" y2="' + (y + 7) + '" class="okc-boxplot-whisker"/>');
      parts.push('<line x1="' + sx(+b.max) + '" y1="' + (y - 7) + '" x2="' + sx(+b.max) + '" y2="' + (y + 7) + '" class="okc-boxplot-whisker"/>');
      // IQR box — rich hover surfaces all 5 quartile stats.
      var bpPayload = JSON.stringify({
        label: b.label || ('Box ' + (i + 1)),
        kv: [
          { k: 'min',    v: fmtNum(+b.min) },
          { k: 'q1',     v: fmtNum(+b.q1) },
          { k: 'median', v: fmtNum(+b.median) },
          { k: 'q3',     v: fmtNum(+b.q3) },
          { k: 'max',    v: fmtNum(+b.max) }
        ].concat((b.outliers || []).length ? [{ k: 'outliers', v: (b.outliers || []).map(fmtNum).join(', ') }] : [])
      });
      parts.push('<rect x="' + sx(+b.q1) + '" y="' + (y - 12) + '" width="' + (sx(+b.q3) - sx(+b.q1)) + '" height="24" fill="' + color + '" fill-opacity="0.28" stroke="' + color + '" class="okc-boxplot-iqr" tabindex="0" data-hover-payload="' + escapeXml(bpPayload) + '"><title>' + escapeXml((b.label || 'box') + ': min ' + fmtNum(+b.min) + ', q1 ' + fmtNum(+b.q1) + ', med ' + fmtNum(+b.median) + ', q3 ' + fmtNum(+b.q3) + ', max ' + fmtNum(+b.max)) + '</title></rect>');
      // Median line.
      parts.push('<line x1="' + sx(+b.median) + '" y1="' + (y - 12) + '" x2="' + sx(+b.median) + '" y2="' + (y + 12) + '" stroke="' + color + '" stroke-width="2" class="okc-boxplot-median"/>');
      (b.outliers || []).forEach(function (o) {
        parts.push('<circle cx="' + sx(+o) + '" cy="' + y + '" r="3" fill="' + color + '" class="okc-boxplot-outlier"><title>' + escapeXml(String(o)) + '</title></circle>');
      });
    });
    // Axis ticks (5).
    for (var t = 0; t <= 4; t++) {
      var vv = vmin + (t / 4) * span;
      var xx = sx(vv);
      parts.push('<line x1="' + xx + '" y1="' + (H - pad.bottom + 2) + '" x2="' + xx + '" y2="' + (H - pad.bottom + 8) + '" class="okc-axis"/>');
      parts.push('<text x="' + xx + '" y="' + (H - pad.bottom + 20) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(vv)) + '</text>');
    }
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: H - pad.bottom, left: pad.left, right: W - pad.right });
  }

  _renderBullet() {
    var x = (this._extras && this._extras.bullet) || {};
    var tracks = x.tracks || [];
    if (!tracks.length) return;
    var W = 640;
    var rowH = 42;
    var pad = { top: this._title ? 36 : 16, left: 140, right: 80 };
    var H = pad.top + tracks.length * rowH + 12;
    var plotW = W - pad.left - pad.right;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Bullet chart') + '" class="okc-svg okc-bullet">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    tracks.forEach(function (t, i) {
      var y = pad.top + i * rowH + 8;
      var trackMax = +t.max || 100;
      function sx(v) { return pad.left + (Math.max(0, Math.min(trackMax, +v || 0)) / trackMax) * plotW; }
      parts.push('<text x="' + (pad.left - 10) + '" y="' + (y + 14) + '" text-anchor="end" class="okc-bullet-label">' + escapeXml(t.label || '') + '</text>');
      // Background track.
      parts.push('<rect x="' + pad.left + '" y="' + y + '" width="' + plotW + '" height="22" rx="3" class="okc-bullet-bg"/>');
      // Zone bands.
      (t.zones || []).forEach(function (z) {
        var zx = sx(z.from), zw = sx(z.to) - sx(z.from);
        parts.push('<rect x="' + zx + '" y="' + y + '" width="' + zw + '" height="22" fill="' + (palette[z.tone] || palette.muted) + '" fill-opacity="0.22" class="okc-bullet-zone"/>');
      });
      // Value bar — rich hover surfaces actual / target / max + zones.
      var color = palette[t.color] || palette.accent;
      var bulletKv = [
        { k: 'value', v: fmtNum(+t.value || 0) },
        { k: 'max',   v: fmtNum(trackMax) }
      ];
      if (typeof t.target === 'number') bulletKv.push({ k: 'target', v: fmtNum(t.target) });
      var bulletPayload = JSON.stringify({
        label: t.label || 'metric',
        kv: bulletKv
      });
      parts.push('<rect x="' + pad.left + '" y="' + (y + 6) + '" width="' + (sx(t.value) - pad.left) + '" height="10" rx="2" fill="' + color + '" class="okc-bullet-value" tabindex="0" data-hover-payload="' + escapeXml(bulletPayload) + '"><title>' + escapeXml((t.label || 'metric') + ': ' + fmtNum(+t.value || 0) + ' / ' + fmtNum(trackMax) + (typeof t.target === 'number' ? ' (target ' + fmtNum(t.target) + ')' : '')) + '</title></rect>');
      // Target tick.
      if (typeof t.target === 'number') {
        var tx = sx(t.target);
        parts.push('<line x1="' + tx + '" y1="' + (y - 2) + '" x2="' + tx + '" y2="' + (y + 24) + '" class="okc-bullet-target"/>');
      }
      // Value readout right of the track.
      parts.push('<text x="' + (W - pad.right + 10) + '" y="' + (y + 14) + '" class="okc-bullet-readout">' + escapeXml(fmtNum(+t.value || 0)) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    // Vertical cursor sweeping the plot region. seriesLookup converts
    // cursor.x into a "% of track max" reading per row, so a hover
    // at the cursor's x position surfaces "what fraction of the track
    // would this be?" for every metric simultaneously. The tracks can
    // have different `max` values, so we report each as a percentage
    // of its own scale.
    var pBottom = H - 12;
    this._wireGenericVerticalCursor(
      { top: pad.top, bottom: pBottom, left: pad.left, right: W - pad.right },
      {
        seriesLookup: function (svgX) {
          var pct = Math.max(0, Math.min(1, (svgX - pad.left) / plotW));
          return {
            label: Math.round(pct * 100) + '% of track',
            kv: tracks.map(function (t) {
              var trackMax = +t.max || 100;
              return { k: t.label || 'metric', v: fmtNum(pct * trackMax) + ' / ' + fmtNum(trackMax) };
            })
          };
        }
      }
    );
  }

  _renderSlope() {
    var x = (this._extras && this._extras.slope) || {};
    var items = x.items || [];
    if (!items.length) return;
    // Right-pad scales with the longest endpoint readout ("value · label") so
    // the labels never clip past the SVG edge. Empirically ~6 viewBox-units
    // per character covers our 11px label font + an 8px gutter.
    var maxRightLen = items.reduce(function (acc, it) {
      var s = fmtNum(+it.to || 0) + ' · ' + (it.label || '');
      return Math.max(acc, s.length);
    }, 6);
    var rightPad = Math.max(80, 24 + maxRightLen * 6);
    // Title + "Before/After" column-head row need vertical breathing room so
    // the title (y=22) doesn't collide with the column heads (y=pad.top-12).
    // With pad.top=44 the column heads sit at y=32 — 10px below the title.
    // Bump pad.top so column heads land at y≥40.
    var topPad = this._title ? 56 : 30;
    var W = 480, H = 60 + items.length * 12 + 40;
    if (H < 240) H = 240;
    var pad = { top: topPad, bottom: 30, left: 80, right: rightPad };
    var plotH = H - pad.top - pad.bottom;
    var allVals = items.reduce(function (acc, it) { acc.push(+it.from || 0, +it.to || 0); return acc; }, []);
    var vmin = Math.min.apply(null, allVals), vmax = Math.max.apply(null, allVals);
    if (vmin === vmax) { vmin -= 1; vmax += 1; }
    function sy(v) { return pad.top + plotH - ((v - vmin) / (vmax - vmin)) * plotH; }
    var leftX = pad.left, rightX = W - pad.right;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Slope chart') + '" class="okc-svg okc-slope">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Column labels.
    parts.push('<text x="' + leftX + '" y="' + (pad.top - 12) + '" text-anchor="middle" class="okc-slope-col">' + escapeXml(x.from_label || 'Before') + '</text>');
    parts.push('<text x="' + rightX + '" y="' + (pad.top - 12) + '" text-anchor="middle" class="okc-slope-col">' + escapeXml(x.to_label || 'After') + '</text>');
    // Vertical guides.
    parts.push('<line x1="' + leftX + '" y1="' + pad.top + '" x2="' + leftX + '" y2="' + (pad.top + plotH) + '" class="okc-axis"/>');
    parts.push('<line x1="' + rightX + '" y1="' + pad.top + '" x2="' + rightX + '" y2="' + (pad.top + plotH) + '" class="okc-axis"/>');
    items.forEach(function (it) {
      var fy = sy(+it.from || 0), ty = sy(+it.to || 0);
      var color = palette[it.color] || (((+it.to || 0) >= (+it.from || 0)) ? palette.success : palette.danger);
      var delta = (+it.to || 0) - (+it.from || 0);
      var pct = (+it.from || 0) === 0 ? null : Math.round((delta / Math.abs(+it.from || 1)) * 100);
      var slopePayload = JSON.stringify({
        label: it.label || 'item',
        kv: [
          { k: x.from_label || 'before', v: fmtNum(+it.from || 0) },
          { k: x.to_label   || 'after',  v: fmtNum(+it.to   || 0) },
          { k: 'delta',                  v: (delta >= 0 ? '+' : '') + fmtNum(delta) + (pct !== null ? ' (' + (pct >= 0 ? '+' : '') + pct + '%)' : '') }
        ]
      });
      parts.push('<line x1="' + leftX + '" y1="' + fy.toFixed(1) + '" x2="' + rightX + '" y2="' + ty.toFixed(1) + '" stroke="' + color + '" stroke-width="2" class="okc-slope-line" tabindex="0" data-hover-payload="' + escapeXml(slopePayload) + '"><title>' + escapeXml((it.label || 'item') + ': ' + fmtNum(+it.from || 0) + ' → ' + fmtNum(+it.to || 0)) + '</title></line>');
      parts.push('<circle cx="' + leftX + '" cy="' + fy.toFixed(1) + '" r="4" fill="' + color + '"/>');
      parts.push('<circle cx="' + rightX + '" cy="' + ty.toFixed(1) + '" r="4" fill="' + color + '"/>');
      parts.push('<text x="' + (leftX - 8) + '" y="' + (fy + 4).toFixed(1) + '" text-anchor="end" class="okc-slope-readout">' + escapeXml(fmtNum(+it.from || 0)) + '</text>');
      parts.push('<text x="' + (rightX + 8) + '" y="' + (ty + 4).toFixed(1) + '" class="okc-slope-readout">' + escapeXml(fmtNum(+it.to || 0)) + ' · ' + escapeXml(it.label || '') + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  _renderHistogram() {
    var x = (this._extras && this._extras.histogram) || {};
    var bins = x.bins || [];
    if (!bins.length) return;
    var W = 640, H = 280;
    var pad = { top: this._title ? 36 : 16, bottom: 36, left: 48, right: 16 };
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;
    var lo = +bins[0].lo, hi = +bins[bins.length - 1].hi;
    var counts = bins.map(function (b) { return +b.count || 0; });
    var maxCount = Math.max.apply(null, counts);
    if (maxCount <= 0) maxCount = 1;
    function sx(v) { return pad.left + ((v - lo) / (hi - lo || 1)) * plotW; }
    function sy(v) { return pad.top + plotH - (v / maxCount) * plotH; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Histogram') + '" class="okc-svg okc-histogram">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Y axis + ticks (5).
    parts.push('<line x1="' + pad.left + '" y1="' + pad.top + '" x2="' + pad.left + '" y2="' + (pad.top + plotH) + '" class="okc-axis"/>');
    for (var t = 0; t <= 4; t++) {
      var v = maxCount * (t / 4);
      var y = sy(v);
      parts.push('<line x1="' + (pad.left - 4) + '" y1="' + y + '" x2="' + pad.left + '" y2="' + y + '" class="okc-axis"/>');
      parts.push('<text x="' + (pad.left - 6) + '" y="' + (y + 4) + '" text-anchor="end" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    }
    // X axis baseline.
    parts.push('<line x1="' + pad.left + '" y1="' + (pad.top + plotH) + '" x2="' + (W - pad.right) + '" y2="' + (pad.top + plotH) + '" class="okc-axis"/>');
    // Bars + x-axis edge ticks.
    bins.forEach(function (b, i) {
      var x0 = sx(+b.lo), x1 = sx(+b.hi);
      var top = sy(+b.count || 0);
      var payload = JSON.stringify({
        label: '[' + fmtNum(+b.lo) + ', ' + fmtNum(+b.hi) + ')',
        kv: [{ k: 'count', v: fmtNum(+b.count || 0) }]
      });
      parts.push('<rect x="' + (x0 + 0.5) + '" y="' + top + '" width="' + (x1 - x0 - 1) + '" height="' + (pad.top + plotH - top) + '" rx="1" fill="var(--accent)" fill-opacity="0.78" class="okc-histogram-bar" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>[' + escapeXml(fmtNum(+b.lo)) + ', ' + escapeXml(fmtNum(+b.hi)) + '): ' + escapeXml(fmtNum(+b.count || 0)) + '</title></rect>');
      if (i === 0 || i === bins.length - 1 || (i % Math.max(1, Math.floor(bins.length / 6))) === 0) {
        parts.push('<line x1="' + x0 + '" y1="' + (pad.top + plotH) + '" x2="' + x0 + '" y2="' + (pad.top + plotH + 4) + '" class="okc-axis"/>');
        parts.push('<text x="' + x0 + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(+b.lo)) + '</text>');
      }
    });
    // Right edge tick (the upper bound of the last bin).
    var xMax = sx(hi);
    parts.push('<line x1="' + xMax + '" y1="' + (pad.top + plotH) + '" x2="' + xMax + '" y2="' + (pad.top + plotH + 4) + '" class="okc-axis"/>');
    parts.push('<text x="' + xMax + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(hi)) + '</text>');
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: pad.top + plotH, left: pad.left, right: W - pad.right });
  }

  _renderCalendarHeatmap() {
    var x = (this._extras && this._extras['calendar-heatmap']) || {};
    var dv = x.date_values || {};
    var keys = Object.keys(dv);
    if (!keys.length) return;
    // Year derivation: explicit overrides; otherwise pick the modal year.
    var year = +x.year || (function () {
      var counts = {};
      keys.forEach(function (k) { var y = parseInt(k.slice(0, 4), 10); if (!isNaN(y)) counts[y] = (counts[y] || 0) + 1; });
      var pick = 0, max = 0;
      for (var y in counts) if (counts[y] > max) { max = counts[y]; pick = +y; }
      return pick || (new Date()).getFullYear();
    })();
    // Compute value domain.
    var vmin = Infinity, vmax = -Infinity;
    keys.forEach(function (k) {
      var v = +dv[k]; if (isNaN(v)) return;
      if (v < vmin) vmin = v; if (v > vmax) vmax = v;
    });
    if (Array.isArray(x.domain) && x.domain.length === 2) { vmin = +x.domain[0]; vmax = +x.domain[1]; }
    var diverging = x.scale === 'diverging';
    function tone(v) {
      if (diverging) return v >= 0 ? 'var(--accent)' : 'var(--danger)';
      return 'var(--accent)';
    }
    function alpha(v) {
      if (isNaN(v)) return 0;
      if (diverging) {
        var span = Math.max(Math.abs(vmin), Math.abs(vmax)) || 1;
        return Math.max(0.08, Math.min(1, Math.abs(v) / span));
      }
      var span2 = (vmax - vmin) || 1;
      return Math.max(0.08, Math.min(1, (v - vmin) / span2));
    }
    var cell = 14, gap = 2;
    var dayLabelW = 22, monthLabelH = 18;
    var titleTop = this._title ? 28 : 4;
    // 53 columns covers any year (≤ 53 ISO weeks). Render starting Monday.
    var weekCols = 53;
    var W = dayLabelW + weekCols * (cell + gap) + 12;
    var H = titleTop + monthLabelH + 7 * (cell + gap) + 16;
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || ('Activity calendar ' + year)) + '" class="okc-svg okc-calendar">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Day-of-week labels (Mon, Wed, Fri only — typical convention).
    var dayLabels = ['Mon', '', 'Wed', '', 'Fri', '', ''];
    for (var d = 0; d < 7; d++) {
      if (!dayLabels[d]) continue;
      var dy = titleTop + monthLabelH + d * (cell + gap) + cell / 2 + 4;
      parts.push('<text x="' + (dayLabelW - 6) + '" y="' + dy + '" text-anchor="end" class="okc-calendar-label">' + dayLabels[d] + '</text>');
    }
    // Walk the year.
    var start = new Date(year, 0, 1);
    var jsDay = start.getDay();   // 0=Sun..6=Sat
    var dow0 = (jsDay + 6) % 7;   // 0=Mon..6=Sun
    var msPerDay = 86400000;
    var cursor = new Date(year, 0, 1);
    var monthAt = {};
    var col = 0;
    var pad2 = function (n) { return n < 10 ? '0' + n : '' + n; };
    while (cursor.getFullYear() === year) {
      var dayIso = cursor.getFullYear() + '-' + pad2(cursor.getMonth() + 1) + '-' + pad2(cursor.getDate());
      var dowJs = cursor.getDay();
      var row = (dowJs + 6) % 7;
      var px = dayLabelW + col * (cell + gap);
      var py = titleTop + monthLabelH + row * (cell + gap);
      var val = dv[dayIso];
      var hasVal = (typeof val !== 'undefined') && !isNaN(+val);
      var rectAlpha = hasVal ? alpha(+val).toFixed(3) : '0.08';
      var rectFill = hasVal ? tone(+val) : 'var(--text-soft)';
      var calPayload = JSON.stringify({
        label: dayIso,
        kv: hasVal ? [{ k: 'value', v: fmtNum(+val) }] : [{ k: 'value', v: 'no data' }]
      });
      parts.push('<rect x="' + px + '" y="' + py + '" width="' + cell + '" height="' + cell + '" rx="2" fill="' + rectFill + '" fill-opacity="' + rectAlpha + '" class="okc-calendar-cell" tabindex="0" data-hover-payload="' + escapeXml(calPayload) + '"><title>' + escapeXml(dayIso + (hasVal ? ' · ' + fmtNum(+val) : '')) + '</title></rect>');
      // Record the column where a new month begins.
      var mKey = cursor.getMonth();
      if (monthAt[mKey] === undefined) monthAt[mKey] = col;
      // Advance: stepping forward; column increments after Sun (row 6).
      if (row === 6) col++;
      cursor = new Date(cursor.getTime() + msPerDay);
      // Also bump col if we filled the week before EOY — handle in row reset only.
    }
    // Month labels at their first columns.
    var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    for (var m = 0; m < 12; m++) {
      if (monthAt[m] === undefined) continue;
      var mx = dayLabelW + monthAt[m] * (cell + gap);
      parts.push('<text x="' + mx + '" y="' + (titleTop + 12) + '" class="okc-calendar-month">' + monthNames[m] + '</text>');
    }
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    void dow0; // referenced for clarity above; not currently used after refactor
  }

  _renderTreemap() {
    var x = (this._extras && this._extras.treemap) || {};
    var tree = (x.tree || []).slice().sort(function (a, b) { return (+b.value || 0) - (+a.value || 0); });
    if (!tree.length) return;
    var total = tree.reduce(function (s, it) { return s + Math.max(0, +it.value || 0); }, 0);
    if (total <= 0) return;
    var W = 640, H = this._title ? 360 : 320;
    var titleTop = this._title ? 28 : 0;
    var pad = 8;
    var area = { x: pad, y: titleTop + pad, w: W - pad * 2, h: H - titleTop - pad * 2 };
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    // Squarified treemap — pure JS port. Goal: keep each row's aspect
    // ratio near 1.
    function worstRatio(row, w) {
      var sum = row.reduce(function (s, n) { return s + n; }, 0);
      var rMin = Math.min.apply(null, row), rMax = Math.max.apply(null, row);
      var w2 = w * w, s2 = sum * sum;
      return Math.max((w2 * rMax) / s2, s2 / (w2 * rMin));
    }
    var rects = [];
    function squarify(values, items, rect) {
      var w = Math.min(rect.w, rect.h);
      var row = [], rowItems = [];
      while (values.length) {
        var v = values[0], it = items[0];
        var trial = row.concat([v]);
        if (!row.length || worstRatio(trial, w) <= worstRatio(row, w)) {
          row.push(v); rowItems.push(it);
          values.shift(); items.shift();
        } else {
          layoutRow(row, rowItems, rect, w);
          row = []; rowItems = [];
          w = Math.min(rect.w, rect.h);
        }
      }
      if (row.length) layoutRow(row, rowItems, rect, w);
    }
    function layoutRow(row, rowItems, rect, w) {
      var sum = row.reduce(function (s, n) { return s + n; }, 0);
      var span = sum / w;
      if (rect.w >= rect.h) {
        // Place horizontal column on the left of remaining rect (width=span).
        var y = rect.y;
        for (var i = 0; i < row.length; i++) {
          var h = row[i] / sum * rect.h;
          rects.push({ x: rect.x, y: y, w: span, h: h, item: rowItems[i] });
          y += h;
        }
        rect.x += span; rect.w -= span;
      } else {
        // Horizontal row on top.
        var x = rect.x;
        for (var j = 0; j < row.length; j++) {
          var ww = row[j] / sum * rect.w;
          rects.push({ x: x, y: rect.y, w: ww, h: span, item: rowItems[j] });
          x += ww;
        }
        rect.y += span; rect.h -= span;
      }
    }
    var areaSize = area.w * area.h;
    var scaled = tree.map(function (it) { return (Math.max(0, +it.value || 0) / total) * areaSize; });
    squarify(scaled.slice(), tree.slice(), { x: area.x, y: area.y, w: area.w, h: area.h });
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Treemap') + '" class="okc-svg okc-treemap">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    rects.forEach(function (r) {
      var color = palette[r.item.color] || palette.accent;
      var labelFits = (r.w > 50 && r.h > 22);
      var v = +r.item.value || 0;
      var share = v / total;
      parts.push('<g class="okc-treemap-cell"><rect x="' + r.x.toFixed(1) + '" y="' + r.y.toFixed(1) + '" width="' + r.w.toFixed(1) + '" height="' + r.h.toFixed(1) + '" fill="' + color + '" fill-opacity="0.82"' +
        ' tabindex="0"' +
        ' data-cell-label="' + escapeXml(r.item.label) + '"' +
        ' data-cell-value="' + v + '"' +
        ' data-cell-share="' + share.toFixed(4) + '">' +
        '<title>' + escapeXml(r.item.label + ': ' + fmtNum(v) + ' (' + Math.round(share * 100) + '%)') + '</title>' +
      '</rect>');
      if (labelFits) {
        parts.push('<text x="' + (r.x + 8).toFixed(1) + '" y="' + (r.y + 18).toFixed(1) + '" class="okc-treemap-label">' + escapeXml(r.item.label) + '</text>');
        if (r.h > 38) parts.push('<text x="' + (r.x + 8).toFixed(1) + '" y="' + (r.y + 34).toFixed(1) + '" class="okc-treemap-value">' + escapeXml(fmtNum(v)) + '</text>');
      }
      parts.push('</g>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  _renderRidgeline() {
    var x = (this._extras && this._extras.ridgeline) || {};
    var distributions = x.distributions || [];
    if (distributions.length < 2) return;
    var W = 640;
    var rowH = 56;
    var titleTop = this._title ? 36 : 16;
    var H = titleTop + distributions.length * rowH + 18;
    var pad = { left: 130, right: 24 };
    var plotW = W - pad.left - pad.right;
    // Expose layout for the parallel-cursor wiring (see
    // _wireRidgelineCursor below). Bin width + plot bounds are
    // recovered there from these attributes so the cursor knows
    // which x value the pointer maps to.
    this.setAttribute('data-ridge-pad-left', pad.left);
    this.setAttribute('data-ridge-pad-right', pad.right);
    this.setAttribute('data-ridge-title-top', titleTop);
    this.setAttribute('data-ridge-row-h', rowH);
    this.setAttribute('data-ridge-w', W);
    this.setAttribute('data-ridge-h', H);
    // Global domain.
    var allVals = [];
    distributions.forEach(function (d) { (d.values || []).forEach(function (v) { allVals.push(+v); }); });
    var lo = Math.min.apply(null, allVals), hi = Math.max.apply(null, allVals);
    if (lo === hi) { lo -= 1; hi += 1; }
    // Each ridge: bin its values into ~30 bins over [lo,hi].
    var bins = 30, binW = (hi - lo) / bins;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Ridgeline') + '" class="okc-svg okc-ridgeline">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    distributions.forEach(function (d, i) {
      var counts = new Array(bins).fill(0);
      (d.values || []).forEach(function (v) {
        var idx = Math.min(bins - 1, Math.max(0, Math.floor(((+v) - lo) / (binW || 1))));
        counts[idx]++;
      });
      var maxC = Math.max.apply(null, counts) || 1;
      var baseY = titleTop + i * rowH + rowH - 8;
      var ridgeH = rowH - 14;
      function sx(bi) { return pad.left + (bi / (bins - 1)) * plotW; }
      function sy(cnt) { return baseY - (cnt / maxC) * ridgeH; }
      var color = palette[d.color] || palette.accent;
      var pathPts = [];
      pathPts.push('M ' + pad.left + ' ' + baseY);
      counts.forEach(function (cnt, bi) { pathPts.push('L ' + sx(bi).toFixed(1) + ' ' + sy(cnt).toFixed(1)); });
      pathPts.push('L ' + (pad.left + plotW) + ' ' + baseY + ' Z');
      // Summary stats for the rich-hover tooltip — n / min / max /
      // mean / median per distribution. The parallel cursor handles
      // "value at pointer"; this tooltip covers the whole-row
      // summary the cursor can't.
      var vs = (d.values || []).map(Number).filter(function (n) { return !isNaN(n); }).sort(function (a, b) { return a - b; });
      var sum = vs.reduce(function (s, n) { return s + n; }, 0);
      var mean = vs.length ? sum / vs.length : 0;
      var median = vs.length ? (vs.length % 2 ? vs[(vs.length - 1) / 2] : (vs[vs.length / 2 - 1] + vs[vs.length / 2]) / 2) : 0;
      var ridgePayload = JSON.stringify({
        label: d.label || ('distribution ' + (i + 1)),
        kv: [
          { k: 'n',       v: String(vs.length) },
          { k: 'min',     v: fmtNum(vs.length ? vs[0] : 0) },
          { k: 'median',  v: fmtNum(median) },
          { k: 'mean',    v: fmtNum(mean) },
          { k: 'max',     v: fmtNum(vs.length ? vs[vs.length - 1] : 0) }
        ]
      });
      parts.push('<path d="' + pathPts.join(' ') + '" fill="' + color + '" fill-opacity="0.32" stroke="' + color + '" stroke-width="1.2" class="okc-ridgeline-curve" tabindex="0" data-hover-payload="' + escapeXml(ridgePayload) + '"><title>' + escapeXml((d.label || 'distribution') + ': n=' + vs.length + ', median=' + fmtNum(median)) + '</title></path>');
      parts.push('<text x="' + (pad.left - 10) + '" y="' + (baseY - 2) + '" text-anchor="end" class="okc-ridgeline-label">' + escapeXml(d.label || '') + '</text>');
    });
    // X axis ticks (5).
    var axisY = titleTop + distributions.length * rowH + 4;
    for (var t = 0; t <= 4; t++) {
      var v = lo + (t / 4) * (hi - lo);
      var ax = pad.left + (t / 4) * plotW;
      parts.push('<text x="' + ax + '" y="' + axisY + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    }
    // Parallel cursor — a single vertical line spanning every ridge
    // that follows the pointer's X position. Sits inside the SVG so
    // its coordinates use the same viewBox basis as the ridges.
    parts.push('<line class="okc-ridge-cursor" x1="0" y1="' + titleTop + '" x2="0" y2="' + (titleTop + distributions.length * rowH) + '" stroke-width="1" pointer-events="none" visibility="hidden"/>');
    parts.push('<text class="okc-ridge-cursor-label" x="0" y="' + (titleTop - 8) + '" text-anchor="middle" pointer-events="none" visibility="hidden"></text>');
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireRidgelineCursor(lo, hi);
  }
  /* Parallel cursor for ridgeline charts. Listens to pointer moves
     on the SVG, projects the pointer's X back into the data domain
     using the same scale the ridges use, and positions a vertical
     line that spans every ridge — readers can compare "where is this
     value across all distributions" in a single glance. */
  _wireRidgelineCursor(lo, hi) {
    var self = this;
    var svg = self.querySelector('svg');
    if (!svg) return;
    var cursor = svg.querySelector('.okc-ridge-cursor');
    var label = svg.querySelector('.okc-ridge-cursor-label');
    if (!cursor || !label) return;
    var padLeft = +self.getAttribute('data-ridge-pad-left');
    var padRight = +self.getAttribute('data-ridge-pad-right');
    var W = +self.getAttribute('data-ridge-w');
    var plotW = W - padLeft - padRight;
    // Stash distributions so the cursor handler can compute the
    // density at the cursor x and surface it in the rich tooltip.
    var distributions = ((self._extras || {}).ridgeline || {}).distributions || [];
    function pointerToViewBoxX(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var ctm = svg.getScreenCTM();
      if (!ctm) return null;
      return pt.matrixTransform(ctm.inverse()).x;
    }
    function move(ev) {
      // Pinned tooltips do not follow the cursor — let the reader
      // read the pinned values without the floor moving under them.
      if (self._tipPinned) return;
      var vx = pointerToViewBoxX(ev);
      if (vx === null) return;
      if (vx < padLeft || vx > padLeft + plotW) {
        cursor.setAttribute('visibility', 'hidden');
        label.setAttribute('visibility', 'hidden');
        self._hideCursorTip();
        return;
      }
      var v = lo + ((vx - padLeft) / plotW) * (hi - lo);
      cursor.setAttribute('x1', vx);
      cursor.setAttribute('x2', vx);
      cursor.setAttribute('visibility', 'visible');
      label.setAttribute('x', vx);
      label.setAttribute('visibility', 'visible');
      label.textContent = fmtNum(v);
      // Find each distribution's count near v (±bin tolerance) so the
      // tooltip surfaces per-distribution density at the cursor x.
      var span = (hi - lo) || 1;
      var binW = span / 30;
      var kv = distributions.map(function (d) {
        var vs = (d.values || []).map(Number).filter(function (n) { return !isNaN(n) && n >= v - binW && n <= v + binW; });
        return { k: d.label || 'series', v: vs.length ? String(vs.length) : '·' };
      });
      self._showCursorTip({
        label: 'value ≈ ' + fmtNum(v),
        kv: kv,
        footer: 'count within ±' + fmtNum(binW)
      }, ev.clientX, ev.clientY);
    }
    function leave() {
      cursor.setAttribute('visibility', 'hidden');
      label.setAttribute('visibility', 'hidden');
      if (!self._tipPinned) self._hideCursorTip();
    }
    svg.addEventListener('mousemove', move);
    svg.addEventListener('mouseleave', leave);
  }

  _renderFunnel() {
    var x = (this._extras && this._extras.funnel) || {};
    var stages = x.stages || [];
    if (stages.length < 2) return;
    // Layout columns (anchored to a fixed grid so every label,
    // value, and percentage line up — previously each row's label
    // sat at the band edge, so labels staggered as the funnel
    // narrowed).
    //
    //   [ label-col ]   [ band ]   [ value-col ][ pct-col ]
    //   right-anchored             right-aligned   right-aligned
    //
    // Numbers right-align so the digits stack visually.
    var labelColRight = 168;          // x where label text ends
    var bandLeft       = 184;          // x of band's leftmost extent
    var bandRight      = 184 + 200;    // x of band's rightmost extent
    var bandMaxW       = bandRight - bandLeft;
    var valueColRight  = 470;          // value text right-aligned to here
    var pctColRight    = 528;          // percentage text right-aligned to here
    var W              = 540;
    var stageH         = 56;
    var titleTop       = this._title ? 36 : 12;
    var H              = titleTop + stages.length * stageH + 12;
    var maxVal = stages.reduce(function (m, s) { return Math.max(m, +s.value || 0); }, 0);
    if (maxVal <= 0) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var bandCenter = (bandLeft + bandRight) / 2;
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Funnel') + '" class="okc-svg okc-funnel">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="22" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    stages.forEach(function (st, i) {
      var v = +st.value || 0;
      var next = stages[i + 1];
      var nv = next ? (+next.value || 0) : v;
      var topW = (v / maxVal) * bandMaxW;
      var botW = (nv / maxVal) * bandMaxW;
      var y = titleTop + i * stageH;
      var nextY = titleTop + (i + 1) * stageH;
      var color = palette[st.color] || palette.accent;
      var pts = [
        (bandCenter - topW / 2).toFixed(1) + ',' + y,
        (bandCenter + topW / 2).toFixed(1) + ',' + y,
        (bandCenter + botW / 2).toFixed(1) + ',' + nextY,
        (bandCenter - botW / 2).toFixed(1) + ',' + nextY
      ].join(' ');
      var firstVal = +stages[0].value || 1;
      var share = v / firstVal;
      var pct = Math.round(share * 100);
      // Drop-off vs the previous stage — null on the first stage,
      // negative shouldn't happen in a funnel (sanity-clamped).
      var prev = i > 0 ? (+stages[i - 1].value || 0) : null;
      var drop = (prev !== null && prev > 0) ? Math.max(0, Math.round((1 - v / prev) * 100)) : null;
      parts.push('<polygon points="' + pts + '" fill="' + color + '" fill-opacity="' + (0.82 - i * 0.08).toFixed(2) + '" class="okc-funnel-band"' +
        ' tabindex="0"' +
        ' data-stage-label="' + escapeXml(st.label || '') + '"' +
        ' data-stage-value="' + v + '"' +
        ' data-stage-share="' + share.toFixed(4) + '"' +
        (drop !== null ? (' data-stage-drop="' + drop + '"') : '') +
        '><title>' + escapeXml((st.label || '') + ': ' + fmtNum(v) + ' (' + pct + '%)') + '</title></polygon>');
      var textY = y + stageH / 2 + 4;
      // Three fixed columns — labels, values, percentages — all
      // right-anchored to their column edge so digits stack and
      // labels line up regardless of band width.
      parts.push('<text x="' + labelColRight + '" y="' + textY + '" text-anchor="end" class="okc-funnel-label">' + escapeXml(st.label || '') + '</text>');
      parts.push('<text x="' + valueColRight + '" y="' + textY + '" text-anchor="end" class="okc-funnel-value">' + escapeXml(fmtNum(v)) + '</text>');
      parts.push('<text x="' + pctColRight + '" y="' + textY + '" text-anchor="end" class="okc-funnel-pct">' + pct + '%</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Tier 3 — sankey ----------------
     Layered left→right flow. Column = BFS depth from any source
     node; height in each column is proportional to the node's
     incoming-or-outgoing total flow. Links draw as cubic Bezier
     ribbons whose thickness matches link.value. */
  _renderSankey() {
    var x = (this._extras && this._extras.sankey) || {};
    var nodes = (x.nodes || []).slice();
    var links = (x.links || []).slice();
    if (nodes.length < 2 || !links.length) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    // Index nodes by id; compute incoming/outgoing totals.
    var byId = {};
    nodes.forEach(function (n) { n._in = 0; n._out = 0; n._adj = []; byId[n.id] = n; });
    links.forEach(function (l) {
      var s = byId[l.source], t = byId[l.target];
      if (!s || !t) return;
      var v = +l.value || 1;
      s._out += v; t._in += v;
      s._adj.push(l);
    });
    // BFS columns from any node with no incoming edges (sources).
    nodes.forEach(function (n) { n._col = (n._in === 0 && n._out > 0) ? 0 : -1; });
    var queue = nodes.filter(function (n) { return n._col === 0; });
    while (queue.length) {
      var n = queue.shift();
      n._adj.forEach(function (l) {
        var t = byId[l.target];
        if (t && (t._col === -1 || t._col < n._col + 1)) {
          t._col = n._col + 1;
          queue.push(t);
        }
      });
    }
    // Sinks without any outgoing — put them at last column.
    var maxCol = 0;
    nodes.forEach(function (n) { if (n._col > maxCol) maxCol = n._col; });
    nodes.forEach(function (n) { if (n._col === -1) n._col = maxCol; });
    // Layout: equally-spaced columns; within a column, stack by total flow.
    var W = 640, H = this._title ? 360 : 320;
    var titleTop = this._title ? 28 : 12;
    var pad = { left: 12, right: 12, top: titleTop, bottom: 12 };
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;
    var nodeW = 14;
    var gap = 6;
    var cols = [];
    for (var c = 0; c <= maxCol; c++) cols.push([]);
    nodes.forEach(function (n) { cols[n._col].push(n); });
    var colX = function (c) {
      if (cols.length <= 1) return pad.left + plotW / 2 - nodeW / 2;
      return pad.left + (c / (cols.length - 1)) * (plotW - nodeW);
    };
    cols.forEach(function (col) {
      var totalFlow = col.reduce(function (s, n) { return s + Math.max(n._in, n._out, 1); }, 0);
      var avail = plotH - (col.length - 1) * gap;
      var y = pad.top;
      col.forEach(function (n) {
        n._h = Math.max(8, (Math.max(n._in, n._out, 1) / totalFlow) * avail);
        n._y = y;
        y += n._h + gap;
      });
    });
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Sankey') + '" class="okc-svg okc-sankey">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Track running source/target heights so concurrent links stack.
    nodes.forEach(function (n) { n._srcUsed = 0; n._tgtUsed = 0; });
    // Ribbons — draw before nodes so the rectangles cap the band edges.
    links.forEach(function (l) {
      var s = byId[l.source], t = byId[l.target];
      if (!s || !t) return;
      var v = +l.value || 1;
      var sH = Math.max(1, (v / Math.max(s._out, 1)) * s._h);
      var tH = Math.max(1, (v / Math.max(t._in, 1)) * t._h);
      var sx = colX(s._col) + nodeW;
      var tx = colX(t._col);
      var sy = s._y + s._srcUsed;
      var ty = t._y + t._tgtUsed;
      s._srcUsed += sH;
      t._tgtUsed += tH;
      var mx = (sx + tx) / 2;
      var d = 'M ' + sx + ' ' + sy +
              ' C ' + mx + ' ' + sy + ', ' + mx + ' ' + ty + ', ' + tx + ' ' + ty +
              ' L ' + tx + ' ' + (ty + tH) +
              ' C ' + mx + ' ' + (ty + tH) + ', ' + mx + ' ' + (sy + sH) + ', ' + sx + ' ' + (sy + sH) +
              ' Z';
      var color = palette[s.color] || palette.accent;
      var payload = JSON.stringify({
        label: (l.label || (s.label || s.id) + ' → ' + (t.label || t.id)),
        kv: [{ k: 'flow', v: fmtNum(v) }]
      });
      parts.push('<path d="' + d + '" fill="' + color + '" fill-opacity="0.32" class="okc-sankey-link" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((l.label || (s.label || s.id) + ' → ' + (t.label || t.id)) + ': ' + fmtNum(v)) + '</title></path>');
    });
    // Node rectangles + labels.
    nodes.forEach(function (n) {
      var nx = colX(n._col);
      var color = palette[n.color] || palette.accent;
      parts.push('<rect x="' + nx + '" y="' + n._y + '" width="' + nodeW + '" height="' + n._h + '" fill="' + color + '" class="okc-sankey-node"><title>' + escapeXml((n.label || n.id) + ': ' + fmtNum(Math.max(n._in, n._out))) + '</title></rect>');
      var labelX = nx + (n._col === cols.length - 1 ? -6 : nodeW + 6);
      var anchor = n._col === cols.length - 1 ? 'end' : 'start';
      parts.push('<text x="' + labelX + '" y="' + (n._y + n._h / 2 + 4) + '" text-anchor="' + anchor + '" class="okc-sankey-label">' + escapeXml(n.label || n.id) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Tier 3 — network ----------------
     Force-relaxed node-link diagram. Initial layout = ring; we then
     run a small number of spring-relaxation iterations (Fruchterman-
     Reingold-ish) so connected nodes attract and all nodes repel.
     Cheap enough for tens of nodes; not intended for production
     graph-viz of thousands. */
  _renderNetwork() {
    var x = (this._extras && this._extras.network) || {};
    var nodes = (x.nodes || []).slice();
    var links = (x.links || []).slice();
    if (nodes.length < 2 || !links.length) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var W = 640, H = this._title ? 460 : 420;
    var titleTop = this._title ? 28 : 12;
    var byId = {};
    var cx = W / 2, cy = (titleTop + H) / 2;
    var R = Math.min(W, H) / 2 - 60;
    nodes.forEach(function (n, i) {
      var a = (i / nodes.length) * Math.PI * 2;
      n._x = cx + R * Math.cos(a);
      n._y = cy + R * Math.sin(a);
      byId[n.id] = n;
    });
    // Build neighbour map for the attraction step.
    var adj = {};
    nodes.forEach(function (n) { adj[n.id] = []; });
    links.forEach(function (l) {
      if (!byId[l.source] || !byId[l.target]) return;
      adj[l.source].push(l.target);
      adj[l.target].push(l.source);
    });
    // Fruchterman-Reingold-ish — k = ideal distance.
    var area = (W - 80) * (H - 80);
    var k = Math.sqrt(area / nodes.length);
    var iterations = 60;
    var temp = R / 3;
    for (var step = 0; step < iterations; step++) {
      // Repulsion.
      nodes.forEach(function (a) { a._dx = 0; a._dy = 0; });
      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          var a = nodes[i], b = nodes[j];
          var dx = a._x - b._x, dy = a._y - b._y;
          var dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
          var f = (k * k) / dist;
          var ux = dx / dist, uy = dy / dist;
          a._dx += ux * f; a._dy += uy * f;
          b._dx -= ux * f; b._dy -= uy * f;
        }
      }
      // Attraction (only along edges).
      links.forEach(function (l) {
        var a = byId[l.source], b = byId[l.target];
        if (!a || !b) return;
        var dx = a._x - b._x, dy = a._y - b._y;
        var dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
        var f = (dist * dist) / k;
        var ux = dx / dist, uy = dy / dist;
        a._dx -= ux * f; a._dy -= uy * f;
        b._dx += ux * f; b._dy += uy * f;
      });
      // Apply, clamp to viewbox.
      nodes.forEach(function (n) {
        var disp = Math.sqrt(n._dx * n._dx + n._dy * n._dy) || 0.01;
        n._x += (n._dx / disp) * Math.min(disp, temp);
        n._y += (n._dy / disp) * Math.min(disp, temp);
        n._x = Math.max(40, Math.min(W - 40, n._x));
        n._y = Math.max(titleTop + 20, Math.min(H - 20, n._y));
      });
      temp *= 0.92;
    }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Network') + '" class="okc-svg okc-network">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Edges first (drawn under nodes). Tagged with source / target so
    // the drag handler can locate every edge touching a moved node.
    links.forEach(function (l) {
      var a = byId[l.source], b = byId[l.target];
      if (!a || !b) return;
      parts.push('<line data-source="' + escapeXml(String(l.source)) + '" data-target="' + escapeXml(String(l.target)) + '" x1="' + a._x.toFixed(1) + '" y1="' + a._y.toFixed(1) + '" x2="' + b._x.toFixed(1) + '" y2="' + b._y.toFixed(1) + '" class="okc-network-edge"/>');
    });
    // Nodes use a translated group so drag updates one transform
    // instead of three coordinate attributes. Layout positions are
    // stored on data-x / data-y for the drag handler.
    nodes.forEach(function (n) {
      var color = palette[n.color] || palette.accent;
      var deg = adj[n.id].length;
      var r = 6 + Math.min(8, deg);
      parts.push('<g class="okc-network-node" tabindex="0" data-node-id="' + escapeXml(String(n.id)) + '" data-x="' + n._x.toFixed(1) + '" data-y="' + n._y.toFixed(1) + '" transform="translate(' + n._x.toFixed(1) + ',' + n._y.toFixed(1) + ')" data-hover-payload="' + escapeXml(JSON.stringify({label: n.label || n.id, kv: [{k: 'degree', v: String(deg)}]})) + '">' +
        '<circle cx="0" cy="0" r="' + r + '" fill="' + color + '"/>' +
        '<text x="0" y="' + (-r - 4).toFixed(1) + '" text-anchor="middle" class="okc-network-label">' + escapeXml(n.label || n.id) + '</text>' +
        '<title>' + escapeXml((n.label || n.id) + ' · degree ' + deg) + '</title>' +
        '</g>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireNetworkDrag();
  }

  /* ---------------- Network drag — drag-to-untangle ----------------
     Force-directed layouts pack nicely but often produce overlapping
     bundles for small graphs. Let the reader drag individual nodes
     to clean up the view — pointer events on each node group update
     its transform AND every edge that touches it. Pinned positions
     persist for the lifetime of the chart instance (until the page
     re-renders). */
  _wireNetworkDrag() {
    var svg = this.querySelector('.okc-network');
    if (!svg) return;
    var dragging = null;       // { node, edges, startCx, startCy, ptX, ptY }
    function svgPoint(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var ctm = svg.getScreenCTM();
      if (!ctm) return { x: ev.clientX, y: ev.clientY };
      var inv = ctm.inverse();
      return pt.matrixTransform(inv);
    }
    svg.addEventListener('pointerdown', function (ev) {
      var node = ev.target.closest('.okc-network-node');
      if (!node || !svg.contains(node)) return;
      var id = node.getAttribute('data-node-id');
      if (!id) return;
      var edges = svg.querySelectorAll('line[data-source="' + CSS.escape(id) + '"], line[data-target="' + CSS.escape(id) + '"]');
      var startPt = svgPoint(ev);
      dragging = {
        node: node,
        id: id,
        edges: edges,
        startCx: +node.getAttribute('data-x'),
        startCy: +node.getAttribute('data-y'),
        ptX: startPt.x,
        ptY: startPt.y,
      };
      node.classList.add('okc-dragging');
      svg.setPointerCapture(ev.pointerId);
      ev.preventDefault();
    });
    svg.addEventListener('pointermove', function (ev) {
      if (!dragging) return;
      var pt = svgPoint(ev);
      var nx = dragging.startCx + (pt.x - dragging.ptX);
      var ny = dragging.startCy + (pt.y - dragging.ptY);
      dragging.node.setAttribute('transform', 'translate(' + nx.toFixed(1) + ',' + ny.toFixed(1) + ')');
      dragging.node.setAttribute('data-x', nx.toFixed(1));
      dragging.node.setAttribute('data-y', ny.toFixed(1));
      for (var i = 0; i < dragging.edges.length; i++) {
        var e = dragging.edges[i];
        var isSrc = e.getAttribute('data-source') === dragging.id;
        if (isSrc) {
          e.setAttribute('x1', nx.toFixed(1));
          e.setAttribute('y1', ny.toFixed(1));
        } else {
          e.setAttribute('x2', nx.toFixed(1));
          e.setAttribute('y2', ny.toFixed(1));
        }
      }
    });
    function endDrag(ev) {
      if (!dragging) return;
      dragging.node.classList.remove('okc-dragging');
      try { svg.releasePointerCapture(ev.pointerId); } catch (e) {}
      dragging = null;
    }
    svg.addEventListener('pointerup', endDrag);
    svg.addEventListener('pointercancel', endDrag);
  }

  /* ---------------- Tier 3 — scatter-matrix ----------------
     N×N grid of mini scatter plots for multivariate correlation
     reading. Diagonal cells show the variable name; off-diagonal
     cells plot var-col vs var-row. Domain auto-derived per variable
     unless the schema declares one. */
  _renderScatterMatrix() {
    var x = (this._extras && this._extras['scatter-matrix']) || {};
    var vars = (x.variables || []).slice();
    var records = (x.records || []).slice();
    if (vars.length < 2 || records.length < 2) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var n = vars.length;
    var W = 640, H = 640;
    var titleTop = this._title ? 28 : 12;
    var pad = 10;
    var grid = W - pad * 2;
    var cell = grid / n;
    // Compute per-variable domains.
    vars.forEach(function (v) {
      if (Array.isArray(v.domain) && v.domain.length === 2) { v._lo = v.domain[0]; v._hi = v.domain[1]; return; }
      var vs = records.map(function (r) { return +r[v.key]; }).filter(function (x) { return !isNaN(x); });
      v._lo = vs.length ? Math.min.apply(null, vs) : 0;
      v._hi = vs.length ? Math.max.apply(null, vs) : 1;
      if (v._lo === v._hi) { v._lo -= 1; v._hi += 1; }
    });
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + (titleTop + H + 12) + '" role="img" aria-label="' + escapeXml(this._title || 'Scatter matrix') + '" class="okc-svg okc-scatter-matrix">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Pearson correlation per off-diagonal pair, used both in the
    // hover payload and in the on-cell text annotation so the reader
    // sees the strength of the relationship without leaving the
    // scatter matrix.
    function correlation(xs, ys) {
      var n = xs.length;
      if (n < 2) return 0;
      var mx = 0, my = 0;
      for (var k = 0; k < n; k++) { mx += xs[k]; my += ys[k]; }
      mx /= n; my /= n;
      var num = 0, dx = 0, dy = 0;
      for (var k2 = 0; k2 < n; k2++) {
        var ex = xs[k2] - mx, ey = ys[k2] - my;
        num += ex * ey; dx += ex * ex; dy += ey * ey;
      }
      var denom = Math.sqrt(dx * dy);
      return denom > 0 ? num / denom : 0;
    }
    for (var i = 0; i < n; i++) {
      for (var j = 0; j < n; j++) {
        var cx = pad + j * cell;
        var cy = titleTop + i * cell;
        if (i === j) {
          // Diagonal: variable label on a quiet frame.
          parts.push('<rect x="' + cx + '" y="' + cy + '" width="' + cell + '" height="' + cell + '" class="okc-sm-cell okc-sm-cell-diag"/>');
          parts.push('<text x="' + (cx + cell / 2) + '" y="' + (cy + cell / 2 + 4) + '" text-anchor="middle" class="okc-sm-label">' + escapeXml(vars[i].label || vars[i].key) + '</text>');
          continue;
        }
        var vx = vars[j], vy = vars[i];
        var rangeX = (vx._hi - vx._lo) || 1;
        var rangeY = (vy._hi - vy._lo) || 1;
        // Collect aligned x/y values for correlation + plotting.
        var xs = [], ys = [];
        records.forEach(function (r) {
          var xv = +r[vx.key], yv = +r[vy.key];
          if (isNaN(xv) || isNaN(yv)) return;
          xs.push(xv); ys.push(yv);
        });
        var corr = correlation(xs, ys);
        // Off-diagonal frame becomes the hover anchor — the rich
        // tooltip lists the variable pair, the correlation, and the
        // point count.
        var smPayload = JSON.stringify({
          label: (vx.label || vx.key) + ' vs ' + (vy.label || vy.key),
          kv: [
            { k: 'x-axis',      v: vx.label || vx.key },
            { k: 'y-axis',      v: vy.label || vy.key },
            { k: 'n',           v: String(xs.length) },
            { k: 'correlation', v: corr.toFixed(2) }
          ]
        });
        parts.push('<rect x="' + cx + '" y="' + cy + '" width="' + cell + '" height="' + cell + '" class="okc-sm-cell" tabindex="0" data-hover-payload="' + escapeXml(smPayload) + '"><title>' + escapeXml((vx.label || vx.key) + ' vs ' + (vy.label || vy.key) + ' · r=' + corr.toFixed(2) + ' · n=' + xs.length) + '</title></rect>');
        // Plot the dots.
        for (var pi = 0; pi < xs.length; pi++) {
          var rec = records[pi] || {};
          var px = cx + ((xs[pi] - vx._lo) / rangeX) * (cell - 6) + 3;
          var py = cy + cell - ((ys[pi] - vy._lo) / rangeY) * (cell - 6) - 3;
          var color = palette[rec._color] || palette.accent;
          parts.push('<circle cx="' + px.toFixed(1) + '" cy="' + py.toFixed(1) + '" r="1.8" fill="' + color + '" fill-opacity="0.78" class="okc-sm-dot" pointer-events="none"/>');
        }
        // Correlation chip in the cell's top-left — accent-tinted
        // when |r| > 0.7 so strong relationships pop out.
        var strong = Math.abs(corr) >= 0.7;
        parts.push('<text x="' + (cx + 6) + '" y="' + (cy + 14) + '" class="okc-sm-corr' + (strong ? ' strong' : '') + '">r=' + corr.toFixed(2) + '</text>');
      }
    }
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Tier 3 — parallel-coordinates ----------------
     Multi-axis polyline per record. Each variable becomes a vertical
     axis; each record draws a polyline crossing all axes at its
     scaled position. Lines coloured by record._color when set.
     Hovering a polyline highlights it. */
  _renderParallelCoordinates() {
    var x = (this._extras && this._extras['parallel-coordinates']) || {};
    var vars = (x.variables || []).slice();
    var records = (x.records || []).slice();
    if (vars.length < 2 || records.length < 1) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var W = 720, H = 360;
    var titleTop = this._title ? 28 : 12;
    var pad = { left: 40, right: 40, top: titleTop + 20, bottom: 40 };
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;
    vars.forEach(function (v) {
      if (Array.isArray(v.domain) && v.domain.length === 2) { v._lo = v.domain[0]; v._hi = v.domain[1]; return; }
      var vs = records.map(function (r) { return +r[v.key]; }).filter(function (x) { return !isNaN(x); });
      v._lo = vs.length ? Math.min.apply(null, vs) : 0;
      v._hi = vs.length ? Math.max.apply(null, vs) : 1;
      if (v._lo === v._hi) { v._lo -= 1; v._hi += 1; }
    });
    var axisX = function (i) {
      if (vars.length <= 1) return pad.left + plotW / 2;
      return pad.left + (i / (vars.length - 1)) * plotW;
    };
    var scaleY = function (v, val) {
      var range = (v._hi - v._lo) || 1;
      return pad.top + plotH - ((val - v._lo) / range) * plotH;
    };
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Parallel coordinates') + '" class="okc-svg okc-parcoord">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Axes.
    vars.forEach(function (v, i) {
      var ax = axisX(i);
      parts.push('<line x1="' + ax + '" y1="' + pad.top + '" x2="' + ax + '" y2="' + (pad.top + plotH) + '" class="okc-parcoord-axis"/>');
      parts.push('<text x="' + ax + '" y="' + (pad.top - 8) + '" text-anchor="middle" class="okc-parcoord-label">' + escapeXml(v.label || v.key) + '</text>');
      parts.push('<text x="' + ax + '" y="' + (pad.top - 22) + '" text-anchor="middle" class="okc-tick">' + fmtNum(v._hi) + '</text>');
      parts.push('<text x="' + ax + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="okc-tick">' + fmtNum(v._lo) + '</text>');
    });
    // Polylines.
    records.forEach(function (r, ri) {
      var pts = [];
      for (var i = 0; i < vars.length; i++) {
        var v = vars[i];
        var val = +r[v.key];
        if (isNaN(val)) val = (v._lo + v._hi) / 2;
        pts.push(axisX(i).toFixed(1) + ',' + scaleY(v, val).toFixed(1));
      }
      var color = palette[r._color] || palette.accent;
      var payload = JSON.stringify({ label: r._label || ('record ' + (ri + 1)), kv: vars.map(function (v) { return { k: v.label || v.key, v: fmtNum(+r[v.key]) }; }) });
      parts.push('<polyline points="' + pts.join(' ') + '" stroke="' + color + '" fill="none" stroke-width="1.5" class="okc-parcoord-line" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml(r._label || ('record ' + (ri + 1))) + '</title></polyline>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Tier 3 — chord ----------------
     Circular relationship diagram. Each group occupies an arc on
     the perimeter sized by its total in+out flow; ribbons between
     groups draw as cubic Bezier curves through the centre.
     Input: groups[] (N entries — order = clockwise sequence from
     12 o'clock) + matrix (N×N, where matrix[i][j] is flow from
     groups[i] to groups[j]). */
  _renderChord() {
    var x = (this._extras && this._extras.chord) || {};
    var groups = (x.groups || []).slice();
    var matrix = x.matrix || [];
    if (groups.length < 2 || !matrix.length) return;
    var n = groups.length;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    // Total flow per group (in + out).
    var totals = new Array(n).fill(0);
    for (var i = 0; i < n; i++) {
      for (var j = 0; j < n; j++) {
        var v = (matrix[i] && +matrix[i][j]) || 0;
        totals[i] += v;
        if (i !== j) totals[j] += v;
      }
    }
    var grand = totals.reduce(function (s, v) { return s + v; }, 0);
    if (grand <= 0) return;
    // Geometry — outer arc radius, inner ribbon radius, gap between arcs.
    var W = 560, H = 560;
    var titleTop = this._title ? 28 : 12;
    var cx = W / 2, cy = (titleTop + H) / 2 - 8;
    var rOuter = 220, rInner = 200;
    var gap = (Math.PI / 180) * 2; // 2 degrees gap between arcs
    var totalGap = n * gap;
    var avail = Math.PI * 2 - totalGap;
    var startAngle = -Math.PI / 2; // start at 12 o'clock, clockwise
    var arcs = [];
    groups.forEach(function (g, i) {
      var span = (totals[i] / grand) * avail;
      var a0 = startAngle;
      var a1 = startAngle + span;
      arcs.push({ start: a0, end: a1, group: g, idx: i });
      startAngle = a1 + gap;
    });
    // Compute per-(i,j) start/end angles within each arc — cells
    // stack by matrix-column order within the source arc, by row
    // order within the target arc. Symmetric so undirected flows
    // (matrix[i][j] == matrix[j][i]) read as one ribbon visually.
    function point(r, a) { return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; }
    var srcCursor = new Array(n).fill(0);
    var tgtCursor = new Array(n).fill(0);
    var ribbons = [];
    for (var i = 0; i < n; i++) {
      for (var j = 0; j < n; j++) {
        var flow = (matrix[i] && +matrix[i][j]) || 0;
        if (flow <= 0 || i === j) continue;
        var sArc = arcs[i];
        var tArc = arcs[j];
        var sSpan = (flow / totals[i]) * (sArc.end - sArc.start);
        var tSpan = (flow / totals[j]) * (tArc.end - tArc.start);
        var sA0 = sArc.start + srcCursor[i];
        var sA1 = sA0 + sSpan;
        var tA0 = tArc.start + tgtCursor[j];
        var tA1 = tA0 + tSpan;
        srcCursor[i] += sSpan;
        tgtCursor[j] += tSpan;
        ribbons.push({ sA0: sA0, sA1: sA1, tA0: tA0, tA1: tA1, source: i, target: j, value: flow });
      }
    }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Chord') + '" class="okc-svg okc-chord">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Ribbons first (drawn under arcs).
    ribbons.forEach(function (r) {
      var s0 = point(rInner, r.sA0), s1 = point(rInner, r.sA1);
      var t0 = point(rInner, r.tA0), t1 = point(rInner, r.tA1);
      // Use the centre as the Bezier control to bend ribbons through
      // the middle of the chart.
      var d =
        'M ' + s0[0].toFixed(1) + ' ' + s0[1].toFixed(1) +
        ' A ' + rInner + ' ' + rInner + ' 0 0 1 ' + s1[0].toFixed(1) + ' ' + s1[1].toFixed(1) +
        ' Q ' + cx + ' ' + cy + ' ' + t0[0].toFixed(1) + ' ' + t0[1].toFixed(1) +
        ' A ' + rInner + ' ' + rInner + ' 0 0 1 ' + t1[0].toFixed(1) + ' ' + t1[1].toFixed(1) +
        ' Q ' + cx + ' ' + cy + ' ' + s0[0].toFixed(1) + ' ' + s0[1].toFixed(1) +
        ' Z';
      var sg = groups[r.source];
      var tg = groups[r.target];
      var color = palette[sg.color] || palette.accent;
      var payload = JSON.stringify({
        label: (sg.label || sg.id) + ' → ' + (tg.label || tg.id),
        kv: [{ k: 'flow', v: fmtNum(r.value) }]
      });
      parts.push('<path d="' + d + '" fill="' + color + '" fill-opacity="0.28" class="okc-chord-ribbon" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((sg.label || sg.id) + ' → ' + (tg.label || tg.id) + ': ' + fmtNum(r.value)) + '</title></path>');
    });
    // Outer arcs (group perimeter).
    arcs.forEach(function (a) {
      var p0 = point(rOuter, a.start), p1 = point(rOuter, a.end);
      var ip0 = point(rInner, a.start), ip1 = point(rInner, a.end);
      var largeArc = (a.end - a.start) > Math.PI ? 1 : 0;
      var d =
        'M ' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) +
        ' A ' + rOuter + ' ' + rOuter + ' 0 ' + largeArc + ' 1 ' + p1[0].toFixed(1) + ' ' + p1[1].toFixed(1) +
        ' L ' + ip1[0].toFixed(1) + ' ' + ip1[1].toFixed(1) +
        ' A ' + rInner + ' ' + rInner + ' 0 ' + largeArc + ' 0 ' + ip0[0].toFixed(1) + ' ' + ip0[1].toFixed(1) +
        ' Z';
      var color = palette[a.group.color] || palette.accent;
      parts.push('<path d="' + d + '" fill="' + color + '" class="okc-chord-arc"><title>' + escapeXml((a.group.label || a.group.id) + ': ' + fmtNum(totals[a.idx])) + '</title></path>');
      // Label outside the arc.
      var mid = (a.start + a.end) / 2;
      var lp = point(rOuter + 14, mid);
      var anchor = Math.cos(mid) < -0.2 ? 'end' : (Math.cos(mid) > 0.2 ? 'start' : 'middle');
      parts.push('<text x="' + lp[0].toFixed(1) + '" y="' + lp[1].toFixed(1) + '" text-anchor="' + anchor + '" dominant-baseline="middle" class="okc-chord-label">' + escapeXml(a.group.label || a.group.id) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Tier 3 — geo ----------------
     Tile cartogram. Each region gets a uniformly-sized cell in a
     grid that approximates world geography. Cell fill scales with
     value via a sequential colour ramp. Designed for "country / market
     comparison" charts without dragging in real map tile data — keeps
     the kit's no-build ethos intact.
     The tile grid is fixed and ships ~60 regions (US, EU, BR, IN, CN,
     ...) at hardcoded (col, row) positions. Authors pass {id, value}
     for the regions they care about; cells for absent regions render
     as faint outlines. */
  _renderGeo() {
    var x = (this._extras && this._extras.geo) || {};
    var regions = (x.regions || []).slice();
    if (!regions.length) return;
    var values = regions.map(function (r) { return +r.value; }).filter(function (v) { return !isNaN(v); });
    if (!values.length) return;
    var vMin = Math.min.apply(null, values);
    var vMax = Math.max.apply(null, values);
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    // Tile grid — (col, row) per region. 11 columns × 7 rows; roughly
    // matches a flattened world (Americas left, Europe + Africa middle,
    // Asia + Oceania right). Coordinates picked to be readable rather
    // than geographically exact.
    var TILES = {
      // North America
      CA: [1, 1], US: [1, 2], MX: [1, 3],
      // South America
      CO: [2, 3], BR: [2, 4], AR: [2, 5], CL: [2, 5], PE: [1, 4],
      // Europe (col 4-5)
      IS: [4, 1], GB: [4, 2], IE: [3, 2], NO: [5, 1], SE: [5, 1], FI: [6, 1],
      PT: [3, 3], ES: [4, 3], FR: [4, 3], NL: [5, 2], BE: [4, 2], DE: [5, 2], DK: [5, 1], PL: [6, 2],
      IT: [5, 3], CH: [4, 3], AT: [5, 3], CZ: [6, 3], SK: [6, 3], HU: [6, 3], RO: [6, 3], GR: [5, 4],
      UA: [7, 2], RU: [8, 1],
      // Middle East + Africa
      TR: [6, 4], IL: [5, 4], SA: [6, 5], AE: [7, 5], IR: [7, 4], EG: [5, 5],
      ZA: [5, 6], NG: [4, 5], KE: [5, 5], ET: [6, 5], MA: [4, 4],
      // Asia
      IN: [7, 4], PK: [7, 3], BD: [8, 4], CN: [8, 3], JP: [9, 3], KR: [9, 3], TW: [9, 4],
      VN: [9, 4], TH: [8, 5], MY: [9, 5], SG: [9, 5], ID: [9, 6], PH: [10, 5],
      // Oceania
      AU: [10, 6], NZ: [10, 7],
      // Synthetic bucket for everything else
      OTH: [0, 0]
    };
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var cellW = 54, cellH = 36, cellGap = 4;
    var maxCol = 10, maxRow = 7;
    var W = (maxCol + 1) * (cellW + cellGap) + 40;
    var H = (maxRow + 1) * (cellH + cellGap) + 80;
    var titleTop = this._title ? 28 : 12;
    var legendY = H - 36;
    var byId = {};
    regions.forEach(function (r) { byId[r.id] = r; });
    function fillFor(value) {
      // Linear interpolation in the accent ramp via fill-opacity 0.2 → 1.
      var t = Math.max(0, Math.min(1, (value - vMin) / (vMax - vMin)));
      return { color: palette.accent, opacity: 0.2 + t * 0.8 };
    }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Geo cartogram') + '" class="okc-svg okc-geo">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Render every tile in the grid — present regions get colour;
    // absent get a faint placeholder outline so the geography reads.
    Object.keys(TILES).forEach(function (id) {
      var pos = TILES[id];
      var col = pos[0], row = pos[1];
      var px = 20 + col * (cellW + cellGap);
      var py = titleTop + 12 + row * (cellH + cellGap);
      var r = byId[id];
      var attrs;
      if (r) {
        var f = fillFor(+r.value);
        var payload = JSON.stringify({
          label: r.label || id,
          kv: [{ k: 'value', v: fmtNum(+r.value) }, { k: 'region', v: id }]
        });
        attrs = ' fill="' + f.color + '" fill-opacity="' + f.opacity.toFixed(2) + '" data-hover-payload="' + escapeXml(payload) + '"';
        parts.push('<g class="okc-geo-cell okc-geo-cell-on" tabindex="0">');
        parts.push('<rect x="' + px + '" y="' + py + '" width="' + cellW + '" height="' + cellH + '" rx="3"' + attrs + '/>');
        parts.push('<text x="' + (px + cellW / 2) + '" y="' + (py + cellH / 2 - 2) + '" text-anchor="middle" class="okc-geo-code">' + escapeXml(id) + '</text>');
        parts.push('<text x="' + (px + cellW / 2) + '" y="' + (py + cellH / 2 + 12) + '" text-anchor="middle" class="okc-geo-value">' + escapeXml(fmtNum(+r.value)) + '</text>');
        parts.push('<title>' + escapeXml((r.label || id) + ': ' + fmtNum(+r.value)) + '</title>');
        parts.push('</g>');
      } else {
        parts.push('<rect x="' + px + '" y="' + py + '" width="' + cellW + '" height="' + cellH + '" rx="3" class="okc-geo-cell-off"/>');
        parts.push('<text x="' + (px + cellW / 2) + '" y="' + (py + cellH / 2 + 4) + '" text-anchor="middle" class="okc-geo-code-off">' + escapeXml(id) + '</text>');
      }
    });
    // Legend — value scale band at the bottom.
    var lgW = 240, lgX = (W - lgW) / 2, lgH = 12;
    var stops = 12;
    for (var s = 0; s < stops; s++) {
      var t = s / (stops - 1);
      parts.push('<rect x="' + (lgX + s * (lgW / stops)).toFixed(1) + '" y="' + legendY + '" width="' + (lgW / stops + 0.5).toFixed(2) + '" height="' + lgH + '" fill="' + palette.accent + '" fill-opacity="' + (0.2 + t * 0.8).toFixed(2) + '"/>');
    }
    parts.push('<text x="' + lgX + '" y="' + (legendY + lgH + 14) + '" class="okc-geo-legend-tick">' + escapeXml(fmtNum(vMin)) + '</text>');
    parts.push('<text x="' + (lgX + lgW) + '" y="' + (legendY + lgH + 14) + '" text-anchor="end" class="okc-geo-legend-tick">' + escapeXml(fmtNum(vMax)) + '</text>');
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Dot plot ----------------
     One row per category; a single dot positioned on a continuous
     x-axis. Compact comparison shape — like a horizontal bar
     stripped to just the endpoint. Useful when bar length itself
     adds visual noise (ratios near each other, ordered lists). */
  _renderDotPlot() {
    var x = (this._extras && this._extras['dot-plot']) || {};
    var rows = (x.rows || []).slice();
    if (!rows.length) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var vMin = x.min !== undefined ? +x.min : Math.min.apply(null, rows.map(function (r) { return +r.value || 0; }));
    var vMax = x.max !== undefined ? +x.max : Math.max.apply(null, rows.map(function (r) { return +r.value || 0; }));
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    var W = 640, rowH = 28;
    var pad = { top: this._title ? 36 : 12, bottom: 28, left: 140, right: 24 };
    var H = pad.top + rows.length * rowH + pad.bottom;
    var plotW = W - pad.left - pad.right;
    function xOf(v) { return pad.left + (v - vMin) / (vMax - vMin) * plotW; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Dot plot') + '" class="okc-svg okc-dot-plot">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Faint baseline + ticks at min/max + midpoint.
    [vMin, (vMin + vMax) / 2, vMax].forEach(function (v) {
      var xx = xOf(v);
      parts.push('<line x1="' + xx.toFixed(1) + '" y1="' + pad.top + '" x2="' + xx.toFixed(1) + '" y2="' + (H - pad.bottom + 4) + '" class="okc-axis" stroke-dasharray="2 3"/>');
      parts.push('<text x="' + xx.toFixed(1) + '" y="' + (H - pad.bottom + 18) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    });
    rows.forEach(function (r, i) {
      var y = pad.top + i * rowH + rowH / 2;
      var color = palette[r.color] || palette.accent;
      parts.push('<text x="' + (pad.left - 10) + '" y="' + (y + 4) + '" text-anchor="end" class="okc-dot-plot-label">' + escapeXml(r.label || '') + '</text>');
      // Connector from axis-left to dot (light) so the row reads as a single beat.
      parts.push('<line x1="' + pad.left + '" y1="' + y + '" x2="' + xOf(+r.value || 0).toFixed(1) + '" y2="' + y + '" class="okc-dot-plot-track"/>');
      var payload = JSON.stringify({ label: r.label || '', kv: [{ k: 'value', v: fmtNum(+r.value || 0) }] });
      parts.push('<circle cx="' + xOf(+r.value || 0).toFixed(1) + '" cy="' + y + '" r="6" fill="' + color + '" class="okc-dot-plot-dot" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((r.label || '') + ' · ' + fmtNum(+r.value || 0)) + '</title></circle>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: H - pad.bottom, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Density plot ----------------
     Smoothed histogram via Gaussian KDE. Bandwidth defaults to
     Silverman's rule of thumb (1.06·σ·n^-1/5) — author can override
     with bandwidth. The curve is sampled at sample_count x-positions
     (default 100) across the data range. */
  _renderDensity() {
    var x = (this._extras && this._extras.density) || {};
    var values = (x.values || []).map(Number).filter(function (v) { return !isNaN(v); });
    if (values.length < 2) return;
    values.sort(function (a, b) { return a - b; });
    var vMin = x.min !== undefined ? +x.min : values[0];
    var vMax = x.max !== undefined ? +x.max : values[values.length - 1];
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    // Bandwidth — Silverman's rule on the input range.
    var mean = values.reduce(function (s, v) { return s + v; }, 0) / values.length;
    var variance = values.reduce(function (s, v) { return s + (v - mean) * (v - mean); }, 0) / values.length;
    var stdev = Math.sqrt(variance) || 1;
    var bw = +x.bandwidth || 1.06 * stdev * Math.pow(values.length, -1 / 5);
    var sampleCount = +x.sample_count || 100;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)' };
    var color = palette[x.color] || palette.accent;
    var W = 640, H = this._title ? 320 : 280;
    var pad = { top: this._title ? 36 : 16, bottom: 32, left: 36, right: 24 };
    var plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    // Compute density samples.
    var step = (vMax - vMin) / (sampleCount - 1);
    var samples = [];
    var maxDensity = 0;
    for (var i = 0; i < sampleCount; i++) {
      var xi = vMin + i * step;
      var sum = 0;
      for (var k = 0; k < values.length; k++) {
        var u = (xi - values[k]) / bw;
        sum += Math.exp(-0.5 * u * u);
      }
      var d = sum / (values.length * bw * Math.sqrt(2 * Math.PI));
      samples.push({ x: xi, d: d });
      if (d > maxDensity) maxDensity = d;
    }
    if (maxDensity === 0) maxDensity = 1;
    function xOf(v) { return pad.left + (v - vMin) / (vMax - vMin) * plotW; }
    function yOf(d) { return pad.top + plotH - (d / maxDensity) * plotH; }
    var pathD = samples.map(function (s, idx) {
      return (idx === 0 ? 'M ' : 'L ') + xOf(s.x).toFixed(1) + ' ' + yOf(s.d).toFixed(1);
    }).join(' ');
    var areaD = pathD + ' L ' + xOf(samples[samples.length - 1].x).toFixed(1) + ' ' + (pad.top + plotH).toFixed(1) +
                ' L ' + xOf(samples[0].x).toFixed(1) + ' ' + (pad.top + plotH).toFixed(1) + ' Z';
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Density') + '" class="okc-svg okc-density">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // X-axis ticks at vMin / mid / vMax.
    [vMin, (vMin + vMax) / 2, vMax].forEach(function (v) {
      var xx = xOf(v);
      parts.push('<text x="' + xx.toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    });
    parts.push('<line x1="' + pad.left + '" y1="' + (pad.top + plotH) + '" x2="' + (W - pad.right) + '" y2="' + (pad.top + plotH) + '" class="okc-axis"/>');
    parts.push('<path d="' + areaD + '" fill="' + color + '" fill-opacity="0.22" stroke="none"/>');
    parts.push('<path d="' + pathD + '" stroke="' + color + '" stroke-width="2" fill="none" class="okc-density-line"/>');
    // Tiny rug at the bottom to show actual data positions.
    var rugY = pad.top + plotH + 3;
    values.forEach(function (v) {
      parts.push('<line x1="' + xOf(v).toFixed(1) + '" y1="' + rugY + '" x2="' + xOf(v).toFixed(1) + '" y2="' + (rugY + 6) + '" stroke="' + color + '" stroke-opacity="0.45"/>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: pad.top + plotH, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Candlestick ----------------
     Financial OHLC. Each entry: { date, open, high, low, close }.
     Up day (close > open) renders in success; down day in danger.
     Bar from open→close + wick from low→high. */
  _renderCandlestick() {
    var x = (this._extras && this._extras.candlestick) || {};
    var entries = (x.entries || []).slice();
    if (!entries.length) return;
    var allValues = [];
    entries.forEach(function (e) {
      allValues.push(+e.low, +e.high);
    });
    var vMin = Math.min.apply(null, allValues);
    var vMax = Math.max.apply(null, allValues);
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    var pad = { top: this._title ? 36 : 16, bottom: 28, left: 48, right: 12 };
    var W = 640, H = this._title ? 360 : 320;
    var plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    var step = plotW / entries.length;
    var bw = Math.min(step * 0.7, 22);
    function yOf(v) { return pad.top + plotH - (v - vMin) / (vMax - vMin) * plotH; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Candlestick') + '" class="okc-svg okc-candlestick">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Y-axis ticks (5).
    var ticks = 5;
    for (var t = 0; t <= ticks; t++) {
      var v = vMin + (t / ticks) * (vMax - vMin);
      var ty = yOf(v);
      parts.push('<line x1="' + pad.left + '" y1="' + ty.toFixed(1) + '" x2="' + (W - pad.right) + '" y2="' + ty.toFixed(1) + '" class="okc-axis" stroke-dasharray="2 3"/>');
      parts.push('<text x="' + (pad.left - 6) + '" y="' + (ty + 4).toFixed(1) + '" text-anchor="end" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    }
    entries.forEach(function (e, i) {
      var cx = pad.left + step * (i + 0.5);
      var up = (+e.close) >= (+e.open);
      var color = up ? 'var(--success)' : 'var(--danger)';
      var yOpen = yOf(+e.open), yClose = yOf(+e.close);
      var yHigh = yOf(+e.high), yLow = yOf(+e.low);
      var bodyTop = Math.min(yOpen, yClose);
      var bodyH = Math.max(1, Math.abs(yClose - yOpen));
      var payload = JSON.stringify({
        label: e.date || '',
        kv: [
          { k: 'O', v: fmtNum(+e.open) },
          { k: 'H', v: fmtNum(+e.high) },
          { k: 'L', v: fmtNum(+e.low) },
          { k: 'C', v: fmtNum(+e.close) }
        ]
      });
      // Wick.
      parts.push('<line x1="' + cx.toFixed(1) + '" y1="' + yHigh.toFixed(1) + '" x2="' + cx.toFixed(1) + '" y2="' + yLow.toFixed(1) + '" stroke="' + color + '" stroke-width="1.2" class="okc-candle-wick"/>');
      // Body.
      parts.push('<rect x="' + (cx - bw / 2).toFixed(1) + '" y="' + bodyTop.toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + bodyH.toFixed(1) + '" fill="' + color + '" fill-opacity="' + (up ? '0.85' : '0.95') + '" stroke="' + color + '" class="okc-candle-body" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((e.date || '') + ' O ' + e.open + ' H ' + e.high + ' L ' + e.low + ' C ' + e.close) + '</title></rect>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: pad.top + plotH, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Sunburst ----------------
     Radial hierarchy chart. Each tree node renders as an arc at its
     depth ring; arc length is proportional to the node's value sum.
     Input tree: nested { label, value, children }. */
  _renderSunburst() {
    var x = (this._extras && this._extras.sunburst) || {};
    var root = x.tree || x.root || (Array.isArray(x.tree) ? { children: x.tree } : null);
    if (!root) return;
    // Compute per-node value rollup.
    function rollup(node) {
      if (!node.children || !node.children.length) {
        node._value = Math.max(0, +node.value || 0);
        return node._value;
      }
      node._value = 0;
      node.children.forEach(function (c) { node._value += rollup(c); });
      return node._value;
    }
    // Single-root or multi-root: unify to { children: [...] }.
    var rootNode = Array.isArray(root) ? { children: root } : root;
    if (Array.isArray(rootNode.children)) {
      rootNode._value = 0;
      rootNode.children.forEach(function (c) { rootNode._value += rollup(c); });
    } else {
      rollup(rootNode);
    }
    if (!rootNode._value) return;
    function maxDepth(node, d) {
      if (!node.children || !node.children.length) return d;
      var m = d;
      node.children.forEach(function (c) { m = Math.max(m, maxDepth(c, d + 1)); });
      return m;
    }
    var depth = maxDepth(rootNode, 0);
    if (depth < 1) return;
    var palette = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)', 'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)', 'var(--series-9)', 'var(--series-10)'];
    // Reserve room for the title above the wheel so the outermost
    // ring doesn't run under the title text. Without the offset the
    // title (y=20) and the top of the outer arc (cy-rMax) collided
    // for any non-trivial wheel.
    var titleH = this._title ? 28 : 8;
    var W = 480, H = 480 + titleH;
    var cx = W / 2, cy = (H + titleH) / 2;
    var rMax = Math.min(W, H - titleH) / 2 - 12;
    var rMin = 36;
    var ringW = (rMax - rMin) / depth;
    var totalValue = rootNode._value;
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Sunburst') + '" class="okc-svg okc-sunburst">');
    if (this._title) parts.push('<text x="' + cx + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    function arcPath(rIn, rOut, a0, a1) {
      var large = (a1 - a0) > Math.PI ? 1 : 0;
      var p0 = [cx + rOut * Math.cos(a0), cy + rOut * Math.sin(a0)];
      var p1 = [cx + rOut * Math.cos(a1), cy + rOut * Math.sin(a1)];
      var p2 = [cx + rIn  * Math.cos(a1), cy + rIn  * Math.sin(a1)];
      var p3 = [cx + rIn  * Math.cos(a0), cy + rIn  * Math.sin(a0)];
      return 'M ' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) +
             ' A ' + rOut + ' ' + rOut + ' 0 ' + large + ' 1 ' + p1[0].toFixed(1) + ' ' + p1[1].toFixed(1) +
             ' L ' + p2[0].toFixed(1) + ' ' + p2[1].toFixed(1) +
             ' A ' + rIn  + ' ' + rIn  + ' 0 ' + large + ' 0 ' + p3[0].toFixed(1) + ' ' + p3[1].toFixed(1) + ' Z';
    }
    // Walk + paint per ring.
    var paletteIdx = 0;
    function walk(node, d, a0, a1, color) {
      if (d > 0) {
        var label = node.label || '';
        var sharePct = totalValue > 0 ? Math.round((node._value / totalValue) * 100) : 0;
        var payload = JSON.stringify({
          label: label,
          kv: [
            { k: 'value', v: fmtNum(node._value) },
            { k: 'share', v: sharePct + '%' },
            { k: 'depth', v: String(d) }
          ],
          footer: 'of ' + fmtNum(totalValue)
        });
        var rIn = rMin + (d - 1) * ringW;
        var rOut = rIn + ringW;
        parts.push('<path d="' + arcPath(rIn, rOut, a0, a1) + '" fill="' + color + '" fill-opacity="' + (0.55 + d * 0.07).toFixed(2) + '" stroke="var(--bg)" stroke-width="1" class="okc-sunburst-arc" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml(label + ' · ' + fmtNum(node._value) + ' (' + sharePct + '%)') + '</title></path>');
      }
      if (!node.children || !node.children.length) return;
      var span = a1 - a0;
      var offset = 0;
      node.children.forEach(function (c) {
        var frac = node._value > 0 ? (c._value / node._value) : 0;
        var ca0 = a0 + offset * span;
        var ca1 = a0 + (offset + frac) * span;
        var childColor = d === 0 ? palette[paletteIdx++ % palette.length] : color;
        walk(c, d + 1, ca0, ca1, childColor);
        offset += frac;
      });
    }
    walk(rootNode, 0, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2, palette[0]);
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Marimekko (variable-width stacked bar) ----------------
     Like stacked-bar except each column's WIDTH is proportional to
     that column's total — so the chart shows both within-column
     proportions and across-column magnitudes in one read. */
  _renderMarimekko() {
    var x = (this._extras && this._extras.marimekko) || {};
    var categories = x.categories || [];
    var series = x.series || [];
    if (!categories.length || !series.length) return;
    var palette = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)', 'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)'];
    // Column totals = sum across series for each category.
    var colTotals = categories.map(function (_, i) {
      return series.reduce(function (s, ser) { return s + Math.max(0, +(ser.values && ser.values[i]) || 0); }, 0);
    });
    var grandTotal = colTotals.reduce(function (s, v) { return s + v; }, 0) || 1;
    var legendY = (this._title ? 30 : 12);
    var legendH = 18;
    var W = 640, H = (this._title ? 360 : 320);
    var pad = { top: legendY + legendH + 8, bottom: 36, left: 16, right: 16 };
    var plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Marimekko') + '" class="okc-svg okc-marimekko">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    parts.push(this._renderSeriesLegend(series, palette, { x: pad.left, y: legendY, width: plotW, idxAttr: 'series-idx' }));
    var xCursor = pad.left;
    categories.forEach(function (cat, ci) {
      var colW = (colTotals[ci] / grandTotal) * plotW;
      if (colW <= 0) return;
      var colTotal = colTotals[ci] || 1;
      var yCursor = pad.top;
      series.forEach(function (ser, si) {
        var v = Math.max(0, +(ser.values && ser.values[ci]) || 0);
        var segH = (v / colTotal) * plotH;
        var color = palette[si % palette.length];
        var payload = JSON.stringify({
          label: (ser.label || '') + ' · ' + cat,
          kv: [
            { k: 'value', v: fmtNum(v) },
            { k: '% of col', v: Math.round((v / colTotal) * 100) + '%' }
          ]
        });
        parts.push('<rect x="' + xCursor.toFixed(1) + '" y="' + yCursor.toFixed(1) + '" width="' + colW.toFixed(1) + '" height="' + segH.toFixed(1) + '" fill="' + color + '" stroke="var(--bg)" stroke-width="1" class="okc-marimekko-cell" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((ser.label || '') + ' · ' + cat + ' · ' + fmtNum(v)) + '</title></rect>');
        yCursor += segH;
      });
      // Category label at the bottom of the column.
      parts.push('<text x="' + (xCursor + colW / 2).toFixed(1) + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="okc-tick">' + escapeXml(cat) + '</text>');
      xCursor += colW;
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Stream graph (centered stacked area) ----------------
     Same data shape as stacked-bar (categories + series.values) but
     each layer is centered on the x-axis instead of stacked from the
     bottom. Useful for showing composition trends where the total
     varies. */
  _renderStream() {
    var x = (this._extras && this._extras.stream) || {};
    var categories = x.categories || [];
    var series = x.series || [];
    if (categories.length < 2 || !series.length) return;
    var palette = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)', 'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)'];
    // Per-category total — used to centre each column's stack.
    var totals = categories.map(function (_, i) {
      return series.reduce(function (s, ser) { return s + Math.max(0, +(ser.values && ser.values[i]) || 0); }, 0);
    });
    var maxTotal = Math.max.apply(null, totals.concat([1]));
    var legendY = (this._title ? 30 : 12);
    var legendH = 18;
    var W = 640, H = this._title ? 320 : 280;
    var pad = { top: legendY + legendH + 8, bottom: 30, left: 36, right: 12 };
    var plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    function xOf(i) { return pad.left + (i / (categories.length - 1)) * plotW; }
    function scaleY(v) { return (v / maxTotal) * plotH; }
    // Per-series, compute the top and bottom edges across categories.
    var bands = series.map(function () { return { top: [], bottom: [] }; });
    for (var i = 0; i < categories.length; i++) {
      var total = totals[i];
      var halfTotal = scaleY(total) / 2;
      var midY = pad.top + plotH / 2;
      var cursor = midY - halfTotal;
      for (var s = 0; s < series.length; s++) {
        var v = Math.max(0, +(series[s].values && series[s].values[i]) || 0);
        var h = scaleY(v);
        bands[s].top.push({ x: xOf(i), y: cursor });
        bands[s].bottom.push({ x: xOf(i), y: cursor + h });
        cursor += h;
      }
    }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Stream graph') + '" class="okc-svg okc-stream">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    parts.push(this._renderSeriesLegend(series, palette, { x: pad.left, y: legendY, width: plotW, idxAttr: 'series-idx' }));
    bands.forEach(function (b, si) {
      var color = palette[si % palette.length];
      var d = b.top.map(function (p, j) {
        return (j === 0 ? 'M ' : 'L ') + p.x.toFixed(1) + ' ' + p.y.toFixed(1);
      }).join(' ');
      for (var j = b.bottom.length - 1; j >= 0; j--) {
        d += ' L ' + b.bottom[j].x.toFixed(1) + ' ' + b.bottom[j].y.toFixed(1);
      }
      d += ' Z';
      var payload = JSON.stringify({ label: series[si].label || '', kv: [{ k: 'series', v: series[si].label || '' }] });
      parts.push('<path d="' + d + '" fill="' + color + '" fill-opacity="0.78" stroke="var(--bg)" stroke-width="0.6" class="okc-stream-band" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml(series[si].label || '') + '</title></path>');
    });
    // Category ticks at bottom.
    categories.forEach(function (c, i) {
      parts.push('<text x="' + xOf(i).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle" class="okc-tick">' + escapeXml(c) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor(
      { top: pad.top, bottom: pad.top + plotH, left: pad.left, right: W - pad.right },
      {
        seriesLookup: function (svgX) {
          // Find the nearest category index by inverting xOf.
          var nearestIdx = 0;
          var bestDelta = Math.abs(xOf(0) - svgX);
          for (var i = 1; i < categories.length; i++) {
            var d = Math.abs(xOf(i) - svgX);
            if (d < bestDelta) { bestDelta = d; nearestIdx = i; }
          }
          var rows = series.map(function (s) {
            var v = +(s.values && s.values[nearestIdx]) || 0;
            return { k: s.label || '', v: fmtNum(v) };
          });
          return { label: categories[nearestIdx], kv: rows };
        }
      }
    );
  }

  /* ---------------- Violin ----------------
     Kernel-density box-plot alternative. One violin per distribution.
     Shape: mirrored density curve, with median + IQR marked. */
  _renderViolin() {
    var x = (this._extras && this._extras.violin) || {};
    var distributions = (x.distributions || []).slice();
    if (!distributions.length) return;
    // Compute global range across all values.
    var allValues = [];
    distributions.forEach(function (d) {
      (d.values || []).forEach(function (v) { if (!isNaN(+v)) allValues.push(+v); });
    });
    if (allValues.length < 2) return;
    var vMin = Math.min.apply(null, allValues);
    var vMax = Math.max.apply(null, allValues);
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    var W = 640, H = 80 + distributions.length * 80;
    var pad = { top: this._title ? 36 : 16, bottom: 28, left: 120, right: 20 };
    var plotW = W - pad.left - pad.right;
    var rowH = (H - pad.top - pad.bottom) / distributions.length;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    function xOf(v) { return pad.left + (v - vMin) / (vMax - vMin) * plotW; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Violin') + '" class="okc-svg okc-violin">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    distributions.forEach(function (dist, di) {
      var values = (dist.values || []).map(Number).filter(function (v) { return !isNaN(v); });
      if (values.length < 2) return;
      values.sort(function (a, b) { return a - b; });
      var color = palette[dist.color] || palette.accent;
      var rowMid = pad.top + di * rowH + rowH / 2;
      // KDE setup — Silverman bandwidth per distribution.
      var mean = values.reduce(function (s, v) { return s + v; }, 0) / values.length;
      var variance = values.reduce(function (s, v) { return s + (v - mean) * (v - mean); }, 0) / values.length;
      var stdev = Math.sqrt(variance) || 1;
      var bw = 1.06 * stdev * Math.pow(values.length, -1 / 5);
      var sampleCount = 80;
      var samples = [];
      var maxD = 0;
      var step = (vMax - vMin) / (sampleCount - 1);
      for (var i = 0; i < sampleCount; i++) {
        var xi = vMin + i * step;
        var sum = 0;
        for (var k = 0; k < values.length; k++) {
          var u = (xi - values[k]) / bw;
          sum += Math.exp(-0.5 * u * u);
        }
        var d = sum / (values.length * bw * Math.sqrt(2 * Math.PI));
        samples.push({ x: xi, d: d });
        if (d > maxD) maxD = d;
      }
      if (maxD === 0) return;
      var halfH = rowH * 0.4;
      // Build mirrored violin polygon.
      var topPath = samples.map(function (s, idx) {
        var y = rowMid - (s.d / maxD) * halfH;
        return (idx === 0 ? 'M ' : 'L ') + xOf(s.x).toFixed(1) + ' ' + y.toFixed(1);
      }).join(' ');
      var bottomPath = '';
      for (var j = samples.length - 1; j >= 0; j--) {
        var y = rowMid + (samples[j].d / maxD) * halfH;
        bottomPath += ' L ' + xOf(samples[j].x).toFixed(1) + ' ' + y.toFixed(1);
      }
      parts.push('<path d="' + topPath + bottomPath + ' Z" fill="' + color + '" fill-opacity="0.32" stroke="' + color + '" stroke-width="1.2" class="okc-violin-body"/>');
      // Quartile + median markers.
      function quantile(p) {
        var pos = (values.length - 1) * p;
        var i = Math.floor(pos);
        var frac = pos - i;
        return values[i] + frac * ((values[i + 1] || values[i]) - values[i]);
      }
      var q1 = quantile(0.25), median = quantile(0.5), q3 = quantile(0.75);
      // IQR box.
      parts.push('<rect x="' + xOf(q1).toFixed(1) + '" y="' + (rowMid - 5).toFixed(1) + '" width="' + (xOf(q3) - xOf(q1)).toFixed(1) + '" height="10" fill="' + color + '" fill-opacity="0.7" stroke="none"/>');
      // Median line.
      parts.push('<line x1="' + xOf(median).toFixed(1) + '" y1="' + (rowMid - 10).toFixed(1) + '" x2="' + xOf(median).toFixed(1) + '" y2="' + (rowMid + 10).toFixed(1) + '" stroke="var(--bg)" stroke-width="2"/>');
      // Label on the left.
      parts.push('<text x="' + (pad.left - 12) + '" y="' + (rowMid + 4).toFixed(1) + '" text-anchor="end" class="okc-violin-label">' + escapeXml(dist.label || '') + '</text>');
    });
    // Bottom axis ticks at vMin / mid / vMax.
    [vMin, (vMin + vMax) / 2, vMax].forEach(function (v) {
      parts.push('<text x="' + xOf(v).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: H - pad.bottom, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Beeswarm ----------------
     One-axis distribution rendered as jittered dots, one per data
     point. Vertical position is force-balanced to avoid overlap so
     the dot density at any x-position visually encodes count. */
  _renderBeeswarm() {
    var x = (this._extras && this._extras.beeswarm) || {};
    var values = (x.values || []).map(Number).filter(function (v) { return !isNaN(v); });
    if (values.length < 1) return;
    var vMin = Math.min.apply(null, values);
    var vMax = Math.max.apply(null, values);
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    var W = 640, H = this._title ? 240 : 200;
    var pad = { top: this._title ? 36 : 16, bottom: 32, left: 24, right: 24 };
    var plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    var dotR = +x.dot_radius || 5;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)' };
    var color = palette[x.color] || palette.accent;
    function xOf(v) { return pad.left + (v - vMin) / (vMax - vMin) * plotW; }
    // Place dots greedily: for each value, compute its x. Then assign
    // y by checking existing placed dots in x-neighbourhood and
    // bumping above/below to avoid overlap. Output y centred around
    // the row mid.
    var placed = [];
    var mid = pad.top + plotH / 2;
    var sorted = values.slice().sort(function (a, b) { return a - b; });
    sorted.forEach(function (v) {
      var cx = xOf(v);
      var y = mid;
      var direction = 1; // try alternating up/down
      var step = 0;
      var safeIters = 200;
      while (safeIters-- > 0) {
        var clash = false;
        for (var i = 0; i < placed.length; i++) {
          var dx = placed[i].x - cx;
          var dy = placed[i].y - y;
          if (dx * dx + dy * dy < (dotR * 2.1) * (dotR * 2.1)) { clash = true; break; }
        }
        if (!clash) break;
        step++;
        y = mid + direction * step * (dotR * 1.4);
        direction *= -1;
        if (Math.abs(y - mid) > plotH / 2 - dotR) {
          y = mid + (Math.random() - 0.5) * (plotH - 2 * dotR);
        }
      }
      placed.push({ x: cx, y: y, v: v });
    });
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Beeswarm') + '" class="okc-svg okc-beeswarm">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    placed.forEach(function (p) {
      var payload = JSON.stringify({ label: '', kv: [{ k: 'value', v: fmtNum(p.v) }] });
      parts.push('<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + dotR + '" fill="' + color + '" fill-opacity="0.78" class="okc-beeswarm-dot" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml(fmtNum(p.v)) + '</title></circle>');
    });
    // Bottom axis ticks at min / mid / max.
    [vMin, (vMin + vMax) / 2, vMax].forEach(function (v) {
      parts.push('<text x="' + xOf(v).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: pad.top + plotH, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Waterfall chart ----------------
     Incremental changes connecting two totals: start → +A → −B →
     +C → end. Each step is a coloured bar floating at the running
     cumulative; positive bars rise from the prior cumulative,
     negative bars drop. Bookend bars (start / end) stand on the
     baseline. Bridges connect step tops to clarify the running
     line. */
  _renderWaterfall() {
    var x = (this._extras && this._extras.waterfall) || {};
    var steps = x.steps || [];
    if (!steps.length) return;
    // Pre-compute cumulative + per-step body extent.
    // step.kind: 'start' | 'plus' | 'minus' | 'end'
    var running = 0;
    var entries = steps.map(function (s) {
      var v = +s.value || 0;
      var top, bottom, kind = s.kind || (v >= 0 ? 'plus' : 'minus');
      if (kind === 'start' || kind === 'total') {
        top = v; bottom = 0; running = v;
      } else if (kind === 'end') {
        top = running; bottom = 0;
      } else if (kind === 'minus' || v < 0) {
        bottom = running;
        top = running + v;
        running += v;
      } else {
        bottom = running;
        top = running + v;
        running += v;
      }
      return { label: s.label || '', kind: kind, value: v, top: top, bottom: bottom, running: running };
    });
    var allValues = entries.flatMap(function (e) { return [e.top, e.bottom, 0]; });
    var vMin = Math.min.apply(null, allValues);
    var vMax = Math.max.apply(null, allValues);
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    var pad = { top: this._title ? 36 : 16, bottom: 36, left: 56, right: 16 };
    var W = 640, H = this._title ? 360 : 320;
    var plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    var step = plotW / entries.length;
    var bw = Math.min(step * 0.65, 48);
    function yOf(v) { return pad.top + plotH - (v - vMin) / (vMax - vMin) * plotH; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Waterfall') + '" class="okc-svg okc-waterfall">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Y-axis ticks (5).
    for (var t = 0; t <= 4; t++) {
      var v = vMin + (t / 4) * (vMax - vMin);
      var ty = yOf(v);
      parts.push('<line x1="' + pad.left + '" y1="' + ty.toFixed(1) + '" x2="' + (W - pad.right) + '" y2="' + ty.toFixed(1) + '" class="okc-axis" stroke-dasharray="2 3"/>');
      parts.push('<text x="' + (pad.left - 6) + '" y="' + (ty + 4).toFixed(1) + '" text-anchor="end" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    }
    // Zero baseline.
    parts.push('<line x1="' + pad.left + '" y1="' + yOf(0).toFixed(1) + '" x2="' + (W - pad.right) + '" y2="' + yOf(0).toFixed(1) + '" class="okc-axis"/>');
    // Bridges first (under the bars).
    entries.forEach(function (e, i) {
      if (i === 0) return;
      var prevRight = pad.left + step * i - (step - bw) / 2;
      var thisLeft  = pad.left + step * i + (step - bw) / 2;
      var prevRun = entries[i - 1].running;
      parts.push('<line x1="' + prevRight.toFixed(1) + '" y1="' + yOf(prevRun).toFixed(1) + '" x2="' + thisLeft.toFixed(1) + '" y2="' + yOf(prevRun).toFixed(1) + '" class="okc-waterfall-bridge" stroke-dasharray="2 3"/>');
    });
    entries.forEach(function (e, i) {
      var cx = pad.left + step * (i + 0.5);
      var color, kindClass;
      if (e.kind === 'start' || e.kind === 'end' || e.kind === 'total') {
        color = 'var(--accent)'; kindClass = 'okc-waterfall-total';
      } else if (e.kind === 'minus' || e.value < 0) {
        color = 'var(--danger)'; kindClass = 'okc-waterfall-minus';
      } else {
        color = 'var(--success)'; kindClass = 'okc-waterfall-plus';
      }
      var yT = yOf(Math.max(e.top, e.bottom));
      var yB = yOf(Math.min(e.top, e.bottom));
      var h  = Math.max(2, yB - yT);
      var payload = JSON.stringify({
        label: e.label,
        kv: [
          { k: 'change',     v: (e.value >= 0 ? '+' : '') + fmtNum(e.value) },
          { k: 'cumulative', v: fmtNum(e.running) }
        ]
      });
      parts.push('<rect x="' + (cx - bw / 2).toFixed(1) + '" y="' + yT.toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + h.toFixed(1) + '" rx="2" fill="' + color + '" class="okc-waterfall-bar ' + kindClass + '" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml(e.label + ' · ' + (e.value >= 0 ? '+' : '') + fmtNum(e.value) + ' → ' + fmtNum(e.running)) + '</title></rect>');
      parts.push('<text x="' + cx.toFixed(1) + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="okc-tick">' + escapeXml(e.label) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: pad.top + plotH, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Lollipop chart ----------------
     Variant of dot-plot — same data shape, with a thin stem
     from the axis to the dot. Reads as a less-noisy bar chart
     when the value comparison is the headline. */
  _renderLollipop() {
    var x = (this._extras && this._extras.lollipop) || {};
    var rows = (x.rows || []).slice();
    if (!rows.length) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var vMin = x.min !== undefined ? +x.min : Math.min(0, Math.min.apply(null, rows.map(function (r) { return +r.value || 0; })));
    var vMax = x.max !== undefined ? +x.max : Math.max.apply(null, rows.map(function (r) { return +r.value || 0; }));
    if (vMin === vMax) { vMax += 1; }
    var W = 640, rowH = 28;
    var pad = { top: this._title ? 36 : 12, bottom: 28, left: 140, right: 24 };
    var H = pad.top + rows.length * rowH + pad.bottom;
    var plotW = W - pad.left - pad.right;
    function xOf(v) { return pad.left + (v - vMin) / (vMax - vMin) * plotW; }
    var x0 = xOf(0);
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Lollipop') + '" class="okc-svg okc-lollipop">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    parts.push('<line x1="' + x0.toFixed(1) + '" y1="' + pad.top + '" x2="' + x0.toFixed(1) + '" y2="' + (H - pad.bottom) + '" class="okc-axis"/>');
    rows.forEach(function (r, i) {
      var y = pad.top + i * rowH + rowH / 2;
      var color = palette[r.color] || palette.accent;
      var cx = xOf(+r.value || 0);
      parts.push('<text x="' + (pad.left - 10) + '" y="' + (y + 4) + '" text-anchor="end" class="okc-lollipop-label">' + escapeXml(r.label || '') + '</text>');
      parts.push('<line x1="' + x0.toFixed(1) + '" y1="' + y + '" x2="' + cx.toFixed(1) + '" y2="' + y + '" stroke="' + color + '" stroke-width="2" class="okc-lollipop-stem"/>');
      var payload = JSON.stringify({ label: r.label || '', kv: [{ k: 'value', v: fmtNum(+r.value || 0) }] });
      parts.push('<circle cx="' + cx.toFixed(1) + '" cy="' + y + '" r="6" fill="' + color + '" class="okc-lollipop-dot" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((r.label || '') + ' · ' + fmtNum(+r.value || 0)) + '</title></circle>');
    });
    // Bottom ticks.
    [vMin, (vMin + vMax) / 2, vMax].forEach(function (v) {
      parts.push('<text x="' + xOf(v).toFixed(1) + '" y="' + (H - pad.bottom + 18) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: H - pad.bottom, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Dumbbell / arrow plot ----------------
     Two dots per category joined by a line — before/after,
     men/women, 2010/2020. Compact alternative to the slope chart
     when many categories don't fit a slope layout. */
  _renderDumbbell() {
    var x = (this._extras && this._extras.dumbbell) || {};
    var rows = (x.rows || []).slice();
    if (!rows.length) return;
    var allVals = [];
    rows.forEach(function (r) { allVals.push(+r.from || 0, +r.to || 0); });
    var vMin = Math.min.apply(null, allVals);
    var vMax = Math.max.apply(null, allVals);
    if (vMin === vMax) { vMin -= 1; vMax += 1; }
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var fromColor = palette[x.from_color] || palette.muted;
    var toColor   = palette[x.to_color]   || palette.accent;
    var W = 640, rowH = 32;
    var pad = { top: this._title ? 36 : 12, bottom: 40, left: 140, right: 24 };
    var H = pad.top + rows.length * rowH + pad.bottom;
    var plotW = W - pad.left - pad.right;
    function xOf(v) { return pad.left + (v - vMin) / (vMax - vMin) * plotW; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Dumbbell') + '" class="okc-svg okc-dumbbell">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    rows.forEach(function (r, i) {
      var y = pad.top + i * rowH + rowH / 2;
      var fromX = xOf(+r.from || 0);
      var toX   = xOf(+r.to   || 0);
      var change = (+r.to || 0) - (+r.from || 0);
      var connectorColor = change >= 0 ? 'var(--success)' : 'var(--danger)';
      parts.push('<text x="' + (pad.left - 10) + '" y="' + (y + 4) + '" text-anchor="end" class="okc-dumbbell-label">' + escapeXml(r.label || '') + '</text>');
      parts.push('<line x1="' + fromX.toFixed(1) + '" y1="' + y + '" x2="' + toX.toFixed(1) + '" y2="' + y + '" stroke="' + connectorColor + '" stroke-width="3" stroke-opacity="0.4" class="okc-dumbbell-connector"/>');
      var fromPayload = JSON.stringify({ label: r.label + ' · ' + (x.from_label || 'from'), kv: [{ k: 'value', v: fmtNum(+r.from || 0) }] });
      var toPayload   = JSON.stringify({ label: r.label + ' · ' + (x.to_label || 'to'), kv: [{ k: 'value', v: fmtNum(+r.to || 0) }, { k: 'Δ', v: (change >= 0 ? '+' : '') + fmtNum(change) }] });
      parts.push('<circle cx="' + fromX.toFixed(1) + '" cy="' + y + '" r="5" fill="' + fromColor + '" class="okc-dumbbell-dot okc-dumbbell-from" tabindex="0" data-hover-payload="' + escapeXml(fromPayload) + '"><title>' + escapeXml((x.from_label || 'from') + ': ' + fmtNum(+r.from || 0)) + '</title></circle>');
      parts.push('<circle cx="' + toX.toFixed(1)   + '" cy="' + y + '" r="6" fill="' + toColor   + '" class="okc-dumbbell-dot okc-dumbbell-to"   tabindex="0" data-hover-payload="' + escapeXml(toPayload)   + '"><title>' + escapeXml((x.to_label   || 'to')   + ': ' + fmtNum(+r.to   || 0)) + '</title></circle>');
    });
    // Bottom ticks + legend.
    [vMin, (vMin + vMax) / 2, vMax].forEach(function (v) {
      parts.push('<text x="' + xOf(v).toFixed(1) + '" y="' + (H - pad.bottom + 18) + '" text-anchor="middle" class="okc-tick">' + escapeXml(fmtNum(v)) + '</text>');
    });
    if (x.from_label || x.to_label) {
      var lyt = H - 10;
      parts.push('<circle cx="' + (pad.left + 4) + '" cy="' + lyt + '" r="4" fill="' + fromColor + '"/>');
      parts.push('<text x="' + (pad.left + 14) + '" y="' + (lyt + 4) + '" class="okc-tick">' + escapeXml(x.from_label || 'from') + '</text>');
      parts.push('<circle cx="' + (pad.left + 90) + '" cy="' + lyt + '" r="5" fill="' + toColor + '"/>');
      parts.push('<text x="' + (pad.left + 100) + '" y="' + (lyt + 4) + '" class="okc-tick">' + escapeXml(x.to_label || 'to') + '</text>');
    }
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: H - pad.bottom, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Polar area / Nightingale rose ----------------
     Bars laid out around a circle. Cyclical categorical data
     (months, hours, compass directions) where the cyclic shape
     itself carries meaning. Distinct from radar — bars not polygon. */
  _renderPolarArea() {
    var x = (this._extras && this._extras['polar-area']) || {};
    var sectors = x.sectors || [];
    if (!sectors.length) return;
    var palette = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)', 'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)'];
    var vMax = Math.max.apply(null, sectors.map(function (s) { return +s.value || 0; }).concat([1]));
    var totalValue = sectors.reduce(function (s, c) { return s + Math.max(0, +c.value || 0); }, 0) || 1;
    var W = 420, H = 380;
    var cx = W / 2, cy = H / 2 + (this._title ? 8 : 0);
    var rMax = Math.min(W, H) / 2 - 36;
    var angleStep = (Math.PI * 2) / sectors.length;
    var startAngle = -Math.PI / 2 - angleStep / 2;
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Polar area') + '" class="okc-svg okc-polar-area">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Reference rings.
    [0.25, 0.5, 0.75, 1].forEach(function (f) {
      parts.push('<circle cx="' + cx + '" cy="' + cy + '" r="' + (rMax * f).toFixed(1) + '" fill="none" stroke="var(--border-soft)" stroke-dasharray="2 3"/>');
    });
    sectors.forEach(function (s, i) {
      var v = Math.max(0, +s.value || 0);
      var r = (v / vMax) * rMax;
      var a0 = startAngle + i * angleStep;
      var a1 = a0 + angleStep;
      var p0 = [cx + r * Math.cos(a0), cy + r * Math.sin(a0)];
      var p1 = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)];
      var large = angleStep > Math.PI ? 1 : 0;
      var d = 'M ' + cx + ' ' + cy +
              ' L ' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) +
              ' A ' + r.toFixed(1) + ' ' + r.toFixed(1) + ' 0 ' + large + ' 1 ' + p1[0].toFixed(1) + ' ' + p1[1].toFixed(1) +
              ' Z';
      var color = palette[i % palette.length];
      var sharePct = Math.round((v / totalValue) * 100);
      var payload = JSON.stringify({
        label: s.label || '',
        kv: [
          { k: 'value', v: fmtNum(v) },
          { k: 'share', v: sharePct + '%' }
        ],
        footer: 'of ' + fmtNum(totalValue)
      });
      parts.push('<path d="' + d + '" fill="' + color + '" fill-opacity="0.72" stroke="var(--bg)" stroke-width="1" class="okc-polar-area-sector" tabindex="0" data-slice-idx="' + i + '" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((s.label || '') + ' · ' + fmtNum(v) + ' (' + sharePct + '%)') + '</title></path>');
      // Label on outer perimeter.
      var labelA = a0 + angleStep / 2;
      var labelR = rMax + 14;
      var lx = cx + labelR * Math.cos(labelA);
      var ly = cy + labelR * Math.sin(labelA);
      var anchor = Math.cos(labelA) > 0.1 ? 'start' : Math.cos(labelA) < -0.1 ? 'end' : 'middle';
      parts.push('<text x="' + lx.toFixed(1) + '" y="' + (ly + 3).toFixed(1) + '" text-anchor="' + anchor + '" class="okc-polar-area-label">' + escapeXml(s.label || '') + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
  }

  /* ---------------- Gantt chart ----------------
     Horizontal bars positioned on a time axis, one per task.
     Tasks: { label, start, end, color?, group? }. start/end are
     numeric (interpret as days, hours, or unitless ticks per the
     author's data — the renderer treats them as continuous). */
  _renderGantt() {
    var x = (this._extras && this._extras.gantt) || {};
    var tasks = (x.tasks || []).slice();
    if (!tasks.length) return;
    var palette = { accent: 'var(--accent)', warn: 'var(--warning)', danger: 'var(--danger)', success: 'var(--success)', muted: 'var(--text-soft)' };
    var vMin = Math.min.apply(null, tasks.map(function (t) { return +t.start || 0; }));
    var vMax = Math.max.apply(null, tasks.map(function (t) { return +t.end   || 0; }));
    if (vMin === vMax) { vMax += 1; }
    var pad = { top: this._title ? 36 : 16, bottom: 36, left: 160, right: 16 };
    var rowH = 26;
    var W = 720, H = pad.top + tasks.length * rowH + pad.bottom;
    var plotW = W - pad.left - pad.right;
    function xOf(v) { return pad.left + (v - vMin) / (vMax - vMin) * plotW; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Gantt') + '" class="okc-svg okc-gantt">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Vertical grid lines (5).
    for (var t = 0; t <= 4; t++) {
      var v = vMin + (t / 4) * (vMax - vMin);
      var gx = xOf(v);
      parts.push('<line x1="' + gx.toFixed(1) + '" y1="' + pad.top + '" x2="' + gx.toFixed(1) + '" y2="' + (H - pad.bottom) + '" class="okc-axis" stroke-dasharray="2 3"/>');
      parts.push('<text x="' + gx.toFixed(1) + '" y="' + (H - pad.bottom + 18) + '" text-anchor="middle" class="okc-tick">' + (x.tick_format === 'date' ? new Date(+v).toISOString().slice(0, 10) : escapeXml(fmtNum(v))) + '</text>');
    }
    tasks.forEach(function (task, i) {
      var y = pad.top + i * rowH + 4;
      var bx = xOf(+task.start || 0);
      var bw = Math.max(2, xOf(+task.end || 0) - bx);
      var color = palette[task.color] || palette.accent;
      parts.push('<text x="' + (pad.left - 10) + '" y="' + (y + 14) + '" text-anchor="end" class="okc-gantt-label">' + escapeXml(task.label || '') + '</text>');
      var payload = JSON.stringify({
        label: task.label || '',
        kv: [
          { k: 'start',    v: x.tick_format === 'date' ? new Date(+task.start).toISOString().slice(0,10) : fmtNum(+task.start || 0) },
          { k: 'end',      v: x.tick_format === 'date' ? new Date(+task.end).toISOString().slice(0,10)   : fmtNum(+task.end   || 0) },
          { k: 'duration', v: fmtNum((+task.end || 0) - (+task.start || 0)) }
        ]
      });
      parts.push('<rect x="' + bx.toFixed(1) + '" y="' + y + '" width="' + bw.toFixed(1) + '" height="18" rx="3" fill="' + color + '" class="okc-gantt-bar" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((task.label || '') + ' · ' + fmtNum(+task.start || 0) + ' → ' + fmtNum(+task.end || 0)) + '</title></rect>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor({ top: pad.top, bottom: H - pad.bottom, left: pad.left, right: W - pad.right });
  }

  /* ---------------- Bump chart ----------------
     Line chart where the y-axis is RANK instead of value. Each
     series has values per category (e.g. years); the chart plots
     the series' rank-position at each category. "Who was #1 each
     year" — leaderboards, popularity drift. */
  _renderBump() {
    var x = (this._extras && this._extras.bump) || {};
    var categories = x.categories || [];
    var series = (x.series || []).slice();
    if (categories.length < 2 || !series.length) return;
    var palette = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)', 'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)'];
    // Compute per-category ranks. Rank 1 = highest value at that
    // category index. Ties get the same rank (stable).
    var ranks = categories.map(function (_, ci) {
      var vals = series.map(function (s, si) { return { i: si, v: +(s.values && s.values[ci]) || 0 }; });
      vals.sort(function (a, b) { return b.v - a.v; });
      var rankBySeries = {};
      vals.forEach(function (entry, idx) { rankBySeries[entry.i] = idx + 1; });
      return rankBySeries;
    });
    var nSeries = series.length;
    var W = 720, H = this._title ? 320 : 280;
    var pad = { top: this._title ? 36 : 16, bottom: 28, left: 110, right: 110 };
    var plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    function xOf(i) { return pad.left + (i / (categories.length - 1)) * plotW; }
    function yOf(rank) { return pad.top + ((rank - 1) / Math.max(1, nSeries - 1)) * plotH; }
    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeXml(this._title || 'Bump') + '" class="okc-svg okc-bump">');
    if (this._title) parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="okc-title">' + escapeXml(this._title) + '</text>');
    // Series ranking lines.
    series.forEach(function (s, si) {
      var color = palette[si % palette.length];
      var pathD = categories.map(function (_, ci) {
        return (ci === 0 ? 'M ' : 'L ') + xOf(ci).toFixed(1) + ' ' + yOf(ranks[ci][si]).toFixed(1);
      }).join(' ');
      parts.push('<path d="' + pathD + '" stroke="' + color + '" stroke-width="2.5" fill="none" stroke-linejoin="round" class="okc-bump-line"/>');
      // Dots at each rank.
      categories.forEach(function (_, ci) {
        var rank = ranks[ci][si];
        var payload = JSON.stringify({ label: (s.label || '') + ' · ' + categories[ci], kv: [
          { k: 'rank', v: '#' + rank },
          { k: 'value', v: fmtNum(+(s.values && s.values[ci]) || 0) }
        ]});
        parts.push('<circle cx="' + xOf(ci).toFixed(1) + '" cy="' + yOf(rank).toFixed(1) + '" r="5" fill="' + color + '" class="okc-bump-dot" tabindex="0" data-hover-payload="' + escapeXml(payload) + '"><title>' + escapeXml((s.label || '') + ' · ' + categories[ci] + ' · #' + rank) + '</title></circle>');
      });
      // Series label at each end.
      var firstRank = ranks[0][si];
      var lastRank  = ranks[categories.length - 1][si];
      parts.push('<text x="' + (pad.left - 8) + '" y="' + (yOf(firstRank) + 4) + '" text-anchor="end" class="okc-bump-end-label" fill="' + color + '">' + escapeXml(s.label || '') + '</text>');
      parts.push('<text x="' + (W - pad.right + 8) + '" y="' + (yOf(lastRank) + 4) + '" text-anchor="start" class="okc-bump-end-label" fill="' + color + '">' + escapeXml(s.label || '') + '</text>');
    });
    // Category ticks at bottom.
    categories.forEach(function (c, i) {
      parts.push('<text x="' + xOf(i).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle" class="okc-tick">' + escapeXml(c) + '</text>');
    });
    parts.push('</svg>');
    this.appendChild(document.createRange().createContextualFragment(parts.join('')));
    this._wireGenericVerticalCursor(
      { top: pad.top, bottom: pad.top + plotH, left: pad.left, right: W - pad.right },
      {
        seriesLookup: function (svgX) {
          var nearestIdx = 0;
          var bestDelta = Math.abs(xOf(0) - svgX);
          for (var i = 1; i < categories.length; i++) {
            var d = Math.abs(xOf(i) - svgX);
            if (d < bestDelta) { bestDelta = d; nearestIdx = i; }
          }
          var rows = series.map(function (s, si) {
            return {
              k: s.label || ('series ' + (si + 1)),
              v: '#' + ranks[nearestIdx][si] + ' (' + fmtNum(+(s.values && s.values[nearestIdx]) || 0) + ')'
            };
          });
          return { label: categories[nearestIdx], kv: rows };
        }
      }
    );
  }

  _attachToolbar() {
    var self = this;
    var chartTitle = self._title || (self._type + '-chart');
    // Order (per user feedback): data-output actions (reset / copy /
    // download) on the left, then a separator, then the chart-side
    // affordances (configure, expand). The separator is a special
    // toolbar entry the visual-tools module recognises.
    __okuVisualTools.makeToolbar(this, [
      {
        title: 'Reset zoom',
        icon: ICON_RESET,
        run: function (btn) { self.resetView(); __okuVisualTools.flash(btn, 'ok', ICON_RESET); }
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
          __okuVisualTools.copyText(btn, lines.join('\n'), ICON_CLIPBOARD);
        }
      },
      {
        title: 'Download as PNG',
        icon: ICON_CAMERA,
        run: function (btn) {
          var svg = self.querySelector('.okc-svg');
          __okuVisualTools.svgToPng(svg, chartTitle)
            .then(function () { __okuVisualTools.flash(btn, 'ok', ICON_CAMERA); })
            .catch(function () { __okuVisualTools.flash(btn, 'fail', ICON_CAMERA); });
        }
      },
      { separator: true },
      {
        title: 'Configure chart',
        icon: ICON_GEAR,
        run: function (btn) { __okuChartConfig.open(self, btn); }
      },
      {
        title: 'Expand to fullscreen',
        icon: ICON_EXPAND,
        run: function () {
          if (!self.parentNode || !window.__okuLightbox) return;
          // Move (not clone) the entire <oku-chart> host into the
          // lightbox so all CSS selectors scoped to `oku-chart .okc-*`
          // keep matching — moving just the SVG breaks edge/node/slice
          // styling because the rules no longer match an oku-chart
          // ancestor. The connectedCallback guard above prevents
          // re-init when the host is reparented. A placeholder takes
          // the host's slot inline so the page layout doesn't
          // collapse; onClose returns the host to its origin.
          var placeholder = document.createComment('okc-fullscreen-placeholder');
          var origInlineMaxHeight = self.style.maxHeight;
          var origInlineMaxWidth  = self.style.maxWidth;
          self.parentNode.insertBefore(placeholder, self);
          self.classList.add('okc-fullscreen');
          __okuLightbox.open(self, {
            title: chartTitle,
            onClose: function () {
              self.classList.remove('okc-fullscreen');
              self.style.maxHeight = origInlineMaxHeight || '';
              self.style.maxWidth  = origInlineMaxWidth  || '';
              if (placeholder.parentNode) {
                placeholder.parentNode.insertBefore(self, placeholder);
                placeholder.parentNode.removeChild(placeholder);
              }
            }
          });
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

    function getSvg() { return self.querySelector(':scope > .okc-svg'); }

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
      if (e.target.closest('.okt-bar, .okc-legend-chip')) return;
      e.preventDefault();
      var factor = e.deltaY > 0 ? 1.12 : (1 / 1.12);
      zoomAround(dataAtPointer(e.clientX, e.clientY), factor);
    }, { passive: false });

    // Drag pan.
    this.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      if (e.target.closest('.okt-bar, .okc-legend-chip, .okc-dot, .okc-point-label')) return;
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
      if (e.target.closest('.okt-bar, .okc-legend-chip')) return;
      self.resetView();
    });

    var svg = getSvg();
    if (svg) svg.style.cursor = 'grab';
  }

  _wireInteractivity() {
    var self = this;

    /* Hover tooltip — one shared element per chart, lazily created.
       The persistent close button sits in the top-right; CSS hides
       it unless the tooltip is `.pinned`. Clicking it unpins (same
       path as the Escape key handler at the bottom of this
       function). */
    function ensureTip() {
      var t = self.querySelector(':scope > .okc-tooltip');
      if (t) return t;
      t = document.createElement('div');
      t.className = 'okc-tooltip';
      t.setAttribute('role', 'tooltip');
      t.setAttribute('aria-hidden', 'true');
      var closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'okc-tt-close';
      closeBtn.setAttribute('aria-label', 'Close tooltip');
      closeBtn.setAttribute('title', 'Close (Esc)');
      closeBtn.textContent = '×'; // ×
      closeBtn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        unpinRich();
      });
      t.appendChild(closeBtn);
      self.appendChild(t);
      return t;
    }
    /* Place the (position: fixed) tooltip at viewport coords
       (anchorX, anchorY) but clamp it to stay inside the viewport.
       The tooltip's CSS transform is translate(-50%, -100%) so the
       requested point ends up at the centre-bottom of the box.
       We re-measure post-paint so the clamp uses the tooltip's
       actual width / height after the content swap. Without clamp,
       anchors near the viewport's right / top edges push the
       tooltip off-screen — the user has reported both. */
    function placeTooltipAt(tip, anchorX, anchorY) {
      tip.style.left = anchorX + 'px';
      tip.style.top  = anchorY + 'px';
      requestAnimationFrame(function () {
        var rect = tip.getBoundingClientRect();
        var vw = window.innerWidth, vh = window.innerHeight;
        var pad = 8;
        var left = anchorX, top = anchorY;
        // Horizontal clamp.
        if (rect.left < pad) left += (pad - rect.left);
        else if (rect.right > vw - pad) left -= (rect.right - (vw - pad));
        // Vertical clamp — flip below the anchor when the tooltip
        // would render above the viewport (anchor near top).
        if (rect.top < pad) top += (rect.height + 16);
        else if (rect.bottom > vh - pad) top -= (rect.bottom - (vh - pad));
        tip.style.left = left + 'px';
        tip.style.top  = top  + 'px';
      });
    }
    /* Reposition a tooltip to track its anchor's current viewport
       position. Used by the global scroll/resize handler so a tip
       opened when the page is at scrollY=0 keeps appearing next
       to the same data point after the reader scrolls. */
    function placeTooltipAtAnchor(tip, anchor, anchorOffset) {
      if (!anchor || !anchor.isConnected) return;
      var r = anchor.getBoundingClientRect();
      var ax = r.left + r.width / 2;
      var ay = r.top - (anchorOffset || 8);
      placeTooltipAt(tip, ax, ay);
    }
    // Global listener — keep every visible tooltip pinned to its
    // anchor element while the reader scrolls or resizes. Without
    // this, position:fixed tooltips appear glued to the viewport
    // and drift away from the chart they describe.
    if (!window.__okuTipScrollWired) {
      window.__okuTipScrollWired = true;
      var rafPending = false;
      function repositionAll() {
        rafPending = false;
        document.querySelectorAll('.okc-tooltip.visible').forEach(function (tip) {
          var anchor = tip.__okuAnchor;
          if (!anchor) return;
          placeTooltipAtAnchor(tip, anchor, tip.__okuAnchorOffset || 8);
        });
      }
      function schedule() {
        if (rafPending) return;
        rafPending = true;
        requestAnimationFrame(repositionAll);
      }
      window.addEventListener('scroll', schedule, true);
      window.addEventListener('resize', schedule);
    }
    function rebuildTipBody(tip, innerHtml) {
      // Replace the tooltip body without clobbering the persistent
      // close button. Anything inside `.okc-tt-body` is volatile;
      // siblings (the close button) survive.
      var body = tip.querySelector(':scope > .okc-tt-body');
      if (!body) {
        body = document.createElement('div');
        body.className = 'okc-tt-body';
        tip.insertBefore(body, tip.firstChild);
      }
      body.innerHTML = innerHtml;
    }
    function showTip(dot) {
      var tip = ensureTip();
      var seriesLbl = dot.getAttribute('data-series-label') || '';
      var pointLbl  = dot.getAttribute('data-point-label')  || '';
      var x = dot.getAttribute('data-x');
      var y = dot.getAttribute('data-y');
      var html = '';
      if (seriesLbl) html += '<div class="okc-tt-series">' + escapeXml(seriesLbl) + '</div>';
      if (pointLbl)  html += '<div class="okc-tt-label">'  + escapeXml(pointLbl)  + '</div>';
      html += '<div class="okc-tt-coords">(' + fmtNum(parseFloat(x)) + ', ' + fmtNum(parseFloat(y)) + ')</div>';
      rebuildTipBody(tip, html);
      tip.setAttribute('aria-hidden', 'false');
      // `position: fixed` tooltip — anchor at viewport coords so the
      // tip lands consistently whether it lives inside the chart
      // host or temporarily inside the lightbox content (chart
      // fullscreen). Viewport-clamped so the box stays on-screen
      // even at the rightmost / topmost extents of the plot.
      var dotRect = dot.getBoundingClientRect();
      placeTooltipAt(tip, dotRect.left + dotRect.width / 2, dotRect.top - 8);
      tip.__okuAnchor = dot;
      tip.__okuAnchorOffset = 8;
      tip.classList.add('visible');
    }
    function hideTip() {
      var tip = self.querySelector(':scope > .okc-tooltip');
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
    this.querySelectorAll('.okc-dot').forEach(function (dot) {
      var key = dot.getAttribute('data-point-key');
      dot.addEventListener('mouseenter', function () { setHover(key, true);  showTip(dot); });
      dot.addEventListener('mouseleave', function () { setHover(key, false); hideTip();   });
      dot.addEventListener('focus',      function () { setHover(key, true);  showTip(dot); });
      dot.addEventListener('blur',       function () { setHover(key, false); hideTip();   });
    });
    this.querySelectorAll('.okc-point-label').forEach(function (label) {
      var key = label.getAttribute('data-point-key');
      label.addEventListener('mouseenter', function () {
        setHover(key, true);
        var dot = self.querySelector('.okc-dot[data-point-key="' + key + '"]');
        if (dot) showTip(dot);
      });
      label.addEventListener('mouseleave', function () { setHover(key, false); hideTip(); });
      label.addEventListener('focus', function () {
        setHover(key, true);
        var dot = self.querySelector('.okc-dot[data-point-key="' + key + '"]');
        if (dot) showTip(dot);
      });
      label.addEventListener('blur', function () { setHover(key, false); hideTip(); });
    });

    /* Legend chip — click toggles `.dim` on the matching
       <g class="okc-series"> so the user can mute series visually.

       Modifier+click (Cmd on Mac, Ctrl elsewhere) solos: only the
       clicked series stays visible, every other series is dimmed.
       A second modifier+click on the same chip (when it's the only
       un-dimmed series) restores ALL series. Useful when a chart
       has many series and the reader wants to focus on one without
       individually muting the rest. */
    function setSeriesDim(idx, dim) {
      var chip = self.querySelector('.okc-legend-chip[data-series-idx="' + idx + '"]');
      var series = self.querySelector('.okc-series[data-series-idx="' + idx + '"]');
      if (series) series.classList.toggle('dim', dim);
      if (chip) {
        chip.classList.toggle('off', dim);
        chip.setAttribute('aria-pressed', dim ? 'true' : 'false');
      }
    }
    function toggleSeries(chip) {
      var idx = chip.getAttribute('data-series-idx');
      var series = self.querySelector('.okc-series[data-series-idx="' + idx + '"]');
      if (!series) return;
      setSeriesDim(idx, !series.classList.contains('dim'));
    }
    function soloSeries(idx) {
      // If `idx` is already the only visible series, restore all.
      var allChips = self.querySelectorAll('.okc-legend-chip[data-series-idx]');
      var visibleIdxs = [];
      allChips.forEach(function (c) {
        var i = c.getAttribute('data-series-idx');
        var s = self.querySelector('.okc-series[data-series-idx="' + i + '"]');
        if (s && !s.classList.contains('dim')) visibleIdxs.push(i);
      });
      var alreadySolo = visibleIdxs.length === 1 && visibleIdxs[0] === idx;
      allChips.forEach(function (c) {
        var i = c.getAttribute('data-series-idx');
        setSeriesDim(i, alreadySolo ? false : i !== idx);
      });
    }
    /* Hover highlight — putting a pointer on a legend entry
       emphasizes the matching series. (Earlier behaviour dimmed
       the rest, which made the reader's eye track the change-points
       instead of the target; flipped to emphasis-only via CSS in
       chrome.css's `.okc-legend-hovering` rules.) */
    function setHoverHighlight(idx) {
      self.classList.toggle('okc-legend-hovering', idx != null);
      self.setAttribute('data-legend-hover', idx == null ? '' : String(idx));
    }
    this.querySelectorAll('.okc-legend-chip').forEach(function (chip) {
      chip.setAttribute('aria-pressed', 'false');
      chip.addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey) {
          e.preventDefault();
          soloSeries(chip.getAttribute('data-series-idx'));
        } else {
          toggleSeries(chip);
        }
      });
      chip.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (e.metaKey || e.ctrlKey) {
            soloSeries(chip.getAttribute('data-series-idx'));
          } else {
            toggleSeries(chip);
          }
        }
      });
      chip.addEventListener('mouseenter', function () { setHoverHighlight(chip.getAttribute('data-series-idx')); });
      chip.addEventListener('mouseleave', function () { setHoverHighlight(null); });
      chip.addEventListener('focus', function () { setHoverHighlight(chip.getAttribute('data-series-idx')); });
      chip.addEventListener('blur',  function () { setHoverHighlight(null); });
      // Tooltip hint so first-time users know the modifier exists.
      var prevTitle = chip.getAttribute('title') || '';
      if (!prevTitle.includes('solo')) {
        chip.setAttribute('title', (prevTitle ? prevTitle + ' · ' : '') + 'click toggles · ' + (navigator.platform.toLowerCase().includes('mac') ? '⌘' : 'Ctrl') + '+click solos');
      }
    });

    /* Legend interactivity for non-Cartesian charts. Each legend item
       carries an index attribute (`data-slice-idx` for donut/pie,
       `data-segment-idx` for waffle, `data-series-idx` for radar)
       and toggling adds `.okc-hidden` to every matching shape. CSS
       collapses opacity / pointer events for hidden shapes so the
       reader can mute parts of the breakdown without re-rendering. */
    function wireNonCartesianLegend(legendSel, idxAttr, targetSel) {
      var items = self.querySelectorAll(legendSel);
      function setHidden(idx, hidden) {
        var item = self.querySelector(legendSel + '[' + idxAttr + '="' + CSS.escape(idx) + '"]');
        var targets = self.querySelectorAll(targetSel + '[' + idxAttr + '="' + CSS.escape(idx) + '"]');
        targets.forEach(function (t) { t.classList.toggle('okc-hidden', hidden); });
        if (item) {
          item.classList.toggle('okc-legend-off', hidden);
          item.setAttribute('aria-pressed', hidden ? 'true' : 'false');
        }
      }
      function getIdx(item) { return item.getAttribute(idxAttr); }
      function solo(idx) {
        // Already solo? Restore all.
        var visibleIdxs = [];
        items.forEach(function (it) {
          var i = getIdx(it);
          var targets = self.querySelectorAll(targetSel + '[' + idxAttr + '="' + CSS.escape(i) + '"]');
          if (!targets.length) return;
          if (!targets[0].classList.contains('okc-hidden')) visibleIdxs.push(i);
        });
        var alreadySolo = visibleIdxs.length === 1 && visibleIdxs[0] === idx;
        items.forEach(function (it) {
          var i = getIdx(it);
          setHidden(i, alreadySolo ? false : i !== idx);
        });
      }
      items.forEach(function (legendItem) {
        function toggle() {
          var idx = legendItem.getAttribute(idxAttr);
          if (idx == null) return;
          var targets = self.querySelectorAll(targetSel + '[' + idxAttr + '="' + CSS.escape(idx) + '"]');
          if (!targets.length) return;
          setHidden(idx, !targets[0].classList.contains('okc-hidden'));
        }
        function setHover(on) {
          var idx = legendItem.getAttribute(idxAttr);
          self.classList.toggle('okc-legend-hovering', on);
          self.setAttribute('data-legend-hover-attr', idxAttr);
          self.setAttribute('data-legend-hover', on ? (idx || '') : '');
        }
        legendItem.addEventListener('click', function (e) {
          if (e.metaKey || e.ctrlKey) { e.preventDefault(); solo(getIdx(legendItem)); }
          else toggle();
        });
        legendItem.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (e.metaKey || e.ctrlKey) solo(getIdx(legendItem));
            else toggle();
          }
        });
        legendItem.addEventListener('mouseenter', function () { setHover(true); });
        legendItem.addEventListener('mouseleave', function () { setHover(false); });
        legendItem.addEventListener('focus', function () { setHover(true); });
        legendItem.addEventListener('blur',  function () { setHover(false); });
      });
    }
    wireNonCartesianLegend('.okc-donut-legend',  'data-slice-idx',   '.okc-slice');
    wireNonCartesianLegend('.okc-waffle-legend', 'data-segment-idx', '.okc-waffle-cell');
    wireNonCartesianLegend('.okc-radar-legend',  'data-series-idx',  '.okc-radar-series');

    /* Rich-tooltip wiring for non-dot chart shapes. Reads the data
       payload from the element's own attributes (label, value, share,
       series) — each renderer below tags its shapes accordingly. The
       tooltip element is the same .okc-tooltip the dot-tip uses, so
       only one tip is visible at a time. */
    // Click-pinned anchor state. When set, hover-leave does NOT
    // hide the tooltip; only another click (on the same anchor or
    // anywhere outside) unpins it. Lets readers select tooltip
    // text or follow values without the popup auto-closing.
    var pinnedAnchor = null;
    // Expose tip-pinned state to other methods on the instance —
    // cursor-driven charts (ridgeline, sparkline) check this before
    // overwriting the pinned tooltip content with the cursor's
    // payload.
    Object.defineProperty(self, '_tipPinned', {
      configurable: true,
      get: function () { return !!pinnedAnchor; }
    });
    // Cursor-driven update path used by _wireRidgelineCursor /
    // _wireSparklineCursor — render a payload near the screen
    // coordinates (clientX/Y) without binding to a DOM anchor.
    self._showCursorTip = function (payload, sx, sy) {
      if (pinnedAnchor) return;
      var tip = ensureTip();
      var html = '';
      if (payload.label) html += '<div class="okc-tt-label">' + escapeXml(payload.label) + '</div>';
      if (payload.kv && payload.kv.length) {
        html += '<dl class="okc-tt-kv">';
        payload.kv.forEach(function (row) {
          html += '<dt>' + escapeXml(row.k) + '</dt><dd>' + escapeXml(row.v) + '</dd>';
        });
        html += '</dl>';
      }
      if (payload.footer) html += '<div class="okc-tt-coords">' + escapeXml(payload.footer) + '</div>';
      html += '<span class="okc-tt-pin-hint">click to pin</span>';
      rebuildTipBody(tip, html);
      tip.setAttribute('aria-hidden', 'false');
      placeTooltipAt(tip, sx, sy - 8);
      tip.classList.add('visible');
    };
    self._hideCursorTip = function () {
      if (pinnedAnchor) return;
      var tip = self.querySelector(':scope > .okc-tooltip');
      if (tip) { tip.classList.remove('visible'); tip.setAttribute('aria-hidden', 'true'); }
    };
    function showRich(anchor, payload) {
      var tip = ensureTip();
      var html = '';
      if (payload.series) html += '<div class="okc-tt-series">' + escapeXml(payload.series) + '</div>';
      if (payload.label)  html += '<div class="okc-tt-label">'  + escapeXml(payload.label)  + '</div>';
      if (payload.kv && payload.kv.length) {
        html += '<dl class="okc-tt-kv">';
        payload.kv.forEach(function (row) {
          html += '<dt>' + escapeXml(row.k) + '</dt><dd>' + escapeXml(row.v) + '</dd>';
        });
        html += '</dl>';
      }
      if (payload.footer) html += '<div class="okc-tt-coords">' + escapeXml(payload.footer) + '</div>';
      html += '<span class="okc-tt-pin-hint">click to pin</span>';
      rebuildTipBody(tip, html);
      tip.setAttribute('aria-hidden', 'false');
      // Viewport-relative + clamped position (tooltip is
      // `position: fixed`). Robust across "tooltip in chart host"
      // and "tooltip moved into lightbox content during chart-
      // fullscreen" paths, and never leaks past the viewport edges.
      var aRect = anchor.getBoundingClientRect();
      placeTooltipAt(tip, aRect.left + aRect.width / 2, aRect.top - 8);
      tip.__okuAnchor = anchor;
      tip.__okuAnchorOffset = 8;
      tip.classList.add('visible');
    }
    function hideRich(force) {
      if (pinnedAnchor && !force) return;
      var tip = self.querySelector(':scope > .okc-tooltip');
      if (tip) {
        tip.classList.remove('visible', 'pinned');
        tip.setAttribute('aria-hidden', 'true');
      }
    }
    function pinRich(anchor, payload) {
      // Drop the pinned-marker from any previous pin before applying
      // the new one — keeps a single "selected" indicator across the
      // chart at any time.
      self.querySelectorAll('.okc-pinned').forEach(function (el) { el.classList.remove('okc-pinned'); });
      pinnedAnchor = anchor;
      anchor.classList.add('okc-pinned');
      showRich(anchor, payload);
      var tip = self.querySelector(':scope > .okc-tooltip');
      if (tip) tip.classList.add('pinned');
    }
    function unpinRich() {
      self.querySelectorAll('.okc-pinned').forEach(function (el) { el.classList.remove('okc-pinned'); });
      pinnedAnchor = null;
      hideRich(true);
    }
    function rich(selector, payloadFn) {
      self.querySelectorAll(selector).forEach(function (el) {
        el.addEventListener('mouseenter', function () {
          if (pinnedAnchor && pinnedAnchor !== el) return;
          showRich(el, payloadFn(el));
        });
        el.addEventListener('mouseleave', function () {
          if (pinnedAnchor === el) return;
          hideRich();
        });
        el.addEventListener('focus',      function () { showRich(el, payloadFn(el)); });
        el.addEventListener('blur',       function () {
          if (pinnedAnchor === el) return;
          hideRich();
        });
        el.addEventListener('click', function (ev) {
          ev.stopPropagation();
          if (pinnedAnchor === el) {
            unpinRich();
          } else {
            pinRich(el, payloadFn(el));
          }
        });
      });
    }
    // Outside-click + Escape unpin handlers (host-scoped).
    self.addEventListener('click', function (ev) {
      if (!pinnedAnchor) return;
      // Bubble guard — only unpin when the click landed somewhere
      // OTHER than the pinned anchor (the rich handler already
      // stops the anchor's own click from reaching here).
      if (!pinnedAnchor.contains(ev.target)) unpinRich();
    });
    self.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && pinnedAnchor) unpinRich();
    });
    // Donut slices — label, value, share-of-total.
    rich('.okc-slice', function (el) {
      var label = el.getAttribute('data-slice-label') || '';
      var value = +el.getAttribute('data-slice-value') || 0;
      var share = +el.getAttribute('data-slice-share') || 0;
      var total = +el.getAttribute('data-slice-total') || 0;
      return {
        label: label,
        kv: [
          { k: 'value', v: fmtNum(value) },
          { k: 'share', v: Math.round(share * 100) + '%' }
        ],
        footer: 'of ' + fmtNum(total)
      };
    });
    // Treemap cells — already tagged from renderer.
    rich('.okc-treemap-cell rect', function (el) {
      var label = el.getAttribute('data-cell-label') || '';
      var value = +el.getAttribute('data-cell-value') || 0;
      var share = +el.getAttribute('data-cell-share') || 0;
      return {
        label: label,
        kv: [
          { k: 'value', v: fmtNum(value) },
          { k: 'share', v: Math.round(share * 100) + '%' }
        ]
      };
    });
    // Funnel bands — stage value, share-of-first, drop-off to next.
    rich('.okc-funnel-band', function (el) {
      var label = el.getAttribute('data-stage-label') || '';
      var value = +el.getAttribute('data-stage-value') || 0;
      var share = +el.getAttribute('data-stage-share') || 0;
      var dropPct = el.getAttribute('data-stage-drop');
      var kv = [
        { k: 'value', v: fmtNum(value) },
        { k: 'share', v: Math.round(share * 100) + '%' }
      ];
      if (dropPct !== null) kv.push({ k: 'drop-off', v: dropPct + '%' });
      return { label: label, kv: kv };
    });
    // Histogram bins, heatmap cells, waffle units — generic
    // data-hover-payload attribute carrying pre-built JSON. Keeps
    // future chart types cheap to instrument.
    rich('[data-hover-payload]', function (el) {
      try { return JSON.parse(el.getAttribute('data-hover-payload')); }
      catch (e) { return { label: el.getAttribute('data-hover-payload') }; }
    });
  }
}
if (!customElements.get('oku-chart')) customElements.define('oku-chart', OkuChart);

/* ============ .bar-chart hover enhancer ============ *
 * bar / stacked-bar / grouped-bar charts render via renderer.js as
 * <div class="bar-chart"> (single) or <div class="bar-chart-multi">
 * (stacked/grouped) — outside the <oku-chart> custom-element
 * lifecycle. This enhancer attaches the same rich tooltip to those
 * DIV-based charts by walking .bar-fill elements and reading their
 * data-hover-payload JSON.
 * --------------------------------------------------------------------- */
/* Same viewport-clamped placement as OkuChart's tooltip — exposed
   at module scope so the bar enhancer (and any future DIV-based
   chart family) can use it without re-implementing the clamp math.
   The tooltip is `position: fixed`, so left/top are VIEWPORT coords,
   not document coords. */
function __okuPlaceTooltipAt(tip, anchorX, anchorY) {
  tip.style.left = anchorX + 'px';
  tip.style.top  = anchorY + 'px';
  requestAnimationFrame(function () {
    var rect = tip.getBoundingClientRect();
    var vw = window.innerWidth, vh = window.innerHeight;
    var pad = 8;
    var left = anchorX, top = anchorY;
    if (rect.left < pad) left += (pad - rect.left);
    else if (rect.right > vw - pad) left -= (rect.right - (vw - pad));
    if (rect.top < pad) top += (rect.height + 16);
    else if (rect.bottom > vh - pad) top -= (rect.bottom - (vh - pad));
    tip.style.left = left + 'px';
    tip.style.top  = top  + 'px';
  });
}

function __okuEnhanceBarCharts(root) {
  var charts = (root || document).querySelectorAll('.bar-chart, .bar-chart-multi');
  charts.forEach(function (host) {
    if (host.dataset.hdcBarsBound === '1') return;
    host.dataset.hdcBarsBound = '1';
    // Vertical cursor — absolute-positioned line following the
    // pointer within the chart wrap. SVG charts get an SVG cursor
    // via _wireGenericVerticalCursor; bar charts are DIV-based, so
    // the same affordance lives as a DOM line.
    var cursor = document.createElement('div');
    cursor.className = 'okc-bar-cursor';
    cursor.setAttribute('aria-hidden', 'true');
    host.appendChild(cursor);
    // Plot region is the .bar-row stack — exclude the title (.bar-chart-title)
    // and the legend rack so the cursor never extends over them.
    function plotYBounds() {
      var rows = host.querySelectorAll('.bar-row');
      if (!rows.length) return null;
      var hostRect = host.getBoundingClientRect();
      var firstRect = rows[0].getBoundingClientRect();
      var lastRect = rows[rows.length - 1].getBoundingClientRect();
      return {
        top: firstRect.top - hostRect.top,
        bottom: lastRect.bottom - hostRect.top,
      };
    }
    host.addEventListener('mousemove', function (ev) {
      var r = host.getBoundingClientRect();
      var x = ev.clientX - r.left;
      var y = ev.clientY - r.top;
      var pyb = plotYBounds();
      if (x < 0 || x > r.width || !pyb || y < pyb.top || y > pyb.bottom) {
        cursor.style.opacity = '0';
        return;
      }
      // Recompute on every move so a window resize / fold doesn't
      // leave the cursor stuck at the prior plot extent.
      cursor.style.top    = pyb.top + 'px';
      cursor.style.height = (pyb.bottom - pyb.top) + 'px';
      cursor.style.left = x + 'px';
      cursor.style.opacity = '1';
    });
    host.addEventListener('mouseleave', function () {
      cursor.style.opacity = '0';
    });
    var tip = null;
    function ensureTip() {
      if (tip) return tip;
      tip = document.createElement('div');
      tip.className = 'okc-tooltip';
      tip.setAttribute('role', 'tooltip');
      tip.setAttribute('aria-hidden', 'true');
      host.appendChild(tip);
      return tip;
    }
    var pinnedFill = null;
    function show(anchor, payload) {
      var t = ensureTip();
      var html = '';
      if (payload.series) html += '<div class="okc-tt-series">' + escapeXml(payload.series) + '</div>';
      if (payload.label)  html += '<div class="okc-tt-label">'  + escapeXml(payload.label)  + '</div>';
      if (payload.kv && payload.kv.length) {
        html += '<dl class="okc-tt-kv">';
        payload.kv.forEach(function (row) {
          html += '<dt>' + escapeXml(row.k) + '</dt><dd>' + escapeXml(row.v) + '</dd>';
        });
        html += '</dl>';
      }
      if (payload.footer) html += '<div class="okc-tt-coords">' + escapeXml(payload.footer) + '</div>';
      html += '<span class="okc-tt-pin-hint">click to pin</span>';
      t.innerHTML = html;
      t.setAttribute('aria-hidden', 'false');
      // `.okc-tooltip` is `position: fixed`, so style.left/top must be
      // **viewport** coords, not host-relative. The earlier code
      // computed `aRect.left - hostRect.left + aRect.width/2` — a
      // host-relative number near 0 — which placed the tooltip at the
      // viewport's left edge, far away from the chart. Use the
      // module-level viewport-clamped helper the SVG charts use.
      var aRect = anchor.getBoundingClientRect();
      __okuPlaceTooltipAt(t, aRect.left + aRect.width / 2, aRect.top - 8);
      t.__okuAnchor = anchor;
      t.__okuAnchorOffset = 8;
      t.classList.add('visible');
    }
    function hide(force) {
      if (pinnedFill && !force) return;
      if (tip) {
        tip.classList.remove('visible', 'pinned');
        tip.setAttribute('aria-hidden', 'true');
      }
    }
    host.querySelectorAll('.bar-fill[data-hover-payload]').forEach(function (fill) {
      // Drop the native tooltip — we render our own.
      if (fill.title) { fill.removeAttribute('title'); }
      var raw = fill.getAttribute('data-hover-payload');
      var payload;
      try { payload = JSON.parse(raw); } catch (e) { payload = { label: raw }; }
      fill.addEventListener('mouseenter', function () {
        if (pinnedFill && pinnedFill !== fill) return;
        show(fill, payload);
      });
      fill.addEventListener('mouseleave', function () {
        if (pinnedFill === fill) return;
        hide();
      });
      fill.addEventListener('click', function (ev) {
        ev.stopPropagation();
        if (pinnedFill === fill) {
          pinnedFill = null;
          hide(true);
        } else {
          pinnedFill = fill;
          show(fill, payload);
          if (tip) tip.classList.add('pinned');
        }
      });
    });
    host.addEventListener('click', function (ev) {
      if (!pinnedFill) return;
      if (!pinnedFill.contains(ev.target)) {
        pinnedFill = null;
        hide(true);
      }
    });
    host.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && pinnedFill) {
        pinnedFill = null;
        hide(true);
      }
    });
    // Legend toggle — click a chip to dim the matching series across
    // every category row. Mirrors the Cartesian chart legend chip
    // behaviour. State is purely visual (CSS class), no data
    // recompute — kept simple so the page doesn't repaint heavily.
    var allLegendChips = host.querySelectorAll('.bar-chart-legend-chip[data-series-idx]');
    function setChipDim(chip, dim) {
      var idx = chip.getAttribute('data-series-idx');
      chip.classList.toggle('off', dim);
      chip.setAttribute('aria-pressed', dim ? 'true' : 'false');
      host.querySelectorAll('.bar-fill[data-series="' + idx + '"]').forEach(function (f) {
        f.classList.toggle('dim', dim);
      });
    }
    function soloBarSeries(idx) {
      // Restore-all if this idx is already the only un-dimmed.
      var visibleIdxs = [];
      allLegendChips.forEach(function (c) {
        if (!c.classList.contains('off')) visibleIdxs.push(c.getAttribute('data-series-idx'));
      });
      var alreadySolo = visibleIdxs.length === 1 && visibleIdxs[0] === idx;
      allLegendChips.forEach(function (c) {
        var i = c.getAttribute('data-series-idx');
        setChipDim(c, alreadySolo ? false : i !== idx);
      });
    }
    allLegendChips.forEach(function (chip) {
      chip.addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey) {
          e.preventDefault();
          soloBarSeries(chip.getAttribute('data-series-idx'));
        } else {
          setChipDim(chip, !chip.classList.contains('off'));
        }
      });
      var prevTitle = chip.getAttribute('title') || '';
      if (!prevTitle.includes('solo')) {
        chip.setAttribute('title', (prevTitle ? prevTitle + ' · ' : '') + 'click toggles · ' + (navigator.platform.toLowerCase().includes('mac') ? '⌘' : 'Ctrl') + '+click solos');
      }
    });
  });
}
document.addEventListener('DOMContentLoaded', function () {
  __okuEnhanceBarCharts(document);
});
// Renderer dispatches oku:rendered on window after each async
// page render; re-enhance then to catch fresh bar-charts.
window.addEventListener('oku:rendered', function () {
  __okuEnhanceBarCharts(document);
});

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
var __okuVisualTools = (function () {
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
    var existing = host.querySelector(':scope > .okt-bar');
    if (existing) existing.remove();
    host.classList.add('okt-host');
    var bar = document.createElement('div');
    bar.className = 'okt-bar';
    actions.forEach(function (a) {
      if (a && a.separator) {
        var sep = document.createElement('span');
        sep.className = 'okt-bar-sep';
        sep.setAttribute('aria-hidden', 'true');
        bar.appendChild(sep);
        return;
      }
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
        // Eagerly preload the languages most commonly nested inside
        // other languages — JavaScript inside <script>, CSS inside
        // <style>, bash inside Markdown fences, JSON inside fences.
        // Prism's markup grammar inlines <script> / <style> contents
        // as `language-javascript` / `language-css` ONLY when the
        // embedded grammar is already loaded at first-highlight time.
        // Without this preload the script body shows as raw text
        // until the autoloader's second pass — which we can't safely
        // re-trigger because our line-wrap mutation invalidates the
        // anchor. Cheap: ~5 small CDN fetches once per page.
        return Promise.all([
          ensureScript(CDN + 'components/prism-javascript.min.js').catch(function () {}),
          ensureScript(CDN + 'components/prism-css.min.js').catch(function () {}),
          ensureScript(CDN + 'components/prism-bash.min.js').catch(function () {}),
          ensureScript(CDN + 'components/prism-json.min.js').catch(function () {}),
          ensureScript(CDN + 'components/prism-yaml.min.js').catch(function () {}),
        ]);
      })
      .then(function () {
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
      window.dispatchEvent(new CustomEvent('oku:warnings', {
        detail: [{ code: 'prism-load-failed', msg: 'Could not load Prism: ' + (e.message || e), level: 'info' }]
      }));
    });
  }
  return { load: load, highlightAll: highlightAll };
})();

/* ============ <oku-diagram> — Mermaid (lazy-loaded) ============ */
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
      // Cap default font size so state / mindmap diagrams that have
      // few labels don't blow them up to 24-30px — Mermaid's default
      // scales the font with the diagram, which reads as cramped in
      // an example-pair render column. 13px is comfortable inline;
      // the lightbox still upscales when the reader opens it.
      fontSize: 13,
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
        // Text colour on state-diagram labels — Mermaid defaults to
        // a white-ish stateLabelColor that's invisible against our
        // light surface. Pin to --text so it tracks the theme.
        stateLabelColor:  text,
        labelColor:       text,
        altBackground:    surface2,
        compositeBackground: surface2,
        compositeBorder:  border,
        compositeTitleBackground: bg,
        innerEndBackground: textSoft,
        // ER / class diagram colours — same family so the tokens
        // stay consistent.
        attributeBackgroundColorPrimary: surface,
        attributeBackgroundColorSecondary: surface2,
        classText:        text,
        relationColor:    textSoft,
        relationLabelColor: text,
        // Mindmap / timeline / journey
        cScale0: accent,
        cScale1: '#b45309',
        cScale2: '#4338ca',
        cScale3: '#15803d',
        cScale4: '#be185d',
        cScale5: '#0369a1',
        cScaleLabel0: text,
        cScaleLabel1: text,
        cScaleLabel2: text,
        cScaleLabel3: text,
        cScaleLabel4: text,
        cScaleLabel5: text,
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

class OkuDiagram extends HTMLElement {
  connectedCallback() {
    var srcNode = this.querySelector('script[type="text/x-mermaid"]');
    var src = srcNode ? srcNode.textContent.trim() : '';
    var caption = this.getAttribute('caption') || '';
    this.classList.add('okd-wrap');
    // Two stacked views: rendered SVG and the raw Mermaid source. The
    // toolbar's first button toggles between them. Source is wrapped
    // in a language-mermaid <code> so the existing Prism + line-number
    // pipeline picks it up.
    this.innerHTML =
      '<div class="okd-render" aria-label="Diagram loading">Rendering…</div>' +
      '<pre class="okd-source" hidden><code class="language-mermaid">' + escapeXml(src) + '</code></pre>' +
      (caption ? '<figcaption class="okd-caption">' + escapeXml(caption) + '</figcaption>' : '');
    var renderHost = this.querySelector('.okd-render');
    var self = this;
    this._src = src;
    __mermaidLoader.load()
      .then(function (mermaid) {
        var id = 'okd-' + Math.random().toString(36).slice(2, 9);
        return mermaid.render(id, src).then(function (out) {
          renderHost.innerHTML = out.svg;
          // Strip Mermaid's intrinsic width/height + inline style so
          // CSS width:100% / height:auto can fit the SVG to the
          // container instead of clipping when the column is narrower
          // than Mermaid's natural render size.
          var svg = renderHost.querySelector('svg');
          if (svg) {
            // Pin width/height to the viewBox dimensions instead of
            // letting CSS auto-size the SVG. Auto-size lets the SVG
            // scale UP to fill its container, which enlarges every
            // foreignObject-rendered text label proportionally — a
            // 13px label inside a tall mermaid state diagram could
            // become ~26px once the SVG was stretched 2× to fit the
            // column. CSS max-width:100% still scales DOWN large
            // diagrams; tall narrow ones now render at their authored
            // size so labels stay readable instead of cartoonish.
            var vb = (svg.getAttribute('viewBox') || '').split(/\s+/).map(parseFloat);
            if (vb.length === 4 && !isNaN(vb[2]) && !isNaN(vb[3])) {
              svg.setAttribute('width', String(vb[2]));
              svg.setAttribute('height', String(vb[3]));
            } else {
              svg.removeAttribute('width');
              svg.removeAttribute('height');
            }
            svg.style.removeProperty('max-width');
            svg.style.removeProperty('width');
            svg.style.removeProperty('height');
            svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
            self._wireNeighborHighlight(svg);
          }
          self._rendered = true;
          self._attachToolbar();
        });
      })
      .catch(function (err) {
        // Stable id so the warning panel can jump-link back here.
        if (!self.id) self.id = 'okd-error-' + Math.random().toString(36).slice(2, 9);
        var raw = String((err && err.message) || err);
        // Replace our own render surface with our error card so the
        // framework noise doesn't leak through. The toolbar's source
        // toggle still lets the reader inspect the offending source.
        renderHost.classList.add('okd-error');
        renderHost.innerHTML =
          '<div class="okd-error-card" role="alert">' +
            '<strong>Diagram could not be rendered.</strong>' +
            '<div class="okd-error-hint">The source is preserved — open it from the toolbar to debug.</div>' +
            '<details>' +
              '<summary>Show parse error</summary>' +
              '<pre>' + escapeXml(raw) + '</pre>' +
            '</details>' +
          '</div>';
        self._attachToolbar();
        var firstLine = raw.split('\n')[0].trim();
        var label = (caption || 'Diagram') + ' — ' + (firstLine || 'parse error');
        window.dispatchEvent(new CustomEvent('oku:warnings', {
          detail: [{
            code: 'mermaid-render-failed',
            msg: label,
            level: 'warn',
            target: '#' + self.id
          }]
        }));
        // Mermaid v10 leaves an orphan error-svg attached to <body>
        // when render() throws. The id is "id" we passed in or the
        // mermaid-generated equivalent — remove any svg whose id
        // starts with the prefix we used, plus generic mermaid-error
        // classes that the framework stamps. Polled briefly because
        // the error svg may be appended after our catch handler runs.
        function purgeOrphanMermaidErrors() {
          document.querySelectorAll('body > svg[id^="okd-"], body > .mermaid-error, body > svg[id^="d"][aria-roledescription="error"]').forEach(function (n) {
            // Only nuke svgs that aren't INSIDE our diagram host.
            if (!n.closest('oku-diagram')) n.remove();
          });
        }
        purgeOrphanMermaidErrors();
        setTimeout(purgeOrphanMermaidErrors, 50);
        setTimeout(purgeOrphanMermaidErrors, 250);
      });
  }
  _attachToolbar() {
    var self = this;
    var caption = this.getAttribute('caption') || 'diagram';
    __okuVisualTools.makeToolbar(this, [
      {
        title: 'Toggle source / render',
        icon: ICON_BRACES,
        run: function (btn) {
          var showSource = !self.classList.contains('okd-source-mode');
          self.classList.toggle('okd-source-mode', showSource);
          var src = self.querySelector(':scope > .okd-source');
          var ren = self.querySelector(':scope > .okd-render');
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
          __okuVisualTools.copyText(btn, self._src || '', ICON_CLIPBOARD);
        }
      },
      {
        title: 'Download as PNG',
        icon: ICON_CAMERA,
        run: function (btn) {
          var svg = self.querySelector('.okd-render svg');
          __okuVisualTools.svgToPng(svg, caption || 'diagram')
            .then(function () { __okuVisualTools.flash(btn, 'ok', ICON_CAMERA); })
            .catch(function () { __okuVisualTools.flash(btn, 'fail', ICON_CAMERA); });
        }
      },
      { separator: true },
      {
        title: 'Expand to fullscreen',
        icon: ICON_EXPAND,
        run: function () {
          var svg = self.querySelector('.okd-render svg');
          if (!svg || !window.__okuLightbox) return;
          var copy = svg.cloneNode(true);
          copy.removeAttribute('width');
          copy.removeAttribute('height');
          copy.style.width = '100%';
          copy.style.height = 'auto';
          __okuLightbox.open(copy, { title: caption || 'Diagram' });
        }
      }
    ]);
  }
  _wireNeighborHighlight(svg) {
    // Mermaid flowcharts encode adjacency in two predictable shapes:
    //   - Nodes carry data-id="<NodeId>" (the user's source id).
    //   - Edges carry classes "LS-<source>" + "LE-<target>".
    // Build an adjacency map once per render, then on node hover/focus
    // mark the node, its incident edges, and its neighbor nodes with
    // data-okd-active="1". CSS dims the rest. Free fallback for
    // diagram types without that shape (sequence, gantt, journey):
    // nodes still get the single-node hover lift via the existing CSS,
    // since this code only runs when nodes have data-id.
    var nodes = Array.from(svg.querySelectorAll('.node[data-id], g.node[data-id]'));
    if (!nodes.length) return;
    var edgesByEndpoint = {}; // 'NodeId' → [edgeEl, neighborNodeId][]
    var nodeById = {};
    nodes.forEach(function (n) {
      var id = n.getAttribute('data-id');
      nodeById[id] = n;
    });
    var edges = svg.querySelectorAll('.flowchart-link, path.edge-thickness-normal');
    edges.forEach(function (e) {
      var cls = e.getAttribute('class') || '';
      var sm = cls.match(/\bLS-([^\s]+)/);
      var tm = cls.match(/\bLE-([^\s]+)/);
      if (!sm || !tm) return;
      var src = sm[1], tgt = tm[1];
      (edgesByEndpoint[src] = edgesByEndpoint[src] || []).push([e, tgt]);
      (edgesByEndpoint[tgt] = edgesByEndpoint[tgt] || []).push([e, src]);
      // Also mark the edge's start/end labels (mermaid renders these as
      // separate <g class="edgeLabel">) when present — they share the
      // edge's class list via mermaid's "edgeLabels" group, but the
      // group's bbox is far from the edge so we don't auto-link them.
    });
    function setActive(id) {
      svg.querySelectorAll('[data-okd-active]').forEach(function (el) { el.removeAttribute('data-okd-active'); });
      svg.removeAttribute('data-okd-has-active');
      if (!id) return;
      svg.setAttribute('data-okd-has-active', '1');
      var node = nodeById[id];
      if (node) node.setAttribute('data-okd-active', '1');
      (edgesByEndpoint[id] || []).forEach(function (pair) {
        pair[0].setAttribute('data-okd-active', '1');
        if (nodeById[pair[1]]) nodeById[pair[1]].setAttribute('data-okd-active', '1');
      });
    }
    nodes.forEach(function (n) {
      var id = n.getAttribute('data-id');
      n.addEventListener('mouseenter', function () { setActive(id); });
      n.addEventListener('mouseleave', function () { setActive(null); });
      n.addEventListener('focus', function () { setActive(id); });
      n.addEventListener('blur', function () { setActive(null); });
      // Keyboard reachability — nodes already get cursor:pointer from CSS.
      if (!n.hasAttribute('tabindex')) n.setAttribute('tabindex', '0');
    });
  }
  rerender() {
    if (!this._src) return;
    var renderHost = this.querySelector('.okd-render');
    var self = this;
    __mermaidLoader.reset();
    __mermaidLoader.load().then(function (mermaid) {
      var id = 'okd-' + Math.random().toString(36).slice(2, 9);
      return mermaid.render(id, self._src).then(function (out) {
        renderHost.innerHTML = out.svg;
        var svg = renderHost.querySelector('svg');
        if (svg) self._wireNeighborHighlight(svg);
        self._attachToolbar();
      });
    }).catch(function () { /* swallow */ });
  }
}
if (!customElements.get('oku-diagram')) customElements.define('oku-diagram', OkuDiagram);

// Re-render every diagram on theme toggle so colors track the theme.
window.addEventListener('oku:theme-changed', function () {
  document.querySelectorAll('oku-diagram').forEach(function (d) {
    if (typeof d.rerender === 'function') d.rerender();
  });
});

/* ============ <oku-annotated-code> — MkDocs-Material-style annotations ============ *
 * Code block with numbered `(1)`, `(2)` markers that map to a side panel
 * of annotations. Hovering a marker brightens its annotation and vice
 * versa. Sources:
 *   - <script type="text/x-code"> code body (preserves whitespace, no escaping)
 *   - <script type="application/json"> [{ id: 1, content: "..." }, ...]
 *     OR a child <ol class="okc-anno-source"> with one <li> per annotation
 *       (li index = id, content = li.innerHTML).
 * Renders into:
 *   <pre><code class="language-{lang}">...with .okc-anno-marker chips...</code></pre>
 *   <ol class="okc-anno-list">...<li class="okc-anno-item">...</li></ol>
 * Prism highlights the code first; the marker replacement walks the
 * highlighted text-nodes so `(1)` chips survive syntax coloring.
 * --------------------------------------------------------------------- */
class OkuAnnotatedCode extends HTMLElement {
  connectedCallback() {
    var srcNode = this.querySelector('script[type="text/x-code"]');
    var jsonNode = this.querySelector('script[type="application/json"]');
    var code = srcNode ? srcNode.textContent.replace(/^\n/, '') : (this.textContent || '');
    var annos = [];
    if (jsonNode) {
      try { annos = JSON.parse(jsonNode.textContent || '[]'); } catch (e) { annos = []; }
    } else {
      var ol = this.querySelector('ol.okc-anno-source, ol.okc-anno-list');
      if (ol) {
        annos = Array.prototype.map.call(ol.querySelectorAll(':scope > li'), function (li, i) {
          return { id: i + 1, content: li.innerHTML };
        });
      }
    }
    var lang = this.getAttribute('language') || this.getAttribute('lang') || '';

    this.innerHTML = '';
    this.classList.add('okc-anno-wrap');

    var pre = document.createElement('pre');
    var codeEl = document.createElement('code');
    if (lang) codeEl.className = 'language-' + lang;
    codeEl.textContent = code;
    pre.appendChild(codeEl);
    this.appendChild(pre);

    if (annos.length) {
      var list = document.createElement('ol');
      list.className = 'okc-anno-list';
      annos.forEach(function (a) {
        var li = document.createElement('li');
        li.className = 'okc-anno-item';
        li.setAttribute('data-anno-id', String(a.id));
        li.setAttribute('tabindex', '0');
        var num = document.createElement('span');
        num.className = 'okc-anno-num';
        num.textContent = String(a.id);
        var body = document.createElement('div');
        body.className = 'okc-anno-body';
        body.innerHTML = a.content || '';
        li.appendChild(num);
        li.appendChild(body);
        list.appendChild(li);
      });
      this.appendChild(list);
    }

    var self = this;
    var validIds = annos.reduce(function (acc, a) { acc[String(a.id)] = true; return acc; }, {});

    // Parse `lines: "1-3,5"` into a sorted unique array of 1-based line
    // numbers. Empty / malformed input → [].
    function parseLineSpec(spec) {
      if (!spec) return [];
      var seen = {};
      var out = [];
      String(spec).split(',').forEach(function (part) {
        part = part.trim();
        if (!part) return;
        var dash = part.indexOf('-');
        if (dash !== -1) {
          var lo = parseInt(part.slice(0, dash), 10);
          var hi = parseInt(part.slice(dash + 1), 10);
          if (lo > 0 && hi >= lo) {
            for (var i = lo; i <= hi; i++) {
              if (!seen[i]) { seen[i] = true; out.push(i); }
            }
          }
        } else {
          var n = parseInt(part, 10);
          if (n > 0 && !seen[n]) { seen[n] = true; out.push(n); }
        }
      });
      return out.sort(function (a, b) { return a - b; });
    }

    // Per-annotation: { lines: [1-based ints], match: [strings] }.
    // Captures structured target info the markers carry as data attrs.
    var annoTargets = {};
    annos.forEach(function (a) {
      var lines = parseLineSpec(a.lines);
      var match = [];
      if (typeof a.match === 'string' && a.match) match = [a.match];
      else if (Array.isArray(a.match)) match = a.match.filter(function (s) { return typeof s === 'string' && s; });
      annoTargets[String(a.id)] = { lines: lines, match: match };
    });

    function injectMarkers() {
      var c = self.querySelector('pre code');
      if (!c) return;
      var pattern = /\((\d+)\)/g;
      var textNodes = [];
      var walker = document.createTreeWalker(c, NodeFilter.SHOW_TEXT, null);
      var n;
      while ((n = walker.nextNode())) textNodes.push(n);
      var placedIds = {};
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
          frag.appendChild(makeMarker(m[1]));
          placedIds[m[1]] = true;
          last = m.index + m[0].length;
        }
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        textNode.parentNode.replaceChild(frag, textNode);
      });

      // For annotations declaring `lines` but NOT placed inline by an
      // (N) marker in the source, auto-place the chip at the start of
      // the first target line. Lets authors keep the source clean and
      // declare targets externally.
      annos.forEach(function (a) {
        var id = String(a.id);
        if (placedIds[id]) return;
        var targets = annoTargets[id];
        if (!targets || !targets.lines.length) return;
        var firstLine = targets.lines[0];
        var lineEl = c.querySelector(':scope > .okt-code-line[data-line="' + firstLine + '"]');
        if (!lineEl) return;
        var content = lineEl.querySelector(':scope > .okt-code-content');
        if (!content) return;
        content.insertBefore(makeMarker(id), content.firstChild);
        placedIds[id] = true;
      });

      // Pure-substring annotations (no inline (N), no lines) used to
      // render the substring underline with NO numeric chip — readers
      // couldn't tell which annotation a highlight belonged to. Now we
      // auto-place the chip immediately before the FIRST substring
      // match. The chip sits in flow, so it reads like
      // "<num>highlighted-substring".
      annos.forEach(function (a) {
        var id = String(a.id);
        if (placedIds[id]) return;
        var targets = annoTargets[id];
        if (!targets || !targets.match.length) return;
        var firstMatch = self.querySelector('pre code .okc-anno-substr[data-anno-id="' + id + '"]');
        if (!firstMatch) return;
        var marker = makeMarker(id);
        marker.classList.add('okc-anno-marker-substr');
        firstMatch.parentNode.insertBefore(marker, firstMatch);
        placedIds[id] = true;
      });

      bindSync();
    }

    function makeMarker(id) {
      var btn = document.createElement('button');
      btn.className = 'okc-anno-marker';
      btn.type = 'button';
      btn.setAttribute('data-anno-id', id);
      btn.setAttribute('aria-label', 'Annotation ' + id);
      btn.textContent = id;
      return btn;
    }

    // Wrap every occurrence of a `match` substring inside the
    // wrapped code lines in <mark class=okc-anno-substr
    // data-anno-id=N>. Works even when Prism has split the needle
    // across token spans (e.g. ${name} becomes
    // <span class=interpolation-punct>${</span><span ...>name</span><span ...>}</span>).
    // Strategy: per line, build a flat character map [char, textNode,
    // offset]; locate every needle occurrence in the joined text;
    // for each character range, split the involved text nodes and
    // re-parent the slices under a single <mark>. Idempotent — slices
    // already inside an existing .okc-anno-substr are skipped.
    function injectSubstringMarks() {
      var c = self.querySelector('pre code');
      if (!c) return;
      var lineEls = c.querySelectorAll(':scope > .okt-code-line');
      // Fall back to whole-block when lines aren't wrapped yet.
      var scopes = lineEls.length ? lineEls : [c];
      annos.forEach(function (a) {
        var id = String(a.id);
        var matches = (annoTargets[id] && annoTargets[id].match) || [];
        if (!matches.length) return;
        matches.forEach(function (needle) {
          if (!needle) return;
          scopes.forEach(function (scope) {
            markNeedleInScope(scope, needle, id);
          });
        });
      });
    }

    function markNeedleInScope(scope, needle, id) {
      // Build [char -> textNode] map, skipping nodes already inside
      // .okc-anno-substr (idempotency) and inside marker buttons.
      var nodes = [];
      var walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, null);
      var n;
      while ((n = walker.nextNode())) {
        if (n.parentElement && n.parentElement.closest('.okc-anno-substr,.okc-anno-marker')) continue;
        nodes.push(n);
      }
      if (!nodes.length) return;
      var map = [];
      var joined = '';
      nodes.forEach(function (node) {
        for (var i = 0; i < node.nodeValue.length; i++) {
          map.push({ node: node, offset: i });
        }
        joined += node.nodeValue;
      });
      // Find every needle occurrence in the joined string.
      var ranges = [];
      var pos = 0;
      while (true) {
        var idx = joined.indexOf(needle, pos);
        if (idx === -1) break;
        ranges.push({ start: idx, end: idx + needle.length });
        pos = idx + needle.length;
      }
      if (!ranges.length) return;
      // Collect every (node, offset) the ranges hit. Group by node so
      // we can do ONE replaceChild per text node — multiple matches
      // inside the same text node (e.g. "ACID is great because ACID")
      // would previously break the second pass because the first pass
      // had detached the original node. Single per-node pass fixes it.
      var perNode = {};
      ranges.forEach(function (rng) {
        for (var i = rng.start; i < rng.end; i++) {
          var e = map[i];
          if (!e) continue;
          var key = nodeKey(e.node);
          if (!perNode[key]) perNode[key] = { node: e.node, hits: new Set() };
          perNode[key].hits.add(e.offset);
        }
      });
      Object.keys(perNode).forEach(function (k) {
        var rec = perNode[k];
        replaceNodeWithSegments(rec.node, rec.hits, id);
      });
    }

    function replaceNodeWithSegments(node, hits, id) {
      // hits is a Set<int> of character offsets to wrap inside this
      // text node's content. Build a fragment of alternating
      // text-node + <mark> elements covering [0, length) in order.
      var text = node.nodeValue;
      var frag = document.createDocumentFragment();
      var i = 0;
      while (i < text.length) {
        if (hits.has(i)) {
          // Extend the matched run while consecutive offsets are hits.
          var j = i;
          while (j < text.length && hits.has(j)) j++;
          var mark = document.createElement('mark');
          mark.className = 'okc-anno-substr';
          mark.setAttribute('data-anno-id', id);
          mark.textContent = text.slice(i, j);
          frag.appendChild(mark);
          i = j;
        } else {
          // Plain text up to the next hit (or end).
          var k = i;
          while (k < text.length && !hits.has(k)) k++;
          frag.appendChild(document.createTextNode(text.slice(i, k)));
          i = k;
        }
      }
      if (node.parentNode) node.parentNode.replaceChild(frag, node);
    }

    function nodeKey(node) {
      // Stable identifier so the perNode bucket groups by reference.
      if (!node.__hdcAnnoKey) node.__hdcAnnoKey = '_n' + (Math.random().toString(36).slice(2));
      return node.__hdcAnnoKey;
    }

    function bindSync() {
      function setHover(id, on) {
        // Toggle .hovered on the marker, the side-panel item, and any
        // .okc-anno-substr matches.
        self.querySelectorAll('[data-anno-id="' + id + '"]').forEach(function (el) {
          el.classList.toggle('hovered', on);
        });
        // Toggle .okt-anno-target on every line the annotation points
        // at. Falls back to the line carrying the marker when no
        // explicit `lines` was authored.
        var targets = annoTargets[id];
        var lines = (targets && targets.lines.length) ? targets.lines.slice() : [];
        if (!lines.length) {
          var markerEl = self.querySelector('.okc-anno-marker[data-anno-id="' + id + '"]');
          var lineEl = markerEl && markerEl.closest('.okt-code-line');
          if (lineEl) {
            var ln = parseInt(lineEl.getAttribute('data-line'), 10);
            if (ln) lines.push(ln);
          }
        }
        lines.forEach(function (n) {
          var lineEl = self.querySelector('pre code > .okt-code-line[data-line="' + n + '"]');
          if (lineEl) lineEl.classList.toggle('okt-anno-target', on);
        });
        // Tooltip positioning. The tip is position:fixed (escapes any
        // ancestor clipping context), pointing at the centre-top of
        // the highlighted block. Always renders ABOVE the block so
        // scroll never clips it; if there isn't room above (block is
        // near the viewport top) we flip below and clamp.
        // Substring chips live inline (not in the gutter slot) and
        // get their tip as a sibling — handle both cases.
        var slotMarker = self.querySelector('.okc-anno-line-marker .okc-anno-marker[data-anno-id="' + id + '"]');
        var substrChip = self.querySelector('.okc-anno-marker.okc-anno-marker-substr[data-anno-id="' + id + '"]');
        var anchorMarker = slotMarker || substrChip;
        var tip = anchorMarker && (function () {
          // Tip is always the immediate next-sibling .okc-anno-tip
          // OR a child of the slot — search both.
          var next = anchorMarker.nextElementSibling;
          if (next && next.classList.contains('okc-anno-tip')) return next;
          var parent = anchorMarker.parentElement;
          return parent && parent.querySelector(':scope > .okc-anno-tip');
        })();
        if (tip) {
          if (on) {
            var anchorRect;
            if (lines.length) {
              var firstLineEl = self.querySelector('pre code > .okt-code-line[data-line="' + lines[0] + '"]');
              var lastLineEl  = self.querySelector('pre code > .okt-code-line[data-line="' + lines[lines.length - 1] + '"]');
              if (firstLineEl && lastLineEl) {
                var a = firstLineEl.getBoundingClientRect();
                var b = lastLineEl.getBoundingClientRect();
                anchorRect = { top: a.top, bottom: b.bottom, left: a.left, right: a.right };
              }
            }
            if (!anchorRect) {
              // Substring annotations: anchor on the first matched
              // <mark>, or fall back to the marker itself.
              var firstMark = self.querySelector('.okc-anno-substr[data-anno-id="' + id + '"]');
              var base = firstMark || anchorMarker;
              anchorRect = base.getBoundingClientRect();
            }
            var anchorMidX = (anchorRect.left + anchorRect.right) / 2;
            // Render once to measure; reset transform / margin so
            // we can take a fresh box, then re-apply the flip rule.
            tip.style.display = 'block';
            tip.style.left = anchorMidX + 'px';
            tip.style.top = (anchorRect.top - 10) + 'px';
            tip.style.transform = 'translate(-50%, -100%)';
            var tipBox = tip.getBoundingClientRect();
            // If the tooltip would render above the viewport top,
            // flip below the anchor block instead.
            if (tipBox.top < 8) {
              tip.style.top = (anchorRect.bottom + 10) + 'px';
              tip.style.transform = 'translate(-50%, 0)';
            }
          } else {
            tip.style.display = '';
            tip.style.left = '';
            tip.style.top = '';
            tip.style.transform = '';
          }
        }
      }
      self.querySelectorAll('.okc-anno-marker, .okc-anno-item').forEach(function (el) {
        var id = el.getAttribute('data-anno-id');
        if (el.dataset.hdcAnnoBound === '1') return;
        el.dataset.hdcAnnoBound = '1';
        el.addEventListener('mouseenter', function () { setHover(id, true); });
        el.addEventListener('mouseleave', function () { setHover(id, false); });
        el.addEventListener('focus',      function () { setHover(id, true); });
        el.addEventListener('blur',       function () { setHover(id, false); });
        el.addEventListener('click', function () {
          var partner = el.classList.contains('okc-anno-marker')
            ? self.querySelector('.okc-anno-item[data-anno-id="' + id + '"]')
            : self.querySelector('.okc-anno-marker[data-anno-id="' + id + '"]');
          if (partner) partner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
      });
    }

    /* Build the per-line annotation slot: each .okt-code-line gets an
       extra cell that lives in its OWN grid column (not overlapping
       line numbers). Empty by default; populated by moveMarkersToSlots
       when an annotation marker for this line exists. */
    function prepareLineSlots() {
      var c = self.querySelector('pre code');
      if (!c) return;
      if (!c.querySelector(':scope > .okt-code-line')) {
        _hdtWrapCodeLines(c);
      }
      var lines = c.querySelectorAll(':scope > .okt-code-line');
      lines.forEach(function (line) {
        if (line.querySelector(':scope > .okc-anno-line-marker')) return;
        var slot = document.createElement('span');
        slot.className = 'okc-anno-line-marker';
        slot.setAttribute('aria-hidden', 'true');
        // Insert BEFORE the code-content cell so the annotation column
        // sits adjacent to the code (right of the line number + fold).
        // Final grid order: [num] [fold] [anno] [content]. The CSS
        // override (below) widens .okt-code-line's grid-template-columns
        // to a 4-column layout matching that DOM order.
        var content = line.querySelector(':scope > .okt-code-content');
        if (content) {
          line.insertBefore(slot, content);
        } else {
          line.appendChild(slot);
        }
      });
      self.classList.add('okc-anno-gutter-on');
    }

    /* After markers are injected inline (within the now per-line spans),
       MOVE each marker into its line's annotation slot AND attach a
       hover-tooltip carrying the annotation body so the reader can
       preview the explanation without scanning the list below. */
    function moveMarkersToSlots() {
      var inline = self.querySelectorAll('pre code .okc-anno-marker');
      Array.prototype.forEach.call(inline, function (btn) {
        // Substring-anchored chips stay inline next to their match.
        // Only the line-anchored chips move into the gutter slot.
        if (btn.classList.contains('okc-anno-marker-substr')) return;
        var line = btn.closest('.okt-code-line');
        if (!line) return;
        var slot = line.querySelector(':scope > .okc-anno-line-marker');
        if (!slot) return;
        if (btn.parentElement !== slot) slot.appendChild(btn);
        // Tooltip carrying the annotation body. Pull from the matching
        // list item's body so authored HTML survives.
        if (!slot.querySelector(':scope > .okc-anno-tip')) {
          var id = btn.getAttribute('data-anno-id');
          var match = self.querySelector('.okc-anno-item[data-anno-id="' + id + '"] .okc-anno-body');
          if (match) {
            var tip = document.createElement('span');
            tip.className = 'okc-anno-tip';
            tip.setAttribute('role', 'tooltip');
            tip.innerHTML = match.innerHTML;
            slot.appendChild(tip);
          }
        }
      });
      // Substring-anchored chips need their own tooltip — but it must
      // be the only tip per annotation id (otherwise the same body
      // shows twice). Attach to the chip itself, sibling-style.
      self.querySelectorAll('pre code .okc-anno-marker.okc-anno-marker-substr').forEach(function (btn) {
        if (btn.nextElementSibling && btn.nextElementSibling.classList.contains('okc-anno-tip')) return;
        var id = btn.getAttribute('data-anno-id');
        var match = self.querySelector('.okc-anno-item[data-anno-id="' + id + '"] .okc-anno-body');
        if (!match) return;
        var tip = document.createElement('span');
        tip.className = 'okc-anno-tip';
        tip.setAttribute('role', 'tooltip');
        tip.innerHTML = match.innerHTML;
        btn.parentNode.insertBefore(tip, btn.nextSibling);
      });
    }

    /* Order matters: WRAP lines first, THEN inject markers + move into
       slots. The previous order (inject → wrap → move) lost button
       handlers because _hdtWrapCodeLines clones-then-clears the code's
       children; the new buttons in the wrapped lines would be cloneless
       copies with no listeners. */
    function buildMarkers() {
      prepareLineSlots();
      injectSubstringMarks(); // wrap `match` occurrences BEFORE injecting (N) markers
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
if (!customElements.get('oku-annotated-code')) customElements.define('oku-annotated-code', OkuAnnotatedCode);

/* ============ <oku-snippet> — editable HTML/CSS/JS playground ============ */
class OkuSnippet extends HTMLElement {
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
if (!customElements.get('oku-snippet')) customElements.define('oku-snippet', OkuSnippet);

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
    // DOM shape:
    //   .page-nav-scroll   ← flex-1, scrolls; holds the site-tree panel
    //                        AND the adopted page-toc (appended by
    //                        adopt() below).
    //   .page-nav-edge     ← absolute-positioned right-edge handle.
    //   .page-nav-footer   ← flex-shrink:0, pinned at the literal
    //                        bottom edge of the sidebar; never scrolls
    //                        and never sits between tree and TOC.
    // The version label is dimmed; it tells the reader which build
    // of oku they're reading without competing with content.
    this.innerHTML =
      '<div class="page-nav-scroll">' +
        '<div class="page-nav-panel">' +
          '<ol class="page-nav-tree"><li class="page-nav-loading">Loading…</li></ol>' +
        '</div>' +
      '</div>' +
      // Right-edge handle: drag to resize, click (no drag) to collapse.
      // Symmetric to the collapsed 24px rail's full-edge expand affordance.
      '<div class="page-nav-edge" role="separator" aria-orientation="vertical" ' +
        'aria-label="Resize or collapse sidebar" tabindex="0"></div>' +
      '<div class="page-nav-footer">' +
        'oku <span class="page-nav-version">v' + KIT_VERSION + '</span>' +
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
      // Adopt INTO the scroll wrapper so the site-tree panel and the
      // TOC share one scroll context, with the footer fixed below.
      // If the wrapper isn't there for any reason (custom shape), the
      // page-nav element itself is the next-best parent.
      var scrollHost = self.querySelector(':scope > .page-nav-scroll') || self;
      if (siblingToc && siblingToc.parentElement !== scrollHost) {
        scrollHost.appendChild(siblingToc);
      }
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', adopt);
    } else {
      Promise.resolve().then(adopt);
    }
    // Click-anywhere-on-the-rail to expand when collapsed. The whole
    // page-nav becomes the click target. The base CSS already sets
    // position: sticky on page-nav, which is enough containing-block
    // for the absolute-positioned children; setting it inline here
    // used to break the narrow-viewport `position: fixed` drawer rule.
    this.addEventListener('click', function (e) {
      if (!document.body.classList.contains('sidebar-collapsed')) return;
      if (e.target && e.target.closest('a, button, input, select')) return;
      if (e.target && e.target.classList.contains('page-nav-edge')) return;
      if (typeof toggleTOC === 'function') toggleTOC();
    });

    // Right-edge handle: click (no drag) toggles collapse; drag resizes.
    // Heuristic: mouseup with movement <= EDGE_DRAG_THRESHOLD is a click;
    // anything beyond is a resize. Width persists per host across reloads.
    var edge = this.querySelector('.page-nav-edge');
    if (edge) {
      var EDGE_DRAG_THRESHOLD = 4;
      var MIN_WIDTH = 200;
      var MAX_WIDTH_FRAC = 0.6;
      // Restore persisted width (only when not collapsed).
      try {
        var stored = parseInt(localStorage.getItem('sidebarWidth') || '', 10);
        if (stored && stored >= MIN_WIDTH) {
          document.body.style.setProperty('--sidebar-width', stored + 'px');
        }
      } catch (eRestore) {}
      edge.addEventListener('mousedown', function (e) {
        // Ignore right/middle clicks.
        if (e.button !== 0) return;
        if (document.body.classList.contains('sidebar-collapsed')) {
          // In collapsed mode the rail handles expansion; bail.
          return;
        }
        e.preventDefault();
        var startX = e.clientX;
        var startWidth = self.getBoundingClientRect().width;
        var moved = false;
        document.body.classList.add('sidebar-resizing');
        function onMove(ev) {
          var dx = ev.clientX - startX;
          if (!moved && Math.abs(dx) <= EDGE_DRAG_THRESHOLD) return;
          moved = true;
          var w = startWidth + dx;
          var max = Math.floor(window.innerWidth * MAX_WIDTH_FRAC);
          if (w < MIN_WIDTH) w = MIN_WIDTH;
          if (w > max) w = max;
          document.body.style.setProperty('--sidebar-width', w + 'px');
        }
        function onUp() {
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          document.body.classList.remove('sidebar-resizing');
          if (moved) {
            try {
              var w = parseInt((document.body.style.getPropertyValue('--sidebar-width') || '').replace('px', ''), 10);
              if (w) localStorage.setItem('sidebarWidth', String(w));
            } catch (eStore) {}
          } else {
            if (typeof toggleTOC === 'function') toggleTOC();
          }
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      });
      // Keyboard alternative for collapse — focus the handle, press Enter/Space.
      edge.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (typeof toggleTOC === 'function') toggleTOC();
        }
      });
    }
    // Drawer Escape handling now lives next to toggleTOC; this block
    // used to remove a stale `.open` class on page-nav that the new
    // drawer model doesn't use.

    // Defer until the document is fully parsed so we can reliably detect
    // the standalone-build inline page-data script (which sits at the
    // end of body, after <page-nav>).
    function start() {
      if (document.getElementById('__oku_page__')) {
        self.style.display = 'none';
        return;
      }
      loadManifest()
        .then(function (manifest) { self._renderTree(manifest); })
        .catch(function () {
          // No manifest: degrade silently. The sidebar prints an inline
          // hint about running `oku serve` so the user knows how
          // to enable full site navigation. A floating warning banner
          // was noisy for IDE-served previews where this is expected.
          self._renderTree(null);
        });
    }

    /* Site tree discovery — three stages, in order of authority.
       1) GET docs/site-manifest.json. `oku serve` synthesises this
          in memory on each request (no file written to source); a built
          dist/site/ has the real file next to the pages. No-op on any
          static server that doesn't expose it (404 → next stage).
       2) Subdir walker. For each subdir already known from the inline
          seed (plus the docs root itself, in case the server returned a
          listing there), fetch the HTML directory listing the server
          serves for a dir URL — Python http.server, nginx autoindex,
          most static servers — parse the anchors, fetch each *.json,
          keep the ones with kind="page". Picks up pages added under
          existing subdirs without re-init.
       3) Inline window.__okuManifest. Last-resort seed for setups
          that do neither — file://, IntelliJ built-in webserver, the
          standalone single-file build. `oku init` refreshes the
          inline at the moment a new top-level page joins the tree. */
    function loadManifest() {
      var fileProto = (window.location && window.location.protocol === 'file:');
      var inline = window.__okuManifest;
      if (fileProto) {
        return inline
          ? Promise.resolve(inline)
          : Promise.reject(new Error('file:// — no manifest reachable'));
      }
      return fetchManifestOverHttp()
        .catch(function () { return discoverManifestByWalking(__okuDocsRoot, inline); })
        .catch(function (err) {
          if (inline) return inline;
          throw err;
        });
    }

    function fetchManifestOverHttp() {
      /* Synthesised per-request by `oku serve` (in memory; nothing
         lands in docs/), and a real file in built dist/site/. Treat any
         non-2xx as "not provided by this server" and fall through to
         the walker. */
      var wa = (window.__okuWithAuth || function (u) { return u; });
      return fetch(wa(__okuDocsRoot + 'site-manifest.json'), { cache: 'no-cache' })
        .then(function (r) {
          if (r.ok) return r.json();
          throw new Error('manifest http ' + r.status);
        });
    }

    function discoverManifestByWalking(rootUrl, seed) {
      /* Build the manifest from a hybrid source: the inline seed gives
         us top-level pages (which can't be enumerated over HTTP because
         servers serve index.html for the docs/ URL), then each subdir
         already known from the seed — plus subdirs discovered by walking
         the root in case the server *did* return a listing — is fetched
         fresh so newly-added pages appear without re-init. SKIP mirrors
         SKIP_DIRS in src/html_doc/cli.py; META lists .json filenames
         that aren't pages. */
      var wa = (window.__okuWithAuth || function (u) { return u; });
      var SKIP = {
        '_kit': 1, 'kit': 1, 'dist': 1, 'build': 1, 'node_modules': 1,
        '.git': 1, '.idea': 1, '.venv': 1, 'venv': 1,
        '__pycache__': 1, '.pytest_cache': 1, '.ruff_cache': 1,
        '.mypy_cache': 1, 'templates': 1, '_internal': 1
      };
      var META = /^(site-manifest|kit|package|tsconfig)\.json$/i;
      var pages = [];
      var visited = {};
      var known = {};

      // Seed: every page the inline manifest reported. Subsequent walks
      // skip these (de-dup by HTML path) and only push new pages.
      if (seed && Array.isArray(seed.pages)) {
        seed.pages.forEach(function (p) {
          if (!p || !p.path || known[p.path]) return;
          pages.push(p);
          known[p.path] = true;
        });
      }

      function listDir(absoluteUrl) {
        return fetch(wa(absoluteUrl), {
          cache: 'no-cache',
          headers: { 'Accept': 'text/html' }
        }).then(function (r) {
          if (!r.ok) return [];
          var ctype = (r.headers.get('Content-Type') || '').toLowerCase();
          if (ctype.indexOf('text/html') === -1 &&
              ctype.indexOf('application/xhtml') === -1) {
            return [];
          }
          return r.text().then(function (html) {
            var doc = new DOMParser().parseFromString(html, 'text/html');
            // A directory listing has plain anchors to siblings; our own
            // index.html loads the kit via _kit/. When we hit index.html
            // (server preferred it over the directory listing), there's
            // nothing to enumerate — return [] and rely on the seed for
            // this level.
            if (doc.querySelector('script[src*="/_kit/"], link[href*="/_kit/"], page-chrome')) {
              return [];
            }
            var out = [];
            var anchors = doc.querySelectorAll('a[href]');
            for (var i = 0; i < anchors.length; i++) {
              var h = anchors[i].getAttribute('href');
              if (!h) continue;
              h = h.split('?')[0].split('#')[0];
              if (!h || h === '../' || h === '/') continue;
              if (h.indexOf('://') !== -1) continue;  // off-host link
              if (h.charAt(0) === '/') continue;       // server-absolute
              out.push(h);
            }
            return out;
          });
        }).catch(function () { return []; });
      }

      function fetchPage(absoluteUrl, relPath) {
        var navPath = relPath.replace(/\.json$/i, '.html');
        if (known[navPath]) return Promise.resolve();
        known[navPath] = true;  // claim early so a parallel walk doesn't dup
        return fetch(wa(absoluteUrl), { cache: 'no-cache' })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (data) {
            if (!data || typeof data !== 'object' || data.kind !== 'page') return;
            var slash = navPath.lastIndexOf('/');
            var parent = slash >= 0 ? navPath.slice(0, slash) : null;
            var meta = data.meta || {};
            var entry = {
              path: navPath,
              source: relPath,
              title: data.title || navPath,
              parent: parent
            };
            if (meta.order != null) entry.order = meta.order;
            if (meta.summary != null) entry.summary = meta.summary;
            pages.push(entry);
          })
          .catch(function () { /* unreadable .json — not a page */ });
      }

      function walk(absoluteUrl, relPrefix, depth) {
        // Cap recursion at 8 levels. A docs/ tree that goes deeper is
        // either a misconfiguration or a tree we shouldn't be walking.
        if (depth > 8) return Promise.resolve();
        if (visited[absoluteUrl]) return Promise.resolve();
        visited[absoluteUrl] = true;
        return listDir(absoluteUrl).then(function (hrefs) {
          var pending = [];
          for (var i = 0; i < hrefs.length; i++) {
            var href = hrefs[i];
            if (href.charAt(href.length - 1) === '/') {
              var name = href.slice(0, -1);
              if (SKIP[name]) continue;
              pending.push(walk(absoluteUrl + href, relPrefix + href, depth + 1));
            } else if (/\.json$/i.test(href) && !META.test(href)) {
              pending.push(fetchPage(absoluteUrl + href, relPrefix + href));
            }
          }
          return Promise.all(pending);
        });
      }

      // Walk the docs root (no-op when the server returns our index.html
      // there — see listDir above) and every subdir referenced by the
      // seed. The latter is what makes adding a page under plans/ etc.
      // visible on refresh without any kit-side state.
      var starts = [walk(rootUrl, '', 0)];
      var seenSubdir = {};
      if (seed && Array.isArray(seed.pages)) {
        seed.pages.forEach(function (p) {
          if (!p.parent || seenSubdir[p.parent] || SKIP[p.parent]) return;
          seenSubdir[p.parent] = true;
          starts.push(walk(rootUrl + p.parent + '/', p.parent + '/', 1));
        });
      }

      return Promise.all(starts).then(function () {
        if (!pages.length) throw new Error('walk: no pages discovered under ' + rootUrl);
        pages.sort(function (a, b) {
          return a.path < b.path ? -1 : a.path > b.path ? 1 : 0;
        });
        return { schema_version: 1, root: '.', pages: pages };
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
      // No manifest available — typical when the page is opened directly
      // (IDE-served, file://). Tell the reader how to enable the full
      // site tree without making it look like an error.
      tree.innerHTML = '<li class="page-nav-empty">Run <code>oku serve</code> for full site navigation.</li>';
      return;
    }
    if (!Array.isArray(manifest.pages)) {
      tree.innerHTML = '<li class="page-nav-empty">site-manifest.json is malformed (no <code>pages</code> array). Run <code>oku build</code>.</li>';
      window.dispatchEvent(new CustomEvent('oku:warnings', {
        detail: [{ code: 'manifest-malformed', msg: 'site-manifest.json missing pages[]', level: 'warn' }]
      }));
      return;
    }
    if (manifest.schema_version && manifest.schema_version > 1) {
      window.dispatchEvent(new CustomEvent('oku:warnings', {
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

    // Hash-based router: the URL pathname always stays at the entry
    // stub (e.g., index.html). The hash carries the current page —
    // "#architecture.html" — so refresh / middle-click / copy-link
    // stay robust under any static host. The "active" page is whatever
    // the hash points to; falls back to index.html when empty.
    function currentHashPage() {
      var raw = (window.location.hash || '').replace(/^#/, '');
      var sep = raw.indexOf(':');
      var p = sep >= 0 ? raw.slice(0, sep) : raw;
      if (p && p.endsWith('.html')) return p;
      return 'index.html';
    }
    function isActive(page) {
      return currentHashPage() === page.path;
    }

    function renderLevel(parentKey, depth) {
      var ol = document.createElement('ol');
      ol.className = 'page-nav-level depth-' + depth;
      var items = byParent[parentKey] || [];
      items.forEach(function (page) {
        var li = document.createElement('li');
        li.className = 'page-nav-item';
        var anchor = document.createElement('a');
        // Hash-only hrefs keep the pathname pinned to index.html so
        // refresh and middle-click both stay valid even when no
        // per-page stub exists on disk.
        anchor.href = '#' + page.path;
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
var __okuWarnings = (function () {
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
      html += '<li class="' + levelClass + '"><code>' + (w.code || 'warn') + '</code> ' + escapeHTML(w.msg || '');
      if (w.target) {
        // Selector-based jump: scrolls + briefly highlights the offending
        // element so the reader can find the source of the warning
        // without scanning the whole page.
        html += ' <a class="warning-panel-jump" href="' + escapeHTML(w.target) + '">Jump to</a>';
      }
      html += '</li>';
    });
    html += '</ul>';
    panel.innerHTML = html;
    document.body.appendChild(panel);
    panel.querySelector('.warning-panel-dismiss').addEventListener('click', function () {
      dismissed = true;
      hide();
      if (panel && panel.parentNode) { panel.parentNode.removeChild(panel); panel = null; }
    });
    panel.querySelectorAll('.warning-panel-jump').forEach(function (a) {
      a.addEventListener('click', function (ev) {
        ev.preventDefault();
        var sel = a.getAttribute('href') || '';
        var el = null;
        try { el = sel ? document.querySelector(sel) : null; } catch (e) { el = null; }
        if (!el) return;
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Brief flash so the eye locks onto the right element even
        // when several are visible after the scroll settles.
        el.classList.add('oku-flash');
        setTimeout(function () { el.classList.remove('oku-flash'); }, 1800);
      });
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

  function clear() {
    // Reset the page-scoped store. Used on hash navigation so a stale
    // warning from the previous page (e.g. a mermaid parse error in
    // build-architecture) doesn't follow the reader to an unrelated
    // page. Per-session dismiss is also reset — the next page gets a
    // fresh chance to surface its own issues.
    list.length = 0;
    dismissed = false;
    hide();
  }

  // Capture standard error channels too
  window.addEventListener('error', function (e) {
    push([{ code: 'window-error', msg: (e.message || 'unknown') + ' @ ' + (e.filename || '?') + ':' + (e.lineno || 0), level: 'error' }]);
  });
  window.addEventListener('unhandledrejection', function (e) {
    push([{ code: 'unhandled-rejection', msg: String((e && e.reason && e.reason.message) || e.reason || 'unknown'), level: 'error' }]);
  });

  return { push: push, clear: clear };
})();

window.addEventListener('oku:warnings', function (e) {
  if (e && e.detail) __okuWarnings.push(e.detail);
});

// Scope warnings to the active page: clear the store on every hash
// navigation so stale entries from the previous page (e.g. a mermaid
// parse error) don't carry over. New renders push fresh entries.
window.addEventListener('hashchange', function () {
  __okuWarnings.clear();
});

/* ============ Pagefind search ============ *
 * Search button in the top-right system cluster opens a modal with
 * an input + result list. Pagefind is loaded lazily on first invoke;
 * if the bundle is absent (e.g., dev mode without a build) the modal
 * shows a graceful message.
 * ----------------------------------------------------------------- */
var __okuSearch = (function () {
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
      __okuDocsRoot + 'pagefind/pagefind.js',
      __okuDocsRoot + '_kit/pagefind/pagefind.js'
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
     served dev pages, no `oku build` has run yet), scan the
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
            'Run <code>oku build</code> + view from <code>dist/site/</code> for full-site search.';
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

document.addEventListener('DOMContentLoaded', function () { __okuSearch.addButton(); });

/* ============ Rebuild TOC after JSON renderer completes ============ */
window.addEventListener('oku:rendered', function () {
  var tocList = document.querySelector('page-toc .toc-list');
  if (tocList) buildTOC(tocList);
  initReadingAids();
});
