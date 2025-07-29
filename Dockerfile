# Use Python slim image
FROM python:3.11-slim

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV NODE_ENV=production

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create app user and necessary directories
RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /app /tmp/chrome-user-data \
    && chown -R app:app /app /tmp/chrome-user-data

# Set working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .
RUN chown -R app:app /app

# Switch to app user
USER app

# Expose port
EXPOSE $PORT

# Add environment variable for Chrome
ENV CHROME_USER_DATA_DIR=/tmp/chrome-user-data

# Optimized gunicorn command
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 1 \
    --worker-class sync \
    --timeout 300 \
    --keep-alive 2 \
    --max-requests 50 \
    --max-requests-jitter 5 \
    --worker-tmp-dir /dev/shm \
    --log-level info \
    --preload \
    app:app