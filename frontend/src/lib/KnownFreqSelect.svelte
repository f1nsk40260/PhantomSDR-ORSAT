<script>
  /**
   * KnownFreqSelect — liste des fréquences recommandées d'un mode, avec bouton
   * « Accorder » (ORSAT). items : [{ label, hz }]. Émet « tune » avec { hz }.
   */
  import { createEventDispatcher } from "svelte";
  export let items = [];
  export let title = "Fréquences connues";
  const dispatch = createEventDispatcher();
  let sel = "";
  $: if (items && !items.find((i) => String(i.hz) === sel)) sel = items.length ? String(items[0].hz) : "";
</script>

{#if items && items.length}
  <div class="kfs" title="Choisir une fréquence recommandée pour ce mode, puis l'accorder">
    <span class="kfs-lbl">{title}</span>
    <select bind:value={sel} class="kfs-sel">
      {#each items as it (it.hz)}<option value={String(it.hz)} data-no-i18n>{it.label}</option>{/each}
    </select>
    <button class="kfs-btn" on:click={() => sel && dispatch("tune", { hz: Number(sel) })}
      title="Accorder le récepteur sur cette fréquence (USB)">Accorder</button>
  </div>
{/if}

<style>
  .kfs { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; font-size: 0.72rem; margin-bottom: 0.5rem; }
  .kfs-lbl { color: rgb(207, 181, 59); font-weight: 600; white-space: nowrap; }
  .kfs-sel {
    background: rgba(0, 0, 0, 0.35); color: #e5e7eb; border: 1px solid rgba(207, 181, 59, 0.45);
    border-radius: 0.35rem; padding: 0.1rem 0.35rem; font-size: 0.72rem;
  }
  .kfs-btn {
    padding: 0.1rem 0.6rem; border-radius: 0.35rem; font-weight: 600; white-space: nowrap;
    color: rgb(207, 181, 59); border: 1px solid rgba(207, 181, 59, 0.55); background: rgba(207, 181, 59, 0.08);
  }
  .kfs-btn:hover { background: rgba(207, 181, 59, 0.2); color: #f3e7a6; }
</style>
