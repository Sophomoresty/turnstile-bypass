# core rules

1. Cloudflare Turnstile widget **and** interstitial waiting-room (请稍候 / Just a moment). Not hCaptcha, reCAPTCHA, 1020/1015 bans.
2. Lane: `scripts/solve.py`. `--lane ab` when agent-browser has this extension. Camoufox / YesCaptcha only if asked.
3. Run `scripts/preflight.py` first.
4. No headless. Do not use `agent-browser-cli chrome-show`. Interstitial **does** CDP `Page.bringToFront` (tab must be visible or CF JS stalls).
5. `ok:true` if Turnstile token length > 20 **or** `cf_clearance` / origin left the waiting room (`kind` cf_clearance / cf_passed / both).
6. AB click: CF iframe body `(24, h/2)` on Chrome CDP, then page host `(x+28, y+h/2)`.
7. Iframe WebSocket never uses AB shim (default 19222).
8. YesCaptcha only after browser lanes fail and `YESCAPTCHA_CLIENT_KEY` is set.
9. Secrets only via env / CLI args, never committed.
10. macOS, Windows, and Linux share `scripts/runtime.py`.
