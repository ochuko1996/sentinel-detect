"""BaseInferenceModel implementations (Ultralytics YOLO now; ONNX Runtime, TensorRT later)."""

from sentinel_detect.models.caching import CachingInferenceModel
from sentinel_detect.models.manager import ModelManager
from sentinel_detect.models.yolo import UltralyticsYoloModel

__all__ = ["CachingInferenceModel", "ModelManager", "UltralyticsYoloModel"]

