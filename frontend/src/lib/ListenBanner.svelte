<script>
  // Bandeau « Indice de performance ORSAT » : note 0–100 par bande calculée par le carnet ORSAT-LOG
  // (prévision sur toutes les distances : ionosondes × diagramme NEC de la loop, corrigée par la mesure
  // réelle de la chute d'eau) et zone où le récepteur entend le mieux.
  // Source : /log/api/public/listenbanner (même serveur, sans connexion). Rafraîchi toutes les 5 min.
  // Si le carnet ne répond pas, le bandeau ne s'affiche pas : aucun effet sur le WebSDR.
  import { onMount, onDestroy } from "svelte";
  import { lang } from "./i18n.js";      // langue choisie dans l'en-tête du WebSDR (FR / EN / ES)

  export let freqKhz = null;            // fréquence écoutée (kHz) : sa bande est mise en évidence

  const BANDS = [
    ["160m", 1810, 2000], ["80m", 3500, 3800], ["60m", 5351, 5367], ["40m", 7000, 7200],
    ["30m", 10100, 10150], ["20m", 14000, 14350], ["17m", 18068, 18168], ["15m", 21000, 21450],
    ["12m", 24890, 24990], ["10m", 28000, 29700],
  ];
  let data = null;
  let timer;

  async function load() {
    try {
      const r = await fetch("/log/api/public/listenbanner?radius=800", { cache: "no-store" });
      const d = r.ok ? await r.json() : null;
      data = d && d.ok ? d : null;
    } catch (e) {
      data = null;
    }
  }
  onMount(() => { load(); timer = setInterval(load, 5 * 60 * 1000); });
  onDestroy(() => clearInterval(timer));

  // bande de la fréquence écoutée ; hors bande amateur : la plus proche (en échelle log), marquée « ≈ »
  $: f = parseFloat(freqKhz);
  $: inBand = BANDS.find(([, lo, hi]) => f >= lo && f <= hi);
  $: near = !f ? null : inBand ? inBand[0]
    : BANDS.reduce((a, b) => (Math.abs(Math.log(f / ((b[1] + b[2]) / 2))) < Math.abs(Math.log(f / ((a[1] + a[2]) / 2))) ? b : a))[0];

  // Textes du bandeau dans les trois langues du WebSDR (le traducteur automatique de la page ne peut pas
  // traduire des phrases contenant des chiffres qui changent : le bandeau porte data-no-i18n).
  const T = {
    fr: {
      ipTitle: "Indice de performance", ipShort: "IP",
      ipTip: (w) => `Indice de performance du récepteur ORSAT, bande par bande (0 à 100, calcul de ${w}).\nPrévision sur toutes les distances (ionosondes mesurées × diagramme de la loop), corrigée par ce qu'ORSAT mesure réellement sur la chute d'eau.\nLettres : zone où ORSAT entend le mieux. Clic : carte détaillée.`,
      ipVerdict: { l5: "Excellent", l4: "Bon", l3: "Correct", l2: "Moyen", l1: "Faible", l0: "Fermé", na: "Pas de données" },
      zoneShort: { loc: "Loc", reg: "Rég", eu: "EU", dx: "DX" },
      zoneLong: { loc: "local (≤ 300 km)", reg: "régional (300–900 km)", eu: "Europe (900–2500 km)", dx: "DX (au-delà de 2500 km)" },
      bestZone: "meilleure portée", noZone: "aucune zone vraiment bonne",
      predWord: "prévision", measWord: "mesure", noMeas: "pas de mesure récente",
      byDist: "Prévision par distance", measErr: "Mesure réelle indisponible",
      measIgnored: "non comptée : la veille FT8 n'entend aucune station sur cette bande (parasites probables)",
      rxq: (v) => (v >= 70 ? "bonne réception" : v >= 40 ? "réception moyenne" : "réception faible"),
      corrected: (r) => `corrigée par les stations entendues, pondérées par leur SNR pour la phonie (ionosondes seules : ${r})`,
      ownNote: (loc) => `Mesures et prévisions propres au récepteur ORSAT${loc ? ` (${loc})` : ""} : elles peuvent différer sur votre station et à votre position.`,
      zoneHead: "zone exploitable", zoneSeen: "constatée", zonePred: "prévue", zoneNone: "zone non déterminée (aucune source localisée)",
      heardHead: (h) => `Stations localisées entendues (carnet + veille FT8, ${h})`, heardNone: (h) => `Aucune station localisée (carnet, veille FT8) depuis ${h}.`,
      farthest: "la plus lointaine", predReach: "Portée prévue", predClosed: "bande fermée à toutes distances",
      upTo: (km) => `jusqu'à ${km} km`, beyond: "au-delà de 2500 km",
      activity: "Activité sur la chute d'eau", unlocated: "origine non localisée",
      disUnder: "⚠ La bande est active alors que la prévision la donne fermée : la prévision sous-estime cette bande en ce moment.",
      disOver: "⚠ La prévision donne la bande ouverte, mais presque rien n'est entendu.",
      sep: " : ", title: "ORSAT exploitable", radius: (r) => `≤ ${r} km`, see: "🗺 Voir la carte",
      seeTip: "Ouvrir la carte détaillée : où ORSAT entend bien en ce moment, bande par bande",
      lblTip: (r, w) => `Probabilité de réception d'une station située à moins de ${r} km du récepteur ORSAT (calcul de ${w})`,
      boxTip: (r, loc) => `Probabilité de réception par ORSAT, en ce moment, d'une station située à moins de ${r} km du récepteur (${loc}). Calcul : ionosondes mesurées (KC2G) × diagramme de l'antenne loop. Clic : carte détaillée.`,
      verdict: { hi: "Fiable", mid: "Correct", lo: "Aléatoire", off: "Fermé", na: "Pas de prévision" },
      meaning: { hi: "une station située dans ce rayon sera presque toujours entendue", mid: "entendue dans une bonne partie de la zone",
                 lo: "entendue seulement dans certaines directions ou à certaines distances", off: "inutile d'insister sur cette bande pour l'instant",
                 na: "pas de mesure d'ionosonde assez proche" },
      measured: "mesuré", measuredBy: "Mesuré par ORSAT", none: "aucun signal",
      sig: (n) => (n > 1 ? "signaux" : "signal"), best: "meilleur", coverage: "couverture",
      nearest: "(bande la plus proche de la fréquence écoutée)",
      calibWait: "Étalonnage en cours : les mesures réelles s'accumulent (quelques jours).",
      calibHead: (d, s) => `Constaté sur ${d} jours (signal exploitable = SNR ≥ ${s} dB) :`,
      calibRow: (x) => `prévision ${x.range} → signal exploitable ${x.rate} % du temps (${x.n} mesures)`,
      mapTitle: "ORSAT exploitable — carte détaillée", close: "✕ Fermer", closeTip: "Fermer la carte et revenir au WebSDR",
    },
    en: {
      ipTitle: "Performance index", ipShort: "PI",
      ipTip: (w) => `Performance index of the ORSAT receiver, band by band (0 to 100, computed at ${w}).\nForecast over all distances (measured ionosondes × loop pattern), corrected by what ORSAT actually measures on the waterfall.\nLetters: area where ORSAT hears best. Click: detailed map.`,
      ipVerdict: { l5: "Excellent", l4: "Good", l3: "Fair", l2: "Average", l1: "Poor", l0: "Closed", na: "No data" },
      zoneShort: { loc: "Loc", reg: "Reg", eu: "EU", dx: "DX" },
      zoneLong: { loc: "local (≤ 300 km)", reg: "regional (300–900 km)", eu: "Europe (900–2500 km)", dx: "DX (beyond 2500 km)" },
      bestZone: "best range", noZone: "no really good area",
      predWord: "forecast", measWord: "measurement", noMeas: "no recent measurement",
      byDist: "Forecast by distance", measErr: "Real measurement unavailable",
      measIgnored: "not counted: the FT8 watch hears no station on this band (likely interference)",
      rxq: (v) => (v >= 70 ? "good reception" : v >= 40 ? "fair reception" : "weak reception"),
      corrected: (r) => `corrected by the stations heard, weighted by their SNR for phone (ionosondes alone: ${r})`,
      ownNote: (loc) => `Measurements and forecasts are specific to the ORSAT receiver${loc ? ` (${loc})` : ""}: they may differ at your station and location.`,
      zoneHead: "usable area", zoneSeen: "observed", zonePred: "forecast", zoneNone: "area undetermined (no located source)",
      heardHead: (h) => `Located stations heard (log + FT8 watch, ${h})`, heardNone: (h) => `No located station (log, FT8 watch) for the last ${h}.`,
      farthest: "farthest", predReach: "Forecast reach", predClosed: "band closed at all distances",
      upTo: (km) => `up to ${km} km`, beyond: "beyond 2500 km",
      activity: "Waterfall activity", unlocated: "origin not located",
      disUnder: "⚠ The band is active although the forecast says closed: the forecast underestimates this band right now.",
      disOver: "⚠ The forecast says the band is open, but almost nothing is heard.",
      sep: ": ", title: "ORSAT usable", radius: (r) => `≤ ${r} km`, see: "🗺 Show map",
      seeTip: "Open the detailed map: where ORSAT hears well right now, band by band",
      lblTip: (r, w) => `Probability of hearing a station located within ${r} km of the ORSAT receiver (computed at ${w})`,
      boxTip: (r, loc) => `Probability, right now, that ORSAT hears a station located within ${r} km of the receiver (${loc}). Computed from measured ionosondes (KC2G) × the loop antenna pattern. Click: detailed map.`,
      verdict: { hi: "Reliable", mid: "Fair", lo: "Patchy", off: "Closed", na: "No forecast" },
      meaning: { hi: "a station within this radius will almost always be heard", mid: "heard over a good part of the area",
                 lo: "heard only in some directions or at some distances", off: "no point trying this band for now",
                 na: "no ionosonde close enough" },
      measured: "measured", measuredBy: "Measured by ORSAT", none: "no signal",
      sig: (n) => (n > 1 ? "signals" : "signal"), best: "best", coverage: "coverage",
      nearest: "(band closest to the tuned frequency)",
      calibWait: "Calibration in progress: real measurements are building up (a few days).",
      calibHead: (d, s) => `Observed over ${d} days (usable signal = SNR ≥ ${s} dB):`,
      calibRow: (x) => `forecast ${x.range} → usable signal ${x.rate} % of the time (${x.n} measurements)`,
      mapTitle: "ORSAT usable — detailed map", close: "✕ Close", closeTip: "Close the map and return to the WebSDR",
    },
    es: {
      ipTitle: "Índice de rendimiento", ipShort: "IR",
      ipTip: (w) => `Índice de rendimiento del receptor ORSAT, banda por banda (0 a 100, cálculo de las ${w}).\nPrevisión sobre todas las distancias (ionosondas medidas × diagrama de la loop), corregida con lo que ORSAT mide realmente en la cascada.\nLetras: zona donde ORSAT escucha mejor. Clic: mapa detallado.`,
      ipVerdict: { l5: "Excelente", l4: "Bueno", l3: "Correcto", l2: "Regular", l1: "Débil", l0: "Cerrada", na: "Sin datos" },
      zoneShort: { loc: "Loc", reg: "Reg", eu: "EU", dx: "DX" },
      zoneLong: { loc: "local (≤ 300 km)", reg: "regional (300–900 km)", eu: "Europa (900–2500 km)", dx: "DX (más de 2500 km)" },
      bestZone: "mejor alcance", noZone: "ninguna zona realmente buena",
      predWord: "previsión", measWord: "medida", noMeas: "sin medida reciente",
      byDist: "Previsión por distancia", measErr: "Medida real no disponible",
      measIgnored: "no contada: la vigilancia FT8 no oye ninguna estación en esta banda (probables parásitos)",
      rxq: (v) => (v >= 70 ? "buena recepción" : v >= 40 ? "recepción media" : "recepción débil"),
      corrected: (r) => `corregida con las estaciones oídas, ponderadas por su SNR para la fonía (solo ionosondas: ${r})`,
      ownNote: (loc) => `Medidas y previsiones propias del receptor ORSAT${loc ? ` (${loc})` : ""}: pueden ser distintas en su estación y en su ubicación.`,
      zoneHead: "zona utilizable", zoneSeen: "constatada", zonePred: "prevista", zoneNone: "zona no determinada (ninguna fuente localizada)",
      heardHead: (h) => `Estaciones localizadas oídas (libro + vigilancia FT8, ${h})`, heardNone: (h) => `Ninguna estación localizada (libro, vigilancia FT8) desde hace ${h}.`,
      farthest: "la más lejana", predReach: "Alcance previsto", predClosed: "banda cerrada a todas las distancias",
      upTo: (km) => `hasta ${km} km`, beyond: "más de 2500 km",
      activity: "Actividad en la cascada", unlocated: "origen no localizado",
      disUnder: "⚠ La banda está activa aunque la previsión la da cerrada: la previsión subestima esta banda ahora mismo.",
      disOver: "⚠ La previsión da la banda abierta, pero casi no se oye nada.",
      sep: ": ", title: "ORSAT utilizable", radius: (r) => `≤ ${r} km`, see: "🗺 Ver el mapa",
      seeTip: "Abrir el mapa detallado: dónde ORSAT escucha bien ahora, banda por banda",
      lblTip: (r, w) => `Probabilidad de recibir una estación situada a menos de ${r} km del receptor ORSAT (cálculo de las ${w})`,
      boxTip: (r, loc) => `Probabilidad, en este momento, de que ORSAT reciba una estación situada a menos de ${r} km del receptor (${loc}). Cálculo: ionosondas medidas (KC2G) × diagrama de la antena loop. Clic: mapa detallado.`,
      verdict: { hi: "Fiable", mid: "Aceptable", lo: "Irregular", off: "Cerrada", na: "Sin previsión" },
      meaning: { hi: "una estación dentro de este radio se oirá casi siempre", mid: "se oirá en buena parte de la zona",
                 lo: "se oirá solo en algunas direcciones o distancias", off: "no merece la pena insistir en esta banda por ahora",
                 na: "ninguna ionosonda lo bastante cerca" },
      measured: "medido", measuredBy: "Medido por ORSAT", none: "ninguna señal",
      sig: (n) => (n > 1 ? "señales" : "señal"), best: "mejor", coverage: "cobertura",
      nearest: "(banda más cercana a la frecuencia sintonizada)",
      calibWait: "Calibración en curso: las medidas reales se acumulan (unos días).",
      calibHead: (d, s) => `Constatado en ${d} días (señal utilizable = SNR ≥ ${s} dB):`,
      calibRow: (x) => `previsión ${x.range} → señal utilizable ${x.rate} % del tiempo (${x.n} medidas)`,
      mapTitle: "ORSAT utilizable — mapa detallado", close: "✕ Cerrar", closeTip: "Cerrar el mapa y volver al WebSDR",
    },
  };
  $: L = T[$lang] || T.fr;

  // verdict pour l'auditeur (seuils de couverture) ; la mesure réelle du WebSDR le confirme ou non
  const cls = (p) => (p == null ? "na" : p >= 70 ? "hi" : p >= 40 ? "mid" : p >= 15 ? "lo" : "off");
  $: meas = data && data.measured ? data.measured.bands : null;
  function measText(L, b) {
    const m = meas && meas[b];
    if (!m) return "";
    return m.signals ? `${m.signals} ${L.sig(m.signals)}, ${L.best} ${Math.round(m.best_snr)} dB` : L.none;
  }
  function chipTip(L, b, p) {
    const k = cls(p), m = measText(L, b);
    return `${b}${L.sep}${L.verdict[k]}${p != null ? ` (${L.coverage} ${p} %)` : ""} — ${L.meaning[k]}`
      + (m ? `\n${L.measuredBy}${L.sep}${m}` : "")
      + (near === b && !inBand ? "\n" + L.nearest : "");
  }

  // Indice de performance (IP) : fourni par le carnet (data.ip) ; carnet plus ancien : couverture à 800 km
  $: IP = data && data.ip ? data.ip : null;
  const ipOf = (b) => (IP ? (IP[b] ? IP[b].ip : null) : data && data.bands ? data.bands[b] : null);
  // six niveaux d'IP, du rouge (fermé) au vert (excellent) ; le calcul de l'IP lui-même est inchangé
  const IP_STEPS = [[85, "l5"], [70, "l4"], [50, "l3"], [30, "l2"], [10, "l1"], [0, "l0"]];
  const ipCls = (v) => (v == null ? "na" : IP_STEPS.find(([lim]) => v >= lim)[1]);
  const ipWord = (L, v) => L.ipVerdict[ipCls(v)];
  const zoneOf = (b) => (IP && IP[b] ? IP[b].zone : null);
  const DIST = [["d100", "≤100"], ["d300", "≤300"], ["d900", "≤900"], ["d2500", "≤2500"], ["dx", ">2500"]];
  // Bulle d'une bande. Les distances ne viennent que de sources localisées (locator ou lat/long) :
  // stations du carnet et prévision géographique. L'activité de la chute d'eau, sans origine connue,
  // est donnée à part, sans distance.
  // durée de la fenêtre des stations entendues (carnet récent : minutes ; ancien : heures)
  const win = (H) => (H.minutes ? `${H.minutes} min` : `${H.hours} h`);
  const TR = [["d100", 100], ["d300", 300], ["d900", 900], ["d2500", 2500], ["dx", null]];
  const km = (n) => Math.round(n).toLocaleString("fr-FR");
  function ipTip(L, b) {
    const v = ipOf(b), x = IP && IP[b];
    const H = data && data.heard, h = H && H.bands ? H.bands[b] : null;
    // zone exploitable : la plus lointaine tranche où le carnet a des stations localisées, sinon la
    // meilleure zone prévue ; sans source localisée, on le dit plutôt que d'afficher une zone inventée
    const T2Z = { d100: "loc", d300: "loc", d900: "reg", d2500: "eu", dx: "dx" };
    const seen = h && h.n ? [...TR].reverse().find(([k]) => h.tranches[k]) : null;
    const zp = zoneOf(b);
    const zone = seen ? `${L.zoneLong[T2Z[seen[0]]]}, ${L.zoneSeen}`
      : zp ? `${L.zoneLong[zp]}, ${L.zonePred}` : null;
    let t = `${b}${L.sep}${ipWord(L, v)}${v != null ? ` (${L.ipShort} ${v})` : ""} — `
      + (zone ? `${L.zoneHead}${L.sep}${zone}` : L.zoneNone);
    if (H) {
      if (h && h.n) {
        t += `\n${L.heardHead(win(H))}${L.sep}${h.n}`
          + `\n   ` + DIST.filter(([k]) => h.tranches[k]).map(([k, l]) => `${l} km : ${h.tranches[k]}`).join(" · ")
          + `\n   ${L.farthest}${L.sep}${h.far_call}, ${km(h.far_km)} km`;
      } else t += `\n${L.heardNone(win(H))}`;
    }
    if (x && x.tranches) {
      // une tranche est atteinte dès que des cases y passent (note > 0) ; une note basse veut dire
      // réception faible (gain de la loop à cet angle), pas bande fermée
      const reachTxt = (trs) => {
        const open = TR.filter(([k]) => (trs[k] ?? 0) > 0);
        if (!open.length) return L.predClosed;
        const last = open[open.length - 1][1];
        const best = Math.max(...open.map(([k]) => trs[k]));
        return (last == null ? L.beyond : L.upTo(last)) + ` (${L.rxq(best)})`;
      };
      t += `\n${L.predReach}${L.sep}${reachTxt(x.tranches)}`;
      // prévision relevée par les stations réellement entendues : on garde la trace des ionosondes seules
      if (x.corrected && x.tranches_iono) t += `\n   ${L.corrected(reachTxt(x.tranches_iono))}`;
    }
    const m = measText(L, b);
    if (m) t += `\n${L.activity}${L.sep}${m} (${L.unlocated})` + (x && x.meas_ignored ? `\n   ${L.measIgnored}` : "");
    if (x && x.pred != null && x.meas != null) {
      if (x.pred < 15 && x.meas >= 50) t += `\n\n${L.disUnder}`;
      else if (x.pred >= 50 && x.meas < 15) t += `\n\n${L.disOver}`;
    }
    if (near === b && !inBand) t += "\n" + L.nearest;
    if (data && data.measure_error && !data.measured) t += `\n${L.measErr}${L.sep}${data.measure_error}`;
    return t + `\n\n${L.ownNote(data && data.locator)}`;
  }



  // Explication de l'IP : panneau ouvert d'un clic sur le titre du bandeau
  let showHelp = false;
  const HELP = {
    fr: {
      title: "Comment ORSAT calcule son indice de performance (IP)",
      intro: "L'IP note de 0 à 100, bande par bande, la capacité du récepteur ORSAT à entendre des stations en ce moment. Il est recalculé en continu sur le serveur, même sans auditeur connecté.",
      blocks: [
        ["1. La prévision de propagation", "Toutes les 15 min, ORSAT lit les mesures des ionosondes du monde entier (réseau KC2G : GIRO, NOAA, INGV…). Pour chaque direction et chaque distance jusqu'à 5000 km, il calcule la fréquence maximale utilisable (MUF) du trajet et l'absorption de jour (couche D), selon la hauteur du Soleil et le flux solaire."],
        ["2. L'antenne réelle d'ORSAT", "Le diagramme de la loop horizontale (80 m de périmètre à 6 m sur sol sablonneux, balun 4:1) a été simulé avec NEC. Pour chaque distance, ORSAT sait sous quel angle arrive le signal et combien la loop le capte : bien près de la verticale (NVIS), moins bien à angle très bas."],
        ["3. La note par distance", "La zone est découpée en 5 tranches : ≤ 100, ≤ 300, ≤ 900, ≤ 2500 et au-delà de 2500 km. Chaque tranche reçoit une note : bonne écoute 1, moyenne 0,6, faible 0,25, zone de silence ou absorbée 0. Une bande ne s'ouvre jamais partout à la fois (zone de silence) : la prévision vaut 70 % de la meilleure tranche + 30 % de la moyenne des tranches. Les stations réellement entendues (veille FT8 cyclique et carnet, avec locator) corrigent la prévision : la note d'une tranche dépend du SNR FT8 de ses meilleures stations, pour rester juste en phonie (le FT8 passe jusqu'à −24 dB, une SSB confortable demande environ +5 dB) : −24 dB → 15, −10 dB → 56, 0 dB → 85, +5 dB → 100, plafonnée à 60 avec seulement 1 ou 2 stations ; un contact du carnet compte pleinement. L'absence de station n'abaisse jamais une tranche."],
        ["4. La mesure réelle", "Toutes les 5 min, ORSAT écoute lui-même chaque bande sur sa chute d'eau, quelques secondes, sans décoder : il compte les signaux qui dépassent le bruit de 10 dB et relève le meilleur rapport signal/bruit (SNR). Note de mesure : jusqu'à 70 points pour le SNR (de 6 à 30 dB) et 30 points pour le nombre de signaux (jusqu'à 10)."],
        ["5. L'indice final", "IP = 40 % prévision + 60 % mesure réelle si la mesure a moins de 15 min ; sinon la prévision seule. La mesure pèse plus : c'est ce que le récepteur entend vraiment."],
      ],
      legendTitle: "Lecture",
      legend: ["Excellent : 85 et plus", "Bon : 70 à 84", "Correct : 50 à 69", "Moyen : 30 à 49", "Faible : 10 à 29", "Fermé : moins de 10"],
      zones: "Lettres : où ORSAT entend le mieux — Loc ≤ 300 km · Rég 300–900 km · EU 900–2500 km · DX au-delà.",
      calib: "Étalonnage : chaque mesure est comparée à la prévision du même instant. Au fil des jours, l'infobulle des bandes indique ce qui a été constaté (« prévision 70–100 → signal exploitable 92 % du temps »).",
      close: "✕ Fermer", btnTip: "Comment ORSAT calcule son indice de performance (clic)",
    },
    en: {
      title: "How ORSAT computes its performance index (PI)",
      intro: "The PI rates from 0 to 100, band by band, how well the ORSAT receiver can hear stations right now. It is recomputed continuously on the server, even with no listener connected.",
      blocks: [
        ["1. Propagation forecast", "Every 15 min, ORSAT reads ionosonde measurements from all over the world (KC2G network: GIRO, NOAA, INGV…). For each direction and distance up to 5000 km, it computes the path's maximum usable frequency (MUF) and the daytime absorption (D layer), from the Sun's elevation and the solar flux."],
        ["2. ORSAT's real antenna", "The pattern of the horizontal loop (80 m perimeter, 6 m above sandy ground, 4:1 balun) was simulated with NEC. For each distance, ORSAT knows the arrival angle of the signal and how well the loop picks it up: well near vertical (NVIS), less well at very low angles."],
        ["3. Score by distance", "The area is split into 5 ranges: ≤ 100, ≤ 300, ≤ 900, ≤ 2500 and beyond 2500 km. Each range is scored: good reception 1, fair 0.6, weak 0.25, skip zone or absorbed 0. A band never opens everywhere at once (skip zone): the forecast is 70 % of the best range + 30 % of the average of the ranges. Stations actually heard (cyclic FT8 watch and log, with a locator) correct the forecast: a range's score depends on the FT8 SNR of its best stations, so it stays fair for phone (FT8 works down to −24 dB, a comfortable SSB QSO needs about +5 dB): −24 dB → 15, −10 dB → 56, 0 dB → 85, +5 dB → 100, capped at 60 with only 1 or 2 stations; a log contact counts in full. No station never lowers a range."],
        ["4. Real measurement", "Every 5 min, ORSAT itself listens to each band on its waterfall for a few seconds, without decoding: it counts the signals 10 dB above the noise and records the best signal-to-noise ratio (SNR). Measurement score: up to 70 points for SNR (6 to 30 dB) and 30 points for the number of signals (up to 10)."],
        ["5. Final index", "PI = 40 % forecast + 60 % real measurement when the measurement is less than 15 min old; otherwise the forecast alone. The measurement weighs more: it is what the receiver actually hears."],
      ],
      legendTitle: "Reading",
      legend: ["Excellent: 85 and above", "Good: 70 to 84", "Fair: 50 to 69", "Average: 30 to 49", "Poor: 10 to 29", "Closed: below 10"],
      zones: "Letters: where ORSAT hears best — Loc ≤ 300 km · Reg 300–900 km · EU 900–2500 km · DX beyond.",
      calib: "Calibration: each measurement is compared with the forecast made at the same time. Over the days, the band tooltips show what was observed (\"forecast 70–100 → usable signal 92 % of the time\").",
      close: "✕ Close", btnTip: "How ORSAT computes its performance index (click)",
    },
    es: {
      title: "Cómo calcula ORSAT su índice de rendimiento (IR)",
      intro: "El IR puntúa de 0 a 100, banda por banda, la capacidad del receptor ORSAT para oír estaciones en este momento. Se recalcula continuamente en el servidor, incluso sin oyentes conectados.",
      blocks: [
        ["1. La previsión de propagación", "Cada 15 min, ORSAT lee las medidas de las ionosondas de todo el mundo (red KC2G: GIRO, NOAA, INGV…). Para cada dirección y distancia hasta 5000 km, calcula la frecuencia máxima utilizable (MUF) del trayecto y la absorción diurna (capa D), según la altura del Sol y el flujo solar."],
        ["2. La antena real de ORSAT", "El diagrama de la loop horizontal (80 m de perímetro a 6 m sobre suelo arenoso, balun 4:1) se simuló con NEC. Para cada distancia, ORSAT sabe con qué ángulo llega la señal y cuánto la capta la loop: bien cerca de la vertical (NVIS), peor a ángulos muy bajos."],
        ["3. La nota por distancia", "La zona se divide en 5 tramos: ≤ 100, ≤ 300, ≤ 900, ≤ 2500 y más de 2500 km. Cada tramo recibe una nota: buena recepción 1, aceptable 0,6, débil 0,25, zona de silencio o absorbida 0. Una banda nunca se abre en todas partes a la vez (zona de silencio): la previsión vale 70 % del mejor tramo + 30 % de la media de los tramos. Las estaciones realmente oídas (vigilancia FT8 cíclica y libro, con locator) corrigen la previsión: la nota de un tramo depende del SNR FT8 de sus mejores estaciones, para seguir siendo justa en fonía (el FT8 pasa hasta −24 dB, una SSB cómoda pide unos +5 dB): −24 dB → 15, −10 dB → 56, 0 dB → 85, +5 dB → 100, limitada a 60 con solo 1 o 2 estaciones; un contacto del libro cuenta por completo. La ausencia de estaciones nunca baja un tramo."],
        ["4. La medida real", "Cada 5 min, ORSAT escucha él mismo cada banda en su cascada durante unos segundos, sin decodificar: cuenta las señales 10 dB por encima del ruido y anota la mejor relación señal/ruido (SNR). Nota de medida: hasta 70 puntos por la SNR (de 6 a 30 dB) y 30 puntos por el número de señales (hasta 10)."],
        ["5. El índice final", "IR = 40 % previsión + 60 % medida real si la medida tiene menos de 15 min; si no, solo la previsión. La medida pesa más: es lo que el receptor oye de verdad."],
      ],
      legendTitle: "Lectura",
      legend: ["Excelente: 85 o más", "Bueno: 70 a 84", "Correcto: 50 a 69", "Regular: 30 a 49", "Débil: 10 a 29", "Cerrada: menos de 10"],
      zones: "Letras: dónde ORSAT escucha mejor — Loc ≤ 300 km · Reg 300–900 km · EU 900–2500 km · DX más allá.",
      calib: "Calibración: cada medida se compara con la previsión del mismo instante. Con los días, la ayuda de las bandas muestra lo constatado («previsión 70–100 → señal utilizable 92 % del tiempo»).",
      close: "✕ Cerrar", btnTip: "Cómo calcula ORSAT su índice de rendimiento (clic)",
    },
  };
  $: H = HELP[$lang] || HELP.fr;
  // carte détaillée : fenêtre par-dessus la page du WebSDR (cadre vers /log/ecoute), bouton Fermer bien visible
  let showMap = false;
  function openMap() { showMap = true; }
  function closeMap() { showMap = false; }
</script>

{#if data}
  <div class="lb" data-no-i18n role="button" tabindex="-1" on:click={openMap} on:keydown={() => {}}
       title={`${L.boxTip(data.radius_km, data.locator)}\n${L.ownNote(data.locator)}`}>
    <button type="button" class="lbl help-btn" class:open={showHelp} title={`${H.btnTip}\n${L.ownNote(data && data.locator)}`}
            on:click|stopPropagation={() => (showHelp = !showHelp)}>{L.ipTitle} <span class="q">?</span></button>
    {#if near}
      {@const v = ipOf(near)}
      <span class="sum {ipCls(v)}" title={ipTip(L, near)}>
        {near}{L.sep}<b>{ipWord(L, v)}</b>{#if zoneOf(near)}<i>&nbsp;· {L.zoneLong[zoneOf(near)]}</i>{/if}
      </span>
    {/if}
    {#each BANDS as [b]}
      {@const v = ipOf(b)}
      <span class="chip {ipCls(v)}" class:cur={near === b} title={ipTip(L, b)}>
        {near === b && !inBand ? "≈" : ""}{b.replace("m", "")}<small>{v == null ? "–" : v}</small>{#if zoneOf(b)}<em>{L.zoneShort[zoneOf(b)]}</em>{/if}
      </span>
    {/each}
    <button type="button" class="see" on:click|stopPropagation={openMap} title={L.seeTip}>{L.see}</button>
  </div>
{/if}

{#if data && showHelp}
  <div class="help-ov" data-no-i18n role="presentation" on:click={() => (showHelp = false)}>
    <div class="help" role="dialog" aria-label={H.title} on:click|stopPropagation={() => {}}>
      <div class="help-head">
        <span class="t">{H.title}</span>
        <button type="button" class="close" on:click={() => (showHelp = false)}>{H.close}</button>
      </div>
      <div class="help-body">
        <p class="intro">{H.intro}</p>
        <p class="own">{L.ownNote(data && data.locator)}</p>
        {#each H.blocks as [h, txt]}<h4>{h}</h4><p>{txt}</p>{/each}
        <h4>{H.legendTitle}</h4>
        <div class="leg">
          <span class="chip l5">85+</span>{H.legend[0]}
          <span class="chip l4">70+</span>{H.legend[1]}
          <span class="chip l3">50+</span>{H.legend[2]}
          <span class="chip l2">30+</span>{H.legend[3]}
          <span class="chip l1">10+</span>{H.legend[4]}
          <span class="chip l0">&lt;10</span>{H.legend[5]}
        </div>
        <p>{H.zones}</p>
        <p class="calib">{H.calib}</p>
      </div>
    </div>
  </div>
{/if}

{#if showMap}
  <div class="ov" data-no-i18n role="presentation" on:click={closeMap}>
    <div class="win" role="dialog" aria-label={L.mapTitle} on:click|stopPropagation={() => {}}>
      <div class="bar">
        <span class="t">{L.mapTitle}</span>
        <button type="button" class="close" on:click={closeMap} title={L.closeTip}>{L.close}</button>
      </div>
      <iframe src="/log/ecoute?lang={$lang}" title={L.mapTitle}></iframe>
    </div>
  </div>
{/if}

<style>
  /* fond opaque : lisible quelle que soit l'image de fond de la page */
  .lb {
    display: flex; align-items: center; gap: 5px; flex-wrap: nowrap; overflow: hidden; width: 100%; box-sizing: border-box;
    height: 28px; margin: 0 0 4px; padding: 0 10px; cursor: pointer; user-select: none;
    background: #15130d; border: 1px solid rgba(207, 181, 59, 0.75); border-radius: 6px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
    font-size: 13px; line-height: 1; color: #f2eedf;
  }
  .lb:hover { border-color: rgb(226, 201, 90); }
  .help-btn {
    display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 11px; cursor: pointer;
    background: #2a2516; border: 1px solid rgba(226, 201, 90, 0.8); font: inherit; font-weight: 700;
  }
  .help-btn:hover, .help-btn.open { background: #3a3218; box-shadow: 0 0 8px rgba(226, 201, 90, 0.6); }
  .help-btn .q { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px;
                 border-radius: 50%; background: rgb(226, 201, 90); color: #1a1606; font-size: 11px; font-weight: 800; }
  .help-ov { position: fixed; inset: 0; z-index: 9000; background: rgba(0, 0, 0, 0.55);
             display: flex; align-items: flex-start; justify-content: center; padding-top: 70px; }
  .help { width: min(820px, 94vw); max-height: 84vh; display: flex; flex-direction: column; overflow: hidden;
          background: #15130d; border: 2px solid rgb(207, 181, 59); border-radius: 10px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8); }
  .help-head { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid rgba(207, 181, 59, 0.5); }
  .help-head .t { color: rgb(226, 201, 90); font-weight: 700; font-size: 16px; }
  .help-body { overflow-y: auto; padding: 12px 18px 16px; color: #ece7d4; font-size: 14px; line-height: 1.5; }
  .help-body .intro { font-size: 15px; color: #fff; }
  .help-body .own { margin: 8px 0 4px; padding: 6px 10px; border-left: 3px solid rgb(207, 181, 59);
                    background: rgba(207, 181, 59, 0.10); color: #f2eedf; }
  .help-body h4 { margin: 14px 0 4px; color: rgb(226, 201, 90); font-size: 14px; font-weight: 700; }
  .help-body p { margin: 0 0 6px; }
  .help-body .calib { color: #c9c3ad; font-size: 13px; margin-top: 10px; }
  .leg { display: grid; grid-template-columns: auto 1fr auto 1fr; gap: 6px 10px; align-items: center; margin-bottom: 8px; }
  .lbl { flex-shrink: 0; color: rgb(226, 201, 90); font-weight: 700; letter-spacing: 0.03em; margin-right: 6px; white-space: nowrap; }
  .chip {
    display: inline-flex; align-items: baseline; gap: 3px; padding: 3px 6px; border-radius: 11px; flex-shrink: 0;
    color: #ffffff; font-weight: 600; white-space: nowrap; border: 1px solid transparent;
  }
  .chip small { font-size: 11px; font-weight: 500; }
  .chip em { font-style: normal; font-size: 10px; font-weight: 700; opacity: 0.9; padding-left: 1px; }
  .sum { min-width: 0; overflow: hidden; text-overflow: ellipsis; flex-shrink: 1 !important; }
  .chip.l5 { background: #1f8a3c; }
  .chip.l4 { background: #5a962a; }
  .chip.l3 { background: #8f8f1a; }
  .chip.l2 { background: #b07a18; }
  .chip.l1 { background: #b4521e; }
  .chip.l0 { background: #9e2b2b; }
  .chip.na { background: transparent; color: #9b9684; }
  .chip.cur { border-color: rgb(226, 201, 90); box-shadow: 0 0 0 1px rgb(226, 201, 90), 0 0 8px rgba(226, 201, 90, 0.7); }
  .sum { flex-shrink: 0; padding: 3px 9px; border-radius: 11px; white-space: nowrap; margin-right: 6px;
         border: 1px solid rgba(207, 181, 59, 0.6); background: #221f15; color: #f2eedf; }
  .sum b { font-weight: 800; }
  .sum.l5 b { color: #5fe07a; } .sum.l4 b { color: #a6dd5c; } .sum.l3 b { color: #e8e060; }
  .sum.l2 b { color: #f0b450; } .sum.l1 b { color: #f08a50; } .sum.l0 b { color: #f06a6a; }
  .sum i { font-style: normal; color: #cfc9b2; font-size: 12px; }
  .lbl .r { color: #b9b39d; font-weight: 500; margin-left: 4px; }
  .see {
    flex-shrink: 0; margin-left: auto; padding: 3px 12px; border-radius: 11px; font-size: 12px; font-weight: 700; white-space: nowrap;
    color: #1a1606; background: linear-gradient(180deg, #e2c95a, rgb(207, 181, 59)); border: 1px solid #f0dc80; cursor: pointer;
  }
  .see:hover { filter: brightness(1.12); box-shadow: 0 0 8px rgba(226, 201, 90, 0.7); }
  .ov { position: fixed; inset: 0; z-index: 9000; background: rgba(0, 0, 0, 0.7); display: flex; align-items: center; justify-content: center; }
  .win { width: min(1240px, 96vw); height: min(920px, 92vh); display: flex; flex-direction: column;
         background: #15130d; border: 2px solid rgb(207, 181, 59); border-radius: 10px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8); overflow: hidden; }
  .win .bar { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 1px solid rgba(207, 181, 59, 0.5); }
  .win .t { color: rgb(226, 201, 90); font-weight: 700; font-size: 15px; letter-spacing: 0.03em; }
  .close {
    margin-left: auto; padding: 7px 18px; border-radius: 8px; font-size: 15px; font-weight: 800; cursor: pointer;
    color: #1a1606; background: linear-gradient(180deg, #f0d96a, rgb(207, 181, 59)); border: 1px solid #fff2a8;
  }
  .close:hover { filter: brightness(1.12); box-shadow: 0 0 10px rgba(240, 217, 106, 0.8); }
  iframe { flex: 1; width: 100%; border: 0; background: #0d0d0f; }
  .when { margin-left: auto; flex-shrink: 0; color: #b9b39d; white-space: nowrap; padding-left: 8px; font-size: 12px; }
</style>
