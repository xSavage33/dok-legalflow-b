#!/bin/bash
set -e

echo "Generating migrations..."
python manage.py makemigrations --noinput

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec gunicorn --bind 0.0.0.0:8005 --workers 2 billing_service.wsgi:application
