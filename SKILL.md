---
name: turnstile-bypass
description: "Use when Cloudflare Turnstile widget needs a token. Clone this repo, python3 scripts/install.py, then python3 scripts/solve.py --url <page>."
---

# turnstile-bypass

Read **`README.md`** and **`AGENTS.md`** before running anything. The repo is self-contained.

Install: `python3 scripts/install.py`  
Solve: `python3 scripts/solve.py --url <page>`  
Success: JSON `ok` and token length > 20.

Default lane loads `assets/turnstilePatch` into headed Chrome (DrissionPage). Not IUAM, not headless.
