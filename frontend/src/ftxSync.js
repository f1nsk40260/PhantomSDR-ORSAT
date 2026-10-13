/**
 * ftxSync.js — détecteur de synchro FT8 / JS8 / FT4 pour le Decoder ID.
 * (version française, F1NSK)
 *
 * Pourquoi : modeId.js reconnaissait le FT8 à sa cadence (rafales de 12,6 s sur
 * la grille de 15 s), mesurée sur la puissance de toute la bande passante.
 * Dans un segment FT8 réel, toujours chargé, les stations se mélangent et la
 * cadence comme la largeur deviennent illisibles ; dans le bruit, la durée des
 * rafales devient floue bien avant que le FT8 cesse d'être décodable.
 *
 * Ici on cherche directement la signature du mode : ses séquences de synchro
 * (tableaux de Costas), connues d'avance. Pour chaque fréquence de départ f0 et
 * chaque décalage temporel t0, on compare l'énergie du ton attendu par la
 * synchro à celle des N tons du mode au même instant :
 *
 *     métrique = Σ P(ton attendu) / Σ P(tous les tons)
 *
 * Bruit ou signal étranger : ≈ 1/N (0,125 en FT8). Vraie synchro : proche de 1.
 * Chaque station est trouvée séparément, quelle que soit sa voisine, et le test
 * ne dépend ni de l'horloge, ni de la cadence : une seule émission suffit.
 *
 * FT8 et JS8 ont la même géométrie (8-FSK, 6,25 Hz, 0,16 s) mais pas les mêmes
 * tableaux de Costas : c'est ce qui permet enfin de les distinguer sans décoder.
 */

import { transformFlat } from './lib/fftRadix2.js';

const FT8_COSTAS = [3, 1, 4, 0, 6, 5, 2];
// JS8 (mode Normal) : trois tableaux différents, en tête, au milieu, en fin.
const JS8_COSTAS = [[4, 2, 5, 6, 1, 3, 0], [1, 5, 0, 2, 3, 6, 4], [2, 5, 0, 6, 4, 1, 3]];
const FT4_SYNC = [[0, 1, 3, 2], [1, 0, 2, 3], [2, 3, 1, 0], [3, 2, 0, 1]];

/** Géométrie et synchro de chaque mode cherché. */
const MODES = [
  {
    key: 'ft8', geom: 'g8', nTones: 8, spacing: 6.25,
    syncs: [0, 36, 72].map((off) => ({ off, arr: FT8_COSTAS })),
  },
  {
    key: 'js8', geom: 'g8', nTones: 8, spacing: 6.25,
    syncs: [0, 36, 72].map((off, i) => ({ off, arr: JS8_COSTAS[i] })),
  },
  {
    key: 'ft4', geom: 'g4', nTones: 4, spacing: 20.8333,
    // Émission de 5 s toutes les 7,5 s : une fenêtre de 18 s en contient
    // toujours une entière, on exige donc les 4 blocs (4 tons seulement, le
    // hasard est plus favorable qu'en FT8 sur une synchro partielle).
    minArrays: 4,
    syncs: [0, 33, 66, 99].map((off, i) => ({ off, arr: FT4_SYNC[i] })),
  },
];

/** Spectrogrammes : un par géométrie de symbole. 4 trames par symbole. */
const GEOMS = {
  g8: { symSec: 0.16 },   // FT8, JS8 Normal
  g4: { symSec: 0.048 },  // FT4
};

const BUFFER_SEC = 18;     // assez pour contenir deux tableaux d'une même émission
const F_LO = 200;
const F_HI = 3100;
const MIN_ARRAYS = 2;      // tableaux de synchro entièrement présents, au minimum
// Seuils de la métrique, calés au banc d'essai sur du bruit seul et sur les
// enregistrements Artemis (voir CALIBRATION plus bas).
const THRESH = { ft8: 0.36, js8: 0.40, ft4: 0.55 };
// Une synchro FT8 est presque aussi forte sous un JS8 que sous un FT8 sur
// certains tons : on n'attribue un signal à l'un que s'il bat l'autre nettement.
const FT8_JS8_MARGIN = 1.25;

function nextPow2(n) { let p = 1; while (p < n) p <<= 1; return p; }

class Spectrogram {
  constructor(sps, symSec) {
    this.sym = Math.round(symSec * sps);
    this.step = Math.max(1, Math.round(this.sym / 4));
    this.nfft = nextPow2(this.sym * 2);
    this.binHz = sps / this.nfft;
    this.kLo = Math.max(1, Math.floor(F_LO / this.binHz));
    this.kHi = Math.min(this.nfft / 2 - 1, Math.ceil(F_HI / this.binHz));
    this.nb = this.kHi - this.kLo + 1;
    this.maxFrames = Math.ceil((BUFFER_SEC * sps) / this.step);
    this.frames = [];               // Float32Array(nb) par trame, la plus ancienne d'abord
    this.win = new Float64Array(this.sym);
    for (let i = 0; i < this.sym; i++) this.win[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (this.sym - 1));
    this.re = new Float64Array(this.nfft);
    this.im = new Float64Array(this.nfft);
    this.ring = new Float32Array(this.sym);   // derniers échantillons, circulaire
    this.wpos = 0;
    this.histLen = 0;
    this.sinceStep = 0;
  }

  push(x) {
    // Fenêtre glissante de `sym` échantillons ; une trame tous les `step`.
    this.ring[this.wpos] = x;
    this.wpos = (this.wpos + 1) % this.sym;
    if (this.histLen < this.sym) this.histLen++;
    if (++this.sinceStep < this.step || this.histLen < this.sym) return;
    this.sinceStep = 0;
    const { re, im } = this;
    re.fill(0); im.fill(0);
    // wpos pointe maintenant sur l'échantillon le plus ancien.
    for (let i = 0; i < this.sym; i++) re[i] = this.ring[(this.wpos + i) % this.sym] * this.win[i];
    transformFlat(re, im, false);
    const f = new Float32Array(this.nb);
    for (let k = 0; k < this.nb; k++) {
      const kk = this.kLo + k;
      f[k] = re[kk] * re[kk] + im[kk] * im[kk];
    }
    this.frames.push(f);
    if (this.frames.length > this.maxFrames) this.frames.shift();
  }

  reset() { this.frames = []; this.histLen = 0; this.sinceStep = 0; this.wpos = 0; }
}

export class FtxSyncDetector {
  constructor(sps = 12000) {
    this.sps = sps;
    this.specs = {};
    for (const [k, g] of Object.entries(GEOMS)) this.specs[k] = new Spectrogram(sps, g.symSec);
  }

  reset() { for (const s of Object.values(this.specs)) s.reset(); }

  feed(pcm) {
    for (const s of Object.values(this.specs)) {
      for (let i = 0; i < pcm.length; i++) s.push(pcm[i]);
    }
  }

  /** Secondes d'audio en mémoire. */
  filledSec() {
    const s = this.specs.g8;
    return (s.frames.length * s.step) / this.sps;
  }

  /**
   * Cherche toutes les stations de chaque mode.
   * Retour : { ft8:[{hz,metric}], js8:[...], ft4:[...] } trié par métrique.
   */
  detect() {
    const out = { ft8: [], js8: [], ft4: [] };
    const best = {};
    for (const m of MODES) {
      const spec = this.specs[m.geom];
      best[m.key] = this._scan(spec, m);
    }
    // FT8 contre JS8 : même fréquence, on garde le plus net des deux.
    for (const key of ['ft8', 'js8', 'ft4']) {
      const spec = this.specs[MODES.find((m) => m.key === key).geom];
      const m = MODES.find((x) => x.key === key);
      const arr = best[key];
      const other = key === 'ft8' ? best.js8 : key === 'js8' ? best.ft8 : null;
      out[key] = this._peaks(arr, spec, m, other);
    }
    return out;
  }

  /** Meilleure métrique par fréquence de départ (bin), sur tous les t0. */
  _scan(spec, m) {
    const F = spec.frames.length;
    const res = new Float32Array(spec.nb);
    if (F < 8) return res;
    const toneOff = [];
    for (let j = 0; j < m.nTones; j++) toneOff.push(Math.round((j * m.spacing) / spec.binHz));
    const span = toneOff[m.nTones - 1];
    const nbF0 = spec.nb - span;
    if (nbF0 <= 0) return res;

    // Somme des N tons, par trame et par f0 : calculée une fois.
    const all = new Array(F);
    for (let t = 0; t < F; t++) {
      const fr = spec.frames[t];
      const a = new Float32Array(nbF0);
      for (let b = 0; b < nbF0; b++) {
        let s = 0;
        for (let j = 0; j < m.nTones; j++) s += fr[b + toneOff[j]];
        a[b] = s;
      }
      all[t] = a;
    }

    const lastOff = m.syncs[m.syncs.length - 1].off + m.syncs[0].arr.length - 1;
    const tMin = -4 * lastOff;
    const syncLen = m.syncs[0].arr.length;
    const exp = new Float64Array(nbF0);
    for (let t0 = tMin; t0 < F; t0 += 2) {
      // Tableaux entièrement dans la fenêtre.
      let nArr = 0, nSym = 0;
      exp.fill(0);
      for (const s of m.syncs) {
        const first = t0 + 4 * s.off;
        const last = t0 + 4 * (s.off + syncLen - 1);
        if (first < 0 || last >= F) continue;
        nArr++;
        for (let k = 0; k < syncLen; k++) {
          const t = first + 4 * k;
          const fr = spec.frames[t];
          const at = all[t];
          const o = toneOff[s.arr[k]];
          // Moyenne des rapports PAR SYMBOLE, pas rapport des sommes : sinon
          // une seule trame très forte (une syllabe, un claquement) impose son
          // rapport à toute la synchro, et la phonie passait pour du FT4.
          for (let b = 0; b < nbF0; b++) { const a = at[b]; if (a > 0) exp[b] += fr[b + o] / a; }
          nSym++;
        }
      }
      if (nArr < (m.minArrays || MIN_ARRAYS)) continue;
      for (let b = 0; b < nbF0; b++) {
        const v = exp[b] / nSym;
        if (v > res[b]) res[b] = v;
      }
    }
    return res;
  }

  _peaks(arr, spec, m, other) {
    const th = THRESH[m.key];
    const width = Math.max(1, Math.round((m.nTones * m.spacing) / spec.binHz / 2));
    const found = [];
    for (let b = 0; b < arr.length; b++) {
      const v = arr[b];
      if (v < th) continue;
      let isMax = true;
      for (let d = -width; d <= width && isMax; d++) {
        const c = b + d;
        if (d !== 0 && c >= 0 && c < arr.length && arr[c] > v) isMax = false;
      }
      if (!isMax) continue;
      if (other) {
        // L'autre mode (FT8 / JS8) fait-il mieux autour de la même fréquence ?
        let o = 0;
        for (let d = -width; d <= width; d++) {
          const c = b + d;
          if (c >= 0 && c < other.length && other[c] > o) o = other[c];
        }
        if (o * FT8_JS8_MARGIN > v) continue;
      }
      const f0 = (spec.kLo + b) * spec.binHz;
      found.push({ hz: f0 + ((m.nTones - 1) * m.spacing) / 2, metric: v });
    }
    found.sort((a, b) => b.metric - a.metric);
    return found;
  }
}

export default FtxSyncDetector;
