# For a new agent

Read `README.md` first. Do not invent extra tools.

1. Clone this repo. It is self-contained: Python scripts, Turnstile Chrome extension (`assets/turnstilePatch/` and `assets/turnstilePatch.zip`), examples.
2. Install Google Chrome (or Chromium).
3. `python3 scripts/install.py`  
   Creates `.venv`, installs `requirements.txt` (DrissionPage), zips the extension, runs `preflight.py`.
4. Confirm preflight JSON has `"ok": true` and `"methods.drissionpage": true`.
5. Solve:
   `python3 scripts/solve.py --url "<PAGE_WITH_TURNSTILE>"`
6. Success: `"ok": true` and either `token` length > 20 (widget) or `kind` is `cf_clearance` / `cf_passed` / `both` (waiting room).
7. Waiting room (grok.com): `python3 scripts/solve.py --url "https://grok.com/" --fresh`
8. `python3 scripts/e2e.py` should stay green.

Default: DrissionPage after `install.py`. If `agent-browser-cli` is on PATH, `solve.py` prefers it (`TURNSTILE_PREFER_AB=0` forces Drission).

Linux without a desktop: `xvfb-run -a python3 scripts/solve.py --url "..."`

Out of scope: Cloudflare 1020/1015, Bot Fight ban, hCaptcha, reCAPTCHA, headless Chrome.
