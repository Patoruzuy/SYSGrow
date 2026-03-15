const API = window.API;
if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before mqtt_sensor_uptime.js');
}

function getStatusClass(status) {
    if (!status) return '';
    const s = String(status).toLowerCase();
    if (s === 'online') return 'text-success';
    if (s === 'offline' || s === 'stale') return 'text-danger';
    return 'text-secondary';
}

async function fetchStatus() {
    try {
        // Using API wrapper if available, otherwise fallback to fetch
        // Note: API.Status.getStatus() calls /status/ (with trailing slash)
        // The original code called /status (without trailing slash)
        // Flask usually handles trailing slashes, but let's be careful.
        
        let data;
        try {
            // Try to use the API wrapper first
            // Note: API.Status.getStatus() might return the full response object or just data
            // depending on how apiRequest is implemented.
            // apiRequest returns data.data if present, or data.
            
            // However, /status endpoint might return { sensors: ... } directly or inside data.
            // Let's assume it returns JSON.
            
            const response = await fetch('/status');
            data = await response.json();
            
        } catch (e) {
            console.warn('Fetch /status failed, trying API wrapper', e);
            data = await API.Status.getStatus();
        }

        const sensors = data.sensors || {};
        const tbody = document.getElementById('sensorList');
        if (!tbody) return;
        
        tbody.innerHTML = '';

        const entries = Object.entries(sensors);
        if (entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3">No sensors reported.</td></tr>';
            return;
        }

        for (const [key, value] of entries) {
            const tr = document.createElement('tr');
            const status = value.status || 'unknown';
            tr.innerHTML = `
                <td>${key}</td>
                <td>${value.last_seen || '-'}</td>
                <td><span class="${getStatusClass(status)}">${status}</span></td>
            `;
            tbody.appendChild(tr);
        }
    } catch (e) {
        const tbody = document.getElementById('sensorList');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="3">Error loading data. Please try again.</td></tr>';
        }
        console.error('Failed to load status:', e);
    }
}

let intervalId;
export function setRefreshInterval() {
    const input = document.getElementById('refreshInterval');
    const seconds = parseInt(input.value, 10) || 30;
    if (intervalId) clearInterval(intervalId);
    intervalId = setInterval(fetchStatus, seconds * 1000);
}

export function initMqttSensorUptime() {
    document.addEventListener('DOMContentLoaded', () => {
        fetchStatus();
        setRefreshInterval();
        const input = document.getElementById('refreshInterval');
        if (input) input.addEventListener('change', setRefreshInterval);
        
        const form = document.getElementById('refreshForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                setRefreshInterval();
            });
        }
    });
}
