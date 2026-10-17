// Extraction indicatif + locator des messages décodés (FT8/FT4/FT2, JS8),
// pour placer les stations sur la carte (ORSAT).

const GRID_RE = /^[A-R]{2}[0-9]{2}([A-X]{2})?$/i;
const NOT_CALLS = new Set(["CQ", "DX", "QRZ", "DE", "TEST", "POTA", "SOTA", "NA", "EU", "AS", "AF", "OC", "SA"]);

export function isGrid(t) {
  return GRID_RE.test(t) && !/^RR\d\d$/i.test(t);
}

export function isCall(t) {
  const c = String(t || "").replace(/^<|>$/g, "").toUpperCase();
  return /^[A-Z0-9/]{3,12}$/.test(c) && /\d/.test(c) && /[A-Z]/.test(c) && !NOT_CALLS.has(c) && !isGrid(c);
}

const clean = (t) => String(t).replace(/^<|>$/g, "").toUpperCase();

/** « CQ F1ABC JN18 », « K1ABC F1ABC JN18 » → { call: "F1ABC", grid: "JN18" } (l'émetteur précède le locator). */
export function parseFtx(text) {
  const tok = String(text || "").trim().split(/\s+/);
  for (let i = 1; i < tok.length; i++) {
    if (isGrid(tok[i]) && isCall(tok[i - 1])) return { call: clean(tok[i - 1]), grid: tok[i].toUpperCase() };
  }
  return null;
}

/** « F1ABC: @HB HEARTBEAT JN18 » → { call: "F1ABC", grid: "JN18" }. */
export function parseJs8(text) {
  const t = String(text || "").trim();
  const m = t.match(/^([A-Z0-9/<>]+):/i);
  if (!m || !isCall(m[1])) return null;
  const grid = t.slice(m[0].length).split(/\s+/).find(isGrid);
  return grid ? { call: clean(m[1]), grid: grid.toUpperCase() } : null;
}

/** Page QRZ.com de l'indicatif (sans les suffixes /P, /M…). */
export function qrzUrl(call) {
  const parts = String(call).split("/");
  const base = parts.reduce((a, b) => (b.length > a.length ? b : a), "");
  return "https://www.qrz.com/db/" + encodeURIComponent(base);
}
