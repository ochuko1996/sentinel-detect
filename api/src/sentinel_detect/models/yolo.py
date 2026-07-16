"""Ultralytics YOLO (YOLOv8/YOLOv11) inference backend.

`ultralytics` is only imported inside `load()`, not at module import time, so
that `sentinel_detect.models` remains importable without the optional
'vision' extra installed — only actually loading a model requires it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.exceptions import InferenceError, ModelLoadError
from sentinel_detect.core.interfaces.model import BaseInferenceModel, RawPrediction
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)

# Applied at the raw-inference level, well below any detector's own
# confidence_threshold, so the backend never discards a box a detector's
# (usually stricter) threshold would otherwise have kept.
_RAW_CONFIDENCE_FLOOR = 0.1
_NMS_IOU = 0.5


class UltralyticsYoloModel(BaseInferenceModel):
    """Wraps `ultralytics.YOLO` behind the `BaseInferenceModel` port.

    One instance is shared by every detector configured with the same
    `model_key` (see `models.manager.ModelManager`) — e.g. a single COCO
    checkpoint backs the person, vehicle, and animal detectors without each
    one loading its own copy of the weights.
    """

    def __init__(self, *, weights_path: Path, device: str, inference_size: tuple[int, int]) -> None:
        self._weights_path = weights_path
        self._device_setting = device
        self._inference_size = inference_size
        self._model: Any | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ModelLoadError(
                "ultralytics is not installed; run `uv sync --extra vision`"
            ) from exc

        self._weights_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._model = YOLO(str(self._weights_path))
        except Exception as exc:
            raise ModelLoadError(
                f"failed to load YOLO weights from '{self._weights_path}': {exc}. "
                "If this is a custom detector (weapon/fire/smoke/ppe), place a "
                "fine-tuned .pt file at this path, or disable the detector via "
                "config until you have one."
            ) from exc

    def warmup(self) -> None:
        self.load()
        assert self._model is not None
        width, height = self._inference_size
        dummy = np.zeros((height, width, 3), dtype=np.uint8)
        self._model.predict(
            dummy,
            conf=_RAW_CONFIDENCE_FLOOR,
            iou=_NMS_IOU,
            imgsz=self._inference_size,
            device=self._resolved_device,
            verbose=False,
        )

    def predict(self, frame: Frame) -> list[RawPrediction]:
        if self._model is None:
            raise InferenceError("model not loaded; call load() first")

        results = self._model.predict(
            frame.image,
            conf=_RAW_CONFIDENCE_FLOOR,
            iou=_NMS_IOU,
            imgsz=self._inference_size,
            device=self._resolved_device,
            verbose=False,
        )

        predictions: list[RawPrediction] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for xyxy, confidence, class_id in zip(
                boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist(), strict=True
            ):
                x1, y1, x2, y2 = xyxy
                try:
                    bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                except ValueError:
                    logger.debug("skipping_degenerate_box", xyxy=xyxy)
                    continue
                predictions.append(
                    RawPrediction(bbox=bbox, class_id=int(class_id), confidence=float(confidence))
                )
        return predictions

    @property
    def class_names(self) -> dict[int, str]:
        if self._model is None:
            raise InferenceError("model not loaded; call load() first")
        names: dict[int, str] = dict(self._model.names)
        return names

    @property
    def _resolved_device(self) -> str:
        if self._device_setting != "auto":
            return self._device_setting
        import torch

        return "cuda:0" if torch.cuda.is_available() else "cpu"
