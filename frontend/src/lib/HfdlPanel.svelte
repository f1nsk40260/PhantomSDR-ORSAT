<script>
  // Panneau du décodeur HFDL (HF Data Link, ACARS des avions en HF).
  // Le décodage lui-même est fait par dumphfdl en WebAssembly (hfdl.worker.js),
  // activé par App.svelte ; ce panneau reçoit les trames et les met en forme.
  import { onMount, onDestroy, tick } from "svelte";
  import { HFDL_STATIONS } from "./hfdlStations.js";

  export let audio;
  /** Fréquence USB affichée par le récepteur, en kHz. */
  export let dialKhz = 0;
  /** Appelé avec une fréquence HFDL en kHz quand on clique sur Tune. */
  export let onTune = () => {};

  const MAX_ROWS = 300;
  const STATIONS = [...HFDL_STATIONS].sort((a, b) => a.name.localeCompare(b.name));
  const STATION_BY_ID = new Map(HFDL_STATIONS.map((s) => [s.id, s]));

  let status = "loading"; // loading | ready | error
  let errorText = "";
  let noiseDb = null;
  let syncing = false;
  let frames = 0;
  let locked = false;
  let ratePpm = 0;
  let messages = [];
  let showSquitters = false;
  let selectedStation = _nearestStationForDial(dialKhz)?.id ?? STATIONS[0].id;
  let selectedFreq = _defaultFreq(selectedStation);
  let scrollEl;
  let followTail = true;

  $: station = STATION_BY_ID.get(Number(selectedStation));
  $: freqChoices = station ? [...station.freqs].sort((a, b) => b - a) : [];
  $: shown = showSquitters ? messages : messages.filter((m) => !m.squitter);
  $: counts = {
    lpdu: messages.filter((m) => !m.squitter).length,
    squitter: messages.filter((m) => m.squitter).length,
  };
  $: onStationFreq = HFDL_STATIONS.some((s) =>
    s.freqs.some((f) => Math.abs(f - Number(dialKhz)) < 0.05),
  );

  function _nearestStationForDial(khz) {
    const k = Number(khz);
    for (const s of HFDL_STATIONS) {
      if (s.freqs.some((f) => Math.abs(f - k) < 0.05)) return s;
    }
    return null;
  }

  function _defaultFreq(id) {
    const s = STATION_BY_ID.get(Number(id));
    if (!s) return "";
    const k = Number(dialKhz);
    const exact = s.freqs.find((f) => Math.abs(f - k) < 0.05);
    if (exact) return String(exact);
    // The closest one to where the receiver is, so the band stays the same.
    const best = [...s.freqs].sort((a, b) => Math.abs(a - k) - Math.abs(b - k))[0];
    return String(best);
  }

  function stationChanged() {
    selectedFreq = _defaultFreq(selectedStation);
  }

  function tune() {
    const khz = Number(selectedFreq);
    if (khz > 0) onTune(khz);
  }

  // ── Reading dumphfdl's JSON ──────────────────────────────────────────────

  function find(obj, key, depth = 0) {
    if (!obj || typeof obj !== "object" || depth > 8) return undefined;
    if (Object.prototype.hasOwnProperty.call(obj, key)) return obj[key];
    for (const v of Object.values(obj)) {
      const r = find(v, key, depth + 1);
      if (r !== undefined) return r;
    }
    return undefined;
  }

  function entityLabel(e) {
    if (!e) return "";
    if (e.type === "Ground station") {
      const s = STATION_BY_ID.get(e.id);
      return e.name || (s ? s.name : `GS ${e.id}`);
    }
    if (e.type === "Aircraft") return `AC ${e.id}`;
    return e.name || `${e.type || "?"} ${e.id ?? ""}`.trim();
  }

  function summarize(msg, text) {
    const h = (msg && msg.hfdl) || {};
    const pdu = h.lpdu || h.spdu || {};
    const squitter = !!h.spdu && !h.lpdu;
    const t = h.t && h.t.sec ? new Date(h.t.sec * 1000) : new Date();
    const src = pdu.src;
    const dst = pdu.dst;
    const uplink = src && src.type === "Ground station";
    const gs = uplink ? src : dst && dst.type === "Ground station" ? dst : src;
    const acars = find(pdu, "acars");
    const icao = find(pdu, "icao");
    const flightId = find(pdu, "flight_id");
    const pos = find(pdu, "pos");
    const hfnpdu = pdu.hfnpdu;
    const kind = squitter
      ? "Squitter"
      : (acars && "ACARS") ||
        (hfnpdu && hfnpdu.type && hfnpdu.type.name) ||
        (pdu.type && pdu.type.name) ||
        "LPDU";
    const validPos =
      pos &&
      Number.isFinite(pos.lat) &&
      Number.isFinite(pos.lon) &&
      Math.abs(pos.lat) <= 90 &&
      Math.abs(pos.lon) <= 180 &&
      !(pos.lat === 0 && pos.lon === 0);
    const aircraft = [
      acars && acars.reg ? String(acars.reg).replace(/^\.+/, "") : "",
      (acars && acars.flight) || (flightId ? String(flightId).trim() : ""),
      icao ? String(icao).toUpperCase() : "",
    ].filter(Boolean);
    return {
      id: `${h.t ? h.t.sec + "." + h.t.usec : Date.now()}-${Math.random()}`,
      time: t.toISOString().slice(11, 19),
      freqKhz: h.freq ? (h.freq / 1000).toFixed(1) : "",
      snr:
        Number.isFinite(h.sig_level) && Number.isFinite(h.noise_level)
          ? h.sig_level - h.noise_level
          : null,
      bps: h.bit_rate || null,
      squitter,
      uplink: !!uplink,
      gsName: entityLabel(gs),
      acName: uplink ? entityLabel(dst) : entityLabel(src),
      aircraft: aircraft.join(" · "),
      kind,
      label: acars && acars.label ? acars.label : "",
      msgText: acars && acars.msg_text ? String(acars.msg_text).trim() : "",
      pos: validPos ? { lat: pos.lat, lon: pos.lon } : null,
      text: text || "",
    };
  }

  async function onEvent(ev) {
    if (!ev) return;
    if (ev.type === "ready") {
      status = "ready";
    } else if (ev.type === "error") {
      status = "error";
      errorText = ev.message || "";
    } else if (ev.type === "stats") {
      noiseDb = ev.noiseDb;
      syncing = ev.state > 1;
      frames = ev.frames;
      locked = !!ev.locked;
      ratePpm = ev.ratePpm || 0;
    } else if (ev.type === "msg") {
      status = "ready";
      messages = [...messages, summarize(ev.msg, ev.text)].slice(-MAX_ROWS);
      if (followTail) {
        await tick();
        if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
      }
    }
  }

  function onScroll() {
    if (!scrollEl) return;
    followTail =
      scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < 40;
  }

  function clear() {
    messages = [];
  }

  function save() {
    const body = messages.map((m) => m.text || "").join("\n");
    const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `hfdl_${new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19)}Z.txt`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 1000);
  }

  function mapUrl(p) {
    return `https://www.openstreetmap.org/?mlat=${p.lat.toFixed(4)}&mlon=${p.lon.toFixed(4)}#map=6/${p.lat.toFixed(3)}/${p.lon.toFixed(3)}`;
  }

  onMount(() => {
    if (audio && typeof audio.setHFDLCallback === "function")
      audio.setHFDLCallback(onEvent);
  });

  onDestroy(() => {
    if (audio && typeof audio.setHFDLCallback === "function")
      audio.setHFDLCallback(null);
  });
</script>

<div class="w-full rounded-lg p-4 mt-6 text-left decoder-window decoder-panel">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
    <h4 class="text-white font-semibold flex items-center gap-2 text-sm">
      <span
        class="inline-block w-2 h-2 rounded-full {status === 'error'
          ? 'bg-red-500'
          : syncing
            ? 'bg-green-400 animate-pulse'
            : 'bg-sky-400 animate-pulse'}"
      ></span>
      HFDL Receiver
      {#if status === "loading"}
        <span class="text-xs text-gray-500 font-normal italic">chargement du décodeur…</span>
      {:else if status === "error"}
        <span class="text-xs text-red-400 font-normal" title={errorText}>décodeur indisponible</span>
      {:else if syncing}
        <span class="text-xs text-green-300 font-mono font-normal">[trame en cours]</span>
      {:else}
        <span class="text-xs text-gray-500 font-normal italic">en attente d'une trame…</span>
      {/if}
    </h4>
    <div class="flex items-center gap-1">
      <button
        title="Enregistrer les messages HFDL décodés (texte)"
        class="text-green-100 bg-green-900 hover:bg-green-800 text-xs px-2 py-0.5 rounded border border-green-700 hover:border-green-500 transition-colors"
        on:click={save}
        disabled={messages.length === 0}>💾 Save</button
      >
      <button
        title="Effacer les messages HFDL"
        class="text-green-100 bg-green-900 hover:bg-green-800 text-xs px-2 py-0.5 rounded border border-green-700 hover:border-green-500 transition-colors"
        on:click={clear}>Clear</button
      >
    </div>
  </div>

  <!-- Station + frequency + Tune -->
  <div class="flex flex-wrap items-center gap-2 mb-2">
    <select
      bind:value={selectedStation}
      on:change={stationChanged}
      title="Station sol HFDL"
      class="glass-select text-white text-xs px-2 py-1 rounded-md flex-1 min-w-0"
    >
      {#each STATIONS as s}
        <option value={s.id}>{s.name}</option>
      {/each}
    </select>
    <select
      bind:value={selectedFreq}
      title="Fréquence de la station (kHz, USB)"
      class="glass-select text-white text-xs px-2 py-1 rounded-md"
    >
      {#each freqChoices as f}
        <option value={String(f)}>{f.toFixed(1)} kHz</option>
      {/each}
    </select>
    <button
      title="Accorder le récepteur sur cette fréquence HFDL en USB et régler le filtre FI"
      class="text-xs px-2 py-1 rounded bg-sky-700 hover:bg-sky-600 text-white transition-colors whitespace-nowrap"
      on:click={tune}>⇒ Tune &amp; Set IF</button
    >
  </div>

  <!-- Status line -->
  <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400 mb-2">
    <span title="Fréquence actuellement écoutée">
      Dial : <span class="font-mono text-gray-200">{Number(dialKhz).toFixed(1)} kHz</span>
      {#if !onStationFreq}
        <span class="text-amber-400" title="La fréquence écoutée n'est pas une fréquence HFDL connue : choisissez une station puis Tune"> ⚠ hors fréquence HFDL</span>
      {/if}
    </span>
    {#if noiseDb !== null && Number.isFinite(noiseDb)}
      <span title="Plancher de bruit mesuré par le décodeur">Bruit : <span class="font-mono text-gray-200">{noiseDb.toFixed(1)} dBFS</span></span>
    {/if}
    <span title="Trames HFDL décodées depuis l'activation">Trames : <span class="font-mono text-gray-200">{frames}</span></span>
    <span title="Le décodeur cherche le rythme exact de l'audio (±1 %) et s'y verrouille dès qu'une trame est décodée">
      Rythme : {#if locked}<span class="font-mono text-green-300">verrouillé ({ratePpm >= 0 ? "+" : ""}{(ratePpm / 10000).toFixed(1)} %)</span>{:else}<span class="text-gray-500 italic">recherche</span>{/if}
    </span>
    <span title="Messages (hors squitters) / squitters des stations sol">
      Messages : <span class="font-mono text-gray-200">{counts.lpdu}</span> · Squitters : <span class="font-mono text-gray-200">{counts.squitter}</span>
    </span>
    <label class="flex items-center gap-1 cursor-pointer" title="Afficher aussi les squitters (annonces périodiques des stations sol, toutes les 32 s)">
      <input type="checkbox" bind:checked={showSquitters} />
      Squitters
    </label>
  </div>

  <!-- Messages -->
  <div
    bind:this={scrollEl}
    on:scroll={onScroll}
    class="rounded-md bg-gray-900 recess-window overflow-y-auto custom-scrollbar text-xs font-mono"
    style="height: 320px;"
  >
    {#if shown.length === 0}
      <div class="p-3 text-gray-500 italic font-sans">
        {#if messages.length === 0}
          Choisissez une station sol, cliquez sur « Tune », puis patientez : les stations émettent un squitter toutes les 32 s, et les avions répondent quand ils ont du trafic.
        {:else}
          Aucun message d'avion pour l'instant ({counts.squitter} squitter{counts.squitter > 1 ? "s" : ""} reçu{counts.squitter > 1 ? "s" : ""}, cochez « Squitters » pour les voir).
        {/if}
      </div>
    {/if}
    {#each shown as m (m.id)}
      <div class="px-2 py-1.5 border-b border-gray-800" title={m.text}>
        <div class="flex flex-wrap items-center gap-x-2">
          <span class="text-gray-500">{m.time}</span>
          <span class="text-gray-400">{m.freqKhz}</span>
          <span class={m.uplink ? "text-sky-300" : "text-amber-300"}
            title={m.uplink ? "Montant : station sol → avion" : "Descendant : avion → station sol"}
            >{m.uplink ? "▼ sol→avion" : "▲ avion→sol"}</span
          >
          <span class="text-gray-200">{m.gsName}</span>
          {#if !m.squitter && m.acName}<span class="text-gray-400">{m.acName}</span>{/if}
          {#if m.aircraft}<span class="text-yellow-300 font-semibold">{m.aircraft}</span>{/if}
          <span class="text-teal-300">{m.kind}{m.label ? ` ${m.label}` : ""}</span>
          {#if m.snr !== null}<span class="text-gray-500">{m.snr.toFixed(0)} dB</span>{/if}
          {#if m.bps}<span class="text-gray-600">{m.bps} bps</span>{/if}
          {#if m.pos}
            <a
              href={mapUrl(m.pos)}
              target="_blank"
              rel="noopener noreferrer"
              class="text-green-300 underline"
              title="Voir la position de l'avion sur une carte"
              >📍 {m.pos.lat.toFixed(2)}, {m.pos.lon.toFixed(2)}</a
            >
          {/if}
        </div>
        {#if m.msgText}
          <div class="text-gray-100 whitespace-pre-wrap break-words mt-0.5">{m.msgText}</div>
        {/if}
      </div>
    {/each}
  </div>
  <p class="text-[11px] text-gray-500 mt-2 font-sans">
    Décodeur dumphfdl (GPL-3) en WebAssembly, sur l'audio USB avant les filtres d'écoute. Survolez un message pour voir la trame complète.
  </p>
</div>
