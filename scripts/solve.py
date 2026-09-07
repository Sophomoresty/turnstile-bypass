#!/usr/bin/env python3
"""Pick the fastest available Turnstile lane and solve. JSON only."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import runtime  # noqa: E402


def emit(ok: bool, **extra) -> int:
    print(json.dumps({"ok": ok, **extra}, ensure_ascii=False))
    return 0 if ok else 1


def run_script(script: str, extra: list[str]) -> int:
    py = sys.executable
    if script.endswith("solve_turnstile.py"):
        venv = runtime.venv_python()
        if venv:
            py = str(venv)
    cmd = [py, str(HERE / script), *extra]
    proc = subprocess.run(cmd)
    return proc.returncode


def pick_lane(forced: str | None) -> str:
    if forced:
        return forced
    ab = bool(runtime.agent_browser_cli() and runtime.node_bin() and runtime.patch_ok())
    if ab:
        return "ab"
    chrome = runtime.find_chrome()
    if chrome and runtime.patch_ok() and runtime.has_display():
        return "drission"
    return "none"


def main() -> int:
    ap = argparse.ArgumentParser(description="Solve Cloudflare Turnstile")
    ap.add_argument("--url", default=None)
    ap.add_argument("--lane", choices=("auto", "ab", "drission", "camoufox"), default="auto")
    ap.add_argument("--timeout", type=float, default=None)
    args, rest = ap.parse_known_args()
    lane = pick_lane(None if args.lane == "auto" else args.lane)
    extra: list[str] = []
    if args.url:
        extra.extend(["--url", args.url])
    if args.timeout is not None:
        extra.extend(["--timeout", str(args.timeout)])
    extra.extend(rest)

    if lane == "ab":
        return run_script("solve_agent_browser.py", extra)
    if lane == "drission":
        if not args.url:
            return emit(False, error="drission lane needs --url")
        return run_script("solve_turnstile.py", extra)
    if lane == "camoufox":
        if not args.url:
            return emit(False, error="camoufox lane needs --url")
        return run_script("camoufox_turnstile.py", extra)
    return emit(
        False,
        error="no solver lane; install Chrome+DrissionPage or agent-browser-cli+node",
        platform=sys.platform,
        chrome=runtime.find_chrome(),
        agent_browser=runtime.agent_browser_cli(),
        node=runtime.node_bin(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
