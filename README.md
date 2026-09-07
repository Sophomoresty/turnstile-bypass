# turnstile-bypass

Self-contained Cloudflare challenge helper for macOS, Windows, and Linux.

It drives headed Chrome to pass:

1. **Turnstile widget** on a site’s own page (checkbox / managed) → JSON `token`
2. **Interstitial / “请稍候…” / Just a moment** (IUAM JS or managed challenge before the origin) → `cf_clearance` and the real page

It does **not** pass IP bans (1020), rate limits (1015), Bot Fight when Chrome itself is rejected, hCaptcha, or reCAPTCHA.

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
| Turnstile widget on the origin page | Cloudflare **1020** / **1015** / WAF block |
| Interstitial “请稍候…” / Just a moment (JS or managed challenge) | Bot Fight when this Chrome is already banned |
| `cf_clearance` + origin HTML | hCaptcha, reCAPTCHA, headless Chrome |

## Verified

macOS, Chrome 152, agent-browser, CDP **19221**.

| Target | What | Result | Time |
|---|---|---|---|
| https://demo.turnstile.workers.dev/ | dummy Turnstile | tokenLen 21 | 3.46s |
| `examples/interactive-dummy.html` | dummy interactive | tokenLen 21 | 7.46s |
| https://aipaycards.com/login | production Turnstile | tokenLen **816**, 3/3 | 8–11s |
| https://grok.com/ | interstitial (`cf-mitigated: challenge`, title 请稍候…) | `kind=cf_clearance`, clearanceLen **597**, origin title Grok | 8.7s (`--fresh`) |

`curl` to grok.com without this Chrome is **403** + `cf-mitigated: challenge`. After solve, the same tab is the Grok app. Interstitial path focuses the tab (`Page.bringToFront`) and clicks the CF iframe; waiting-room JS often refuses to finish if `document.visibilityState` is `hidden`.

```bash
python3 scripts/solve.py --url "https://grok.com/" --fresh
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

- Headed Chrome only. Interstitial needs the tab visible (`Page.bringToFront`).
- Datacenter IPs often fail; one residential-proxy retry, then stop.
- Do not cache tokens across sessions.
- Not 1020/1015/WAF block, not a fingerprint browser.

本项目的开发 agent 能力由 [GenericAgent](https://github.com/lsdefine/GenericAgent) 提供。

### 🚩 友情链接

[![GenericAgent](https://img.shields.io/badge/Agent_Framework-GenericAgent-orange?style=for-the-badge&logo=github)](https://github.com/lsdefine/GenericAgent)
[![LinuxDo](https://img.shields.io/badge/社区-LinuxDo-blue?style=for-the-badge)](https://linux.do/)

## License

MIT. See `LICENSE`.
