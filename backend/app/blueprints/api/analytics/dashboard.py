"""
Dashboard Summary Endpoints
===========================

Endpoints for dashboard cards and summary views.
"""
import logging
from datetime import datetime, timedelta, timezone
from flask import request

from app.utils.time import iso_now
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_analytics_service as _analytics_service,
    get_actuator_service as _actuator_service,
)
from app.blueprints.api.analytics import analytics_api

logger = logging.getLogger(__name__)


# ============================================================================
# DASHBOARD SUMMARY ENDPOINTS
# ============================================================================

@analytics_api.get('/dashboard/environmental-summary')
def get_environmental_summary():
    """
    Get environmental conditions summary for dashboard cards.
    
    Query params:
    - unit_id: Optional unit filter
    
    Returns:
    - Current conditions (latest readings)
    - 24h averages and trends
    - Alert conditions
    - Health indicators
    """
    try:
        unit_id = request.args.get('unit_id', type=int)
        analytics = _analytics_service()
        
        # Logic moved to service
        data = analytics.get_environmental_dashboard_summary(unit_id=unit_id)
        
        return _success(data)
        
    except Exception as e:
        logger.error(f"Error getting environmental summary: {e}", exc_info=True)
        return _fail(str(e), 500)


@analytics_api.get('/dashboard/energy-summary')
def get_energy_summary():
    """
    Get energy consumption summary for dashboard cards.
    
    Query params:
    - unit_id: Optional unit filter
    - days: Days to analyze (default: 7)
    
    Returns:
    - Total cost for period
    - Top consumers
    - Cost trends
    - Optimization opportunities
    """
    try:
        unit_id = request.args.get('unit_id', type=int)
        days = request.args.get('days', 7, type=int)
        
        analytics = _analytics_service()
        
        # Logic moved to service
        data = analytics.get_energy_dashboard_summary(unit_id=unit_id, days=days)
        
        return _success(data)
        
    except Exception as e:
        logger.error(f"Error getting energy summary: {e}", exc_info=True)
        return _fail(str(e), 500)
