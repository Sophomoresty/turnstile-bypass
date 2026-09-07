# For a new agent

Read `README.md` first. Do not invent extra tools.

1. Clone this repo. It is self-contained: Python scripts, Turnstile Chrome extension (`assets/turnstilePatch/` and `assets/turnstilePatch.zip`), examples.
2. Install Google Chrome (or Chromium).
3. `python3 scripts/install.py`  
   Creates `.venv`, installs `requirements.txt` (DrissionPage), zips the extension, runs `preflight.py`.
4. Confirm preflight JSON has `"ok": true` and `"methods.drissionpage": true`.
5. Solve:
   `python3 scripts/solve.py --url "<PAGE_WITH_TURNSTILE>"`
6. Success: stdout JSON `"ok": true` and `token` length > 20. Hand the token to the next request immediately (TTL ~300s).
7. Failure: print `error`. One residential-proxy retry if the IP looks like a datacenter. Do not loop. Do not fake a token.

Default: DrissionPage after `scripts/install.py`. If `agent-browser-cli` is on PATH, `solve.py` prefers it (`TURNSTILE_PREFER_AB=0` forces Drission).

Linux without a desktop:

`xvfb-run -a python3 scripts/solve.py --url "..."`

Out of scope: IUAM 5s page, JS challenge, Bot Fight, hCaptcha, reCAPTCHA, headless Chrome.
