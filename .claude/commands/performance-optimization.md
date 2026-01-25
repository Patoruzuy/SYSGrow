# Performance Optimization Guide

**Target Platform**: Raspberry Pi 3B+ / 4 (1-4GB RAM)

This document provides performance analysis guidelines and optimization strategies specifically tailored for running SYSGrow on resource-constrained Raspberry Pi hardware.

## Critical Performance Principles

### 1. Memory is Precious
- **Never load entire datasets**: Always paginate (max 500 items)
- **Prune old data**: Auto-delete sensor readings > 30 days
- **Use generators**: Avoid materializing large lists
- **Lazy load heavy modules**: Import scikit-learn, pandas only when needed
- **Cache intelligently**: LRU cache with strict size limits (≤100 items)

### 2. CPU Time is Limited
- **Throttle ML inference**: Max 1/min per model
- **Batch operations**: Group database writes, MQTT messages
- **Avoid polling**: Use event-driven architecture where possible
- **Profile before optimizing**: Use `cProfile` to find actual bottlenecks
- **Simple algorithms**: O(n log n) is often good enough; O(n²) rarely is

### 3. I/O is Expensive
- **SQLite WAL mode**: Essential for concurrency (enabled by default)
- **Connection pooling**: Limit to 5-10 connections (not 20-50)
- **Batch writes**: Use transactions for multiple inserts
- **Minimize disk I/O**: Log at WARNING level in production
- **MQTT QoS 1**: Balance reliability and performance (not QoS 2)

## Areas to Analyze

### 1. Database & Data Access

#### Common Issues

**N+1 Query Problems**:
```python
# ❌ BAD: Loads plants one-by-one
def get_plants_with_sensors():
    plants = db.query(Plant).all()
    for plant in plants:
        sensors = db.query(Sensor).filter_by(plant_id=plant.id).all()
        # O(n) queries!

# ✅ GOOD: Single query with join
def get_plants_with_sensors():
    return (db.query(Plant)
              .options(joinedload(Plant.sensors))
              .all())
```

**Missing Indexes**:
```sql
-- Essential indexes for SYSGrow
CREATE INDEX IF NOT EXISTS idx_sensor_readings_unit_timestamp 
ON SensorReadings(unit_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_timestamp 
ON SensorReadings(sensor_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_device_state_actuator_time 
ON DeviceStateHistory(actuator_id, changed_at);
```

**Pagination Enforcement**:
```python
# ❌ BAD: Unbounded query
def get_sensor_readings(sensor_id):
    return db.query(SensorReading).filter_by(sensor_id=sensor_id).all()

# ✅ GOOD: Paginated query
def get_sensor_readings(sensor_id, limit=50, offset=0):
    return (db.query(SensorReading)
              .filter_by(sensor_id=sensor_id)
              .order_by(SensorReading.timestamp.desc())
              .limit(min(limit, 500))  # Cap at 500
              .offset(offset)
              .all())
```

**Data Pruning**:
```python
# Auto-prune old sensor readings (run daily via cron)
def prune_old_sensor_data(days=30):
    cutoff = datetime.now() - timedelta(days=days)
    deleted = (db.query(SensorReading)
                 .filter(SensorReading.timestamp < cutoff)
                 .delete(synchronize_session=False))
    db.commit()
    return deleted
```

#### Checklist
- [ ] All list queries have `LIMIT` clause (max 500)
- [ ] Indexes exist on frequently queried columns
- [ ] Related data loaded with `joinedload()` or `subqueryload()`
- [ ] Old data pruned regularly (sensor readings, logs)
- [ ] Connection pool size ≤ 10
- [ ] WAL mode enabled (`PRAGMA journal_mode=WAL`)

### 2. Algorithm Efficiency

#### Time Complexity Rules

**Target Complexities**:
- **O(1)**: Dictionary lookups, array indexing
- **O(log n)**: Binary search, balanced trees
- **O(n)**: Linear scans (acceptable for small n < 1000)
- **O(n log n)**: Sorting, merge operations
- **❌ O(n²)**: Nested loops over large datasets (avoid!)

#### Common Issues

**Nested Loops**:
```python
# ❌ BAD: O(n²) - checks every sensor against every threshold
def check_all_thresholds(sensors, thresholds):
    violations = []
    for sensor in sensors:  # O(n)
        for threshold in thresholds:  # O(m)
            if sensor.type == threshold.sensor_type:
                if sensor.value > threshold.max_value:
                    violations.append((sensor, threshold))
    return violations

# ✅ GOOD: O(n + m) - single pass with lookup dict
def check_all_thresholds(sensors, thresholds):
    threshold_map = {t.sensor_type: t for t in thresholds}  # O(m)
    violations = []
    for sensor in sensors:  # O(n)
        threshold = threshold_map.get(sensor.type)
        if threshold and sensor.value > threshold.max_value:
            violations.append((sensor, threshold))
    return violations
```

**Redundant Calculations**:
```python
# ❌ BAD: Recalculates VPD for every sensor reading
def analyze_vpd_trend(readings):
    vpd_values = []
    for reading in readings:
        temp = reading.temperature
        humidity = reading.humidity
        vpd = calculate_vpd(temp, humidity)  # Expensive calculation
        vpd_values.append(vpd)
    return vpd_values

# ✅ GOOD: Memoized calculation
from functools import lru_cache

@lru_cache(maxsize=128)
def calculate_vpd(temp, humidity):
    # Expensive calculation cached
    ...

def analyze_vpd_trend(readings):
    return [calculate_vpd(r.temperature, r.humidity) for r in readings]
```

**Data Structure Choice**:
```python
# ❌ BAD: List lookup is O(n)
active_sensors = [1, 3, 5, 7, 9]
if sensor_id in active_sensors:  # O(n)
    process_sensor(sensor_id)

# ✅ GOOD: Set lookup is O(1)
active_sensors = {1, 3, 5, 7, 9}
if sensor_id in active_sensors:  # O(1)
    process_sensor(sensor_id)
```

#### Checklist
- [ ] No O(n²) loops over large datasets (n > 100)
- [ ] Expensive calculations memoized with `@lru_cache`
- [ ] Dictionary/set lookups used instead of list searches
- [ ] Sorting used only when necessary
- [ ] Generators used for large sequences

### 3. Memory Management

#### Memory Monitoring

**Use these tools on Raspberry Pi**:
```bash
# System memory
free -h
htop

# Python process memory
python -c "import psutil; print(psutil.Process().memory_info())"

# Memory profiling
python -m memory_profiler script.py
```

#### Common Issues

**Loading Large Datasets**:
```python
# ❌ BAD: Loads all readings into memory
def export_all_readings():
    readings = SensorReading.query.all()  # Could be 100k+ rows
    csv_data = convert_to_csv(readings)
    return csv_data

# ✅ GOOD: Stream data in chunks
def export_all_readings():
    def generate():
        chunk_size = 1000
        offset = 0
        while True:
            chunk = (SensorReading.query
                     .limit(chunk_size)
                     .offset(offset)
                     .all())
            if not chunk:
                break
            yield convert_chunk_to_csv(chunk)
            offset += chunk_size
    
    return Response(generate(), mimetype='text/csv')
```

**Object Accumulation**:
```python
# ❌ BAD: Grows unbounded in long-running process
class SensorCache:
    def __init__(self):
        self.cache = {}  # No size limit!
    
    def add_reading(self, sensor_id, reading):
        if sensor_id not in self.cache:
            self.cache[sensor_id] = []
        self.cache[sensor_id].append(reading)

# ✅ GOOD: LRU cache with size limit
from collections import OrderedDict

class SensorCache:
    def __init__(self, maxsize=100):
        self.cache = OrderedDict()
        self.maxsize = maxsize
    
    def add_reading(self, sensor_id, reading):
        if sensor_id in self.cache:
            self.cache.move_to_end(sensor_id)
        self.cache[sensor_id] = reading
        
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)  # Remove oldest
```

**Heavy Module Imports**:
```python
# ❌ BAD: Imports at module level (always loaded)
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier

def predict_disease(features):
    # Uses ML libraries
    ...

# ✅ GOOD: Lazy import inside function
def predict_disease(features):
    import pandas as pd  # Only loaded when needed
    from sklearn.ensemble import RandomForestClassifier
    
    # Uses ML libraries
    ...
```

#### Checklist
- [ ] Monitor memory with `htop` during development
- [ ] Use generators for large sequences
- [ ] LRU caches have `maxsize` parameter
- [ ] Heavy modules lazy-loaded (pandas, sklearn)
- [ ] Long-running processes don't accumulate objects
- [ ] Test memory usage under realistic load

### 4. Async & Concurrency

**SYSGrow Context**: We use threading (not asyncio) on Raspberry Pi for simplicity and compatibility with hardware libraries.

#### Threading Guidelines

**Thread Pool Sizing**:
```python
# ❌ BAD: Too many threads on Pi
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=50)  # Way too many!

# ✅ GOOD: Conservative thread count
executor = ThreadPoolExecutor(max_workers=4)  # 2x CPU cores typical
```

**Blocking Operations**:
```python
# ❌ BAD: Blocks main thread
def poll_all_sensors():
    readings = []
    for sensor in sensors:
        reading = sensor.read()  # Could take 1-5 seconds!
        readings.append(reading)
    return readings

# ✅ GOOD: Non-blocking with threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def poll_all_sensors():
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(s.read): s for s in sensors}
        readings = []
        for future in as_completed(futures, timeout=10):
            try:
                reading = future.result()
                readings.append(reading)
            except Exception as e:
                logger.error(f"Sensor read failed: {e}")
        return readings
```

**SocketIO Message Batching**:
```python
# ❌ BAD: Emits message per sensor (hundreds of events!)
def broadcast_sensor_updates(readings):
    for reading in readings:
        socketio.emit('sensor_update', reading)

# ✅ GOOD: Batches messages (1 event)
def broadcast_sensor_updates(readings):
    socketio.emit('sensor_updates_batch', {'readings': readings})
```

#### Checklist
- [ ] Thread pool size ≤ 2x CPU cores (typically 4-8 on Pi)
- [ ] Blocking I/O moved to background threads
- [ ] SocketIO messages batched when possible
- [ ] Timeouts set for all network operations (5-10s)
- [ ] Thread cleanup handled properly

### 5. Network & I/O

#### MQTT Optimization

**QoS Selection**:
```python
# ❌ BAD: QoS 2 has significant overhead
client.publish(topic, payload, qos=2)

# ✅ GOOD: QoS 1 balances reliability and performance
client.publish(topic, payload, qos=1)
```

**Message Batching**:
```python
# ❌ BAD: Individual messages
for sensor_id, value in readings.items():
    mqtt_client.publish(f"sensor/{sensor_id}", value)

# ✅ GOOD: Batch payload
batch_payload = json.dumps(readings)
mqtt_client.publish("sensors/batch", batch_payload)
```

**Persistent Connections**:
```python
# ❌ BAD: Reconnects for each message
def send_command(device_id, command):
    client = mqtt.Client()
    client.connect("localhost", 1883)
    client.publish(f"device/{device_id}/cmd", command)
    client.disconnect()

# ✅ GOOD: Reuse connection
class MQTTClientWrapper:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.connect("localhost", 1883)
        self.client.loop_start()  # Background thread
    
    def send_command(self, device_id, command):
        self.client.publish(f"device/{device_id}/cmd", command)
```

#### Database I/O

**Batch Writes**:
```python
# ❌ BAD: Individual inserts (slow)
for reading in sensor_readings:
    db.session.add(SensorReading(**reading))
    db.session.commit()  # N commits!

# ✅ GOOD: Batch insert (1 transaction)
db.session.bulk_insert_mappings(SensorReading, sensor_readings)
db.session.commit()  # 1 commit
```

**WAL Mode Configuration**:
```python
# Essential SQLite settings for Raspberry Pi
SQLALCHEMY_ENGINE_OPTIONS = {
    'connect_args': {
        'timeout': 15,  # Wait up to 15s for lock
        'check_same_thread': False
    },
    'pool_pre_ping': True,
    'pool_size': 5,  # Conservative for Pi
    'max_overflow': 10,
    'pool_recycle': 3600
}

# Enable WAL mode (in sqlite_handler.py)
cursor.execute("PRAGMA journal_mode=WAL")
cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes
cursor.execute("PRAGMA cache_size=-64000")    # 64MB cache
```

#### Checklist
- [ ] MQTT uses QoS 1 (not 2)
- [ ] MQTT connections persistent (not one-shot)
- [ ] Database writes batched in transactions
- [ ] SQLite WAL mode enabled
- [ ] Connection pool size ≤ 10
- [ ] Network timeouts set (5-10s)
- [ ] Exponential backoff for reconnections

### 6. Frontend Performance

#### JavaScript Optimization

**DOM Manipulation**:
```javascript
// ❌ BAD: Multiple DOM updates (causes reflows)
sensors.forEach(sensor => {
    const elem = document.getElementById(`sensor-${sensor.id}`);
    elem.textContent = sensor.value;
    elem.className = sensor.status;
});

// ✅ GOOD: Batch updates with DocumentFragment
const fragment = document.createDocumentFragment();
sensors.forEach(sensor => {
    const elem = document.getElementById(`sensor-${sensor.id}`);
    const clone = elem.cloneNode(true);
    clone.textContent = sensor.value;
    clone.className = sensor.status;
    fragment.appendChild(clone);
});
elem.parentNode.replaceChildren(fragment);
```

**Event Delegation**:
```javascript
// ❌ BAD: Individual event listeners
sensors.forEach(sensor => {
    document.getElementById(`sensor-${sensor.id}`)
            .addEventListener('click', handleSensorClick);
});

// ✅ GOOD: Single delegated listener
document.getElementById('sensor-grid')
        .addEventListener('click', (e) => {
            if (e.target.matches('.sensor-card')) {
                handleSensorClick(e);
            }
        });
```

**Debouncing/Throttling**:
```javascript
// ❌ BAD: Fires API call on every keystroke
searchInput.addEventListener('input', (e) => {
    fetchSearchResults(e.target.value);  // Too many calls!
});

// ✅ GOOD: Debounced API call
const debouncedSearch = debounce((query) => {
    fetchSearchResults(query);
}, 300);

searchInput.addEventListener('input', (e) => {
    debouncedSearch(e.target.value);
});

function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
}
```

#### Asset Optimization

**Cache Headers**:
```python
# In Flask config
SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year for static assets

@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.cache_control.max_age = 31536000
        response.cache_control.public = True
    return response
```

**Lazy Loading Charts**:
```javascript
// ❌ BAD: Loads Chart.js immediately
import Chart from 'chart.js';

function initDashboard() {
    renderAllCharts();
}

// ✅ GOOD: Lazy loads Chart.js when needed
function initDashboard() {
    // Other initialization...
}

async function showCharts() {
    const { Chart } = await import('https://cdn.jsdelivr.net/npm/chart.js');
    renderAllCharts(Chart);
}
```

#### Checklist
- [ ] DOM updates batched (use DocumentFragment)
- [ ] Event delegation used for dynamic content
- [ ] Debounce/throttle expensive operations (search, scroll)
- [ ] Charts lazy-loaded (not on page load)
- [ ] Static assets have far-future cache headers
- [ ] No blocking CSS/JS in `<head>`
- [ ] Images optimized (WebP, lazy loading)

### 7. Caching Strategy

#### Application-Level Caching

**In-Memory Cache** (current approach):
```python
from functools import lru_cache
from datetime import datetime, timedelta

# ✅ Cache expensive computations
@lru_cache(maxsize=128)
def get_plant_profile(plant_type: str) -> dict:
    """Cached plant profile lookup."""
    with open('plants_info.json') as f:
        plants = json.load(f)
    return plants.get(plant_type, {})

# ✅ Time-based cache invalidation
class TimedCache:
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, datetime.now())

# Usage
sensor_cache = TimedCache(ttl_seconds=60)

def get_sensor_reading(sensor_id):
    cached = sensor_cache.get(sensor_id)
    if cached:
        return cached
    
    reading = fetch_from_database(sensor_id)
    sensor_cache.set(sensor_id, reading)
    return reading
```

**HTTP Caching**:
```python
from flask import make_response

@app.route('/api/plants/guide')
def get_plants_guide():
    """Static data - cache for 1 hour."""
    data = load_plants_guide()
    response = make_response(jsonify(data))
    response.cache_control.max_age = 3600  # 1 hour
    response.cache_control.public = True
    return response

@app.route('/api/sensors/current')
def get_current_sensors():
    """Real-time data - no caching."""
    data = fetch_current_sensors()
    response = make_response(jsonify(data))
    response.cache_control.no_store = True
    return response
```

#### Client-Side Caching

**LocalStorage Cache**:
```javascript
// Utility for client-side caching
class CacheService {
    constructor(prefix = 'sysgrow_', ttl = 300000) {
        this.prefix = prefix;
        this.ttl = ttl;  // 5 minutes default
    }
    
    get(key) {
        const item = localStorage.getItem(this.prefix + key);
        if (!item) return null;
        
        const { value, timestamp } = JSON.parse(item);
        if (Date.now() - timestamp > this.ttl) {
            this.remove(key);
            return null;
        }
        return value;
    }
    
    set(key, value) {
        const item = {
            value,
            timestamp: Date.now()
        };
        localStorage.setItem(this.prefix + key, JSON.stringify(item));
    }
    
    remove(key) {
        localStorage.removeItem(this.prefix + key);
    }
}

// Usage in API calls
const cache = new CacheService('sysgrow_', 60000);  // 1 min TTL

async function fetchPlantGuide() {
    const cached = cache.get('plant_guide');
    if (cached) return cached;
    
    const response = await fetch('/api/plants/guide');
    const data = await response.json();
    cache.set('plant_guide', data);
    return data;
}
```

#### Checklist
- [ ] Expensive computations memoized (`@lru_cache`)
- [ ] Database query results cached (with TTL)
- [ ] Static data cached with long max-age (1 hour+)
- [ ] Real-time data not cached (`no-store`)
- [ ] Client-side cache for API responses (localStorage)
- [ ] Cache invalidation strategy in place
- [ ] Cache size limits enforced (LRU eviction)

## Performance Measurement

### Profiling Tools

**Python Profiling**:
```bash
# CPU profiling
python -m cProfile -o profile.stats smart_agriculture_app.py
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumtime'); p.print_stats(20)"

# Memory profiling
pip install memory_profiler
python -m memory_profiler scripts/analyze_memory.py

# Line-by-line profiling
pip install line_profiler
kernprof -l -v script.py
```

**Flask Request Profiling**:
```python
from werkzeug.middleware.profiler import ProfilerMiddleware

if app.config['DEBUG']:
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])
```

**Database Query Analysis**:
```python
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Shows all SQL queries with execution time
```

### Monitoring Metrics

**Key Metrics to Track**:
```python
import psutil
import time

class PerformanceMonitor:
    def __init__(self):
        self.process = psutil.Process()
    
    def get_metrics(self):
        return {
            'cpu_percent': self.process.cpu_percent(interval=1),
            'memory_mb': self.process.memory_info().rss / 1024 / 1024,
            'threads': self.process.num_threads(),
            'open_files': len(self.process.open_files()),
            'connections': len(self.process.connections())
        }

# Log metrics periodically
monitor = PerformanceMonitor()
metrics = monitor.get_metrics()
logger.info(f"Performance: {metrics}")
```

**Response Time Tracking**:
```python
import time
from functools import wraps

def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.debug(f"{func.__name__} took {elapsed:.3f}s")
        return result
    return wrapper

@timed
def slow_operation():
    # ...
```

### Benchmarking

**Load Testing**:
```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Test endpoint
ab -n 1000 -c 10 http://localhost:5001/api/sensors/current

# Stress test
ab -n 10000 -c 50 -t 60 http://localhost:5001/api/dashboard/status
```

**Memory Leak Detection**:
```python
import tracemalloc
import linecache

tracemalloc.start()

# ... run application ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("[ Top 10 memory allocations ]")
for stat in top_stats[:10]:
    print(stat)
```

## Optimization Workflow

### 1. Measure First
- Profile code to identify actual bottlenecks
- Don't optimize based on assumptions
- Use `cProfile`, `memory_profiler`, `line_profiler`

### 2. Set Performance Goals
- API response time: < 200ms (p95)
- Database queries: < 50ms (p95)
- Memory usage: < 200MB steady state
- CPU usage: < 50% average

### 3. Optimize Iteratively
- Fix one bottleneck at a time
- Re-measure after each change
- Verify performance gains

### 4. Document Changes
- Note optimizations in code comments
- Update this document with new patterns
- Share learnings with team

## Raspberry Pi Specific Optimizations

### System-Level Tuning

**Swap Configuration**:
```bash
# Increase swap for stability (but avoid using it)
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

**CPU Governor**:
```bash
# Use performance governor for consistent speed
sudo apt-get install cpufrequtils
sudo cpufreq-set -g performance
```

**Filesystem**:
```bash
# Use ext4 with noatime for better performance
sudo nano /etc/fstab
# Add noatime to mount options
```

### Python Optimizations

**Disable Debug Mode**:
```bash
export FLASK_ENV=production
export FLASK_DEBUG=0
export LOG_LEVEL=WARNING
```

**Use PyPy** (if compatible):
```bash
# PyPy can be 2-5x faster for CPU-bound code
sudo apt-get install pypy3
pypy3 -m pip install -r requirements.txt
pypy3 smart_agriculture_app.py
```

**Compiled Extensions**:
```bash
# Ensure numpy/scipy use optimized BLAS
sudo apt-get install libatlas-base-dev
```

### Service Configuration

**Systemd Unit** (`/etc/systemd/system/sysgrow.service`):
```ini
[Unit]
Description=SYSGrow Smart Agriculture
After=network.target mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/sysgrow
Environment="PATH=/home/pi/sysgrow/venv/bin"
Environment="FLASK_ENV=production"
Environment="LOG_LEVEL=WARNING"
ExecStart=/home/pi/sysgrow/venv/bin/python smart_agriculture_app.py
Restart=always
RestartSec=10

# Resource limits
MemoryLimit=400M
CPUQuota=150%

[Install]
WantedBy=multi-user.target
```

**Log Rotation** (`/etc/logrotate.d/sysgrow`):
```
/home/pi/sysgrow/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 pi pi
}
```

## Common Performance Anti-Patterns

### ❌ Don't Do This

1. **Loading Everything at Startup**:
   ```python
   # Loads 100MB+ of models/data
   ml_models = load_all_models()
   plant_database = load_all_plants()
   ```

2. **Unbounded Loops**:
   ```python
   while True:
       data = fetch_all_data()  # No limit!
       process(data)
   ```

3. **Synchronous Blocking**:
   ```python
   for sensor in sensors:
       reading = requests.get(f"http://{sensor.ip}/read", timeout=30)
   ```

4. **No Error Handling**:
   ```python
   result = some_operation()  # Crashes on error
   ```

5. **Premature Optimization**:
   ```python
   # Micro-optimizing before profiling
   value = (x << 1) if x < 128 else (x * 2)
   ```

### ✅ Do This Instead

1. **Lazy Loading**:
   ```python
   def get_ml_model(model_name):
       if model_name not in _model_cache:
           _model_cache[model_name] = load_model(model_name)
       return _model_cache[model_name]
   ```

2. **Pagination**:
   ```python
   def fetch_data(limit=50, offset=0):
       return query.limit(min(limit, 500)).offset(offset).all()
   ```

3. **Concurrent I/O**:
   ```python
   with ThreadPoolExecutor(max_workers=4) as executor:
       futures = [executor.submit(read_sensor, s) for s in sensors]
       results = [f.result(timeout=10) for f in as_completed(futures)]
   ```

4. **Robust Error Handling**:
   ```python
   try:
       result = some_operation()
   except Exception as e:
       logger.error(f"Operation failed: {e}")
       return default_value
   ```

5. **Profile First**:
   ```python
   # Measure, then optimize
   with profiler():
       result = some_operation()
   ```

## Performance Checklist

Use this checklist when reviewing code or adding features:

**Database**:
- [ ] Queries paginated (max 500 items)
- [ ] Indexes on frequently queried columns
- [ ] Related data eager-loaded (joins)
- [ ] Old data pruned automatically
- [ ] Connection pool size ≤ 10
- [ ] WAL mode enabled

**Memory**:
- [ ] No unbounded data structures
- [ ] LRU caches have `maxsize`
- [ ] Heavy modules lazy-loaded
- [ ] Generators used for large sequences
- [ ] Memory profiled under load

**CPU**:
- [ ] No O(n²) loops over large data
- [ ] Expensive calculations memoized
- [ ] ML inference throttled
- [ ] Background tasks threaded
- [ ] Profiled before optimizing
**I/O**:
- [ ] MQTT uses QoS 1
- [ ] MQTT connections persistent
- [ ] Database writes batched
- [ ] Network timeouts set (5-10s)
- [ ] SQLite WAL mode enabled
- [ ] Connection pool size ≤ 10

**Frontend**:
- [ ] DOM updates batched
- [ ] Event delegation used
- [ ] Debounce/throttle expensive ops
- [ ] Charts lazy-loaded
- [ ] Static assets cached (1 year)
- [ ] No blocking CSS/JS in `<head>`
- [ ] Images optimized (WebP, lazy loading)
Please analyze and optimize the performance of SYSGrow on Raspberry Pi hardware.
Follow these steps:
1. Profile the application using `cProfile` and `memory_profiler` to identify bottlenecks.
2. Review database queries for pagination, indexing, and batching.
3. Analyze algorithms for time complexity and optimize as needed.
4. Check memory usage patterns and implement caching strategies.
5. Evaluate threading and concurrency for I/O-bound tasks.
6. Optimize MQTT and database I/O operations.
7. Review frontend code for DOM manipulation, event handling, and asset loading.
8. Implement optimizations iteratively, measuring performance after each change.
Remember to document all changes and update this performance guide with any new patterns or strategies discovered during optimization.
Please analyze and optimize the performance of SYSGrow on Raspberry Pi hardware.