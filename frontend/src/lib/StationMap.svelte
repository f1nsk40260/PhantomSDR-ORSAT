<script>
  /**
   * StationMap — carte des stations entendues par un décodeur (ORSAT).
   * Boutons « 🗺 Carte (n) » et « ⤢ Grand format » ; la carte est la même que
   * celle d'APRS / HFDL (aprsMap.js). Le parent l'alimente par add() :
   *   add({ call, grid, text, link })   — locator Maidenhead → position
   * Les stations sont gardées même carte fermée, jusqu'à clear().
   */
  import { AprsMap, locatorToLatLon } from "./aprsMap.js";

  export let homeLocator = "";
  export let title = "Stations entendues";
  export let dot = { color: "#6b5310", fillColor: "#cfb53b" };

  const map = new AprsMap(homeLocator);
  map.labelsOnHover = true;
  map.dotStyle = dot;
  map.linkText = "Fiche QRZ";
  let count = 0;
  map.onChange = (n) => (count = n);

  let showSmall = false, showBig = false, mapError = "";

  export function add(s) {
    if (!s || !s.grid) return;
    const ll = locatorToLatLon(s.grid);
    if (!ll) return;
    map.add({ call: s.call, lat: ll.lat, lon: ll.lon, text: s.text || s.grid, time: Date.now(), link: s.link || "" });
  }
  export function clear() { map.clear(); }

  function mount(node) {
    mapError = "";
    map.open(node).then(() => map.fitAll(),
      (e) => (mapError = "Carte indisponible : " + (e && e.message ? e.message : e)));
    const ro = new ResizeObserver(() => map.invalidate());
    ro.observe(node);
    return { destroy: () => { ro.disconnect(); map.close(); } };
  }

  // ── Fenêtre grand format, déplaçable et redimensionnable ──
  let bx = null, by = null, drag = null, win;
  function portal(node) { document.body.appendChild(node); return { destroy: () => node.remove() }; }
  function place(node) {
    if (bx !== null) return;
    requestAnimationFrame(() => {
      const r = node.getBoundingClientRect();
      bx = Math.max(8, (window.innerWidth - r.width) / 2);
      by = Math.max(8, (window.innerHeight - r.height) / 2);
    });
  }
  function down(e) {
    if (e.button !== 0 || e.target.closest("button")) return;
    drag = { x: e.clientX - bx, y: e.clientY - by };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function move(e) {
    if (!drag) return;
    bx = Math.min(Math.max(e.clientX - drag.x, 40 - (win ? win.offsetWidth : 400)), window.innerWidth - 40);
    by = Math.min(Math.max(e.clientY - drag.y, 0), window.innerHeight - 36);
  }
  function up() { drag = null; }
  function key(e) { if (showBig && e.key === "Escape") showBig = false; }
</script>

<svelte:window on:keydown={key} />

<div class="sm-bar">
  <button class="sm-btn {showSmall ? 'on' : ''}" on:click={() => { showBig = false; showSmall = !showSmall; }}
    title="Afficher la carte des stations entendues (d'après leur locator)">🗺 Carte ({count})</button>
  <button class="sm-btn {showBig ? 'on' : ''}" on:click={() => { showSmall = false; showBig = !showBig; }}
    title="Ouvrir la carte dans une grande fenêtre déplaçable et redimensionnable">⤢ Grand format</button>
</div>

{#if showSmall}
  <div class="sm-small" use:mount></div>
  {#if mapError}<div class="sm-note err">{mapError}</div>
  {:else if count === 0}<div class="sm-note">Aucune station avec locator pour l'instant : les appels CQ en contiennent presque toujours.</div>{/if}
{/if}

{#if showBig}
  <div use:portal use:place bind:this={win} class="sm-big" role="dialog" aria-label={title}
    style={bx === null ? "visibility:hidden" : `left:${bx}px; top:${by}px`}>
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="sm-head" class:dragging={drag} on:pointerdown={down} on:pointermove={move}
      on:pointerup={up} on:pointercancel={up} title="Glisser pour déplacer la fenêtre">
      <span class="sm-grip" aria-hidden="true">⠿</span>
      <span class="sm-title">{title} ({count})</span>
      <span style="flex:1"></span>
      <button class="sm-hbtn" on:click={() => map.fitAll()} title="Recadrer sur toutes les stations">⌖ Tout voir</button>
      <button class="sm-hbtn" on:click={() => (showBig = false)} title="Fermer" aria-label="Fermer">✕</button>
    </div>
    <div class="sm-bigmap" use:mount></div>
    {#if mapError}<div class="sm-note err">{mapError}</div>
    {:else if count === 0}<div class="sm-note">Aucune station avec locator pour l'instant.</div>{/if}
  </div>
{/if}

<style>
  .sm-bar { display: flex; gap: 0.35rem; }
  .sm-btn {
    font-size: 0.7rem; padding: 0.1rem 0.5rem; border-radius: 0.3rem; font-weight: 600; white-space: nowrap;
    color: rgb(207, 181, 59); border: 1px solid rgba(207, 181, 59, 0.5); background: rgba(207, 181, 59, 0.06);
  }
  .sm-btn:hover, .sm-btn.on { background: rgba(207, 181, 59, 0.2); color: #f3e7a6; }
  .sm-small { width: 100%; height: 300px; margin: 0.5rem 0; border-radius: 0.4rem; border: 1px solid #374151; }
  .sm-note { font-size: 0.68rem; color: #9ca3af; font-style: italic; padding: 2px 4px; }
  .sm-note.err { color: #f87171; font-style: normal; }
  .sm-big {
    position: fixed; z-index: 1000; width: min(1100px, calc(100vw - 16px)); height: min(72vh, 760px);
    min-width: 420px; min-height: 280px; max-width: calc(100vw - 8px); max-height: calc(100vh - 8px);
    resize: both; overflow: hidden; display: flex; flex-direction: column; border-radius: 8px;
    background: rgba(17, 24, 39, 0.97); box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(207, 181, 59, 0.45);
  }
  .sm-head {
    display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-bottom: 1px solid #374151;
    background: rgba(207, 181, 59, 0.10); cursor: grab; user-select: none; touch-action: none;
  }
  .sm-head.dragging { cursor: grabbing; }
  .sm-grip { color: rgb(207, 181, 59); font-size: 15px; line-height: 1; }
  .sm-title { color: #f3e7a6; font-weight: 600; font-size: 13px; }
  .sm-hbtn {
    padding: 2px 8px; border-radius: 5px; font-size: 12px; font-weight: 600; color: rgb(207, 181, 59);
    background: rgba(0, 0, 0, 0.35); border: 1px solid rgba(207, 181, 59, 0.55);
  }
  .sm-hbtn:hover { background: rgba(207, 181, 59, 0.18); }
  .sm-bigmap { flex: 1; min-height: 0; }
</style>
