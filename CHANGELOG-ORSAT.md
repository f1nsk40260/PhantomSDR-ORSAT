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

### Décodeurs
- Décodeur **HFDL** (messages ACARS des avions en ondes courtes), à partir de dumphfdl compilé en WebAssembly.

### Documentation
- Mode d'emploi en PDF en français, anglais et espagnol, accessible depuis le menu.
- README réécrit pour ORSAT, avec captures du récepteur en service sur https://orsat.ddns.net.

### Nettoyage du dépôt
- Retrait du code mort `frontend/src/unused/` et des fichiers produits localement (`frontend/stats.html`, `rade_loadtest.csv`), désormais ignorés par git.
- Captures d'écran du README compressées.
