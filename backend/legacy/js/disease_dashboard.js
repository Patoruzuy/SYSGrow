/**
 * Disease Monitoring Dashboard
 * Real-time disease risk assessment and alerts
 */

class DiseaseMonitoringDashboard {
    constructor() {
        this.refreshBtn = document.getElementById('refresh-btn');
        this.diseaseChart = null;
        
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadDashboard();
        
        // Auto-refresh every 5 minutes
        setInterval(() => this.loadDashboard(), 5 * 60 * 1000);
    }

    bindEvents() {
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => this.loadDashboard());
        }

        // Event delegation for alerts
        const alertsContainer = document.getElementById('alerts-container');
        if (alertsContainer) {
            alertsContainer.addEventListener('click', (e) => {
                const dismissBtn = e.target.closest('[data-action="dismiss-alert"]');
                if (dismissBtn) {
                    const alertId = dismissBtn.getAttribute('data-alert-id');
                    this.dismissAlert(alertId);
                }
            });
        }
    }

    async loadDashboard() {
        this.showLoading();
        
        try {
            await Promise.all([
                this.loadRiskAssessments(),
                this.loadAlerts(),
                this.loadStatistics()
            ]);
        } catch (error) {
            console.error('Error loading dashboard:', error);
            this.showNotification('Failed to load dashboard data', 'error');
        } finally {
            this.hideLoading();
        }
    }

    async loadRiskAssessments() {
        try {
            const data = await API.ML.getDiseaseRisks();
            
            // Update summary stats
            document.getElementById('total-units').textContent = data.summary.total_units;
            document.getElementById('high-risk-count').textContent = data.summary.high_risk_units;
            document.getElementById('critical-risk-count').textContent = data.summary.critical_risk_units;
            document.getElementById('common-risk').textContent = 
                data.summary.most_common_risk ? 
                data.summary.most_common_risk.replace('_', ' ') : 
                'N/A';

            // Render unit cards
            this.renderUnitCards(data.units);

        } catch (error) {
            console.error('Error loading risk assessments:', error);
        }
    }

    async loadAlerts() {
        try {
            const data = await API.ML.getDiseaseAlerts();
            this.renderAlerts(data.alerts);

        } catch (error) {
            console.error('Error loading alerts:', error);
        }
    }

    async loadStatistics() {
        try {
            const data = await API.ML.getDiseaseStatistics(90);
            
            // Render disease distribution chart
            this.renderDiseaseChart(data.disease_distribution);
            
            // Render common symptoms
            this.renderSymptomsList(data.common_symptoms);

        } catch (error) {
            console.error('Error loading statistics:', error);
        }
    }

    renderUnitCards(units) {
        const container = document.getElementById('units-container');
        
        if (!units || units.length === 0) {
            container.innerHTML = '<p class="text-muted">No units with active plants found.</p>';
            return;
        }

        // Sort by highest risk score
        units.sort((a, b) => b.highest_risk_score - a.highest_risk_score);

        let html = '';
        
        for (const unit of units) {
            const hasHigh = unit.risks.some(r => r.risk_level === 'high');
            const hasCritical = unit.risks.some(r => r.risk_level === 'critical');
            const cardClass = hasCritical ? 'has-critical' : (hasHigh ? 'has-high' : '');

            html += `
                <div class="unit-card ${cardClass}">
                    <div class="row">
                        <div class="col-md-8">
                            <h5 class="mb-2">
                                🏠 ${this.escapeHtml(unit.unit_name)}
                                <span class="badge bg-secondary ms-2">${this.escapeHtml(unit.plant_type)}</span>
                            </h5>
                            <p class="text-muted mb-3">
                                Plant: ${this.escapeHtml(unit.plant_name)} | 
                                Stage: ${this.escapeHtml(unit.growth_stage)} | 
                                Age: ${unit.plant_age_days} days
                            </p>
                        </div>
                        <div class="col-md-4 text-end">
                            <h6 class="text-muted mb-2">Risk Score</h6>
                            <h3 class="mb-0">${unit.highest_risk_score.toFixed(1)}/100</h3>
                        </div>
                    </div>

                    ${unit.risks.length > 0 ? `
                        <div class="risks-section">
                            <h6 class="mb-2">Detected Risks:</h6>
                            ${unit.risks.map(risk => this.renderRiskItem(risk)).join('')}
                        </div>
                    ` : `
                        <div class="alert alert-success mb-0">
                            ✅ No significant disease risks detected
                        </div>
                    `}
                </div>
            `;
        }

        container.innerHTML = html;
    }

    renderRiskItem(risk) {
        const badgeClass = `risk-${risk.risk_level}`;
        const icon = this.getRiskIcon(risk.disease_type);

        return `
            <div class="risk-item">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <h6 class="mb-1">
                            ${icon} ${this.formatDiseaseType(risk.disease_type)}
                        </h6>
                        <span class="risk-badge ${badgeClass}">${risk.risk_level}</span>
                        <span class="badge bg-light text-dark ms-2">
                            ${(risk.confidence * 100).toFixed(0)}% confidence
                        </span>
                    </div>
                    <div class="text-end">
                        <strong>${risk.risk_score.toFixed(1)}</strong>/100
                    </div>
                </div>

                ${risk.predicted_onset_days ? `
                    <div class="alert alert-warning py-2 mb-2">
                        ⏱️ Symptoms may appear in <strong>${risk.predicted_onset_days} days</strong>
                    </div>
                ` : ''}

                ${risk.contributing_factors.length > 0 ? `
                    <div class="mb-2">
                        <strong>Contributing Factors:</strong>
                        <ul class="mb-0 mt-1">
                            ${risk.contributing_factors.slice(0, 3).map(factor => `
                                <li>${this.formatFactor(factor)}</li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${risk.recommendations.length > 0 ? `
                    <div>
                        <strong>Recommendations:</strong>
                        ${risk.recommendations.slice(0, 3).map(rec => `
                            <div class="recommendation">
                                ${this.escapeHtml(rec)}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }

    renderAlerts(alerts) {
        const container = document.getElementById('alerts-container');

        if (!alerts || alerts.length === 0) {
            container.innerHTML = '<div class="alert alert-success">✅ No active alerts - all systems operating normally</div>';
            return;
        }

        let html = '';
        
        for (const alert of alerts) {
            const alertClass = alert.priority === 1 ? 'alert-danger' : 'alert-warning';
            const icon = alert.priority === 1 ? '🚨' : '⚠️';

            html += `
                <div class="alert ${alertClass} mb-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="alert-heading mb-2">
                                ${icon} ${this.escapeHtml(alert.message)}
                            </h6>
                            <p class="mb-2">
                                <strong>Unit:</strong> ${this.escapeHtml(alert.unit_name)} | 
                                <strong>Risk Score:</strong> ${alert.risk_score}/100 | 
                                <strong>Confidence:</strong> ${(alert.confidence * 100).toFixed(0)}%
                            </p>
                            ${alert.predicted_onset_days ? `
                                <p class="mb-2">
                                    <strong>⏱️ Estimated Onset:</strong> ${alert.predicted_onset_days} days
                                </p>
                            ` : ''}
                            <div>
                                <strong>Immediate Actions:</strong>
                                <ol class="mb-0 mt-1">
                                    ${alert.actions.map(action => `
                                        <li>${this.escapeHtml(action)}</li>
                                    `).join('')}
                                </ol>
                            </div>
                        </div>
                        <button class="btn btn-sm btn-outline-secondary" data-action="dismiss-alert" data-alert-id="${alert.alert_id}">
                            Dismiss
                        </button>
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;
    }

    renderDiseaseChart(diseaseDistribution) {
        const ctx = document.getElementById('disease-distribution-chart');
        
        if (!ctx) return;

        if (!diseaseDistribution || diseaseDistribution.length === 0) {
            ctx.parentElement.innerHTML = '<p class="text-muted">No disease data available</p>';
            return;
        }

        // Destroy existing chart
        if (this.diseaseChart) {
            this.diseaseChart.destroy();
        }

        const labels = diseaseDistribution.map(d => this.formatDiseaseType(d.disease_type));
        const counts = diseaseDistribution.map(d => d.count);
        const severities = diseaseDistribution.map(d => d.avg_severity);

        this.diseaseChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Occurrences',
                        data: counts,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Avg Severity',
                        data: severities,
                        type: 'line',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        type: 'linear',
                        position: 'left',
                        title: { display: true, text: 'Occurrences' }
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        title: { display: true, text: 'Avg Severity' },
                        min: 0,
                        max: 5,
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    renderSymptomsList(commonSymptoms) {
        const container = document.getElementById('symptoms-list');

        if (!commonSymptoms || commonSymptoms.length === 0) {
            container.innerHTML = '<p class="text-muted">No symptom data available</p>';
            return;
        }

        let html = '<ul class="list-group">';
        
        for (const item of commonSymptoms.slice(0, 10)) {
            const symptoms = item.symptoms ? item.symptoms.split(',').map(s => s.trim()) : [];
            html += `
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    <span>${symptoms.slice(0, 3).join(', ')}</span>
                    <span class="badge bg-primary rounded-pill">${item.count}</span>
                </li>
            `;
        }
        
        html += '</ul>';
        container.innerHTML = html;
    }

    getRiskIcon(diseaseType) {
        const icons = {
            'fungal': '🍄',
            'bacterial': '🦠',
            'viral': '🔬',
            'pest': '🐛',
            'nutrient_deficiency': '🌿',
            'environmental_stress': '🌡️'
        };
        return icons[diseaseType] || '⚠️';
    }

    formatDiseaseType(diseaseType) {
        return diseaseType.replace('_', ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    formatFactor(factor) {
        let text = this.formatDiseaseType(factor.factor);
        
        if (factor.value !== undefined) {
            text += `: ${typeof factor.value === 'number' ? factor.value.toFixed(1) : factor.value}`;
        }
        
        if (factor.threshold) {
            text += ` (threshold: ${factor.threshold})`;
        }
        
        if (factor.range) {
            text += ` (${factor.range})`;
        }
        
        return text;
    }

    dismissAlert(alertId) {
        console.log('Dismissing alert:', alertId);
        // TODO: Implement alert dismissal (store in localStorage or backend)
        this.showNotification('Alert dismissed', 'success');
        this.loadAlerts();
    }

    showLoading() {
        if (this.refreshBtn) {
            this.refreshBtn.disabled = true;
            const icon = this.refreshBtn.querySelector('i');
            if (icon) icon.classList.add('fa-spin');
        }
    }

    hideLoading() {
        if (this.refreshBtn) {
            this.refreshBtn.disabled = false;
            const icon = this.refreshBtn.querySelector('i');
            if (icon) icon.classList.remove('fa-spin');
        }
    }

    showNotification(message, type = 'info') {
        // Use existing notification system if available
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new DiseaseMonitoringDashboard();
});
