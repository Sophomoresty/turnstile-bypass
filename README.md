# turnstile-bypass

A small, local solver for **Cloudflare Turnstile** on macOS, Windows, and Linux.

It opens the page (or uses an already-running Chrome), clicks the Turnstile widget the way a real mouse would, and prints a JSON token. That is the CF “checkbox / managed widget” shield — not the 5-second waiting room, not a JS interstitial, and not a generic WAF bypass.

```bash
python3 scripts/preflight.py
python3 scripts/solve.py --url "https://example.com/login"
```

`ok` is `true` only when the token is longer than 20 characters. Use it immediately (lifetime is about five minutes).

## What it is not

| In scope | Out of scope |
|---|---|
| Turnstile widget (visible, managed, interactive) | IUAM / “Checking your browser” interstitial |
| Token in `cf-turnstile-response` / `turnstile.getResponse()` | Bot Fight Mode, JS challenges, IP bans |
| Headed Chrome / Chromium (or Xvfb) | Headless Chrome (fingerprint + Shadow DOM fail) |
| | hCaptcha, reCAPTCHA |

## Why a CDP click is not enough

Chrome DevTools `Input.dispatchMouseEvent` sets `screenX` / `screenY` equal to the client coordinates ([chromium 40280325](https://issues.chromium.org/issues/40280325)). Turnstile treats that as automation.

`assets/turnstilePatch` is a Manifest V3 content script (`world: MAIN`, all frames). It only runs on `challenges.cloudflare.com` and restores a screen offset on `MouseEvent` / `PointerEvent`. Clicks into the CF iframe must go to **Chrome’s CDP port**, not a proxy shim.

## Install

```bash
git clone https://github.com/Sophomoresty/turnstile-bypass.git
cd turnstile-bypass
python3 -m pip install -r requirements.txt
```

You need Google Chrome or Chromium.

| OS | Chrome is found from |
|---|---|
| macOS | `/Applications/Google Chrome.app`, `~/Applications/...` |
| Windows | `%PROGRAMFILES%`, `%LOCALAPPDATA%` |
| Linux | `google-chrome-stable` / `chromium` on `PATH` |
| WSL | also `/mnt/c/Program Files/Google/Chrome/...` |

If detection fails: `export CHROME_PATH=/path/to/chrome`.

Optional **fast lane**: `agent-browser-cli` on your `PATH`, plus Node.js (reuses a Chrome you already launched).

Linux with no desktop:

```bash
sudo apt-get install -y xvfb
xvfb-run -a python3 scripts/solve.py --url "https://example.com/login"
```

Check the machine:

```bash
python3 scripts/preflight.py
```

You want `methods.agent_browser` or `methods.drissionpage` to be `true`.

## Usage

Auto-pick the fastest available lane:

```bash
python3 scripts/solve.py --url "https://example.com/page-with-turnstile"
```

Force a lane:

```bash
python3 scripts/solve.py --lane ab --url "https://example.com/login"
python3 scripts/solve.py --lane drission --url "https://example.com/login"
```

If Chrome is already on the page:

```bash
python3 scripts/solve_agent_browser.py
```

Stdout is one JSON object. On success:

```json
{"ok": true, "token": "0.xxxx...", "tokenLen": 800, "elapsed_s": 9.5}
```

On failure, `ok` is `false` and `error` says why. Empty tokens are never reported as success.

### Lanes

1. **agent-browser** — no extra window. Managed widgets often emit a token in about 1–2s; interactive widgets click the CF iframe (default budget 28s).
2. **DrissionPage + patch** — starts Chrome. Do not call `turnstile.reset()` first (it cancels auto-pass).
3. **Camoufox / Playwright Firefox** — only if the page already lives there, or `--lane camoufox`.
4. **YesCaptcha** — last resort, needs `YESCAPTCHA_CLIENT_KEY`.

### agent-browser ports

Managed agent-browser exposes a shim (default **19222**) and real Chrome CDP (**19221**). Iframe clicks must use the Chrome port:

```
TURNSTILE_AB_CHROME_PORT=19221
TURNSTILE_AB_SHIM_PORT=19222
```

Never attach the iframe WebSocket to `ws://127.0.0.1:19222/devtools/page/<iframe>`.

## Verified

Recorded **2026-09-07** on macOS (Darwin), Chrome 152, agent-browser bridge healthy, Chrome CDP **19221**, `turnstilePatch` loaded (`patched: true`). No GUI (`chrome-show` off).

| Target | Sitekey | Result | Time |
|---|---|---|---|
| [demo.turnstile.workers.dev](https://demo.turnstile.workers.dev/) | Cloudflare always-pass `1x00000000000000000000AA` | `ok`, iframe click, token length 21 | 9.47s |
| Local `examples/interactive-dummy.html` | Cloudflare interactive dummy `3x00000000000000000000FF` | widget found, iframe click, `patched: true`, token length 21 | 9.45s |

Both pages use **Cloudflare dummy sitekeys**. Those keys always mint the official test token `XXXX.DUMMY.TOKEN.XXXX`. That is enough to prove: navigate → find widget → click the CF iframe with the screenXY patch → read a token that passes the length gate.

A production sitekey yields a much longer token (often 700–800+ characters). Dummy keys will not. IUAM interstitials were not tested and are out of scope.

Reproduce the interactive dummy:

```bash
python3 -m http.server 8766 --directory examples
python3 scripts/solve.py --url "http://127.0.0.1:8766/interactive-dummy.html"
```

## Limits

- Headed Chrome only (Xvfb counts).
- Datacenter IPs often get an empty token; retry once on a residential proxy, then stop.
- Token TTL is about 300 seconds; do not cache across sessions.
- This is not a general Cloudflare WAF bypass.

## License

Add a license before you treat this as a public package. The repository is published as-is for the Turnstile widget path above.
