(function () {
  "use strict";
  var root = document.body.getAttribute("data-root") || "";
  var slugs = [];
  try { slugs = JSON.parse(document.body.getAttribute("data-slugs") || "[]"); } catch (e) {}
  var total = parseInt(document.body.getAttribute("data-total") || "0", 10);
  var isSlug = function (s) { return typeof s === "string" && slugs.indexOf(s) !== -1; };

  // Small storage helpers. Storage can be missing or throw (private mode, blocked site data),
  // so every read and write is guarded and the page works without it.
  var load = function (store, key, fallback) {
    try { var v = JSON.parse(window[store].getItem(key)); return v == null ? fallback : v; } catch (e) { return fallback; }
  };
  var save = function (store, key, value) {
    try { window[store].setItem(key, JSON.stringify(value)); } catch (e) {}
  };
  var drop = function (store, key) { try { window[store].removeItem(key); } catch (e) {} };

  var readList = load("localStorage", "mm-read", []);
  if (!Array.isArray(readList)) readList = [];
  readList = readList.filter(isSlug);
  var isRead = function (s) { return readList.indexOf(s) !== -1; };
  var markRead = function (s) {
    if (!isSlug(s) || isRead(s)) return;
    readList.push(s);
    save("localStorage", "mm-read", readList);
  };

  // Offline: register the service worker that precaches every page.
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(root + "sw.js", { scope: root || "./" }).catch(function () {});
  }

  // Random model: prefer ones not read yet, then anything but the current page.
  document.querySelectorAll("button.random").forEach(function (b) {
    b.addEventListener("click", function () {
      var cur = b.getAttribute("data-current");
      var others = slugs.filter(function (s) { return s !== cur; });
      var unread = others.filter(function (s) { return !isRead(s); });
      var pool = unread.length ? unread : others;
      if (!pool.length) return;
      location.href = root + "m/" + pool[Math.floor(Math.random() * pool.length)] + ".html";
    });
  });

  // ---------- Article ----------
  var article = document.querySelector("main.article[data-slug]");
  if (article) {
    var slug = article.getAttribute("data-slug");
    var bar = document.getElementById("readbar");
    var nextNav = document.querySelector("nav.next");
    var finished = isRead(slug);
    var lastSave = 0, ticking = false;

    var fraction = function () {
      var max = document.documentElement.scrollHeight - window.innerHeight;
      return max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 1;
    };
    var update = function () {
      ticking = false;
      var f = fraction();
      if (bar) bar.style.transform = "scaleX(" + f.toFixed(4) + ")";
      if (f >= 0.85) {
        finished = true;
        markRead(slug);
        var last = load("localStorage", "mm-last", null);
        if (last && last.s === slug) drop("localStorage", "mm-last");
      } else if (!finished && f > 0.06) {
        var now = Date.now();
        if (now - lastSave > 600) {
          lastSave = now;
          save("localStorage", "mm-last", { s: slug, p: Math.round(f * 1000) / 1000 });
        }
      }
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener("resize", update);

    // Reaching the "Up next" block also counts as read (helps short articles on tall screens).
    if (nextNav && "IntersectionObserver" in window) {
      new IntersectionObserver(function (entries, obs) {
        if (entries.some(function (en) { return en.isIntersecting; })) {
          finished = true; markRead(slug); obs.disconnect();
        }
      }).observe(nextNav);
    }

    // "Continue reading" from the home page lands on #resume: restore the saved position.
    if (location.hash === "#resume") {
      var last = load("localStorage", "mm-last", null);
      try { history.replaceState(null, "", location.pathname); } catch (e) {}
      if (last && last.s === slug && typeof last.p === "number") {
        window.addEventListener("load", function () {
          var max = document.documentElement.scrollHeight - window.innerHeight;
          window.scrollTo(0, Math.round(max * last.p));
        });
      }
    }
    update();

    // Up next: swap in the first related model not read yet.
    var relEl = document.getElementById("related-data");
    var up = document.getElementById("upnext");
    if (relEl && up) {
      var related = [];
      try { related = JSON.parse(relEl.textContent); } catch (e) {}
      var pick = null;
      for (var k = 0; k < related.length; k++) {
        var r = related[k];
        if (Array.isArray(r) && isSlug(r[0]) && r[0] !== slug && !isRead(r[0])) { pick = r; break; }
      }
      if (pick) {
        up.href = root + "m/" + pick[0] + ".html";
        document.getElementById("upnext-name").textContent = pick[1];
        document.getElementById("upnext-desc").textContent = pick[2] || "";
      }
    }
  }

  // ---------- Home ----------
  var list = document.querySelector("li[data-slug]");
  if (list) {
    var items = document.querySelectorAll("li[data-slug]");
    var nRead = 0;
    items.forEach(function (li) {
      if (isRead(li.getAttribute("data-slug"))) { li.classList.add("read"); nRead++; }
    });
    var rc = document.getElementById("readcount");
    if (rc && nRead) rc.textContent = " · " + nRead + " read";

    var resume = document.getElementById("resume");
    var lastRead = load("localStorage", "mm-last", null);
    if (resume && lastRead && isSlug(lastRead.s) && !isRead(lastRead.s)) {
      var li = document.querySelector('li[data-slug="' + lastRead.s + '"] .name');
      if (li) {
        resume.href = "m/" + lastRead.s + ".html#resume";
        document.getElementById("resume-name").textContent = li.textContent;
        resume.hidden = false;
      }
    }

    // Keep the list position when coming back from an article.
    var y = load("sessionStorage", "mm-home-y", 0);
    if (typeof y === "number" && y > 0) {
      window.addEventListener("load", function () { window.scrollTo(0, y); });
    }
    var homeTick = false;
    window.addEventListener("scroll", function () {
      if (homeTick) return;
      homeTick = true;
      setTimeout(function () { homeTick = false; save("sessionStorage", "mm-home-y", Math.round(window.scrollY)); }, 250);
    }, { passive: true });
  }

  // Offline status on the home page
  var status = document.getElementById("offline");
  if (status && "caches" in window && "serviceWorker" in navigator) {
    var check = function () {
      caches.keys().then(function (keys) {
        var k = keys.filter(function (x) { return x.indexOf("mm-") === 0; }).pop();
        if (!k) { status.hidden = false; status.className = "offline"; status.textContent = "Saving for offline reading…"; return; }
        return caches.open(k).then(function (c) { return c.keys(); }).then(function (reqs) {
          var n = reqs.filter(function (r) { return r.url.indexOf("/m/") !== -1; }).length;
          status.hidden = false;
          if (n >= total) { status.className = "offline ok"; status.textContent = "All " + total + " saved for offline reading"; }
          else { status.className = "offline"; status.textContent = "Saving for offline reading… " + n + " of " + total; setTimeout(check, 1500); }
        });
      }).catch(function () {});
    };
    navigator.serviceWorker.ready.then(check);
    setTimeout(check, 2500);
  }

  // Search filter. Enter opens the first match.
  var q = document.getElementById("q");
  if (q) {
    q.addEventListener("input", function () {
      var v = q.value.trim().toLowerCase();
      var shown = 0;
      document.querySelectorAll(".group").forEach(function (g) {
        var any = 0;
        g.querySelectorAll("li[data-search]").forEach(function (li) {
          var hit = !v || li.getAttribute("data-search").indexOf(v) !== -1;
          li.hidden = !hit;
          if (hit) any++;
        });
        g.hidden = !any;
        shown += any;
      });
      document.getElementById("empty").hidden = shown > 0;
    });
    q.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" || !q.value.trim()) return;
      var first = document.querySelector("li[data-search]:not([hidden]) a");
      if (first) { e.preventDefault(); location.href = first.getAttribute("href"); }
    });
  }

  // ---------- Card deck ----------
  var dataEl = document.getElementById("cards-data");
  if (dataEl) {
    var cards = [];
    try { cards = JSON.parse(dataEl.textContent); } catch (e) {}
    var flash = document.getElementById("flash");
    var fq = document.getElementById("fq"), fa = document.getElementById("fa");
    var reveal = document.getElementById("reveal"), next = document.getElementById("next");
    var progress = document.getElementById("progress");
    var order = [], i = 0;
    var persist = function () { save("localStorage", "mm-deck", { n: cards.length, order: order, i: i }); };
    var shuffle = function () {
      order = cards.map(function (_, k) { return k; });
      for (var j = order.length - 1; j > 0; j--) {
        var r = Math.floor(Math.random() * (j + 1)); var t = order[j]; order[j] = order[r]; order[r] = t;
      }
      i = 0; show();
    };
    var show = function () {
      if (!cards.length) { fq.textContent = "No cards yet."; reveal.hidden = true; return; }
      var c = cards[order[i]];
      fq.textContent = c.q;
      fa.textContent = c.a;
      if (isSlug(c.s)) {
        var src = document.createElement("a");
        src.className = "src"; src.href = "m/" + c.s + ".html"; src.textContent = "Read: " + c.m + " ›";
        fa.appendChild(src);
      }
      fa.hidden = true; flash.classList.remove("revealed");
      reveal.hidden = false; next.hidden = true;
      progress.textContent = (i + 1) + " / " + cards.length;
      persist();
    };
    var doReveal = function () {
      if (!fa.hidden) return;
      fa.hidden = false; flash.classList.add("revealed");
      reveal.hidden = true; next.hidden = false;
      try { next.focus({ preventScroll: true }); } catch (e) { next.focus(); }
    };
    reveal.addEventListener("click", doReveal);
    flash.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest("a")) return;
      doReveal();
    });
    next.addEventListener("click", function () {
      i += 1;
      if (i >= cards.length) { shuffle(); } else { show(); }
      window.scrollTo(0, 0);
      reveal.focus({ preventScroll: true });
    });
    document.getElementById("shuffle").addEventListener("click", shuffle);

    // Resume where the last session stopped, if the deck has not changed since.
    var saved = load("localStorage", "mm-deck", null);
    var valid = saved && saved.n === cards.length && Array.isArray(saved.order) &&
      saved.order.length === cards.length && typeof saved.i === "number" &&
      saved.i >= 0 && saved.i < cards.length &&
      saved.order.every(function (x) { return typeof x === "number" && x >= 0 && x < cards.length; });
    if (valid) { order = saved.order; i = saved.i; show(); } else { shuffle(); }
  }
})();
