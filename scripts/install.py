#!/usr/bin/env python3
"""Create repo .venv, install DrissionPage, pack the extension, run preflight."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
REQ = ROOT / "requirements.txt"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    p3 = VENV / "bin" / "python3"
    p = VENV / "bin" / "python"
    return p3 if p3.is_file() else p


def run(cmd: list[str], env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, env=env)


def has_pip(py: Path) -> bool:
    r = subprocess.run([str(py), "-m", "pip", "--version"], capture_output=True, timeout=30)
    return r.returncode == 0


def create_venv() -> Path:
    uv = shutil.which("uv")
    if uv:
        if VENV.exists():
            shutil.rmtree(VENV)
        run([uv, "venv", str(VENV)])
        return venv_python()
    if VENV.exists() and not has_pip(venv_python()):
        shutil.rmtree(VENV)
    if not VENV.exists():
        try:
            venv.create(VENV, with_pip=True)
        except subprocess.CalledProcessError:
            if VENV.exists():
                shutil.rmtree(VENV)
            venv.create(VENV, with_pip=False)
    return venv_python()


def pip_install(py: Path) -> None:
    uv = shutil.which("uv")
    if uv:
        run([uv, "pip", "install", "--python", str(py), "-r", str(REQ)])
        return
    if has_pip(py):
        run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        run([str(py), "-m", "pip", "install", "-r", str(REQ)])
        return
    run([sys.executable, "-m", "pip", "install", "-r", str(REQ)])


def main() -> int:
    vp = create_venv()
    pip_install(vp)
    py_for_tools = vp if vp.is_file() else Path(sys.executable)
    run([str(py_for_tools), str(ROOT / "scripts" / "pack_extension.py")])
    env = os.environ.copy()
    env["TURNSTILE_VENV"] = str(VENV)
    proc = subprocess.run([str(py_for_tools), str(ROOT / "scripts" / "preflight.py")], env=env)
    print(
        json.dumps(
            {"ok": proc.returncode == 0, "venv_python": str(vp), "root": str(ROOT)},
            indent=2,
        )
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
