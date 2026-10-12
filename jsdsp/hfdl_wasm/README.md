# Décodeur HFDL en WebAssembly

Décodeur HFDL (HF Data Link) utilisé par le bouton **HFDL** de l'interface F1NSK.
Il tourne dans le navigateur (`frontend/src/hfdl.worker.js`) et lit l'audio USB
démodulé par le serveur, avant les aides d'écoute (NR/NB/NS/AN), comme les autres
décodeurs de PhantomSDR-Plus.

## Origine du code

- **dumphfdl 1.7.0** — Tomasz Lemiech, <https://github.com/szpajder/dumphfdl>,
  GPL-3.0-or-later. Les fichiers nécessaires sont dans `dumphfdl/` ;
  `hfdl.c` y devient `hfdl_core.c` (sans threads ni canaliseur SDR, entrée en
  bande de base à 5400 éch./s). `systable.conf` est la table des stations sol.
- **libacars 2.2.1** — Tomasz Lemiech, MIT ; téléchargée à la compilation.
  `libacars-config/` contient les deux fichiers que CMake générerait.
- **liquid-dsp** — Joseph Gaeddert, MIT ; téléchargée à la compilation.
- **libconfig** — Mark Lindner, LGPL-2.1 ; téléchargée à la compilation.

`hfdl_wasm.c` (GPL-3.0-or-later) fait le lien : passage de l'audio réel à la
bande de base (sous-porteuse à 1440 Hz), recherche du rythme exact de l'audio
(±1 %, 11 démodulateurs en parallèle, verrouillage sur celui qui décode),
suppression des doublons, sortie JSON + texte.

## Recompiler

```
sudo apt install emscripten git cmake
cd jsdsp/hfdl_wasm
bash build_hfdl_wasm.sh
```

Le script produit `frontend/public/decoders/hfdl.wasm`,
`frontend/public/decoders/hfdl_systable.conf` et `frontend/src/modules/hfdl.mjs`,
qui sont déjà livrés dans le dépôt : la recompilation n'est utile que si l'on
modifie le décodeur.
