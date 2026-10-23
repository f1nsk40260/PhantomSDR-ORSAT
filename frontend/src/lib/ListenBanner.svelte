<script>
  // Bandeau « écoute ORSAT » : probabilité de réception par bande dans un rayon de 800 km autour du
  // récepteur, calculée par le carnet ORSAT-LOG (ionosondes mesurées × diagramme NEC de la loop).
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
      calibRow: (x) => `couverture ${x.range} % → signal exploitable ${x.rate} % du temps (${x.n} mesures)`,
      mapTitle: "ORSAT exploitable — carte détaillée", close: "✕ Fermer", closeTip: "Fermer la carte et revenir au WebSDR",
    },
    en: {
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
      calibRow: (x) => `coverage ${x.range} % → usable signal ${x.rate} % of the time (${x.n} measurements)`,
      mapTitle: "ORSAT usable — detailed map", close: "✕ Close", closeTip: "Close the map and return to the WebSDR",
    },
    es: {
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
      calibRow: (x) => `cobertura ${x.range} % → señal utilizable ${x.rate} % del tiempo (${x.n} medidas)`,
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
  function calibText(L) {
    const c = data && data.calibration;
    if (!c) return "";
    const rows = c.buckets.filter((x) => x.n >= 30);
    if (!rows.length) return "\n" + L.calibWait;
    return "\n\n" + L.calibHead(c.days, c.snr_min) + "\n" + rows.map(L.calibRow).join("\n");
  }
  function chipTip(L, b, p) {
    const k = cls(p), m = measText(L, b);
    return `${b}${L.sep}${L.verdict[k]}${p != null ? ` (${L.coverage} ${p} %)` : ""} — ${L.meaning[k]}`
      + (m ? `\n${L.measuredBy}${L.sep}${m}` : "")
      + (near === b && !inBand ? "\n" + L.nearest : "");
  }

  // carte détaillée : fenêtre par-dessus la page du WebSDR (cadre vers /log/ecoute), bouton Fermer bien visible
  let showMap = false;
  function openMap() { showMap = true; }
  function closeMap() { showMap = false; }
</script>

{#if data}
  <div class="lb" data-no-i18n role="button" tabindex="-1" on:click={openMap} on:keydown={() => {}}
       title={L.boxTip(data.radius_km, data.locator)}>
    <span class="lbl" title={L.lblTip(data.radius_km, data.when)}>{L.title} <span class="r">{L.radius(data.radius_km)}</span></span>
    {#if near}
      {@const p = data.bands[near]}
      <span class="sum {cls(p)}" title="{chipTip(L, near, p)}{calibText(L)}">
        {near}{L.sep}<b>{L.verdict[cls(p)]}</b>{#if measText(L, near)}<i>&nbsp;· {L.measured}{L.sep}{measText(L, near)}</i>{/if}
      </span>
    {/if}
    {#each BANDS as [b]}
      {@const p = data.bands[b]}
      <span class="chip {cls(p)}" class:cur={near === b} title="{chipTip(L, b, p)}{calibText(L)}">
        {near === b && !inBand ? "≈" : ""}{b.replace("m", "")}<small>{p == null ? "–" : p}</small>
      </span>
    {/each}
    <button type="button" class="see" on:click|stopPropagation={openMap} title={L.seeTip}>{L.see}</button>
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
  .lbl { flex-shrink: 0; color: rgb(226, 201, 90); font-weight: 700; letter-spacing: 0.03em; margin-right: 6px; white-space: nowrap; }
  .chip {
    display: inline-flex; align-items: baseline; gap: 3px; padding: 3px 6px; border-radius: 11px; flex-shrink: 0;
    color: #ffffff; font-weight: 600; white-space: nowrap; border: 1px solid transparent;
  }
  .chip small { font-size: 11px; font-weight: 500; }
  .chip.hi { background: #2f7d3a; }
  .chip.mid { background: #8a8a22; }
  .chip.lo { background: #a5601c; }
  .chip.off { background: #2b2a25; color: #9b9684; }
  .chip.na { background: transparent; color: #9b9684; }
  .chip.cur { border-color: rgb(226, 201, 90); box-shadow: 0 0 0 1px rgb(226, 201, 90), 0 0 8px rgba(226, 201, 90, 0.7); }
  .sum { flex-shrink: 0; padding: 3px 9px; border-radius: 11px; white-space: nowrap; margin-right: 6px;
         border: 1px solid rgba(207, 181, 59, 0.6); background: #221f15; color: #f2eedf; }
  .sum b { font-weight: 800; }
  .sum.hi b { color: #7fe08c; } .sum.mid b { color: #e3e36a; } .sum.lo b { color: #f0a25a; } .sum.off b { color: #9b9684; }
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
