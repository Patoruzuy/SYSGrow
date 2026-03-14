from flask import Flask
from app import create_app


def test_connectivity_history_json():
    app: Flask = create_app({})
    client = app.test_client()

    resp = client.get('/api/devices/connectivity-history?connection_type=mqtt&limit=5')
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        payload = resp.get_json()
        assert 'ok' in payload
        assert 'data' in payload
        assert 'history' in payload['data']


def test_connectivity_history_csv():
    app: Flask = create_app({})
    client = app.test_client()

    resp = client.get('/api/devices/connectivity-history.csv?connection_type=wifi&limit=5')
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert 'text/csv' in resp.mimetype

