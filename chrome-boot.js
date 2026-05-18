/* html-doc · chrome-boot.js
 * Synchronous pre-paint init: sets theme + TOC state before body renders.
 * Must be the FIRST script in <head>, loaded synchronously (no defer/async).
 * Reads localStorage: 'theme-pref' (light|dark|absent=system), 'tocCollapsed'.
 * Also exposes window.__htmldocWithAuth() so chrome.js + renderer.js can
 * propagate IntelliJ's _ijt token to internal asset URLs before either
 * deferred script executes.
 */
(function () {
  try {
    var pref = localStorage.getItem('theme-pref');
    var mode = (pref === 'light' || pref === 'dark') ? pref : 'system';
    var actual = mode === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : mode;
    document.documentElement.setAttribute('data-theme', actual);
    document.documentElement.setAttribute('data-theme-mode', mode);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
    document.documentElement.setAttribute('data-theme-mode', 'system');
  }

  /* IntelliJ's built-in server (localhost:63342) requires ?_ijt=<token>
     on every GET. The page URL carries it; sub-resource requests stripped
     of query strings get 404. Pluck it from location.search once and
     expose a helper to append it to internal URLs. No-op when absent. */
  var authParam = '';
  try {
    var m = (window.location.search || '').match(/[?&]_ijt=([^&]+)/);
    if (m) authParam = '_ijt=' + m[1];
  } catch (e) { /* ignore */ }
  window.__htmldocWithAuth = function (url) {
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

  document.addEventListener('DOMContentLoaded', function () {
    try {
      if (localStorage.getItem('tocCollapsed') === '1' && window.innerWidth > 920) {
        document.body.classList.add('toc-collapsed');
      }
    } catch (e) {}
  });
})();
