<script>
  /**
   * SsbReport — « Bilan audio SSB » (ORSAT).
   *
   * Analyse la modulation de la station écoutée en USB / LSB, sur une fenêtre
   * glissante de 20 s, en ne retenant que les instants où elle parle :
   *   • équilibre tonal : graves 100–300 Hz et présence 1,5–2,7 kHz rapportés au
   *     médium 300–1500 Hz, comparés à une référence (SSB standard, DX, ESSB) ;
   *   • compression : facteur de crête de la forme d'onde sur ~ 340 ms ;
   *   • ronflette secteur : raies stables à 50/100/150 Hz (ou 60/120/180 Hz) ;
   *   • porteuse résiduelle et bande opposée : mesurées sur la cascade RF,
   *     car le filtre de réception les cache dans l'audio ;
   *   • largeur occupée : reprise de la mesure de splatter.
   * Courbe A mémorisable pour comparer avant / après un réglage, et rapport
   * d'écoute copiable en une ligne.
   */
  import { onDestroy } from "svelte";

  export let spectro = null;          // composant Spectrogram (sampleAudio)
  export let rfMeasure = null;        // (dialHz, mode) => mesure RF ou null
  export let mode = "USB";
  export let baseKhz = null;
  export let passband = null;         // filtre de réception en Hz audio
  export let occupied = null;         // largeur occupée (App._obwTick)
  export let enabled = true;
  /** Sorties pour le spectrogramme : spectre moyen de la voix et courbe A. */
  export let ltas = null;
  export let ltasRef = null;

  const WINDOW = 200;                 // 20 s à 10 mesures / s
  const STEP = 50, NB = 80;           // spectre moyen : 80 cases de 50 Hz
  const REFS = {
    std:  { name: "SSB standard", bass: -13, pres: -10 },
    dx:   { name: "DX / punch",   bass: -16, pres: -6 },
    essb: { name: "ESSB / hi-fi", bass: -3,  pres: -12 },
  };
  let refKey = "std";
  const ROWS = [
    { key: "bass", label: "Graves 100–300 Hz" },
    { key: "pres", label: "Présence 1,5–2,7 kHz" },
    { key: "comp", label: "Compression" },
    { key: "hum", label: "Ronflette secteur" },
    { key: "car", label: "Porteuse résiduelle" },
    { key: "opp", label: "Bande opposée" },
    { key: "obw", label: "Largeur occupée" },
  ];
  // Dernier verdict de chaque ligne, gardé tant qu'une nouvelle mesure ne le
  // remplace pas : le panneau garde sa taille et ne clignote pas.
  let held = {};

  $: m = String(mode || "").toUpperCase();
  $: active = enabled && (m === "USB" || m === "LSB");

  let aud = [], rf = [];
  let nb = { b: null, m: null, p: null };   // plancher de bruit audio par bande (dB)
  let rep = null, A = null;
  let timer = null, tick = 0, lastBase = null, lastMode = "";
  let copied = false;

  $: if (active && !timer) timer = setInterval(sample, 100);
  $: if (!active && timer) { clearInterval(timer); timer = null; reset(); }
  onDestroy(() => timer && clearInterval(timer));

  // Remise à zéro dès que l'on change de station ou de mode.
  $: {
    const b = Number(baseKhz);
    if (lastBase != null && Number.isFinite(b) && Math.abs(b - lastBase) > 0.05) reset();
    if (lastMode && m !== lastMode) reset();
    if (Number.isFinite(b)) lastBase = b;
    lastMode = m;
  }

  export function reset() {
    aud = []; rf = []; nb = { b: null, m: null, p: null }; rep = null; ltas = null; held = {};
  }

  const db = (p) => 10 * Math.log10(Math.max(p, 1e-20));
  const median = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[s.length >> 1]; };
  const pct = (a, q) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; };
  function track(prev, v) {             // plancher : descend vite, remonte lentement
    if (prev == null || v < prev) return v;
    return prev + Math.min(0.08, v - prev);
  }

  function bandPow(f, binHz, f0, f1) {
    let s = 0;
    const a = Math.max(1, Math.round(f0 / binHz)), b = Math.min(f.length - 1, Math.round(f1 / binHz));
    for (let i = a; i <= b; i++) s += Math.pow(10, f[i] / 10);
    return s;
  }
  function line(f, binHz, hz) {         // émergence d'une raie par rapport au voisinage
    const c = Math.round(hz / binHz), w = Math.max(1, Math.round(2 / binHz));
    let pk = -Infinity;
    for (let i = c - w; i <= c + w; i++) if (f[i] > pk) pk = f[i];
    const nbh = [];
    for (let d = Math.round(8 / binHz); d <= Math.round(25 / binHz); d++) { nbh.push(f[c - d], f[c + d]); }
    return pk - median(nbh.filter(Number.isFinite));
  }

  function sample() {
    if (!spectro || typeof spectro.sampleAudio !== "function") return;
    const s = spectro.sampleAudio();
    if (s) {
      const { f, t, binHz } = s;
      const pb = bandPow(f, binHz, 100, 300), pm = bandPow(f, binHz, 300, 1500), pp = bandPow(f, binHz, 1500, 2700);
      const lb = db(pb), lm = db(pm), lp = db(pp);
      nb = { b: track(nb.b, lb), m: track(nb.m, lm), p: track(nb.p, lp) };
      const speech = lm > nb.m + 9;
      // Puissances débarrassées du bruit de fond
      const clean = (p, n) => Math.max(0, p - Math.pow(10, n / 10));
      const fr = { sp: speech, snr: lm - nb.m };
      if (speech) {
        fr.b = clean(pb, nb.b); fr.m = clean(pm, nb.m); fr.p = clean(pp, nb.p);
        // Facteur de crête sur la fenêtre de l'analyseur (~ 340 ms : une syllabe ou deux)
        let pk = 0, e = 0;
        for (let i = 0; i < t.length; i++) { const v = t[i]; e += v * v; if (Math.abs(v) > pk) pk = Math.abs(v); }
        const rms = Math.sqrt(e / t.length);
        fr.crest = rms > 1e-5 ? 20 * Math.log10(pk / rms) : null;
        const L = new Float32Array(NB);
        for (let k = 0; k < NB; k++) L[k] = bandPow(f, binHz, k * STEP + 1, (k + 1) * STEP) / Math.max(1, Math.round(STEP / binHz));
        fr.L = L;
      }
      fr.h50 = [50, 100, 150].map((h) => line(f, binHz, h) > 8);
      fr.h60 = [60, 120, 180].map((h) => line(f, binHz, h) > 8);
      aud.push(fr); if (aud.length > WINDOW) aud.shift();
    }
    const dial = Number(baseKhz) * 1000;
    if (typeof rfMeasure === "function" && Number.isFinite(dial)) {
      const r = rfMeasure(dial, m);
      if (r) {
        if (r.ok) r.sp = r.want > r.noise + 8;
        rf.push(r); if (rf.length > WINDOW) rf.shift();
      }
    }
    if (++tick % 10 === 0) compute();
  }

  function verdictTone(d, kind) {
    if (d == null) return null;
    const a = Math.abs(d);
    const lvl = a <= 4 ? "ok" : a <= 8 ? "warn" : "bad";
    let txt;
    if (lvl === "ok") txt = "équilibré";
    else if (kind === "bass") txt = d > 0 ? (lvl === "bad" ? "beaucoup trop de basses" : "trop de basses") : "manque de graves (voix fine)";
    else txt = d > 0 ? (lvl === "bad" ? "beaucoup trop d'aigus (criard)" : "trop d'aigus") : "manque de présence (voix sourde)";
    return { lvl, txt };
  }
  const sgn = (v) => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(0);

  function compute() {
    const sp = aud.filter((a) => a.sp);
    const speechSec = sp.length / 10;
    const out = { speechSec, ready: speechSec >= 3, rows: [] };
    const ref = REFS[refKey];

    // ── Équilibre tonal ──
    const lo = passband ? passband[0] : 0, hi = passband ? passband[1] : 3000;
    let B = 0, M = 0, P = 0;
    for (const a of sp) { B += a.b; M += a.m; P += a.p; }
    const snr = median(sp.map((a) => a.snr));
    out.snr = snr;
    if (out.ready && M > 0) {
      const bass = lo <= 120 && B > 0 ? db(B / M) : null;
      const pres = hi >= 2600 && P > 0 ? db(P / M) : null;
      out.bass = bass; out.pres = pres;
      const vb = bass != null ? verdictTone(bass - ref.bass, "bass") : null;
      const vp = pres != null ? verdictTone(pres - ref.pres, "pres") : null;
      out.rows.push({ key: "bass", label: "Graves 100–300 Hz",
        val: bass != null ? `${sgn(bass)} dB (réf. ${sgn(ref.bass)})` : "",
        lvl: vb ? vb.lvl : "na", txt: vb ? vb.txt : `non mesurable : le filtre RX coupe sous ${Math.round(lo)} Hz` });
      out.rows.push({ key: "pres", label: "Présence 1,5–2,7 kHz",
        val: pres != null ? `${sgn(pres)} dB (réf. ${sgn(ref.pres)})` : "",
        lvl: vp ? vp.lvl : "na", txt: vp ? vp.txt : `non mesurable : le filtre RX coupe à ${Math.round(hi)} Hz` });
      // Spectre moyen de la voix, pour le spectrogramme
      const L = new Float64Array(NB);
      for (const a of sp) for (let k = 0; k < NB; k++) L[k] += a.L[k];
      ltas = { step: STEP, db: Array.from(L, (v) => (v > 0 ? db(v / sp.length) : NaN)), mid: db(M / sp.length) };
    }

    // ── Compression ──
    const cr = median(sp.map((a) => a.crest).filter((v) => v != null));
    if (out.ready && cr != null) {
      const lvl = cr > 15 ? "warn" : cr >= 10 ? "ok" : "bad";
      out.rows.push({ key: "comp", label: "Compression", val: `crête/moyenne ${cr.toFixed(1).replace(".", ",")} dB`, lvl,
        txt: lvl === "ok" ? "compression correcte" : lvl === "warn" ? "peu ou pas compressé" : "très compressé, écrêtage probable" });
    }

    // ── Ronflette secteur ──
    if (out.ready) {
      const frac = (key) => [0, 1, 2].map((i) => aud.filter((a) => a[key][i]).length / aud.length);
      const f50 = frac("h50"), f60 = frac("h60");
      const n50 = f50.filter((v) => v > 0.5).length, n60 = f60.filter((v) => v > 0.5).length;
      if (lo > 140) out.rows.push({ key: "hum", label: "Ronflette secteur", val: "", lvl: "na", txt: `non mesurable : le filtre RX coupe sous ${Math.round(lo)} Hz` });
      else {
        const hit = n50 >= 2 ? "50" : n60 >= 2 ? "60" : null;
        out.rows.push({ key: "hum", label: "Ronflette secteur", val: hit ? `raies à ${hit === "50" ? "50/100/150" : "60/120/180"} Hz` : "", lvl: hit ? "bad" : "ok",
          txt: hit ? "ronflette détectée (masse, alimentation)" : "pas de ronflette" });
      }
    }

    // ── Mesures RF : porteuse et bande opposée ──
    const okRf = rf.filter((r) => r.ok);
    const rsp = okRf.filter((r) => r.sp), ridle = okRf.filter((r) => !r.sp);
    if (rf.length >= 20 && okRf.length < rf.length / 2) {
      const why = rf.filter((r) => !r.ok).some((r) => r.reason === "zoom") ? "zoomez sur la station dans la cascade" : "pas de données de la cascade";
      out.rows.push({ key: "car", label: "Porteuse résiduelle", val: "", lvl: "na", txt: why });
      out.rows.push({ key: "opp", label: "Bande opposée", val: "", lvl: "na", txt: why });
    } else if (rsp.length >= 15) {
      const pk = pct(rsp.map((r) => r.wantPk), 0.9);
      const noise = median(rsp.map((r) => r.noise));
      const cars = rsp.map((r) => r.car).filter((v) => v != null);
      if (cars.length < rsp.length / 2) out.rows.push({ key: "car", label: "Porteuse résiduelle", val: "", lvl: "na", txt: "zoomez davantage (≤ 60 Hz par point)" });
      else {
        const car = median(cars);
        const visible = car > noise + 4;
        const sup = pk - (visible ? car : noise);
        const lvl = !visible ? (sup >= 40 ? "ok" : "na") : sup >= 40 ? "ok" : sup >= 30 ? "warn" : "bad";
        out.rows.push({ key: "car", label: "Porteuse résiduelle", val: visible ? `−${sup.toFixed(0)} dB` : `< −${sup.toFixed(0)} dB`, lvl,
          txt: !visible ? (lvl === "ok" ? "invisible, bien supprimée" : "invisible, signal trop faible pour conclure") : lvl === "ok" ? "bien supprimée" : lvl === "warn" ? "porteuse visible" : "porteuse mal supprimée" });
      }
      const wantM = db(rsp.reduce((s, r) => s + Math.pow(10, r.want / 10), 0) / rsp.length);
      const oppM = db(rsp.reduce((s, r) => s + Math.pow(10, r.opp / 10), 0) / rsp.length);
      const oppIdle = ridle.length >= 10 ? db(ridle.reduce((s, r) => s + Math.pow(10, r.opp / 10), 0) / ridle.length) : null;
      if (oppIdle != null && oppIdle > noise + 6 && Math.abs(oppM - oppIdle) < 3)
        out.rows.push({ key: "opp", label: "Bande opposée", val: "", lvl: "na", txt: "occupée par une autre station (QRM), mesure impossible" });
      else {
        const vis = oppM > noise + 3;
        const rej = wantM - (vis ? oppM : noise);
        const lvl = !vis ? (rej >= 40 ? "ok" : "na") : rej >= 40 ? "ok" : rej >= 30 ? "warn" : "bad";
        out.rows.push({ key: "opp", label: "Bande opposée", val: vis ? `−${rej.toFixed(0)} dB` : `< −${rej.toFixed(0)} dB`, lvl,
          txt: !vis ? (lvl === "ok" ? "bien rejetée" : "sous le bruit, signal trop faible pour conclure") : lvl === "ok" ? "bien rejetée" : lvl === "warn" ? "bande opposée visible" : "bande opposée mal rejetée" });
      }
    }

    // ── Largeur occupée (mesure du splatter) ──
    if (occupied && occupied.status && occupied.status !== "info" && occupied.text) {
      const w = (occupied.text.match(/([\d,]+) kHz/) || [])[1] || "";
      out.rows.push({ key: "obw", label: "Largeur occupée", val: w ? `${w} kHz` : "",
        lvl: occupied.status === "ok" ? "ok" : occupied.status === "wide" ? "warn" : "bad",
        txt: occupied.status === "ok" ? "conforme" : occupied.status === "wide" ? "un peu large" : "splatter" });
    }
    rep = out;
    const h = { ...held };
    for (const r of out.rows) h[r.key] = r;
    held = h;
  }

  function memorize() {
    if (!rep || !ltas) return;
    A = { ltas, bass: rep.bass, pres: rep.pres, when: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) };
  }
  function forgetA() { A = null; }
  // Courbe A recalée sur le niveau du médium actuel (le fading change le niveau, pas la forme).
  $: ltasRef = A && A.ltas ? (ltas ? { step: STEP, db: A.ltas.db.map((v) => v + (ltas.mid - A.ltas.mid)) } : A.ltas) : null;

  function fmtKhz(k) {
    const [i, d] = Number(k).toFixed(3).split(".");
    return i.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + "," + d;
  }
  async function copy() {
    if (!rep) return;
    const parts = [`${fmtKhz(baseKhz)} kHz ${m}`];
    if (rep.ready) parts.push(`réf. ${REFS[refKey].name}`);
    for (const row of ROWS) { const r = held[row.key]; if (r && r.lvl !== "na") parts.push(`${r.label} : ${r.txt}${r.val ? " (" + r.val + ")" : ""}`); }
    const txt = "Bilan audio ORSAT — " + parts.join(" · ");
    try { await navigator.clipboard.writeText(txt); }
    catch (e) { const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
    copied = true; setTimeout(() => (copied = false), 1800);
  }
</script>

{#if active}
  <div class="sr">
    <div class="sr-head">
      <span class="sr-title">Bilan audio SSB</span>
      <label class="sr-ref" title="Courbe tonale de référence : une émission DX renforce la présence, l'ESSB garde des graves">
        <span>Référence</span>
        <select bind:value={refKey} on:change={compute}>
          {#each Object.entries(REFS) as [k, r]}<option value={k}>{r.name}</option>{/each}
        </select>
      </label>
      <span style="flex:1"></span>
      <button class="sr-btn" on:click={memorize} disabled={!rep || !ltas}
        title="Mémoriser la courbe actuelle (pointillés) pour la comparer après un réglage du correspondant">Mémoriser A</button>
      <button class="sr-btn" on:click={forgetA} disabled={!A} title="Effacer la courbe A">Effacer A</button>
      <button class="sr-btn" on:click={reset} title="Recommencer l'analyse (fenêtre de 20 s)">↺ Recommencer</button>
      <button class="sr-btn gold copy" on:click={copy} disabled={!Object.keys(held).length}
        title="Copier le bilan en une ligne, à envoyer au correspondant">{copied ? "✓ Copié" : "📋 Copier le rapport"}</button>
    </div>

    <table class="sr-tab">
      <colgroup><col style="width:18px" /><col style="width:11.5rem" /><col style="width:12rem" /><col /></colgroup>
      {#each ROWS as row (row.key)}
        {@const r = held[row.key]}
        <tr class={r ? r.lvl : "wait"}>
          <td class="dot"><span></span></td>
          <td class="lbl">{row.label}</td>
          <td class="val" data-no-i18n>{r && r.val ? r.val : "—"}</td>
          <td class="txt">{r ? r.txt : "en attente"}</td>
        </tr>
      {/each}
    </table>
    <div class="sr-line" title="Mesure indicative sur 20 s glissantes, pendant la parole uniquement. Le fading, le filtre et l'AGC du récepteur influent : préférez l'AGC lente.">
      {#if !rep || !rep.ready}
        <span>En attente de modulation…</span>
        <span class="num" data-no-i18n>{rep ? rep.speechSec.toFixed(1).replace(".", ",") : "0,0"} s / 3 s</span>
        <span>de voix analysées</span>
      {:else if A}
        <span>Courbe A</span><span class="num" data-no-i18n>({A.when})</span>
        <span>graves</span><span class="num" data-no-i18n>{A.bass != null ? sgn(A.bass) + " dB" : "—"} → {rep.bass != null ? sgn(rep.bass) + " dB" : "—"}</span>
        <span>présence</span><span class="num" data-no-i18n>{A.pres != null ? sgn(A.pres) + " dB" : "—"} → {rep.pres != null ? sgn(rep.pres) + " dB" : "—"}</span>
      {:else}
        <span>Mesure indicative sur 20 s glissantes, pendant la parole uniquement. Le fading, le filtre et l'AGC du récepteur influent : préférez l'AGC lente.</span>
      {/if}
      {#if rep && rep.snr != null && rep.snr < 15 && rep.ready}<span class="weak">Signal faible : fiabilité réduite.</span>{/if}
    </div>
  </div>
{/if}

<style>
  .sr { margin-top: 6px; padding: 6px 8px; border-radius: 5px; border: 1px solid rgba(207, 181, 59, 0.45); background: #111827; background-image: linear-gradient(rgba(207, 181, 59, 0.06), rgba(207, 181, 59, 0.06)); position: relative; z-index: 1; }
  .sr-head { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 4px; }
  .sr-title { font-size: 0.78rem; font-weight: 700; color: rgb(207, 181, 59); text-transform: uppercase; letter-spacing: 0.05em; }
  .sr-ref { display: flex; align-items: center; gap: 0.3rem; font-size: 0.7rem; color: #9ca3af; }
  .sr-ref select { font-size: 0.7rem; padding: 0 0.3rem; background: #111827; color: #f3e7a6; border: 1px solid rgba(207, 181, 59, 0.5); border-radius: 3px; }
  .sr-btn {
    font-size: 0.68rem; padding: 0.1rem 0.5rem; border-radius: 0.3rem; font-weight: 600; white-space: nowrap;
    color: #d1d5db; border: 1px solid #ffffff40; background: rgba(0, 0, 0, 0.25);
  }
  .sr-btn.gold { color: rgb(207, 181, 59); border-color: rgba(207, 181, 59, 0.55); }
  .sr-btn:hover:not(:disabled) { background: rgba(207, 181, 59, 0.18); color: #f3e7a6; }
  .sr-btn:disabled { opacity: 0.4; cursor: default; }
  .sr-line {
    font-size: 0.66rem; color: #9ca3af; font-style: italic; display: flex; gap: 0.35rem; align-items: center;
    height: 1.4rem; margin-top: 3px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
  }
  .sr-line .weak { color: #fcd34d; margin-left: auto; }
  .sr-btn.copy { min-width: 9.5rem; }
  .num { font-family: monospace; font-style: normal; color: #d1d5db; }
  .sr-tab { width: 100%; border-collapse: collapse; font-size: 0.74rem; table-layout: fixed; }
  .sr-tab td { padding: 2px 6px; height: 1.35rem; border-top: 1px solid rgba(255, 255, 255, 0.06); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sr-tab .wait .txt, .sr-tab .wait .val { color: #4b5563; font-style: italic; }
  .sr-tab .dot { width: 14px; }
  .sr-tab .dot span { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #6b7280; }
  .sr-tab .ok .dot span { background: #22c55e; box-shadow: 0 0 5px #22c55e; }
  .sr-tab .warn .dot span { background: #f59e0b; box-shadow: 0 0 5px #f59e0b; }
  .sr-tab .bad .dot span { background: #ef4444; box-shadow: 0 0 5px #ef4444; }
  .sr-tab .lbl { color: #d1d5db; white-space: nowrap; }
  .sr-tab .val { font-family: monospace; color: #f3e7a6; white-space: nowrap; }
  .sr-tab .txt { color: #e5e7eb; }
  .sr-tab .ok .txt { color: #86efac; }
  .sr-tab .warn .txt { color: #fcd34d; }
  .sr-tab .bad .txt { color: #fca5a5; font-weight: 600; }
  .sr-tab .na .txt { color: #9ca3af; font-style: italic; }
</style>
