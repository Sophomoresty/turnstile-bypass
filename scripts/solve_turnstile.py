#!/usr/bin/env python3
"""Solve Cloudflare Turnstile via DrissionPage + turnstilePatch.

JSON only. ok=true only when token length > 20. Never headless.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import runtime  # noqa: E402

DEFAULT_PATCH = runtime.PATCH_DIR


def emit(ok: bool, token: str | None = None, error: str | None = None, **extra) -> int:
    payload = {"ok": ok, "token": token, "error": error, **extra}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else 1


def read_token(page) -> str:
    try:
        token = page.run_js(
            """
            try {
              const t = turnstile.getResponse();
              if (t && String(t).length > 20) return String(t);
            } catch (e) {}
            const inputs = document.querySelectorAll('[name="cf-turnstile-response"]');
            for (const input of inputs) {
              if (input.value && input.value.length > 20) return input.value;
            }
            return '';
            """
        )
    except Exception:
        return ""
    return str(token or "")


def click_widget(page) -> None:
    try:
        host = page.ele(".cf-turnstile", timeout=0.8) or page.ele("@data-sitekey", timeout=0.4)
        if host:
            host.click()
    except Exception:
        pass
    try:
        iframe = page.ele("tag:iframe@src:challenges.cloudflare.com", timeout=0.8)
        if iframe:
            iframe.click()
            iframe.run_js(
                """
                if (!window.dtp) {
                    window.dtp = 1;
                    function r(a,b) { return Math.floor(Math.random()*(b-a+1))+a; }
                    Object.defineProperty(MouseEvent.prototype, 'screenX', {
                      get: function() { return (this.clientX||0)+r(40,180); },
                      configurable: true
                    });
                    Object.defineProperty(MouseEvent.prototype, 'screenY', {
                      get: function() { return (this.clientY||0)+r(60,220); },
                      configurable: true
                    });
                }
                """
            )
    except Exception:
        pass
    try:
        challenge_input = page.ele("@name=cf-turnstile-response", timeout=0.5)
        wrapper = challenge_input.parent()
        iframe = wrapper.shadow_root.ele("tag:iframe")
        body = iframe.ele("tag:body").shadow_root
        btn = body.ele("tag:input")
        btn.click()
    except Exception:
        pass


def solve_turnstile(page, timeout_s: float = 20.0) -> str | None:
    """Do not reset() first — that cancels managed auto-pass."""
    deadline = time.time() + timeout_s
    last_click = 0.0
    while time.time() < deadline:
        token = read_token(page)
        if len(token) > 20:
            return token
        now = time.time()
        if last_click == 0.0 or now - last_click >= 2.2:
            try:
                click_widget(page)
                last_click = now
            except Exception:
                pass
        time.sleep(0.25)
    token = read_token(page)
    return token if len(token) > 20 else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Solve Cloudflare Turnstile")
    ap.add_argument("--url", required=True, help="Page URL with Turnstile")
    ap.add_argument("--chrome-path", default=None)
    ap.add_argument("--patch-dir", default=str(DEFAULT_PATCH))
    ap.add_argument("--proxy", default=None, help="http://host:port (no auth)")
    ap.add_argument("--timeout", type=float, default=25)
    args = ap.parse_args()

    try:
        from DrissionPage import Chromium, ChromiumOptions
    except ImportError:
        return emit(
            False,
            error="DrissionPage not installed; python3 scripts/install.py",
        )

    runtime.ensure_patch()
    patch = Path(args.patch_dir).resolve()
    if not (patch / "manifest.json").is_file():
        return emit(False, error=f"patch dir missing: {patch}")

    chrome = args.chrome_path or runtime.find_chrome()
    if not chrome:
        return emit(False, error="chrome path not found; set CHROME_PATH")

    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    profile = tempfile.mkdtemp(prefix="turnstile-chrome-")
    co = ChromiumOptions()
    co.set_paths(
        browser_path=chrome,
        local_port=port,
        address=f"127.0.0.1:{port}",
        user_data_path=profile,
    )
    co.add_extension(str(patch))
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--no-first-run")
    co.set_argument("--no-default-browser-check")
    co.set_argument("--window-size=1920,1080")
    if args.proxy:
        co.set_proxy(args.proxy)

    browser = None
    t0 = time.time()
    try:
        browser = Chromium(co)
        page = browser.get_tabs()[-1]
        page.get(args.url, timeout=max(15.0, float(args.timeout)))
        token = read_token(page)
        extra: dict = {"lane": "drission", "cdpPort": port}
        if len(token) <= 20:
            import solve_agent_browser as sab

            tabs = sab.json_list(port)
            page_id = None
            for tab in tabs:
                if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
                    page_id = tab.get("id")
            if page_id:
                result = sab.solve(port, str(page_id), float(args.timeout))
                token = str(result.get("token") or "")
                extra["attempts"] = result.get("attempts")
                extra["steps"] = result.get("steps")
            else:
                token = solve_turnstile(page, timeout_s=float(args.timeout)) or ""
        if len(token) <= 20:
            return emit(False, error="no token after timeout", elapsed_s=round(time.time() - t0, 2), **extra)
        return emit(True, token=token, elapsed_s=round(time.time() - t0, 2), tokenLen=len(token), **extra)
    except Exception as exc:
        import traceback

        return emit(False, error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc()[-800:])
    finally:
        if browser is not None:
            try:
                browser.quit()
            except Exception:
                pass
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
