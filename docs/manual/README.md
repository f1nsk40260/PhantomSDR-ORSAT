# Manuels utilisateur de PhantomSDR-ORSAT

Les trois manuels PDF ouverts depuis le menu de l'interface
(`frontend/src/assets/docs/manualFR.pdf`, `manualEN.pdf`, `manualES.pdf`)
sont générés à partir des sources de ce dossier :

- `manual_fr.md`, `manual_en.md`, `manual_es.md` — le texte, à modifier ici ;
- `images/` — les vignettes (captures d'écran) ;
- `build_manual.py` — le générateur (ReportLab, polices DejaVu).

Pour régénérer après une modification :

```
python3 docs/manual/build_manual.py          # les trois langues
python3 docs/manual/build_manual.py fr       # une seule
```

puis reconstruire le frontend pour que le site serve les nouveaux PDF.
La syntaxe des sources est décrite en tête de `build_manual.py`.

## Guide de l'analyseur audio

`analyseur_fr.md`, `analyseur_en.md`, `analyseur_es.md` produisent
`guideAnalyseurFR.pdf`, `guideAnalyseurEN.pdf`, `guideAnalyseurES.pdf`
(ouverts depuis la rubrique « Guide de l'analyseur audio » du menu Informations).
Les images `images/analyseur_*.jpg` sont des captures de l'analyseur alimenté
par un signal de démonstration (voix synthétique).

```
python3 docs/manual/build_manual.py analyseur_fr.md
```

## Guide des décodeurs

`decodeurs_fr.md`, `decodeurs_en.md`, `decodeurs_es.md` produisent `guideDecodeursFR.pdf`, `guideDecodeursEN.pdf`, `guideDecodeursES.pdf` (rubrique « Guide des décodeurs »
du menu Informations). Les vignettes `images/dec_*.jpg` sont à fournir : tant
qu'une image manque, le PDF affiche un cadre « Vignette à fournir » à sa place.

```
python3 docs/manual/build_manual.py decodeurs_fr.md
```

## Guide de la réception en diversité

`diversite_fr.md`, `diversite_en.md`, `diversite_es.md` produisent `guideDiversiteFR.pdf`,
`guideDiversiteEN.pdf`, `guideDiversiteES.pdf`. Les schémas `images/div_principe_*.png`
illustrent le principe (deux trajets, évanouissements décorrélés, sélection).

```
python3 docs/manual/build_manual.py diversite_fr.md
```
