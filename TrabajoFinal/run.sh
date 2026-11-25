#!/usr/bin/env bash
# Levanta todo el sistema (Redis + Phoenix + API) con una sola instrucción: bash run.sh
set -e

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó el archivo .env: completá GOOGLE_API_KEY y volvé a ejecutar 'bash run.sh'."
  exit 1
fi

docker compose up --build -d

echo "Esperando a que la API esté lista (la primera vez descarga el modelo de embeddings)..."
for i in $(seq 1 60); do
  if curl -fs http://localhost:8000/health > /dev/null; then
    echo ""
    echo "Sistema listo:"
    echo "  API y documentación: http://localhost:8000/docs"
    echo "  Phoenix (trazas):    http://localhost:6006"
    echo "  Demo de 5 pruebas:   python scripts/demo.py"
    exit 0
  fi
  sleep 5
done
echo "La API no respondió. Revisá los logs con: docker compose logs api"
exit 1
