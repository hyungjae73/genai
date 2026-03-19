# Payment Compliance Monitor

決済条件監視・検証システム - ECサイトの決済条件コンプライアンスを自動監視するシステム

## Overview

このシステムは、ECサイトが契約時の決済条件を遵守しているか、また擬似サイトが存在しないかを自動監視し、違反を検知してアラートを発信します。

## Features

- 🔍 自動クローリング - 登録されたECサイトを定期的にスキャン
- 📊 決済情報抽出 - 価格、決済方法、手数料、定期縛り条件を自動抽出
- ✅ 契約条件検証 - 抽出した情報と契約条件を照合
- 🚨 擬似サイト検出 - 類似ドメインと擬似サイトを検出
- 📧 マルチチャネル通知 - Email、Slackで即座にアラート
- 📈 ダッシュボード - 監視状況を可視化

## Technology Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL 15+
- **Cache/Queue**: Redis 7.2+
- **Task Queue**: Celery
- **Crawler**: Playwright
- **Frontend**: React 18+ with TypeScript
- **Container**: Docker, Docker Compose

## Project Structure

```
genai/
├── src/                    # Source code
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── models.py          # Database models
│   ├── crawler.py         # Crawler engine
│   ├── analyzer.py        # Content analyzer
│   ├── validator.py       # Validation engine
│   ├── fake_detector.py   # Fake site detector
│   ├── alert_system.py    # Alert system
│   ├── celery_app.py      # Celery configuration
│   ├── tasks.py           # Celery tasks
│   ├── api/               # API endpoints
│   └── security/          # Security utilities
├── tests/                 # Test files
│   ├── __init__.py
│   ├── test_*.py         # Test modules
│   └── conftest.py       # Pytest configuration
├── docker/                # Docker configuration
│   └── Dockerfile
├── alembic/              # Database migrations
├── frontend/             # React frontend (to be created)
├── docker-compose.yml    # Docker Compose configuration
├── requirements.txt      # Python dependencies
├── pytest.ini           # Pytest configuration
├── .env                 # Environment variables (not in git)
├── .env.example         # Environment variables template
└── README.md            # This file
```

## Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Quick Start with Docker

1. Clone the repository and navigate to the project directory:
```bash
cd genai
```

2. Copy the example environment file and configure it:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start all services with Docker Compose:
```bash
docker-compose up -d
```

4. Run database migrations:
```bash
docker-compose exec api alembic upgrade head
```

5. Access the API:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Local Development Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

4. Install Tesseract OCR (required for verification system):

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-jpn
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

6. Start PostgreSQL and Redis (using Docker):
```bash
docker-compose up -d postgres redis
```

7. Run database migrations:
```bash
alembic upgrade head
```

8. Start the development server:
```bash
uvicorn src.main:app --reload
```

## Testing

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

Run specific test types:
```bash
pytest -m unit          # Unit tests only
pytest -m property      # Property-based tests only
pytest -m integration   # Integration tests only
```

## Configuration

Key environment variables (see `.env.example` for full list):

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SENDGRID_API_KEY`: SendGrid API key for email notifications
- `SLACK_BOT_TOKEN`: Slack bot token for Slack notifications
- `ENCRYPTION_KEY`: Encryption key for sensitive data
- `JWT_SECRET_KEY`: JWT secret for API authentication

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Main API Endpoints

#### Sites Management
- `POST /api/sites` - Register a new monitoring site
- `GET /api/sites` - List all monitoring sites
- `GET /api/sites/{id}` - Get site details
- `PUT /api/sites/{id}` - Update site information
- `DELETE /api/sites/{id}` - Delete a site

#### Contract Conditions
- `POST /api/contracts` - Create contract conditions
- `GET /api/contracts/{id}` - Get contract details
- `PUT /api/contracts/{id}` - Update contract conditions
- `DELETE /api/contracts/{id}` - Delete contract

#### Monitoring History
- `GET /api/monitoring-history` - Get monitoring history with filters
- `GET /api/monitoring-history/statistics` - Get monitoring statistics

#### Alerts
- `GET /api/alerts` - List all alerts
- `GET /api/alerts/{id}` - Get alert details

## Architecture

### System Components

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         FastAPI Application         │
│  ┌──────────┐  ┌─────────────────┐ │
│  │   API    │  │   Security      │ │
│  │ Endpoints│  │ (JWT, Audit)    │ │
│  └──────────┘  └─────────────────┘ │
└──────┬──────────────────────────────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│PostgreSQL│   │  Redis   │   │  Celery  │   │  Celery  │
│ Database │   │  Cache   │   │  Worker  │   │   Beat   │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### Workflow

1. **Site Registration**: Register ECサイト with contract conditions
2. **Scheduled Crawling**: Celery Beat triggers daily crawling tasks
3. **Content Analysis**: Extract payment information from HTML
4. **Validation**: Compare extracted data with contract conditions
5. **Alert Generation**: Send notifications for violations
6. **Fake Site Detection**: Weekly scan for similar domains

## Monitoring & Operations

### Health Check

```bash
curl http://localhost:8000/health
```

### View Logs

```bash
# API logs
docker-compose logs -f api

# Celery worker logs
docker-compose logs -f celery-worker

# Celery beat logs
docker-compose logs -f celery-beat
```

### Database Management

```bash
# Create a new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback migration
docker-compose exec api alembic downgrade -1
```

### Celery Task Management

```bash
# View active tasks
docker-compose exec celery-worker celery -A src.celery_app inspect active

# View scheduled tasks
docker-compose exec celery-beat celery -A src.celery_app inspect scheduled

# Purge all tasks
docker-compose exec celery-worker celery -A src.celery_app purge
```

## Security

### Authentication

The API uses JWT (JSON Web Tokens) for authentication:

1. Register a user (admin only):
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@example.com", "password": "secure_password"}'
```

2. Login to get access token:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secure_password"}'
```

3. Use the token in subsequent requests:
```bash
curl -X GET http://localhost:8000/api/sites \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Data Encryption

Sensitive contract data is encrypted using AES-256-GCM. Ensure `ENCRYPTION_KEY` is set in your environment variables.

### Audit Logging

All administrative operations are logged to the `audit_logs` table with:
- User information
- Action performed
- Resource affected
- IP address and user agent
- Timestamp

## Troubleshooting

### Common Issues

**Issue**: Database connection error
```
Solution: Ensure PostgreSQL is running and DATABASE_URL is correct
docker-compose ps postgres
```

**Issue**: Celery tasks not executing
```
Solution: Check Redis connection and Celery worker status
docker-compose logs celery-worker
```

**Issue**: Playwright browser not found
```
Solution: Reinstall Playwright browsers
docker-compose exec api playwright install chromium
```

**Issue**: Permission denied errors
```
Solution: Check file permissions and user ownership
docker-compose exec api ls -la /app
```

## Performance Tuning

### Database Optimization

- Indexes are created on frequently queried columns
- Use connection pooling (configured in SQLAlchemy)
- Regular VACUUM and ANALYZE operations

### Celery Optimization

- Adjust worker concurrency: `--concurrency=N`
- Use task priorities for critical operations
- Configure task time limits and retries

### Caching Strategy

- Redis caching for frequently accessed data
- Rate limiting to prevent abuse
- Cache invalidation on data updates

## Contributing

1. Create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass: `pytest`
4. Check code coverage: `pytest --cov=src`
5. Submit a pull request

## Support

For issues and questions:
- Check the documentation
- Review existing issues
- Contact the development team

## License

Proprietary - All rights reserved
