# Use official Python image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libatlas-base-dev \
    libgl1-mesa-glx \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Optional: copy requirements.txt if you have one
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# Otherwise, install dependencies inline
RUN pip install --no-cache-dir \
    flask \
    flask_socketio \
    eventlet \
    redis \
    paho-mqtt \
    cryptography \
    numpy \
    scikit-learn \
    schedule \
    joblib

# Set Flask environment
ENV FLASK_APP=smart_agriculture_app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# Expose port
EXPOSE 5000

# Run Flask app with SocketIO using eventlet for WebSocket support
CMD ["python", "backend/smart_agriculture_app.py"]

