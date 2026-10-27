// Symboles des markers de fréquence (PhantomSDR-ORSAT).
// Chaque icône est dessinée dans une grille 24x24 et prend la couleur du texte
// (currentColor). La même liste existe dans admin_server.py (page MARKERS) :
// si on ajoute une icône ici, l'ajouter aussi là-bas avec la même clé.

const S = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const F = 'fill="currentColor" stroke="none"';

export const MARKER_ICONS = {
  pirate: {
    label: 'Pirate',
    svg: `<path ${S} d="M12 2a6 6 0 0 0-6 6c0 2 1 3.4 2.5 4.2V15h7v-2.8C17 11.4 18 10 18 8a6 6 0 0 0-6-6z"/><circle ${F} cx="9.6" cy="8" r="1.4"/><circle ${F} cx="14.4" cy="8" r="1.4"/><path ${S} d="M5 17l14 5M19 17L5 22"/>`
  },
  numerique: {
    label: 'Mode numérique',
    svg: `<path ${S} d="M2 16h4V8h4v8h4V8h4v8h4"/>`
  },
  broadcast: {
    label: 'Broadcast',
    svg: `<circle ${F} cx="12" cy="8" r="1.8"/><path ${S} d="M8.5 4.5a5 5 0 0 0 0 7M15.5 4.5a5 5 0 0 1 0 7M5.6 1.8a9 9 0 0 0 0 12.4M18.4 1.8a9 9 0 0 1 0 12.4M12 10v12M8 22l4-12 4 12"/>`
  },
  utilitaire: {
    label: 'Utilitaire',
    svg: `<circle ${S} cx="12" cy="12" r="4.5"/><circle ${F} cx="12" cy="12" r="1.6"/><path ${S} d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>`
  },
  balise: {
    label: 'Balise',
    svg: `<circle ${F} cx="12" cy="12" r="2.5"/><circle ${S} cx="12" cy="12" r="6"/><circle ${S} cx="12" cy="12" r="10" stroke-dasharray="3 3"/>`
  },
  satellite: {
    label: 'Satellite',
    svg: `<g transform="rotate(-45 12 12)"><rect ${S} x="9.5" y="9" width="5" height="6"/><rect ${S} x="1.5" y="10" width="6" height="4"/><rect ${S} x="16.5" y="10" width="6" height="4"/><path ${S} d="M7.5 12h2M14.5 12h2M12 15v3M9.5 20a3 3 0 0 1 5 0"/></g>`
  },
  meteo: {
    label: 'Météo / fax',
    svg: `<path ${S} d="M7 18a4 4 0 0 1-.6-7.95A5.5 5.5 0 0 1 17 9a4.5 4.5 0 0 1 0 9z"/>`
  },
  aviation: {
    label: 'Aviation',
    svg: `<path ${F} d="M12 2c.8 0 1.3.7 1.3 1.5V9l7.7 4.5v2l-7.7-2.3V18l2.2 1.7V21L12 20l-3.5 1v-1.3l2.2-1.7v-4.8L3 15.5v-2L10.7 9V3.5C10.7 2.7 11.2 2 12 2z"/>`
  },
  maritime: {
    label: 'Maritime',
    svg: `<circle ${S} cx="12" cy="4.5" r="2"/><path ${S} d="M12 6.5V21M8 10h8M5 14a7 7 0 0 0 14 0"/>`
  },
  militaire: {
    label: 'Militaire',
    svg: `<path ${F} d="M12 2l2.9 6.3 6.9.7-5.2 4.6 1.5 6.8L12 17l-6.1 3.4 1.5-6.8L2.2 9l6.9-.7z"/>`
  },
  horaire: {
    label: 'Signal horaire',
    svg: `<circle ${S} cx="12" cy="12" r="9"/><path ${S} d="M12 7v5l3.5 2"/>`
  },
  amateur: {
    label: 'Radioamateur',
    svg: `<path ${S} d="M12 3v19M5 6h14M6.5 10h11M8 14h8"/>`
  },
  inconnu: {
    label: 'Inconnu',
    svg: `<circle ${S} cx="12" cy="12" r="9.5"/><path ${S} d="M9.5 9.2a2.6 2.6 0 1 1 3.7 2.3c-.7.4-1.2 1-1.2 1.8v.7"/><circle ${F} cx="12" cy="17.2" r="1.1"/>`
  }
};

// Renvoie le SVG complet d'une icône (chaîne vide si la clé est inconnue).
export function markerIconSvg(key, size = 12) {
  const icon = key && MARKER_ICONS[key];
  if (!icon) return '';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" style="display:inline-block;vertical-align:-2px;margin-right:2px;flex:none" aria-label="${icon.label}">${icon.svg}</svg>`;
}

// Position du label par rapport à l'index de fréquence, selon le mode :
// LSB → à gauche, USB → à droite, AM et autres modes → centré.
export function markerLabelAlign(mode) {
  const m = String(mode || '').trim().toUpperCase();
  if (m === 'LSB') return 'left';
  if (m === 'USB') return 'right';
  return 'center';
}
