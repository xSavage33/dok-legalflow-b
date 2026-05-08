#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec gunicorn --bind 0.0.0.0:8001 --workers 2 iam_service.wsgi:application
