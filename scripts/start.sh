#!/bin/bash
"""Startup script for Document Search Application."""

set -e

echo "Document Search Application Startup"
echo "===================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found. Please run setup first:"
    echo "  python scripts/setup.py"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please run setup first:"
    echo "  python scripts/setup.py"
    exit 1
fi

echo "Starting services..."

# Start Elasticsearch in background
echo "Starting Elasticsearch..."
docker-compose up elasticsearch -d

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        echo "✓ Elasticsearch is ready"
        break
    fi
    echo "  Waiting for Elasticsearch... ($((attempt + 1))/$max_attempts)"
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "Error: Elasticsearch failed to start"
    exit 1
fi

# Activate virtual environment and start API
echo "Starting Document Search FastAPI..."
source venv/bin/activate
export PYTHONPATH="$(pwd)/src"

# Start the FastAPI application with uvicorn
uvicorn src.api.app:app --host 0.0.0.0 --port 5000 --reload 