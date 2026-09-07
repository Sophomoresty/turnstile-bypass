# workflow: DrissionPage

1. `python3 scripts/preflight.py` — want `methods.drissionpage=true` (or install `requirements.txt` + Chrome).
2. Solve:

```bash
python3 scripts/solve.py --lane drission --url "<TARGET_URL>"
# or
python3 scripts/solve_turnstile.py --url "<TARGET_URL>"
```

On Linux without a desktop: prefix with `xvfb-run -a`.

3. `ok==true` and token length > 20.
4. Use the token immediately.
5. Empty token on datacenter IP: one residential retry, then stop or YesCaptcha.
