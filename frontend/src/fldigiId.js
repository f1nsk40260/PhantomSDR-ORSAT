/**
 * fldigiId.js — reconnaissance des modes fldigi pour le Decoder ID.
 * (version française, F1NSK)
 *
 * modeId.js mesure des caractéristiques globales (largeur, rapidité, écart)
 * qui suffisent pour le RTTY ou le PSK31, mais pas pour les modes MFSK de
 * fldigi : Olivia passait pour du FAX, DominoEX et THOR pour de l'Olivia, et
 * MT63, THROB ou Hellschreiber n'étaient pas dans la table.
 *
 * Ici chaque mode est une HYPOTHÈSE de géométrie (nombre de tons, écart,
 * rapidité) que l'on vérifie sur les symboles eux-mêmes :
 *
 *   1. on cale une grille de tons sur le spectre du signal ;
 *   2. on découpe l'audio en symboles de la bonne durée, à la meilleure phase ;
 *   3. pureté = part de l'énergie du symbole portée par son ton le plus fort.
 *      Bonne géométrie : chaque symbole tient dans un ton (pureté proche de 1).
 *      Mauvaise rapidité : le symbole chevauche deux tons ; mauvais écart :
 *      l'énergie tombe entre les points de la grille.
 *
 * Puis des signatures propres à chaque famille :
 *   • IFK (DominoEX, THOR) : le ton change à chaque symbole, d'au moins deux
 *     positions — jamais de répétition, jamais de pas d'un seul ton ;
 *   • Olivia : symboles mis en forme (creux d'amplitude à chaque frontière),
 *     là où le MFSK16/32/64 garde une enveloppe constante ;
 *   • MT63 : 64 porteuses à la fois, bande pleine et plate à chaque instant ;
 *   • THROB : 9 tons lents, une ou deux tonalités à la fois ;
 *   • Hellschreiber : un ton haché au rythme des colonnes (17,5 par seconde).
 *
 * Ce qu'on ne peut pas trancher sans décoder est dit : DominoEX et THOR ont la
 * même géométrie (THOR = DominoEX + FEC), on propose donc les deux.
 */

import { transformFlat } from './lib/fftRadix2.js';

// ── Hypothèses ───────────────────────────────────────────────────────────────
// variant / modemMode : ceux du panneau fldigi (fsk.js, FLDIGI_MODEMS) ;
// Olivia passe par sa propre liste (OLIVIA_MODE_OPTIONS, clé « 8/250 »).
function ifk(key, label, sr, symlen, ds) {
  const baud = sr / symlen;
  return { fam: 'ifk', modemMode: key, label, baud, spacing: baud * ds, n: 18 };
}
const HYP = [
  // Olivia : écart = rapidité = largeur / nombre de tons.
  { fam: 'olivia', variant: 'olivia', oliviaMode: '8/250', label: 'Olivia 8/250', baud: 31.25, spacing: 31.25, n: 8 },
  { fam: 'olivia', variant: 'olivia', oliviaMode: '16/500', label: 'Olivia 16/500', baud: 31.25, spacing: 31.25, n: 16 },
  { fam: 'olivia', variant: 'olivia', oliviaMode: '32/1000', label: 'Olivia 32/1000', baud: 31.25, spacing: 31.25, n: 32 },
  { fam: 'olivia', variant: 'olivia', oliviaMode: '16/1000', label: 'Olivia 16/1000', baud: 62.5, spacing: 62.5, n: 16 },
  // MFSK : 16 tons, écart = rapidité.
  { fam: 'mfsk', variant: 'mfsk', modemMode: 'mfsk16', label: 'MFSK16', baud: 15.625, spacing: 15.625, n: 16 },
  { fam: 'mfsk', variant: 'mfsk', modemMode: 'mfsk32', label: 'MFSK32', baud: 31.25, spacing: 31.25, n: 16 },
  { fam: 'mfsk', variant: 'mfsk', modemMode: 'mfsk64', label: 'MFSK64', baud: 62.5, spacing: 62.5, n: 16 },
  // DominoEX / THOR : IFK+ à 18 tons (même géométrie pour les deux).
  ifk('4', 'DominoEX / THOR 4', 8000, 2048, 2),
  ifk('5', 'DominoEX / THOR 5', 11025, 2048, 2),
  ifk('8', 'DominoEX / THOR 8', 8000, 1024, 2),
  ifk('11', 'DominoEX / THOR 11', 11025, 1024, 1),
  ifk('16', 'DominoEX / THOR 16', 8000, 512, 1),
  ifk('22', 'DominoEX / THOR 22', 11025, 512, 1),
  // THROB : 9 tons, un ou DEUX à la fois par symbole (pureté sur les deux plus forts).
  { fam: 'throb', variant: 'throb', modemMode: 'throb1', label: 'THROB 1', baud: 8000 / 8192, spacing: 8, n: 9, pair: true, minSym: 5 },
  { fam: 'throb', variant: 'throb', modemMode: 'throb2', label: 'THROB 2', baud: 8000 / 4096, spacing: 8, n: 9, pair: true, minSym: 8 },
  { fam: 'throb', variant: 'throb', modemMode: 'throb4', label: 'THROB 4', baud: 8000 / 2048, spacing: 16, n: 9, pair: true },
];

const MT63_BW = [500, 1000, 2000];

// ── Outils ───────────────────────────────────────────────────────────────────

function near(v, t, tolFrac) {
  if (!(v > 0)) return 0;
  const d = Math.abs(v - t) / (t * tolFrac);
  return d >= 1 ? 0 : 1 - d;
}

/** Puissance d'une fréquence sur une tranche (Goertzel : |DFT|² au point w). */
function tonePower(x, start, len, w) {
  const c = 2 * Math.cos(w);
  let s1 = 0, s2 = 0;
  const end = Math.min(x.length, start + len);
  for (let i = start; i < end; i++) {
    const s0 = x[i] + c * s1 - s2;
    s2 = s1; s1 = s0;
  }
  return s1 * s1 + s2 * s2 - c * s1 * s2;
}

/** Spectre moyen (Hann, 2048 points, recouvrement de moitié). */
function meanSpectrum(x, N = 2048) {
  const sp = new Float64Array(N / 2), re = new Float64Array(N), im = new Float64Array(N);
  for (let st = 0; st + N <= x.length; st += N / 2) {
    re.fill(0); im.fill(0);
    for (let i = 0; i < N; i++) re[i] = x[st + i] * (0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (N - 1)));
    transformFlat(re, im, false);
    for (let k = 0; k < N / 2; k++) sp[k] += re[k] * re[k] + im[k] * im[k];
  }
  return sp;
}

/**
 * Bande occupée et rapport signal/bruit, estimés sur le spectre moyen lissé
 * (≈ 20 Hz) : un signal large et plat comme le MT63 n'a pas de pic marqué,
 * c'est son plateau au-dessus du bruit qu'il faut voir.
 */
export function estimateBand(x, sps, fLo = 150, fHi = 3500) {
  const N = 2048;
  if (x.length < N * 2) return null;
  const raw = meanSpectrum(x, N);
  const binHz = sps / N;
  const kLo = Math.ceil(fLo / binHz), kHi = Math.min(raw.length - 1, Math.floor(fHi / binHz));
  const r = Math.max(1, Math.round(10 / binHz));
  const sp = new Float64Array(raw.length);
  for (let k = kLo; k <= kHi; k++) {
    let s = 0, n = 0;
    for (let d = -r; d <= r; d++) { const j = k + d; if (j >= kLo && j <= kHi) { s += raw[j]; n++; } }
    sp[k] = s / n;
  }
  const v = Array.from(sp.subarray(kLo, kHi + 1)).sort((a, b) => a - b);
  const floor = v[Math.floor(v.length * 0.2)] || 1e-30;
  let pk = 0;
  for (let k = kLo; k <= kHi; k++) if (sp[k] > pk) pk = sp[k];
  const b = occupiedBand(sp, binHz, kLo, kHi, floor * 0.5);
  b.snrDb = 10 * Math.log10(pk / floor);
  b.floor = floor;
  return b;
}

/**
 * Bande occupée par le signal : autour du pic du spectre moyen, on étend tant
 * que le niveau reste à plus de `dropDb` sous le pic, en tolérant des trous de
 * `gapHz` (les tons d'un MFSK ne sont pas tous également présents).
 */
export function occupiedBand(spec, binHz, kLo, kHi, floor, dropDb = 20, gapHz = 45) {
  let pk = kLo;
  for (let k = kLo; k <= kHi; k++) if (spec[k] > spec[pk]) pk = k;
  const edge = Math.max(spec[pk] * Math.pow(10, -dropDb / 10), floor * 4);
  const gap = Math.max(1, Math.round(gapHz / binHz));
  let lo = pk, hi = pk, miss = 0;
  for (let k = pk - 1; k >= kLo; k--) {
    if (spec[k] >= edge) { lo = k; miss = 0; } else if (++miss > gap) break;
  }
  miss = 0;
  for (let k = pk + 1; k <= kHi; k++) {
    if (spec[k] >= edge) { hi = k; miss = 0; } else if (++miss > gap) break;
  }
  return { loHz: lo * binHz, hiHz: (hi + 1) * binHz, bwHz: (hi - lo + 1) * binHz };
}

/**
 * Teste une géométrie MFSK sur l'audio : renvoie la pureté moyenne, la phase
 * des symboles retenue et la suite des tons dominants.
 */
function testGeometry(x, sps, band, h) {
  const W = Math.round(sps / h.baud);
  if (W < 16 || x.length < W * ((h.minSym || 12) + 1)) return null;
  const nSym = Math.floor(x.length / W) - 1;
  // Grille de tons : on cale le premier ton au bas de la bande, avec un
  // balayage fin d'un écart pour trouver où tombent réellement les tons.
  const span = (h.n - 1) * h.spacing;
  const centre = (band.loHz + band.hiHz) / 2;
  let bestF0 = centre - span / 2, bestE = -1;
  const probe = Math.min(nSym, 40);
  for (let s = 0; s < 8; s++) {
    const f0 = centre - span / 2 + ((s - 4) / 8) * h.spacing;
    let e = 0;
    for (let k = 0; k < probe; k++) {
      const st = Math.floor((k * nSym) / probe) * W;
      for (let j = 0; j < h.n; j++) e += tonePower(x, st, W, (2 * Math.PI * (f0 + j * h.spacing)) / sps);
    }
    if (e > bestE) { bestE = e; bestF0 = f0; }
  }
  const w = new Float64Array(h.n), wm = new Float64Array(h.n - 1);
  for (let j = 0; j < h.n; j++) w[j] = (2 * Math.PI * (bestF0 + j * h.spacing)) / sps;
  for (let j = 0; j < h.n - 1; j++) wm[j] = (2 * Math.PI * (bestF0 + (j + 0.5) * h.spacing)) / sps;

  // Phase des symboles : 8 essais, on garde la plus pure.
  let best = null;
  const P = new Float64Array(h.n);
  for (let ph = 0; ph < 8; ph++) {
    const off = Math.round((ph * W) / 8);
    let pur = 0, used = 0;
    const seq = [];
    for (let k = 0; k * W + off + W <= x.length; k++) {
      const st = k * W + off;
      let sum = 0, mx = 0, mx2 = 0, arg = 0;
      for (let j = 0; j < h.n; j++) {
        const p = tonePower(x, st, W, w[j]);
        P[j] = p; sum += p;
        if (p > mx) { mx2 = mx; mx = p; arg = j; } else if (p > mx2) mx2 = p;
      }
      if (sum <= 0) continue;
      if (h.pair) mx += mx2;
      pur += mx / sum; used++;
      seq.push({ tone: arg, pur: mx / sum, st });
    }
    if (!used) continue;
    const r = { purity: pur / used, seq, off, W, f0: bestF0 };
    if (!best || r.purity > best.purity) best = r;
  }
  if (!best) return null;
  // Énergie ENTRE les points de la grille, sur les symboles nets : un écart
  // deux fois trop grand ne voit qu'un ton sur deux, mais pas de pureté en
  // moins — c'est ici qu'il se trahit.
  let mid = 0, nm = 0, top = 0;
  for (const q of best.seq) {
    if (q.pur < 0.45) continue;
    let mm = 0;
    for (let j = 0; j < h.n - 1; j++) { const p = tonePower(x, q.st, W, wm[j]); if (p > mm) mm = p; }
    mid += mm; top += tonePower(x, q.st, W, w[q.tone]); nm++;
    if (nm >= 60) break;
  }
  best.mid = top > 0 ? mid / top : 1;
  return best;
}

/** Signature IFK : part des symboles qui répètent le ton ou ne bougent que d'un. */
function ifkViolations(seq, n) {
  let bad = 0, tot = 0;
  for (let i = 1; i < seq.length; i++) {
    if (seq[i].pur < 0.45 || seq[i - 1].pur < 0.45) continue;
    const d = (seq[i].tone - seq[i - 1].tone + n) % n;
    tot++;
    if (d === 0 || d === 1) bad++;
  }
  return tot >= 20 ? bad / tot : null;
}

/**
 * DominoEX ou THOR ? Même géométrie, mais pas le même contenu :
 *   nibble = (ton − ton précédent − 2) mod 18, toujours entre 0 et 15.
 * DominoEX transmet sa varicode telle quelle : le premier nibble d'un
 * caractère a son bit de poids fort à 0, les suivants à 1, et aucun
 * caractère n'en a plus de trois — jamais trois nibbles « de suite » d'affilée.
 * THOR transmet des bits codés (FEC) et entrelacés : nibbles quelconques, une
 * telle suite de trois arrive une fois sur huit.
 * Renvoie la part de triplets « tous suite » (le sens du décalage et la
 * convention du bit sont essayés tous les deux), ou null si trop peu.
 */
export function ifkRunStat(seq) {
  let best = null;
  for (const dir of [1, -1]) {
    const nib = [];
    let bad = 0;
    for (let i = 1; i < seq.length; i++) {
      if (seq[i].pur < 0.5 || seq[i - 1].pur < 0.5) { nib.push(-1); continue; }
      const v = (((dir * (seq[i].tone - seq[i - 1].tone) - 2) % 18) + 18) % 18;
      if (v > 15) { bad++; nib.push(-1); } else nib.push(v);
    }
    const ok = nib.filter((v) => v >= 0).length;
    if (ok < 30) continue;
    for (const hiIsCont of [true, false]) {
      let tri = 0, run = 0;
      for (let i = 2; i < nib.length; i++) {
        const a = nib[i - 2], b = nib[i - 1], c = nib[i];
        if (a < 0 || b < 0 || c < 0) continue;
        tri++;
        const cont = (v) => (hiIsCont ? v >= 8 : v < 8);
        if (cont(a) && cont(b) && cont(c)) run++;
      }
      if (tri < 20) continue;
      const r = { dir, badFrac: bad / (ok + bad), run: run / tri, tri };
      if (!best || r.badFrac < best.badFrac - 0.02 || (Math.abs(r.badFrac - best.badFrac) <= 0.02 && r.run < best.run)) best = r;
    }
  }
  return best;
}

/**
 * Part des symboles nets qui répètent exactement le ton précédent. Pour un
 * MFSK au hasard ≈ 1/N ; quand la durée supposée est trop courte (DominoEX 8
 * lu comme MFSK16, Olivia 32/1000 comme MFSK64), chaque vrai symbole est vu
 * deux fois ou plus et la répétition dépasse 1/2.
 */
function repeatFrac(seq) {
  let rep = 0, tot = 0;
  for (let i = 1; i < seq.length; i++) {
    if (seq[i].pur < 0.45 || seq[i - 1].pur < 0.45) continue;
    tot++;
    if (seq[i].tone === seq[i - 1].tone) rep++;
  }
  return tot >= 20 ? rep / tot : null;
}

/** Nombre de tons différents réellement utilisés (sur les symboles nets). */
function tonesUsed(seq, n) {
  const c = new Int32Array(n);
  let t = 0;
  for (const s of seq) if (s.pur >= 0.45) { c[s.tone]++; t++; }
  if (!t) return 0;
  let u = 0;
  for (let j = 0; j < n; j++) if (c[j] >= Math.max(2, t * 0.01)) u++;
  return u;
}

/** Part des symboles nets portée par le ton le plus fréquent. */
function topShare(seq, n) {
  const c = new Int32Array(n);
  let t = 0, m = 0;
  for (const s of seq) if (s.pur >= 0.45) { if (++c[s.tone] > m) m = c[s.tone]; t++; }
  return t ? m / t : 1;
}

/**
 * Creux d'amplitude aux frontières de symboles (mise en forme Olivia), mesuré
 * sur le TON du symbole (le bruit hors du ton ne compte pas) : puissance du
 * premier quart du symbole / celle du quart central.
 */
function boundaryDip(x, r, h, sps) {
  const e = r.W >> 3;
  let edge = 0, mid = 0;
  for (const s of r.seq) {
    if (s.pur < 0.45) continue;
    const st = s.st;
    if (st + r.W > x.length) break;
    const w = (2 * Math.PI * (r.f0 + s.tone * h.spacing)) / sps;
    // Bords (en retrait d'un seizième, la phase n'est connue qu'à W/16 près).
    edge += tonePower(x, st + (r.W >> 4), e, w) + tonePower(x, st + r.W - (r.W >> 4) - e, e, w);
    mid += 2 * tonePower(x, st + (r.W >> 1) - (e >> 1), e, w);
  }
  return mid > 0 ? edge / mid : 1;
}

/** Enveloppe à 1 kHz (moyenne quadratique par milliseconde). */
function envelope(x, sps) {
  const step = Math.max(1, Math.round(sps / 1000));
  const out = new Float32Array(Math.floor(x.length / step));
  for (let k = 0; k < out.length; k++) {
    let s = 0;
    for (let i = 0; i < step; i++) { const v = x[k * step + i]; s += v * v; }
    out[k] = Math.sqrt(s / step);
  }
  return out;
}

/**
 * Enveloppe à 1 kHz limitée à la bande du signal (mélange vers 0 Hz puis
 * moyenne glissante) : le bruit hors bande n'aplatit plus l'enveloppe.
 */
function bandEnvelope(x, sps, band) {
  const fc = (band.loHz + band.hiHz) / 2;
  const L = Math.max(4, Math.round(sps / Math.max(band.bwHz, 60)));
  const step = Math.max(1, Math.round(sps / 1000));
  const n = Math.floor((x.length - L) / step);
  if (n <= 0) return new Float32Array(0);
  const w = (2 * Math.PI * fc) / sps;
  const I = new Float64Array(x.length + 1), Q = new Float64Array(x.length + 1);
  for (let i = 0; i < x.length; i++) {
    I[i + 1] = I[i] + x[i] * Math.cos(w * i);
    Q[i + 1] = Q[i] + x[i] * Math.sin(w * i);
  }
  const out = new Float32Array(n);
  for (let k = 0; k < n; k++) {
    const a = k * step, b = a + L;
    out[k] = Math.hypot(I[b] - I[a], Q[b] - Q[a]) / L;
  }
  return out;
}

/** Bascules marche/arrêt par seconde, et taux de marche. */
function onOff(env) {
  const sorted = Float32Array.from(env).sort();
  const lo = sorted[Math.floor(sorted.length * 0.1)], hi = sorted[Math.floor(sorted.length * 0.95)];
  if (!(hi > lo * 3)) return { rate: 0, duty: 1 };
  const th = lo + (hi - lo) * 0.4;
  let on = 0, flips = 0, prev = env[0] > th;
  for (const v of env) {
    const s = v > th;
    if (s) on++;
    if (s !== prev) flips++;
    prev = s;
  }
  return { rate: flips / (env.length / 1000) / 2, duty: on / env.length };
}

/** Raie de l'enveloppe à une fréquence donnée, relative à sa moyenne. */
function envLine(env, hz) {
  let c = 0, s = 0, m = 0;
  for (let i = 0; i < env.length; i++) m += env[i];
  m /= env.length || 1;
  const w = (2 * Math.PI * hz) / 1000;
  for (let i = 0; i < env.length; i++) {
    const v = env[i] - m;
    c += v * Math.cos(w * i); s += v * Math.sin(w * i);
  }
  return m > 0 ? (2 * Math.sqrt(c * c + s * s)) / env.length / m : 0;
}

/**
 * Planéité du spectre MOYEN sur les 80 % centraux de la bande (géo./arith.).
 * MT63 : ≈ 1 (plateau) ; HFDL, phonie, SSTV : 0,5 à 0,85 (bosse ou pente).
 */
function longTermFlatness(x, sps, band) {
  const N = 2048;
  if (x.length < N * 2) return 0;
  const sp = meanSpectrum(x, N);
  const binHz = sps / N;
  const k0 = Math.ceil((band.loHz + 0.1 * band.bwHz) / binHz), k1 = Math.floor((band.hiHz - 0.1 * band.bwHz) / binHz);
  if (k1 - k0 < 4) return 0;
  // Bruit retiré (plancher estimé avec la bande) : sinon le bruit, plat par
  // nature, rend plat n'importe quel signal faible.
  const fl = band.floor || 0;
  let lg = 0, ln = 0;
  for (let k = k0; k <= k1; k++) { const v = Math.max(sp[k] - fl, fl * 0.05 + 1e-30); lg += Math.log(v); ln += v; }
  const n = k1 - k0 + 1;
  return Math.exp(lg / n) / (ln / n);
}

/**
 * Planéité moyenne de la bande trame par trame (porteuses simultanées).
 * MT63 : ~0,5 et plus ; un ton qui se déplace (FAX, SSTV, FSK) : très bas.
 */
function instantFlatness(x, sps, band) {
  // 12 sous-bandes de plusieurs points chacune : la mesure reste stable même
  // quand le bruit se mêle au signal.
  const W = 1024, nb = 12, per = 4;
  const step = (band.hiHz - band.loHz) / nb;
  if (step <= 0 || x.length < W * 4) return 0;
  // Référence de bruit : quelques fréquences hors de la bande, retirée ensuite.
  const ref = [];
  for (let f = 220; f < band.loHz - 80 && ref.length < 4; f += 97) ref.push(f);
  for (let f = 3380; f > band.hiHz + 80 && ref.length < 8; f -= 97) ref.push(f);
  let noise = 0, nn = 0;
  for (let st = 0; st + W <= x.length; st += W * 2) {
    for (const f of ref) { noise += tonePower(x, st, W, (2 * Math.PI * f) / sps); nn++; }
  }
  noise = nn ? noise / nn : 0;
  let tot = 0, n = 0;
  for (let st = 0; st + W <= x.length; st += W * 2) {
    let lg = 0, ln = 0;
    for (let b = 0; b < nb; b++) {
      let p = 0;
      for (let q = 0; q < per; q++) {
        const f = band.loHz + (b + (q + 0.5) / per) * step;
        p += tonePower(x, st, W, (2 * Math.PI * f) / sps);
      }
      p = Math.max(p / per - noise, noise * 0.05 + 1e-20);
      lg += Math.log(p); ln += p;
    }
    tot += Math.exp(lg / nb) / (ln / nb); n++;
  }
  return n ? tot / n : 0;
}

/**
 * Analyse complète. `x` : quelques secondes d'audio (Float32Array), `band` :
 * bande occupée du signal. Renvoie des candidats au format de modeId.js.
 */
export function identifyFldigi(x, sps, band = null) {
  const out = [];
  if (!x || x.length < sps * 4) return { candidates: out, info: null };
  if (!band) band = estimateBand(x, sps);
  if (!band || !(band.snrDb >= 4)) return { candidates: out, info: band ? { snrDb: +band.snrDb.toFixed(1) } : null };
  const bw = band.bwHz;
  const info = { bwHz: Math.round(bw), centerHz: Math.round((band.loHz + band.hiHz) / 2), snrDb: +band.snrDb.toFixed(1) };

  // ── MFSK, Olivia, DominoEX / THOR ─────────────────────────────────────────
  const tested = [];
  for (const h of HYP) {
    // Largeur occupée attendue : tons extrêmes + lobe principal de chacun.
    const expBw = (h.n - 1) * h.spacing + 2 * h.baud + 15;
    // Écart de largeur toléré : les tons extrêmes peuvent manquer un moment.
    const fit = near(bw, expBw, 0.45);
    if (fit <= 0) continue;
    const r = testGeometry(x, sps, band, h);
    if (!r) continue;
    tested.push({ h, r, fit });
  }
  // La meilleure pureté pour chaque famille, pondérée par la largeur.
  for (const t of tested) {
    const { h, r } = t;
    const used = tonesUsed(r.seq, h.n);
    const usage = Math.min(1, used / (h.n * (h.pair ? 0.4 : 0.75)));
    // Pureté du hasard ≈ 2/N ; une vraie géométrie dépasse 0,6.
    // (deux tons par symbole pour THROB : le hasard monte plus haut).
    const pur = h.pair ? Math.max(0, (r.purity - 0.6) / 0.3) : Math.max(0, (r.purity - 0.35) / 0.4);
    let score = Math.min(1, pur) * (0.55 + 0.45 * t.fit) * usage;
    // Énergie entre les tons de la grille : mauvais écart. Test valable
    // seulement si l'écart vaut au moins deux fois la rapidité (le milieu
    // tombe alors sur un zéro du ton voisin ; à écart = rapidité, il en
    // reçoit toujours 40 %).
    if (h.spacing >= 1.9 * h.baud && r.mid > 0.25) score *= Math.max(0, 1 - (r.mid - 0.25) * 2);
    const viol = ifkViolations(r.seq, h.n);
    if (h.fam === 'ifk') {
      // Signature IFK exigée : sans elle, c'est un autre MFSK.
      if (viol == null || viol > 0.06) score *= 0.3;
    } else if (h.fam !== 'throb' && viol != null && viol < 0.04) {
      // Un MFSK qui ne répète jamais un ton, c'est un IFK mal calé.
      score *= 0.4;
    }
    if (h.fam === 'olivia' || h.fam === 'mfsk') {
      const dip = boundaryDip(x, r, h, sps);
      t.dip = dip;
      // Olivia : creux nets aux frontières ; MFSK : enveloppe plate.
      if (h.fam === 'olivia') score *= dip < 0.75 ? 1 : 0.45;
      else score *= dip >= 0.75 ? 1 : 0.45;
    }
    // Symbole supposé trop court : chaque vrai symbole lu deux fois.
    const rep = repeatFrac(r.seq);
    if (rep != null && rep > 0.35 && !h.pair) score *= 0.3;
    // Un seul ton presque tout le temps (CW, porteuse) : pas un MFSK.
    const share = topShare(r.seq, h.n);
    if (share > 0.5) score *= 0.3;
    t.score = score;
    t.used = used;
    t.viol = viol;
  }
  tested.sort((a, b) => b.score - a.score);
  info.mfsk = tested.slice(0, 3).map((t) => ({
    mode: t.h.label, purity: +t.r.purity.toFixed(2), used: t.used, mid: +t.r.mid.toFixed(2),
    ifk: t.viol == null ? null : +t.viol.toFixed(2), dip: t.dip == null ? null : +t.dip.toFixed(2),
    score: +t.score.toFixed(2),
  }));
  const seenFam = new Set();
  for (const t of tested) {
    if (t.score < 0.4 || seenFam.has(t.h.fam)) continue;
    seenFam.add(t.h.fam);
    const why = `${t.h.n} tons à ${t.h.spacing.toFixed(2)} Hz, ${t.h.baud.toFixed(2)} Bd, ` +
      `symboles purs à ${Math.round(t.r.purity * 100)} %`;
    if (t.h.fam === 'ifk') {
      const sub = t.h.modemMode;
      const rs = ifkRunStat(t.r.seq);
      info.ifkRun = rs ? +rs.run.toFixed(3) : null;
      // Triplets « suite » : 0 en DominoEX (varicode), ≈ 1/8 en THOR (FEC).
      const pThor = rs == null ? 0.5 : rs.run >= 0.05 ? 0.95 : rs.run <= 0.015 ? 0.05 : 0.5;
      const dom = { key: 'fsk', variant: 'dominoex', modemMode: `domex${sub}`, label: `DominoEX ${sub}`,
                    score: t.score * (pThor >= 0.9 ? 0.6 : 1),
                    why: pThor <= 0.1 ? `${why}, ton jamais répété (IFK), varicode nue (pas de FEC)`
                                      : `${why}, ton jamais répété (IFK) — THOR possible` };
      const thor = { key: 'fsk', variant: 'thor', modemMode: `thor${sub}`, label: `THOR ${sub}`,
                     score: t.score * (pThor <= 0.1 ? 0.6 : pThor >= 0.9 ? 1 : 0.97),
                     why: pThor >= 0.9 ? `${why}, ton jamais répété (IFK), données codées (FEC)`
                                       : `${why}, même géométrie que DominoEX, avec FEC` };
      out.push(dom, thor);
    } else {
      out.push({ key: 'fsk', variant: t.h.variant, modemMode: t.h.modemMode, oliviaMode: t.h.oliviaMode,
                 label: t.h.label, score: t.score, why });
    }
  }

  // ── Hellschreiber, THROB, MT63 : enveloppe et bande ───────────────────────
  const env = envelope(x, sps);
  const oo = onOff(env);
  info.onOffRate = +oo.rate.toFixed(1);
  info.duty = +oo.duty.toFixed(2);

  // Feld Hell : 17,5 colonnes de 7 × 2 pixels par seconde. L'enveloppe porte
  // une raie nette à 17,5 Hz, qu'aucun autre mode ni la phonie (4-6 Hz) n'a.
  const hell = bw < 600 ? envLine(bandEnvelope(x, sps, band), 17.5) : 0;
  info.hellLine = +hell.toFixed(2);
  if (bw < 600 && hell > 0.25) {
    out.push({ key: 'fsk', variant: 'hell', modemMode: 'feld', label: 'Hellschreiber (Feld Hell)',
               score: Math.min(0.95, 0.6 + hell * 0.6),
               why: `ton seul haché au rythme des colonnes (17,5 par seconde)` });
  }

  // MT63 : 64 porteuses à la fois — bande à plat en permanence (trame par
  // trame) ET en moyenne (plateau à bords francs, là où HFDL ou la phonie
  // dessinent une bosse ou une pente).
  const iflat = instantFlatness(x, sps, band);
  info.instFlat = +iflat.toFixed(2);
  let lflat = 0;
  if (iflat > 0.5 && MT63_BW.some((b) => near(bw, b, 0.18) > 0)) lflat = longTermFlatness(x, sps, band);
  info.ltFlat = +lflat.toFixed(2);
  for (const b of MT63_BW) {
    const fit = near(bw, b, 0.18);
    if (fit <= 0 || iflat <= 0.5 || lflat < 0.95) continue;
    out.push({ key: 'fsk', variant: 'mt63', modemMode: `mt63-${b}l`, label: `MT63-${b}`,
               score: Math.min(1, 0.45 + iflat * 0.3 + (lflat - 0.95) * 4) * (0.75 + 0.25 * fit),
               why: `${Math.round(bw)} Hz occupés à plat en permanence (64 porteuses)` });
  }

  out.sort((a, b) => b.score - a.score);
  return { candidates: out, info };
}

export default identifyFldigi;
