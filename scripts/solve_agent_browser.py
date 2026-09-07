#!/usr/bin/env python3
"""Generic agent-browser Turnstile solver. JSON only. No GUI.

ok:true only when token length > 20. Never chrome-show / bringToFront.
Iframe clicks go to Chrome CDP (19221), never the AB shim (19222).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import URLError

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import runtime  # noqa: E402

TOKEN_JS = """(() => {
  try { const t = turnstile.getResponse(); if (t && String(t).length > 20) return String(t); } catch (e) {}
  const v = (document.querySelector('[name=cf-turnstile-response]') || {}).value || '';
  return String(v || '');
})()"""

HOST_JS = """(() => {
  const inp = document.querySelector('[name=cf-turnstile-response]');
  const box = document.querySelector('.cf-turnstile, [data-sitekey]');
  let ts = { has: typeof turnstile !== 'undefined', resp: '' };
  try { ts.resp = (typeof turnstile !== 'undefined' && turnstile.getResponse) ? String(turnstile.getResponse() || '') : ''; }
  catch (e) { ts.err = String(e); }
  const host = (inp && (inp.closest('.cf-turnstile') || inp.closest('div.w-full') || inp.parentElement))
    || box;
  const sitekey = (box && box.getAttribute('data-sitekey')) || (host && host.getAttribute && host.getAttribute('data-sitekey'));
  if (!host) {
    return { found: false, href: location.href, sitekey, ts, vis: document.visibilityState };
  }
  const r = host.getBoundingClientRect();
  return {
    found: r.width >= 50 || !!(inp && inp.value),
    href: location.href,
    x: r.x,
    y: r.y,
    w: r.width,
    h: r.height,
    len: (inp && inp.value || '').length,
    sitekey,
    ts,
    vis: document.visibilityState,
  };
})()"""

NODE_RUNNER = r"""
const ws = new WebSocket(process.argv[1]);
const plan = JSON.parse(process.argv[2]);
let id = 0;
const pending = new Map();
function call(method, params={}, timeoutMs=8000) {
  const reqId = ++id;
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => { pending.delete(reqId); reject(new Error('timeout ' + method)); }, timeoutMs);
    pending.set(reqId, { resolve: v => { clearTimeout(t); resolve(v); }, reject: e => { clearTimeout(t); reject(e); } });
    ws.send(JSON.stringify({ id: reqId, method, params }));
  });
}
ws.addEventListener('message', ev => {
  let msg; try { msg = JSON.parse(ev.data); } catch { return; }
  if (!msg.id || !pending.has(msg.id)) return;
  const { resolve, reject } = pending.get(msg.id);
  pending.delete(msg.id);
  if (msg.error) reject(new Error(JSON.stringify(msg.error)));
  else resolve(msg.result || {});
});
async function click(x, y) {
  const seq = [
    ['mouseMoved', 0, 'none', 0],
    ['mousePressed', 1, 'left', 1],
    ['mouseReleased', 0, 'left', 1],
  ];
  for (const [type, buttons, button, clickCount] of seq) {
    await call('Input.dispatchMouseEvent', { type, x, y, button, buttons, clickCount, pointerType: 'mouse' });
    await new Promise(r => setTimeout(r, 16));
  }
}
ws.addEventListener('open', async () => {
  const out = { ok: false };
  try {
    if (plan.eval) {
      const ev = await call('Runtime.evaluate', { expression: plan.eval, returnByValue: true, awaitPromise: false });
      if (ev.exceptionDetails) throw new Error(JSON.stringify(ev.exceptionDetails));
      out.value = (ev.result || {}).value;
    }
    if (plan.click) {
      await click(Number(plan.click.x), Number(plan.click.y));
      out.clicked = { x: Number(plan.click.x), y: Number(plan.click.y) };
    }
    out.ok = true;
  } catch (e) {
    out.error = String(e);
  }
  console.log(JSON.stringify(out));
  ws.close();
  process.exit(out.ok ? 0 : 1);
});
setTimeout(() => { console.log(JSON.stringify({ ok: false, error: 'open-timeout' })); process.exit(1); }, 12000);
"""


def emit(ok: bool, **extra: Any) -> int:
    payload = {"ok": ok, **extra}
    if ok and extra.get("token") and len(str(extra["token"])) <= 20:
        payload = {"ok": False, "error": "token_too_short", **extra}
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def run_ab(args: list[str], timeout: int = 60) -> dict[str, Any]:
    cli = runtime.agent_browser_cli()
    if not cli:
        raise RuntimeError("agent-browser-cli not on PATH")
    proc = subprocess.run(
        [cli, *args, "--compact"],
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    raw = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    try:
        return json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"ab failed rc={proc.returncode}: {raw[:500]}") from exc


def json_list(port: int) -> list[dict[str, Any]]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as resp:
        data = json.loads(resp.read())
    return data if isinstance(data, list) else []


def chrome_port_for(ab_port: int) -> int:
    return runtime.chrome_port_for(ab_port)


def node_cdp(ws_url: str, plan: dict[str, Any], timeout: float = 14.0) -> dict[str, Any]:
    node = runtime.node_bin()
    if not node:
        raise RuntimeError("node not found")
    proc = subprocess.run(
        [node, "-e", NODE_RUNNER, ws_url, json.dumps(plan)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    raw = (proc.stdout or "").strip()
    try:
        out = json.loads(raw) if raw else {"ok": False, "error": "empty_node_output"}
    except Exception:
        out = {"ok": False, "error": f"node_json:{raw[:300]}", "stderr": (proc.stderr or "")[:200]}
    if proc.returncode != 0 and out.get("ok"):
        out["ok"] = False
        out.setdefault("error", f"node_rc={proc.returncode}")
    return out


def tab_ws(port: int, target_id: str) -> str:
    for tab in json_list(port):
        if tab.get("id") == target_id and tab.get("webSocketDebuggerUrl"):
            return str(tab["webSocketDebuggerUrl"]).replace(
            f":{runtime.DEFAULT_AB_SHIM_PORT}/", f":{port}/"
        )
    raise RuntimeError(f"target not on chrome port {port}: {target_id}")


def cf_iframes(port: int, page_id: str) -> list[dict[str, Any]]:
    out = []
    for tab in json_list(port):
        if tab.get("type") != "iframe":
            continue
        if tab.get("parentId") != page_id:
            continue
        url = tab.get("url") or ""
        if "challenges.cloudflare.com" in url or "turnstile" in url:
            ws = tab.get("webSocketDebuggerUrl")
            if ws:
                tab = dict(tab)
                tab["webSocketDebuggerUrl"] = str(ws).replace(
                    f":{runtime.DEFAULT_AB_SHIM_PORT}/", f":{port}/"
                )
                out.append(tab)
    return out


def page_eval(port: int, target_id: str, expression: str) -> Any:
    ws = tab_ws(port, target_id)
    res = node_cdp(ws, {"eval": expression})
    if not res.get("ok"):
        raise RuntimeError(res.get("error") or "page_eval_failed")
    return res.get("value")


def click_xy(port: int, target_id: str, x: float, y: float) -> dict[str, Any]:
    ws = tab_ws(port, target_id)
    return node_cdp(ws, {"click": {"x": x, "y": y}})


def click_cf_iframe(port: int, page_id: str) -> dict[str, Any]:
    frames = cf_iframes(port, page_id)
    if not frames:
        return {"ok": False, "error": "cf_iframe_not_found"}
    frame = frames[-1]
    ws = frame["webSocketDebuggerUrl"]
    probe = node_cdp(
        ws,
        {
            "eval": "({patched:!!window.__ts_patch, inner:[innerWidth,innerHeight], href:location.href, vis:document.visibilityState})"
        },
    )
    if not probe.get("ok"):
        return {"ok": False, "error": probe.get("error") or "iframe_eval_failed", "frameId": frame.get("id")}
    info = probe.get("value") or {}
    inner = info.get("inner") or [300, 65]
    h = float(inner[1] or 65)
    x, y = 24.0, max(h, 20.0) / 2.0
    clicked = node_cdp(ws, {"click": {"x": x, "y": y}})
    return {
        "ok": bool(clicked.get("ok")),
        "frameId": frame.get("id"),
        "x": x,
        "y": y,
        "patched": bool(info.get("patched")),
        "inner": inner,
        "error": clicked.get("error"),
    }


def read_token(port: int, target_id: str) -> str:
    try:
        val = page_eval(port, target_id, TOKEN_JS)
    except Exception:
        return ""
    return str(val or "")


def resolve_binding(url: str | None) -> dict[str, Any]:
    if url:
        go = run_ab(["go", url], timeout=90)
        if not go.get("ok"):
            raise RuntimeError(f"go failed: {go.get('summary') or go.get('failure') or go}")
        data = go.get("data") or {}
        target_id = data.get("targetId") or (data.get("lease") or {}).get("targetId")
        port = (data.get("lease") or {}).get("port") or runtime.DEFAULT_AB_SHIM_PORT
        if not target_id:
            raise RuntimeError("go returned no targetId")
        return {"targetId": target_id, "abPort": int(port), "url": data.get("url") or url}
    cur = run_ab(["target", "current"], timeout=20)
    if not cur.get("ok"):
        raise RuntimeError(f"no current AB target: {cur.get('summary') or cur.get('failure')}")
    data = cur.get("data") or {}
    target = data.get("target") or {}
    target_id = data.get("targetId") or target.get("id")
    if not target_id:
        raise RuntimeError("session_has_no_tab_lease")
    return {
        "targetId": target_id,
        "abPort": int(data.get("port") or runtime.DEFAULT_AB_SHIM_PORT),
        "url": target.get("url"),
    }


def wait_widget(port: int, target_id: str, timeout_s: float) -> dict[str, Any] | None:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            last = page_eval(port, target_id, HOST_JS)
        except Exception:
            last = None
        if isinstance(last, dict) and last.get("found") and float(last.get("w") or 0) >= 50:
            tok = last.get("ts") or {}
            if last.get("len", 0) > 20 or len(str(tok.get("resp") or "")) > 20:
                return last
            return last
            time.sleep(0.25)
    return last if isinstance(last, dict) else None


def solve(port: int, target_id: str, timeout_s: float) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    token = read_token(port, target_id)
    if len(token) > 20:
        return {"token": token, "steps": [{"step": "existing", "tokenLen": len(token)}]}

    host = wait_widget(port, target_id, min(18.0, timeout_s))
    steps.append({"step": "wait_widget", "host": host})
    if not host or not host.get("found"):
        raise RuntimeError("turnstile host not found")

    auto_until = time.time() + 1.2
    while time.time() < auto_until:
        token = read_token(port, target_id)
        if len(token) > 20:
            return {"token": token, "steps": steps + [{"step": "auto", "tokenLen": len(token)}]}
        time.sleep(0.2)

    deadline = time.time() + timeout_s
    attempt = 0
    while time.time() < deadline and attempt < 4:
        attempt += 1
        token = read_token(port, target_id)
        if len(token) > 20:
            return {"token": token, "steps": steps, "attempts": attempt}

        iframe_click = click_cf_iframe(port, target_id)
        steps.append({"step": f"iframe{attempt}", **iframe_click})
        for _ in range(12):
            token = read_token(port, target_id)
            if len(token) > 20:
                return {"token": token, "steps": steps, "attempts": attempt}
            time.sleep(0.25)

        try:
            host = page_eval(port, target_id, HOST_JS) or {}
        except Exception:
            host = {}
        if host.get("found") and float(host.get("w") or 0) >= 50:
            x = float(host["x"]) + 28.0
            y = float(host["y"]) + float(host.get("h") or 65) / 2.0
            page_click = click_xy(port, target_id, x, y)
            steps.append({"step": f"page{attempt}", "x": x, "y": y, "ok": page_click.get("ok"), "error": page_click.get("error")})
            for _ in range(12):
                token = read_token(port, target_id)
                if len(token) > 20:
                    return {"token": token, "steps": steps, "attempts": attempt}
                time.sleep(0.25)

    raise RuntimeError("turnstile token timeout after click")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Solve Cloudflare Turnstile on current AB page")
    p.add_argument("--url", default=None, help="Navigate first, then solve")
    p.add_argument("--target-id", default=None)
    p.add_argument("--chrome-port", type=int, default=None)
    p.add_argument("--timeout", type=float, default=28.0)
    args = p.parse_args(argv)

    try:
        if args.target_id and args.chrome_port:
            bind = {"targetId": args.target_id, "abPort": args.chrome_port, "url": None}
            chrome_port = args.chrome_port
        else:
            bind = resolve_binding(args.url)
            chrome_port = args.chrome_port or chrome_port_for(int(bind["abPort"]))
        # Probe Chrome CDP before clicking. Shim 19222 must not receive iframe WS.
        try:
            json_list(chrome_port)
        except URLError as exc:
            return emit(False, error=f"chrome_cdp_unreachable:{chrome_port}:{exc}", binding=bind)

        result = solve(chrome_port, bind["targetId"], args.timeout)
        token = str(result["token"])
        return emit(
            True,
            token=token,
            tokenLen=len(token),
            tokenPrefix=token[:24],
            chromePort=chrome_port,
            binding=bind,
            attempts=result.get("attempts"),
            steps=result.get("steps"),
        )
    except Exception as exc:
        return emit(False, error=f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
