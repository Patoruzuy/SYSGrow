"""API documentation blueprint — serves OpenAPI spec + Swagger UI.

Sprint 5, Finding #13:  /api/v1/docs   → Swagger UI
                         /api/v1/docs/openapi.json → raw spec
"""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify

from app.utils.http import safe_route

docs_api = Blueprint("docs_api", __name__)

_SWAGGER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SYSGrow API Documentation</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui.css"
    crossorigin="anonymous"
  />
  <style>
    html { box-sizing: border-box; overflow-y: scroll; }
    *, *::before, *::after { box-sizing: inherit; }
    body { margin: 0; background: #fafafa; }
    .topbar { display: none !important; }   /* hide Swagger-UI top bar */
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script
    src="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui-bundle.js"
    crossorigin="anonymous"
  ></script>
  <script>
    SwaggerUIBundle({
      url: '/api/v1/docs/openapi.json',
      dom_id: '#swagger-ui',
      deepLinking: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset,
      ],
      layout: 'BaseLayout',
    });
  </script>
</body>
</html>
"""


@docs_api.get("/")
@safe_route("Failed to serve API documentation")
def swagger_ui() -> Response:
    """Serve the Swagger UI single-page application."""
    return _SWAGGER_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@docs_api.get("/openapi.json")
@safe_route("Failed to generate OpenAPI spec")
def openapi_spec() -> Response:
    """Return the full OpenAPI 3.0.3 specification as JSON."""
    from app.utils.openapi import generate_openapi_spec

    spec = generate_openapi_spec(current_app)
    return jsonify(spec)
