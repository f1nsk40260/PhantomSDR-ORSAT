# Journal des versions — PhantomSDR-ORSAT

PhantomSDR-ORSAT est la version francophone de F1NSK, construite sur
[PhantomSDR-Plus](https://github.com/sv1btl/PhantomSDR-Plus) de SV1BTL.
Ce journal ne liste que les apports d'ORSAT ; les nouveautés de la base sont
décrites dans le README et dans le projet original.

## En cours (après ORSAT 1.0)

### Interface
- **Panneau admin réorganisé** : menu à deux niveaux — 6 entrées (Tableau de bord · Le WebSDR · Auditeurs · Surveillance · Carnet ORSAT-LOG · Système), les pages de chaque groupe en onglets au-dessus du contenu ; un groupe rouvre sa dernière page consultée ; titre « GROUPE · PAGE ». Pastilles dans le menu : nombre d'auditeurs en ligne, alertes de Surveillance et du carnet (rouge / orange, détail au survol), relues chaque minute. Pages inchangées. Tableau de bord : encadré « À vérifier » avec des alertes cliquables (serveur radio, services en échec, certificat, disque, mémoire, plantage, carnet ORSAT-LOG) qui ouvrent la bonne page. Page Carnet ORSAT-LOG en onglets : État · Station · QRZ.com · Sauvegardes · Mise à jour.
- **Diversité réservée à la phonie** : disponible seulement en USB, LSB, AM, SAM, QUAM, FM et WBFM, et arrêtée dès qu'un décodeur démarre (bouton Démarrer grisé avec la raison). Aide « Comment ça marche ? » : mention de cette règle et, en gras, de l'augmentation de la latence de réception.
- **Panneau admin, Sécurité** : les cellules du tableau portaient deux attributs `style` (le second, avec les largeurs, était ignoré par le navigateur) — corrigé dans tout le panneau des auditeurs et de la sécurité. Tableau des IP suspectes : colonnes bornées (reverse DNS, lieu, chemins coupés proprement), 4 chemins affichés et les autres au survol, boutons « 24 H » / « DÉFINITIF » empilés et toujours visibles.
- **Manuels PDF mis à jour (FR / EN / ES)** : manuel utilisateur — nouveau § 3.3 bandeau « Indice de performance » (pastilles, zones, carte, explication, avertissement expérimental), § 5.1 bouton « COUPER L'AUDIO », § 8 réception en diversité réécrite (partenaires du sysop, badges de conseil), § 9 « Décodeurs » sans le scanner (sous-sections renumérotées 9.1 à 9.5), vignettes de la colonne centrale refaites. Guide de la diversité — utilisation, état, détails techniques, partenaire conseillé (calcul), partenaires proposés (relais http), dépannage réécrits. Guide des décodeurs — emplacement de la rangée corrigé. Anciennes vignettes devenues inutiles retirées.
- **Bouton « COUPER L'AUDIO »** : même taille, style adouci (vieil or patiné du bouton « Réglage automatique » du waterfall) ; reste rouge et pulsé quand la coupure est engagée (« SILENCIEUX »).
- **Diversité, vignettes** : le type de récepteur n'est plus affiché (réservé au panneau admin) ; à la place, locator du partenaire et azimut depuis ORSAT (ex. « JO21OC · azimut 28° »).
- **Diversité, relais pour les partenaires en http** : une page ouverte en https ne peut pas se connecter à un récepteur en http (la plupart des KiwiSDR). Le proxy relaie alors la connexion (`/divrelay/<id>/…`, websocket et HTTP). Relais fermé : seuls les partenaires inscrits dans le panneau admin sont joignables, aucun cookie ni en-tête de l'auditeur n'est transmis, 30 connexions au plus.
- **Diversité, partenaire conseillé** : sur chaque carte partenaire, badge pour la bande écoutée — « ★ Conseillé sur 40m », « Possible · 41 % », « Peu utile sur … » ou « Hors ligne » (carte grisée). Calcul fait par le carnet ORSAT-LOG (≥ 1.24.0, `/log/api/public/diversity`) : part de la zone entendue par ORSAT que le partenaire entend aussi (ionosondes KC2G), disponibilité sondée toutes les 10 min. Sans carnet : pas de badge. N'a aucun effet sur l'indice de performance d'ORSAT.
- **Diversité, partenaires fixés par l'opérateur** : nouvelle rubrique « 📡 Réception en diversité » du panneau admin (actif, nom, indicatif, pays/drapeau, lieu, type, adresse, locator, correction SNR propre à chaque partenaire, ordre, bouton « Tester » qui vérifie depuis le serveur que le récepteur répond). Liste enregistrée dans `diversity_partners.json` (hors git, incluse dans les sauvegardes) et servie au public par le proxy en `/diversity.json`. Côté auditeur : uniquement les cartes des partenaires et le bouton Démarrer, plus de saisie d'adresse, de liste enregistrée, d'import/export/QR ni de réglage de correction ; détails techniques en lecture seule, traduits. Sans liste enregistrée, l'annuaire intégré sert par défaut.
- **Diversité, liste enregistrée** : les boutons ✎ (modifier) et ✕ (retirer) ne répondaient pas sous Firefox, la ligne entière étant « glissable » pour le tri. Seule une petite poignée ⠿ à gauche sert désormais à glisser ; les flèches ▲▼ restent. Annuaire : drapeau du pays sur chaque carte partenaire (SVG intégré, les émojis-drapeaux ne s'affichent pas sous Windows).
- **Diversité, correctifs d'adresse** : UberSDR — seule l'origine du site est gardée (l'adresse copiée `…/v2/` est celle de la page ; `/connection` et `/ws` sont à la racine) ; PhantomSDR / NovaSDR — les paramètres `?frequency=…&modulation=…` d'une adresse copiée ne sont plus collés devant `/audio`. Type de récepteur reconnu d'après l'adresse saisie (`/v2/` → UberSDR, `:8073` → KiwiSDR…). Annuaire : + WebSDR Heppen (UberSDR, ON5HB · ON3MS).
- **Réception en diversité, partie guidée** : titre et sous-titre clairs, parcours en 3 étapes (choisir un partenaire dans l'annuaire, démarrer avec un grand bouton, écouter avec « 🎧 Vous écoutez : ORSAT / partenaire », états en clair, deux barres de signal, part du temps sur le partenaire), bouton « Comment ça marche ? », FR / EN / ES. Annuaire `frontend/src/lib/diversityPartners.js` (NovaSDR Rigi HB9RYZ, KiwiSDR 21051). Les réglages existants (adresse libre, type, liste enregistrée, correction SNR, détails techniques) sont intacts sous « Réglages avancés ».
- **Scanner supprimé** : sans intérêt sur ORSAT. Section, boutons, réglages, traductions et module `scanner.js` retirés intégralement.
- **Bouton « Indice de performance ? »** (titre du bandeau) : ouvre un panneau qui explique, en FR / EN / ES, comment ORSAT calcule son IP (prévision ionosondes, antenne NEC, note par distance, mesure réelle, mélange 40/60, lecture, zones, étalonnage), avec un grand bouton Fermer.
- **Bandeau « Indice de performance »** (remplace la couverture à 800 km) : note 0–100 par bande et zone où ORSAT entend le mieux (Loc ≤ 300 km, Rég 300–900, EU 900–2500, DX au-delà). Prévision sur toutes les distances (meilleure tranche 70 %, étendue 30 %), corrigée par la mesure réelle de la chute d'eau quand elle a moins de 15 min (40 % prévision, 60 % mesure). Verdicts Excellent ≥ 75 / Bon ≥ 50 / Moyen ≥ 25 / Faible ; détail par distance et cause d'une mesure absente dans l'infobulle ; FR / EN / ES.
- **Grand bouton de coupure du son** (section Audio) à la place du petit haut-parleur : « 🔊 COUPER L'AUDIO » (doré), qui devient « 🔇 SILENCIEUX » (rouge, pulsant). Pour les auditeurs sans liaison automatique transceiver ↔ ordinateur : couper d'un clic avant de passer en émission, sans larsen. Même fonction qu'avant (la coupure automatique en émission par CAT Sync l'affiche aussi) ; curseur de volume raccourci d'autant ; textes FR / EN / ES.
- **Bandeau « ORSAT exploitable » : trilingue et à la largeur de la chute d'eau** — textes FR / EN / ES selon le sélecteur de langue (le bandeau a son propre dictionnaire : ses phrases contiennent des chiffres variables), rayon « ≤ 800 km » affiché, placé dans le cadre de la chute d'eau ; la carte détaillée s'ouvre dans la même langue.
- **Bandeau « ORSAT exploitable » : verdict et mesure réelle** — pour la bande écoutée, verdict en clair (Fiable / Correct / Aléatoire / Fermé) et ce qu'ORSAT mesure réellement (nombre de signaux, meilleur SNR), relevé par le carnet sur la chute d'eau toutes les 5 min. L'infobulle donne l'étalonnage constaté : pour chaque niveau de couverture, la part du temps où un signal exploitable (SNR ≥ 10 dB) était présent.
- **Bandeau « ORSAT exploitable »** (probabilité à 800 km) entre l'en-tête et la chute d'eau : probabilité de réception, bande par bande, d'une station située à moins de 800 km du récepteur, calculée par le carnet ORSAT-LOG (ionosondes mesurées × diagramme NEC de la loop). Bande écoutée mise en évidence, rafraîchi toutes les 5 min. Bouton « 🗺 Voir la carte » (ou clic sur le bandeau) : carte détaillée dans une fenêtre par-dessus le WebSDR (`/log/ecoute`), avec un grand bouton « ✕ Fermer » (ou clic à côté). Composant isolé `frontend/src/lib/ListenBanner.svelte` ; si le carnet ne répond pas, le bandeau n'apparaît simplement pas.
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
