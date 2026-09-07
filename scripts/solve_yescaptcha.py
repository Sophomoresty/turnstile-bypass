#!/usr/bin/env python3
"""YesCaptcha Turnstile fallback. Needs YESCAPTCHA_CLIENT_KEY."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request


def emit(ok: bool, **extra) -> int:
    print(json.dumps({"ok": ok, **extra}, ensure_ascii=False))
    return 0 if ok else 1


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--sitekey", required=True)
    ap.add_argument("--timeout", type=float, default=180)
    args = ap.parse_args()
    key = os.environ.get("YESCAPTCHA_CLIENT_KEY") or ""
    if not key:
        return emit(False, error="YESCAPTCHA_CLIENT_KEY missing")
    created = post(
        "https://api.yescaptcha.com/createTask",
        {
            "clientKey": key,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": args.url,
                "websiteKey": args.sitekey,
            },
        },
    )
    task_id = created.get("taskId")
    if not task_id:
        return emit(False, error=created.get("errorDescription") or "createTask failed", raw=created)
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(3)
        box = post(
            "https://api.yescaptcha.com/getTaskResult",
            {"clientKey": key, "taskId": task_id},
        )
        if box.get("status") == "ready":
            token = str((box.get("solution") or {}).get("token") or "")
            if len(token) <= 20:
                return emit(False, error="token_too_short", tokenLen=len(token))
            return emit(True, token=token, tokenLen=len(token), lane="yescaptcha")
        if box.get("errorId"):
            return emit(False, error=box.get("errorDescription") or "getTaskResult error")
    return emit(False, error="yescaptcha timeout")


if __name__ == "__main__":
    raise SystemExit(main())
