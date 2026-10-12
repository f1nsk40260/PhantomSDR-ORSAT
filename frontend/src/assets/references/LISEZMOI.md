# Signaux de référence

Base de signaux de référence pour un futur menu d'identification.
Source : Artemis-DB / Signal Identification Wiki (https://www.sigidwiki.com) — version indiquée dans `VERSION`.

- `index.json` : liste de tous les signaux (id, titre, catégories, fréquences min/max, largeur de bande, modulation, mode, présence d'image et de son).
- `<id>/signal.json` : fiche complète du signal (description, localisation, lien vers la page d'origine `page`, etc.).
- `<id>/spectre.webp` : spectre / cascade de référence (si `has_img`).
- `<id>/son.opus` : enregistrement audio de référence (si `has_snd`).

Ces fichiers ne sont importés par aucun composant pour l'instant : ils n'alourdissent pas la compilation.
