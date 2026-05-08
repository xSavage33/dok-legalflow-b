#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec gunicorn --bind 0.0.0.0:8004 --workers 2 time_tracking_service.wsgi:application
