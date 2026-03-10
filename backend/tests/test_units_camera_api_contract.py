from __future__ import annotations

from pathlib import Path


def test_units_data_service_camera_uses_supported_growth_api_methods():
    source = Path("static/js/units/data-service.js").read_text(encoding="utf-8")

    assert "this.api.Growth.startCamera(unitId)" in source
    assert "this.api.Growth.stopCamera(unitId)" in source
    assert "this.api.Growth.getCameraStatus(unitId)" in source

    assert "this.api.post(`/api/growth/units/${unitId}/camera/start`)" not in source
    assert "this.api.post(`/api/growth/units/${unitId}/camera/stop`)" not in source
    assert "this.api.get(`/api/growth/units/${unitId}/camera/status`)" not in source
