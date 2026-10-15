<script>
  // Liste des stations CW régulières (FAV22, F9TM…) avec leur planning en
  // heure de Paris, un indicateur « en cours / prochaine émission » et un
  // clic sur la fréquence pour y régler le récepteur.
  import { onMount, onDestroy } from "svelte";
  import { lang } from "./i18n.js";
  import { CW_STATIONS, CW_DEFAULT_DURATION_MIN } from "./cwStations.js";

  export let onTune = (khz) => {};

  const TZ = "Europe/Paris";

  const L = {
    fr: { title: "Stations CW", tz: "heure de Paris", live: "EN COURS", until: "jusqu'à", next: "Prochaine émission", in: "dans",
          from: "à partir de", tune: "Régler le récepteur sur", days: ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"],
          weekdays: "lun–ven", weekend: "sam–dim", none: "aucune émission prévue" },
    en: { title: "CW stations", tz: "Paris time", live: "ON AIR", until: "until", next: "Next transmission", in: "in",
          from: "from", tune: "Tune the receiver to", days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
          weekdays: "Mon–Fri", weekend: "Sat–Sun", none: "no transmission scheduled" },
    es: { title: "Estaciones CW", tz: "hora de París", live: "EN EMISIÓN", until: "hasta", next: "Próxima emisión", in: "en",
          from: "desde", tune: "Sintonizar el receptor en", days: ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"],
          weekdays: "lun–vie", weekend: "sáb–dom", none: "sin emisión prevista" },
  };
  $: t = L[$lang] || L.fr;

  // Jour (0-6) et minutes depuis minuit, en heure de Paris.
  function parisNow(date) {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: TZ, weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false,
    }).formatToParts(date);
    const get = (k) => parts.find((p) => p.type === k)?.value;
    const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(get("weekday"));
    return { day: wd, min: (Number(get("hour")) % 24) * 60 + Number(get("minute")) };
  }

  const toMin = (s) => { const [h, m] = s.split(":").map(Number); return h * 60 + m; };
  const fmtMin = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

  function slotRange(slot) {
    const start = toMin(slot[0]);
    const end = slot[1] ? toMin(slot[1]) : start + CW_DEFAULT_DURATION_MIN;
    return [start, end];
  }

  function status(station, now) {
    const { day, min } = parisNow(now);
    let best = null; // délai en minutes avant le prochain début
    for (const entry of station.schedule) {
      for (const slot of entry.slots) {
        const [start, end] = slotRange(slot);
        if (entry.days.includes(day) && min >= start && min < end) {
          return { live: true, end, openEnd: !slot[1] };
        }
        for (let d = 0; d <= 7; d++) {
          if (!entry.days.includes((day + d) % 7)) continue;
          const delta = d * 1440 + start - min;
          if (delta > 0 && (best === null || delta < best)) best = delta;
        }
      }
    }
    return { live: false, wait: best };
  }

  function fmtWait(m) {
    if (m < 60) return `${m} min`;
    if (m < 1440) return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
    const d = Math.floor(m / 1440);
    return `${d} j ${Math.floor((m % 1440) / 60)} h`;
  }

  function daysLabel(days, tt) {
    const k = [...days].sort().join(",");
    if (k === "1,2,3,4,5") return tt.weekdays;
    if (k === "0,6") return tt.weekend;
    return days.map((d) => tt.days[d]).join(", ");
  }

  function slotLabel(slot, tt) {
    return slot[1] ? `${slot[0]}–${slot[1]}` : `${tt.from} ${slot[0]}`;
  }

  let now = new Date();
  let timer;
  onMount(() => { timer = setInterval(() => (now = new Date()), 15000); });
  onDestroy(() => clearInterval(timer));
</script>

<div class="cw-sched" data-no-i18n>
  <div class="cw-sched-title">{t.title} <span class="cw-sched-tz">({t.tz})</span></div>
  {#each CW_STATIONS as st}
    {@const s = status(st, now)}
    <div class="cw-st" class:cw-st-live={s.live}>
      <div class="cw-st-head">
        <span class="cw-st-name" title={st.info}>{st.name}</span>
        {#each st.freqs as f}
          <button class="cw-freq" title="{t.tune} {f} kHz (CW)" on:click={() => onTune(f)}>{f} kHz</button>
        {/each}
        <span class="cw-st-status">
          {#if s.live}
            <span class="cw-live">● {t.live}</span>
            {#if !s.openEnd}<span class="cw-dim">{t.until} {fmtMin(s.end)}</span>{/if}
          {:else if s.wait !== null}
            <span class="cw-dim">{t.next} {t.in} {fmtWait(s.wait)}</span>
          {:else}
            <span class="cw-dim">{t.none}</span>
          {/if}
        </span>
      </div>
      <div class="cw-st-plan">
        {#each st.schedule as e}
          <span><b>{daysLabel(e.days, t)}</b> : {e.slots.map((sl) => slotLabel(sl, t)).join(" · ")}</span>
        {/each}
      </div>
    </div>
  {/each}
</div>

<style>
  .cw-sched { margin-bottom: 0.75rem; font-size: 0.75rem; }
  .cw-sched-title { color: rgb(207, 181, 59); font-weight: 600; margin-bottom: 0.35rem; }
  .cw-sched-tz { color: #9ca3af; font-weight: 400; }
  .cw-st { border: 1px solid rgba(207, 181, 59, 0.25); border-radius: 0.375rem; padding: 0.35rem 0.5rem; margin-bottom: 0.35rem; background: rgba(17, 24, 39, 0.5); }
  .cw-st-live { border-color: rgb(207, 181, 59); box-shadow: 0 0 6px rgba(207, 181, 59, 0.35); }
  .cw-st-head { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; }
  .cw-st-name { color: #fff; font-weight: 700; font-family: monospace; min-width: 3.5rem; }
  .cw-freq { font-family: monospace; color: rgb(207, 181, 59); border: 1px solid rgba(207, 181, 59, 0.6); border-radius: 0.25rem; padding: 0 0.4rem; background: rgba(207, 181, 59, 0.08); transition: background 0.15s; }
  .cw-freq:hover { background: rgba(207, 181, 59, 0.25); color: #fff; }
  .cw-st-status { margin-left: auto; display: flex; gap: 0.4rem; }
  .cw-live { color: rgb(207, 181, 59); font-weight: 700; animation: cwpulse 1.5s ease-in-out infinite; }
  .cw-dim { color: #9ca3af; }
  .cw-st-plan { display: flex; flex-wrap: wrap; gap: 0.2rem 0.9rem; color: #d1d5db; margin-top: 0.2rem; }
  .cw-st-plan b { color: #e5e7eb; font-weight: 600; }
  @keyframes cwpulse { 50% { opacity: 0.45; } }
</style>
