/**
 * Plants Growing Guide Module
 * ============================================
 * Displays comprehensive plant growing information in a modern card grid
 * with filtering, search, and detailed modal views.
 */

let plantsData = [];
let filteredPlants = [];

// Plant emoji mapping
const PLANT_EMOJIS = {
    'tomato': '🍅',
    'tomatoes': '🍅',
    'lettuce': '🥬',
    'leafy greens': '🥬',
    'pepper': '🌶️',
    'peppers': '🌶️',
    'cucumber': '🥒',
    'cucumbers': '🥒',
    'carrot': '🥕',
    'carrots': '🥕',
    'strawberry': '🍓',
    'strawberries': '🍓',
    'basil': '🌿',
    'herbs': '🌿',
    'mint': '🌿',
    'rosemary': '🌿',
    'cannabis': '🌿',
    'flower': '🌸',
    'flowers': '🌸',
    'sunflower': '🌻',
    'rose': '🌹',
    'corn': '🌽',
    'potato': '🥔',
    'potatoes': '🥔',
    'onion': '🧅',
    'onions': '🧅',
    'garlic': '🧄',
    'mushroom': '🍄',
    'mushrooms': '🍄',
    'broccoli': '🥦',
    'eggplant': '🍆',
    'avocado': '🥑',
    'bean': '🫘',
    'beans': '🫘',
    'pea': '🫛',
    'peas': '🫛',
    'chili': '🌶️',
    'default': '🌱'
};

// Plant type categorization
const PLANT_CATEGORIES = {
    vegetable: ['tomato', 'tomatoes', 'lettuce', 'leafy greens', 'pepper', 'peppers', 'cucumber', 'cucumbers', 'carrot', 'carrots', 'potato', 'potatoes', 'onion', 'onions', 'garlic', 'broccoli', 'eggplant', 'corn', 'bean', 'beans', 'pea', 'peas'],
    herb: ['basil', 'mint', 'rosemary', 'thyme', 'oregano', 'parsley', 'cilantro', 'sage', 'herbs', 'cannabis'],
    fruit: ['strawberry', 'strawberries', 'tomato', 'tomatoes', 'pepper', 'peppers', 'cucumber', 'cucumbers', 'avocado'],
    flower: ['flower', 'flowers', 'sunflower', 'rose', 'marigold', 'lavender']
};

/**
 * Initialize the plants guide page
 */
export async function initPlantsGuide() {
    try {
        await loadPlantsData();
        renderPlantCards(plantsData);
        bindEvents();
        updateResultsCount();
    } catch (error) {
        console.error('Failed to initialize plants guide:', error);
        showError('Failed to load plant guide data. Please try again.');
    }
}

/**
 * Load plants data from API
 */
async function loadPlantsData() {
    const container = document.getElementById('plant-cards-container');
    container.innerHTML = `
        <div class="loading-state">
            <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
            <p>Loading plant guide...</p>
        </div>
    `;

    try {
        let result;
        if (window.API && window.API.Plant && window.API.Plant.getPlantsGuideFull) {
            result = await window.API.Plant.getPlantsGuideFull();
            // window.API unwraps data.data, so result IS the guide payload
            if (result && result.plants) {
                plantsData = result.plants;
            } else {
                throw new Error('Invalid response format');
            }
        } else {
            // Fallback to direct fetch
            const response = await fetch('/api/plants/guide/full');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            result = await response.json();
            if (result.ok && result.data && result.data.plants) {
                plantsData = result.data.plants;
            } else {
                throw new Error(result.error?.message || 'Invalid response format');
            }
        }
        filteredPlants = [...plantsData];
    } catch (error) {
        console.error('Error loading plants data:', error);
        throw error;
    }
}

/**
 * Bind event listeners
 */
function bindEvents() {
    // Search input
    const searchInput = document.getElementById('guide-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleSearch, 300));
    }

    // Difficulty filter
    const difficultyFilter = document.getElementById('difficulty-filter');
    if (difficultyFilter) {
        difficultyFilter.addEventListener('change', handleFilters);
    }

    // Type filter
    const typeFilter = document.getElementById('type-filter');
    if (typeFilter) {
        typeFilter.addEventListener('change', handleFilters);
    }

    // Modal close
    const modal = document.getElementById('plant-details-modal');
    if (modal) {
        const closeBtn = modal.querySelector('.modal-close');
        const backdrop = modal.querySelector('.modal-backdrop');

        if (closeBtn) {
            closeBtn.addEventListener('click', closeModal);
        }
        if (backdrop) {
            backdrop.addEventListener('click', closeModal);
        }

        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !modal.hidden) {
                closeModal();
            }
        });
    }

    // Card clicks (event delegation) - navigate to detail page
    const container = document.getElementById('plant-cards-container');
    if (container) {
        container.addEventListener('click', (e) => {
            const card = e.target.closest('.plant-guide-card');
            if (card) {
                const plantId = card.dataset.plantId;
                // Navigate to plant detail page
                window.location.href = `/plants/guide/${plantId}`;
            }
        });

        // Also handle keyboard navigation
        container.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                const card = e.target.closest('.plant-guide-card');
                if (card) {
                    e.preventDefault();
                    const plantId = card.dataset.plantId;
                    window.location.href = `/plants/guide/${plantId}`;
                }
            }
        });
    }
}

/**
 * Handle search input
 */
function handleSearch(e) {
    const query = e.target.value.toLowerCase().trim();
    applyFilters(query);
}

/**
 * Handle filter changes
 */
function handleFilters() {
    const searchInput = document.getElementById('guide-search');
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
    applyFilters(query);
}

/**
 * Apply all filters and search
 */
function applyFilters(searchQuery = '') {
    const difficultyFilter = document.getElementById('difficulty-filter');
    const typeFilter = document.getElementById('type-filter');

    const difficulty = difficultyFilter ? difficultyFilter.value : 'all';
    const type = typeFilter ? typeFilter.value : 'all';

    filteredPlants = plantsData.filter(plant => {
        // Search filter
        if (searchQuery) {
            const name = (plant.common_name || '').toLowerCase();
            const species = (plant.species || '').toLowerCase();
            const variety = (plant.variety || '').toLowerCase();
            const aliases = (plant.aliases || []).map(a => a.toLowerCase());

            const matchesSearch = name.includes(searchQuery) ||
                species.includes(searchQuery) ||
                variety.includes(searchQuery) ||
                aliases.some(a => a.includes(searchQuery));

            if (!matchesSearch) return false;
        }

        // Difficulty filter
        if (difficulty !== 'all') {
            const plantDifficulty = plant.yield_data?.difficulty_level || 'intermediate';
            if (plantDifficulty !== difficulty) return false;
        }

        // Type filter
        if (type !== 'all') {
            const plantType = getPlantType(plant);
            if (plantType !== type) return false;
        }

        return true;
    });

    renderPlantCards(filteredPlants);
    updateResultsCount();
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
    return 'vegetable'; // Default
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
 * Update results count display
 */
function updateResultsCount() {
    const countEl = document.getElementById('results-count');
    if (countEl) {
        countEl.textContent = `Showing ${filteredPlants.length} of ${plantsData.length} plants`;
    }
}

/**
 * Render plant cards
 */
function renderPlantCards(plants) {
    const container = document.getElementById('plant-cards-container');
    if (!container) return;

    if (!plants || plants.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-seedling" aria-hidden="true"></i>
                <p>No plants found matching your criteria.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = plants.map(plant => renderPlantCard(plant)).join('');
}

/**
 * Render a single plant card
 */
function renderPlantCard(plant) {
    const emoji = getPlantEmoji(plant);
    const type = getPlantType(plant);
    const difficulty = plant.yield_data?.difficulty_level || 'intermediate';
    const totalDays = calculateTotalDays(plant.growth_stages);

    // Get first growth stage for temperature and light
    const firstStage = plant.growth_stages?.[0] || {};
    const conditions = firstStage.conditions || {};

    const tempRange = conditions.temperature_C
        ? `${conditions.temperature_C.min}-${conditions.temperature_C.max}°C`
        : 'N/A';

    const lightHours = conditions.hours_per_day
        ? `${conditions.hours_per_day}h light`
        : 'N/A';

    const yieldData = plant.yield_data?.expected_yield_per_plant;
    const yieldStr = yieldData
        ? `${yieldData.min}-${yieldData.max}${yieldData.unit === 'grams' ? 'g' : yieldData.unit}`
        : 'N/A';

    const spaceData = plant.yield_data?.space_requirement_cm;
    const spaceStr = spaceData
        ? `${spaceData.width}x${spaceData.depth}x${spaceData.height}cm`
        : 'N/A';

    return `
        <article class="plant-guide-card" data-plant-id="${plant.id}" tabindex="0" role="button" aria-label="View details for ${plant.common_name}">
            <div class="plant-card-header">
                <div class="plant-emoji">${emoji}</div>
            </div>
            <div class="plant-card-body">
                <h3 class="plant-card-name">${escapeHtml(plant.common_name || 'Unknown')}</h3>
                <p class="plant-card-species">${escapeHtml(plant.species || plant.variety || '')}</p>

                <div class="plant-card-badges">
                    <span class="badge badge-${type}">${type}</span>
                    <span class="badge badge-${difficulty}">${difficulty}</span>
                </div>

                <p class="plant-card-description">${escapeHtml(plant.tips || '')}</p>

                <div class="plant-quick-stats">
                    <div class="quick-stat">
                        <span class="quick-stat-icon">⏱</span>
                        <span class="quick-stat-text">${totalDays} days</span>
                    </div>
                    <div class="quick-stat">
                        <span class="quick-stat-icon">🌡</span>
                        <span class="quick-stat-text">${tempRange}</span>
                    </div>
                    <div class="quick-stat">
                        <span class="quick-stat-icon">☀</span>
                        <span class="quick-stat-text">${lightHours}</span>
                    </div>
                    <div class="quick-stat">
                        <span class="quick-stat-icon">💧</span>
                        <span class="quick-stat-text">${escapeHtml(truncate(plant.water_requirements || 'Regular', 20))}</span>
                    </div>
                    <div class="quick-stat">
                        <span class="quick-stat-icon">📦</span>
                        <span class="quick-stat-text">${yieldStr}</span>
                    </div>
                    <div class="quick-stat">
                        <span class="quick-stat-icon">📏</span>
                        <span class="quick-stat-text">${spaceStr}</span>
                    </div>
                </div>
            </div>
        </article>
    `;
}

/**
 * Open plant details modal
 */
function openPlantDetails(plantId) {
    const plant = plantsData.find(p => String(p.id) === String(plantId));
    if (!plant) {
        console.error('Plant not found:', plantId);
        return;
    }

    const modal = document.getElementById('plant-details-modal');
    const modalName = document.getElementById('modal-plant-name');
    const modalBody = document.getElementById('modal-body');

    if (!modal || !modalBody) return;

    modalName.textContent = plant.common_name || 'Plant Details';
    modalBody.innerHTML = renderPlantDetails(plant);

    // Bind issue card toggles
    modalBody.querySelectorAll('.issue-header').forEach(header => {
        header.addEventListener('click', () => {
            const card = header.closest('.issue-card');
            card.classList.toggle('expanded');
        });
    });

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
}

/**
 * Close modal
 */
function closeModal() {
    const modal = document.getElementById('plant-details-modal');
    if (modal) {
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }
}

/**
 * Render detailed plant information
 */
function renderPlantDetails(plant) {
    const emoji = getPlantEmoji(plant);
    const type = getPlantType(plant);
    const difficulty = plant.yield_data?.difficulty_level || 'intermediate';

    return `
        <!-- Overview Section -->
        <div class="plant-overview">
            <div class="plant-overview-header">
                <div class="plant-emoji">${emoji}</div>
                <h2>${escapeHtml(plant.common_name)}</h2>
                <p class="species">${escapeHtml(plant.species || '')}${plant.variety ? ` - ${escapeHtml(plant.variety)}` : ''}</p>
                <div class="plant-card-badges" style="justify-content: center; margin-top: var(--space-2);">
                    <span class="badge badge-${type}">${type}</span>
                    <span class="badge badge-${difficulty}">${difficulty}</span>
                </div>
            </div>
            <div class="plant-overview-info">
                <div class="info-row">
                    <div class="info-item">
                        <div class="info-item-label">pH Range</div>
                        <div class="info-item-value">${escapeHtml(plant.pH_range || 'N/A')}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-item-label">Water Requirements</div>
                        <div class="info-item-value">${escapeHtml(plant.water_requirements || 'Regular watering')}</div>
                    </div>
                </div>
                ${plant.tips ? `
                    <div class="info-item" style="flex: none;">
                        <div class="info-item-label">Growing Tips</div>
                        <div class="info-item-value" style="font-weight: normal; font-size: 0.875rem; line-height: 1.5;">${escapeHtml(plant.tips)}</div>
                    </div>
                ` : ''}
            </div>
        </div>

        <!-- Growth Stages -->
        ${renderGrowthStages(plant.growth_stages)}

        <!-- Sensor Requirements -->
        ${renderSensorRequirements(plant.sensor_requirements)}

        <!-- Automation Settings -->
        ${renderAutomationSettings(plant.automation)}

        <!-- Yield & Space -->
        ${renderYieldInfo(plant.yield_data)}

        <!-- Nutritional Info -->
        ${renderNutritionalInfo(plant.nutritional_info)}

        <!-- Common Issues -->
        ${renderCommonIssues(plant.common_issues)}

        <!-- Companion Plants -->
        ${renderCompanionPlants(plant.companion_plants)}

        <!-- Harvest Guide -->
        ${renderHarvestGuide(plant.harvest_guide)}
    `;
}

/**
 * Render growth stages section
 */
function renderGrowthStages(stages) {
    if (!stages || !Array.isArray(stages) || stages.length === 0) {
        return '';
    }

    const stagesHtml = stages.map(stage => {
        const duration = stage.duration
            ? `${stage.duration.min_days}-${stage.duration.max_days} days`
            : 'N/A';

        const temp = stage.conditions?.temperature_C
            ? `${stage.conditions.temperature_C.min}-${stage.conditions.temperature_C.max}°C`
            : 'N/A';

        const humidity = stage.conditions?.humidity_percent
            ? `${stage.conditions.humidity_percent.min}-${stage.conditions.humidity_percent.max}%`
            : 'N/A';

        const light = stage.conditions?.hours_per_day
            ? `${stage.conditions.hours_per_day}h light`
            : 'N/A';

        return `
            <div class="growth-stage">
                <div class="stage-name">${escapeHtml(stage.stage)}</div>
                <div class="stage-duration">${duration}</div>
                <div class="stage-conditions">
                    🌡 ${temp}<br>
                    💧 ${humidity}<br>
                    ☀ ${light}
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-chart-line" aria-hidden="true"></i>
                <h3>Growth Stages</h3>
            </div>
            <div class="growth-timeline">
                ${stagesHtml}
            </div>
        </div>
    `;
}

/**
 * Render sensor requirements section
 */
function renderSensorRequirements(requirements) {
    if (!requirements) return '';

    const items = [];

    if (requirements.soil_moisture_range) {
        items.push({
            label: 'Soil Moisture',
            value: `${requirements.soil_moisture_range.min}-${requirements.soil_moisture_range.max}%`
        });
    }

    if (requirements.soil_temperature_C) {
        items.push({
            label: 'Soil Temperature',
            value: `${requirements.soil_temperature_C.min}-${requirements.soil_temperature_C.max}°C`
        });
    }

    if (requirements.co2_requirements) {
        items.push({
            label: 'CO2 Level',
            value: `${requirements.co2_requirements.min}-${requirements.co2_requirements.max} ppm`
        });
    }

    if (requirements.vpd_range) {
        items.push({
            label: 'VPD Range',
            value: `${requirements.vpd_range.min}-${requirements.vpd_range.max} kPa`
        });
    }

    if (requirements.light_spectrum) {
        const spectrum = requirements.light_spectrum;
        items.push({
            label: 'Light Spectrum',
            value: `Blue: ${spectrum.blue_percent}%, Red: ${spectrum.red_percent}%, Green: ${spectrum.green_percent}%`
        });
    }

    if (items.length === 0) return '';

    const itemsHtml = items.map(item => `
        <div class="sensor-requirement">
            <div class="sensor-requirement-label">${item.label}</div>
            <div class="sensor-requirement-value">${item.value}</div>
        </div>
    `).join('');

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-microchip" aria-hidden="true"></i>
                <h3>Sensor Requirements</h3>
            </div>
            <div class="sensor-requirements-grid">
                ${itemsHtml}
            </div>
        </div>
    `;
}

/**
 * Render automation settings section
 */
function renderAutomationSettings(automation) {
    if (!automation) return '';

    const cards = [];

    if (automation.watering_schedule) {
        const ws = automation.watering_schedule;
        cards.push({
            icon: 'fa-tint',
            title: 'Watering',
            items: [
                `Every ${ws.frequency_hours} hours`,
                `${ws.amount_ml_per_plant}ml per plant`,
                `Trigger at ${ws.soil_moisture_trigger}% moisture`
            ]
        });
    }

    if (automation.lighting_schedule) {
        const ls = automation.lighting_schedule;
        const items = [];
        if (ls.seedling) items.push(`Seedling: ${ls.seedling.hours}h @ ${ls.seedling.intensity}%`);
        if (ls.vegetative) items.push(`Vegetative: ${ls.vegetative.hours}h @ ${ls.vegetative.intensity}%`);
        if (ls.harvest) items.push(`Harvest: ${ls.harvest.hours}h @ ${ls.harvest.intensity}%`);

        if (items.length > 0) {
            cards.push({
                icon: 'fa-lightbulb',
                title: 'Lighting',
                items
            });
        }
    }

    if (automation.alert_thresholds) {
        const at = automation.alert_thresholds;
        cards.push({
            icon: 'fa-bell',
            title: 'Alert Thresholds',
            items: [
                `Temp: ${at.temperature_min}-${at.temperature_max}°C`,
                `Humidity: ${at.humidity_min}-${at.humidity_max}%`,
                `Critical moisture: ${at.soil_moisture_critical}%`
            ]
        });
    }

    if (cards.length === 0) return '';

    const cardsHtml = cards.map(card => `
        <div class="automation-card">
            <h4><i class="fas ${card.icon}" aria-hidden="true"></i> ${card.title}</h4>
            <ul>
                ${card.items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
            </ul>
        </div>
    `).join('');

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-cogs" aria-hidden="true"></i>
                <h3>Automation Settings</h3>
            </div>
            <div class="automation-grid">
                ${cardsHtml}
            </div>
        </div>
    `;
}

/**
 * Render yield info section
 */
function renderYieldInfo(yieldData) {
    if (!yieldData) return '';

    const items = [];

    if (yieldData.expected_yield_per_plant) {
        const y = yieldData.expected_yield_per_plant;
        items.push({
            icon: '📦',
            value: `${y.min}-${y.max}${y.unit === 'grams' ? 'g' : y.unit}`,
            label: 'Expected Yield'
        });
    }

    if (yieldData.harvest_frequency) {
        items.push({
            icon: '🔄',
            value: yieldData.harvest_frequency,
            label: 'Harvest Type'
        });
    }

    if (yieldData.harvest_period_weeks) {
        items.push({
            icon: '📅',
            value: `${yieldData.harvest_period_weeks} weeks`,
            label: 'Harvest Period'
        });
    }

    if (yieldData.storage_life_days) {
        items.push({
            icon: '🧊',
            value: `${yieldData.storage_life_days} days`,
            label: 'Storage Life'
        });
    }

    if (yieldData.space_requirement_cm) {
        const s = yieldData.space_requirement_cm;
        items.push({
            icon: '📐',
            value: `${s.width}x${s.depth}x${s.height}cm`,
            label: 'Space Required'
        });
    }

    if (yieldData.market_value_per_kg) {
        items.push({
            icon: '💰',
            value: `$${yieldData.market_value_per_kg}/kg`,
            label: 'Market Value'
        });
    }

    if (items.length === 0) return '';

    const itemsHtml = items.map(item => `
        <div class="yield-item">
            <div class="yield-icon">${item.icon}</div>
            <div class="yield-value">${item.value}</div>
            <div class="yield-label">${item.label}</div>
        </div>
    `).join('');

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-balance-scale" aria-hidden="true"></i>
                <h3>Yield & Space</h3>
            </div>
            <div class="yield-grid">
                ${itemsHtml}
            </div>
        </div>
    `;
}

/**
 * Render nutritional info section
 */
function renderNutritionalInfo(nutrition) {
    if (!nutrition) return '';

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

    const statsHtml = stats.map(stat => `
        <div class="nutrition-item">
            <div class="nutrition-value">${stat.value}</div>
            <div class="nutrition-label">${stat.label}</div>
        </div>
    `).join('');

    const keyNutrients = nutrition.key_nutrients || [];
    const healthBenefits = nutrition.health_benefits || [];

    const tagsHtml = [...keyNutrients, ...healthBenefits].map(tag =>
        `<span class="nutrition-tag">${escapeHtml(tag)}</span>`
    ).join('');

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-apple-alt" aria-hidden="true"></i>
                <h3>Nutritional Information</h3>
            </div>
            ${stats.length > 0 ? `<div class="nutrition-grid">${statsHtml}</div>` : ''}
            ${tagsHtml ? `<div class="nutrition-tags">${tagsHtml}</div>` : ''}
        </div>
    `;
}

/**
 * Render common issues section
 */
function renderCommonIssues(issues) {
    if (!issues || !Array.isArray(issues) || issues.length === 0) {
        return '';
    }

    const issuesHtml = issues.map(issue => `
        <div class="issue-card">
            <div class="issue-header">
                <span class="issue-name">${escapeHtml(issue.problem)}</span>
                <i class="fas fa-chevron-down issue-toggle" aria-hidden="true"></i>
            </div>
            <div class="issue-details">
                ${issue.symptoms && issue.symptoms.length > 0 ? `
                    <div class="issue-section">
                        <div class="issue-section-title">Symptoms</div>
                        <ul>
                            ${issue.symptoms.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${issue.causes && issue.causes.length > 0 ? `
                    <div class="issue-section">
                        <div class="issue-section-title">Causes</div>
                        <ul>
                            ${issue.causes.map(c => `<li>${escapeHtml(c)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${issue.solutions && issue.solutions.length > 0 ? `
                    <div class="issue-section">
                        <div class="issue-section-title">Solutions</div>
                        <ul>
                            ${issue.solutions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${issue.prevention ? `
                    <div class="issue-section">
                        <div class="issue-section-title">Prevention</div>
                        <p style="margin: 0; font-size: 0.8125rem;">${escapeHtml(issue.prevention)}</p>
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('');

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-bug" aria-hidden="true"></i>
                <h3>Common Issues</h3>
            </div>
            <div class="issues-list">
                ${issuesHtml}
            </div>
        </div>
    `;
}

/**
 * Render companion plants section
 */
function renderCompanionPlants(companions) {
    if (!companions) return '';

    const beneficial = companions.beneficial || [];
    const avoid = companions.avoid || [];

    if (beneficial.length === 0 && avoid.length === 0) return '';

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-heart" aria-hidden="true"></i>
                <h3>Companion Plants</h3>
            </div>
            <div class="companion-section">
                ${beneficial.length > 0 ? `
                    <div class="companion-group beneficial">
                        <h4><i class="fas fa-check-circle" aria-hidden="true"></i> Beneficial Companions</h4>
                        <div class="companion-list">
                            ${beneficial.map(p => `<span class="companion-tag">${escapeHtml(p)}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
                ${avoid.length > 0 ? `
                    <div class="companion-group avoid">
                        <h4><i class="fas fa-times-circle" aria-hidden="true"></i> Avoid Planting Near</h4>
                        <div class="companion-list">
                            ${avoid.map(p => `<span class="companion-tag">${escapeHtml(p)}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
            ${companions.reasoning ? `
                <p style="margin-top: var(--space-3); font-size: 0.8125rem; color: var(--color-text-muted);">
                    <i class="fas fa-info-circle" aria-hidden="true"></i> ${escapeHtml(companions.reasoning)}
                </p>
            ` : ''}
        </div>
    `;
}

/**
 * Render harvest guide section
 */
function renderHarvestGuide(guide) {
    if (!guide) return '';

    const cards = [];

    if (guide.indicators && guide.indicators.length > 0) {
        cards.push({
            icon: 'fa-check-double',
            title: 'Harvest Indicators',
            items: guide.indicators
        });
    }

    if (guide.storage_tips && guide.storage_tips.length > 0) {
        cards.push({
            icon: 'fa-box',
            title: 'Storage Tips',
            items: guide.storage_tips
        });
    }

    if (guide.processing_options && guide.processing_options.length > 0) {
        cards.push({
            icon: 'fa-utensils',
            title: 'Processing Options',
            items: guide.processing_options
        });
    }

    if (cards.length === 0) return '';

    const cardsHtml = cards.map(card => `
        <div class="harvest-card">
            <h4><i class="fas ${card.icon}" aria-hidden="true"></i> ${card.title}</h4>
            <ul>
                ${card.items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
            </ul>
        </div>
    `).join('');

    return `
        <div class="detail-section">
            <div class="detail-section-header">
                <i class="fas fa-cut" aria-hidden="true"></i>
                <h3>Harvest Guide</h3>
            </div>
            <div class="harvest-grid">
                ${cardsHtml}
            </div>
        </div>
    `;
}

/**
 * Show error message
 */
function showError(message) {
    const container = document.getElementById('plant-cards-container');
    if (container) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
                <p>${escapeHtml(message)}</p>
            </div>
        `;
    }
}

/**
 * Utility: Escape HTML — delegate to shared utility
 */
function escapeHtml(text) {
    if (window.escapeHtml) return window.escapeHtml(text);
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Utility: Truncate text
 */
function truncate(text, maxLength) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

/**
 * Utility: Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
