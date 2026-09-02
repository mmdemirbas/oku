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
    /* The reader gets two states, sun and moon. Following the OS is not
       a third one they click into — it is where the page rests, and an
       explicit choice lives only until the OS next flips. So the stored
       value carries the OS setting that was in force when the choice was
       made ("dark@light"); once the OS has moved on, the choice has
       expired and is dropped here. This is the half a matchMedia
       listener cannot do: the flip usually happens with the tab closed. */
    var sys = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var pref = (localStorage.getItem('theme-pref') || '').split('@');
    /* pref[0] !== sys is not redundant with the pref[1] test — it is what
       rejects a value written by a kit old enough to store a bare theme. */
    var mode = (pref.length === 2 && pref[1] === sys
                && (pref[0] === 'light' || pref[0] === 'dark') && pref[0] !== sys)
      ? pref[0] : 'system';
    if (mode === 'system') localStorage.removeItem('theme-pref');
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
