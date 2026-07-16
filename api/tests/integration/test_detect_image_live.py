"""Live end-to-end test against a real Ultralytics YOLO model.

Skipped unless `ultralytics` is installed (`uv sync --extra vision`). On
first run it also needs network access to download the small pretrained
COCO checkpoint (yolo11n.pt, ~5MB) if it isn't already cached under
data/weights. This intentionally exercises the real inference path, not a
fake model — everything else in tests/unit covers detector logic hermetically.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

pytest.importorskip("ultralytics")
cv2 = pytest.importorskip("cv2")

from fastapi.testclient import TestClient  # noqa: E402

from sentinel_detect.main import app  # noqa: E402


def test_detect_image_endpoint_runs_real_yolo_inference() -> None:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    with TestClient(app) as client:
        response = client.post(
            "/detect/image",
            files={"file": ("frame.jpg", io.BytesIO(encoded.tobytes()), "image/jpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["detections"], list)
    assert "person" in body["active_detectors"]
