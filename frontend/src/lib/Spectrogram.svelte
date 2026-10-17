<script>
  /**
   * Spectrogram — spectre + spectrogramme défilant du signal audio démodulé.
   *
   * ORSAT : refonte pour la lisibilité.
   *   • canevas à la résolution réelle de l'écran (HiDPI), sans flou ;
   *   • chaque colonne de pixels prend le maximum des cases FFT qu'elle couvre
   *     (plus de trous ni d'aliasing), courbe pleine + ligne de crête ;
   *   • moitié haute : spectre instantané avec grille en dB ;
   *     moitié basse : spectrogramme défilant (historique temps-fréquence) ;
   *   • échelle linéaire (plage adaptée au mode) ou logarithmique ;
   *   • balises de largeur de bande préconisée selon le mode, et filtre actuel.
   *
   * API inchangée pour App.svelte : initialize(), feedPCMData(), start(), stop(),
   * setDisplayGain(), setFrequencyRange(), destroy().
   */
  import { onMount, onDestroy, createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher();

  export let minHz = 50;
  export let maxHzLimit = 10000;
  export let fftSize = 4096;
  export let displayGain = 1.0;
  export let colorScheme = "rainbow";
  export let showLabels = true;
  export let height = 300;
  export let enabled = true;
  export let frequencyCalibration = 1.0;
  /** ORSAT : mode de démodulation en cours (USB, LSB, CW, AM, FM…). */
  export let mode = "USB";
  /** ORSAT : filtre actuel en fréquences audio [bas, haut] (Hz), ou null. */
  export let passband = null;
  /** ORSAT : "lin" (plage selon le mode) ou "log". */
  export let scale = "lin";
  /** ORSAT : afficher les balises de largeur de bande. */
  export let showMarkers = true;
  /** ORSAT : mesure RF de la largeur occupée { status, text, alo, ahi, normHi }. */
  export let occupied = null;
  /** ORSAT : historique défilant sous le spectre (désactivé par défaut). */
  export let showHistory = false;
  /** ORSAT : fréquence de base du récepteur (kHz), affichée en clair. */
  export let baseKhz = null;
  /** ORSAT : spectre moyen de la voix { step, db[] } et courbe A mémorisée. */
  export let ltas = null;
  export let ltasRef = null;

  /** ORSAT : échantillon audio pour le bilan SSB (spectre + forme d'onde). */
  export function sampleAudio() {
    if (!analyser || !isRunning || !audioContext) return null;
    const f = new Float32Array(analyser.frequencyBinCount);
    analyser.getFloatFrequencyData(f);
    const t = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(t);
    return { f, t, binHz: (audioContext.sampleRate / analyser.fftSize) * frequencyCalibration, sr: audioContext.sampleRate };
  }

  // Fréquence de base et correspondance audio → RF.
  $: base = Number(baseKhz);
  $: hasBase = Number.isFinite(base) && base > 0;
  $: modeU = String(mode || "").toUpperCase();
  $: isCw = modeU.startsWith("CW");
  $: symmetric = ["AM", "QUAM", "FM", "WBFM", "SAM"].includes(modeU);
  /** Fréquence audio (Hz) de la fréquence de base : 0 Hz, ou la note CW. */
  $: baseAudio = isCw ? 750 : 0;
  export function fmtKhz(k) {
    const [i, d] = Number(k).toFixed(3).split(".");
    return i.replace(/\B(?=(\d{3})+(?!\d))/g, "\u202f") + "," + d;
  }
  function rfOf(a) {
    if (!hasBase) return null;
    if (symmetric) return null;
    const off = a - baseAudio;
    return base + (mirrored ? -off : off) / 1000;
  }

  // Lecture au survol de la souris.
  let geo = null, hoverX = null, hover = null;
  function onMove(e) {
    if (!geo) return;
    const r = canvas.getBoundingClientRect();
    const x = (e.clientX - r.left) * dpr;
    if (x < geo.left || x > geo.left + geo.pw) { onLeave(); return; }
    hoverX = x;
    const a = fOf(x, geo.lo, geo.hi, geo.left, geo.pw);
    const rf = rfOf(a);
    hover = {
      px: e.clientX - r.left,
      flip: e.clientX - r.left > r.width - 170,
      audio: Math.round(a) + " Hz audio",
      rf: rf != null ? fmtKhz(rf) + " kHz"
        : hasBase && symmetric ? `${fmtKhz(base)} ± ${(a / 1000).toFixed(3).replace(".", ",")} kHz` : "",
    };
  }
  function onLeave() { hoverX = null; hover = null; }

  let canvas, ctx, wrap;
  let audioContext, analyser, gainNode;
  let fdata = null;           // dB par case FFT
  let peak = null;            // ligne de crête par colonne
  let animationId, isRunning = false, playTime = 0;
  let dpr = 1, W = 0, H = 0;
  let wfImg = null;           // spectrogramme défilant (ImageData)
  let lut = null, lutScheme = "";

  const DB_MIN = -110, DB_MAX = -20;

  onMount(() => {
    ctx = canvas.getContext("2d", { alpha: false });
    resizeCanvas();
    const ro = new ResizeObserver(resizeCanvas);
    ro.observe(wrap);
    return () => ro.disconnect();
  });
  onDestroy(() => { stop(); destroy(); });

  $: if (canvas && height) resizeCanvas();

  function resizeCanvas() {
    if (!canvas || !wrap) return;
    dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(1, Math.round(wrap.clientWidth * dpr));
    const h = Math.max(1, Math.round(height * dpr));
    if (w !== canvas.width || h !== canvas.height) {
      canvas.width = w; canvas.height = h; W = w; H = h;
      canvas.style.height = height + "px";
      wfImg = null;
      peak = null;
    }
  }

  export async function initialize(sampleRate = 12000) {
    if (audioContext) return audioContext;
    audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate, latencyHint: "interactive" });
    if (audioContext.state === "suspended") await audioContext.resume();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = fftSize;
    analyser.minDecibels = -120;
    analyser.maxDecibels = 0;
    analyser.smoothingTimeConstant = 0.55;
    gainNode = audioContext.createGain();
    gainNode.gain.value = displayGain;
    gainNode.connect(analyser);
    fdata = new Float32Array(analyser.frequencyBinCount);
    playTime = audioContext.currentTime;
    dispatch("initialized");
    return audioContext;
  }

  export function feedPCMData(pcmArray) {
    if (!audioContext || !gainNode || !isRunning || !enabled) return;
    try {
      const buf = audioContext.createBuffer(1, pcmArray.length, audioContext.sampleRate);
      buf.copyToChannel(pcmArray, 0, 0);
      const src = audioContext.createBufferSource();
      src.buffer = buf;
      src.connect(gainNode);
      const now = audioContext.currentTime;
      if (playTime < now) playTime = now;
      src.start(playTime);
      playTime += buf.duration;
      src.onended = () => src.disconnect();
    } catch (e) {
      console.error("Error feeding PCM data:", e);
    }
  }

  export function start() {
    if (isRunning || !audioContext) return;
    isRunning = true;
    playTime = audioContext.currentTime;
    setTimeout(resizeCanvas, 10);
    draw();
  }

  export function stop() {
    isRunning = false;
    if (animationId) cancelAnimationFrame(animationId);
    animationId = null;
  }

  export function setDisplayGain(g) {
    displayGain = g;
    if (gainNode) gainNode.gain.value = g;
  }

  export function setFrequencyRange(min, max) {
    minHz = Math.max(min, 20);
    maxHzLimit = max;
  }

  // ── Palette (table de 256 couleurs, calculée une fois par schéma) ──
  function buildLut() {
    lut = new Uint8ClampedArray(256 * 3);
    for (let i = 0; i < 256; i++) {
      const v = i / 255;
      let r, g, b;
      if (colorScheme === "blue") { [r, g, b] = hsl(210, 1, 0.04 + v * 0.7); }
      else if (colorScheme === "green") { [r, g, b] = hsl(120, 1, 0.04 + v * 0.6); }
      else if (colorScheme === "white") { r = g = b = Math.round(v * 255); }
      else {
        const t = Math.pow(v, 0.8);
        const st = [[0, 0, 0, 0], [0.15, 0, 0, 90], [0.3, 0, 40, 255], [0.5, 0, 230, 255],
                    [0.68, 255, 255, 0], [0.84, 255, 120, 0], [1, 220, 0, 0]];
        for (let k = 0; k < st.length - 1; k++) {
          const [t0, r0, g0, b0] = st[k], [t1, r1, g1, b1] = st[k + 1];
          if (t <= t1) { const f = (t - t0) / (t1 - t0); r = r0 + f * (r1 - r0); g = g0 + f * (g1 - g0); b = b0 + f * (b1 - b0); break; }
        }
      }
      lut[i * 3] = r; lut[i * 3 + 1] = g; lut[i * 3 + 2] = b;
    }
    lutScheme = colorScheme;
  }
  function hsl(h, s, l) {
    const a = s * Math.min(l, 1 - l);
    const f = (n) => { const k = (n + h / 30) % 12; return 255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))); };
    return [f(0), f(8), f(4)];
  }

  // ── Échelle de fréquence ──
  function range() {
    const nyq = audioContext ? audioContext.sampleRate / 2 : 6000;
    if (scale === "log") return [Math.max(minHz, 40), Math.min(maxHzLimit, nyq)];
    const m = String(mode || "").toUpperCase();
    let top = m.startsWith("CW") ? 2000 : m === "AM" || m === "QUAM" || m === "FM" || m === "WBFM" ? 5500 : 4500;
    return [0, Math.min(top, nyq)];
  }
  // LSB : l'axe est inversé (aigus à gauche) pour suivre le sens du spectre RF.
  $: mirrored = ["LSB", "RADEL", "CW-L"].includes(String(mode || "").toUpperCase());
  function xOf(f, lo, hi, x0, w) {
    let a = scale === "log" ? Math.log(Math.max(f, lo) / lo) / Math.log(hi / lo) : (f - lo) / (hi - lo);
    if (mirrored) a = 1 - a;
    return x0 + a * w;
  }
  function fOf(x, lo, hi, x0, w) {
    let a = (x - x0) / w;
    if (mirrored) a = 1 - a;
    return scale === "log" ? lo * Math.pow(hi / lo, a) : lo + a * (hi - lo);
  }

  // ── Balises de largeur de bande préconisée selon le mode ──
  function markersFor(m) {
    m = String(m || "").toUpperCase();
    if (m === "USB" || m === "LSB" || m.startsWith("RADE")) return [
      { lo: 300, hi: 2700, label: "SSB standard 300–2700 Hz", color: "207,181,59" },
      { lo: 50, hi: 4000, label: "ESSB 50–4000 Hz", color: "56,189,248", dash: true },
    ];
    if (m.startsWith("CW")) return [
      { lo: 500, hi: 1000, label: "CW 500 Hz", color: "207,181,59" },
      { lo: 625, hi: 875, label: "CW 250 Hz", color: "56,189,248", dash: true },
    ];
    if (m === "AM" || m === "QUAM") return [
      { lo: 50, hi: 4500, label: "AM radiodiffusion ≤ 4,5 kHz", color: "207,181,59" },
      { lo: 100, hi: 3000, label: "AM radioamateur ≤ 3 kHz", color: "56,189,248", dash: true },
    ];
    if (m === "FM") return [{ lo: 300, hi: 3000, label: "FM voix 300–3000 Hz", color: "207,181,59" }];
    return [];
  }

  function draw() {
    if (!isRunning || !enabled) return;
    animationId = requestAnimationFrame(draw);
    if (!W || !H || !analyser) return;
    if (lutScheme !== colorScheme || !lut) buildLut();

    const s = dpr;
    const left = showLabels ? Math.round(38 * s) : Math.round(4 * s);
    const top = showLabels ? Math.round(18 * s) : Math.round(4 * s);
    const pw = W - left - Math.round(4 * s);
    const specH = showHistory ? Math.round((H - top) * 0.45) : H - top - Math.round(2 * s);
    const wfTop = top + specH + Math.round(2 * s);
    const wfH = H - wfTop;
    const [lo, hi] = range();
    geo = { left, pw, lo, hi };

    analyser.getFloatFrequencyData(fdata);
    const binHz = (audioContext.sampleRate / analyser.fftSize) * frequencyCalibration;

    // Valeur 0..1 par colonne (maximum des cases couvertes)
    const cols = new Float32Array(pw);
    for (let x = 0; x < pw; x++) {
      const fa = fOf(left + x, lo, hi, left, pw), fb = fOf(left + x + 1, lo, hi, left, pw);
      const f0 = Math.min(fa, fb), f1 = Math.max(fa, fb);
      let i0 = Math.floor(f0 / binHz), i1 = Math.max(i0, Math.floor(f1 / binHz));
      i0 = Math.max(0, i0); i1 = Math.min(fdata.length - 1, i1);
      let m = -Infinity;
      for (let i = i0; i <= i1; i++) if (fdata[i] > m) m = fdata[i];
      cols[x] = Math.max(0, Math.min(1, (m - DB_MIN) / (DB_MAX - DB_MIN)));
    }
    if (!peak || peak.length !== pw) peak = new Float32Array(pw);
    for (let x = 0; x < pw; x++) peak[x] = Math.max(cols[x], peak[x] - 0.004);

    // Fond
    ctx.fillStyle = "#0b0f17";
    ctx.fillRect(0, 0, W, H);

    // ── Spectre : grille dB ──
    ctx.font = `${Math.round(9.5 * s)}px monospace`;
    ctx.textBaseline = "middle";
    for (let db = -100; db <= -40; db += 20) {
      const y = top + specH - ((db - DB_MIN) / (DB_MAX - DB_MIN)) * specH;
      ctx.strokeStyle = "rgba(255,255,255,0.07)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + pw, y); ctx.stroke();
      if (showLabels && db > DB_MIN && db < DB_MAX) { ctx.fillStyle = "#8b93a3"; ctx.textAlign = "right"; ctx.fillText(db + "", left - 4 * s, y); }
    }

    // ── Spectre : courbe pleine colorée + crête ──
    for (let x = 0; x < pw; x++) {
      const v = cols[x];
      const h = v * specH;
      const k = Math.min(255, Math.round(v * 255)) * 3;
      ctx.fillStyle = `rgb(${lut[k]},${lut[k + 1]},${lut[k + 2]})`;
      ctx.fillRect(left + x, top + specH - h, 1, h);
    }
    ctx.strokeStyle = "rgba(243,231,166,0.85)";
    ctx.lineWidth = 1 * s;
    ctx.beginPath();
    for (let x = 0; x < pw; x++) {
      const y = top + specH - peak[x] * specH;
      x ? ctx.lineTo(left + x, y) : ctx.moveTo(left + x, y);
    }
    ctx.stroke();

    // ── Spectrogramme défilant (optionnel) ──
    if (!showHistory) { wfImg = null; }
    else {
    if (!wfImg || wfImg.width !== pw || wfImg.height !== wfH) {
      wfImg = ctx.createImageData(pw, Math.max(1, wfH));
      for (let i = 3; i < wfImg.data.length; i += 4) wfImg.data[i] = 255;
    }
    const d = wfImg.data, row = pw * 4;
    d.copyWithin(row, 0, d.length - row);           // tout descend d'une ligne
    for (let x = 0; x < pw; x++) {
      const k = Math.min(255, Math.round(cols[x] * 255)) * 3, o = x * 4;
      d[o] = lut[k]; d[o + 1] = lut[k + 1]; d[o + 2] = lut[k + 2]; d[o + 3] = 255;
    }
    ctx.putImageData(wfImg, left, wfTop);
    }

    // ── Balises de largeur de bande et filtre actuel ──
    const yTop = top, yBot = showHistory ? H : top + specH;
    if (showMarkers) {
      let ly = top + Math.round(3 * s);
      for (const mk of markersFor(mode)) {
        const xa = xOf(mk.lo, lo, hi, left, pw), xb = xOf(mk.hi, lo, hi, left, pw);
        const x0 = Math.min(xa, xb), x1 = Math.max(xa, xb);
        if (x1 < left || x0 > left + pw) continue;
        const a = Math.max(left, x0), b = Math.min(left + pw, x1);
        ctx.fillStyle = `rgba(${mk.color},0.07)`;
        ctx.fillRect(a, yTop, b - a, specH);
        ctx.strokeStyle = `rgba(${mk.color},0.9)`;
        ctx.lineWidth = 1.2 * s;
        ctx.setLineDash(mk.dash ? [5 * s, 4 * s] : []);
        for (const xx of [x0, x1]) {
          if (xx < left || xx > left + pw) continue;
          ctx.beginPath(); ctx.moveTo(xx, yTop); ctx.lineTo(xx, yBot); ctx.stroke();
        }
        ctx.setLineDash([]);
        ctx.font = `bold ${Math.round(9.5 * s)}px sans-serif`;
        ctx.textAlign = "left"; ctx.textBaseline = "top";
        const tw = ctx.measureText(mk.label).width + 6 * s;
        const tx = Math.min(Math.max(a + 3 * s, left), left + pw - tw);
        ctx.fillStyle = "rgba(11,15,23,0.8)";
        ctx.fillRect(tx - 2 * s, ly - 1 * s, tw, 13 * s);
        ctx.fillStyle = `rgb(${mk.color})`;
        ctx.fillText(mk.label, tx, ly);
        ly += Math.round(14 * s);
      }
    }
    if (passband && passband.length === 2 && passband[1] > passband[0]) {
      const xa = xOf(passband[0], lo, hi, left, pw), xb = xOf(passband[1], lo, hi, left, pw);
      const x0 = Math.min(xa, xb), x1 = Math.max(xa, xb);
      ctx.strokeStyle = "rgba(255,255,255,0.75)";
      ctx.lineWidth = 1 * s;
      ctx.setLineDash([2 * s, 3 * s]);
      ctx.strokeRect(Math.max(left, x0), top + 1, Math.min(left + pw, x1) - Math.max(left, x0), specH - 2);
      ctx.setLineDash([]);
      ctx.font = `${Math.round(9 * s)}px sans-serif`;
      ctx.textAlign = "right"; ctx.textBaseline = "bottom";
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.fillText(`Filtre actuel ${Math.round(passband[0])}–${Math.round(passband[1])} Hz`,
        Math.min(left + pw - 2 * s, Math.max(left + 140 * s, x1 - 2 * s)), top + specH - 2 * s);
    }

    // ── Largeur occupée mesurée : débordement en rouge (ou ambre si « large ») ──
    if (occupied && (occupied.status === "wide" || occupied.status === "splatter") && Number.isFinite(occupied.ahi)) {
      const col = occupied.status === "splatter" ? "255,60,60" : "245,158,11";
      const segs = [];
      if (occupied.normHi != null) segs.push([occupied.normHi, occupied.ahi]);
      else segs.push([occupied.alo, occupied.ahi]);
      for (const [f0, f1] of segs) {
        const xa = xOf(f0, lo, hi, left, pw), xb = xOf(f1, lo, hi, left, pw);
        const x0 = Math.max(left, Math.min(xa, xb)), x1 = Math.min(left + pw, Math.max(xa, xb));
        if (x1 <= x0) continue;
        ctx.fillStyle = `rgba(${col},0.18)`;
        ctx.fillRect(x0, top, x1 - x0, specH);
        ctx.fillStyle = `rgba(${col},0.95)`;
        ctx.fillRect(x0, top + specH - 3 * s, x1 - x0, 3 * s);
      }
    }

    // ── Spectre moyen de la voix (bilan SSB) et courbe A mémorisée ──
    const curve = (c, style, dash) => {
      if (!c || !c.db) return;
      ctx.strokeStyle = style; ctx.lineWidth = 1.6 * s; ctx.setLineDash(dash);
      ctx.beginPath();
      let on = false;
      for (let i = 0; i < c.db.length; i++) {
        const f = (i + 0.5) * c.step, v = c.db[i];
        if (f < lo || f > hi || !Number.isFinite(v)) { on = false; continue; }
        const x = xOf(f, lo, hi, left, pw);
        const y = top + specH - Math.max(0, Math.min(1, (v - DB_MIN) / (DB_MAX - DB_MIN))) * specH;
        on ? ctx.lineTo(x, y) : ctx.moveTo(x, y); on = true;
      }
      ctx.stroke(); ctx.setLineDash([]);
    };
    curve(ltasRef, "rgba(255,255,255,0.8)", [4 * s, 3 * s]);
    curve(ltas, "rgba(56,189,248,0.95)", []);
    if (ltas || ltasRef) {
      ctx.font = `bold ${Math.round(9 * s)}px sans-serif`;
      ctx.textAlign = "right"; ctx.textBaseline = "top";
      let ly = top + Math.round(3 * s);
      if (ltas) { ctx.fillStyle = "rgb(56,189,248)"; ctx.fillText("— voix moyenne", left + pw - 4 * s, ly); ly += 12 * s; }
      if (ltasRef) { ctx.fillStyle = "rgba(255,255,255,0.85)"; ctx.fillText("- - courbe A", left + pw - 4 * s, ly); }
    }

    // ── Fréquence de base : trait or à sa position audio ──
    if (hasBase && baseAudio >= lo && baseAudio <= hi) {
      const xb = Math.min(left + pw - s, Math.max(left + s, xOf(baseAudio, lo, hi, left, pw)));
      ctx.strokeStyle = "rgba(207,181,59,0.95)";
      ctx.lineWidth = 2 * s;
      ctx.beginPath(); ctx.moveTo(xb, top); ctx.lineTo(xb, yBot); ctx.stroke();
      const tag = (isCw ? "CW " : symmetric ? "Porteuse " : "Base ") + fmtKhz(base);
      ctx.font = `bold ${Math.round(10 * s)}px monospace`;
      ctx.textBaseline = "bottom";
      const tw = ctx.measureText(tag).width + 8 * s;
      const right = xb > left + pw / 2;
      const tx = right ? xb - tw - 2 * s : xb + 3 * s;
      const ty = top + Math.round(specH * 0.55);
      ctx.fillStyle = "rgba(11,15,23,0.85)";
      ctx.fillRect(tx, ty - 13 * s, tw, 13 * s);
      ctx.fillStyle = "rgb(243,231,166)";
      ctx.textAlign = "left";
      ctx.fillText(tag, tx + 4 * s, ty - 1 * s);
    }
    if (hoverX != null) {
      ctx.strokeStyle = "rgba(255,255,255,0.55)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(hoverX, top); ctx.lineTo(hoverX, yBot); ctx.stroke();
    }

    // ── Graduations de fréquence ──
    if (showLabels) {
      ctx.fillStyle = "#0b0f17";
      ctx.fillRect(0, 0, W, top);
      ctx.font = `${Math.round(10 * s)}px monospace`;
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      const ticks = [];
      if (scale === "log") {
        for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
          for (const m of [1, 2, 5]) { const f = m * 10 ** e; if (f >= lo && f <= hi) ticks.push(f); }
      } else {
        const step = hi - lo > 3000 ? 500 : 250;
        for (let f = Math.ceil(lo / step) * step; f <= hi; f += step) ticks.push(f);
      }
      for (const f of ticks) {
        const x = xOf(f, lo, hi, left, pw);
        ctx.strokeStyle = "rgba(255,255,255,0.10)";
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + specH); ctx.stroke();
        ctx.fillStyle = "#aab2c0";
        ctx.fillText(f >= 1000 ? +(f / 1000).toFixed(2) + "k" : f + "", x, 3 * s);
      }
      ctx.textAlign = "left";
      ctx.fillStyle = "#8b93a3";
      ctx.fillText("dB", 4 * s, 3 * s);
      if (mirrored) {
        ctx.font = `bold ${Math.round(9 * s)}px sans-serif`;
        ctx.textBaseline = "bottom";
        ctx.fillStyle = "rgb(207,181,59)";
        ctx.fillText("◂ LSB : axe inversé", left + 4 * s, top + specH - 2 * s);
      }
    }
  }

  export function destroy() {
    stop();
    try { gainNode && gainNode.disconnect(); } catch (e) {}
    try { analyser && analyser.disconnect(); } catch (e) {}
    gainNode = analyser = null;
    if (audioContext && audioContext.state !== "closed") audioContext.close();
    audioContext = null;
    fdata = null; peak = null; wfImg = null;
  }
</script>

<div class="spg" bind:this={wrap}>
  {#if hasBase}
    <div class="spg-base" title="Fréquence affichée par le récepteur ; le trait or la situe dans le spectre audio">
      <span class="lbl">Fréquence de base</span>
      <span class="val">{fmtKhz(base)} kHz</span>
      <span class="mode">{modeU}</span>
      <span class="hint">{isCw ? "note CW à 750 Hz audio" : symmetric ? "porteuse au centre, bandes latérales repliées" : mirrored ? "0 Hz audio = porteuse, fréquences RF décroissantes vers la droite" : "0 Hz audio = porteuse"}</span>
    </div>
  {/if}
  <div class="spg-cv">
    <canvas bind:this={canvas} on:mousemove={onMove} on:mouseleave={onLeave}></canvas>
    {#if hover}
      <div class="spg-tip" class:flip={hover.flip} style="left:{hover.px}px">{#if hover.rf}<b>{hover.rf}</b><br />{/if}{hover.audio}</div>
    {/if}
  </div>
  <div class="spg-obw {occupied && occupied.text ? occupied.status : 'empty'}">{occupied && occupied.text ? occupied.text : "\u00a0"}</div>
</div>

<style>
  .spg { width: 100%; }
  .spg-base {
    display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 4px;
    padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(207, 181, 59, 0.45); background: #111827; background-image: linear-gradient(rgba(207, 181, 59, 0.08), rgba(207, 181, 59, 0.08));
  }
  .spg-base .lbl { font-size: 0.72rem; color: rgb(207, 181, 59); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
  .spg-base .val { font-family: monospace; font-size: 1.05rem; font-weight: 700; color: #f3e7a6; }
  .spg-base .mode { font-size: 0.72rem; font-weight: 700; color: #0b0f17; background: rgb(207, 181, 59); border-radius: 3px; padding: 0 5px; }
  .spg-base .hint { font-size: 0.68rem; color: #9ca3af; font-style: italic; }
  .spg-cv { position: relative; }
  .spg-tip {
    position: absolute; top: 20px; transform: translateX(8px); pointer-events: none; white-space: nowrap;
    font: 11px/1.3 monospace; color: #e5e7eb; background: rgba(11, 15, 23, 0.92);
    border: 1px solid rgba(207, 181, 59, 0.6); border-radius: 4px; padding: 2px 6px; z-index: 2;
  }
  .spg-tip.flip { transform: translateX(calc(-100% - 8px)); }
  .spg-tip b { color: #f3e7a6; }
  .spg-obw { margin-top: 4px; font-size: 0.72rem; line-height: 1.1rem; height: calc(1.1rem + 6px); padding: 2px 8px; border-radius: 4px; border: 1px solid transparent; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .spg-obw.ok { color: #86efac; border-color: rgba(134, 239, 172, 0.35); background: rgba(22, 101, 52, 0.15); }
  .spg-obw.wide { color: #fcd34d; border-color: rgba(252, 211, 77, 0.4); background: rgba(146, 64, 14, 0.18); }
  .spg-obw.splatter { color: #fecaca; font-weight: 700; border-color: rgba(248, 113, 113, 0.6); background: rgba(153, 27, 27, 0.35); }
  .spg-obw.info { color: #9ca3af; font-style: italic; }
  canvas {
    width: 100%;
    display: block;
    background: #0b0f17;
    border-radius: 4px;
    border: 1px solid rgba(207, 181, 59, 0.35);
  }
</style>
