export function fillPlantInfo() {
    const select = document.getElementById('plant_select');
    const selectedOption = select.options[select.selectedIndex];
    
    if (!selectedOption.value) return;
    
    // Fill visible fields
    document.getElementById('plant_type').value = selectedOption.dataset.species || '';
    document.getElementById('common_name').value = selectedOption.dataset.common || '';
    document.getElementById('variety').value = selectedOption.dataset.variety || '';
    
    // Fill hidden fields
    document.getElementById('ph_range').value = selectedOption.dataset.ph || '';
    document.getElementById('water_requirements').value = selectedOption.dataset.water || '';
    document.getElementById('soil_moisture_min').value = selectedOption.dataset.soilMin || '';
    document.getElementById('soil_moisture_max').value = selectedOption.dataset.soilMax || '';
    document.getElementById('soil_temp_min').value = selectedOption.dataset.tempMin || '';
    document.getElementById('soil_temp_max').value = selectedOption.dataset.tempMax || '';
    document.getElementById('co2_min').value = selectedOption.dataset.co2Min || '';
    document.getElementById('co2_max').value = selectedOption.dataset.co2Max || '';
    document.getElementById('difficulty_level').value = selectedOption.dataset.difficulty || '';
    
    // Display requirements
    document.getElementById('display_ph').textContent = selectedOption.dataset.ph || '-';
    document.getElementById('display_soil_moisture').textContent = 
        `${selectedOption.dataset.soilMin || '-'} - ${selectedOption.dataset.soilMax || '-'}`;
    document.getElementById('display_soil_temp').textContent = 
        `${selectedOption.dataset.tempMin || '-'} - ${selectedOption.dataset.tempMax || '-'}`;
    document.getElementById('display_co2').textContent = 
        `${selectedOption.dataset.co2Min || '-'} - ${selectedOption.dataset.co2Max || '-'}`;
    document.getElementById('display_water').textContent = selectedOption.dataset.water || '-';
    document.getElementById('display_difficulty').textContent = 
        (selectedOption.dataset.difficulty || 'unknown').charAt(0).toUpperCase() + 
        (selectedOption.dataset.difficulty || 'unknown').slice(1);
    
    // Show requirements section
    const reqSection = document.getElementById('plant_requirements');
    if (reqSection) {
        reqSection.style.display = 'block';
    }
}

export function fillPlantType(plantType, stage) {
    const nameElem = document.getElementById('name');
    const stageElem = document.getElementById('stage');

    if (nameElem) {
        nameElem.value = plantType;
    }
    if (stageElem) {
        stageElem.value = stage;
    }
    if (nameElem) {
        nameElem.focus();
    }
}

function setupEventListeners() {
    const plantSelect = document.getElementById('plant_select');
    if (plantSelect) {
        plantSelect.addEventListener('change', fillPlantInfo);
    }

    document.addEventListener('click', (event) => {
        const target = event.target.closest('[data-action="fill-plant-type"]');
        if (target) {
            fillPlantType(target.dataset.type, target.dataset.stage);
        }
    });
}

document.addEventListener('DOMContentLoaded', setupEventListeners);
