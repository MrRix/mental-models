/* Display settings: a bottom sheet (<dialog>, showModal) opened by any [data-open-settings]
   button. Every change applies live to the page behind the sheet and is saved at once;
   there is no Save button. Storage and apply logic live in prefs.js (window.mmPrefs). */
(function () {
  "use strict";
  var P = window.mmPrefs;
  if (!P) return;
  var dlg = document.getElementById("settings");
  var openers = document.querySelectorAll("[data-open-settings]");
  var prefs = P.read();

  // Another tab changed the settings, or this page came back from the back/forward cache.
  function reload() { prefs = P.apply(P.read()); if (dlg && dlg.open) render(); }
  window.addEventListener("storage", function (e) { if (e.key === P.KEY) reload(); });
  window.addEventListener("pageshow", function (e) { if (e.persisted) reload(); });

  if (!dlg || typeof dlg.showModal !== "function") {
    // No <dialog> support (iOS before 15.4): hide the buttons rather than offer a broken sheet.
    for (var i = 0; i < openers.length; i++) openers[i].hidden = true;
    return;
  }

  var KINDS = ["theme", "font", "spacing"];
  var opener = null, askedPersist = false;
  var note = document.getElementById("settings-note");
  var NOTE = note ? note.textContent : "";
  var valueEl = document.getElementById("set-size-value");
  var down = dlg.querySelector('[data-size-step="-1"]');
  var up = dlg.querySelector('[data-size-step="1"]');

  // aria-disabled (not disabled) so an end button keeps focus for keyboard and VoiceOver users.
  function setStep(b, off, label) {
    b.setAttribute("aria-disabled", off ? "true" : "false");
    b.setAttribute("aria-label", label + (off ? ", " + (b === up ? "largest" : "smallest") : ""));
  }
  function render() {
    var pct = prefs.size + "%", at = P.SIZES.indexOf(prefs.size);
    valueEl.textContent = pct;
    setStep(down, at <= 0, "Decrease text size, currently " + pct);
    setStep(up, at >= P.SIZES.length - 1, "Increase text size, currently " + pct);
    KINDS.forEach(function (k) {
      var r = dlg.querySelectorAll('input[name="mm-' + k + '"]');
      for (var j = 0; j < r.length; j++) r[j].checked = r[j].value === prefs[k];
    });
  }
  function commit(next) {
    prefs = P.apply(next);
    var saved = P.save(prefs);
    if (note) note.textContent = saved ? NOTE : "This browser is not allowing saving, so these settings last until you leave this page.";
    if (saved && !askedPersist) {
      askedPersist = true;
      // Ask the browser not to evict site storage under pressure. The answer does not matter.
      try { if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {}); } catch (e) {}
    }
    render();
  }
  function change(k, v) {
    var next = {};
    for (var key in prefs) next[key] = prefs[key];
    next[k] = v;
    commit(next);
  }

  [down, up].forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.getAttribute("aria-disabled") === "true") return;
      var at = P.SIZES.indexOf(prefs.size) + (b === up ? 1 : -1);
      if (at >= 0 && at < P.SIZES.length) change("size", P.SIZES[at]);
    });
  });
  dlg.addEventListener("change", function (e) {
    var t = e.target;
    if (t && t.type === "radio" && t.checked && /^mm-/.test(t.name)) change(t.name.slice(3), t.value);
  });
  dlg.querySelector("[data-reset-settings]").addEventListener("click", function () { commit(P.DEFAULTS); });

  for (var n = 0; n < openers.length; n++) {
    openers[n].addEventListener("click", function (e) {
      opener = e.currentTarget;
      render();
      if (!dlg.open) dlg.showModal();
    });
  }
  dlg.querySelector("[data-close-settings]").addEventListener("click", function () { dlg.close(); });
  // Esc closes natively (cancel, then close). Focus always returns to the Aa button that opened it.
  dlg.addEventListener("close", function () {
    var o = opener;
    opener = null;
    if (o && document.contains(o)) { try { o.focus({ preventScroll: true }); } catch (err) { o.focus(); } }
  });
  // Tap on the backdrop closes. The dialog box has no padding of its own (content sits in
  // .sheet-body), so an event targeting the dialog itself came from the backdrop. Both the
  // press and the release must be outside, so a drag that ends on the backdrop does not close.
  function outside(e) {
    if (e.target !== dlg) return false;
    var r = dlg.getBoundingClientRect();
    return e.clientY < r.top || e.clientY > r.bottom || e.clientX < r.left || e.clientX > r.right;
  }
  var pressedOutside = false;
  dlg.addEventListener("pointerdown", function (e) { pressedOutside = outside(e); });
  dlg.addEventListener("click", function (e) {
    if (pressedOutside && outside(e)) dlg.close();
    pressedOutside = false;
  });
})();
