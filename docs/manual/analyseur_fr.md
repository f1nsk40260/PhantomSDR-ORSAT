---
pdf: guideAnalyseurFR.pdf
pdf_title: PhantomSDR-ORSAT — Guide de l'analyseur audio
title: Analyseur audio ORSAT
subtitle: Guide détaillé — spectre, bilan de modulation SSB et rapport d'écoute
url: https://orsat.ddns.net
cover: analyseur_usb.jpg
cover_caption: L'analyseur audio en USB : spectre, balises de largeur, voix moyenne et bilan de modulation.
summary: Ce guide explique comment lire l'analyseur audio d'ORSAT, juger la modulation d'une station (équilibre tonal, compression, ronflette, porteuse, bande opposée, splatter), comparer deux réglages et envoyer un rapport d'écoute avec un extrait sonore.
edition: Version française — Édition octobre 2026 — ORSAT 1.0
credits: Module développé par **F1NSK** pour ORSAT, sur la base de PhantomSDR-Plus de **SV1BTL**.
header_left: ORSAT — Guide de l'analyseur audio
header_right: ORSAT 1.0
page: Page
toc: Sommaire
---

# 1. Présentation

L'**analyseur audio** montre et mesure le signal de la station que vous écoutez. Il sert à deux choses :

- **voir** le signal : spectre audio, fréquence de base, largeur de bande, filtre du récepteur ;
- **juger** une modulation SSB : un bilan chiffré, critère par critère, avec un verdict en clair et un rapport à envoyer au correspondant.

Il se trouve dans la colonne de droite de l'interface, sous le titre **ANALYSEUR AUDIO**. Le bouton **📊 Show** l'ouvre au-dessus des panneaux, **📊 Hide** le referme. Le curseur **Gain** règle seulement la hauteur de l'affichage.

## 1.1 Un analyseur qui travaille sur l'audio brut

L'analyseur reçoit le son du récepteur **avant** tous les traitements d'écoute : muet, squelch, AGC du navigateur, réduction de bruit, notch, égaliseur. Deux conséquences :

- vos réglages d'écoute ne faussent pas les mesures : on juge la station, pas votre confort d'écoute ;
- l'analyseur **continue de fonctionner quand le son est coupé**.

> [Remarque] Le seul traitement qui reste visible est le **filtre de réception**, appliqué par le serveur avant l'envoi du son. L'analyseur l'affiche et en tient compte.

## 1.2 Un affichage qui s'adapte au mode

| Mode | Ce que montre l'analyseur |
| USB, LSB | Spectre audio, balises SSB et ESSB, bilan audio SSB complet |
| CW | Spectre audio centré sur la note de 750 Hz, balises de largeur CW |
| AM, FM | Vue RF : porteuse au centre, bandes latérales de part et d'autre |

# 2. Prise en main rapide

1. Accordez la station et choisissez le mode (USB ou LSB pour un bilan complet).
2. Dans la colonne de droite, cliquez sur **📊 Show** sous **ANALYSEUR AUDIO**.
3. Zoomez la cascade sur la station : la largeur occupée, la porteuse et la bande opposée se mesurent sur la cascade, qui doit être assez fine.
4. Laissez la station parler : les verdicts du bilan apparaissent après **3 secondes de voix**.
5. Pour envoyer le résultat, cliquez sur **🎧 Générer un rapport d'écoute**.

> [Astuce] Pour analyser **votre propre émission**, écoutez-vous sur ORSAT et cliquez sur **Couper le son** dans le bandeau : rien ne repart dans votre micro, et l'analyse continue.

# 3. Le bandeau « Fréquence de base »

En haut de l'analyseur, un bandeau rappelle :

- la **fréquence de base**, celle du cadran, en grands chiffres ;
- le **mode** dans une pastille dorée ;
- une courte explication : « 0 Hz audio = porteuse » en USB, l'axe inversé en LSB, la note à 750 Hz en CW, la vue RF en AM et FM.

À droite, le bouton **🔊 Couper le son** coupe le son du récepteur. Il passe en rouge, **🔇 Son coupé**, tant que le son est coupé. C'est le même réglage que le bouton muet du récepteur : les deux restent synchronisés. Si le son a été coupé depuis ce bouton, il **revient automatiquement à la fermeture de l'analyseur**.

# 4. Lire le spectre en USB

![Spectre audio en USB avec la lecture au survol, les balises SSB et ESSB, le filtre actuel et la courbe de voix moyenne.](images/analyseur_usb.jpg){w=482}

- **Axe horizontal** : fréquence audio, de 0 à 4,5 kHz. **Axe vertical** : niveau en dB.
- **Remplissage coloré** : le spectre instantané. **Ligne claire** : la crête, qui retombe lentement.
- **Trait or « Base »** : la fréquence de base, à 0 Hz audio, c'est-à-dire la porteuse supprimée de la station.
- **Balises** : **SSB standard 300–2700 Hz** (or) et **ESSB 50–4000 Hz** (bleu, en tirets).
- **Cadre en pointillés blancs** : le **filtre actuel** du récepteur, avec ses limites en bas à droite.
- **Courbe bleue « voix moyenne »** : la forme moyenne de la voix sur les dernières secondes, calculée par le bilan SSB.
- **Survol de la souris** : une bulle donne la **fréquence RF exacte** du point visé et sa fréquence audio.

Sous le spectre, une ligne donne la **largeur occupée** mesurée et son verdict (voir le chapitre 7).

# 5. LSB et CW

## 5.1 LSB : l'axe est inversé

![En LSB, les aigus sont à gauche et la porteuse à droite, comme sur la cascade.](images/analyseur_lsb.jpg){w=482}

En LSB, la voix est sous la porteuse. Pour que l'analyseur se lise dans le même sens que la cascade, l'axe est **inversé** : la fréquence de base (0 Hz audio) est à droite et les aigus à gauche. Les mesures et le bilan sont identiques à l'USB.

## 5.2 CW

![En CW, l'axe va de 0 à 2 kHz et le trait or marque la note à 750 Hz.](images/analyseur_cw.jpg){w=482}

En CW, l'axe va de 0 à 2 kHz. Le trait or marque la **note à 750 Hz**, qui correspond à la fréquence du cadran. Les balises **CW 500 Hz** et **CW 250 Hz** montrent les filtres usuels. La largeur occupée sert à repérer les **clics de manipulation** : une émission CW propre reste sous 300 Hz à −26 dB.

# 6. AM et FM : la vue RF

![En AM, la porteuse est au centre et les deux bandes latérales s'étendent de part et d'autre.](images/analyseur_am.jpg){w=482}

En AM et en FM, le son démodulé ne contient plus la porteuse. Elle passe à 0 Hz et les deux bandes latérales se superposent. L'analyseur bascule donc **automatiquement** sur une **vue RF**, prise sur la cascade :

- **la porteuse au centre** (trait or), les bandes latérales à gauche et à droite ;
- un axe gradué en **écart à la porteuse** (−6k … 0 … +6k) et un niveau en **dB au-dessus du bruit** ;
- des balises symétriques : AM radiodiffusion **±4,5 kHz** et AM radioamateur **±3 kHz**, FM étroite **±5,5 kHz** (largeur de Carson), FM large **±100 kHz** ;
- le filtre actuel, symétrique, et le splatter éventuel des deux côtés.

Largeur affichée : ±6 kHz en AM, ±8 kHz en FM, ±120 kHz en FM large. La symétrie des bandes latérales et le niveau de porteuse se lisent d'un coup d'œil.

> [Astuce] La vue RF a besoin d'une cascade fine : au moins 50 points sur la largeur affichée, soit 240 Hz par point au maximum en AM. Sinon, l'analyseur affiche « Zoomez sur la station dans la cascade pour la vue RF ».

# 7. Largeur occupée et splatter

![Une station trop large : le débordement est coloré en rouge et la ligne d'état signale un splatter probable.](images/analyseur_splat.jpg){w=482}

L'analyseur mesure sur la cascade la **largeur occupée** par la station : la largeur où son spectre dépasse le niveau situé 26 dB sous sa crête (méthode usuelle des normes d'émission). La mesure :

- porte sur 6 secondes et retient une largeur que 80 % des mesures ne dépassent pas : un pic isolé ne compte pas ;
- ignore les traces soulevées par un **parasite statique** ;
- attend 2 secondes de mesures avant de donner un verdict.

| Mode | Conforme | Un peu large | Splatter probable |
| SSB | jusqu'à 3,3 kHz | jusqu'à 5 kHz | au-delà de 5 kHz |
| AM | jusqu'à 10 kHz | jusqu'à 12 kHz | au-delà de 12 kHz |
| CW | jusqu'à 0,3 kHz | jusqu'à 0,6 kHz | au-delà (clics de manipulation) |

Sur le spectre, la partie qui déborde est teintée en **ambre** (un peu large) ou en **rouge** (splatter).

# 8. Le bilan audio SSB

En USB et LSB, l'encadré **BILAN AUDIO SSB** analyse la modulation sur les **20 dernières secondes**, et **seulement pendant que la station parle**. Les verdicts apparaissent après 3 s de voix. Chaque ligne porte un voyant : **vert** (bon), **orange** (à surveiller), **rouge** (défaut), **gris** (non mesurable, avec la raison).

## 8.1 Les critères

| Critère | Ce qui est mesuré | Vert | Orange | Rouge |
| Graves 100–300 Hz | Énergie des graves par rapport au médium (300–1500 Hz), comparée à la référence | écart ≤ 4 dB | écart ≤ 8 dB | au-delà |
| Présence 1,5–2,7 kHz | Énergie de la présence par rapport au médium | écart ≤ 4 dB | écart ≤ 8 dB | au-delà |
| Compression | Rapport crête / moyenne de la voix | 10 à 15 dB | plus de 15 dB | moins de 10 dB |
| Ronflette secteur | Raies stables à 50/100/150 Hz ou 60/120/180 Hz | absente | — | détectée |
| Porteuse résiduelle | Niveau de la porteuse sous les crêtes de voix | ≥ 40 dB | 30 à 40 dB | < 30 dB |
| Bande opposée | Énergie de l'autre bande latérale | ≥ 40 dB | 30 à 40 dB | < 30 dB |
| Largeur occupée | Mesure du chapitre 7 | conforme | un peu large | splatter |

**Comment lire les verdicts :**

- **Graves** : « trop de basses » donne une voix sourde et gaspille de la puissance ; « manque de graves » donne une voix fine.
- **Présence** : « manque de présence » donne une voix étouffée, peu lisible en DX ; « trop d'aigus » donne une voix criarde.
- **Compression** : « peu ou pas compressé » est naturel mais perce moins ; « très compressé, écrêtage probable » signale un compresseur poussé trop loin, avec souvent un bruit de fond qui pompe dans les pauses.
- **Ronflette** : un défaut de masse ou d'alimentation chez le correspondant.
- **Porteuse résiduelle** et **bande opposée** : mesurées sur la cascade, car le filtre de réception les cache dans l'audio. Une valeur précédée de « < » signifie que le défaut est sous le bruit : on sait seulement qu'il est au moins aussi bon que la valeur affichée. Si l'autre bande latérale est occupée par une autre station, l'analyseur le signale (QRM) au lieu d'accuser le correspondant.

## 8.2 La référence tonale

La rangée de boutons **Juger la voix par rapport à :**, en tête du bilan, choisit la courbe tonale à laquelle on compare la voix ; le bouton doré est la référence active :

| Référence | Graves / médium | Présence / médium | Pour quel usage |
| SSB standard | −13 dB | −10 dB | Trafic courant, filtre 300–2700 Hz |
| DX / punch | −16 dB | −6 dB | Présence renforcée pour percer dans le bruit |
| ESSB / hi-fi | −3 dB | −12 dB | Large bande, graves conservés |

Un même réglage peut donc être « équilibré » en ESSB et avoir « trop de basses » en DX : choisissez la référence qui correspond à ce que veut faire le correspondant.

## 8.3 Les parasites statiques

Les claquements de parasites (très brefs, à spectre plat) sont repérés et **écartés** du bilan. Les rapports graves et présence sont en outre calculés en **médiane** : un parasite qui échapperait au tri ne déplace pas le résultat. Quand plus de 10 % des mesures sont écartées, la ligne du bas affiche « Parasites écartés : xx % ».

# 9. Comparer avant / après : la courbe A

![Après « Mémoriser A », la courbe A (pointillés blancs) reste affichée ; la ligne du bas compare les graves et la présence.](images/analyseur_ab.jpg){w=482}

Pour aider un correspondant à régler son audio :

1. Laissez-le parler quelques secondes, puis cliquez sur **Mémoriser A** : la courbe de voix moyenne est figée en **pointillés blancs**.
2. Il modifie son égaliseur ou son compresseur. Cliquez sur **↺ Recommencer** pour repartir d'une mesure neuve.
3. La nouvelle courbe bleue se superpose à la courbe A. La ligne du bas donne l'évolution, par exemple « graves −21 dB → −12 dB ».

La courbe A est recalée sur le niveau du médium actuel : le fading change le niveau, pas la forme. **Effacer A** la retire.

# 10. Le rapport d'écoute

![Le rapport d'écoute s'ouvre dans n'importe quel navigateur, avec le son, le bilan et l'image du spectre.](images/analyseur_rapport.jpg){w=420}

Le bouton **🎧 Générer un rapport d'écoute** télécharge un fichier HTML autonome, par exemple « Rapport-ORSAT-14200,000kHz-USB-20261019-0934.html ». Il s'ouvre dans n'importe quel navigateur, sans connexion, et s'envoie par courriel. Il contient :

- la fréquence, le mode, la date et l'heure UTC, la référence tonale ;
- un **lecteur audio** avec les **20 dernières secondes** du son brut du récepteur, normalisé en niveau, et un lien pour télécharger ce son en WAV ;
- le tableau des verdicts avec leurs voyants ;
- la comparaison avec la courbe A, si elle existe ;
- une **image du spectre** au moment du rapport.

> [Remarque] Le fichier pèse environ 1 Mo. L'extrait est pris dans l'audio brut : ce que le correspondant entend ne dépend pas de vos réglages d'écoute.

# 11. Conseils pour des mesures fiables

- **Zoomez la cascade** sur la station : largeur occupée, porteuse, bande opposée et vue RF en dépendent.
- **Ouvrez le filtre de réception** : pour juger les graves, il doit descendre vers 120 Hz ; pour la présence, monter vers 2,6 kHz. Un filtre 100–2800 Hz convient.
- **Préférez une station au-dessus de 15 dB de rapport signal/bruit**. En dessous, le bilan affiche « Signal faible : fiabilité réduite ».
- **Le fading sélectif** déforme le spectre d'un instant à l'autre : la moyenne sur 20 s l'atténue, mais un bilan pris pendant un fort fading reste indicatif.
- **Comparez ce qui est comparable** : même référence tonale, même filtre, même zoom de cascade.

# 12. Messages et dépannage

| Message | Signification et remède |
| En attente de modulation… | Moins de 3 s de voix analysées : laissez la station parler. |
| Zoomez sur la station dans la cascade… | La cascade est trop large pour mesurer : zoomez sur la station. |
| non mesurable : le filtre RX coupe… | Le filtre de réception masque la zone mesurée : élargissez-le. |
| occupée par une autre station (QRM) | La bande opposée contient un autre signal : la mesure est impossible. |
| Signal faible : fiabilité réduite | Rapport signal/bruit inférieur à 15 dB. |
| Parasites écartés : xx % | La bande crépite : le bilan repose sur moins de voix. |
| Pas d'extrait sonore (rapport) | L'analyseur était ouvert depuis trop peu de temps : attendez quelques secondes. |
