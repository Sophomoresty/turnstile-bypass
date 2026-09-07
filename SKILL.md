---
name: turnstile-bypass
description: "Use when Cloudflare Turnstile or CF widget challenge needs a token. Mac/Windows/Linux. Fast path is agent-browser CDP or DrissionPage + turnstilePatch."
---

# turnstile-bypass

Cloudflare **Turnstile** solver. Not IUAM / JS challenge / Bot Fight, not hCaptcha/reCAPTCHA.

## Overview

- Root cause: Chrome CDP `Input.dispatchMouseEvent` sets `screenX/Y == clientX/Y` (chromium #40280325). Patch runs in extension `world: MAIN` on `challenges.cloudflare.com`.
- **Fast path:** `scripts/solve.py` auto-picks `agent-browser` (if CLI+node) else DrissionPage+Chrome.
- Success: token length **> 20**. Never report ok on empty token.
- Headed only. No `chrome-show` / `Page.bringToFront`. No headless.

## Always Read

1. `rules/core-rules.md`
2. `references/usage.md`

## Common Tasks

- Preflight -> `scripts/preflight.py`
- Auto solve -> `scripts/solve.py --url <page>`
- Existing agent-browser tab -> `scripts/solve_agent_browser.py`
- Standalone Chrome -> `scripts/solve_turnstile.py --url <page>`
- Camoufox/Playwright page already open -> `workflows/solve-camoufox.md`
- Proxy with user/pass -> `scripts/proxy_auth_extension.py`

## Known Gotchas

- Token TTL ~300s; use immediately.
- Datacenter IPs often fail; residential proxy if the first try is empty.
- AB iframe CDP must hit Chrome port (`TURNSTILE_AB_CHROME_PORT`, default 19221), never shim 19222.
- Linux without DISPLAY: `xvfb-run -a python3 scripts/solve.py --url ...`
- Windows: `CHROME_PATH` if Chrome is not under Program Files.
- Do not run Drission Chrome and Camoufox against the same proxy session in parallel.

## References

- `README.md`
- `rules/core-rules.md`
- `references/usage.md`
- `workflows/solve-agent-browser.md`
- `workflows/solve-drission.md`
- `workflows/solve-camoufox.md`
- `workflows/fallback.md`
- `assets/turnstilePatch/`
- `scripts/runtime.py`
- `scripts/preflight.py`
- `scripts/solve.py`
- `scripts/solve_agent_browser.py`
- `scripts/solve_turnstile.py`
- `scripts/camoufox_turnstile.py`
- `scripts/proxy_auth_extension.py`
