<script>
  // Réception en diversité (ORSAT).
  //
  // Les récepteurs partenaires sont choisis par l'opérateur dans le panneau
  // d'administration (rubrique « Réception en diversité ») et servis par le
  // proxy en /diversity.json ; l'auditeur ne fait que choisir parmi eux et
  // démarrer. Pas d'adresse libre, pas de liste à gérer : un auditeur ne sait
  // pas juger de la fiabilité d'un récepteur. La correction SNR propre à
  // chaque partenaire est réglée par l'opérateur.
  // Voir diversity.js pour le combineur lui-même.
  import { onMount, onDestroy } from "svelte";
  import { startDiversity, stopDiversity, getDiversityStatus } from "./backend.js";
  import { normalise } from "../diversityList.js";
  import { lang } from "./i18n.js";
  import { PARTNERS as BUILTIN, ORSAT_LOCATOR, locatorLatLon, distanceKm, bearingDeg, flagSvg } from "./diversityPartners.js";

  const T = {
    fr: {
      stOff: "Arrêtée", stWait: "Synchronisation…", stOn: "En marche", stBad: "Erreur", open: "Ouvrir ▸", close: "Fermer ▾",
      title: "Réception en diversité", sub: "Deux récepteurs, toujours le meilleur signal",
      step1: "1. Choisissez un récepteur partenaire", step2: "2. Lancez la diversité", step3: "3. Écoutez",
      none: "Aucun récepteur partenaire n'est proposé pour le moment.",
      start: (n) => `▶ Démarrer avec ${n}`, stop: "■ Arrêter la diversité", pick: "Choisissez d'abord un partenaire",
      listening: "Vous écoutez", local: "ORSAT",
      sync: "Synchronisation des deux récepteurs… (environ 10 à 15 s)", ready: "Synchronisé ✓ — le meilleur signal est choisi en continu",
      fail: "Le partenaire ne répond pas", notCovered: "Ce partenaire ne reçoit pas cette fréquence : choisissez-en un autre",
      noAudio: "Pas encore de son du partenaire…",
      signal: "Qualité du signal", onPartner: (p) => `${p} % du temps sur le partenaire`, saves: (n) => `${n} bascule${n > 1 ? "s" : ""}`,
      az: "azimut", tech: "Détails techniques", km: (d) => `${d} km d'ORSAT`, kiwi: "KiwiSDR", phantom: "PhantomSDR / NovaSDR", uber: "UberSDR", websdr: "WebSDR",
      help: "Comment ça marche ?",
      helpText: "Deux récepteurs éloignés de plusieurs centaines de kilomètres ne reçoivent pas les ondes par le même chemin dans l'ionosphère : quand le signal s'évanouit chez l'un, il reste souvent fort chez l'autre. La diversité écoute les deux en même temps, les synchronise, et vous fait entendre à chaque instant celui qui reçoit le mieux. Les décodeurs, eux, restent sur ORSAT.",
      decoders: "Les décodeurs continuent d'utiliser ORSAT seul ; la diversité ne concerne que le son du haut-parleur.",
      tLink: "liaison", tAligned: "décalage", tSearch: "recherche", tCorr: "corrélation", tAudio: "son distant", tNone: "aucun",
      adBest: (b) => `★ Conseillé sur ${b}`, adOk: "Possible", adLow: (b) => `Peu utile sur ${b}`, adOff: "Hors ligne", adTip: (v, b) => `Entend environ ${v} % de la zone qu’ORSAT entend en ce moment sur ${b} (ionosondes mesurées), par un autre chemin.`, adOffTip: "Ce récepteur ne répond pas en ce moment (vérifié par le serveur toutes les 10 min).",
      tSnrL: "SNR ORSAT", tSnrR: "SNR partenaire", tTrim: "correction", tSw: "bascules",
    },
    en: {
      stOff: "Off", stWait: "Synchronising…", stOn: "Running", stBad: "Error", open: "Open ▸", close: "Close ▾",
      title: "Diversity reception", sub: "Two receivers, always the best signal",
      step1: "1. Choose a partner receiver", step2: "2. Start diversity", step3: "3. Listen",
      none: "No partner receiver is offered at the moment.",
      start: (n) => `▶ Start with ${n}`, stop: "■ Stop diversity", pick: "Choose a partner first",
      listening: "You are hearing", local: "ORSAT",
      sync: "Synchronising the two receivers… (about 10 to 15 s)", ready: "Synchronised ✓ — the best signal is picked continuously",
      fail: "The partner does not answer", notCovered: "This partner does not receive this frequency: choose another one",
      noAudio: "No audio from the partner yet…",
      signal: "Signal quality", onPartner: (p) => `${p} % of the time on the partner`, saves: (n) => `${n} switch${n > 1 ? "es" : ""}`,
      az: "bearing", tech: "Technical details", km: (d) => `${d} km from ORSAT`, kiwi: "KiwiSDR", phantom: "PhantomSDR / NovaSDR", uber: "UberSDR", websdr: "WebSDR",
      help: "How does it work?",
      helpText: "Two receivers several hundred kilometres apart do not get the waves along the same path through the ionosphere: when the signal fades at one, it often stays strong at the other. Diversity listens to both at once, synchronises them and lets you hear, at every moment, the one receiving best. The decoders stay on ORSAT.",
      decoders: "Decoders keep using ORSAT alone; diversity only affects the speaker audio.",
      tLink: "link", tAligned: "delay", tSearch: "searching", tCorr: "correlation", tAudio: "remote audio", tNone: "none",
      adBest: (b) => `★ Recommended on ${b}`, adOk: "Possible", adLow: (b) => `Of little use on ${b}`, adOff: "Offline", adTip: (v, b) => `Hears about ${v} % of the area ORSAT hears right now on ${b} (measured ionosondes), along another path.`, adOffTip: "This receiver is not answering right now (checked by the server every 10 min).",
      tSnrL: "ORSAT SNR", tSnrR: "partner SNR", tTrim: "trim", tSw: "switches",
    },
    es: {
      stOff: "Detenida", stWait: "Sincronizando…", stOn: "En marcha", stBad: "Error", open: "Abrir ▸", close: "Cerrar ▾",
      title: "Recepción en diversidad", sub: "Dos receptores, siempre la mejor señal",
      step1: "1. Elija un receptor asociado", step2: "2. Inicie la diversidad", step3: "3. Escuche",
      none: "No se ofrece ningún receptor asociado por el momento.",
      start: (n) => `▶ Iniciar con ${n}`, stop: "■ Detener la diversidad", pick: "Elija primero un receptor asociado",
      listening: "Está escuchando", local: "ORSAT",
      sync: "Sincronizando los dos receptores… (unos 10 a 15 s)", ready: "Sincronizado ✓ — se elige continuamente la mejor señal",
      fail: "El receptor asociado no responde", notCovered: "Este receptor no recibe esta frecuencia: elija otro",
      noAudio: "Todavía no hay audio del receptor asociado…",
      signal: "Calidad de la señal", onPartner: (p) => `${p} % del tiempo en el receptor asociado`, saves: (n) => `${n} conmutacion${n > 1 ? "es" : ""}`,
      az: "acimut", tech: "Detalles técnicos", km: (d) => `a ${d} km de ORSAT`, kiwi: "KiwiSDR", phantom: "PhantomSDR / NovaSDR", uber: "UberSDR", websdr: "WebSDR",
      help: "¿Cómo funciona?",
      helpText: "Dos receptores separados varios cientos de kilómetros no reciben las ondas por el mismo camino en la ionosfera: cuando la señal se desvanece en uno, a menudo sigue fuerte en el otro. La diversidad escucha los dos a la vez, los sincroniza y le hace oír en cada momento el que mejor recibe. Los decodificadores siguen en ORSAT.",
      decoders: "Los decodificadores siguen usando solo ORSAT; la diversidad solo afecta al audio del altavoz.",
      tLink: "enlace", tAligned: "retardo", tSearch: "buscando", tCorr: "correlación", tAudio: "audio remoto", tNone: "ninguno",
      adBest: (b) => `★ Recomendado en ${b}`, adOk: "Posible", adLow: (b) => `Poco útil en ${b}`, adOff: "Fuera de línea", adTip: (v, b) => `Escucha cerca del ${v} % de la zona que ORSAT escucha ahora en ${b} (ionosondas medidas), por otro camino.`, adOffTip: "Este receptor no responde ahora (comprobado por el servidor cada 10 min).",
      tSnrL: "SNR ORSAT", tSnrR: "SNR asociado", tTrim: "corrección", tSw: "conmutaciones",
    },
  };
  $: D = T[$lang] || T.fr;

  // ── Conseil de partenaire (carnet ORSAT-LOG, /log/api/public/diversity) ──
  // Pour la bande écoutée : part de la zone entendue par ORSAT que le partenaire entend aussi,
  // et disponibilité (sondée par le serveur toutes les 10 min). Sans carnet : aucun badge.
  export let freqKhz = null;
  const HAM = [["160m", 1810, 2000], ["80m", 3500, 3800], ["60m", 5351, 5367], ["40m", 7000, 7200],
    ["30m", 10100, 10150], ["20m", 14000, 14350], ["17m", 18068, 18168], ["15m", 21000, 21450],
    ["12m", 24890, 24990], ["10m", 28000, 29700], ["6m", 50000, 52000]];
  $: fk = parseFloat(freqKhz);
  $: band = !fk ? null : (HAM.find(([, lo, hi]) => fk >= lo && fk <= hi)
    || HAM.reduce((a, b) => (Math.abs(Math.log(fk / ((b[1] + b[2]) / 2))) < Math.abs(Math.log(fk / ((a[1] + a[2]) / 2))) ? b : a)))[0];
  let advice = null;
  async function loadAdvice() {
    try {
      const r = await fetch("/log/api/public/diversity", { cache: "no-store" });
      const d = r.ok ? await r.json() : null;
      advice = d && d.ok ? d : null;
    } catch (_) { advice = null; }
  }
  let adviceTimer;
  onMount(() => { loadAdvice(); adviceTimer = setInterval(loadAdvice, 10 * 60 * 1000); });
  onDestroy(() => clearInterval(adviceTimer));
  // badge d'une carte : best / ok / low / off (hors ligne) / null (pas d'avis)
  function adviceOf(x, adv, b) {
    const a = adv && adv.partners ? adv.partners[x.id] : null;
    if (!a) return null;
    if (a.online === false) return { k: "off" };
    const v = b ? a.bands[b] : null;
    if (v == null) return null;
    return { k: adv.best[b] === x.id && v >= adv.good ? "best" : v >= adv.fair ? "ok" : "low", v };
  }

  const LS_PARTNER = "orsat.diversity.partner";
  let home = locatorLatLon(ORSAT_LOCATOR);
  let partners = BUILTIN.map((x) => ({ ...x, trim: x.trim || 0 }));
  let partnerId = null;
  try { partnerId = localStorage.getItem(LS_PARTNER) || null; } catch (_) {}

  // Liste fixée par l'opérateur (panneau admin). Fichier absent ou illisible :
  // l'annuaire intégré sert de liste par défaut.
  onMount(async () => {
    try {
      const r = await fetch("/diversity.json", { cache: "no-store" });
      if (!r.ok) return;
      const d = await r.json();
      if (d && Array.isArray(d.partners)) {
        partners = d.partners.filter((x) => x && x.enabled !== false && x.addr);
        if (d.locator) home = locatorLatLon(d.locator) || home;
      }
    } catch (_) {}
  });

  $: partner = partners.find((x) => x.id === partnerId) || null;
  $: partnerName = partner ? partner.name : "";
  const posOf = (x) => (x.locator ? locatorLatLon(x.locator) : [x.lat, x.lon]);
  const placeOf = (x) => (x.place && typeof x.place === "object" ? x.place[$lang] || x.place.fr : x.place || "");

  let expanded = false;
  let showTech = false;
  let showHelp = false;
  let running = false;
  let status = { active: false, state: "idle", locked: false };
  let poller = null;
  let polls = 0, pollsRemote = 0;

  function choosePartner(x) {
    if (running) return;
    partnerId = x.id;
    try { localStorage.setItem(LS_PARTNER, x.id); } catch (_) {}
  }

  $: if (running && status.locked) {
    polls += 1;
    if (status.live === "remote") pollsRemote += 1;
  }
  $: sharePct = polls ? Math.round((100 * pollsRemote) / polls) : 0;
  $: waiting = running && (status.state !== "ready" || !status.locked);
  $: bad = running && (status.state === "error" || status.state === "closed");
  $: stateText = !running ? "" : bad ? `${D.fail}${status.errorText ? " — " + status.errorText : ""}`
    : status.inRange === false && status.state === "ready" ? D.notCovered
    : !status.remoteSamples ? D.noAudio : waiting ? D.sync : D.ready;
  const bar = (v) => (v == null ? 0 : Math.max(3, Math.min(100, (v / 40) * 100)));
  const dB = (v) => (v === undefined || v === null ? "—" : v.toFixed(1));

  // Le combineur ne publie que quelques fois par seconde : 500 ms suffisent.
  function startPolling() {
    if (poller) return;
    poller = setInterval(() => {
      try {
        status = getDiversityStatus();
        running = !!status.active;
      } catch (_) {}
    }, 500);
  }
  function stopPolling() {
    if (poller) clearInterval(poller);
    poller = null;
  }

  function toggle() {
    if (running) {
      stopDiversity();
      stopPolling();
      running = false;
      status = { active: false, state: "idle", locked: false };
      return;
    }
    if (!partner) return;
    // Page en https, partenaire en http (la plupart des KiwiSDR) : le navigateur refuse la connexion
    // directe ; elle passe par le relais du serveur ORSAT (/divrelay/<id>/, proxy.py).
    const relayed = location.protocol === "https:" && partner.type !== "websdr" && /^(http|ws):/i.test(String(partner.addr).trim());
    const url = relayed
      ? `wss://${location.host}/divrelay/${encodeURIComponent(partner.id)}` + (partner.type === "phantom" ? "/audio" : "")
      : normalise(partner.addr, partner.type);
    if (!url) return;
    polls = 0;
    pollsRemote = 0;
    if (startDiversity(url, { remoteCalibDb: Number(partner.trim) || 0, type: partner.type })) {
      running = true;
      startPolling();
    }
  }

  onDestroy(() => {
    stopPolling();
    try { stopDiversity(); } catch (_) {}
  });

  $: dotClass = !running ? "bg-gray-500"
    : status.locked ? (status.live === "remote" ? "bg-cyan-400 animate-pulse" : "bg-emerald-400 animate-pulse")
    : "bg-amber-400 animate-pulse";
</script>

<div class="w-full rounded-lg p-4 mt-2 text-left decoder-window decoder-panel">
  <!-- En-tête bien visible : barre dorée, icône, état en clair, bouton Ouvrir / Fermer -->
  <button class="dv-head" class:on={running} class:open={expanded} on:click={() => (expanded = !expanded)}
          title={D.sub} data-no-i18n>
    <span class="dv-ico" aria-hidden="true">📡📡</span>
    <span class="dv-titles">
      <b>{D.title}</b>
      <small>{D.sub}</small>
    </span>
    <span class="dv-badge {bad ? 'bad' : !running ? 'off' : waiting ? 'wait' : 'ok'}">
      <i class="inline-block w-2 h-2 rounded-full {dotClass}"></i>
      {bad ? D.stBad : !running ? D.stOff : waiting ? D.stWait : D.stOn}
    </span>
    <span class="dv-open">{expanded ? D.close : D.open}</span>
  </button>

  {#if expanded}
    <div class="dv" data-no-i18n>
      <div class="dv-top">
        <span class="dv-step">{D.step1}</span>
        <button type="button" class="dv-help-btn" on:click={() => (showHelp = !showHelp)}>{showHelp ? "✕" : "?"} {D.help}</button>
      </div>
      {#if showHelp}<p class="dv-help">{D.helpText}</p>{/if}
      {#if partners.length}
        <div class="dv-cards">
          {#each partners as x (x.id)}
            {@const d = distanceKm(home, posOf(x))}
            {@const az = bearingDeg(home, posOf(x))}
            {@const ad = adviceOf(x, advice, band)}
            <button type="button" class="dv-card" class:sel={partnerId === x.id} class:offline={ad && ad.k === "off"}
                    disabled={running && partnerId !== x.id}
                    title={ad ? (ad.k === "off" ? D.adOffTip : D.adTip(ad.v, band)) : ""}
                    on:click={() => choosePartner(x)}>
              {#if ad}<span class="dv-ad {ad.k}">{ad.k === "best" ? D.adBest(band) : ad.k === "ok" ? `${D.adOk} · ${ad.v} %` : ad.k === "low" ? D.adLow(band) : D.adOff}</span>{/if}
              <b>{#if x.country}<span class="dv-flag" title={x.country}>{@html flagSvg(x.country)}</span>{/if}{x.name}{#if x.call}<i> · {x.call}</i>{/if}</b>
              <span>{placeOf(x)}{d != null ? `${placeOf(x) ? " · " : ""}${D.km(d)}` : ""}</span>
              {#if x.locator || az != null}<em>{x.locator || ""}{x.locator && az != null ? " · " : ""}{az != null ? `${D.az} ${az}°` : ""}</em>{/if}
            </button>
          {/each}
        </div>
      {:else}
        <p class="dv-empty">{D.none}</p>
      {/if}

      <span class="dv-step">{D.step2}</span>
      <button type="button" class="dv-go" class:stop={running} disabled={!running && !partner} on:click={toggle}>
        {running ? D.stop : partner ? D.start(partnerName) : D.pick}
      </button>

      {#if running}
        <span class="dv-step">{D.step3}</span>
        <div class="dv-live">
          <div class="dv-now">🎧 {D.listening} :
            <b class:remote={status.locked && status.live === "remote"}>
              {status.locked && status.live === "remote" ? partnerName : D.local}</b></div>
          <p class="dv-state" class:bad class:ok={!bad && !waiting && status.inRange !== false}>{stateText}</p>
          <div class="dv-bars" title={D.signal}>
            <span>{D.local}</span>
            <div class="dv-bar"><i class:win={status.locked && status.live !== "remote"} style="width:{bar(status.snrLocalDb)}%"></i></div>
            <small>{dB(status.snrLocalDb)} dB</small>
            <span>{partnerName}</span>
            <div class="dv-bar"><i class:win={status.locked && status.live === "remote"} style="width:{bar(status.snrRemoteDb)}%"></i></div>
            <small>{dB(status.snrRemoteDb)} dB</small>
          </div>
          {#if status.locked}<p class="dv-stats">{D.onPartner(sharePct)} · {D.saves(status.switches ?? 0)}</p>{/if}
          <p class="dv-note">{D.decoders}</p>
        </div>

        <button type="button" class="dv-adv-btn" on:click={() => (showTech = !showTech)}>{showTech ? "▾" : "▸"} {D.tech}</button>
        {#if showTech}
          <div class="dv-tech">
            <span>{D.tLink}</span>
            <span>{status.state}{status.errorText ? " — " + status.errorText : ""}{status.closeCode ? ` (${status.closeCode}${status.closeReason ? " " + status.closeReason : ""})` : ""}</span>
            <span>{D.tAligned}</span><span>{status.locked ? (status.delayMs / 1000).toFixed(2) + " s" : D.tSearch}</span>
            <span>{D.tCorr}</span><span>{status.locked ? dB(status.corrPeak * 100) + " %" : "—"}</span>
            <span>{D.tAudio}</span>
            <span class:warn={!status.remoteSamples}>{status.remoteSamples ? (status.remoteSamples / 1000).toFixed(0) + "k @ " + status.remoteRateIn + " Hz" : D.tNone}</span>
            <span>{D.tSnrL}</span><span>{dB(status.snrLocalDb)} dB</span>
            <span>{D.tSnrR}</span><span>{dB(status.snrRemoteDb)} dB</span>
            <span>{D.tTrim}</span><span>{dB(Number(partner?.trim) || 0)} dB</span>
            <span>{D.tSw}</span><span>{status.switches ?? 0}</span>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  /* Partie guidée (ORSAT) */
  .dv-head { width: 100%; display: flex; align-items: center; gap: 12px; cursor: pointer; text-align: left;
             padding: 10px 14px; border-radius: 10px; color: #f2eedf;
             background: linear-gradient(180deg, rgba(207, 181, 59, 0.22), rgba(207, 181, 59, 0.08));
             border: 2px solid rgba(207, 181, 59, 0.85); box-shadow: 0 2px 10px rgba(0, 0, 0, 0.45); }
  .dv-head:hover { background: linear-gradient(180deg, rgba(207, 181, 59, 0.32), rgba(207, 181, 59, 0.12)); }
  .dv-head.on { border-color: #7fe08c; box-shadow: 0 0 12px rgba(127, 224, 140, 0.45); }
  .dv-ico { font-size: 22px; line-height: 1; letter-spacing: -6px; padding-right: 6px; }
  .dv-titles { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
  .dv-titles b { font-size: 17px; color: rgb(226, 201, 90); font-weight: 800; letter-spacing: 0.02em; }
  .dv-titles small { font-size: 12.5px; color: #e6e2d3; }
  .dv-badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 11px; font-size: 12px;
              font-weight: 700; white-space: nowrap; background: #2b2a25; color: #cfc9b2; border: 1px solid #555; }
  .dv-badge.ok { background: rgba(63, 154, 75, 0.35); color: #9ef0a8; border-color: #7fe08c; }
  .dv-badge.wait { background: rgba(224, 160, 48, 0.25); color: #f0c060; border-color: #e0a030; }
  .dv-badge.bad { background: rgba(200, 64, 64, 0.3); color: #ff9a9a; border-color: #ff8080; }
  .dv-open { flex-shrink: 0; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 800; white-space: nowrap;
             color: #1a1606; background: linear-gradient(180deg, #e2c95a, rgb(207, 181, 59)); border: 1px solid #f0dc80; }
  .dv-sub { font-weight: 400; color: #b9b39d; font-size: 0.75rem; }
  .dv { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: #e6e2d3; }
  .dv-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .dv-step { color: rgb(226, 201, 90); font-weight: 700; font-size: 13px; }
  .dv-help-btn { font-size: 12px; padding: 2px 10px; border-radius: 11px; cursor: pointer; color: #1a1606;
                 background: linear-gradient(180deg, #e2c95a, rgb(207, 181, 59)); border: 1px solid #f0dc80; font-weight: 700; }
  .dv-help { margin: 0; padding: 8px 10px; border-radius: 8px; background: rgba(207, 181, 59, 0.1);
             border: 1px solid rgba(207, 181, 59, 0.4); line-height: 1.45; }
  .dv-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 6px; }
  .dv-card { text-align: left; padding: 7px 10px; border-radius: 8px; cursor: pointer; display: flex; flex-direction: column; gap: 2px;
             background: rgba(0, 0, 0, 0.35); border: 1px solid rgba(207, 181, 59, 0.35); color: #e6e2d3; }
  .dv-card:hover:not(:disabled) { border-color: rgb(226, 201, 90); }
  .dv-card.sel { border: 2px solid rgb(226, 201, 90); background: rgba(207, 181, 59, 0.15); }
  .dv-card:disabled { opacity: 0.45; cursor: not-allowed; }
  .dv-card b { color: #fff; font-size: 13px; }
  .dv-card.offline { opacity: 0.6; }
  .dv-card .dv-ad { align-self: flex-start; font-size: 11px; font-weight: 800; padding: 1px 8px; border-radius: 9px; margin-bottom: 2px; }
  .dv-card .dv-ad.best { color: #1a1606; background: linear-gradient(180deg, #9ef0a8, #4fbf5e); }
  .dv-card .dv-ad.ok { color: #f0c060; background: rgba(224, 160, 48, 0.18); border: 1px solid rgba(224, 160, 48, 0.6); }
  .dv-card .dv-ad.low { color: #b9b39d; background: #2b2a25; border: 1px solid #555; }
  .dv-card .dv-ad.off { color: #ff9a9a; background: rgba(200, 64, 64, 0.25); border: 1px solid #ff8080; }
  .dv-card .dv-flag { margin-right: 6px; font-size: inherit; }
  .dv-card i { font-style: normal; color: rgb(226, 201, 90); }
  .dv-card span { font-size: 12px; color: #cfc9b2; }
  .dv-card em { font-style: normal; font-size: 11px; color: #9b9684; }
  .dv-go { padding: 9px 14px; border-radius: 9px; font-size: 14px; font-weight: 800; cursor: pointer;
           color: #fff; background: linear-gradient(180deg, #3f9a4b, #2a6e34); border: 1px solid #7fe08c; }
  .dv-go.stop { background: linear-gradient(180deg, #c84040, #8e1f1f); border-color: #ff9a9a; }
  .dv-go:disabled { opacity: 0.5; cursor: not-allowed; background: #2b2a25; border-color: #555; color: #9b9684; }
  .dv-live { display: flex; flex-direction: column; gap: 6px; padding: 8px 10px; border-radius: 8px;
             background: rgba(0, 0, 0, 0.4); border: 1px solid rgba(207, 181, 59, 0.35); }
  .dv-now { font-size: 15px; }
  .dv-now b { color: #7fe08c; font-size: 16px; }
  .dv-now b.remote { color: #6ad0e8; }
  .dv-state { margin: 0; font-size: 12px; color: #f0c060; }
  .dv-state.ok { color: #7fe08c; }
  .dv-state.bad { color: #ff8080; }
  .dv-bars { display: grid; grid-template-columns: auto 1fr auto; gap: 4px 8px; align-items: center; font-size: 12px; }
  .dv-bar { height: 10px; border-radius: 5px; background: #2b2a25; overflow: hidden; }
  .dv-bar i { display: block; height: 100%; background: #7f7a66; transition: width 0.4s; }
  .dv-bar i.win { background: linear-gradient(90deg, #3f9a4b, #7fe08c); }
  .dv-bars small { font-family: ui-monospace, monospace; color: #cfc9b2; }
  .dv-stats { margin: 0; font-size: 12px; color: #cfc9b2; }
  .dv-note { margin: 0; font-size: 11px; color: #9b9684; }
  .dv-adv-btn { align-self: flex-start; background: transparent; border: 0; color: #b9b39d; cursor: pointer; font-size: 12px; padding: 2px 0; }
  .dv-adv-btn:hover { color: rgb(226, 201, 90); }
  .dv-empty { margin: 0; padding: 8px 10px; border-radius: 8px; color: #f0c060; background: rgba(0, 0, 0, 0.35);
              border: 1px dashed rgba(207, 181, 59, 0.5); }
  .dv-tech { display: grid; grid-template-columns: auto 1fr; gap: 2px 14px; font-family: ui-monospace, monospace; font-size: 11px;
             padding: 8px 10px; border-radius: 8px; background: rgba(0, 0, 0, 0.4); color: #cfc9b2; }
  .dv-tech span:nth-child(odd) { color: #9b9684; }
  .dv-tech .warn { color: #f0c060; }
</style>
