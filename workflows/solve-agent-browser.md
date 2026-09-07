# workflow: agent-browser Turnstile

Page already opened with `agent-browser-cli go <url>`, or pass `--url`. Chrome must load `turnstilePatch`. No GUI.

```bash
python3 scripts/preflight.py
python3 scripts/solve_agent_browser.py
python3 scripts/solve_agent_browser.py --url "https://example.com/login"
```

`ok:true` only when token length > 20.

1. Read existing token
2. Wait host box `width>=50` (≤18s); managed often auto-issues
3. CDP click CF iframe body `(24, h/2)` on Chrome port (default 19221)
4. Page host `(x+28, y+h/2)`
5. Poll every 250ms; max 4 click rounds; default timeout 28s

Do not connect iframe WebSocket to shim 19222. Do not `chrome-show` / `bringToFront`.
