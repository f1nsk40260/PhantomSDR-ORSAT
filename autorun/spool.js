/**
 * spool.js — journal local des stations décodées par l'autorun (ORSAT).
 *
 * Chaque station décodée (indicatif, locator, bande, mode, SNR, fréquence) est ajoutée à
 * autorun-spots/AAAAMMJJ-HH.jsonl (une ligne JSON par station, un fichier par heure UTC),
 * que l'envoi vers PSK Reporter / WSPRnet soit activé ou non. Le carnet ORSAT-LOG relit ces
 * fichiers pour en faire des observations de propagation, puis efface ceux qu'il a lus.
 * Garde-fou si le carnet ne tourne pas : les fichiers de plus de 3 jours sont effacés ici.
 */
import { appendFileSync, mkdirSync, readdirSync, unlinkSync } from 'node:fs';
import { join } from 'node:path';

const KEEP_MS = 3 * 86400 * 1000;

export class SpotSpool {
    constructor(dir) {
        this.dir = dir;
        this.count = 0;
        try { mkdirSync(dir, { recursive: true }); } catch (e) { /* signalé à l'écriture */ }
        this._sweep();
        this._timer = setInterval(() => this._sweep(), 3600 * 1000);
    }

    /** Ajoute les stations d'un créneau décodé : [{t, mode, band, call, grid, snr, f, dbm?}] */
    add(spots) {
        if (!spots.length) return;
        const byFile = new Map();
        for (const s of spots) {
            const d = new Date(s.t * 1000).toISOString();
            const name = `${d.slice(0, 4)}${d.slice(5, 7)}${d.slice(8, 10)}-${d.slice(11, 13)}.jsonl`;
            if (!byFile.has(name)) byFile.set(name, []);
            byFile.get(name).push(JSON.stringify(s));
        }
        for (const [name, lines] of byFile) {
            try {
                appendFileSync(join(this.dir, name), lines.join('\n') + '\n');
                this.count += lines.length;
            } catch (e) {
                console.error(`[autorun] journal local : ${e.message}`);
            }
        }
    }

    _sweep() {
        let names = [];
        try { names = readdirSync(this.dir); } catch { return; }
        const now = Date.now();
        for (const n of names) {
            const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})\.jsonl$/.exec(n);
            if (!m) continue;
            const t = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4]);
            if (now - t > KEEP_MS) {
                try { unlinkSync(join(this.dir, n)); } catch { /* ignore */ }
            }
        }
    }

    close() { clearInterval(this._timer); }
}
