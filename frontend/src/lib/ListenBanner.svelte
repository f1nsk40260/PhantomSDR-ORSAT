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

  const cls = (p) => (p == null ? "na" : p >= 70 ? "hi" : p >= 40 ? "mid" : p >= 15 ? "lo" : "off");
  const word = (p) => (p == null ? "pas de mesure" : p >= 70 ? "très probable" : p >= 40 ? "probable" : p >= 15 ? "possible" : "improbable");

  function openMap() { window.open("/log/ecoute", "_blank", "noopener"); }
</script>

{#if data}
  <div class="lb" role="button" tabindex="-1" on:click={openMap} on:keydown={() => {}}
       title="Probabilité de réception par ORSAT, en ce moment, d'une station située à moins de {data.radius_km} km du récepteur ({data.locator}). Calcul : ionosondes mesurées (KC2G) × diagramme de l'antenne loop. Clic : carte détaillée.">
    <span class="lbl">Écoute ORSAT ≤ {data.radius_km} km</span>
    {#each BANDS as [b]}
      {@const p = data.bands[b]}
      <span class="chip {cls(p)}" class:cur={near === b} title="{b} : réception {word(p)}{p != null ? ` (${p} %)` : ''}{near === b && !inBand ? ' — bande la plus proche de la fréquence écoutée' : ''}">
        {near === b && !inBand ? "≈" : ""}{b.replace("m", "")}<small>{p == null ? "–" : `${p} %`}</small>
      </span>
    {/each}
    <span class="when">{data.when}</span>
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
  .lbl { color: rgb(226, 201, 90); font-weight: 700; letter-spacing: 0.03em; margin-right: 6px; white-space: nowrap; }
  .chip {
    display: inline-flex; align-items: baseline; gap: 4px; padding: 3px 8px; border-radius: 11px;
    color: #ffffff; font-weight: 600; white-space: nowrap; border: 1px solid transparent;
  }
  .chip small { font-size: 11px; font-weight: 500; }
  .chip.hi { background: #2f7d3a; }
  .chip.mid { background: #8a8a22; }
  .chip.lo { background: #a5601c; }
  .chip.off { background: #2b2a25; color: #9b9684; }
  .chip.na { background: transparent; color: #9b9684; }
  .chip.cur { border-color: rgb(226, 201, 90); box-shadow: 0 0 0 1px rgb(226, 201, 90), 0 0 8px rgba(226, 201, 90, 0.7); }
  .when { margin-left: auto; color: #b9b39d; white-space: nowrap; padding-left: 8px; font-size: 12px; }
</style>
