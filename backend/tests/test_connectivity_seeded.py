from flask import Flask

from app import create_app


def seed_connectivity_events(app: Flask):
    with app.app_context():
        container = app.config["CONTAINER"]
        repo = container.device_repo
        # Seed MQTT connect
        repo.save_connectivity_event(
            connection_type="mqtt",
            status="connected",
            endpoint="127.0.0.1:1883",
            broker="127.0.0.1",
            port=1883,
            timestamp="2025-01-01T00:00:00Z",
        )
        # Seed WiFi disconnect
        repo.save_connectivity_event(
            connection_type="wifi",
            status="disconnected",
            endpoint="192.168.1.50",
            device_id="esp-relay-1",
            timestamp="2025-01-01T00:01:00Z",
        )


def test_connectivity_history_seeded_json_and_csv():
    app: Flask = create_app({})
    client = app.test_client()
    seed_connectivity_events(app)

    # JSON, filtered by mqtt
    resp = client.get("/api/devices/connectivity-history?connection_type=mqtt&limit=2")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert "history" in payload["data"]
    rows = payload["data"]["history"]
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        for k in ["timestamp", "connection_type", "status"]:
            assert k in row

    # CSV, filtered by mqtt
    resp_csv = client.get("/api/devices/connectivity-history.csv?connection_type=mqtt&limit=2")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.mimetype
    text = resp_csv.get_data(as_text=True)
    assert "timestamp,connection_type,status" in text.splitlines()[0]


def test_dashboard_recent_connectivity_feed():
    app: Flask = create_app({})
    client = app.test_client()
    seed_connectivity_events(app)

    resp = client.get("/api/dashboard/connectivity/recent?limit=5")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert "events" in payload["data"]
    assert isinstance(payload["data"]["events"], list)
