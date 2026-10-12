#!/bin/bash
# ---------------------------------------------------------------------------
# interface.sh — choisir l'interface de bureau du WebSDR (version française).
#
# Deux interfaces de bureau sont livrées :
#   [1] F1NSK    — frontend/src/App.svelte : thème or, infobulles en français,
#                  manuels utilisateur FR/EN/ES, hamdash et synchro DX cluster,
#                  disposition F1NSK (Audio DSP, Scanner, Decoders Control…)
#   [2] Originale — frontend/src/App.original.svelte : interface sv1btl v5.1.0
#
# Le choix est écrit dans frontend/interface.json (lu par vite.config.js) et
# n'a d'effet qu'après une recompilation du frontend, que le script propose.
# La page /mobile est la même dans les deux cas.
#
#   ./interface.sh                 # affiche le choix actuel puis demande
#   ./interface.sh f1nsk           # interface F1NSK, puis propose de recompiler
#   ./interface.sh original --build     # interface sv1btl et recompile sans demander
#   ./interface.sh f1nsk --no-build     # change le choix sans recompiler
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$ROOT/frontend"
CHOICE_FILE="$FRONTEND/interface.json"

UI=""
DO_BUILD=ask          # ask | yes | no

for arg in "$@"; do
  case "$arg" in
    f1nsk|1)          UI="f1nsk" ;;
    original|sv1btl|2) UI="original" ;;
    --build|-b)       DO_BUILD=yes ;;
    --no-build)       DO_BUILD=no ;;
    -h|--help)
      sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "interface.sh : argument inconnu « $arg »" >&2
      echo "usage : ./interface.sh [f1nsk|original] [--build|--no-build]" >&2
      exit 2 ;;
  esac
done

current_ui() {
  local ui=""
  [ -f "$CHOICE_FILE" ] && ui="$(grep -oP '"ui"\s*:\s*"\K[a-z0-9]+' "$CHOICE_FILE" || true)"
  case "$ui" in original) echo "original" ;; *) echo "f1nsk" ;; esac
}

label() {
  case "$1" in
    original) echo "Originale sv1btl (v5.1.0)" ;;
    *)        echo "F1NSK (thème or, en français)" ;;
  esac
}

CUR="$(current_ui)"

if [ -z "$UI" ]; then
  echo "=========================================="
  echo "Interface de bureau du WebSDR"
  echo "=========================================="
  echo
  echo "Actuelle : $(label "$CUR")"
  echo
  echo "  [1] F1NSK     — thème or, infobulles en français, manuels FR/EN/ES,"
  echo "                  hamdash et synchro DX cluster, disposition F1NSK"
  echo "  [2] Originale — interface sv1btl PhantomSDR+ v5.1.0, sans modification"
  echo
  def=1; [ "$CUR" = "original" ] && def=2
  read -r -p "Votre choix [1-2] (ENTRÉE = $def) : " ans || ans=""
  case "${ans:-$def}" in
    1) UI="f1nsk" ;;
    2) UI="original" ;;
    *) echo "Choix invalide — rien n'est changé."; exit 1 ;;
  esac
fi

cat > "$CHOICE_FILE" << EOF
{
  "ui": "$UI"
}
EOF
echo "✅ Interface choisie : $(label "$UI")"

if [ "$UI" = "$CUR" ] && [ "$DO_BUILD" = ask ]; then
  echo "   (c'était déjà le choix en place)"
fi

case "$DO_BUILD" in
  no)  echo "   Recompilez le frontend pour l'appliquer : cd frontend && ./build-all.sh"; exit 0 ;;
  ask)
    read -r -p "Recompiler le frontend maintenant (build-all.sh) ? [O/n] " r || r="n"
    case "${r:-o}" in [OoYy]*) ;; *) echo "   Pour l'appliquer plus tard : cd frontend && ./build-all.sh"; exit 0 ;; esac ;;
esac

cd "$FRONTEND"
chmod +x ./build-all.sh
./build-all.sh
echo "✅ Frontend recompilé avec l'interface $(label "$UI")."
echo "   Rechargez la page du WebSDR dans le navigateur (Ctrl+Maj+R)."
