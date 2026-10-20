# Ponts TCI de PhantomSDR-ORSAT

Ce dossier contient deux outils, qui tournent tous deux sur le PC de l'auditeur
et jamais sur le serveur WebSDR.

| Outil | Rôle |
|---|---|
| `orsat-tci-server.py` | Fait voir le WebSDR ORSAT comme un récepteur TCI local, pour ORSAT-LOG, Log4OM, WSJT-X, Décodium… |
| `tci-rigctld.mjs` | Fait voir un transceiver Hamlib comme un serveur TCI, pour le bouton TCI-CAT de la page du récepteur |

## Serveur TCI pour ORSAT (`orsat-tci-server.py`)

Le programme se connecte au WebSDR exactement comme un navigateur. Il lit le
même flux audio FLAC et envoie les mêmes commandes de réglage. Il republie le
tout en TCI sur `ws://127.0.0.1:40001`. **Le serveur WebSDR n'est pas modifié** :
le pont compte simplement comme un auditeur de plus.

### Fonctions exposées

- **Fréquence** (`vfo`, `dds`), dans les deux sens : le logiciel TCI lit la
  fréquence d'écoute et peut aussi la changer.
- **Mode** (`modulation`) : `usb`, `lsb`, `digu`, `digl`, `cw`, `am`
  (enveloppe), `sam` (synchrone) et `nfm`.
- **Filtre** (`rx_filter_band`), en Hz relatifs à la fréquence affichée.
- **Audio RX** (`audio_start` / `audio_stop`) : 8, 12, 24 ou 48 kHz ; int16,
  int24, int32 ou float32 ; mono ou stéréo (la même voie sur les deux canaux).
- **S-mètre** (`rx_smeter`), en dBm, cinq fois par seconde.

Le récepteur est annoncé `receive_only` : les commandes d'émission (`trx`,
`tune`, drive, macros CW) ne sont jamais exécutées. Le spectre et l'IQ ne sont
pas transmis.

Plusieurs logiciels TCI peuvent être connectés en même temps. Ils partagent
alors la même écoute, comme sur un vrai poste : si l'un change la fréquence,
tous la suivent.

La connexion au WebSDR ne s'ouvre qu'au premier logiciel TCI connecté. Elle se
referme 10 s après le départ du dernier, pour ne pas occuper une place
d'auditeur pour rien.

### Installation (Linux)

Il faut Python 3.9 ou plus récent, et ffmpeg :

```bash
sudo apt install ffmpeg python3-venv
cd PhantomSDR-ORSAT/tci-bridge
chmod +x orsat-tci.sh
./orsat-tci.sh
```

Le premier lancement installe les dépendances Python dans `.venv/`, à côté du
script. Les lancements suivants démarrent directement.

### Options

```
./orsat-tci.sh --server https://orsat.ddns.net    # WebSDR à suivre (défaut)
               --listen 127.0.0.1:40001           # port TCI local (50001 pour imiter AetherSDR)
               --freq 7074000 --mode digu         # réglage de départ
               --cw-pitch 750                     # tonalité CW en Hz
               -v                                 # journal détaillé
```

Sans `--freq`, la fréquence de départ est celle que le WebSDR propose par
défaut.

### Réglage des logiciels

Dans le logiciel, choisissez une radio TCI (souvent nommée « ExpertSDR » ou
« SunSDR TCI »), sur l'adresse `127.0.0.1` et le port `40001`. Pour l'audio en
réception, sélectionnez l'audio TCI plutôt qu'une carte son.

### Limites connues

- Les modes à bande large (WFM) et le C-QUAM stéréo ne sont pas proposés : la
  largeur audio du WebSDR est limitée à son `audio_max_sps`.
- Un filtre plus large que cette limite est recentré et réduit, car le serveur
  refuse une fenêtre trop large.
- Si le serveur refuse la connexion (salle pleine, trop de tentatives), le pont
  attend avant de réessayer, au moins 30 s puis jusqu'à 2 min. Il évite ainsi
  le bannissement pour reconnexions trop rapides.
