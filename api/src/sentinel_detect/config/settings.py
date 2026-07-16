"""Layered application configuration.

All configuration is a `pydantic-settings` model tree rooted at `AppSettings`.
Values are sourced, in increasing priority, from: field defaults below, a
`.env` file, and environment variables. Nested fields are addressed with a
double-underscore delimiter, e.g.:

    SENTINEL_DATABASE__URL=postgresql+asyncpg://...
    SENTINEL_DETECTORS__WEAPON__ENABLED=false
    SENTINEL_DETECTORS__WEAPON__CONFIDENCE_THRESHOLD=0.6

`get_settings()` is the single entry point the rest of the application uses
to obtain configuration; it is memoized so settings are parsed once per
process and can be overridden in tests via `get_settings.cache_clear()`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Every built-in detector module, keyed identically to how it will register
# with `detector_registry` in Phase 2. Listing them here (rather than an open
# `dict[str, DetectorSettings]`) means an invalid detector key in config/env
# fails fast at startup instead of silently doing nothing.
BUILTIN_DETECTOR_KEYS = (
    "person",
    "vehicle",
    "weapon",
    "fire",
    "smoke",
    "ppe",
    "animal",
)


class DetectorSettings(BaseModel):
    """Per-detector-module configuration."""

    enabled: bool = True
    confidence_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    iou_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    model_key: str = "yolov11n"
    """Key of the model weights/backend this detector should use (see ModelSettings)."""


# Every built-in event rule module, keyed identically to how it registers
# with `event_rule_registry` in Phase 4.
BUILTIN_EVENT_RULE_KEYS = (
    "person_detected",
    "vehicle_detected",
    "weapon_detected",
    "fire_detected",
    "smoke_detected",
    "multiple_people",
    "crowd_detected",
    "restricted_area_intrusion",
    "tripwire_crossing",
    "loitering",
    "object_abandoned",
    "object_removed",
)


class EventRuleSettings(BaseModel):
    """Per-event-rule-module configuration.

    `params` is a small generic numeric knob bag (e.g. `min_count`,
    `dwell_seconds`, `movement_threshold_px`) rather than a bespoke field per
    rule, since each rule needs a different, small set of thresholds — a
    dedicated settings class per rule would be a lot of near-identical
    boilerplate for twelve rules. Each rule reads its own keys out of
    `params` with a sensible hardcoded fallback, so it works with zero
    config.
    """

    enabled: bool = True
    cooldown_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description="Minimum time between repeated events from this rule for the same key.",
    )
    params: dict[str, float] = Field(default_factory=dict)


# Every built-in alert channel module, keyed identically to how it registers
# with `alert_channel_registry` in Phase 5. SMS/push/Slack/Teams remain
# AlertChannelType enum entries only — no implementation exists yet.
BUILTIN_ALERT_CHANNEL_KEYS = ("rest", "websocket", "webhook", "email")


class AlertChannelSettings(BaseModel):
    """Per-alert-channel-module configuration.

    `params` is a generic string knob bag (webhook URL, SMTP host/creds,
    ...) rather than a bespoke field per channel, for the same reason
    `EventRuleSettings.params` is a generic float bag: four channels need
    four very different small parameter sets. Each channel parses its own
    keys out of `params` (`int()`/`float()`/`.lower() == "true"` as needed).
    """

    enabled: bool = True
    params: dict[str, str] = Field(default_factory=dict)


class DatabaseSettings(BaseModel):
    url: str = "sqlite+aiosqlite:///./data/sentinel.db"
    echo: bool = False
    pool_size: int = Field(default=5, ge=1)


class StorageSettings(BaseModel):
    backend: str = "local"
    local_path: Path = Path("./data/storage")


class SecuritySettings(BaseModel):
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=1)
    api_key_header: str = "X-API-Key"
    api_keys: list[str] = Field(
        default_factory=list,
        description=(
            "Static pre-shared keys accepted on api_key_header as an alternative to a JWT "
            "bearer token — for service/machine callers. Empty by default (no key grants "
            "access until configured); rotation/per-key management is a future enhancement."
        ),
    )
    rate_limit_per_minute: int = Field(default=120, ge=1)

    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str | None = Field(
        default=None,
        description=(
            "If set, an ADMIN user with this username/password is created at startup if no "
            "user with that username exists yet — solves the chicken-and-egg problem of "
            "needing a user to log in as before any user-management endpoint exists. Unset "
            "by default so a fresh deployment doesn't get a default admin account nobody "
            "asked for."
        ),
    )


class TrackingSettings(BaseModel):
    backend: str = "bytetrack"
    max_age: int = Field(
        default=30, ge=1, description="Frames a lost track is kept before removal."
    )
    min_hits: int = Field(
        default=3, ge=1, description="Matches required before a track is confirmed."
    )
    iou_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum IoU for stage-1 (high-confidence) matching.",
    )
    second_stage_iou_threshold: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum IoU for stage-2 (low-confidence recovery) matching.",
    )
    high_confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Detections at/above this confidence get first crack at matching "
            "every track (BYTE stage 1); detections below it (but still above "
            "the detector's own confidence_threshold) only get a shot at "
            "tracks that stage 1 left unmatched (BYTE stage 2)."
        ),
    )


class ModelSettings(BaseModel):
    device: str = "auto"
    """One of 'auto', 'cpu', 'cuda', 'cuda:0', etc. 'auto' picks GPU if available."""
    weights_dir: Path = Path("./data/weights")
    default_inference_size: tuple[int, int] = (640, 640)
    weights: dict[str, str] = Field(
        default_factory=lambda: {
            # Ultralytics-recognized name: auto-downloaded on first load if not
            # already present under weights_dir. Covers person/vehicle/animal.
            "yolov11n": "yolo11n.pt",
            # Custom fine-tuned checkpoints. Not shipped — no open pretrained
            # COCO model covers guns/rifles/fire/smoke/PPE. An operator must
            # place a real .pt file at weights_dir/<filename> and flip the
            # corresponding detector's `enabled` flag to use it.
            "yolov11n_weapon": "weapon.pt",
            "yolov11n_fire": "fire.pt",
            "yolov11n_smoke": "smoke.pt",
            "yolov11n_ppe": "ppe.pt",
        }
    )


class PipelineSettings(BaseModel):
    frame_skip: int = Field(
        default=0, ge=0, description="Process 1 of every (frame_skip + 1) frames."
    )
    batch_size: int = Field(default=1, ge=1)
    max_fps: float | None = Field(default=None, gt=0)


class LoggingSettings(BaseModel):
    level: str = "INFO"
    json_format: bool = True


def _default_detector_settings() -> dict[str, DetectorSettings]:
    """Person/vehicle/animal run on the stock COCO checkpoint and are on by
    default. Weapon/fire/smoke/ppe need fine-tuned weights nobody ships for
    free, so they default to disabled until an operator supplies real
    weights at `models.weights_dir` and flips `enabled` on.
    """
    return {
        "person": DetectorSettings(model_key="yolov11n"),
        "vehicle": DetectorSettings(model_key="yolov11n"),
        "animal": DetectorSettings(model_key="yolov11n"),
        "weapon": DetectorSettings(
            enabled=False, model_key="yolov11n_weapon", confidence_threshold=0.5
        ),
        "fire": DetectorSettings(enabled=False, model_key="yolov11n_fire"),
        "smoke": DetectorSettings(enabled=False, model_key="yolov11n_smoke"),
        "ppe": DetectorSettings(enabled=False, model_key="yolov11n_ppe"),
    }


def _default_event_rule_settings() -> dict[str, EventRuleSettings]:
    """All twelve built-in rules are enabled by default: unlike the
    weapon/fire/smoke/ppe detectors, none of these rules require external
    configuration to be harmless when their trigger never occurs (e.g.
    restricted_area_intrusion simply never fires if no regions are
    configured on a camera).
    """
    return {
        "person_detected": EventRuleSettings(cooldown_seconds=30.0),
        "vehicle_detected": EventRuleSettings(cooldown_seconds=30.0),
        "weapon_detected": EventRuleSettings(cooldown_seconds=5.0),
        "fire_detected": EventRuleSettings(cooldown_seconds=5.0),
        "smoke_detected": EventRuleSettings(cooldown_seconds=15.0),
        "multiple_people": EventRuleSettings(cooldown_seconds=30.0, params={"min_count": 2}),
        "crowd_detected": EventRuleSettings(cooldown_seconds=30.0, params={"min_count": 5}),
        "restricted_area_intrusion": EventRuleSettings(cooldown_seconds=15.0),
        "tripwire_crossing": EventRuleSettings(cooldown_seconds=0.0),
        "loitering": EventRuleSettings(cooldown_seconds=60.0, params={"dwell_seconds": 60.0}),
        "object_abandoned": EventRuleSettings(
            cooldown_seconds=0.0,
            params={"stationary_seconds": 30.0, "movement_threshold_px": 20.0},
        ),
        "object_removed": EventRuleSettings(cooldown_seconds=0.0, params={"min_hits": 5}),
    }


def _default_alert_channel_settings() -> dict[str, AlertChannelSettings]:
    """`rest` and `websocket` need no external resources — safe to enable by
    default. `webhook`/`email` need a real URL / real SMTP credentials to do
    anything, so they default to disabled until an operator configures one,
    same honesty pattern as the weapon/fire/smoke/ppe detectors.
    """
    return {
        "rest": AlertChannelSettings(enabled=True, params={"max_stored": "500"}),
        "websocket": AlertChannelSettings(enabled=True),
        "webhook": AlertChannelSettings(enabled=False, params={"timeout_seconds": "5.0"}),
        "email": AlertChannelSettings(
            enabled=False, params={"smtp_port": "587", "use_tls": "true"}
        ),
    }


class AppSettings(BaseSettings):
    """Root configuration object for SENTINEL Detect."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SENTINEL Detect"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    tracking: TrackingSettings = Field(default_factory=TrackingSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    detectors: dict[str, DetectorSettings] = Field(default_factory=_default_detector_settings)
    events: dict[str, EventRuleSettings] = Field(default_factory=_default_event_rule_settings)
    alerts: dict[str, AlertChannelSettings] = Field(default_factory=_default_alert_channel_settings)

    def enabled_detector_keys(self) -> list[str]:
        return sorted(key for key, cfg in self.detectors.items() if cfg.enabled)

    def enabled_event_rule_keys(self) -> list[str]:
        return sorted(key for key, cfg in self.events.items() if cfg.enabled)

    def enabled_alert_channel_keys(self) -> list[str]:
        return sorted(key for key, cfg in self.alerts.items() if cfg.enabled)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
