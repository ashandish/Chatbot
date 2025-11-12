FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV APP_MODULE=app.main:app \
    WORKERS=2 \
    HOST=0.0.0.0 \
    PORT=8000

CMD ["/bin/sh", "-c", "gunicorn ${APP_MODULE} --workers ${WORKERS} --worker-class uvicorn.workers.UvicornWorker --bind ${HOST}:${PORT}"]
