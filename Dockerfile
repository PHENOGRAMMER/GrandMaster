FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 5000

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    stockfish \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Use shell form with explicit sh -c to ensure $PORT is expanded
CMD ["sh", "-c", "gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT app_online:app"]