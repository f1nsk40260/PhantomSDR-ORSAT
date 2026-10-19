<script>
  /**
   * SsbReport — « Bilan audio SSB » (ORSAT).
   *
   * Analyse la modulation de la station écoutée en USB / LSB, sur une fenêtre
   * glissante de 20 s, en ne retenant que les instants où elle parle :
   *   • équilibre tonal : graves 100–300 Hz et présence 1,5–2,7 kHz rapportés au
   *     médium 300–1500 Hz, comparés à une référence (SSB standard, DX, ESSB) ;
   *   • parasites statiques écartés (claquements brefs à spectre plat), rapports
 *     pris en médiane trame par trame ;
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
    std:  { name: "SSB standard", bass: -13, pres: -10, desc: "trafic courant, filtre 300–2700 Hz",
            tip: "Référence pour le trafic courant : voix équilibrée dans un filtre 300–2700 Hz" },
    dx:   { name: "DX / punch",   bass: -16, pres: -6, desc: "présence renforcée pour percer dans le bruit",
            tip: "Référence DX : peu de graves, présence renforcée pour être lisible dans le bruit" },
    essb: { name: "ESSB / hi-fi", bass: -3,  pres: -12, desc: "large bande, graves conservés",
            tip: "Référence ESSB : modulation large bande et hi-fi, graves conservés" },
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
  let impHold = 0, warm = 0;
  let timer = null, tick = 0, lastBase = null, lastMode = "";

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
    aud = []; rf = []; nb = { b: null, m: null, p: null }; rep = null; ltas = null; held = {}; impHold = 0; warm = 0;
  }

  const db = (p) => 10 * Math.log10(Math.max(p, 1e-20));
  const median = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[s.length >> 1]; };
  const pct = (a, q) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; };
  function track(prev, v) {             // plancher : descend vite, remonte lentement
    if (prev == null || v < prev) return v;
    return prev + Math.min(0.25, v - prev);           // ~2,5 dB/s
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
      // Pas encore de son (analyseur vide, −∞ dB) : on ignore la trame, sinon le
      // plancher de bruit tombe à −200 dB et tout passe ensuite pour de la voix.
      if (!(lm > -160)) { tick++; return; }
      // 2 s de mise en route : le plancher de bruit s'installe, l'analyseur se remplit.
      if (++warm < 20) { nb = { b: track(nb.b, lb), m: track(nb.m, lm), p: track(nb.p, lp) }; tick++; return; }
      nb = { b: track(nb.b, lb), m: track(nb.m, lm), p: track(nb.p, lp) };
      // Parasites statiques (claquements) : très brefs et à spectre plat.
      // Fenêtre de l'analyseur découpée en tranches de 128 échantillons (~ 11 ms) :
      // un claquement n'en occupe que quelques-unes, très au-dessus des autres,
      // alors qu'une attaque de voix en occupe beaucoup. La voix a aussi bien
      // moins d'énergie en présence qu'en médium ; un parasite presque autant.
      const nbk = t.length >> 7, br = new Float32Array(nbk);
      for (let k = 0; k < nbk; k++) { let e = 0; for (let i = k << 7; i < (k + 1) << 7; i++) e += t[i] * t[i]; br[k] = e / 128; }
      const sorted = Array.from(br).sort((x, y) => x - y);
      const bmed = Math.max(sorted[nbk >> 1], 1e-12), bmax = sorted[nbk - 1];
      const burst = db(bmax / bmed), nHigh = sorted.filter((v) => v > bmed * 10).length;
      const flat = lp - lm;
      // Les deux critères ensemble : bref ET plat. Une fin de phrase avant un
      // silence est brève aussi, mais garde le spectre penché de la voix.
      const hit = flat > -6 && (burst > 8 || nHigh <= 4 && burst > 6);
      if (hit) impHold = 4;                              // + traîne du lissage de l'analyseur
      const imp = impHold > 0; if (impHold > 0) impHold--;
      const speech = !imp && lm > nb.m + 9;
      // Puissances débarrassées du bruit de fond
      const clean = (p, n) => Math.max(0, p - Math.pow(10, n / 10));
      const fr = { sp: speech, imp: hit && lm > nb.m + 9, snr: lm - nb.m };
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
    // Rapports pris en médiane trame par trame : un parasite qui aurait échappé
    // au tri ne déplace plus le résultat.
    const rB = sp.filter((a) => a.m > 0 && a.b > 0).map((a) => db(a.b / a.m));
    const rP = sp.filter((a) => a.m > 0 && a.p > 0).map((a) => db(a.p / a.m));
    const nImp = aud.filter((a) => a.imp).length;
    out.impPct = sp.length + nImp ? Math.round((100 * nImp) / (sp.length + nImp)) : 0;
    const snr = median(sp.map((a) => a.snr));
    out.snr = snr;
    if (out.ready && M > 0) {
      const bass = lo <= 120 && rB.length >= 10 ? median(rB) : null;
      const pres = hi >= 2600 && rP.length >= 10 ? median(rP) : null;
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
  // ── Rapport complet avec un extrait sonore (fichier HTML autonome) ──
  function wavBlob(pcm, sr) {
    let pk = 0;
    for (let i = 0; i < pcm.length; i++) { const a = Math.abs(pcm[i]); if (a > pk) pk = a; }
    const g = pk > 1e-6 ? 0.89 / pk : 1;                 // normalisé à −1 dBFS pour l'écoute
    const n = pcm.length, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    str(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); str(8, "WAVE"); str(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, "data"); v.setUint32(40, n * 2, true);
    for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.max(-32768, Math.min(32767, Math.round(pcm[i] * g * 32767))), true);
    return new Blob([buf], { type: "audio/wav" });
  }
  const blobToDataUrl = (b) => new Promise((ok, ko) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = ko; r.readAsDataURL(b); });
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let building = false;
  async function fullReport() {
    if (!spectro || building) return;
    building = true;
    try {
      const au = typeof spectro.getRecentAudio === "function" ? spectro.getRecentAudio(20) : null;
      const img = typeof spectro.getSnapshot === "function" ? spectro.getSnapshot() : null;
      const now = new Date();
      const utc = now.toISOString().replace("T", " ").slice(0, 16) + " UTC";
      const stamp = now.toISOString().slice(0, 16).replace(/[-:]/g, "").replace("T", "-");
      const fk = fmtKhz(baseKhz);
      const dot = { ok: "#22c55e", warn: "#f59e0b", bad: "#ef4444", na: "#6b7280" };
      const rows = ROWS.map((row) => {
        const r = held[row.key];
        return `<tr><td><span class="d" style="background:${dot[r ? r.lvl : "na"]}"></span></td><td>${esc(row.label)}</td><td class="v">${esc(r && r.val ? r.val : "—")}</td><td>${esc(r ? r.txt : "non mesuré")}</td></tr>`;
      }).join("");
      let audioHtml = "<p class=\"n\">Pas d'extrait sonore : ouvrez l'analyseur audio quelques secondes avant de générer le rapport.</p>";
      let wavUrl = null;
      if (au && au.pcm.length > au.sr) {
        const wav = wavBlob(au.pcm, au.sr);
        wavUrl = await blobToDataUrl(wav);
        audioHtml = `<audio controls src="${wavUrl}"></audio>
<p class="n">${(au.pcm.length / au.sr).toFixed(0)} s d'audio brut du récepteur (avant tout traitement d'écoute), normalisé en niveau. <a download="ORSAT-${esc(fk.replace(/\s/g, ""))}kHz-${stamp}.wav" href="${wavUrl}">Télécharger le fichier WAV</a></p>`;
      }
      const ab = A && rep && rep.ready
        ? `<p>Comparaison avec la courbe A (${esc(A.when)}) : graves ${A.bass != null ? sgn(A.bass) + " dB" : "—"} → ${rep.bass != null ? sgn(rep.bass) + " dB" : "—"} ; présence ${A.pres != null ? sgn(A.pres) + " dB" : "—"} → ${rep.pres != null ? sgn(rep.pres) + " dB" : "—"}.</p>` : "";
      const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rapport d'écoute ORSAT — ${esc(fk)} kHz ${esc(m)}</title>
<style>body{background:#0b0f17;color:#e5e7eb;font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px}main{max-width:820px;margin:auto}
h1{color:#cfb53b;font-size:1.4rem;margin:0 0 .2rem}.sub{color:#9ca3af;margin:0 0 1.2rem}.f{font:700 1.6rem monospace;color:#f3e7a6}
.m{background:#cfb53b;color:#0b0f17;border-radius:4px;padding:0 6px;font-weight:700;margin-left:.4rem}
table{width:100%;border-collapse:collapse;margin:.8rem 0}td{padding:6px 8px;border-top:1px solid #1f2937}.v{font-family:monospace;color:#f3e7a6;white-space:nowrap}
.d{display:inline-block;width:10px;height:10px;border-radius:50%}img{width:100%;border:1px solid #cfb53b66;border-radius:6px}audio{width:100%;margin-top:.4rem}
.n{color:#9ca3af;font-size:.85rem}a{color:#cfb53b}h2{color:#cfb53b;font-size:1.05rem;margin:1.4rem 0 .3rem}</style></head><body><main>
<h1>Rapport d'écoute — station ORSAT</h1>
<p class="sub">${esc(utc)} · ${esc(location.host)} · référence tonale ${esc(REFS[refKey].name)}</p>
<p><span class="f">${esc(fk)} kHz</span><span class="m">${esc(m)}</span></p>
<h2>Extrait sonore</h2>${audioHtml}
<h2>Bilan de la modulation</h2><table>${rows}</table>${ab}
${img ? `<h2>Spectre audio au moment du rapport</h2><img alt="Spectre audio" src="${img}"><p class="n">Courbe bleue : forme moyenne de la voix ; pointillés blancs : courbe A mémorisée ; trait or : fréquence de base.</p>` : ""}
<p class="n">Mesure indicative sur 20 s glissantes, pendant la parole uniquement. Le fading, le filtre et l'AGC du récepteur influent.</p>
</main></body></html>`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([html], { type: "text/html" }));
      a.download = `Rapport-ORSAT-${fk.replace(/\s/g, "")}kHz-${m}-${stamp}.html`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } finally { building = false; }
  }

</script>

{#if active}
  <div class="sr">
    <div class="sr-head">
      <span class="sr-title">Bilan audio SSB</span>
      <span style="flex:1"></span>
      <button class="sr-btn" on:click={memorize} disabled={!rep || !ltas}
        title="Mémoriser la courbe actuelle (pointillés) pour la comparer après un réglage du correspondant">Mémoriser A</button>
      <button class="sr-btn" on:click={forgetA} disabled={!A} title="Effacer la courbe A">Effacer A</button>
      <button class="sr-btn" on:click={reset} title="Recommencer l'analyse (fenêtre de 20 s)">↺ Recommencer</button>
      <button class="sr-btn gold" on:click={fullReport} disabled={building || !Object.keys(held).length}
        title="Télécharger un rapport d'écoute complet (fichier HTML à envoyer au correspondant) : bilan, image du spectre et les 20 dernières secondes de son">{building ? "…" : "🎧 Générer un rapport d'écoute"}</button>
    </div>

    <div class="sr-refbar">
      <span class="sr-reflbl">Juger la voix par rapport à :</span>
      <div class="sr-seg" role="radiogroup" aria-label="Référence tonale">
        {#each Object.entries(REFS) as [k, r]}
          <button role="radio" aria-checked={refKey === k} class:on={refKey === k}
            on:click={() => { refKey = k; compute(); }} title={r.tip}>{r.name}</button>
        {/each}
      </div>
      <span class="sr-refdesc">{REFS[refKey].desc}</span>
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
      {#if rep && rep.impPct >= 10}<span class="imp">Parasites écartés :</span><span class="num" data-no-i18n>{rep.impPct} %</span>{/if}
      {#if rep && rep.snr != null && rep.snr < 15 && rep.ready}<span class="weak">Signal faible : fiabilité réduite.</span>{/if}
    </div>
  </div>
{/if}

<style>
  .sr { margin-top: 6px; padding: 6px 8px; border-radius: 5px; border: 1px solid rgba(207, 181, 59, 0.45); background: #111827; background-image: linear-gradient(rgba(207, 181, 59, 0.06), rgba(207, 181, 59, 0.06)); position: relative; z-index: 1; }
  .sr-head { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 4px; }
  .sr-title { font-size: 0.78rem; font-weight: 700; color: rgb(207, 181, 59); text-transform: uppercase; letter-spacing: 0.05em; }
  .sr-refbar { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin: 2px 0 6px; padding: 5px 8px;
    border-radius: 5px; background: rgba(207, 181, 59, 0.08); border: 1px solid rgba(207, 181, 59, 0.35); }
  .sr-reflbl { font-size: 0.74rem; font-weight: 700; color: rgb(207, 181, 59); }
  .sr-seg { display: inline-flex; border: 1px solid rgba(207, 181, 59, 0.6); border-radius: 0.4rem; overflow: hidden; }
  .sr-seg button { font-size: 0.74rem; font-weight: 700; padding: 0.2rem 0.75rem; color: #d1d5db; background: rgba(0, 0, 0, 0.3);
    border-right: 1px solid rgba(207, 181, 59, 0.4); cursor: pointer; }
  .sr-seg button:last-child { border-right: 0; }
  .sr-seg button:hover { background: rgba(207, 181, 59, 0.15); color: #f3e7a6; }
  .sr-seg button.on { color: #0b0f17; background: linear-gradient(180deg, rgb(226, 201, 90), rgb(176, 150, 40)); }
  .sr-refdesc { font-size: 0.7rem; color: #9ca3af; font-style: italic; }
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
  .sr-line .weak { color: #fcd34d; }
  .sr-line .imp { color: #fcd34d; margin-left: auto; }
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
