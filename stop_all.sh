#!/bin/bash
# Stop all services for Payment Compliance Monitor

echo "=========================================="
echo "Stopping all services..."
echo "=========================================="
echo ""

# Stop FastAPI
echo "Stopping FastAPI..."
pkill -f "uvicorn src.main:app"

# Stop Celery Worker
echo "Stopping Celery Worker..."
pkill -f "celery.*worker"

# Stop Celery Beat
echo "Stopping Celery Beat..."
pkill -f "celery.*beat"

# Stop Frontend
echo "Stopping Frontend..."
pkill -f "vite"

echo ""
echo "✅ All services stopped!"
echo ""
