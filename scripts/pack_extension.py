#!/usr/bin/env python3
"""Zip assets/turnstilePatch for distribution. Source of truth remains the folder."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "turnstilePatch"
DST = ROOT / "assets" / "turnstilePatch.zip"
NEEDED = ("manifest.json", "script.js")


def pack() -> dict:
    missing = [n for n in NEEDED if not (SRC / n).is_file()]
    if missing:
        return {"ok": False, "error": f"missing {missing}", "src": str(SRC)}
    DST.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DST, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in NEEDED:
            zf.write(SRC / name, name)
    names = zipfile.ZipFile(DST).namelist()
    return {"ok": True, "zip": str(DST), "files": names, "bytes": DST.stat().st_size}


if __name__ == "__main__":
    print(json.dumps(pack(), ensure_ascii=False, indent=2))
