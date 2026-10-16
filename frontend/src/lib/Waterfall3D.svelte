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
   * Branchement : waterfall.view3d = { pushLine, setColormap, remap } —
   * waterfall.js appelle ces fonctions s'il trouve l'objet (voir drawSpectrogram,
   * setColormapArray et setWaterfallRange). Désactivée, la vue ne coûte rien.
   */
  import { onMount, onDestroy } from "svelte";

  export let waterfall;          // l'objet waterfall de backend.js
  export let onClose = () => {};

  const W = 1024;                // largeur de l'historique (points de fréquence)
  const H = 128;                 // profondeur de l'historique (traces)
  const GX = 1024, GY = 128;     // maillage affiché

  let canvas, gl, prog, vao, histTex, cmapTex, nIdx = 0;
  let hist = new Uint8Array(W * H);
  let head = 0;                  // ligne la plus récente
  let ro, raf = 0, failed = "";

  // Caméra fixe (pas de réglage d'inclinaison : vue de face, légèrement plongeante).
  const yaw = 0, pitch = 0.5, dist = 2.7;

  const VS = `#version 300 es
  in vec2 aUV;
  uniform highp usampler2D uHist;
  uniform int uHead;
  uniform mat4 uMVP;
  out float vVal;
  out float vAge;
  void main() {
    int x = int(aUV.x * float(${W - 1}) + 0.5);
    int age = int(aUV.y * float(${H - 1}) + 0.5);
    int row = (uHead - age + ${H}) % ${H};
    float val = float(texelFetch(uHist, ivec2(x, row), 0).r) / 255.0;
    vVal = val;
    vAge = aUV.y;
    float y = pow(val, 1.25) * 0.9;
    gl_Position = uMVP * vec4((aUV.x - 0.5) * 3.2, y, aUV.y * 2.4, 1.0);
  }`;

  const FS = `#version 300 es
  precision mediump float;
  in float vVal;
  in float vAge;
  uniform sampler2D uCmap;
  out vec4 frag;
  void main() {
    vec3 c = texture(uCmap, vec2(vVal, 0.5)).rgb;
    float fog = 1.0 - 0.7 * vAge;
    frag = vec4(c * fog, 1.0);
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

    cmapTex = gl.createTexture();
    setColormap(waterfall && waterfall.colormap);

    gl.enable(gl.DEPTH_TEST);
    gl.clearColor(0, 0, 0, 1);
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

  /** Nouvelle ligne (indices de palette 0-255), placée entre pxL et pxR sur un canevas de largeur cw. */
  const line = new Uint8Array(W);
  function pushLine(arr, pxL, pxR, cw) {
    if (!gl || !arr || !arr.length || !(cw > 0)) return;
    const span = pxR - pxL;
    for (let x = 0; x < W; x++) {
      const p0 = (x / W) * cw, p1 = ((x + 1) / W) * cw;
      if (p1 <= pxL || p0 >= pxR || span <= 0) { line[x] = 0; continue; }
      let i0 = Math.floor(((p0 - pxL) / span) * arr.length);
      let i1 = Math.ceil(((p1 - pxL) / span) * arr.length);
      i0 = Math.max(0, i0); i1 = Math.min(arr.length, Math.max(i1, i0 + 1));
      let m = 0;
      for (let i = i0; i < i1; i++) if (arr[i] > m) m = arr[i];   // max : garde les porteuses fines
      line[x] = m;
    }
    head = (head + 1) % H;
    hist.set(line, head * W);
    gl.bindTexture(gl.TEXTURE_2D, histTex);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, head, W, 1, gl.RED_INTEGER, gl.UNSIGNED_BYTE, line);
    schedule();
  }

  /** Zoom / défilement : l'ancienne fenêtre [x1, x1+w] (en px du canevas cw) est étirée sur la nouvelle, comme en 2D. */
  function remap(x1, w, cw) {
    if (!gl || !(w > 0) || !(cw > 0)) return;
    const out = new Uint8Array(W * H);
    for (let x = 0; x < W; x++) {
      const px = ((x + 0.5) / W) * cw;
      const src = Math.floor(((px - x1) / w) * W);
      if (src < 0 || src >= W) continue;
      for (let r = 0; r < H; r++) out[r * W + x] = hist[r * W + src];
    }
    hist = out;
    gl.bindTexture(gl.TEXTURE_2D, histTex);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, W, H, gl.RED_INTEGER, gl.UNSIGNED_BYTE, hist);
    schedule();
  }

  // ── Matrices 4×4 (colonnes) ──────────────────────────────────────────────
  function mul(a, b) {
    const o = new Float32Array(16);
    for (let c = 0; c < 4; c++)
      for (let r = 0; r < 4; r++) {
        let s = 0;
        for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
        o[c * 4 + r] = s;
      }
    return o;
  }
  function persp(fov, asp, n, f) {
    const t = 1 / Math.tan(fov / 2);
    return new Float32Array([t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, (2 * f * n) / (n - f), 0]);
  }
  const tr = (x, y, z) => new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]);
  const rx = (a) => { const c = Math.cos(a), s = Math.sin(a); return new Float32Array([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]); };
  const ry = (a) => { const c = Math.cos(a), s = Math.sin(a); return new Float32Array([c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]); };

  function schedule() { if (!raf) raf = requestAnimationFrame(render); }

  function render() {
    raf = 0;
    if (!gl) return;
    const w = canvas.width, h = canvas.height;
    gl.viewport(0, 0, w, h);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    // Le paysage va de z=0 (ligne la plus récente, devant) à z=2,4 (le passé).
    // On le recule et on le pivote autour de son centre.
    const model = tr(0, -0.15, -1.2);
    const view = mul(tr(0, 0, -dist), mul(rx(pitch), ry(yaw)));
    const flip = new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1]); // le passé s'éloigne
    const mvp = mul(persp(0.6, w / Math.max(1, h), 0.05, 50), mul(view, mul(flip, model)));
    gl.useProgram(prog);
    gl.bindVertexArray(vao);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, histTex);
    gl.uniform1i(gl.getUniformLocation(prog, "uHist"), 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, cmapTex);
    gl.uniform1i(gl.getUniformLocation(prog, "uCmap"), 1);
    gl.uniform1i(gl.getUniformLocation(prog, "uHead"), head);
    gl.uniformMatrix4fv(gl.getUniformLocation(prog, "uMVP"), false, mvp);
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
    if (waterfall) waterfall.view3d = { pushLine, setColormap, remap };
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
  <div class="w3d-tools">
    <button on:click={onClose} title="Revenir au spectre classique">✕ 2D</button>
  </div>
</div>

<style>
  .w3d { position: absolute; inset: 0; z-index: 20; background: #000; }
  .w3d-canvas { width: 100%; height: 100%; display: block; }
  .w3d-tools { position: absolute; top: 6px; right: 8px; display: flex; gap: 6px; }
  .w3d-tools button {
    padding: 2px 8px; border-radius: 5px; font-size: 11px; font-weight: 600;
    color: rgb(207, 181, 59); background: rgba(0, 0, 0, 0.55);
    border: 1px solid rgba(207, 181, 59, 0.55);
  }
  .w3d-tools button:hover { background: rgba(207, 181, 59, 0.18); }
  .w3d-msg {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    color: rgb(207, 181, 59); font-size: 13px;
  }
</style>
