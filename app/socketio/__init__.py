"""
Socket.IO Event Handlers
========================

Centralized Socket.IO namespace handlers for real-time communication.

Namespaces:
- / (default) - General app events
- /dashboard - Dashboard-specific updates
- /devices - Device management events
- /notifications - User notifications
- /session - Session management
- /alerts - System alerts
- /system - System monitoring (includes ML monitoring events)

Usage:
    Import this module after socketio.init_app() to register all handlers.

    from app.socketio import register_handlers
    register_handlers()
"""

import logging

logger = logging.getLogger(__name__)


def register_handlers():
    """
    Register all Socket.IO event handlers.

    This function must be called AFTER socketio.init_app() to ensure
    the Flask app context is available for all handlers.
    """
    # Import handlers to trigger @socketio.on() decorator registration
    from . import (
        ml_handlers,
        sensor_handlers,
    )
    # from . import notification_handlers
    # from . import alert_handlers

    logger.info("✅ Socket.IO handlers registered (core, system/ml)")
