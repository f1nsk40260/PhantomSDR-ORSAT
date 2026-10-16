<script>
  // Panneau du décodeur HFDL (HF Data Link, ACARS des avions en HF).
  // Le décodage lui-même est fait par dumphfdl en WebAssembly (hfdl.worker.js),
  // activé par App.svelte ; ce panneau reçoit les trames et les met en forme.
  import { onMount, onDestroy, tick } from "svelte";
  import { HFDL_STATIONS } from "./hfdlStations.js";
  import { AprsMap } from "./aprsMap.js";

  export let audio;
  /** Fréquence USB affichée par le récepteur, en kHz. */
  export let dialKhz = 0;
  /** Appelé avec une fréquence HFDL en kHz quand on clique sur Tune. */
  export let onTune = () => {};
  /** Locator de la station, pour les distances sur la carte. */
  export let homeLocator = "";

  // Carte des avions : la liste des positions est gardée même carte fermée.
  const acMap = new AprsMap(homeLocator);
  let showMap = false;
  let mapError = "";
  let planeCount = 0;
  acMap.onChange = (n) => (planeCount = n);

  function mapMount(node) {
    mapError = "";
    acMap.open(node).then(
      () => acMap.fitAll(),
      (e) => (mapError = "Carte indisponible : " + (e && e.message ? e.message : e)),
    );
    return { destroy: () => acMap.close() };
  }

  // ── Carte grand format : fenêtre flottante, déplaçable et redimensionnable ──
  let bigMap = false;
  let bx = null, by = null, bdrag = null, bwin;
  function openBig() { showMap = false; bigMap = true; }
  function closeBig() { bigMap = false; }
  // La fenêtre est rattachée à <body> : aucun parent (transform, filtre) ne la contraint.
  function portal(node) {
    document.body.appendChild(node);
    return { destroy: () => node.remove() };
  }
  function bigMount(node) {
    mapError = "";
    const r = node.closest(".hfdl-big");
    if (r && bx === null) {
      const w = r.offsetWidth, h = r.offsetHeight;
      bx = Math.max(8, (window.innerWidth - w) / 2);
      by = Math.max(8, (window.innerHeight - h) / 2);
    }
    acMap.open(node).then(
      () => acMap.fitAll(),
      (e) => (mapError = "Carte indisponible : " + (e && e.message ? e.message : e)),
    );
    const ro = new ResizeObserver(() => acMap.invalidate());
    ro.observe(node);
    return { destroy: () => { ro.disconnect(); acMap.close(); } };
  }
  function bigDown(e) {
    if (e.button !== 0 || e.target.closest("button")) return;
    bdrag = { x: e.clientX - bx, y: e.clientY - by };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function bigMove(e) {
    if (!bdrag) return;
    bx = Math.min(Math.max(e.clientX - bdrag.x, 40 - (bwin ? bwin.offsetWidth : 400)), window.innerWidth - 40);
    by = Math.min(Math.max(e.clientY - bdrag.y, 0), window.innerHeight - 36);
  }
  function bigUp() { bdrag = null; }
  function bigKey(e) { if (bigMap && e.key === "Escape") closeBig(); }

  function addPlane(m) {
    if (!m.pos) return;
    const call = m.aircraft || m.acName || "Avion";
    const parts = [m.time + " UTC", m.gsName, m.kind];
    if (m.msgText) parts.push(m.msgText);
    acMap.add({ call, lat: m.pos.lat, lon: m.pos.lon, text: parts.filter(Boolean).join(" · "), time: Date.now() });
  }

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
  let freqOffset = 0;
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
    const regTxt = acars && acars.reg ? String(acars.reg).replace(/^\.+/, "").trim() : "";
    const fltTxt = String((acars && acars.flight) || (flightId ? String(flightId) : "")).trim();
    const icaoTxt = icao ? String(icao).toUpperCase() : "";
    const aircraft = [regTxt, fltTxt, icaoTxt].filter(Boolean);
    // Liens FlightAware : vol, immatriculation, adresse ICAO 24 bits (Mode S).
    const fa = [];
    if (regTxt) fa.push({ t: regTxt, url: `https://www.flightaware.com/live/flight/${encodeURIComponent(regTxt.replace(/[^A-Za-z0-9]/g, ""))}`, title: "Fiche de l'avion (immatriculation) sur FlightAware" });
    if (fltTxt) {
      // ACARS écrit souvent « AF0123 » : FlightAware attend « AF123 ».
      const f = fltTxt.replace(/[^A-Za-z0-9]/g, "").replace(/^([A-Za-z]{2,3})0+(\d)/, "$1$2");
      fa.push({ t: fltTxt, url: `https://www.flightaware.com/live/flight/${encodeURIComponent(f)}`, title: "Fiche du vol sur FlightAware" });
    }
    if (icaoTxt) fa.push({ t: icaoTxt, url: `https://www.flightaware.com/live/modes/${encodeURIComponent(icaoTxt.toLowerCase())}/redirect`, title: "Avion identifié par son transpondeur (ICAO 24 bits) sur FlightAware" });
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
      fa,
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
      freqOffset = ev.freqOffset || 0;
    } else if (ev.type === "msg") {
      status = "ready";
      const m = summarize(ev.msg, ev.text);
      messages = [...messages, m].slice(-MAX_ROWS);
      addPlane(m);
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
    acMap.clear();
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
        title="Afficher la carte des avions dont une position a été reçue"
        class="text-green-100 {showMap ? 'bg-green-700' : 'bg-green-900'} hover:bg-green-800 text-xs px-2 py-0.5 rounded border border-green-700 hover:border-green-500 transition-colors"
        on:click={() => { bigMap = false; showMap = !showMap; }}>🗺 Carte ({planeCount})</button
      >
      <button
        title="Ouvrir la carte des avions dans une grande fenêtre déplaçable et redimensionnable"
        class="text-green-100 {bigMap ? 'bg-green-700' : 'bg-green-900'} hover:bg-green-800 text-xs px-2 py-0.5 rounded border border-green-700 hover:border-green-500 transition-colors"
        on:click={() => (bigMap ? closeBig() : openBig())}>⤢ Grand format</button
      >
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

  {#if showMap}
    <div class="mb-2">
      <div use:mapMount class="w-full rounded border border-gray-700" style="height: 320px;"></div>
      {#if mapError}
        <div class="text-xs text-red-400 mt-1">{mapError}</div>
      {:else if planeCount === 0}
        <div class="text-xs text-gray-500 mt-1 italic">Aucune position reçue pour l'instant : seuls certains messages (rapports de position, données de performance) en contiennent.</div>
      {/if}
    </div>
  {/if}

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
      Rythme : {#if locked}<span class="font-mono text-green-300">verrouillé ({ratePpm >= 0 ? "+" : ""}{(ratePpm / 10000).toFixed(1)} %)</span>{#if freqOffset}&nbsp;·&nbsp;<span class="font-mono text-green-300" title="Écart de fréquence rattrapé par le décodeur (erreur d'horloge du récepteur ou accord approximatif)">écart {freqOffset > 0 ? "+" : ""}{freqOffset} Hz</span>{/if}{:else}<span class="text-gray-500 italic">recherche</span>{/if}
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
          Aucun message d'avion pour l'instant ({counts.squitter} squitter(s) reçu(s), cochez « Squitters » pour les voir).
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
          {#if m.fa && m.fa.length}
            <span class="text-yellow-300 font-semibold" data-no-i18n>
              {#each m.fa as a, i}{#if i}<span class="text-gray-500"> · </span>{/if}<a
                  href={a.url} target="_blank" rel="noopener noreferrer"
                  class="hover:underline hover:text-yellow-200" title={a.title}
                  on:click|stopPropagation>{a.t}</a>{/each}
            </span>
          {:else if m.aircraft}<span class="text-yellow-300 font-semibold">{m.aircraft}</span>{/if}
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

<svelte:window on:keydown={bigKey} />

{#if bigMap}
  <div
    use:portal
    bind:this={bwin}
    class="hfdl-big"
    role="dialog"
    aria-label="Carte HFDL"
    style={bx === null ? "visibility:hidden" : `left:${bx}px; top:${by}px`}
  >
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="hfdl-big-head" class:dragging={bdrag}
      on:pointerdown={bigDown} on:pointermove={bigMove} on:pointerup={bigUp} on:pointercancel={bigUp}
      title="Glisser pour déplacer la fenêtre">
      <span class="hfdl-grip" aria-hidden="true">⠿</span>
      <span class="hfdl-big-title">HFDL — carte des avions ({planeCount})</span>
      <span style="flex:1"></span>
      <button class="hfdl-big-btn" on:click={() => acMap.fitAll()} title="Recadrer sur tous les avions">⌖ Tout voir</button>
      <button class="hfdl-big-btn" on:click={closeBig} title="Fermer" aria-label="Fermer">✕</button>
    </div>
    <div class="hfdl-big-map" use:bigMount></div>
    {#if mapError}
      <div class="hfdl-big-note err">{mapError}</div>
    {:else if planeCount === 0}
      <div class="hfdl-big-note">Aucune position reçue pour l'instant : seuls certains messages (rapports de position, données de performance) en contiennent.</div>
    {/if}
  </div>
{/if}

<style>
  .hfdl-big {
    position: fixed; z-index: 1000;
    width: min(1100px, calc(100vw - 16px)); height: min(72vh, 760px);
    min-width: 420px; min-height: 280px;
    max-width: calc(100vw - 8px); max-height: calc(100vh - 8px);
    resize: both; overflow: hidden;
    display: flex; flex-direction: column;
    border-radius: 8px; background: rgba(17, 24, 39, 0.97);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(207, 181, 59, 0.45);
  }
  .hfdl-big-head {
    display: flex; align-items: center; gap: 10px; padding: 6px 10px;
    border-bottom: 1px solid #374151; background: rgba(207, 181, 59, 0.10);
    cursor: grab; user-select: none; touch-action: none;
  }
  .hfdl-big-head.dragging { cursor: grabbing; }
  .hfdl-grip { color: rgb(207, 181, 59); font-size: 15px; line-height: 1; }
  .hfdl-big-title { color: #f3e7a6; font-weight: 600; font-size: 13px; }
  .hfdl-big-btn {
    padding: 2px 8px; border-radius: 5px; font-size: 12px; font-weight: 600;
    color: rgb(207, 181, 59); background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(207, 181, 59, 0.55);
  }
  .hfdl-big-btn:hover { background: rgba(207, 181, 59, 0.18); }
  .hfdl-big-map { flex: 1; min-height: 0; }
  .hfdl-big-note { font-size: 11px; color: #9ca3af; font-style: italic; padding: 4px 10px; }
  .hfdl-big-note.err { color: #f87171; font-style: normal; }
</style>
