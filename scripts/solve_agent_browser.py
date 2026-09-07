#!/usr/bin/env python3
"""Cloudflare Turnstile + interstitial solver for agent-browser. JSON only.

ok:true for widget token length > 20, or waiting-room pass (cf_clearance / origin).
Iframe clicks go to Chrome CDP, never the AB shim (19222).
Interstitial uses Page.bringToFront (CF JS ignores hidden tabs).
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
    if (plan.calls) {
      out.calls = {};
      for (const c of plan.calls) {
        out.calls[c.as || c.method] = await call(c.method, c.params || {});
      }
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
    token = extra.get("token")
    clearance = int(extra.get("clearanceLen") or 0)
    token_ok = bool(token) and len(str(token)) > 20
    kind = str(extra.get("kind") or "")
    passed = token_ok or clearance > 20 or kind in ("cf_passed", "cf_clearance", "both")
    if ok and not passed:
        payload = {"ok": False, "error": extra.get("error") or "no_token_or_clearance", **extra}
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


PAGE_META_JS = """(() => {
  const title = document.title || '';
  const href = location.href || '';
  const text = ((document.body && document.body.innerText) || '').slice(0, 500);
  const html = (document.documentElement.outerHTML || '').slice(0, 2500);
  const hasWidget = !!(
    document.querySelector('[name=cf-turnstile-response], .cf-turnstile, [data-sitekey]')
  );
  return { title, href, text, html, hasWidget };
})()"""

CHALLENGE_TITLE = (
    "just a moment",
    "请稍候",
    "attention required",
    "checking your browser",
    "verify you are human",
    "moment...",
)


def host_key(url: str) -> str:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_challenge_meta(meta: dict[str, Any] | None) -> bool:
    if not isinstance(meta, dict):
        return False
    title = str(meta.get("title") or "").strip().lower()
    html = str(meta.get("html") or "").lower()
    text = str(meta.get("text") or "").lower()
    if any(s in title for s in CHALLENGE_TITLE):
        return True
    blob = html + " " + text
    return any(
        s in blob
        for s in (
            "cf-browser-verification",
            "cf-challenge-running",
            "cf-mitigated",
            "cdn-cgi/challenge-platform",
            "challenges.cloudflare.com",
        )
    ) and ("请稍候" in title or "just a moment" in title or "challenge-platform" in html)


def page_meta(port: int, target_id: str) -> dict[str, Any]:
    try:
        val = page_eval(port, target_id, PAGE_META_JS)
    except Exception:
        return {}
    return val if isinstance(val, dict) else {}


def cdp_calls(port: int, target_id: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
    ws = tab_ws(port, target_id)
    res = node_cdp(ws, {"calls": calls})
    if not res.get("ok"):
        raise RuntimeError(res.get("error") or "cdp_calls_failed")
    return res.get("calls") or {}


def host_cookies(port: int, target_id: str, host: str) -> list[dict[str, Any]]:
    host = (host or "").lower().lstrip(".")
    urls = [f"https://{host}/", f"https://www.{host}/"]
    try:
        calls = cdp_calls(
            port,
            target_id,
            [
                {"method": "Network.enable", "as": "enable"},
                {"method": "Network.getCookies", "as": "cookies", "params": {"urls": urls}},
            ],
        )
    except Exception:
        return []
    return (calls.get("cookies") or {}).get("cookies") or []


def clearance_cookie(port: int, target_id: str, host: str) -> dict[str, Any] | None:
    host = (host or "").lower().lstrip(".")
    best = None
    for c in host_cookies(port, target_id, host):
        if c.get("name") != "cf_clearance":
            continue
        val = str(c.get("value") or "")
        if len(val) > 20:
            best = {"domain": c.get("domain"), "len": len(val), "httpOnly": c.get("httpOnly")}
    return best


def drop_clearance(port: int, target_id: str, host: str) -> int:
    """Delete CF cookies for host. Returns how many deletes were issued."""
    host = (host or "").lower().lstrip(".")
    cookies = host_cookies(port, target_id, host)
    deletes: list[dict[str, Any]] = [{"method": "Network.enable", "as": "enable"}]
    n = 0
    for c in cookies:
        name = str(c.get("name") or "")
        if name not in {"cf_clearance", "__cf_bm", "__cf_ob"} and not name.startswith("cf_chl"):
            continue
        n += 1
        deletes.append(
            {
                "method": "Network.deleteCookies",
                "as": f"d{n}",
                "params": {
                    "name": name,
                    "domain": c.get("domain"),
                    "path": c.get("path") or "/",
                },
            }
        )
    if n:
        cdp_calls(port, target_id, deletes)
    return n


VIS_SPOOF_JS = """(() => {
  try {
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
    Object.defineProperty(document, 'visibilityState', {configurable: true, get: () => 'visible'});
    document.dispatchEvent(new Event('visibilitychange'));
  } catch (e) {}
  return document.visibilityState;
})()"""


def spoof_visible(port: int, target_id: str) -> None:
    try:
        page_eval(port, target_id, VIS_SPOOF_JS)
    except Exception:
        pass
    for frame in cf_iframes(port, target_id):
        try:
            node_cdp(frame["webSocketDebuggerUrl"], {"eval": VIS_SPOOF_JS})
        except Exception:
            pass


def solve_interstitial(port: int, target_id: str, host: str, timeout_s: float) -> dict[str, Any]:
    """Wait out CF JS / managed challenge until the waiting-room title is gone."""
    steps: list[dict[str, Any]] = []
    try:
        cdp_calls(port, target_id, [{"method": "Page.bringToFront", "as": "front"}])
        steps.append({"step": "bringToFront"})
    except Exception as exc:
        steps.append({"step": "bringToFront", "error": str(exc)[:80]})
    spoof_visible(port, target_id)
    time.sleep(0.5)
    deadline = time.time() + max(8.0, timeout_s)
    last_click = 0.0
    while time.time() < deadline:
        meta = page_meta(port, target_id)
        cl = clearance_cookie(port, target_id, host)
        challenge = is_challenge_meta(meta)
        title = str(meta.get("title") or "").strip()
        steps.append(
            {
                "step": "poll",
                "title": title[:40],
                "challenge": challenge,
                "clearanceLen": (cl or {}).get("len") or 0,
            }
        )
        if not challenge and title and title not in ("请稍候…", "Just a moment..."):
            return {"ok": True, "clearance": cl, "meta": meta, "steps": steps[-8:]}
        now = time.time()
        if last_click == 0.0 or now - last_click >= 1.4:
            spoof_visible(port, target_id)
            hit = click_cf_iframe(port, target_id)
            steps.append({"step": "challenge_click", **{k: hit.get(k) for k in ("ok", "patched", "error", "x", "y")}})
            last_click = now
        time.sleep(0.35)
    meta = page_meta(port, target_id)
    cl = clearance_cookie(port, target_id, host)
    passed = not is_challenge_meta(meta)
    return {
        "ok": passed,
        "clearance": cl,
        "meta": meta,
        "steps": steps[-12:],
        "error": None if passed else "cf_interstitial_failed",
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
        data = go.get("data") or {}
        target_id = data.get("targetId") or (data.get("lease") or {}).get("targetId")
        port = (data.get("lease") or {}).get("port") or runtime.DEFAULT_AB_SHIM_PORT
        summary = str(go.get("summary") or "")
        title = str(data.get("title") or "")
        challenge_go = (not go.get("ok")) and bool(target_id) and (
            "http_403" in summary
            or "http_503" in summary
            or "http_429" in summary
            or any(s in title.lower() for s in CHALLENGE_TITLE)
        )
        if not go.get("ok") and not challenge_go:
            raise RuntimeError(f"go failed: {summary or go.get('failure') or go}")
        if not target_id:
            raise RuntimeError("go returned no targetId")
        return {
            "targetId": target_id,
            "abPort": int(port),
            "url": data.get("url") or url,
            "challengeGo": challenge_go,
            "goSummary": summary,
        }
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
            return last
        time.sleep(0.25)
    return last if isinstance(last, dict) else None


def solve(port: int, target_id: str, timeout_s: float, url: str | None = None) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    host = host_key(url or page_meta(port, target_id).get("href") or "")
    meta0 = page_meta(port, target_id)
    if is_challenge_meta(meta0) or (meta0.get("title") or "").strip() in ("请稍候…", "Just a moment..."):
        inter = solve_interstitial(port, target_id, host, timeout_s)
        steps.extend(inter.get("steps") or [])
        cl = inter.get("clearance")
        if not inter.get("ok"):
            raise RuntimeError(inter.get("error") or "cf_interstitial_failed")
        token = read_token(port, target_id)
        out = {
            "kind": "cf_clearance",
            "clearance": cl,
            "token": token if len(token) > 20 else "",
            "steps": steps,
        }
        if len(token) > 20:
            out["kind"] = "both"
        return out

    token = read_token(port, target_id)
    if len(token) > 20:
        return {"kind": "turnstile_token", "token": token, "steps": [{"step": "existing", "tokenLen": len(token)}]}

    host_box = wait_widget(port, target_id, min(18.0 if (meta0.get("hasWidget")) else 3.0, timeout_s))
    steps.append({"step": "wait_widget", "host": host_box})
    if not host_box or not host_box.get("found"):
        cl = clearance_cookie(port, target_id, host)
        meta2 = page_meta(port, target_id)
        if cl:
            return {"kind": "cf_clearance", "clearance": cl, "token": "", "steps": steps}
        if not is_challenge_meta(meta2):
            return {
                "kind": "cf_passed",
                "clearance": cl,
                "token": "",
                "steps": steps,
                "title": (meta2.get("title") or "")[:80],
            }
        raise RuntimeError("turnstile host not found")

    auto_until = time.time() + 1.2
    while time.time() < auto_until:
        token = read_token(port, target_id)
        if len(token) > 20:
            return {"token": token, "kind": "turnstile_token", "steps": steps + [{"step": "auto", "tokenLen": len(token)}]}
        time.sleep(0.2)

    deadline = time.time() + timeout_s
    attempt = 0
    while time.time() < deadline and attempt < 4:
        attempt += 1
        token = read_token(port, target_id)
        if len(token) > 20:
            return {"token": token, "kind": "turnstile_token", "steps": steps, "attempts": attempt}

        iframe_click = click_cf_iframe(port, target_id)
        steps.append({"step": f"iframe{attempt}", **iframe_click})
        for _ in range(12):
            token = read_token(port, target_id)
            if len(token) > 20:
                return {"token": token, "kind": "turnstile_token", "steps": steps, "attempts": attempt}
            time.sleep(0.25)

        try:
            host_box = page_eval(port, target_id, HOST_JS) or {}
        except Exception:
            host_box = {}
        if host_box.get("found") and float(host_box.get("w") or 0) >= 50:
            x = float(host_box["x"]) + 28.0
            y = float(host_box["y"]) + float(host_box.get("h") or 65) / 2.0
            page_click = click_xy(port, target_id, x, y)
            steps.append({"step": f"page{attempt}", "x": x, "y": y, "ok": page_click.get("ok"), "error": page_click.get("error")})
            for _ in range(12):
                token = read_token(port, target_id)
                if len(token) > 20:
                    return {"token": token, "kind": "turnstile_token", "steps": steps, "attempts": attempt}
                time.sleep(0.25)

    raise RuntimeError("turnstile token timeout after click")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Solve Cloudflare Turnstile on current AB page")
    p.add_argument("--url", default=None, help="Navigate first, then solve")
    p.add_argument("--target-id", default=None)
    p.add_argument("--chrome-port", type=int, default=None)
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--fresh", action="store_true", help="Drop cf_clearance for this host then reload (force interstitial)")
    args = p.parse_args(argv)

    try:
        if args.target_id and args.chrome_port:
            bind = {"targetId": args.target_id, "abPort": args.chrome_port, "url": args.url}
            chrome_port = args.chrome_port
        else:
            bind = resolve_binding(args.url)
            chrome_port = args.chrome_port or chrome_port_for(int(bind["abPort"]))
        try:
            json_list(chrome_port)
        except URLError as exc:
            return emit(False, error=f"chrome_cdp_unreachable:{chrome_port}:{exc}", binding=bind)

        tid = bind["targetId"]
        url = bind.get("url") or args.url or ""
        if args.fresh and url:
            n = drop_clearance(chrome_port, tid, host_key(url))
            bind["droppedCookies"] = n
            cdp_calls(
                chrome_port,
                tid,
                [{"method": "Page.navigate", "params": {"url": url}, "as": "nav"}],
            )
            time.sleep(0.8)
            host = host_key(url)
            for tab in json_list(chrome_port):
                title = str(tab.get("title") or "")
                tab_url = str(tab.get("url") or "")
                if tab.get("type") != "page":
                    continue
                if host not in tab_url:
                    continue
                if any(s in title.lower() or s in title for s in ("请稍候", "Just a moment", "just a moment")):
                    tid = tab["id"]
                    bind["targetId"] = tid
                    bind["retargeted"] = True
                    break
            bind["titleAfterFresh"] = (page_meta(chrome_port, tid).get("title") or title or "")[:40]

        result = solve(chrome_port, tid, args.timeout, url=url)
        token = str(result.get("token") or "")
        cl = result.get("clearance") or {}
        return emit(
            True,
            token=token,
            tokenLen=len(token),
            tokenPrefix=token[:24] if token else "",
            kind=result.get("kind") or "turnstile_token",
            clearanceLen=int(cl.get("len") or 0),
            clearanceDomain=cl.get("domain"),
            chromePort=chrome_port,
            binding=bind,
            attempts=result.get("attempts"),
            steps=result.get("steps"),
        )
    except Exception as exc:
        return emit(False, error=f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
