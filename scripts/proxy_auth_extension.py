#!/usr/bin/env python3
"""Generate a temporary Chrome extension for proxy authentication.

Prints JSON: {ok, extension_dir|null, error|null}
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path


def create_proxy_auth_extension(
    host: str, port: int, username: str, password: str, scheme: str = "http"
) -> str:
    plugin_dir = tempfile.mkdtemp(prefix="proxy_plugin_")
    manifest = {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auth",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking",
        ],
        "background": {"scripts": ["background.js"]},
    }
    host = str(host)
    username = str(username)
    password = str(password)
    scheme = str(scheme)
    background_js = f"""
var config = {{ mode: "fixed_servers",
    rules: {{ singleProxy: {{ scheme: {json.dumps(scheme)}, host: {json.dumps(host)}, port: parseInt({int(port)}) }} }} }};
chrome.proxy.settings.set({{value: config, scope: "regular"}}, function(){{}});
chrome.webRequest.onAuthRequired.addListener(
    function(details) {{ return {{ authCredentials: {{ username: {json.dumps(username)}, password: {json.dumps(password)} }} }}; }},
    {{urls: ["<all_urls>"]}}, ['blocking']
);
"""
    Path(plugin_dir, "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    Path(plugin_dir, "background.js").write_text(background_js, encoding="utf-8")
    return plugin_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--scheme", default="http")
    args = ap.parse_args()
    try:
        d = create_proxy_auth_extension(
            args.host, args.port, args.username, args.password, args.scheme
        )
        print(json.dumps({"ok": True, "extension_dir": d, "error": None}))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "extension_dir": None, "error": f"{type(exc).__name__}: {exc}"}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
