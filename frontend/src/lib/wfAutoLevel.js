// Waterfall auto brightness / contrast ("Auto Adj." switch).
//
// Pure, DOM-free so it can be tested offline on captured frames
// (~/sdr-shots/scripts/wf-autolevel-test.mjs).
//
// It never touches minWaterfall/maxWaterfall. Instead each frame is remapped
// in dB BEFORE transformValue(), so that after the user's own (frozen) linear
// [min, max] mapping every bin lands on the colormap index chosen here:
//
//   1. Noise floor is estimated ACROSS FREQUENCY (low percentile of small
//      blocks, eroded so a busy block borrows its quieter neighbour's floor,
//      then interpolated) and smoothed over time. A sloped spectrum (LF
//      noise, filter roll-off, a noisy 40 m next to a quiet 10 m on the full
//      span) therefore gets a flat, even background.
//   2. Noise spread (sigma) is measured from the lower half of the residuals,
//      which signals cannot reach, so a band full of carriers can't fake a
//      wide spread.
//   3. Brightness: the noise centre is pinned to a dark-but-visible index
//      picked from the colormap's own luminance curve, so it looks the same
//      on gqrx, turbo, PhantomSDR... Noise variance is COMPRESSED around that
//      point — never expanded, which is what made the old soft-knee
//      suppressor (and every min/max attempt) look noisier than "off".
//   4. Contrast: above a soft knee at ~2.5 sigma, signal rises linearly in dB
//      so the recent strongest signal reaches the top of the colormap, with
//      a minimum gain so weak signals still stand out next to a huge carrier
//      (the carrier simply clips to the top colour).

export default class WaterfallAutoLevel {
  constructor() {
    this.config = {
      // Positions/gains are fractions of the colormap's perceived length.
      backgroundPos: 0.008,     // where the noise centre sits (brightness)
      noiseGain: 0.006,         // per noise sigma — keeps a faint texture
      kneeSigma: 2.0,           // where noise ends and signal begins
      kneeWidthSigma: 2.0,      // soft transition width
      topPos: 0.92,             // where the recent strongest signal lands (contrast)
      minSignalGain: 0.02,      // per sigma above the knee, at least
      floorTimeConstant: 1.5,   // s
      levelTimeConstant: 3.0,   // s — sigma / ceiling glide
    }
    this.reset()
  }

  setConfig(cfg) {
    // Only take the keys this class knows; App.svelte still passes its old
    // preset objects, which carry unrelated fields.
    for (const k of Object.keys(this.config)) {
      if (cfg && Number.isFinite(cfg[k])) this.config[k] = cfg[k]
    }
  }

  reset() {
    this._key = null
    this._blockFloor = null
    this._sigma = null
    this._centre = null
    this._ceilZ = null
    this._lastTime = null
    this._floor = null
    this._resid = null
    this.stats = { floorDb: null, sigmaDb: null, ceilingDb: null, snrDb: null }
  }

  // Colormaps differ wildly at the dark end (turbo is pure black up to index
  // ~40, gqrx up to ~20, PhantomSDR is navy from 0), so every target below is
  // a position along the colormap's PERCEIVED length — cumulative colour
  // change from index 0 — not a raw index. 0 = first colour, 1 = last.
  // Call whenever the colormap changes.
  setColormap(colormapArray) {
    if (!colormapArray || colormapArray.length < 256) return
    const cum = new Float32Array(256)
    for (let i = 1; i < 256; i++) {
      const a = colormapArray[i - 1], b = colormapArray[i]
      const dr = b[0] - a[0], dg = b[1] - a[1], db = b[2] - a[2]
      // Weighted RGB distance (redmean-style weights, cheap and good enough).
      cum[i] = cum[i - 1] + Math.sqrt(2 * dr * dr + 4 * dg * dg + 3 * db * db)
    }
    const total = cum[255] || 1
    // pos (0..1, 1024 steps) → colormap index
    const lut = new Float32Array(1025)
    let idx = 0
    for (let k = 0; k <= 1024; k++) {
      const target = (k / 1024) * total
      while (idx < 255 && cum[idx + 1] <= target) idx++
      const span = idx < 255 ? cum[idx + 1] - cum[idx] : 1
      lut[k] = idx < 255 && span > 0 ? idx + (target - cum[idx]) / span : 255
    }
    this._lut = lut
  }

  _posToIndex(pos) {
    if (pos <= 0) return 0
    if (pos >= 1) return 255
    if (!this._lut) return pos * 255
    return this._lut[Math.round(pos * 1024)]
  }

  _alpha(dt, tau) {
    return 1 - Math.exp(-dt / tau)
  }

  _estimateBlockFloor(v, n) {
    const nb = Math.max(4, Math.min(48, Math.round(n / 24)))
    const bs = n / nb
    const raw = new Float32Array(nb)
    const tmp = []
    for (let b = 0; b < nb; b++) {
      const s = Math.floor(b * bs), e = Math.max(s + 1, Math.floor((b + 1) * bs))
      tmp.length = 0
      for (let i = s; i < e; i++) tmp.push(v[i])
      tmp.sort((a, c) => a - c)
      raw[b] = tmp[Math.floor(tmp.length * 0.2)]
    }
    // Erode: a block crowded with signal takes its quieter neighbour's floor.
    const out = new Float32Array(nb)
    for (let b = 0; b < nb; b++) {
      let m = raw[b]
      if (b > 0) m = Math.min(m, raw[b - 1])
      if (b < nb - 1) m = Math.min(m, raw[b + 1])
      out[b] = m
    }
    return out
  }

  // v: per-bin dB for one frame. key: anything that changes when the visible
  // window changes (zoom/pan) so the floor reseeds instead of smearing.
  // minDb/maxDb: the user's frozen colour range, used only to translate the
  // chosen colormap index back into the dB value transformValue() expects.
  // update=false (history redraw after zoom/pan/colormap change) maps with
  // the current levels without feeding old lines back into them.
  process(v, key, minDb, maxDb, now, update = true) {
    const n = v.length
    const c = this.config
    if (n < 8 || !(maxDb > minDb)) return v
    if (!update && this._sigma == null) return v

    const dt = this._lastTime == null ? 0.1 : Math.min(1, Math.max(0, (now - this._lastTime) / 1000))
    if (update) this._lastTime = now

    let blockFloor
    const sameWindow = this._key === key && this._blockFloor
    if (!update) {
      blockFloor = sameWindow ? this._blockFloor : this._estimateBlockFloor(v, n)
    } else {
      const bf = this._estimateBlockFloor(v, n)
      if (!sameWindow || this._blockFloor.length !== bf.length) {
        this._key = key
        this._blockFloor = bf
      } else {
        const a = this._alpha(dt, c.floorTimeConstant)
        for (let b = 0; b < bf.length; b++) this._blockFloor[b] += a * (bf[b] - this._blockFloor[b])
      }
      blockFloor = this._blockFloor
    }

    // Interpolate block floors back to bins.
    if (!this._floor || this._floor.length !== n) {
      this._floor = new Float32Array(n)
      this._resid = new Float32Array(n)
    }
    const nb = blockFloor.length, bs = n / nb
    for (let i = 0; i < n; i++) {
      const x = (i + 0.5) / bs - 0.5
      const b0 = Math.max(0, Math.min(nb - 1, Math.floor(x)))
      const b1 = Math.min(nb - 1, b0 + 1)
      const t = Math.max(0, Math.min(1, x - b0))
      this._floor[i] = blockFloor[b0] * (1 - t) + blockFloor[b1] * t
      this._resid[i] = v[i] - this._floor[i]
    }
    if (!update) return this._map(minDb, maxDb, n)

    // Noise statistics from the lower half of the residual distribution.
    const sorted = Float32Array.from(this._resid.subarray(0, n)).sort()
    const q = (p) => sorted[Math.min(n - 1, Math.floor(p * n))]
    const centre = q(0.4)
    const sigma = Math.max(0.75, (q(0.4) - q(0.1)) / 1.03)   // p40−p10 ≈ 1.03 σ for Gaussian-ish noise
    const la = this._alpha(dt, c.levelTimeConstant)
    this._centre = this._centre == null ? centre : this._centre + la * (centre - this._centre)
    this._sigma = this._sigma == null ? sigma : this._sigma + la * (sigma - this._sigma)

    const peakZ = (q(0.999) - this._centre) / this._sigma
    const minCeil = c.kneeSigma + c.kneeWidthSigma + 6
    const ceilZ = Math.max(minCeil, peakZ)
    // Fast to follow a new strong signal, slow to let go of it.
    const ca = ceilZ > (this._ceilZ ?? 0) ? Math.min(1, la * 3) : la * 0.5
    this._ceilZ = this._ceilZ == null ? ceilZ : this._ceilZ + ca * (ceilZ - this._ceilZ)

    let fsum = 0
    for (let i = 0; i < n; i++) fsum += this._floor[i]
    const meanFloor = fsum / n + this._centre
    this.stats = {
      floorDb: meanFloor,
      sigmaDb: this._sigma,
      ceilingDb: meanFloor + this._ceilZ * this._sigma,
      snrDb: this._ceilZ * this._sigma,
    }
    return this._map(minDb, maxDb, n)
  }

  _map(minDb, maxDb, n) {
    const c = this.config
    // Signal gain so _ceilZ reaches topPos, but never below minSignalGain.
    const B = c.backgroundPos
    const k = c.kneeSigma, w = c.kneeWidthSigma
    const noisePart = B + c.noiseGain * this._ceilZ     // noise-ramp contribution at the ceiling
    const ramp = this._ceilZ - k - w / 2
    const A = Math.max(c.minSignalGain, (c.topPos - noisePart) / Math.max(1, ramp))

    // A fresh buffer per call: the caller keeps the result only until it
    // has been colour-mapped, but redraw and live frames can interleave.
    const out = new Float32Array(n)
    const scale = (maxDb - minDb) / 255
    const invS = 1 / this._sigma
    for (let i = 0; i < n; i++) {
      const z = (this._resid[i] - this._centre) * invS
      const s = z - k
      let sig = 0
      if (s > 0) sig = s < w ? A * s * s / (2 * w) : A * (s - w / 2)
      // Noise below the centre fades toward black gently, never below 0.
      const idx = this._posToIndex(B + c.noiseGain * z + sig)
      out[i] = minDb + (idx + 0.5) * scale
    }
    return out
  }
}
