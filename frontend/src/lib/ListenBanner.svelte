<script>
  // Bandeau « écoute ORSAT » : probabilité de réception par bande dans un rayon de 800 km autour du
  // récepteur, calculée par le carnet ORSAT-LOG (ionosondes mesurées × diagramme NEC de la loop).
  // Source : /log/api/public/listenbanner (même serveur, sans connexion). Rafraîchi toutes les 5 min.
  // Si le carnet ne répond pas, le bandeau ne s'affiche pas : aucun effet sur le WebSDR.
  import { onMount, onDestroy } from "svelte";

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

  // verdict pour l'auditeur (seuils de couverture) ; la mesure réelle du WebSDR le confirme ou non
  const cls = (p) => (p == null ? "na" : p >= 70 ? "hi" : p >= 40 ? "mid" : p >= 15 ? "lo" : "off");
  const VERDICT = { hi: "Fiable", mid: "Correct", lo: "Aléatoire", off: "Fermé", na: "Pas de prévision" };
  const MEANING = {
    hi: "une station située dans ce rayon sera presque toujours entendue",
    mid: "entendue dans une bonne partie de la zone",
    lo: "entendue seulement dans certaines directions ou à certaines distances",
    off: "inutile d'insister sur cette bande pour l'instant",
    na: "pas de mesure d'ionosonde assez proche",
  };
  const word = (p) => VERDICT[cls(p)];
  $: meas = data && data.measured ? data.measured.bands : null;
  function measText(b) {
    const m = meas && meas[b];
    if (!m) return "";
    return m.signals ? `${m.signals} ${m.signals > 1 ? "signaux" : "signal"}, meilleur ${Math.round(m.best_snr)} dB` : "aucun signal";
  }
  function calibText() {
    const c = data && data.calibration;
    if (!c) return "";
    const rows = c.buckets.filter((x) => x.n >= 30);
    if (!rows.length) return "\nÉtalonnage en cours : les mesures réelles s'accumulent (quelques jours).";
    return `\n\nConstaté sur ${c.days} jours (signal exploitable = SNR ≥ ${c.snr_min} dB) :\n`
      + rows.map((x) => `couverture ${x.range} % → signal exploitable ${x.rate} % du temps (${x.n} mesures)`).join("\n");
  }
  function chipTip(b, p) {
    const k = cls(p), m = measText(b);
    return `${b} : ${VERDICT[k]}${p != null ? ` (couverture ${p} %)` : ""} — ${MEANING[k]}`
      + (m ? `\nMesuré par ORSAT : ${m}` : "")
      + (near === b && !inBand ? "\n(bande la plus proche de la fréquence écoutée)" : "");
  }

  // carte détaillée : fenêtre par-dessus la page du WebSDR (cadre vers /log/ecoute), bouton Fermer bien visible
  let showMap = false;
  function openMap() { showMap = true; }
  function closeMap() { showMap = false; }
</script>

{#if data}
  <div class="lb" role="button" tabindex="-1" on:click={openMap} on:keydown={() => {}}
       title="Probabilité de réception par ORSAT, en ce moment, d'une station située à moins de {data.radius_km} km du récepteur ({data.locator}). Calcul : ionosondes mesurées (KC2G) × diagramme de l'antenne loop. Clic : carte détaillée.">
    <span class="lbl" title="Probabilité de réception d'une station située à moins de {data.radius_km} km du récepteur ORSAT, calcul de {data.when}">ORSAT exploitable</span>
    {#if near}
      {@const p = data.bands[near]}
      <span class="sum {cls(p)}" title="{chipTip(near, p)}{calibText()}">
        {near} : <b>{word(p)}</b>{#if measText(near)}<i>&nbsp;· mesuré : {measText(near)}</i>{/if}
      </span>
    {/if}
    {#each BANDS as [b]}
      {@const p = data.bands[b]}
      <span class="chip {cls(p)}" class:cur={near === b} title="{chipTip(b, p)}{calibText()}">
        {near === b && !inBand ? "≈" : ""}{b.replace("m", "")}<small>{p == null ? "–" : p}</small>
      </span>
    {/each}
    <button type="button" class="see" on:click|stopPropagation={openMap}
            title="Ouvrir la carte détaillée : où ORSAT entend bien en ce moment, bande par bande">🗺 Voir la carte</button>
  </div>
{/if}

{#if showMap}
  <div class="ov" role="presentation" on:click={closeMap}>
    <div class="win" role="dialog" aria-label="Carte d'écoute ORSAT" on:click|stopPropagation={() => {}}>
      <div class="bar">
        <span class="t">ORSAT exploitable — carte détaillée</span>
        <button type="button" class="close" on:click={closeMap} title="Fermer la carte et revenir au WebSDR">✕ Fermer</button>
      </div>
      <iframe src="/log/ecoute" title="Carte d'écoute ORSAT"></iframe>
    </div>
  </div>
{/if}

<style>
  /* fond opaque : lisible quelle que soit l'image de fond de la page */
  .lb {
    display: flex; align-items: center; gap: 5px; flex-wrap: nowrap; overflow: hidden; width: 100%; box-sizing: border-box;
    height: 28px; margin: 3px 0 5px; padding: 0 10px; cursor: pointer; user-select: none;
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
