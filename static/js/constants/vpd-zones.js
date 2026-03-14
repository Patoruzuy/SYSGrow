/**
 * VPD Zone Constants
 * ==================
 * Centralized VPD (Vapor Pressure Deficit) zone definitions.
 * Used across sensor analytics, correlation charts, and plant monitoring.
 *
 * @module constants/vpd-zones
 */
(function () {
  'use strict';

  /**
   * VPD Zone definitions with boundaries, labels, and styling.
   * VPD is measured in kPa (kilopascals).
   *
   * Zone Reference:
   * - Too Low (<0.4): High disease risk, poor transpiration
   * - Vegetative (0.4-0.8): Ideal for vegetative growth
   * - Optimal (0.8-1.2): Ideal for flowering/fruiting
   * - Late Flower (1.2-1.6): Acceptable for late flowering
   * - Too High (>1.6): Stress risk, excessive transpiration
   */
  const VPD_ZONES = {
    TOO_LOW: {
      key: 'TOO_LOW',
      min: 0,
      max: 0.4,
      label: 'Too Low',
      shortLabel: 'Low',
      class: 'status-danger',
      badgeClass: 'badge-danger',
      color: '#dc3545',
      backgroundColor: 'rgba(220, 53, 69, 0.1)',
      description: 'Transpiration too slow - risk of mold and disease',
      recommendation: 'Increase temperature or decrease humidity'
    },
    VEGETATIVE: {
      key: 'VEGETATIVE',
      min: 0.4,
      max: 0.8,
      label: 'Vegetative',
      shortLabel: 'Veg',
      class: 'status-warning',
      badgeClass: 'badge-warning',
      color: '#8bc34a',
      backgroundColor: 'rgba(139, 195, 74, 0.1)',
      description: 'Ideal for vegetative growth stage',
      recommendation: 'Good for young plants and leaf development'
    },
    OPTIMAL: {
      key: 'OPTIMAL',
      min: 0.8,
      max: 1.2,
      label: 'Optimal',
      shortLabel: 'Opt',
      class: 'status-success',
      badgeClass: 'badge-success',
      color: '#28a745',
      backgroundColor: 'rgba(40, 167, 69, 0.1)',
      description: 'Ideal VPD range for most growth stages',
      recommendation: 'Maintain current conditions'
    },
    LATE_FLOWER: {
      key: 'LATE_FLOWER',
      min: 1.2,
      max: 1.6,
      label: 'Late Flower',
      shortLabel: 'Late',
      class: 'status-warning',
      badgeClass: 'badge-warning',
      color: '#ffc107',
      backgroundColor: 'rgba(255, 193, 7, 0.1)',
      description: 'Suitable for late flowering stage',
      recommendation: 'Acceptable for mature flowering plants'
    },
    TOO_HIGH: {
      key: 'TOO_HIGH',
      min: 1.6,
      max: Infinity,
      label: 'Too High',
      shortLabel: 'High',
      class: 'status-danger',
      badgeClass: 'badge-danger',
      color: '#dc3545',
      backgroundColor: 'rgba(220, 53, 69, 0.1)',
      description: 'Transpiration too fast - risk of wilting and stress',
      recommendation: 'Decrease temperature or increase humidity'
    }
  };

  /**
   * Ordered array of zones for iteration (low to high).
   */
  const VPD_ZONES_ORDERED = [
    VPD_ZONES.TOO_LOW,
    VPD_ZONES.VEGETATIVE,
    VPD_ZONES.OPTIMAL,
    VPD_ZONES.LATE_FLOWER,
    VPD_ZONES.TOO_HIGH
  ];

  /**
   * Get VPD zone for a given VPD value.
   *
   * @param {number} vpd - VPD value in kPa
   * @returns {Object} Zone object with label, class, color, description
   *
   * @example
   * getVPDZone(0.9)
   * // Returns: { key: 'OPTIMAL', label: 'Optimal', ... }
   */
  function getVPDZone(vpd) {
    if (vpd == null || isNaN(vpd)) {
      return { ...VPD_ZONES.OPTIMAL, key: 'UNKNOWN', label: 'Unknown' };
    }

    for (const zone of VPD_ZONES_ORDERED) {
      if (vpd >= zone.min && vpd < zone.max) {
        return { ...zone };
      }
    }

    return { ...VPD_ZONES.TOO_HIGH };
  }

  /**
   * Get VPD zone label for a given VPD value.
   *
   * @param {number} vpd - VPD value in kPa
   * @param {boolean} short - Use short label
   * @returns {string} Zone label
   */
  function getVPDZoneLabel(vpd, short = false) {
    const zone = getVPDZone(vpd);
    return short ? zone.shortLabel : zone.label;
  }

  /**
   * Get VPD zone CSS class for a given VPD value.
   *
   * @param {number} vpd - VPD value in kPa
   * @returns {string} CSS class name
   */
  function getVPDZoneClass(vpd) {
    return getVPDZone(vpd).class;
  }

  /**
   * Get VPD zone color for a given VPD value.
   *
   * @param {number} vpd - VPD value in kPa
   * @returns {string} Color hex code
   */
  function getVPDZoneColor(vpd) {
    return getVPDZone(vpd).color;
  }

  /**
   * Calculate VPD from temperature and humidity.
   *
   * @param {number} tempC - Temperature in Celsius
   * @param {number} humidity - Relative humidity (0-100)
   * @param {number} leafOffset - Leaf temperature offset in Celsius (default: 0)
   * @returns {number} VPD in kPa
   *
   * @example
   * calculateVPD(25, 60)
   * // Returns: ~1.26 kPa
   */
  function calculateVPD(tempC, humidity, leafOffset = 0) {
    if (tempC == null || humidity == null) return null;

    // Saturation vapor pressure at air temperature (kPa)
    // Using Tetens equation
    const SVPair = 0.6108 * Math.exp((17.27 * tempC) / (tempC + 237.3));

    // Saturation vapor pressure at leaf temperature
    const leafTemp = tempC - leafOffset;
    const SVPleaf = 0.6108 * Math.exp((17.27 * leafTemp) / (leafTemp + 237.3));

    // Actual vapor pressure
    const AVP = SVPair * (humidity / 100);

    // VPD = SVP at leaf - AVP
    const vpd = SVPleaf - AVP;

    return Math.max(0, Math.round(vpd * 100) / 100);
  }

  /**
   * Get ideal VPD range for a growth stage.
   *
   * @param {string} stage - Growth stage (e.g., 'seedling', 'vegetative', 'flowering')
   * @returns {Object} { min, max, zone } VPD range
   */
  function getIdealVPDForStage(stage) {
    const normalizedStage = (stage || '').toLowerCase();

    const stageRanges = {
      germination: { min: 0.4, max: 0.8, zone: VPD_ZONES.VEGETATIVE },
      seedling: { min: 0.4, max: 0.8, zone: VPD_ZONES.VEGETATIVE },
      vegetative: { min: 0.8, max: 1.2, zone: VPD_ZONES.OPTIMAL },
      flowering: { min: 0.8, max: 1.2, zone: VPD_ZONES.OPTIMAL },
      fruiting: { min: 0.8, max: 1.4, zone: VPD_ZONES.OPTIMAL },
      harvest: { min: 1.0, max: 1.4, zone: VPD_ZONES.LATE_FLOWER }
    };

    return stageRanges[normalizedStage] || stageRanges.vegetative;
  }

  // Export to window for global access
  window.VPDConstants = {
    VPD_ZONES,
    VPD_ZONES_ORDERED,
    getVPDZone,
    getVPDZoneLabel,
    getVPDZoneClass,
    getVPDZoneColor,
    calculateVPD,
    getIdealVPDForStage
  };

  // Also export individual items for convenience
  window.VPD_ZONES = VPD_ZONES;
  window.getVPDZone = getVPDZone;
  window.calculateVPD = calculateVPD;

})();
