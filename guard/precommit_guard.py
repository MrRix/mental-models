#!/usr/bin/env python3
"""Fail-closed guard for a PUBLIC repo.

Blocks a commit (or a CI deploy with --all) if any file:
  - is outside the path allowlist, or has a secret-looking filename
  - contains a token/key pattern, an email address, or a local user path
  - contains a personal identifier whose SHA-256 is listed in guard/private_hashes.txt
    (hashes only, so the identifiers themselves never appear in the repo)
Then runs scripts/audit.py; a failing audit also blocks.

Every run appends ALLOW/BLOCK to logs/guard.log (gitignored) as proof the guard ran.
Any unexpected error blocks (exit 1).
"""
import datetime
import fnmatch
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "guard.log"

ALLOWED_PATHS = [
    "CLAUDE.md", "README.md", "Models Index.md", ".gitignore",
    "Models/*.md",
    "scripts/*.py",
    "site/*.css", "site/*.js",
    "guard/*.py", "guard/private_hashes.txt",
    ".githooks/pre-commit",
    ".github/workflows/*.yml",
    ".claude/settings.json",
]
BLOCKED_NAMES = [".env*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "*.sqlite", "*.log"]

PATTERNS = {
    "GitHub token": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "AWS key": r"\bAKIA[0-9A-Z]{16}\b",
    "API secret key": r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "email address": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
    "local user path": r"(?:/Users/[A-Za-z]|/home/[a-z]|[A-Za-z]:\\Users\\)",
}
TOKEN = re.compile(r"[A-Za-z0-9._%+@-]+")


def log(line):
    try:
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {line}\n")
    except OSError:
        pass


def git(*args, binary=False):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True)
    return out.stdout if binary else out.stdout.decode("utf-8", "replace")


def load_hashes():
    p = ROOT / "guard" / "private_hashes.txt"
    if not p.exists():
        raise RuntimeError("guard/private_hashes.txt missing")
    return {l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")}


def personal_hits(text, hashes):
    for tok in TOKEN.findall(text):
        tok = tok.strip(".-").lower()
        parts = {tok, *re.split(r"[._%+@-]+", tok)}
        for p in parts:
            if p and hashlib.sha256(p.encode()).hexdigest() in hashes:
                return True
    return False


def scan(files, read):
    hashes = load_hashes()
    problems = []
    for f in files:
        if not any(fnmatch.fnmatch(f, pat) for pat in ALLOWED_PATHS):
            problems.append(f"{f}: path not on the allowlist")
            continue
        if any(fnmatch.fnmatch(Path(f).name, pat) for pat in BLOCKED_NAMES):
            problems.append(f"{f}: secret-looking filename")
            continue
        data = read(f)
        if data is None:
            continue
        text = data.decode("utf-8", "replace")
        for label, pat in PATTERNS.items():
            if re.search(pat, text):
                problems.append(f"{f}: contains {label}")
        if personal_hits(text, hashes):
            problems.append(f"{f}: contains a personal identifier")
    return problems


def main():
    mode = "ci" if "--all" in sys.argv else "pre-commit"
    try:
        if mode == "ci":
            files = [f for f in git("ls-files", "-z").split("\0") if f]
            read = lambda f: (ROOT / f).read_bytes() if (ROOT / f).is_file() else None
        else:
            files = [f for f in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0") if f]
            read = lambda f: git("show", f":{f}", binary=True)
        problems = scan(files, read)
        audit = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit.py")], cwd=ROOT,
                               capture_output=True, text=True)
        if audit.returncode != 0:
            problems.append("audit failed:\n" + audit.stdout.strip())
    except Exception as e:  # fail closed
        problems = [f"guard error: {e!r}"]
        files = []
    if problems:
        print("BLOCKED by guard/precommit_guard.py:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        log(f"BLOCK {mode} files={len(files)} :: " + " | ".join(p.splitlines()[0] for p in problems))
        return 1
    print(f"guard: OK ({mode}, {len(files)} file(s) scanned, audit passed)")
    log(f"ALLOW {mode} files={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
