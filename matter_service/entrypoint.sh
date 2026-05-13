#!/bin/bash
set -e

echo "Generating migrations..."
python manage.py makemigrations --noinput

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec gunicorn --bind 0.0.0.0:8002 --workers 2 matter_service.wsgi:application
