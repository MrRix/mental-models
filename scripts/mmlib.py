"""Shared parsing for the mental models library. Standard library only."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "Models"
INDEX = ROOT / "Models Index.md"

SECTIONS = [
    "What it is",
    "Origin",
    "Why it works",
    "Best used when",
    "Limitations",
    "Avoid when",
    "Counter-models and tensions",
    "Who used it",
    "Trigger question",
    "Often confused with",
    "Go deeper",
    "Recall",
]
TYPES = {"model", "heuristic", "bias"}
DOMAINS = ["decisions", "systems", "psychology", "economics", "other"]
REQUIRED_KEYS = ["type", "domain", "origin_year", "status", "aliases"]

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
# URLs may contain balanced parentheses (DOIs, Wikipedia), e.g. .../Margin_of_safety_(financial)
URL = r"https?://(?:[^()\s]|\([^()\s]*\))+"
MDLINK = re.compile(r"\[([^\]]+)\]\((" + URL + r")\)")


def slugify(name: str) -> str:
    s = name.lower().replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def parse_frontmatter(text: str):
    """Return (dict, body, error). Supports the simple key: value format we use."""
    if not text.startswith("---\n"):
        return {}, text, "missing frontmatter"
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text, "unterminated frontmatter"
    fm = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            return fm, text[end + 5:], f"bad frontmatter line: {line!r}"
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            import csv
            v = [x.strip().strip('"').strip("'") for x in next(csv.reader([inner], skipinitialspace=True))
                 if x.strip()] if inner else []
        else:
            v = v.strip('"')
        fm[k.strip()] = v
    return fm, text[end + 5:], None


def split_sections(body: str):
    """Return list of (heading, content) for '## ' headings, plus any preamble."""
    sections = []
    pre = []
    cur = None
    buf = []
    for line in body.splitlines():
        m = re.match(r"^## (.+?)\s*$", line)
        if m:
            if cur is not None:
                sections.append((cur, "\n".join(buf).strip("\n")))
            cur, buf = m.group(1), []
        elif cur is None:
            pre.append(line)
        else:
            buf.append(line)
    if cur is not None:
        sections.append((cur, "\n".join(buf).strip("\n")))
    return "\n".join(pre).strip(), sections


def parse_cards(recall: str):
    lines = [l.strip() for l in recall.splitlines() if l.strip()]
    tag = lines[0] if lines else ""
    cards = []
    for l in lines[1:]:
        if "::" in l:
            q, a = l.split("::", 1)
            cards.append((q.strip(), a.strip()))
    return tag, cards, lines[1:]


def word_count(sections):
    text = " ".join(c for h, c in sections if h != "Recall")
    text = WIKILINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = MDLINK.sub(lambda m: m.group(1), text)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.%-]*", text))


def load_models():
    models = {}
    for p in sorted(MODELS.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, body, err = parse_frontmatter(text)
        pre, sections = split_sections(body)
        models[p.stem] = {
            "name": p.stem,
            "path": p,
            "text": text,
            "fm": fm,
            "fm_error": err,
            "pre": pre,
            "sections": sections,
            "slug": slugify(p.stem),
        }
    return models


def parse_index():
    """Return (groups, error_lines). groups: list of (heading, [(name, desc)])."""
    if not INDEX.exists():
        return [], ["Models Index.md missing"]
    groups, errors = [], []
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            groups.append((line[3:].strip(), []))
        elif line.startswith("- "):
            m = re.match(r"^- \[\[([^\]|]+)\]\]:?\s*(.*)$", line)
            if not m or not groups:
                errors.append(f"unparseable index line: {line!r}")
                continue
            groups[-1][1].append((m.group(1).strip(), m.group(2).strip()))
    return groups, errors


def link_targets(text: str):
    return [m.group(1).strip() for m in WIKILINK.finditer(text)]
