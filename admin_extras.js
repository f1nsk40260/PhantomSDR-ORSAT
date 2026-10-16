/* admin_extras.js — pages ajoutées au panneau d'administration (F1NSK / ORSAT)
 * Mise à jour · Sauvegardes · Santé du serveur · Qualité du signal · Carte
 * Servi par /admin/extras.js (admin_extras.py). Fichier JS ordinaire : pas de
 * gabarit Jinja ici, les accolades ne posent aucun problème.
 */
(function () {
  'use strict';

  // ── Outils ────────────────────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const notify = (msg, type) => (window.toast ? window.toast(msg, type || 'ok') : console.log(msg));
  async function api(url, opts) {
    const r = await fetch(url, Object.assign({ credentials: 'same-origin' }, opts || {}));
    if (r.redirected && /\/admin\/?$/.test(r.url)) throw new Error('session expirée — reconnectez-vous');
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('json')) throw new Error('réponse inattendue (' + r.status + ')');
    return r.json();
  }
  const post = (url, body) => api(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  function fmtBytes(n) {
    if (n == null) return '—';
    const u = ['o', 'Ko', 'Mo', 'Go', 'To']; let i = 0; n = Number(n);
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + u[i];
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d)) return esc(iso);
    return d.toLocaleDateString('fr-FR') + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }
  function fmtDur(s) {
    s = Math.floor(s || 0);
    const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
    return (d ? d + ' j ' : '') + (d || h ? h + ' h ' : '') + m + ' min';
  }
  function card(title, body, dotColor, extra) {
    const dot = dotColor ? ' style="background:' + dotColor + ';box-shadow:0 0 6px ' + dotColor + '"' : '';
    return '<div class="card" style="margin-bottom:1rem;"><div class="card-header"><div class="dot"' + dot + '></div>' +
      title + (extra || '') + '</div>' + body + '</div>';
  }
  const small = 'font-size:.72rem;color:var(--text2);line-height:1.6;';
  const css = document.createElement('style');
  css.textContent = `
    .x-tbl{width:100%;border-collapse:collapse;font-size:.72rem;}
    .x-tbl th{color:var(--text3);font-weight:normal;letter-spacing:.08em;text-align:left;padding:.3rem .5rem;border-bottom:1px solid var(--border);}
    .x-tbl td{padding:.3rem .5rem;border-bottom:1px solid #0a1a0a;vertical-align:top;}
    .x-tbl tr:hover td{background:rgba(0,255,65,0.04);}
    .x-ok{color:var(--green);} .x-warn{color:var(--amber);} .x-bad{color:var(--red);} .x-dim{color:var(--text3);}
    .x-log{font-family:'Share Tech Mono',monospace;font-size:.72rem;line-height:1.5;background:#020902;border:1px solid var(--border);
      border-radius:3px;padding:.5rem .7rem;max-height:420px;overflow:auto;white-space:pre-wrap;word-break:break-word;user-select:text;}
    .x-chips{display:flex;flex-wrap:wrap;gap:.35rem;margin-bottom:.6rem;}
    .x-chip{font-size:.65rem;padding:.2rem .55rem;border:1px solid var(--border);border-radius:999px;cursor:pointer;color:var(--text2);background:#030803;}
    .x-chip.on{color:#000;background:var(--green);border-color:var(--green);}
    .x-bar{height:6px;background:#0a1a0a;border-radius:3px;overflow:hidden;}
    .x-bar > div{height:100%;background:var(--green);}
    .x-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin-bottom:1rem;}
    .x-kpi{border:1px solid var(--border);border-radius:4px;padding:.5rem .7rem;background:#030803;}
    .x-kpi .l{font-size:.58rem;color:var(--text3);letter-spacing:.12em;}
    .x-kpi .v{font-size:1rem;margin-top:.2rem;}
    #x-leaflet{height:62vh;min-height:360px;border:1px solid var(--border);border-radius:4px;background:#020902;}
    .leaflet-popup-content{font-family:'Share Tech Mono',monospace;font-size:12px;}
    .x-diff-old{background:rgba(255,64,64,.12);} .x-diff-new{background:rgba(0,255,65,.10);}
  `;
  document.head.appendChild(css);

  let timers = {};
  function stopTimers() { Object.values(timers).forEach(clearInterval); timers = {}; }

  // ══════════════════════════════════════════════════════════════════════
  //  Mise à jour
  // ══════════════════════════════════════════════════════════════════════
  let updPos = 0, updWatching = false;

  async function updRender() {
    const box = $('x-update');
    box.innerHTML = card('VERSION INSTALLÉE', '<div id="x-upd-cur" style="' + small + '">Chargement…</div>', 'var(--green)') +
      card('NOUVEAUTÉS DISPONIBLES',
        '<div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.6rem;">' +
        '<button class="btn btn-green" id="x-upd-check">🔍 VÉRIFIER</button>' +
        '<button class="btn btn-amber" id="x-upd-run" disabled>🔄 METTRE À JOUR</button>' +
        '<label style="font-size:.65rem;color:var(--text3);display:flex;align-items:center;gap:.3rem;">' +
        '<input type="checkbox" id="x-upd-force"> reconstruire le frontend même sans nouveauté</label></div>' +
        '<div id="x-upd-info" style="' + small + '">Cliquez sur VÉRIFIER pour interroger le dépôt GitHub.</div>', 'var(--amber)') +
      card('JOURNAL DE LA DERNIÈRE MISE À JOUR', '<div class="x-log" id="x-upd-log">—</div>');
    $('x-upd-check').onclick = updCheck;
    $('x-upd-run').onclick = updRun;
    $('x-upd-force').onchange = () => { $('x-upd-run').disabled = !$('x-upd-force').checked && !updHasNew; };
    try {
      const d = await api('/admin/api/update/status');
      $('x-upd-cur').innerHTML = '<b style="color:var(--green)">' + esc(d.commit) + '</b> — ' + esc(d.subject) +
        '<br><span class="x-dim">' + fmtDate(d.date) + ' · branche ' + esc(d.branch) + ' · ' + esc(d.remote) + '</span>';
      if (d.has_log || d.running) { updPos = 0; $('x-upd-log').textContent = ''; updWatch(); }
    } catch (e) { $('x-upd-cur').textContent = 'Erreur : ' + e.message; }
  }
  let updHasNew = false;

  async function updCheck() {
    const info = $('x-upd-info');
    info.textContent = 'Interrogation de GitHub…';
    try {
      const d = await post('/admin/api/update/check');
      if (!d.ok) { info.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
      updHasNew = d.commits.length > 0;
      let h = '';
      if (!updHasNew) h += '<span class="x-ok">✓ Vous êtes à jour.</span>';
      else {
        h += '<b class="x-warn">' + d.commits.length + ' nouveauté(s) :</b><ul style="margin:.3rem 0 .5rem 1.1rem;">' +
          d.commits.map((c) => '<li><span class="x-dim">' + esc(c.h) + '</span> ' + esc(c.s) + ' <span class="x-dim">(' + fmtDate(c.d) + ')</span></li>').join('') + '</ul>';
        h += '<b>Ce qui sera fait :</b><ul style="margin:.3rem 0 .5rem 1.1rem;">' +
          (d.plan.length ? d.plan.map((p) => '<li>' + esc(p) + '</li>').join('') : '<li>Mise à jour des fichiers uniquement</li>') + '</ul>';
      }
      if (d.dirty.length) h += '<div class="x-bad" style="margin-top:.4rem;">⚠ Fichiers modifiés localement (la mise à jour sera refusée) :<br>' + d.dirty.map(esc).join('<br>') + '</div>';
      info.innerHTML = h;
      $('x-upd-run').disabled = !(updHasNew || $('x-upd-force').checked);
    } catch (e) { info.innerHTML = '<span class="x-bad">✗ ' + esc(e.message) + '</span>'; }
  }

  async function updRun() {
    if (!confirm('Lancer la mise à jour maintenant ?')) return;
    $('x-upd-run').disabled = true;
    try {
      const d = await post('/admin/api/update/run', { force_build: $('x-upd-force').checked });
      if (!d.ok) { notify(d.msg, 'err'); $('x-upd-run').disabled = false; return; }
      updPos = 0; $('x-upd-log').textContent = '';
      updWatch();
    } catch (e) { notify(e.message, 'err'); $('x-upd-run').disabled = false; }
  }

  function updWatch() {
    if (updWatching) return;
    updWatching = true;
    let fails = 0, restarting = false;
    const tick = async () => {
      try {
        const d = await api('/admin/api/update/log?pos=' + updPos);
        fails = 0;
        if (restarting) { location.reload(); return; }
        if (d.text) {
          const el = $('x-upd-log');
          if (el) { el.textContent += d.text; el.scrollTop = el.scrollHeight; }
          updPos = d.pos;
          if (/### FIN rc=0 \(redémarrage du panneau\)/.test(el ? el.textContent : '')) restarting = true;
        }
        if (!d.running && !restarting) {
          updWatching = false;
          const txt = ($('x-upd-log') || {}).textContent || '';
          if (/### FIN rc=0/.test(txt)) notify('Mise à jour terminée');
          else if (/### FIN rc=/.test(txt)) notify('La mise à jour a échoué — voir le journal', 'err');
          return;
        }
      } catch (e) {
        fails++;   // proxy ou panneau en cours de redémarrage
        const el = $('x-upd-log');
        if (el && fails === 2) el.textContent += '\n… redémarrage en cours, reconnexion…\n';
        if (fails > 60) { updWatching = false; return; }
      }
      setTimeout(tick, 1200);
    };
    tick();
  }

  // ══════════════════════════════════════════════════════════════════════
  //  Sauvegardes et historique
  // ══════════════════════════════════════════════════════════════════════
  async function bkRender() {
    const box = $('x-backup');
    box.innerHTML =
      '<div class="grid grid-2">' +
      card('SAUVEGARDER',
        '<p style="' + small + 'margin-bottom:.6rem;">Un fichier .zip avec toute la configuration de la station : réglages du panneau, configurations du récepteur (.toml), signets, informations du site, message waterfall, liste des bannis.</p>' +
        '<p style="' + small + 'margin-bottom:.6rem;" class="x-warn">⚠ Le fichier contient l\'empreinte du mot de passe et la clé secrète du panneau : gardez-le pour vous.</p>' +
        '<a class="btn btn-green" href="/admin/api/backup/download" style="display:inline-block;text-decoration:none;">💾 TÉLÉCHARGER LA SAUVEGARDE</a>' +
        '<div id="x-bk-files" style="' + small + 'margin-top:.6rem;"></div>', 'var(--green)') +
      card('RESTAURER',
        '<p style="' + small + 'margin-bottom:.6rem;">Choisissez un .zip de sauvegarde : le contenu est d\'abord comparé à la configuration actuelle, rien n\'est écrit avant votre confirmation. La configuration actuelle est sauvegardée automatiquement juste avant.</p>' +
        '<input type="file" id="x-bk-file" accept=".zip" style="font-size:.7rem;color:var(--text2);">' +
        '<div id="x-bk-preview" style="' + small + 'margin-top:.6rem;"></div>', 'var(--amber)') +
      '</div>' +
      card('SAUVEGARDES CONSERVÉES SUR LE SERVEUR', '<div id="x-bk-saved" style="' + small + '">…</div>') +
      card('HISTORIQUE DES FICHIERS MODIFIÉS DEPUIS LE PANNEAU',
        '<p style="' + small + 'margin-bottom:.5rem;">Chaque enregistrement fait depuis le Config Editor, les Markers ou Site Info conserve la version précédente (30 dernières par fichier).</p>' +
        '<div id="x-hist" style="' + small + '"></div><div id="x-hist-v" style="margin-top:.6rem;"></div>');
    $('x-bk-file').onchange = bkPreview;
    try {
      const d = await api('/admin/api/backup/info');
      $('x-bk-files').innerHTML = '<span class="x-dim">' + d.files.length + ' fichiers : ' + d.files.map(esc).join(', ') + '</span>';
      $('x-bk-saved').innerHTML = d.saved.length
        ? '<table class="x-tbl"><tr><th>FICHIER</th><th>DATE</th><th>TAILLE</th><th></th></tr>' +
          d.saved.map((f) => '<tr><td>' + esc(f.name) + '</td><td>' + fmtDate(f.date) + '</td><td>' + fmtBytes(f.size) +
            '</td><td><a href="/admin/api/backup/download?name=' + encodeURIComponent(f.name) + '" style="color:var(--green);">télécharger</a></td></tr>').join('') + '</table>' +
          '<p class="x-dim" style="font-size:.62rem;margin-top:.4rem;">Une sauvegarde automatique est faite chaque jour (7 jours conservés).</p>'
        : '<span class="x-dim">Aucune pour l\'instant — la première sauvegarde automatique est faite une minute après le démarrage du panneau.</span>';
      const hist = $('x-hist');
      hist.innerHTML = d.history.length
        ? '<table class="x-tbl"><tr><th>FICHIER</th><th>VERSIONS</th><th>DERNIÈRE MODIFICATION</th><th></th></tr>' +
          d.history.map((h) => '<tr><td>' + esc(h.path) + '</td><td>' + h.count + '</td><td>' + fmtDate(h.last) +
            '</td><td><a href="#" data-k="' + esc(h.key) + '" style="color:var(--green);">voir</a></td></tr>').join('') + '</table>'
        : '<span class="x-dim">Aucune modification enregistrée pour l\'instant.</span>';
      hist.querySelectorAll('a[data-k]').forEach((a) => a.onclick = (e) => { e.preventDefault(); histVersions(a.dataset.k); });
    } catch (e) { $('x-bk-saved').textContent = 'Erreur : ' + e.message; }
  }

  async function bkPreview() {
    const f = $('x-bk-file').files[0];
    const box = $('x-bk-preview');
    if (!f) { box.innerHTML = ''; return; }
    box.textContent = 'Analyse…';
    const fd = new FormData(); fd.append('file', f); fd.append('preview', '1');
    try {
      const d = await api('/admin/api/backup/restore', { method: 'POST', body: fd });
      if (!d.ok) { box.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
      const m = d.manifest || {};
      const changed = d.files.filter((x) => x.state !== 'identique');
      let h = (m.created ? '<div class="x-dim">Sauvegarde du ' + fmtDate(m.created) + (m.host ? ' (' + esc(m.host) + ')' : '') + '</div>' : '') +
        '<table class="x-tbl" style="margin:.4rem 0;"><tr><th>FICHIER</th><th>ÉTAT</th></tr>' +
        d.files.map((x) => '<tr><td>' + esc(x.name) + '</td><td class="' + (x.state === 'identique' ? 'x-dim' : 'x-warn') + '">' + x.state + '</td></tr>').join('') + '</table>';
      if (d.refused.length) h += '<div class="x-dim">Ignorés (hors configuration) : ' + d.refused.map(esc).join(', ') + '</div>';
      h += changed.length
        ? '<button class="btn btn-amber" id="x-bk-go" style="margin-top:.4rem;">♻ RESTAURER ' + changed.length + ' FICHIER(S)</button>'
        : '<div class="x-ok">✓ Identique à la configuration actuelle, rien à restaurer.</div>';
      box.innerHTML = h;
      const go = $('x-bk-go');
      if (go) go.onclick = bkRestore;
    } catch (e) { box.innerHTML = '<span class="x-bad">✗ ' + esc(e.message) + '</span>'; }
  }

  async function bkRestore() {
    if (!confirm('Restaurer ces fichiers ? (la configuration actuelle est sauvegardée avant)')) return;
    const f = $('x-bk-file').files[0];
    const fd = new FormData(); fd.append('file', f);
    try {
      const d = await api('/admin/api/backup/restore', { method: 'POST', body: fd });
      if (!d.ok) { notify(d.msg, 'err'); return; }
      $('x-bk-preview').innerHTML = '<div class="x-ok">✓ ' + d.restored.length + ' fichier(s) restauré(s).</div>' +
        '<div class="x-dim">Copie de sécurité de l\'ancienne configuration : ' + esc(d.safety) + '</div>' +
        '<div class="x-warn" style="margin-top:.3rem;">Pour que le récepteur et le proxy relisent leur configuration, redémarrez-les (Dashboard).</div>';
      notify('Configuration restaurée');
      bkRender();
    } catch (e) { notify(e.message, 'err'); }
  }

  async function histVersions(key) {
    const box = $('x-hist-v');
    box.textContent = 'Chargement…';
    try {
      const d = await api('/admin/api/history/versions?key=' + encodeURIComponent(key));
      box.innerHTML = '<div style="' + small + '"><b>' + esc(d.path) + '</b></div>' +
        '<table class="x-tbl"><tr><th>VERSION (avant modification du)</th><th>TAILLE</th><th></th></tr>' +
        d.versions.map((v) => '<tr><td>' + fmtDate(v.date) + '</td><td>' + fmtBytes(v.size) + '</td><td>' +
          '<a href="#" data-v="' + esc(v.v) + '" data-a="see" style="color:var(--green);">comparer</a> · ' +
          '<a href="#" data-v="' + esc(v.v) + '" data-a="rest" style="color:var(--amber);">restaurer</a></td></tr>').join('') +
        '</table><div id="x-hist-diff" style="margin-top:.5rem;"></div>';
      box.querySelectorAll('a[data-v]').forEach((a) => a.onclick = (e) => {
        e.preventDefault();
        if (a.dataset.a === 'see') histDiff(key, a.dataset.v);
        else histRestore(key, a.dataset.v);
      });
    } catch (e) { box.textContent = 'Erreur : ' + e.message; }
  }

  function lineDiff(a, b) {
    // Différence ligne à ligne simple (LCS), suffisante pour des fichiers de configuration.
    const A = a.split('\n'), B = b.split('\n');
    if (A.length * B.length > 4e6) return null;
    const n = A.length, m = B.length;
    const L = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
      L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const out = []; let i = 0, j = 0;
    while (i < n && j < m) {
      if (A[i] === B[j]) { out.push([' ', A[i]]); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) out.push(['-', A[i++]]);
      else out.push(['+', B[j++]]);
    }
    while (i < n) out.push(['-', A[i++]]);
    while (j < m) out.push(['+', B[j++]]);
    return out;
  }

  async function histDiff(key, v) {
    const box = $('x-hist-diff');
    box.textContent = 'Chargement…';
    try {
      const d = await api('/admin/api/history/read?key=' + encodeURIComponent(key) + '&v=' + encodeURIComponent(v));
      const diff = lineDiff(d.content, d.current);
      if (!diff) { box.innerHTML = '<div class="x-log">' + esc(d.content) + '</div>'; return; }
      const changed = diff.some((x) => x[0] !== ' ');
      // Contexte : 3 lignes autour de chaque différence.
      const keep = new Array(diff.length).fill(false);
      diff.forEach((x, k) => { if (x[0] !== ' ') for (let t = Math.max(0, k - 3); t <= Math.min(diff.length - 1, k + 3); t++) keep[t] = true; });
      let html = '', gap = false;
      diff.forEach((x, k) => {
        if (!keep[k]) { if (!gap) { html += '<div class="x-dim">  …</div>'; gap = true; } return; }
        gap = false;
        const cls = x[0] === '-' ? 'x-diff-old' : x[0] === '+' ? 'x-diff-new' : '';
        html += '<div class="' + cls + '">' + (x[0] === ' ' ? '  ' : x[0] + ' ') + esc(x[1]) + '</div>';
      });
      box.innerHTML = '<div style="' + small + 'margin-bottom:.3rem;"><span class="x-diff-old">− version sauvegardée</span> &nbsp; <span class="x-diff-new">+ version actuelle</span></div>' +
        '<div class="x-log">' + (changed ? html : '<span class="x-dim">Identique à la version actuelle.</span>') + '</div>';
    } catch (e) { box.textContent = 'Erreur : ' + e.message; }
  }

  async function histRestore(key, v) {
    if (!confirm('Remettre cette version ? (la version actuelle reste dans l\'historique)')) return;
    try {
      const d = await post('/admin/api/history/restore', { key, v });
      notify(d.ok ? 'Version restaurée' : (d.msg || 'Erreur'), d.ok ? 'ok' : 'err');
      bkRender();
    } catch (e) { notify(e.message, 'err'); }
  }

  // ══════════════════════════════════════════════════════════════════════
  //  Santé du serveur
  // ══════════════════════════════════════════════════════════════════════
  async function healthRender() {
    const box = $('x-health');
    if (!box.dataset.init) {
      box.dataset.init = '1';
      box.innerHTML = '<div id="x-h-kpis" class="x-kpis"></div><div class="grid grid-2"><div id="x-h-left"></div><div id="x-h-right"></div></div>';
    }
    let d;
    try { d = await api('/admin/api/health'); }
    catch (e) { $('x-h-kpis').innerHTML = '<span class="x-bad">Erreur : ' + esc(e.message) + '</span>'; return; }
    const sdrOk = d.sdr && d.sdr.running;
    const certCls = !d.cert.ok ? 'x-bad' : d.cert.days < 10 ? 'x-bad' : d.cert.days < 25 ? 'x-warn' : 'x-ok';
    const used = d.disk.used / d.disk.total;
    const diskCls = used > 0.92 ? 'x-bad' : used > 0.8 ? 'x-warn' : 'x-ok';
    const memA = d.mem.MemAvailable, memT = d.mem.MemTotal;
    const kpi = (l, v, cls) => '<div class="x-kpi"><div class="l">' + l + '</div><div class="v ' + (cls || '') + '">' + v + '</div></div>';
    $('x-h-kpis').innerHTML =
      kpi('SERVEUR RADIO', sdrOk ? '● en marche' : '● arrêté', sdrOk ? 'x-ok' : 'x-bad') +
      kpi('CERTIFICAT HTTPS', d.cert.ok ? d.cert.days + ' jours restants' : 'problème', certCls) +
      kpi('DISQUE', fmtBytes(d.disk.free) + ' libres (' + Math.round(used * 100) + ' %)', diskCls) +
      kpi('MÉMOIRE DISPONIBLE', memT ? fmtBytes(memA) + ' / ' + fmtBytes(memT) : '—', memT && memA / memT < 0.1 ? 'x-warn' : '') +
      kpi('MACHINE ALLUMÉE DEPUIS', fmtDur(d.uptime)) +
      kpi('CHARGE (1/5/15 min)', d.load.map((x) => x.toFixed(2)).join(' · '));

    const svcRows = d.units.map((u) => {
      const ok = u.active === 'active';
      return '<tr><td>' + esc(u.label) + '<div class="x-dim">' + esc(u.unit) + '</div></td><td class="' + (ok ? 'x-ok' : 'x-bad') + '">' +
        esc(u.active) + ' / ' + esc(u.sub) + '</td><td>' + (u.pid || '—') + '</td><td>' + esc(u.restarts) + '</td><td class="x-dim">' + esc(u.since) + '</td></tr>';
    }).join('');
    const sdr = d.sdr || {};
    const sdrRow = '<tr><td>Serveur radio<div class="x-dim">' + esc(sdr.name || 'spectrumserver') + '</div></td><td class="' + (sdrOk ? 'x-ok' : 'x-bad') + '">' +
      (sdrOk ? 'en marche' : 'arrêté') + '</td><td>' + (sdr.pid || '—') + '</td><td class="x-dim">—</td><td class="x-dim">' + (sdr.uptime ? 'depuis ' + esc(sdr.uptime) : '') + '</td></tr>';
    $('x-h-left').innerHTML =
      card('SERVICES', '<table class="x-tbl"><tr><th>SERVICE</th><th>ÉTAT</th><th>PID</th><th>REDÉM.</th><th>ACTIF DEPUIS</th></tr>' + sdrRow + svcRows + '</table>' +
        '<p class="x-dim" style="font-size:.6rem;margin-top:.4rem;">REDÉM. = redémarrages automatiques par systemd depuis le dernier démarrage de la machine.</p>', 'var(--green)') +
      card('CERTIFICAT HTTPS', '<div style="' + small + '">' + (d.cert.ok
        ? 'Domaine <b>' + esc(d.cert.host) + '</b><br>Émis par ' + esc(d.cert.issuer) + '<br>Expire le <b class="' + certCls + '">' + fmtDate(d.cert.expires) + '</b> (' + d.cert.days + ' jours)<br><span class="x-dim">Caddy le renouvelle tout seul environ 30 jours avant l\'échéance.</span>'
        : '<span class="x-bad">' + esc(d.cert.msg || 'indisponible') + '</span>' + (d.cert.host ? '<br>Domaine : ' + esc(d.cert.host) : '')) + '</div>', 'var(--blue)');
    const maxSize = Math.max(1, ...d.sizes.map((s) => s.size));
    $('x-h-right').innerHTML =
      card('ESPACE DISQUE', '<div style="' + small + '">' + fmtBytes(d.disk.used) + ' utilisés sur ' + fmtBytes(d.disk.total) + '</div>' +
        '<div class="x-bar" style="margin:.3rem 0 .7rem;"><div style="width:' + Math.round(used * 100) + '%;background:' + (used > 0.92 ? 'var(--red)' : used > 0.8 ? 'var(--amber)' : 'var(--green)') + '"></div></div>' +
        '<table class="x-tbl">' + d.sizes.map((s) => '<tr><td>' + esc(s.label) + '</td><td style="width:40%"><div class="x-bar"><div style="width:' +
          Math.max(1, Math.round(s.size / maxSize * 100)) + '%"></div></div></td><td style="text-align:right">' + fmtBytes(s.size) + '</td></tr>').join('') + '</table>', 'var(--amber)') +
      card('DERNIERS ÉVÉNEMENTS DU SERVEUR RADIO (crash.log)',
        d.crash.length ? '<div class="x-log" style="max-height:260px;">' + d.crash.map(esc).join('\n') + '</div>'
          : '<span class="x-dim" style="font-size:.7rem;">crash.log vide ou absent : aucun plantage enregistré.</span>', 'var(--red)') +
      card('MESURE DU SIGNAL', '<div style="' + small + '">' + (d.signal.last_ok
        ? 'Dernière mesure : ' + fmtDate(new Date(d.signal.last_ok * 1000).toISOString()) : 'Aucune mesure encore') +
        (d.signal.last_error ? '<br><span class="x-bad">Dernière erreur : ' + esc(d.signal.last_error) + '</span>' : '') + '</div>');
  }

  // ══════════════════════════════════════════════════════════════════════
  //  Qualité du signal
  // ══════════════════════════════════════════════════════════════════════
  let sigHours = 24, sigBand = 'all', sigData = null;

  async function sigRender() {
    const box = $('x-signal');
    if (!box.dataset.init) {
      box.dataset.init = '1';
      box.innerHTML =
        card('BRUIT DE FOND ET SIGNAUX FORTS PAR BANDE',
          '<p style="' + small + 'margin-bottom:.6rem;">Toutes les 10 minutes, le panneau lit le waterfall du récepteur bande par bande. ' +
          '<b>Bruit de fond</b> = niveau sous lequel se trouvent 20 % des points (le « plancher » sans les signaux) ; ' +
          '<b>Signaux forts</b> = niveau dépassé par seulement 0,5 % des points (les stations les plus puissantes) ; <b>Saturés</b> = part des points au maximum de l\'échelle. ' +
          'Les valeurs sont en dB relatifs du waterfall : c\'est l\'évolution qui compte. Une hausse durable du bruit de fond sur toutes les bandes signale souvent un nouveau parasite local.</p>' +
          '<div class="x-chips" id="x-sig-per"></div><div class="x-chips" id="x-sig-bands"></div>' +
          '<canvas id="x-sig-canvas" style="width:100%;height:280px;display:block;background:#020902;border:1px solid var(--border);border-radius:3px;"></canvas>' +
          '<div style="display:flex;gap:1rem;font-size:.62rem;margin-top:.3rem;"><span style="color:var(--green)">━ bruit de fond</span><span style="color:var(--amber)">━ signaux forts</span><span style="color:var(--red)">▮ saturés (%)</span></div>',
          'var(--green)', '<span style="margin-left:auto;font-size:.6rem;color:var(--text3);cursor:pointer;" id="x-sig-now">⟳ MESURER MAINTENANT</span>') +
        card('DERNIÈRE MESURE ET TENDANCE', '<div id="x-sig-table" style="' + small + '"></div>');
      $('x-sig-now').onclick = async () => {
        $('x-sig-now').textContent = '… mesure en cours';
        try {
          const d = await post('/admin/api/signal/sample');
          notify(d.ok ? 'Mesure enregistrée' : 'Mesure impossible : ' + d.msg, d.ok ? 'ok' : 'err');
        } catch (e) { notify(e.message, 'err'); }
        $('x-sig-now').textContent = '⟳ MESURER MAINTENANT';
        sigLoad();
      };
      window.addEventListener('resize', () => { if (sigData) sigDraw(); });
    }
    const per = [[24, '24 h'], [72, '3 jours'], [168, '7 jours'], [720, '30 jours']];
    $('x-sig-per').innerHTML = per.map((p) => '<span class="x-chip' + (p[0] === sigHours ? ' on' : '') + '" data-h="' + p[0] + '">' + p[1] + '</span>').join('');
    $('x-sig-per').querySelectorAll('.x-chip').forEach((c) => c.onclick = () => { sigHours = +c.dataset.h; sigRender(); });
    sigLoad();
  }

  async function sigLoad() {
    try { sigData = await api('/admin/api/signal?hours=' + sigHours); }
    catch (e) { $('x-sig-table').textContent = 'Erreur : ' + e.message; return; }
    const present = new Set();
    sigData.rows.forEach((r) => Object.keys(r.bands || {}).forEach((b) => present.add(b)));
    const bands = [['all', 'Spectre complet']].concat(sigData.bands.filter((b) => present.has(b)).map((b) => [b, b]));
    if (!bands.some((b) => b[0] === sigBand)) sigBand = 'all';
    $('x-sig-bands').innerHTML = bands.map((b) => '<span class="x-chip' + (b[0] === sigBand ? ' on' : '') + '" data-b="' + b[0] + '">' + b[1] + '</span>').join('');
    $('x-sig-bands').querySelectorAll('.x-chip').forEach((c) => c.onclick = () => { sigBand = c.dataset.b; sigLoad(); });
    sigDraw();
    sigTable();
  }

  const val = (r, b) => (b === 'all' ? r.all : (r.bands || {})[b]);

  function sigDraw() {
    const cv = $('x-sig-canvas');
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth, H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    g.font = '11px "Share Tech Mono", monospace';
    const pts = sigData.rows.map((r) => [r.ts, val(r, sigBand)]).filter((p) => p[1]);
    if (!pts.length) {
      g.fillStyle = '#4a8a4a';
      g.fillText(sigData.state && sigData.state.last_error ? 'Mesure impossible : ' + sigData.state.last_error
        : 'Pas encore de mesure sur cette période (la première arrive environ une minute après le démarrage du panneau).', 12, 24);
      return;
    }
    const pad = { l: 44, r: 40, t: 12, b: 24 };
    const t0 = Date.now() / 1000 - sigHours * 3600, t1 = Date.now() / 1000;
    let lo = Infinity, hi = -Infinity, satMax = 1;
    pts.forEach((p) => { lo = Math.min(lo, p[1][0]); hi = Math.max(hi, p[1][1]); satMax = Math.max(satMax, p[1][2]); });
    lo = Math.floor(lo / 5) * 5 - 5; hi = Math.ceil(hi / 5) * 5 + 5;
    const X = (t) => pad.l + (t - t0) / (t1 - t0) * (W - pad.l - pad.r);
    const Y = (v) => H - pad.b - (v - lo) / (hi - lo) * (H - pad.t - pad.b);
    // grille
    g.strokeStyle = '#123012'; g.fillStyle = '#4a8a4a'; g.lineWidth = 1;
    const span = hi - lo, stepV = span > 120 ? 20 : span > 50 ? 10 : 5;
    for (let v = Math.ceil(lo / stepV) * stepV; v <= hi; v += stepV) {
      g.beginPath(); g.moveTo(pad.l, Y(v)); g.lineTo(W - pad.r, Y(v)); g.stroke();
      g.fillText(String(v), 6, Y(v) + 4);
    }
    const ticks = sigHours <= 24 ? 6 : sigHours <= 72 ? 6 : sigHours <= 168 ? 7 : 6;
    for (let k = 0; k <= ticks; k++) {
      const t = t0 + (t1 - t0) * k / ticks, d = new Date(t * 1000);
      const lbl = sigHours <= 24 ? d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
        : d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) + (sigHours <= 72 ? ' ' + d.getHours() + 'h' : '');
      g.fillText(lbl, Math.min(W - pad.r - 30, Math.max(pad.l, X(t) - 18)), H - 6);
    }
    // saturation (barres, échelle à droite)
    g.fillStyle = 'rgba(255,64,64,0.55)';
    const bw = Math.max(2, (W - pad.l - pad.r) / Math.max(30, pts.length) * 0.6);
    pts.forEach((p) => {
      if (p[1][2] > 0) {
        const h = p[1][2] / satMax * (H - pad.t - pad.b) * 0.35;
        g.fillRect(X(p[0]) - bw / 2, H - pad.b - h, bw, h);
      }
    });
    g.fillStyle = '#ff4040'; g.fillText(satMax.toFixed(satMax < 10 ? 1 : 0) + '%', W - pad.r + 4, H - pad.b - (H - pad.t - pad.b) * 0.35 + 4);
    // lignes (coupées s'il manque plus de 3 mesures)
    const line = (idx, color) => {
      g.strokeStyle = color; g.lineWidth = 1.6; g.beginPath();
      let prev = null;
      pts.forEach((p) => {
        const x = X(p[0]), y = Y(p[1][idx]);
        if (prev === null || p[0] - prev > (sigData.every || 600) * 3.5) g.moveTo(x, y); else g.lineTo(x, y);
        prev = p[0];
      });
      g.stroke();
    };
    line(1, '#ffb000');
    line(0, '#00ff41');
  }

  function sigTable() {
    const rows = sigData.rows;
    if (!rows.length) { $('x-sig-table').innerHTML = '<span class="x-dim">—</span>'; return; }
    const last = rows[rows.length - 1];
    const bands = ['all'].concat(sigData.bands.filter((b) => last.bands && last.bands[b]));
    const avg = (b) => {
      const v = rows.slice(0, -1).map((r) => val(r, b)).filter(Boolean).map((x) => x[0]);
      return v.length ? v.reduce((a, c) => a + c, 0) / v.length : null;
    };
    $('x-sig-table').innerHTML = '<div class="x-dim" style="margin-bottom:.3rem;">Mesure du ' + fmtDate(new Date(last.ts * 1000).toISOString()) + '</div>' +
      '<table class="x-tbl"><tr><th>BANDE</th><th>BRUIT DE FOND</th><th>ÉCART / MOYENNE ' + ($('x-sig-per').querySelector('.on') || {}).textContent + '</th><th>SIGNAUX FORTS</th><th>SATURÉS</th></tr>' +
      bands.map((b) => {
        const v = val(last, b), a = avg(b);
        const dlt = a == null ? null : v[0] - a;
        const cls = dlt == null ? 'x-dim' : dlt > 6 ? 'x-bad' : dlt > 3 ? 'x-warn' : dlt < -3 ? 'x-ok' : '';
        return '<tr><td>' + (b === 'all' ? 'Spectre complet' : b) + '</td><td>' + Number(v[0]).toFixed(1) + ' dB</td><td class="' + cls + '">' +
          (dlt == null ? '—' : (dlt > 0 ? '+' : '') + dlt.toFixed(1) + ' dB') + '</td><td>' + Number(v[1]).toFixed(1) + ' dB</td><td class="' + (v[2] > 0.5 ? 'x-bad' : v[2] > 0 ? 'x-warn' : 'x-dim') + '">' + Number(v[2]).toFixed(2) + ' %</td></tr>';
      }).join('') + '</table>';
  }

  // ══════════════════════════════════════════════════════════════════════
  //  Carte des auditeurs
  // ══════════════════════════════════════════════════════════════════════
  let map = null, liveLayer = null, visitLayer = null, mapHours = 24, leafletLoading = null;

  function loadLeaflet() {
    if (window.L) return Promise.resolve();
    if (leafletLoading) return leafletLoading;
    leafletLoading = new Promise((res, rej) => {
      const l = document.createElement('link');
      l.rel = 'stylesheet'; l.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(l);
      const s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      s.onload = res; s.onerror = () => rej(new Error('Leaflet n\'a pas pu être chargé (pas d\'accès à unpkg.com ?)'));
      document.head.appendChild(s);
    });
    return leafletLoading;
  }

  async function mapRender() {
    const box = $('x-map');
    if (!box.dataset.init) {
      box.dataset.init = '1';
      box.innerHTML = card('AUDITEURS SUR LA CARTE',
        '<div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center;margin-bottom:.5rem;">' +
        '<div class="x-chips" id="x-map-per" style="margin:0;"></div>' +
        '<span style="font-size:.65rem;color:#ffd24a;">● en ligne maintenant</span>' +
        '<span style="font-size:.65rem;color:#3fa9ff;">● visite sur la période</span>' +
        '<span id="x-map-count" style="font-size:.65rem;color:var(--text3);margin-left:auto;"></span></div>' +
        '<div id="x-leaflet"></div>' +
        '<p class="x-dim" style="font-size:.6rem;margin-top:.4rem;">Position = localisation approximative de l\'adresse IP (ville du fournisseur d\'accès). Visible uniquement dans ce panneau.</p>', 'var(--blue)');
    }
    const per = [[24, '24 h'], [168, '7 jours'], [720, '30 jours'], [2160, '90 jours']];
    $('x-map-per').innerHTML = per.map((p) => '<span class="x-chip' + (p[0] === mapHours ? ' on' : '') + '" data-h="' + p[0] + '">' + p[1] + '</span>').join('');
    $('x-map-per').querySelectorAll('.x-chip').forEach((c) => c.onclick = () => { mapHours = +c.dataset.h; mapRender(); });
    try { await loadLeaflet(); }
    catch (e) { $('x-leaflet').innerHTML = '<div style="padding:1rem;" class="x-bad">' + esc(e.message) + '</div>'; return; }
    if (!map) {
      map = L.map('x-leaflet', { worldCopyJump: true, attributionControl: true }).setView([46.5, 2.5], 3);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        subdomains: 'abcd', maxZoom: 18,
        attribution: '&copy; OpenStreetMap &copy; CARTO',
      }).addTo(map);
      visitLayer = L.layerGroup().addTo(map);
      liveLayer = L.layerGroup().addTo(map);
    }
    setTimeout(() => map.invalidateSize(), 50);
    mapLoad(true);
    clearInterval(timers.map);
    timers.map = setInterval(() => { if (currentPageIs('map')) mapLoad(false); }, 15000);
  }

  function currentPageIs(name) {
    const p = $('page-' + name);
    return p && p.classList.contains('active');
  }

  async function mapLoad(fit) {
    let live = [], visits = [];
    try {
      const [a, b] = await Promise.all([api('/admin/api/listeners/live'), api('/admin/api/map/visits?hours=' + mapHours)]);
      live = (a.users || []).filter((u) => u.lat != null && u.lon != null);
      visits = (b.visits || []);
    } catch (e) { notify('Carte : ' + e.message, 'err'); return; }
    visitLayer.clearLayers(); liveLayer.clearLayers();
    const bounds = [];
    visits.forEach((v) => {
      const r = Math.min(11, 4 + Math.log2(1 + v.n) * 1.6);
      L.circleMarker([v.lat, v.lon], { radius: r, color: '#3fa9ff', weight: 1, fillColor: '#3fa9ff', fillOpacity: 0.35 })
        .bindPopup('<b>' + esc(v.city || '?') + '</b>, ' + esc(v.country || '') + '<br>' + v.n + ' visite(s)<br>dernière : ' + fmtDate(v.last) +
          (v.net && v.net !== 'fixe' ? '<br>réseau : ' + esc(v.net) : ''))
        .addTo(visitLayer);
      bounds.push([v.lat, v.lon]);
    });
    // Plusieurs auditeurs au même endroit : un seul point avec la liste.
    const groups = {};
    live.forEach((u) => { const k = u.lat.toFixed(2) + ',' + u.lon.toFixed(2); (groups[k] = groups[k] || []).push(u); });
    Object.values(groups).forEach((us) => {
      const u0 = us[0];
      const html = '<b>' + esc(u0.city || '?') + '</b>, ' + esc(u0.country || '') + '<br>' + us.map((u) =>
        (u.freq_khz ? Number(u.freq_khz).toFixed(1) + ' kHz ' : '') + esc(u.mode || '') + (u.decoder ? ' · ' + esc(u.decoder) : '') +
        (u.duration ? ' · ' + esc(u.duration) : '') + (u.isp ? '<br><span style="color:#888">' + esc(u.isp) + '</span>' : '')).join('<hr style="border:0;border-top:1px solid #333;margin:3px 0">');
      L.circleMarker([u0.lat, u0.lon], { radius: 7 + Math.min(6, us.length * 1.5), color: '#ffd24a', weight: 2, fillColor: '#ffd24a', fillOpacity: 0.85 })
        .bindPopup(html).bindTooltip(us.length > 1 ? us.length + ' auditeurs' : ((u0.freq_khz ? Number(u0.freq_khz).toFixed(1) + ' kHz ' : '') + (u0.mode || '')))
        .addTo(liveLayer);
      bounds.push([u0.lat, u0.lon]);
    });
    $('x-map-count').textContent = live.length + ' en ligne · ' + visits.length + ' auditeur(s) distinct(s) sur la période';
    if (fit && bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 6 });
  }

  // ── Aiguillage depuis showPage() ──────────────────────────────────────
  window.extrasShow = function (name) {
    stopTimers();
    if (name === 'update') updRender();
    else if (name === 'backup') bkRender();
    else if (name === 'health') { healthRender(); timers.health = setInterval(() => currentPageIs('health') && healthRender(), 30000); }
    else if (name === 'signal') { sigRender(); timers.signal = setInterval(() => currentPageIs('signal') && sigLoad(), 120000); }
    else if (name === 'map') mapRender();
  };
})();
