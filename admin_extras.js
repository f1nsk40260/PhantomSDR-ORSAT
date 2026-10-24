/* admin_extras.js — pages ajoutées au panneau d'administration (F1NSK / ORSAT)
 * Mise à jour · Sauvegardes · Santé du serveur · Qualité du signal · Carte · Carnet ORSAT-LOG · Diversité
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
      if (d.has_log || d.running) { updPos = 0; $('x-upd-log').textContent = ''; updWatch(!!d.running); }
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
      updWatch(true);
    } catch (e) { notify(e.message, 'err'); $('x-upd-run').disabled = false; }
  }

  // live = une mise à jour est en cours (lancée ou suivie maintenant). Hors de ce cas,
  // on se contente de réafficher l'ancien journal : sa ligne « redémarrage du panneau »
  // ne doit pas recharger la page (sinon l'onglet renvoie aussitôt au tableau de bord).
  function updWatch(live) {
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
          if (live && /### FIN rc=0 \(redémarrage du panneau\)/.test(el ? el.textContent : '')) restarting = true;
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
      // CARTO renvoie désormais des tuiles « API KEY REQUIRED » : même fond
      // sombre Esri sans clé que users.html et stats.html (tuiles natives jusqu'à z16).
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 18, maxNativeZoom: 16,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; Esri, HERE, Garmin',
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


  // ══════════════════════════════════════════════════════════════════════
  //  Carnet ORSAT-LOG (/log) : état, réglages, sauvegardes, mise à jour
  // ══════════════════════════════════════════════════════════════════════
  let olPos = 0, olWatching = false;
  const olField = (id, label, value, hint, extra) =>
    '<div style="margin-bottom:.6rem;"><label for="' + id + '" style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">' +
    label + '</label><input id="' + id + '" value="' + esc(value || '') + '" ' + (extra || '') +
    ' style="width:100%;">' + (hint ? '<div class="x-dim" style="font-size:.6rem;margin-top:.2rem;">' + hint + '</div>' : '') + '</div>';
  const day8 = (d) => (d && d.length === 8 ? d.slice(6) + '/' + d.slice(4, 6) + '/' + d.slice(0, 4) : '—');

  async function olRender() {
    const box = $('x-orsatlog');
    box.innerHTML = '<div id="x-ol-state">' + card('CARNET ORSAT-LOG', '<div style="' + small + '">Chargement…</div>') + '</div>';
    let d;
    try { d = await api('/admin/api/orsatlog/status'); }
    catch (e) { $('x-ol-state').innerHTML = card('CARNET ORSAT-LOG', '<span class="x-bad">' + esc(e.message) + '</span>', 'var(--red)'); return; }
    const u = d.unit, st = d.status || {}, cfg = d.settings || {}, bk = (d.backups || {}).items || [];
    const active = u && u.active === 'active';
    const kpi = (l, v) => '<div class="x-kpi"><div class="l">' + l + '</div><div class="v">' + v + '</div></div>';
    let html = card('ÉTAT',
      (d.ok ? '' : '<div class="x-bad" style="margin-bottom:.6rem;">✗ ' + esc(d.msg) + '</div>') +
      '<div class="x-kpis">' +
      kpi('SERVICE', u ? '<span class="' + (active ? 'x-ok' : 'x-bad') + '">' + esc(u.active + ' / ' + u.sub) + '</span>' : '<span class="x-bad">non installé</span>') +
      kpi('VERSION', esc(st.version || '—') + ' <span class="x-dim" style="font-size:.7rem;">' + esc(st.commit || '') + '</span>') +
      kpi('QSO / SWL', (st.qso ?? '—') + ' / ' + (st.swl ?? '—')) +
      kpi('QSO DE GROUPE', st.sessions ?? '—') +
      kpi('BASE', fmtBytes(st.db_size)) +
      kpi('PÉRIODE', day8(st.first_day) + ' → ' + day8(st.last_day)) +
      kpi('EN LIGNE', (st.clients ?? 0) + ' carnet · ' + (st.websdr_pages ?? 0) + ' page WebSDR') +
      (st.enrich ? kpi('ENTITÉS DXCC', st.enrich.dxcc) +
        kpi('CONFIRMÉS', st.enrich.conf + ' / ' + st.enrich.n) +
        kpi('SFI / K CONNUS', st.enrich.solar + ' / ' + st.enrich.n +
          (st.enrich.gfz ? ' <span class="x-dim" style="font-size:.65rem;" title="Complétés par l\'archive GFZ Potsdam">(' + st.enrich.gfz + ' GFZ)</span>' : '')) +
        kpi('DISTANCE CONNUE', st.enrich.dist + ' / ' + st.enrich.n) : '') +
      (st.heard ? kpi('ENTENDU (AUTORUN)', st.heard.spool_found
          ? Number(st.heard.rows).toLocaleString('fr-FR') + ' <span class="x-dim" style="font-size:.65rem;" title="Stations décodées par l\'autorun, une par heure et par bande ; détail gardé 2 ans (2 Go au plus), résumé gardé toujours">' +
            (st.heard.last_ingest ? 'lu ' + st.heard.last_ingest.slice(11) : 'en attente') + '</span>'
          : '<span class="x-dim" title="Mettre l\'autorun en service (rubrique Envoi des spots)">autorun arrêté</span>') : '') +
      '</div><div style="' + small + '">Adresse : <a href="/log/" target="_blank" style="color:var(--green);">/log/</a> · dossier ' +
      esc(d.dir) + ' · port interne ' + d.port + (u && u.since ? ' · actif depuis ' + esc(u.since) : '') + '</div>',
      active ? 'var(--green)' : 'var(--red)');

    html += '<div class="grid grid-2">' +
      card('STATION',
        '<form id="x-ol-form">' +
        olField('x-ol-call', 'INDICATIF', cfg.callsign, '', 'class="mono" style="text-transform:uppercase;"') +
        olField('x-ol-loc', 'LOCATOR STATION (QSO)', cfg.locator, 'Station émettrice (FlexRadio) : distances et azimuts des QSO.') +
        olField('x-ol-swl', 'LOCATOR WEBSDR (SWL)', cfg.swl_locator, 'Récepteur WebSDR : distances et azimuts des écoutes. Vide = locator de la station.') +
        olField('x-ol-wc', 'STATION MÉTÉO WEATHERCLOUD', cfg.weathercloud, 'Identifiant à 10 chiffres ou adresse de la station.') +
        '<div style="margin:.4rem 0 .6rem;font-size:.65rem;color:var(--text3);">CONNEXION TCI À AETHERSDR <span class="x-dim">(faite par le navigateur du poste d\'exploitation)</span></div>' +
        '<label style="font-size:.7rem;color:var(--text2);display:flex;align-items:center;gap:.4rem;margin-bottom:.5rem;">' +
        '<input type="checkbox" id="x-ol-tci"' + (cfg.tci_enabled === '1' ? ' checked' : '') + '> suivre AetherSDR</label>' +
        '<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:.5rem;">' +
        olField('x-ol-host', 'ADRESSE', cfg.tci_host) + olField('x-ol-port', 'PORT', cfg.tci_port) +
        '<div><label for="x-ol-trx" style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">RÉCEPTEUR</label>' +
        '<select id="x-ol-trx" style="width:100%;">' + ['0', '1', '2', '3'].map((n) =>
          '<option value="' + n + '"' + (String(cfg.tci_trx || '0') === n ? ' selected' : '') + '>' + 'ABCD'[+n] + ' (' + n + ')</option>').join('') +
        '</select></div></div>' +
        '<button class="btn btn-green" type="submit" style="margin-top:.4rem;">💾 ENREGISTRER</button>' +
        '<span id="x-ol-saved" style="' + small + 'margin-left:.6rem;"></span></form>', 'var(--green)') +
      card('SAUVEGARDES DU CARNET',
        '<p style="' + small + 'margin-bottom:.6rem;">Une copie automatique par jour, gardée ' + ((d.backups || {}).keep_days || 30) + ' jours, dans le dossier data/backups du carnet.</p>' +
        '<a class="btn btn-green" href="/admin/api/orsatlog/backup" style="display:inline-block;text-decoration:none;margin-bottom:.6rem;">💾 TÉLÉCHARGER UNE SAUVEGARDE</a>' +
        (bk.length ? '<table class="x-tbl"><tr><th>COPIE</th><th>DATE</th><th>TAILLE</th><th></th></tr>' + bk.slice(0, 8).map((b) =>
          '<tr><td>' + esc(b.name) + '</td><td>' + esc(b.time) + '</td><td>' + fmtBytes(b.size) +
          '</td><td><a href="/admin/api/orsatlog/backup?name=' + encodeURIComponent(b.name) + '" style="color:var(--green);">télécharger</a></td></tr>').join('') + '</table>'
          : '<div class="x-dim" style="font-size:.7rem;">Pas encore de copie.</div>') +
        '<div style="margin-top:.8rem;font-size:.65rem;color:var(--text3);">RESTAURER (en cas de panne)</div>' +
        '<p style="' + small + 'margin:.3rem 0;">Remplace TOUT le carnet par une sauvegarde .db. Le carnet actuel est sauvegardé juste avant.</p>' +
        '<input type="file" id="x-ol-restore" accept=".db" style="font-size:.7rem;color:var(--text2);">' +
        '<div id="x-ol-restore-msg" style="' + small + 'margin-top:.4rem;"></div>', 'var(--amber)') +
      '</div>';

    html += card('SYNCHRONISATION QRZ.COM', '<div id="x-ol-qrz" style="' + small + '">Chargement…</div>', 'var(--green)');

    html += card('MISE À JOUR DU CARNET',
      '<div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.6rem;">' +
      '<button class="btn btn-green" id="x-ol-check">🔍 VÉRIFIER</button>' +
      '<button class="btn btn-amber" id="x-ol-run">🔄 METTRE À JOUR</button></div>' +
      '<div id="x-ol-info" style="' + small + 'margin-bottom:.6rem;">' + esc(st.commit_subject || '') + '</div>' +
      '<p class="x-dim" style="font-size:.62rem;margin-bottom:.4rem;">Récupère le code, recompile l\'interface en basse priorité, puis redémarre le carnet (le WebSDR n\'est pas touché).</p>' +
      '<div class="x-log" id="x-ol-log">—</div>', 'var(--amber)');
    $('x-ol-state').innerHTML = html;

    $('x-ol-form').onsubmit = olSave;
    olQrzRender();
    $('x-ol-restore').onchange = olRestore;
    $('x-ol-check').onclick = olCheck;
    $('x-ol-run').onclick = olRun;
    // Mise à jour en cours : suivi en direct. Sinon, l'ancien journal est seulement affiché
    // (le relire comme une fin de mise à jour rechargeait la page en boucle).
    if (d.updating) { olPos = 0; $('x-ol-log').textContent = ''; olWatch(true); }
    else if (d.has_log) olShowLastLog();
  }

  // ── Synchronisation QRZ.com ─────────────────────────────────────────
  let olQrzTimer = null;
  let olQrzLast = {};
  async function olQrzRender(keepJournal) {
    const box = $('x-ol-qrz');
    if (!box) return;
    let d;
    try { d = await api('/admin/api/orsatlog/qrz'); } catch (e) { box.innerHTML = '<span class="x-bad">' + esc(e.message) + '</span>'; return; }
    if (!d.ok) { box.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
    olQrzLast = d;
    const kpi = (l, v) => '<div class="x-kpi"><div class="l">' + l + '</div><div class="v">' + v + '</div></div>';
    const etat = d.running ? '<span class="x-warn">synchronisation en cours…</span>'
      : d.last_error ? '<span class="x-bad">✗ ' + esc(d.last_error) + '</span>'
      : d.last_ok ? '<span class="x-ok">✓ dernière synchronisation réussie : ' + esc(d.last_ok) + '</span>'
      : '<span class="x-dim">jamais synchronisé</span>';
    if (!keepJournal || !$('x-ol-qrz-form')) {
      box.innerHTML =
        '<p style="margin-bottom:.6rem;">Le carnet de trafic et le logbook QRZ.com se tiennent à jour l\'un l\'autre : ' +
        'tout le logbook QRZ est repris au premier passage, puis toutes les 15 min les modifications faites chez QRZ, ' +
        'et chaque contact saisi ou corrigé dans le carnet part vers QRZ. Les écoutes SWL ne partent jamais. ' +
        'Une suppression dans le carnet demande s\'il faut aussi supprimer chez QRZ.</p>' +
        // Pas de <form> ni de champ « password » : le gestionnaire de mots de passe du navigateur
        // prenait l'identifiant + mot de passe QRZ pour la connexion au panneau et remplaçait le
        // mot de passe enregistré du site. Les secrets sont masqués par CSS (x-secret).
        '<div id="x-ol-qrz-form">' +
        olField('x-ol-qrz-key', 'CLÉ D\'ACCÈS DU LOGBOOK QRZ (API KEY)', '',
          d.key_set ? 'Clé enregistrée (' + esc(d.key_hint) + '). Laisser vide pour la garder.' : 'Elle est vérifiée auprès de QRZ.com avant d\'être enregistrée.',
          'type="text" class="x-secret" autocomplete="off" data-lpignore="true" data-1p-ignore spellcheck="false" placeholder="' + (d.key_set ? '••••••••' : 'XXXX-XXXX-XXXX-XXXX') + '"') +
        '<div style="font-size:.7rem;color:var(--text2);margin:.2rem 0 .3rem;">ANNUAIRE QRZ — photo, prénom, nom et QTH au clic sur un indicatif du carnet. ' +
        'Il demande l\'identifiant et le mot de passe du compte QRZ.com (pas la clé du logbook) ; sans abonnement XML, QRZ peut ne pas donner la photo.</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;">' +
        olField('x-ol-qrz-xuser', 'IDENTIFIANT QRZ.COM', d.xml_user || '', d.xml_set ? 'Vérifié et enregistré. Vider pour effacer.' : 'Votre indicatif, en général.', 'autocomplete="off" data-lpignore="true" data-1p-ignore spellcheck="false"') +
        olField('x-ol-qrz-xpwd', 'MOT DE PASSE QRZ.COM', '', d.xml_set ? 'Enregistré. Laisser vide pour le garder.' : 'Vérifié auprès de QRZ.com avant d\'être enregistré.',
          'type="text" class="x-secret" autocomplete="off" data-lpignore="true" data-1p-ignore spellcheck="false" placeholder="' + (d.xml_set ? '••••••••' : '') + '"') +
        '</div>' +
        '<label style="font-size:.7rem;color:var(--text2);display:flex;align-items:center;gap:.4rem;margin-bottom:.6rem;">' +
        '<input type="checkbox" id="x-ol-qrz-on"' + (d.enabled ? ' checked' : '') + '> synchronisation automatique</label>' +
        '<div style="display:flex;gap:.5rem;flex-wrap:wrap;">' +
        '<button class="btn btn-green" type="button" id="x-ol-qrz-save">💾 ENREGISTRER</button>' +
        '<button class="btn btn-amber" type="button" id="x-ol-qrz-run">🔄 SYNCHRONISER MAINTENANT</button>' +
        '<button class="btn" type="button" id="x-ol-qrz-full" title="Relire tout le logbook QRZ (après une coupure longue, ou en cas de doute)">RELIRE TOUT QRZ</button>' +
        '</div><div id="x-ol-qrz-msg" style="margin-top:.4rem;"></div></div>' +
        '<style>.x-secret{-webkit-text-security:disc;text-security:disc;}</style>' +
        '<div id="x-ol-qrz-state" style="margin-top:.8rem;"></div>' +
        '<div id="x-ol-grid" style="margin-top:.8rem;"></div>' +
        '<div class="x-log" id="x-ol-qrz-log" style="margin-top:.6rem;max-height:220px;">—</div>';
      $('x-ol-qrz-save').onclick = olQrzSave;
      $('x-ol-qrz-run').onclick = () => olQrzRun(false);
      $('x-ol-qrz-full').onclick = () => {
        if (confirm('Relire tout le logbook QRZ maintenant ?\n\nLes QSO retirés volontairement du carnet ne reviendront pas.')) olQrzRun(true);
      };
    }
    $('x-ol-qrz-state').innerHTML = '<div class="x-kpis">' +
      kpi('SYNCHRONISÉS', d.synced) + kpi('EN ATTENTE', d.pending) +
      kpi('REFUSÉS PAR QRZ', d.errors ? '<span class="x-bad">' + d.errors + '</span>' : 0) +
      kpi('SYNCHRO AUTO', d.enabled ? '<span class="x-ok">activée</span>' : '<span class="x-dim">désactivée</span>') +
      '</div><div>' + etat + '</div>';
    olGridRender();
    const log = $('x-ol-qrz-log');
    log.textContent = (d.journal || []).join('\n') || '—';
    log.scrollTop = log.scrollHeight;
    clearTimeout(olQrzTimer);
    if (d.running) olQrzTimer = setTimeout(() => currentPageIs('orsatlog') && olQrzRender(true), 2000);
  }

  // Locators manquants des QSO déjà enregistrés : recherche dans l'annuaire QRZ
  let olGridTimer = null;
  async function olGridRender(start) {
    const box = $('x-ol-grid');
    if (!box) return;
    let d;
    try { d = start ? await post('/admin/api/orsatlog/gridfill', {}) : await api('/admin/api/orsatlog/gridfill'); }
    catch (e) { box.innerHTML = '<span class="x-bad">' + esc(e.message) + '</span>'; return; }
    if (!d.ok) { box.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
    const st = d.state || {};
    const res = st.total ? ' — dernier passage : ' + st.filled + ' indicatif(s) trouvé(s), ' + st.qsos + ' QSO complété(s), ' +
      st.notfound + ' sans locator chez QRZ' + (st.skipped ? ', ' + st.skipped + ' portable(s) ignoré(s)' : '') : '';
    box.innerHTML = '<div style="font-size:.7rem;color:var(--text2);margin-bottom:.3rem;">LOCATORS MANQUANTS — ' +
      '<b>' + d.qsos + '</b> QSO sans locator (' + d.calls + ' indicatifs). Le locator est cherché dans l\'annuaire QRZ ' +
      '(adresse actuelle de la station), puis distance et azimut sont recalculés. Rien n\'est renvoyé vers le logbook QRZ.</div>' +
      (st.running
        ? '<span class="x-warn">recherche en cours… ' + st.done + ' / ' + st.total + (st.last ? ' · ' + esc(st.last) : '') + '</span>'
        : '<button class="btn btn-amber" type="button" id="x-ol-grid-run"' + (d.qsos ? '' : ' disabled') + '>📍 COMPLÉTER LES LOCATORS</button>' +
          '<span class="x-dim" style="font-size:.65rem;margin-left:.5rem;">' + esc(res) + '</span>' +
          (st.error ? '<div class="x-bad" style="margin-top:.3rem;">✗ ' + esc(st.error) + '</div>' : ''));
    const b = $('x-ol-grid-run');
    if (b) b.onclick = () => olGridRender(true);
    clearTimeout(olGridTimer);
    if (st.running) olGridTimer = setTimeout(() => currentPageIs('orsatlog') && olGridRender(), 3000);
  }

  async function olQrzSave(e) {
    e && e.preventDefault && e.preventDefault();
    const msg = $('x-ol-qrz-msg');
    const body = { enabled: $('x-ol-qrz-on').checked };
    const key = $('x-ol-qrz-key').value.trim();
    if (key) body.api_key = key;
    const xu = $('x-ol-qrz-xuser').value.trim(), xp = $('x-ol-qrz-xpwd').value;
    if (xu !== (olQrzLast.xml_user || '') || xp) { body.xml_user = xu; if (xp) body.xml_password = xp; }
    msg.innerHTML = '<span class="x-dim">' + (key || body.xml_user ? 'Vérification auprès de QRZ.com…' : 'Enregistrement…') + '</span>';
    try {
      const d = await post('/admin/api/orsatlog/qrz', body);
      if (!d.ok) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
      msg.innerHTML = '<span class="x-ok">✓ Enregistré</span>';
      $('x-ol-qrz-key').value = '';
      $('x-ol-qrz-xpwd').value = '';
      olQrzRender();
    } catch (err) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(err.message) + '</span>'; }
  }

  async function olQrzRun(full) {
    try {
      const d = await post('/admin/api/orsatlog/qrz/run', { full: !!full });
      if (!d.ok) { notify(d.msg, 'err'); return; }
      olQrzRender(true);
    } catch (err) { notify(err.message, 'err'); }
  }

  async function olSave(e) {
    e.preventDefault();
    const v = (id) => $(id).value.trim();
    const msg = $('x-ol-saved');
    msg.textContent = 'Enregistrement…';
    try {
      const d = await post('/admin/api/orsatlog/settings', {
        callsign: v('x-ol-call').toUpperCase(), locator: v('x-ol-loc').toUpperCase(),
        swl_locator: v('x-ol-swl').toUpperCase(), weathercloud: v('x-ol-wc'),
        tci_enabled: $('x-ol-tci').checked ? '1' : '0', tci_host: v('x-ol-host') || '127.0.0.1',
        tci_port: v('x-ol-port') || '50001', tci_trx: $('x-ol-trx').value,
      });
      if (!d.ok) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
      msg.innerHTML = '<span class="x-ok">✓ Enregistré</span> <span class="x-dim">(rechargez le carnet ouvert pour l\'appliquer)</span>';
      notify('Réglages du carnet enregistrés');
    } catch (err) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(err.message) + '</span>'; }
  }

  async function olRestore(e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!file) return;
    if (!confirm('Remplacer TOUT le carnet par « ' + file.name + ' » ?\n\nLe carnet actuel est d\'abord sauvegardé.')) return;
    const msg = $('x-ol-restore-msg');
    msg.textContent = 'Restauration…';
    const fd = new FormData();
    fd.append('file', file);
    try {
      const d = await api('/admin/api/orsatlog/restore', { method: 'POST', body: fd });
      if (!d.ok) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
      msg.innerHTML = '<span class="x-ok">✓ Carnet restauré.</span> Ancien carnet gardé : ' + esc(d.previous);
      notify('Carnet restauré');
    } catch (err) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(err.message) + '</span>'; }
  }

  async function olCheck() {
    const info = $('x-ol-info');
    info.textContent = 'Interrogation de GitHub…';
    try {
      const d = await post('/admin/api/orsatlog/check');
      if (!d.ok) { info.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
      info.innerHTML = d.commits.length
        ? '<b class="x-warn">' + d.commits.length + ' nouveauté(s) :</b><ul style="margin:.3rem 0 0 1.1rem;">' +
          d.commits.map((c) => '<li><span class="x-dim">' + esc(c.h) + '</span> ' + esc(c.s) + '</li>').join('') + '</ul>'
        : '<span class="x-ok">✓ Le carnet est à jour.</span>';
    } catch (err) { info.innerHTML = '<span class="x-bad">✗ ' + esc(err.message) + '</span>'; }
  }

  async function olRun() {
    if (!confirm('Mettre à jour le carnet ORSAT-LOG maintenant ?\n\nIl redémarre à la fin (quelques secondes) ; le WebSDR n\'est pas touché.')) return;
    try {
      const d = await post('/admin/api/orsatlog/update');
      if (!d.ok) { notify(d.msg, 'err'); return; }
      olPos = 0; $('x-ol-log').textContent = '';
      olWatch(true);
    } catch (err) { notify(err.message, 'err'); }
  }

  async function olShowLastLog() {
    try {
      const d = await api('/admin/api/orsatlog/update/log?pos=0');
      const el = $('x-ol-log');
      if (el && d.text) { el.textContent = d.text; el.scrollTop = el.scrollHeight; }
    } catch (e) { /* journal indisponible : on garde « — » */ }
  }

  function olWatch(live) {
    if (olWatching) return;
    olWatching = true;
    const tick = async () => {
      try {
        const d = await api('/admin/api/orsatlog/update/log?pos=' + olPos);
        const el = $('x-ol-log');
        if (d.text && el) { el.textContent += d.text; el.scrollTop = el.scrollHeight; }
        olPos = d.pos;
        if (!d.running) {
          olWatching = false;
          const txt = (el || {}).textContent || '';
          if (!live) return;
          if (/### FIN rc=0/.test(txt)) { notify('Carnet mis à jour'); setTimeout(() => currentPageIs('orsatlog') && olRender(), 4000); }
          else if (/### FIN rc=/.test(txt)) notify('Mise à jour du carnet échouée — voir le journal', 'err');
          return;
        }
      } catch (e) { /* panneau momentanément injoignable */ }
      setTimeout(tick, 1200);
    };
    tick();
  }

  // ══════════════════════════════════════════════════════════════════════
  //  Réception en diversité : récepteurs partenaires proposés aux auditeurs
  // ══════════════════════════════════════════════════════════════════════
  const DV_TYPES = { phantom: 'PhantomSDR / NovaSDR', kiwi: 'KiwiSDR', uber: 'UberSDR', websdr: 'WebSDR (relais)' };
  const DV_COUNTRIES = { '': '—', AT: 'Autriche', BE: 'Belgique', CH: 'Suisse', DE: 'Allemagne', ES: 'Espagne', FR: 'France',
    IE: 'Irlande', IT: 'Italie', LU: 'Luxembourg', NL: 'Pays-Bas', PL: 'Pologne' };
  let dvRows = [];
  const dvOpts = (map, cur) => Object.entries(map).map(([k, v]) =>
    '<option value="' + k + '"' + (k === cur ? ' selected' : '') + '>' + esc(k ? (k.length === 2 ? k + ' · ' + v : v) : v) + '</option>').join('');

  async function dvRender() {
    const box = $('x-diversity');
    box.innerHTML = card('RÉCEPTEURS PARTENAIRES', '<div style="' + small + '">Chargement…</div>');
    let d;
    try { d = await api('/admin/api/diversity'); }
    catch (e) { box.innerHTML = card('RÉCEPTEURS PARTENAIRES', '<span class="x-bad">' + esc(e.message) + '</span>', 'var(--red)'); return; }
    dvRows = d.partners.map((r) => Object.assign({}, r));
    dvDraw(d.saved);
  }

  function dvDraw(saved) {
    const inp = (i, k, w, ph, cls) => '<input data-i="' + i + '" data-k="' + k + '" value="' + esc(dvRows[i][k] ?? '') + '" placeholder="' + (ph || '') +
      '" style="width:' + w + ';"' + (cls ? ' class="' + cls + '"' : '') + '>';
    const rows = dvRows.map((r, i) =>
      '<tr>' +
      '<td><input type="checkbox" data-i="' + i + '" data-k="enabled"' + (r.enabled !== false ? ' checked' : '') + ' title="Proposé aux auditeurs"></td>' +
      '<td>' + inp(i, 'name', '9rem', 'Nom affiché') + '<br>' + inp(i, 'call', '9rem', 'Indicatif(s)', 'mono') + '</td>' +
      '<td><select data-i="' + i + '" data-k="country" style="width:8rem;">' + dvOpts(DV_COUNTRIES, r.country || '') + '</select><br>' + inp(i, 'place', '8rem', 'Lieu') + '</td>' +
      '<td><select data-i="' + i + '" data-k="type" style="width:10rem;">' + dvOpts(DV_TYPES, r.type) + '</select><br>' + inp(i, 'addr', '16rem', 'https://…', 'mono') + '</td>' +
      '<td>' + inp(i, 'locator', '5.5rem', 'JN47FB', 'mono') + '</td>' +
      '<td><input type="number" data-i="' + i + '" data-k="trim" value="' + (r.trim || 0) + '" min="-15" max="15" step="0.5" style="width:4.5rem;"> dB</td>' +
      '<td style="white-space:nowrap;">' +
        '<button class="btn" data-act="test" data-i="' + i + '" title="Vérifier depuis le serveur que ce récepteur répond">Tester</button> ' +
        '<button class="btn" data-act="up" data-i="' + i + '" title="Monter"' + (i ? '' : ' disabled') + '>▲</button>' +
        '<button class="btn" data-act="down" data-i="' + i + '" title="Descendre"' + (i < dvRows.length - 1 ? '' : ' disabled') + '>▼</button> ' +
        '<button class="btn" data-act="del" data-i="' + i + '" title="Supprimer ce partenaire" style="color:var(--red);">✕</button>' +
        '<div id="x-dv-t' + i + '" style="font-size:.62rem;max-width:16rem;white-space:normal;margin-top:.2rem;"></div></td>' +
      '</tr>').join('');
    $('x-diversity').innerHTML = card('RÉCEPTEURS PARTENAIRES',
      '<div style="' + small + 'margin-bottom:.7rem;">Les auditeurs choisissent uniquement parmi ces récepteurs (ordre conservé) ; ils ne peuvent saisir aucune autre adresse. ' +
      'Un bon partenaire est assez loin d\'ORSAT pour que les évanouissements soient indépendants (300 km au moins) et assez près pour entendre les mêmes stations (1500 km au plus). ' +
      'Une adresse en <b>http</b> (souvent les KiwiSDR) passe automatiquement par le relais du serveur ORSAT quand la page est ouverte en https (le navigateur refuserait la connexion directe) ; les auditeurs relayés apparaissent alors chez le partenaire avec l\'adresse IP d\'ORSAT. ' +
      '<b>Correction</b> : ajoutée au SNR du partenaire avant la comparaison (un codec avec pertes fait paraître son SNR plus bas ; 0 pour un autre PhantomSDR). ' +
      'Décocher la première case retire un partenaire sans l\'effacer.' +
      (saved ? '' : '<br><span class="x-warn">Liste par défaut : rien n\'est encore enregistré.</span>') + '</div>' +
      '<div style="overflow-x:auto;"><table class="x-tbl"><thead><tr><th>ACTIF</th><th>NOM · INDICATIF</th><th>PAYS · LIEU</th><th>TYPE · ADRESSE</th><th>LOCATOR</th><th>CORRECTION</th><th></th></tr></thead><tbody>' +
      (rows || '<tr><td colspan="7" class="x-dim">Aucun partenaire : la diversité ne sera pas proposée.</td></tr>') + '</tbody></table></div>' +
      '<div style="display:flex;gap:.6rem;align-items:center;margin-top:.8rem;">' +
      '<button class="btn" id="x-dv-add">+ Ajouter un partenaire</button>' +
      '<button class="btn btn-green" id="x-dv-save">💾 ENREGISTRER</button><span id="x-dv-msg" style="font-size:.7rem;"></span></div>',
      'var(--green)');
    const box = $('x-diversity');
    box.querySelectorAll('[data-k]').forEach((el) => el.addEventListener(el.type === 'checkbox' || el.tagName === 'SELECT' ? 'change' : 'input', () => {
      const r = dvRows[+el.dataset.i];
      r[el.dataset.k] = el.type === 'checkbox' ? el.checked : el.dataset.k === 'trim' ? Number(el.value) || 0 : el.value;
      $('x-dv-msg').innerHTML = '<span class="x-warn">Modifications non enregistrées</span>';
    }));
    box.querySelectorAll('[data-act]').forEach((el) => el.addEventListener('click', () => dvAct(el.dataset.act, +el.dataset.i)));
    $('x-dv-add').onclick = () => { dvRows.push({ enabled: true, name: '', call: '', country: '', place: '', type: 'phantom', addr: '', locator: '', trim: 0 }); dvDraw(saved); };
    $('x-dv-save').onclick = dvSave;
  }

  async function dvAct(act, i) {
    if (act === 'up' && i > 0) { [dvRows[i - 1], dvRows[i]] = [dvRows[i], dvRows[i - 1]]; dvDraw(true); }
    else if (act === 'down' && i < dvRows.length - 1) { [dvRows[i + 1], dvRows[i]] = [dvRows[i], dvRows[i + 1]]; dvDraw(true); }
    else if (act === 'del') { dvRows.splice(i, 1); dvDraw(true); $('x-dv-msg').innerHTML = '<span class="x-warn">Modifications non enregistrées</span>'; }
    else if (act === 'test') {
      const out = $('x-dv-t' + i);
      out.innerHTML = '<span class="x-dim">test en cours…</span>';
      try {
        const d = await post('/admin/api/diversity/test', { addr: dvRows[i].addr, type: dvRows[i].type });
        out.innerHTML = '<span class="' + (d.ok ? 'x-ok' : 'x-bad') + '">' + (d.ok ? '✓ ' : '✗ ') + esc(d.msg) + '</span>';
      } catch (e) { out.innerHTML = '<span class="x-bad">✗ ' + esc(e.message) + '</span>'; }
    }
  }

  async function dvSave() {
    const msg = $('x-dv-msg');
    try {
      const d = await post('/admin/api/diversity', { partners: dvRows });
      if (!d.ok) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(d.msg) + '</span>'; return; }
      dvRows = d.partners.map((r) => Object.assign({}, r));
      dvDraw(true);
      $('x-dv-msg').innerHTML = '<span class="x-ok">✓ Enregistré — visible des auditeurs au prochain chargement de la page</span>';
      notify('Partenaires de diversité enregistrés');
    } catch (e) { msg.innerHTML = '<span class="x-bad">✗ ' + esc(e.message) + '</span>'; }
  }

  // ── Aiguillage depuis showPage() ──────────────────────────────────────
  window.extrasShow = function (name) {
    stopTimers();
    if (name === 'update') updRender();
    else if (name === 'backup') bkRender();
    else if (name === 'health') { healthRender(); timers.health = setInterval(() => currentPageIs('health') && healthRender(), 30000); }
    else if (name === 'signal') { sigRender(); timers.signal = setInterval(() => currentPageIs('signal') && sigLoad(), 120000); }
    else if (name === 'map') mapRender();
    else if (name === 'orsatlog') olRender();
    else if (name === 'diversity') dvRender();
  };
})();
