"""
Batch Analytics Endpoints
=========================

Endpoints for batch operations on analytics data.
"""
import logging
from flask import request

from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_analytics_service as _analytics_service,
    get_actuator_service as _actuator_service,
)
from app.blueprints.api.analytics import analytics_api

logger = logging.getLogger(__name__)


# ============================================================================
# BATCH OPERATIONS
# ============================================================================

@analytics_api.get('/batch/failure-predictions')
def get_batch_failure_predictions():
    """
    Get failure predictions for all or filtered actuators.
    
    Query params:
    - unit_id: Optional unit filter
    - threshold: Minimum risk score (default: 0.0)
    - risk_level: Filter by level (low/medium/high/critical)
    
    Returns:
    - List of actuators with predictions
    - Sorted by risk score (highest first)
    - Summary statistics
    """
    try:
        unit_id = request.args.get('unit_id', type=int)
        threshold = request.args.get('threshold', 0.0, type=float)
        risk_level = request.args.get('risk_level')
        
        if threshold < 0.0 or threshold > 1.0:
            return _fail("threshold must be between 0.0 and 1.0", 400)
        
        if risk_level and risk_level not in ['low', 'medium', 'high', 'critical']:
            return _fail("risk_level must be one of: low, medium, high, critical", 400)
        
        actuator_svc = _actuator_service()
        analytics = _analytics_service()
        
        actuators = actuator_svc.list_actuators(unit_id=unit_id) if unit_id else actuator_svc.list_actuators()
        
        predictions = []
        for actuator in actuators:
            try:
                actuator_id = actuator['actuator_id']
                prediction = analytics.predict_device_failure(actuator_id)
                
                # Apply filters
                if prediction['risk_score'] >= threshold:
                    if not risk_level or prediction['risk_level'] == risk_level:
                        predictions.append({
                            'actuator_id': actuator_id,
                            'actuator_name': actuator.get('name'),
                            'actuator_type': actuator.get('actuator_type'),
                            'prediction': prediction
                        })
            except Exception as e:
                logger.warning(f"Failed to predict for actuator {actuator_id}: {e}")
        
        # Sort by risk score (highest first)
        predictions.sort(key=lambda x: x['prediction']['risk_score'], reverse=True)
        
        return _success({
            'unit_id': unit_id,
            'threshold': threshold,
            'risk_level_filter': risk_level,
            'predictions': predictions,
            'count': len(predictions),
            'high_risk_count': len([p for p in predictions if p['prediction']['risk_level'] in ['high', 'critical']])
        })
        
    except Exception as e:
        logger.error(f"Error getting batch predictions: {e}", exc_info=True)
        return _fail(str(e), 500)
