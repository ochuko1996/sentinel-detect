"""Integration tests for GET /alerts and WS /ws/alerts.

Rather than relying on real detections (which need the 'vision' extra and a
real matching object in footage — see test_detect_image_live.py for that),
these tests dispatch a synthetic Event directly through the app's real,
wired-up `AlertEngine` (`app.state.alert_engine`), then verify it actually
reaches the real REST store and a real WebSocket client. This proves the
wiring between AlertEngine, AlertStore, and ConnectionManager is genuine,
independent of whether the ML backend is installed.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.main import app


def _event() -> Event:
    return Event(
        camera_id="cam-1",
        type=EventType.PERSON_DETECTED,
        severity=EventSeverity.INFO,
        rule="person_detected",
        message="a person was detected",
    )


def test_get_alerts_reflects_events_dispatched_through_the_alert_engine() -> None:
    with TestClient(app) as client:
        alert_engine = client.app.state.alert_engine  # type: ignore[attr-defined]
        asyncio.run(alert_engine.dispatch([_event()]))

        response = client.get("/alerts")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "person_detected"
    assert body[0]["message"] == "a person was detected"


def test_get_alerts_respects_limit() -> None:
    with TestClient(app) as client:
        alert_engine = client.app.state.alert_engine  # type: ignore[attr-defined]
        asyncio.run(alert_engine.dispatch([_event(), _event(), _event()]))

        response = client.get("/alerts", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_websocket_receives_a_broadcast_alert_in_real_time() -> None:
    with TestClient(app) as client, client.websocket_connect("/ws/alerts") as websocket:
        alert_engine = client.app.state.alert_engine  # type: ignore[attr-defined]
        asyncio.run(alert_engine.dispatch([_event()]))

        message = websocket.receive_json()

    assert message["type"] == "person_detected"
    assert message["camera_id"] == "cam-1"
