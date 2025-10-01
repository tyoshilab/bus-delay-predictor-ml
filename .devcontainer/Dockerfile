FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /usr/src/app

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    libpq-dev \
    gcc \
    g++ \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python -m pip install --upgrade pip setuptools wheel

# Copy requirements and install Python packages (CPU version by default)
COPY requirements-cpu.txt .
RUN pip install --no-cache-dir -r requirements-cpu.txt

# Verify TensorFlow setup
RUN python -c "import tensorflow as tf; print('TensorFlow version:', tf.__version__); print('Running on CPU')"
