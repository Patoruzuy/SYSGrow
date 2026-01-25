/**
 * Modal Utility
 * ============================================================================
 * - Backdrop click closes
 * - Close button closes
 * - ESC closes (single global keydown listener)
 * - Restores focus to previously focused element
 *
 * Requirement:
 * Your CSS should show/hide based on ".modal.active" (avoid inline display:none).
 */
(function () {
  'use strict';

  const Modal = {
    _openStack: [],
    _keydownBound: false,
    _lastActiveElement: null,

    open(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) {
        console.warn(`[Modal] Modal not found: ${modalId}`);
        return;
      }

      try {
        this._lastActiveElement = document.activeElement;

        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';

        this._setupCloseHandlers(modal, modalId);
        this._ensureKeydownListener();

        // Track open modals (top-most closes first)
        if (!this._openStack.includes(modalId)) this._openStack.push(modalId);

        // Focus management (best-effort)
        this._focusFirstFocusable(modal);

        modal.dispatchEvent(new CustomEvent('modal:opened', { detail: { modalId } }));
      } catch (error) {
        console.warn('[Modal] Failed to open modal:', error);
      }
    },

    close(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) {
        console.warn(`[Modal] Modal not found: ${modalId}`);
        return;
      }

      try {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');

        this._openStack = this._openStack.filter((id) => id !== modalId);

        if (this._openStack.length === 0) {
          document.body.style.overflow = '';
        }

        // Restore focus
        if (this._lastActiveElement && typeof this._lastActiveElement.focus === 'function') {
          this._lastActiveElement.focus();
        }
        this._lastActiveElement = null;

        modal.dispatchEvent(new CustomEvent('modal:closed', { detail: { modalId } }));
      } catch (error) {
        console.warn('[Modal] Failed to close modal:', error);
      }
    },

    toggle(modalId) {
      if (this.isOpen(modalId)) this.close(modalId);
      else this.open(modalId);
    },

    closeAll() {
      // Close in reverse order to mimic "stack" semantics
      [...this._openStack].reverse().forEach((id) => this.close(id));
    },

    isOpen(modalId) {
      const modal = document.getElementById(modalId);
      return Boolean(modal && modal.classList.contains('active'));
    },

    _setupCloseHandlers(modal, modalId) {
      // Prevent duplicate wiring
      if (modal.dataset.handlersSetup === 'true') return;
      modal.dataset.handlersSetup = 'true';

      const closeBtn = modal.querySelector('.modal-close, [data-modal-close]');
      if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
          e.preventDefault();
          this.close(modalId);
        });
      }

      // Backdrop click: click on the modal container (not dialog content)
      modal.addEventListener('click', (e) => {
        if (e.target === modal) this.close(modalId);
      });
    },

    _ensureKeydownListener() {
      if (this._keydownBound) return;
      this._keydownBound = true;

      document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;

        // Close top-most modal only (more predictable UX)
        const top = this._openStack[this._openStack.length - 1];
        if (top) this.close(top);
      });
    },

    _focusFirstFocusable(modal) {
      try {
        const focusable = modal.querySelector(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable && typeof focusable.focus === 'function') focusable.focus();
      } catch {
        // ignore
      }
    },
  };

  window.Modal = Modal;
})();
