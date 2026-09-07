#!/usr/bin/env python3
"""turnstile-bypass dependency preflight. Emits JSON only."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import runtime  # noqa: E402


def main() -> int:
    runtime.ensure_patch()
    chrome = runtime.find_chrome()
    venv = runtime.venv_python()
    solver_py = Path(runtime.solver_python())
    venv_ok = runtime.has_drissionpage(venv) if venv else False
    sys_ok = runtime.has_drissionpage(Path(sys.executable))
    yescaptcha = bool(os.environ.get("YESCAPTCHA_CLIENT_KEY"))
    ab_cli = runtime.agent_browser_cli()
    node = runtime.node_bin()
    display_ok = runtime.has_display()
    patch_ok = runtime.patch_ok()
    manifest_main = runtime.manifest_world_main()
    drission_ok = bool(chrome and (venv_ok or sys_ok) and patch_ok and display_ok)
    ab_ok = bool(ab_cli and node and patch_ok and manifest_main)

    checks = {
        "ok": bool(ab_ok or drission_ok or yescaptcha),
        "platform": sys.platform,
        "patch_dir": str(runtime.PATCH_DIR),
        "patch_zip": str(runtime.PATCH_ZIP),
        "patch_ok": patch_ok,
        "manifest_world_main": manifest_main,
        "chrome_path": chrome,
        "chrome_ok": chrome is not None,
        "venv_python": str(venv) if venv else None,
        "solver_python": str(solver_py),
        "drissionpage_venv": venv_ok,
        "drissionpage_sys": sys_ok,
        "yescaptcha_key": yescaptcha,
        "display_ok": display_ok,
        "agent_browser_cli": ab_cli,
        "node": node,
        "ab_chrome_port": runtime.DEFAULT_AB_CHROME_PORT,
        "ab_shim_port": runtime.DEFAULT_AB_SHIM_PORT,
        "methods": {
            "drissionpage": drission_ok,
            "agent_browser": ab_ok,
            "yescaptcha": yescaptcha,
        },
        "preferred": (
            "drissionpage" if drission_ok else "agent_browser" if ab_ok else "yescaptcha" if yescaptcha else None
        ),
        "install": "python3 scripts/install.py",
        "blockers": [],
    }
    if not patch_ok:
        checks["blockers"].append("missing assets/turnstilePatch")
    if not manifest_main:
        checks["blockers"].append('manifest missing world:MAIN')
    if not ab_ok and not chrome:
        checks["blockers"].append("chrome not found; set CHROME_PATH")
    if not ab_ok and not (venv_ok or sys_ok):
        checks["blockers"].append("DrissionPage missing; pip install -r requirements.txt")
    if not ab_ok and not display_ok:
        checks["blockers"].append("no DISPLAY/Wayland and no Xvfb; headed Chrome required")
    if ab_cli and not node:
        checks["blockers"].append("node not found; agent-browser lane needs node")
    if not ab_ok and not drission_ok and not yescaptcha:
        checks["blockers"].append("no solver lane available")

    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
