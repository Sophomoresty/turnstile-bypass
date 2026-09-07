#!/usr/bin/env python3
"""OS-agnostic paths for Chrome, venv, agent-browser, and Node."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PATCH_DIR = SKILL_DIR / "assets" / "turnstilePatch"
PATCH_ZIP = SKILL_DIR / "assets" / "turnstilePatch.zip"

# AB managed Chrome CDP vs shim. Override if your bridge uses other ports.
DEFAULT_AB_SHIM_PORT = int(os.environ.get("TURNSTILE_AB_SHIM_PORT") or "19222")
DEFAULT_AB_CHROME_PORT = int(os.environ.get("TURNSTILE_AB_CHROME_PORT") or "19221")


def is_windows() -> bool:
    return sys.platform == "win32"


def is_darwin() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if is_windows() and not name.lower().endswith((".exe", ".cmd", ".bat")):
        for ext in (".cmd", ".exe", ".bat"):
            found = shutil.which(name + ext)
            if found:
                return found
    return None


def venv_pythons() -> list[Path]:
    home = Path.home()
    names = ("python.exe", "python3.exe", "python", "python3")
    roots = [
        home / ".local" / "share" / "turnstile-bypass-venv",
        SKILL_DIR / ".venv",
        SKILL_DIR / "venv",
    ]
    extra = os.environ.get("TURNSTILE_VENV")
    if extra:
        roots.insert(0, Path(extra))
    out: list[Path] = []
    for root in roots:
        for sub in ("Scripts", "bin"):
            for name in names:
                cand = root / sub / name
                if cand.is_file():
                    out.append(cand)
    return out


def venv_python() -> Path | None:
    found = venv_pythons()
    return found[0] if found else None


def chrome_candidates() -> list[Path]:
    env = os.environ.get("CHROME_PATH") or os.environ.get("TURNSTILE_CHROME_PATH")
    out: list[Path] = []
    if env:
        out.append(Path(env))
    home = Path.home()
    if is_darwin():
        out.extend(
            [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                home / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                home / "Applications/AB Test Chrome.app/Contents/MacOS/Google Chrome",
                Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            ]
        )
    if is_windows() or Path("/mnt/c/Windows").exists():
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        out.extend(
            [
                Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(pf86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            ]
        )
        if local:
            out.append(Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe")
        out.append(Path("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"))
        out.append(Path("/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"))
    if is_linux():
        for name in (
            "google-chrome-stable",
            "google-chrome",
            "chromium-browser",
            "chromium",
            "chrome",
        ):
            p = which(name)
            if p:
                out.append(Path(p))
    else:
        for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "chrome"):
            p = which(name)
            if p:
                out.append(Path(p))
    # de-dupe while keeping order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def find_chrome() -> str | None:
    for cand in chrome_candidates():
        if cand.is_file():
            return str(cand)
    return None


def agent_browser_cli() -> str | None:
    return which("agent-browser-cli")


def node_bin() -> str | None:
    return which("node")


def chrome_port_for(ab_port: int) -> int:
    """Managed AB: shim 19222, real Chrome CDP 19221. Instances are Chrome itself."""
    env = os.environ.get("TURNSTILE_AB_CHROME_PORT")
    if env and str(ab_port) == str(DEFAULT_AB_SHIM_PORT):
        return int(env)
    if int(ab_port) == DEFAULT_AB_SHIM_PORT:
        return DEFAULT_AB_CHROME_PORT
    return int(ab_port)


def has_display() -> bool:
    if is_darwin() or is_windows():
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def has_drissionpage(py: Path | None = None) -> bool:
    import subprocess

    exe = str(py) if py and py.is_file() else sys.executable
    r = subprocess.run(
        [exe, "-c", "import DrissionPage"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return r.returncode == 0


def solver_python() -> str:
    """Python that can import DrissionPage: current interp, then repo/user venv."""
    if has_drissionpage(Path(sys.executable)):
        return sys.executable
    venv = venv_python()
    if venv and has_drissionpage(venv):
        return str(venv)
    return sys.executable


def patch_ok() -> bool:
    return (PATCH_DIR / "manifest.json").is_file() and (PATCH_DIR / "script.js").is_file()


def ensure_patch() -> bool:
    if patch_ok():
        return True
    if not PATCH_ZIP.is_file():
        return False
    import zipfile

    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PATCH_ZIP) as zf:
        zf.extractall(PATCH_DIR)
    return patch_ok()


def manifest_world_main() -> bool:
    if not patch_ok():
        return False
    text = (PATCH_DIR / "manifest.json").read_text(encoding="utf-8")
    return '"world"' in text and "MAIN" in text
