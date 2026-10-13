# Signaux de référence

Base de signaux de référence pour un futur menu d'identification.
Source : base de données d'Artemis (https://github.com/AresValley/Artemis), construite à partir du
Signal Identification Wiki (https://www.sigidwiki.com) — version indiquée dans `VERSION`.
Tout le mérite de ce contenu revient aux contributeurs du Signal Identification Wiki.
Redistribution autorisée par l'équipe d'Artemis (octobre 2026), avec mention et lien vers
Artemis et SigIDWiki. Le futur menu qui utilisera ces données devra afficher cette mention
et ces deux liens, ainsi que le lien de chaque fiche vers sa page SigIDWiki (champ `page`).

- `index.json` : liste de tous les signaux (id, titre, catégories, fréquences min/max, largeur de bande, modulation, mode, présence d'image et de son).
- `<id>/signal.json` : fiche complète du signal (description, localisation, lien vers la page d'origine `page`, etc.).
- `<id>/spectre.webp` : spectre / cascade de référence (si `has_img`).
- `<id>/son.opus` : enregistrement audio de référence (si `has_snd`).

Ces fichiers ne sont importés par aucun composant pour l'instant : ils n'alourdissent pas la compilation.
