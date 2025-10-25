#!/usr/bin/env sh
set -e

echo "🚀 Starting Travel MVP Backend..."

# Run database migrations
echo "📦 Running database migrations..."
alembic upgrade head

# Check if we're in production mode
if [ "$FASTAPI_ENV" = "production" ]; then
    echo "🏭 Starting production server with Gunicorn..."
    echo "   Workers: ${WORKERS:-4}"
    echo "   Timeout: 120s"
    
    exec gunicorn app.main:app \
        --workers ${WORKERS:-4} \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --timeout 120 \
        --graceful-timeout 30 \
        --keep-alive 5 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --access-logfile - \
        --error-logfile - \
        --log-level ${LOG_LEVEL:-info}
else
    echo "🔧 Starting development server with Uvicorn..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level ${LOG_LEVEL:-debug}
fi
