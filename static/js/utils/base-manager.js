/**
 * BaseManager
 * ============================================================================
 * A small base class providing:
 *  - Consistent init lifecycle with safe wrapper (_safeInit)
 *  - Event listener registration with automatic cleanup
 *  - Common UI helpers (loading/error/empty states)
 *
 * Best practices:
 *  - removeEventListener requires matching capture flag; we store it explicitly.
 *  - messages passed to showLoading/showError/showEmpty are escaped to prevent XSS.
 */
(function () {
  'use strict';

  class BaseManager {
    /**
     * @param {string} name - Manager name for logging
     */
    constructor(name = 'BaseManager') {
      this.name = name;
      this.initialized = false;

      /**
       * Tracks event listeners for cleanup.
       * Each entry: { element, event, handler, capture }
       */
      this.eventListeners = [];
    }

    /**
     * Safe initialization wrapper that logs failures but does not crash the page.
     * Subclasses should not override this.
     */
    async _safeInit() {
      try {
        await this.init();
        this.initialized = true;
        this.log('Initialized successfully');
      } catch (error) {
        this.error('Initialization failed:', error);
      }
    }

    /**
     * Initialize the manager (override in subclass).
     * Can be async.
     */
    async init() {
      // Default behavior: bind events
      this.bindEvents();
    }

    /**
     * Bind event listeners (override in subclass).
     */
    bindEvents() {
      // Override
    }

    /**
     * Add an event listener and register it for automatic cleanup.
     *
     * Note: removeEventListener matching is sensitive to "capture".
     * We store capture only (the rest of options do not matter for removal).
     *
     * @param {Element|Document|Window} element
     * @param {string} event
     * @param {Function} handler
     * @param {Object|boolean} [options]
     */
    addEventListener(element, event, handler, options = {}) {
      if (!element) {
        this.warn(`Cannot add listener: element is null for event "${event}"`);
        return;
      }

      try {
        element.addEventListener(event, handler, options);
        const capture = typeof options === 'boolean' ? options : Boolean(options?.capture);
        this.eventListeners.push({ element, event, handler, capture });
      } catch (error) {
        this.warn(`Failed to add listener for "${event}":`, error);
      }
    }

    /**
     * Add delegated event listener (useful for dynamic content).
     *
     * @param {Element|Document} parent
     * @param {string} event
     * @param {string} selector
     * @param {Function} handler
     */
    addDelegatedListener(parent, event, selector, handler) {
      const delegatedHandler = (e) => {
        const target = e.target?.closest?.(selector);
        if (target) handler.call(target, e);
      };
      this.addEventListener(parent, event, delegatedHandler);
    }

    /**
     * Remove all tracked listeners.
     */
    removeAllListeners() {
      for (const { element, event, handler, capture } of this.eventListeners) {
        try {
          element.removeEventListener(event, handler, capture);
        } catch {
          // ignore
        }
      }
      this.eventListeners = [];
      this.log('Removed all event listeners');
    }

    /**
     * Destroy manager and cleanup resources.
     */
    destroy() {
      this.removeAllListeners();
      this.initialized = false;
      this.log('Destroyed');
    }

    /**
     * Escape text for safe HTML insertion.
     * @param {any} str
     * @returns {string}
     */
    escapeHTML(str) {
      const div = document.createElement('div');
      div.textContent = String(str ?? '');
      return div.innerHTML;
    }

    /**
     * Show a loading state (safe, escaped text).
     */
    showLoading(container, message = 'Loading...') {
      if (!container) return;
      container.innerHTML = `
        <div class="loading-state">
          <div class="spinner"></div>
          <p>${this.escapeHTML(message)}</p>
        </div>
      `;
    }

    /**
     * Show an error state (safe, escaped text).
     */
    showError(container, message = 'An error occurred') {
      if (!container) return;
      container.innerHTML = `
        <div class="error-state">
          <i class="fas fa-exclamation-triangle"></i>
          <p>${this.escapeHTML(message)}</p>
        </div>
      `;
    }

    /**
     * Show an empty state (safe, escaped text).
     */
    showEmpty(container, message = 'No data available') {
      if (!container) return;
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-inbox"></i>
          <p>${this.escapeHTML(message)}</p>
        </div>
      `;
    }

    // Logging helpers
    log(...args) { console.log(`[${this.name}]`, ...args); }
    warn(...args) { console.warn(`[${this.name}]`, ...args); }
    error(...args) { console.error(`[${this.name}]`, ...args); }
    debug(...args) { console.debug(`[${this.name}]`, ...args); }
  }

  window.BaseManager = BaseManager;
})();
