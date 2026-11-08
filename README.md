# Mental Models

A small library of mental models, heuristics and biases, written to be read on a phone.
Each article covers what the model is, where it came from (with disputed origins called out),
why it works, its limits, counter-models, and three recall cards.

**Read it:** https://mrrix.github.io/mental-models/

On iPhone, open the link in Safari, tap Share, then **Add to Home Screen**. Open it once from
the home screen while online and every article is saved for offline reading.

## How it works

- Articles are Markdown files in `Models/`, indexed in `Models Index.md`. Rules for writing them are in `CLAUDE.md`.
- `python3 scripts/build.py` turns them into a static site in `_site/` (not committed). Standard library only, no dependencies.
- `python3 scripts/audit.py` checks format, sections, word counts, em dashes, links and the Index. `--backlog` lists unwritten models that other articles already link to.
- Pushing to `main` runs `.github/workflows/pages.yml`, which guards, audits, builds and deploys to GitHub Pages.

## Security model

This repo is public, so the controls focus on keeping private data out and keeping the deploy path narrow.

- **Pre-commit guard** (`guard/precommit_guard.py`, wired in through `.githooks/pre-commit`): blocks the commit if any staged file is outside a path allowlist, has a secret-looking filename, contains a token or key pattern, an email address, a local user path, or a personal identifier (checked against SHA-256 hashes so the identifiers never appear here), or if the audit fails. Any error inside the guard blocks too (fail closed). Every run appends ALLOW or BLOCK to `logs/guard.log`, which is gitignored.
- **CI runs the same guard** over every tracked file before building, so a commit that skips the local hook still can't deploy.
- **Workflow permissions** are `contents: read`, `pages: write` and `id-token: write`. No repo secrets. Only GitHub's own actions, pinned to commit SHAs.
- **Branch ruleset** on `main` blocks force-pushes and branch deletion.
- **Site hardening:** a strict Content-Security-Policy (scripts from this site only, no inline scripts, no third-party requests), `no-referrer`, `noindex`, and outbound links opened with `noopener noreferrer`. Article text is HTML-escaped at build time.
- **Claude Code deny rules** (`.claude/settings.json`) stop the agent from editing the guard, hooks, workflow or its own settings, and from running `--no-verify`, force-push, repo edit or delete, or secret commands.
