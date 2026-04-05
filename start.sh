#!/bin/sh
echo "🚀 Starting GrandMaster Chess..."
echo "📍 Binding to 0.0.0.0:${PORT:-5000}"
exec gunicorn -k eventlet -w 1 --bind 0.0.0.0:${PORT:-5000} app_online:app
