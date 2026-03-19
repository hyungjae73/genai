#!/bin/bash
# Start FastAPI application

# Activate virtual environment
source venv/bin/activate

# Add PostgreSQL to PATH
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"

# Start uvicorn server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
