"""
Unified Analytics API
=====================

Comprehensive analytics endpoints for environmental monitoring, energy tracking,
and plant health insights. Designed for dashboard charts and data visualization.

Features:
- Sensor analytics (temperature, humidity, soil moisture, CO2, VOC)
- Actuator energy analytics (consumption, costs, efficiency)
- Environmental trends and correlations
- Comparative analytics across units
- Predictive analytics for failure detection
- Aggregated statistics and time-series data

All endpoints support unit_id filtering for multi-unit installations.
"""
import logging
from flask import Blueprint

logger = logging.getLogger(__name__)

# Create the blueprint
analytics_api = Blueprint('analytics_api', __name__, url_prefix='/api/analytics')

# Import routes after blueprint creation to avoid circular imports
from app.blueprints.api.analytics import sensors  # noqa: F401, E402
from app.blueprints.api.analytics import actuators  # noqa: F401, E402
from app.blueprints.api.analytics import batch  # noqa: F401, E402
from app.blueprints.api.analytics import dashboard  # noqa: F401, E402
from app.blueprints.api.analytics import efficiency  # noqa: F401, E402

# Re-export for backwards compatibility
__all__ = ['analytics_api']
