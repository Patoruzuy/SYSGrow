const API = window.API;
if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before harvest_report.js');
}

let currentPlantId = null;
let energyChart = null;

async function loadPlantsForUnit() {
  const unitId = document.getElementById('unitSelect').value;
  if (!unitId) {
    document.getElementById('plantSelect').innerHTML = '<option value="">Select Plant...</option>';
    return;
  }

  try {
    const response = await API.Plant.listPlants(unitId);
    const plants = response.data || response || [];
    const select = document.getElementById('plantSelect');
    select.innerHTML = '<option value="">Select Plant...</option>';
    plants.forEach(plant => {
      const option = document.createElement('option');
      option.value = plant.plant_id || plant.id;
      option.textContent = `${plant.name} (${plant.current_stage})`;
      select.appendChild(option);
    });
  } catch (error) {
    console.error('Error loading plants:', error);
    alert('Failed to load plants for this unit');
  }
}

async function loadPlantInfo() {
  const plantId = document.getElementById('plantSelect').value;
  const unitId = document.getElementById('unitSelect').value;
  if (!plantId) {
    document.getElementById('plantInfoCard').style.display = 'none';
    document.getElementById('harvestForm').style.display = 'none';
    return;
  }

  currentPlantId = plantId;

  try {
    const plant = await API.Plant.getPlant(plantId, unitId);
    
    document.getElementById('plantName').textContent = plant.name;
    document.getElementById('plantType').textContent = plant.plant_type;
    document.getElementById('currentStage').textContent = plant.current_stage;
    document.getElementById('daysGrowing').textContent = plant.days_in_stage || 'N/A';
    
    document.getElementById('plantInfoCard').style.display = 'block';
    document.getElementById('harvestForm').style.display = 'block';
  } catch (error) {
    console.error('Error loading plant info:', error);
    alert('Failed to load plant information');
  }
}

async function generateHarvestReport() {
  const weight = document.getElementById('harvestWeight').value;
  const quality = document.getElementById('qualityRating').value;
  const notes = document.getElementById('harvestNotes').value;
  const deletePlantData = document.getElementById('deletePlantData').value === 'true';

  if (!weight || !quality) {
    alert('Please fill in all required fields');
    return;
  }

  // Show loading
  document.getElementById('harvestForm').style.display = 'none';
  document.getElementById('loadingIndicator').style.display = 'block';

  try {
    const result = await API.Plant.harvestPlant(currentPlantId, {
        harvest_weight_grams: parseFloat(weight),
        quality_rating: parseInt(quality),
        notes: notes,
        delete_plant_data: deletePlantData
    });

    displayHarvestReport(result.harvest_report || result);
  } catch (error) {
    console.error('Error generating harvest report:', error);
    alert('Failed to generate harvest report: ' + error.message);
    document.getElementById('harvestForm').style.display = 'block';
  } finally {
    document.getElementById('loadingIndicator').style.display = 'none';
  }
}

function displayHarvestReport(report) {
  // Update summary cards
  document.getElementById('summaryWeight').textContent = report.yield.weight_grams.toFixed(1);
  document.getElementById('summaryEnergy').textContent = report.energy_consumption.total_kwh.toFixed(2);
  document.getElementById('summaryEfficiency').textContent = report.efficiency_metrics.grams_per_kwh.toFixed(2);
  document.getElementById('summaryCost').textContent = '$' + report.energy_consumption.total_cost.toFixed(2);

  // Display lifecycle timeline
  displayLifecycleTimeline(report.lifecycle);

  // Display energy chart
  displayEnergyChart(report.energy_consumption);

  // Display efficiency metrics
  displayEfficiencyMetrics(report.efficiency_metrics);

  // Display environmental data
  displayEnvironmentalData(report.environmental_conditions);

  // Display recommendations
  displayRecommendations(report.recommendations);

  // Show report
  document.getElementById('plantInfoCard').style.display = 'none';
  document.getElementById('harvestReportDisplay').style.display = 'block';
}

function displayLifecycleTimeline(lifecycle) {
  const timeline = document.getElementById('lifecycleTimeline');
  const stages = lifecycle.stages;
  
  let html = '<div class="timeline">';
  for (const [stage, data] of Object.entries(stages)) {
    html += `
      <div class="timeline-item">
        <strong>${stage.charAt(0).toUpperCase() + stage.slice(1)} Stage</strong>
        <p class="mb-0">${data.days} days</p>
      </div>
    `;
  }
  html += '</div>';
  html += `<p class="text-muted mt-3">
    <strong>Planted:</strong> ${new Date(lifecycle.planted_date).toLocaleDateString()} | 
    <strong>Harvested:</strong> ${new Date(lifecycle.harvested_date).toLocaleDateString()} | 
    <strong>Total:</strong> ${lifecycle.total_days} days
  </p>`;
  
  timeline.innerHTML = html;
}

function displayEnergyChart(energyData) {
  const ctx = document.getElementById('energyChart').getContext('2d');
  
  if (energyChart) energyChart.destroy();
  
  const stages = Object.keys(energyData.by_stage);
  const values = Object.values(energyData.by_stage);
  
  energyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: stages.map(s => s.charAt(0).toUpperCase() + s.slice(1)),
      datasets: [{
        label: 'Energy Consumption (kWh)',
        data: values,
        backgroundColor: ['#28a745', '#17a2b8', '#ffc107', '#dc3545']
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Energy Consumption by Growth Stage' }
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'kWh' } }
      }
    }
  });

  // Energy breakdown table
  let breakdown = '<h6 class="mt-3">Cost Breakdown</h6><table class="table table-sm">';
  breakdown += '<tr><th>Stage</th><th>Energy (kWh)</th><th>Cost</th><th>%</th></tr>';
  for (const [stage, kwh] of Object.entries(energyData.by_stage)) {
    const cost = energyData.cost_by_stage[stage] || 0;
    const percent = (kwh / energyData.total_kwh * 100).toFixed(1);
    breakdown += `<tr>
      <td>${stage}</td>
      <td>${kwh.toFixed(2)}</td>
      <td>$${cost.toFixed(2)}</td>
      <td>${percent}%</td>
    </tr>`;
  }
  breakdown += `<tr class="fw-bold">
    <td>Total</td>
    <td>${energyData.total_kwh.toFixed(2)}</td>
    <td>$${energyData.total_cost.toFixed(2)}</td>
    <td>100%</td>
  </tr></table>`;
  
  document.getElementById('energyBreakdown').innerHTML = breakdown;
}

function displayEfficiencyMetrics(metrics) {
  const ratingClass = {
    'Excellent': 'efficiency-excellent',
    'Good': 'efficiency-good',
    'Average': 'efficiency-average',
    'Poor': 'efficiency-poor'
  }[metrics.energy_efficiency_rating] || 'efficiency-average';

  const html = `
    <div class="row">
      <div class="col-md-3">
        <h6>Yield Efficiency</h6>
        <h3>${metrics.grams_per_kwh.toFixed(2)} g/kWh</h3>
        <span class="efficiency-badge ${ratingClass}">${metrics.energy_efficiency_rating}</span>
      </div>
      <div class="col-md-3">
        <h6>Cost per Gram</h6>
        <h3>$${metrics.cost_per_gram.toFixed(3)}</h3>
      </div>
      <div class="col-md-3">
        <h6>Cost per Pound</h6>
        <h3>$${metrics.cost_per_pound.toFixed(2)}</h3>
      </div>
      <div class="col-md-3">
        <h6>Rating</h6>
        <h3>${'⭐'.repeat(Math.max(1, Math.ceil(metrics.grams_per_kwh)))}</h3>
      </div>
    </div>
  `;
  document.getElementById('efficiencyMetrics').innerHTML = html;
}

function displayEnvironmentalData(envData) {
  const html = `
    <div class="row">
      <div class="col-md-4">
        <h6><i class="fas fa-thermometer-half"></i> Temperature</h6>
        <p>Average: ${envData.temperature.avg}°C</p>
        <p class="text-muted small">Optimal: ${envData.temperature.optimal_range || '22-26°C'}</p>
      </div>
      <div class="col-md-4">
        <h6><i class="fas fa-tint"></i> Humidity</h6>
        <p>Average: ${envData.humidity.avg}%</p>
        <p class="text-muted small">Optimal: ${envData.humidity.optimal_range || '60-70%'}</p>
      </div>
      <div class="col-md-4">
        <h6><i class="fas fa-wind"></i> CO2</h6>
        <p>Average: ${envData.co2.avg || 'N/A'} ppm</p>
        <p class="text-muted small">Optimal: ${envData.co2.optimal || '400-1000 ppm'}</p>
      </div>
    </div>
  `;
  document.getElementById('environmentalData').innerHTML = html;
}

function displayRecommendations(recommendations) {
  if (!recommendations || Object.keys(recommendations).length === 0) {
    document.getElementById('recommendations').innerHTML = '<p class="text-muted">No recommendations available.</p>';
    return;
  }

  let html = '<ul class="list-group">';
  for (const [category, items] of Object.entries(recommendations)) {
    if (Array.isArray(items)) {
      items.forEach(item => {
        html += `<li class="list-group-item"><i class="fas fa-check-circle text-success"></i> ${item}</li>`;
      });
    } else {
      html += `<li class="list-group-item"><i class="fas fa-check-circle text-success"></i> ${items}</li>`;
    }
  }
  html += '</ul>';
  document.getElementById('recommendations').innerHTML = html;
}

function cancelHarvest() {
  document.getElementById('plantSelect').value = '';
  document.getElementById('plantInfoCard').style.display = 'none';
  document.getElementById('harvestForm').style.display = 'none';
}

function newHarvest() {
  document.getElementById('harvestReportDisplay').style.display = 'none';
  document.getElementById('plantInfoCard').style.display = 'block';
  document.getElementById('harvestForm').style.display = 'block';
  document.getElementById('harvestWeight').value = '';
  document.getElementById('qualityRating').value = '';
  document.getElementById('harvestNotes').value = '';
}

async function viewAllHarvests() {
  document.getElementById('harvestReportDisplay').style.display = 'none';
  document.getElementById('harvestHistory').style.display = 'block';
  
  try {
    const harvests = await API.Plant.getHarvests();
    const tbody = document.getElementById('harvestHistoryBody');
    
    tbody.innerHTML = harvests.map(h => `
      <tr>
        <td>${new Date(h.harvested_date).toLocaleDateString()}</td>
        <td>${h.plant_name || 'N/A'}</td>
        <td>${h.harvest_weight_grams.toFixed(1)}</td>
        <td>${h.total_energy_kwh.toFixed(2)}</td>
        <td>${h.grams_per_kwh.toFixed(2)}</td>
        <td>$${h.total_cost.toFixed(2)}</td>
        <td>${'⭐'.repeat(h.quality_rating)}</td>
        <td>
          <button class="btn btn-sm btn-info" data-action="view-harvest" data-harvest-id="${h.harvest_id}">
            <i class="fas fa-eye"></i>
          </button>
        </td>
      </tr>
    `).join('');
  } catch (error) {
    console.error('Error loading harvest history:', error);
  }
}

async function viewHarvest(harvestId) {
  try {
    const report = await API.Plant.getHarvest(harvestId);
    document.getElementById('harvestHistory').style.display = 'none';
    displayHarvestReport(report);
  } catch (error) {
    console.error('Error loading harvest:', error);
    alert('Failed to load harvest report');
  }
}

function exportPDF() {
  window.print();
}

// Initialize
export function initHarvestReport() {
    document.addEventListener('DOMContentLoaded', async () => {
        // Attach event listeners
        document.getElementById('unitSelect')?.addEventListener('change', loadPlantsForUnit);
        document.getElementById('plantSelect')?.addEventListener('change', loadPlantInfo);
        document.getElementById('generate-report-btn')?.addEventListener('click', generateHarvestReport);
        document.getElementById('cancel-harvest-btn')?.addEventListener('click', cancelHarvest);
        document.getElementById('view-all-harvests-btn')?.addEventListener('click', viewAllHarvests);
        document.getElementById('new-harvest-btn')?.addEventListener('click', newHarvest);
        document.getElementById('print-btn')?.addEventListener('click', () => window.print());
        document.getElementById('export-pdf-btn')?.addEventListener('click', exportPDF);
        document.getElementById('print-report-btn')?.addEventListener('click', () => window.print());
        document.getElementById('print-report-btn-2')?.addEventListener('click', () => window.print());

        // Event delegation for harvest history table
        document.getElementById('harvestHistoryBody')?.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action="view-harvest"]');
            if (btn) {
                const harvestId = btn.dataset.harvestId;
                viewHarvest(harvestId);
            }
        });

        try {
            const response = await API.Growth.listUnits();
            const units = response.data || response || [];
            const select = document.getElementById('unitSelect');
            units.forEach(unit => {
                const option = document.createElement('option');
                option.value = unit.id || unit.unit_id;
                option.textContent = unit.name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading units:', error);
        }
    });
}
