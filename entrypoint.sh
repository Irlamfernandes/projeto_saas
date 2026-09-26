#!/bin/sh
set -e

echo "Executando migrações..."
python manage.py migrate --no-input

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --no-input --ignore "tests"

# Com um comando (ex.: o runserver do docker-compose, que recarrega ao salvar), roda ele.
# Sem comando, sobe o Gunicorn (produção).
if [ "$#" -gt 0 ]; then
    echo "Iniciando: $*"
    exec "$@"
fi

echo "Iniciando Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}