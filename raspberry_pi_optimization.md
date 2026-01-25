# Raspberry Pi Deployment & Optimization Guide

## 🎯 Overview

This guide covers deploying and optimizing SYSGrow AI/ML features on Raspberry Pi (Pi 4/5 recommended).

---

## 📦 System Requirements

### Minimum (Pi 4)
- **RAM**: 2GB (4GB recommended)
- **Storage**: 32GB microSD (64GB+ recommended)
- **OS**: Raspberry Pi OS (64-bit) Lite or Desktop

### Recommended (Pi 5)
- **RAM**: 4GB or 8GB
- **Storage**: 64GB+ NVMe SSD (via M.2 HAT)
- **Cooling**: Active cooling (fan/heatsink)

---

## 🚀 Installation Steps

### 1. Initial Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install system dependencies
sudo apt install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libopenblas-dev \
    libhdf5-dev \
    libjpeg-dev \
    zlib1g-dev

# Install Redis (for caching)
sudo apt install redis-server -y
sudo systemctl enable redis-server
```

### 2. Create Virtual Environment

```bash
cd /home/pi/sysgrow
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies (Optimized)

```bash
# Install numpy/scipy with OpenBLAS (faster)
pip install --no-cache-dir numpy scipy

# Install scikit-learn (lightweight ML)
pip install --no-cache-dir scikit-learn

# Install pandas with optimizations
pip install --no-cache-dir pandas

# Install Flask and dependencies
pip install -r requirements.txt

# Install TensorFlow Lite (optional, for advanced models)
pip install --no-cache-dir tensorflow-lite-runtime
```

### 4. Configure Memory and Swap

```bash
# Increase swap for model training (temporary)
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=2048 (2GB)
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Configure Python for lower memory
export PYTHONHASHSEED=0  # Reproducible hashing
export OMP_NUM_THREADS=2  # Limit OpenBLAS threads
```

---

## ⚡ Performance Optimizations

### 1. Model Optimization

#### Use Lightweight Models
```python
# In ml_trainer.py - Use smaller models
RandomForestClassifier(
    n_estimators=50,        # Reduced from 100
    max_depth=10,           # Limit depth
    min_samples_split=10,   # Prevent overfitting
    n_jobs=2                # Limit parallelism
)
```

#### Model Quantization
```python
# Convert trained models to lower precision
import joblib
import numpy as np

# Load model
model = joblib.load('model.pkl')

# For tree-based models, no quantization needed
# For neural networks, use TensorFlow Lite:

# Convert to TFLite (if using TensorFlow)
converter = tf.lite.TFLiteConverter.from_saved_model('model')
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

# Save quantized model
with open('model_quantized.tflite', 'wb') as f:
    f.write(tflite_model)
```

### 2. Continuous Monitoring Optimization

```python
# In continuous_monitor.py
class ContinuousMonitoringService:
    def __init__(self, ..., check_interval=600):  # 10 min instead of 5
        # Reduce check frequency on Pi
        if is_raspberry_pi():
            check_interval = max(600, check_interval)  # Min 10 minutes
        
        # Limit monitored units if many exist
        self.max_monitored_units = 3  # Monitor max 3 units simultaneously
```

**Adaptive Monitoring**:
```python
def _monitor_unit(self, unit_id: int):
    """Adaptive monitoring based on system load."""
    
    # Check CPU usage before heavy analysis
    cpu_usage = psutil.cpu_percent(interval=1)
    
    if cpu_usage > 80:
        logger.warning(f"High CPU ({cpu_usage}%), skipping AI analysis")
        return
    
    # Proceed with analysis
    ...
```

### 3. Database Optimization

```python
# Use connection pooling
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'sqlite:///sysgrow.db',
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True
)
```

**Optimize Queries**:
```python
# Add indexes for frequently queried columns
CREATE INDEX idx_sensor_readings_timestamp ON sensor_readings(timestamp);
CREATE INDEX idx_sensor_readings_unit_id ON sensor_readings(unit_id);
CREATE INDEX idx_ai_insights_unit_timestamp ON ai_insights(unit_id, timestamp);
```

### 4. Caching Strategy

```python
# Use Redis for caching predictions
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_cached_prediction(key, func, ttl=300):
    """Cache ML predictions for 5 minutes."""
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    
    result = func()
    redis_client.setex(key, ttl, json.dumps(result))
    return result

# Usage
predictions = get_cached_prediction(
    f'disease_risk:{unit_id}',
    lambda: disease_predictor.predict_disease_risk(unit_id, ...),
    ttl=300  # 5 minutes
)
```

---

## 🔧 Configuration Files

### 1. Systemd Service (Production)

Create `/etc/systemd/system/sysgrow.service`:

```ini
[Unit]
Description=SYSGrow Smart Agriculture Platform
After=network.target redis-server.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/sysgrow
Environment="PATH=/home/pi/sysgrow/venv/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="OMP_NUM_THREADS=2"
Environment="FLASK_ENV=production"
ExecStart=/home/pi/sysgrow/venv/bin/python run.py
Restart=always
RestartSec=10

# Resource limits for Raspberry Pi
MemoryLimit=1.5G
CPUQuota=150%

# Logging
StandardOutput=append:/var/log/sysgrow/app.log
StandardError=append:/var/log/sysgrow/error.log

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable sysgrow
sudo systemctl start sysgrow
sudo systemctl status sysgrow
```

### 2. Gunicorn Configuration (Recommended)

Create `gunicorn_config.py`:

```python
# Gunicorn configuration for Raspberry Pi
import multiprocessing
import os

# Bind to all interfaces
bind = "0.0.0.0:5000"

# Workers: 2 for Pi 4, 3 for Pi 5
workers = min(2, (multiprocessing.cpu_count() * 2) + 1)

# Worker class
worker_class = "sync"

# Threads per worker
threads = 2

# Timeout (increased for ML operations)
timeout = 120
keepalive = 5

# Logging
accesslog = "/var/log/sysgrow/access.log"
errorlog = "/var/log/sysgrow/error.log"
loglevel = "info"

# Process naming
proc_name = "sysgrow"

# Preload app for faster startup
preload_app = True

# Limit request size (prevent memory issues)
limit_request_line = 4096
limit_request_fields = 100

# Worker lifecycle hooks
def on_starting(server):
    print("Starting SYSGrow on Raspberry Pi...")

def pre_fork(server, worker):
    # Limit memory before fork
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (1500 * 1024 * 1024, -1))  # 1.5GB

def worker_int(worker):
    print(f"Worker {worker.pid} received interrupt, gracefully shutting down...")
```

Update systemd service to use Gunicorn:
```ini
ExecStart=/home/pi/sysgrow/venv/bin/gunicorn -c gunicorn_config.py "app:create_app()"
```

### 3. Nginx Reverse Proxy (Recommended)

```bash
sudo apt install nginx -y
```

Create `/etc/nginx/sites-available/sysgrow`:

```nginx
upstream sysgrow_app {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name sysgrow.local;

    # Increase timeouts for ML operations
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;

    # Buffer settings
    client_body_buffer_size 128k;
    client_max_body_size 20M;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;

    # Static files (cache aggressively)
    location /static/ {
        alias /home/pi/sysgrow/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API endpoints (no caching)
    location /api/ {
        proxy_pass http://sysgrow_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # No caching for API
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    # Socket.IO
    location /socket.io/ {
        proxy_pass http://sysgrow_app;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Main application
    location / {
        proxy_pass http://sysgrow_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/sysgrow /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 📊 Monitoring & Maintenance

### 1. System Monitoring Script

Create `scripts/monitor_pi.sh`:

```bash
#!/bin/bash
# System monitoring for Raspberry Pi

echo "=== SYSGrow System Monitor ==="
echo "Timestamp: $(date)"
echo ""

# CPU Temperature
temp=$(vcgencmd measure_temp | egrep -o '[0-9]*\.[0-9]*')
echo "CPU Temperature: ${temp}°C"

# Throttling check
throttled=$(vcgencmd get_throttled)
echo "Throttling Status: $throttled"

# Memory usage
free -h | grep "Mem:"

# Disk usage
df -h / | tail -1

# SYSGrow processes
echo ""
echo "=== SYSGrow Processes ==="
ps aux | grep "[p]ython.*sysgrow" | awk '{print $2, $3, $4, $11}'

# Service status
echo ""
echo "=== Service Status ==="
systemctl is-active sysgrow
systemctl is-active redis-server
systemctl is-active nginx

# Recent errors
echo ""
echo "=== Recent Errors (last 10) ==="
tail -10 /var/log/sysgrow/error.log
```

```bash
chmod +x scripts/monitor_pi.sh

# Run hourly via cron
crontab -e
# Add: 0 * * * * /home/pi/sysgrow/scripts/monitor_pi.sh >> /var/log/sysgrow/monitor.log 2>&1
```

### 2. Automatic Model Cleanup

```python
# scripts/cleanup_old_models.py
"""Clean up old model versions to save space."""

import os
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_models(models_dir='models', keep_versions=3):
    """
    Keep only the N most recent model versions.
    
    Args:
        models_dir: Path to models directory
        keep_versions: Number of versions to keep per model
    """
    models_path = Path(models_dir)
    
    for model_name_dir in models_path.iterdir():
        if not model_name_dir.is_dir():
            continue
        
        # Get all version directories
        versions = []
        for version_dir in model_name_dir.iterdir():
            if version_dir.name == 'production':
                continue  # Skip symlink
            
            metadata_file = version_dir / 'metadata.json'
            if metadata_file.exists():
                stat = metadata_file.stat()
                versions.append((version_dir, stat.st_mtime))
        
        # Sort by modification time (newest first)
        versions.sort(key=lambda x: x[1], reverse=True)
        
        # Keep only N most recent versions
        for version_dir, _ in versions[keep_versions:]:
            print(f"Removing old version: {version_dir}")
            import shutil
            shutil.rmtree(version_dir)
            
    print(f"Cleanup complete. Kept {keep_versions} versions per model.")

if __name__ == '__main__':
    cleanup_old_models()
```

Run weekly:
```bash
0 2 * * 0 /home/pi/sysgrow/venv/bin/python /home/pi/sysgrow/scripts/cleanup_old_models.py
```

---

## 🔥 Thermal Management

### 1. Temperature Monitoring

```python
# Add to app initialization
import subprocess

def check_cpu_temp():
    """Check Raspberry Pi CPU temperature."""
    try:
        temp_str = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        temp = float(temp_str.split('=')[1].split("'")[0])
        return temp
    except:
        return None

def thermal_throttle_protection():
    """Reduce load if temperature too high."""
    temp = check_cpu_temp()
    if temp and temp > 75:
        logger.warning(f"High temperature ({temp}°C), throttling AI services")
        return True
    return False

# Use in continuous monitoring
def _monitor_unit(self, unit_id: int):
    if thermal_throttle_protection():
        logger.info("Skipping monitoring due to thermal throttling")
        return
    # ... proceed with monitoring
```

### 2. Hardware Setup

1. **Essential**: Install heatsinks on CPU, RAM, and USB controller
2. **Recommended**: Add a 5V fan (40mm or larger)
3. **Optimal**: Use official Active Cooler or Argon ONE case

---

## 📈 Performance Benchmarks

### Expected Performance (Raspberry Pi 4, 4GB)

| Operation | Time | Notes |
|-----------|------|-------|
| Sensor reading | <50ms | Direct GPIO/I2C |
| Disease prediction | 200-500ms | With caching: <50ms |
| Growth analysis | 100-300ms | Lightweight computation |
| Model training (small) | 2-5 min | 100-500 samples |
| Model training (large) | 15-30 min | 1000+ samples |
| Continuous monitoring loop | 5-10s | Per unit |

### RAM Usage

| Component | Typical RAM |
|-----------|-------------|
| Base Flask app | 150-200 MB |
| ML models loaded | 50-100 MB |
| Continuous monitor | 100-150 MB |
| Total (steady state) | 400-600 MB |
| Training spike | +300-500 MB |

---

## 🐛 Troubleshooting

### Issue: Out of Memory During Training

```python
# Solution 1: Train on smaller batches
def train_with_chunking(self, df, chunk_size=100):
    """Train incrementally on data chunks."""
    model = None
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        if model is None:
            model = RandomForestClassifier(...)
            model.fit(chunk_X, chunk_y)
        else:
            # Partial fit for online learning
            model.n_estimators += 10
            model.fit(chunk_X, chunk_y, warm_start=True)
    return model

# Solution 2: Use joblib memory mapping
from joblib import Memory
memory = Memory('/tmp/joblib_cache', verbose=0)

@memory.cache
def train_cached(X, y):
    # Training results cached to disk
    ...
```

### Issue: Slow Predictions

```bash
# Check for thermal throttling
vcgencmd get_throttled

# If throttled (0x50000 or similar):
# 1. Improve cooling
# 2. Reduce continuous monitoring frequency
# 3. Use prediction caching
```

### Issue: High CPU Usage

```python
# Limit scikit-learn parallelism
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

# Use fewer workers in Gunicorn
workers = 1  # For Pi 3/4 with 2GB RAM
```

---

## ✅ Deployment Checklist

- [ ] Raspberry Pi OS (64-bit) installed and updated
- [ ] Python 3.11+ with virtual environment
- [ ] All dependencies installed (optimized versions)
- [ ] Redis running and enabled
- [ ] Swap increased to 2GB
- [ ] Models directory created with proper permissions
- [ ] Systemd service configured and running
- [ ] Gunicorn workers tuned for hardware
- [ ] Nginx reverse proxy configured
- [ ] Cooling solution installed (heatsink + fan)
- [ ] Monitoring scripts in cron
- [ ] Log rotation configured
- [ ] Backup strategy in place
- [ ] Access via local network tested

---

## 🚀 Next Steps

1. **Start with Phase 1**: Deploy continuous monitoring only
2. **Monitor resource usage**: Use `htop` and `scripts/monitor_pi.sh`
3. **Tune as needed**: Adjust check intervals and worker counts
4. **Phase 2**: Add training data collection
5. **Phase 3**: Enable ML model training (test off-peak hours)
6. **Phase 4**: Add advanced features incrementally

---

## 📚 Resources

- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)
- [scikit-learn Performance Tips](https://scikit-learn.org/stable/computing/scaling_strategies.html)
- [Flask Optimization](https://flask.palletsprojects.com/en/stable/deploying/)
- [Gunicorn Deployment](https://docs.gunicorn.org/en/stable/deploy.html)

---

**Remember**: Start simple, monitor performance, and scale features based on your specific hardware and needs. The AI features are designed to be incrementally adoptable!
