/**
 * System Health Dashboard
 * ==============================================
 */

const API = window.API;
if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before system_health.js');
}

// ============================================================
// DATA SERVICE
// ============================================================

class HealthDataService {
    async loadAllData() {
        try {
            const [overview, health, infra, units, devices] = await Promise.all([
                API.Insights.getDashboardOverview(),
                API.Health.getDetailed(),
                API.Health.getInfrastructure(),
                API.Health.getUnitsHealth(),
                API.Health.getDevicesHealth()
            ]);

            // Use backend-computed health scores if available, fallback to client-side calculation
            const healthWithScores = health?.health_scores
                ? { ...health, score: health.health_scores.overall, breakdown: health.health_scores.breakdown }
                : this.calculateHealthScore(health, infra);

            return {
                overview,
                health: healthWithScores,
                infra,
                units,
                devices
            };
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            throw error;
        }
    }

    /**
     * Calculate health score (fallback for legacy backend responses)
     * @deprecated - Backend now provides health_scores in /api/health/detailed response
     */
    calculateHealthScore(healthData, infraData) {
        let infrastructureScore = 100;
        let connectivityScore = 100;
        let sensorScore = 100;

        // Infrastructure score
        if (infraData) {
            if (infraData.apiStatus !== 'online') infrastructureScore -= 30;
            if (infraData.dbStatus !== 'connected') infrastructureScore -= 30;
            
            const storagePercent = healthData?.infrastructure_details?.storage?.percent || 0;
            if (storagePercent > 90) infrastructureScore -= 20;
            else if (storagePercent > 75) infrastructureScore -= 10;
        }

        // Connectivity score
        if (infraData?.mqttStatus !== 'connected') connectivityScore -= 40;

        // Sensor score
        if (healthData?.sensor_health) {
            const sh = healthData.sensor_health;
            if (sh.total_sensors > 0) {
                sensorScore = sh.average_success_rate || 0;
                if (sh.critical_sensors > 0) sensorScore = Math.min(sensorScore, 30);
                else if (sh.degraded_sensors > 0) sensorScore = Math.min(sensorScore, 60);
            } else {
                sensorScore = 50; // neutral
            }
        }

        const overallScore = (infrastructureScore * 0.4 + connectivityScore * 0.3 + sensorScore * 0.3);

        return {
            ...healthData,
            score: Math.round(overallScore),
            breakdown: {
                infrastructure: Math.round(infrastructureScore),
                connectivity: Math.round(connectivityScore),
                sensors: Math.round(sensorScore)
            }
        };
    }
}

// ============================================================
// UI RENDERER
// ============================================================

class HealthDashboardUI {
    constructor() {
        this.dataService = new HealthDataService();
    }

    renderAll(data) {
        this.renderHeroStatus(data.health, data.infra);
        this.renderMetrics(data.overview);
        this.renderInfrastructure(data.infra);
        this.renderResources(data.health, data.infra);
        this.renderUnits(data.units);
        this.renderDevices(data.devices);
        this.renderActivity(data.overview);
        this.renderAlertBanner(data.health);
        this.updateTimestamp();
    }

    renderHeroStatus(health, infra) {
        // Health Score Circle
        const score = health.score || 0;
        const circle = document.getElementById('score-circle');
        const scoreEl = document.getElementById('health-score');

        if (scoreEl) scoreEl.textContent = score;

        if (circle) {
            const circumference = 2 * Math.PI * 90;
            const offset = circumference - (score / 100) * circumference;
            circle.style.strokeDasharray = `${circumference} ${circumference}`;
            circle.style.strokeDashoffset = offset;

            // Color based on score
            const color = score >= 80 ? 'var(--success-500)' :
                         score >= 60 ? 'var(--warning-500)' :
                         'var(--error-500)';
            circle.style.stroke = color;
        }

        // Status Badge
        const statusBadge = document.getElementById('system-status');
        if (statusBadge) {
            const status = score >= 80 ? 'healthy' : score >= 60 ? 'degraded' : 'critical';
            const icon = score >= 80 ? 'check-circle' : score >= 60 ? 'exclamation-triangle' : 'times-circle';
            const text = score >= 80 ? 'All Systems Healthy' : score >= 60 ? 'System Degraded' : 'Critical Issues';

            statusBadge.className = `status-badge ${status}`;
            statusBadge.innerHTML = `<i class="fas fa-${icon}"></i><span>${text}</span>`;
            
            // Make clickable to show details
            statusBadge.onclick = () => this.showHealthDetails(health);
            statusBadge.title = 'Click to view health details';
        }

        // Uptime & Version
        this.setText('system-uptime', this.formatUptime(infra?.uptime || 0));
        this.setText('system-version', infra?.version || 'Unknown');
    }

    renderMetrics(overview) {
        const stats = overview?.stats || {};
        this.setText('metric-units', stats.total_units || stats.units || 0);
        this.setText('metric-plants', stats.total_plants || stats.plants || 0);
        this.setText('metric-devices', stats.active_devices || stats.devices || 0);
        this.setText('metric-alerts', stats.critical_alerts || stats.alerts || 0);
    }

    renderInfrastructure(infra) {
        this.setStatus('status-api', infra?.apiStatus);
        this.setStatus('status-db', infra?.dbStatus);
        this.setStatus('status-mqtt', infra?.mqttStatus);
        this.setStatus('status-ml', infra?.mlAvailable ? 'available' : 'unavailable');
        this.setStatus('status-zigbee', infra?.zigbeeEnabled ? 'enabled' : 'disabled');
    }

    renderResources(health, infra) {
        // Storage
        const storage = health?.infrastructure_details?.storage;
        if (storage) {
            const percent = storage.percent || 0;
            this.setText('storage-percent', `${percent.toFixed(1)}%`);
            this.setText('storage-detail', `${this.formatBytes(storage.used)} / ${this.formatBytes(storage.total)}`);

            const bar = document.getElementById('storage-bar');
            if (bar) {
                bar.style.width = `${percent}%`;
                bar.style.backgroundColor = percent > 90 ? 'var(--error-500)' :
                                            percent > 75 ? 'var(--warning-500)' :
                                            'var(--success-500)';
            }
        }

        // API Performance
        const metrics = health?.infrastructure_details?.api_metrics;
        if (metrics) {
            this.setText('api-response', `${metrics.avg_response_time_ms?.toFixed(0) || 0}ms`);
            this.setText('api-requests', metrics.total_requests?.toLocaleString() || '0');
            this.setText('api-errors', `${metrics.error_rate?.toFixed(2) || 0}%`);
        }

        // Health Breakdown
        if (health?.breakdown) {
            this.setBreakdownBar('mini-infra', 'score-infra', health.breakdown.infrastructure);
            this.setBreakdownBar('mini-conn', 'score-conn', health.breakdown.connectivity);
            this.setBreakdownBar('mini-sensor', 'score-sensor', health.breakdown.sensors);
        }
    }

    renderUnits(unitsData) {
        // unitsData structure: { units: [...], summary: {...} }
        const units = unitsData?.units || [];
        const unitsList = document.getElementById('units-list');
        const unitsCount = document.getElementById('units-count');

        if (unitsCount) {
            unitsCount.textContent = `(${units.length})`;
        }

        if (!unitsList) return;

        if (units.length === 0) {
            unitsList.innerHTML = '<div class="empty-state">No growth units configured</div>';
            return;
        }

        unitsList.innerHTML = units.map(unit => {
            const status = unit.status || 'unknown';
            const esc = window.escapeHtml || (t => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; });
            return `
                <div class="unit-card ${esc(status)}">
                    <div class="unit-header">
                        <span class="unit-name">${esc(unit.name || 'Unit ' + unit.unit_id)}</span>
                        <span class="unit-status-badge ${esc(status)}">${esc(status)}</span>
                    </div>
                    <div class="unit-stats">
                        <div class="unit-stat">
                            <i class="fas fa-thermometer-half"></i>
                            <span class="unit-stat-value">${unit.sensor_count || 0}</span>
                            <span class="unit-stat-label">Sensors</span>
                        </div>
                        <div class="unit-stat">
                            <i class="fas fa-toggle-on"></i>
                            <span class="unit-stat-value">${unit.actuator_count || 0}</span>
                            <span class="unit-stat-label">Actuators</span>
                        </div>
                        <div class="unit-stat">
                            <i class="fas fa-seedling"></i>
                            <span class="unit-stat-value">${unit.plant_count || 0}</span>
                            <span class="unit-stat-label">Plants</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderDevices(devicesData) {
        // devicesData structure: { sensors: {...}, actuators: {...}, by_unit: {...} }
        const sensors = devicesData?.sensors || {};
        const actuators = devicesData?.actuators || {};
        
        const totalDevices = (sensors.total || 0) + (actuators.total || 0);
        
        this.setText('devices-count', `(${totalDevices})`);
        this.setText('sensors-total', sensors.total || 0);
        this.setText('sensors-online', sensors.healthy || 0);
        this.setText('actuators-total', actuators.total || 0);
        this.setText('actuators-active', actuators.operational || 0);
    }

    renderActivity(overview) {
        const activities = overview?.activities || [];
        const feed = document.getElementById('activity-feed');

        if (!feed) return;

        if (activities.length === 0) {
            feed.innerHTML = '<div class="empty-state">No recent activity</div>';
            return;
        }

        feed.innerHTML = activities.slice(0, 10).map(item => {
            const esc = window.escapeHtml || (t => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; });
            return `
            <div class="activity-item">
                <div class="activity-icon">
                    <i class="fas fa-${this.getActivityIcon(item.activity_type || item.type)}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-title">${esc(item.description || item.title || 'Activity')}</div>
                    <div class="activity-time">${this.formatTimestamp(item.timestamp)}</div>
                </div>
            </div>
        `;
        }).join('');
    }

    renderAlertBanner(health) {
        const alerts = health?.alerts;
        const banner = document.getElementById('alert-banner');

        if (!banner) return;

        const criticalCount = alerts?.active_by_severity?.critical || 0;
        const warningCount = alerts?.active_by_severity?.warning || 0;

        if (criticalCount > 0 || warningCount > 0) {
            const message = document.getElementById('alert-message');
            if (message) {
                message.textContent = `${criticalCount + warningCount} active alert${criticalCount + warningCount !== 1 ? 's' : ''} detected`;
            }
            banner.style.display = 'flex';
            
            // Make entire banner clickable to show alerts
            banner.onclick = () => this.showAlerts(alerts);
            banner.title = 'Click to view alerts';
        } else {
            banner.style.display = 'none';
        }
    }

    // Helper methods
    setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    setStatus(id, status) {
        const el = document.getElementById(id);
        if (!el) return;

        const normalizedStatus = status?.toLowerCase() || 'unknown';
        el.className = `status-indicator ${normalizedStatus}`;
        el.textContent = status || 'unknown';
    }

    setBreakdownBar(barId, scoreId, score) {
        const bar = document.getElementById(barId);
        const scoreEl = document.getElementById(scoreId);

        if (scoreEl) scoreEl.textContent = score;

        if (bar) {
            bar.style.width = `${score}%`;
            bar.style.backgroundColor = score >= 80 ? 'var(--success-500)' :
                                        score >= 60 ? 'var(--warning-500)' :
                                        'var(--error-500)';
        }
    }

    updateTimestamp() {
        const el = document.getElementById('last-updated');
        if (el) {
            el.textContent = new Date().toLocaleTimeString();
        }
    }

    formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${days}d ${hours}h ${minutes}m`;
    }

    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    }

    getActivityIcon(type) {
        const icons = {
            'system_startup': 'power-off',
            'alert_created': 'bell',
            'alert_resolved': 'check',
            'device_connected': 'plug',
            'device_disconnected': 'unlink',
            'sensor_reading': 'thermometer-half',
            'actuator_control': 'toggle-on',
            'plant_updated': 'leaf',
            'harvest': 'cut',
            'watering': 'droplet',
            'lighting': 'lightbulb'
        };
        return icons[type] || 'info-circle';
    }

    showHealthDetails(health) {
        const breakdown = health?.breakdown || {};
        const infra = health?.infrastructure_details || {};
        
        let details = `<div style="padding: 20px;">`;
        details += `<h3 style="margin-top: 0;">Health Breakdown</h3>`;
        details += `<div style="margin-bottom: 15px;">`;
        details += `<strong>Infrastructure:</strong> ${breakdown.infrastructure || 0}/100`;
        if (breakdown.infrastructure < 80) {
            details += ` <span style="color: var(--warning-600);">⚠</span>`;
            if (infra.api_metrics?.status !== 'online') details += `<br><small>• API server issues</small>`;
            if (infra.database_status !== 'connected') details += `<br><small>• Database connection issues</small>`;
            const storagePercent = infra.storage?.percent || 0;
            if (storagePercent > 75) details += `<br><small>• Storage usage: ${storagePercent.toFixed(1)}%</small>`;
        }
        details += `</div>`;
        
        details += `<div style="margin-bottom: 15px;">`;
        details += `<strong>Connectivity:</strong> ${breakdown.connectivity || 0}/100`;
        if (breakdown.connectivity < 80) {
            details += ` <span style="color: var(--warning-600);">⚠</span>`;
            details += `<br><small>• MQTT broker connection issues</small>`;
        }
        details += `</div>`;
        
        details += `<div style="margin-bottom: 15px;">`;
        details += `<strong>Sensors:</strong> ${breakdown.sensors || 0}/100`;
        if (breakdown.sensors < 80) {
            details += ` <span style="color: var(--warning-600);">⚠</span>`;
            const sensorHealth = health?.sensor_health || {};
            if (sensorHealth.critical_sensors > 0) details += `<br><small>• ${sensorHealth.critical_sensors} critical sensors</small>`;
            if (sensorHealth.degraded_sensors > 0) details += `<br><small>• ${sensorHealth.degraded_sensors} degraded sensors</small>`;
            if (sensorHealth.total_sensors === 0) details += `<br><small>• No sensors registered</small>`;
        }
        details += `</div>`;
        details += `</div>`;
        
        this.showModal('Health Details', details);
    }

    showAlerts(alerts) {
        const criticalCount = alerts?.active_by_severity?.critical || 0;
        const warningCount = alerts?.active_by_severity?.warning || 0;
        const infoCount = alerts?.active_by_severity?.info || 0;
        
        let content = `<div style="padding: 20px;">`;
        content += `<h3 style="margin-top: 0;">Active Alerts</h3>`;
        
        if (criticalCount > 0) {
            content += `<div style="margin-bottom: 15px; padding: 10px; background: color-mix(in srgb, var(--error-500) 10%, white); border-left: 4px solid var(--error-500); border-radius: 4px;">`;
            content += `<strong style="color: var(--error-600);">Critical: ${criticalCount}</strong>`;
            content += `<br><small>Immediate attention required</small>`;
            content += `</div>`;
        }
        
        if (warningCount > 0) {
            content += `<div style="margin-bottom: 15px; padding: 10px; background: var(--warning-100); border-left: 4px solid var(--warning-500); border-radius: 4px;">`;
            content += `<strong style="color: var(--warning-600);">Warning: ${warningCount}</strong>`;
            content += `<br><small>Should be reviewed soon</small>`;
            content += `</div>`;
        }
        
        if (infoCount > 0) {
            content += `<div style="margin-bottom: 15px; padding: 10px; background: var(--info-100); border-left: 4px solid var(--info-500); border-radius: 4px;">`;
            content += `<strong style="color: var(--info-600);">Info: ${infoCount}</strong>`;
            content += `<br><small>Informational alerts</small>`;
            content += `</div>`;
        }
        
        content += `<div style="margin-top: 20px;">`;
        content += `<a href="/settings#alerts" class="btn btn-primary" style="text-decoration: none; display: inline-block; padding: 8px 16px; background: var(--brand-600); color: white; border-radius: var(--radius-md);">View All Alerts</a>`;
        content += `</div>`;
        content += `</div>`;
        
        this.showModal('System Alerts', content);
    }

    showModal(title, content) {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.id = 'health-modal-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        `;
        
        // Create modal
        const modal = document.createElement('div');
        modal.style.cssText = `
            background: var(--card-bg);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        `;
        
        modal.innerHTML = `
            <div style="padding: 20px; border-bottom: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center;">
                <h2 style="margin: 0; font-size: 1.25rem; color: var(--color-text-strong);">${title}</h2>
                <button id="modal-close" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--color-text-muted); padding: 0; width: 32px; height: 32px;">&times;</button>
            </div>
            <div>${content}</div>
        `;
        
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        
        // Close handlers
        const closeModal = () => {
            overlay.remove();
        };
        
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });
        
        modal.querySelector('#modal-close').addEventListener('click', closeModal);
        
        // ESC key to close
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }
}

// ============================================================
// MAIN DASHBOARD CONTROLLER
// ============================================================

export class SystemHealthDashboard {
    static async init() {
        console.log('­ƒÅÑ Initializing System Health Dashboard (Redesigned)');

        if (!API.Health || !API.Insights) {
            console.error('ÔØî Required APIs not available');
            return;
        }

        const ui = new HealthDashboardUI();
        let autoRefreshInterval = null;

        // Load initial data
        const loadData = async () => {
            try {
                const data = await ui.dataService.loadAllData();
                ui.renderAll(data);
            } catch (error) {
                console.error('Failed to load dashboard:', error);
            }
        };

        await loadData();

        // Setup refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                refreshBtn.disabled = true;
                refreshBtn.querySelector('i').classList.add('fa-spin');
                await loadData();
                refreshBtn.disabled = false;
                refreshBtn.querySelector('i').classList.remove('fa-spin');
            });
        }

        // Setup auto-refresh
        const autoRefreshToggle = document.getElementById('auto-refresh');
        const refreshStatus = document.getElementById('refresh-status');

        const startAutoRefresh = () => {
            autoRefreshInterval = setInterval(loadData, 30000);
            if (refreshStatus) refreshStatus.textContent = 'Auto-refresh enabled';
        };

        const stopAutoRefresh = () => {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
            if (refreshStatus) refreshStatus.textContent = 'Auto-refresh disabled';
        };

        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    startAutoRefresh();
                } else {
                    stopAutoRefresh();
                }
            });

            // Start if checked
            if (autoRefreshToggle.checked) {
                startAutoRefresh();
            }
        }
        // Cleanup on page leave
        window.addEventListener('beforeunload', stopAutoRefresh);
        console.log('Ô£à Dashboard initialized');
        return { ui };
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => SystemHealthDashboard.init());
} else {
    SystemHealthDashboard.init();
}
