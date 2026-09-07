# core rules

1. Turnstile / CF widget only. Not hCaptcha, reCAPTCHA, IUAM, or JS challenge.
2. Lane: `scripts/solve.py` auto-picks. Existing agent-browser → AB. Else DrissionPage. Camoufox only if asked or `--lane camoufox`.
3. Run `scripts/preflight.py` first. `ok` if any lane is true.
4. No headless. No `chrome-show` / `Page.bringToFront`.
5. `ok:true` only when token length > 20.
6. AB click: read token first; then CF iframe body `(24, h/2)` on Chrome CDP; then page host `(x+28, y+h/2)`.
7. Iframe WebSocket never uses AB shim (default 19222).
8. YesCaptcha only after browser lanes fail and `YESCAPTCHA_CLIENT_KEY` is set.
9. Secrets only via env / CLI args, never committed.
10. macOS, Windows, and Linux share `scripts/runtime.py` for Chrome/venv/PATH. Do not hardcode `/mnt/c/...` or Unix-only venv paths in callers.
