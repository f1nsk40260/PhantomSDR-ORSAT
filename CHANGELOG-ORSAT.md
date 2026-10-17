# Journal des versions — PhantomSDR-ORSAT

PhantomSDR-ORSAT est la version francophone de F1NSK, construite sur
[PhantomSDR-Plus](https://github.com/sv1btl/PhantomSDR-Plus) de SV1BTL.
Ce journal ne liste que les apports d'ORSAT ; les nouveautés de la base sont
décrites dans le README et dans le projet original.

## ORSAT 1.0 — octobre 2026 (base PhantomSDR-Plus 5.1.0)

### Interface
- Interface intégralement traduite en français, anglais et espagnol, avec un sélecteur de langue à drapeaux dans l'en-tête.
- Thème « vieil or » homogène pour les boutons, titres de sections et liens ; infobulles en français sur tous les boutons.
- En-tête : ORSAT renvoie à la page QRZ de F1NSK, le locator à la carte du QTH.
- Panneau hamdash : propagation, météo spatiale, DX cluster, synchronisation du récepteur avec le DX cluster, liens GitHub, liens externes et manuels.
- Badge de version « ORSAT 1.0 · base 5.1.0 » dans le panneau d'informations.

### Analyse des signaux
- Module **Analyse des signaux numériques** : tente de reconnaître le mode écouté (FT8, RTTY, CW, PSK…) et propose le décodeur adapté. Analyse automatique désactivée par défaut. Expérimental.
- Fenêtre **Identifier un signal** : flottante, déplaçable et redimensionnable, avec ascenseurs larges ; recherche dans 583 signaux de référence d'[Artemis](https://github.com/AresValley/Artemis) / [Signal Identification Wiki](https://www.sigidwiki.com), filtre par catégorie, spectre, son de référence et description.

### Spectre et waterfall
- **Spectre 3D** (WebGL2) : les 128 dernières traces du spectre empilées en perspective douce, nappe de bruit éclairée, crêtes lissées ; suit zoom et glissement, reprend la palette de la cascade, échelle dB et repères de temps. Petit bouton « 3D » à côté du réglage automatique. Désactivé par défaut, masqué si le navigateur n'a pas WebGL2.
- Commandes du waterfall repensées : grand bouton « Réglage automatique » actif au démarrage, réglage manuel « Fond (bruit) / Signaux forts », menu déroulant des palettes avec aperçu, curseur de zoom retiré.
- Infobulles de l'AGC : usage conseillé selon le mode (CW, SSB, AM, numériques).

### Analyseur audio (ex-spectrogramme audio)
- Travaille sur l'audio brut du récepteur (avant muet, squelch, AGC, NR, notch, égaliseur) et fonctionne son coupé.
- Fréquence de base affichée en clair, trait or, lecture de la fréquence RF au survol ; axe inversé en LSB.
- Balises de largeur préconisée selon le mode (SSB standard, ESSB, CW, AM, FM) et filtre actuel.
- Mesure de la largeur occupée (−26 dB) sur la cascade et détection du splatter, parasites statiques ignorés.
- Vue RF automatique en AM et FM : porteuse au centre, bandes latérales de part et d'autre.
- **Bilan audio SSB** : équilibre tonal (graves, présence) selon une référence SSB standard / DX / ESSB, compression, ronflette secteur, porteuse résiduelle, bande opposée, largeur occupée ; courbe « voix moyenne », comparaison A/B et rapport d'écoute copiable.

### Interface desktop
- Copie de l'interface mobile retirée d'App.svelte (−4 400 lignes) : ORSAT vise les PC et tablettes ; les téléphones sont dirigés vers /mobile.

### Décodeurs
- Décodeur **HFDL** (messages ACARS des avions en ondes courtes), à partir de dumphfdl compilé en WebAssembly ; liens FlightAware, carte des avions en grand format (icônes orientées selon le cap, trace rouge).
- Menus de **fréquences connues** pour FT8/FT4/FT2, JS8, WSPR et SSTV ; **carte des stations** entendues (d'après leur locator) pour FT8/FT4/FT2, WSPR et JS8.

### Panneau d'administration
- Carte des auditeurs (tuiles Esri), analyse du niveau de danger des connexions, journal vidable, liste de bannissement complète (plages CIDR, ajout en masse, filtre, export).

### Documentation
- Mode d'emploi en PDF en français, anglais et espagnol, accessible depuis le menu.
- README réécrit pour ORSAT, avec captures du récepteur en service sur https://orsat.ddns.net.

### Nettoyage du dépôt
- Retrait du code mort `frontend/src/unused/` et des fichiers produits localement (`frontend/stats.html`, `rade_loadtest.csv`), désormais ignorés par git.
- Captures d'écran du README compressées.
