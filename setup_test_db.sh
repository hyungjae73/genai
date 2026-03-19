#!/bin/bash
# Setup test database for running tests

echo "Setting up test database..."

# Check if PostgreSQL is running
if ! docker ps | grep -q postgres; then
    echo "Starting PostgreSQL container..."
    docker-compose up -d postgres
    sleep 5
fi

# Check if Redis is running
if ! docker ps | grep -q redis; then
    echo "Starting Redis container..."
    docker-compose up -d redis
    sleep 3
fi

# Create test database
echo "Creating test database..."
docker-compose exec -T postgres psql -U payment_monitor -d payment_monitor -c "DROP DATABASE IF EXISTS payment_monitor_test;" 2>/dev/null || true
docker-compose exec -T postgres psql -U payment_monitor -d payment_monitor -c "CREATE DATABASE payment_monitor_test;"

# Run migrations on test database
echo "Running migrations on test database..."
export DATABASE_URL="postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor_test"
alembic upgrade head

echo "Test database setup complete!"
echo ""
echo "You can now run tests with: pytest tests/"
