#!/usr/bin/env python3
"""Build the static site from /Models and Models Index.md into /_site.

Standard library only. Output is fully static, offline-capable (service worker
precaches every page), and uses a strict Content-Security-Policy: no inline
scripts, no third-party requests.
"""
import hashlib
import html
import json
import re
import shutil
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from urllib.parse import urlsplit  # noqa: E402
from mmlib import DOMAINS, ROOT, URL, load_models, parse_cards, parse_index, word_count  # noqa: E402

OUT = ROOT / "_site"
STATIC = ROOT / "site"
TITLE = "Mental Models"
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; "
       "form-action 'none'; object-src 'none'")

TOKEN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]"
                   r"|\[([^\]]+)\]\((" + URL + r")\)")
TYPE_LABEL = {"model": "Model", "heuristic": "Heuristic", "bias": "Bias"}


def esc(s):
    return html.escape(s, quote=False)


def attr(s):
    return html.escape(s, quote=True)


def emph(t):
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", t)
    return t


class Renderer:
    def __init__(self, models):
        self.known = {}
        for name, m in models.items():
            self.known[name.lower()] = m
        for name, m in models.items():
            for a in m["fm"].get("aliases", []) or []:
                self.known.setdefault(a.lower(), m)

    def resolve(self, target):
        return self.known.get(target.strip().lower())

    def inline(self, raw, root):
        out, pos = [], 0
        for m in TOKEN.finditer(raw):
            out.append(emph(esc(raw[pos:m.start()])))
            if m.group(1):
                target = m.group(1).strip()
                label = emph(esc((m.group(2) or target).strip()))
                hit = self.resolve(target)
                if hit:
                    out.append(f'<a class="wl" href="{root}m/{hit["slug"]}.html">{label}</a>')
                else:
                    out.append(f'<span class="wl-missing" title="Not written yet">{label}</span>')
            else:
                label, url = emph(esc(m.group(3))), m.group(4)
                host = (urlsplit(url).hostname or "").removeprefix("www.")
                host_html = f'<span class="host">{esc(host)}</span>' if host else ""
                out.append(f'<a class="ext" href="{attr(url)}" target="_blank" '
                           f'rel="noopener noreferrer">{label}{host_html}</a>')
            pos = m.end()
        out.append(emph(esc(raw[pos:])))
        return "".join(out)

    def blocks(self, text, root):
        html_out = []
        for block in re.split(r"\n\s*\n", text.strip()):
            lines = [l.rstrip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue
            if all(re.match(r"^\s*([-*]|\d+\.)\s+", l) or not re.match(r"^\S", l) for l in lines) \
                    and re.match(r"^\s*([-*]|\d+\.)\s+", lines[0]):
                ordered = bool(re.match(r"^\s*\d+\.", lines[0]))
                items = []
                for l in lines:
                    mm = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.*)$", l)
                    if mm:
                        items.append(mm.group(1))
                    elif items:
                        items[-1] += " " + l.strip()
                tag = "ol" if ordered else "ul"
                lis = "".join(f"<li>{self.inline(i, root)}</li>" for i in items)
                html_out.append(f"<{tag}>{lis}</{tag}>")
            elif all(l.startswith(">") for l in lines):
                body = " ".join(l.lstrip("> ").strip() for l in lines)
                html_out.append(f"<blockquote>{self.inline(body, root)}</blockquote>")
            else:
                html_out.append(f"<p>{self.inline(' '.join(l.strip() for l in lines), root)}</p>")
        return "\n".join(html_out)


def page(title, body, root, desc="", body_attrs=""):
    t = esc(title) if title == TITLE else f"{esc(title)} · {TITLE}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex">
<meta name="description" content="{attr(desc)}">
<meta name="theme-color" content="#F7F6F2" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14161C" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Models">
<link rel="manifest" href="{root}manifest.webmanifest">
<link rel="icon" href="{root}icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="{root}icon-180.png">
<link rel="stylesheet" href="{root}style.css">
<title>{t}</title>
</head>
<body data-root="{root}"{body_attrs}>
{body}
<script src="{root}app.js" defer></script>
</body>
</html>
"""


def plain_text(text):
    """Strip [[links]], [label](url) and emphasis markers, leaving readable text."""
    t = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
    t = re.sub(r"\[([^\]]+)\]\((" + URL + r")\)", r"\1", t)
    return re.sub(r"[*_]", "", t).strip()


def first_sentence(text, limit=160):
    plain = plain_text(text)
    # a sentence may end inside closing quotes or brackets: ...later." Next
    m = re.match(r"(.+?[.!?][\"'”’)]*)(\s|$)", plain)
    s = m.group(1) if m else plain
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s


def build():
    models = load_models()
    if not models:
        sys.exit("No articles in /Models")
    r = Renderer(models)
    groups, _ = parse_index()
    desc = {n: d for _, items in groups for n, d in items}
    for n, m in models.items():
        sec = dict(m["sections"])
        desc.setdefault(n, first_sentence(sec.get("What it is", "")))
    if not groups:
        groups = []
        for d in DOMAINS:
            items = [(n, desc[n]) for n, m in models.items() if m["fm"].get("domain") == d]
            if items:
                groups.append((d.title(), items))

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "m").mkdir(parents=True)

    # backlinks
    backlinks = {n: set() for n in models}
    for n, m in models.items():
        for t in TOKEN.finditer(m["text"]):
            if t.group(1):
                hit = r.resolve(t.group(1))
                if hit and hit["name"] != n:
                    backlinks[hit["name"]].add(n)

    slugs = sorted(m["slug"] for m in models.values())
    data_attr = f' data-slugs="{attr(json.dumps(slugs))}" data-total="{len(models)}"'
    all_cards = []
    files = {}

    # article pages
    for n, m in sorted(models.items()):
        fm, sec = m["fm"], dict(m["sections"])
        root = "../"
        chips = [TYPE_LABEL.get(fm.get("type", ""), fm.get("type", "")),
                 str(fm.get("domain", "")).title()]
        oy = str(fm.get("origin_year", ""))
        if oy == "disputed":
            chips.append("Origin disputed")
        elif oy:
            y = int(oy) if re.fullmatch(r"-?\d+", oy) else None
            chips.append(f"{-y} BC" if y is not None and y < 0 else oy)
        minutes = max(1, round(word_count(m["sections"]) / 230))
        chip_html = "".join(f'<span class="chip">{esc(c)}</span>' for c in chips if c)
        chip_html += f'<span class="chip quiet">{minutes} min read</span>'
        aliases = fm.get("aliases") or []
        alias_html = (f'<p class="aka">Also called {esc(", ".join(aliases))}</p>' if aliases else "")

        parts = []
        for h, content in m["sections"]:
            sid = re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")
            if h == "Recall":
                _, cards, _ = parse_cards(content)
                cs = []
                for q, a in cards:
                    all_cards.append({"q": q, "a": a, "m": n, "s": m["slug"]})
                    cs.append(f'<details class="card"><summary>{r.inline(q, root)}</summary>'
                              f'<div class="answer">{r.inline(a, root)}</div></details>')
                parts.append(f'<section id="{sid}" class="recall"><h2>Recall</h2>'
                             f'<p class="hint">Tap a scenario to reveal the answer.</p>{"".join(cs)}</section>')
            elif h == "Trigger question":
                parts.append(f'<section id="{sid}" class="trigger"><h2>{esc(h)}</h2>'
                             f'{r.blocks(content, root)}</section>')
            elif h == "What it is":
                parts.append(f'<section id="{sid}" class="lede"><h2 class="sr">What it is</h2>'
                             f'{r.blocks(content, root)}</section>')
            elif h == "Go deeper":
                parts.append(f'<section id="{sid}" class="deeper"><h2>{esc(h)}</h2>{r.blocks(content, root)}</section>')
            else:
                parts.append(f'<section id="{sid}"><h2>{esc(h)}</h2>{r.blocks(content, root)}</section>')

        bl = sorted(backlinks[n])
        bl_html = ""
        if bl:
            links = "".join(f'<li><a class="wl" href="{root}m/{models[b]["slug"]}.html">{esc(b)}</a></li>'
                            for b in bl)
            bl_html = f'<section class="backlinks"><h2>Linked from</h2><ul>{links}</ul></section>'

        # "Up next": models this article links to (in reading order), then those linking here.
        # The first is rendered statically; app.js may swap in the first one not yet read.
        related = []
        for t in TOKEN.finditer(m["text"]):
            hit = r.resolve(t.group(1)) if t.group(1) else None
            if hit and hit["name"] != n and hit["name"] not in related:
                related.append(hit["name"])
        related += [b for b in bl if b not in related]
        if not related:
            names = sorted(models)
            related = [names[(names.index(n) + 1) % len(names)]] if len(names) > 1 else []
        upnext_html = ""
        if related:
            first = related[0]
            rel_json = json.dumps([[models[x]["slug"], x, plain_text(desc.get(x, ""))] for x in related],
                                  ensure_ascii=False).replace("<", "\\u003c")
            upnext_html = (f'<a class="upnext" id="upnext" href="{root}m/{models[first]["slug"]}.html">'
                           f'<span class="label" id="upnext-label">Up next</span>'
                           f'<span class="name" id="upnext-name">{esc(first)}</span>'
                           f'<span class="desc" id="upnext-desc">{esc(plain_text(desc.get(first, "")))}</span></a>'
                           f'<script type="application/json" id="related-data">{rel_json}</script>')

        body = f"""<header class="bar">
  <a class="back" href="{root}index.html" aria-label="All models"><span aria-hidden="true">‹</span> All models</a>
  <button class="random" type="button" data-current="{m['slug']}">Random</button>
  <span class="readbar" id="readbar" aria-hidden="true"></span>
</header>
<main class="article" data-slug="{m['slug']}">
  <h1>{esc(n)}</h1>
  <div class="chips">{chip_html}</div>
  {alias_html}
  {''.join(parts)}
  {bl_html}
  <nav class="next" aria-label="Keep reading">
  {upnext_html}
  <button class="random big" type="button" data-current="{m['slug']}">Read another at random</button>
  </nav>
</main>"""
        files[f"m/{m['slug']}.html"] = page(n, body, root, desc.get(n, ""), data_attr)

    # index
    root = ""
    sections = []
    for heading, items in groups:
        lis = []
        for n, d in items:
            if n not in models:
                continue
            mm = models[n]
            tlabel = TYPE_LABEL.get(mm["fm"].get("type", ""), "")
            d_plain = plain_text(d)
            search = " ".join([n, d_plain, tlabel, " ".join(mm["fm"].get("aliases") or [])]).lower()
            # plain text: a description with [[links]] would otherwise nest <a> inside <a>
            lis.append(f'<li data-search="{attr(search)}" data-slug="{mm["slug"]}"><a href="m/{mm["slug"]}.html">'
                       f'<span class="name">{esc(n)}</span><span class="type">{esc(tlabel)}</span>'
                       f'<span class="desc">{esc(d_plain)}</span></a></li>')
        if lis:
            sections.append(f'<section class="group"><h2>{esc(heading)} <span class="count">{len(lis)}</span></h2>'
                            f'<ul class="list">{"".join(lis)}</ul></section>')
    body = f"""<header class="home">
  <h1>{TITLE}</h1>
  <p class="sub">{len(models)} models, heuristics and biases<span id="readcount"></span></p>
  <p class="offline" id="offline" role="status" hidden></p>
  <a class="resume" id="resume" href="index.html" hidden>
    <span class="label">Continue reading</span>
    <span class="name" id="resume-name"></span>
  </a>
  <div class="actions">
    <button class="random primary" type="button">Random model</button>
    <a class="button" href="cards.html">Review cards</a>
  </div>
  <label class="search"><span class="sr">Search models</span>
    <input id="q" type="search" placeholder="Search models" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="go">
  </label>
</header>
<main>
{''.join(sections)}
<p class="empty" id="empty" hidden>No matches.</p>
</main>"""
    files["index.html"] = page(TITLE, body, root, f"{len(models)} mental models", data_attr)

    # cards
    cards_json = json.dumps(all_cards, ensure_ascii=False).replace("<", "\\u003c")
    body = f"""<header class="bar">
  <a class="back" href="index.html"><span aria-hidden="true">‹</span> All models</a>
  <span class="progress" id="progress"></span>
</header>
<main class="deck">
  <h1 class="sr">Review cards</h1>
  <div class="flash" id="flash" aria-live="polite">
    <p class="label">Scenario</p>
    <p class="q" id="fq"></p>
    <div class="a" id="fa" hidden></div>
    <p class="tap" aria-hidden="true">Tap the card to reveal</p>
  </div>
  <button class="link" id="shuffle" type="button">Shuffle and start over</button>
  <div class="deck-actions">
    <button class="primary big" id="reveal" type="button">Show answer</button>
    <button class="primary big" id="next" type="button" hidden>Next card</button>
  </div>
</main>
<script type="application/json" id="cards-data">{cards_json}</script>"""
    files["cards.html"] = page("Review cards", body, "", "Recall cards", data_attr)

    files["404.html"] = page("Not found", '<main class="article"><h1>Not found</h1>'
                             '<p><a href="./index.html">Back to all models</a></p></main>', "", "", data_attr)

    manifest = {
        "name": TITLE, "short_name": "Models", "start_url": "./index.html", "scope": "./",
        "display": "standalone", "background_color": "#F7F6F2", "theme_color": "#F7F6F2",
        "icons": [{"src": f"icon-{s}.png", "sizes": f"{s}x{s}", "type": "image/png", "purpose": "any"}
                  for s in (192, 512)] + [{"src": "icon-512.png", "sizes": "512x512",
                                           "type": "image/png", "purpose": "maskable"}],
    }
    files["manifest.webmanifest"] = json.dumps(manifest, indent=2)

    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    for p in STATIC.iterdir():
        if p.is_file() and p.name != "sw.template.js":
            shutil.copy(p, OUT / p.name)
    for s in (180, 192, 512):
        (OUT / f"icon-{s}.png").write_bytes(icon_png(s))

    assets = ["./"] + sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*")
                             if p.is_file() and p.name != "404.html")
    h = hashlib.sha256()
    for a in assets[1:]:
        h.update(a.encode())
        h.update((OUT / a).read_bytes())
    version = "mm-" + h.hexdigest()[:12]
    sw = (STATIC / "sw.template.js").read_text(encoding="utf-8")
    sw = sw.replace("__VERSION__", version).replace("__ASSETS__", json.dumps(assets, indent=1))
    (OUT / "sw.js").write_text(sw, encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"Built {len(models)} articles, {len(all_cards)} cards, {len(assets)} cached assets -> _site ({version})")


def icon_png(size):
    """Indigo rounded-square icon with a white lens (ring + dot). Pure Python PNG."""
    ss = 3
    bg, fg = (61, 90, 254), (255, 255, 255)
    c = size / 2
    r_out, r_in, r_dot = size * 0.30, size * 0.215, size * 0.085
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            cov = 0
            for sy in range(ss):
                for sx in range(ss):
                    px, py = x + (sx + 0.5) / ss, y + (sy + 0.5) / ss
                    d = ((px - c) ** 2 + (py - c * 1.0) ** 2) ** 0.5
                    if r_in <= d <= r_out or d <= r_dot:
                        cov += 1
            a = cov / (ss * ss)
            row += bytes(int(bg[i] * (1 - a) + fg[i] * a) for i in range(3))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    build()
