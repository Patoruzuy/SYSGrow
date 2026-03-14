/**
 * Notifications Component
 * =======================
 * Handles the notification bell dropdown in the header.
 * Loads notifications from the API, displays them, and handles user actions.
 */

(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    POLL_INTERVAL: 60000, // Poll every 60 seconds
    MAX_DISPLAY: 10,      // Max notifications to show in dropdown
  };

  // Notification type icons
  const TYPE_ICONS = {
    low_battery: 'fa-battery-quarter',
    plant_needs_water: 'fa-tint',
    irrigation_confirm: 'fa-faucet',
    irrigation_feedback: 'fa-hand-holding-water',
    threshold_exceeded: 'fa-exclamation-triangle',
    device_offline: 'fa-plug',
    harvest_ready: 'fa-seedling',
    plant_health_warning: 'fa-heartbeat',
    system_alert: 'fa-bell',
  };

  // Severity to icon class mapping
  const SEVERITY_CLASS = {
    info: 'info',
    warning: 'warning',
    critical: 'critical',
  };

  // State
  let isOpen = false;
  let notifications = [];
  let unreadCount = 0;
  let pollTimer = null;

  // DOM Elements
  let toggleBtn, dropdown, badge, listContainer;

  /**
   * Initialize the notifications component
   */
  function init() {
    toggleBtn = document.getElementById('notifications-toggle');
    dropdown = document.getElementById('notifications-dropdown');
    badge = document.getElementById('notification-badge');
    listContainer = document.getElementById('notifications-list');

    if (!toggleBtn || !dropdown) return;

    // Event listeners
    toggleBtn.addEventListener('click', toggleDropdown);
    document.addEventListener('click', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);

    // Mark all read button
    const markAllBtn = document.getElementById('mark-all-read-btn');
    if (markAllBtn) {
      markAllBtn.addEventListener('click', markAllAsRead);
    }

    // Initial load
    loadNotifications();

    // Start polling
    startPolling();

    // Listen for WebSocket notifications
    listenForSocketNotifications();

    console.log('[Notifications] Component initialized');
  }

  /**
   * Toggle dropdown visibility
   */
  function toggleDropdown(e) {
    e.stopPropagation();
    isOpen = !isOpen;

    toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    dropdown.setAttribute('aria-hidden', isOpen ? 'false' : 'true');

    if (isOpen) {
      loadNotifications();
    }
  }

  /**
   * Close dropdown when clicking outside
   */
  function handleOutsideClick(e) {
    if (!isOpen) return;

    if (!dropdown.contains(e.target) && !toggleBtn.contains(e.target)) {
      closeDropdown();
    }
  }

  /**
   * Close dropdown on Escape key
   */
  function handleEscape(e) {
    if (e.key === 'Escape' && isOpen) {
      closeDropdown();
      toggleBtn.focus();
    }
  }

  /**
   * Close the dropdown
   */
  function closeDropdown() {
    isOpen = false;
    toggleBtn.setAttribute('aria-expanded', 'false');
    dropdown.setAttribute('aria-hidden', 'true');
  }

  /**
   * Load notifications from API
   */
  async function loadNotifications() {
    try {
      showLoading();

      const data = await API.Notification.getMessages({ limit: CONFIG.MAX_DISPLAY });

      if (data) {
        notifications = data.notifications || [];
        unreadCount = data.unread_count || 0;
        updateBadge();
        renderNotifications();
      } else {
        // API returned error or unexpected format - show empty state
        notifications = [];
        unreadCount = 0;
        updateBadge();
        renderNotifications();
      }
    } catch (err) {
      console.error('[Notifications] Error loading:', err);
      // On error, show empty state instead of error message
      notifications = [];
      unreadCount = 0;
      updateBadge();
      renderNotifications();
    }
  }

  /**
   * Update the badge count
   */
  function updateBadge() {
    if (!badge) return;

    if (unreadCount > 0) {
      badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }

  /**
   * Show loading state
   */
  function showLoading() {
    if (!listContainer) return;
    listContainer.innerHTML = `
      <div class="notification-loading">
        <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
      </div>
    `;
  }

  /**
   * Show error state
   */
  function showError(message) {
    if (!listContainer) return;
    listContainer.innerHTML = `
      <div class="notification-empty">
        <i class="fas fa-exclamation-circle" aria-hidden="true"></i>
        <p>${message}</p>
      </div>
    `;
  }

  /**
   * Render notifications list
   */
  function renderNotifications() {
    if (!listContainer) return;

    if (notifications.length === 0) {
      listContainer.innerHTML = `
        <div class="notification-empty">
          <i class="fas fa-bell-slash" aria-hidden="true"></i>
          <p>No notifications</p>
        </div>
      `;
      return;
    }

    listContainer.innerHTML = notifications.map(n => renderNotificationItem(n)).join('');

    // Attach event listeners
    attachNotificationListeners();
  }

  /**
   * Render a single notification item
   */
  function renderNotificationItem(notification) {
    const isUnread = !notification.in_app_read;
    const icon = TYPE_ICONS[notification.notification_type] || 'fa-bell';
    const severityClass = SEVERITY_CLASS[notification.severity] || 'info';
    const timeAgo = window.formatTimeAgo(notification.created_at);

    let actionsHtml = '';

    // Render action buttons based on notification type
    if (notification.requires_action && !notification.action_taken) {
      if (notification.action_type === 'irrigation_confirm') {
        actionsHtml = renderIrrigationConfirmActions(notification);
      } else if (notification.action_type === 'irrigation_feedback') {
        actionsHtml = renderIrrigationFeedbackActions(notification);
      }
    }

    return `
      <div class="notification-item ${isUnread ? 'unread' : ''}"
           data-message-id="${notification.message_id}"
           data-notification-type="${notification.notification_type}">
        <div class="notification-icon ${severityClass}">
          <i class="fas ${icon}" aria-hidden="true"></i>
        </div>
        <div class="notification-content">
          <h4 class="notification-title">${window.escapeHtml(notification.title)}</h4>
          <p class="notification-message">${window.escapeHtml(notification.message)}</p>
          <span class="notification-time">${timeAgo}</span>
          ${actionsHtml}
        </div>
      </div>
    `;
  }

  /**
   * Render irrigation confirmation actions (approve/delay/cancel)
   */
  function renderIrrigationConfirmActions(notification) {
    const actionData = notification.action_data ? JSON.parse(notification.action_data) : {};
    const requestId = actionData.request_id;
    const scheduledTime = actionData.scheduled_time;

    // Format scheduled time for display
    let scheduledDisplay = '';
    if (scheduledTime) {
      try {
        const dt = new Date(scheduledTime);
        scheduledDisplay = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        scheduledDisplay = '21:00';
      }
    }

    return `
      <div class="notification-actions irrigation-approval-actions">
        <button class="notification-action-btn primary irrigation-action"
                data-action="approve"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}"
                title="Approve irrigation at ${scheduledDisplay}">
          <i class="fas fa-check" aria-hidden="true"></i>
          Approve
        </button>
        <button class="notification-action-btn irrigation-action"
                data-action="delay"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}"
                title="Delay by 1 hour">
          <i class="fas fa-clock" aria-hidden="true"></i>
          Delay
        </button>
        <button class="notification-action-btn danger irrigation-action"
                data-action="cancel"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}"
                title="Cancel irrigation">
          <i class="fas fa-times" aria-hidden="true"></i>
          Cancel
        </button>
      </div>
    `;
  }

  /**
   * Render irrigation feedback actions
   */
  function renderIrrigationFeedbackActions(notification) {
    const actionData = notification.action_data ? JSON.parse(notification.action_data) : {};
    const feedbackId = actionData.feedback_id;

    return `
      <div class="irrigation-feedback-actions">
        <button class="irrigation-feedback-btn too-little"
                data-feedback="too_little"
                data-feedback-id="${feedbackId}"
                data-message-id="${notification.message_id}"
                title="Not enough water">
          <i class="fas fa-tint-slash" aria-hidden="true"></i>
          <span>Too Little</span>
        </button>
        <button class="irrigation-feedback-btn just-right"
                data-feedback="just_right"
                data-feedback-id="${feedbackId}"
                data-message-id="${notification.message_id}"
                title="Perfect amount">
          <i class="fas fa-check-circle" aria-hidden="true"></i>
          <span>Just Right</span>
        </button>
        <button class="irrigation-feedback-btn too-much"
                data-feedback="too_much"
                data-feedback-id="${feedbackId}"
                data-message-id="${notification.message_id}"
                title="Too much water">
          <i class="fas fa-water" aria-hidden="true"></i>
          <span>Too Much</span>
        </button>
      </div>
    `;
  }

  /**
   * Attach event listeners to notification items
   */
  function attachNotificationListeners() {
    // Click to mark as read
    listContainer.querySelectorAll('.notification-item').forEach(item => {
      item.addEventListener('click', (e) => {
        // Don't mark as read if clicking action buttons
        if (e.target.closest('.notification-actions, .irrigation-feedback-actions')) return;

        const messageId = item.dataset.messageId;
        if (item.classList.contains('unread')) {
          markAsRead(messageId);
        }
      });
    });

    // Irrigation approval actions (approve/delay/cancel)
    listContainer.querySelectorAll('.irrigation-action').forEach(btn => {
      btn.addEventListener('click', handleIrrigationAction);
    });

    // Legacy irrigation confirm actions (for backwards compatibility)
    listContainer.querySelectorAll('.notification-action-btn:not(.irrigation-action)').forEach(btn => {
      btn.addEventListener('click', handleActionResponse);
    });

    // Irrigation feedback actions
    listContainer.querySelectorAll('.irrigation-feedback-btn').forEach(btn => {
      btn.addEventListener('click', handleFeedbackResponse);
    });
  }

  /**
   * Mark a notification as read
   */
  async function markAsRead(messageId) {
    try {
      await API.Notification.markAsRead(messageId);
      // Update local state
      const item = listContainer.querySelector(`[data-message-id="${messageId}"]`);
      if (item) {
        item.classList.remove('unread');
      }
      unreadCount = Math.max(0, unreadCount - 1);
      updateBadge();
    } catch (err) {
      console.error('[Notifications] Error marking as read:', err);
    }
  }

  /**
   * Mark all notifications as read
   */
  async function markAllAsRead(e) {
    e.stopPropagation();

    try {
      await API.Notification.markAllAsRead();
      // Update local state
      listContainer.querySelectorAll('.notification-item.unread').forEach(item => {
        item.classList.remove('unread');
      });
      unreadCount = 0;
      updateBadge();
    } catch (err) {
      console.error('[Notifications] Error marking all as read:', err);
    }
  }

  /**
   * Handle irrigation workflow action (approve/delay/cancel)
   */
  async function handleIrrigationAction(e) {
    e.stopPropagation();

    const btn = e.currentTarget;
    const action = btn.dataset.action;
    const requestId = btn.dataset.requestId;
    const messageId = btn.dataset.messageId;

    if (!requestId) {
      console.error('[Notifications] Missing request ID for irrigation action');
      return;
    }

    const originalContent = btn.innerHTML;

    try {
      // Disable all buttons in the container
      const container = btn.closest('.irrigation-approval-actions');
      container.querySelectorAll('button').forEach(b => b.disabled = true);
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      // Call irrigation workflow API
      const data = await API.Irrigation.handleAction(requestId, action);

      // Replace buttons with success message
      const actionMessages = {
        approve: 'Irrigation approved',
        delay: data.delayed_until ? `Delayed to ${formatDelayedTime(data.delayed_until)}` : 'Delayed by 1 hour',
        cancel: 'Irrigation cancelled',
      };

      container.innerHTML = `
        <span class="notification-action-taken">
          <i class="fas fa-check" aria-hidden="true"></i>
          ${actionMessages[action]}
        </span>
      `;

      // Mark notification as read
      markAsRead(messageId);

      // Show toast for feedback
      const toastMessages = {
        approve: 'Irrigation approved! Will execute at scheduled time.',
        delay: 'Irrigation delayed.',
        cancel: 'Irrigation cancelled.',
      };
      window.showToast(toastMessages[action], action === 'cancel' ? 'warning' : 'success');
    } catch (err) {
      console.error('[Notifications] Error handling irrigation action:', err);
      const container = btn.closest('.irrigation-approval-actions');
      container.querySelectorAll('button').forEach(b => b.disabled = false);
      btn.innerHTML = originalContent;
      window.showToast('Connection error', 'error');
    }
  }

  /**
   * Format delayed time for display
   */
  function formatDelayedTime(isoString) {
    try {
      const dt = new Date(isoString);
      return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return 'later';
    }
  }

  /**
   * Handle action response (confirm/cancel irrigation) - Legacy
   */
  async function handleActionResponse(e) {
    e.stopPropagation();

    const btn = e.currentTarget;
    const action = btn.dataset.action;
    const messageId = btn.dataset.messageId;

    try {
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      await API.Notification.respondToAction(messageId, action);

      // Remove actions from this notification
      const actionsContainer = btn.closest('.notification-actions');
      if (actionsContainer) {
        actionsContainer.innerHTML = `
          <span class="notification-action-taken">
            <i class="fas fa-check" aria-hidden="true"></i>
            ${action === 'confirm' ? 'Irrigation started' : 'Skipped'}
          </span>
        `;
      }
      // Mark as read
      markAsRead(messageId);
    } catch (err) {
      console.error('[Notifications] Error handling action:', err);
      btn.disabled = false;
      window.showToast('Connection error', 'error');
    }
  }

  /**
   * Handle irrigation feedback response
   */
  async function handleFeedbackResponse(e) {
    e.stopPropagation();

    const btn = e.currentTarget;
    const feedback = btn.dataset.feedback;
    const feedbackId = btn.dataset.feedbackId;
    const messageId = btn.dataset.messageId;

    try {
      // Disable all feedback buttons
      const container = btn.closest('.irrigation-feedback-actions');
      container.querySelectorAll('button').forEach(b => b.disabled = true);
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      await API.Notification.submitIrrigationFeedback(feedbackId, feedback);

      // Replace buttons with thank you message
      const feedbackLabels = {
        too_little: 'Too little',
        just_right: 'Just right',
        too_much: 'Too much',
      };

      container.innerHTML = `
        <span class="notification-action-taken">
          <i class="fas fa-check" aria-hidden="true"></i>
          Thanks! (${feedbackLabels[feedback]})
        </span>
      `;

      // Also respond to the notification action
      await API.Notification.respondToAction(messageId, feedback);

      markAsRead(messageId);
      window.showToast('Feedback submitted! This helps improve irrigation.', 'success');
    } catch (err) {
      console.error('[Notifications] Error submitting feedback:', err);
      const container = btn.closest('.irrigation-feedback-actions');
      container.querySelectorAll('button').forEach(b => b.disabled = false);
      window.showToast('Connection error', 'error');
    }
  }

  /**
   * Restore feedback button content
   */
  function renderFeedbackButtonContent(btn, feedback) {
    const icons = {
      too_little: 'fa-tint-slash',
      just_right: 'fa-check-circle',
      too_much: 'fa-water',
    };
    const labels = {
      too_little: 'Too Little',
      just_right: 'Just Right',
      too_much: 'Too Much',
    };
    btn.innerHTML = `
      <i class="fas ${icons[feedback]}" aria-hidden="true"></i>
      <span>${labels[feedback]}</span>
    `;
  }

  /**
   * Start polling for new notifications
   */
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(() => {
      // Only poll if dropdown is closed
      if (!isOpen) {
        fetchUnreadCount();
      }
    }, CONFIG.POLL_INTERVAL);
  }

  /**
   * Fetch just the unread count (lightweight)
   */
  async function fetchUnreadCount() {
    try {
      const data = await API.Notification.getMessages({ limit: 1 });
      unreadCount = data?.unread_count || 0;
      updateBadge();
    } catch (err) {
      // Silent fail for background polling
    }
  }

  /**
   * Listen for real-time WebSocket notifications
   */
  function listenForSocketNotifications() {
    // Check if socket.io is available
    if (typeof io === 'undefined') return;

    try {
      const socket = io('/notifications', {
        transports: ['polling'],
        reconnection: true,
      });

      socket.on('notification', (data) => {
        console.log('[Notifications] Received WebSocket notification:', data);

        // Increment unread count
        unreadCount++;
        updateBadge();

        // If dropdown is open, reload notifications
        if (isOpen) {
          loadNotifications();
        }

        // Show toast for important notifications
        if (data.severity === 'critical' || data.severity === 'warning') {
          window.showToast(data.title, data.severity === 'critical' ? 'error' : 'warning');
        }
      });

      socket.on('connect', () => {
        console.log('[Notifications] WebSocket connected');
      });

      socket.on('disconnect', () => {
        console.log('[Notifications] WebSocket disconnected');
      });
    } catch (err) {
      console.warn('[Notifications] WebSocket setup failed:', err);
    }
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for debugging
  window.NotificationsComponent = {
    reload: loadNotifications,
    getUnreadCount: () => unreadCount,
  };

})();
