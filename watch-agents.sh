#!/bin/bash
# watch-agents.sh — Abre una ventana Windows Terminal por agente
# Uso: ./watch-agents.sh <path1> [path2] [path3] ...

if [ $# -eq 0 ]; then
  echo "Uso: ./watch-agents.sh <output-path-1> [output-path-2] ..."
  exit 1
fi

for path in "$@"; do
  LABEL=$(basename "$path" .output)
  wt --window new new-tab --title "$LABEL" bash -c "tail -f '$path'; exec bash"
done
