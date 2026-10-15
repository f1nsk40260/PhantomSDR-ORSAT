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
  import { createEventDispatcher } from "svelte";
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
      <span class="modeid-title">Decoder ID</span>
      <span class="text-gray-400 text-[11px]">Reconnaissance automatique du mode numérique entendu</span>
    </div>
    <span class="flex-1"></span>
    <button
      class="modeid-switch {on ? 'is-on' : ''}"
      on:click={() => dispatch("toggle")}
      title="Identify the digital mode in the passband. Off by default — it only uses CPU while it is on."
      aria-pressed={on}
    >
      <span class="modeid-knob" aria-hidden="true"></span>
      <span>{on ? "Analyse : ON" : "Analyse : OFF"}</span>
    </button>
    <button
      class="modeid-lookup"
      on:click={() => dispatch("identify")}
      title="Chercher dans la base de signaux de référence ce qui correspond à la fréquence, à la largeur du filtre et à la démodulation en cours"
    >
      📚 Que peut être ce signal ?
    </button>
  </div>

  <!-- Ligne 2 : le verdict -->
  <div class="modeid-result flex flex-wrap items-center gap-x-3 gap-y-1.5">
    {#if !on}
      <span class="text-gray-500">Activez l'analyse : le mode est reconnu en 15 s environ (FT8, WSPR, RTTY, PSK, Olivia, CW…).</span>
    {/if}
    {#if on}
      {#if !ready}
        <!-- The cadence measurements need ~15 s before FT8/WSPR timing means
             anything, so say so rather than showing a half-formed guess. -->
        <span class="text-gray-400 whitespace-nowrap">Listening…</span>
        <div class="flex-1 h-2.5 bg-gray-700 rounded overflow-hidden min-w-[4rem]">
          <div class="h-full bg-blue-500 transition-all" style="width:{pct(fill)}"></div>
        </div>
        <span class="text-gray-500 whitespace-nowrap">{pct(fill)}</span>
      {:else if !best}
        <span class="text-gray-400 whitespace-nowrap">
          {result && result.quiet ? "Nothing above the noise" : "Not recognised"}
        </span>
        {#if measured}
          <span class="text-gray-500 flex-1 truncate">{measured}</span>
        {:else}
          <span class="flex-1"></span>
        {/if}
        {#if offCentre}
          <button
            class="px-3 py-0.5 rounded bg-amber-700 hover:bg-amber-600 text-white whitespace-nowrap transition-colors"
            on:click={() => dispatch("recentre")}
            title="The signal is near the edge of the passband, where the measurement is unreliable. Move the dial so it sits mid-passband, then measure again."
          >
            Recentre &amp; retry
          </button>
        {/if}
      {:else}
        <span class="{tone(best.score)} font-bold text-base whitespace-nowrap" title={best.why}>
          {best.label}
        </span>
        {#if bestRef}
          <button
            class="px-1 rounded text-blue-300 hover:bg-gray-700 hover:text-blue-200 transition-colors"
            on:click={() => dispatch("info", bestRef)}
            title="Fiche de référence : spectre, son et description du mode"
            aria-label="Fiche de référence"
          >ⓘ</button>
        {/if}
        {#if best.onPlan}
          <span
            class="text-blue-300 whitespace-nowrap"
            title="This is a known calling frequency for that mode, which is part of why it ranks first."
          >📻</span>
        {/if}
        <span class="text-gray-400 whitespace-nowrap">{pct(best.score)}</span>

        {#if measured}
          <span class="text-gray-500 flex-1 truncate" title="Measured from the signal">
            {measured}
          </span>
        {:else}
          <span class="flex-1"></span>
        {/if}

        {#if rest.length}
          <span class="text-gray-600 whitespace-nowrap">or</span>
          {#each rest as c}
            <button
              class="px-1.5 py-0.5 rounded text-gray-400 whitespace-nowrap transition-colors {c.key
                ? 'hover:bg-gray-700 hover:text-gray-200'
                : 'opacity-60 cursor-default'}"
              on:click={() => c.key && dispatch("tune", c)}
              title={c.key ? c.why : `${c.why} — no decoder for this mode`}
            >
              {c.label.split(" (")[0]}
              <span class="text-gray-600">{pct(c.score)}</span>
            </button>
          {/each}
        {/if}

        {#if offCentre}
          <button
            class="px-3 py-0.5 rounded bg-amber-700 hover:bg-amber-600 text-white whitespace-nowrap transition-colors"
            on:click={() => dispatch("recentre")}
            title="The signal is near the edge of the passband, where the measurement is unreliable. Move the dial so it sits mid-passband, then measure again."
          >
            Recentre &amp; retry
          </button>
        {/if}
        {#if best.key}
          <button
            class="px-3 py-0.5 rounded bg-green-700 hover:bg-green-600 text-white whitespace-nowrap transition-colors"
            on:click={() => dispatch("tune", best)}
            title="Switch to the decoder for this mode"
          >
            Use {best.label.split(" (")[0]}
          </button>
        {:else}
          <span
            class="text-gray-500 whitespace-nowrap"
            title="Identified, but this build has no decoder for it."
          >no decoder</span>
        {/if}
      {/if}
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
</style>