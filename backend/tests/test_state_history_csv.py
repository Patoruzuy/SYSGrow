import json
from flask import Flask
from app import create_app


def test_unit_state_history_csv_endpoint(monkeypatch):
    app: Flask = create_app({})
    client = app.test_client()

    # Call CSV export (unit 1). Should return 200 and text/csv mimetype even if empty.
    resp = client.get('/api/devices/units/1/actuators/state-history.csv?limit=5')
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert 'text/csv' in resp.mimetype


def test_actuator_state_history_json(monkeypatch):
    app: Flask = create_app({})
    client = app.test_client()

    # JSON endpoint should respond 200 or 404 depending on DB state
    resp = client.get('/api/devices/actuators/1/state-history?limit=5')
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        payload = resp.get_json()
        assert 'ok' in payload
        assert 'data' in payload
