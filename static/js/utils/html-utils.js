/**
 * HTML Utility Functions
 * ======================
 * Centralized HTML escaping and manipulation utilities.
 * Replaces duplicate implementations across components.
 *
 * @module utils/html-utils
 */
(function () {
  'use strict';

  /**
   * Escape HTML special characters to prevent XSS.
   * Uses DOM textContent assignment for reliable escaping.
   *
   * @param {any} text - Text to escape (coerced to string)
   * @returns {string} Escaped HTML-safe text
   *
   * @example
   * escapeHtml('<script>alert("xss")</script>')
   * // Returns: '&lt;script&gt;alert("xss")&lt;/script&gt;'
   */
  function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  /**
   * Escape text for use in HTML attributes.
   * Handles quotes and special characters for safe attribute values.
   *
   * @param {any} text - Text to escape
   * @returns {string} Escaped attribute-safe text
   *
   * @example
   * escapeHtmlAttr('value with "quotes"')
   * // Returns: 'value with &quot;quotes&quot;'
   */
  function escapeHtmlAttr(text) {
    if (text == null) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  /**
   * Strip HTML tags from a string, returning plain text.
   *
   * @param {string} html - HTML string to strip
   * @returns {string} Plain text content
   *
   * @example
   * stripHtml('<p>Hello <strong>world</strong></p>')
   * // Returns: 'Hello world'
   */
  function stripHtml(html) {
    if (!html) return '';
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || div.innerText || '';
  }

  /**
   * Safely set innerHTML with escaped content.
   * Useful when you need to set text content but the container
   * might have other HTML structure.
   *
   * @param {Element} element - Target element
   * @param {string} text - Text to set (will be escaped)
   */
  function setTextSafe(element, text) {
    if (!element) return;
    element.textContent = text == null ? '' : String(text);
  }

  /**
   * Create an HTML element with safe text content.
   *
   * @param {string} tag - Element tag name
   * @param {string} text - Text content (safely set)
   * @param {Object} attributes - Optional attributes to set
   * @returns {Element} Created element
   *
   * @example
   * createElementWithText('span', 'Hello', { class: 'greeting' })
   */
  function createElementWithText(tag, text, attributes = {}) {
    const element = document.createElement(tag);
    element.textContent = text == null ? '' : String(text);
    for (const [key, value] of Object.entries(attributes)) {
      if (key === 'class') {
        element.className = value;
      } else if (key === 'data') {
        for (const [dataKey, dataValue] of Object.entries(value)) {
          element.dataset[dataKey] = dataValue;
        }
      } else {
        element.setAttribute(key, value);
      }
    }
    return element;
  }

  // Export to window for global access
  window.HtmlUtils = {
    escapeHtml,
    escapeHtmlAttr,
    stripHtml,
    setTextSafe,
    createElementWithText
  };

  // Also export individual functions for convenience
  window.escapeHtml = escapeHtml;
  window.escapeHtmlAttr = escapeHtmlAttr;
  window.stripHtml = stripHtml;

})();
