# turnstile-bypass

Self-contained **Cloudflare Turnstile** solver for macOS, Windows, and Linux.

It loads a small Chrome extension, opens the page in headed Chrome, clicks the Turnstile widget, and prints a JSON token. That is the CF checkbox / managed **widget**. It does not pass the 5-second “Checking your browser” waiting room, JS interstitials, Bot Fight, or other CAPTCHAs.

A new agent should follow **Install** then **Use**. Nothing else is required.

## Install

Needs: Python 3.10+, Google Chrome or Chromium.

```bash
git clone https://github.com/Sophomoresty/turnstile-bypass.git
cd turnstile-bypass
python3 scripts/install.py
```

`install.py` creates `.venv` in this repo, installs `requirements.txt` (DrissionPage), packs `assets/turnstilePatch.zip`, and runs `scripts/preflight.py`.

You want:

```json
{ "ok": true, "methods": { "drissionpage": true } }
```

| OS | If Chrome is not found |
|---|---|
| macOS | Install Google Chrome, or `export CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"` |
| Windows | `set CHROME_PATH=C:\Path\to\chrome.exe` |
| Linux | `sudo apt-get install -y google-chrome-stable` or `chromium` |
| Linux, no desktop | `sudo apt-get install -y xvfb` then prefix commands with `xvfb-run -a` |

Manual install (same result):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt   # Windows: .venv\Scripts\python.exe
python3 scripts/pack_extension.py
python3 scripts/preflight.py
```

## Use

```bash
python3 scripts/solve.py --url "https://example.com/page-with-turnstile"
```

Stdout is one JSON object.

- Success: `"ok": true` and `token` longer than 20 characters. Send it in the next request immediately (about 300s TTL).
- Failure: `"ok": false` and `error`. Do not invent a token.

Force a lane:

```bash
python3 scripts/solve.py --lane drission --url "https://example.com/login"
python3 scripts/solve.py --lane ab --url "https://example.com/login"
```

Linux without GUI:

```bash
xvfb-run -a python3 scripts/solve.py --url "https://example.com/login"
```

Default lane: **DrissionPage + packaged extension** after `install.py`. If `agent-browser-cli` and Node are already on `PATH`, `solve.py` prefers that faster lane (`TURNSTILE_PREFER_AB=0` to force Drission).

`--lane ab` is optional and faster only if `agent-browser-cli` + Node are already installed **and** that Chrome already has this extension. Iframe clicks must use Chrome CDP (default port **19221**), never the shim **19222**.

YesCaptcha (last resort): `YESCAPTCHA_CLIENT_KEY` and

```bash
python3 scripts/solve.py --lane yescaptcha --url "https://example.com" --sitekey "0x..."
```

## Chrome extension

Source of truth: **`assets/turnstilePatch/`** (load unpacked).

Packed copy: **`assets/turnstilePatch.zip`** (same two files). Rebuild with `python3 scripts/pack_extension.py`.

The extension is Manifest V3, `world: MAIN`, `all_frames`, matches `https://challenges.cloudflare.com/*` only. It patches `MouseEvent.screenX/Y` because Chrome CDP clicks set screen coords equal to client coords ([chromium 40280325](https://issues.chromium.org/issues/40280325)), which Turnstile treats as a bot.

**Load unpacked (manual Chrome):** `chrome://extensions` → Developer mode → Load unpacked → select `assets/turnstilePatch/`.

DrissionPage does this for you via `add_extension`. You do not need to click that UI for the default `solve.py` path.

## What it is not

| In scope | Out of scope |
|---|---|
| Turnstile widget (visible / managed / interactive) | IUAM waiting room |
| Token from `turnstile.getResponse()` or `cf-turnstile-response` | Bot Fight, JS challenge, IP ban |
| Headed Chrome (Xvfb counts) | Headless Chrome |
| | hCaptcha, reCAPTCHA |

## Verified

Live `python3 scripts/e2e.py` on **2026-09-08** (macOS, Chrome 152, agent-browser, CDP **19221**). Dummy-key cases and the production aipay widget all returned `ok: true`.

| Target | Lane | Token length | Time | Notes |
|---|---|---|---|---|
| https://demo.turnstile.workers.dev/ | ab | 21 | 3.46s | Cloudflare dummy key → official dummy token |
| `examples/interactive-dummy.html` | ab | 21 | 7.46s | Interactive dummy key |
| https://aipaycards.com/login | ab | **816** | 9.73s / 9.74s / 7.99s | Real sitekey, `patched: true`, not dummy; 3/3 |

Cloudflare dummy sitekeys mint `XXXX.DUMMY.TOKEN.XXXX`. That still proves: open page → find widget → click CF iframe → token longer than 20. Production sitekeys return much longer tokens.

```bash
python3 scripts/e2e.py
```

## Layout

```
AGENTS.md                 # short runbook for coding agents
README.md                 # this file
LICENSE
requirements.txt          # DrissionPage
assets/turnstilePatch/    # unpacked MV3 extension
assets/turnstilePatch.zip # same, zipped
examples/interactive-dummy.html
scripts/install.py            # venv + deps + pack + preflight
scripts/e2e.py                # live two-page check; exit 0 only on success
scripts/preflight.py
scripts/solve.py          # entry
scripts/solve_turnstile.py
scripts/pack_extension.py
scripts/solve_agent_browser.py
scripts/camoufox_turnstile.py
scripts/solve_yescaptcha.py
scripts/proxy_auth_extension.py
scripts/runtime.py
```

## Limits

- Headed Chrome only.
- Datacenter IPs often return an empty token; one residential-proxy retry, then stop.
- Do not cache tokens across sessions.
- Not a general Cloudflare WAF bypass.

## License

MIT. See `LICENSE`.
