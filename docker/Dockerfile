# ---- Builder Stage ----
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Production Stage ----
FROM python:3.11-slim AS production
WORKDIR /app

# Playwright + Chromiumに必要なシステム依存関係（クローラー機能で必須）
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libatspi2.0-0 libxshmfence1 fonts-liberation \
    xdg-utils wget \
    tesseract-ocr tesseract-ocr-jpn \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# appuserを先に作成し、Playwrightブラウザを共有パスにインストール
RUN useradd -m -u 1000 appuser
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN mkdir -p /opt/playwright-browsers && playwright install chromium && chmod -R 755 /opt/playwright-browsers

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN mkdir -p /app/screenshots && chown -R appuser:appuser /app

# gosuをインストール（entrypoint.shでroot→appuser切り替え用）
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*

EXPOSE 8000
USER appuser
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
