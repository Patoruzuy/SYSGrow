// --- Utilities ---
const $ = (id) => document.getElementById(id);
const connDot = $('conn-dot');
const toastEl = $('toast');
let hasDashboardSnapshot = false;

function showToast(msg, isError=false) {
  toastEl.textContent = msg;
  toastEl.classList.toggle('error', !!isError);
  toastEl.classList.add('show');
  setTimeout(() => toastEl.classList.remove('show'), 2200);
}

function fmt(n, digits=1) {
  if (n === undefined || n === null || isNaN(n)) return '—';
  return Number(n).toFixed(digits);
}

// --- Sensor chip helpers ---
function setChipValue(id, value, unit, status) {
  const chip = $(id);
  const valueEl = chip.querySelector('strong');
  valueEl.textContent = value;
  chip.classList.remove('status-ok','status-warn','status-bad');
  if (!status) return;
  const s = (status+'').toLowerCase();
  if (s.includes('critical') || s.includes('high') || s.includes('low')) chip.classList.add('status-bad');
  else if (s.includes('warn')) chip.classList.add('status-warn');
  else chip.classList.add('status-ok');
}

function normalizeSnapshotPayload(snapshot) {
  const metrics = snapshot?.metrics;
  if (!metrics || typeof metrics !== 'object') return {};

  const out = {};
  const applyMetric = (metricKey, outputKey, statusKey) => {
    const metric = metrics[metricKey];
    if (!metric || metric.value === undefined || metric.value === null) return;
    out[outputKey] = metric.value;
    const status = metric?.source?.status;
    if (status) out[statusKey] = status;
  };

  applyMetric('temperature', 'temperature', 'temperature_status');
  applyMetric('humidity', 'humidity', 'humidity_status');
  applyMetric('co2', 'co2_level', 'co2_status');
  applyMetric('lux', 'light_level', 'light_status');
  applyMetric('soil_moisture', 'soil_moisture', 'soil_moisture_status');

  return out;
}

function normalizeDeviceReadingPayload(payload, options = {}) {
  const readings = payload?.readings;
  if (!readings || typeof readings !== 'object') return {};

  const onlyExtras = options.onlyExtras === true;
  const out = {};
  const pick = (keys) => {
    for (const key of keys) {
      const val = readings[key];
      if (val !== undefined && val !== null) return val;
    }
    return null;
  };

  if (!onlyExtras) {
    const temperature = pick(['temperature']);
    if (temperature !== null) out.temperature = temperature;

    const humidity = pick(['humidity']);
    if (humidity !== null) out.humidity = humidity;

    const co2 = pick(['co2', 'co2_ppm']);
    if (co2 !== null) out.co2_level = co2;

    const light = pick(['lux', 'illuminance', 'illuminance_lux', 'light_level']);
    if (light !== null) out.light_level = light;

    const soil = pick(['soil_moisture']);
    if (soil !== null) out.soil_moisture = soil;
  }

  const energy = pick(['energy_usage', 'energy', 'power', 'power_watts']);
  if (energy !== null) out.energy_usage = energy;

  const status = payload?.status;
  if (status) {
    if (Object.prototype.hasOwnProperty.call(out, 'temperature')) out.temperature_status = status;
    if (Object.prototype.hasOwnProperty.call(out, 'humidity')) out.humidity_status = status;
    if (Object.prototype.hasOwnProperty.call(out, 'co2_level')) out.co2_status = status;
    if (Object.prototype.hasOwnProperty.call(out, 'light_level')) out.light_status = status;
    if (Object.prototype.hasOwnProperty.call(out, 'soil_moisture')) out.soil_moisture_status = status;
    if (Object.prototype.hasOwnProperty.call(out, 'energy_usage')) out.energy_status = status;
  }

  return out;
}

function normalizePayload(payload, options = {}) {
  if (!payload || typeof payload !== 'object') return {};
  if (payload.metrics) return normalizeSnapshotPayload(payload);
  if (payload.readings) return normalizeDeviceReadingPayload(payload, options);
  return payload;
}

function updateFromPayload(raw, options = {}) {
  const d = normalizePayload(raw, options);
  if (!d || typeof d !== 'object') return;
  const now = new Date().toLocaleTimeString();
  $('last-updated').textContent = now;

  if ('temperature' in d) setChipValue('chip-temp', fmt(d.temperature), '°C', d.temperature_status || 'ok');
  if ('humidity' in d)    setChipValue('chip-hum',  fmt(d.humidity),    '%',  d.humidity_status || 'ok');
  if ('co2_level' in d)   setChipValue('chip-co2',  fmt(d.co2_level,0), 'ppm', d.co2_status || 'ok');
  if ('light_level' in d) setChipValue('chip-light',fmt(d.light_level,0),'lux', d.light_status || 'ok');
  if ('soil_moisture' in d) setChipValue('chip-soil', fmt(d.soil_moisture), '%', d.soil_moisture_status || 'ok');
  if ('energy_usage' in d)  setChipValue('chip-energy', fmt(d.energy_usage,1), 'W', d.energy_status || 'ok');
}

// --- Socket.IO live feed using centralized socket manager ---
function initSocket() {
  // Get selected unit ID from body data attribute
  const unitIdStr = document.body.dataset.unitId || '';
  const selectedUnitId = unitIdStr !== '' ? parseInt(unitIdStr) : null;
  console.log('📍 Fullscreen unit ID:', selectedUnitId);
  
  // Use centralized socket manager
  import('/static/js/socket.js')
    .then(module => {
      const socketManager = module.default;
      
      // Listen for connection status
      socketManager.on('connection_status', (data) => {
        if (data.connected) {
          connDot.classList.add('connected');
        } else {
          connDot.classList.remove('connected');
        }
      });
      
      // Listen for dashboard snapshots (priority metrics)
      socketManager.on('dashboard_snapshot', (data) => {
        if (selectedUnitId !== null && data && data.unit_id !== undefined && data.unit_id !== selectedUnitId) {
          console.log(`⏭️ Skipping dashboard snapshot from unit ${data.unit_id} (selected: ${selectedUnitId})`);
          return;
        }
        hasDashboardSnapshot = true;
        updateFromPayload(data || {});
      });

      // Listen for per-device readings (fallback + extras like energy usage)
      socketManager.on('device_sensor_reading', (data) => {
        if (selectedUnitId !== null && data && data.unit_id !== undefined && data.unit_id !== selectedUnitId) {
          console.log(`⏭️ Skipping device reading from unit ${data.unit_id} (selected: ${selectedUnitId})`);
          return;
        }
        updateFromPayload(data || {}, { onlyExtras: hasDashboardSnapshot });
      });

      // Legacy fallback (if any sensors still emit sensor_update)
      socketManager.on('sensor_update', (data) => {
        if (selectedUnitId !== null && data && data.unit_id !== undefined && data.unit_id !== selectedUnitId) {
          console.log(`⏭️ Skipping sensor update from unit ${data.unit_id} (selected: ${selectedUnitId})`);
          return;
        }
        updateFromPayload(data || {});
      });

      console.log('✅ Fullscreen socket listeners ready');
    })
    .catch(error => {
      console.warn('⚠️ Socket.IO not available:', error);
    });
}

// --- Take photo handler ---
async function capturePhoto() {
  const btn = $('captureBtn');
  btn.disabled = true;

  // Get unit ID from query string, body data attribute, or default to first available
  const qsUnit = new URLSearchParams(location.search).get('unit_id');
  const dataUnit = document.body.dataset.unitId || '';
  const unitId = qsUnit || dataUnit;

  if (!unitId) {
    showToast('❌ No unit ID specified', true);
    btn.disabled = false;
    return;
  }

  const endpoint = `/api/growth/units/${unitId}/camera/capture`;

  try {
    const res = await fetch(endpoint, { method: 'POST' });
    let ok = false, message = '📸 Photo captured';
    if (res.headers.get('content-type')?.includes('application/json')) {
      const j = await res.json().catch(() => ({}));
      ok = j.status === 'success' || !!j.ok;
      if (!ok) message = j?.error?.message || j?.message || 'Failed to capture photo';
    } else {
      ok = res.ok;
      if (!ok) message = 'Failed to capture photo';
    }
    showToast(ok ? '📸 Photo captured' : `❌ ${message}`, !ok);
  } catch (e) {
    console.error(e);
    showToast('❌ Failed to capture photo', true);
  } finally {
    btn.disabled = false;
  }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  initSocket();
  $('captureBtn').addEventListener('click', capturePhoto);
});
