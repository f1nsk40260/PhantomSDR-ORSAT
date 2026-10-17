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
