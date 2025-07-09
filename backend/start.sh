#!/usr/bin/env sh
# Run all outstanding migrations
alembic upgrade head

# Start the server
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
