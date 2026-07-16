"""ByteTrack: IoU + Kalman-filter multi-object tracking with two-stage
association (BYTE), assigning persistent track IDs to per-frame detections.

Chosen over DeepSORT because it needs no appearance re-identification model
— just motion (Kalman filter) and IoU — which keeps tracking fast, GPU-free,
and free of an extra trained network to source/maintain. DeepSORT remains a
plausible future `tracker_registry` entry for deployments where occlusion
robustness from appearance features matters more than tracker latency.

Detections and tracks are matched only within the same `DetectionClass` — a
car box never absorbs a person track. Track IDs are unique per camera
(shared counter across classes for that camera).

Two-stage matching: detections at/above `high_confidence_threshold` get
first crack at matching every track of their class; only tracks stage 1
left unmatched get a second chance against detections between the
detector's own `confidence_threshold` floor and `high_confidence_threshold`.
This is the real BYTE algorithm, just operating on a stream already
filtered by each detector's own threshold (see docs/architecture.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from sentinel_detect.config.settings import TrackingSettings
from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.tracking import TrackedObject
from sentinel_detect.core.interfaces.tracker import BaseTracker, tracker_registry
from sentinel_detect.tracking.track import Track


@dataclass
class _CameraState:
    tracks: dict[int, Track] = field(default_factory=dict)
    next_id: int = 1


@tracker_registry.register("bytetrack")
class ByteTracker(BaseTracker):
    def __init__(self, settings: TrackingSettings) -> None:
        self._settings = settings
        self._camera_states: dict[str, _CameraState] = {}

    def reset(self, camera_id: str) -> None:
        self._camera_states.pop(camera_id, None)

    def update(self, camera_id: str, detections: list[Detection]) -> list[TrackedObject]:
        state = self._camera_states.setdefault(camera_id, _CameraState())

        for track in state.tracks.values():
            track.predict()

        high, low = self._split_by_confidence(detections)
        unmatched_high: list[Detection] = []

        for label in self._labels_present(state, high, low):
            track_ids = [tid for tid, t in state.tracks.items() if t.label == label]
            high_dets = [d for d in high if d.label == label]
            low_dets = [d for d in low if d.label == label]

            # Stage 1: high-confidence detections vs. every track of this class.
            matches, unmatched_tracks, unmatched_dets = self._associate(
                state, track_ids, high_dets, self._settings.iou_threshold
            )
            for tid, det in matches:
                state.tracks[tid].mark_matched(det)
            unmatched_high.extend(unmatched_dets)

            # Stage 2 (BYTE recovery): tracks stage 1 left unmatched vs.
            # low-confidence detections of the same class.
            matches2, _, _ = self._associate(
                state, unmatched_tracks, low_dets, self._settings.second_stage_iou_threshold
            )
            for tid, det in matches2:
                state.tracks[tid].mark_matched(det)

        # Only unmatched high-confidence detections start new tracks — BYTE
        # uses low-confidence detections only to rescue existing tracks.
        for det in unmatched_high:
            state.tracks[state.next_id] = Track(state.next_id, camera_id, det)
            state.next_id += 1

        # Age out tracks that have gone too long without a match.
        max_age = self._settings.max_age
        stale_ids = [tid for tid, t in state.tracks.items() if t.time_since_update > max_age]
        for tid in stale_ids:
            del state.tracks[tid]

        return [
            track.to_tracked_object()
            for track in state.tracks.values()
            if track.time_since_update == 0 and track.is_confirmed(self._settings.min_hits)
        ]

    def _split_by_confidence(
        self, detections: list[Detection]
    ) -> tuple[list[Detection], list[Detection]]:
        threshold = self._settings.high_confidence_threshold
        high = [d for d in detections if d.confidence >= threshold]
        low = [d for d in detections if d.confidence < threshold]
        return high, low

    @staticmethod
    def _labels_present(
        state: _CameraState, *detection_groups: list[Detection]
    ) -> set[DetectionClass]:
        labels = {t.label for t in state.tracks.values()}
        for group in detection_groups:
            labels.update(d.label for d in group)
        return labels

    @staticmethod
    def _associate(
        state: _CameraState,
        track_ids: list[int],
        detections: list[Detection],
        iou_threshold: float,
    ) -> tuple[list[tuple[int, Detection]], list[int], list[Detection]]:
        """Optimal (Hungarian) IoU-cost assignment between `track_ids` and `detections`."""
        if not track_ids or not detections:
            return [], list(track_ids), list(detections)

        cost = np.zeros((len(track_ids), len(detections)))
        for i, tid in enumerate(track_ids):
            predicted_bbox = state.tracks[tid].kalman.bbox
            for j, det in enumerate(detections):
                cost[i, j] = 1.0 - predicted_bbox.iou(det.bbox)

        row_idx, col_idx = linear_sum_assignment(cost)

        matches: list[tuple[int, Detection]] = []
        matched_rows: set[int] = set()
        matched_cols: set[int] = set()
        for raw_r, raw_c in zip(row_idx, col_idx, strict=True):
            r, c = int(raw_r), int(raw_c)
            if cost[r, c] <= 1.0 - iou_threshold:
                matches.append((track_ids[r], detections[c]))
                matched_rows.add(r)
                matched_cols.add(c)

        unmatched_tracks = [tid for i, tid in enumerate(track_ids) if i not in matched_rows]
        unmatched_dets = [d for j, d in enumerate(detections) if j not in matched_cols]
        return matches, unmatched_tracks, unmatched_dets
