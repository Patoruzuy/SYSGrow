/**
 * help-banner.js
 * ============================================================================
 * Manages the collapsible help-banner component.
 *
 * Behaviour:
 *  - On first visit the banner renders fully (CSS default).
 *  - Clicking the × dismiss button collapses it to an icon-pill and writes a
 *    flag to localStorage so it stays collapsed on subsequent page loads.
 *  - Hovering over the collapsed pill re-expands it (handled by CSS
 *    .help-banner--collapsed:hover rules in components.css).
 *
 * Storage key format:  sysgrow_help_banner_<banner-id>
 */
(function () {
  'use strict';

  const STORAGE_PREFIX = 'sysgrow_help_banner_';

  function init() {
    document.querySelectorAll('.help-banner[data-banner-id]').forEach(function (banner) {
      var id = banner.dataset.bannerId;
      if (!id) return;

      // Restore collapsed state from previous visit (no flash because this runs
      // before first paint only when the DOM is ready but before repaint).
      if (localStorage.getItem(STORAGE_PREFIX + id) === '1') {
        banner.classList.add('help-banner--collapsed');
      }

      // Wire up the dismiss button.
      var dismissBtn = banner.querySelector('.help-banner-dismiss');
      if (dismissBtn) {
        dismissBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          banner.classList.add('help-banner--collapsed');
          try {
            localStorage.setItem(STORAGE_PREFIX + id, '1');
          } catch (_) {
            // Private browsing or storage quota exceeded — ignore silently.
          }
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
