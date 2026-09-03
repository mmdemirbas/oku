/* oku · chrome-boot.js
 * Synchronous pre-paint init: sets theme before body renders.
 * Must be the FIRST script in <head>, loaded synchronously (no defer/async).
 * Reads localStorage: 'theme-pref' ("<chosen>@<os-at-choice>", absent=follow OS).
 * Sidebar-collapsed state is restored later by chrome.js (key:
 * 'sidebarCollapsed'). The first-visit default is EXPANDED so a new
 * visitor sees the site tree — chrome.js only applies the collapsed
 * class when the key is explicitly '1'.
 * Also exposes window.__okuWithAuth() so chrome.js + renderer.js can
 * propagate IntelliJ's _ijt token to internal asset URLs before either
 * deferred script executes.
 */
(function () {
  try {
    /* Three stops: system, light, dark. The absence of a key IS system,
       so a reader who has never touched the control and one who chose
       System back are the same state rather than two that can drift.

       A kit before this rule stored `<theme>@<os-at-choice>` and expired
       the choice when the OS moved on. Under this rule there is no
       expiry, so the first field is simply that reader's pin and is
       honoured — and rewritten to the bare form, so the migration
       happens once rather than on every load. */
    var sys = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var stored = (localStorage.getItem('theme-pref') || '').split('@')[0];
    var mode = (stored === 'light' || stored === 'dark') ? stored : 'system';
    if (mode === 'system') localStorage.removeItem('theme-pref');
    else localStorage.setItem('theme-pref', mode);
    document.documentElement.setAttribute('data-theme', mode === 'system' ? sys : mode);
    document.documentElement.setAttribute('data-theme-mode', mode);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
    document.documentElement.setAttribute('data-theme-mode', 'system');
  }

  /* The reader's text scale, before first paint and for the same reason
     the theme is here: `zoom` on the reading column reflows every line
     on the page, so restoring it after the document has been drawn is a
     visible re-layout on every load. The ladder is chrome.js's
     (TEXT_SCALES) and is not repeated — an out-of-range value written by
     hand is snapped there, and until then it is only a number in a
     `zoom`, which cannot break the layout the way a bad theme name
     would. Clamped anyway, because `zoom: 0` renders nothing at all. */
  try {
    var scale = parseFloat(localStorage.getItem('oku-text-scale'));
    if (scale > 0) {
      scale = Math.max(0.5, Math.min(3, scale));
      document.documentElement.style.setProperty('--oku-text-scale', String(scale));
      document.documentElement.setAttribute('data-text-scale', String(scale));
    }
  } catch (e) { /* ignore */ }

  /* IntelliJ's built-in server (localhost:63342) requires ?_ijt=<token>
     on every GET. The page URL carries it; sub-resource requests stripped
     of query strings get 404. Pluck it from location.search once and
     expose a helper to append it to internal URLs. No-op when absent. */
  var authParam = '';
  try {
    var m = (window.location.search || '').match(/[?&]_ijt=([^&]+)/);
    if (m) authParam = '_ijt=' + m[1];
  } catch (e) { /* ignore */ }
  window.__okuWithAuth = function (url) {
    if (!authParam || !url) return url;
    if (url.charAt(0) === '#' || url.indexOf('javascript:') === 0) return url;
    // Absolute URL with scheme — only append for same-origin (don't taint
    // Mermaid/Prism CDN requests with our IDE auth token).
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(url)) {
      if (url.indexOf(window.location.origin + '/') !== 0
          && url !== window.location.origin) return url;
    }
    var sep = url.indexOf('?') >= 0 ? '&' : '?';
    return url + sep + authParam;
  };

})();
