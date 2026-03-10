"""OpenAPI 3.0.3 spec generator — auto-discovers Flask routes + Pydantic schemas.

Sprint 5, Finding #13: Add OpenAPI documentation for the 428-route API surface.

The spec is generated dynamically from:
  • Flask's ``url_map``  (paths, methods, path-parameter types)
  • Route-function docstrings (summary / description)
  • Pydantic v2 ``model_json_schema()``  (request/response ``$ref`` s)

No external packages required.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from flask import Flask

# ── Helpers ─────────────────────────────────────────────────────

_PARAM_RE = re.compile(r"<(?:(\w+):)?(\w+)>")
"""Matches Flask path-parameter syntax  ``<type:name>`` or ``<name>``."""

logger = logging.getLogger(__name__)

_FLASK_TYPE_MAP: dict[str, dict[str, Any]] = {
    "int": {"type": "integer"},
    "float": {"type": "number", "format": "float"},
    "string": {"type": "string"},
    "path": {"type": "string"},
    "uuid": {"type": "string", "format": "uuid"},
    "": {"type": "string"},  # default when no converter is given
}

# Tags we want to group under nicer display names
_TAG_DISPLAY: dict[str, str] = {
    "plants_api": "Plants",
    "growth_api": "Growth Units",
    "devices_api": "Devices",
    "dashboard_api": "Dashboard",
    "settings_api": "Settings",
    "harvest": "Harvest",
    "health_api": "Health",
    "help_api": "Help / Guides",
    "blog_api": "Blog",
    "disease": "Plant Disease",
    "ml_base": "ML — Core",
    "ml_predictions": "ML — Predictions",
    "ml_models": "ML — Models",
    "ml_monitoring": "ML — Monitoring",
    "ml_analytics": "ML — Analytics",
    "ml_retraining": "ML — Retraining",
    "ml_analysis": "ML — Analysis",
    "ml_readiness": "ML — Readiness",
    "ml_ab_testing": "ML — A/B Testing",
    "ml_continuous": "ML — Continuous Learning",
    "ml_personalized": "ML — Personalized",
    "ml_training_data": "ML — Training Data",
    "auth": "Authentication",
}


def _flask_path_to_openapi(rule_path: str) -> str:
    """``/api/v1/plants/<int:pid>``  →  ``/plants/{pid}``."""
    # Strip the /api/v1 prefix so paths are relative to the server base URL
    path = rule_path
    if path.startswith("/api/v1"):
        path = path[7:] or "/"
    return _PARAM_RE.sub(r"{\2}", path)


def _path_parameters(rule) -> list[dict[str, Any]]:
    """Build OpenAPI ``parameters`` list from a Werkzeug ``Rule``."""
    params: list[dict[str, Any]] = []
    for match in _PARAM_RE.finditer(rule.rule):
        converter = match.group(1) or ""
        name = match.group(2)
        schema = dict(_FLASK_TYPE_MAP.get(converter, {"type": "string"}))
        params.append(
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": schema,
            }
        )
    return params


def _extract_summary_description(view_func) -> tuple[str, str]:
    """Return ``(summary, description)`` from a view function's docstring."""
    if not view_func or not view_func.__doc__:
        return "", ""
    lines = view_func.__doc__.strip().splitlines()
    summary = lines[0].strip().rstrip(".")
    desc_lines = [ln.strip() for ln in lines[1:] if ln.strip()]
    description = "\n".join(desc_lines) if desc_lines else ""
    return summary, description


# ── Pydantic schema collection ──────────────────────────────────


def _collect_pydantic_schemas() -> dict[str, Any]:
    """Import all Pydantic models from ``app.schemas`` and return JSON Schema defs."""
    schemas: dict[str, Any] = {}
    try:
        import inspect

        from pydantic import BaseModel

        import app.schemas as schema_pkg

        # Walk every public name exported by the schemas package
        for name in dir(schema_pkg):
            obj = getattr(schema_pkg, name, None)
            if obj is not None and inspect.isclass(obj) and issubclass(obj, BaseModel) and obj is not BaseModel:
                try:
                    json_schema = obj.model_json_schema(mode="serialization")
                    # Flatten $defs into top-level components if present
                    defs = json_schema.pop("$defs", {})
                    schemas[name] = json_schema
                    for def_name, def_schema in defs.items():
                        if def_name not in schemas:
                            schemas[def_name] = def_schema
                except Exception as exc:
                    logger.debug("Skipping schema %s during OpenAPI extraction: %s", name, exc)
    except (ImportError, AttributeError, RuntimeError) as exc:
        logger.debug("Failed to import schema package for OpenAPI generation: %s", exc)
    return schemas


# ── Main generator ──────────────────────────────────────────────


def generate_openapi_spec(app: Flask) -> dict[str, Any]:
    """Return a complete OpenAPI 3.0.3 dict for the running Flask application.

    Call inside an application context (``with app.app_context(): ...``).
    """
    spec: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": "SYSGrow — Smart Agriculture API",
            "version": "1.0.0",
            "description": (
                "REST API for the SYSGrow smart agriculture platform.  "
                "Provides plant management, growth-unit control, device "
                "orchestration, ML inference, health monitoring, and more."
            ),
            "contact": {"name": "SYSGrow Team"},
        },
        "servers": [
            {"url": "/api/v1", "description": "API v1 (current)"},
        ],
        "tags": [],
        "paths": {},
        "components": {"schemas": {}},
    }

    seen_tags: dict[str, str] = {}  # tag_key → display_name
    paths: dict[str, dict[str, Any]] = {}

    for rule in app.url_map.iter_rules():
        # Only document versioned API endpoints
        if rule.endpoint == "static" or not rule.rule.startswith("/api/v1"):
            continue
        # Skip the docs endpoints themselves
        if rule.rule.startswith("/api/v1/docs"):
            continue

        openapi_path = _flask_path_to_openapi(rule.rule)

        # Determine tag from blueprint
        parts = rule.endpoint.split(".")
        tag_key = parts[0] if len(parts) > 1 else "default"
        if tag_key not in seen_tags:
            display = _TAG_DISPLAY.get(tag_key, tag_key.replace("_", " ").title())
            seen_tags[tag_key] = display

        if openapi_path not in paths:
            paths[openapi_path] = {}

        view_func = app.view_functions.get(rule.endpoint)
        summary, description = _extract_summary_description(view_func)

        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            method_lower = method.lower()
            operation_id = f"{method_lower}_{rule.endpoint.replace('.', '_')}"

            operation: dict[str, Any] = {
                "tags": [seen_tags[tag_key]],
                "summary": summary or rule.endpoint.replace(".", " → ").replace("_", " ").title(),
                "operationId": operation_id,
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "400": {"description": "Bad request"},
                    "401": {"description": "Unauthorized"},
                    "404": {"description": "Not found"},
                    "500": {"description": "Internal server error"},
                },
            }
            if description:
                operation["description"] = description

            params = _path_parameters(rule)
            if params:
                operation["parameters"] = params

            if method_lower in ("post", "put", "patch"):
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"},
                        },
                    },
                }

            paths[openapi_path][method_lower] = operation

    # Sort paths alphabetically for readability
    spec["paths"] = dict(sorted(paths.items()))

    # Build tags list sorted alphabetically by display name
    spec["tags"] = sorted(
        [{"name": display, "description": f"Endpoints for {display}"} for display in seen_tags.values()],
        key=lambda t: t["name"],
    )

    # Attach Pydantic-derived component schemas
    spec["components"]["schemas"] = _collect_pydantic_schemas()

    return spec
