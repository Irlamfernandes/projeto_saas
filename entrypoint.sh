#!/bin/sh
set -e

echo "Executando migrações..."
python manage.py migrate --no-input

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --no-input

echo "Iniciando Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}