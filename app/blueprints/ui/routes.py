from __future__ import annotations

import logging
from urllib.parse import urlparse

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from app.blueprints.ui.helpers import get_unit_card_data
from app.security.auth import login_required

ui_bp = Blueprint("ui", __name__)
logger = logging.getLogger(__name__)


def _container():
    return current_app.config["CONTAINER"]


@ui_bp.app_context_processor
def inject_unit_context():
    try:
        selected_unit_id, units = _ensure_selected_unit()
        selected_unit = None
        if selected_unit_id is not None:
            selected_unit = _container().growth_service.get_unit(selected_unit_id)
        return {
            "nav_units": units,
            "nav_selected_unit_id": selected_unit_id,
            "nav_selected_unit": selected_unit,
        }
    except Exception:
        # Fail safe: don't break template rendering
        return {
            "nav_units": [],
            "nav_selected_unit_id": None,
            "nav_selected_unit": None,
        }


def _normalize_unit_entry(unit_obj):
    """Ensure unit entries are dicts with at least unit_id and name."""
    if isinstance(unit_obj, dict):
        return unit_obj
    try:
        if hasattr(unit_obj, "to_dict"):
            return unit_obj.to_dict()
        return {
            "unit_id": getattr(unit_obj, "unit_id", None) or getattr(unit_obj, "id", None),
            "name": getattr(unit_obj, "name", "Unit"),
            "location": getattr(unit_obj, "location", "Indoor"),
        }
    except Exception:  # pragma: no cover - defensive
        return {"unit_id": None, "name": "Unit", "location": "Unknown"}


def _ensure_selected_unit():
    """Ensure a selected unit is in session; return (unit_id, units)."""
    raw_units = _container().growth_service.list_units()
    units = [_normalize_unit_entry(u) for u in (raw_units or [])]
    logger.debug("Units available: %s", units)
    if not units:
        return None, units
    selected = session.get("selected_unit")
    if selected is None:
        first_unit = units[0]
        candidate = first_unit.get("unit_id") if isinstance(first_unit, dict) else getattr(first_unit, "unit_id", None)
        if candidate is None:
            logger.warning("Unable to resolve unit_id from first unit entry")
            return None, units
        selected = candidate
        session["selected_unit"] = selected
    try:
        return int(selected), units
    except (TypeError, ValueError):
        logger.warning("Selected unit id is invalid: %s", selected)
        return None, units


def _api_success(data=None, status: int = 200):
    return jsonify({"ok": True, "data": data, "error": None}), status


def _api_error(message: str, status: int = 400):
    return jsonify({"ok": False, "data": None, "error": {"message": message}}), status


def _render_page_with_units(template_name: str, **extra_context):
    """Helper to render pages with standard unit context and error handling.

    Args:
        template_name: Template file name (e.g., 'plant_health.html')
        **extra_context: Additional context variables to pass to template

    Returns:
        Rendered template with units, selected_unit_id, and extra context
    """
    selected_unit_id, units = _ensure_selected_unit()
    context = {"units": units, "selected_unit_id": selected_unit_id, **extra_context}
    return render_template(template_name, **context)


@ui_bp.route("/")
@login_required
def index() -> str | Response:
    """Dashboard page - shows selected unit."""
    try:
        logger.debug("=" * 80)
        logger.debug("INDEX ROUTE CALLED")

        # Get selected unit from session (should be set during login)
        selected_unit_id, units = _ensure_selected_unit()
        logger.debug("Selected unit: %s, Units count: %s", selected_unit_id, len(units))

        # If no units exist, redirect to a setup page or show empty state
        if not units:
            flash("Please create your first growth unit to get started.", "info")
            return redirect(url_for("ui.growth_units"))

        selected_unit = None
        plants = []
        thresholds = {}
        actuators = []

        if selected_unit_id is not None:
            logger.debug("Getting data for unit %s...", selected_unit_id)
            selected_unit = _container().growth_service.get_unit(selected_unit_id)
            logger.debug("Selected unit data: %s", selected_unit)
            plants = _container().plant_service.list_plants_as_dicts(selected_unit_id)
            logger.debug("Plants count: %s, Plants: %s", len(plants), plants)
            thresholds = _container().growth_service.get_thresholds(selected_unit_id)
            logger.debug("Thresholds: %s", thresholds)
            actuators = _container().actuator_management_service.list_actuators(unit_id=selected_unit_id)
            logger.debug("Actuators: %s", actuators)

        logger.debug("Rendering template...")
        return render_template(
            "dashboard.html",
            units=units,
            selected_unit=selected_unit,
            plants=plants,
            thresholds=thresholds,
            actuators=actuators,
        )
    except Exception as e:
        logger.exception("Error in index route: %s", e)
        raise


@ui_bp.get("/device-state-history")
@login_required
def device_state_history() -> str | Response:
    """Paginated view of recent actuator state history.

    Query params:
      - unit_id: filter by unit (optional)
      - actuator_id: filter by actuator (optional)
      - page: page number (1-based)
      - per_page: items per page (default 50)
    """
    try:
        selected_unit_id, units = _ensure_selected_unit()
        container = _container()
        device_repo = container.device_repo
        actuator_service = container.actuator_management_service

        # Params
        unit_id = request.args.get("unit_id", type=int)
        actuator_id = request.args.get("actuator_id", type=int)
        device_name = request.args.get("device_name", type=str)
        page = request.args.get("page", default=1, type=int)
        per_page = request.args.get("per_page", default=50, type=int)
        page = max(page, 1)
        per_page = max(min(per_page, 200), 10)

        # Fetch data (simple pagination by slicing)
        limit = page * per_page
        rows: list[dict] = []
        if actuator_id:
            rows = device_repo.get_actuator_state_history(actuator_id, limit=limit)
            meta = actuator_service.get_actuator(actuator_id) or {}
            for r in rows:
                r["name"] = meta.get("name")
                r["unit_id"] = meta.get("unit_id")

        elif unit_id and device_name:
            rows = device_repo.get_unit_actuator_state_history(unit_id, limit=limit)
            rows = [r for r in rows if str(r.get("name")) == device_name]
        elif unit_id:
            rows = device_repo.get_unit_actuator_state_history(unit_id, limit=limit)
        elif device_name:
            # Search across all units by device name
            ids = [
                int(a.get("actuator_id"))
                for a in actuator_service.list_actuators()
                if str(a.get("name")) == device_name and a.get("actuator_id") is not None
            ]
            rows = []
            for aid in ids:
                history = device_repo.get_actuator_state_history(aid, limit=limit)
                meta = actuator_service.get_actuator(aid) or {}
                for r in history:
                    r["name"] = meta.get("name")
                    r["unit_id"] = meta.get("unit_id")
                rows.extend(history)

            rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
        else:
            rows = device_repo.get_recent_actuator_state(limit=limit)

        # Slice for current page
        start = (page - 1) * per_page
        page_rows = rows[start : start + per_page]
        has_next = len(rows) > start + per_page
        has_prev = page > 1

        return render_template(
            "device_state_history.html",
            units=units,
            selected_unit_id=selected_unit_id,
            current_unit_id=unit_id,
            actuator_id=actuator_id,
            page=page,
            per_page=per_page,
            has_next=has_next,
            has_prev=has_prev,
            rows=page_rows,
        )
    except Exception as e:
        logger.error("Error rendering device state history: %s", e, exc_info=True)
        flash("Failed to load device state history.", "error")
        return redirect(url_for("ui.index"))


@ui_bp.route("/units/select")
@login_required
def unit_selector() -> str:
    """Show unit selection page for users with multiple units."""
    user_id: int = session.get("user_id", 1)

    growth_service = _container().growth_service
    plant_service = _container().plant_service
    units = growth_service.list_units(user_id=user_id)

    # Enrich with card data for visual display
    unit_cards = []
    for unit in units:
        try:
            card_data = get_unit_card_data(growth_service, plant_service, unit["unit_id"])
            unit_cards.append(card_data)
        except Exception as e:
            current_app.logger.error("Error getting card data for unit %s: %s", unit["unit_id"], e)
            # Use basic unit data as fallback
            unit_cards.append(unit)

    return render_template("unit_selector.html", units=unit_cards)


@ui_bp.post("/api/session/select-unit")
@login_required
def api_select_unit() -> Response:
    """API endpoint to store selected unit in session."""
    data = request.get_json(silent=True) or {}
    raw_unit_id = data.get("unit_id")

    if raw_unit_id is None:
        return _api_error("unit_id is required")

    try:
        unit_id = int(raw_unit_id)
    except (TypeError, ValueError):
        return _api_error("unit_id must be an integer")

    # Verify user owns this unit
    user_id: int = session.get("user_id", 1)
    growth_service = _container().growth_service

    try:
        unit = growth_service.get_unit(unit_id)
        if not unit:
            return _api_error("Unit not found", 404)

        unit_owner_id = unit.get("user_id")
        if unit_owner_id is not None:
            try:
                unit_owner_id = int(unit_owner_id)
                current_user_id = int(user_id)
            except (TypeError, ValueError):
                current_app.logger.warning("Unable to validate ownership for unit %s; denying access", unit_id)
                return _api_error("Unauthorized", 403)
            if unit_owner_id != current_user_id:
                return _api_error("Unauthorized", 403)

        session["selected_unit"] = unit_id
        return _api_success(
            {
                "unit_id": unit_id,
                "redirect_url": url_for("ui.index"),
            }
        )
    except Exception as e:
        current_app.logger.error("Error selecting unit: %s", e)
        return _api_error("Failed to select unit", 500)


@ui_bp.post("/select-unit")
@login_required
def select_unit() -> Response:
    unit_id = request.form.get("unit_id")
    next_url = request.form.get("next")  # e.g. /settings or /?foo=bar

    def _safe_next(url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.scheme or parsed.netloc:
            return None
        if not url.startswith("/"):
            return None
        return url

    if not unit_id:
        return redirect(_safe_next(next_url) or url_for("ui.index"))

    try:
        unit_id_int = int(unit_id)
    except (TypeError, ValueError):
        flash("Invalid unit selection.", "error")
        return redirect(_safe_next(next_url) or url_for("ui.index"))

    # Ownership check (same idea as api_select_unit)
    user_id = session.get("user_id", 1)
    growth_service = _container().growth_service
    unit = growth_service.get_unit(unit_id_int)

    if not unit:
        flash("Unit not found.", "error")
        return redirect(_safe_next(next_url) or url_for("ui.index"))

    unit_owner_id = unit.get("user_id")
    if unit_owner_id is not None:
        try:
            if int(unit_owner_id) != int(user_id):
                flash("Unauthorized unit selection.", "error")
                return redirect(_safe_next(next_url) or url_for("ui.index"))
        except (TypeError, ValueError):
            flash("Unauthorized unit selection.", "error")
            return redirect(_safe_next(next_url) or url_for("ui.index"))

    session["selected_unit"] = unit_id_int
    session.modified = True

    return redirect(_safe_next(next_url) or url_for("ui.index"))


@ui_bp.post("/growth-units")
@login_required
def create_growth_unit() -> Response:
    name = request.form.get("name", "").strip()
    location = request.form.get("location", "Indoor")
    user_id = session.get("user_id", 1)

    if not name:
        flash("Name is required to create a growth unit.", "error")
        return redirect(url_for("ui.index"))

    unit = _container().growth_service.create_unit(name=name, location=location, user_id=user_id)
    session["selected_unit"] = unit["unit_id"]
    flash("Growth unit created successfully.", "success")
    return redirect(url_for("ui.index"))


@ui_bp.post("/plants")
@login_required
def add_plant() -> Response:
    selected_unit_id = session.get("selected_unit")
    if selected_unit_id is None:
        flash("Select a growth unit before adding plants.", "error")
        return redirect(url_for("ui.index"))

    name = request.form.get("name", "").strip()
    plant_type = request.form.get("plant_type", "").strip()
    stage = request.form.get("stage", "Seedling")
    if not name or not plant_type:
        flash("Plant name and type are required.", "error")
        return redirect(url_for("ui.index"))

    _container().plant_service.create_plant(
        unit_id=int(selected_unit_id),
        name=name,
        plant_type=plant_type,
        current_stage=stage,
        days_in_stage=int(request.form.get("days_in_stage", 0) or 0),
    )
    flash("Plant added successfully.", "success")
    return redirect(url_for("ui.index"))


@ui_bp.post("/plants/<int:plant_id>/delete")
@login_required
def delete_plant(plant_id: int) -> Response:
    selected_unit_id = session.get("selected_unit")
    if selected_unit_id is None:
        flash("Select a growth unit first.", "error")
        return redirect(url_for("ui.index"))

    _container().plant_service.remove_plant(int(selected_unit_id), plant_id)
    flash("Plant removed.", "success")
    return redirect(url_for("ui.index"))


@ui_bp.post("/thresholds")
@login_required
def update_thresholds() -> Response:
    selected_unit_id = session.get("selected_unit")
    if selected_unit_id is None:
        flash("Select a growth unit first.", "error")
        return redirect(url_for("ui.index"))

    try:
        temperature = float(request.form.get("temperature_threshold", 0))
        humidity = float(request.form.get("humidity_threshold", 0))
    except ValueError:
        flash("Thresholds must be numeric.", "error")
        return redirect(url_for("ui.index"))

    _container().growth_service.set_thresholds(
        int(selected_unit_id),
        temperature_threshold=temperature,
        humidity_threshold=humidity,
    )
    flash("Thresholds updated.", "success")
    return redirect(url_for("ui.index"))


@ui_bp.route("/settings")
@login_required
def settings() -> str:
    """Settings page for configuring system-wide settings via API endpoints."""
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("settings.html", selected_unit_id=selected_unit_id, units=units)


@ui_bp.route("/notifications")
@login_required
def notifications() -> str:
    """Notifications page for viewing all notifications and irrigation requests."""
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("notifications.html", selected_unit_id=selected_unit_id, units=units)


@ui_bp.route("/devices")
@login_required
def devices() -> str:
    """Device management page"""
    from app.defaults import SystemConfigDefaults
    from app.enums import SensorModel, SensorType

    selected_unit_id, units = _ensure_selected_unit()

    # Get available GPIO pins (excluding used ones)
    available_gpio_pins = SystemConfigDefaults.get_available_gpio_pins()

    # Get ADS1115 channels for soil moisture sensors
    ads1115_channels = SystemConfigDefaults.get_adc_channels()

    # Get current devices from repository

    def _label_for_sensor_type(value: str) -> str:
        return value.replace("_", " ").title()

    # UI simplification: keep sensor type selection minimal.
    # Multi-reading Zigbee/WiFi devices, light sensors, air-quality sensors are still treated as Environment
    # (capabilities come from model/readings, not from exposing many separate "types" in the UI).
    ui_sensor_types = [SensorType.ENVIRONMENTAL, SensorType.PLANT]
    sensor_type_choices = [(st.value, _label_for_sensor_type(st.value)) for st in ui_sensor_types]

    env_models = [
        {"value": SensorModel.MQ2.value, "text": "Smoke/Gas Sensor (MQ2)"},
        {"value": SensorModel.MQ135.value, "text": "Air Quality Sensor (MQ135)"},
        {"value": SensorModel.BME280.value, "text": "BME280 Sensor"},
        {"value": SensorModel.BME680.value, "text": "BME680 Sensor"},
        {"value": SensorModel.ENS160AHT21.value, "text": "Environment Sensor (ENS160+AHT21)"},
        {"value": SensorModel.DHT22.value, "text": "DHT22 Sensor"},
        {"value": SensorModel.DHT11.value, "text": "DHT11 Sensor"},
        {"value": SensorModel.TSL2591.value, "text": "Light Intensity Sensor (TSL2591)"},
        {"value": SensorModel.BH1750.value, "text": "Light Sensor (BH1750)"},
    ]
    plant_models = [
        {"value": SensorModel.SOIL_MOISTURE.value, "text": "Soil Moisture Sensor"},
        {"value": SensorModel.CAPACITIVE_SOIL.value, "text": "Capacitive Soil Sensor"},
        {"value": SensorModel.PH_SENSOR.value, "text": "pH Sensor"},
        {"value": SensorModel.EC_SENSOR.value, "text": "EC Sensor"},
    ]

    adc_sensor_types = {
        SensorType.PLANT.value,
    }

    sensor_model_options: dict[str, list[dict[str, str]]] = {
        SensorType.ENVIRONMENTAL.value: env_models,
        SensorType.PLANT.value: plant_models,
    }

    # Get actuators and sensors for display via repository (no raw SQL)
    db_actuators = []
    db_sensors = []
    available_actuators = []

    try:
        device_repo = _container().device_repo

        # Get actuators from repository filtered by selected unit
        for actuator_data in device_repo.list_actuator_configs(unit_id=selected_unit_id):
            db_actuators.append(
                {
                    "id": actuator_data.get("actuator_id"),
                    "name": actuator_data.get("device") or actuator_data.get("name"),
                    "gpio": actuator_data.get("gpio"),
                    "ip_address": actuator_data.get("ip_address"),
                }
            )
            available_actuators.append(actuator_data.get("device") or actuator_data.get("name"))

        # Get sensors from repository filtered by selected unit
        for sensor_data in device_repo.list_sensor_configs(unit_id=selected_unit_id):
            db_sensors.append(
                {
                    "sensor_id": sensor_data.get("sensor_id"),
                    "name": sensor_data.get("name"),
                    "sensor_type": sensor_data.get("sensor_type"),
                    "sensor_model": sensor_data.get("model", "Unknown"),
                    "gpio": sensor_data.get("gpio"),
                    "ip_address": sensor_data.get("ip_address"),
                }
            )

    except Exception as e:
        logger.error("Error loading devices: %s", e)
        db_actuators = []
        db_sensors = []
        available_actuators = []

    return render_template(
        "devices.html",
        units=units,
        selected_unit_id=selected_unit_id,
        available_gpio_pins=available_gpio_pins,
        ads1115_channels=ads1115_channels,
        db_actuators=db_actuators,
        db_sensors=db_sensors,
        available_actuators=available_actuators,
        sensor_type_choices=sensor_type_choices,
        sensor_model_options=sensor_model_options,
        adc_sensor_types=sorted(adc_sensor_types),
    )


@ui_bp.route("/units")
@login_required
def growth_units() -> str:
    """Growth units management page"""
    try:
        units = _container().growth_service.list_units()
        return render_template("units.html", units=units)
    except Exception:
        flash("Failed to load growth units.", "error")
        return render_template("units.html", units=[])


@ui_bp.route("/fullscreen")
@login_required
def fullscreen_camera() -> str:
    """Fullscreen camera view for a specific unit."""
    try:
        unit_id = request.args.get("unit_id")
        selected_unit_id, units = _ensure_selected_unit()
        if unit_id is not None:
            try:
                selected_unit_id = int(unit_id)
            except (TypeError, ValueError):
                selected_unit_id = None

        selected_unit = None
        if selected_unit_id is not None:
            selected_unit = _container().growth_service.get_unit(selected_unit_id)

        return render_template(
            "fullscreen.html",
            units=units,
            selected_unit_id=selected_unit_id,
            selected_unit=selected_unit,
        )
    except Exception as e:
        logger.error("Error loading fullscreen camera: %s", e, exc_info=True)
        return render_template("fullscreen.html", selected_unit=None)


@ui_bp.route("/sensor-analytics")
@login_required
def sensor_analytics() -> str:
    """Unified sensor analytics and visualization dashboard.

    Displays:
    - Time-series analysis with multi-metric support
    - Multi-sensor comparison charts
    - Statistical analysis (avg, min, max, std dev, trends)
    - Anomaly detection and alerts
    - Saved views and custom alert builder
    - Real-time updates via Socket.IO
    - CSV export capabilities
    """
    selected_unit_id, units = _ensure_selected_unit()
    selected_unit = None
    if selected_unit_id:
        selected_unit = _container().growth_service.get_unit(selected_unit_id)
    return render_template(
        "sensor_analytics.html", units=units, selected_unit_id=selected_unit_id, selected_unit=selected_unit
    )


# ============================================================================
# Analytics & Health Routes
# ============================================================================


@ui_bp.route("/energy-analytics")
@login_required
def energy_analytics() -> str:
    """Energy analytics and cost tracking dashboard.

    Displays:
    - Total energy consumption and costs
    - Energy consumption by actuator
    - Cost trends and predictions
    - Failure predictions for devices
    - Efficiency metrics
    """
    return _render_page_with_units("energy_analytics.html")


@ui_bp.route("/device-health")
@login_required
def device_health() -> str:
    """Device health monitoring and diagnostics dashboard.

    Displays:
    - Device health status (all sensors and actuators)
    - Anomaly detection alerts
    - Device uptime and connectivity
    - Power consumption per device
    - Maintenance predictions
    """
    # Get device information via repository (no raw SQL)
    devices_summary: dict[str, list[dict]] = {"actuators": [], "sensors": []}
    try:
        device_repo = _container().device_repo
        devices_summary["actuators"] = device_repo.list_actuators()
        devices_summary["sensors"] = device_repo.list_sensors()
    except Exception as e:
        logger.error("Error loading device data: %s", e)

    return _render_page_with_units("device_health.html", devices_summary=devices_summary)


@ui_bp.route("/system-health", endpoint="status")
@ui_bp.route("/system-health")
@login_required
def system_health() -> str:
    """Unified System Health & Status Dashboard.

    Displays comprehensive system health, device status, and monitoring.
    """
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("system_health.html", selected_unit_id=selected_unit_id, units=units)


@ui_bp.route("/plants")
@login_required
def plants_hub() -> str:
    """Plants Hub - Comprehensive Plant Management Dashboard.

    Consolidated single-page dashboard combining:
    - Plant health monitoring and status
    - Plant journal (observations and nutrients tracking)
    - Growing guide reference
    - Harvest tracking and reports
    - Disease risk monitoring

    Features:
    - Interactive health status with detailed breakdown
    - Filterable plant lists (all/healthy/stressed/diseased)
    - Plant journal with observations and nutrient records
    - Single plant and bulk nutrient application
    - Searchable growing guide
    - localStorage caching for performance
    - Auto-refresh capabilities

    All data loaded dynamically via Plants API endpoints.
    """
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("plants.html", selected_unit_id=selected_unit_id, units=units)


@ui_bp.route("/plants/guide")
@login_required
def plants_guide() -> str:
    """Plants Growing Guide - Comprehensive reference for plant care.

    Displays plant information in a modern card grid format with:
    - Plant overview (name, species, difficulty, pH range)
    - Growth stages timeline with conditions
    - Sensor requirements (soil, CO2, VPD, light spectrum)
    - Automation settings
    - Yield and space information
    - Nutritional data
    - Common issues and solutions
    - Companion plants
    - Harvest guide

    Data loaded dynamically from /api/plants/guide/full endpoint.
    """
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("plants_guide.html", selected_unit_id=selected_unit_id, units=units)


@ui_bp.route("/plants/guide/<int:plant_id>")
@login_required
def plant_detail(plant_id) -> str:
    """Individual Plant Detail Page - Full growing information.

    Displays comprehensive plant information including:
    - Plant overview with badges and description
    - Growing requirements (temp, light, water, spacing, soil, humidity)
    - Growth timeline and harvest season
    - Companion plants
    - Pest and disease risks with prevention tips
    - Automation settings
    - Nutritional information

    Args:
        plant_id: The ID of the plant from plants_info.json
    """
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("plant_detail.html", plant_id=plant_id, selected_unit_id=selected_unit_id, units=units)


@ui_bp.route("/plants/<int:plant_id>/my-detail")
@login_required
def my_plant_detail(plant_id) -> str:
    """My Plant Detail Page - Comprehensive view of a user's plant.

    Tabbed interface with:
    - Overview: plant info, health status, linked devices, stage info
    - Journal: paginated entries with filters, add entry forms
    - Analytics: watering frequency chart, health trend, stage timeline
    - Stage Management: extend stage, view transition history

    All data loaded dynamically via /api/plants/<id>/detail and journal endpoints.

    Args:
        plant_id: The ID of the user's plant
    """
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("my_plant_detail.html", plant_id=plant_id, selected_unit_id=selected_unit_id, units=units)


@ui_bp.route("/ml-dashboard")
@login_required
def ml_dashboard() -> str:
    """Machine Learning infrastructure dashboard.

    Displays:
    - Registered ML models and their versions
    - Model drift detection and monitoring
    - Automated retraining jobs and schedules
    - Training history and performance metrics
    - A/B testing results
    - Manual model control (retrain, activate, rollback)
    """
    return _render_page_with_units("ml_dashboard.html")


# ============================================================================
# System API Endpoints
# ============================================================================


@ui_bp.get("/api/system/uptime")
def get_server_uptime() -> Response:
    """Get server uptime information.

    Returns:
        JSON with uptime_seconds and started_at timestamp
    """
    health = _container().system_health_service
    uptime = health.get_uptime_seconds()
    started_at = health.uptime_start.isoformat() + "Z" if health.uptime_start else None
    return jsonify({"ok": True, "data": {"uptime_seconds": uptime, "started_at": started_at}})


@ui_bp.get("/api/system/activities")
def get_recent_activities() -> Response:
    """Get recent system activities.

    Query Parameters:
        limit: Maximum number of activities (default: 50)
        activity_type: Filter by activity type
        severity: Filter by severity level (info, warning, error)

    Returns:
        JSON with list of recent activities
    """
    try:
        limit = int(request.args.get("limit", 50))
        activity_type = request.args.get("activity_type")
        severity = request.args.get("severity")

        activity_logger = _container().activity_logger
        activities = activity_logger.get_recent_activities(limit=limit, activity_type=activity_type, severity=severity)

        response = jsonify({"ok": True, "data": {"activities": activities, "count": len(activities)}, "error": None})
        response.status_code = 200
        return response
    except Exception as e:
        logger.error("Error fetching activities: %s", e)
        response = jsonify({"ok": False, "data": None, "error": {"message": "Failed to fetch activities"}})
        response.status_code = 500
        return response


@ui_bp.get("/api/system/alerts")
def get_active_alerts() -> Response:
    """Get active system alerts.

    Query Parameters:
        severity: Filter by severity level (info, warning, critical)
        unit_id: Filter by unit ID
        limit: Maximum number of alerts (default: 100)

    Returns:
        JSON with list of active alerts and summary
    """
    try:
        severity = request.args.get("severity")
        unit_id = request.args.get("unit_id", type=int)
        limit = int(request.args.get("limit", 100))

        alert_service = _container().alert_service
        alerts = alert_service.get_active_alerts(severity=severity, unit_id=unit_id, limit=limit)
        summary = alert_service.get_alert_summary()
        logger.debug("Fetched %s alerts with summary: %s", len(alerts), summary)

        response = jsonify(
            {"ok": True, "data": {"alerts": alerts, "count": len(alerts), "summary": summary}, "error": None}
        )
        response.status_code = 200
        return response
    except Exception as e:
        logger.error("Error fetching alerts: %s", e)
        response = jsonify({"ok": False, "data": None, "error": {"message": "Failed to fetch alerts"}})
        response.status_code = 500
        return response


@ui_bp.post("/api/system/alerts/<int:alert_id>/acknowledge")
def acknowledge_alert(alert_id: int) -> Response:
    """Acknowledge an alert.

    Args:
        alert_id: ID of the alert to acknowledge

    Returns:
        JSON with success status
    """
    try:
        user_id = session.get("user_id")

        alert_service = _container().alert_service
        success = alert_service.acknowledge_alert(alert_id, user_id)

        if success:
            response = jsonify({"ok": True, "data": {"message": "Alert acknowledged"}, "error": None})
            response.status_code = 200
            return response
        else:
            response = jsonify({"ok": False, "data": None, "error": {"message": "Failed to acknowledge alert"}})
            response.status_code = 500
            return response
    except Exception as e:
        logger.error("Error acknowledging alert: %s", e)
        response = jsonify({"ok": False, "data": None, "error": {"message": "Failed to acknowledge alert"}})
        response.status_code = 500
        return response


@ui_bp.post("/api/system/alerts/<int:alert_id>/resolve")
@login_required
def resolve_alert(alert_id: int) -> Response:
    """Mark an alert as resolved.

    Args:
        alert_id: ID of the alert to resolve

    Returns:
        JSON with success status
    """
    try:
        alert_service = _container().alert_service
        success = alert_service.resolve_alert(alert_id)

        if success:
            response = jsonify({"ok": True, "data": {"message": "Alert resolved"}, "error": None})
            response.status_code = 200
            return response
        else:
            response = jsonify({"ok": False, "data": None, "error": {"message": "Failed to resolve alert"}})
            response.status_code = 500
            return response
    except Exception as e:
        logger.error("Error resolving alert: %s", e)
        response = jsonify({"ok": False, "data": None, "error": {"message": "Failed to resolve alert"}})
        response.status_code = 500
        return response


@ui_bp.post("/api/system/alerts/clear-all")
@login_required
def clear_all_alerts() -> Response:
    """Clear all active alerts.

    Returns:
        JSON with success status and count of cleared alerts
    """
    try:
        alert_service = _container().alert_service

        # Get all active alerts
        active_alerts = alert_service.get_active_alerts(limit=1000)
        count = 0

        # Resolve each alert
        for alert in active_alerts:
            alert_id = alert.get("alert_id")
            if alert_id and alert_service.resolve_alert(alert_id):
                count += 1

        response = jsonify({"ok": True, "data": {"message": f"Cleared {count} alerts", "count": count}, "error": None})
        response.status_code = 200
        return response
    except Exception as e:
        logger.error("Error clearing all alerts: %s", e)
        response = jsonify({"ok": False, "data": None, "error": {"message": "Failed to clear alerts"}})
        response.status_code = 500
        return response


@ui_bp.route("/activity")
@login_required
def activity() -> str:
    """Activity Log page - Full page with filters.

    Shows comprehensive system activity with:
    - Activity type filters
    - Severity level filters
    - Date range selection
    - Search functionality
    - Pagination
    """
    selected_unit_id, units = _ensure_selected_unit()
    return render_template("activity.html", selected_unit_id=selected_unit_id, units=units)


# ============================================================================
# Help & Documentation Routes (Public - No login required)
# ============================================================================


@ui_bp.route("/help")
def help_page() -> str:
    """Help Center main page.

    Public access (no login required) for better SEO and user support.
    Displays searchable help categories and articles.
    """
    return render_template("help.html")


@ui_bp.route("/help/<category>")
def help_category(category: str) -> str:
    """Help category page with filtered articles.

    Args:
        category: Category ID to filter articles
    """
    return render_template("help.html", category=category)


@ui_bp.route("/help/<category>/<article_id>")
def help_article(category: str, article_id: str) -> str:
    """Individual help article page.

    Args:
        category: Category ID
        article_id: Article ID
    """
    return render_template("help_article.html", category=category, article_id=article_id)


# ============================================================================
# Blog Routes (Public - No login required)
# ============================================================================


@ui_bp.route("/blog")
def blog_page() -> str:
    """Blog main page with post listing.

    Public access (no login required) for better SEO.
    Displays blog posts with category filters and search.
    """
    return render_template("blog.html")


@ui_bp.route("/blog/<slug>")
def blog_post(slug: str) -> str:
    """Individual blog post page.

    Args:
        slug: Post slug (URL-friendly identifier)
    """
    return render_template("blog_post.html", slug=slug)
