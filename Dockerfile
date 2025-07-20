# Use Python 3.13 Alpine image as base
FROM python:3.13-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CHROME_VERSION=125.0.6422.113

# Install system dependencies and Chrome
RUN apk add --no-cache \
    wget \
    gnupg \
    unzip \
    xvfb \
    curl \
    chromium \
    chromium-chromedriver \
    build-base \
    python3-dev \
    musl-dev \
    libffi-dev \
    openssl-dev

# Set Chrome binary location
ENV CHROME_BIN=/usr/bin/chromium-browser

# Set up working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies using uv
RUN uv pip install --no-cache --system -r requirements.txt

# Copy the rest of the application
COPY . .

# Create data directory
RUN mkdir -p data

# Set the entrypoint to run the scraper
ENTRYPOINT ["python", "meetup_scraper.py"] 