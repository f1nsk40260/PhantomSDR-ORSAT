// Statistiques privées de la station : la page signale au proxy quel décodeur
// tourne et quelques infos de navigateur. Ces données ne sont lisibles que
// dans le panneau admin (page « Analyse auditeurs ») — jamais publiées.
const ENDPOINT = "/__usage";

function send(ev, extra = {}) {
  try {
    const body = JSON.stringify({ ev, ...extra });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
    } else {
      fetch(ENDPOINT, { method: "POST", body, keepalive: true,
                        headers: { "Content-Type": "application/json" } }).catch(() => {});
    }
  } catch (_) { /* jamais bloquant */ }
}

let lastDecoder = null;

/** Appelé à chaque changement du décodeur actif ("none" quand aucun). */
export function reportDecoder(name) {
  const cur = name || "none";
  if (cur === lastDecoder) return;
  const prev = lastDecoder;
  lastDecoder = cur;
  if (prev === null && cur === "none") return;   // état initial : rien à dire
  send("decoder", { decoder: cur, prev: prev || "none" });
}

let helloSent = false;

/** Une fois par chargement de page. */
export function reportHello() {
  if (helloSent) return;
  helloSent = true;
  const s = window.screen || {};
  let tz = "";
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (_) {}
  send("hello", {
    lang: navigator.language || "",
    langs: (navigator.languages || []).slice(0, 4),
    tz,
    screen: `${s.width || 0}x${s.height || 0}`,
    dpr: window.devicePixelRatio || 1,
    touch: navigator.maxTouchPoints || 0,
    ref: document.referrer || "",
    path: location.pathname,
  });
}
