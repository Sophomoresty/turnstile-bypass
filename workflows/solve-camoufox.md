# Camoufox / Playwright Turnstile

Frame click + token poll. Does not need `turnstilePatch`. Use when the page already runs in Camoufox / Playwright Firefox.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # or skill scripts/
from camoufox_turnstile import wait_turnstile_token, fill_token

token = wait_turnstile_token(page, timeout=35, log=print)
fill_token(page, token)
assert len(token) > 20
```

CLI:

```bash
python3 scripts/camoufox_turnstile.py --url https://example.com/page --proxy http://127.0.0.1:7897
```

Clicks `challenges.cloudflare.com` frame at `(24, h/2)`, retries about every 2.8s, default timeout 35s. No headless. No parallel Drission Chrome on the same proxy session.
