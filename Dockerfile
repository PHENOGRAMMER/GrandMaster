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

# Copy application and the wrapper script
COPY . .

# Ensure the start script is executable
RUN chmod +x start.sh

EXPOSE 5000

# Use the wrapper script for the start command
CMD ["./start.sh"]