#!/bin/bash
# Start Celery Worker

# Activate virtual environment
source venv/bin/activate

# Add PostgreSQL to PATH
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"

# Start Celery worker
celery -A src.celery_app worker --loglevel=info
