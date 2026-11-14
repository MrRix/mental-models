/* Issue finder: match a described situation to curated situations and models.
   Offline, no dependencies. Ranking: BM25F-style field-weighted scoring over two
   collections (curated situations, models), light stemming, phrase boosts for curated
   keywords, prefix matching on the last typed word, and typo tolerance on longer words.
   Curated situations rank first ("best bets"); their models inherit relevance.
   All rendering uses DOM methods with textContent (no innerHTML). */
(function () {
  "use strict";
  var dataEl = document.getElementById("guide-data");
  var input = document.getElementById("gq");
  var out = document.getElementById("gresults");
  if (!dataEl || !input || !out) return;
  var data;
  try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var root = document.body.getAttribute("data-root") || "";

  // ---------- text processing ----------
  var STOP = new Set(("a an and are as at be been being but by can could did do does doing for from had has have " +
    "having he her hers him his how i id ill im is it its ive just me my myself of on or our ours she so some " +
    "than that the their them then there these they this those to too up us very was we were what when where " +
    "which while who whom why will with would you your yours yourself about again all am any because before " +
    "into more most no nor not now only other out over own same should such also really thing things " +
    "something someone somebody anything everything get gets got getting go goes going gone keep keeps kept " +
    "feel feels felt like lot lots kind sort way much many even still ever dont doesnt didnt cant wont isnt " +
    "arent wasnt werent help need want wants wanted think thinking know").split(" "));

  function norm(s) {
    return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/['’]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }
  function stem(w) {
    if (w.length > 5 && /ing$/.test(w)) w = w.slice(0, -3);
    else if (w.length > 4 && /ed$/.test(w)) w = w.slice(0, -2);
    else if (w.length > 4 && /ies$/.test(w)) w = w.slice(0, -3) + "y";
    else if (w.length > 4 && /(ch|sh|x|ss)es$/.test(w)) w = w.slice(0, -2);
    else if (w.length > 3 && /s$/.test(w) && !/(ss|us|is)$/.test(w)) w = w.slice(0, -1);
    if (w.length > 4 && /ly$/.test(w)) w = w.slice(0, -2);
    if (/([b-df-hj-np-tv-z])\1$/.test(w) && !/(ll|ss|zz|ff)$/.test(w)) w = w.slice(0, -1);
    if (w.length > 4 && /e$/.test(w)) w = w.slice(0, -1);
    return w;
  }
  function terms(s) {
    var t = norm(s).split(" "), r = [];
    for (var i = 0; i < t.length; i++) if (t[i] && !STOP.has(t[i])) r.push(stem(t[i]));
    return r;
  }

  // Everyday synonyms and feelings mapped to the words situations are indexed under.
  // Weighted below exact matches; fixes the cold start when someone types a feeling.
  var SYN_RAW = {
    boss: "manager", manager: "boss", coworker: "colleague", colleague: "coworker", team: "colleague",
    job: "career", career: "job", quit: "stop leave abandon", leave: "quit", stop: "quit",
    late: "delay deadline", delay: "late deadline", deadline: "late", slow: "late delay",
    money: "invest spend cost", cash: "money", invest: "money stock", stock: "invest market", price: "cost",
    buy: "spend purchase", purchase: "buy", expensive: "cost", cheap: "cost",
    news: "media headline", media: "news", headline: "news", viral: "news",
    rule: "policy process", policy: "rule", process: "rule", tradition: "rule",
    metric: "kpi target measure", kpi: "metric target", target: "metric goal", goal: "target",
    hire: "staff people", staff: "hire", estimate: "forecast predict", forecast: "estimate predict",
    predict: "forecast", guess: "estimate", lucky: "luck", luck: "lucky chance",
    stressed: "overwhelm pressure deadline", stress: "overwhelm pressure", overwhelmed: "overwhelm pressure",
    anxious: "worry risk uncertain", worried: "worry risk", nervous: "worry risk", scared: "risk fear loss",
    afraid: "risk fear loss", angry: "upset unfair rude", furious: "upset unfair", annoyed: "upset rude",
    frustrated: "stuck upset", stuck: "quit stall", regret: "mistake hindsight", ashamed: "mistake",
    burned: "overwhelm", burnt: "overwhelm", tired: "overwhelm", confused: "unclear complex",
    unsure: "uncertain", uncertain: "risk unsure", sure: "certain confident", confident: "certain sure",
    betrayed: "upset unfair", break: "broke broken", broke: "break broken", broken: "break", credit: "recognition", recognition: "credit", jealous: "success compare", envious: "success compare"
  };
  var SYN = Object.create(null);
  Object.keys(SYN_RAW).forEach(function (k) {
    SYN[stem(norm(k))] = SYN_RAW[k].split(" ").map(function (w) { return stem(w); });
  });

  // ---------- indexing ----------
  // Each doc: {fields: [[weight, [terms]]], phrases: [normalized multi-word keywords]}
  function makeCollection(docs) {
    var df = Object.create(null), totalLen = 0;
    docs.forEach(function (d) {
      var tf = Object.create(null), len = 0;
      d.fields.forEach(function (f) {
        f[1].forEach(function (t) { tf[t] = (tf[t] || 0) + f[0]; len += f[0]; });
      });
      d.tf = tf; d.len = len; totalLen += len;
      Object.keys(tf).forEach(function (t) { df[t] = (df[t] || 0) + 1; });
    });
    return { docs: docs, df: df, N: docs.length, avg: totalLen / Math.max(1, docs.length), vocab: Object.keys(df) };
  }

  var modelsBySlug = Object.create(null);
  var mdocs = data.models.map(function (m) {
    modelsBySlug[m.s] = m;
    var f = m.f || {};
    return {
      ref: m,
      fields: [[3, terms(m.n + " " + (m.a || []).join(" "))], [2, terms(m.d)], [1.5, terms(f.trigger || "")],
               [1.5, terms(f.best || "")], [1, terms(f.what || "")], [0.6, terms(f.why || "")],
               [0.4, terms(f.confused || "")]],
      phrases: []
    };
  });
  var sdocs = data.situations.map(function (s) {
    var reasons = s.m.map(function (p) { return p[1]; }).join(" ");
    var names = s.m.map(function (p) { return (modelsBySlug[p[0]] || {}).n || ""; }).join(" ");
    return {
      ref: s,
      fields: [[3, terms(s.t)], [5, terms((s.k || []).join(" "))], [1, terms(reasons)], [0.8, terms(names)],
               [0.4, terms(s.c)]],
      phrases: (s.k || []).map(norm).filter(function (p) { return p.indexOf(" ") > 0; })
    };
  });
  var MC = makeCollection(mdocs), SC = makeCollection(sdocs);

  // ---------- query expansion ----------
  function editDistance(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var pp = [], prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      var rowMin = i;
      for (j = 1; j <= b.length; j++) {
        var c = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], pp[j - 2] + 1);
        if (cur[j] < rowMin) rowMin = cur[j];
      }
      if (rowMin > max) return max + 1;
      pp = prev; prev = cur;
    }
    return prev[b.length];
  }
  // Variants of one query term within a collection: exact, prefix (last word), typo.
  function expand(t, col, isLast) {
    var vars = [];
    if (col.df[t]) vars.push({ t: t, w: 1 });
    (SYN[t] || []).forEach(function (s) { if (col.df[s]) vars.push({ t: s, w: 0.6 }); });
    if (isLast && t.length >= 3) {
      col.vocab.forEach(function (v) { if (v !== t && v.indexOf(t) === 0) vars.push({ t: v, w: 0.4 }); });
    }
    if (!vars.length && t.length >= 4) {
      var max = t.length >= 8 ? 2 : 1;
      col.vocab.forEach(function (v) {
        if (v.length >= 4 && v[0] === t[0] && editDistance(t, v, max) <= max) vars.push({ t: v, w: 0.45 });
      });
    }
    return vars;
  }

  // ---------- scoring ----------
  var K1 = 1.2, B = 0.7;
  function score(col, qterms, qnorm, lastPartial) {
    var results = [];
    var expanded = qterms.map(function (t, i) { return expand(t, col, lastPartial && i === qterms.length - 1); });
    col.docs.forEach(function (d) {
      var s = 0, matched = 0, hits = [];
      expanded.forEach(function (vars) {
        var best = 0, bestTerm = null;
        vars.forEach(function (v) {
          var tf = d.tf[v.t];
          if (!tf) return;
          var idf = Math.log(1 + (col.N - col.df[v.t] + 0.5) / (col.df[v.t] + 0.5));
          var sc = v.w * idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * d.len / col.avg));
          if (sc > best) { best = sc; bestTerm = v.t; }
        });
        if (best > 0) { s += best; matched++; hits.push(bestTerm); }
      });
      d.phrases.forEach(function (p) { if (qnorm.indexOf(" " + p + " ") !== -1) { s += 3; matched += 0.5; } });
      if (s > 0) {
        var coverage = Math.min(1, matched / Math.max(1, qterms.length));
        results.push({ doc: d, score: s * (0.4 + 0.6 * coverage), hits: hits, coverage: coverage });
      }
    });
    results.sort(function (a, b) { return b.score - a.score; });
    return results;
  }

  function search(q) {
    if (norm(q).replace(/ /g, "").length < 2) return null;
    var qt = terms(q);
    if (!qt.length) return null;
    var qnorm = " " + norm(q) + " ";
    var lastPartial = !/\s$/.test(q);
    var sres = score(SC, qt, qnorm, lastPartial);
    var mres = score(MC, qt, qnorm, lastPartial);
    var topS = sres.length ? sres[0].score : 0;
    var sits = sres.filter(function (r) { return r.score >= topS * 0.45; }).slice(0, 3);

    // Models: direct relevance plus relevance inherited from matched situations.
    var topM = mres.length ? mres[0].score : 0;
    var agg = Object.create(null);
    // Direct hits must match at least half the query, or one word of a one-word query,
    // so a single shared word ("push", "keep") can't drag in an unrelated model.
    mres.forEach(function (r) {
      if (qt.length > 1 && r.coverage < 0.5) return;
      agg[r.doc.ref.s] = { m: r.doc.ref, score: topM ? 0.5 * r.score / topM : 0, via: null };
    });
    var POS = [1, 0.85, 0.7, 0.6, 0.5];
    sres.slice(0, 5).forEach(function (r) {
      var ns = topS ? r.score / topS : 0;
      if (ns < 0.45) return;
      r.doc.ref.m.forEach(function (p, i) {
        var a = agg[p[0]] || (agg[p[0]] = { m: modelsBySlug[p[0]], score: 0, via: null });
        if (!a.m) return;
        a.score += 0.8 * ns * (POS[i] || 0.5);
        if (!a.via && ns >= 0.45) a.via = { sit: r.doc.ref, reason: p[1] };
      });
    });
    var models = Object.keys(agg).map(function (k) { return agg[k]; }).filter(function (a) { return a.m; });
    models.sort(function (a, b) { return b.score - a.score; });
    var topA = models.length ? models[0].score : 0;
    models = models.filter(function (a) { return a.score >= topA * 0.3; }).slice(0, 8);
    return { sits: sits, models: models, qt: qt };
  }

  // ---------- rendering (DOM only) ----------
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  // Append text with words matching the query wrapped in <mark>.
  function highlighted(parent, text, qt) {
    var re = /[A-Za-z0-9'’]+|[^A-Za-z0-9'’]+/g, m, set = new Set(qt);
    while ((m = re.exec(text))) {
      var w = m[0];
      if (/^[A-Za-z0-9]/.test(w) && set.has(stem(norm(w)))) parent.appendChild(el("mark", null, w));
      else parent.appendChild(document.createTextNode(w));
    }
  }
  function bestSentence(m, qt) {
    var f = m.f || {}, best = "", bestN = 0;
    [f.trigger, f.best, f.what, f.why].forEach(function (txt) {
      String(txt || "").split(/(?<=[.?!])\s+/).forEach(function (sen) {
        var ts = terms(sen), n = 0;
        qt.forEach(function (q) { if (ts.indexOf(q) !== -1) n++; });
        if (n > bestN) { bestN = n; best = sen; }
      });
    });
    return best || m.d;
  }

  function render(res, q) {
    while (out.firstChild) out.removeChild(out.firstChild);
    if (!res) { out.hidden = true; return; }
    out.hidden = false;
    var status = el("p", "gstatus");
    status.setAttribute("role", "status");
    out.appendChild(status);
    if (!res.sits.length && !res.models.length) {
      status.textContent = "Nothing matched “" + q.trim() + "”. Try other words, or pick a situation below.";
      return;
    }
    var parts = [];
    if (res.sits.length) parts.push(res.sits.length + (res.sits.length === 1 ? " situation" : " situations"));
    if (res.models.length) parts.push(res.models.length + (res.models.length === 1 ? " model" : " models"));
    status.textContent = parts.join(" and ") + " match.";

    if (res.sits.length) {
      var sec = el("section", "gsits");
      sec.appendChild(el("h2", null, "Situations like this"));
      res.sits.forEach(function (r) {
        var s = r.doc.ref, card = el("div", "gsit");
        var h = el("h3"); highlighted(h, s.t, res.qt); card.appendChild(h);
        card.appendChild(el("p", "gcat", s.c));
        var ul = el("ul", "picks");
        s.m.forEach(function (p) {
          var m = modelsBySlug[p[0]]; if (!m) return;
          var li = el("li"), a = el("a");
          a.href = root + "m/" + m.s + ".html";
          a.appendChild(el("span", "name", m.n));
          var why = el("span", "why"); highlighted(why, p[1], res.qt); a.appendChild(why);
          li.appendChild(a); ul.appendChild(li);
        });
        card.appendChild(ul);
        sec.appendChild(card);
      });
      out.appendChild(sec);
    }
    if (res.models.length) {
      var ms = el("section", "gmodels");
      ms.appendChild(el("h2", null, "Models that fit"));
      var list = el("ul", "list");
      res.models.forEach(function (a) {
        var li = el("li"), link = el("a");
        link.href = root + "m/" + a.m.s + ".html";
        link.appendChild(el("span", "name", a.m.n));
        if (a.m.t) link.appendChild(el("span", "type", a.m.t));
        var d = el("span", "desc");
        if (a.via) {
          d.appendChild(el("span", "via", a.via.sit.t + ": "));
          highlighted(d, a.via.reason, res.qt);
        } else {
          highlighted(d, bestSentence(a.m, res.qt), res.qt);
        }
        link.appendChild(d);
        li.appendChild(link);
        list.appendChild(li);
      });
      ms.appendChild(list);
      out.appendChild(ms);
    }
  }

  // ---------- wiring ----------
  // State lives in the URL hash (#q=...), which stays on the device: personal queries
  // never reach the server, even on reload.
  var live = el("p", "sr");
  live.setAttribute("role", "status");
  live.setAttribute("aria-atomic", "true");
  out.parentNode.insertBefore(live, out);
  var timer = null, liveTimer = null;
  function run() {
    var q = input.value;
    var res = q.trim() ? search(q) : null;
    render(res, q);
    clearTimeout(liveTimer);
    liveTimer = setTimeout(function () {
      var s = out.querySelector(".gstatus");
      live.textContent = s ? s.textContent : "";
    }, 500);
    try {
      var h = q.trim() ? "#q=" + encodeURIComponent(q.trim()) : "";
      history.replaceState(null, "", location.pathname + h);
    } catch (e) {}
  }
  input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 150); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); clearTimeout(timer); run(); input.blur(); }
  });
  document.querySelectorAll("[data-example]").forEach(function (b) {
    b.addEventListener("click", function () { input.value = b.getAttribute("data-example"); run(); });
  });

  // Deep links: #q=... restores a search; #s-id opens a situation in the menu.
  function fromHash() {
    var h = location.hash || "";
    if (h.indexOf("#q=") === 0) {
      try { input.value = decodeURIComponent(h.slice(3)); } catch (e) { input.value = ""; }
      run();
      return;
    }
    var id = h.slice(1);
    if (!/^s-[a-z0-9-]+$/.test(id)) return;
    var d = document.getElementById(id);
    if (d && d.tagName === "DETAILS") { d.open = true; d.scrollIntoView({ block: "start" }); }
  }
  fromHash();
  window.addEventListener("hashchange", fromHash);

  // Expose the matcher for automated relevance tests (read-only).
  window.__mmGuideSearch = function (q) {
    var r = search(q);
    return r ? { sits: r.sits.map(function (x) { return x.doc.ref.t; }),
                 models: r.models.map(function (x) { return x.m.n; }) } : null;
  };
})();
