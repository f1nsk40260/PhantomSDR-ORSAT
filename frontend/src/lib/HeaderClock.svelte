<script>
  /**
   * HeaderClock.svelte — horloge numérique du header (desktop).
   *
   * Placée à gauche du bouton clignotant, en miroir du sélecteur de langue.
   * Bascule TU (UTC) / LOCAL ; le choix est retenu dans le navigateur.
   * Les libellés suivent la langue de l'interface via le store `lang` :
   * le composant est marqué data-no-i18n pour que la traduction automatique
   * ne touche ni aux chiffres ni à « UTC » ailleurs dans la page.
   */
  import { onMount, onDestroy } from "svelte";
  import { lang } from "./i18n.js";

  const KEY = "phantom.clockUtc";
  let utc = true; // les radioamateurs travaillent en UTC par défaut
  try {
    if (localStorage.getItem(KEY) === "0") utc = false;
  } catch (e) {}

  let now = new Date();
  let timer = null;
  let align = null;

  onMount(() => {
    now = new Date();
    // Caler les tops sur le changement de seconde, puis une fois par seconde.
    align = setTimeout(() => {
      now = new Date();
      timer = setInterval(() => (now = new Date()), 1000);
    }, 1000 - now.getMilliseconds());
  });
  onDestroy(() => {
    clearTimeout(align);
    clearInterval(timer);
  });

  function setMode(u) {
    utc = u;
    try {
      localStorage.setItem(KEY, u ? "1" : "0");
    } catch (e) {}
  }

  const p2 = (n) => String(n).padStart(2, "0");

  $: h = utc ? now.getUTCHours() : now.getHours();
  $: m = utc ? now.getUTCMinutes() : now.getMinutes();
  $: s = utc ? now.getUTCSeconds() : now.getSeconds();
  $: d = utc ? now.getUTCDate() : now.getDate();
  $: mo = (utc ? now.getUTCMonth() : now.getMonth()) + 1;
  $: y = utc ? now.getUTCFullYear() : now.getFullYear();
  $: dateTxt = $lang === "en" ? `${y}-${p2(mo)}-${p2(d)}` : `${p2(d)}/${p2(mo)}/${y}`;

  const L = {
    fr: { utc: "TU", loc: "LOCAL", tUtc: "Temps universel (UTC)", tLoc: "Heure locale de votre ordinateur", group: "Horloge" },
    en: { utc: "UTC", loc: "LOCAL", tUtc: "Coordinated Universal Time", tLoc: "Your computer's local time", group: "Clock" },
    es: { utc: "UTC", loc: "LOCAL", tUtc: "Tiempo universal coordinado", tLoc: "Hora local de su ordenador", group: "Reloj" },
  };
  $: t = L[$lang] || L.fr;
</script>

<div class="hclock" data-no-i18n role="group" aria-label={t.group}>
  <span class="hclock-face" title={utc ? t.tUtc : t.tLoc}>
    <span class="hclock-time">{p2(h)}:{p2(m)}<span class="hclock-sec">:{p2(s)}</span></span>
    <span class="hclock-date">{dateTxt}</span>
  </span>
  <button
    type="button"
    class="hclock-btn"
    class:active={utc}
    aria-pressed={utc}
    title={t.tUtc}
    on:click={() => setMode(true)}>{t.utc}</button
  ><button
    type="button"
    class="hclock-btn"
    class:active={!utc}
    aria-pressed={!utc}
    title={t.tLoc}
    on:click={() => setMode(false)}>{t.loc}</button
  >
</div>

<style>
  /* Même pastille que le sélecteur de langue : bord vieil or, fond sombre. */
  .hclock {
    display: inline-flex;
    align-items: stretch;
    flex-shrink: 0;
    border: 1px solid rgba(207, 181, 59, 0.6);
    border-radius: 999px;
    overflow: hidden;
    background: rgba(0, 0, 0, 0.3);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
  }
  /* Afficheur façon LED ambre, comme un transceiver. */
  .hclock-face {
    display: inline-flex;
    align-items: baseline;
    gap: 8px;
    padding: 3px 12px 3px 14px;
    background: rgba(0, 0, 0, 0.45);
    border-right: 1px solid rgba(207, 181, 59, 0.35);
    cursor: default;
  }
  .hclock-time {
    font-family: "Courier New", monospace;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    font-size: 1.05rem;
    letter-spacing: 0.06em;
    color: #ffd166;
    text-shadow:
      0 0 4px rgba(255, 190, 70, 0.55),
      0 0 10px rgba(255, 170, 40, 0.25);
  }
  .hclock-sec {
    opacity: 0.7;
    font-size: 0.85em;
  }
  .hclock-date {
    font-family: "Courier New", monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.72rem;
    color: rgba(207, 181, 59, 0.8);
  }
  .hclock-btn {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: rgba(207, 181, 59, 0.8);
    background: transparent;
    border: 0;
    border-radius: 0;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }
  .hclock-btn + .hclock-btn {
    border-left: 1px solid rgba(207, 181, 59, 0.25);
  }
  .hclock-btn:hover {
    background: rgba(207, 181, 59, 0.18);
    color: rgb(230, 205, 90);
  }
  .hclock-btn.active {
    background: rgb(207, 181, 59);
    color: #1a1405;
    cursor: default;
  }
  .hclock-btn:focus-visible {
    outline: 2px solid #fff8d6;
    outline-offset: -2px;
  }
</style>
