"""
Actuator Predictive Analytics
==============================

Endpoints for predictive analytics and failure prediction using the AnalyticsService.
Provides comprehensive dashboards and proactive maintenance insights.
"""
from __future__ import annotations

from flask import current_app, request
from app.utils.http import success_response, error_response
import logging

from ...devices import devices_api

logger = logging.getLogger("devices_api.actuators.analytics")


def _analytics_service():
    """Get analytics service from container"""
    return current_app.config["CONTAINER"].analytics_service


def _actuator_service():
    """Get actuator management service from container"""
    return current_app.config["CONTAINER"].actuator_management_service


def _success(data: dict | list | None = None, status: int = 200):
    """Return success response"""
    return success_response(data, status)


def _fail(message: str, status: int = 500):
    """Return error response"""
    return error_response(message, status)


# ==================== ANALYTICS SERVICE ENDPOINTS ====================

@devices_api.get("/analytics/actuators/<int:actuator_id>/dashboard")
def get_analytics_actuator_dashboard(actuator_id: int):
    """
    Get comprehensive energy dashboard using AnalyticsService directly.
    
    **Phase 5 Endpoint**: Uses AnalyticsService for unified analytics.
    """
    try:
        analytics_service = _analytics_service()
        dashboard = analytics_service.get_actuator_energy_dashboard(actuator_id)
        return _success(dashboard)
        
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.get("/analytics/actuators/<int:actuator_id>/predict-failure")
def predict_actuator_failure(actuator_id: int):
    """
    Predict device failure risk using analytics and historical data.
    
    **Phase 5 NEW**: Predictive analytics for proactive maintenance.
    
    Query Parameters:
    - days_ahead: Number of days to predict (default: 7)
    """
    try:
        days_ahead = request.args.get('days_ahead', 7, type=int)
        
        if days_ahead < 1 or days_ahead > 30:
            return _fail("days_ahead must be between 1 and 30", 400)
        
        analytics_service = _analytics_service()
        prediction = analytics_service.predict_device_failure(actuator_id, days_ahead)
        
        return _success(prediction)
        
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.get("/analytics/actuators/predict-failures")
def predict_all_actuator_failures():
    """
    Predict failure risk for all actuators or filtered by unit.
    
    **Phase 5 NEW**: Batch prediction for maintenance planning.
    
    Query Parameters:
    - unit_id: Optional unit ID to filter (default: all actuators)
    - threshold: Minimum risk score to include (0.0-1.0, default: 0.0)
    - risk_level: Filter by risk level ('low', 'medium', 'high', 'critical')
    """
    try:
        unit_id = request.args.get('unit_id', type=int)
        threshold = request.args.get('threshold', 0.0, type=float)
        risk_level = request.args.get('risk_level', type=str)
        
        if threshold < 0.0 or threshold > 1.0:
            return _fail("threshold must be between 0.0 and 1.0", 400)
        
        if risk_level and risk_level not in ['low', 'medium', 'high', 'critical']:
            return _fail("risk_level must be one of: low, medium, high, critical", 400)
        
        analytics_service = _analytics_service()
        
        # Get all actuators for unit or all units
        actuator_svc = _actuator_service()
        actuators = actuator_svc.list_actuators(unit_id=unit_id)
        
        # Generate predictions for all actuators
        predictions = []
        for actuator in actuators:
            try:
                prediction = analytics_service.predict_device_failure(actuator['actuator_id'])
                
                # Apply filters
                if prediction['risk_score'] >= threshold:
                    if not risk_level or prediction['risk_level'] == risk_level:
                        predictions.append(prediction)
            except Exception as e:
                logger.warning(f"Failed to predict for actuator {actuator['actuator_id']}: {e}")
        
        # Sort by risk score (highest first)
        predictions.sort(key=lambda x: x['risk_score'], reverse=True)
        
        return _success({
            'unit_id': unit_id,
            'threshold': threshold,
            'risk_level_filter': risk_level,
            'predictions': predictions,
            'count': len(predictions),
            'high_risk_count': len([p for p in predictions if p['risk_level'] in ['high', 'critical']])
        })
        
    except Exception as e:
        return _fail(str(e), 500)
