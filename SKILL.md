---
name: turnstile-bypass
description: "Use for Cloudflare Turnstile widgets and 请稍候 / Just a moment interstitials. install.py then solve.py --url <page>."
---

# turnstile-bypass

Read **`README.md`** and **`AGENTS.md`**.

```bash
python3 scripts/install.py
python3 scripts/solve.py --url "https://grok.com/" --fresh
python3 scripts/solve.py --url "https://aipaycards.com/login"
```

Success: JSON `ok` with Turnstile `token` length > 20, or `kind` `cf_clearance` / `cf_passed` after the waiting room.
