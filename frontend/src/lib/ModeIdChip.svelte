<script>
  /**
   * ModeIdChip — the "what am I listening to?" readout that sits under the
   * Decoders heading, above the one-touch decoder buttons.
   *
   * Deliberately suggests rather than acts: it never switches the decoder by
   * itself, because a misidentification would then yank the operator out of a
   * decoder they had chosen on purpose.  The best guess gets a Tune button, and
   * the runners-up sit alongside it so a wrong top answer costs nothing.
   *
   * The frame sits on its own line under the heading and is full width, so the
   * layout runs left-to-right — verdict, what was measured, then the actions.
   * It wraps rather than overflowing: the parent lives inside screw-col-2, and
   * nothing here may grow past that column.
   */
  import { createEventDispatcher, onMount, onDestroy } from "svelte";
  import { refIdForCandidate } from "./signalRefs.js";
  const dispatch = createEventDispatcher();

  export let on = false;
  export let result = null;
  /** Candidates after the band plan has been applied — see modePriors.js. */
  export let ranked = [];
  /** Set when the signal sits where measurement is unreliable — see App.svelte. */
  export let offCentre = false;

  $: fill = result && result.fill ? result.fill : 0;
  $: ready = !!(result && result.ready);
  // Prefer the band-plan ranking; fall back to the raw one if it is absent.
  $: candidates = (ranked && ranked.length ? ranked : (result && result.candidates)) || [];
  $: best = candidates[0] || null;
  $: rest = candidates.slice(1);
  // Fiche de référence (Artemis) du mode reconnu, s'il en existe une.
  $: bestRef = refIdForCandidate(best);
  $: features = (result && result.features) || null;

  /** What was actually measured — the evidence behind the verdict. */
  $: measured = features
    ? [
        features.bwHz ? `${features.bwHz.toFixed(0)} Hz wide` : null,
        features.toneSpacingHz ? `${features.toneSpacingHz.toFixed(0)} Hz shift` : null,
        features.baud ? `${features.baud.toFixed(2)} Bd` : null,
        features.envRate ? `${features.envRate.toFixed(1)} Bd env` : null,
        features.gridSec
          ? `${features.gridSec} s grid`
          : features.slowGridSec
            // Recovered by folding the history onto the grid rather than from
            // whole bursts, which is how a fading signal is placed at all.  Said
            // differently on purpose: it is weaker evidence and scores lower.
            ? `${features.slowGridSec} s grid (through fading)`
            : null,
        features.burstSec
          ? `${features.burstSec.toFixed(1)} s burst`
          : features.runSec
            ? `${features.runSec.toFixed(0)} s on air`
            : null,
        features.keyRate ? `${(features.keyRate * 1.2).toFixed(0)} WPM` : null,
        features.snrDb ? `${features.snrDb.toFixed(0)} dB S/N` : null,
      ]
        .filter(Boolean)
        .join("  ·  ")
    : "";

  // ── Mémoire des verdicts ────────────────────────────────────────────────
  // Chaque mesure remplace la précédente : un mode bien reconnu disparaissait
  // dès la mesure suivante (silence entre deux cycles FT8, fading…). On garde
  // donc chaque mode vu, avec son meilleur score qui s'érode lentement, et on
  // les présente par pertinence. Remise à zéro quand l'analyse est coupée ou
  // que le cadran bouge (App.svelte remet alors result à null).
  const HOLD_S = 120;          // un mode non revu depuis 2 min disparaît
  const DECAY_PER_S = 0.003;   // -18 points de score par minute sans être revu
  const MIN_SCORE = 0.3;
  let memory = new Map();
  let lastResult = null;
  let now = Date.now();
  let timer;
  onMount(() => { timer = setInterval(() => (now = Date.now()), 2000); });
  onDestroy(() => clearInterval(timer));

  $: if (!on || result === null) { memory = new Map(); lastResult = null; }
  $: if (on && ready && result !== lastResult) { lastResult = result; absorb(candidates); }

  function absorb(list) {
    const t = Date.now();
    const m = new Map(memory);
    for (const c of list || []) {
      if (!c || (c.score || 0) < MIN_SCORE) continue;
      const k = c.label;
      const e = m.get(k);
      const kept = e ? e.score - DECAY_PER_S * (t - e.seen) / 1000 : 0;
      m.set(k, { c, score: Math.max(c.score, kept), seen: t, hits: (e ? e.hits : 0) + 1 });
    }
    memory = m;
    now = t;
  }

  $: memList = [...memory.values()]
    .map((e) => ({ ...e, eff: Math.max(0, e.score - DECAY_PER_S * (now - e.seen) / 1000),
                   age: Math.round((now - e.seen) / 1000) }))
    .filter((e) => e.age < HOLD_S)
    .sort((a, b) => b.eff - a.eff)
    .slice(0, 5);

  function ago(s) {
    if (s < 4) return "à l'instant";
    if (s < 60) return `il y a ${s} s`;
    return `il y a ${Math.round(s / 60)} min`;
  }

  function pct(x) {
    return `${Math.round((x || 0) * 100)}%`;
  }

  /** Green when we are confident, amber when it is a guess. */
  function tone(score) {
    if (score >= 0.75) return "text-green-400";
    if (score >= 0.5) return "text-yellow-300";
    return "text-orange-300";
  }
</script>

<div class="glass-window modeid-panel rounded-md px-3 py-2.5 text-xs w-full">
  <!-- Ligne 1 : titre, explication, interrupteur d'analyse et recherche manuelle -->
  <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
    <span class="modeid-icon" aria-hidden="true">📡</span>
    <div class="flex flex-col leading-tight min-w-0">
      <span class="modeid-title">ANALYSE DES SIGNAUX NUMÉRIQUES</span>
      <span class="text-gray-400 text-[11px]">Tente de reconnaître le signal</span>
    </div>
    <span class="flex-1"></span>
    <button
      class="modeid-switch {on ? 'is-on' : ''}"
      on:click={() => dispatch("toggle")}
      title="Analyse en continu le signal de la bande passante. Désactivée par défaut : ne consomme du processeur que lorsqu'elle est active."
      aria-pressed={on}
    >
      <span class="modeid-knob" aria-hidden="true"></span>
      <span>{on ? "Analyse automatique : ON" : "Analyse automatique : OFF"}</span>
    </button>
    <button
      class="modeid-lookup"
      on:click={() => dispatch("identify")}
      title="Chercher dans la base de signaux de référence ce qui correspond à la fréquence, à la largeur du filtre et à la démodulation en cours"
    >
      📚 Chercher dans la base de signaux
    </button>
  </div>

  <!-- Ligne 2 : le verdict -->
  <div class="modeid-result flex flex-wrap items-center gap-x-3 gap-y-1.5">
    {#if !on}
      <span class="text-gray-500">Activez l'analyse : le mode est reconnu en 15 s environ (FT8, WSPR, RTTY, PSK, Olivia, CW…).</span>
    {:else}
      <div class="w-full flex flex-col gap-1.5">
        <!-- État de la mesure en cours -->
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          {#if !ready}
            <span class="text-gray-400 whitespace-nowrap">Écoute…</span>
            <div class="flex-1 h-2.5 bg-gray-700 rounded overflow-hidden min-w-[4rem]">
              <div class="h-full bg-blue-500 transition-all" style="width:{pct(fill)}"></div>
            </div>
            <span class="text-gray-500 whitespace-nowrap">{pct(fill)}</span>
          {:else}
            <span class="text-gray-400 whitespace-nowrap">
              {#if best}Mesure en cours :{:else if result && result.quiet}Rien au-dessus du bruit{:else}Non reconnu{/if}
            </span>
            {#if best}<span class="{tone(best.score)} font-semibold whitespace-nowrap">{best.label}</span>{/if}
            {#if measured}
              <span class="text-gray-500 flex-1 truncate" title="Mesuré sur le signal">{measured}</span>
            {:else}
              <span class="flex-1"></span>
            {/if}
          {/if}
          {#if offCentre}
            <button
              class="px-3 py-0.5 rounded bg-amber-700 hover:bg-amber-600 text-white whitespace-nowrap transition-colors"
              on:click={() => dispatch("recentre")}
              title="The signal is near the edge of the passband, where the measurement is unreliable. Move the dial so it sits mid-passband, then measure again."
            >Recentrer &amp; réessayer</button>
          {/if}
        </div>

        {#if memList.length}
          <!-- Modes reconnus, par pertinence : ils restent affichés -->
          <div class="modeid-list">
            <div class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Modes reconnus, par pertinence</div>
            {#each memList as e, i (e.c.label)}
              <div class="modeid-row {i === 0 ? 'is-best' : ''}">
                <span class="modeid-rank">{i + 1}</span>
                <span class="{tone(e.eff)} {i === 0 ? 'text-base font-bold' : 'font-semibold'} whitespace-nowrap" title={e.c.why}>{e.c.label}</span>
                {#if refIdForCandidate(e.c)}
                  <button
                    class="px-1 rounded text-blue-300 hover:bg-gray-700 hover:text-blue-200 transition-colors"
                    on:click={() => dispatch("info", refIdForCandidate(e.c))}
                    title="Fiche de référence : spectre, son et description du mode"
                    aria-label="Fiche de référence"
                  >ⓘ</button>
                {/if}
                {#if e.c.onPlan}
                  <span class="text-blue-300" title="This is a known calling frequency for that mode, which is part of why it ranks first.">📻</span>
                {/if}
                <div class="modeid-bar"><div style="width:{pct(e.eff)}"></div></div>
                <span class="text-gray-300 w-9 text-right">{pct(e.eff)}</span>
                <span class="text-gray-500 whitespace-nowrap text-[11px] w-24" title="Nombre de mesures qui ont reconnu ce mode">vu {e.hits}× · {ago(e.age)}</span>
                {#if e.c.key}
                  <button
                    class="modeid-launch {i === 0 ? 'is-best' : ''}"
                    on:click={() => dispatch("tune", e.c)}
                    title="Switch to the decoder for this mode"
                  >▶ Lancer {e.c.label.split(" (")[0]}</button>
                {:else}
                  <span class="text-gray-500 whitespace-nowrap text-[11px]" title="Identified, but this build has no decoder for it.">pas de décodeur</span>
                {/if}
              </div>
            {/each}
          </div>
        {:else if ready}
          <!-- Rien de reconnu : proposer l'analyse visuelle -->
          <div class="modeid-hint">
            <span>Aucun mode reconnu pour l'instant. Essayez l'analyse visuelle :</span>
            <div class="flex flex-wrap gap-2 mt-1.5">
              <button class="modeid-lookup" on:click={() => dispatch("identify")}
                title="Comparer la forme du signal avec les spectrogrammes et les sons de la base de signaux">📚 Comparer avec la base de signaux</button>
              <button class="modeid-lookup" on:click={() => dispatch("spectro")}
                title="Afficher le spectrogramme audio pour voir la structure du signal (tons, espacement, rythme)">📊 Voir le spectrogramme audio</button>
            </div>
            <span class="text-gray-500 text-[11px] block mt-1.5">Astuce : centrez le signal dans la bande passante et élargissez le filtre s'il est coupé.</span>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .modeid-panel {
    border-left: 3px solid rgb(207, 181, 59);
    box-shadow: inset 0 0 0 1px rgba(207, 181, 59, 0.18);
  }
  .modeid-icon { font-size: 1.35rem; line-height: 1; }
  .modeid-title {
    color: rgb(207, 181, 59);
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: 0.02em;
  }
  .modeid-switch {
    display: inline-flex; align-items: center; gap: 0.45rem;
    padding: 0.3rem 0.7rem 0.3rem 0.35rem; border-radius: 999px;
    background: rgb(55, 65, 81); color: rgb(209, 213, 219);
    font-weight: 600; white-space: nowrap; transition: all 0.2s;
  }
  .modeid-switch:hover { background: rgb(75, 85, 99); }
  .modeid-switch.is-on { background: rgb(37, 99, 235); color: #fff; box-shadow: 0 0 10px rgba(59, 130, 246, 0.5); }
  .modeid-knob {
    width: 1.6rem; height: 0.95rem; border-radius: 999px; position: relative;
    background: rgba(0, 0, 0, 0.35); flex: none;
  }
  .modeid-knob::after {
    content: ""; position: absolute; top: 0.12rem; left: 0.12rem;
    width: 0.71rem; height: 0.71rem; border-radius: 50%; background: #d1d5db;
    transition: transform 0.2s;
  }
  .modeid-switch.is-on .modeid-knob::after { transform: translateX(0.65rem); background: #fff; }
  .modeid-lookup {
    padding: 0.3rem 0.75rem; border-radius: 0.375rem; white-space: nowrap;
    color: rgb(207, 181, 59); border: 1px solid rgba(207, 181, 59, 0.55);
    background: rgba(207, 181, 59, 0.08); font-weight: 600; transition: all 0.2s;
  }
  .modeid-lookup:hover { background: rgba(207, 181, 59, 0.2); color: #f3e7a6; }
  .modeid-result {
    margin-top: 0.55rem; padding-top: 0.5rem; min-height: 2rem;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 0.8rem;
  }
  .modeid-list { display: flex; flex-direction: column; gap: 0.3rem; }
  .modeid-row {
    display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem;
    padding: 0.3rem 0.5rem; border-radius: 0.375rem;
    background: rgba(255, 255, 255, 0.03);
  }
  .modeid-row.is-best { background: rgba(207, 181, 59, 0.08); box-shadow: inset 0 0 0 1px rgba(207, 181, 59, 0.3); }
  .modeid-rank {
    width: 1.2rem; height: 1.2rem; border-radius: 50%; flex: none;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 0.65rem; font-weight: 700; background: rgb(55, 65, 81); color: rgb(209, 213, 219);
  }
  .modeid-row.is-best .modeid-rank { background: rgb(207, 181, 59); color: #111; }
  .modeid-bar { flex: 1; min-width: 3rem; height: 0.45rem; background: rgb(55, 65, 81); border-radius: 999px; overflow: hidden; }
  .modeid-bar > div { height: 100%; background: linear-gradient(90deg, rgb(37, 99, 235), rgb(34, 197, 94)); }
  .modeid-launch {
    padding: 0.2rem 0.6rem; border-radius: 0.375rem; white-space: nowrap; font-weight: 600;
    background: rgb(21, 128, 61); color: #fff; transition: background 0.2s;
  }
  .modeid-launch:hover { background: rgb(22, 163, 74); }
  .modeid-launch:not(.is-best) { background: rgb(55, 65, 81); }
  .modeid-launch:not(.is-best):hover { background: rgb(21, 128, 61); }
  .modeid-hint {
    padding: 0.5rem 0.6rem; border-radius: 0.375rem; color: rgb(209, 213, 219);
    background: rgba(207, 181, 59, 0.06); border: 1px dashed rgba(207, 181, 59, 0.4);
  }
</style>