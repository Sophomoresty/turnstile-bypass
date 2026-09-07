# turnstile-bypass trigger cases

## Positive

1. Cloudflare Turnstile click fails → `scripts/solve.py` / solve-agent-browser
2. CF widget / turnstile token needed → preflight then solve.py
3. agent-browser click misses Turnstile (screenX) → solve-agent-browser (iframe CDP, no GUI)
4. Camoufox / Playwright Turnstile → solve-camoufox
5. YesCaptcha Turnstile → usage YesCaptcha

## Negative

6. Cloudflare WARP / DNS → no
7. Generic login click → agent-browser, not this skill
8. reCAPTCHA / hCaptcha → no
9. IUAM 5s interstitial / JS challenge → no (widget only)

## Fallback

Other CAPTCHA → workflows/fallback.md, never fake success
