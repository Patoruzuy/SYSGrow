/**
 * Notification Utility Functions
 * ===============================
 * Centralized toast notification system.
 * Replaces duplicate showToast implementations across components.
 *
 * @module utils/notification-utils
 */
(function () {
  'use strict';

  /**
   * Default configuration for toast notifications.
   */
  const TOAST_CONFIG = {
    duration: 5000,
    position: 'top-right',
    maxToasts: 5
  };

  /**
   * Icon mappings for notification types.
   */
  const TOAST_ICONS = {
    success: 'fa-check-circle',
    error: 'fa-exclamation-circle',
    warning: 'fa-exclamation-triangle',
    info: 'fa-info-circle'
  };

  /**
   * Color mappings for notification types.
   */
  const TOAST_COLORS = {
    success: '#28a745',
    error: '#dc3545',
    warning: '#ffc107',
    info: '#17a2b8'
  };

  /**
   * Get or create the toast container element.
   *
   * @returns {Element} Toast container element
   */
  function getToastContainer() {
    // Try to find existing container by common IDs
    let container = document.getElementById('toastContainer') ||
                    document.querySelector('.flash-messages') ||
                    document.getElementById('toast-container');

    if (!container) {
      // Create a container if none exists
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      container.setAttribute('aria-live', 'polite');
      container.setAttribute('aria-atomic', 'true');
      document.body.appendChild(container);
    }

    return container;
  }

  /**
   * Escape HTML for safe text display.
   *
   * @param {string} text - Text to escape
   * @returns {string} Escaped text
   */
  function escapeForToast(text) {
    if (window.escapeHtml) {
      return window.escapeHtml(text);
    }
    // Fallback if html-utils not loaded
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Show a toast notification.
   *
   * @param {string} message - Message to display
   * @param {string} type - Type: 'success', 'error', 'warning', 'info'
   * @param {Object} options - Additional options
   * @param {number} options.duration - Duration in ms (default: 5000)
   * @param {boolean} options.dismissible - Show close button (default: true)
   * @param {string} options.title - Optional title
   * @returns {Element} The toast element
   *
   * @example
   * showToast('Data saved successfully', 'success')
   * showToast('Connection failed', 'error', { duration: 10000 })
   */
  function showToast(message, type = 'info', options = {}) {
    const {
      duration = TOAST_CONFIG.duration,
      dismissible = true,
      title = null
    } = options;

    const container = getToastContainer();
    const icon = TOAST_ICONS[type] || TOAST_ICONS.info;
    const safeMessage = escapeForToast(message);
    const safeTitle = title ? escapeForToast(title) : null;

    // Limit number of visible toasts
    const existingToasts = container.querySelectorAll('.toast, .flash-message');
    if (existingToasts.length >= TOAST_CONFIG.maxToasts) {
      existingToasts[0].remove();
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type} flash-message flash-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');

    // Build toast HTML
    let html = `
      <span class="toast-icon flash-icon">
        <i class="fas ${icon}"></i>
      </span>
      <div class="toast-content">
    `;

    if (safeTitle) {
      html += `<strong class="toast-title">${safeTitle}</strong>`;
    }

    html += `<span class="toast-message flash-text">${safeMessage}</span></div>`;

    if (dismissible) {
      html += `
        <button class="toast-close flash-close" type="button" aria-label="Close">
          <i class="fas fa-times"></i>
        </button>
      `;
    }

    toast.innerHTML = html;
    container.appendChild(toast);

    // Bind close button
    if (dismissible) {
      const closeBtn = toast.querySelector('.toast-close, .flash-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => {
          dismissToast(toast);
        });
      }
    }

    // Auto-dismiss
    if (duration > 0) {
      setTimeout(() => {
        if (toast.parentElement) {
          dismissToast(toast);
        }
      }, duration);
    }

    return toast;
  }

  /**
   * Dismiss a toast with animation.
   *
   * @param {Element} toast - Toast element to dismiss
   */
  function dismissToast(toast) {
    if (!toast) return;

    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';

    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 300);
  }

  /**
   * Clear all visible toasts.
   */
  function clearAllToasts() {
    const container = getToastContainer();
    const toasts = container.querySelectorAll('.toast, .flash-message');
    toasts.forEach(toast => dismissToast(toast));
  }

  /**
   * Show a success toast.
   *
   * @param {string} message - Message to display
   * @param {Object} options - Additional options
   * @returns {Element} The toast element
   */
  function showSuccess(message, options = {}) {
    return showToast(message, 'success', options);
  }

  /**
   * Show an error toast.
   *
   * @param {string} message - Message to display
   * @param {Object} options - Additional options
   * @returns {Element} The toast element
   */
  function showError(message, options = {}) {
    return showToast(message, 'error', { duration: 8000, ...options });
  }

  /**
   * Show a warning toast.
   *
   * @param {string} message - Message to display
   * @param {Object} options - Additional options
   * @returns {Element} The toast element
   */
  function showWarning(message, options = {}) {
    return showToast(message, 'warning', options);
  }

  /**
   * Show an info toast.
   *
   * @param {string} message - Message to display
   * @param {Object} options - Additional options
   * @returns {Element} The toast element
   */
  function showInfo(message, options = {}) {
    return showToast(message, 'info', options);
  }

  // Export to window for global access
  window.NotificationUtils = {
    showToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    dismissToast,
    clearAllToasts,
    TOAST_CONFIG,
    TOAST_ICONS,
    TOAST_COLORS
  };

  // Export main function for convenience
  window.showToast = showToast;
  window.showNotification = showToast; // Alias

})();
