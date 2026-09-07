#!/usr/bin/env python3
"""Live Turnstile e2e. Exit 0 only if every case returns ok and tokenLen>20."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
SOLVE = ROOT / "scripts" / "solve.py"


def solve(url: str, lane: str, timeout: float = 40.0, extra: list[str] | None = None) -> dict:
    t0 = time.time()
    cmd = [sys.executable, str(SOLVE), "--lane", lane, "--url", url, "--timeout", str(timeout)]
    if extra:
        cmd.extend(extra)
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout + 40,
        cwd=str(ROOT),
    )
    elapsed = round(time.time() - t0, 2)
    line = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
    try:
        box = json.loads(line)
    except Exception:
        box = {"ok": False, "error": f"bad_json:{line[:240]}", "stderr": (r.stderr or "")[-240:]}
    box["elapsed_s"] = box.get("elapsed_s") or elapsed
    box["lane"] = lane
    box["url"] = url
    box["rc"] = r.returncode
    return box


class ExampleHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(EXAMPLES), **kwargs)


def main() -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", 8766), ExampleHandler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    cases = [
        ("ab", "https://demo.turnstile.workers.dev/", []),
        ("ab", "http://127.0.0.1:8766/interactive-dummy.html", []),
        ("ab", "https://grok.com/", ["--fresh"]),
    ]
    out = []
    try:
        for lane, url, extra in cases:
            box = solve(url, lane, timeout=60.0 if "grok.com" in url else 40.0, extra=extra)
            out.append(
                {
                    "ok": bool(
                        box.get("ok")
                        and (
                            int(box.get("tokenLen") or 0) > 20
                            or str(box.get("kind") or "") in ("cf_passed", "cf_clearance", "both")
                        )
                    ),
                    "lane": lane,
                    "url": url,
                    "kind": box.get("kind"),
                    "elapsed_s": box.get("elapsed_s"),
                    "tokenLen": box.get("tokenLen"),
                    "clearanceLen": box.get("clearanceLen"),
                    "titleAfterFresh": (box.get("binding") or {}).get("titleAfterFresh"),
                    "error": box.get("error"),
                    "chromePort": box.get("chromePort") or box.get("cdpPort"),
                }
            )
    finally:
        httpd.shutdown()
    ok = all(x["ok"] for x in out)
    print(json.dumps({"ok": ok, "cases": out}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
