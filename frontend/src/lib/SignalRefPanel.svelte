<script>
  /**
   * SignalRefPanel — fiche de signal de référence (Artemis-DB / Signal
   * Identification Wiki), en deux usages :
   *   • ouverte depuis le Decoder ID sur le mode reconnu (refId fourni) ;
   *   • « Identifier un signal » : recherche dans les 583 fiches à partir de
   *     la fréquence, de la largeur du filtre et de la démodulation en cours.
   * (version française, F1NSK)
   */
  import { createEventDispatcher, onMount, onDestroy } from "svelte";
  import {
    loadIndex, loadRef, refImage, refSound, searchRefs, mdToHtml, fmtHz,
  } from "./signalRefs.js";

  export let refId = null;          // fiche à ouvrir directement (ou null)
  export let freqHz = 0;            // fréquence du récepteur
  export let bwHz = 0;              // largeur mesurée ou du filtre
  export let demod = "USB";

  const dispatch = createEventDispatcher();

  // Pendant l'écoute d'un enregistrement de référence, le son réel du
  // récepteur est coupé (sinon les deux se superposent) ; il revient dès que
  // la lecture s'arrête, se termine, change de fiche ou que le panneau ferme.
  let refPlaying = false;
  function setRefPlaying(on) {
    if (on === refPlaying) return;
    refPlaying = on;
    dispatch("refplay", on);
  }
  onDestroy(() => setRefPlaying(false));

  let index = [];
  let results = [];
  let selected = null;              // entrée de l'index
  let detail = null;                // signal.json complet
  let loading = true;

  // Champs de recherche (modifiables).
  let fKhz = freqHz > 0 ? +(freqHz / 1e3).toFixed(1) : "";
  let bw = bwHz > 0 ? Math.round(bwHz) : "";
  let dm = demod;
  let text = "";

  onMount(async () => {
    index = await loadIndex();
    loading = false;
    if (refId) {
      const e = index.find((s) => s.id === refId);
      if (e) select(e);
    }
  });

  $: results = index.length
    ? searchRefs(index, { freqHz: Number(fKhz) * 1e3, bwHz: Number(bw), demod: dm, text })
    : [];

  async function select(e) {
    selected = e;
    detail = null;
    detail = await loadRef(e.id);
  }

  function close() { dispatch("close"); }
  function onKey(ev) { if (ev.key === "Escape") close(); }

  const pct = (x) => `${Math.round(x * 100)} %`;
  const list = (a) => (a && a.length ? a.join(", ") : "—");
</script>

<svelte:window on:keydown={onKey} />

<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
<div class="sigref-overlay" on:click|self={close}>
  <div class="sigref glass-window" role="dialog" aria-label="Signaux de référence">
    <div class="sigref-head">
      <span class="font-semibold text-white">Identifier un signal</span>
      <span class="text-gray-500 text-[11px] hidden sm:inline">Base Artemis / Signal Identification Wiki</span>
      <span class="flex-1"></span>
      <button class="sigref-x" on:click={close} title="Fermer" aria-label="Fermer">✕</button>
    </div>

    <div class="sigref-form">
      <label>Fréquence (kHz)<input type="number" step="0.1" min="0" bind:value={fKhz} /></label>
      <label>Largeur (Hz)<input type="number" step="10" min="0" bind:value={bw} /></label>
      <label>Démodulation
        <select bind:value={dm}>
          {#each ["USB", "LSB", "CW", "AM", "FM"] as d}<option value={d}>{d}</option>{/each}
        </select>
      </label>
      <label class="grow">Filtre<input type="text" placeholder="nom, catégorie, modulation…" bind:value={text} /></label>
    </div>

    <div class="sigref-body">
      <div class="sigref-list">
        {#if loading}
          <div class="text-gray-400 p-2">Chargement…</div>
        {:else if !results.length}
          <div class="text-gray-400 p-2">Aucune fiche ne correspond.</div>
        {:else}
          {#each results as r (r.id)}
            <button
              class="sigref-item {selected && selected.id === r.id ? 'active' : ''}"
              on:click={() => select(r)}
            >
              <span class="t" data-no-i18n>{r.title}</span>
              <span class="m">
                <span data-no-i18n>{r.bw ? fmtHz(r.bw) : "—"} · {list(r.mod)}</span>
                <span class="s">{pct(r.score)}</span>
              </span>
            </button>
          {/each}
        {/if}
      </div>

      <div class="sigref-detail">
        {#if !selected}
          <div class="text-gray-400 p-3">
            Choisissez une fiche dans la liste. Le classement compare la fréquence,
            la largeur et la démodulation à celles de chaque signal connu.
          </div>
        {:else}
          <h3 class="text-white font-semibold text-sm mb-1" data-no-i18n>{selected.title}</h3>
          {#if selected.has_img && refImage(selected.id)}
            <img class="sigref-img" src={refImage(selected.id)} alt="Spectre de référence" loading="lazy" />
          {/if}
          {#if selected.has_snd && refSound(selected.id)}
            <!-- svelte-ignore a11y-media-has-caption -->
            <audio class="w-full mt-1" controls preload="none" src={refSound(selected.id)}
              on:play={() => setRefPlaying(true)}
              on:pause={() => setRefPlaying(false)}
              on:ended={() => setRefPlaying(false)}
              on:emptied={() => setRefPlaying(false)}></audio>
          {/if}
          <table class="sigref-tab">
            <tr><td>Largeur</td><td data-no-i18n>{selected.bw ? fmtHz(selected.bw) : "—"}</td></tr>
            <tr><td>Modulation</td><td data-no-i18n>{list(selected.mod)}</td></tr>
            <tr><td>Mode de réception</td><td data-no-i18n>{list(selected.mode)}</td></tr>
            <tr><td>Plage de fréquences</td><td data-no-i18n>{fmtHz(selected.fmin)} – {fmtHz(selected.fmax)}</td></tr>
            {#if detail && detail.freqs && detail.freqs.length > 2}
              <tr><td>Fréquences connues</td><td data-no-i18n>{detail.freqs.slice(0, 12).map(fmtHz).join(", ")}{detail.freqs.length > 12 ? "…" : ""}</td></tr>
            {/if}
            <tr><td>Catégorie</td><td data-no-i18n>{list(selected.cat)}</td></tr>
            {#if detail && detail.loc && detail.loc.length}
              <tr><td>Zone</td><td data-no-i18n>{list(detail.loc)}</td></tr>
            {/if}
          </table>
          {#if detail && detail.desc}
            <div class="sigref-desc" data-no-i18n>{@html mdToHtml(detail.desc)}</div>
          {/if}
          {#if detail && detail.page}
            <a class="sigref-link" href={detail.page} target="_blank" rel="noopener noreferrer">Fiche complète sur sigidwiki.com ↗</a>
          {/if}
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .sigref-overlay {
    position: fixed; inset: 0; z-index: 1000;
    background: rgba(0, 0, 0, 0.55);
    display: flex; align-items: center; justify-content: center;
    padding: 16px;
  }
  .sigref {
    width: min(980px, 100%); max-height: min(88vh, 900px);
    display: flex; flex-direction: column; overflow: hidden;
    border-radius: 8px; font-size: 12px; color: #d1d5db;
    background: rgba(17, 24, 39, 0.96);
  }
  .sigref-head { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 1px solid #374151; }
  .sigref-x { color: #9ca3af; padding: 0 6px; font-size: 14px; background: transparent; border: 0; }
  .sigref-x:hover { color: #fff; }
  .sigref-form { display: flex; flex-wrap: wrap; gap: 8px 12px; padding: 8px 12px; border-bottom: 1px solid #374151; }
  .sigref-form label { display: flex; flex-direction: column; gap: 2px; color: #9ca3af; font-size: 11px; }
  .sigref-form label.grow { flex: 1; min-width: 140px; }
  .sigref-form input, .sigref-form select {
    background: #1f2937; border: 1px solid #4b5563; border-radius: 4px;
    color: #e5e7eb; padding: 3px 6px; font-size: 12px; width: 110px;
  }
  .sigref-form label.grow input { width: 100%; }
  .sigref-form input, .sigref-form select, .sigref-form label { box-sizing: border-box; min-width: 0; }
  .sigref-body { display: flex; min-height: 0; flex: 1; }
  .sigref-list { width: 42%; overflow-y: auto; border-right: 1px solid #374151; }
  .sigref-item {
    display: flex; flex-direction: column; width: 100%; text-align: left;
    padding: 5px 10px; border: 0; border-bottom: 1px solid #1f2937;
    background: transparent; font: inherit; cursor: pointer;
  }
  .sigref-item:hover { background: #1f2937; }
  .sigref-item.active { background: #1e3a5f; }
  .sigref-item .t { color: #e5e7eb; }
  .sigref-item .m { display: flex; gap: 8px; color: #9ca3af; font-size: 11px; }
  .sigref-item .s { margin-left: auto; color: #93c5fd; }
  .sigref-detail { flex: 1; overflow-y: auto; padding: 10px 12px; min-width: 0; }
  .sigref-img { width: 100%; max-height: 260px; object-fit: contain; background: #000; border-radius: 4px; }
  .sigref-tab { margin: 8px 0; border-collapse: collapse; }
  .sigref-tab td { padding: 2px 10px 2px 0; vertical-align: top; }
  .sigref-tab td:first-child { color: #9ca3af; white-space: nowrap; }
  .sigref-desc { color: #d1d5db; line-height: 1.45; }
  .sigref-desc :global(p) { margin: 0 0 6px; }
  .sigref-desc :global(a), .sigref-link { color: #93c5fd; text-decoration: underline; }
  @media (max-width: 640px) {
    .sigref-overlay { padding: 0; }
    .sigref { max-height: 100vh; height: 100%; border-radius: 0; }
    .sigref-body { flex-direction: column; overflow-y: auto; }
    .sigref-list { width: 100%; max-height: 35vh; flex-shrink: 0; border-right: 0; border-bottom: 1px solid #374151; }
    .sigref-detail { overflow: visible; }
  }
</style>
