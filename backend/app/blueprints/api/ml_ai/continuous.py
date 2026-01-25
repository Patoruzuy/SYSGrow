"""
Continuous Monitoring API
=========================
Endpoints for managing continuous AI monitoring service.
"""

import logging
from flask import Blueprint, request

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

continuous_bp = Blueprint("ml_continuous", __name__, url_prefix="/api/ml/continuous")


def _get_monitoring_service():
    """Get continuous monitoring service from container."""
    container = _container()
    if not container:
        return None
    return getattr(container, 'continuous_monitoring', None)


# ==============================================================================
# MONITORING CONTROL
# ==============================================================================

@continuous_bp.get("/status")
def get_status():
    """
    Get current status of continuous monitoring service.
    
    Returns:
        {
            "running": bool,
            "monitored_units": [int],
            "check_interval_seconds": int,
            "total_insights_generated": int
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _success({
                "running": False,
                "monitored_units": [],
                "message": "Continuous monitoring service is not enabled"
            })
        
        return _success({
            "running": service._running,
            "monitored_units": service._monitored_units,
            "check_interval_seconds": service.check_interval,
            "total_insights_generated": sum(
                len(insights) for insights in service._insights.values()
            )
        })
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}", exc_info=True)
        return _fail(str(e), 500)


@continuous_bp.post("/start")
def start_monitoring():
    """
    Start continuous monitoring.
    
    Request body:
        {
            "unit_ids": [int] (optional, null = all units)
        }
    
    Returns:
        {
            "started": true,
            "monitored_units": [int]
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _fail("Continuous monitoring service is not enabled", 503)
        
        data = request.get_json() or {}
        unit_ids = data.get('unit_ids')
        
        service.start_monitoring(unit_ids)
        
        return _success({
            "started": True,
            "monitored_units": service._monitored_units
        })
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}", exc_info=True)
        return _fail(str(e), 500)


@continuous_bp.post("/stop")
def stop_monitoring():
    """
    Stop continuous monitoring.
    
    Returns:
        {
            "stopped": true
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _fail("Continuous monitoring service is not enabled", 503)
        
        service.stop_monitoring()
        
        return _success({"stopped": True})
        
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}", exc_info=True)
        return _fail(str(e), 500)


@continuous_bp.post("/units/<int:unit_id>/add")
def add_unit(unit_id: int):
    """
    Add a unit to continuous monitoring.
    
    Returns:
        {
            "added": true,
            "unit_id": int,
            "monitored_units": [int]
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _fail("Continuous monitoring service is not enabled", 503)
        
        service.add_unit(unit_id)
        
        return _success({
            "added": True,
            "unit_id": unit_id,
            "monitored_units": service._monitored_units
        })
        
    except Exception as e:
        logger.error(f"Error adding unit {unit_id} to monitoring: {e}", exc_info=True)
        return _fail(str(e), 500)


@continuous_bp.post("/units/<int:unit_id>/remove")
def remove_unit(unit_id: int):
    """
    Remove a unit from continuous monitoring.
    
    Returns:
        {
            "removed": true,
            "unit_id": int,
            "monitored_units": [int]
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _fail("Continuous monitoring service is not enabled", 503)
        
        service.remove_unit(unit_id)
        
        return _success({
            "removed": True,
            "unit_id": unit_id,
            "monitored_units": service._monitored_units
        })
        
    except Exception as e:
        logger.error(f"Error removing unit {unit_id} from monitoring: {e}", exc_info=True)
        return _fail(str(e), 500)


# ==============================================================================
# INSIGHTS
# ==============================================================================

@continuous_bp.get("/insights")
def get_all_insights():
    """
    Get insights from all monitored units.
    
    Query params:
    - insight_type: Filter by type (prediction, alert, recommendation, trend)
    - alert_level: Filter by level (info, warning, critical)
    - limit: Max insights per unit (default 20)
    
    Returns:
        {
            "insights": {
                "unit_id": [...]
            },
            "total_count": int
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _success({
                "insights": {},
                "total_count": 0,
                "message": "Continuous monitoring service is not enabled"
            })
        
        insight_type = request.args.get('insight_type')
        alert_level = request.args.get('alert_level')
        limit = request.args.get('limit', 20, type=int)
        
        all_insights = {}
        total_count = 0
        
        for unit_id in service._monitored_units:
            insights = service.get_insights(
                unit_id=unit_id,
                insight_type=insight_type,
                alert_level=alert_level,
                limit=limit
            )
            all_insights[str(unit_id)] = [i.to_dict() for i in insights]
            total_count += len(insights)
        
        return _success({
            "insights": all_insights,
            "total_count": total_count
        })
        
    except Exception as e:
        logger.error(f"Error getting insights: {e}", exc_info=True)
        return _fail(str(e), 500)


@continuous_bp.get("/insights/<int:unit_id>")
def get_unit_insights(unit_id: int):
    """
    Get insights for a specific unit.
    
    Query params:
    - insight_type: Filter by type (prediction, alert, recommendation, trend)
    - alert_level: Filter by level (info, warning, critical)
    - limit: Max insights (default 50)
    
    Returns:
        {
            "unit_id": int,
            "insights": [...],
            "count": int
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _success({
                "unit_id": unit_id,
                "insights": [],
                "count": 0,
                "message": "Continuous monitoring service is not enabled"
            })
        
        insight_type = request.args.get('insight_type')
        alert_level = request.args.get('alert_level')
        limit = request.args.get('limit', 50, type=int)
        
        insights = service.get_insights(
            unit_id=unit_id,
            insight_type=insight_type,
            alert_level=alert_level,
            limit=limit
        )
        
        return _success({
            "unit_id": unit_id,
            "insights": [i.to_dict() for i in insights],
            "count": len(insights)
        })
        
    except Exception as e:
        logger.error(f"Error getting insights for unit {unit_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@continuous_bp.get("/insights/critical")
def get_critical_insights():
    """
    Get all critical-level insights across all units.
    
    Query params:
    - limit: Max insights (default 50)
    
    Returns:
        {
            "insights": [...],
            "count": int
        }
    """
    try:
        service = _get_monitoring_service()
        
        if not service:
            return _success({
                "insights": [],
                "count": 0,
                "message": "Continuous monitoring service is not enabled"
            })
        
        limit = request.args.get('limit', 50, type=int)
        
        all_critical = []
        
        for unit_id in service._monitored_units:
            insights = service.get_insights(
                unit_id=unit_id,
                alert_level='critical',
                limit=limit
            )
            all_critical.extend([i.to_dict() for i in insights])
        
        # Sort by timestamp descending
        all_critical.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return _success({
            "insights": all_critical[:limit],
            "count": len(all_critical)
        })
        
    except Exception as e:
        logger.error(f"Error getting critical insights: {e}", exc_info=True)
        return _fail(str(e), 500)
