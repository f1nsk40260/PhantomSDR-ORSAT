// Annuaire PAR DÉFAUT des récepteurs partenaires de la réception en diversité (ORSAT).
// La liste réelle est fixée dans le panneau admin (rubrique « Réception en diversité ») et servie
// en /diversity.json ; celle-ci ne sert que tant que l'opérateur n'a rien enregistré.
//
// Ajouter un partenaire : une entrée de plus dans PARTNERS.
//   type : 'phantom' (PhantomSDR / NovaSDR), 'kiwi' (KiwiSDR), 'uber' (UberSDR), 'websdr' (WebSDR classique,
//          demande le relais websdr_relay.py sur ce serveur)
//   addr : l'adresse telle qu'on l'ouvre dans un navigateur (normalisée par diversityList.normalise)
//   country : code pays ISO (drapeau dessiné par FLAGS ci-dessous ; vide si inconnu)
//   lat / lon : position approximative, pour afficher la distance à ORSAT (null si inconnue)
// Le meilleur partenaire est assez loin d'ORSAT pour que les évanouissements soient indépendants
// (au moins 300 km environ), mais assez près pour entendre les mêmes stations (moins de 1500 km environ).

// Drapeaux en SVG intégré : les émojis-drapeaux ne s'affichent pas sous Windows (lettres « CH », « BE »).
// Ajouter un pays : une entrée de plus, dessin 3:2.
const BAND3V = (a, b, c) => `<rect width="1" height="2" fill="${a}"/><rect x="1" width="1" height="2" fill="${b}"/><rect x="2" width="1" height="2" fill="${c}"/>`;
const BAND3H = (a, b, c) => `<rect width="3" height=".667" fill="${a}"/><rect y=".667" width="3" height=".667" fill="${b}"/><rect y="1.333" width="3" height=".667" fill="${c}"/>`;
export const FLAGS = {
  CH: '<rect width="3" height="2" fill="#d52b1e"/><rect x="1.3" y=".4" width=".4" height="1.2" fill="#fff"/><rect x=".9" y=".8" width="1.2" height=".4" fill="#fff"/>',
  BE: BAND3V("#000", "#fdda24", "#ef3340"),
  FR: BAND3V("#002395", "#fff", "#ed2939"),
  IT: BAND3V("#009246", "#fff", "#ce2b37"),
  DE: BAND3H("#000", "#dd0000", "#ffce00"),
  NL: BAND3H("#ae1c28", "#fff", "#21468b"),
  AT: BAND3H("#c8102e", "#fff", "#c8102e"),
  LU: BAND3H("#ed2939", "#fff", "#00a1de"),
  IE: BAND3V("#169b62", "#fff", "#ff883e"),
  PL: '<rect width="3" height="1" fill="#fff"/><rect y="1" width="3" height="1" fill="#dc143c"/>',
  ES: '<rect width="3" height="2" fill="#aa151b"/><rect y=".5" width="3" height="1" fill="#f1bf00"/>',
};
export function flagSvg(cc) {
  const f = FLAGS[String(cc || "").toUpperCase()];
  return f ? `<svg viewBox="0 0 3 2" width="18" height="12" style="display:inline-block;vertical-align:-1px;border-radius:2px;box-shadow:0 0 0 1px rgba(255,255,255,.25)" aria-hidden="true">${f}</svg>` : "";
}

export const ORSAT_LOCATOR = "IN93LR";

export const PARTNERS = [
  {
    id: "rigi",
    name: "NovaSDR Rigi",
    call: "HB9RYZ",
    place: { fr: "Suisse (Rigi)", en: "Switzerland (Rigi)", es: "Suiza (Rigi)" },
    country: "CH",
    type: "phantom",
    addr: "https://novasdr.rigiremote.ch/",
    lat: 47.056, lon: 8.485,
  },
  {
    id: "heppen",
    name: "WebSDR Heppen",
    call: "ON5HB · ON3MS",
    place: { fr: "Belgique (Heppen, Limbourg)", en: "Belgium (Heppen, Limburg)", es: "Bélgica (Heppen, Limburgo)" },
    country: "BE",
    type: "uber",
    addr: "https://websdr.heppen.be/",
    lat: 51.10, lon: 5.23,
  },
  {
    id: "kiwi21051",
    name: "KiwiSDR 21051",
    call: "",
    place: { fr: "Localisation à préciser", en: "Location to be confirmed", es: "Ubicación por confirmar" },
    country: "",
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
