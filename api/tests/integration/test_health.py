from fastapi.testclient import TestClient

from sentinel_detect.main import app


def test_health_endpoint_reports_ok_and_configured_detectors() -> None:
    # The lifespan (which builds the detection service) only runs when
    # TestClient is used as a context manager.
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "person" in body["configured_detectors"]
    # active_detectors depends on model weights actually loading (network
    # access / the 'vision' extra); assert shape, not membership, so this
    # test stays hermetic.
    assert isinstance(body["active_detectors"], list)
    assert "loitering" in body["enabled_event_rules"]
