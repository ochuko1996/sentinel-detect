"""Wraps a `BaseInferenceModel` with a single-slot per-frame prediction cache.

Detectors sharing a `model_key` (e.g. person/vehicle/animal all default to
`yolov11n`) each call `model.predict(frame)` independently — without this,
one frame runs the same forward pass through the same weights once per
detector that shares the model, tripling (or worse) GPU/CPU cost for no
benefit. `DetectionService.detect()` processes exactly one frame at a time,
strictly sequentially, so a cache holding only the *most-recently-computed*
frame's result is sufficient: the first detector to call `predict()` for a
given frame actually runs inference; every other detector sharing that model
instance for the *same* frame gets the cached result instead of a redundant
forward pass.

Keyed by `id(frame)` (object identity), not frame content: `Frame` is a
frozen dataclass wrapping a `numpy.ndarray`, which is unhashable, so `Frame`
can never be a dict key or participate in `==`-based caching without extra
machinery. Every detector processing one frame within one
`DetectionService.detect()` call receives the exact same `Frame` object, so
identity is a correct, free-to-compute "is this still the same frame" check
— and since `Frame`s are one-shot per pipeline call, a single-slot cache
never grows and never risks returning stale results for a different frame.

**Caller contract:** this is only safe because every caller in this
codebase holds one `Frame` referenced for the entire span it's passed
around a single frame's worth of detector calls before moving on to the
next. CPython reuses a freed object's memory address, so a *transient*
`Frame` (constructed and immediately dropped, with no variable holding a
reference) could coincidentally get the same `id()` as the next one built
— harmless here because nothing constructs a `Frame` and discards it within
that span, but worth knowing before reusing this cache in a context that
does.
"""

from __future__ import annotations

from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.model import BaseInferenceModel, RawPrediction


class CachingInferenceModel(BaseInferenceModel):
    """Delegates to `wrapped`, memoizing `predict()` for repeat calls on the same frame."""

    def __init__(self, wrapped: BaseInferenceModel) -> None:
        self._wrapped = wrapped
        self._cached_frame_id: int | None = None
        self._cached_result: list[RawPrediction] = []

    def load(self) -> None:
        self._wrapped.load()

    def predict(self, frame: Frame) -> list[RawPrediction]:
        frame_id = id(frame)
        if frame_id != self._cached_frame_id:
            self._cached_result = self._wrapped.predict(frame)
            self._cached_frame_id = frame_id
        return self._cached_result

    def warmup(self) -> None:
        self._wrapped.warmup()

    @property
    def is_loaded(self) -> bool:
        return self._wrapped.is_loaded

    @property
    def class_names(self) -> dict[int, str]:
        return self._wrapped.class_names
