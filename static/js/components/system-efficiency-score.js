/**
 * System Efficiency Score Component
 * 
 * Displays a composite efficiency metric combining:
 * - Environmental Stability (40%): Temperature, humidity, VPD consistency
 * - Energy Efficiency (30%): Power usage optimization
 * - Automation Effectiveness (30%): Device response and alert handling
 * 
 * Features:
 * - Real-time score calculation (0-100)
 * - Grade display (A+, A, B+, B, C, D, F)
 * - Component breakdown with individual scores
 * - Improvement suggestions based on weak areas
 * - Trend indicator (improving/stable/declining)
 * - ML-powered recommendations when available
 */

class SystemEfficiencyScore {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    
    if (!this.container) {
      console.error(`Container with id "${containerId}" not found`);
      return;
    }
    
    this.options = {
      updateInterval: options.updateInterval || 60000, // 1 minute default
      enableMLSuggestions: options.enableMLSuggestions !== false,
      ...options
    };
    
    this.unitId = null;
    this.currentScore = null;
    this.components = null;
    this.suggestions = [];
    this.updateTimer = null;
    
    // Weights for composite score
    this.weights = {
      environmental: 0.40,
      energy: 0.30,
      automation: 0.30
    };
    
    this.render();
  }
  
  async init(unitId = null) {
    this.unitId = unitId;
    await this.calculateScore();
    this.startAutoUpdate();
  }
  
  render() {
    this.container.innerHTML = `
      <div class="efficiency-score-card">
        <div class="efficiency-header">
          <h3 class="efficiency-title">
            <i class="fas fa-tachometer-alt"></i>
            System Efficiency Score
          </h3>
          <button class="refresh-btn efficiency-refresh" aria-label="Refresh score">
            <i class="fas fa-sync-alt"></i>
          </button>
        </div>
        
        <div class="efficiency-body">
          <!-- Main Score Display -->
          <div class="efficiency-main">
            <div class="efficiency-gauge-container">
              <svg class="efficiency-gauge" viewBox="0 0 200 120" role="img" aria-label="Efficiency gauge">
                <!-- Background arc -->
                <path class="gauge-bg" d="M 30 110 A 70 70 0 0 1 170 110" fill="none" stroke="var(--card-border)" stroke-width="20" stroke-linecap="round"/>
                <!-- Score arc -->
                <path class="gauge-fill" d="M 30 110 A 70 70 0 0 1 170 110" fill="none" stroke="var(--success-600)" stroke-width="20" stroke-linecap="round" stroke-dasharray="0 220"/>
                <!-- Center text -->
                <text class="gauge-score" x="100" y="90" text-anchor="middle" font-size="32" font-weight="bold" fill="var(--color-text-strong)">--</text>
                <text class="gauge-label" x="100" y="108" text-anchor="middle" font-size="14" fill="var(--color-text-muted)">Loading...</text>
              </svg>
            </div>
            
            <div class="efficiency-grade-display">
              <div class="grade-badge grade-unknown">
                <span class="grade-letter">--</span>
              </div>
              <div class="grade-trend">
                <i class="fas fa-minus"></i>
                <span>Calculating...</span>
              </div>
            </div>
          </div>
          
          <!-- Component Breakdown -->
          <div class="efficiency-breakdown">
            <div class="breakdown-title">Score Breakdown</div>
            
            <div class="breakdown-item">
              <div class="breakdown-header">
                <div class="breakdown-label">
                  <i class="fas fa-leaf text-success"></i>
                  Environmental Stability
                </div>
                <div class="breakdown-score">
                  <span class="score-value">--</span>
                  <span class="score-weight">(40%)</span>
                </div>
              </div>
              <div class="breakdown-bar">
                <div class="breakdown-fill environmental" style="width: 0%"></div>
              </div>
            </div>
            
            <div class="breakdown-item">
              <div class="breakdown-header">
                <div class="breakdown-label">
                  <i class="fas fa-bolt text-warning"></i>
                  Energy Efficiency
                </div>
                <div class="breakdown-score">
                  <span class="score-value">--</span>
                  <span class="score-weight">(30%)</span>
                </div>
              </div>
              <div class="breakdown-bar">
                <div class="breakdown-fill energy" style="width: 0%"></div>
              </div>
            </div>
            
            <div class="breakdown-item">
              <div class="breakdown-header">
                <div class="breakdown-label">
                  <i class="fas fa-robot text-info"></i>
                  Automation Effectiveness
                </div>
                <div class="breakdown-score">
                  <span class="score-value">--</span>
                  <span class="score-weight">(30%)</span>
                </div>
              </div>
              <div class="breakdown-bar">
                <div class="breakdown-fill automation" style="width: 0%"></div>
              </div>
            </div>
          </div>
          
          <!-- Improvement Suggestions -->
          <div class="efficiency-suggestions">
            <div class="suggestions-title">
              <i class="fas fa-lightbulb"></i>
              Improvement Suggestions
            </div>
            <div class="suggestions-list">
              <div class="text-muted">Calculating recommendations...</div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Bind refresh button
    const refreshBtn = this.container.querySelector('.efficiency-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.refresh());
    }
  }
  
  async calculateScore() {
    try {
      // Fetch efficiency data from API
      const options = {};
      if (this.unitId) {
        options.unit_id = this.unitId;
      }
      
      const result = await API.Analytics.getEfficiencyScore(options);
      
      if (result) {
        this.currentScore = result.overall_score;
        this.components = result.components;
        this.suggestions = result.suggestions || [];
        
        this.updateDisplay();
      } else {
        console.error('Failed to calculate efficiency score: no data');
        this.showError('No efficiency data available');
      }
    } catch (error) {
      console.error('Error calculating efficiency score:', error);
      this.showError('Failed to load efficiency data');
    }
  }
  
  updateDisplay() {
    // Update gauge
    this.updateGauge(this.currentScore);
    
    // Update grade
    const grade = this.calculateGrade(this.currentScore);
    this.updateGrade(grade);
    
    // Update component breakdown
    this.updateBreakdown();
    
    // Update suggestions
    this.updateSuggestions();
  }
  
  updateGauge(score) {
    const gaugeFill = this.container.querySelector('.gauge-fill');
    const gaugeScore = this.container.querySelector('.gauge-score');
    const gaugeLabel = this.container.querySelector('.gauge-label');
    
    if (!gaugeFill || !gaugeScore || !gaugeLabel) return;
    
    // Calculate arc length (semicircle = ~220 units)
    const arcLength = 220;
    const fillLength = (score / 100) * arcLength;
    
    // Animate gauge
    gaugeFill.style.strokeDasharray = `${fillLength} ${arcLength}`;
    
    // Color based on score
    const color = this.getScoreColor(score);
    gaugeFill.setAttribute('stroke', color);
    
    // Update text
    gaugeScore.textContent = Math.round(score);
    gaugeLabel.textContent = this.getScoreLabel(score);
  }
  
  calculateGrade(score) {
    if (score >= 97) return { letter: 'A+', class: 'grade-a-plus' };
    if (score >= 93) return { letter: 'A', class: 'grade-a' };
    if (score >= 90) return { letter: 'A-', class: 'grade-a-minus' };
    if (score >= 87) return { letter: 'B+', class: 'grade-b-plus' };
    if (score >= 83) return { letter: 'B', class: 'grade-b' };
    if (score >= 80) return { letter: 'B-', class: 'grade-b-minus' };
    if (score >= 77) return { letter: 'C+', class: 'grade-c-plus' };
    if (score >= 73) return { letter: 'C', class: 'grade-c' };
    if (score >= 70) return { letter: 'C-', class: 'grade-c-minus' };
    if (score >= 60) return { letter: 'D', class: 'grade-d' };
    return { letter: 'F', class: 'grade-f' };
  }
  
  updateGrade(grade) {
    const gradeBadge = this.container.querySelector('.grade-badge');
    const gradeLetter = this.container.querySelector('.grade-letter');
    
    if (!gradeBadge || !gradeLetter) return;
    
    // Remove old grade classes
    gradeBadge.className = 'grade-badge';
    gradeBadge.classList.add(grade.class);
    
    // Update letter
    gradeLetter.textContent = grade.letter;
    
    // Update trend (if available)
    this.updateTrend();
  }
  
  updateTrend() {
    const trendContainer = this.container.querySelector('.grade-trend');
    if (!trendContainer) return;
    
    // For now, show stable
    // In production, compare with previous score
    trendContainer.innerHTML = `
      <i class="fas fa-minus"></i>
      <span>Stable</span>
    `;
  }
  
  updateBreakdown() {
    if (!this.components) return;
    
    const items = this.container.querySelectorAll('.breakdown-item');
    
    // Environmental
    if (items[0] && this.components.environmental !== undefined) {
      const score = this.components.environmental;
      items[0].querySelector('.score-value').textContent = Math.round(score);
      items[0].querySelector('.breakdown-fill').style.width = `${score}%`;
      items[0].querySelector('.breakdown-fill').style.backgroundColor = this.getScoreColor(score);
    }
    
    // Energy
    if (items[1] && this.components.energy !== undefined) {
      const score = this.components.energy;
      items[1].querySelector('.score-value').textContent = Math.round(score);
      items[1].querySelector('.breakdown-fill').style.width = `${score}%`;
      items[1].querySelector('.breakdown-fill').style.backgroundColor = this.getScoreColor(score);
    }
    
    // Automation
    if (items[2] && this.components.automation !== undefined) {
      const score = this.components.automation;
      items[2].querySelector('.score-value').textContent = Math.round(score);
      items[2].querySelector('.breakdown-fill').style.width = `${score}%`;
      items[2].querySelector('.breakdown-fill').style.backgroundColor = this.getScoreColor(score);
    }
  }
  
  updateSuggestions() {
    const listContainer = this.container.querySelector('.suggestions-list');
    if (!listContainer) return;
    
    if (this.suggestions.length === 0) {
      listContainer.innerHTML = '<div class="text-success"><i class="fas fa-check-circle"></i> System running optimally!</div>';
      return;
    }
    
    const esc = window.escapeHtml || function(t) { if (!t) return ''; const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
    const escAttr = window.escapeHtmlAttr || function(t) { return String(t ?? '').replace(/[&"'<>]/g, c => ({'&':'&amp;','"':'&quot;',"'":'&#39;','<':'&lt;','>':'&gt;'}[c])); };
    
    listContainer.innerHTML = this.suggestions.map((suggestion, index) => `
      <div class="suggestion-item">
        <div class="suggestion-icon">
          <i class="fas ${this.getSuggestionIcon(suggestion.priority)}"></i>
        </div>
        <div class="suggestion-content">
          <div class="suggestion-text">${esc(suggestion.message)}</div>
          ${suggestion.action ? `<button class="suggestion-action btn btn-sm btn-link" data-action="${escAttr(suggestion.action)}">
            ${esc(suggestion.action_label || 'Fix Now')}
          </button>` : ''}
        </div>
      </div>
    `).join('');
    
    // Bind action buttons
    listContainer.querySelectorAll('.suggestion-action').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const action = e.target.dataset.action;
        this.handleSuggestionAction(action);
      });
    });
  }
  
  getSuggestionIcon(priority) {
    switch (priority) {
      case 'high': return 'fa-exclamation-circle text-danger';
      case 'medium': return 'fa-exclamation-triangle text-warning';
      case 'low': return 'fa-info-circle text-info';
      default: return 'fa-lightbulb text-primary';
    }
  }
  
  handleSuggestionAction(action) {
    console.log('Suggestion action:', action);
    // Implement action handlers (navigate to settings, trigger optimization, etc.)
  }
  
  getScoreColor(score) {
    if (score >= 90) return 'var(--success-600)';
    if (score >= 80) return 'var(--accent-growth)';
    if (score >= 70) return 'var(--warning-600)';
    if (score >= 60) return 'var(--earth-600)';
    return 'var(--danger-600)';
  }
  
  getScoreLabel(score) {
    if (score >= 90) return 'Excellent';
    if (score >= 80) return 'Good';
    if (score >= 70) return 'Fair';
    if (score >= 60) return 'Poor';
    return 'Critical';
  }
  
  showError(message) {
    const gaugeLabel = this.container.querySelector('.gauge-label');
    if (gaugeLabel) {
      gaugeLabel.textContent = message;
      gaugeLabel.style.fill = 'var(--danger-600)';
    }
  }
  
  async refresh() {
    const refreshBtn = this.container.querySelector('.efficiency-refresh');
    if (refreshBtn) {
      refreshBtn.classList.add('spinning');
    }
    
    await this.calculateScore();
    
    if (refreshBtn) {
      refreshBtn.classList.remove('spinning');
    }
  }
  
  startAutoUpdate() {
    this.stopAutoUpdate();
    
    if (this.options.updateInterval > 0) {
      this.updateTimer = setInterval(() => {
        this.calculateScore();
      }, this.options.updateInterval);
    }
  }
  
  stopAutoUpdate() {
    if (this.updateTimer) {
      clearInterval(this.updateTimer);
      this.updateTimer = null;
    }
  }
  
  destroy() {
    this.stopAutoUpdate();
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SystemEfficiencyScore;
}

// Export to window for browser usage
if (typeof window !== 'undefined') {
  window.SystemEfficiencyScore = SystemEfficiencyScore;
}
