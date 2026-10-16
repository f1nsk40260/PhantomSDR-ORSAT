/**
 * signalRefs.js — accès à la base de signaux de référence (Artemis-DB /
 * Signal Identification Wiki) livrée dans src/assets/references/<id>/.
 * (version française, F1NSK)
 *
 * Rien n'est chargé au démarrage : l'index (≈ 120 ko) et chaque fiche
 * (signal.json) sont des imports dynamiques, le spectre et le son ne sont
 * téléchargés que quand une fiche est affichée.
 */

// URL des fichiers (des chaînes seulement : les fichiers restent sur le serveur).
const IMG = import.meta.glob('../assets/references/*/spectre.webp', { query: '?url', import: 'default', eager: true });
const SND = import.meta.glob('../assets/references/*/son.opus', { query: '?url', import: 'default', eager: true });
const META = import.meta.glob('../assets/references/*/signal.json', { import: 'default' });

const path = (id, f) => `../assets/references/${id}/${f}`;

export const refImage = (id) => IMG[path(id, 'spectre.webp')] || null;
export const refSound = (id) => SND[path(id, 'son.opus')] || null;

let _index = null;
/** Liste des signaux : { id, title, cat, fmin, fmax, bw, mod, mode, … } */
export async function loadIndex() {
  if (!_index) {
    const m = await import('../assets/references/index.json');
    _index = (m.default || m).signals || [];
  }
  return _index;
}

/** Fiche complète (description, fréquences, page du wiki…). */
export async function loadRef(id) {
  const f = META[path(id, 'signal.json')];
  return f ? await f() : null;
}

// ── Decoder ID → fiche ──────────────────────────────────────────────────────
// Clé du décodeur (et variante pour le panneau fsk) → numéro de fiche.
const BY_KEY = {
  ft8: 4702, js8: 5775, ft4: 5624, wspr: 5137, navtex: 620,
  hffax: 99, sstv: 960, cw: 567,
};
const BY_VARIANT = {
  ham: 197, weather: 197, maritime: 197, psk31: 140, olivia: 504,
  mfsk: 200, dominoex: 832, thor: 1421, mt63: 1370, throb: 1443, hell: 1309,
  packet: 955, aprs: 88, contestia: 1236,
};

/** Numéro de fiche pour un candidat du Decoder ID, ou null. */
export function refIdForCandidate(c) {
  if (!c) return null;
  if (c.key === 'fsk' && c.variant && BY_VARIANT[c.variant]) return BY_VARIANT[c.variant];
  if (c.key && BY_KEY[c.key]) return BY_KEY[c.key];
  return null;
}

// ── Recherche par caractéristiques ──────────────────────────────────────────

/** Compatibilité démodulation du récepteur ↔ modes de la fiche (0..1). */
function modeScore(demod, modes) {
  if (!modes || !modes.length) return 0.7;
  const d = String(demod || '').toUpperCase();
  const m = modes.map((x) => String(x).toUpperCase());
  const has = (...k) => m.some((x) => k.some((y) => x.startsWith(y)));
  if (d === 'USB' || d === 'LSB') return has(d, 'SSB') ? 1 : has('CW') ? 0.7 : 0.35;
  if (d.startsWith('CW')) return has('CW', 'USB', 'LSB', 'SSB') ? 1 : 0.35;
  if (d === 'AM' || d === 'SAM' || d === 'QUAM') return has('AM') ? 1 : 0.35;
  if (d.includes('FM')) return has('FM', 'NFM', 'WFM') ? 1 : 0.35;
  return 0.6;
}

/**
 * Classe les fiches selon une mesure : fréquence (Hz), largeur occupée (Hz),
 * démodulation, et un filtre texte facultatif. Renvoie les meilleures, avec
 * un score 0..1 et le détail de ce qui colle.
 */
export function searchRefs(index, { freqHz, bwHz, demod, text, cat } = {}, limit = 40) {
  const t = (text || '').trim().toLowerCase();
  const out = [];
  for (const s of index) {
    if (cat && !(s.cat || []).includes(cat)) continue;
    if (t && !(`${s.title} ${(s.cat || []).join(' ')} ${(s.mod || []).join(' ')}`.toLowerCase().includes(t))) continue;

    // Fréquence : dans la plage de la fiche → 1 ; en dehors → décroît vite.
    let fs = 0.5;
    if (freqHz > 0 && s.fmin > 0 && s.fmax > 0) {
      if (freqHz >= s.fmin && freqHz <= s.fmax) fs = 1;
      else {
        const r = freqHz < s.fmin ? s.fmin / freqHz : freqHz / s.fmax;
        fs = Math.max(0, 1 - Math.log(r) / Math.log(1.5));
      }
    }
    if (freqHz > 0 && fs === 0 && !t && !cat) continue;

    // Largeur : à ×4 près, au mieux à l'identique.
    let bs = 0.3;
    if (bwHz > 0 && s.bw > 0) bs = Math.max(0, 1 - Math.abs(Math.log(s.bw / bwHz)) / Math.log(4));

    const ms = modeScore(demod, s.mode);
    const score = 0.4 * fs + 0.4 * bs + 0.2 * ms;
    out.push({ ...s, score, fs, bs, ms });
  }
  out.sort((a, b) => b.score - a.score);
  return out.slice(0, limit);
}

/** Texte de la fiche (markdown simple du wiki) → HTML sûr. */
export function mdToHtml(md) {
  const esc = String(md || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  return esc
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('');
}

/** Hz → texte lisible (kHz / MHz / GHz). */
export function fmtHz(hz) {
  if (!(hz > 0)) return '—';
  if (hz >= 1e9) return `${+(hz / 1e9).toFixed(3)} GHz`;
  if (hz >= 1e6) return `${+(hz / 1e6).toFixed(3)} MHz`;
  if (hz >= 1e3) return `${+(hz / 1e3).toFixed(2)} kHz`;
  return `${+hz.toFixed(1)} Hz`;
}
