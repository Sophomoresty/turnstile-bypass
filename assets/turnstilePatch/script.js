(() => {
  try {
    const h = String(location.hostname || "");
    if (!h.includes("challenges.cloudflare.com")) return;
  } catch (e) {
    return;
  }
  if (window.__ts_patch) return;
  window.__ts_patch = 1;
  const r = (a, b) => Math.floor(Math.random() * (b - a + 1)) + a;
  // Root cause: CDP Input.dispatchMouseEvent sets screenX/Y == clientX/Y
  // (chromium #40280325). Turnstile fingerprint checks that delta.
  const patch = (proto) => {
    try {
      Object.defineProperty(proto, "screenX", {
        get: function () {
          return (this.clientX || 0) + r(40, 180);
        },
        configurable: true,
      });
      Object.defineProperty(proto, "screenY", {
        get: function () {
          return (this.clientY || 0) + r(60, 220);
        },
        configurable: true,
      });
    } catch (e) {}
  };
  patch(MouseEvent.prototype);
  try {
    patch(PointerEvent.prototype);
  } catch (e) {}
})();
