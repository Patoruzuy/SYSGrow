/**
 * SYSGrow API Client Module
 * 
 * Centralized API client for all backend endpoints.
 * Provides type-safe, promise-based functions for all API routes.
 * 
 * @module api
 * @version 1.0.0
 */

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : null;
}

/**
 * Base API request handler with error handling
 * @param {string} url - API endpoint URL
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Response data
 */
async function apiRequest(url, options = {}) {
    const csrfToken = getCsrfToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
    }

    const defaultOptions = {
        headers,
        ...options
    };

    try {
        const response = await fetch(url, defaultOptions);

        // Be tolerant of non-JSON error bodies (e.g., Werkzeug HTML 405 pages).
        const rawText = await response.text();
        let data = null;
        if (rawText) {
            try {
                data = JSON.parse(rawText);
            } catch {
                data = null;
            }
        }

        if (!response.ok) {
            const message =
                data?.error?.message ||
                (typeof data?.error === 'string' ? data.error : null) ||
                data?.message ||
                `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
            const err = new Error(message);
            err.status = response.status;
            err.details = data?.details || null;
            err.payload = data || null;
            throw err;
        }

        if (data && data.data !== undefined) return data.data;
        return data !== null ? data : rawText;
    } catch (error) {
        console.error(`API Request Failed: ${url}`, error);
        throw error;
    }
}

/**
 * Helper for GET requests
 */
function get(url) {
    return apiRequest(url, { method: 'GET' });
}

/**
 * Helper for POST requests
 */
function post(url, body = null) {
    return apiRequest(url, {
        method: 'POST',
        body: body ? JSON.stringify(body) : null
    });
}

/**
 * Helper for PUT requests
 */
function put(url, body = null) {
    return apiRequest(url, {
        method: 'PUT',
        body: body ? JSON.stringify(body) : null
    });
}

/**
 * Helper for PATCH requests
 */
function patch(url, body = null) {
    return apiRequest(url, {
        method: 'PATCH',
        body: body ? JSON.stringify(body) : null
    });
}

/**
 * Helper for DELETE requests
 */
function del(url) {
    return apiRequest(url, { method: 'DELETE' });
}

/**
 * Helper for POST requests with FormData (multipart)
 * @param {string} url - API endpoint URL  
 * @param {FormData} formData - Form data to send
 * @returns {Promise<Object>} Response data
 */
async function postFormData(url, formData) {
    const csrfToken = getCsrfToken();
    const headers = {};
    if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
    }
    // Don't set Content-Type - browser will set it with boundary for multipart

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers,
            body: formData
        });

        const rawText = await response.text();
        let data = null;
        if (rawText) {
            try {
                data = JSON.parse(rawText);
            } catch {
                data = null;
            }
        }

        if (!response.ok) {
            const message =
                data?.error?.message ||
                (typeof data?.error === 'string' ? data.error : null) ||
                data?.message ||
                `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
            throw new Error(message);
        }

        if (data && data.data !== undefined) return data.data;
        return data !== null ? data : rawText;
    } catch (error) {
        console.error(`API FormData Request Failed: ${url}`, error);
        throw error;
    }
}

// ============================================================================
// GROWTH UNITS API
// ============================================================================

const GrowthAPI = {
    /**
     * List all growth units
     * @returns {Promise<{units: Array, count: number}>}
     */
    async listUnits() {
        let payload;
        try {
            payload = await get('/api/growth/v2/units');
        } catch (err) {
            if (err?.message?.includes('405') || err?.message?.includes('404')) {
                payload = await get('/api/growth/units');
            } else {
                throw err;
            }
        }
        const list = Array.isArray(payload)
            ? payload
            : payload?.data || payload?.units || [];
        return { data: list };
    },

    /**
     * Get specific growth unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Unit data
     */
    getUnit(unitId) {
        return get(`/api/growth/units/${unitId}`);
    },

    /**
     * Create a new growth unit
     * @param {Object} unitData - Unit data
     * @param {string} unitData.name - Unit name (required)
     * @param {string} [unitData.location='Indoor'] - Location
     * @param {Object} [unitData.dimensions] - Physical dimensions
     * @param {Object} [unitData.device_schedules] - Device schedules
     * @param {string} [unitData.custom_image] - Custom image path
     * @param {boolean} [unitData.camera_enabled=false] - Enable camera
     * @returns {Promise<Object>} Created unit
     */
    createUnit(unitData) {
        return post('/api/growth/v2/units', unitData);
    },

    /**
     * Update an existing growth unit
     * @param {number} unitId - Unit ID
     * @param {Object} updates - Fields to update
     * @returns {Promise<Object>} Updated unit
     */
    updateUnit(unitId, updates) {
        return patch(`/api/growth/v2/units/${unitId}`, updates);
    },

    /**
     * Delete a growth unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Deletion result
     */
    deleteUnit(unitId) {
        return del(`/api/growth/v2/units/${unitId}`);
    },

    /**
     * Get unit thresholds
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Threshold settings
     */
    getThresholds(unitId) {
        return get(`/api/growth/v2/units/${unitId}/thresholds`);
    },

    /**
     * Set unit thresholds
     * @param {number} unitId - Unit ID
     * @param {Object} thresholds - Threshold values
     * @returns {Promise<Object>} Updated thresholds
     */
    setThresholds(unitId, thresholds) {
        return post(`/api/growth/v2/units/${unitId}/thresholds`, thresholds);
    },

    /**
     * Suggest environmental thresholds based on the active plant in the unit.
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Suggested thresholds
     */
    async suggestThresholds(unitId) {
        if (!Number.isFinite(Number(unitId))) {
            throw new Error('unitId is required');
        }

        const unit = await this.getUnit(unitId);
        const activePlantId = unit?.active_plant_id ?? null;

        let plant = null;

        if (activePlantId !== null && activePlantId !== undefined) {
            try {
                plant = await get(`/api/plants/plants/${unitId}/${activePlantId}`);
            } catch {
                plant = null;
            }
        }

        if (!plant) {
            const list = await get(`/api/plants/units/${unitId}/plants`);
            plant = list?.plants?.[0] || null;
        }

        if (!plant) {
            throw new Error('No plants found in this unit. Add a plant to enable threshold suggestions.');
        }

        const plantType = plant?.plant_type || plant?.plantType || plant?.type || null;
        if (!plantType) {
            throw new Error('Plant type is required to suggest thresholds.');
        }

        const growthStage =
            plant?.current_stage ||
            plant?.growth_stage ||
            plant?.stage ||
            plant?.currentStage ||
            null;

        const params = new URLSearchParams();
        params.set('plant_type', plantType);
        if (growthStage) params.set('growth_stage', growthStage);

        const recommended = await get(`/api/growth/thresholds/recommended?${params.toString()}`);
        const raw = recommended?.raw || {};

        if (window.SensorFields) {
            return window.SensorFields.standardize(raw);
        }

        return {
            temperature: raw.temperature_threshold ?? raw.temperature,
            humidity: raw.humidity_threshold ?? raw.humidity,
            soil_moisture: raw.soil_moisture_threshold ?? raw.soil_moisture,
            co2: raw.co2_threshold ?? raw.co2 ?? raw.co2_level,
            voc: raw.voc_threshold ?? raw.voc,
            lux: raw.lux_threshold ?? raw.light_intensity_threshold ?? raw.light_intensity ?? raw.lux ?? raw.light_level,
            air_quality: raw.air_quality_threshold ?? raw.air_quality ?? raw.aqi_threshold ?? raw.aqi
        };
    },

    /**
     * Get all device schedules for a unit (v3-backed, v2-compatible response)
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Device schedules
     */
    async getSchedules(unitId) {
        const response = await this.getSchedulesV3(unitId);
        const schedules = response?.schedules || [];
        const device_schedules = {};

        schedules.forEach((schedule) => {
            const deviceType = schedule?.device_type;
            if (!deviceType || device_schedules[deviceType]) return;
            device_schedules[deviceType] = {
                schedule_id: schedule.schedule_id,
                start_time: schedule.start_time,
                end_time: schedule.end_time,
                enabled: schedule.enabled,
            };
        });

        return { schedules, device_schedules };
    },

    /**
     * Get schedule for specific device (v3-backed, v2-compatible response)
     * @param {number} unitId - Unit ID
     * @param {string} deviceType - Device type
     * @returns {Promise<Object>} Device schedule
     */
    async getDeviceSchedule(unitId, deviceType) {
        const response = await this.getSchedulesV3(unitId, { device_type: deviceType });
        const schedules = response?.schedules || [];
        const schedule = schedules[0] || null;

        return {
            device_type: deviceType,
            schedule: schedule
                ? {
                    schedule_id: schedule.schedule_id,
                    start_time: schedule.start_time,
                    end_time: schedule.end_time,
                    enabled: schedule.enabled,
                }
                : null
        };
    },

    /**
     * Set device schedule (v3-backed)
     * @param {number} unitId - Unit ID
     * @param {Object} scheduleData - Schedule data
     * @param {string} scheduleData.device_type - Device type
     * @param {string} scheduleData.start_time - Start time (HH:MM)
     * @param {string} scheduleData.end_time - End time (HH:MM)
     * @param {boolean} [scheduleData.enabled=true] - Enable schedule
     * @returns {Promise<Object>} Created schedule
     */
    async setDeviceSchedule(unitId, scheduleData) {
        const deviceType = scheduleData?.device_type;
        if (!deviceType) {
            throw new Error('device_type is required');
        }

        const enabled = scheduleData.enabled !== undefined ? scheduleData.enabled : true;
        const existing = await this.getSchedulesV3(unitId, { device_type: deviceType });
        const schedules = existing?.schedules || [];

        if (schedules.length) {
            const scheduleId = schedules[0].schedule_id;
            const updated = await this.updateScheduleV3(unitId, scheduleId, {
                start_time: scheduleData.start_time,
                end_time: scheduleData.end_time,
                enabled
            });
            return updated;
        }

        return this.createScheduleV3(unitId, {
            name: scheduleData.name || `${deviceType} Schedule`,
            device_type: deviceType,
            start_time: scheduleData.start_time,
            end_time: scheduleData.end_time,
            enabled
        });
    },

    /**
     * Delete device schedule (v3-backed)
     * @param {number} unitId - Unit ID
     * @param {string} deviceType - Device type
     * @returns {Promise<Object>} Deletion result
     */
    async deleteDeviceSchedule(unitId, deviceType) {
        const response = await this.getSchedulesV3(unitId, { device_type: deviceType });
        const schedules = response?.schedules || [];
        if (!schedules.length) {
            return { device_type: deviceType, message: "Schedule not found" };
        }

        return this.deleteScheduleV3(unitId, schedules[0].schedule_id);
    },

    /**
     * Get currently active devices (v3-backed)
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Active devices
     */
    getActiveDevices(unitId) {
        return this.getActiveSchedulesV3(unitId);
    },

    // ==========================================================================
    // V3 SCHEDULE API - Unified Schedule Management
    // ==========================================================================

    /**
     * Get all schedules for a unit (v3 API)
     * @param {number} unitId - Unit ID
     * @param {Object} [options] - Query options
     * @param {string} [options.device_type] - Filter by device type
     * @param {boolean} [options.enabled_only] - Only return enabled schedules
     * @returns {Promise<Object>} Schedules response
     */
    getSchedulesV3(unitId, options = {}) {
        const params = new URLSearchParams();
        if (options.device_type) params.append('device_type', options.device_type);
        if (options.enabled_only) params.append('enabled_only', 'true');
        const query = params.toString();
        return get(`/api/growth/v3/units/${unitId}/schedules${query ? '?' + query : ''}`);
    },

    /**
     * Get a specific schedule by ID (v3 API)
     * @param {number} unitId - Unit ID
     * @param {number} scheduleId - Schedule ID
     * @returns {Promise<Object>} Schedule response
     */
    getScheduleV3(unitId, scheduleId) {
        return get(`/api/growth/v3/units/${unitId}/schedules/${scheduleId}`);
    },

    /**
     * Create a new schedule (v3 API)
     * @param {number} unitId - Unit ID
     * @param {Object} scheduleData - Schedule data
     * @param {string} scheduleData.name - Schedule name
     * @param {string} scheduleData.device_type - Device type
     * @param {string} scheduleData.start_time - Start time (HH:MM)
     * @param {string} scheduleData.end_time - End time (HH:MM)
     * @param {string} [scheduleData.schedule_type] - Schedule type
     * @param {number[]} [scheduleData.days_of_week] - Days of week (0-6)
     * @param {boolean} [scheduleData.enabled] - Enable schedule
     * @param {number} [scheduleData.priority] - Priority level
     * @param {Object} [scheduleData.photoperiod] - Photoperiod config
     * @returns {Promise<Object>} Created schedule
     */
    createScheduleV3(unitId, scheduleData) {
        return post(`/api/growth/v3/units/${unitId}/schedules`, scheduleData);
    },

    /**
     * Update an existing schedule (v3 API)
     * @param {number} unitId - Unit ID
     * @param {number} scheduleId - Schedule ID
     * @param {Object} scheduleData - Updated schedule data
     * @returns {Promise<Object>} Updated schedule
     */
    updateScheduleV3(unitId, scheduleId, scheduleData) {
        return put(`/api/growth/v3/units/${unitId}/schedules/${scheduleId}`, scheduleData);
    },

    /**
     * Toggle schedule enabled state (v3 API)
     * @param {number} unitId - Unit ID
     * @param {number} scheduleId - Schedule ID
     * @param {boolean} enabled - New enabled state
     * @returns {Promise<Object>} Updated schedule
     */
    toggleScheduleV3(unitId, scheduleId, enabled) {
        return patch(`/api/growth/v3/units/${unitId}/schedules/${scheduleId}/enabled`, { enabled });
    },

    /**
     * Delete a schedule (v3 API)
     * @param {number} unitId - Unit ID
     * @param {number} scheduleId - Schedule ID
     * @returns {Promise<Object>} Deletion result
     */
    deleteScheduleV3(unitId, scheduleId) {
        return del(`/api/growth/v3/units/${unitId}/schedules/${scheduleId}`);
    },

    /**
     * Get currently active schedules (v3 API)
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Active schedules
     */
    getActiveSchedulesV3(unitId) {
        return get(`/api/growth/v3/units/${unitId}/schedules/active`);
    },

    /**
     * Get schedule summary for a unit (v3 API)
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Schedule summary
     */
    getScheduleSummaryV3(unitId) {
        return get(`/api/growth/v3/units/${unitId}/schedules/summary`);
    },

    /**
     * Preview upcoming schedule events (v3 API)
     * @param {number} unitId - Unit ID
     * @param {Object} [options] - Query options
     * @param {number} [options.hours] - Hours to preview (default 24)
     * @param {string} [options.device_type] - Filter by device type
     * @returns {Promise<Object>} Preview events
     */
    previewSchedulesV3(unitId, options = {}) {
        const params = new URLSearchParams();
        if (options.hours) params.append('hours', options.hours);
        if (options.device_type) params.append('device_type', options.device_type);
        const query = params.toString();
        return get(`/api/growth/v3/units/${unitId}/schedules/preview${query ? '?' + query : ''}`);
    },

    /**
     * Get schedule change history/audit log (v3 API)
     * @param {number} unitId - Unit ID
     * @param {Object} [options] - Query options
     * @param {number} [options.schedule_id] - Filter by schedule ID
     * @param {number} [options.limit] - Maximum records
     * @returns {Promise<Object>} History records
     */
    getScheduleHistoryV3(unitId, options = {}) {
        const params = new URLSearchParams();
        if (options.schedule_id) params.append('schedule_id', options.schedule_id);
        if (options.limit) params.append('limit', options.limit);
        const query = params.toString();
        return get(`/api/growth/v3/units/${unitId}/schedules/history${query ? '?' + query : ''}`);
    },

    /**
     * Get schedule execution log (v3 API)
     * @param {number} scheduleId - Schedule ID
     * @param {Object} [options] - Query options
     * @param {number} [options.limit] - Maximum records
     * @returns {Promise<Object>} Execution log
     */
    getScheduleExecutionLogV3(scheduleId, options = {}) {
        const params = new URLSearchParams();
        if (options.limit) params.append('limit', options.limit);
        const query = params.toString();
        return get(`/api/growth/v3/schedules/${scheduleId}/execution-log${query ? '?' + query : ''}`);
    },

    /**
     * Detect schedule conflicts for a unit (v3 API)
     * @param {number} unitId - Unit ID
     * @param {Object} [options] - Query options
     * @param {string} [options.device_type] - Filter by device type
     * @returns {Promise<Object>} Conflicts
     */
    detectScheduleConflictsV3(unitId, options = {}) {
        const params = new URLSearchParams();
        if (options.device_type) params.append('device_type', options.device_type);
        const query = params.toString();
        return get(`/api/growth/v3/units/${unitId}/schedules/conflicts${query ? '?' + query : ''}`);
    },

    /**
     * Auto-generate schedules from plant stage (v3 API)
     * Creates AUTOMATIC type schedules based on the active plant's growth stage.
     * @param {number} unitId - Unit ID
     * @param {Object} [options] - Options
     * @param {boolean} [options.replace_existing] - Replace existing auto schedules (default true)
     * @param {number} [options.plant_id] - Specific plant ID
     * @returns {Promise<Object>} Generated schedules
     */
    autoGenerateSchedulesV3(unitId, options = {}) {
        return post(`/api/growth/v3/units/${unitId}/schedules/auto-generate`, options);
    },

    /**
     * Get schedule templates for a unit (v3 API)
     * Returns recommended schedule configurations based on plant type/stage.
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Schedule templates
     */
    getScheduleTemplatesV3(unitId) {
        return get(`/api/growth/v3/units/${unitId}/schedules/templates`);
    },

    /**
     * Bulk update schedules (v3 API)
     * Enable or disable multiple schedules at once.
     * @param {number} unitId - Unit ID
     * @param {Object} data - Bulk update data
     * @param {number[]} data.schedule_ids - Schedule IDs to update
     * @param {boolean} data.enabled - Enable or disable
     * @returns {Promise<Object>} Update result
     */
    bulkUpdateSchedulesV3(unitId, data) {
        return post(`/api/growth/v3/units/${unitId}/schedules/bulk-update`, data);
    },

    /**
     * Start camera for a growth unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Camera status
     */
    startCamera(unitId) {
        return post(`/api/growth/units/${unitId}/camera/start`);
    },

    /**
     * Stop camera for a growth unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Camera status
     */
    stopCamera(unitId) {
        return post(`/api/growth/units/${unitId}/camera/stop`);
    },

    /**
     * Capture a photo with the growth unit camera
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Capture result
     */
    capturePhoto(unitId) {
        return post(`/api/growth/units/${unitId}/camera/capture`);
    },

    /**
     * Get camera status for a growth unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Camera status
     */
    getCameraStatus(unitId) {
        return get(`/api/growth/units/${unitId}/camera/status`);
    },

    /**
     * Update camera settings for a growth unit
     * @param {number} unitId - Unit ID
     * @param {Object} settings - Camera settings (camera_type, ip_address, stream_url, etc.)
     * @returns {Promise<Object>} Updated settings
     */
    updateCameraSettings(unitId, settings) {
        return put(`/api/growth/units/${unitId}/camera/settings`, settings);
    },

    /**
     * Get camera feed URL for a growth unit
     * @param {number} unitId - Unit ID
     * @returns {string} Camera feed URL
     */
    getCameraFeedUrl(unitId) {
        return `/api/growth/units/${unitId}/camera/feed`;
    }
};

// ============================================================================
// PLANTS API
// ============================================================================

const PlantAPI = {
    /**
     * Get health status for all plants
     * @returns {Promise<Object>} Plant health summary
     */
    getPlantHealth() {
        return get('/api/health/plants/summary');
    },

    /**
     * List plants. When `unitId` is provided, returns plants in that unit.
     * When omitted, returns overall plant health list/summary.
     * @param {number} [unitId]
     * @returns {Promise<Object>}
     */
    listPlants(unitId = null) {
        if (unitId !== null && unitId !== undefined) {
            return get(`/api/plants/units/${unitId}/plants`);
        }
        return get('/api/plants/health');
    },

    /**
     * List plants in a specific growth unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<{plants: Array, count: number}>}
     */
    listPlantsInUnit(unitId) {
        return get(`/api/plants/units/${unitId}/plants`);
    },

    /**
     * Get plant health history
     * @param {number} plantId
     * @param {number} days
     * @returns {Promise<Object>}
     */
    getHealthHistory(plantId, days = 30) {
        return get(`/api/plants/plants/${plantId}/health/history?days=${days}`);
    },

    /**
     * Add a new plant to a growth unit
     * @param {number} unitId - Unit ID
     * @param {Object} plantData - Plant data
     * @param {string} plantData.name - Plant name (required)
     * @param {string} plantData.plant_type - Plant type (required)
     * @param {string} plantData.current_stage - Growth stage (required)
     * @param {number} [plantData.days_in_stage=0] - Days in current stage
     * @returns {Promise<Object>} Created plant
     */
    addPlant(unitId, plantData) {
        return post(`/api/plants/units/${unitId}/plants`, plantData);
    },

    /**
     * Get a specific plant by ID
     * @param {number} plantId - Plant ID
     * @param {number|null} [unitId] - Optional unit ID (required by backend endpoint; inferred from body dataset when omitted)
     * @returns {Promise<Object>} Plant data
     */
    getPlantDetails(unitId, plantId) {
        if (unitId === null || unitId === undefined || unitId === '') {
            throw new Error('unitId is required to fetch plant details');
        }
        return get(`/api/plants/plants/${unitId}/${plantId}`);
    },

    getPlant(plantId, unitId = null) {
        const numericPlantId = Number(plantId);
        if (!Number.isFinite(numericPlantId) || numericPlantId <= 0) {
            throw new Error('plantId is required to fetch plant details');
        }

        let resolvedUnitId = unitId;
        if (resolvedUnitId === null || resolvedUnitId === undefined || resolvedUnitId === '') {
            const raw = typeof document !== 'undefined' ? document.body?.dataset?.activeUnitId : null;
            const parsed = raw !== null && raw !== '' ? parseInt(raw, 10) : null;
            resolvedUnitId = Number.isFinite(parsed) ? parsed : null;
        }

        const numericUnitId = Number(resolvedUnitId);
        if (Number.isFinite(numericUnitId) && numericUnitId > 0) {
            return this.getPlantDetails(numericUnitId, numericPlantId);
        }

        // Fallback: backend can resolve unit by plant id.
        return get(`/api/plants/plants/${numericPlantId}`);
    },

    /**
     * Update plant information
     * @param {number} plantId - Plant ID
     * @param {Object} updates - Fields to update
     * @param {string} [updates.name] - Plant name
     * @param {string} [updates.plant_type] - Plant type
     * @param {string} [updates.current_stage] - Growth stage
     * @param {number} [updates.days_in_stage] - Days in stage
     * @returns {Promise<Object>} Updated plant
     */
    updatePlant(plantId, updates) {
        return put(`/api/plants/plants/${plantId}`, updates);
    },

    /**
     * Remove a plant from a growth unit
     * @param {number} unitId - Unit ID
     * @param {number} plantId - Plant ID
     * @returns {Promise<Object>} Deletion result
     */
    removePlant(unitId, plantId) {
        return del(`/api/plants/units/${unitId}/plants/${plantId}`);
    },

    /**
     * Update plant growth stage
     * @param {number} plantId - Plant ID
     * @param {Object} stageData - Stage data
     * @param {string} stageData.stage - New stage name
     * @param {number} [stageData.days_in_stage=0] - Days in stage
     * @returns {Promise<Object>} Updated plant
     */
    updatePlantStage(plantId, stageData) {
        return put(`/api/plants/plants/${plantId}/stage`, stageData);
    },

    /**
     * Set active plant for climate control
     * @param {number} unitId - Unit ID
     * @param {number} plantId - Plant ID
     * @returns {Promise<Object>} Result
     */
    setActivePlant(unitId, plantId) {
        return post(`/api/plants/units/${unitId}/plants/${plantId}/active`);
    },

    // ============================================================================
    // PLANT-SENSOR LINKING
    // ============================================================================

    /**
     * Get available sensors that can be linked to plants
     * @param {number} unitId - Unit ID
     * @param {string} [sensorType='SOIL_MOISTURE'] - Sensor type filter
     * @returns {Promise<Object>} Available sensors
     */
    getAvailableSensors(unitId, sensorType = 'SOIL_MOISTURE') {
        return get(`/api/plants/units/${unitId}/sensors/available?sensor_type=${sensorType}`);
    },

    /**
     * Link plant to sensor
     * @param {number} plantId - Plant ID
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Link result
     */
    linkPlantToSensor(plantId, sensorId) {
        return post(`/api/plants/plants/${plantId}/sensors/${sensorId}`);
    },

    /**
     * Unlink plant from sensor
     * @param {number} plantId - Plant ID
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Unlink result
     */
    unlinkPlantFromSensor(plantId, sensorId) {
        return del(`/api/plants/plants/${plantId}/sensors/${sensorId}`);
    },

    /**
     * Get sensors linked to plant with full details
     * @param {number} plantId - Plant ID
     * @returns {Promise<Object>} Plant sensors with details
     */
    getPlantSensors(plantId) {
        return get(`/api/plants/plants/${plantId}/sensors`);
    },

    // ============================================================================
    // PLANT-ACTUATOR LINKING
    // ============================================================================

    /**
     * Get available actuators that can be linked to plants
     * @param {number} unitId - Unit ID
     * @param {string} [actuatorType='pump'] - Actuator type filter
     * @returns {Promise<Object>} Available actuators
     */
    getAvailableActuators(unitId, actuatorType = 'pump') {
        return get(`/api/plants/units/${unitId}/actuators/available?actuator_type=${actuatorType}`);
    },

    /**
     * Get actuators linked to a plant
     * @param {number} plantId - Plant ID
     * @returns {Promise<Object>} Plant actuators with details
     */
    getPlantActuators(plantId) {
        return get(`/api/plants/plants/${plantId}/actuators`);
    },

    /**
     * Link plant to actuator
     * @param {number} plantId - Plant ID
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Link result
     */
    linkPlantToActuator(plantId, actuatorId) {
        return post(`/api/plants/plants/${plantId}/actuators/${actuatorId}`);
    },

    /**
     * Unlink plant from actuator
     * @param {number} plantId - Plant ID
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Unlink result
     */
    unlinkPlantFromActuator(plantId, actuatorId) {
        return del(`/api/plants/plants/${plantId}/actuators/${actuatorId}`);
    },

    // ============================================================================
    // PLANT HEALTH MONITORING
    // ============================================================================

    /**
     * Record a plant health observation
     * @param {number} plantId - Plant ID
     * @param {Object} observation - Health observation data
     * @param {string} observation.health_status - Health status (healthy, stressed, diseased, pest_infestation, nutrient_deficiency, dying)
     * @param {Array<string>} observation.symptoms - List of symptoms
     * @param {string} [observation.disease_type] - Disease type (fungal, bacterial, viral, pest, nutrient_deficiency, environmental_stress)
     * @param {number} observation.severity_level - Severity level (1-5)
     * @param {Array<string>} observation.affected_parts - Affected plant parts
     * @param {string} [observation.treatment_applied] - Treatment applied
     * @param {string} observation.notes - Observation notes
     * @param {string} [observation.image_path] - Image path
     * @param {string} [observation.growth_stage] - Growth stage (auto-detected if not provided)
     * @returns {Promise<Object>} Recorded observation with correlations
     */
    recordHealthObservation(plantId, observation) {
        return post(`/api/plants/plants/${plantId}/health/record`, observation);
    },

    /**
     * Record a plant health observation with image (FormData)
     * @param {number} plantId - Plant ID
     * @param {FormData} formData - Form data including image file
     * @returns {Promise<Object>} Recorded observation
     */
    recordHealthObservationWithImage(plantId, formData) {
        return postFormData(`/api/plants/${plantId}/health/record`, formData);
    },

    /**
     * Record nutrient application (FormData)
     * @param {FormData} formData - Form data for nutrient record
     * @returns {Promise<Object>} Recorded nutrient entry
     */
    recordNutrients(formData) {
        return postFormData('/api/plants/journal/nutrients', formData);
    },

    /**
     * Get health observation history for a plant
     * @param {number} plantId - Plant ID
     * @param {number} [days=7] - Number of days of history
     * @returns {Promise<Object>} Health history
     */
    getHealthHistory(plantId, days = 7) {
        return get(`/api/plants/plants/${plantId}/health/history?days=${days}`);
    },

    /**
     * Get health recommendations for a plant
     * @param {number} plantId - Plant ID
     * @returns {Promise<Object>} Health recommendations
     */
    getHealthRecommendations(plantId) {
        return get(`/api/plants/plants/${plantId}/health/recommendations`);
    },

    // ============================================================================
    // HARVEST
    // ============================================================================

    /**
     * Harvest a plant
     * @param {number} plantId - Plant ID
     * @param {Object} harvestData - Harvest data
     * @returns {Promise<Object>} Harvest report
     */
    harvestPlant(plantId, harvestData) {
        return post(`/api/plants/${plantId}/harvest`, harvestData);
    },

    /**
     * Get all harvest reports
     * @returns {Promise<Array>} List of harvest reports
     */
    getHarvests() {
        return get('/api/harvests');
    },

    /**
     * Get a specific harvest report
     * @param {number} harvestId - Harvest ID
     * @returns {Promise<Object>} Harvest report
     */
    getHarvest(harvestId) {
        return get(`/api/harvests/${harvestId}`);
    },

    /**
     * Get list of available plant health symptoms
     * @returns {Promise<Object>} Available symptoms with causes
     */
    getAvailableSymptoms() {
        return get('/api/health/plants/symptoms');
    },

    /**
     * Get list of available health status values and disease types
     * @returns {Promise<Object>} Health statuses and disease types
     */
    getHealthStatuses() {
        return get('/api/health/plants/statuses');
    },

    /**
     * Get journal entries for all plants
     * @param {number} [days=30] - Number of days of history
     * @param {number} [plantId] - Filter by plant ID
     * @returns {Promise<Object>} Journal entries
     */
    getJournalEntries(days = 30, plantId = null) {
        const params = new URLSearchParams();
        if (days) params.append('days', days);
        if (plantId) params.append('plant_id', plantId);
        const query = params.toString();
        return get(`/api/plants/journal${query ? '?' + query : ''}`);
    },

    /**
     * Get health status for all plants
     * @returns {Promise<Object>} Plants health data
     */
    getPlantHealth() {
        return get('/api/plants/health');
    },

    /**
     * Get plants growing guide (basic info)
     * @returns {Promise<Object>} Plants guide from plants_info.json
     */
    getPlantsGuide() {
        return get('/api/plants/guide');
    },

    /**
     * Get full plants growing guide with all details
     * @returns {Promise<Object>} Full plants guide from plants_info.json
     */
    getPlantsGuideFull() {
        return get('/api/plants/guide/full');
    },

    /**
     * Get disease risk assessments
     * @param {number} [unitId] - Filter by unit ID
     * @param {string} [riskLevel] - Filter by risk level
     * @returns {Promise<Object>} Disease risks
     */
    getDiseaseRisks(unitId = null, riskLevel = null) {
        const params = new URLSearchParams();
        if (unitId) params.append('unit_id', unitId);
        if (riskLevel) params.append('risk_level', riskLevel);
        const query = params.toString();
        return get(`/api/ml/predictions/disease/risks${query ? '?' + query : ''}`);
    },

    // Plant Intelligence
    getWateringDecision(params = {}) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/plants/watering-decision${query ? '?' + query : ''}`);
    },

    getEnvironmentalAlerts(params = {}) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/plants/environmental-alerts${query ? '?' + query : ''}`);
    },

    getProblemDiagnosis(data) {
        return post('/api/plants/problem-diagnosis', data);
    },

    getYieldProjection(params = {}) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/plants/yield-projection${query ? '?' + query : ''}`);
    },

    getHarvestRecommendations(params = {}) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/plants/harvest-recommendations${query ? '?' + query : ''}`);
    },

    getLightingSchedule(params = {}) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/plants/lighting-schedule${query ? '?' + query : ''}`);
    },

    getAutomationStatus(params = {}) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/plants/automation-status${query ? '?' + query : ''}`);
    },

    getAvailablePlants() {
        return get('/api/plants/available-plants');
    },

    // ============================================================================
    // PLANT CATALOG
    // ============================================================================

    /**
     * Get plant catalog with all available plants
     * @returns {Promise<Array>} Plant catalog data
     */
    getCatalog() {
        return get('/api/plants/catalog');
    },

    /**
     * Save a custom plant to the catalog
     * @param {Object} plantData - Custom plant data
     * @returns {Promise<Object>} Saved plant
     */
    saveCustomPlant(plantData) {
        return post('/api/plants/catalog/custom', plantData);
    },

    /**
     * Record an AI health observation
     * @param {Object} observation - Health observation data
     * @returns {Promise<Object>} AI analysis result
     */
    recordAIHealthObservation(observation) {
        return post('/api/ml/predictions/health/observation', observation);
    }
};



// ============================================================================
// DEVICES API
// ============================================================================

const DeviceAPI = {
    // Sensors
    /**
     * Get all sensors across all units
     * @returns {Promise<{sensors: Array, count: number}>}
     */
    getAllSensors() {
        return get('/api/devices/v2/sensors');
    },

    /**
     * Get sensors for a specific unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<{sensors: Array, count: number}>}
     */
    getSensorsByUnit(unitId) {
        return get(`/api/devices/v2/sensors/unit/${unitId}`);
    },

    /**
     * Add sensor
     * @param {Object} sensorData - Sensor data
     * @returns {Promise<Object>} Created sensor
     */
    addSensor(sensorData) {
        return post('/api/devices/v2/sensors', sensorData);
    },

    /**
     * Resolve primary metric conflicts by unassigning metrics from sensors
     * @param {Object} payload - { unit_id, unassign: [{sensor_id, metrics}] }
     * @returns {Promise<Object>} Result
     */
    resolvePrimaryMetrics(payload) {
        return post('/api/devices/v2/sensors/primary-metrics/resolve', payload);
    },

    /**
     * Update primary metrics for a sensor
     * @param {number} sensorId - Sensor ID
     * @param {Object} payload - { primary_metrics: [...] }
     * @returns {Promise<Object>} Result
     */
    updateSensorPrimaryMetrics(sensorId, payload) {
        return patch(`/api/devices/v2/sensors/${sensorId}/primary-metrics`, payload);
    },

    /**
     * Update sensor details
     * @param {number} sensorId - Sensor ID
     * @param {Object} payload - Updates
     * @returns {Promise<Object>} Result
     */
    updateSensor(sensorId, payload) {
        return patch(`/api/devices/v2/sensors/${sensorId}`, payload);
    },

    /**
     * Delete sensor by ID
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Deletion result
     */
    deleteSensor(sensorId) {
        return del(`/api/devices/v2/sensors/${sensorId}`);
    },

    /**
     * Read sensor value
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Sensor reading
     */
    readSensor(sensorId) {
        return get(`/api/devices/sensors/${sensorId}/read`);
    },

    /**
     * Calibrate sensor
     * @param {number} sensorId - Sensor ID
     * @param {Object} calibrationData - Calibration data
     * @returns {Promise<Object>} Calibration result
     */
    calibrateSensor(sensorId, calibrationData) {
        return post(`/api/devices/sensors/${sensorId}/calibrate`, calibrationData);
    },

    /**
     * Get sensor health status
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Health status
     */
    getSensorHealth(sensorId) {
        return get(`/api/health/sensors/${sensorId}`);
    },

    /**
     * Get sensor anomalies
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Anomalies
     */
    getSensorAnomalies(sensorId) {
        return get(`/api/devices/sensors/${sensorId}/anomalies`);
    },

    /**
     * Get sensor statistics
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Statistics
     */
    getSensorStatistics(sensorId) {
        return get(`/api/devices/sensors/${sensorId}/statistics`);
    },

    /**
     * Get sensor calibration history
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Calibration history
     */
    getSensorCalibrationHistory(sensorId) {
        return get(`/api/devices/sensors/${sensorId}/history/calibration`);
    },

    /**
     * Get sensor health history
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Health history
     */
    getSensorHealthHistory(sensorId) {
        return get(`/api/devices/sensors/${sensorId}/history/health`);
    },

    /**
     * Get sensor anomaly history
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Anomaly history
     */
    getSensorAnomalyHistory(sensorId) {
        return get(`/api/devices/sensors/${sensorId}/history/anomalies`);
    },

    /**
     * Discover sensors
     * @param {Object} searchData - Search parameters
     * @returns {Promise<Object>} Discovered sensors
     */
    discoverSensors(searchData) {
        return post('/api/devices/sensors/discover', searchData);
    },

    /**
     * Discover Zigbee devices
     * @returns {Promise<Object>} Discovered devices
     */
    discoverZigbee() {
        return get('/api/devices/v2/zigbee2mqtt/discover');
    },

    // Actuators
    /**
     * Get all actuators across all units
     * @returns {Promise<{actuators: Array, count: number}>}
     */
    getAllActuators() {
        return get('/api/devices/v2/actuators');
    },

    /**
     * Get actuators for a specific unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<{actuators: Array, count: number}>}
     */
    getActuatorsByUnit(unitId) {
        return get(`/api/devices/v2/actuators/unit/${unitId}`);
    },

    /**
     * Add actuator
     * @param {Object} actuatorData - Actuator data
     * @returns {Promise<Object>} Created actuator
     */
    addActuator(actuatorData) {
        return post('/api/devices/v2/actuators', actuatorData);
    },

    /**
     * Delete actuator by ID
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Deletion result
     */
    deleteActuator(actuatorId) {
        return del(`/api/devices/v2/actuators/${actuatorId}`);
    },

    /**
     * Get sensors and actuators for a unit (aggregated from v2 endpoints)
     * @param {number} unitId - Unit ID
     * @returns {Promise<{sensors: Array, actuators: Array}>}
     */
    async getDevicesByUnit(unitId) {
        const [sensors, actuators] = await Promise.all([
            this.getSensorsByUnit(unitId),
            this.getActuatorsByUnit(unitId),
        ]);
        return {
            sensors: sensors?.data || sensors || [],
            actuators: actuators?.data || actuators || [],
        };
    },

    /**
     * Control actuator
     * @param {Object} controlData - {actuator_id: number, state: string, duration?: number}
     * @returns {Promise<Object>} Control result
     */
    controlActuator(controlData) {
        return post('/api/devices/control_actuator', controlData);
    },

    /**
     * Toggle actuator state (ON/OFF)
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Toggle result
     */
    toggleActuator(actuatorId) {
        return post(`/api/devices/actuators/${actuatorId}/toggle`);
    },

    /**
     * Get actuator power consumption
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Power data
     */
    getActuatorPower(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/power`);
    },

    /**
     * Get actuator energy consumption
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Energy data
     */
    getActuatorEnergy(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/energy`);
    },

    /**
     * Get actuator cost analysis
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Cost data
     */
    getActuatorCost(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/cost`);
    },

    /**
     * Get actuator health status
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Health status
     */
    getActuatorHealth(actuatorId) {
        return get(`/api/health/actuators/${actuatorId}`);
    },

    /**
     * Record actuator health check
     * @param {number} actuatorId - Actuator ID
     * @param {Object} healthData - Health data
     * @returns {Promise<Object>} Result
     */
    recordActuatorHealth(actuatorId, healthData) {
        return post(`/api/health/actuators/${actuatorId}`, healthData);
    },

    /**
     * Get actuator anomalies
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Anomalies
     */
    getActuatorAnomalies(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/anomalies`);
    },

    /**
     * Report actuator anomaly
     * @param {number} actuatorId - Actuator ID
     * @param {Object} anomalyData - Anomaly data
     * @returns {Promise<Object>} Result
     */
    reportActuatorAnomaly(actuatorId, anomalyData) {
        return post(`/api/devices/actuators/${actuatorId}/anomalies`, anomalyData);
    },

    /**
     * Resolve actuator anomaly
     * @param {number} anomalyId - Anomaly ID
     * @param {Object} resolutionData - Resolution data
     * @returns {Promise<Object>} Result
     */
    resolveActuatorAnomaly(anomalyId, resolutionData) {
        return patch(`/api/devices/actuators/anomalies/${anomalyId}/resolve`, resolutionData);
    },

    /**
     * Get actuator power readings
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Power readings
     */
    getActuatorPowerReadings(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/power-readings`);
    },

    /**
     * Record actuator power reading
     * @param {number} actuatorId - Actuator ID
     * @param {Object} readingData - Power reading data
     * @returns {Promise<Object>} Result
     */
    recordActuatorPowerReading(actuatorId, readingData) {
        return post(`/api/devices/actuators/${actuatorId}/power-readings`, readingData);
    },

    /**
     * Get actuator calibrations
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Calibration data
     */
    getActuatorCalibrations(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/calibrations`);
    },

    /**
     * Record actuator calibration
     * @param {number} actuatorId - Actuator ID
     * @param {Object} calibrationData - Calibration data
     * @returns {Promise<Object>} Result
     */
    recordActuatorCalibration(actuatorId, calibrationData) {
        return post(`/api/devices/actuators/${actuatorId}/calibrations`, calibrationData);
    },

    /**
     * Get actuator energy cost trends
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Cost trends
     */
    getActuatorCostTrends(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/energy/cost-trends`);
    },

    /**
     * Get actuator energy recommendations
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Recommendations
     */
    getActuatorEnergyRecommendations(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/energy/recommendations`);
    },

    /**
     * Get actuator energy anomalies
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Energy anomalies
     */
    getActuatorEnergyAnomalies(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/energy/anomalies`);
    },

    /**
     * Get actuator energy dashboard
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Energy dashboard data
     */
    getActuatorEnergyDashboard(actuatorId) {
        return get(`/api/devices/actuators/${actuatorId}/energy/dashboard`);
    },

    /**
     * Get actuator analytics dashboard
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Analytics dashboard
     */
    getActuatorAnalyticsDashboard(actuatorId) {
        return get(`/api/devices/analytics/actuators/${actuatorId}/dashboard`);
    },

    /**
     * Predict actuator failure
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Failure prediction
     */
    predictActuatorFailure(actuatorId) {
        return get(`/api/devices/analytics/actuators/${actuatorId}/predict-failure`);
    },

    /**
     * Get batch failure predictions
     * @returns {Promise<Object>} All failure predictions
     */
    getBatchFailurePredictions() {
        return get('/api/devices/analytics/actuators/predict-failures');
    },

    /**
     * Get total power consumption
     * @returns {Promise<Object>} Total power data
     */
    getTotalPower() {
        return get('/api/devices/actuators/total-power');
    },

    /**
     * Get comparative energy analysis
     * @returns {Promise<Object>} Energy comparison
     */
    getComparativeEnergyAnalysis() {
        return get('/api/devices/actuators/energy/comparative-analysis');
    },

    /**
     * Get all devices for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} All devices
     */
    getAllDevicesForUnit(unitId) {
        return get(`/api/devices/all/unit/${unitId}`);
    },

    // Zigbee2MQTT Integration
    /**
     * Get all Zigbee2MQTT devices
     * @returns {Promise<Object>} Zigbee devices
     */
    getZigbeeDevices() {
        return get('/api/devices/zigbee2mqtt/devices');
    },

    /**
     * Get Zigbee devices for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Zigbee devices
     */
    getZigbeeDevicesByUnit(unitId) {
        return get(`/api/devices/zigbee2mqtt/devices/unit/${unitId}`);
    },

    /**
     * Send Zigbee2MQTT command
     * @param {Object} commandData - Command data
     * @returns {Promise<Object>} Command result
     */
    sendZigbeeCommand(commandData) {
        return post('/api/devices/zigbee2mqtt/command', commandData);
    },

    /**
     * Get Zigbee2MQTT bridge status
     * @returns {Promise<Object>} Bridge status including online state and device count
     */
    getZigbeeBridgeStatus() {
        return get('/api/devices/v2/zigbee2mqtt/bridge/status');
    },

    /**
     * Enable permit join to allow new Zigbee devices to join
     * @param {number} duration - Duration in seconds (0-254, 0 = disable)
     * @returns {Promise<Object>} Permit join result
     */
    permitZigbeeJoin(duration = 254) {
        return post('/api/devices/v2/zigbee2mqtt/permit-join', { duration });
    },

    /**
     * Force rediscovery of all Zigbee devices
     * @returns {Promise<Object>} Rediscovery result
     */
    forceZigbeeRediscovery() {
        return post('/api/devices/v2/zigbee2mqtt/rediscover', {});
    },

    /**
     * Get a specific Zigbee device by IEEE address
     * @param {string} ieeeAddress - Device IEEE address
     * @returns {Promise<Object>} Device details and state
     */
    getZigbeeDevice(ieeeAddress) {
        return get(`/api/devices/v2/zigbee2mqtt/devices/${encodeURIComponent(ieeeAddress)}`);
    },

    /**
     * Get current state of a Zigbee device
     * @param {string} ieeeAddress - Device IEEE address
     * @returns {Promise<Object>} Device state
     */
    getZigbeeDeviceState(ieeeAddress) {
        return get(`/api/devices/v2/zigbee2mqtt/devices/${encodeURIComponent(ieeeAddress)}/state`);
    },

    /**
     * Rename a Zigbee device
     * @param {string} ieeeAddress - Device IEEE address
     * @param {string} newName - New friendly name
     * @returns {Promise<Object>} Rename result
     */
    renameZigbeeDevice(ieeeAddress, newName) {
        return post(`/api/devices/v2/zigbee2mqtt/devices/${encodeURIComponent(ieeeAddress)}/rename`, { new_name: newName });
    },

    /**
     * Remove a Zigbee device from the network
     * @param {string} ieeeAddress - Device IEEE address
     * @returns {Promise<Object>} Removal result
     */
    removeZigbeeDevice(ieeeAddress) {
        return del(`/api/devices/v2/zigbee2mqtt/devices/${encodeURIComponent(ieeeAddress)}`);
    },

    /**
     * Get only Zigbee sensor devices
     * @returns {Promise<Object>} Zigbee sensors
     */
    getZigbeeSensors() {
        return get('/api/devices/v2/zigbee2mqtt/sensors');
    },

    /**
     * Get only Zigbee actuator devices
     * @returns {Promise<Object>} Zigbee actuators
     */
    getZigbeeActuators() {
        return get('/api/devices/v2/zigbee2mqtt/actuators');
    },

    // Configuration
    /**
     * Get available GPIO pins
     * @returns {Promise<Object>} GPIO pins
     */
    getGPIOPins() {
        return get('/api/devices/config/gpio_pins');
    },

    /**
     * Get available ADC channels
     * @returns {Promise<Object>} ADC channels
     */
    getADCChannels() {
        return get('/api/devices/config/adc_channels');
    },

    /**
     * Get sensor types
     * @returns {Promise<Object>} Sensor types
     */
    getSensorTypes() {
        return get('/api/devices/config/sensor_types');
    },

    /**
     * Get actuator types
     * @returns {Promise<Object>} Actuator types
     */
    getActuatorTypes() {
        return get('/api/devices/config/actuator_types');
    },

    // Device Discovery
    /**
     * Discover MQTT sensors on a unit
     * @param {number} unitId - Unit ID
     * @param {string} topicPrefix - MQTT topic prefix (default: 'growtent')
     * @returns {Promise<Array>} Discovered sensors
     */
    discoverMQTTSensors(unitId, topicPrefix = 'growtent') {
        return get(`/api/devices/sensors/discover-mqtt?unit_id=${unitId}&topic_prefix=${topicPrefix}`);
    },

    // ============================================================================
    // SENSOR CALIBRATION
    // ============================================================================

    /**
     * Get Zigbee sensor calibration offsets
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Calibration offsets
     */
    getZigbeeCalibration(sensorId) {
        return get(`/api/devices/sensors/${sensorId}/zigbee2mqtt/calibration`);
    },

    /**
     * Set Zigbee sensor calibration offset
     * @param {number} sensorId - Sensor ID
     * @param {string} sensorType - Type of sensor measurement
     * @param {number} offset - Calibration offset value
     * @returns {Promise<Object>} Updated calibration
     */
    setZigbeeCalibration(sensorId, sensorType, offset) {
        return post(`/api/devices/sensors/${sensorId}/zigbee2mqtt/calibration`, {
            sensor_type: sensorType,
            offset: offset
        });
    },

    // ============================================================================
    // MQTT BROKER MANAGEMENT
    // ============================================================================

    /**
     * Configure MQTT broker settings
     * @param {Object} brokerConfig - Broker configuration
     * @returns {Promise<Object>} Configuration result
     */
    configureMQTTBroker(brokerConfig) {
        return post('/api/mqtt/broker/config', brokerConfig);
    },

    /**
     * Test MQTT connection
     * @returns {Promise<Object>} Connection test result
     */
    testMQTTConnection() {
        return post('/api/mqtt/test-connection', {});
    },

    /**
     * Discover MQTT devices
     * @returns {Promise<Object>} Discovered devices
     */
    discoverMQTTDevices() {
        return post('/api/mqtt/devices/discover', {});
    },

    /**
     * Add MQTT device
     * @param {Object} deviceData - Device configuration
     * @returns {Promise<Object>} Added device
     */
    addMQTTDevice(deviceData) {
        return post('/api/mqtt/devices/add', deviceData);
    },

    /**
     * Add MQTT sensor
     * @param {Object} sensorData - Sensor configuration
     * @returns {Promise<Object>} Added sensor
     */
    addMQTTSensor(sensorData) {
        return post('/api/mqtt/sensors/add', sensorData);
    },

    /**
     * Add MQTT actuator
     * @param {Object} actuatorData - Actuator configuration
     * @returns {Promise<Object>} Added actuator
     */
    addMQTTActuator(actuatorData) {
        return post('/api/mqtt/actuators/add', actuatorData);
    },

    /**
     * Get all MQTT devices
     * @returns {Promise<Object>} All MQTT devices
     */
    getMQTTDevices() {
        return get('/api/mqtt/devices/all');
    }
};

// ============================================================================
// INSIGHTS API (Legacy - delegates to Analytics/Health/Dashboard APIs)
// ============================================================================

const InsightsAPI = {
    /**
     * Get health metrics for a specific unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Unit health metrics
     */
    getUnitHealth(unitId) {
        return get(`/api/health/units/${unitId}`);
    },

    /**
     * Get unit health metrics (alias for getUnitHealth)
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Unit health metrics
     */
    getUnitHealthMetrics(unitId) {
        return get(`/api/health/units/${unitId}`);
    },

    // Energy Analytics - Delegated to /api/analytics
    /**
     * Get actuator energy dashboard
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Energy dashboard with costs, trends, and recommendations
     */
    getActuatorEnergyDashboard(actuatorId) {
        return get(`/api/analytics/actuators/${actuatorId}/dashboard`);
    },

    /**
     * Predict actuator failure
     * @param {number} actuatorId - Actuator ID
     * @param {number} [daysAhead=7] - Days to predict ahead
     * @returns {Promise<Object>} Failure prediction with risk score
     */
    predictActuatorFailure(actuatorId, daysAhead = 7) {
        return get(`/api/analytics/actuators/${actuatorId}/predict-failure?days_ahead=${daysAhead}`);
    },

    /**
     * Get actuator cost trends
     * @param {number} actuatorId - Actuator ID
     * @param {number} [days=7] - Number of days
     * @returns {Promise<Object>} Cost trends and analysis
     */
    getActuatorCostTrends(actuatorId, days = 7) {
        return get(`/api/analytics/actuators/${actuatorId}/energy-costs?days=${days}`);
    },

    /**
     * Get actuator optimization recommendations
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Optimization recommendations
     */
    getActuatorRecommendations(actuatorId) {
        return get(`/api/analytics/actuators/${actuatorId}/recommendations`);
    },

    /**
     * Get actuator power anomalies
     * @param {number} actuatorId - Actuator ID
     * @param {number} [hours=24] - Hours to analyze
     * @returns {Promise<Object>} Detected anomalies
     */
    getActuatorAnomalies(actuatorId, hours = 24) {
        return get(`/api/analytics/actuators/${actuatorId}/anomalies?hours=${hours}`);
    },

    /**
     * Get unit energy comparison
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Comparative energy analysis
     */
    getUnitEnergyComparison(unitId) {
        return get(`/api/analytics/units/${unitId}/comparison`);
    },

    /**
     * Get batch failure predictions
     * @param {number} [unitId] - Optional unit ID filter
     * @param {number} [threshold=0.5] - Minimum risk score
     * @param {number} [daysAhead=7] - Prediction window
     * @returns {Promise<Object>} Batch failure predictions
     */
    getBatchFailurePredictions(unitId, threshold = 0.5, daysAhead = 7) {
        const params = new URLSearchParams();
        if (unitId) params.append('unit_id', unitId);
        params.append('threshold', threshold);
        params.append('days_ahead', daysAhead);
        return get(`/api/analytics/batch/failure-predictions?${params}`);
    },

    // Sensor Analytics - Delegated to /api/analytics
    /**
     * Get latest sensor reading
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Latest reading
     */
    getLatestSensorReading(sensorId) {
        return get(`/api/analytics/sensors/overview?sensor_id=${sensorId}`);
    },

    /**
     * Get sensor history
     * @param {number} sensorId - Sensor ID
     * @param {number} [hours=24] - Hours of history
     * @param {number} [limit=100] - Max readings
     * @returns {Promise<Object>} Sensor readings history
     */
    getSensorHistory(sensorId, hours = 24, limit = 100) {
        return get(`/api/analytics/sensors/history?sensor_id=${sensorId}&hours=${hours}&limit=${limit}`);
    },

    /**
     * Get sensor statistics
     * @param {number} sensorId - Sensor ID
     * @param {number} [hours=24] - Hours to analyze
     * @returns {Promise<Object>} Statistical analysis
     */
    getSensorStatistics(sensorId, hours = 24) {
        return get(`/api/analytics/sensors/statistics?sensor_id=${sensorId}&hours=${hours}`);
    },

    // Dashboard Overviews - Delegated to /api/dashboard
    /**
     * Get system-wide dashboard overview
     * @returns {Promise<Object>} Comprehensive system overview
     */
    getDashboardOverview() {
        return get('/api/dashboard/summary');
    },

    /**
     * Get energy summary
     * @param {number} [days=7] - Days to analyze
     * @returns {Promise<Object>} System-wide energy summary
     */
    getEnergySummary(days = 7) {
        return get(`/api/analytics/dashboard/energy-summary?days=${days}`);
    },

    /**
     * Get health summary
     * @returns {Promise<Object>} System-wide health summary
     */
    getHealthSummary() {
        return get('/api/health/system');
    },

    /**
     * Health check for insights API
     * @returns {Promise<Object>} API health status
     */
    healthCheck() {
        return get('/api/health/ml');
    },

    /**
     * Get system statistics
     * @returns {Promise<Object>} System statistics including devices, plants, alerts
     */
    getSystemStats() {
        return get('/api/dashboard/summary');
    },

    /**
     * Get energy statistics for dashboard
     * @param {Object} [params] - Query parameters
     * @param {number} [params.unit_id] - Optional unit filter
     * @param {number} [params.days=7] - Days to analyze
     * @returns {Promise<Object>} Energy stats with costs
     */
    getEnergyStats(params = {}) {
        const query = new URLSearchParams();
        if (params.unit_id) query.append('unit_id', params.unit_id);
        if (params.days) query.append('days', params.days);
        const queryStr = query.toString();
        return get(`/api/analytics/dashboard/energy-summary${queryStr ? '?' + queryStr : ''}`);
    },

    /**
     * Get energy predictions
     * @param {Object} [params] - Query parameters
     * @returns {Promise<Object>} Energy predictions
     */
    getEnergyPredictions(params = {}) {
        const query = new URLSearchParams();
        if (params.unit_id) query.append('unit_id', params.unit_id);
        if (params.days) query.append('days', params.days || 7);
        const queryStr = query.toString();
        return get(`/api/analytics/dashboard/energy-summary${queryStr ? '?' + queryStr : ''}`);
    },

    /**
     * Get activity log
     * @param {Object} [params] - Query parameters
     * @param {number} [params.limit=10] - Maximum number of activities to return
     * @returns {Promise<Object>} Recent activity log
     */
    getActivityLog(params = {}) {
        const limit = params.limit || 10;
        return get(`/api/dashboard/summary?limit=${limit}`);
    },

    /**
     * Get alerts
     * @param {Object} [params] - Query parameters
     * @param {string} [params.severity] - Filter by severity (critical, high, medium, low)
     * @param {number} [params.limit=10] - Maximum number of alerts to return
     * @returns {Promise<Object>} System alerts
     */
    getAlerts(params = {}) {
        const queryParams = new URLSearchParams();
        if (params.severity) queryParams.append('severity', params.severity);
        if (params.limit) queryParams.append('limit', params.limit);
        const queryString = queryParams.toString();
        return get(`/api/dashboard/summary${queryString ? '?' + queryString : ''}`);
    },

    /**
     * Get system info
     * @returns {Promise<Object>} System health score and metrics
     */
    getSystemInfo() {
        return get('/api/health/infrastructure');
    }
};

// ============================================================================
// ANALYTICS API (NEW - Unified Analytics Endpoints)
// ============================================================================

const AnalyticsAPI = {
    // ==================== Sensor Analytics ====================
    
    /**
     * Get overview of all sensor readings across units
     * @param {number} [unitId] - Optional unit filter
     * @returns {Promise<Object>} Sensors overview with latest readings
     */
    getSensorsOverview(unitId = null) {
        const params = unitId ? `?unit_id=${unitId}` : '';
        return get(`/api/analytics/sensors/overview${params}`);
    },

    /**
     * Get historical sensor readings for time-series charts
     * @param {Object} options - Query options
     * @param {string} [options.start] - Start datetime (ISO 8601)
     * @param {string} [options.end] - End datetime (ISO 8601)
     * @param {number} [options.unit_id] - Optional unit filter
     * @param {number} [options.sensor_id] - Optional sensor filter
     * @param {number} [options.limit=500] - Max readings
     * @param {string} [options.interval] - Aggregation interval ('1h', '6h', '1d')
     * @returns {Promise<Object>} Time-series data formatted for charts
     */
    getSensorsHistory(options = {}) {
        const params = new URLSearchParams();
        if (options.start) params.append('start', options.start);
        if (options.end) params.append('end', options.end);
        if (options.unit_id) params.append('unit_id', options.unit_id);
        if (options.sensor_id) params.append('sensor_id', options.sensor_id);
        if (options.limit) params.append('limit', options.limit);
        if (options.interval) params.append('interval', options.interval);
        if (options.hours) params.append('hours', options.hours);
        if (options.days) params.append('days', options.days);
        return get(`/api/analytics/sensors/history?${params}`);
    },

    /**
     * Get enriched historical sensor readings with photoperiod and day/night overlays
     * @param {Object} options - Query options
     * @param {number} [options.unit_id] - Optional unit filter
     * @param {number} [options.hours=24] - Hours of history
     * @returns {Promise<Object>} Enriched time-series data
     */
    getSensorsHistoryEnriched(options = {}) {
        const params = new URLSearchParams();
        if (options.unit_id) params.append('unit_id', options.unit_id);
        if (options.hours) params.append('hours', options.hours);
        return get(`/api/analytics/sensors/history/enriched?${params}`);
    },

    /**
     * Get statistical analysis of sensor data
     * @param {Object} options - Query options
     * @param {number} [options.hours=24] - Hours to analyze
     * @param {number} [options.unit_id] - Optional unit filter
     * @param {number} [options.sensor_id] - Optional sensor filter
     * @returns {Promise<Object>} Statistical analysis (min, max, avg, std dev, etc.)
     */
    getSensorsStatistics(options = {}) {
        const params = new URLSearchParams();
        if (options.hours) params.append('hours', options.hours);
        if (options.unit_id) params.append('unit_id', options.unit_id);
        if (options.sensor_id) params.append('sensor_id', options.sensor_id);
        return get(`/api/analytics/sensors/statistics?${params}`);
    },

    /**
     * Get environmental trend analysis
     * @param {Object} options - Query options
     * @param {number} [options.days=7] - Days to analyze
     * @param {number} [options.unit_id] - Optional unit filter
     * @returns {Promise<Object>} Trends (stable, rising, falling, volatile)
     */
    getSensorsTrends(options = {}) {
        const params = new URLSearchParams();
        if (options.days) params.append('days', options.days);
        if (options.unit_id) params.append('unit_id', options.unit_id);
        return get(`/api/analytics/sensors/trends?${params}`);
    },

    /**
     * Get correlation analysis between environmental factors
     * @param {Object} options - Query options
     * @param {number} [options.days=7] - Days to analyze
     * @param {number} [options.hours] - Hours to analyze (alternative to days)
     * @param {number} [options.unit_id] - Optional unit filter
     * @param {number} [options.threshold] - Correlation threshold
     * @param {string} [options.metrics] - Comma-separated metrics
     * @returns {Promise<Object>} Correlations, VPD analysis, stress indicators
     */
    getSensorsCorrelations(options = {}) {
        const params = new URLSearchParams();
        if (options.days) params.append('days', options.days);
        if (options.hours) params.append('hours', options.hours);
        if (options.unit_id) params.append('unit_id', options.unit_id);
        if (options.threshold) params.append('threshold', options.threshold);
        if (options.metrics) params.append('metrics', options.metrics);
        return get(`/api/analytics/sensors/correlations?${params}`);
    },

    /**
     * Get anomaly detection results for sensors
     * @param {Object} options - Query options
     * @param {number} [options.hours=24] - Hours to analyze
     * @param {number} [options.unit_id] - Optional unit filter
     * @param {string} [options.sensor_ids] - Comma-separated sensor IDs
     * @returns {Promise<Object>} Detected anomalies
     */
    getSensorsAnomalies(options = {}) {
        const params = new URLSearchParams();
        if (options.hours) params.append('hours', options.hours);
        if (options.unit_id) params.append('unit_id', options.unit_id);
        if (options.sensor_ids) params.append('sensor_ids', options.sensor_ids);
        return get(`/api/analytics/sensors/anomalies?${params}`);
    },

    // ==================== Actuator Energy Analytics ====================

    /**
     * Get overview of all actuators and their current state
     * @param {number} [unitId] - Optional unit filter
     * @returns {Promise<Object>} Actuators overview with analytics
     */
    getActuatorsOverview(unitId = null) {
        const params = unitId ? `?unit_id=${unitId}` : '';
        return get(`/api/analytics/actuators/overview${params}`);
    },

    /**
     * Get comprehensive energy dashboard for an actuator
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Complete dashboard (status, costs, recommendations, anomalies)
     */
    getActuatorDashboard(actuatorId) {
        return get(`/api/analytics/actuators/${actuatorId}/dashboard`);
    },

    /**
     * Get detailed energy cost breakdown and trends
     * @param {number} actuatorId - Actuator ID
     * @param {number} [days=7] - Days to analyze
     * @returns {Promise<Object>} Daily cost breakdown and trends
     */
    getActuatorEnergyCosts(actuatorId, days = 7) {
        return get(`/api/analytics/actuators/${actuatorId}/energy-costs?days=${days}`);
    },

    /**
     * Get energy optimization recommendations
     * @param {number} actuatorId - Actuator ID
     * @returns {Promise<Object>} Actionable recommendations with savings estimates
     */
    getActuatorRecommendations(actuatorId) {
        return get(`/api/analytics/actuators/${actuatorId}/recommendations`);
    },

    /**
     * Detect power consumption anomalies
     * @param {number} actuatorId - Actuator ID
     * @param {number} [hours=24] - Hours to analyze
     * @returns {Promise<Object>} Detected anomalies (spikes, drops, unusual patterns)
     */
    getActuatorAnomalies(actuatorId, hours = 24) {
        return get(`/api/analytics/actuators/${actuatorId}/anomalies?hours=${hours}`);
    },

    /**
     * Predict device failure risk
     * @param {number} actuatorId - Actuator ID
     * @param {number} [daysAhead=7] - Prediction window (1-30)
     * @returns {Promise<Object>} Risk score, level, factors, recommendation
     */
    predictActuatorFailure(actuatorId, daysAhead = 7) {
        return get(`/api/analytics/actuators/${actuatorId}/predict-failure?days_ahead=${daysAhead}`);
    },

    // ==================== Comparative Analytics ====================

    /**
     * Get comparative analysis across all devices in a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Comparison, rankings, top consumers
     */
    getUnitComparison(unitId) {
        return get(`/api/analytics/units/${unitId}/comparison`);
    },

    /**
     * Compare environmental conditions and energy across all units
     * @returns {Promise<Object>} Multi-unit comparison with performance metrics
     */
    getMultiUnitComparison() {
        return get('/api/analytics/units/comparison');
    },

    // ==================== Batch Operations ====================

    /**
     * Get failure predictions for all or filtered actuators
     * @param {Object} options - Query options
     * @param {number} [options.unit_id] - Optional unit filter
     * @param {number} [options.threshold=0.0] - Minimum risk score (0.0-1.0)
     * @param {string} [options.risk_level] - Filter by level (low, medium, high, critical)
     * @returns {Promise<Object>} Batch predictions sorted by risk
     */
    getBatchFailurePredictions(options = {}) {
        const params = new URLSearchParams();
        if (options.unit_id) params.append('unit_id', options.unit_id);
        if (options.threshold !== undefined) params.append('threshold', options.threshold);
        if (options.risk_level) params.append('risk_level', options.risk_level);
        return get(`/api/analytics/batch/failure-predictions?${params}`);
    },

    // ==================== Dashboard Summaries ====================

    /**
     * Get environmental conditions summary for dashboard cards
     * @param {number} [unitId] - Optional unit filter
     * @returns {Promise<Object>} Current conditions, 24h averages, trends, alerts
     */
    getEnvironmentalSummary(unitId = null) {
        const params = unitId ? `?unit_id=${unitId}` : '';
        return get(`/api/analytics/dashboard/environmental-summary${params}`);
    },

    /**
     * Get energy consumption summary for dashboard cards
     * @param {Object} options - Query options
     * @param {number} [options.unit_id] - Optional unit filter
     * @param {number} [options.days=7] - Days to analyze
     * @returns {Promise<Object>} Total cost, top consumers, trends
     */
    getEnergySummary(options = {}) {
        const params = new URLSearchParams();
        if (options.unit_id) params.append('unit_id', options.unit_id);
        if (options.days) params.append('days', options.days);
        return get(`/api/analytics/dashboard/energy-summary?${params}`);
    },

    /**
     * Get system efficiency score
     * @param {Object} options - Query options
     * @param {number} [options.unit_id] - Optional unit filter
     * @returns {Promise<Object>} Efficiency score with components and suggestions
     */
    getEfficiencyScore(options = {}) {
        const params = new URLSearchParams();
        if (options.unit_id) params.append('unit_id', options.unit_id);
        return get(`/api/analytics/efficiency-score?${params}`);
    }
};

// ============================================================================
// HEALTH API
// ============================================================================

const HealthAPI = {
    /**
     * Get overall system health with all units
     * @returns {Promise<Object>} System health with status, units, and summary
     */
    getSystemHealth() {
        return get('/api/health/system');
    },
    
    /**
     * Get health summary for all units
     * @returns {Promise<Object>} Units health summary
     */
    getUnitsHealth() {
        return get('/api/health/units');
    },
    
    /**
     * Get detailed health for specific unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Unit health details
     */
    getUnitHealth(unitId) {
        return get(`/api/health/units/${unitId}`);
    },
    
    /**
     * Get aggregated device health across all units
     * @returns {Promise<Object>} Device health with sensor/actuator counts
     */
    getDevicesHealth() {
        return get('/api/health/devices');
    },
    
    /**
     * Get health for a specific sensor
     * @param {number} sensorId - Sensor ID
     * @returns {Promise<Object>} Sensor health details
     */
    getSensorHealth(sensorId) {
        return get(`/api/health/sensors/${sensorId}`);
    },
    
    /**
     * Basic liveness check
     * @returns {Promise<Object>} Ping response with timestamp
     */
    ping() {
        return get('/api/health/ping');
    },

    /**
     * Get detailed system health information
     * @returns {Promise<Object>} Detailed health data including components and metrics
     */
    getDetailed() {
        return get('/api/health/detailed');
    },

    /**
     * Get infrastructure status (API, DB, MQTT, ML, Zigbee)
     * @returns {Promise<Object>} Infrastructure component statuses
     */
    getInfrastructure() {
        return get('/api/health/infrastructure');
    },

    /**
     * Get storage/disk usage information
     * @returns {Promise<Object>} Storage metrics (total, used, free)
     */
    getStorage() {
        return get('/api/health/storage');
    },

    /**
     * Get API performance metrics
     * @returns {Promise<Object>} API metrics (requests, response times, errors)
     */
    getApiMetrics() {
        return get('/api/health/api-metrics');
    },

    /**
     * Get database health information
     * @returns {Promise<Object>} Database connection and performance metrics
     */
    getDatabase() {
        return get('/api/health/database');
    },

    /**
     * Dismiss a health alert
     * @param {number} alertId - Alert ID
     * @returns {Promise<Object>} Dismiss result
     */
    dismissAlert(alertId) {
        return post(`/api/health/alerts/${alertId}/dismiss`);
    }
};

// ============================================================================
// SENSORS & HISTORY API
// ============================================================================

const SensorAPI = {
    /**
     * Get sensor history
     * @param {Object} params - Query parameters
     * @param {string} [params.start_date] - Start date (ISO format)
     * @param {string} [params.end_date] - End date (ISO format)
     * @returns {Promise<Object>} Sensor history
     */
    getHistory(params = {}) {
        const query = new URLSearchParams();
        if (params.start_date) query.append('start', params.start_date);
        if (params.end_date) query.append('end', params.end_date);
        const queryStr = query.toString();
        return get(`/api/analytics/sensors/history${queryStr ? '?' + queryStr : ''}`);
    }
};

// ============================================================================
// DASHBOARD API
// ============================================================================

const DashboardAPI = {
    /**
     * Get current sensor readings
     * @returns {Promise<Object>} Current sensor data
     */
    getCurrentSensors() {
        return get('/api/dashboard/sensors/current');
    },

    /**
     * Get decoded sensor timeseries for charts.
     * @param {Object} params - Query parameters
     * @param {string} [params.start] - ISO start datetime
     * @param {string} [params.end] - ISO end datetime
     * @param {number} [params.hours] - Horizon in hours (fallback if start missing)
     * @param {number} [params.unit_id] - Unit filter
     * @param {number} [params.sensor_id] - Sensor filter
     * @param {number} [params.limit] - Row cap before downsampling
     * @returns {Promise<Object>} Timeseries payload
     */
    getTimeseries(params = {}) {
        const search = new URLSearchParams();
        if (params.start) search.append('start', params.start);
        if (params.end) search.append('end', params.end);
        if (params.hours != null) search.append('hours', params.hours);
        if (params.unit_id != null) search.append('unit_id', params.unit_id);
        if (params.sensor_id != null) search.append('sensor_id', params.sensor_id);
        if (params.limit != null) search.append('limit', params.limit);
        const qs = search.toString();
        return get(`/api/dashboard/timeseries${qs ? `?${qs}` : ''}`);
    },

    /**
     * Toggle device on/off
     * @param {string} deviceType - Device type
     * @param {Object} data - Toggle data
     * @returns {Promise<Object>} Toggle result
     */
    toggleDevice(deviceType, data) {
        return post(`/api/dashboard/devices/toggle/${deviceType}`, data);
    },

    /**
     * Get system status
     * @returns {Promise<Object>} System status
     */
    getStatus() {
        return get('/api/dashboard/status');
    },

    /**
     * Get comprehensive dashboard summary
     * @returns {Promise<Object>} Aggregated dashboard data including:
     *   - sensors: Current sensor values with status
     *   - vpd: VPD calculation with zone indicator
     *   - plants: Plants in unit with health summary
     *   - alerts: Recent alerts count and list
     *   - energy: Current power and estimated daily cost
     *   - devices: Active device counts
     *   - actuators: Actuator list for quick controls
     *   - system: Overall health score
     */
    getSummary() {
        return get('/api/dashboard/summary');
    },

    /**
     * Get recent actuator state changes
     * @param {Object} options - Query options
     * @param {number} [options.limit=20] - Max records
     * @param {number} [options.unit_id] - Optional unit filter
     * @returns {Promise<Object>} Recent actuator states
     */
    getRecentActuatorStates(options = {}) {
        const params = new URLSearchParams();
        if (options.limit) params.append('limit', String(options.limit));
        if (options.unit_id) params.append('unit_id', String(options.unit_id));
        return get(`/api/dashboard/actuators/recent-state?${params}`);
    },

    /**
     * Get recent connectivity events
     * @param {Object} options - Query options
     * @param {number} [options.limit=20] - Max records
     * @param {string} [options.connection_type] - Filter by connection type
     * @param {number} [options.unit_id] - Optional unit filter
     * @returns {Promise<Object>} Recent connectivity events
     */
    getConnectivityHistory(options = {}) {
        const params = new URLSearchParams();
        if (options.limit) params.append('limit', String(options.limit));
        if (options.connection_type) params.append('connection_type', options.connection_type);
        if (options.unit_id) params.append('unit_id', String(options.unit_id));
        return get(`/api/dashboard/connectivity/recent?${params}`);
    },

    /**
     * Get growth stage progress for a unit
     * @param {number} [unitId] - Optional unit ID
     * @returns {Promise<Object>} Growth stage data
     */
    getGrowthStage(unitId = null) {
        const params = new URLSearchParams();
        if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
        const qs = params.toString();
        return get(`/api/dashboard/growth-stage${qs ? `?${qs}` : ''}`);
    },

    /**
     * Get harvest timeline for a unit
     * @param {number} [unitId] - Optional unit ID
     * @returns {Promise<Object>} Harvest timeline data
     */
    getHarvestTimeline(unitId = null) {
        const params = new URLSearchParams();
        if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
        const qs = params.toString();
        return get(`/api/dashboard/harvest-timeline${qs ? `?${qs}` : ''}`);
    },

    /**
     * Get water and feed schedule overview for a unit
     * @param {number} [unitId] - Optional unit ID
     * @returns {Promise<Object>} Water schedule data
     */
    getWaterSchedule(unitId = null) {
        const params = new URLSearchParams();
        if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
        const qs = params.toString();
        return get(`/api/dashboard/water-schedule${qs ? `?${qs}` : ''}`);
    },

    /**
     * Get irrigation status for a unit
     * @param {number} [unitId] - Optional unit ID
     * @returns {Promise<Object>} Irrigation status data
     */
    getIrrigationStatus(unitId = null) {
        const params = new URLSearchParams();
        if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
        const qs = params.toString();
        return get(`/api/dashboard/irrigation-status${qs ? `?${qs}` : ''}`);
    }
};

// ============================================================================
// SETTINGS API
// ============================================================================

const SettingsAPI = {
    // Hotspot
    /**
     * Get hotspot settings
     * @returns {Promise<Object>} Hotspot settings
     */
    getHotspot() {
        return get('/api/settings/hotspot');
    },

    /**
     * Update hotspot settings
     * @param {Object} settings - {ssid: string, password?: string}
     * @returns {Promise<Object>} Updated settings
     */
    updateHotspot(settings) {
        return put('/api/settings/hotspot', settings);
    },

    // Camera
    /**
     * Get camera settings
     * @returns {Promise<Object>} Camera settings
     */
    getCamera() {
        return get('/api/settings/camera');
    },

    /**
     * Update camera settings
     * @param {Object} settings - Camera settings
     * @returns {Promise<Object>} Updated settings
     */
    updateCamera(settings) {
        return put('/api/settings/camera', settings);
    },

    // Environment
    /**
     * Get environment settings
     * @returns {Promise<Object>} Environment settings
     */
    getEnvironment() {
        return get('/api/settings/environment');
    },

    /**
     * Update environment settings
     * @param {Object} settings - Environment settings
     * @returns {Promise<Object>} Updated settings
     */
    updateEnvironment(settings) {
        return put('/api/settings/environment', settings);
    },

    // WiFi
    /**
     * Scan for WiFi networks
     * @returns {Promise<Object>} List of networks
     */
    scanWiFi() {
        return get('/api/settings/wifi/scan');
    },

    /**
     * Configure WiFi for a device
     * @param {Object} config - WiFi configuration
     * @returns {Promise<Object>} Result
     */
    configureWiFi(config) {
        return post('/api/settings/wifi/configure', config);
    },

    /**
     * Broadcast WiFi configuration
     * @param {Object} config - WiFi configuration
     * @returns {Promise<Object>} Result
     */
    broadcastWiFi(config) {
        return post('/api/settings/wifi/broadcast', config);
    },

    // Throttle (unit-scoped)
    /**
     * Get sensor data throttling configuration for a unit
     * @param {number} unitId
     */
    getThrottleConfig(unitId) {
        return get(`/api/settings/throttle?unit_id=${encodeURIComponent(unitId)}`);
    },

    /**
     * Update throttling configuration for a unit (partial updates supported)
     * @param {number} unitId
     * @param {Object} payload
     */
    updateThrottleConfig(unitId, payload) {
        return put(`/api/settings/throttle?unit_id=${encodeURIComponent(unitId)}`, payload);
    },

    /**
     * Reset throttling configuration to defaults for a unit
     * @param {number} unitId
     */
    resetThrottleConfig(unitId) {
        return post(`/api/settings/throttle/reset?unit_id=${encodeURIComponent(unitId)}`);
    }
};

// ============================================================================
// ML/AI API
// ============================================================================

const MLAPI = {
    // ---------- Health & Status ----------
    /**
     * Get ML system health
     * @returns {Promise<Object>} ML health status
     */
    getHealth() {
        return get('/api/ml/health');
    },

    /**
     * Get all models status summary
     * @returns {Promise<Object>} Models status
     */
    getModelsStatus() {
        return get('/api/ml/models/status');
    },

    // ---------- Models Management ----------
    /**
     * Get all ML models
     * @returns {Promise<Object>} List of models
     */
    getModels() {
        return get('/api/ml/models');
    },

    /**
     * Get details for a specific model
     * @param {string} modelName - Model name
     * @returns {Promise<Object>} Model details
     */
    getModel(modelName) {
        return get(`/api/ml/models/${modelName}`);
    },

    /**
     * Get model features
     * @param {string} modelName - Model name
     * @returns {Promise<Object>} Model features
     */
    getModelFeatures(modelName) {
        return get(`/api/ml/models/${modelName}/features`);
    },

    /**
     * Activate a model version
     * @param {string} modelName - Model name
     * @param {string} version - Version to activate
     * @returns {Promise<Object>} Activation result
     */
    activateModel(modelName, version) {
        return post(`/api/ml/models/${modelName}/activate`, { version });
    },

    /**
     * Retrain a specific model
     * @param {string} modelName - Model name
     * @param {Object} [options] - Retraining options
     * @returns {Promise<Object>} Retraining result
     */
    retrainModel(modelName, options = {}) {
        return post(`/api/ml/models/${modelName}/retrain`, options);
    },

    // ---------- Drift Monitoring ----------
    /**
     * Get drift status for a model
     * @param {string} modelName - Model name
     * @returns {Promise<Object>} Drift metrics
     */
    getDrift(modelName) {
        return get(`/api/ml/models/${modelName}/drift`);
    },

    /**
     * Get drift history for a model
     * @param {string} modelName - Model name
     * @returns {Promise<Object>} Drift history
     */
    getDriftHistory(modelName) {
        return get(`/api/ml/models/${modelName}/drift/history`);
    },

    // ---------- Training ----------
    /**
     * Get training history
     * @returns {Promise<Object>} Training events
     */
    getTrainingHistory() {
        return get('/api/ml/training/history');
    },

    /**
     * Cancel a training job
     * @param {string} [modelType] - Model type to cancel
     * @returns {Promise<Object>} Cancellation result
     */
    cancelTraining(modelType = null) {
        return post('/api/ml/training/cancel', modelType ? { model_type: modelType } : {});
    },

    /**
     * Schedule a retraining job
     * @param {Object} scheduleData - Schedule configuration
     * @returns {Promise<Object>} Schedule result
     */
    scheduleRetraining(scheduleData) {
        return post('/api/ml/retraining/schedule', scheduleData);
    },

    /**
     * Run a retraining job immediately
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Job result
     */
    runJob(jobId) {
        return post(`/api/ml/retraining/jobs/${jobId}/run`);
    },

    /**
     * Update a retraining job
     * @param {string} jobId - Job ID
     * @param {string} action - Action (enable/disable)
     * @returns {Promise<Object>} Update result
     */
    updateJob(jobId, action) {
        return post(`/api/ml/retraining/jobs/${jobId}/${action}`);
    },

    // ---------- Predictions ----------
    /**
     * Get disease risks
     * @param {Object} [params] - Optional parameters
     * @returns {Promise<Object>} Disease risks
     */
    getDiseaseRisks(params = {}) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/ml/predictions/disease/risks${query ? '?' + query : ''}`);
    },

    /**
     * Get disease alerts
     * @returns {Promise<Object>} Disease alerts
     */
    getDiseaseAlerts() {
        return get('/api/ml/predictions/disease/alerts');
    },

    /**
     * Run what-if simulation
     * @param {Object} simulationData - Simulation parameters
     * @returns {Promise<Object>} Simulation results
     */
    whatIfSimulation(simulationData) {
        return post('/api/ml/predictions/what-if', simulationData);
    },

    /**
     * Get climate forecast
     * @param {Object} params - Forecast parameters
     * @returns {Promise<Object>} Climate forecast
     */
    getClimateForecast(params) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/ml/predictions/climate/forecast?${query}`);
    },

    // ---------- Analysis ----------
    /**
     * Run root cause analysis
     * @param {Object} analysisData - Analysis parameters
     * @returns {Promise<Object>} Root cause analysis results
     */
    rootCauseAnalysis(analysisData) {
        return post('/api/ml/analysis/root-cause', analysisData);
    },

    // ---------- Analytics ----------
    /**
     * Get disease statistics
     * @param {number} [days=90] - Days of history
     * @returns {Promise<Object>} Disease statistics
     */
    getDiseaseStatistics(days = 90) {
        return get(`/api/ml/analytics/disease/statistics?days=${days}`);
    },

    // ---------- Insights ----------
    /**
     * Get ML annotations for chart
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Annotations
     */
    getAnnotations(params) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/ml/insights/annotations?${query}`);
    },

    /**
     * Get confidence bands for predictions
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Confidence bands
     */
    getConfidenceBands(params) {
        const query = new URLSearchParams(params).toString();
        return get(`/api/ml/predictions/confidence-bands?${query}`);
    }
};

// ============================================================================
// A/B TESTING API
// ============================================================================

const ABTestingAPI = {
    /**
     * List all A/B tests
     * @param {string} [status] - Filter by status (active, completed, cancelled)
     * @returns {Promise<Object>} List of A/B tests
     */
    listTests(status = null) {
        const query = status ? `?status=${status}` : '';
        return get(`/api/ml/ab-testing/tests${query}`);
    },

    /**
     * Create a new A/B test
     * @param {Object} testData - Test configuration
     * @param {string} testData.model_name - Base model name
     * @param {string} testData.challenger_version - Challenger version
     * @param {string} testData.champion_version - Champion version
     * @param {number} [testData.traffic_split] - Traffic split for challenger (0-1)
     * @param {number} [testData.min_samples] - Minimum samples before analysis
     * @returns {Promise<Object>} Created test
     */
    createTest(testData) {
        return post('/api/ml/ab-testing/tests', testData);
    },

    /**
     * Get A/B test details
     * @param {string} testId - Test ID
     * @returns {Promise<Object>} Test details with metrics
     */
    getTest(testId) {
        return get(`/api/ml/ab-testing/tests/${testId}`);
    },

    /**
     * Get statistical analysis for a test
     * @param {string} testId - Test ID
     * @returns {Promise<Object>} Statistical analysis results
     */
    getAnalysis(testId) {
        return get(`/api/ml/ab-testing/tests/${testId}/analysis`);
    },

    /**
     * Select a version for prediction (A/B routing)
     * @param {string} testId - Test ID
     * @param {Object} [context] - Optional context for selection
     * @returns {Promise<Object>} Selected version info
     */
    selectVersion(testId, context = {}) {
        return post(`/api/ml/ab-testing/tests/${testId}/select-version`, context);
    },

    /**
     * Record a prediction result for the test
     * @param {string} testId - Test ID
     * @param {Object} resultData - Result data
     * @param {string} resultData.version - Version used (champion/challenger)
     * @param {boolean} resultData.success - Whether prediction was successful
     * @param {number} [resultData.score] - Optional score metric
     * @returns {Promise<Object>} Recording result
     */
    recordResult(testId, resultData) {
        return post(`/api/ml/ab-testing/tests/${testId}/record-result`, resultData);
    },

    /**
     * Complete a test and promote winner
     * @param {string} testId - Test ID
     * @param {string} [winner] - Optional winner override (champion/challenger)
     * @returns {Promise<Object>} Completion result
     */
    completeTest(testId, winner = null) {
        return post(`/api/ml/ab-testing/tests/${testId}/complete`, winner ? { winner } : {});
    },

    /**
     * Cancel an active test
     * @param {string} testId - Test ID
     * @returns {Promise<Object>} Cancellation result
     */
    cancelTest(testId) {
        return post(`/api/ml/ab-testing/tests/${testId}/cancel`);
    }
};

// ============================================================================
// CONTINUOUS MONITORING API
// ============================================================================

const ContinuousMonitoringAPI = {
    /**
     * Get monitoring service status
     * @returns {Promise<Object>} Monitoring status and metrics
     */
    getStatus() {
        return get('/api/ml/continuous/status');
    },

    /**
     * Start continuous monitoring
     * @returns {Promise<Object>} Start result
     */
    start() {
        return post('/api/ml/continuous/start');
    },

    /**
     * Stop continuous monitoring
     * @returns {Promise<Object>} Stop result
     */
    stop() {
        return post('/api/ml/continuous/stop');
    },

    /**
     * Add a unit to monitoring
     * @param {number} unitId - Unit ID to add
     * @returns {Promise<Object>} Add result
     */
    addUnit(unitId) {
        return post(`/api/ml/continuous/units/${unitId}/add`);
    },

    /**
     * Remove a unit from monitoring
     * @param {number} unitId - Unit ID to remove
     * @returns {Promise<Object>} Remove result
     */
    removeUnit(unitId) {
        return post(`/api/ml/continuous/units/${unitId}/remove`);
    },

    /**
     * Get all insights from monitoring
     * @param {number} [limit] - Max insights to return
     * @returns {Promise<Object>} All insights
     */
    getInsights(limit = null) {
        const query = limit ? `?limit=${limit}` : '';
        return get(`/api/ml/continuous/insights${query}`);
    },

    /**
     * Get insights for a specific unit
     * @param {number} unitId - Unit ID
     * @param {number} [limit] - Max insights
     * @returns {Promise<Object>} Unit insights
     */
    getUnitInsights(unitId, limit = null) {
        const query = limit ? `?limit=${limit}` : '';
        return get(`/api/ml/continuous/insights/${unitId}${query}`);
    },

    /**
     * Get critical insights only
     * @returns {Promise<Object>} Critical insights
     */
    getCriticalInsights() {
        return get('/api/ml/continuous/insights/critical');
    }
};

// ============================================================================
// PERSONALIZED LEARNING API
// ============================================================================

const PersonalizedLearningAPI = {
    /**
     * Get user profile for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} User profile with preferences
     */
    getProfile(unitId) {
        return get(`/api/ml/personalized/profiles/${unitId}`);
    },

    /**
     * Create or initialize a user profile
     * @param {Object} profileData - Profile data
     * @param {number} profileData.unit_id - Unit ID
     * @param {string} [profileData.growing_experience] - Experience level
     * @param {Array} [profileData.preferred_plants] - Preferred plant types
     * @returns {Promise<Object>} Created profile
     */
    createProfile(profileData) {
        return post('/api/ml/personalized/profiles', profileData);
    },

    /**
     * Update user profile
     * @param {number} unitId - Unit ID
     * @param {Object} updates - Profile updates
     * @returns {Promise<Object>} Updated profile
     */
    updateProfile(unitId, updates) {
        return put(`/api/ml/personalized/profiles/${unitId}`, updates);
    },

    /**
     * Record a growing success
     * @param {Object} successData - Success data
     * @param {number} successData.unit_id - Unit ID
     * @param {string} successData.success_type - Type of success
     * @param {Object} [successData.details] - Additional details
     * @returns {Promise<Object>} Recording result
     */
    recordSuccess(successData) {
        return post('/api/ml/personalized/successes', successData);
    },

    /**
     * Get personalized recommendations
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Personalized recommendations
     */
    getRecommendations(unitId) {
        return get(`/api/ml/personalized/recommendations/${unitId}`);
    },

    /**
     * Find similar growers
     * @param {number} unitId - Unit ID
     * @param {number} [limit=5] - Max results
     * @returns {Promise<Object>} Similar growers with tips
     */
    findSimilarGrowers(unitId, limit = 5) {
        return get(`/api/ml/personalized/similar-growers/${unitId}?limit=${limit}`);
    }
};

// ============================================================================
// TRAINING DATA API
// ============================================================================

const TrainingDataAPI = {
    /**
     * Get training data summary
     * @returns {Promise<Object>} Summary of available training data
     */
    getSummary() {
        return get('/api/ml/training-data/summary');
    },

    /**
     * Collect disease training data
     * @param {Object} data - Disease sample data
     * @returns {Promise<Object>} Collection result
     */
    collectDiseaseData(data) {
        return post('/api/ml/training-data/collect/disease', data);
    },

    /**
     * Collect climate training data
     * @param {Object} data - Climate sample data
     * @returns {Promise<Object>} Collection result
     */
    collectClimateData(data) {
        return post('/api/ml/training-data/collect/climate', data);
    },

    /**
     * Collect growth training data
     * @param {Object} data - Growth sample data
     * @returns {Promise<Object>} Collection result
     */
    collectGrowthData(data) {
        return post('/api/ml/training-data/collect/growth', data);
    },

    /**
     * Validate training data
     * @param {Object} validationRequest - Validation request
     * @param {string} validationRequest.dataset_type - Type of dataset
     * @param {Array} [validationRequest.sample_ids] - Specific samples to validate
     * @returns {Promise<Object>} Validation results
     */
    validate(validationRequest) {
        return post('/api/ml/training-data/validate', validationRequest);
    },

    /**
     * Get data quality metrics
     * @param {string} datasetType - Dataset type (disease, climate, growth)
     * @returns {Promise<Object>} Quality metrics
     */
    getQualityMetrics(datasetType) {
        return get(`/api/ml/training-data/quality/${datasetType}`);
    }
};

// ============================================================================
// GROWTH STAGES API
// ============================================================================

const GrowthStagesAPI = {
    /**
     * Get optimal conditions for a specific growth stage
     * @param {string} stage - Growth stage (germination, seedling, vegetative, flowering, fruiting, harvest)
     * @param {number} [daysInStage] - Optional days in stage for prediction
     * @returns {Promise<Object>} Optimal conditions and recommendations
     */
    async predictStageConditions(stage, daysInStage = null) {
        const url = `/api/ml/predictions/growth/${stage}${daysInStage ? `?days_in_stage=${daysInStage}` : ''}`;
        return get(url);
    },

    /**
     * Get optimal conditions for all growth stages
     * @returns {Promise<Object>} All stage conditions
     */
    async getAllStageConditions() {
        return get('/api/ml/predictions/growth/stages/all');
    },

    /**
     * Compare actual conditions against optimal for a stage
     * @param {string} stage - Growth stage
     * @param {Object} actualConditions - Actual environmental conditions
     * @param {number} actualConditions.temperature - Temperature in °C
     * @param {number} actualConditions.humidity - Humidity percentage
     * @param {number} actualConditions.light_hours - Light hours per day
     * @param {number} actualConditions.light_intensity - Light intensity (PAR µmol/m²/s)
     * @param {number} [actualConditions.co2_ppm] - CO2 concentration
     * @param {number} [actualConditions.vpd] - Vapor pressure deficit
     * @returns {Promise<Object>} Comparison results with recommendations
     */
    async compareConditions(stage, actualConditions) {
        return post('/api/ml/predictions/growth/compare', {
            stage,
            actual_conditions: actualConditions
        });
    },

    /**
     * Analyze readiness for growth stage transition
     * @param {string} currentStage - Current growth stage
     * @param {number} daysInStage - Days in current stage
     * @param {Object} [actualConditions] - Current conditions
     * @returns {Promise<Object>} Transition analysis with readiness score
     */
    async analyzeTransition(currentStage, daysInStage, actualConditions = {}) {
        return post('/api/ml/predictions/growth/transition-analysis', {
            current_stage: currentStage,
            days_in_stage: daysInStage,
            actual_conditions: actualConditions
        });
    },

    /**
     * Get growth predictor status
     * @returns {Promise<Object>} Predictor status and available stages
     */
    async getStatus() {
        return get('/api/ml/predictions/growth/status');
    }
};

// ============================================================================
// RETRAINING API
// ============================================================================

const RetrainingAPI = {
    /**
     * Get all retraining jobs
     * @returns {Promise<Object>} List of retraining jobs
     */
    async getJobs() {
        return get('/api/ml/retraining/jobs');
    },

    /**
     * Create a new retraining job
     * @param {Object} jobData - Job configuration
     * @param {string} jobData.model_type - Model type (climate, disease, etc.)
     * @param {string} jobData.schedule_type - Schedule type (daily, weekly, monthly, on_drift)
     * @param {string} [jobData.schedule_time] - Time for scheduled jobs (HH:MM)
     * @param {number} [jobData.schedule_day] - Day for weekly/monthly jobs (0-6 or 1-31)
     * @param {number} [jobData.min_samples] - Minimum samples required
     * @param {number} [jobData.drift_threshold] - Drift threshold for on_drift jobs
     * @param {number} [jobData.performance_threshold] - Performance threshold
     * @param {boolean} [jobData.enabled=true] - Enable job immediately
     * @returns {Promise<Object>} Created job
     */
    async createJob(jobData) {
        return post('/api/ml/retraining/jobs', jobData);
    },

    /**
     * Delete a retraining job
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Deletion result
     */
    async deleteJob(jobId) {
        return del(`/api/ml/retraining/jobs/${jobId}`);
    },

    /**
     * Enable or disable a retraining job
     * @param {string} jobId - Job ID
     * @param {boolean} enabled - Enable/disable status
     * @returns {Promise<Object>} Update result
     */
    async enableJob(jobId, enabled) {
        return post(`/api/ml/retraining/jobs/${jobId}/enable`, { enabled });
    },

    /**
     * Manually trigger model retraining
     * @param {string} modelType - Model type to retrain
     * @returns {Promise<Object>} Retraining event
     */
    async triggerRetraining(modelType) {
        return post('/api/ml/retraining/trigger', { model_type: modelType });
    },

    /**
     * Get retraining event history
     * @param {string} [modelType] - Filter by model type
     * @param {number} [limit=100] - Maximum events to return
     * @returns {Promise<Object>} Event history
     */
    async getEvents(modelType = null, limit = 100) {
        const params = new URLSearchParams();
        if (modelType) params.append('model_type', modelType);
        params.append('limit', limit);
        const query = params.toString();
        return get(`/api/ml/retraining/events${query ? '?' + query : ''}`);
    },

    /**
     * Start the automated retraining scheduler
     * @returns {Promise<Object>} Start result
     */
    async startScheduler() {
        return post('/api/ml/retraining/scheduler/start');
    },

    /**
     * Stop the automated retraining scheduler
     * @returns {Promise<Object>} Stop result
     */
    async stopScheduler() {
        return post('/api/ml/retraining/scheduler/stop');
    },

    /**
     * Get retraining service status
     * @returns {Promise<Object>} Service status including job counts and scheduler state
     */
    async getStatus() {
        return get('/api/ml/retraining/status');
    }
};

// ============================================================================
// SESSION API
// ============================================================================

const SessionAPI = {
    /**
     * Select unit in session
     * @param {Object} data - {unit_id: number}
     * @returns {Promise<Object>} Selection result
     */
    selectUnit(data) {
        return post('/api/session/select-unit', data);
    }
};

// ============================================================================
// AI DASHBOARD API (Continuous AI monitoring & predictions)
// Maps to actual ML endpoints
// ============================================================================

const AIAPI = {
    /**
     * Get AI-generated insights for a unit
     * @param {number} unitId - Unit ID
     * @param {number} [limit=5] - Max insights to return
     * @returns {Promise<Object>} AI insights list
     */
    getInsights(unitId, limit = 5) {
        // Use continuous monitoring insights endpoint
        return get(`/api/ml/continuous/insights/${unitId}?limit=${limit}`).catch(() => 
            // Fallback to monitoring insights
            get(`/api/ml/monitoring/insights/${unitId}`).catch(() => ({ insights: [] }))
        );
    },

    /**
     * Get disease risk prediction for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Disease risk assessment with scores
     */
    getDiseaseRisk(unitId) {
        const params = new URLSearchParams();
        if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
        const qs = params.toString();
        return get(`/api/ml/predictions/disease/risks${qs ? `?${qs}` : ''}`)
            .then((payload) => {
                const units = payload?.units || [];
                const match = unitId !== null && unitId !== undefined
                    ? units.find((unit) => Number(unit.unit_id) === Number(unitId))
                    : units[0];
                return {
                    unit_id: unitId ?? match?.unit_id ?? null,
                    risks: match?.risks || []
                };
            })
            .catch(() => ({
                unit_id: unitId ?? null,
                risks: []
            }));
    },

    /**
     * Get growth progress analysis for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Growth progress with stage info
     */
    async getGrowthProgress(unitId) {
        let stageData = null;
        try {
            const params = new URLSearchParams();
            if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
            const qs = params.toString();
            stageData = await get(`/api/dashboard/growth-stage${qs ? `?${qs}` : ''}`);
        } catch {
            stageData = null;
        }

        let predictorStatus = null;
        try {
            predictorStatus = await get('/api/ml/predictions/growth/status');
        } catch {
            predictorStatus = null;
        }

        const stages = stageData?.stages?.length
            ? stageData.stages
            : ['seedling', 'vegetative', 'flowering', 'fruiting', 'harvest'];
        const currentStage = stageData?.current_stage || 'unknown';
        let stageIndex = stageData?.stage_index;
        if (stageIndex === null || stageIndex === undefined) {
            stageIndex = stages.findIndex(
                (stage) => String(stage).toLowerCase() === String(currentStage).toLowerCase()
            );
        }

        const nextStage = stageIndex >= 0 && stageIndex < stages.length - 1
            ? stages[stageIndex + 1]
            : currentStage;

        const daysInStage = stageData?.days_in_stage ?? 0;
        const daysTotal = stageData?.days_total ?? null;
        const daysLeft = stageData?.days_left ?? (
            daysTotal !== null && daysTotal !== undefined
                ? Math.max(Number(daysTotal) - Number(daysInStage), 0)
                : null
        );

        return {
            current_stage: currentStage,
            days_in_stage: daysInStage,
            progress_percent: stageData?.progress ?? null,
            next_stage: nextStage,
            estimated_days_to_next_stage: daysLeft ?? 'unknown',
            ready_for_next_stage: daysLeft !== null ? daysLeft <= 0 : false,
            predictor_status: predictorStatus?.status || predictorStatus || null
        };
    },

    /**
     * Get harvest forecast for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Harvest prediction with estimated date
     */
    async getHarvestForecast(unitId) {
        try {
            const params = new URLSearchParams();
            if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
            const qs = params.toString();
            const timeline = await get(`/api/dashboard/harvest-timeline${qs ? `?${qs}` : ''}`);
            const upcoming = timeline?.upcoming || [];
            const next = upcoming.length > 0 ? upcoming[0] : null;
            const readyPlants = upcoming.filter((item) => (item.days_until_harvest ?? 0) <= 0);

            return {
                days_remaining: next?.days_until_harvest ?? null,
                estimated_date: next?.expected_harvest_date ?? null,
                confidence: next ? 0.6 : 0,
                ready_plants: readyPlants
            };
        } catch {
            return {
                days_remaining: null,
                estimated_date: null,
                confidence: 0,
                ready_plants: []
            };
        }
    },

    /**
     * Get optimization score and recommendations for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Optimization score and quick actions
     */
    async getOptimization(unitId) {
        try {
            const recommendations = await get(`/api/ml/predictions/climate/${unitId}/recommendations`);
            const priority = recommendations?.priority || 'low';
            const scoreMap = {
                critical: 35,
                high: 55,
                medium: 70,
                low: 85
            };
            const score = scoreMap[priority] ?? 75;
            const actions = recommendations?.actions || [];

            return {
                score,
                status: priority,
                quick_actions: actions.slice(0, 3).map((action, index) => ({
                    type: `climate-${index + 1}`,
                    label: action
                }))
            };
        } catch {
            return {
                score: 85,
                status: 'low',
                quick_actions: []
            };
        }
    },

    /**
     * Get personalized recommendations for a unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Success factors, attention areas, learning stats
     */
    async getRecommendations(unitId) {
        const normalizeList = (items) => (items || [])
            .map((item) => {
                if (typeof item === 'string') return item;
                return item?.description || item?.issue || item?.title || null;
            })
            .filter(Boolean);

        let profile = null;
        try {
            const payload = await get(`/api/ml/personalized/profiles/${unitId}`);
            profile = payload?.profile || null;
        } catch {
            profile = null;
        }

        let recs = null;
        try {
            const payload = await get(`/api/ml/personalized/recommendations/${unitId}`);
            recs = payload?.recommendations || null;
        } catch {
            recs = null;
        }

        const successFactors = normalizeList(profile?.success_factors || recs?.success_factors);
        const attentionAreas = normalizeList(profile?.challenge_areas || recs?.adjustments || recs?.issues);

        const learningStats = {
            cycles_analyzed: profile?.historical_patterns?.cycles_analyzed ?? 0,
            success_rate: profile?.historical_patterns?.success_rate ?? 0,
            profile_completeness: profile ? 100 : 0
        };

        return {
            success_factors: successFactors,
            attention_areas: attentionAreas,
            learning_stats: learningStats
        };
    },

    /**
     * Get multi-day environmental forecast for a unit
     * @param {number} unitId - Unit ID
     * @param {number} [days=7] - Days to forecast
     * @returns {Promise<Object>} Forecast with predictions
     */
    async getForecast(unitId, days = 7) {
        try {
            const hoursAhead = Math.min(Math.max(days, 1) * 24, 24);
            const params = new URLSearchParams();
            if (unitId !== null && unitId !== undefined) params.append('unit_id', String(unitId));
            params.append('hours_ahead', String(hoursAhead));
            const payload = await get(`/api/ml/predictions/climate/forecast?${params.toString()}`);
            const forecast = payload?.forecast || {};

            const timestamps = forecast.timestamps || [];
            const temperatures = forecast.temperature || [];
            const humidities = forecast.humidity || [];
            const moisture = forecast.soil_moisture || [];

            const buckets = new Map();
            for (let i = 0; i < timestamps.length; i += 1) {
                const ts = timestamps[i];
                if (!ts) continue;
                const date = new Date(ts);
                if (Number.isNaN(date.getTime())) continue;
                const key = date.toISOString().slice(0, 10);
                const bucket = buckets.get(key) || { temps: [], hums: [], moistures: [] };
                if (temperatures[i] !== null && temperatures[i] !== undefined) bucket.temps.push(Number(temperatures[i]));
                if (humidities[i] !== null && humidities[i] !== undefined) bucket.hums.push(Number(humidities[i]));
                if (moisture[i] !== null && moisture[i] !== undefined) bucket.moistures.push(Number(moisture[i]));
                buckets.set(key, bucket);
            }

            const daily = Array.from(buckets.entries())
                .sort((a, b) => a[0].localeCompare(b[0]))
                .map(([date, bucket]) => {
                    const avg = (arr) => arr.length > 0
                        ? arr.reduce((sum, value) => sum + value, 0) / arr.length
                        : 0;
                    return {
                        date,
                        temperature: avg(bucket.temps),
                        humidity: avg(bucket.hums),
                        soil_moisture: avg(bucket.moistures),
                        predicted_issues: []
                    };
                });

            return {
                forecast: daily,
                confidence: payload?.confidence ?? 0
            };
        } catch {
            return {
                forecast: [],
                confidence: 0
            };
        }
    },

    /**
     * Get similar growers / community insights for a unit
     * @param {number} unitId - Unit ID
     * @param {number} [limit=3] - Max growers to return
     * @returns {Promise<Object>} Similar growers data
     */
    getSimilarGrowers(unitId, limit = 3) {
        // Use personalized similar growers endpoint
        return get(`/api/ml/personalized/similar-growers/${unitId}?limit=${limit}`).catch(() => ({
            similar_growers: [],
            community_tips: []
        }));
    }
};

// ============================================================================
// STATUS API (Non-API routes)
// ============================================================================

const StatusAPI = {
    /**
     * Get status page data
     * @returns {Promise<Object>} Status data
     */
    getStatus() {
        return get('/status/');
    },

    /**
     * Get system health status
     * @returns {Promise<Object>} System health status
     */
    getHealth() {
        return get('/api/health/system');
    }
};

// ============================================================================
// SYSTEM API (System-level operations)
// ============================================================================

const SystemAPI = {
    /**
     * Get active system alerts
     * @param {Object} [options] - Query options
     * @param {number} [options.hours] - Hours to look back
     * @param {number} [options.limit] - Max alerts
     * @param {number} [options.unit_id] - Optional unit filter
     * @returns {Promise<Object>} Alert data with alerts array
     */
    getAlerts(options = {}) {
        const params = new URLSearchParams();
        if (options.hours) params.append('hours', options.hours);
        if (options.limit) params.append('limit', options.limit);
        if (options.unit_id) params.append('unit_id', options.unit_id);
        const query = params.toString();
        return get(`/api/system/alerts${query ? '?' + query : ''}`);
    },

    /**
     * Get recent system activities
     * @param {number} [limit=10] - Number of activities to retrieve
     * @returns {Promise<Array>} Recent activities
     */
    getActivities(limit = 10) {
        return get(`/api/system/activities?limit=${limit}`);
    },

    /**
     * Get server uptime
     * @returns {Promise<Object>} Uptime information
     */
    getUptime() {
        return get('/api/system/uptime');
    },

    /**
     * Acknowledge an alert
     * @param {number} alertId - Alert ID
     * @returns {Promise<Object>} Acknowledgment result
     */
    acknowledgeAlert(alertId) {
        return post(`/api/system/alerts/${alertId}/acknowledge`);
    },

    /**
     * Resolve an alert
     * @param {number} alertId - Alert ID
     * @returns {Promise<Object>} Resolution result
     */
    resolveAlert(alertId) {
        return post(`/api/system/alerts/${alertId}/resolve`);
    },

    /**
     * Clear all alerts
     * @returns {Promise<Object>} Result
     */
    clearAllAlerts() {
        return post('/api/system/alerts/clear-all');
    }
};

// ============================================================================
// NOTIFICATION API
// ============================================================================

/**
 * Notification-related API endpoints.
 * Handles user notification preferences, messages, and irrigation feedback.
 */
const NotificationAPI = {
    /**
     * Get notification settings for the current user
     * @returns {Promise<Object>} Notification settings
     */
    getSettings() {
        return get('/api/settings/notifications');
    },

    /**
     * Update notification settings
     * @param {Object} settings - Settings to update
     * @returns {Promise<Object>} Updated settings
     */
    updateSettings(settings) {
        return put('/api/settings/notifications', settings);
    },

    /**
     * Send a test email notification
     * @returns {Promise<Object>} Test result
     */
    sendTestEmail() {
        return post('/api/settings/notifications/test-email');
    },

    /**
     * Get notifications for the current user
     * @param {Object} options - Query options
     * @param {boolean} [options.unreadOnly=false] - Only get unread notifications
     * @param {number} [options.limit=50] - Max notifications to return
     * @param {number} [options.offset=0] - Pagination offset
     * @returns {Promise<Object>} Notifications list with unread count
     */
    getMessages(options = {}) {
        const params = new URLSearchParams();
        if (options.unreadOnly) params.set('unread_only', 'true');
        if (options.limit) params.set('limit', options.limit);
        if (options.offset) params.set('offset', options.offset);
        const query = params.toString();
        return get(`/api/settings/notifications/messages${query ? '?' + query : ''}`);
    },

    /**
     * Mark a notification as read
     * @param {number} messageId - Notification message ID
     * @returns {Promise<Object>} Result
     */
    markAsRead(messageId) {
        return post(`/api/settings/notifications/messages/${messageId}/read`);
    },

    /**
     * Mark all notifications as read
     * @returns {Promise<Object>} Result with count marked
     */
    markAllAsRead() {
        return post('/api/settings/notifications/messages/read-all');
    },

    /**
     * Delete a notification
     * @param {number} messageId - Notification message ID
     * @returns {Promise<Object>} Result
     */
    deleteMessage(messageId) {
        return del(`/api/settings/notifications/messages/${messageId}`);
    },

    /**
     * Clear all notifications
     * @returns {Promise<Object>} Result with count deleted
     */
    clearAll() {
        return del('/api/settings/notifications/messages');
    },

    /**
     * Get pending action notifications
     * @param {string} [actionType] - Filter by action type
     * @returns {Promise<Object>} Pending actions list
     */
    getPendingActions(actionType = null) {
        const query = actionType ? `?action_type=${actionType}` : '';
        return get(`/api/settings/notifications/actions${query}`);
    },

    /**
     * Respond to an action notification
     * @param {number} messageId - Notification message ID
     * @param {string} response - Action response
     * @returns {Promise<Object>} Result
     */
    respondToAction(messageId, response) {
        return post(`/api/settings/notifications/actions/${messageId}/respond`, { response });
    },

    /**
     * Get pending irrigation feedback requests
     * @returns {Promise<Object>} Pending feedback list
     */
    getPendingIrrigationFeedback() {
        return get('/api/settings/notifications/irrigation-feedback');
    },

    /**
     * Submit irrigation feedback
     * @param {number} feedbackId - Feedback record ID
     * @param {string} response - Feedback response (too_little, just_right, too_much, skipped)
     * @param {string} [notes] - Optional notes
     * @returns {Promise<Object>} Result
     */
    submitIrrigationFeedback(feedbackId, response, notes = null) {
        const body = { response };
        if (notes) body.notes = notes;
        return post(`/api/settings/notifications/irrigation-feedback/${feedbackId}`, body);
    },

    /**
     * Get irrigation feedback history for a unit
     * @param {number} unitId - Growth unit ID
     * @param {number} [limit=20] - Max records to return
     * @returns {Promise<Object>} Feedback history
     */
    getIrrigationFeedbackHistory(unitId, limit = 20) {
        return get(`/api/settings/notifications/irrigation-feedback/history/${unitId}?limit=${limit}`);
    }
};

// ============================================================================
// IRRIGATION WORKFLOW API
// ============================================================================

/**
 * Irrigation Workflow API
 * Manages irrigation standby/notification/approval workflow
 */
const IrrigationAPI = {
    /**
     * Get pending irrigation requests for current user
     * @param {number} [limit=20] - Max requests to return
     * @returns {Promise<Object>} Pending requests
     */
    getPendingRequests(limit = 20) {
        return get(`/api/irrigation/requests?limit=${limit}`);
    },

    /**
     * Get a specific irrigation request
     * @param {number} requestId - Request ID
     * @returns {Promise<Object>} Request details
     */
    getRequest(requestId) {
        return get(`/api/irrigation/requests/${requestId}`);
    },

    /**
     * Approve an irrigation request
     * @param {number} requestId - Request ID
     * @returns {Promise<Object>} Result
     */
    approveRequest(requestId) {
        return post(`/api/irrigation/requests/${requestId}/approve`, {});
    },

    /**
     * Delay an irrigation request
     * @param {number} requestId - Request ID
     * @param {number} [delayMinutes] - Minutes to delay (optional)
     * @returns {Promise<Object>} Result with delayed_until
     */
    delayRequest(requestId, delayMinutes = null) {
        const body = delayMinutes ? { delay_minutes: delayMinutes } : {};
        return post(`/api/irrigation/requests/${requestId}/delay`, body);
    },

    /**
     * Cancel an irrigation request
     * @param {number} requestId - Request ID
     * @returns {Promise<Object>} Result
     */
    cancelRequest(requestId) {
        return post(`/api/irrigation/requests/${requestId}/cancel`, {});
    },

    /**
     * Submit feedback for an executed irrigation request
     * @param {number} requestId - Request ID
     * @param {string} response - 'too_little', 'just_right', or 'too_much'
     * @param {string} [notes] - Optional notes
     * @returns {Promise<Object>} Result
     */
    submitFeedback(requestId, response, notes = null) {
        const body = { response };
        if (notes) body.notes = notes;
        return post(`/api/irrigation/requests/${requestId}/feedback`, body);
    },

    /**
     * Handle action from notification (convenience endpoint)
     * @param {number} requestId - Request ID
     * @param {string} action - 'approve', 'delay', or 'cancel'
     * @param {number} [delayMinutes] - Minutes to delay (for delay action)
     * @returns {Promise<Object>} Result
     */
    handleAction(requestId, action, delayMinutes = null) {
        const body = { action };
        if (action === 'delay' && delayMinutes) {
            body.delay_minutes = delayMinutes;
        }
        return post(`/api/irrigation/action/${requestId}`, body);
    },

    /**
     * Get irrigation request history for a unit
     * @param {number} unitId - Growth unit ID
     * @param {number} [limit=50] - Max requests to return
     * @returns {Promise<Object>} Request history
     */
    getHistory(unitId, limit = 50) {
        return get(`/api/irrigation/history/${unitId}?limit=${limit}`);
    },

    /**
     * Get irrigation execution logs for a unit
     * @param {number} unitId - Growth unit ID
     * @param {Object} [params] - Optional query params
     * @returns {Promise<Object>} Execution logs
     */
    getExecutionLogs(unitId, params = {}) {
        const qs = new URLSearchParams(params).toString();
        return get(`/api/irrigation/executions/${unitId}${qs ? `?${qs}` : ''}`);
    },

    /**
     * Get irrigation eligibility traces for a unit
     * @param {number} unitId - Growth unit ID
     * @param {Object} [params] - Optional query params
     * @returns {Promise<Object>} Eligibility traces
     */
    getEligibilityTraces(unitId, params = {}) {
        const qs = new URLSearchParams(params).toString();
        return get(`/api/irrigation/eligibility/${unitId}${qs ? `?${qs}` : ''}`);
    },

    /**
     * Get manual irrigation history for a unit
     * @param {number} unitId - Growth unit ID
     * @param {Object} [params] - Optional query params
     * @returns {Promise<Object>} Manual irrigation logs
     */
    getManualHistory(unitId, params = {}) {
        const qs = new URLSearchParams(params).toString();
        return get(`/api/irrigation/manual/${unitId}${qs ? `?${qs}` : ''}`);
    },

    /**
     * Predict next irrigation time for manual mode
     * @param {number} plantId - Plant ID
     * @param {Object} params - { unit_id, threshold, soil_moisture }
     * @returns {Promise<Object>} Prediction
     */
    predictManualNext(plantId, params = {}) {
        const qs = new URLSearchParams(params).toString();
        return get(`/api/irrigation/manual/predict/${plantId}${qs ? `?${qs}` : ''}`);
    },

    /**
     * Get irrigation workflow configuration for a unit
     * @param {number} unitId - Growth unit ID
     * @returns {Promise<Object>} Workflow configuration
     */
    getConfig(unitId) {
        return get(`/api/irrigation/config/${unitId}`);
    },

    /**
     * Update irrigation workflow configuration for a unit
     * @param {number} unitId - Growth unit ID
     * @param {Object} config - Configuration updates
     * @returns {Promise<Object>} Updated configuration
     */
    updateConfig(unitId, config) {
        return put(`/api/irrigation/config/${unitId}`, config);
    },

    /**
     * Get user irrigation preferences
     * @param {number} [unitId] - Optional unit ID for unit-specific preferences
     * @returns {Promise<Object>} User preferences
     */
    getPreferences(unitId = null) {
        const url = unitId
            ? `/api/irrigation/preferences?unit_id=${unitId}`
            : '/api/irrigation/preferences';
        return get(url);
    },

    // ========== Pump Calibration ==========

     /**
      * Start pump calibration session
      * @param {number} actuatorId - Pump actuator ID
     * @param {number|null} [durationSeconds=null] - Optional duration in seconds
      * @returns {Promise<Object>} Calibration session info
      */
    startCalibration(actuatorId, durationSeconds = null) {
        const payload = { actuator_id: actuatorId };
        if (durationSeconds != null) {
            payload.duration_seconds = durationSeconds;
        }
        return post('/api/irrigation/calibration/pump/start', payload);
    },

     /**
      * Complete pump calibration with measured values
      * @param {number} actuatorId - Pump actuator ID
     * @param {number} measuredMl - Measured volume
      * @returns {Promise<Object>} Calibration result with flow rate
      */
    completeCalibration(actuatorId, measuredMl) {
        return post(`/api/irrigation/calibration/pump/${actuatorId}/complete`, {
            measured_ml: measuredMl
        });
    },

    /**
     * Get current calibration data for a pump
     * @param {number} actuatorId - Pump actuator ID
     * @returns {Promise<Object>} Calibration data
     */
    getCalibration(actuatorId) {
        return get(`/api/irrigation/calibration/pump/${actuatorId}`);
    },

    /**
     * Get calibration history and trend analysis for a pump
     * @param {number} actuatorId - Pump actuator ID
     * @returns {Promise<Object>} Calibration history with trend analysis
     */
    getCalibrationHistory(actuatorId) {
        return get(`/api/irrigation/calibration/pump/${actuatorId}/history`);
    },

     /**
      * Adjust calibration based on post-irrigation feedback
      * @param {number} actuatorId - Pump actuator ID
     * @param {string} feedback - "too_little", "just_right", or "too_much"
     * @param {number|null} [adjustmentFactor=null] - Optional adjustment percentage
      * @returns {Promise<Object>} Adjusted flow rate
      */
    adjustCalibration(actuatorId, feedback, adjustmentFactor = null) {
        const payload = { feedback };
        if (adjustmentFactor != null) {
            payload.adjustment_factor = adjustmentFactor;
        }
        return post(`/api/irrigation/calibration/pump/${actuatorId}/adjust`, payload);
    },

    // ========== Irrigation Recommendations ==========

    /**
     * Get irrigation recommendations for a plant
     * @param {number} plantId - Plant ID
     * @returns {Promise<Object>} Recommendation with urgency and calculation preview
     */
    getRecommendations(plantId) {
        return get(`/api/irrigation/recommendations/${plantId}`);
    },

    /**
     * Get irrigation calculation for a plant
     * @param {number} plantId - Plant ID
     * @param {boolean} [useML=true] - Whether to use ML enhancement
     * @returns {Promise<Object>} Irrigation calculation (volume, duration, confidence)
     */
    calculate(plantId, useML = true) {
        const url = `/api/irrigation/calculate/${plantId}${useML ? '' : '?use_ml=false'}`;
        return get(url);
    },

    /**
     * Send irrigation recommendation notification to plant owner
     * @param {number} plantId - Plant ID
     * @param {number} [currentMoisture] - Optional current moisture override
     * @returns {Promise<Object>} Send result with recommendation details
     */
    sendRecommendation(plantId, currentMoisture = null) {
        const body = {};
        if (currentMoisture !== null) {
            body.current_moisture = currentMoisture;
        }
        return post(`/api/irrigation/send-recommendation/${plantId}`, body);
    }
};

// ============================================================================
// EXPORTS
// ============================================================================

// Export all API modules
const API = {
    Growth: GrowthAPI,
    Plant: PlantAPI,
    Device: DeviceAPI,
    Sensor: SensorAPI,
    Analytics: AnalyticsAPI,
    Insights: InsightsAPI,
    Health: HealthAPI,
    Dashboard: DashboardAPI,
    Settings: SettingsAPI,
    ML: MLAPI,
    AI: AIAPI,
    GrowthStages: GrowthStagesAPI,
    Retraining: RetrainingAPI,
    ABTesting: ABTestingAPI,
    ContinuousMonitoring: ContinuousMonitoringAPI,
    PersonalizedLearning: PersonalizedLearningAPI,
    TrainingData: TrainingDataAPI,
    Session: SessionAPI,
    Status: StatusAPI,
    System: SystemAPI,
    Notification: NotificationAPI,
    Irrigation: IrrigationAPI,

    /**
     * Generic fetch method for custom API endpoints
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options (method, headers, body, etc.)
     * @returns {Promise<Object>} Response data with ok status
     */
    async fetch(url, options = {}) {
        const csrfToken = getCsrfToken();
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        try {
            // Use window.fetch to avoid recursion with this method
            const response = await window.fetch(url, {
                ...options,
                headers
            });

            const rawText = await response.text();
            let data = null;
            if (rawText) {
                try {
                    data = JSON.parse(rawText);
                } catch {
                    data = null;
                }
            }

            // Return full response object with ok status for proper error handling
            return data || { ok: response.ok };
        } catch (error) {
            console.error(`API.fetch failed: ${url}`, error);
            return { ok: false, error: { message: error.message } };
        }
    }
};

// Make available globally
window.API = API;
