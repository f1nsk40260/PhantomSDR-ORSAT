<script>
  /**
   * Waterfall3D — spectre 3D (ORSAT, F1NSK) : les dernières traces du spectre
   * empilées en relief — fréquence en largeur, temps en profondeur, niveau en hauteur.
   *
   * Tout est calculé par la carte graphique (WebGL2) : l'historique des lignes
   * est une texture circulaire W×H mise à jour d'une seule ligne à chaque trame,
   * et le vertex shader y lit la hauteur de chaque point du maillage. Le
   * processeur ne fait que rééchantillonner la ligne reçue sur W points.
   *
   * Chaque trace garde sa propre plage de fréquences (indices FFT absolus) dans
   * une petite texture : le shader la replace exactement dans la fenêtre
   * affichée, donc zoom et glissement sont suivis sans approximation.
   *
   * Branchement : waterfall.view3d = { pushLine, setColormap, setView } —
   * waterfall.js appelle ces fonctions s'il trouve l'objet (voir drawSpectrogram,
   * setColormapArray et setWaterfallRange). Désactivée, la vue ne coûte rien.
   */
  import { onMount, onDestroy } from "svelte";

  export let waterfall;          // l'objet waterfall de backend.js
  export let onClose = () => {};

  const W = 1024;                // largeur de l'historique (points de fréquence)
  const H = 128;                 // profondeur de l'historique (traces)
  const GX = 1024, GY = 128;     // maillage affiché

  let canvas, gl, prog, vao, histTex, rangeTex, cmapTex, nIdx = 0;
  let viewL = 0, viewR = 1;      // fenêtre affichée (indices FFT)
  const hist = new Uint8Array(W * H);
  let head = 0;                  // ligne la plus récente
  let ro, raf = 0, failed = "";

  // Rendu : montée du passé et hauteur du relief (en unités écran, -1..1).
  const RISE = 1.5;    // remontée du sol, de l'avant au fond
  const AMP = 0.85;    // hauteur des crêtes (devant)
  const K = 0.16;      // perspective : au fond, les signaux se rapprochent du centre d'un facteur 1/(1+K)
  const FLOORV = "0.10";  // niveau attribué hors des traces (≈ bruit de fond), en littéral GLSL
  const HPOW = "0.55";    // courbe de hauteur (< 1 : relève le bruit, comprime les forts)

  const VS = `#version 300 es
  in vec2 aUV;
  uniform highp usampler2D uHist;
  uniform highp sampler2D uRange;   // par trace : plage [L, R] en indices FFT
  uniform int uHead;
  uniform vec2 uView;               // fenêtre affichée [L, R]
  uniform float uRise;              // montée totale du passé (unités écran)
  uniform float uAmp;               // hauteur du relief
  out float vVal;
  out float vAge;
  out float vRow;
  out float vLight;

  // Niveau (0-1) d'une trace à la position u de la fenêtre affichée.
  float sampleAt(float u, int age) {
    int row = (uHead - age + ${H}) % ${H};
    vec2 rr = texelFetch(uRange, ivec2(row, 0), 0).rg;
    float idx = uView.x + u * (uView.y - uView.x);
    float t = (idx - rr.x) / max(rr.y - rr.x, 1e-6);
    if (t < 0.0 || t >= 1.0) return ${FLOORV};   // hors de la trace : niveau du bruit
    int x = int(t * float(${W}));
    return float(texelFetch(uHist, ivec2(min(x, ${W - 1}), row), 0).r) / 255.0;
  }

  void main() {
    int age = int(aUV.y * float(${H - 1}) + 0.5);
    float d = aUV.y;                              // 0 = trace la plus récente (devant)
    // Perspective : chaque rangée couvre toute la largeur de l'écran ; plus
    // elle est loin, plus elle montre de fréquences (facteur 1/s) — seuls les
    // signaux convergent doucement vers le centre, la nappe garde ses bords droits.
    float s = 1.0 / (1.0 + ${K} * d);
    float sx = aUV.x * 2.0 - 1.0;
    float u = 0.5 + 0.5 * sx / s;
    float v = sampleAt(u, age);
    float du = 1.0 / float(${GX - 1}) / s;
    float vl = sampleAt(u - du, age);
    float vr = sampleAt(u + du, age);
    float vf = sampleAt(u, max(age - 1, 0));
    float vb = sampleAt(u, min(age + 1, ${H - 1}));

    // Perspective douce d'un plan vu de haut : au fond, largeur et hauteurs
    // sont réduites du facteur s (point de fuite au centre). Devant, s = 1 :
    // la trace la plus récente est exactement alignée sur le waterfall.
    float sBack = 1.0 / (1.0 + ${K});
    // Le bruit de fond (≈ FLOORV) est posé au ras du bord bas : pas de vide noir dessous.
    float ground = -1.0 - pow(${FLOORV}, ${HPOW}) * uAmp + uRise * (1.0 - s) / (1.0 - sBack);
    float amp = uAmp * s;
    // Courbe de hauteur : relève le moutonnement du bruit, comprime les signaux forts.
    float y = ground + pow(v, ${HPOW}) * amp;
    float x = sx;

    // Éclairage : normale estimée à partir des pentes voisines.
    vec3 n = normalize(vec3((pow(vl, ${HPOW}) - pow(vr, ${HPOW})) * amp * 45.0, 1.0, (pow(vf, ${HPOW}) - pow(vb, ${HPOW})) * amp * 25.0));
    vLight = 0.5 + 0.5 * max(dot(n, normalize(vec3(-0.35, 0.8, 0.5))), 0.0);

    vVal = v;
    vAge = d;
    vRow = aUV.y * float(${GY - 1});
    gl_Position = vec4(x, y, d * 0.98, 1.0);
  }`;

  const FS = `#version 300 es
  precision mediump float;
  in float vVal;
  in float vAge;
  in float vRow;
  in float vLight;
  uniform sampler2D uCmap;          // palette choisie pour le waterfall (256 couleurs)
  out vec4 frag;

  void main() {
    // Mêmes couleurs que le waterfall ; un léger plancher garde la nappe de
    // bruit lisible avec les palettes dont le bas est noir.
    vec3 pal = texture(uCmap, vec2(clamp(vVal, 0.0, 1.0) * (255.0 / 256.0) + 0.5 / 256.0, 0.5)).rgb;
    vec3 c = max(pal, vec3(0.035, 0.045, 0.09)) * vLight;
    // Une ligne discrète toutes les quatre traces : l'aspect « fil de fer ».
    float r = vRow * 0.25;
    float g = min(fract(r), 1.0 - fract(r));
    float line = 1.0 - smoothstep(0.0, fwidth(r) * 1.2, g);
    c += line * 0.10 * vec3(0.7, 0.85, 1.0);
    c *= 1.0 - 0.35 * vAge;                 // le passé s'estompe doucement
    frag = vec4(c, 1.0);
  }`;

  function sh(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }

  function initGL() {
    gl = canvas.getContext("webgl2", { antialias: true, alpha: false });
    if (!gl) throw new Error("WebGL2 indisponible");
    prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));

    // Maillage GX×GY (coordonnées u,v) + indices de triangles.
    const uv = new Float32Array(GX * GY * 2);
    for (let j = 0, k = 0; j < GY; j++)
      for (let i = 0; i < GX; i++) { uv[k++] = i / (GX - 1); uv[k++] = j / (GY - 1); }
    const idx = new Uint32Array((GX - 1) * (GY - 1) * 6);
    for (let j = 0, k = 0; j < GY - 1; j++)
      for (let i = 0; i < GX - 1; i++) {
        const a = j * GX + i, b = a + 1, c = a + GX, d = c + 1;
        idx[k++] = a; idx[k++] = c; idx[k++] = b;
        idx[k++] = b; idx[k++] = c; idx[k++] = d;
      }
    nIdx = idx.length;
    vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const vb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vb);
    gl.bufferData(gl.ARRAY_BUFFER, uv, gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "aUV");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const ib = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);

    // Historique : texture entière 8 bits (lecture exacte par texelFetch).
    histTex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, histTex);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, W, H, 0, gl.RED_INTEGER, gl.UNSIGNED_BYTE, hist);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);

    rangeTex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, rangeTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG32F, H, 1, 0, gl.RG, gl.FLOAT, new Float32Array(H * 2));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);

    cmapTex = gl.createTexture();
    setColormap(waterfall && waterfall.colormap);

    gl.enable(gl.DEPTH_TEST);
    gl.clearColor(0.01, 0.02, 0.07, 1);
  }

  /** Palette du waterfall : 256 couleurs RGBA. */
  function setColormap(cm) {
    if (!gl || !cm || !cm.length) return;
    const px = new Uint8Array(256 * 4);
    for (let i = 0; i < 256; i++) px.set(cm[Math.min(i, cm.length - 1)], i * 4);
    gl.bindTexture(gl.TEXTURE_2D, cmapTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 256, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, px);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    schedule();
  }

  /** Nouvelle trace : indices de palette 0-255 couvrant les indices FFT [l, r]. */
  const line = new Uint8Array(W);
  const hist256 = new Uint32Array(256);
  let floorE = -1, spanE = -1;
  const times = new Float64Array(H);   // instant d'arrivée de chaque trace
  let dbPerRaw = 0.55;                 // dB par pas de niveau (0-255), d'après min/max du waterfall
  // Graduations superposées à la vue (recalculées 4 fois par seconde).
  let dbMarks = [], timeMarks = [], lastMarks = 0;
  const norm = new Float32Array(W), prev = new Float32Array(W);
  let havePrev = false, prevL = 0, prevR = 0;
  const rng = new Float32Array(2);
  function pushLine(arr, l, r) {
    if (!gl || !arr || !arr.length || !(r > l)) return;
    if (l !== prevL || r !== prevR) { havePrev = false; prevL = l; prevR = r; }
    const n = arr.length;
    for (let x = 0; x < W; x++) {
      const i0 = Math.floor((x * n) / W);
      const i1 = Math.max(i0 + 1, Math.floor(((x + 1) * n) / W));
      let m = 0;
      for (let i = i0; i < i1 && i < n; i++) if (arr[i] > m) m = arr[i];   // max : garde les porteuses fines
      line[x] = m;
    }
    // Étalonnage sur le bruit de fond de la trace (lissé dans le temps) :
    // le bruit forme une nappe qui moutonne, les signaux s'en dressent.
    hist256.fill(0);
    for (let x = 0; x < W; x++) hist256[line[x]]++;
    let acc = 0, p20 = 0, p995 = 255;
    for (let i = 0; i < 256; i++) { acc += hist256[i]; if (acc >= W * 0.2) { p20 = i; break; } }
    acc = 0;
    for (let i = 255; i >= 0; i--) { acc += hist256[i]; if (acc >= W * 0.005) { p995 = i; break; } }
    floorE = floorE < 0 ? p20 : floorE * 0.9 + p20 * 0.1;
    spanE = spanE < 0 ? Math.max(40, p995 - p20) : spanE * 0.95 + Math.max(40, p995 - p20) * 0.05;
    const base = floorE - spanE * 0.10;
    for (let x = 0; x < W; x++) {
      const v = (line[x] - base) / (spanE * 1.15);
      norm[x] = v <= 0 ? 0 : v >= 1 ? 1 : v;
    }
    // Lissage léger : entre fréquences voisines (1-2-1) puis dans le temps,
    // pour des crêtes en « tubes » plutôt qu'en pics hérissés.
    for (let x = 0; x < W; x++) {
      const a = norm[x > 0 ? x - 1 : 0], b = norm[x], c = norm[x < W - 1 ? x + 1 : W - 1];
      let v = 0.25 * a + 0.5 * b + 0.25 * c;
      if (havePrev) v = 0.6 * v + 0.4 * prev[x];
      prev[x] = v;
      line[x] = Math.round(v * 255);
    }
    havePrev = true;
    head = (head + 1) % H;
    times[head] = performance.now();
    if (waterfall && Number.isFinite(waterfall.maxWaterfall) && Number.isFinite(waterfall.minWaterfall))
      dbPerRaw = (waterfall.maxWaterfall - waterfall.minWaterfall) / 255;
    gl.bindTexture(gl.TEXTURE_2D, histTex);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, head, W, 1, gl.RED_INTEGER, gl.UNSIGNED_BYTE, line);
    rng[0] = l; rng[1] = r;
    gl.bindTexture(gl.TEXTURE_2D, rangeTex);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, head, 0, 1, 1, gl.RG, gl.FLOAT, rng);
    schedule();
  }

  /** Zoom / glissement : nouvelle fenêtre affichée (indices FFT). */
  function setView(l, r) {
    if (!(r > l)) return;
    viewL = l; viewR = r;
    schedule();
  }

  function schedule() { if (!raf) raf = requestAnimationFrame(render); }

  // ── Graduations : mêmes formules que le vertex shader, côté JavaScript ──
  const fl = Math.pow(Number(FLOORV), Number(HPOW));
  const sOf = (d) => 1 / (1 + K * d);
  const sBack = 1 / (1 + K);
  const groundOf = (d) => -1 - fl * AMP + RISE * (1 - sOf(d)) / (1 - sBack);
  const pct = (y) => ((1 - y) / 2) * 100;          // y écran (-1..1) → % depuis le haut

  function updateMarks() {
    // Échelle en dB au-dessus du bruit, sur la trace la plus récente (devant, à droite).
    const db = [];
    if (spanE > 0 && dbPerRaw > 0) {
      const base = floorE - spanE * 0.10;
      for (let k = 10; k <= 80; k += 10) {
        const raw = floorE + k / dbPerRaw;
        const v = (raw - base) / (spanE * 1.15);
        if (v >= 1) break;
        const y = groundOf(0) + Math.pow(Math.max(v, 0), Number(HPOW)) * AMP;
        if (y > 0.92) break;
        db.push({ k, top: pct(y) });
      }
    }
    dbMarks = db;

    // Repères de temps en profondeur (−5 s, −10 s…), à gauche.
    const tm = [];
    const now = times[head];
    let oldest = 0;
    for (let a = H - 1; a > 0; a--) { const t = times[(head - a + H) % H]; if (t > 0) { oldest = a; break; } }
    if (now > 0 && oldest > 4) {
      const total = (now - times[(head - oldest + H) % H]) / 1000;
      const step = [1, 2, 5, 10, 15, 30, 60, 120].find((st) => total / st <= 5) || 300;
      let a = 1;
      for (let sec = step; sec < total; sec += step) {
        while (a < oldest && (now - times[(head - a + H) % H]) / 1000 < sec) a++;
        const d = a / (H - 1);
        const y = groundOf(d) + fl * AMP * sOf(d);
        tm.push({ sec, top: pct(y) });
      }
    }
    timeMarks = tm;
  }

  function render() {
    raf = 0;
    const tnow = performance.now();
    if (tnow - lastMarks > 250) { lastMarks = tnow; updateMarks(); }
    if (!gl) return;
    const w = canvas.width, h = canvas.height;
    gl.viewport(0, 0, w, h);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.useProgram(prog);
    gl.bindVertexArray(vao);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, histTex);
    gl.uniform1i(gl.getUniformLocation(prog, "uHist"), 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, cmapTex);
    gl.uniform1i(gl.getUniformLocation(prog, "uCmap"), 1);
    gl.activeTexture(gl.TEXTURE2);
    gl.bindTexture(gl.TEXTURE_2D, rangeTex);
    gl.uniform1i(gl.getUniformLocation(prog, "uRange"), 2);
    gl.uniform2f(gl.getUniformLocation(prog, "uView"), viewL, viewR);
    gl.uniform1i(gl.getUniformLocation(prog, "uHead"), head);
    gl.uniform1f(gl.getUniformLocation(prog, "uRise"), RISE);
    gl.uniform1f(gl.getUniformLocation(prog, "uAmp"), AMP);
    gl.drawElements(gl.TRIANGLES, nIdx, gl.UNSIGNED_INT, 0);
  }

  function resize() {
    if (!canvas) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const r = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.round(r.width * dpr));
    canvas.height = Math.max(1, Math.round(r.height * dpr));
    schedule();
  }

  onMount(() => {
    try {
      initGL();
    } catch (err) {
      failed = "La vue 3D nécessite WebGL2, indisponible dans ce navigateur.";
      console.warn("Waterfall3D:", err);
      return;
    }
    ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();
    if (waterfall) {
      viewL = waterfall.waterfallL; viewR = waterfall.waterfallR;
      waterfall.view3d = { pushLine, setColormap, setView };
    }
  });

  onDestroy(() => {
    if (waterfall && waterfall.view3d && waterfall.view3d.pushLine === pushLine) waterfall.view3d = null;
    if (ro) ro.disconnect();
    if (raf) cancelAnimationFrame(raf);
    const ext = gl && gl.getExtension("WEBGL_lose_context");
    if (ext) ext.loseContext();
    gl = null;
  });
</script>

<div class="w3d">
  <canvas bind:this={canvas} class="w3d-canvas"></canvas>
  {#if failed}<div class="w3d-msg">{failed}</div>{/if}
  <!-- Graduations : temps en profondeur (à gauche), dB au-dessus du bruit (à droite) -->
  {#each timeMarks as m (m.sec)}
    <div class="w3d-tline" style="top:{m.top}%"><span data-no-i18n>−{m.sec} s</span></div>
  {/each}
  {#each dbMarks as m (m.k)}
    <div class="w3d-db" style="top:{m.top}%"><span data-no-i18n>+{m.k} dB</span></div>
  {/each}
  <div class="w3d-tools">
    <button on:click={onClose} title="Revenir au spectre classique">✕ 2D</button>
  </div>
</div>

<style>
  .w3d { position: absolute; inset: 0; z-index: 20; background: #02040f; }
  .w3d-canvas { width: 100%; height: 100%; display: block; }
  .w3d-tools { position: absolute; top: 6px; right: 8px; display: flex; gap: 6px; }
  .w3d-tools button {
    padding: 2px 8px; border-radius: 5px; font-size: 11px; font-weight: 600;
    color: rgb(207, 181, 59); background: rgba(0, 0, 0, 0.55);
    border: 1px solid rgba(207, 181, 59, 0.55);
  }
  .w3d-tools button:hover { background: rgba(207, 181, 59, 0.18); }
  .w3d-tline {
    position: absolute; left: 0; right: 0; height: 0; pointer-events: none;
    border-top: 1px dashed rgba(207, 181, 59, 0.28);
  }
  .w3d-tline span {
    position: absolute; left: 6px; top: -8px; font-size: 10px; line-height: 1;
    color: rgba(243, 231, 166, 0.85); background: rgba(2, 4, 15, 0.6); padding: 1px 3px; border-radius: 3px;
  }
  .w3d-db {
    position: absolute; right: 0; width: 46px; height: 0; pointer-events: none;
    border-top: 1px solid rgba(207, 181, 59, 0.45);
  }
  .w3d-db span {
    position: absolute; right: 4px; top: -13px; font-size: 10px; line-height: 1;
    color: rgba(243, 231, 166, 0.9); text-shadow: 0 0 3px #000;
  }
  .w3d-msg {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    color: rgb(207, 181, 59); font-size: 13px;
  }
</style>
