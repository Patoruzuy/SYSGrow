/**
 * Plant Detail Page Module
 * ============================================
 * Displays comprehensive plant growing information on a dedicated page.
 */

let plantData = null;

// Plant emoji mapping
const PLANT_EMOJIS = {
    'tomato': '🍅', 'tomatoes': '🍅',
    'lettuce': '🥬', 'leafy greens': '🥬',
    'pepper': '🌶️', 'peppers': '🌶️',
    'cucumber': '🥒', 'cucumbers': '🥒',
    'carrot': '🥕', 'carrots': '🥕',
    'strawberry': '🍓', 'strawberries': '🍓',
    'basil': '🌿', 'herbs': '🌿', 'mint': '🌿', 'rosemary': '🌿',
    'flower': '🌸', 'flowers': '🌸',
    'sunflower': '🌻', 'rose': '🌹',
    'corn': '🌽',
    'potato': '🥔', 'potatoes': '🥔',
    'onion': '🧅', 'onions': '🧅',
    'garlic': '🧄',
    'mushroom': '🍄', 'mushrooms': '🍄',
    'broccoli': '🥦', 'eggplant': '🍆', 'avocado': '🥑',
    'bean': '🫘', 'beans': '🫘',
    'pea': '🫛', 'peas': '🫛',
    'chili': '🌶️',
    'default': '🌱'
};

// Plant type categorization
const PLANT_CATEGORIES = {
    vegetable: ['tomato', 'tomatoes', 'lettuce', 'leafy greens', 'pepper', 'peppers', 'cucumber', 'cucumbers', 'carrot', 'carrots', 'potato', 'potatoes', 'onion', 'onions', 'garlic', 'broccoli', 'eggplant', 'corn', 'bean', 'beans', 'pea', 'peas'],
    herb: ['basil', 'mint', 'rosemary', 'thyme', 'oregano', 'parsley', 'cilantro', 'sage', 'herbs'],
    fruit: ['strawberry', 'strawberries', 'tomato', 'tomatoes', 'pepper', 'peppers', 'cucumber', 'cucumbers', 'avocado'],
    flower: ['flower', 'flowers', 'sunflower', 'rose', 'marigold', 'lavender']
};

/**
 * Initialize the plant detail page
 */
export async function initPlantDetail(plantId) {
    try {
        await loadPlantData(plantId);
        renderPlantDetail();
        bindEvents();
    } catch (error) {
        console.error('Failed to initialize plant detail:', error);
        showError(error.message || 'Failed to load plant details.');
    }
}

/**
 * Load plant data from API
 */
async function loadPlantData(plantId) {
    try {
        const response = await fetch(`/api/plants/guide/${plantId}`);
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Plant not found');
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        if (result.ok && result.data && result.data.plant) {
            plantData = result.data.plant;
        } else {
            throw new Error(result.error?.message || 'Invalid response format');
        }
    } catch (error) {
        console.error('Error loading plant data:', error);
        throw error;
    }
}

/**
 * Render the plant detail page
 */
function renderPlantDetail() {
    if (!plantData) return;

    // Hide loading, show content
    document.getElementById('loading-state')?.classList.add('hidden');
    document.getElementById('plant-content')?.classList.remove('hidden');

    // Breadcrumb
    const breadcrumb = document.getElementById('breadcrumb-plant-name');
    if (breadcrumb) breadcrumb.textContent = plantData.common_name || 'Plant';

    // Hero section
    renderHeroSection();

    // Growing Requirements
    renderRequirements();

    // Timeline
    renderTimeline();

    // Growth Stages
    renderGrowthStages();

    // Companion Plants
    renderCompanionPlants();

    // Pest & Disease Risks
    renderRisks();

    // Automation Settings
    renderAutomation();

    // Sensor Requirements
    renderSensors();

    // Yield Information
    renderYield();

    // Nutritional Information
    renderNutrition();

    // Harvest Guide
    renderHarvestGuide();
}

/**
 * Render hero section
 */
function renderHeroSection() {
    const emoji = getPlantEmoji(plantData);
    const type = getPlantType(plantData);
    const difficulty = plantData.yield_data?.difficulty_level || 'intermediate';

    const safeType = type.replace(/[^a-z0-9-]/g, '');
    const safeDifficulty = String(difficulty).replace(/[^a-z0-9-]/g, '');

    // Badges
    document.getElementById('plant-badges').innerHTML = `
        <span class="badge badge-${safeType}">${escapeHtml(type)}</span>
        <span class="badge badge-${safeDifficulty}">${escapeHtml(difficulty)}</span>
    `;

    // Title and species
    document.getElementById('plant-title').textContent = plantData.common_name || 'Unknown Plant';
    document.getElementById('plant-species').textContent =
        `${plantData.species || ''}${plantData.variety ? ` var. ${plantData.variety}` : ''}`;

    // Description
    document.getElementById('plant-description').textContent =
        plantData.tips || 'No description available.';

    // Emoji
    document.getElementById('plant-emoji').textContent = emoji;
}

/**
 * Render growing requirements
 */
function renderRequirements() {
    const container = document.getElementById('requirements-grid');
    const requirements = [];

    // Temperature from first growth stage
    const firstStage = plantData.growth_stages?.[0];
    if (firstStage?.conditions?.temperature_C) {
        const temp = firstStage.conditions.temperature_C;
        requirements.push({
            icon: 'fa-thermometer-half',
            label: 'Temperature',
            value: `${temp.min}-${temp.max}°C`
        });
    }

    // Light hours
    if (firstStage?.conditions?.hours_per_day) {
        requirements.push({
            icon: 'fa-sun',
            label: 'Light',
            value: `${firstStage.conditions.hours_per_day} hours/day`
        });
    }

    // Water requirements
    if (plantData.water_requirements) {
        requirements.push({
            icon: 'fa-tint',
            label: 'Watering',
            value: plantData.water_requirements
        });
    }

    // Spacing
    if (plantData.yield_data?.space_requirement_cm) {
        const space = plantData.yield_data.space_requirement_cm;
        requirements.push({
            icon: 'fa-arrows-alt',
            label: 'Spacing',
            value: `${space.width}x${space.depth}cm`
        });
    }

    // pH
    if (plantData.pH_range) {
        requirements.push({
            icon: 'fa-flask',
            label: 'Soil pH',
            value: plantData.pH_range
        });
    }

    // Humidity from first stage
    if (firstStage?.conditions?.humidity_percent) {
        const humidity = firstStage.conditions.humidity_percent;
        requirements.push({
            icon: 'fa-water',
            label: 'Humidity',
            value: `${humidity.min}-${humidity.max}%`
        });
    }

    // Feeding schedule from automation
    if (plantData.automation?.watering_schedule) {
        const ws = plantData.automation.watering_schedule;
        requirements.push({
            icon: 'fa-clock',
            label: 'Watering Schedule',
            value: `Every ${ws.frequency_hours} hours, ${ws.amount_ml_per_plant}ml`
        });
    }

    // Space height
    if (plantData.yield_data?.space_requirement_cm?.height) {
        requirements.push({
            icon: 'fa-ruler-vertical',
            label: 'Height Required',
            value: `${plantData.yield_data.space_requirement_cm.height}cm`
        });
    }

    container.innerHTML = requirements.map(req => `
        <div class="requirement-item">
            <div class="requirement-label">
                <i class="fas ${req.icon}" aria-hidden="true"></i>
                ${req.label}
            </div>
            <div class="requirement-value">${escapeHtml(req.value)}</div>
        </div>
    `).join('');
}

/**
 * Render growth timeline
 */
function renderTimeline() {
    const container = document.getElementById('timeline-content');
    const items = [];

    // Calculate total days
    const totalDays = calculateTotalDays(plantData.growth_stages);
    items.push({
        icon: '📅',
        label: 'Full Growth Cycle',
        value: totalDays !== 'N/A' ? `${totalDays} days` : 'N/A'
    });

    // Harvest period
    if (plantData.yield_data?.harvest_period_weeks) {
        items.push({
            icon: '🌾',
            label: 'Harvest Period',
            value: `${plantData.yield_data.harvest_period_weeks} weeks`
        });
    }

    // Harvest type
    if (plantData.yield_data?.harvest_frequency) {
        items.push({
            icon: '🔄',
            label: 'Harvest Type',
            value: plantData.yield_data.harvest_frequency
        });
    }

    container.innerHTML = items.map(item => `
        <div class="timeline-item">
            <div class="timeline-icon">${item.icon}</div>
            <div class="timeline-label">${item.label}</div>
            <div class="timeline-value">${escapeHtml(item.value)}</div>
        </div>
    `).join('');
}

/**
 * Render growth stages
 */
function renderGrowthStages() {
    const container = document.getElementById('stages-timeline');
    const stages = plantData.growth_stages || [];

    if (stages.length === 0) {
        container.innerHTML = '<p class="empty-message">No growth stage information available.</p>';
        return;
    }

    container.innerHTML = stages.map(stage => {
        const duration = stage.duration
            ? `${stage.duration.min_days}-${stage.duration.max_days} days`
            : 'N/A';

        const temp = stage.conditions?.temperature_C
            ? `🌡 ${stage.conditions.temperature_C.min}-${stage.conditions.temperature_C.max}°C`
            : '';

        const humidity = stage.conditions?.humidity_percent
            ? `💧 ${stage.conditions.humidity_percent.min}-${stage.conditions.humidity_percent.max}%`
            : '';

        const light = stage.conditions?.hours_per_day
            ? `☀ ${stage.conditions.hours_per_day}h light`
            : '';

        return `
            <div class="stage-item">
                <div class="stage-name">${escapeHtml(stage.stage)}</div>
                <div class="stage-duration">${duration}</div>
                <div class="stage-details">
                    ${temp ? `<p>${temp}</p>` : ''}
                    ${humidity ? `<p>${humidity}</p>` : ''}
                    ${light ? `<p>${light}</p>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render companion plants
 */
function renderCompanionPlants() {
    const container = document.getElementById('companion-content');
    const companions = plantData.companion_plants;

    if (!companions) {
        container.innerHTML = '<p class="empty-message">No companion plant information available.</p>';
        return;
    }

    const beneficial = companions.beneficial || [];
    const avoid = companions.avoid || [];

    let html = '';

    if (beneficial.length > 0) {
        html += `
            <div class="companion-group beneficial">
                <div class="companion-group-title">
                    <i class="fas fa-check-circle" aria-hidden="true"></i>
                    Beneficial Companions
                </div>
                <div class="companion-tags">
                    ${beneficial.map(p => `<span class="companion-tag">${escapeHtml(p)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    if (avoid.length > 0) {
        html += `
            <div class="companion-group avoid">
                <div class="companion-group-title">
                    <i class="fas fa-times-circle" aria-hidden="true"></i>
                    Avoid Planting Near
                </div>
                <div class="companion-tags">
                    ${avoid.map(p => `<span class="companion-tag">${escapeHtml(p)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    if (companions.reasoning) {
        html += `<p class="companion-note"><i class="fas fa-info-circle" aria-hidden="true"></i> ${escapeHtml(companions.reasoning)}</p>`;
    }

    container.innerHTML = html || '<p class="empty-message">No companion plant information available.</p>';
}

/**
 * Render pest and disease risks
 */
function renderRisks() {
    const container = document.getElementById('risks-content');
    const issues = plantData.common_issues || [];

    if (issues.length === 0 && !plantData.disease_prevention) {
        container.innerHTML = '<p class="empty-message">No pest or disease information available.</p>';
        return;
    }

    let html = '';

    // Common issues as pest tags
    if (issues.length > 0) {
        html += `
            <div class="risks-section">
                <div class="risks-section-title">Common Issues to Watch For:</div>
                <div class="pest-tags">
                    ${issues.map(issue => `
                        <span class="pest-tag">
                            <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
                            ${escapeHtml(issue.problem)}
                        </span>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // Prevention tips
    if (plantData.disease_prevention) {
        html += `
            <div class="prevention-tips">
                <div class="prevention-tips-title">
                    <i class="fas fa-shield-alt" aria-hidden="true"></i>
                    Prevention Tips
                </div>
                <p>${escapeHtml(plantData.disease_prevention)}</p>
            </div>
        `;
    }

    container.innerHTML = html;
}

/**
 * Render automation settings
 */
function renderAutomation() {
    const container = document.getElementById('automation-content');
    const automation = plantData.automation;

    if (!automation) {
        container.innerHTML = '<p class="empty-message">No automation settings available.</p>';
        return;
    }

    let html = '';

    // Watering schedule
    if (automation.watering_schedule) {
        const ws = automation.watering_schedule;
        html += `
            <div class="automation-item">
                <div class="automation-item-title">
                    <i class="fas fa-tint" aria-hidden="true"></i>
                    Watering Schedule
                </div>
                <ul class="automation-list">
                    <li>Every ${ws.frequency_hours} hours</li>
                    <li>${ws.amount_ml_per_plant}ml per plant</li>
                    <li>Trigger at ${ws.soil_moisture_trigger}% moisture</li>
                    ${ws.early_morning_boost ? '<li>Early morning boost enabled</li>' : ''}
                </ul>
            </div>
        `;
    }

    // Lighting schedule
    if (automation.lighting_schedule) {
        const ls = automation.lighting_schedule;
        const items = [];
        if (ls.seedling) items.push(`Seedling: ${ls.seedling.hours}h @ ${ls.seedling.intensity}%`);
        if (ls.vegetative) items.push(`Vegetative: ${ls.vegetative.hours}h @ ${ls.vegetative.intensity}%`);
        if (ls.harvest) items.push(`Harvest: ${ls.harvest.hours}h @ ${ls.harvest.intensity}%`);

        if (items.length > 0) {
            html += `
                <div class="automation-item">
                    <div class="automation-item-title">
                        <i class="fas fa-lightbulb" aria-hidden="true"></i>
                        Lighting Schedule
                    </div>
                    <ul class="automation-list">
                        ${items.map(item => `<li>${item}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
    }

    // Alert thresholds
    if (automation.alert_thresholds) {
        const at = automation.alert_thresholds;
        html += `
            <div class="automation-item">
                <div class="automation-item-title">
                    <i class="fas fa-bell" aria-hidden="true"></i>
                    Alert Thresholds
                </div>
                <ul class="automation-list">
                    <li>Temp: ${at.temperature_min}-${at.temperature_max}°C</li>
                    <li>Humidity: ${at.humidity_min}-${at.humidity_max}%</li>
                    <li>Critical moisture: ${at.soil_moisture_critical}%</li>
                </ul>
            </div>
        `;
    }

    // Environmental controls
    if (automation.environmental_controls) {
        const ec = automation.environmental_controls;
        html += `
            <div class="automation-item">
                <div class="automation-item-title">
                    <i class="fas fa-fan" aria-hidden="true"></i>
                    Environmental Controls
                </div>
                <ul class="automation-list">
                    ${ec.ventilation_trigger_temp ? `<li>Ventilation at ${ec.ventilation_trigger_temp}°C</li>` : ''}
                    ${ec.heating_trigger_temp ? `<li>Heating at ${ec.heating_trigger_temp}°C</li>` : ''}
                    ${ec.dehumidify_trigger ? `<li>Dehumidify at ${ec.dehumidify_trigger}%</li>` : ''}
                </ul>
            </div>
        `;
    }

    container.innerHTML = html || '<p class="empty-message">No automation settings available.</p>';
}

/**
 * Render sensor requirements
 */
function renderSensors() {
    const container = document.getElementById('sensors-content');
    const sensors = plantData.sensor_requirements;

    if (!sensors) {
        container.innerHTML = '<p class="empty-message">No sensor requirements available.</p>';
        return;
    }

    const items = [];

    if (sensors.soil_moisture_range) {
        items.push({
            label: 'Soil Moisture',
            value: `${sensors.soil_moisture_range.min}-${sensors.soil_moisture_range.max}%`
        });
    }

    if (sensors.soil_temperature_C) {
        items.push({
            label: 'Soil Temperature',
            value: `${sensors.soil_temperature_C.min}-${sensors.soil_temperature_C.max}°C`
        });
    }

    if (sensors.co2_requirements) {
        items.push({
            label: 'CO2 Level',
            value: `${sensors.co2_requirements.min}-${sensors.co2_requirements.max} ppm`
        });
    }

    if (sensors.vpd_range) {
        items.push({
            label: 'VPD Range',
            value: `${sensors.vpd_range.min}-${sensors.vpd_range.max} kPa`
        });
    }

    if (sensors.light_spectrum) {
        const ls = sensors.light_spectrum;
        items.push({
            label: 'Light Spectrum',
            value: `Blue ${ls.blue_percent}%, Red ${ls.red_percent}%, Green ${ls.green_percent}%`
        });
    }

    if (sensors.air_quality_sensitivity) {
        items.push({
            label: 'Air Quality Sensitivity',
            value: sensors.air_quality_sensitivity
        });
    }

    container.innerHTML = items.map(item => `
        <div class="sensor-item">
            <div class="sensor-label">${item.label}</div>
            <div class="sensor-value">${escapeHtml(item.value)}</div>
        </div>
    `).join('') || '<p class="empty-message">No sensor requirements available.</p>';
}

/**
 * Render yield information
 */
function renderYield() {
    const container = document.getElementById('yield-content');
    const yieldData = plantData.yield_data;

    if (!yieldData) {
        container.innerHTML = '<p class="empty-message">No yield information available.</p>';
        return;
    }

    const items = [];

    if (yieldData.expected_yield_per_plant) {
        const y = yieldData.expected_yield_per_plant;
        items.push({
            icon: '📦',
            value: `${y.min}-${y.max}${y.unit === 'grams' ? 'g' : y.unit}`,
            label: 'Expected Yield'
        });
    }

    if (yieldData.storage_life_days) {
        items.push({
            icon: '🧊',
            value: `${yieldData.storage_life_days} days`,
            label: 'Storage Life'
        });
    }

    if (yieldData.market_value_per_kg) {
        items.push({
            icon: '💰',
            value: `$${yieldData.market_value_per_kg}/kg`,
            label: 'Market Value'
        });
    }

    container.innerHTML = items.map(item => `
        <div class="yield-item">
            <div class="yield-icon">${item.icon}</div>
            <div class="yield-value">${item.value}</div>
            <div class="yield-label">${item.label}</div>
        </div>
    `).join('') || '<p class="empty-message">No yield information available.</p>';
}

/**
 * Render nutritional information
 */
function renderNutrition() {
    const container = document.getElementById('nutrition-content');
    const nutrition = plantData.nutritional_info;

    if (!nutrition) {
        container.innerHTML = '<p class="empty-message">No nutritional information available.</p>';
        return;
    }

    let html = '';

    // Nutrition stats
    const stats = [];
    if (nutrition.calories_per_100g !== undefined) {
        stats.push({ value: nutrition.calories_per_100g, label: 'Calories/100g' });
    }
    if (nutrition.protein_g !== undefined) {
        stats.push({ value: `${nutrition.protein_g}g`, label: 'Protein' });
    }
    if (nutrition.vitamin_c_mg !== undefined) {
        stats.push({ value: `${nutrition.vitamin_c_mg}mg`, label: 'Vitamin C' });
    }
    if (nutrition.vitamin_k_mcg !== undefined) {
        stats.push({ value: `${nutrition.vitamin_k_mcg}mcg`, label: 'Vitamin K' });
    }

    if (stats.length > 0) {
        html += `
            <div class="nutrition-grid">
                ${stats.map(stat => `
                    <div class="nutrition-item">
                        <div class="nutrition-value">${stat.value}</div>
                        <div class="nutrition-label">${stat.label}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // Key nutrients and health benefits
    const tags = [...(nutrition.key_nutrients || []), ...(nutrition.health_benefits || [])];
    if (tags.length > 0) {
        html += `
            <div class="nutrition-tags">
                ${tags.map(tag => `<span class="nutrition-tag">${escapeHtml(tag)}</span>`).join('')}
            </div>
        `;
    }

    container.innerHTML = html || '<p class="empty-message">No nutritional information available.</p>';
}

/**
 * Render harvest guide
 */
function renderHarvestGuide() {
    const container = document.getElementById('harvest-content');
    const guide = plantData.harvest_guide;

    if (!guide) {
        container.innerHTML = '<p class="empty-message">No harvest guide available.</p>';
        return;
    }

    let html = '';

    if (guide.indicators && guide.indicators.length > 0) {
        html += `
            <div class="harvest-section">
                <div class="harvest-section-title">
                    <i class="fas fa-check-double" aria-hidden="true"></i>
                    Harvest Indicators
                </div>
                <ul class="harvest-list">
                    ${guide.indicators.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    if (guide.storage_tips && guide.storage_tips.length > 0) {
        html += `
            <div class="harvest-section">
                <div class="harvest-section-title">
                    <i class="fas fa-box" aria-hidden="true"></i>
                    Storage Tips
                </div>
                <ul class="harvest-list">
                    ${guide.storage_tips.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    if (guide.processing_options && guide.processing_options.length > 0) {
        html += `
            <div class="harvest-section">
                <div class="harvest-section-title">
                    <i class="fas fa-utensils" aria-hidden="true"></i>
                    Uses
                </div>
                <ul class="harvest-list">
                    ${guide.processing_options.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    container.innerHTML = html || '<p class="empty-message">No harvest guide available.</p>';
}

/**
 * Bind event handlers
 */
function bindEvents() {
    // Add to garden button
    const addToGardenBtn = document.getElementById('add-to-garden-btn');
    if (addToGardenBtn) {
        addToGardenBtn.addEventListener('click', () => {
            const notify = window.showNotification || ((msg) => alert(msg));
            notify(`Add "${plantData.common_name}" to your garden — coming soon!`, 'info');
        });
    }

    // Download guide button
    const downloadBtn = document.getElementById('download-guide-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            const notify = window.showNotification || ((msg) => alert(msg));
            notify(`Download guide for "${plantData.common_name}" — coming soon!`, 'info');
        });
    }
}

/**
 * Show error state
 */
function showError(message) {
    document.getElementById('loading-state').classList.add('hidden');
    document.getElementById('error-state').classList.remove('hidden');
    document.getElementById('error-message').textContent = message;
}

/**
 * Get plant emoji
 */
function getPlantEmoji(plant) {
    const name = (plant.common_name || '').toLowerCase();
    for (const [keyword, emoji] of Object.entries(PLANT_EMOJIS)) {
        if (name.includes(keyword)) {
            return emoji;
        }
    }
    return PLANT_EMOJIS.default;
}

/**
 * Get plant type/category
 */
function getPlantType(plant) {
    const name = (plant.common_name || '').toLowerCase();
    for (const [category, keywords] of Object.entries(PLANT_CATEGORIES)) {
        if (keywords.some(keyword => name.includes(keyword))) {
            return category;
        }
    }
    return 'vegetable';
}

/**
 * Calculate total growth days
 */
function calculateTotalDays(stages) {
    if (!stages || !Array.isArray(stages) || stages.length === 0) {
        return 'N/A';
    }

    let minDays = 0;
    let maxDays = 0;

    stages.forEach(stage => {
        if (stage.duration) {
            minDays += stage.duration.min_days || 0;
            maxDays += stage.duration.max_days || 0;
        }
    });

    if (maxDays === 0) return 'N/A';
    return `${minDays}-${maxDays}`;
}

/**
 * Escape HTML – prefer shared utility from html-utils.js (loaded in base.html)
 */
const escapeHtml = window.escapeHtml || function (text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};
