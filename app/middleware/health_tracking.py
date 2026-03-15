"""
Health Tracking Middleware
===========================
Flask middleware for automatic API request tracking and health monitoring.

This middleware records metrics for all API requests except health check endpoints.

Author: SYSGrow Team
Date: December 2025
"""

import logging
import time
from flask import Flask, request, g
from typing import Optional

logger = logging.getLogger(__name__)


def init_health_tracking(app: Flask, system_health_service) -> None:
    """
    Initialize health tracking middleware for Flask application.
    
    Args:
        app: Flask application instance
        system_health_service: SystemHealthService instance for metric tracking
    """
    if not system_health_service:
        logger.warning("SystemHealthService not provided, health tracking disabled")
        return
    
    # Store service reference in app config for access in handlers
    app.config['SYSTEM_HEALTH_SERVICE'] = system_health_service
    
    @app.before_request
    def before_request_handler():
        """Record request start time."""
        # Skip health endpoints to avoid circular tracking
        if request.path.startswith('/api/health'):
            return
        
        # Store request start time
        g.request_start_time = time.time()
    
    @app.after_request
    def after_request_handler(response):
        """Record request completion and metrics."""
        # Skip health endpoints
        if request.path.startswith('/api/health'):
            return response
        
        # Skip if start time not set (shouldn't happen, but safety check)
        if not hasattr(g, 'request_start_time'):
            return response
        
        # Calculate response time
        response_time = (time.time() - g.request_start_time) * 1000  # Convert to ms
        
        # Determine if request was successful (2xx or 3xx status codes)
        success = 200 <= response.status_code < 400
        
        # Record metrics
        try:
            service = app.config.get('SYSTEM_HEALTH_SERVICE')
            if service:
                service.record_api_request(success, response_time)
                service.check_api_health()
        except Exception as e:
            # Don't fail the request if metrics recording fails
            logger.error(f"Failed to record API metrics: {e}")
        
        return response
    
    @app.teardown_request
    def teardown_request_handler(exception=None):
        """Handle request errors."""
        # Skip health endpoints
        if request.path.startswith('/api/health'):
            return
        
        # If there was an exception and we have start time, record as failed request
        if exception is not None and hasattr(g, 'request_start_time'):
            response_time = (time.time() - g.request_start_time) * 1000
            try:
                service = app.config.get('SYSTEM_HEALTH_SERVICE')
                if service:
                    service.record_api_request(False, response_time)
                    service.check_api_health()
            except Exception as e:
                logger.error(f"Failed to record failed request metrics: {e}")
    
    logger.info("Health tracking middleware initialized")
