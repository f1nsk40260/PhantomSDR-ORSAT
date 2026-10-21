# Journal des versions — PhantomSDR-ORSAT

PhantomSDR-ORSAT est la version francophone de F1NSK, construite sur
[PhantomSDR-Plus](https://github.com/sv1btl/PhantomSDR-Plus) de SV1BTL.
Ce journal ne liste que les apports d'ORSAT ; les nouveautés de la base sont
décrites dans le README et dans le projet original.

## En cours (après ORSAT 1.0)

### Interface
- **Carte APRS** : fond de carte au choix à la souris (Nuit, Satellite, Plan OSM sombre, Plan OSM), sans clé d'API ; le choix est retenu par le navigateur. « Nuit » par défaut, dans l'esprit ORSAT.

### Outils
- **Carnet ORSAT-LOG, carte QRZ** : « Compléter les locators » — les QSO enregistrés sans locator le reçoivent depuis l'annuaire QRZ (distance et azimut recalculés), avec l'avancement.
- **Correctif carte QRZ (panneau admin)** : le navigateur prenait l'identifiant + mot de passe QRZ.com pour la connexion au panneau et proposait de remplacer le mot de passe enregistré du site. Plus de formulaire ni de champ « mot de passe » dans cette carte (saisie masquée autrement).
- **Carnet ORSAT-LOG → annuaire QRZ** : identifiant et mot de passe QRZ.com dans la carte QRZ (vérifiés avant enregistrement), pour la photo, le nom et le QTH des correspondants dans la fiche QSO.
- **Autorun → carnet ORSAT-LOG** : chaque station décodée par l'autorun (FT8, FT4, JS8, WSPR) est aussi écrite dans `autorun-spots/` (un fichier par heure), que l'envoi vers PSK Reporter / WSPRnet soit activé ou non. Le carnet en fait des observations de propagation et efface les fichiers lus ; sans carnet, ils sont effacés au bout de 3 jours. Rubrique Carnet ORSAT-LOG : indicateur « Entendu (autorun) ».
- **Carnet ORSAT-LOG ↔ QRZ.com** : carte « Synchronisation QRZ.com » dans la rubrique Carnet ORSAT-LOG, avec la clé du logbook QRZ, la synchronisation automatique, le bouton « synchroniser maintenant » et le journal.
- **Panneau admin → rubrique « Carnet ORSAT-LOG »** : un seul centre de gestion pour le WebSDR et le carnet. On y trouve l'état du service, les réglages du carnet (indicatif, locators station / WebSDR, TCI, météo), ses sauvegardes et sa restauration, et sa mise à jour en un clic, sans couper le WebSDR. Le service apparaît aussi dans « Santé du serveur ».
- **CAT Sync ↔ carnet ORSAT-LOG** : si le navigateur a une session ouverte au carnet (`/log/`), la page l'ajoute à ses sources TCI. Le carnet suit alors la fréquence et le mode écoutés, et peut recaler la page. Les autres auditeurs ne voient aucune différence.
- **Carnet ORSAT-LOG sous `/log`** : `proxy.py` relaie `/log` vers le carnet de trafic ORSAT-LOG (serveur central, port `log_port` de `admin_config.json`), comme `/admin` vers le panneau. Sans `log_port`, rien ne change.
- **Serveur TCI local** (`tci-bridge/orsat-tci-server.py`) : fait voir le WebSDR comme un récepteur TCI sur `ws://127.0.0.1:40001`. Il expose la fréquence et le mode (dans les deux sens), le filtre, l'audio RX et le S-mètre, pour ORSAT-LOG, Log4OM, WSJT-X ou Décodium. Il tourne sur le PC de l'auditeur et se connecte comme un navigateur : aucune modification du serveur. Voir `tci-bridge/README.md`.

## ORSAT 1.0 — 20 octobre 2026 (base PhantomSDR-Plus 5.1.0)

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
- Zoom automatique de la cascade sur la station quand la mesure l'exige (une fois par station).
- Référence **ESSB** : le filtre FI s'élargit à 50–4000 Hz pendant l'analyse, filtre d'origine rétabli ensuite.
- Trait de base renforcé, avec l'étiquette « bande opposée » ; bouton **✕ Fermer** à côté de « Couper le son ».
- **Bilan audio SSB** : équilibre tonal (graves, présence) selon une référence SSB standard / DX / ESSB, compression, ronflette secteur, porteuse résiduelle, bande opposée, largeur occupée ; courbe « voix moyenne », comparaison A/B et rapport d'écoute copiable.

### Interface desktop
- Colonne centrale : barre VFO / Modes / Bandes / Filtres juste sous le S-mètre, réception en diversité plus bas.
- Panneau Infos : bandeau d'ouverture à pulsation lente et texte lumineux, bouton « Fermer les fenêtres » en or plein, boutons hamdash et DX cluster plus visibles, contenu centré.
- Logo ORSAT : icônes du navigateur (onglet, écran d'accueil des téléphones), bandeau du README, images pour Facebook (`docs/branding/`).
- Copie de l'interface mobile retirée d'App.svelte (−4 400 lignes) : ORSAT vise les PC et tablettes ; les téléphones sont dirigés vers /mobile.

### Décodeurs
- Décodeur **HFDL** (messages ACARS des avions en ondes courtes), à partir de dumphfdl compilé en WebAssembly ; liens FlightAware, carte des avions en grand format (icônes orientées selon le cap, trace rouge).
- Menus de **fréquences connues** pour FT8/FT4/FT2, JS8, WSPR et SSTV ; **carte des stations** entendues (d'après leur locator) pour FT8/FT4/FT2, WSPR et JS8.
- SSTV : les fréquences connues accordent en LSB sur 80/40 m, comme le décodeur.
- CW : vitesse (WPM) affichée en grand, en vert fluo.

### Panneau d'administration
- Carte des auditeurs (tuiles Esri), analyse du niveau de danger des connexions, journal vidable, liste de bannissement complète (plages CIDR, ajout en masse, filtre, export).

### Documentation
- Quatre guides PDF en français, anglais et espagnol, accessibles depuis le menu Informations : **guide général d'utilisation**, **guide des décodeurs**, **guide de l'analyseur audio** et **guide de la réception en diversité**.
- README réécrit pour ORSAT : nouvelle page de garde (décodeurs, identification, analyseur, guides), Ubuntu 26.04 validé en production.

### Nettoyage du dépôt
- Retrait du code mort `frontend/src/unused/` et des fichiers produits localement (`frontend/stats.html`, `rade_loadtest.csv`), désormais ignorés par git.
- Captures d'écran du README compressées.
