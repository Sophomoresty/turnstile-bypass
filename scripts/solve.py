#!/usr/bin/env python3
"""Pick a working Turnstile lane and solve. JSON only.

Default: DrissionPage + packaged extension (self-contained).
agent-browser only if --lane ab or TURNSTILE_PREFER_AB=1.
"""
from __future__ import annotations

import argparse
import json
import os
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


def run_script(script: str, extra: list[str], py: str | None = None) -> int:
    exe = py or sys.executable
    cmd = [exe, str(HERE / script), *extra]
    proc = subprocess.run(cmd)
    return proc.returncode


def pick_lane(forced: str | None) -> str:
    runtime.ensure_patch()
    if forced:
        return forced
    prefer_ab = os.environ.get("TURNSTILE_PREFER_AB", "1").strip() not in ("0", "false", "no")
    ab = bool(runtime.agent_browser_cli() and runtime.node_bin() and runtime.patch_ok())
    drission = bool(
        runtime.find_chrome()
        and runtime.has_display()
        and runtime.patch_ok()
        and runtime.has_drissionpage(Path(runtime.solver_python()))
    )
    if prefer_ab and ab:
        return "ab"
    if drission:
        return "drission"
    if ab:
        return "ab"
    return "none"


def main() -> int:
    ap = argparse.ArgumentParser(description="Solve Cloudflare Turnstile")
    ap.add_argument("--url", default=None)
    ap.add_argument("--lane", choices=("auto", "ab", "drission", "camoufox", "yescaptcha"), default="auto")
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
        return run_script("solve_turnstile.py", extra, py=runtime.solver_python())
    if lane == "camoufox":
        if not args.url:
            return emit(False, error="camoufox lane needs --url")
        return run_script("camoufox_turnstile.py", extra)
    if lane == "yescaptcha":
        if not args.url:
            return emit(False, error="yescaptcha lane needs --url and --sitekey")
        return run_script("solve_yescaptcha.py", extra)
    return emit(
        False,
        error="no solver lane; run: python3 scripts/install.py",
        hint="needs Chrome + pip install -r requirements.txt",
        platform=sys.platform,
        chrome=runtime.find_chrome(),
        drissionpage=runtime.has_drissionpage(Path(runtime.solver_python())),
        agent_browser=runtime.agent_browser_cli(),
        node=runtime.node_bin(),
        patch=runtime.patch_ok(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
