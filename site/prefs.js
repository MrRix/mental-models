/* Applies saved display preferences before first paint.
   Loaded as a blocking script in <head>, before style.css, so the first frame already has the
   right theme, typeface, spacing and text size (no flash). CSP-safe: no inline code, and the
   --scale custom property is set through the CSSOM, not a style="" attribute.
   Exposes window.mmPrefs for settings.js. */
(function () {
  "use strict";
  var KEY = "mm-prefs";
  var SIZES = [85, 100, 115, 130, 150, 175, 200];
  var DEFAULTS = { size: 100, theme: "system", font: "serif", spacing: "normal" };
  var CHOICES = { theme: ["system", "light", "dark"], font: ["serif", "sans"], spacing: ["normal", "relaxed"] };
  // Must match --bg in style.css and the theme-color tags build.py writes.
  var BAR = { light: "#F7F6F2", dark: "#14161C" };

  function clean(p) {
    var out = {}, k;
    p = p && typeof p === "object" ? p : {};
    for (k in DEFAULTS) out[k] = DEFAULTS[k];
    for (k in CHOICES) if (CHOICES[k].indexOf(p[k]) !== -1) out[k] = p[k];
    if (SIZES.indexOf(p.size) !== -1) out.size = p.size;
    return out;
  }

  function read() {
    try { return clean(JSON.parse(window.localStorage.getItem(KEY))); } catch (e) { return clean(null); }
  }

  function save(p) {
    try { window.localStorage.setItem(KEY, JSON.stringify(clean(p))); return true; } catch (e) { return false; }
  }

  function apply(p) {
    p = clean(p);
    var d = document.documentElement;
    d.setAttribute("data-theme", p.theme);
    d.setAttribute("data-font", p.font);
    d.setAttribute("data-spacing", p.spacing);
    d.style.setProperty("--scale", String(p.size / 100));
    // Status bar / browser chrome colour: the forced theme's, or each tag's own when following the system.
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) {
      var own = (metas[i].getAttribute("media") || "").indexOf("dark") !== -1 ? BAR.dark : BAR.light;
      metas[i].setAttribute("content", p.theme === "system" ? own : BAR[p.theme]);
    }
    return p;
  }

  window.mmPrefs = { KEY: KEY, SIZES: SIZES, DEFAULTS: DEFAULTS, clean: clean, read: read, save: save, apply: apply };
  apply(read());
})();
