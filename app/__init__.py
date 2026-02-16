from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

from flask import Flask, request

from app.blueprints.api.blog import blog_api
from app.blueprints.api.dashboard import dashboard_api
from app.blueprints.api.devices import devices_api
from app.blueprints.api.growth import growth_api
from app.blueprints.api.harvest_routes import harvest_bp
from app.blueprints.api.help import help_api

# Import new consolidated ML/AI endpoints
from app.blueprints.api.ml_ai import (
    ab_testing_bp,
    analysis_bp,
    analytics_bp,
    base_bp,
    continuous_bp,
    models_bp,
    monitoring_bp,
    personalized_bp,
    predictions_bp,
    readiness_bp,
    retraining_bp,
    training_data_bp,
)
from app.blueprints.api.plants import plants_api
from app.blueprints.api.plants.disease import disease_bp
from app.blueprints.api.settings import settings_api
from app.blueprints.auth.routes import auth_bp
from app.blueprints.ui.routes import ui_bp
from app.config import load_config, setup_logging
from app.extensions import init_extensions, socketio
from app.middleware.health_tracking import init_health_tracking
from app.middleware.rate_limiting import init_rate_limiting
from app.middleware.api_auth import init_api_write_protection
from app.middleware.response_validation import init_response_validation
from app.middleware.security_headers import init_security_headers
from app.security.csrf import CSRFMiddleware
from app.security.login_limiter import LoginLimiter

# Import health API
try:
    from app.blueprints.api.health import health_api
except ImportError:
    health_api = None

try:
    from app.blueprints.api.analytics import analytics_api
except ImportError:
    analytics_api = None

try:
    from app.blueprints.api.irrigation import irrigation_bp
except ImportError:
    irrigation_bp = None

ml_components_available = True


def create_app(config_overrides: dict[str, Any] | None = None, *, bootstrap_runtime: bool = False) -> Flask:
    config = load_config()
    if config_overrides:
        for key, value in config_overrides.items():
            setattr(config, key.lower(), value)

    # Configure logging early so container startup (MQTT connect/subscriptions, hardware bootstrap)
    # is visible in the terminal and sysgrow.log.
    setup_logging(debug=config.DEBUG)

    base_path = Path(__file__).resolve().parent.parent
    flask_app = Flask(__name__, static_folder=str(base_path / "static"), template_folder=str(base_path / "templates"))
    flask_app.config.update(config.as_flask_config())

    # Session configuration for "Remember Me" functionality
    flask_app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=config.session_lifetime_remember_days)
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    flask_app.config["SESSION_COOKIE_SECURE"] = config.environment == "production"

    # Non-permanent session timeout (applies when "Remember Me" is NOT checked)
    flask_app.config["SESSION_TIMEOUT_MINUTES"] = config.session_lifetime_default_minutes

    # Reject request bodies larger than configured limit (default 16 MB)
    flask_app.config["MAX_CONTENT_LENGTH"] = config.max_upload_mb * 1024 * 1024

    # Disable template caching for development
    flask_app.config["TEMPLATES_AUTO_RELOAD"] = True
    flask_app.jinja_env.auto_reload = True
    flask_app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # Initialize Socket.IO BEFORE building ServiceContainer (EmitterService needs it)
    init_extensions(flask_app, config.socketio_cors_origins)

    from app.services.container import ServiceContainer

    container = ServiceContainer.build(config, start_coordinator=bootstrap_runtime)
    flask_app.config["CONTAINER"] = container

    # Initialize health tracking middleware
    init_health_tracking(flask_app, container.system_health_service)

    # Initialize response envelope validation middleware
    # Set strict_mode=False for development (logs warnings), True for production (returns 500)
    init_response_validation(flask_app, strict_mode=config.DEBUG is False)

    # Initialize request rate limiting (IP-based, in-memory)
    limiter = init_rate_limiting(flask_app, enabled=config.rate_limit_enabled)
    limiter.config.default_limit = config.rate_limit_default_limit
    limiter.config.default_window = config.rate_limit_default_window_seconds
    limiter.config.burst_limit = config.rate_limit_burst

    # Initialize security response headers (X-Frame-Options, CSP, nosniff, etc.)
    init_security_headers(flask_app, enable_hsts=getattr(config, "enable_hsts", False))

    # Enforce authentication on all API write endpoints (POST/PUT/DELETE/PATCH)
    init_api_write_protection(flask_app)

    # Login brute-force protection (IP-based, in-memory)
    flask_app.config["LOGIN_LIMITER"] = LoginLimiter(
        max_attempts=config.login_max_attempts,
        lockout_minutes=config.login_lockout_minutes,
    )

    CSRFMiddleware(
        exempt_endpoints={"auth.login", "auth.register"},
        exempt_blueprints={
            # Public/read-only endpoints remain exempt
            "health_api",
            "help_api",
            "blog_api",
            # ML endpoints remain exempt (mostly read operations, lower risk)
            "ml_predictions",
            "ml_base",
            "ml_models",
            "ml_monitoring",
            "ml_analytics",
            "ml_retraining",
            "ml",
            "ml_analysis",
            "ml_ab_testing",
            "ml_continuous",
            "ml_personalized",
            "ml_training_data",
            "ml_readiness",
            # API endpoints (JSON-based, use auth tokens instead of CSRF)
            "devices_api",
            "growth_api",
            "plants_api",
            "settings_api",
            "dashboard_api",
        },
    ).init_app(flask_app)

    # Global JSON error handler — catches any unhandled exception on /api/
    # routes and returns a generic message instead of leaking stack traces.
    @flask_app.errorhandler(Exception)
    def _handle_unhandled(exc):  # noqa: ANN001, ANN202
        if not request.path.startswith("/api/"):
            raise exc  # Let Flask's default HTML error pages handle UI routes
        from app.utils.http import safe_error

        return safe_error(exc, 500, context="unhandled")

    @flask_app.errorhandler(413)
    def _handle_too_large(_exc):  # noqa: ANN001, ANN202
        from app.utils.http import error_response

        return error_response("Request payload too large", 413)

    # Register core blueprints
    flask_app.register_blueprint(auth_bp, url_prefix="/auth")
    flask_app.register_blueprint(harvest_bp)
    flask_app.register_blueprint(ui_bp)
    flask_app.register_blueprint(plants_api, url_prefix="/api/plants")
    flask_app.register_blueprint(disease_bp)  # Already has /api/plants/disease prefix
    flask_app.register_blueprint(settings_api, url_prefix="/api/settings")
    flask_app.register_blueprint(growth_api, url_prefix="/api/growth")
    flask_app.register_blueprint(devices_api, url_prefix="/api/devices")
    flask_app.register_blueprint(dashboard_api, url_prefix="/api/dashboard")

    # Register consolidated ML/AI blueprints
    flask_app.register_blueprint(base_bp)  # /api/ml (health, training history)
    flask_app.register_blueprint(predictions_bp)  # /api/ml/predictions
    flask_app.register_blueprint(models_bp)  # /api/ml/models
    flask_app.register_blueprint(monitoring_bp)  # /api/ml/monitoring
    flask_app.register_blueprint(analytics_bp)  # /api/ml/analytics
    flask_app.register_blueprint(retraining_bp)  # /api/ml/retraining
    flask_app.register_blueprint(analysis_bp)  # /api/ml/analysis
    flask_app.register_blueprint(readiness_bp)  # /api/ml/readiness
    flask_app.register_blueprint(ab_testing_bp)  # /api/ml/ab-testing
    flask_app.register_blueprint(continuous_bp)  # /api/ml/continuous
    flask_app.register_blueprint(personalized_bp)  # /api/ml/personalized
    flask_app.register_blueprint(training_data_bp)  # /api/ml/training-data

    # Register health API if available
    if health_api:
        flask_app.register_blueprint(health_api)  # Already has /api/health prefix

    # Register Help and Blog APIs (public access, no auth required)
    flask_app.register_blueprint(help_api)  # /api/help
    flask_app.register_blueprint(blog_api)  # /api/blog

    # Register Socket.IO event handlers (must be after socketio init)
    from app.socketio import register_handlers

    register_handlers()

    # List all registered blueprints
    for bp_name, bp in flask_app.blueprints.items():
        logging.info(f" Registered blueprint: {bp_name}")

    # Register analytics API if available
    if analytics_api is not None:
        flask_app.register_blueprint(analytics_api)  # Already has /api/analytics prefix

    # Register irrigation workflow API if available
    if irrigation_bp is not None:
        flask_app.register_blueprint(irrigation_bp)  # Already has /api/irrigation prefix

    if bootstrap_runtime:
        _initialize_hardware_runtimes(flask_app, container)
    else:
        logging.info("Skipping hardware bootstrap (bootstrap_runtime=False)")

    logger = logging.getLogger(__name__)
    logger.info("SYSGrow application initialized successfully.")
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    return flask_app


def _initialize_hardware_runtimes(flask_app: Flask, container) -> None:
    """Start hardware runtimes for all active growth units."""
    with flask_app.app_context():
        try:
            logging.info(" Initializing hardware runtimes for active growth units...")
            active_units = container.growth_service.list_units()

            for unit in active_units:
                unit_id = unit.get("unit_id")
                unit_name = unit.get("name", f"Unit {unit_id}")

                try:
                    if container.growth_service.start_unit_runtime(unit_id):
                        logging.info(f"   Started runtime for unit {unit_id} ({unit_name})")
                    else:
                        logging.error(f"   Failed to start runtime for unit {unit_id}")
                except Exception as exc:
                    logging.error(f"   Failed to start runtime for unit {unit_id}: {exc}")

            logging.info(" Hardware initialization complete: %s units operational", len(active_units))

        except Exception as exc:
            logging.error(" Failed to initialize hardware runtimes: %s", exc)
            # Continue app startup even if hardware initialization fails
            # This allows the UI to be accessible for debugging


__all__ = ["create_app", "socketio"]
