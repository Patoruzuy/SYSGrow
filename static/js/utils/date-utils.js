/**
 * Date Utility Functions
 * ======================
 * Centralized date formatting and manipulation utilities.
 * Replaces duplicate formatTimeAgo implementations across components.
 *
 * @module utils/date-utils
 */
(function () {
  'use strict';

  /**
   * Time interval definitions for relative time formatting.
   * Ordered from largest to smallest for proper matching.
   */
  const TIME_INTERVALS = [
    { label: 'year', seconds: 31536000, plural: 'years' },
    { label: 'month', seconds: 2592000, plural: 'months' },
    { label: 'week', seconds: 604800, plural: 'weeks' },
    { label: 'day', seconds: 86400, plural: 'days' },
    { label: 'hour', seconds: 3600, plural: 'hours' },
    { label: 'minute', seconds: 60, plural: 'minutes' },
    { label: 'second', seconds: 1, plural: 'seconds' }
  ];

  /**
   * Format a date as relative time (e.g., "5 minutes ago").
   *
   * @param {string|Date|number} date - Date to format
   * @param {Object} options - Formatting options
   * @param {boolean} options.short - Use short format (5m, 2h, 3d)
   * @param {boolean} options.future - Support future dates ("in 5 minutes")
   * @returns {string} Relative time string
   *
   * @example
   * formatTimeAgo(new Date(Date.now() - 300000))
   * // Returns: '5 minutes ago'
   *
   * formatTimeAgo(new Date(Date.now() - 300000), { short: true })
   * // Returns: '5m ago'
   */
  function formatTimeAgo(date, options = {}) {
    if (!date) return '';

    const { short = false, future = false } = options;
    const now = new Date();
    const then = new Date(date);

    if (isNaN(then.getTime())) return '';

    const diffMs = now - then;
    const isFuture = diffMs < 0;
    const seconds = Math.floor(Math.abs(diffMs) / 1000);

    // Handle "just now" case
    if (seconds < 60) {
      return seconds < 10 ? 'just now' : (short ? `${seconds}s ago` : `${seconds} seconds ago`);
    }

    // Find appropriate interval
    for (const interval of TIME_INTERVALS) {
      const count = Math.floor(seconds / interval.seconds);
      if (count >= 1) {
        if (short) {
          const suffix = interval.label[0]; // 'y', 'm', 'w', 'd', 'h', 'm', 's'
          const shortSuffix = interval.label === 'minute' ? 'm' :
                              interval.label === 'month' ? 'mo' :
                              interval.label[0];
          return isFuture && future
            ? `in ${count}${shortSuffix}`
            : `${count}${shortSuffix} ago`;
        }

        const label = count === 1 ? interval.label : interval.plural;
        return isFuture && future
          ? `in ${count} ${label}`
          : `${count} ${label} ago`;
      }
    }

    return 'just now';
  }

  /**
   * Format a date for display (localized short date).
   *
   * @param {string|Date|number} date - Date to format
   * @param {Object} options - Intl.DateTimeFormat options
   * @returns {string} Formatted date string
   *
   * @example
   * formatDate('2024-01-15')
   * // Returns: 'Jan 15, 2024'
   */
  function formatDate(date, options = {}) {
    if (!date) return '';

    const d = new Date(date);
    if (isNaN(d.getTime())) return '';

    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      ...options
    });
  }

  /**
   * Format a datetime for display (localized date and time).
   *
   * @param {string|Date|number} date - Date to format
   * @param {Object} options - Additional formatting options
   * @returns {string} Formatted datetime string
   *
   * @example
   * formatDateTime('2024-01-15T14:30:00')
   * // Returns: 'Jan 15, 2024, 2:30 PM'
   */
  function formatDateTime(date, options = {}) {
    if (!date) return '';

    const d = new Date(date);
    if (isNaN(d.getTime())) return '';

    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      ...options
    });
  }

  /**
   * Format time only (HH:MM format).
   *
   * @param {string|Date|number} date - Date to format
   * @param {boolean} seconds - Include seconds
   * @returns {string} Formatted time string
   *
   * @example
   * formatTime('2024-01-15T14:30:45')
   * // Returns: '2:30 PM'
   */
  function formatTime(date, seconds = false) {
    if (!date) return '';

    const d = new Date(date);
    if (isNaN(d.getTime())) return '';

    const options = {
      hour: '2-digit',
      minute: '2-digit'
    };

    if (seconds) {
      options.second = '2-digit';
    }

    return d.toLocaleTimeString(undefined, options);
  }

  /**
   * Get ISO date string (YYYY-MM-DD) for a date.
   *
   * @param {Date|string|number} date - Date to format
   * @returns {string} ISO date string
   */
  function toISODate(date) {
    if (!date) return '';
    const d = new Date(date);
    if (isNaN(d.getTime())) return '';
    return d.toISOString().split('T')[0];
  }

  /**
   * Check if a date is today.
   *
   * @param {Date|string|number} date - Date to check
   * @returns {boolean} True if the date is today
   */
  function isToday(date) {
    if (!date) return false;
    const d = new Date(date);
    const today = new Date();
    return d.toDateString() === today.toDateString();
  }

  /**
   * Check if a date is within the last N days.
   *
   * @param {Date|string|number} date - Date to check
   * @param {number} days - Number of days
   * @returns {boolean} True if within the specified days
   */
  function isWithinDays(date, days) {
    if (!date) return false;
    const d = new Date(date);
    const now = new Date();
    const diffMs = now - d;
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    return diffDays >= 0 && diffDays <= days;
  }

  // Export to window for global access
  window.DateUtils = {
    formatTimeAgo,
    formatDate,
    formatDateTime,
    formatTime,
    toISODate,
    isToday,
    isWithinDays,
    TIME_INTERVALS
  };

  // Also export individual functions for convenience
  window.formatTimeAgo = formatTimeAgo;
  window.formatDate = formatDate;
  window.formatDateTime = formatDateTime;

})();
