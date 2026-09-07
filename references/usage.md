# turnstile-bypass usage

Chrome CDP `Input.dispatchMouseEvent` sets `screenX`/`screenY` equal to client coords (chromium #40280325). Turnstile uses that delta. `assets/turnstilePatch` patches MouseEvent in `world: MAIN` on `challenges.cloudflare.com`.

## Install

```bash
python3 -m pip install -r requirements.txt   # DrissionPage lane
# optional: agent-browser-cli + node  (fast lane)
# optional: camoufox                  (Firefox lane)
```

Chrome must be installed (Google Chrome or Chromium). Set `CHROME_PATH` if auto-detect fails.

| OS | Chrome lookup |
|---|---|
| macOS | `/Applications/Google Chrome.app/...`, `~/Applications/...` |
| Windows | `%PROGRAMFILES%`, `%LOCALAPPDATA%` |
| Linux | `google-chrome-stable` / `chromium` on PATH |
| WSL | also `/mnt/c/Program Files/Google/Chrome/...` |

Linux without a desktop:

```bash
sudo apt-get install -y xvfb
xvfb-run -a python3 scripts/solve.py --url "https://example.com/login"
```

## Entry

```bash
python3 scripts/preflight.py
python3 scripts/solve.py --url "https://example.com/login"
python3 scripts/solve_agent_browser.py          # current AB tab
python3 scripts/solve_turnstile.py --url "..."  # force Drission
```

`ok:true` only if `token` length > 20. Use the token immediately (TTL ~300s).

## Lanes (speed)

1. **agent-browser** — existing Chrome, no extra window. Managed widgets often auto-issue in ~1–2s. Interactive widget: iframe CDP click, default timeout 28s.
2. **DrissionPage + patch** — starts Chrome, default ~25s budget. Do not `turnstile.reset()` first.
3. **Camoufox** — only if the page already lives in Playwright Firefox, or `--lane camoufox`.
4. **YesCaptcha** — `YESCAPTCHA_CLIENT_KEY`, last resort.

AB iframe clicks go to Chrome CDP (`TURNSTILE_AB_CHROME_PORT`, default 19221). Never `ws://127.0.0.1:19222/devtools/page/<iframe>`.

## Proxy auth

Chrome CLI has no user/pass proxy. Generate an extension:

```bash
python3 scripts/proxy_auth_extension.py --host HOST --port 8080 --username USER --password PASS
```

Pass `extension_dir` to Drission `co.add_extension(...)`. Rotate residential sessions in the username (`sid-...`).

## Fail

| Symptom | Action |
|---|---|
| preflight chrome missing | install Chrome or `CHROME_PATH` |
| Linux no DISPLAY | `xvfb-run -a` |
| click but empty token + DC IP | one retry on residential proxy |
| token rejected | TTL; do not cache across sessions |
