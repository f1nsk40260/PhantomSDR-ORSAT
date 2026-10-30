/**
 * cycle.js — ORSAT : veille cyclique. Même interface qu'AutorunManager (événements
 * 'ready' / 'decode' / 'error', méthode stop()), mais une seule bande écoutée à la fois :
 * chaque créneau coché est écouté dwellS secondes (≈ 2 à 3 cycles FT8), puis le suivant ;
 * après un tour complet, pause jusqu'à periodMin minutes depuis le début du tour.
 * Charge : un décodeur et une prise audio, actifs une petite partie du temps seulement.
 * Les stations décodées (indicatif, locator) partent dans le journal local (spool.js),
 * relu par le carnet ORSAT-LOG pour le bandeau « Indice de performance ».
 */
import { EventEmitter } from 'node:events';
import { AutorunManager } from './manager.js';

const sleep = (ms, ctl) => new Promise((res) => { ctl.timer = setTimeout(res, ms); ctl.wake = res; });

export class CycleManager extends EventEmitter {
    constructor({ slots = [], host, port, dwellS = 45, periodMin = 15 } = {}) {
        super();
        this.slots = slots;
        this.host = host;
        this.port = port;
        this.dwellMs = dwellS * 1000;
        this.periodMs = periodMin * 60 * 1000;
        this._stopping = false;
        this._cur = null;
        this._ctl = {};
        this._run();
    }

    async _run() {
        while (!this._stopping) {
            const t0 = Date.now();
            for (const slot of this.slots) {
                if (this._stopping) break;
                const m = new AutorunManager({ slots: [slot], poolSize: 1, host: this.host, port: this.port });
                this._cur = m;
                for (const ev of ['ready', 'decode', 'error']) m.on(ev, (...a) => this.emit(ev, ...a));
                await sleep(this.dwellMs, this._ctl);
                this._cur = null;
                try { await m.stop(); } catch (e) { this.emit('error', e, slot); }
            }
            const rest = this.periodMs - (Date.now() - t0);
            if (rest > 0 && !this._stopping) {
                console.log(`[autorun] veille cyclique : tour terminé, pause ${Math.round(rest / 1000)} s`);
                await sleep(rest, this._ctl);
            }
        }
    }

    async stop() {
        this._stopping = true;
        clearTimeout(this._ctl.timer);
        if (this._ctl.wake) this._ctl.wake();
        if (this._cur) await this._cur.stop();
    }
}
