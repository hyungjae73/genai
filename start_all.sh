#!/bin/bash
# Start all services for Payment Compliance Monitor

echo "=========================================="
echo "Payment Compliance Monitor - Local Setup"
echo "=========================================="
echo ""

# Check if PostgreSQL is running
echo "Checking PostgreSQL..."
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
  echo "❌ PostgreSQL is not running. Starting PostgreSQL..."
  brew services start postgresql@15
  sleep 3
else
  echo "✅ PostgreSQL is running"
fi

# Check if Redis is running
echo "Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
  echo "❌ Redis is not running. Starting Redis..."
  brew services start redis
  sleep 2
else
  echo "✅ Redis is running"
fi

echo ""
echo "=========================================="
echo "Starting services..."
echo "=========================================="
echo ""

# Start FastAPI in background
echo "🚀 Starting FastAPI API Server (port 8080)..."
./start_api.sh > logs/api.log 2>&1 &
API_PID=$!
echo "   PID: $API_PID"
sleep 3

# Start Celery Worker in background
echo "🚀 Starting Celery Worker..."
./start_celery_worker.sh > logs/celery_worker.log 2>&1 &
WORKER_PID=$!
echo "   PID: $WORKER_PID"
sleep 2

# Start Celery Beat in background
echo "🚀 Starting Celery Beat (Scheduler)..."
./start_celery_beat.sh > logs/celery_beat.log 2>&1 &
BEAT_PID=$!
echo "   PID: $BEAT_PID"
sleep 2

# Start Frontend in background
echo "🚀 Starting React Frontend (port 5173)..."
cd frontend && ./start_frontend.sh > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "   PID: $FRONTEND_PID"

echo ""
echo "=========================================="
echo "✅ All services started!"
echo "=========================================="
echo ""
echo "Service URLs:"
echo "  - API Documentation: http://localhost:8080/docs"
echo "  - API Health Check: http://localhost:8080/health"
echo "  - Frontend Dashboard: http://localhost:5173"
echo ""
echo "Process IDs:"
echo "  - FastAPI: $API_PID"
echo "  - Celery Worker: $WORKER_PID"
echo "  - Celery Beat: $BEAT_PID"
echo "  - Frontend: $FRONTEND_PID"
echo ""
echo "Logs are available in the logs/ directory"
echo ""
echo "To stop all services, run: ./stop_all.sh"
echo "Or press Ctrl+C and run: pkill -f 'uvicorn|celery|vite'"
echo ""
