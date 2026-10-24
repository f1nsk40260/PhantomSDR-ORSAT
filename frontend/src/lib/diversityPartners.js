// Annuaire des récepteurs partenaires proposés pour la réception en diversité (ORSAT).
//
// Ajouter un partenaire : une entrée de plus dans PARTNERS.
//   type : 'phantom' (PhantomSDR / NovaSDR), 'kiwi' (KiwiSDR), 'uber' (UberSDR), 'websdr' (WebSDR classique,
//          demande le relais websdr_relay.py sur ce serveur)
//   addr : l'adresse telle qu'on l'ouvre dans un navigateur (normalisée par diversityList.normalise)
//   lat / lon : position approximative, pour afficher la distance à ORSAT (null si inconnue)
// Le meilleur partenaire est assez loin d'ORSAT pour que les évanouissements soient indépendants
// (au moins 300 km environ), mais assez près pour entendre les mêmes stations (moins de 1500 km environ).

export const ORSAT_LOCATOR = "IN93LR";

export const PARTNERS = [
  {
    id: "rigi",
    name: "NovaSDR Rigi",
    call: "HB9RYZ",
    place: { fr: "Suisse (Rigi)", en: "Switzerland (Rigi)", es: "Suiza (Rigi)" },
    type: "phantom",
    addr: "https://novasdr.rigiremote.ch/",
    lat: 47.056, lon: 8.485,
  },
  {
    id: "heppen",
    name: "WebSDR Heppen",
    call: "ON5HB · ON3MS",
    place: { fr: "Belgique (Heppen, Limbourg)", en: "Belgium (Heppen, Limburg)", es: "Bélgica (Heppen, Limburgo)" },
    type: "uber",
    addr: "https://websdr.heppen.be/",
    lat: 51.10, lon: 5.23,
  },
  {
    id: "kiwi21051",
    name: "KiwiSDR 21051",
    call: "",
    place: { fr: "Localisation à préciser", en: "Location to be confirmed", es: "Ubicación por confirmar" },
    type: "kiwi",
    addr: "http://21051.proxy2.kiwisdr.com:8073/",
    lat: null, lon: null,
  },
];

/** Centre du carré locator -> [lat, lon]. */
export function locatorLatLon(loc) {
  const L = String(loc || "").toUpperCase();
  if (!/^[A-R]{2}[0-9]{2}([A-X]{2})?$/.test(L)) return null;
  let lon = (L.charCodeAt(0) - 65) * 20 - 180 + Number(L[2]) * 2;
  let lat = (L.charCodeAt(1) - 65) * 10 - 90 + Number(L[3]);
  if (L.length >= 6) {
    lon += (L.charCodeAt(4) - 65) * (2 / 24) + 1 / 24;
    lat += (L.charCodeAt(5) - 65) * (1 / 24) + 1 / 48;
  } else {
    lon += 1; lat += 0.5;
  }
  return [lat, lon];
}

/** Distance orthodromique en km (null si une position manque). */
export function distanceKm(a, b) {
  if (!a || !b || a[0] == null || b[0] == null) return null;
  const r = Math.PI / 180;
  const h = Math.sin(((b[0] - a[0]) * r) / 2) ** 2
    + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(((b[1] - a[1]) * r) / 2) ** 2;
  return Math.round(2 * 6371 * Math.asin(Math.sqrt(h)));
}
