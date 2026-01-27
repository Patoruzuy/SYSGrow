const API = window.API;
if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before unit_selector.js');
}

// =====================================
// UNIT SELECTION & NAVIGATION
// =====================================

export function initUnitSelector() {
    // Attach event listeners to unit cards
    document.querySelectorAll('.unit-selector-card').forEach(card => {
        card.addEventListener('click', function() {
            const unitId = this.getAttribute('data-unit-id');
            selectUnit(unitId);
        });

        card.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                const unitId = this.getAttribute('data-unit-id');
                selectUnit(unitId);
            }
        });
    });
    
    // Edit button click
    document.querySelectorAll('.edit-unit-btn').forEach(btn => {
        btn.addEventListener('click', function(event) {
            event.stopPropagation();
            const unitId = this.getAttribute('data-unit-id');
            editUnit(unitId);
        });
    });
    
    // Camera button click
    document.querySelectorAll('.view-camera-btn').forEach(btn => {
        btn.addEventListener('click', function(event) {
            event.stopPropagation();
            const unitId = this.getAttribute('data-unit-id');
            viewCamera(unitId);
        });
    });

    // Create Unit buttons
    document.querySelectorAll('.create-unit-btn').forEach(btn => {
        btn.addEventListener('click', createNewUnit);
    });

    // Close Modal buttons
    document.querySelectorAll('.close-modal-btn').forEach(btn => {
        btn.addEventListener('click', closeModal);
    });

    // Form submission
    const unitForm = document.getElementById('unitForm');
    if (unitForm) {
        unitForm.addEventListener('submit', handleUnitFormSubmit);
    }

    // Close modal on escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeModal();
        }
    });

    // Close modal on outside click
    const unitModal = document.getElementById('unitModal');
    if (unitModal) {
        unitModal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
    }
}

function selectUnit(unitId) {
    // Store selected unit in session
    API.post('/api/session/select-unit', { unit_id: unitId })
    .then(data => {
        // API wrapper returns data directly if successful, or throws.
        // Assuming success if we get here.
        // Navigate to dashboard
        window.location.href = '/';
    })
    .catch(error => {
        console.error('Error selecting unit:', error);
        window.showToast('Error selecting unit', 'error');
    });
}

function viewCamera(unitId) {
    // Navigate to camera view
    window.location.href = `/fullscreen?unit_id=${unitId}`;
}

// =====================================
// UNIT CRUD OPERATIONS
// =====================================

let __lastFocus = null;
function focusables(modal) {
    return modal.querySelectorAll('a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])');
}
function enableTrap(modal) {
    modal.__trap = (e) => {
        if (e.key !== 'Tab') return;
        const items = focusables(modal);
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    modal.addEventListener('keydown', modal.__trap);
}
function disableTrap(modal) {
    if (modal.__trap) { modal.removeEventListener('keydown', modal.__trap); delete modal.__trap; }
}

function createNewUnit() {
    __lastFocus = document.activeElement;
    const modalTitle = document.getElementById('modalTitle');
    if (modalTitle) modalTitle.innerHTML = '<i class="fas fa-plus-circle"></i> Create Growth Unit';
    
    const submitBtnText = document.getElementById('submitBtnText');
    if (submitBtnText) submitBtnText.textContent = 'Create Unit';
    
    const unitForm = document.getElementById('unitForm');
    if (unitForm) unitForm.reset();
    
    const unitIdEl = document.getElementById('unitId');
    if (unitIdEl) unitIdEl.value = '';
    
    const modal = document.getElementById('unitModal');
    if (!modal) return;
    
    modal.classList.remove('hidden');
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    enableTrap(modal);
    const first = modal.querySelector('input, select, textarea, button');
    if (first) first.focus();
}

function editUnit(unitId) {
    // Load unit data and show edit modal
    API.Growth.listUnits()
        .then(response => {
            // API.Growth.listUnits returns { data: list }
            const data = response.data || response;
            const unit = Array.isArray(data) ? data.find(u => u.id == unitId || u.unit_id == unitId) : null;
            
            if (unit) {
                const modalTitle = document.getElementById('modalTitle');
                if (modalTitle) modalTitle.innerHTML = '<i class="fas fa-edit"></i> Edit Growth Unit';
                
                const submitBtnText = document.getElementById('submitBtnText');
                if (submitBtnText) submitBtnText.textContent = 'Save Changes';
                
                const unitIdEl = document.getElementById('unitId');
                if (unitIdEl) unitIdEl.value = unit.id || unit.unit_id;
                
                const unitNameEl = document.getElementById('unitName');
                if (unitNameEl) unitNameEl.value = unit.name;
                
                const unitLocationEl = document.getElementById('unitLocation');
                if (unitLocationEl) unitLocationEl.value = unit.location;
                
                if (unit.dimensions) {
                    const w = document.getElementById('unitWidth');
                    const h = document.getElementById('unitHeight');
                    const d = document.getElementById('unitDepth');
                    if (w) w.value = unit.dimensions.width;
                    if (h) h.value = unit.dimensions.height;
                    if (d) d.value = unit.dimensions.depth;
                }
                
                if (unit.custom_image) {
                    const img = document.getElementById('unitImage');
                    if (img) img.value = unit.custom_image;
                }
                
                const modal = document.getElementById('unitModal');
                if (modal) {
                    __lastFocus = document.activeElement;
                    modal.classList.remove('hidden');
                    modal.classList.add('active');
                    modal.setAttribute('aria-hidden', 'false');
                    enableTrap(modal);
                    const first = modal.querySelector('input, select, textarea, button');
                    if (first) first.focus();
                }
            }
        })
        .catch(error => {
            console.error('Error loading unit:', error);
            window.showToast('Failed to load unit data', 'error');
        });
}

function closeModal() {
    const modal = document.getElementById('unitModal');
    if (!modal) return;
    
    disableTrap(modal);
    modal.classList.add('hidden');
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    if (__lastFocus && typeof __lastFocus.focus === 'function') { __lastFocus.focus(); __lastFocus = null; }
}

async function handleUnitFormSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const unitId = formData.get('unit_id');
    
    const data = {
        name: formData.get('name'),
        location: formData.get('location'),
        custom_image: formData.get('custom_image') || null
    };
    
    // Add dimensions if provided
    const width = formData.get('width');
    const height = formData.get('height');
    const depth = formData.get('depth');
    
    if (width && height && depth) {
        data.dimensions = {
            width: parseFloat(width),
            height: parseFloat(height),
            depth: parseFloat(depth)
        };
    }
    
    try {
        let result;
        if (unitId) {
            result = await API.Growth.updateUnit(unitId, data);
        } else {
            result = await API.Growth.createUnit(data);
        }
        
        // API wrapper throws on error, so if we are here it's success
        window.showToast(unitId ? 'Unit updated successfully' : 'Unit created successfully', 'success');
        closeModal();
        setTimeout(() => location.reload(), 1000);
        
    } catch (error) {
        console.error('Error saving unit:', error);
        window.showToast('Error saving unit: ' + error.message, 'error');
    }
}

// =====================================
// UTILITY FUNCTIONS
// =====================================


