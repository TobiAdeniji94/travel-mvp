#!/bin/bash
set -e

echo "========================================="
echo "Travel MVP Backend - Render Free Tier"
echo "========================================="

# Use PORT from Render environment (default 10000)
export PORT=${PORT:-10000}
export WORKERS=${WORKERS:-2}  # Free tier: use 2 workers max

echo "Environment: ${FASTAPI_ENV:-development}"
echo "Port: $PORT"
echo "Workers: $WORKERS"

# Wait for database to be ready
echo "Waiting for database connection..."
max_retries=30
retry_count=0

until python -c "
import sys
import psycopg2
from urllib.parse import urlparse
import os

db_url = os.getenv('DB_URL', '')
if not db_url:
    print('⚠️  No DB_URL set, skipping database check')
    sys.exit(0)

try:
    result = urlparse(db_url)
    conn = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    conn.close()
    print('✅ Database connection successful')
    sys.exit(0)
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
" || [ $retry_count -eq $max_retries ]; do
    retry_count=$((retry_count + 1))
    echo "Retry $retry_count/$max_retries..."
    sleep 2
done

# Run database migrations (idempotent)
echo "Running database migrations..."
cd /app && alembic upgrade head || echo "⚠️  Migration failed or already applied"

# Check if database needs seeding (first run detection)
echo "Checking if database needs initial seeding..."
python -c "
import sys
import os
from sqlalchemy import create_engine, text

db_url = os.getenv('DB_URL', '')
if not db_url:
    print('⚠️  No DB_URL set, skipping seed check')
    sys.exit(0)

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        # Check if destinations table has data
        result = conn.execute(text('SELECT COUNT(*) FROM destinations'))
        count = result.scalar()
        if count == 0:
            print('📦 Database is empty, needs seeding')
            sys.exit(1)
        else:
            print(f'✅ Database already seeded ({count} destinations found)')
            sys.exit(0)
except Exception as e:
    print(f'⚠️  Could not check database: {e}')
    sys.exit(0)
"

# If exit code is 1, database needs seeding
if [ $? -eq 1 ]; then
    echo "Seeding database with catalog data..."
    python scripts/seed_catalog.py || echo "⚠️  Seeding failed, will use existing data"
fi

# Verify ML models exist
echo "Verifying ML models..."
if [ ! -f "/app/models/tfidf_vectorizer_dest.pkl" ]; then
    echo "⚠️  ML models not found in /app/models/"
    echo "Attempting to build models now..."
    python scripts/train_all_models.py || echo "❌ Model training failed"
fi

# Download spaCy model if not present (fallback)
echo "Verifying spaCy model..."
python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null || {
    echo "Downloading spaCy model..."
    python -m spacy download en_core_web_sm
}

echo "========================================="
echo "Starting FastAPI application..."
echo "========================================="

# Start application with Gunicorn (production) or Uvicorn (development)
if [ "$FASTAPI_ENV" = "production" ]; then
    echo "🚀 Starting production server with Gunicorn"
    echo "   Workers: $WORKERS"
    echo "   Binding: 0.0.0.0:$PORT"
    
    exec gunicorn app.main:app \
        --workers $WORKERS \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:$PORT \
        --timeout 120 \
        --graceful-timeout 30 \
        --keep-alive 5 \
        --access-logfile - \
        --error-logfile - \
        --log-level info
else
    echo "🔧 Starting development server with Uvicorn"
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --log-level info
fi
