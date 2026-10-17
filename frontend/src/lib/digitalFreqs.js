// Fréquences « dial » (USB) recommandées des modes numériques, pour les listes
// « Fréquences connues » des décodeurs (ORSAT). Mêmes valeurs que
// autorun/bandplan.js (FT8, FT4, JS8, WSPR) ; 6 m ajouté côté navigateur pour
// les récepteurs qui le couvrent.

const fmt = (hz) => (hz / 1000).toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const list = (table) => Object.entries(table).map(([band, hz]) => ({ band, hz, label: `${band} — ${fmt(hz)} kHz` }));

export const FT8_DIALS = list({
  "160m": 1840000, "80m": 3573000, "60m": 5357000, "40m": 7074000, "30m": 10136000, "20m": 14074000,
  "17m": 18100000, "15m": 21074000, "12m": 24915000, "10m": 28074000, "6m": 50313000,
});
export const FT4_DIALS = list({
  "80m": 3575000, "40m": 7047500, "30m": 10140000, "20m": 14080000, "17m": 18104000,
  "15m": 21140000, "12m": 24919000, "10m": 28180000, "6m": 50318000,
});
export const JS8_DIALS = list({
  "160m": 1842000, "80m": 3578000, "40m": 7078000, "30m": 10130000, "20m": 14078000,
  "17m": 18104000, "15m": 21078000, "12m": 24922000, "10m": 28078000,
});
export const WSPR_DIALS = list({
  "2200m": 136000, "630m": 474200, "160m": 1836600, "80m": 3568600, "80m EU": 3592600, "60m": 5287200,
  "40m": 7038600, "30m": 10138700, "20m": 14095600, "17m": 18104600, "15m": 21094600, "12m": 24924600,
  "10m": 28124600,
});

// SSTV : fréquences d'appel usuelles (réception en USB sur toutes les bandes).
export const SSTV_DIALS = [
  ["80m", 3730000, "Europe"], ["80m", 3845000, "Amériques"], ["40m", 7171000, "international"],
  ["20m", 14230000, "principale"], ["20m", 14233000, "secondaire"], ["17m", 18160000, ""],
  ["15m", 21340000, ""], ["12m", 24975000, ""], ["10m", 28680000, ""],
].map(([band, hz, note]) => ({ band, hz, label: `${band} — ${fmt(hz)} kHz${note ? " (" + note + ")" : ""}` }));
