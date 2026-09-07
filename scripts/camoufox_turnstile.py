#!/usr/bin/env python3
"""Camoufox / Playwright Turnstile helpers + optional CLI smoke.

Library (import into an existing page session):
  from camoufox_turnstile import wait_turnstile_token, click_turnstile_frame, read_token, fill_token

CLI:
  python camoufox_turnstile.py --url https://example.com/page --proxy http://127.0.0.1:7897

Success gate: token length > 20 (prefer >= 80 for managed widgets). Emits JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable

LogFn = Callable[[str], None]

READ_TOKEN_JS = """
() => {
  try {
    const byInput = String(
      (document.querySelector('input[name="cf-turnstile-response"]') || {}).value || ''
    ).trim();
    if (byInput) return byInput;
    if (window.turnstile && typeof turnstile.getResponse === 'function') {
      return String(turnstile.getResponse() || '').trim();
    }
    return '';
  } catch (e) {
    return '';
  }
}
"""

FILL_TOKEN_JS = """
(token) => {
  const t = String(token || '').trim();
  const cfInput = document.querySelector('input[name="cf-turnstile-response"]');
  if (!cfInput || !t) return 0;
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  )?.set;
  if (nativeSetter) nativeSetter.call(cfInput, t);
  else cfInput.value = t;
  cfInput.dispatchEvent(new Event('input', { bubbles: true }));
  cfInput.dispatchEvent(new Event('change', { bubbles: true }));
  return String(cfInput.value || '').length;
}
"""


def _log(log: LogFn | None, msg: str) -> None:
    if log:
        log(msg)


def read_token(page: Any) -> str:
    """Read current Turnstile token from page (hidden input or turnstile.getResponse)."""
    try:
        token = page.evaluate(READ_TOKEN_JS)
    except Exception:
        return ""
    return str(token or "").strip()


def fill_token(page: Any, token: str) -> int:
    """Write token into cf-turnstile-response. Returns filled length."""
    try:
        n = page.evaluate(FILL_TOKEN_JS, str(token or "").strip())
        return int(n or 0)
    except Exception:
        return 0


def click_turnstile_frame(page: Any, *, log: LogFn | None = None) -> bool:
    """Click Turnstile widget via Playwright frame API.

    Managed Turnstile often has no checkbox DOM (canvas/overlay). Strategy:
      1) find challenges.cloudflare.com / turnstile frame
      2) click body at (24, h/2)
      3) fallback: page-level iframe bounding box click
    """
    turnstile_frame = None
    all_frame_urls: list[str] = []
    try:
        frames = page.frames
    except Exception as exc:
        _log(log, f"[cf] frames unavailable: {exc}")
        return False

    for frame in frames:
        frame_url = str(getattr(frame, "url", "") or "")
        all_frame_urls.append(frame_url[:80])
        low = frame_url.lower()
        if "challenges.cloudflare.com" in low or "turnstile" in low:
            turnstile_frame = frame
            break

    if not turnstile_frame:
        _log(log, f"[cf] frame not found frames={all_frame_urls}")
        return False

    frame_url = str(getattr(turnstile_frame, "url", "") or "")
    _log(log, f"[cf] frame located: {frame_url[:100]}")

    try:
        body_info = turnstile_frame.evaluate(
            """() => {
  const b = document.body;
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { w: r.width, h: r.height };
}"""
        )
        if not body_info or float(body_info.get("w") or 0) <= 0:
            _log(log, "[cf] frame body not ready")
        else:
            click_x = 24
            click_y = float(body_info["h"]) / 2.0
            turnstile_frame.click(
                "body", position={"x": click_x, "y": click_y}, timeout=3000
            )
            _log(log, f"[cf] clicked frame body ({click_x}, {click_y:.0f})")
            return True
    except Exception as exc:
        _log(log, f"[cf] frame body click failed: {exc}")

    try:
        iframe_el = page.query_selector(
            'iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]'
        )
        if iframe_el:
            box = iframe_el.bounding_box()
            if box and box.get("width", 0) > 0:
                px = box["x"] + 24
                py = box["y"] + box["height"] / 2
                page.mouse.click(px, py)
                _log(log, f"[cf] clicked page iframe ({px:.0f}, {py:.0f})")
                return True
    except Exception as exc:
        _log(log, f"[cf] page iframe click failed: {exc}")
    return False


def wait_turnstile_token(
    page: Any,
    *,
    timeout: float = 35.0,
    min_len: int = 20,
    prefer_len: int = 80,
    log: LogFn | None = None,
) -> str:
    """Poll + click until token length >= min_len (prefer prefer_len). Raises on timeout."""
    deadline = time.time() + max(5.0, float(timeout))
    click_attempted = False
    last_click = 0.0
    round_i = 0
    while time.time() < deadline:
        round_i += 1
        token = read_token(page)
        if len(token) >= prefer_len or (len(token) > min_len and click_attempted):
            _log(log, f"[cf] token ok len={len(token)}")
            return token
        if len(token) > min_len:
            _log(log, f"[cf] token weak len={len(token)}, keep waiting")
        now = time.time()
        if (not click_attempted) or (now - last_click >= 2.8):
            _log(log, "[cf] click attempt")
            click_turnstile_frame(page, log=log)
            click_attempted = True
            last_click = now
            time.sleep(0.8)
            continue
        time.sleep(0.35)
    raise TimeoutError(f"turnstile timeout after {timeout:.0f}s rounds={round_i}")


def emit(obj: dict[str, Any], *, code: int) -> int:
    print(json.dumps(obj, ensure_ascii=False), flush=True)
    return code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True, help="page that hosts Turnstile")
    p.add_argument("--proxy", default="", help="http://host:port or socks5://host:port")
    p.add_argument("--timeout", type=float, default=35.0)
    p.add_argument("--headed", action="store_true", default=True)
    p.add_argument("--headless", action="store_true", help="forbidden for real solves; smoke only")
    p.add_argument("--os", default="windows", dest="os_name")
    args = p.parse_args(argv)

    if args.headless:
        return emit(
            {
                "ok": False,
                "error_class": "headless_forbidden",
                "error": "Turnstile must not use headless",
            },
            code=2,
        )

    try:
        from camoufox.sync_api import Camoufox
    except Exception as exc:
        return emit(
            {"ok": False, "error_class": "deps", "error": f"camoufox missing: {exc}"},
            code=3,
        )

    opts: dict[str, Any] = {
        "headless": False,
        "humanize": True,
        "os": args.os_name,
        "block_webrtc": True,
        "disable_coop": True,
        "i_know_what_im_doing": True,
    }
    if args.proxy.strip():
        opts["proxy"] = {"server": args.proxy.strip()}
        opts["geoip"] = True

    token = ""
    try:
        with Camoufox(**opts) as browser:
            # Camoufox may return Browser or BrowserContext depending on opts
            if hasattr(browser, "new_context"):
                ctx = browser.new_context()
                page = ctx.new_page()
            else:
                page = browser.pages[0] if getattr(browser, "pages", None) else browser.new_page()
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            token = wait_turnstile_token(
                page,
                timeout=args.timeout,
                log=lambda m: print(m, file=sys.stderr, flush=True),
            )
    except Exception as exc:
        return emit(
            {
                "ok": False,
                "error_class": type(exc).__name__,
                "error": str(exc)[:400],
                "token_len": len(token),
            },
            code=1,
        )

    ok = len(token) > 20
    return emit(
        {
            "ok": ok,
            "token_len": len(token),
            "token_prefix": token[:16] if ok else "",
            "url": args.url,
            "method": "camoufox_frame_click",
        },
        code=0 if ok else 1,
    )


if __name__ == "__main__":
    raise SystemExit(main())
