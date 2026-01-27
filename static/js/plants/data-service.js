/**
 * Plants Data Service
 * ============================================
 * Handles all data fetching for Plants Hub with caching
 */

class PlantsDataService {
    constructor() {
        this.cache = new CacheService('plants', 5 * 60 * 1000); // 5 minutes
        this.catalogCache = new CacheService('catalog', 24 * 60 * 60 * 1000); // 24 hours
        if (!window.API) {
            throw new Error('API not loaded. Ensure api.js is loaded before data-service.js');
        }
        this.api = window.API;
    }

    /**
     * Load all Plants Hub data
     */
    async loadAll() {
        try {
            console.log('[PlantsDataService] Loading all plants data...');
            
            // Use allSettled to handle failures gracefully
            const results = await Promise.allSettled([
                this.loadPlantsHealth(),
                this.loadPlantsGuide(),
                this.loadDiseaseRisk(),
                this.loadHarvests(),
                this.loadJournal()
            ]);
            
            console.log('[PlantsDataService] Load results:', results);
            
            const [plantsHealth, plantsGuide, diseaseRisk, harvests, journal] = results;
            
            const data = {
                plantsHealth: plantsHealth.status === 'fulfilled' ? plantsHealth.value : { plants: [] },
                plantsGuide: plantsGuide.status === 'fulfilled' ? plantsGuide.value : [],
                diseaseRisk: diseaseRisk.status === 'fulfilled' ? diseaseRisk.value : [],
                harvests: harvests.status === 'fulfilled' ? harvests.value : { harvests: [] },
                journal: journal.status === 'fulfilled' ? journal.value : { entries: [] }
            };
            
            // Use backend-computed summary (fallback to client-side calculation for compatibility)
            data.healthScore = data.plantsHealth?.summary || this.calculateHealthScore(data.plantsHealth);
            
            console.log('[PlantsDataService] Final data:', data);
            return data;
        } catch (error) {
            console.error('[PlantsDataService] Failed to load data:', error);
            throw error;
        }
    }

    /**
     * Load plants health data
     */
    async loadPlantsHealth() {
        return this._fetchWithCache('health', async () => {
            const response = await this.api.Plant.getPlantHealth();
            return response.data || response;
        });
    }

    /**
     * Load plants guide
     */
    async loadPlantsGuide() {
        return this._fetchWithCache('guide', async () => {
            const response = await this.api.Plant.getPlantsGuide();
            return response.data || response;
        });
    }

    /**
     * Load disease risk assessment
     */
    async loadDiseaseRisk() {
        return this._fetchWithCache('disease_risk', async () => {
            try {
                const response = await this.api.Plant.getDiseaseRisks();
                return response.data || response;
            } catch (error) {
                // Disease prediction model may not be available - fail gracefully
                console.log('[PlantsDataService] Disease prediction not available:', error.message);
                return [];
            }
        });
    }

    /**
     * Load harvest records
     */
    async loadHarvests(params = {}) {
        const cacheKey = `harvests_${JSON.stringify(params)}`;
        return this._fetchWithCache(cacheKey, async () => {
            const response = await this.api.Plant.getHarvests(params);
            return response.data || response;
        });
    }

    /**
     * Load journal entries
     */
    async loadJournal(params = {}) {
        const cacheKey = `journal_${JSON.stringify(params)}`;
        return this._fetchWithCache(cacheKey, async () => {
            const response = await this.api.Plant.getJournalEntries(params.days, params.plant_id);
            return response.data || response;
        });
    }

    /**
     * Get full plant details by plant ID (requires unit ID).
     */
    async getPlantDetails(plantId, unitId = null) {
        const cacheKey = `plant_${unitId || 'unknown'}_${plantId}`;
        return this._fetchWithCache(cacheKey, async () => {
            return this.api.Plant.getPlant(plantId, unitId);
        });
    }

    /**
     * Record plant observation
     */
    async recordObservation(data) {
        const response = await this.api.Plant.recordObservation(data);
        this.invalidateCache(['journal', 'health']);
        return response;
    }

    /**
     * Record nutrient application
     */
    async recordNutrient(data) {
        const response = await this.api.Plant.recordNutrient(data);
        this.invalidateCache(['journal']);
        return response;
    }

    /**
     * Calculate overall health score
     */
    calculateHealthScore(healthData) {
        if (!healthData || !healthData.plants) return 0;

        const plants = healthData.plants;
        if (plants.length === 0) return 0;

        const healthyCount = plants.filter(p => p.current_health_status === 'healthy').length;
        return Math.round((healthyCount / plants.length) * 100);
    }

    /**
     * Invalidate cache entries
     */
    invalidateCache(patterns = []) {
        patterns.forEach(pattern => {
            this.cache.clearPattern(pattern);
        });
    }

    /**
     * Clear all cache
     */
    clearCache() {
        this.cache.clear();
    }

    // Private helper for caching
    async _fetchWithCache(key, fetcher) {
        const cached = this.cache.get(key);
        if (cached) {
            return cached;
        }

        const data = await fetcher();
        this.cache.set(key, data);
        return data;
    }

    /**
     * Load plant catalog from JSON
     * Cached for 24 hours
     */
    async loadPlantCatalog() {
        const cacheKey = 'plant_catalog';
        const cached = this.catalogCache.get(cacheKey);
        
        if (cached) {
            console.log('[PlantsDataService] Using cached catalog');
            return cached;
        }
        
        console.log('[PlantsDataService] Fetching plant catalog...');
        try {
            const result = await API.Plant.getCatalog();
            console.log('[PlantsDataService] Raw API response:', result);
            
            // API unwraps the response, so result is the actual data
            const catalog = Array.isArray(result) ? result : [];
            this.catalogCache.set(cacheKey, catalog);
            console.log(`[PlantsDataService] Loaded ${catalog.length} plants from catalog`);
            return catalog;
        } catch (error) {
            console.error('[PlantsDataService] Error loading catalog:', error);
            return [];
        }
    }

    /**
     * Get plant by ID from catalog
     */
    async getCatalogPlant(plantId) {
        const catalog = await this.loadPlantCatalog();
        return catalog.find(p => p.id === plantId);
    }

    /**
     * Save custom plant to catalog
     */
    async saveCustomPlant(plantData) {
        console.log('[PlantsDataService] Saving custom plant:', plantData);
        try {
            const result = await API.Plant.saveCustomPlant(plantData);
            // Invalidate catalog cache to force reload
            this.catalogCache.clear();
            console.log('[PlantsDataService] Custom plant saved successfully');
            return result;
        } catch (error) {
            console.error('[PlantsDataService] Error saving custom plant:', error);
            throw error;
        }
    }
}

// Global export
window.PlantsDataService = PlantsDataService;
