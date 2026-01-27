"""
ML Analytics API
================
ML performance metrics, statistics, and insights.

Consolidates functionality from:
- ai_predictions.py (disease statistics)
- disease.py (statistics, trends endpoints)
- insights.py (energy analytics, dashboard)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from flask import Blueprint, jsonify, request

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

analytics_bp = Blueprint("ml_analytics", __name__, url_prefix="/api/ml/analytics")


@analytics_bp.get("/disease/statistics")
def get_disease_statistics():
    """
    Get disease occurrence statistics and trends.

    Query params:
    - days: Number of days to analyze (default: 90)
    - unit_id: Optional unit ID filter
    """
    try:
        container = _container()
        ai_health_repo = container.ai_health_repo

        days = request.args.get("days", 90, type=int)
        unit_id = request.args.get("unit_id", type=int)

        stats = ai_health_repo.get_disease_statistics(days=days, unit_id=unit_id)

        return _success(stats)

    except Exception as e:
        logger.error(f"Error getting disease statistics: {e}", exc_info=True)
        return _fail(str(e), 500)


@analytics_bp.get("/disease/trends")
def get_disease_trends():
    """
    Get disease occurrence trends over time.

    Query params:
    - days: Number of days to analyze (default: 30)
    - unit_id: Optional unit ID filter
    - disease_type: Optional disease type filter

    Returns:
    - daily_counts: Daily disease occurrence counts
    - disease_totals: Total counts by disease type
    - period_days: Number of days analyzed
    """
    try:
        container = _container()
        db_handler = container.database_handler

        days = request.args.get("days", 30, type=int)
        unit_id = request.args.get("unit_id", type=int)
        disease_type = request.args.get("disease_type", type=str)

        trends = _calculate_disease_trends(db_handler, days, unit_id, disease_type)

        return _success(trends)

    except Exception as e:
        logger.error(f"Error getting disease trends: {e}", exc_info=True)
        return _fail(str(e), 500)


def _calculate_disease_trends(
    db_handler,
    days: int,
    unit_id: Optional[int] = None,
    disease_type: Optional[str] = None
) -> dict:
    """Calculate disease trends over time."""
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
            SELECT
                DATE(observation_date) as date,
                disease_type,
                COUNT(*) as count,
                AVG(severity_level) as avg_severity
            FROM PlantHealthLogs
            WHERE observation_date >= ?
            AND disease_type IS NOT NULL
        """

        params = [start_date]

        if unit_id:
            query += " AND unit_id = ?"
            params.append(unit_id)

        if disease_type:
            query += " AND disease_type = ?"
            params.append(disease_type)

        query += " GROUP BY DATE(observation_date), disease_type ORDER BY date"

        rows = db_handler.execute_query(query, tuple(params))

        daily_data = {}
        disease_totals = {}

        for row in rows:
            row_dict = dict(row)
            date = row_dict['date']
            dtype = row_dict['disease_type']
            count = row_dict['count']

            if date not in daily_data:
                daily_data[date] = {'total': 0, 'by_type': {}}

            daily_data[date]['total'] += count
            daily_data[date]['by_type'][dtype] = count

            disease_totals[dtype] = disease_totals.get(dtype, 0) + count

        daily_counts = [
            {
                'date': date,
                'total': data['total'],
                'by_type': data['by_type']
            }
            for date, data in sorted(daily_data.items())
        ]

        return {
            'daily_counts': daily_counts,
            'disease_totals': disease_totals,
            'period_days': days
        }

    except Exception as e:
        logger.warning(f"Error calculating trends: {e}")
        return {'daily_counts': [], 'disease_totals': {}, 'period_days': days}


@analytics_bp.get("/energy/actuator/<int:actuator_id>/dashboard")
def get_actuator_energy_dashboard(actuator_id: int):
    """
    Get unified energy dashboard for an actuator.
    
    Combines:
    - Cost trends (7 days)
    - Optimization recommendations
    - Recent anomalies (24 hours)
    - Current power status
    """
    try:
        container = _container()
        analytics = container.analytics_service
        
        dashboard = analytics.get_actuator_energy_dashboard(actuator_id)
        
        return _success({
            'actuator_id': actuator_id,
            'dashboard': dashboard
        })
        
    except Exception as e:
        logger.error(f"Error getting energy dashboard: {e}", exc_info=True)
        return _fail(str(e), 500)


@analytics_bp.get("/energy/actuator/<int:actuator_id>/predict-failure")
def predict_actuator_failure(actuator_id: int):
    """
    Predict device failure risk for an actuator.
    
    Query params:
    - days_ahead: Number of days to predict (default: 7)
    """
    try:
        days_ahead = request.args.get('days_ahead', 7, type=int)
        
        container = _container()
        analytics = container.analytics_service
        
        prediction = analytics.predict_device_failure(actuator_id, days_ahead)
        
        return _success({
            'actuator_id': actuator_id,
            'prediction': prediction
        })
        
    except Exception as e:
        logger.error(f"Error predicting failure: {e}", exc_info=True)
        return _fail(str(e), 500)
