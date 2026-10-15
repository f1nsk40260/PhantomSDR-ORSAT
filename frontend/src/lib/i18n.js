// ─────────────────────────────────────────────────────────────────────────────
// i18n.js — traduction intégrale FR / EN / ES de l'interface PhantomSDR+ (F1NSK)
//
// Principe : plutôt que de réécrire chaque libellé de App.svelte et des
// sous-composants en {$t('clé')}, l'interface est traduite au niveau du DOM.
// Un MutationObserver voit chaque texte et chaque attribut title / placeholder /
// aria-label que Svelte écrit, et le remplace par sa traduction.
//
//  • Le dictionnaire D associe les trois langues d'un même libellé : la source
//    peut être en français ou en anglais (l'interface est mixte), peu importe.
//  • Les textes inconnus (fréquences, indicatifs, texte décodé…) ne sont pas
//    touchés : seule une correspondance exacte est traduite.
//  • Le texte d'origine est mémorisé par nœud : changer de langue retraduit
//    depuis l'original, sans dérive.
//  • Un élément (et tout son contenu) portant data-no-i18n est ignoré.
//
// Ajouter un libellé : une ligne [fr, en, es] dans D.
// Libellé contenant une valeur variable : une ligne dans P, avec $1, $2…
// Dans la console du navigateur, i18nMissing() liste les textes vus à l'écran
// qui n'ont pas encore de traduction.
// ─────────────────────────────────────────────────────────────────────────────

import { writable } from "svelte/store";

export const LANGS = ["fr", "en", "es"];
export const LANG_NAMES = { fr: "Français", en: "English", es: "Español" };
const IDX = { fr: 0, en: 1, es: 2 };
// Drapeaux en SVG intégré : les émojis drapeaux ne s'affichent pas sous
// Windows ni dans Chrome sous Linux (ils y deviennent les lettres « FR »).
const FLAG_ATTR = 'class="lang-flag" viewBox="0 0 60 40" preserveAspectRatio="none" aria-hidden="true"';
export const LANG_FLAGS = {
  fr: `<svg ${FLAG_ATTR}><rect width="20" height="40" fill="#002395"/><rect x="20" width="20" height="40" fill="#fff"/><rect x="40" width="20" height="40" fill="#ED2939"/></svg>`,
  en: `<svg ${FLAG_ATTR}><clipPath id="lang-uk-clip"><path d="M30,20h30v20zv20h-30zh-30v-20zv-20h30z"/></clipPath><rect width="60" height="40" fill="#012169"/><path d="M0,0L60,40M60,0L0,40" stroke="#fff" stroke-width="8"/><path d="M0,0L60,40M60,0L0,40" clip-path="url(#lang-uk-clip)" stroke="#C8102E" stroke-width="5"/><path d="M30,0v40M0,20h60" stroke="#fff" stroke-width="12"/><path d="M30,0v40M0,20h60" stroke="#C8102E" stroke-width="7"/></svg>`,
  es: `<svg ${FLAG_ATTR}><rect width="60" height="40" fill="#AA151B"/><rect y="10" width="60" height="20" fill="#F1BF00"/></svg>`,
};

const STORAGE_KEY = "phantom.lang";

function initialLang() {
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    if (LANGS.includes(s)) return s;
  } catch (e) {}
  const nav = String(navigator.language || "fr").slice(0, 2).toLowerCase();
  return LANGS.includes(nav) ? nav : "fr";
}

let current = initialLang();
export const lang = writable(current);

// ── Dictionnaire : [français, anglais, espagnol] ────────────────────────────
const D = [
  // En-tête
  [", situé à", ", located in", ", ubicado en"],
  ["Page QRZ :", "QRZ page :", "Página QRZ :"],
  [", SDR sur le Web situé à", ", SDR over Web located at", ", SDR por la Web ubicado en"],
  ["Page QRZ du Sysop", "Sysop's QRZ page", "Página QRZ del Sysop"],
  ["Ouvre la carte satellite du QTH de l'ORSAT", "Opens the satellite map of the ORSAT QTH", "Abre el mapa satelital del QTH del ORSAT"],
  ["e-mail", "email", "correo"],
  ["Utilisateurs connectés", "Connected users", "Usuarios conectados"],
  ["📝 Utilisateurs", "📝 Users", "📝 Usuarios"],
  ["📊 Stats", "📊 Stats", "📊 Estadísticas"],
  ["Statistiques des connexions", "Connection statistics", "Estadísticas de conexiones"],
  ["- Autres serveurs :", "- Other servers:", "- Otros servidores:"],
  ["Récepteurs :", "Receivers:", "Receptores:"],
  ["Recherche de fréquence :", "Frequency Search :", "Búsqueda de frecuencia:"],
  ["Identifiez la Station MW que vous écoutez", "Identify the MW station you are listening to", "Identifique la estación de OM que escucha"],
  ["Identifiez la Station SW que vous écoutez", "Identify the SW station you are listening to", "Identifique la estación de OC que escucha"],
  ["Site PSK Reporter", "PSK Reporter website", "Sitio PSK Reporter"],
  ["Site WSPRnet", "WSPRnet website", "Sitio WSPRnet"],
  ["Recherche d'indicatif :", "Callsign Search:", "Búsqueda de indicativo:"],
  ["Rechercher", "Search", "Buscar"],
  ["PhantomSDR+ à", "PhantomSDR+ in", "PhantomSDR+ en"],
  ["Autres", "Other", "Otros"],
  ["serveurs", "Servers", "servidores"],
  ["Mobile simplifié", "Simplified mobile", "Móvil simplificado"],
  ["Version mobile simplifiée", "Simplified mobile version", "Versión móvil simplificada"],

  // Fenêtres modales
  ["Raccourcis clavier", "Keyboard Shortcuts", "Atajos de teclado"],
  ["Raccourcis clavier dans le waterfall", "Keyboard Shortcuts inside Waterfall", "Atajos de teclado en la cascada"],
  ["Modes LSB, USB, AM, QUAM, FM", "LSB, USB, AM, QUAM, FM mode", "Modos LSB, USB, AM, QUAM, FM"],
  ["inverser le waterfall", "reverse waterfall", "invertir la cascada"],
  ["Molette haut/bas", "Wheel up/down", "Rueda arriba/abajo"],
  ["Zoom avant/arrière", "Zoom in/out", "Acercar/alejar"],
  ["Shift + molette haut/bas", "Shift + Wheel up/down", "Mayús + rueda arriba/abajo"],
  ["Accord ±100 Hz", "Tune ±100 Hz", "Sintonía ±100 Hz"],
  ["Ctrl + molette haut/bas", "Ctrl + Wheel up/down", "Ctrl + rueda arriba/abajo"],
  ["Accord ±10 Hz", "Tune ±10 Hz", "Sintonía ±10 Hz"],
  ["Ctrl + Shift + molette", "Ctrl + Shift + Wheel", "Ctrl + Mayús + rueda"],
  ["Caler sur .00 kHz", "Snap to .00 kHz", "Ajustar a .00 kHz"],
  ["Appuyez sur", "Press", "Pulse"],
  ["Échap", "Esc", "Esc"],
  ["ou cliquez sur", "or click", "o haga clic en"],
  ["pour fermer.", "to close.", "para cerrar."],
  ["Touchez", "Tap", "Toque"],
  ["ou en dehors de cette fenêtre pour fermer.", "or outside this window to close.", "o fuera de esta ventana para cerrar."],
  ["Fermer la fenêtre", "Close the window", "Cerrar la ventana"],
  ["Fermer", "Close", "Cerrar"],
  ["👥 Utilisateurs connectés", "👥 Connected Users", "👥 Usuarios conectados"],
  ["📊 Statistiques des utilisateurs", "📊 User Statistics", "📊 Estadísticas de usuarios"],
  ["Connexion refusée", "Connection refused", "Conexión rechazada"],
  ["Ce récepteur a refusé la connexion :", "This receiver refused the connection:", "Este receptor rechazó la conexión:"],
  ["Toutes les personnes partageant votre connexion Internet comptent comme une seule adresse. Fermez les autres onglets ouverts sur ce récepteur, puis rechargez.",
   "Everyone sharing your internet connection counts as one address. Close any other tabs that have this receiver open, then reload.",
   "Todas las personas que comparten su conexión a Internet cuentan como una sola dirección. Cierre las demás pestañas abiertas en este receptor y recargue."],
  ["Recharger", "Reload", "Recargar"],

  // Menu repliable
  ["Fermer les fenêtres", "Close Windows", "Cerrar las ventanas"],
  ["Ouvrir Météo - Alertes - Infos - Propagation - DXcluster et Manuels utilisateur",
   "Open Meteo - Alerts - Infos - Propagation - DXcluster and User Manuals",
   "Abrir Meteo - Alertas - Info - Propagación - DXcluster y Manuales de usuario"],
  ["hamdash : indicatif", "hamdash: callsign", "hamdash: indicativo"],
  ["· locator", "· locator", "· localizador"],
  ["Copier", "Copy", "Copiar"],
  ["Copié !", "Copied!", "¡Copiado!"],
  ["Copier l'indicatif et le locator pour les coller dans hamdash", "Copy the callsign and locator to paste them into hamdash", "Copiar el indicativo y el localizador para pegarlos en hamdash"],
  ["Propagation", "Propagation", "Propagación"],
  ["Météo spatiale", "Space Weather", "Meteorología espacial"],
  ["Météo & alertes", "Weather & Alerts", "Tiempo y alertas"],
  ["Carte en direct", "Live Map", "Mapa en directo"],
  ["Concours", "Contests", "Concursos"],
  ["Satellites", "Satellites", "Satélites"],
  ["Prévisions de propagation HF", "HF propagation forecasts", "Previsiones de propagación HF"],
  ["Météo spatiale : vent solaire, indices K et A, éruptions", "Space weather: solar wind, K and A indices, flares", "Meteorología espacial: viento solar, índices K y A, erupciones"],
  ["Météo locale et alertes orages", "Local weather and storm alerts", "Tiempo local y alertas de tormenta"],
  ["Spots du DX cluster en direct", "Live DX cluster spots", "Spots del DX cluster en directo"],
  ["Carte des bandes et des stations en direct", "Live map of bands and stations", "Mapa en directo de bandas y estaciones"],
  ["Calendrier des concours", "Contest calendar", "Calendario de concursos"],
  ["Passages des satellites radioamateurs", "Amateur radio satellite passes", "Pasos de satélites de radioaficionado"],
  ["Synchroniser le récepteur avec le DX cluster", "Sync the receiver with the DX cluster", "Sincronizar el receptor con el DX cluster"],
  ["Accorder le récepteur sur une fréquence du DX cluster", "Tune the receiver to a DX cluster frequency", "Sintonizar el receptor en una frecuencia del DX cluster"],
  ["Installation & configuration :", "Setup & Configuration:", "Instalación y configuración:"],
  ["avec", "with", "con"],
  ["et", "and", "y"],
  ["PC :", "PC:", "PC:"],
  ["📊 Ressources système", "📊 System Resources", "📊 Recursos del sistema"],
  ["Ressources système", "System Resources", "Recursos del sistema"],
  ["Ressources système du serveur", "Server system resources", "Recursos del sistema del servidor"],
  ["Utilisation :", "Usage:", "Uso:"],
  ["Cœurs :", "Cores:", "Núcleos:"],
  ["Fréquence :", "Frequency:", "Frecuencia:"],
  ["Température :", "Temperature:", "Temperatura:"],
  ["Processus principaux :", "Top Processes:", "Procesos principales:"],
  ["💾 Mémoire", "💾 Memory", "💾 Memoria"],
  ["Utilisée :", "Used:", "Usada:"],
  ["Récepteurs SDR & antenne", "SDR Receivers & Antenna", "Receptores SDR y antena"],
  ["Récepteur :", "Receiver:", "Receptor:"],
  ["Antenne :", "Antenna:", "Antena:"],
  ["Github — source originale (SV1BTL) :", "Github — original source (SV1BTL):", "Github — fuente original (SV1BTL):"],
  ["Github — version ORSAT modifiée (F1NSK) :", "Github — modified ORSAT version (F1NSK):", "Github — versión ORSAT modificada (F1NSK):"],
  ["Github — Artemis (base de signaux) :", "Github — Artemis (signal database):", "Github — Artemis (base de señales):"],
  ["Base de données d'identification des signaux Artemis", "Artemis signal identification database", "Base de datos de identificación de señales Artemis"],
  ["Dépôt original de PhantomSDR-Plus par SV1BTL", "Original PhantomSDR-Plus repository by SV1BTL", "Repositorio original de PhantomSDR-Plus de SV1BTL"],
  ["Dépôt de cette version ORSAT modifiée par F1NSK", "Repository of this modified ORSAT version by F1NSK", "Repositorio de esta versión ORSAT modificada por F1NSK"],
  ["💾 Applications desktop", "💾 Desktop applications", "💾 Aplicaciones de escritorio"],
  ["Télécharger PhantomSDR+ Desktop pour Linux et Windows", "Download PhantomSDR+ Desktop for Linux and Windows", "Descargar PhantomSDR+ Desktop para Linux y Windows"],
  ["Remarque :", "Note:", "Nota:"],
  ["Info :", "Info:", "Info:"],
  ["📡 Carte FT8", "📡 FT8 map", "📡 Mapa FT8"],
  ["📡 Carte FT4", "📡 FT4 map", "📡 Mapa FT4"],
  ["📡 Carte JS8", "📡 JS8 map", "📡 Mapa JS8"],
  ["📋 Journal WSPR", "📋 WSPR log", "📋 Registro WSPR"],
  ["🗺️ Carte WSPR", "🗺️ WSPR map", "🗺️ Mapa WSPR"],
  ["Ouvrir la carte des spots FT8 (PSK Reporter)", "Open the FT8 spot map (PSK Reporter)", "Abrir el mapa de spots FT8 (PSK Reporter)"],
  ["Ouvrir la carte des spots FT4 (PSK Reporter)", "Open the FT4 spot map (PSK Reporter)", "Abrir el mapa de spots FT4 (PSK Reporter)"],
  ["Ouvrir la carte des spots JS8 (PSK Reporter)", "Open the JS8 spot map (PSK Reporter)", "Abrir el mapa de spots JS8 (PSK Reporter)"],
  ["Ouvrir le journal WSPR (WSPRnet)", "Open the WSPR log (WSPRnet)", "Abrir el registro WSPR (WSPRnet)"],
  ["Ouvrir la carte WSPR", "Open the WSPR map", "Abrir el mapa WSPR"],
  ["MANUEL DE L'UTILISATEUR", "USER MANUAL", "MANUAL DEL USUARIO"],
  ["Ouvrir le manuel utilisateur en français", "Open the user manual in French", "Abrir el manual de usuario en francés"],
  ["Ouvrir le manuel utilisateur en anglais", "Open the user manual in English", "Abrir el manual de usuario en inglés"],
  ["Ouvrir le manuel utilisateur en espagnol", "Open the user manual in Spanish", "Abrir el manual de usuario en español"],
  ["Impossible de charger le document.", "Unable to load the document.", "No se pudo cargar el documento."],
  ["Ouvrir dans un nouvel onglet", "Open in a new tab", "Abrir en una pestaña nueva"],
  ["Chargement du document…", "Loading document…", "Cargando documento…"],

  // Waterfall
  ["Touchez pour activer l'audio", "Tap to enable audio", "Toque para activar el audio"],
  ["★ ADMIN :", "★ ADMIN:", "★ ADMIN:"],
  ["Masquer les étiquettes utilisateurs", "Hide user labels", "Ocultar etiquetas de usuarios"],
  ["Afficher les étiquettes utilisateurs", "Show user labels", "Mostrar etiquetas de usuarios"],
  ["Molette = Zoom\nShift + Molette = 0,1 kHz\nCtrl + Molette = 0,01 kHz\nShift + Ctrl + Molette = caler sur .00 kHz",
   "Wheel = Zoom\nShift + Wheel = 0.1 KHz\nCtrl + Wheel = 0.01 KHz\nShift + Ctrl + Wheel = snap to .00 KHz",
   "Rueda = Zoom\nMayús + rueda = 0,1 kHz\nCtrl + rueda = 0,01 kHz\nMayús + Ctrl + rueda = ajustar a .00 kHz"],

  // Colonne 1 : audio
  ["Audio & tampon", "Audio & Buffer", "Audio y búfer"],
  ["Cliquer pour couper l'audio", "Click to mute the audio", "Clic para silenciar el audio"],
  ["Réglage du volume Audio", "Audio volume", "Volumen de audio"],
  ["Silencieux Automatique\nRecherchez une fréquence silencieuse\nCliquez pour mesurer le bruit\nCliquez à nouveau pour désactiver",
   "Automatic squelch\nFind a quiet frequency\nClick to measure the noise\nClick again to disable",
   "Silenciador automático\nBusque una frecuencia silenciosa\nHaga clic para medir el ruido\nHaga clic de nuevo para desactivar"],
  ["Réglage du silencieux", "Squelch level", "Nivel del silenciador"],
  ["Augmentez le Buffer si connection Internet lente", "Increase the buffer on a slow Internet connection", "Aumente el búfer si la conexión a Internet es lenta"],
  ["Réglage du Buffer", "Buffer setting", "Ajuste del búfer"],
  ["Tampon", "Buffer", "Búfer"],
  ["Slow (décodeur)", "Slow (decoder)", "Slow (decodificador)"],
  ["Un décodeur est ouvert : l'AGC est maintenu sur Slow pour que le gain reste stable. Votre réglage revient à la fermeture du décodeur.",
   "A decoder is open: the AGC is held on Slow so the gain stays steady for it. Your choice returns when the decoder closes.",
   "Hay un decodificador abierto: el AGC se mantiene en Slow para que la ganancia sea estable. Su ajuste vuelve al cerrar el decodificador."],
  ["Rapide", "Fast", "Rápido"],
  ["Moyen", "Medium", "Medio"],
  ["Lent", "Slow", "Lento"],
  ["Égaliseur", "Equalizer", "Ecualizador"],
  ["Activer l'égaliseur", "Enable Equalizer", "Activar el ecualizador"],
  ["Activer/désactiver l'égaliseur", "Enable/disable the equalizer", "Activar/desactivar el ecualizador"],
  ["Réinitialiser", "Reset", "Restablecer"],
  ["Réinitialiser l'égaliseur", "Reset the equalizer", "Restablecer el ecualizador"],
  ["Compresseur", "Compressor", "Compresor"],
  ["Activer le compresseur", "Enable Compressor", "Activar el compresor"],
  ["Activer/désactiver le compresseur", "Enable/disable the compressor", "Activar/desactivar el compresor"],
  ["Seuil", "Threshold", "Umbral"],
  ["Taux", "Ratio", "Relación"],
  ["Attaque", "Attack", "Ataque"],
  ["Relâchement", "Release", "Liberación"],
  ["Coude", "Knee", "Codo"],
  ["Compensation", "Makeup", "Compensación"],
  ["Gain de compensation (makeup gain)", "Makeup gain", "Ganancia de compensación (makeup)"],
  ["Compensation auto (suit le seuil et le taux)", "Auto makeup (tracks threshold & ratio)", "Compensación auto (sigue umbral y relación)"],
  ["Réinitialiser le compresseur", "Reset the compressor", "Restablecer el compresor"],
  ["Filtres", "Filters", "Filtros"],
  ["Réduction de bruit (NR)", "Noise reduction (NR)", "Reducción de ruido (NR)"],
  ["Suppresseur de bruit impulsionnel (NB)", "Impulse noise blanker (NB)", "Supresor de ruido impulsivo (NB)"],
  ["Suppression du souffle (NS)", "Background noise suppression (NS)", "Supresión de soplido (NS)"],
  ["Anti-notch automatique (AN)", "Automatic notch (AN)", "Notch automático (AN)"],
  ["Dosage de la réduction de bruit NR", "NR noise reduction strength", "Intensidad de la reducción de ruido NR"],
  ["Dosage du filtre NR : vers la gauche plus doux (préserve les signaux faibles), vers la droite plus énergique. 14 dB = réglage d'origine.",
   "NR filter strength: to the left gentler (keeps weak signals), to the right stronger. 14 dB = original setting.",
   "Intensidad del filtro NR: a la izquierda más suave (conserva las señales débiles), a la derecha más enérgico. 14 dB = ajuste original."],
  ["Filtre audio IA", "AI Audio Filter", "Filtro de audio IA"],
  ["Réducteur de bruit neural piloté par I.A - Actif uniquement en SSB et AM/SAM", "AI-driven neural noise reducer - active in SSB and AM/SAM only", "Reductor de ruido neuronal por IA - activo solo en SSB y AM/SAM"],
  ["Dosage du filtre I.A : jusqu'à 50 % réglage doux d'origine ; au-delà, filtre énergique (jusqu'à 40 dB de réduction et silences nettoyés). Réduire si vous n'entendez plus les stations QRP",
   "AI filter strength: up to 50 % the original gentle setting; above, a strong filter (up to 40 dB of reduction, silences cleaned). Turn it down if you can no longer hear QRP stations",
   "Intensidad del filtro IA: hasta el 50 % ajuste suave original; por encima, filtro enérgico (hasta 40 dB de reducción y silencios limpios). Redúzcalo si ya no oye las estaciones QRP"],
  ["Réduction de bruit IA (RNNoise)\nModes phonie uniquement : USB, LSB, AM\nCurseur : part de l'audio débruité, le reste est l'original",
   "AI noise reduction (RNNoise)\nVoice modes only: USB, LSB, AM\nSlider: share of denoised audio, the rest is the original",
   "Reducción de ruido IA (RNNoise)\nSolo modos de voz: USB, LSB, AM\nControl: parte de audio sin ruido, el resto es el original"],
  ["Curseur de force IA", "AI strength slider", "Control de intensidad IA"],
  ["DSP audio", "Audio DSP", "DSP de audio"],
  ["Gate :", "Gate:", "Gate:"],
  ["Activer/désactiver le gate (réducteur de bruit) côté serveur", "Enable/disable the server-side noise gate", "Activar/desactivar el gate (reductor de ruido) del servidor"],
  ["Préréglage :", "Preset:", "Preajuste:"],
  ["Préréglage du gate", "Gate preset", "Preajuste del gate"],
  ["Équilibré", "Balanced", "Equilibrado"],
  ["Agressif", "Aggressive", "Agresivo"],
  ["Signal faible", "Weak Signal", "Señal débil"],
  ["Doux", "Smooth", "Suave"],
  ["Maximum", "Maximum", "Máximo"],
  ["CW/Numérique", "CW/Digital", "CW/Digital"],

  // QRSS
  ["Ouvrir les réglages QRSS. ( Mode de transmission lente)", "Open the QRSS settings (slow transmission mode)", "Abrir los ajustes QRSS (modo de transmisión lenta)"],
  ["🐌 Masquer", "🐌 Hide", "🐌 Ocultar"],
  ["🐌 Afficher", "🐌 Show", "🐌 Mostrar"],
  ["Bande :", "Band:", "Banda:"],
  ["— Fréquence QRSS —", "— QRSS frequency —", "— Frecuencia QRSS —"],
  ["Accorder sur la fréquence QRSS connue", "Tune to the known QRSS frequency", "Sintonizar la frecuencia QRSS conocida"],
  ["Accorder", "Tune", "Sintonizar"],
  ["Vitesse :", "Speed:", "Velocidad:"],
  ["Centre :", "Centre:", "Centro:"],
  ["Largeur :", "Span:", "Ancho:"],
  ["Effacer", "Clear", "Borrar"],
  ["Effacer l'affichage du grabber et démarrer une nouvelle trace", "Clear the grabber display and start a new trace", "Borrar la pantalla del grabber y empezar una nueva traza"],
  ["Gain :", "Gain:", "Ganancia:"],
  ["Couleur :", "Color:", "Color:"],
  ["Arc-en-ciel", "Rainbow", "Arcoíris"],
  ["Vert", "Green", "Verde"],
  ["Bleu", "Blue", "Azul"],
  ["Niveaux de gris", "Grayscale", "Escala de grises"],
  ["💾 Enregistrer en .PNG", "💾 Save as .PNG", "💾 Guardar como .PNG"],
  ["Enregistrer la capture d'écran en PNG, avec la fréquence et l'heure UTC en légende", "Save the capture as PNG, captioned with the frequency and UTC time", "Guardar la captura en PNG, con la frecuencia y la hora UTC como leyenda"],

  // Enregistrement
  ["Options d'enregistrement", "Recording Options", "Opciones de grabación"],
  ["Arrêt audio", "Stop Audio", "Detener audio"],
  ["Vidéo", "Video", "Vídeo"],
  ["Arrêt vidéo", "Stop Video", "Detener vídeo"],
  ["Zone", "Area", "Zona"],
  ["Zone ✓", "Area ✓", "Zona ✓"],
  ["Annuler", "Cancel", "Cancelar"],
  ["Enregistrer uniquement l'audio démodulé (WAV)", "Record the demodulated audio only (WAV)", "Grabar solo el audio demodulado (WAV)"],
  ["Enregistrer le waterfall en même temps que l'audio démodulé", "Record the waterfall together with the demodulated audio", "Grabar la cascada junto con el audio demodulado"],
  ["Tracez une zone sur le waterfall pour n'enregistrer que cette partie. Enregistre le panneau complet si non définie.",
   "Draw an area on the waterfall to record only that part. The whole panel is recorded if none is set.",
   "Trace una zona en la cascada para grabar solo esa parte. Si no se define, se graba el panel completo."],
  ["Télécharger l'audio", "Download Audio", "Descargar audio"],
  ["Télécharger la vidéo", "Download Video", "Descargar vídeo"],
  ["Télécharger l'enregistrement audio", "Download the audio recording", "Descargar la grabación de audio"],
  ["Télécharger l'enregistrement vidéo", "Download the video recording", "Descargar la grabación de vídeo"],
  ["Complet", "Full", "Completo"],
  ["Revenir à l'enregistrement du panneau waterfall complet", "Go back to recording the whole waterfall panel", "Volver a grabar el panel de cascada completo"],
  ["Annuler les enregistrements et la zone sélectionnée, prêt pour un nouveau", "Discard the recordings and the selected area, ready for a new one", "Descartar las grabaciones y la zona seleccionada, listo para una nueva"],
  ["L'enregistrement vidéo n'a pas pu démarrer.\n\nVérifiez que l'audio est démarré et que le waterfall est visible. Votre navigateur ne permet peut-être pas d'enregistrer de la vidéo.",
   "Video recording could not start.\n\nMake sure audio is started and the waterfall is visible. Your browser may not support recording video.",
   "No se pudo iniciar la grabación de vídeo.\n\nCompruebe que el audio está iniciado y la cascada visible. Puede que su navegador no permita grabar vídeo."],

  // Colonne 2 : cadran, accord, popups
  ["Bande actuelle :", "Current Band:", "Banda actual:"],
  ["Survolez un chiffre et faites défiler pour accorder · clic droit pour saisir", "Hover a digit and scroll to tune · right-click to type", "Pase sobre una cifra y gire la rueda para sintonizar · clic derecho para escribir"],
  ["Heure :", "Time:", "Hora:"],
  ["MUET", "MUTED", "SILENCIO"],
  ["Accord fin (kHz)", "Fine Tuning (kHz)", "Sintonía fina (kHz)"],
  ["Basculer entre VFO A et VFO B", "Switch between VFO A and VFO B", "Alternar entre VFO A y VFO B"],
  ["Modes", "Modes", "Modos"],
  ["Mode", "Mode", "Modo"],
  ["Choisir le mode de démodulation", "Choose the demodulation mode", "Elegir el modo de demodulación"],
  ["Bandes", "Bands", "Bandas"],
  ["Bande", "Band", "Banda"],
  ["Choisir la bande", "Choose the band", "Elegir la banda"],
  ["Filtres FI", "IF Filters", "Filtros FI"],
  ["FI", "IF", "FI"],
  ["Choisir le filtre FI (largeur de bande)", "Choose the IF filter (bandwidth)", "Elegir el filtro FI (ancho de banda)"],
  ["Filtres FI fixes", "Static IF Filters", "Filtros FI fijos"],
  ["Largeur de bande (centre → bord)", "Bandwidth (center → edge)", "Ancho de banda (centro → borde)"],
  ["Ajuster la largeur de bande depuis le centre vers la bande latérale active", "Adjust the bandwidth from the centre toward the active sideband", "Ajustar el ancho de banda del centro hacia la banda lateral activa"],
  ["Réinitialiser la bande passante par défaut du mode", "Reset to the mode's default passband", "Restablecer la banda de paso por defecto del modo"],
  ["Contrôle CAT via TCI", "CAT control via TCI", "Control CAT vía TCI"],
  ["Contrôle CAT via TCI (ExpertSDR, AetherSDR, Thetis)", "CAT control via TCI (ExpertSDR, AetherSDR, Thetis)", "Control CAT vía TCI (ExpertSDR, AetherSDR, Thetis)"],
  ["ExpertSDR, AetherSDR, Thetis — les ports TCI 50001 / 40001 sont recherchés automatiquement.",
   "ExpertSDR, AetherSDR, Thetis — TCI ports 50001 / 40001 are searched automatically.",
   "ExpertSDR, AetherSDR, Thetis — los puertos TCI 50001 / 40001 se buscan automáticamente."],
  ["Inactif", "Inactive", "Inactivo"],
  ["⏳ Patientez", "⏳ Wait", "⏳ Espere"],
  ["Synchro CAT", "CAT Sync", "Sincronización CAT"],
  ["Hôte :", "Host:", "Host:"],
  ["Active ou désactive la synchro en fréquence/mode/filtre (rig <-> PhantomSDR). L'audio est systématiquement coupée quand vous passez en TX.",
   "Turns frequency/mode/filter sync (rig <-> PhantomSDR) on or off. The audio is always muted while you transmit.",
   "Activa o desactiva la sincronización de frecuencia/modo/filtro (equipo <-> PhantomSDR). El audio se silencia siempre al pasar a TX."],
  ["Adresse du serveur TCI. Sur un seul PC entrez : localhost. Sur 2 PC distincts entrez l'adresse du PC qui gère le transceiver. Exemple : 192.168.1.xx",
   "TCI server address. On a single PC enter: localhost. On two PCs enter the address of the PC that runs the transceiver. Example: 192.168.1.xx",
   "Dirección del servidor TCI. En un solo PC escriba: localhost. En dos PC escriba la dirección del PC que gestiona el transceptor. Ejemplo: 192.168.1.xx"],
  ["Aucune liaison CAT détectée (recherche TCI sur les ports 50001/40001)", "No CAT link detected (searching TCI on ports 50001/40001)", "No se detecta enlace CAT (buscando TCI en los puertos 50001/40001)"],
  ["Recherche d'un serveur TCI...", "Searching for a TCI server...", "Buscando un servidor TCI..."],

  // Scanner
  ["Scanner", "Scanner", "Escáner"],
  ["Scanner de canaux", "Channel scanner", "Escáner de canales"],
  ["Stopper le Balayage", "Stop scanning", "Detener el barrido"],
  ["Exclure une fréquence du balayage (Porteuse ou parasite)", "Exclude a frequency from the scan (carrier or interference)", "Excluir una frecuencia del barrido (portadora o interferencia)"],
  ["Seuil du scanner — le balayage s'arrête sur le premier canal dépassant le bruit de fond de cette valeur",
   "Scanner threshold — the scan stops on the first channel that rises this far above the noise floor",
   "Umbral del escáner — el barrido se detiene en el primer canal que supera el ruido de fondo en este valor"],
  ["Plage", "Range", "Rango"],
  ["Balayage", "Scan", "Barrido"],
  ["Arrêt à (dB au-dessus du bruit)", "Stop at (dB over noise)", "Parar en (dB sobre el ruido)"],
  ["Reprise après", "Resume after", "Reanudar tras"],
  ["Séjour max", "Max stay", "Estancia máx."],
  ["Bande entière", "Scan Band", "Barrer la banda"],
  ["Partie visible", "Scan Visible", "Barrer lo visible"],
  ["Balayer la bande où démarre le scan, d'après le plan de bandes", "Sweep the band the scan starts in, from the band plan", "Barrer la banda en la que empieza el escaneo, según el plan de bandas"],
  ["Balayer exactement ce qu'affiche le waterfall — zoomez ou faites-le glisser et le scan suit", "Sweep exactly what the waterfall is showing — zoom or drag it and the scan follows", "Barrer exactamente lo que muestra la cascada — haga zoom o arrástrela y el escaneo la sigue"],
  ["Chaque canal", "Every channel", "Cada canal"],
  ["Sauter les vides", "Skip empty", "Saltar vacíos"],
  ["Le scan classique : chaque canal est accordé et écouté, on le voit et l'entend parcourir la bande", "The classic scan: every channel is tuned and listened to, so you see and hear it cross the band", "El escaneo clásico: cada canal se sintoniza y escucha, se ve y se oye recorrer la banda"],
  ["Les canaux que le spectre place sous le seuil sont sautés sans être accordés — bien plus rapide, mais le scan saute de signal en signal", "Channels the spectrum places below the threshold are skipped without tuning — much faster, but the scan jumps signal to signal", "Los canales que el espectro sitúa bajo el umbral se saltan sin sintonizarlos — mucho más rápido, pero el escaneo salta de señal en señal"],
  ["Maintien", "Hold", "Mantener"],
  ["Rester sur le canal jusqu'à l'appui sur une flèche", "Stay on the channel until an arrow is pressed", "Quedarse en el canal hasta pulsar una flecha"],
  ["Rester tant que le signal dure — une porteuse permanente bloquera le balayage", "Stay as long as the signal lasts — a permanent carrier will block the scan", "Quedarse mientras dure la señal — una portadora permanente bloqueará el barrido"],
  ["Effacer les verrouillages du scanner", "Clear the scanner locks", "Borrar los bloqueos del escáner"],
  ["haut", "up", "arriba"],
  ["bas", "down", "abajo"],

  // Décodeurs : commun
  ["Contrôle des décodeurs", "Decoders Control", "Control de decodificadores"],
  ["Options des décodeurs", "Decoder Options", "Opciones de decodificador"],
  ["Décodeur :", "Decoder:", "Decodificador:"],
  ["Activer/désactiver le décodeur", "Enable/disable the decoder", "Activar/desactivar el decodificador"],
  ["— Choisir un décodeur —", "— Select decoder —", "— Elegir decodificador —"],
  ["HFDL — HF Data Link : messages ACARS des avions sur ondes courtes", "HFDL — HF Data Link: aircraft ACARS messages on shortwave", "HFDL — HF Data Link: mensajes ACARS de aviones en onda corta"],
  ["modes fldigi : RTTY / SITOR / PSK31 / Olivia / MFSK / DominoEX / THOR / THROB / Hellschreiber / MT63 / Packet / APRS",
   "fldigi modes: RTTY / SITOR / PSK31 / Olivia / MFSK / DominoEX / THOR / THROB / Hellschreiber / MT63 / Packet / APRS",
   "modos fldigi: RTTY / SITOR / PSK31 / Olivia / MFSK / DominoEX / THOR / THROB / Hellschreiber / MT63 / Packet / APRS"],
  ["decoder has taken control of mode and IF while active.", "decoder has taken control of mode and IF while active.", ""],
  ["Messages", "Messages", "Mensajes"],
  ["Message", "Message", "Mensaje"],
  ["Locator", "Locator", "Localizador"],
  ["Décalage de synchro", "Sync offset", "Desfase de sincronización"],
  ["Avance de capture après le début du créneau UTC, pour compenser la latence du pipeline audio (KiwiSDR time_shift)",
   "Capture lead-in after the start of the UTC slot, to make up for the audio pipeline latency (KiwiSDR time_shift)",
   "Retardo de captura tras el inicio del intervalo UTC, para compensar la latencia del audio (KiwiSDR time_shift)"],
  ["Avance de capture après le début du créneau UTC, pour compenser la latence du pipeline audio",
   "Capture lead-in after the start of the UTC slot, to make up for the audio pipeline latency",
   "Retardo de captura tras el inicio del intervalo UTC, para compensar la latencia del audio"],
  ["Ajuster automatiquement le timing de capture à partir de la mesure DT du décodeur", "Adjust the capture timing automatically from the decoder's DT measurement", "Ajustar automáticamente el tiempo de captura a partir de la medida DT del decodificador"],
  ["Vitesse", "Speed", "Velocidad"],
  ["Vitesse JS8. Toutes les stations d'un QSO doivent utiliser la même ; Normal est la vitesse d'appel courante.",
   "JS8 speed. Every station in a QSO must use the same one; Normal is the usual calling speed.",
   "Velocidad JS8. Todas las estaciones de un QSO deben usar la misma; Normal es la velocidad de llamada habitual."],
  ["Effacer les messages JS8", "Clear the JS8 messages", "Borrar los mensajes JS8"],
  ["Progression du créneau JS8", "JS8 slot progress", "Progreso del intervalo JS8"],
  ["À l'écoute du cycle", "Listening on the", "Escuchando el ciclo"],
  ["en cours…", "cycle…", "en curso…"],
  ["Délai dépassé avant l'arrivée de la dernière trame", "Timed out before the last frame arrived", "Tiempo agotado antes de llegar la última trama"],
  ["balayage…", "scanning…", "buscando…"],
  ["Effacer les messages CW", "Clear the CW messages", "Borrar los mensajes CW"],
  ["🔓 Verrouiller la tonalité", "🔓 Lock tone", "🔓 Bloquear tono"],
  ["🔒 Tonalité verrouillée", "🔒 Tone locked", "🔒 Tono bloqueado"],
  ["Verrouiller la tonalité sur la station décodée (ignore les autres signaux du filtre)", "Lock the tone on the decoded station (ignores other signals in the filter)", "Bloquear el tono en la estación decodificada (ignora las otras señales del filtro)"],
  ["Déverrouiller la tonalité (le décodeur reprend la recherche dans tout le filtre)", "Unlock the tone (the decoder searches the whole filter again)", "Desbloquear el tono (el decodificador vuelve a buscar en todo el filtro)"],
  ["À l'écoute d'un signal CW…", "Listening for CW signal…", "Escuchando señal CW…"],
  ["Progression du créneau WSPR", "WSPR slot progress", "Progreso del intervalo WSPR"],
  ["Effacer les messages WSPR", "Clear the WSPR messages", "Borrar los mensajes WSPR"],
  ["UTC Indicatif", "UTC Callsign", "UTC Indicativo"],
  ["Carré", "Grid", "Cuadrícula"],
  ["Puissance", "Power", "Potencia"],
  ["Fréq.", "Freq", "Frec."],
  ["En attente du prochain créneau UTC de minute paire…", "Waiting for next even UTC minute slot…", "Esperando el próximo intervalo UTC de minuto par…"],

  // FAX
  ["Récepteur HF FAX / WEFAX", "HF FAX / WEFAX Receiver", "Receptor HF FAX / WEFAX"],
  ["[PHASAGE]", "[PHASING]", "[FASE]"],
  ["Lignes :", "Lines:", "Líneas:"],
  ["Station", "Station", "Estación"],
  ["— Choisir une station —", "— Select station —", "— Elegir estación —"],
  ["Fréquence", "Frequency", "Frecuencia"],
  ["▶ Accorder", "▶ Tune", "▶ Sintonizar"],
  ["Accorder sur cette station", "Tune to this station", "Sintonizar esta estación"],
  ["Prochaines émissions · UTC", "Next Transmissions · UTC", "Próximas emisiones · UTC"],
  ["Prochaines diffusions · UTC", "Next Broadcasts · UTC", "Próximas difusiones · UTC"],
  ["Émission en cours", "On air", "En el aire"],
  ["Émission imminente", "Transmission imminent", "Emisión inminente"],
  ["Armer le décodeur maintenant", "Arm the decoder now", "Armar el decodificador ahora"],
  ["Écart", "Shift", "Desplazamiento"],
  ["⇔ Alignement auto", "⇔ Auto-align", "⇔ Alineación auto"],
  ["Alignement automatique des lignes sur les impulsions de synchro", "Align the lines automatically on the sync pulses", "Alinear las líneas automáticamente con los pulsos de sincronía"],
  ["⇅ Inverser", "⇅ Invert", "⇅ Invertir"],
  ["Inverser le noir et blanc (pour réception LSB ou polarité inversée)", "Swap black and white (for LSB reception or reversed polarity)", "Invertir blanco y negro (para recepción LSB o polaridad invertida)"],
  ["Noir :", "Black:", "Negro:"],
  ["Blanc :", "White:", "Blanco:"],
  ["px/ligne", "px/line", "px/línea"],
  ["ms/ligne", "ms/line", "ms/línea"],
  ["Image HF FAX — tournée de 180°, les lignes récentes se construisent de bas en haut", "HF FAX image — rotated 180°, newest lines build from bottom to top", "Imagen HF FAX — girada 180°, las líneas nuevas se construyen de abajo arriba"],
  ["phasage 300 Hz", "300 Hz phasing", "fase 300 Hz"],
  ["arrêt 450 Hz", "450 Hz stop", "parada 450 Hz"],
  ["↺ Réinit.", "↺ Reset", "↺ Reiniciar"],
  ["Effacer l'image et réinitialiser le décodeur — à utiliser entre deux transmissions", "Clear the image and reset the decoder — use it between transmissions", "Borrar la imagen y reiniciar el decodificador — úselo entre transmisiones"],
  ["⤓ Enregistrer PNG", "⤓ Save PNG", "⤓ Guardar PNG"],
  ["Enregistrer l'image actuelle en PNG", "Save the current image as PNG", "Guardar la imagen actual en PNG"],
  ["Le mode doit être", "Mode must be", "El modo debe ser"],
  ["· Standard : noir 1500 Hz · blanc 2300 Hz · 120 LPM · IOC 576 · L'image défile vers le haut — lignes récentes en bas · Utilisez",
   "· Standard: 1500 Hz black · 2300 Hz white · 120 LPM · IOC 576 · Image scrolls upward — newest lines at bottom · Use",
   "· Estándar: negro 1500 Hz · blanco 2300 Hz · 120 LPM · IOC 576 · La imagen se desplaza hacia arriba — líneas nuevas abajo · Use"],
  ["↺ Actualiser", "↺ Refresh", "↺ Actualizar"],
  ["entre deux transmissions ou quand l'image se déchire -", "between transmissions or when image tears -", "entre transmisiones o cuando la imagen se rasga -"],
  ["Horaires des émissions FAX", "FAX transmission schedules", "Horarios de emisiones FAX"],

  // SSTV
  ["maintien de synchro souple", "soft sync hold", "sincronía suave"],
  ["verrouillage synchro franc", "hard sync lock", "sincronía firme"],
  ["▶ Démarrer", "▶ Start", "▶ Iniciar"],
  ["■ Arrêter", "■ Stop", "■ Detener"],
  ["⏺ Forcer", "⏺ Force", "⏺ Forzar"],
  ["💾 Enregistrer", "💾 Save", "💾 Guardar"],
  ["Démarrer la réception SSTV", "Start SSTV reception", "Iniciar la recepción SSTV"],
  ["Arrêter la réception SSTV", "Stop SSTV reception", "Detener la recepción SSTV"],
  ["Réinitialiser l'image SSTV", "Reset the SSTV image", "Reiniciar la imagen SSTV"],
  ["Enregistrer l'image SSTV", "Save the SSTV image", "Guardar la imagen SSTV"],
  ["Démarrer le décodage immédiatement dans le mode sélectionné, sans attendre l'en-tête VIS ni la détection de synchro. Choisissez un mode autre qu'Auto pour activer.",
   "Start decoding at once in the selected mode, without waiting for the VIS header or sync detection. Pick a mode other than Auto to enable it.",
   "Iniciar la decodificación de inmediato en el modo elegido, sin esperar la cabecera VIS ni la detección de sincronía. Elija un modo distinto de Auto para activarlo."],
  ["Desktop + mobile · PCM brut avant AGC/NR/mute", "Desktop + mobile · raw PCM before AGC/NR/mute", "Escritorio + móvil · PCM bruto antes de AGC/NR/mute"],
  ["En marche", "Running", "En marcha"],
  ["Arrêté", "Stopped", "Detenido"],
  ["En attente du verrouillage VIS / AUTO", "Waiting for VIS / AUTO lock", "Esperando enganche VIS / AUTO"],
  ["SSTV arrêté", "SSTV stopped", "SSTV detenido"],
  ["Réinitialisation du décodeur SSTV", "Resetting SSTV decoder", "Reiniciando el decodificador SSTV"],

  // NAVTEX
  ["Récepteur NAVTEX", "NAVTEX Receiver", "Receptor NAVTEX"],
  ["en attente du phasage…", "waiting for phasing…", "esperando la fase…"],
  ["Effacer les messages NAVTEX", "Clear the NAVTEX messages", "Borrar los mensajes NAVTEX"],
  ["⇒ Accorder & régler la FI", "⇒ Tune & Set IF", "⇒ Sintonizar y ajustar FI"],
  ["Accorder sur la station NAVTEX sélectionnée et régler le filtre FI", "Tune to the selected NAVTEX station and set the IF filter", "Sintonizar la estación NAVTEX elegida y ajustar el filtro FI"],
  ["À l'écoute d'un signal NAVTEX…", "Listening for NAVTEX signal…", "Escuchando señal NAVTEX…"],
  ["Réglez le mode sur", "Set mode to", "Ponga el modo en"],
  ["et utilisez", "and use", "y use"],
  ["pour l'accord automatique.", "to auto-tune.", "para la sintonía automática."],
  ["· FSK 100 bauds · shift 170 Hz · FEC SITOR-B · Cadran réglé 500 Hz sous le canal (centre du signal à 500 Hz audio) ·",
   "· 100 Baud FSK · 170 Hz shift · SITOR-B FEC · Dial set 500 Hz below channel (signal centre at 500 Hz audio) ·",
   "· FSK 100 baudios · desplazamiento 170 Hz · FEC SITOR-B · Dial 500 Hz por debajo del canal (centro de la señal a 500 Hz de audio) ·"],
  ["Carte des stations NAVTEX", "NAVTEX Maps Stations", "Mapa de estaciones NAVTEX"],
  ["Enregistrer le texte", "Save Text", "Guardar texto"],
  ["Enregistrer l'image", "Save Picture", "Guardar imagen"],
  ["Enregistrer le texte NAVTEX", "Save the NAVTEX text", "Guardar el texto NAVTEX"],

  // RADE
  ["Connexion au sidecar…", "Connecting to sidecar…", "Conectando con el sidecar…"],
  ["Synchronisé", "Synced", "Sincronizado"],
  ["Recherche du signal…", "Searching for signal…", "Buscando señal…"],
  ["Pas de sidecar", "No Sidecar", "Sin sidecar"],
  ["Synchro trame", "Frame Sync", "Sincronía de trama"],
  ["Acquisition…", "Acquiring…", "Adquiriendo…"],
  ["BP 1500 Hz · vocodeur FARGAN", "1500 Hz BW · FARGAN vocoder", "AB 1500 Hz · vocoder FARGAN"],
  ["⚠ Sidecar injoignable.", "⚠ Sidecar not reachable.", "⚠ Sidecar inaccesible."],
  ["Lancez-le sur le serveur :", "Start it on the server:", "Inícielo en el servidor:"],
  ["(recherché", "(looked for it", "(buscado"],
  ["FreeDV RADE v1 · décodé côté serveur par", "FreeDV RADE v1 · decoded server-side by", "FreeDV RADE v1 · decodificado en el servidor por"],
  ["LSB — à utiliser sur 40 m / 80 m / 160 m.", "LSB — use on 40 m / 80 m / 160 m.", "LSB — para 40 m / 80 m / 160 m."],
  ["USB — à utiliser sur 20 m / 17 m / 15 m / 10 m.", "USB — use on 20 m / 17 m / 15 m / 10 m.", "USB — para 20 m / 17 m / 15 m / 10 m."],
  ["Voir", "See", "Véase"],
  ["Afficher/masquer le FreeDV Reporter", "Show/hide the FreeDV Reporter", "Mostrar/ocultar el FreeDV Reporter"],
  ["▲ Masquer le Reporter", "▲ Hide Reporter", "▲ Ocultar el Reporter"],
  ["↗ ouvrir dans un onglet", "↗ open in tab", "↗ abrir en pestaña"],
  ["En direct ·", "Live ·", "En directo ·"],

  // FSK / fldigi / Packet
  ["en attente de verrouillage…", "waiting for lock…", "esperando enganche…"],
  ["Effacer les messages FSK", "Clear the FSK messages", "Borrar los mensajes FSK"],
  ["Variante", "Variant", "Variante"],
  ["FSK maritime / SITOR", "Maritime FSK / SITOR", "FSK marítimo / SITOR"],
  ["RTTY météo", "Weather RTTY", "RTTY meteorológico"],
  ["RTTY amateur", "Amateur RTTY", "RTTY de aficionado"],
  ["Fréquence connue", "Known frequency", "Frecuencia conocida"],
  ["— Choisir une fréquence —", "— Select frequency —", "— Elegir frecuencia —"],
  ["Accorder sur la fréquence FSK connue", "Tune to the known FSK frequency", "Sintonizar la frecuencia FSK conocida"],
  ["Centre audio (Hz)", "Center audio (Hz)", "Centro de audio (Hz)"],
  ["Écart (Hz)", "Shift (Hz)", "Desplazamiento (Hz)"],
  ["Encodage", "Encoding", "Codificación"],
  ["Trame", "Framing", "Trama"],
  ["Inverser mark / space", "Invert mark / space", "Invertir mark / space"],
  ["Détection auto de l'écart", "Auto shift detect", "Detección auto del desplazamiento"],
  ["Afficher le paquet brut", "Show raw packet", "Mostrar paquete bruto"],
  ["Squelch (S/B FEC)", "Squelch (FEC S/N)", "Squelch (S/R FEC)"],
  ["Squelch (S/B)", "Squelch (SNR)", "Squelch (S/R)"],
  ["Squelch (métrique FEC)", "Squelch (FEC metric)", "Squelch (métrica FEC)"],
  ["Squelch (ton / bruit)", "Squelch (tone / noise)", "Squelch (tono / ruido)"],
  ["Squelch (S/B)", "Squelch (S/N)", "Squelch (S/R)"],
  ["Sous 3,5 le bruit commence à s'imprimer ; un bon signal donne 8–9 au compteur FEC.", "Below 3.5 noise starts printing; a good signal reads 8–9 on the FEC meter.", "Por debajo de 3,5 el ruido empieza a imprimirse; una buena señal da 8–9 en el medidor FEC."],
  ["Le bruit donne −12 à −15 dB ; le RTTY reste lisible jusque vers −4 dB. Tout à gauche le désactive.", "Noise reads −12 to −15 dB; RTTY stays readable down to about −4 dB. Far left turns it off.", "El ruido da −12 a −15 dB; el RTTY sigue legible hasta unos −4 dB. Todo a la izquierda lo desactiva."],
  ["Le bruit seul atteint environ 20 ; une copie propre dépasse 23 au compteur FEC.", "Noise alone reaches about 20; clean copy reads above 23 on the FEC meter.", "El ruido solo alcanza unos 20; una copia limpia supera 23 en el medidor FEC."],
  ["Le bruit seul reste sous 20 ; une copie lisible donne 35 et plus.", "Noise alone stays under 20; readable copy reads 35 and up.", "El ruido solo queda por debajo de 20; una copia legible da 35 o más."],
  ["Le bruit seul reste sous 1 dB ; un signal copiable donne 10 dB et plus.", "Noise alone stays under 1 dB; a copyable signal reads 10 dB and up.", "El ruido solo queda por debajo de 1 dB; una señal copiable da 10 dB o más."],
  ["Le bruit seul donne environ 3 ; un signal verrouillé 4,5 et plus.", "Noise alone reads about 3; a locked signal 4.5 and up.", "El ruido solo da unos 3; una señal enganchada 4,5 o más."],
  ["Inverser (échanger les tons encre et papier)", "Reverse (swap ink and paper tones)", "Invertir (intercambiar tonos de tinta y papel)"],
  ["⇒ Régler le passe-bande FI", "⇒ Set IF Band-Pass", "⇒ Ajustar pasabanda FI"],
  ["Régler le filtre passe-bande FI pour ce mode FSK", "Set the IF band-pass filter for this FSK mode", "Ajustar el filtro pasabanda FI para este modo FSK"],
  ["⟳ Centrage auto", "⟳ Auto-tune Center", "⟳ Centrado auto"],
  ["Centrage auto en cours…", "Auto-tune scanning…", "Centrado auto en curso…"],
  ["Tons :", "Tones:", "Tonos:"],
  ["Trames :", "Frames:", "Tramas:"],
  ["Stations :", "Stations:", "Estaciones:"],
  ["Audio :", "Audio:", "Audio:"],
  ["Porteuse :", "Carrier:", "Portadora:"],
  ["Mode :", "Mode:", "Modo:"],
  ["Verrou", "Lock", "Enganche"],
  ["Qualité", "Quality", "Calidad"],
  ["Synchro", "Sync", "Sincronía"],
  ["SYNCHRO", "SYNCED", "SINCRO"],
  ["VERROUILLÉ", "LOCKED", "ENGANCHADO"],
  ["RECHERCHE", "SEARCH", "BÚSQUEDA"],
  ["Silencieux fermé", "Squelch closed", "Silenciador cerrado"],
  ["Choisissez un point d'eau ci-dessus, puis utilisez le centrage auto ou réglez la porteuse à la main — le décodeur rattrape lui-même les derniers ±25 Hz.",
   "Pick a watering hole above, then use Auto-tune Center or set the carrier by hand — the decoder pulls in the last ±25 Hz on its own.",
   "Elija un punto de encuentro arriba y use el centrado auto o ajuste la portadora a mano — el decodificador corrige solo los últimos ±25 Hz."],
  ["Choisissez un canal ci-dessus (ou accordez-en un vous-même) — seules les trames qui passent leur somme de contrôle sont affichées, donc un panneau muet signifie un canal muet.",
   "Pick a channel above (or tune one yourself) — every frame that passes its checksum is printed, nothing else, so a quiet pane means a quiet channel.",
   "Elija un canal arriba (o sintonice uno usted mismo) — solo se muestran las tramas que pasan su suma de control, así que un panel callado es un canal callado."],
  ["Placez le bloc de tons sur la fréquence centrale (ou utilisez le centrage auto) ; le décodeur rattrape le dernier quart de ton. Le mode doit correspondre : MFSK16, 32 et 64 ne diffèrent que par la vitesse.",
   "Put the tone block on the centre frequency (or use Auto-tune Center); the decoder pulls in the last quarter of a tone. The Mode must match: MFSK16, 32 and 64 differ only in speed.",
   "Coloque el bloque de tonos en la frecuencia central (o use el centrado auto); el decodificador corrige el último cuarto de tono. El modo debe coincidir: MFSK16, 32 y 64 solo difieren en velocidad."],
  ["Placez le bloc de tons sur la fréquence centrale (ou utilisez le centrage auto). La manipulation incrémentale tolère quelques hertz d'erreur, mais le mode doit correspondre à la vitesse émise.",
   "Put the tone block on the centre frequency (or use Auto-tune Center). Incremental keying makes it forgiving of a few hertz of error, but the Mode must match the speed being sent.",
   "Coloque el bloque de tonos en la frecuencia central (o use el centrado auto). La manipulación incremental tolera unos hercios de error, pero el modo debe coincidir con la velocidad emitida."],
  ["THROB doit être accordé à ±3 Hz près (±6 Hz pour THROB 4) : utilisez le centrage auto, puis laissez l'AFC se stabiliser. Le mode doit correspondre exactement.",
   "THROB must be tuned within ±3 Hz (±6 Hz for THROB 4): use Auto-tune Center, then let the AFC settle. The Mode must match exactly.",
   "THROB debe sintonizarse a ±3 Hz (±6 Hz para THROB 4): use el centrado auto y deje que el AFC se estabilice. El modo debe coincidir exactamente."],
  ["Placez le signal sur la fréquence centrale (MT63 émet sa porteuse la plus basse à 500 Hz, le centre vaut donc 500 Hz plus la moitié de la largeur) ; le décodeur trouve seul les 8 dernières porteuses. Le texte est en retard sur le signal à cause de l'entrelaceur.",
   "Put the signal on the centre frequency (MT63 sends its lowest carrier at 500 Hz, so the centre is 500 Hz plus half the bandwidth); the decoder finds the last 8 carriers by itself. Text lags the signal by the interleaver.",
   "Coloque la señal en la frecuencia central (MT63 emite su portadora más baja a 500 Hz, así que el centro es 500 Hz más la mitad del ancho); el decodificador encuentra solo las últimas 8 portadoras. El texto va con retraso por el entrelazador."],
  ["Olivia n'émet pas de préambule, la synchro est donc recherchée : comptez quelques secondes avant que le texte apparaisse. Le mode doit correspondre exactement à l'émission.",
   "Olivia sends no preamble, so sync is searched for: allow a few seconds before text appears. The Mode setting must match the transmission exactly.",
   "Olivia no envía preámbulo, así que la sincronía se busca: cuente unos segundos antes de que aparezca texto. El modo debe coincidir exactamente con la emisión."],
  ["Utilisez la liste des fréquences connues, puis affinez l'accord jusqu'à ce que le texte se stabilise.", "Use the known frequency list, then fine-tune until the text becomes stable.", "Use la lista de frecuencias conocidas y afine la sintonía hasta que el texto se estabilice."],
  ["Placez le signal sur la fréquence centrale (ou utilisez le centrage auto). Chaque lettre est peinte deux fois, l'une au-dessus de l'autre ; une petite erreur de vitesse incline le texte, et une copie est toujours entière.",
   "Put the signal on the centre frequency (or use Auto-tune Center). Each letter is painted twice, one copy above the other; a small speed error slants the text, and one copy is always whole.",
   "Coloque la señal en la frecuencia central (o use el centrado auto). Cada letra se pinta dos veces, una encima de otra; un pequeño error de velocidad inclina el texto y una copia siempre está entera."],
  ["Mode : USB. Accordez pour que la porteuse tombe sur la valeur Centre audio,", "Mode: USB. Tune so the carrier sits on the Center audio value,", "Modo: USB. Sintonice para que la portadora quede en el valor Centro de audio,"],
  ["et attendez un IMD meilleur que −20 dB d'un émetteur propre", "and expect IMD better than −20 dB from a clean transmitter", "y espere un IMD mejor que −20 dB de un transmisor limpio"],
  ["FM, accordé sur le canal", "FM, tuned on the channel", "FM, sintonizado en el canal"],
  ["USB, tons 1600 / 1800 Hz au cadran", "USB, tones 1600 / 1800 Hz at the dial", "USB, tonos 1600 / 1800 Hz en el dial"],
  [". Une lampe DCD sans trames signifie des signaux trop faibles ou trop déformés pour passer la somme de contrôle", ". A DCD lamp with no frames means signals too weak or too distorted to pass the checksum", ". Un indicador DCD sin tramas indica señales demasiado débiles o distorsionadas para pasar la suma de control"],
  ["Mode : USB.", "Mode: USB.", "Modo: USB."],
  ["Hz de large.", "Hz wide.", "Hz de ancho."],
  ["Le texte est en retard de quelques secondes sur le signal (entrelaceur + FEC),", "Text lags the signal by a couple of seconds (interleaver + FEC),", "El texto va unos segundos por detrás de la señal (entrelazador + FEC),"],
  ["et quelques caractères parasites au début d'une émission sont normaux.", "and a few stray characters at the start of a transmission are normal.", "y unos caracteres sueltos al inicio de una emisión son normales."],
  ["Pas de FEC : un mauvais ton coûte un caractère, un craquement donne donc une coquille,", "No FEC: a bad tone costs one character, so a static crash shows as a typo,", "Sin FEC: un tono erróneo cuesta un carácter, así que un chasquido aparece como errata,"],
  ["et le squelch masque le bruit entre les passages.", "and the squelch hides the noise between overs.", "y el squelch oculta el ruido entre pasadas."],
  ["Un caractère par impulsion : lent, mais il passe à travers un fort fading,", "One character per pulse: slow, but it copies through heavy fading,", "Un carácter por pulso: lento, pero pasa a través de un fuerte desvanecimiento,"],
  ["à condition d'être accordé à quelques hertz près.", "provided it is tuned within a few hertz.", "siempre que esté sintonizado a pocos hercios."],
  ["Il n'y a rien à décoder : lisez les lettres sur l'image,", "There is nothing to decode: read the letters off the picture,", "No hay nada que decodificar: lea las letras en la imagen,"],
  ["c'est pourquoi le Hell reste lisible quand aucun mode texte ne l'est.", "which is why Hell stays readable when no text mode is.", "por eso el Hell sigue legible cuando ningún modo de texto lo es."],
  ["Le texte est en retard sur le signal à cause de l'entrelaceur (secondes),", "Text lags the signal by the interleaver (seconds),", "El texto va con retraso por el entrelazador (segundos),"],
  ["et le squelch masque le moment où le synchroniseur se stabilise.", "and the squelch hides the moment the synchroniser needs to settle.", "y el squelch oculta el momento en que el sincronizador se estabiliza."],
  ["Mode : USB. Choisissez les bons tons / la bonne largeur — un mauvais mode ne décode rien du tout,", "Mode: USB. Pick the right tones / bandwidth — a wrong Mode decodes nothing at all,", "Modo: USB. Elija los tonos / el ancho correctos — un modo erróneo no decodifica nada,"],
  ["et la FEC a quelques blocs de retard, le texte arrive donc par rafales", "and the FEC lags a few blocks, so text arrives in bursts", "y la FEC lleva unos bloques de retraso, así que el texto llega a ráfagas"],
  ["Mode : USB. Cochez « Inverser mark / space » pour le RTTY (météo),", "Mode: USB. Please check \"Invert mark / space\" for RTTY (weather),", "Modo: USB. Marque «Invertir mark / space» para el RTTY (meteo),"],
  ["mais laissez-le décoché pour le FSK maritime et le RTTY amateur", "but leave it unchecked for maritime FSK and HAM RTTY", "pero déjelo sin marcar para el FSK marítimo y el RTTY de aficionado"],
  ["Carte APRS", "APRS map", "Mapa APRS"],
  ["Cadrage auto", "Auto fit", "Encuadre auto"],
  ["Tout afficher", "Fit all", "Ver todo"],
  ["Afficher la carte", "Show the map", "Mostrar el mapa"],
  ["Réduire la carte", "Minimize the map", "Minimizar el mapa"],
  ["Restaurer la carte", "Restore map", "Restaurar el mapa"],
  ["Réduire la carte ", "Minimize map", "Minimizar el mapa"],
  ["Recadrer la carte à l'arrivée et au déplacement des stations. Un déplacement ou un zoom manuel le désactive.", "Reframe the map as stations arrive and move. Panning or zooming by hand turns it off.", "Reencuadrar el mapa cuando llegan o se mueven estaciones. Mover o hacer zoom a mano lo desactiva."],
  ["Afficher sur la carte", "Show on the map", "Mostrar en el mapa"],
  ["Cliquez sur une station pour ses détails, ou sur une ligne décodée ci-dessus pour la trouver sur la carte. L'ambre est ce récepteur.", "Click a station for details, or a decoded line above to find it on the map. Amber is this receiver.", "Haga clic en una estación para ver detalles, o en una línea decodificada arriba para encontrarla en el mapa. El ámbar es este receptor."],
  ["La carte n'a pas pu être chargée.", "The map could not be loaded.", "No se pudo cargar el mapa."],

  // Colonne 3 : waterfall
  ["Commandes du waterfall", "Waterfall Controls", "Controles de la cascada"],
  ["Réglage auto", "Auto Adj.", "Ajuste auto"],
  ["Réglage automatique", "Automatic adjustment", "Ajuste automático"],
  ["Min :", "Min:", "Mín:"],
  ["Max :", "Max:", "Máx:"],
  ["Curseur de luminosité", "Brightness", "Brillo"],
  ["Réglage du contraste", "Contrast", "Contraste"],
  ["Active le zoom manuel par pas", "Enables step-by-step manual zoom", "Activa el zoom manual por pasos"],
  ["Réglage du zoom", "Zoom level", "Nivel de zoom"],
  ["Vers la bande", "To Band", "A la banda"],
  ["Zoomer le waterfall sur la bande de la fréquence accordée", "Zoom the waterfall to the band of the tuned frequency", "Ajustar la cascada a la banda de la frecuencia sintonizada"],
  ["Zoom avant", "Zoom in", "Acercar"],
  ["Zoom arrière", "Zoom out", "Alejar"],
  ["Zoom maximum", "Zoom to max", "Zoom máximo"],
  ["Zoom minimum", "Zoom to min", "Zoom mínimo"],
  ["Avant", "In", "Más"],
  ["Arrière", "Out", "Menos"],
  ["Waterfall", "Waterfall", "Cascada"],
  ["Waterf.", "Waterf.", "Casc."],
  ["Spectre", "Spectrum", "Espectro"],
  ["Spectre ", "Spectr.", "Espec."],
  ["Afficher/masquer le waterfall", "Show/hide the waterfall", "Mostrar/ocultar la cascada"],
  ["Afficher/masquer le spectre", "Show/hide the spectrum", "Mostrar/ocultar el espectro"],
  ["Hauteur (+)", "Height (+)", "Altura (+)"],
  ["Spectrogramme audio", "Audio Spectrogram", "Espectrograma de audio"],
  ["📊 Masquer", "📊 Hide", "📊 Ocultar"],
  ["📊 Afficher", "📊 Show", "📊 Mostrar"],
  ["Affiche/masque le spectre audio de votre correspondant", "Shows/hides the audio spectrum of the station you hear", "Muestra/oculta el espectro de audio de su corresponsal"],
  ["Favoris", "Bookmarks", "Marcadores"],
  ["Gérer vos Fréquences Favorites.(mis en mémoire sur votre PC)", "Manage your favourite frequencies (stored on your PC)", "Gestione sus frecuencias favoritas (guardadas en su PC)"],

  // Favoris
  ["Ajouter un favori", "Add New Bookmark", "Añadir marcador"],
  ["Nom du favori", "Bookmark name", "Nombre del marcador"],
  ["Étiquette", "Label", "Etiqueta"],
  ["Étiquette (facultatif)", "Label (optional)", "Etiqueta (opcional)"],
  ["Ajouter", "Add", "Añadir"],
  ["Ajouter la fréquence actuelle aux favoris", "Add the current frequency to the bookmarks", "Añadir la frecuencia actual a los marcadores"],
  ["Lien actuel", "Current Link", "Enlace actual"],
  ["Copier le lien de partage", "Copy the share link", "Copiar el enlace para compartir"],
  ["Importer - exporter les favoris. Si vous ne les voyez pas, rechargez la page (ou appuyez sur F5) !", "Upload - Download Bookmarks. If you don't see them, please refresh the webpage (or press F5)!", "Importar - exportar marcadores. Si no los ve, recargue la página (o pulse F5)."],
  ["Importer/exporter les favoris. RECHARGEZ la page (F5) pour les voir !", "Up-Down/load Bookmarks. REFRESH the webpage (F5) to see them!", "Importar/exportar marcadores. ¡RECARGUE la página (F5) para verlos!"],
  ["Importer les favoris", "Upload Bookmarks", "Importar marcadores"],
  ["Exporter les favoris", "Download Bookmarks", "Exportar marcadores"],
  ["Importer des favoris depuis un fichier (JSON/CSV)", "Import bookmarks from a file (JSON/CSV)", "Importar marcadores desde un archivo (JSON/CSV)"],
  ["Télécharger les favoris (JSON/CSV)", "Download the bookmarks (JSON/CSV)", "Descargar los marcadores (JSON/CSV)"],
  ["Favoris enregistrés", "Saved Bookmarks", "Marcadores guardados"],
  ["Aller", "Go", "Ir"],
  ["Supprimer", "Delete", "Eliminar"],
  ["Accorder sur ce favori", "Tune to this bookmark", "Sintonizar este marcador"],
  ["Copier le lien de ce favori", "Copy this bookmark's link", "Copiar el enlace de este marcador"],
  ["Supprimer ce favori", "Delete this bookmark", "Eliminar este marcador"],
  ["Veuillez choisir un fichier.", "Please select a file.", "Seleccione un archivo."],
  ["Veuillez choisir un fichier JSON ou CSV.", "Please select a JSON or CSV file.", "Seleccione un archivo JSON o CSV."],
  ["Erreur de lecture du fichier.", "Error reading the file.", "Error al leer el archivo."],
  ["Erreur de lecture du fichier CSV.", "Error reading the CSV file.", "Error al leer el archivo CSV."],

  // CTCSS
  ["Sous-tonalité CTCSS (Hz)", "CTCSS subtone (Hz)", "Subtono CTCSS (Hz)"],
  ["Sous-tonalité CTCSS", "CTCSS subtone", "Subtono CTCSS"],
  ["N'importe quelle tonalité", "Any tone", "Cualquier tono"],
  ["Le squelch par tonalité ne fonctionne qu'en FM.", "Tone squelch works in FM only.", "El squelch por tono solo funciona en FM."],
  ["Entendu :", "Heard:", "Oído:"],

  // Fenêtre DX cluster
  ["Toutes bandes", "All bands", "Todas las bandas"],
  ["Filtrer par bande", "Filter by band", "Filtrar por banda"],
  ["Rafraîchir les spots", "Refresh spots", "Actualizar spots"],
  ["Spots indisponibles pour le moment.", "Spots unavailable for now.", "Spots no disponibles por ahora."],
  ["Chargement des spots…", "Loading spots…", "Cargando spots…"],
  ["Aucun spot pour cette bande.", "No spots for this band.", "No hay spots para esta banda."],
  ["Commentaire", "Comment", "Comentario"],
  ["Accorder le récepteur sur cette fréquence", "Tune the receiver to this frequency", "Sintonizar el receptor en esta frecuencia"],
  ["Hors de la plage du récepteur actif", "Outside the active receiver's range", "Fuera del rango del receptor activo"],
  ["Cliquez une fréquence bleue pour accorder le récepteur. Mise à jour toutes les 30 s.", "Click a blue frequency to tune the receiver. Updated every 30 s.", "Haga clic en una frecuencia azul para sintonizar el receptor. Actualización cada 30 s."],

  // Chat et pied de page
  ["↪ Répondre", "↪ Reply", "↪ Responder"],
  ["Répondre à ce message", "Reply to this message", "Responder a este mensaje"],
  ["Annuler la réponse (Échap)", "Cancel the reply (Esc)", "Cancelar la respuesta (Esc)"],
  ["↪ Réponse à", "↪ Replying to", "↪ Respondiendo a"],
  ["Envoyer", "Send", "Enviar"],
  ["Coller la fréq.", "Paste Freq", "Pegar frec."],
  ["Modifier", "Edit", "Editar"],
  ["Enregistrer", "Save", "Guardar"],
  ["Discuter en tant que :", "Chatting as:", "Chateando como:"],
  ["Saisissez votre nom/indicatif", "Enter your name/callsign", "Escriba su nombre/indicativo"],
  ["Tapez un message...", "Type a message...", "Escriba un mensaje..."],
  ["Tapez votre réponse...", "Type your reply...", "Escriba su respuesta..."],
  ["d'origine :", "original from", "original de"],

  // ── Sous-composants (lib/*.svelte) ──
  // S-mètre, œil magique, spectres, sélection vidéo
  ["Cliquer pour changer le style du S-mètre (sombre / clair / vintage)", "Click to switch meter style (dark / light / vintage)", "Clic para cambiar el estilo del S-meter (oscuro / claro / vintage)"],
  ["cliquer pour changer de style", "click to switch style", "clic para cambiar de estilo"],
  ["Oeil Magique (Sensible à la puissance du signal reçu", "Magic eye (responds to the received signal strength", "Ojo mágico (sensible a la potencia de la señal recibida"],
  ["Hz audio — repères jaunes = spots décodés", "audio Hz — yellow marks = decoded spots", "Hz de audio — marcas amarillas = spots decodificados"],
  ["Faites glisser pour choisir la zone d'enregistrement vidéo · Échap pour annuler", "Drag to select the video recording area · Esc to cancel", "Arrastre para elegir la zona de grabación de vídeo · Esc para cancelar"],
  ["— version ORSAT modifiée par F1NSK (", "— ORSAT version modified by F1NSK (", "— versión ORSAT modificada por F1NSK ("],

  // FreeDV Reporter
  ["Indicatif", "Callsign", "Indicativo"],
  ["Statut", "Status", "Estado"],
  ["Mode TX", "TX Mode", "Modo TX"],
  ["Dernier TX", "Last TX", "Último TX"],
  ["Indicatif RX", "RX Callsign", "Indicativo RX"],
  ["Mode RX", "RX Mode", "Modo RX"],
  ["Mis à jour", "Updated", "Actualizado"],
  ["En émission", "Transmitting", "Transmitiendo"],
  ["En réception", "Receiving", "Recibiendo"],
  ["Réception seule", "Receive Only", "Solo recepción"],

  // Decoder ID (ModeIdChip)
  ["ID décodeur", "Decoder ID", "ID decodificador"],
  ["Qu'est-ce que j'entends ?", "What am I hearing?", "¿Qué estoy escuchando?"],
  ["Reconnaît le mode du signal écouté (FT8, RTTY, CW, PSK…) et propose le bon décodeur", "Recognises the mode of the signal you are hearing (FT8, RTTY, CW, PSK…) and offers the right decoder", "Reconoce el modo de la señal que escucha (FT8, RTTY, CW, PSK…) y propone el decodificador adecuado"],
  ["▶ Écouter le modèle", "▶ Play the sample", "▶ Escuchar la muestra"],
  ["⏸ Pause", "⏸ Pause", "⏸ Pausa"],
  ["Écouter l'enregistrement de référence (le son du récepteur est coupé pendant l'écoute)", "Play the reference recording (the receiver audio is muted while it plays)", "Escuchar la grabación de referencia (el audio del receptor se silencia durante la escucha)"],
  ["Position de lecture", "Playback position", "Posición de reproducción"],
  ["📚 Chercher dans la base de signaux", "📚 Search the signal database", "📚 Buscar en la base de señales"],
  ["Analyse en continu le signal de la bande passante. Désactivée par défaut : ne consomme du processeur que lorsqu'elle est active.", "Continuously analyses the signal in the passband. Off by default: it only uses CPU while it is on.", "Analiza continuamente la señal de la banda de paso. Desactivada por defecto: solo consume CPU mientras está activa."],
  ["Reconnaissance automatique du mode numérique entendu", "Automatic recognition of the digital mode you are hearing", "Reconocimiento automático del modo digital que escucha"],
  ["Analyse : ON", "Analysis: ON", "Análisis: ON"],
  ["Analyse : OFF", "Analysis: OFF", "Análisis: OFF"],
  ["📚 Que peut être ce signal ?", "📚 What could this signal be?", "📚 ¿Qué puede ser esta señal?"],
  ["Mesure en cours :", "Current measurement:", "Medida actual:"],
  ["Modes reconnus, par pertinence", "Recognised modes, by relevance", "Modos reconocidos, por relevancia"],
  ["Mesuré sur le signal", "Measured from the signal", "Medido en la señal"],
  ["Nombre de mesures qui ont reconnu ce mode", "Number of measurements that recognised this mode", "Número de medidas que reconocieron este modo"],
  ["Aucun mode reconnu pour l'instant. Essayez l'analyse visuelle :", "No mode recognised yet. Try the visual analysis:", "Ningún modo reconocido por ahora. Pruebe el análisis visual:"],
  ["📚 Comparer avec la base de signaux", "📚 Compare with the signal database", "📚 Comparar con la base de señales"],
  ["📊 Voir le spectrogramme audio", "📊 Show the audio spectrogram", "📊 Ver el espectrograma de audio"],
  ["Comparer la forme du signal avec les spectrogrammes et les sons de la base de signaux", "Compare the signal with the spectrograms and sounds of the signal database", "Comparar la señal con los espectrogramas y sonidos de la base de señales"],
  ["Afficher le spectrogramme audio pour voir la structure du signal (tons, espacement, rythme)", "Show the audio spectrogram to see the signal structure (tones, spacing, rhythm)", "Mostrar el espectrograma de audio para ver la estructura de la señal (tonos, separación, ritmo)"],
  ["Astuce : centrez le signal dans la bande passante et élargissez le filtre s'il est coupé.", "Tip: centre the signal in the passband and widen the filter if it is clipped.", "Consejo: centre la señal en la banda de paso y amplíe el filtro si está recortada."],
  ["Activez l'analyse : le mode est reconnu en 15 s environ (FT8, WSPR, RTTY, PSK, Olivia, CW…).",
   "Turn the analysis on: the mode is recognised in about 15 s (FT8, WSPR, RTTY, PSK, Olivia, CW…).",
   "Active el análisis: el modo se reconoce en unos 15 s (FT8, WSPR, RTTY, PSK, Olivia, CW…)."],
  ["Identifier le mode numérique présent dans la bande passante. Désactivé par défaut — il ne consomme du CPU que lorsqu'il est actif.",
   "Identify the digital mode in the passband. Off by default — it only uses CPU while it is on.",
   "Identificar el modo digital presente en la banda de paso. Desactivado por defecto — solo usa CPU mientras está activo."],
  ["Le signal est près du bord de la bande passante, où la mesure n'est pas fiable. Déplacez le cadran pour le placer au milieu, puis mesurez à nouveau.",
   "The signal is near the edge of the passband, where the measurement is unreliable. Move the dial so it sits mid-passband, then measure again.",
   "La señal está cerca del borde de la banda de paso, donde la medida no es fiable. Mueva el dial para centrarla y mida de nuevo."],
  ["C'est une fréquence d'appel connue pour ce mode, ce qui explique en partie son premier rang.",
   "This is a known calling frequency for that mode, which is part of why it ranks first.",
   "Es una frecuencia de llamada conocida para ese modo, lo que explica en parte su primer puesto."],
  ["Mesuré sur le signal", "Measured from the signal", "Medido en la señal"],
  ["Passer au décodeur de ce mode", "Switch to the decoder for this mode", "Pasar al decodificador de este modo"],
  ["Identifié, mais cette version n'a pas de décodeur pour ce mode.", "Identified, but this build has no decoder for it.", "Identificado, pero esta versión no tiene decodificador para él."],
  ["Écoute…", "Listening…", "Escuchando…"],
  ["Recentrer & réessayer", "Recentre & retry", "Recentrar y reintentar"],
  ["ou", "or", "o"],
  ["Utiliser", "Use", "Usar"],
  ["pas de décodeur", "no decoder", "sin decodificador"],
  ["qu'est-ce que j'écoute ?", "what am I listening to?", "¿qué estoy escuchando?"],
  ["Rien au-dessus du bruit", "Nothing above the noise", "Nada por encima del ruido"],
  ["Non reconnu", "Not recognised", "No reconocido"],

  // HFDL (HfdlPanel)
  ["Récepteur HFDL", "HFDL Receiver", "Receptor HFDL"],
  ["chargement du décodeur…", "loading the decoder…", "cargando el decodificador…"],
  ["décodeur indisponible", "decoder unavailable", "decodificador no disponible"],
  ["[trame en cours]", "[frame in progress]", "[trama en curso]"],
  ["en attente d'une trame…", "waiting for a frame…", "esperando una trama…"],
  ["🗺 Carte (", "🗺 Map (", "🗺 Mapa ("],
  ["Afficher la carte des avions dont une position a été reçue", "Show the map of aircraft whose position was received", "Mostrar el mapa de los aviones cuya posición se ha recibido"],
  ["Enregistrer les messages HFDL décodés (texte)", "Save the decoded HFDL messages (text)", "Guardar los mensajes HFDL decodificados (texto)"],
  ["Effacer les messages HFDL", "Clear the HFDL messages", "Borrar los mensajes HFDL"],
  ["Aucune position reçue pour l'instant : seuls certains messages (rapports de position, données de performance) en contiennent.",
   "No position received yet: only some messages (position reports, performance data) carry one.",
   "Aún no se ha recibido ninguna posición: solo algunos mensajes (informes de posición, datos de rendimiento) la incluyen."],
  ["Station sol HFDL", "HFDL ground station", "Estación de tierra HFDL"],
  ["Fréquence de la station (kHz, USB)", "Station frequency (kHz, USB)", "Frecuencia de la estación (kHz, USB)"],
  ["Accorder le récepteur sur cette fréquence HFDL en USB et régler le filtre FI", "Tune the receiver to this HFDL frequency in USB and set the IF filter", "Sintonizar el receptor en esta frecuencia HFDL en USB y ajustar el filtro FI"],
  ["Fréquence actuellement écoutée", "Frequency being listened to", "Frecuencia que se está escuchando"],
  ["Dial :", "Dial:", "Dial:"],
  ["⚠ hors fréquence HFDL", "⚠ off HFDL frequency", "⚠ fuera de frecuencia HFDL"],
  ["La fréquence écoutée n'est pas une fréquence HFDL connue : choisissez une station puis Tune", "The frequency you are on is not a known HFDL frequency: pick a station, then Tune", "La frecuencia escuchada no es una frecuencia HFDL conocida: elija una estación y luego Tune"],
  ["Bruit :", "Noise:", "Ruido:"],
  ["Plancher de bruit mesuré par le décodeur", "Noise floor measured by the decoder", "Ruido de fondo medido por el decodificador"],
  ["Trames HFDL décodées depuis l'activation", "HFDL frames decoded since start", "Tramas HFDL decodificadas desde la activación"],
  ["Rythme :", "Rate:", "Ritmo:"],
  ["verrouillé (", "locked (", "enganchado ("],
  ["recherche", "searching", "buscando"],
  ["Le décodeur cherche le rythme exact de l'audio (±1 %) et s'y verrouille dès qu'une trame est décodée", "The decoder looks for the exact audio rate (±1 %) and locks onto it as soon as a frame decodes", "El decodificador busca el ritmo exacto del audio (±1 %) y se engancha en cuanto decodifica una trama"],
  ["Écart de fréquence rattrapé par le décodeur (erreur d'horloge du récepteur ou accord approximatif)", "Frequency offset taken up by the decoder (receiver clock error or rough tuning)", "Desfase de frecuencia corregido por el decodificador (error de reloj del receptor o sintonía aproximada)"],
  ["Messages :", "Messages:", "Mensajes:"],
  ["· Squitters :", "· Squitters:", "· Squitters:"],
  ["Messages (hors squitters) / squitters des stations sol", "Messages (squitters excluded) / ground station squitters", "Mensajes (sin squitters) / squitters de las estaciones de tierra"],
  ["Afficher aussi les squitters (annonces périodiques des stations sol, toutes les 32 s)", "Also show the squitters (periodic ground station announcements, every 32 s)", "Mostrar también los squitters (anuncios periódicos de las estaciones de tierra, cada 32 s)"],
  ["Choisissez une station sol, cliquez sur « Tune », puis patientez : les stations émettent un squitter toutes les 32 s, et les avions répondent quand ils ont du trafic.",
   "Pick a ground station, click “Tune”, then wait: stations send a squitter every 32 s, and aircraft answer when they have traffic.",
   "Elija una estación de tierra, pulse «Tune» y espere: las estaciones emiten un squitter cada 32 s y los aviones responden cuando tienen tráfico."],
  ["Aucun message d'avion pour l'instant (", "No aircraft message yet (", "Ningún mensaje de avión por ahora ("],
  ["squitter(s) reçu(s), cochez « Squitters » pour les voir).", "squitter(s) received, tick “Squitters” to see them).", "squitter(s) recibido(s), marque «Squitters» para verlos)."],
  ["Voir la position de l'avion sur une carte", "Show the aircraft's position on a map", "Ver la posición del avión en un mapa"],
  ["Montant : station sol → avion", "Uplink: ground station → aircraft", "Ascendente: estación de tierra → avión"],
  ["Descendant : avion → station sol", "Downlink: aircraft → ground station", "Descendente: avión → estación de tierra"],
  ["Décodeur dumphfdl (GPL-3) en WebAssembly, sur l'audio USB avant les filtres d'écoute. Survolez un message pour voir la trame complète.",
   "dumphfdl decoder (GPL-3) in WebAssembly, on the USB audio before the listening filters. Hover a message to see the full frame.",
   "Decodificador dumphfdl (GPL-3) en WebAssembly, sobre el audio USB antes de los filtros de escucha. Pase sobre un mensaje para ver la trama completa."],

  // Réception en diversité (DiversityPanel)
  ["Réception en diversité", "Receive Diversity", "Recepción en diversidad"],
  ["Combiner ce récepteur avec un second pour passer les évanouissements", "Combine this receiver with a second one to ride through fades", "Combinar este receptor con un segundo para superar los desvanecimientos"],
  ["2e récepteur", "Second RX", "Segundo RX"],
  ["Ajouter un récepteur à la main", "Add a receiver by hand", "Añadir un receptor a mano"],
  ["Tous les oublier", "Forget them all", "Olvidarlos todos"],
  ["nom (facultatif)", "name (optional)", "nombre (opcional)"],
  ["Monter", "Move up", "Subir"],
  ["Descendre", "Move down", "Bajar"],
  ["Mettre cette adresse dans le champ (faites glisser la ligne pour réordonner)", "Put this address in the box (drag the row to reorder)", "Poner esta dirección en el campo (arrastre la fila para reordenar)"],
  ["Ouvrir la page de ce récepteur dans un nouvel onglet", "Open this receiver's own page in a new tab", "Abrir la página de este receptor en una pestaña nueva"],
  ["Modifier le nom et l'adresse", "Edit the name and address", "Editar el nombre y la dirección"],
  ["Retirer ce récepteur", "Remove this receiver", "Quitar este receptor"],
  ["Ignorer", "Dismiss", "Descartar"],
  ["Garder ce qui est enregistré et y ajouter les récepteurs du fichier", "Keep what is saved and add the file's receivers to it", "Conservar lo guardado y añadirle los receptores del archivo"],
  ["Jeter tous les récepteurs enregistrés et utiliser ceux du fichier", "Throw away every saved receiver and use the file's", "Descartar todos los receptores guardados y usar los del archivo"],
  ["Enregistrer toutes les listes dans un fichier à conserver", "Save every list to a file you can keep", "Guardar todas las listas en un archivo"],
  ["Relire les listes depuis un fichier", "Read the lists back from a file", "Volver a leer las listas desde un archivo"],
  ["Afficher les listes en QR code, pour les transférer sur un téléphone", "Show the lists as a QR code, to carry them to a phone", "Mostrar las listas como código QR, para pasarlas a un teléfono"],
  ["Ajouté au SNR distant avant comparaison. Un codec distant avec pertes plafonne son propre bruit, son SNR paraît donc plus bas qu'en réalité. Laisser à 0 pour un autre PhantomSDR-Plus.",
   "Added to the remote's SNR before comparison. A lossy remote codec floors its own noise, so its SNR reads lower than it really is. Leave at 0 for another PhantomSDR-Plus.",
   "Se suma al SNR remoto antes de comparar. Un códec remoto con pérdidas limita su propio ruido, así que su SNR parece más bajo de lo que es. Deje 0 para otro PhantomSDR-Plus."],
  ["Enregistrés pour", "Saved for", "Guardados para"],
  ["tout effacer", "clear all", "borrar todo"],
  ["récepteur", "receiver", "receptor"],
  ["récepteurs", "receivers", "receptores"],
  ["dans ce fichier", "in that file", "en ese archivo"],
  ["fusionner", "merge", "combinar"],
  ["remplacer", "replace", "reemplazar"],
  ["copier le texte", "copy text", "copiar texto"],
  ["Scannez-le avec le téléphone, puis collez-le dans", "Scan it on the phone, then paste into", "Escanéelo con el teléfono y péguelo en"],
  ["Importer", "Import", "Importar"],
  ["dans l'onglet Div de la page /mobile.", "on the Div tab of the /mobile page.", "en la pestaña Div de la página /mobile."],
  ["⭳ exporter", "⭳ export", "⭳ exportar"],
  ["⭱ importer", "⭱ import", "⭱ importar"],
  ["Correction SNR distant", "Remote SNR trim", "Corrección SNR remoto"],
  ["liaison", "link", "enlace"],
  ["aligné", "aligned", "alineado"],
  ["audio distant", "remote audio", "audio remoto"],
  ["SNR distant", "SNR remote", "SNR remoto"],
  ["basculements", "switches", "conmutaciones"],
  ["le récepteur distant ne couvre pas cette fréquence", "remote does not cover this frequency", "el receptor remoto no cubre esta frecuencia"],
  ["Les décodeurs continuent d'utiliser le récepteur local — un basculement de site en plein créneau casse le décodage cohérent. La diversité n'alimente que le haut-parleur.",
   "Decoders keep using the local receiver — a site switch mid-slot breaks coherent decoding. Diversity feeds the speaker only.",
   "Los decodificadores siguen usando el receptor local — un cambio de sitio a mitad de intervalo rompe la decodificación coherente. La diversidad solo alimenta el altavoz."],
  ["Trop de récepteurs pour un QR code encore lisible par un téléphone — copiez plutôt le texte.", "Too many receivers for a QR code that a phone can still read — copy the text instead.", "Demasiados receptores para un código QR legible por un teléfono — copie el texto."],
  ["Impossible de dessiner le QR code — copiez plutôt le texte.", "Could not draw the QR code — copy the text instead.", "No se pudo dibujar el código QR — copie el texto."],
  ["Copié dans le presse-papiers.", "Copied to the clipboard.", "Copiado al portapapeles."],
  ["Échec de la copie — sélectionnez le texte et copiez-le à la main.", "Copy failed — select the text and copy it by hand.", "Falló la copia — seleccione el texto y cópielo a mano."],
  ["Ce fichier n'est pas un JSON lisible.", "That file is not readable JSON.", "Ese archivo no es un JSON legible."],
  ["Ce fichier ne contient aucun récepteur enregistré.", "That file holds no saved receivers.", "Ese archivo no contiene receptores guardados."],
  ["Veuillez patienter…", "Please wait…", "Espere…"],
  ["Récepteurs enregistrés — sauvegarder ou restaurer", "Saved receivers — back up or restore", "Receptores guardados — copia de seguridad o restaurar"],
  ["Récepteurs enregistrés en QR code", "Saved receivers as a QR code", "Receptores guardados como código QR"],
  ["La sauvegarde couvre les quatre types de récepteurs", "Backup covers all four receiver types", "La copia cubre los cuatro tipos de receptor"],
  ["Rien d'enregistré — restaurez un fichier de sauvegarde", "Nothing saved yet — restore a backup file", "Nada guardado — restaure un archivo de copia"],
  // Decoder ID — modes fldigi (fldigiId.js)
  ["ton jamais répété (IFK), varicode nue (pas de FEC)", "tone never repeated (IFK), bare varicode (no FEC)", "tono nunca repetido (IFK), varicode sin codificar (sin FEC)"],
  ["ton jamais répété (IFK) — THOR possible", "tone never repeated (IFK) — could be THOR", "tono nunca repetido (IFK) — puede ser THOR"],
  ["ton jamais répété (IFK), données codées (FEC)", "tone never repeated (IFK), coded data (FEC)", "tono nunca repetido (IFK), datos codificados (FEC)"],
  ["même géométrie que DominoEX, avec FEC", "same geometry as DominoEX, with FEC", "misma geometría que DominoEX, con FEC"],
  ["ton seul haché au rythme des colonnes (17,5 par seconde)", "single tone chopped at the column rate (17.5 per second)", "tono único troceado al ritmo de las columnas (17,5 por segundo)"],
  // Fiches de signaux de référence (SignalRefPanel)
  ["Identifier un signal", "Identify a signal", "Identificar una señal"],
  ["🔍 Identifier", "🔍 Identify", "🔍 Identificar"],
  ["Base Artemis / Signal Identification Wiki", "Artemis / Signal Identification Wiki database", "Base Artemis / Signal Identification Wiki"],
  ["Signaux de référence", "Reference signals", "Señales de referencia"],
  ["Fréquence (kHz)", "Frequency (kHz)", "Frecuencia (kHz)"],
  ["Largeur (Hz)", "Width (Hz)", "Ancho (Hz)"],
  ["Démodulation", "Demodulation", "Demodulación"],
  ["Filtre", "Filter", "Filtro"],
  ["nom, catégorie, modulation…", "name, category, modulation…", "nombre, categoría, modulación…"],
  ["Chargement…", "Loading…", "Cargando…"],
  ["Aucune fiche ne correspond.", "No entry matches.", "Ninguna ficha coincide."],
  ["Choisissez une fiche dans la liste. Le classement compare la fréquence, la largeur et la démodulation à celles de chaque signal connu.", "Pick an entry from the list. The ranking compares frequency, width and demodulation with those of each known signal.", "Elija una ficha de la lista. La clasificación compara la frecuencia, el ancho y la demodulación con las de cada señal conocida."],
  ["Spectre de référence", "Reference spectrum", "Espectro de referencia"],
  ["Largeur", "Width", "Ancho"],
  ["Modulation", "Modulation", "Modulación"],
  ["Mode de réception", "Receive mode", "Modo de recepción"],
  ["Plage de fréquences", "Frequency range", "Rango de frecuencias"],
  ["Fréquences connues", "Known frequencies", "Frecuencias conocidas"],
  ["Catégorie", "Category", "Categoría"],
  ["Fiche complète sur sigidwiki.com ↗", "Full entry on sigidwiki.com ↗", "Ficha completa en sigidwiki.com ↗"],
  ["Fiche de référence : spectre, son et description du mode", "Reference entry: spectrum, sound and description of the mode", "Ficha de referencia: espectro, sonido y descripción del modo"],
  ["Fiche de référence", "Reference entry", "Ficha de referencia"],
  ["Chercher dans la base de signaux de référence ce qui correspond à la fréquence, à la largeur du filtre et à la démodulation en cours", "Search the reference signal database for what matches the current frequency, filter width and demodulation", "Buscar en la base de señales de referencia lo que coincide con la frecuencia, el ancho del filtro y la demodulación actuales"],
];

// ── Libellés variables : $1, $2 sont repris (et traduits s'ils sont connus) ──
const P = [
  ["Lecture impossible : $1", "Playback failed: $1", "Reproducción imposible: $1"],
  ["vu $1× · il y a $2 s", "seen $1× · $2 s ago", "visto $1× · hace $2 s"],
  ["vu $1× · il y a $2 min", "seen $1× · $2 min ago", "visto $1× · hace $2 min"],
  ["vu $1× · à l'instant", "seen $1× · just now", "visto $1× · ahora mismo"],
  ["▶ Lancer $1", "▶ Launch $1", "▶ Iniciar $1"],
  ["$1 tons à $2 Hz, $3 Bd, symboles purs à $4 %, $5", "$1 tones at $2 Hz, $3 Bd, symbols $4 % pure, $5", "$1 tonos a $2 Hz, $3 Bd, símbolos puros al $4 %, $5"],
  ["$1 tons à $2 Hz, $3 Bd, symboles purs à $4 %", "$1 tones at $2 Hz, $3 Bd, symbols $4 % pure", "$1 tonos a $2 Hz, $3 Bd, símbolos puros al $4 %"],
  ["$1 Hz occupés à plat en permanence (64 porteuses)", "$1 Hz filled flat at all times (64 carriers)", "$1 Hz ocupados de forma plana en todo momento (64 portadoras)"],
  ["synchro de Costas reconnue — $1 stations", "Costas sync recognised — $1 stations", "sincronismo Costas reconocido — $1 estaciones"],
  ["synchro de Costas reconnue — $1 station", "Costas sync recognised — $1 station", "sincronismo Costas reconocido — $1 estación"],
  ["Plus lointain : $1", "Farthest: $1", "Más lejano: $1"],
  ["Active — $1", "Active — $1", "Activa — $1"],
  ["Contrôle CAT actif — $1", "CAT control active — $1", "Control CAT activo — $1"],
  ["Liaison CAT active — source : $1", "CAT link active — source: $1", "Enlace CAT activo — fuente: $1"],
  ["$1 / $2 utilisés", "$1 / $2 in use", "$1 / $2 en uso"],
  ["Effacer $1 verrouillages", "Clear $1 locked", "Borrar $1 bloqueos"],
  ["occupé $1", "busy $1", "ocupado $1"],
  ["Réglage AGC : $1", "AGC setting: $1", "Ajuste AGC: $1"],
  ["Sélectionner le mode $1", "Select the $1 mode", "Seleccionar el modo $1"],
  ["Démarrer le décodeur RADE v1 $1", "Start the RADE v1 $1 decoder", "Iniciar el decodificador RADE v1 $1"],
  ["Bande $1", "$1 band", "Banda $1"],
  ["$1 trames", "$1 frames", "$1 tramas"],
  ["$1 trame", "$1 frame", "$1 trama"],
  ["Décodeur $1", "$1 Decoder", "Decodificador $1"],
  ["Le décodeur $1 a pris le contrôle du mode et de la FI pendant son fonctionnement.",
   "$1 decoder has taken control of mode and IF while active.",
   "El decodificador $1 ha tomado el control del modo y la FI mientras está activo."],
  ["Balayage vers le $1 — seuil $2 dB au-dessus du bruit de fond", "Scanning $1 — threshold $2 dB over the noise floor", "Barrido hacia $1 — umbral $2 dB sobre el ruido de fondo"],
  ["Balayer vers le $1 par pas de $2 kHz — reprend une fois à l'arrêt", "Scan $1 in $2 kHz steps — resumes once stopped", "Barrer hacia $1 en pasos de $2 kHz — se reanuda tras detenerse"],
  ["$1 dB au-dessus du bruit de fond de la bande, suivi en continu par le waterfall", "$1 dB over the band noise floor, tracked continuously by the waterfall", "$1 dB sobre el ruido de fondo de la banda, seguido continuamente por la cascada"],
  ["Reprendre après $1 secondes de silence sur le canal", "Resume after $1 seconds of silence on the channel", "Reanudar tras $1 segundos de silencio en el canal"],
  ["Repartir après $1 même si le signal est toujours présent", "Move on after $1 even if the signal is still there", "Seguir tras $1 aunque la señal siga presente"],
  ["PhantomSDR+ | v$1 d'origine :", "PhantomSDR+ | v$1 original from", "PhantomSDR+ | v$1 original de"],
  ["PC : $1", "PC: $1", "PC: $1"],
  ["$1 — pas de décodeur pour ce mode", "$1 — no decoder for this mode", "$1 — sin decodificador para este modo"],
  ["Carte indisponible : $1", "Map unavailable: $1", "Mapa no disponible: $1"],
  ["$1 récepteur enregistré pour ce type — cliquer pour nommer, modifier, sauvegarder ou restaurer", "$1 saved receiver for this receiver type — click to name, edit, back up or restore", "$1 receptor guardado para este tipo — clic para nombrar, editar, guardar o restaurar"],
  ["$1 récepteurs enregistrés pour ce type — cliquer pour nommer, modifier, sauvegarder ou restaurer", "$1 saved receivers for this receiver type — click to name, edit, back up or restore", "$1 receptores guardados para este tipo — clic para nombrar, editar, guardar o restaurar"],
  ["$1 Hz/ligne — l'affichage est la limite, réduisez la largeur", "$1 Hz/row — display is the limit, narrow the Span", "$1 Hz/fila — la pantalla es el límite, reduzca el ancho"],
  ["$1 Hz/ligne", "$1 Hz/row", "$1 Hz/fila"],
  ["$1 s/colonne", "$1 s/column", "$1 s/columna"],
];

// Le fragment « decoder has taken control… » qui suit un nom de mode variable.
D.find((e) => e[1] === "decoder has taken control of mode and IF while active.").splice(
  0, 3,
  "— ce décodeur a pris le contrôle du mode et de la FI pendant son fonctionnement.",
  "decoder has taken control of mode and IF while active.",
  "— este decodificador ha tomado el control del modo y la FI mientras está activo.",
);

// ── Index de recherche ──────────────────────────────────────────────────────
const norm = (s) => String(s).replace(/[\s ]+/g, " ").trim();
const exact = new Map();
const lower = new Map();
for (const entry of D) {
  for (const v of entry) {
    const k = norm(v);
    if (!k) continue;
    if (!exact.has(k)) exact.set(k, entry);
    const l = k.toLowerCase();
    if (!lower.has(l)) lower.set(l, entry);
  }
}
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const patterns = [];
for (const entry of P) {
  for (const tpl of entry) {
    const src = escapeRe(norm(tpl)).replace(/\\\$(\d)/g, "(.+?)");
    patterns.push({ re: new RegExp("^" + src + "$"), entry });
  }
}

function entryFor(core) {
  return exact.get(core) || lower.get(core.toLowerCase()) || null;
}

const HAS_LETTERS = /\p{L}{2}/u;
const missing = new Set(); // plafonné, pour ne pas grossir avec le texte décodé

function translateCore(core) {
  const k = norm(core);
  if (!k || !HAS_LETTERS.test(k)) return null;
  const e = entryFor(k);
  if (e) return e[IDX[current]];
  for (const p of patterns) {
    const m = k.match(p.re);
    if (!m) continue;
    return p.entry[IDX[current]].replace(/\$(\d)/g, (_, i) => {
      const cap = m[+i] || "";
      const ce = entryFor(norm(cap));
      return ce ? ce[IDX[current]] : cap;
    });
  }
  if (missing.size < 2000) missing.add(k);
  return null;
}

/** Traduit une chaîne dans la langue courante, en gardant ses espaces de bord. */
export function tr(raw) {
  if (raw == null) return raw;
  const s = String(raw);
  const m = s.match(/^([\s ]*)([\s\S]*?)([\s ]*)$/);
  const t = translateCore(m[2]);
  return t == null ? s : m[1] + t + m[3];
}

// ── Couche DOM ──────────────────────────────────────────────────────────────
const ATTRS = ["title", "placeholder", "aria-label"];
const texts = new WeakMap(); // nœud texte → { src, out }
const attrs = new WeakMap(); // élément → { attr: { src, out } }
let observer = null;

function ignored(el) {
  return !el || !!(el.closest && el.closest("[data-no-i18n],script,style,textarea"));
}

function doText(node) {
  const cur = node.data;
  const rec = texts.get(node);
  const src = rec && cur === rec.out ? rec.src : cur;
  if (!rec && !HAS_LETTERS.test(cur)) return;
  if (ignored(node.parentElement)) return;
  const out = tr(src);
  texts.set(node, { src, out });
  if (out !== cur) node.data = out;
}

function doAttr(el, name) {
  if (!el.hasAttribute(name)) return;
  const cur = el.getAttribute(name);
  let recs = attrs.get(el);
  const rec = recs && recs[name];
  const src = rec && cur === rec.out ? rec.src : cur;
  const out = tr(src);
  if (!recs) attrs.set(el, (recs = {}));
  recs[name] = { src, out };
  if (out !== cur) el.setAttribute(name, out);
}

function doElement(el) {
  if (ignored(el)) return;
  for (const a of ATTRS) doAttr(el, a);
  if (el.tagName === "INPUT" && /^(submit|button)$/i.test(el.type)) doAttr(el, "value");
}

function walk(root) {
  if (!root) return;
  if (root.nodeType === 3) return doText(root);
  if (root.nodeType !== 1) return;
  if (ignored(root)) return;
  doElement(root);
  const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    if (n.nodeType === 3) doText(n);
    else doElement(n);
  }
}

/** Démarre la traduction du DOM. À appeler une fois, depuis onMount. */
export function startI18n() {
  document.documentElement.lang = current;
  walk(document.body);
  if (observer) return;
  observer = new MutationObserver((list) => {
    for (const m of list) {
      if (m.type === "characterData") doText(m.target);
      else if (m.type === "attributes") {
        if (!ignored(m.target)) doAttr(m.target, m.attributeName);
      } else for (const n of m.addedNodes) walk(n);
    }
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: [...ATTRS, "value"],
  });
}

/** Change la langue de toute l'interface et la mémorise dans le navigateur. */
export function setLang(l) {
  if (!LANGS.includes(l) || l === current) return;
  current = l;
  lang.set(l);
  try {
    localStorage.setItem(STORAGE_KEY, l);
  } catch (e) {}
  document.documentElement.lang = l;
  walk(document.body);
}

// Outil de maintenance : textes vus à l'écran sans traduction.
if (typeof window !== "undefined") {
  window.i18nMissing = () => [...missing].sort();
}
