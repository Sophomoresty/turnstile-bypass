#!/usr/bin/env python3
"""HTTP front-end for scripts/solve.py (--url)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from flask import Flask, Response, request

ROOT = Path(__file__).resolve().parent
SCRIPT = Path(os.environ.get("CLI_SCRIPT", ROOT / "scripts" / "solve.py"))
PYTHON = os.environ.get("CLI_PYTHON", "python3")
TIMEOUT = int(os.environ.get("CLI_TIMEOUT", "90"))

app = Flask(__name__)


def _url_from_request() -> str | None:
    if request.is_json:
        body = request.get_json(silent=True) or {}
        if isinstance(body.get("url"), str) and body["url"].strip():
            return body["url"].strip()
    for src in (request.args, request.form):
        value = src.get("url")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _json_response(payload: str, status: int) -> Response:
    return Response(payload, status=status, mimetype="application/json")


@app.post("/solve")
def solve():
    url = _url_from_request()
    if not url:
        return {"error": "missing url"}, 400
    if not url.startswith(("http://", "https://")):
        return {"error": "url must be http(s)"}, 400

    try:
        proc = subprocess.run(
            [PYTHON, str(SCRIPT), "--url", url],
            cwd=ROOT,
            env=os.environ,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"error": "script timed out", "timeout": TIMEOUT}, 504

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "")[-4000:]

    if stdout:
        try:
            json.loads(stdout)
            status = 200 if proc.returncode == 0 else 500
            return _json_response(stdout, status)
        except json.JSONDecodeError:
            pass

    if proc.returncode != 0:
        return {
            "error": "script failed",
            "returncode": proc.returncode,
            "stdout": stdout[-4000:],
            "stderr": stderr,
        }, 500

    return {
        "error": "script did not print JSON",
        "stdout": stdout[-4000:],
        "stderr": stderr,
    }, 502


@app.get("/test")
def test():
    return {"ok": True}
