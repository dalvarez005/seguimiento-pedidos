#!/usr/bin/env bash
# Despliega en el servidor: copia el código y reconstruye el contenedor.
# Uso: deploy/deploy.sh [usuario@host]   (el .env del servidor no se toca)
set -euo pipefail

SERVIDOR="${1:-orangepi@192.168.1.77}"
DESTINO="pedidos"
cd "$(dirname "$0")/.."

echo "→ Pruebas"
uv run pytest -q

echo "→ Copiando a $SERVIDOR:~/$DESTINO"
rsync -az --delete \
  --exclude .venv --exclude .git --exclude .pytest_cache --exclude '__pycache__' \
  --exclude '*.db' --exclude .env --exclude .impeccable \
  ./ "$SERVIDOR:$DESTINO/"

echo "→ Construyendo y levantando"
ssh "$SERVIDOR" "cd $DESTINO && test -f .env && docker compose up -d --build && docker image prune -f >/dev/null"

echo "→ Verificando"
ssh "$SERVIDOR" 'for i in $(seq 30); do curl -fsS http://localhost:5210/health && exit 0; sleep 2; done; exit 1'
echo
echo "Listo."
