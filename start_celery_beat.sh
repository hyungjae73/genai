#!/bin/bash
# Start Celery Beat (Scheduler)

# Activate virtual environment
source venv/bin/activate

# Add PostgreSQL to PATH
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"

# Start Celery beat
celery -A src.celery_app beat --loglevel=info
