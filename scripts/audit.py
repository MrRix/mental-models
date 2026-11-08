#!/usr/bin/env python3
"""Audit the library. Exit 1 on any error (blocks commit and deploy).

Usage:
  python3 scripts/audit.py            # full audit
  python3 scripts/audit.py --backlog  # unresolved [[links]], most-referenced first
"""
import re
import sys
from collections import Counter

sys.path.insert(0, __import__("os").path.dirname(__file__))
from mmlib import (DOMAINS, MDLINK, REQUIRED_KEYS, SECTIONS, TYPES, INDEX, ROOT,
                   link_targets, load_models, parse_cards, parse_index, word_count)

EM_DASH = "\u2014"
EN_DASH = "\u2013"


def names_and_aliases(models):
    known = {}
    for name, m in models.items():
        known[name.lower()] = name
        for a in m["fm"].get("aliases", []) or []:
            known.setdefault(a.lower(), name)
    return known


def backlog(models):
    known = names_and_aliases(models)
    counts = Counter()
    for m in models.values():
        for t in link_targets(m["text"]):
            if t.lower() not in known:
                counts[t] += 1
    return counts


def audit():
    models = load_models()
    errors, warnings = [], []
    if not models:
        errors.append("no articles in /Models")

    alias_owner = {}
    for name, m in models.items():
        e = lambda msg: errors.append(f"{name}: {msg}")
        w = lambda msg: warnings.append(f"{name}: {msg}")
        fm = m["fm"]
        if m["fm_error"]:
            e(m["fm_error"])
        for k in REQUIRED_KEYS:
            if k not in fm:
                e(f"frontmatter missing '{k}'")
        if fm.get("type") and fm["type"] not in TYPES:
            e(f"type '{fm['type']}' not in {sorted(TYPES)}")
        if fm.get("domain") and fm["domain"] not in DOMAINS:
            e(f"domain '{fm['domain']}' not in {DOMAINS}")
        oy = str(fm.get("origin_year", ""))
        if oy and not (oy == "disputed" or re.fullmatch(r"(c\. )?\d{1,4}( BC)?", oy)):
            e(f"origin_year '{oy}' must be a year (e.g. 1931, c. 1320, c. 350 BC) or 'disputed'")
        if "aliases" in fm and not isinstance(fm["aliases"], list):
            e("aliases must be a [list]")
        for a in fm.get("aliases", []) or []:
            key = a.lower()
            if key in (n.lower() for n in models) and key != name.lower():
                e(f"alias '{a}' duplicates article '{a}'")
            if key in alias_owner and alias_owner[key] != name:
                e(f"alias '{a}' also used by {alias_owner[key]}")
            alias_owner[key] = name

        heads = [h for h, _ in m["sections"]]
        if heads != SECTIONS:
            missing = [s for s in SECTIONS if s not in heads]
            extra = [h for h in heads if h not in SECTIONS]
            if missing:
                e(f"missing sections: {missing}")
            if extra:
                e(f"unexpected sections: {extra}")
            if not missing and not extra:
                e("sections out of order")
        if m["pre"]:
            w("text before first section (ignored on site)")
        sec = dict(m["sections"])
        for h in SECTIONS:
            if h in sec and not sec[h].strip():
                e(f"section '{h}' is empty")

        if EM_DASH in m["text"]:
            e(f"{m['text'].count(EM_DASH)} em dash(es)")
        if re.search(r"\s" + EN_DASH + r"\s", m["text"]):
            e("en dash used as a dash")

        if "Recall" in sec:
            tag, cards, raw = parse_cards(sec["Recall"])
            if tag != "#flashcards":
                e("Recall must start with #flashcards")
            if len(cards) != 3 or len(raw) != 3:
                e(f"Recall needs exactly 3 'Q::A' cards (found {len(cards)} of {len(raw)} lines)")
        if "Go deeper" in sec:
            links = MDLINK.findall(sec["Go deeper"])
            if not 1 <= len(links) <= 3:
                e(f"Go deeper needs 1 to 3 http(s) links (found {len(links)})")
        if "Trigger question" in sec and "?" not in sec["Trigger question"]:
            w("Trigger question has no question mark")

        wc = word_count(m["sections"])
        if not 300 <= wc <= 400:
            (e if not 270 <= wc <= 440 else w)(f"{wc} words (target 300 to 400)")

    # Index checks
    groups, idx_errors = parse_index()
    errors += [f"Index: {x}" for x in idx_errors]
    listed = Counter(n for _, items in groups for n, _ in items)
    for n, c in listed.items():
        if n not in models:
            errors.append(f"Index: [[{n}]] has no file in /Models")
        if c > 1:
            errors.append(f"Index: [[{n}]] listed {c} times")
    for n in models:
        if n not in listed:
            errors.append(f"Index: {n} is missing from the Index")
    for heading, items in groups:
        for n, desc in items:
            if not desc:
                errors.append(f"Index: [[{n}]] has no description")
            dom = models.get(n, {}).get("fm", {}).get("domain")
            if dom and heading.lower() != dom:
                errors.append(f"Index: [[{n}]] is under '{heading}' but its domain is '{dom}'")
    if INDEX.exists() and EM_DASH in INDEX.read_text(encoding="utf-8"):
        errors.append("Index: contains em dash")
    for extra in ("CLAUDE.md", "README.md"):
        p = ROOT / extra
        if p.exists() and EM_DASH in p.read_text(encoding="utf-8"):
            errors.append(f"{extra}: contains em dash")

    return models, errors, warnings


def main():
    if "--backlog" in sys.argv:
        b = backlog(load_models())
        if not b:
            print("Backlog empty: every [[link]] resolves.")
        for name, c in b.most_common():
            print(f"{c:3d}  {name}")
        return 0
    models, errors, warnings = audit()
    print(f"Audited {len(models)} articles: {len(errors)} error(s), {len(warnings)} warning(s)")
    for x in errors:
        print(f"  ERROR  {x}")
    for x in warnings:
        print(f"  warn   {x}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
