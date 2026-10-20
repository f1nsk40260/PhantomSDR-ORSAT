#!/usr/bin/env bash
# Lance le serveur TCI local pour PhantomSDR-ORSAT.
# Premier lancement : crée un environnement Python à côté du script et y installe
# les dépendances. Les options sont transmises telles quelles, par exemple :
#   ./orsat-tci.sh --server https://orsat.ddns.net --listen 127.0.0.1:40001
set -e
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null; then
  echo "ffmpeg est nécessaire : sudo apt install ffmpeg" >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Installation des dépendances (une seule fois)..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/python orsat-tci-server.py "$@"
