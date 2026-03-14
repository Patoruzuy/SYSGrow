/**
 * Notifications Page
 * ==================
 * Full page for viewing and managing all notifications and irrigation requests.
 */

(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    PAGE_SIZE: 20,
    POLL_INTERVAL: 60000,
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

  // Notification type to filter mapping
  const TYPE_FILTERS = {
    irrigation: ['irrigation_confirm', 'irrigation_feedback', 'plant_needs_water'],
    alerts: ['threshold_exceeded', 'low_battery', 'device_offline', 'plant_health_warning'],
    system: ['system_alert', 'harvest_ready'],
  };

  // Severity classes
  const SEVERITY_CLASS = {
    info: 'info',
    warning: 'warning',
    critical: 'critical',
    success: 'success',
  };

  // State
  let notifications = [];
  let currentFilter = 'all';
  let currentPage = 1;
  let totalCount = 0;
  let unreadCount = 0;

  // DOM elements
  let listContainer, countDisplay, pagination, paginationInfo;

  /**
   * Initialize the page
   */
  function init() {
    listContainer = document.getElementById('notifications-list');
    countDisplay = document.getElementById('notifications-count');
    pagination = document.getElementById('pagination');
    paginationInfo = document.getElementById('pagination-info');

    // Bind event listeners
    bindEventListeners();

    // Load initial data
    loadNotifications();

    console.log('[NotificationsPage] Initialized');
  }

  /**
   * Bind event listeners
   */
  function bindEventListeners() {
    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        currentPage = 1;
        loadNotifications();
      });
    });

    // Mark all read
    document.getElementById('mark-all-read')?.addEventListener('click', markAllAsRead);

    // Refresh
    document.getElementById('refresh-notifications')?.addEventListener('click', () => {
      loadNotifications();
    });

    // Clear all
    document.getElementById('clear-all')?.addEventListener('click', clearAllNotifications);

    // Pagination
    document.getElementById('prev-page')?.addEventListener('click', () => {
      if (currentPage > 1) {
        currentPage--;
        loadNotifications();
      }
    });

    document.getElementById('next-page')?.addEventListener('click', () => {
      const totalPages = Math.ceil(totalCount / CONFIG.PAGE_SIZE);
      if (currentPage < totalPages) {
        currentPage++;
        loadNotifications();
      }
    });
  }

  /**
   * Load notifications from API
   */
  async function loadNotifications() {
    showLoading();

    try {
      const offset = (currentPage - 1) * CONFIG.PAGE_SIZE;
      let url = `/api/settings/notifications/messages?limit=${CONFIG.PAGE_SIZE}&offset=${offset}`;

      // Add filter if not 'all'
      if (currentFilter === 'unread') {
        url += '&unread_only=true';
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (data.ok && data.data) {
        notifications = data.data.notifications || [];
        // API doesn't return total_count, use array length
        totalCount = notifications.length;
        unreadCount = data.data.unread_count || 0;

        // Apply client-side filter for type filters
        if (currentFilter !== 'all' && currentFilter !== 'unread') {
          const filterTypes = TYPE_FILTERS[currentFilter] || [];
          notifications = notifications.filter(n => filterTypes.includes(n.notification_type));
          totalCount = notifications.length;
        }

        renderNotifications();
        updateCount();
        updatePagination();
      } else if (data.ok === false) {
        // API returned an error - show empty state with message
        console.warn('[NotificationsPage] API error:', data.error?.message);
        notifications = [];
        totalCount = 0;
        unreadCount = 0;
        renderNotifications();
        updateCount();
        updatePagination();
      } else {
        // Unexpected response format - show empty state
        notifications = [];
        totalCount = 0;
        unreadCount = 0;
        renderNotifications();
        updateCount();
        updatePagination();
      }
    } catch (err) {
      console.error('[NotificationsPage] Error loading notifications:', err);
      // On error, show empty state rather than error message
      notifications = [];
      totalCount = 0;
      unreadCount = 0;
      renderNotifications();
      updateCount();
      updatePagination();
    }
  }

  /**
   * Show loading state
   */
  function showLoading() {
    if (!listContainer) return;
    listContainer.innerHTML = `
      <div class="notifications-loading">
        <i class="fas fa-spinner fa-spin"></i>
      </div>
    `;
  }

  /**
   * Show error state
   */
  function showError(message) {
    if (!listContainer) return;
    listContainer.innerHTML = `
      <div class="notifications-empty">
        <i class="fas fa-exclamation-circle"></i>
        <h3>Error</h3>
        <p>${window.escapeHtml(message)}</p>
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
        <div class="notifications-empty">
          <i class="fas fa-bell-slash"></i>
          <h3>No Notifications</h3>
          <p>You're all caught up!</p>
        </div>
      `;
      return;
    }

    listContainer.innerHTML = notifications.map(n => renderNotificationItem(n)).join('');
    attachListeners();
  }

  /**
   * Render a single notification item
   */
  function renderNotificationItem(notification) {
    const isUnread = !notification.in_app_read;
    const icon = TYPE_ICONS[notification.notification_type] || 'fa-bell';
    const severityClass = SEVERITY_CLASS[notification.severity] || 'info';
    const timeAgo = window.formatTimeAgo(notification.created_at);
    const typeLabel = formatNotificationType(notification.notification_type);

    let actionsHtml = '';
    let extraContent = '';

    // Render action buttons based on notification type
    if (notification.requires_action && !notification.action_taken) {
      if (notification.action_type === 'irrigation_approval') {
        actionsHtml = renderIrrigationApprovalActions(notification);
        extraContent = renderIrrigationRequestInfo(notification);
      } else if (notification.action_type === 'irrigation_feedback') {
        actionsHtml = renderIrrigationFeedbackActions(notification);
      }
    }

    return `
      <div class="notification-item ${isUnread ? 'unread' : ''}"
           data-message-id="${notification.message_id}"
           data-notification-type="${notification.notification_type}">
        <div class="notification-item-expanded">
          <div class="notification-icon ${severityClass}">
            <i class="fas ${icon}" aria-hidden="true"></i>
          </div>
          <div class="notification-content">
            <h4 class="notification-title">${window.escapeHtml(notification.title)}</h4>
            <p class="notification-message">${window.escapeHtml(notification.message)}</p>
            <div class="notification-meta">
              <span class="notification-time">${timeAgo}</span>
              <span class="tag ${isUnread ? 'unread' : ''}">${typeLabel}</span>
              ${isUnread ? '<span class="tag unread">Unread</span>' : ''}
            </div>
            ${extraContent}
            ${actionsHtml}
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render irrigation request info card
   */
  function renderIrrigationRequestInfo(notification) {
    const actionData = notification.action_data ? JSON.parse(notification.action_data) : {};

    if (!actionData.soil_moisture) return '';

    let scheduledDisplay = 'Not set';
    if (actionData.scheduled_time) {
      try {
        const dt = new Date(actionData.scheduled_time);
        scheduledDisplay = dt.toLocaleString([], {
          dateStyle: 'short',
          timeStyle: 'short'
        });
      } catch (e) {}
    }

    return `
      <div class="irrigation-request-card">
        <dl class="request-info">
          <div>
            <dt>Soil Moisture</dt>
            <dd>${actionData.soil_moisture?.toFixed(1) || '-'}%</dd>
          </div>
          <div>
            <dt>Threshold</dt>
            <dd>${actionData.threshold?.toFixed(1) || '-'}%</dd>
          </div>
          <div>
            <dt>Scheduled</dt>
            <dd>${scheduledDisplay}</dd>
          </div>
        </dl>
      </div>
    `;
  }

  /**
   * Render irrigation approval actions
   */
  function renderIrrigationApprovalActions(notification) {
    const actionData = notification.action_data ? JSON.parse(notification.action_data) : {};
    const requestId = actionData.request_id;

    if (!requestId) return '';

    return `
      <div class="notification-actions irrigation-approval-actions">
        <button class="notification-action-btn primary irrigation-action"
                data-action="approve"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}">
          <i class="fas fa-check"></i> Approve
        </button>
        <button class="notification-action-btn irrigation-action"
                data-action="delay"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}">
          <i class="fas fa-clock"></i> Delay 1h
        </button>
        <button class="notification-action-btn danger irrigation-action"
                data-action="cancel"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}">
          <i class="fas fa-times"></i> Cancel
        </button>
      </div>
    `;
  }

  /**
   * Render irrigation feedback actions
   */
  function renderIrrigationFeedbackActions(notification) {
    const actionData = notification.action_data ? JSON.parse(notification.action_data) : {};
    const requestId = actionData.request_id || actionData.feedback_id;

    return `
      <div class="irrigation-feedback-actions">
        <button class="irrigation-feedback-btn too-little"
                data-feedback="too_little"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}">
          <i class="fas fa-tint-slash"></i>
          <span>Too Little</span>
        </button>
        <button class="irrigation-feedback-btn just-right"
                data-feedback="just_right"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}">
          <i class="fas fa-check-circle"></i>
          <span>Just Right</span>
        </button>
        <button class="irrigation-feedback-btn too-much"
                data-feedback="too_much"
                data-request-id="${requestId}"
                data-message-id="${notification.message_id}">
          <i class="fas fa-water"></i>
          <span>Too Much</span>
        </button>
      </div>
    `;
  }

  /**
   * Attach event listeners to notification items
   */
  function attachListeners() {
    // Click to mark as read
    listContainer.querySelectorAll('.notification-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('.notification-actions, .irrigation-feedback-actions')) return;

        const messageId = item.dataset.messageId;
        if (item.classList.contains('unread')) {
          markAsRead(messageId);
          item.classList.remove('unread');
        }
      });
    });

    // Irrigation approval actions
    listContainer.querySelectorAll('.irrigation-action').forEach(btn => {
      btn.addEventListener('click', handleIrrigationAction);
    });

    // Irrigation feedback actions
    listContainer.querySelectorAll('.irrigation-feedback-btn').forEach(btn => {
      btn.addEventListener('click', handleFeedbackAction);
    });
  }

  /**
   * Handle irrigation approval action
   */
  async function handleIrrigationAction(e) {
    e.stopPropagation();

    const btn = e.currentTarget;
    const action = btn.dataset.action;
    const requestId = btn.dataset.requestId;
    const messageId = btn.dataset.messageId;

    if (!requestId) return;

    const container = btn.closest('.irrigation-approval-actions');
    const originalHtml = container.innerHTML;

    try {
      container.querySelectorAll('button').forEach(b => b.disabled = true);
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      await API.Irrigation.handleAction(requestId, action);

      const messages = {
        approve: 'Approved',
        delay: 'Delayed',
        cancel: 'Cancelled',
      };

      container.innerHTML = `
        <span class="notification-action-taken">
          <i class="fas fa-check"></i> ${messages[action]}
        </span>
      `;

      markAsRead(messageId);
      window.showToast(`Irrigation ${messages[action].toLowerCase()}`, 'success');
    } catch (err) {
      console.error('[NotificationsPage] Error:', err);
      container.innerHTML = originalHtml;
      attachListeners();
      window.showToast(err.message || 'Action failed', 'error');
    }
  }

  /**
   * Handle irrigation feedback action
   */
  async function handleFeedbackAction(e) {
    e.stopPropagation();

    const btn = e.currentTarget;
    const feedback = btn.dataset.feedback;
    const requestId = btn.dataset.requestId;
    const messageId = btn.dataset.messageId;

    const container = btn.closest('.irrigation-feedback-actions');

    try {
      container.querySelectorAll('button').forEach(b => b.disabled = true);
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      await API.Irrigation.submitFeedback(requestId, feedback);

      const labels = { too_little: 'Too little', just_right: 'Just right', too_much: 'Too much' };
      container.innerHTML = `
        <span class="notification-action-taken">
          <i class="fas fa-check"></i> Thanks! (${labels[feedback]})
        </span>
      `;

      markAsRead(messageId);
      window.showToast('Feedback submitted', 'success');
    } catch (err) {
      console.error('[NotificationsPage] Error:', err);
      loadNotifications(); // Reload on error
      window.showToast(err.message || 'Failed to submit feedback', 'error');
    }
  }

  /**
   * Mark notification as read
   */
  async function markAsRead(messageId) {
    try {
      await API.Notification.markAsRead(messageId);
      unreadCount = Math.max(0, unreadCount - 1);
      updateCount();
    } catch (err) {
      console.error('[NotificationsPage] Error marking as read:', err);
    }
  }

  /**
   * Mark all as read
   */
  async function markAllAsRead() {
    try {
      await API.Notification.markAllAsRead();
      listContainer.querySelectorAll('.notification-item.unread').forEach(item => {
        item.classList.remove('unread');
      });
      unreadCount = 0;
      updateCount();
      window.showToast('All notifications marked as read', 'success');
    } catch (err) {
      console.error('[NotificationsPage] Error:', err);
      window.showToast('Failed to mark all as read', 'error');
    }
  }

  /**
   * Clear all notifications
   */
  async function clearAllNotifications() {
    if (!confirm('Are you sure you want to clear all notifications?')) return;

    try {
      await API.Notification.clearAll();
      notifications = [];
      totalCount = 0;
      unreadCount = 0;
      renderNotifications();
      updateCount();
      updatePagination();
      window.showToast('All notifications cleared', 'success');
    } catch (err) {
      console.error('[NotificationsPage] Error:', err);
      window.showToast('Failed to clear notifications', 'error');
    }
  }

  /**
   * Update count display
   */
  function updateCount() {
    if (!countDisplay) return;

    const filterLabel = currentFilter === 'all' ? '' : ` (${currentFilter})`;
    const unreadLabel = unreadCount > 0 ? ` - ${unreadCount} unread` : '';
    countDisplay.textContent = `${totalCount} notifications${filterLabel}${unreadLabel}`;
  }

  /**
   * Update pagination
   */
  function updatePagination() {
    if (!pagination) return;

    const totalPages = Math.ceil(totalCount / CONFIG.PAGE_SIZE);

    if (totalPages <= 1) {
      pagination.style.display = 'none';
      return;
    }

    pagination.style.display = 'flex';
    paginationInfo.textContent = `Page ${currentPage} of ${totalPages}`;

    document.getElementById('prev-page').disabled = currentPage <= 1;
    document.getElementById('next-page').disabled = currentPage >= totalPages;
  }

  /**
   * Format notification type for display
   */
  function formatNotificationType(type) {
    const labels = {
      low_battery: 'Battery',
      plant_needs_water: 'Water',
      irrigation_confirm: 'Irrigation',
      irrigation_feedback: 'Feedback',
      threshold_exceeded: 'Alert',
      device_offline: 'Device',
      harvest_ready: 'Harvest',
      plant_health_warning: 'Health',
      system_alert: 'System',
    };
    return labels[type] || 'Notification';
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
