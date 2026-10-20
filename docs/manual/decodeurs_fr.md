---
pdf: guideDecodeursFR.pdf
pdf_title: PhantomSDR-ORSAT — Guide des décodeurs
title: Les décodeurs d'ORSAT
subtitle: Guide complet — modes numériques, télégraphie, images, messages maritimes et aéronautiques
url: https://orsat.ddns.net
cover: fr_p19_0.jpg
cover_caption: Le décodeur FT8 : forme d'onde audio, repères de décodage et tableau des messages.
summary: Ce guide décrit, un par un, tous les décodeurs intégrés à ORSAT : à quoi ils servent, où les écouter, comment les régler et comment lire ce qu'ils affichent. Il se termine par les outils d'aide à l'identification des signaux et par un chapitre de dépannage.
edition: Version française — Édition octobre 2026 — ORSAT 1.0
credits: Décodeurs intégrés par **F1NSK** pour ORSAT, sur la base de PhantomSDR-Plus de **SV1BTL**. Base de signaux : **Artemis** (AresValley) et **Signal Identification Wiki**.
header_left: ORSAT — Guide des décodeurs
header_right: ORSAT 1.0
page: Page
toc: Sommaire
---

# 1. Principes communs

## 1.1 Où se trouvent les décodeurs

Tous les décodeurs sont regroupés dans la rangée **Decoders Control**, dans la colonne de droite, sous le scanner. Chaque bouton lance un décodeur ; un second clic sur le même bouton l'arrête. **Un seul décodeur fonctionne à la fois** : en lancer un autre arrête le précédent.

![La rangée « Decoders Control » et ses onze boutons.](images/dec_rangee.jpg){w=380}

| Bouton | Décodeur | Chapitre |
| FT8 / FT4 / FT2 | Modes WSJT faible signal | 2 |
| JS8 | JS8Call | 3 |
| CW | Télégraphie Morse | 4 |
| WSPR | Balises WSPR-2 | 5 |
| FAX | Fac-similé météo HF (WEFAX) | 6 |
| SSTV | Télévision à balayage lent | 7 |
| NAVTX | NAVTEX (avis aux navigateurs) | 8 |
| HFDL | HF Data Link (aviation) | 9 |
| FLDIGI | Famille fldigi : RTTY, SITOR, PSK31, Olivia, MFSK… | 10 |

Les modes vocaux numériques **RADE (FreeDV)** ne sont pas dans cette rangée : ils ont leurs propres boutons **RADEL / RADEU** dans le sélecteur de modes (chapitre 11).

## 1.2 Ce que fait un décodeur quand il démarre

Un décodeur ne se contente pas de lire le son : il **prend en main le récepteur** pour se placer dans les bonnes conditions.

- **Mode de démodulation** — FT8, FT4, FT2, JS8 et WSPR passent le récepteur en **USB**, quel que soit le mode habituel de la bande. FAX et NAVTEX travaillent aussi en USB. SSTV choisit la bande latérale d'usage (voir chapitre 7).
- **Filtre FI** — la bande passante est réglée sur celle du mode : toute la sous-bande de 3 kHz pour FT8/FT4/FT2/JS8, la fenêtre étroite des balises pour WSPR.
- **Retour à la normale** — à l'arrêt du décodeur, le récepteur reprend le **mode par défaut de la bande** (LSB, CW, AM…).
- **Analyse automatique** — si le module « Analyse des signaux numériques » tournait, il s'arrête : il a rempli son rôle, qui était d'aider à choisir un décodeur.

> [Astuce] Les décodeurs travaillent sur le son **brut** du récepteur, avant la réduction de bruit, l'AGC audio et le volume. Couper le son ou baisser le volume n'empêche donc pas de décoder.

## 1.3 Les outils partagés

**Fréquences connues.** Les panneaux FT8/FT4, JS8, WSPR et SSTV proposent un menu **Fréquences connues** : choisir une bande accorde directement le récepteur sur la fréquence « dial » d'usage du mode. FAX, NAVTEX, HFDL et FLDIGI ont leurs propres listes de stations, décrites dans leurs chapitres.

**Carte des stations.** FT8/FT4/FT2, JS8 et WSPR ont un bouton **🗺 Carte (n)** : chaque station dont le message contient un locator y est placée. **⤢ Grand format** ouvre la carte dans une fenêtre flottante, déplaçable et redimensionnable. Le survol d'un point montre l'indicatif et le message, un clic ouvre la fiche QRZ de la station.

![Carte des stations entendues, en grand format.](images/dec_carte.jpg){w=380}

**Spectre audio du décodeur.** FT8/FT4/FT2, JS8 et WSPR affichent sous leurs réglages une **cascade audio** de la bande passante : on y voit les signaux arriver, et chaque décodage y est repéré.

**Synchronisation horaire.** Les modes à créneaux fixes (FT8, FT4, FT2, JS8, WSPR) dépendent de l'heure UTC. ORSAT compense le retard du flux audio entre le serveur et votre navigateur grâce au réglage **Sync offset** (section 2.4).

# 2. FT8, FT4 et FT2

## 2.1 Les trois modes

Ces trois modes de la famille WSJT-X transmettent de courts messages normalisés (indicatifs, locator, report) avec une très grande sensibilité. Ils fonctionnent par **créneaux** synchronisés sur l'heure UTC.

| Mode | Durée d'un créneau | Usage |
| FT8 | 15 s | Le plus répandu : DX, propagation, trafic courant |
| FT4 | 7,5 s | Plus rapide, surtout en concours |
| FT2 | 3,75 s | Variante très rapide, encore peu utilisée |

## 2.2 Mise en route

1. Cliquez sur **FT8**, **FT4** ou **FT2**.
2. Dans **Fréquences connues**, choisissez une bande (FT8 et FT4 ; FT2 n'a pas encore de liste). Le récepteur s'accorde en USB.
3. Attendez la fin du créneau en cours : les premiers décodages apparaissent après 15 s (FT8), 7,5 s (FT4) ou 3,75 s (FT2).

| Bande | FT8 (kHz) | FT4 (kHz) |
| 160 m | 1 840,0 | — |
| 80 m | 3 573,0 | 3 575,0 |
| 60 m | 5 357,0 | — |
| 40 m | 7 074,0 | 7 047,5 |
| 30 m | 10 136,0 | 10 140,0 |
| 20 m | 14 074,0 | 14 080,0 |
| 17 m | 18 100,0 | 18 104,0 |
| 15 m | 21 074,0 | 21 140,0 |
| 12 m | 24 915,0 | 24 919,0 |
| 10 m | 28 074,0 | 28 180,0 |
| 6 m | 50 313,0 | 50 318,0 |

## 2.3 Lire le panneau

![Panneau FT8 : forme d'onde, réglage de synchro et tableau des messages.](images/fr_p19_0.jpg){w=375}

- **Farthest** — distance du contact le plus lointain entendu depuis le début de la session.
- **Forme d'onde audio** — les repères marquent chaque signal décodé dans la bande passante.
- **Tableau des messages** — une ligne par décodage :

| Colonne | Contenu |
| Mode | FT8, FT4 ou FT2 |
| dB | Rapport signal/bruit estimé (un signal à −20 dB est encore décodé) |
| Hz | Fréquence audio du signal dans la bande passante |
| DT | Écart de synchronisation, en secondes |
| Message | Le texte : CQ F1ABC JN03, F1ABC DL1XYZ -12, RR73… |
| Locator / Dist | Locator Maidenhead de la station et distance estimée depuis ORSAT |

## 2.4 Sync offset et Auto

Le son met un peu de temps à vous parvenir. **Sync offset** décale le début de la capture après le début du créneau UTC pour compenser ce retard (valeur affichée en secondes).

- **Auto** coché (recommandé) — ORSAT ajuste lui-même le décalage à partir des valeurs **DT** mesurées par le décodeur.
- **Auto** décoché — réglez le curseur à la main : si la plupart des DT sont fortement positifs ou négatifs, déplacez-le dans le même sens.

> [Astuce] Des DT tous voisins de 0 (entre −0,5 et +0,5 s) indiquent une synchro correcte. Des DT dispersés au-delà de ±1 s font perdre des décodages.

# 3. JS8 (JS8Call)

## 3.1 Le mode

JS8 reprend la modulation de FT8 mais transporte du **texte libre** : messagerie clavier, relais entre stations, balises de présence. Un message long est découpé en plusieurs trames.

## 3.2 Réglages

- **Speed** — la vitesse JS8 écoutée. Toutes les stations d'un QSO utilisent la même ; **Normal** est la vitesse d'appel courante.

| Vitesse | Créneau |
| Normal | 15 s |
| Fast | 10 s |
| Turbo | 6 s |
| Slow | 30 s |
| Ultra | 4 s |

- **Fréquences connues** — 160 m 1 842,0 · 80 m 3 578,0 · 40 m 7 078,0 · 30 m 10 130,0 · 20 m 14 078,0 · 17 m 18 104,0 · 15 m 21 078,0 · 12 m 24 922,0 · 10 m 28 078,0 kHz.
- **Barre de progression** — avancement du créneau en cours.
- **Sync offset / Auto** — comme pour FT8 (section 2.4).
- **Clear** — efface les messages.

![Panneau JS8 : vitesse, progression du créneau et messages.](images/dec_js8.jpg){w=375}

## 3.3 Lire les messages

Chaque ligne porte le mode, le SNR et le message, avec l'**indicatif de l'émetteur mis en valeur**. Un message en cours de réception s'affiche **au fur et à mesure**, suivi d'un curseur ▌, avant d'être complété par les trames suivantes. Si la dernière trame n'arrive pas, la ligne le signale (délai dépassé).

> [Astuce] « Listening on the Normal cycle… » indique que le décodeur attend. Sur une bande calme, il peut se passer plusieurs minutes avant le premier message.

# 4. CW (télégraphie Morse)

## 4.1 Fonctionnement

Le décodeur CW **trouve seul la tonalité** du signal dans la bande passante et **mesure seul la vitesse**. Il suit les vitesses d'environ **5 à 65 mots par minute**.

- **≈ … Hz** — fréquence audio de la note décodée.
- **· … WPM** — vitesse mesurée.
- **scanning…** — aucune note n'est encore accrochée.
- Le texte s'écrit en continu ; une ligne **───** marque un silence (fin d'émission).
- **Clear** efface le texte.

![Panneau CW : note détectée, vitesse et texte décodé.](images/dec_cw.jpg){w=375}

## 4.2 Bien régler la réception

1. Écoutez en mode **CW** avec un filtre étroit (300 à 500 Hz).
2. Placez **un seul signal** dans la bande passante : deux notes simultanées font perdre la synchronisation.
3. Patientez quelques caractères, le temps que la vitesse soit mesurée.

## 4.3 Stations CW régulières

Sous le texte décodé, un tableau rappelle les **émissions CW programmées** (heure de Paris, changement d'heure pris en compte), avec un bouton pour s'accorder directement :

| Station | Fréquences | Horaires |
| FAV22 (Marine nationale) | 3 881 et 6 825 kHz | semaine 10 h 30–11 h et 13 h 30–14 h ; week-end 9 h–9 h 30 et 10 h 20–10 h 55 |
| F9TM | 3 536 kHz | jeudi à partir de 19 h 15 |

> [Astuce] Les émissions de FAV22 sont idéales pour s'entraîner : vitesse régulière et texte bien formé.

# 5. WSPR

## 5.1 Le mode

WSPR (« whisper ») est un mode de **balises de très faible puissance** servant à étudier la propagation. Chaque émission dure presque 2 minutes et commence au début d'une **minute UTC paire**. Le décodeur d'ORSAT reçoit le WSPR-2 classique.

## 5.2 Mise en route

1. Cliquez sur **WSPR**.
2. Choisissez une bande dans **Fréquences connues** :

| Bande | kHz | Bande | kHz |
| 2200 m | 136,0 | 30 m | 10 138,7 |
| 630 m | 474,2 | 20 m | 14 095,6 |
| 160 m | 1 836,6 | 17 m | 18 104,6 |
| 80 m | 3 568,6 | 15 m | 21 094,6 |
| 80 m EU | 3 592,6 | 12 m | 24 924,6 |
| 60 m | 5 287,2 | 10 m | 28 124,6 |
| 40 m | 7 038,6 | | |

3. Attendez : « Waiting for next even UTC minute slot… » s'affiche jusqu'au début du prochain créneau, puis la barre de progression avance pendant la réception. Les résultats tombent **à la fin** du créneau.

## 5.3 Lire le tableau

![Panneau WSPR : progression du créneau et balises décodées.](images/dec_wspr.jpg){w=375}

- **UTC** — heure du créneau ;
- **Callsign** et **Grid** — indicatif et locator de la balise ;
- **Power** — puissance déclarée (en dBm : 37 dBm = 5 W, 30 dBm = 1 W, 23 dBm = 200 mW) ;
- **Freq** — fréquence exacte de la balise ;
- **SNR** — rapport signal/bruit (WSPR décode jusqu'à −28 dB environ).

> [Astuce] Les boutons **WSPR log** et **WSPR map** de la rubrique « Liens externes » du menu Informations montrent les balises reçues par ORSAT sur les sites de référence.

# 6. FAX (fac-similé météo HF)

## 6.1 Le mode

Les stations météorologiques et militaires diffusent des **cartes météo** (analyses, prévisions, état de la mer, glaces) en fac-similé radio. Chaque image est précédée d'un signal de démarrage et de phasage, et terminée par un signal d'arrêt.

## 6.2 Choisir une station

- **Station** — choisissez une station dans la liste, puis une **Frequency**, et cliquez sur **▶ Tune**.

| Station | Fréquences (kHz) |
| GYA — Northwood (Royaume-Uni) | 2 618,5 · 4 610 · 8 040 · 11 086,5 |
| DDH3 / DDK6 — Hambourg (Allemagne) | 3 855 · 7 880 · 13 882,5 |
| SVJ4 — Athènes (Grèce) | 4 482,9 · 8 106,9 |
| RBW41 — Mourmansk (Russie) | 5 336 · 6 445,5 · 7 908,8 · 8 444 · 10 130 |
| HLL2 — Séoul (Corée du Sud) | 3 585 · 5 857,5 · 7 433,5 · 9 165 · 13 570 |
| JMH — Tokyo (Japon) | 3 622,5 · 7 795 · 13 988,5 |
| JFX — Kagoshima (Japon) | 4 274 · 8 658 · 13 074 · 16 907,5 · 22 559,6 |

- **Next Transmissions · UTC** — les prochaines émissions de la station choisie, avec un compte à rebours. Une émission **en cours** est signalée en vert (●), une émission **imminente** en rouge. Le lien **FAX transmission schedules** ouvre les grilles horaires complètes.

## 6.3 Réglages de l'image

| Réglage | Valeurs | Défaut |
| LPM (lignes par minute) | 100 · 120 · 240 | 120 |
| IOC (indice de coopération) | 288 · 576 | 576 |
| Shift (écart noir/blanc) | 400 Hz · 800 Hz | 800 Hz |

Les valeurs marquées ★ dans les menus sont la norme ; presque toutes les stations l'utilisent. La ligne d'information rappelle les fréquences du **noir** (1 500 Hz) et du **blanc** (2 300 Hz), la résolution en pixels par ligne et la durée d'une ligne.

- **⇔ Auto-align** — aligne automatiquement les lignes sur les impulsions de synchronisation : l'image ne penche plus.
- **⇅ Invert** — inverse le noir et le blanc (réception en LSB ou station à polarité inversée).

## 6.4 Pendant la réception

![Panneau FAX : station, horaires, réglages et image en cours de réception.](images/dec_fax.jpg){w=375}

- Les voyants **300 Hz phasing** et **450 Hz stop** s'allument pendant le phasage et le signal d'arrêt ; l'en-tête affiche **[PHASING]**, **[STOP]** et le nombre de lignes reçues (**Lines**).
- L'image se construit ligne par ligne, **les plus récentes en bas**.
- **↺ Reset** efface l'image et réinitialise le décodeur : à utiliser entre deux émissions ou si l'image se déchire.
- **⤓ Save PNG** enregistre l'image.

> [Astuce] Lancez le décodeur une ou deux minutes avant l'heure prévue : vous capterez le phasage et l'image démarrera bien calée.

# 7. SSTV (télévision à balayage lent)

## 7.1 Le mode

Les radioamateurs échangent des **images fixes** en SSTV ; la Station spatiale internationale en diffuse aussi lors d'événements ponctuels. Une image demande de 36 secondes à plusieurs minutes selon le mode.

## 7.2 Bande latérale

Par convention, la SSTV se pratique en **LSB sur 80 et 40 m** et en **USB à partir du 30 m**. Au démarrage, le décodeur choisit la bande latérale correspondante. Si une station ne suit pas la convention, changez la bande latérale à la main : ORSAT respecte votre choix. Sur la mauvaise bande latérale, rien ne se décode.

## 7.3 Réglages

- **Fréquences connues** — 80 m 3 730,0 (Europe) et 3 845,0 (Amériques) · 40 m 7 171,0 · 20 m 14 230,0 (principale) et 14 233,0 · 17 m 18 160,0 · 15 m 21 340,0 · 12 m 24 975,0 · 10 m 28 680,0 kHz.
- **Mode** — **Auto** (recommandé) reconnaît le mode grâce à l'en-tête VIS envoyé au début de chaque image. On peut aussi imposer : Martin M1, Martin M2, Scottie S1, Scottie S2, Scottie DX, Robot 36, Robot 72.
- **▶ Start** / **■ Stop** — démarre ou arrête la réception.
- **↺ Reset** — efface l'image.
- **⏺ Force** — démarre le décodage tout de suite dans le mode choisi, sans attendre l'en-tête VIS. Utile quand on arrive au milieu d'une image. Ne fonctionne pas en mode Auto.
- **💾 Save** — enregistre l'image.

## 7.4 Indicateurs

![Panneau SSTV : mode détecté, état de la synchro et image reçue.](images/dec_sstv.jpg){w=375}

- **[mode détecté]** — par exemple [Martin M1].
- **hard sync lock** — synchronisation franche sur les impulsions de ligne ; **soft sync hold** — synchro maintenue malgré un signal faible.
- **Running / Stopped** et **Lines** — état et nombre de lignes reçues sur le total de l'image.

> [Astuce] Une image penchée vient d'un mauvais calage de synchro ; une image aux couleurs fausses, d'un mauvais mode ou d'une mauvaise bande latérale.

# 8. NAVTEX

## 8.1 Le mode

Le NAVTEX diffuse aux navires les **avis aux navigateurs**, la météo marine et les alertes de détresse. Chaque station côtière a une **lettre d'identification** (A à Z) et des créneaux d'émission de 10 minutes, répétés toutes les 4 heures. Transmission : FSK 100 bauds, écart de 170 Hz, code SITOR-B.

- **518 kHz** — NAVTEX international, en anglais ;
- **490 kHz** — NAVTEX national, en langue du pays.

## 8.2 Mise en route

1. Cliquez sur **NAVTX** : le récepteur passe en USB.
2. Choisissez une station et cliquez sur **⇒ Tune & Set IF** : le récepteur s'accorde 500 Hz sous le canal (le signal tombe à 500 Hz audio) et le filtre FI se règle.
3. L'en-tête indique « waiting for phasing… » jusqu'à ce qu'une émission commence.

## 8.3 Le tableau des diffusions

![Panneau NAVTEX : prochaines diffusions et messages reçus.](images/dec_navtex.jpg){w=375}

**Next Broadcasts · UTC** liste les stations dans l'ordre de leurs prochaines émissions : drapeau, lettre d'identification, nom, zone, heure UTC et compte à rebours. La station **en cours d'émission** est signalée en vert, la suivante en rouge quand elle est imminente.

- Un bouton permet d'**armer le décodeur immédiatement**, sans attendre le phasage.
- **NAVTEX Maps Stations** ouvre la carte des stations.
- **Clear** et **Save Text** effacent ou enregistrent le texte reçu.

> [Astuce] La nuit, le 518 kHz porte loin : on capte régulièrement des stations de toute l'Europe de l'Ouest et de la Méditerranée.

# 9. HFDL (HF Data Link)

## 9.1 Le mode

Les avions en vol au-dessus des océans échangent des messages **ACARS** avec des stations sol HF réparties dans le monde. Le décodeur d'ORSAT est **dumphfdl**, compilé pour fonctionner dans votre navigateur.

## 9.2 Réglages et lecture

![Récepteur HFDL : station sol, indicateurs et messages.](images/fr_p22_0.jpg){w=204,side}
- **Station sol** — Shannon, Reykjavik, Canarias, Riverhead, Johannesburg… puis une de ses fréquences et **Accorder & régler la FI**.
- **Dial** — signale si vous êtes hors d'une fréquence HFDL.
- **Bruit**, **Trames**, **Rythme** — qualité de la réception.
- **Messages** et **Squitters** — compteurs ; cochez **Squitters** pour afficher aussi les balises des stations sol.
- Survolez un message pour voir la trame complète ; **Enregistrer** et **Effacer** gèrent le journal.

**Identifiants cliquables.** Le **numéro de vol**, l'**immatriculation** et le **code ICAO** de l'avion ouvrent sa fiche FlightAware dans un nouvel onglet.

**Carte des avions.** **🗺 Carte** affiche les avions dont une position a été reçue ; **⤢ Grand format** l'ouvre dans une fenêtre flottante ; **⌖ Tout voir** recadre sur tous les avions. Chaque avion est dessiné orienté selon son cap, avec sa trace en rouge ; un clic ouvre sa fiche FlightAware.

> [Astuce] Les stations sol émettent un squitter toutes les 32 s. Choisissez une fréquence où la propagation est ouverte vers la station, et patientez quelques minutes : seuls certains messages contiennent une position.

# 10. FLDIGI : RTTY, SITOR, PSK, Olivia et les autres

## 10.1 Un décodeur, quatorze variantes

Le bouton **FLDIGI** ouvre un décodeur unique qui reprend les modes du logiciel fldigi. Le menu **Variant** choisit la famille ; le titre du panneau change en conséquence (FSK / RTTY, PSK31, Olivia, Packet, APRS…).

| Variante | Usage |
| Maritime FSK / SITOR | NAVTEX, avis maritimes SITOR, NBDP |
| Weather RTTY | Bulletins météo en RTTY (DWD) |
| Amateur RTTY | RTTY radioamateur |
| PSK31 (BPSK) | Conversation clavier radioamateur |
| Olivia | Texte très robuste en conditions difficiles |
| MFSK16 · 32 · 64 | Texte robuste, bonne tenue au fading |
| DominoEX | Texte, résiste à la dérive et aux trajets multiples |
| THOR | DominoEX avec correction d'erreurs |
| THROB / THROBX | Mode lent à tonalités multiples |
| Hellschreiber | Texte transmis comme une image (fac-similé de caractères) |
| MT63 | Mode large et très robuste, souvent utilisé en urgence |
| Packet (AX.25) | Trafic packet radio |
| APRS | Positions et messages APRS |

> [Astuce] Pendant son fonctionnement, ce décodeur prend le contrôle du mode et du filtre FI. Choisissez d'abord une fréquence connue, puis affinez l'accord jusqu'à ce que le texte se stabilise.

## 10.2 Les commandes communes

![Décodeur FLDIGI, variante FSK maritime / SITOR.](images/fr_p21_1.jpg){w=204,side}
- **Known frequency** puis **Tune** — accorde sur une fréquence de référence de la variante.
- **Next Broadcasts · UTC** — horaires des diffusions pour les variantes qui en ont (stations NAVTEX, DWD).
- **⇒ Set IF Band-Pass** — règle le filtre FI sur la largeur du mode.
- **⟳ Auto-tune Center** — cherche le signal et recentre le décodeur dessus.
- **Clear** — efface le texte ; un bouton permet d'**enregistrer le texte**.
- L'en-tête affiche l'état du décodeur ; « waiting for lock… » tant qu'aucun signal n'est accroché.

## 10.3 RTTY et SITOR (FSK)

Les trois variantes FSK partagent les mêmes réglages :

- **Center audio (Hz)** — fréquence audio du centre du signal.
- **Shift (Hz)** — écart entre les deux tonalités mark et space.
- **Baud** — vitesse.
- **Framing** — 5N1, 5N1.5, 5N2, 7N1, 7E1, 7O1, 8N1.
- **Encoding** — CCIR-476 (SITOR), ITA2 / Baudot (RTTY), ASCII.
- **Invert mark / space** — inverse les deux tonalités.
- **Auto shift detect** — mesure l'écart automatiquement.
- **Squelch (SNR)** — bloque l'affichage du bruit. Le bruit seul se lit vers −12 à −15 dB ; le RTTY reste lisible jusqu'à environ −4 dB. Curseur tout à gauche : squelch coupé (« off »).

| Variante | Centre | Shift | Baud | Code | Inverser |
| Maritime FSK / SITOR | 500 Hz | 170 Hz | 100 | CCIR-476, 7N1 | non |
| Weather RTTY | 1 000 Hz | 450 Hz | 50 | ITA2, 5N1.5 | **oui** |
| Amateur RTTY | 1 000 Hz | 170 Hz | 45,45 | ITA2, 5N1.5 | non |

Indicateurs : **Mark** et **Space** (fréquences mesurées des deux tonalités), **Tones**, **SNR**, **Verrou** et **Timing**.

**Fréquences connues :**

- *Maritime* — 518 kHz (NAVTEX international), 490 kHz (NAVTEX national), 2 174,5 kHz (NBDP), 4 209,5 kHz (NAVTEX HF), SITOR MSI sur 4 210, 6 314, 8 416,5, 12 579, 16 806,5, 19 680,5, 22 376 et 26 100,5 kHz.
- *Weather* — DWD Pinneberg : 4 583 (DDK2), 7 646 (DDH7), 10 100,8 (DDK9), 11 039 (DDH9), 14 467,3 (DDH8) et 147,3 kHz (DDH47, en ondes longues, écart de 85 Hz).
- *Amateur* — RTTY sur 3 590, 7 043, 10 143, 14 083, 21 083 et 28 083 kHz.

> [Astuce] Le RTTY météo du DWD arrive avec la tonalité mark en bas : laissez **Invert** coché. Pour le RTTY amateur et le SITOR, laissez-le décoché.

## 10.4 PSK31

- **Center audio** — placez le décodeur sur la trace du signal (un trait fin de 31 Hz de large sur la cascade), ou utilisez **⟳ Auto-tune Center**.
- Indicateurs : **Carrier** (fréquence de la porteuse), **IMD** (qualité de l'émission : −25 dB ou moins est propre, au-delà de −20 dB l'émetteur est saturé), **DCD** (● quand un signal est détecté), **Audio** (niveau).
- Fréquences connues : 3 580,15 · 7 040,15 · 10 142,15 · 14 070,15 · 18 100,15 · 21 080,15 · 24 920,15 · 28 120,15 kHz.

## 10.5 Olivia

- **Mode** — nombre de tonalités / largeur : 8/250, 16/500, 32/1000, 16/1000. Il faut le même que la station écoutée.
- **Squelch (FEC S/N)** — en dessous de 3,5 le bruit commence à s'afficher ; un bon signal se lit 8 à 9.
- Fréquences connues : 20 m 14 072,5 (8/250) et 14 108,5 (32/1000), 80 m 3 583, 40 m 7 040 et 7 072,5, 12 m 24 922,5, 10 m 28 122,5 kHz…

## 10.6 MFSK, DominoEX, THOR, THROB, Hellschreiber, MT63

Ces modes ont tous deux réglages : un **Mode** (sous-mode, à choisir comme la station écoutée) et un **Squelch** propre à chaque famille. Les indicateurs **Centre**, **Mode** et **Audio** suivent la réception.

| Variante | Sous-modes | Défaut |
| MFSK | MFSK16, MFSK32, MFSK64 | MFSK16 |
| DominoEX | Micro, 4, 5, 8, 11, 16, 22, 44, 88 | DominoEX 11 |
| THOR | Micro, 4, 5, 8, 11, 16, 22, 25 x4, 50 x1, 50 x2, 100 | THOR 16 |
| THROB | THROB 1, 2, 4 · THROBX 1, 2, 4 | THROB 2 |
| Hellschreiber | Feld Hell, Slow Hell, Hell X5, Hell X9, FSK Hell 245, FSK Hell 105, Hell 80 | Feld Hell |
| MT63 | 500, 1000, 2000 (entrelacement court ou long) | MT63-1000 long |

> [Astuce] En Hellschreiber, le texte n'est pas décodé mais **dessiné** : on le lit à l'œil, comme un ruban. Un texte en double hauteur est normal.

## 10.7 Packet et APRS

- **Speed** — 1 200 bauds (VHF) ou 300 bauds (HF) ; tonalités 1 200 / 2 200 Hz en VHF.
- **Show raw packet** — affiche aussi la trame brute AX.25.
- Indicateurs : **Frames** (trames valides reçues), **Stations** (nombre de stations différentes), **DCD**, **Audio**.
- En APRS, les stations qui envoient une position peuvent être **affichées sur la carte**.
- Fréquences connues : 144,800 MHz (APRS Europe), 144,390 (Amérique du Nord), 145,175 (Australie), 144,640 (Chine), 144,660 (Japon), 145,825 MHz (digipeater de l'ISS) et 10 147,6 kHz (APRS HF, 300 bauds).

> [Astuce] Les fréquences VHF ne sont utilisables que si le récepteur d'ORSAT couvre la bande des 2 m.

# 11. RADE (FreeDV, voix numérique)

RADE v1 est le mode vocal numérique de FreeDV, à base de réseau neuronal. Il ne se lance pas depuis la rangée des décodeurs mais depuis les boutons **RADEL** (LSB, pour 160, 80 et 40 m) et **RADEU** (USB, pour 20, 17, 15 et 10 m) du sélecteur de modes. Le décodage est fait **sur le serveur**.

- Voyant **vert** : synchronisé, avec le SNR ; **jaune** : recherche d'un signal ; **rouge** : service de décodage injoignable sur le serveur.
- Bande passante : 1 500 Hz ; la voix est reconstituée par le vocodeur FARGAN.
- **📡 FreeDV Reporter** affiche la liste des stations FreeDV actives dans le monde (qso.freedv.org).

# 12. Aides à l'identification

## 12.1 Analyse des signaux numériques

Le module, placé en tête de la rangée des décodeurs, **tente de reconnaître le mode** du signal écouté (FT8, WSPR, RTTY, PSK, Olivia, CW…) et propose le décodeur adapté. Cette fonction est **expérimentale**.

![Module « Analyse des signaux numériques ».](images/new_analyse.jpg){w=380}

- **Analyse automatique : OFF / ON** — le mode est en général reconnu en une quinzaine de secondes.
- **Mesure en cours** — largeur, écart entre tonalités, vitesse, cadence, rapport signal/bruit.
- **Modes reconnus, par pertinence** — **▶ Lancer** ouvre le décodeur correspondant (avec ses réglages), l'icône **i** affiche la fiche du mode.
- **Recentrer & réessayer** — apparaît quand le signal est trop près du bord du filtre.

## 12.2 Identifier un signal (base Artemis)

**📚 Chercher dans la base de signaux** recherche parmi **583 signaux de référence** ce qui correspond à la fréquence, à la largeur du filtre et à la démodulation en cours, classés par pourcentage de correspondance. Chaque fiche donne un spectrogramme, un **échantillon audio** à comparer, la modulation, la plage de fréquences et un lien vers le Signal Identification Wiki.

![Fenêtre « Identifier un signal ».](images/new_identifier.jpg){w=440}

# 13. Dépannage

| Symptôme | Cause probable | Remède |
| Aucun décodage FT8 / FT4 / WSPR | Mauvaise fréquence ou bande fermée | Passez par **Fréquences connues** ; vérifiez sur la cascade que des signaux sont présents |
| Décodages FT8 rares, DT dispersés | Synchro horaire | Cochez **Auto** à côté de Sync offset |
| CW illisible | Plusieurs signaux dans le filtre | Filtre CW étroit, un seul signal |
| Image FAX penchée | Synchro de ligne | **⇔ Auto-align** |
| Image FAX en négatif | Polarité | **⇅ Invert** |
| SSTV : couleurs fausses ou rien | Mauvaise bande latérale ou mauvais mode | Changez de bande latérale ; essayez un mode imposé puis **⏺ Force** |
| NAVTEX muet | Hors créneau | Attendez le créneau de la station (tableau des diffusions) |
| RTTY : caractères aléatoires | Mark / space inversés | Cochez ou décochez **Invert mark / space** |
| RTTY : rien ne s'affiche | Squelch trop haut | Baissez le **Squelch** |
| PSK31 / Olivia : texte haché | Décodeur décentré | **⟳ Auto-tune Center** |
| HFDL : aucun message | Propagation vers la station sol | Essayez une autre fréquence ou une autre station |
| RADE : voyant rouge | Service serveur arrêté | Prévenez l'administrateur d'ORSAT |

> [Astuce] Pour tout décodeur, vérifiez d'abord à l'oreille et sur la cascade qu'un signal est bien présent et bien centré : la plupart des échecs viennent d'un accord approximatif.
