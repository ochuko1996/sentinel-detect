# SENTINEL Detect — Architecture

This document is the design-rationale record for every phase of this
project: why each piece is built the way it is, what trade-offs were made,
what's deliberately out of scope, and what each phase actually verified
(not just claimed). It grows by one section (design) and one section
(verification) per phase — see `README.md` for a shorter, task-oriented
overview and quickstart.

## Contents

- [Layering](#layering)
- [Plugin system](#plugin-system)
- [The detection engine (Phase 2)](#the-detection-engine-phase-2)
- [Object tracking (Phase 3)](#object-tracking-phase-3)
- [The rule engine (Phase 4)](#the-rule-engine-phase-4)
- [The alert engine (Phase 5)](#the-alert-engine-phase-5)
- [The database layer (Phase 6)](#the-database-layer-phase-6)
- [The FastAPI backend (Phase 7)](#the-fastapi-backend-phase-7)
- [Live streaming (Phase 8)](#live-streaming-phase-8)
- [Performance optimization (Phase 9)](#performance-optimization-phase-9)
- [Dockerization (Phase 10)](#dockerization-phase-10)
- [Testing (Phase 11)](#testing-phase-11)
- [Documentation (Phase 12)](#documentation-phase-12)
- [Configuration](#configuration)
- [Dependency injection](#dependency-injection)
- [Entities vs. schemas](#entities-vs-schemas)
- [What's deferred to later phases](#whats-deferred-to-later-phases)
- Verified — [Phase 1](#verified--phase-1) · [2](#verified--phase-2) ·
  [3](#verified--phase-3) · [4](#verified--phase-4) · [5](#verified--phase-5) ·
  [6](#verified--phase-6) · [7](#verified--phase-7) · [8](#verified--phase-8) ·
  [9](#verified--phase-9) · [10](#verified--phase-10) ·
  [11](#verified--phase-11) · [12](#verified--phase-12)

## Layering

```
core/            <- entities + interfaces (ports). No imports from any other package.
config/          <- pydantic-settings configuration tree.
detectors/       <- BaseDetector implementations, registered into detector_registry.
models/          <- BaseInferenceModel implementations (Ultralytics YOLO now; ONNX/TensorRT later).
tracking/        <- BaseTracker implementations (ByteTrack now; DeepSORT is a plausible addition).
events/          <- BaseEventRule implementations: the rule engine.
alerts/          <- BaseAlertChannel implementations: REST, WebSocket, webhook, email.
database/        <- Async SQLAlchemy engine/session + ORM models + Repository implementations.
security/        <- Password hashing, JWT tokens, rate-limit middleware.
storage/         <- BaseStorageBackend implementations.
streaming/       <- BaseVideoSource implementations, live per-camera streaming (Phase 8).
services/        <- use-case orchestration, depends only on core interfaces.
api/             <- FastAPI routers/schemas/dependencies. Presentation layer.
utils/           <- logging, Prometheus metrics, and other cross-cutting helpers.
main.py          <- composition root: builds the FastAPI app.
```

The dependency rule: everything points inward at `core/`. `core/` never imports
from `detectors/`, `api/`, `database/`, etc. This is what lets a whole category
of change — swapping YOLOv11 for RT-DETR, SQLite for Postgres, local disk for
S3 — happen by writing a new adapter, without touching `services/` or `api/`.

## Plugin system

Each pluggable concern (detector, tracker, event rule, alert channel, storage
backend, video source) has:

1. An ABC in `core/interfaces/` defining the contract.
2. A `Registry[T]` instance (`core/registry.py`) that concrete implementations
   register into via a decorator, keyed by a string.
3. A config field (`AppSettings`) that names which registered key(s) to
   activate, and with what parameters.

Example — adding a new detector (e.g. a future ANPR/license-plate module)
requires only:

```python
@detector_registry.register("license_plate")
class LicensePlateDetector(LabelMappedDetector):
    detector_key = "license_plate"
    label_map = {"license_plate": DetectionClass.LICENSE_PLATE}
```

No file in `core/`, `api/`, or `services/` changes. This is also how the
platform absorbs the roadmap items (ANPR, pose estimation, violence
detection, ...) without an architecture change — each is a new registry
entry.

## The detection engine (Phase 2)

`BaseInferenceModel` (raw boxes + class ids + confidence) and `BaseDetector`
(domain `Detection` objects, in the `DetectionClass` taxonomy) are separate
interfaces, joined by one concrete implementation:

- **`models/yolo.py::UltralyticsYoloModel`** wraps `ultralytics.YOLO`. It
  applies only a low raw-confidence floor (0.1) and standard NMS IoU (0.5) at
  the inference level — real thresholding happens per-detector, one layer up.
  `ultralytics`/`torch` are imported lazily inside `load()`, not at module
  scope, so the rest of the app works even without the optional `vision`
  extra installed.
- **`models/manager.py::ModelManager`** resolves a `model_key` (from
  `DetectorSettings.model_key`) to a cached, loaded model instance. Detectors
  sharing a `model_key` share one instance — by default `person`, `vehicle`,
  and `animal` all point at `"yolov11n"`, so one COCO checkpoint backs all
  three.
- **`detectors/base.py::LabelMappedDetector`** is the one concrete
  `BaseDetector` implementation every built-in detector subclasses. It filters
  raw predictions to the detector's own `label_map`, applies
  `confidence_threshold`, and maps the backend's class name to a
  `DetectionClass`. Name matching is case/separator-normalized
  (`"Hard-Hat"` == `"hard_hat"` == `"HARDHAT"`) because custom-trained
  checkpoints in the wild don't agree on naming conventions.

### COCO coverage is real, not assumed

The stock Ultralytics COCO checkpoint (`yolo11n.pt`, auto-downloaded on
first load) genuinely covers: `person`; `car`/`bus`/`truck`/`motorcycle`/
`bicycle`; `dog`/`cat`/`cow`/`horse`. It does **not** cover `goat`, `gun`,
`rifle`, `fire`/`flame`, `smoke`, or any PPE class — there is no free,
pretrained model for those. Rather than fake it, `_default_detector_settings()`
in `config/settings.py` ships `person`/`vehicle`/`animal` **enabled** and
`weapon`/`fire`/`smoke`/`ppe` **disabled**, each already pointed at a
`model_key` (`yolov11n_weapon`, `yolov11n_fire`, ...) an operator activates
by dropping a real fine-tuned `.pt` file at `models.weights_dir` and setting
`SENTINEL_DETECTORS__<NAME>__ENABLED=true`.

### Startup never crashes on a missing model

`detectors/factory.py::build_enabled_detectors` attempts to load every
*enabled* detector's model; if loading fails (missing custom weights, no
network for the first COCO download, `vision` extra not installed), it logs
a structured `detector_unavailable` error and excludes that detector rather
than raising — so e.g. losing network access degrades to "no active
detectors," not a crash. `GET /health` reports both `configured_detectors`
(what config says should run) and `active_detectors` (what actually loaded),
so this degradation is observable rather than silent.

### Redundant inference eliminated (Phase 9)

`person`/`vehicle`/`animal` share one model instance, but each
`BaseDetector.detect()` called `model.predict(frame)` independently — a
frame routed through all three ran the same COCO forward pass three times
for no benefit. `models/caching.py::CachingInferenceModel` wraps whatever
`ModelManager._build()` constructs with a single-slot cache keyed by
`id(frame)`: the first detector to call `predict()` for a given frame
actually runs inference; every other detector sharing that model instance
for the *same* frame gets the cached result. `Frame` is an unhashable
frozen dataclass (wraps a `numpy.ndarray`), so this can't be an ordinary
`==`/hash-based cache — identity is the only cheap, correct "same frame"
check, and it's valid precisely because every caller in this codebase holds
one `Frame` referenced for its entire span of detector calls before moving
to the next (see the module docstring for the id-reuse hazard this
depends on not happening).

## Object tracking (Phase 3)

`BaseTracker.update(camera_id, detections) -> list[TrackedObject]` assigns
persistent identities to per-frame detections. The one built-in
implementation, `tracking/byte_track.py::ByteTracker`, is a from-scratch
ByteTrack: a `KalmanBoxFilter` (`tracking/kalman_filter.py`, classic SORT
`[cx, cy, s, r, vcx, vcy, vs]` state) predicts each track's next position,
and `scipy.optimize.linear_sum_assignment` solves the optimal (Hungarian)
IoU-cost assignment between predictions and detections.

**Why ByteTrack over DeepSORT.** DeepSORT needs a trained appearance
re-identification CNN; ByteTrack needs only motion + IoU. That keeps
tracking fast, GPU-free, and free of another model to source or fine-tune.
`BaseTracker` stays registry-backed, so DeepSORT remains a legitimate future
`tracker_registry` entry for deployments where occlusion-robustness from
appearance matters more than latency.

**Per-camera, per-class association.** Tracks and detections are only ever
matched within the same `DetectionClass` (a car box never absorbs a person
track). Track IDs are unique per camera, with one shared counter across
classes for that camera — `reset(camera_id)` drops all state for it.

**Real two-stage BYTE matching, honestly scoped.** ByteTrack's actual
contribution is a second matching pass using low-confidence detections to
recover occluded objects a stricter threshold would otherwise drop. Since
each detector already discards anything below its own `confidence_threshold`
(Phase 2), the tracker can't reach below *that* floor. What it does do
faithfully: split whatever detections do arrive at `high_confidence_threshold`
(default 0.6) — detections at/above it get first crack at matching every
track of their class (stage 1); only tracks stage 1 left unmatched get a
second chance against the detections between the detector's floor and 0.6
(stage 2). Only unmatched *high*-confidence detections start new tracks —
low-confidence ones only rescue, never create.

**Emission rule.** `update()` only returns tracks with `hits >= min_hits`
(filters out one-off false-positive detections becoming spurious IDs) that
were actually matched in the current call (`time_since_update == 0`) — no
phantom predicted boxes for tracks that didn't match this frame. A lost
track is still kept internally for up to `max_age` frames in case it's
matched again later.

**One-shot camera_ids must be reset.** `ByteTracker` keeps per-`camera_id`
state indefinitely (by design — that's what lets a persistent
webcam/RTSP stream keep the same track IDs across calls). A one-shot input,
like a video upload, must generate a unique `camera_id` per request *and*
call `tracker.reset(camera_id)` when done, or state accumulates forever.
`POST /detect/video` (`api/routers/detect.py`) does exactly this: mints
`f"video-upload-{uuid4()}"` and resets in a `finally` block.

**Video decoding + inference no longer blocks the event loop (Phase 9).**
`POST /detect/video` still decodes the whole upload into a temp file and
processes it in the request handler — real streaming (arbitrary-length
RTSP/webcam feeds, backpressure, concurrent cameras) is Phase 8's job, not
this endpoint's — but every blocking call in that per-frame loop
(`cv2.VideoCapture.read`, `PipelineService.process_frame`, and
`DetectionService.detect` inside `POST /detect/image`) now runs via
`asyncio.to_thread`, the same pattern `StreamManager._run()` already used
for a live stream's per-frame loop. Verified live: a 300-frame real-inference
request that took ~35s left concurrent `GET /health` calls answering in
2-5ms throughout — before this fix, the whole server (including any active
`StreamManager` tasks) would have been frozen for that entire 35s.

## The rule engine (Phase 4)

`BaseEventRule.evaluate(EventContext) -> list[Event]` inspects the current
frame's tracked objects (and, for ROI rules, a camera's configured
`Region`s) and returns zero or more events. Twelve built-in rules cover
every example in the spec, in four families sharing two base classes
(`events/base.py`):

- **Presence** (`events/detected.py`, `LabelPresenceRule`): `person_detected`,
  `vehicle_detected`, `weapon_detected`, `fire_detected`, `smoke_detected` —
  fires while any tracked object matches a label set.
- **Count threshold** (`events/crowd.py`, `PersonCountThresholdRule`):
  `multiple_people` (≥2 people), `crowd_detected` (≥5, configurable).
- **ROI-aware** (`events/regions.py`): `restricted_area_intrusion` (a
  track's center falls inside a `RESTRICTED_ZONE` polygon) and
  `tripwire_crossing` (a person's track flips which side of a `TRIPWIRE`
  line it's on between frames — the standard 2D cross-product side test —
  emitting `PERSON_ENTERING` or `PERSON_LEAVING` depending on direction).
- **Stateful** (`events/loitering.py`, `events/object_state.py`):
  `loitering` (a person's `last_seen - first_seen` dwell time, already
  maintained by the tracker, exceeds a threshold); `object_abandoned` (a
  non-person track whose position hasn't moved beyond a pixel threshold for
  a duration — fires once per track); `object_removed` (a
  stably-tracked non-person track that vanishes between one frame and the
  next).

**Uniform rule construction, like the tracker.** Every rule takes exactly
one constructor arg, `EventRuleSettings` (`cooldown_seconds` + a generic
`params: dict[str, float]` bag) — `events/factory.py::build_enabled_rules`
builds any of the twelve identically, the same pattern
`ByteTracker(TrackingSettings)` uses.

**Cooldown, not per-frame spam.** `events/base.py::Cooldown` tracks a
last-fired timestamp per key (camera, or `camera:track_id`, or
`camera:region:track_id` depending on the rule) so a condition holding for
200 consecutive frames raises at most one event per configured interval,
not 200.

**`object_abandoned`/`object_removed` are honestly scoped.** This platform
has no dedicated "unattended bag/luggage" detector (no free pretrained
model provides one — same story as weapon/fire/PPE). Both rules are
implemented as genuine, class-agnostic stationary/disappearance tracking
that works correctly on whatever non-person class is actually tracked (a
car parked motionless in a restricted lane is a real, valid trigger today);
they become semantically sharper once a real object detector exists. They
are not placeholders — the tracking logic is real — but the *label* they
key off is a generic stand-in until that detector exists.

**Regions come from `Camera.regions`, but camera CRUD is Phase 7.** Until
`POST /camera`/ROI management endpoints exist, `POST /detect/video` accepts
an optional `regions_json` form field (a JSON array of `core.entities.camera.Region`)
so `restricted_area_intrusion`/`tripwire_crossing` can be genuinely
exercised against real footage now.

**Pipeline composition.** `services/pipeline_service.py::PipelineService`
is the full per-frame chain: `TrackingService.process_frame()` (detection +
tracking) feeds an `EventContext` into `EventEngine.evaluate()` (fan-out to
every active rule). `POST /detect/video` uses `PipelineService` and
aggregates both per-track summaries and every event raised across all
processed frames into its response.

## The alert engine (Phase 5)

`BaseAlertChannel.send(Event) -> None` delivers one event through one
channel; `AlertEngine.dispatch(events)` fans every event out to every active
channel, recording an `Alert` (SENT/FAILED + error) per (event, channel)
pair. `POST /detect/video` calls `alert_engine.dispatch(events)` right after
`PipelineService.process_frame()` returns them — matching the spec's
pipeline stage order (... → event detection → alert generation → ...).

Four channels, split by what's honestly deliverable in this environment:

- **`alerts/rest_channel.py::RestAlertChannel`** writes into `AlertStore`, a
  bounded in-memory deque. There's no database yet (Phase 6), so this
  doesn't survive a restart — but it's real, working storage, and
  `GET /alerts` reads from the exact same instance. Enabled by default.
- **`alerts/websocket_channel.py::WebSocketAlertChannel`** broadcasts to
  every client connected to `WS /ws/alerts` via a shared `ConnectionManager`
  (tracks live connections, drops any that error on send). Enabled by
  default; broadcasting to zero connected clients is a harmless no-op.
- **`alerts/webhook_channel.py::WebhookAlertChannel`** POSTs the event as
  JSON to a configured URL via `httpx.AsyncClient`. Disabled by default —
  needs `params.url` set (`SENTINEL_ALERTS__WEBHOOK__PARAMS__URL=...`).
- **`alerts/email_channel.py::SmtpEmailAlertChannel`** sends real email via
  stdlib `smtplib`/`email` — genuine code, not a stub, but disabled by
  default: it needs real SMTP credentials nobody can supply in this
  environment, matching the spec's own "Email (interface)" framing and the
  same honesty as the weapon/fire/PPE detectors needing real weights.
  `smtplib` is blocking, so the actual send runs via `asyncio.to_thread` to
  avoid blocking the event loop.

SMS/push/Slack/Teams remain `AlertChannelType` enum entries only — adding a
real one later is a new `alert_channel_registry` entry, no core changes.

**Uniform channel construction, like detectors/rules/tracker.** Every
channel's `__init__` takes `(settings: AlertChannelSettings, resources:
AlertResources)` — `alerts/resources.py::AlertResources` bundles the shared
`ConnectionManager`/`AlertStore` so channels that don't need one just
ignore it (mirroring `ModelManager` for detectors).
`alerts/factory.py::build_enabled_channels` builds every enabled channel
this way, logging and skipping (not crashing) one that's enabled but
missing required config — e.g. webhook without a URL — the same
graceful-degradation pattern as `build_enabled_detectors`.

**Verified against real sockets, not mocks.** The webhook channel is tested
against a real local `http.server.HTTPServer` (`tests/unit/test_webhook_channel.py`)
and the email channel against a minimal real local SMTP protocol stub
(`tests/unit/test_email_channel.py`) — both prove `httpx`/`smtplib` actually
open a socket and speak the protocol correctly, not just that a mocked
client was called as expected.

**A real bug this caught:** the first `WS /ws/alerts` implementation used a
`Depends()`-based dependency (`get_connection_manager(request: Request)`)
copied from the HTTP dependency pattern. FastAPI's dependency injection for
WebSocket routes requires the dependency to take `websocket: WebSocket`, not
`request: Request` — there is no HTTP request in a WebSocket connection.
This failed at runtime (not at import time, not under mypy) and was only
caught by actually exercising the route with `TestClient.websocket_connect`.
Fixed by reading `websocket.app.state.connection_manager` directly inside
the route handler instead of through a dependency.

## The database layer (Phase 6)

Six tables, one per persisted entity: `detections`, `events`, `cameras`,
`users`, `configurations`, and `alerts` (see below for why alerts serve as
the "logs" table). Async SQLAlchemy 2.0 throughout — `aiosqlite` for the
zero-setup SQLite default, `asyncpg` (the `postgres` extra) for the same
models against Postgres.

**Why `Alert` records are this platform's "logs" table.** The spec's DB
list includes "Logs" alongside events/detections. Rather than adding a
synthetic logging table nothing would actually write to yet (no auth, no
config-mutation API exists to generate audit-worthy events), `AlertRecord`
repurposes data we already produce for real: every alert dispatch attempt
(channel, SENT/FAILED, error, timestamps) is genuinely auditable — "was
this event's weapon_detected alert actually delivered via email at
14:32:01, and if not, why" is exactly what an operator needs a logs table
for. `AlertRecord.event_id` is a real foreign key into `events`.

**Camera/User/Configuration have no API surface yet.** Their ORM models and
repositories are complete and tested (`CameraRepository`, `UserRepository`,
`ConfigurationRepository`), ready for Phase 7 to build `POST /camera`,
login/JWT, and `POST /config` on top of — building the HTTP layer now would
duplicate that work. `Region`s on a `Camera` are stored as a JSON blob
rather than normalized into separate tables, since there's no ROI CRUD yet
to justify that complexity today.

**Repositories are written directly, not through a forced generic base.**
Five different entities with genuinely different shapes (UUID vs. `str`
primary keys, a real FK relationship for alerts, different natural
orderings) would fight a one-size-fits-all generic repository more than a
little duplication costs — each of the six repositories implements
`Repository[T, ID]` (`core/interfaces/repository.py`, from Phase 1)
directly with a small, explicit `_to_entity`/`_to_record` pair.

**A real SQLite gotcha this project hit, not a hypothetical one:** SQLite
has no native timezone-aware datetime type. `DateTime(timezone=True)`
stores a value correctly but SQLite always hands back a *naive* `datetime`
on read — which compared unequal to the original timezone-aware value in
the very first repository round-trip test. `database/types.py::UTCDateTime`
is a small `TypeDecorator` that re-attaches UTC tzinfo on read (every
datetime this app produces is UTC by convention), used on every timestamp
column. Postgres's native `timestamptz` doesn't need this, but applying it
universally keeps model code identical across both backends.

**`create_all()` for dev convenience, Alembic for real schema evolution.**
`database/engine.py::init_models` runs `Base.metadata.create_all()` at
every startup — idempotent, zero-setup, matches SQLite being the default.
Real migrations live in `migrations/` (Alembic, async template), with
`migrations/env.py` pulling the database URL from `AppSettings` (not a
hardcoded `alembic.ini` value) so `alembic upgrade head` always targets
whatever database the app itself is configured to use. **Operational
gotcha:** don't run both against the same fresh database — `init_models()`
already created every table via `create_all()`, so a subsequent
`alembic upgrade head` will fail trying to create tables that already
exist. Reconcile with `alembic stamp head` (marks the database as being at
that revision without re-running its DDL) if you need Alembic tracking on
a database `init_models()` already bootstrapped.

**Storage wiring.** `POST /detect/video` persists everything a run
produces at the end (not per-frame — cheaper than one commit per detection
across up to 2000 frames): every raw `Detection`, every `Event`, and every
`Alert` `AlertEngine.dispatch()` returned, in that order within one
session/transaction (events before alerts, since the FK requires the
referenced event to exist first). The response reports
`detections_stored`/`events_stored`/`alerts_stored` for observability.

## The FastAPI backend (Phase 7)

The remaining REST surface, sitting directly on top of Phase 6's
repositories: Camera CRUD (`GET /cameras`, `GET /cameras/{id}`,
`POST /camera`, `PUT /camera/{id}`, `DELETE /camera/{id}`), `GET /events`
and `GET /detections` (both paginated, both filterable by `camera_id` via
`Repository.list_by_camera` — an addition beyond the base `Repository[T,
ID]` interface, same precedent as `UserRepository.get_by_username`),
`POST /config`/`GET /config`/`GET /config/{key}`, plus the auth/security
layer needed to gate the mutating ones.

**Auth: JWT primary, API key secondary, both real.** `security/passwords.py`
hashes with `bcrypt` directly rather than `passlib` (which has had
long-standing bcrypt-version compatibility friction and is effectively
unmaintained). `security/tokens.py` issues/verifies JWTs via `PyJWT`.
`POST /auth/login` is a standard OAuth2 password flow — verifies against
`UserRepository`, returns a bearer token. `api/dependencies/auth.py::get_current_user`
accepts *either* a valid bearer token *or* a valid `X-API-Key` header
(checked against `SecuritySettings.api_keys`, a static pre-shared list —
real auth, but no per-key management/rotation UI, which would be a
distinct feature beyond what's asked here). An API key resolves to a
synthetic ADMIN-equivalent principal (`username="api-key"`), since
pre-shared service keys aren't tied to a specific user account.

**RBAC.** `require_role(min_role)` is a dependency factory enforcing
VIEWER < OPERATOR < ADMIN. Reads (camera/event/detection listing) need only
an authenticated principal; camera create/update need OPERATOR+; camera
delete and all `/config` mutations need ADMIN — the most destructive and
most blast-radius actions get the highest bar.

**Bootstrapping the first user.** There's no `POST /users` endpoint (not in
the spec's list), which creates a chicken-and-egg problem: something has to
create the first account before anyone can log in. `SecuritySettings.bootstrap_admin_password`,
if set, causes `main.py`'s lifespan to create an ADMIN user with that
username/password on startup if none exists yet with that username —
unset by default, so a fresh deployment doesn't silently get a default
admin account nobody asked for.

**Rate limiting.** `security/rate_limit.py::RateLimitMiddleware` is a real
in-memory sliding-window limiter (not a stub), keyed by `X-API-Key` if
present, else client IP, using `SecuritySettings.rate_limit_per_minute`
(configured since Phase 1, unused until now). `/health`, `/metrics`,
`/docs`, `/openapi.json`, `/redoc` are exempt — orchestrator health checks
and API-doc browsing shouldn't count against a caller's budget. Per-request
pruning only trims the *current* caller's own hit history, so a key that
simply stops being seen would keep its (now-empty) entry forever; **Phase
9** adds a periodic full sweep (`_maybe_sweep`, every 5 minutes) that drops
any key whose newest hit has already aged out of the window — enough to
bound memory over a long-running process without a real LRU structure,
since the actual requirement is "don't grow forever," not "evict the
least-recently-used key first."

**Metrics.** `GET /metrics` serves real Prometheus text format via
`prometheus-client` — HTTP request counts/latency (via `MetricsMiddleware`)
plus `sentinel_detections_total`/`sentinel_events_total`/`sentinel_alerts_total`,
incremented exactly where `POST /detect/video`'s storage stage already
persists that data (real instrumentation of real activity, not placeholder
gauges). Deliberately unauthenticated and rate-limit-exempt, matching
`/health` — Prometheus scrapers typically can't do an OAuth2 login flow;
network-level access control, not app-level auth, is the standard way to
protect a scrape endpoint.

**Audit logging via structured logs, not a new table.** Login
success/failure, authorization denials, and every camera/config mutation
are logged as structured `structlog` events (`login_succeeded`,
`camera_created`, `config_updated`, ...). `AlertRecord` already serves as
this platform's persisted "logs" table (Phase 6) for alert dispatch
history; a second, parallel audit-log table for administrative actions
would duplicate that role without new value at this scope — structured
logs are the pragmatic choice here.

**Deliberately not retrofitted with auth: `/detect/image`, `/detect/video`,
`/alerts`, `/ws/alerts`.** These were built and thoroughly tested across
Phases 2–5 as open endpoints. Retroactively gating them now would mean
updating authentication into every existing test across those phases for
scope that wasn't requested — a disproportionate, risky retrofit for a
"continue" instruction. The new administrative surface (camera/config
management) is where Phase 7's auth effort is deliberately concentrated;
securing the detection/alert endpoints too is a reasonable explicit ask for
a future phase.

**A real bug this design decision avoided:** repository classes here
implement the `Repository[T, ID]` interface's `list()` method by that exact
name. Adding `list_by_camera()` *after* `list()` in the same class caused
`mypy` to resolve the bare `list[Event]` return-type annotation to the
class's own `list` **method** instead of the builtin type — a genuine
Python name-shadowing gotcha (a class attribute named `list` shadows the
builtin within that class's own annotations, even under `from __future__
import annotations`). Fixed by writing `builtins.list[Event]` explicitly
in the affected signatures.

## Live streaming (Phase 8)

`POST /detect/video` (Phase 3) proved the pipeline against a bounded upload;
Phase 8 runs the exact same `PipelineService`/`AlertEngine`/repositories
against an *unbounded* per-camera feed as a background `asyncio.Task`, rather
than building a second, parallel pipeline implementation.

**`BaseVideoSource` (Phase 1's interface, first concrete implementations
now).** Two adapters cover every `SourceType`:

- **`streaming/opencv_source.py::OpenCVVideoSource`** wraps
  `cv2.VideoCapture`, which accepts either an integer device index
  (webcam/USB) or a URL/path string (RTSP, an IP camera, a local video file)
  uniformly — one class, registered under all five matching `SourceType`
  keys (`webcam`/`usb`/`rtsp`/`ip_camera`/`video_file`) via a loop rather
  than the usual one-decorator-per-class pattern, since one implementation
  genuinely serves all five.
- **`streaming/directory_source.py::DirectoryVideoSource`** polls a
  directory for image files — a `watch: bool` flag distinguishes one-shot
  batch draining (`watch=False`, used for bulk image processing) from
  indefinite monitoring (`watch=True`, used for a live camera substitute:
  a separate process drops snapshots into the directory).
  `streaming/factory.py::build_video_source` always passes `watch=True` for
  `SourceType.DIRECTORY` when building a *stream* source (batch mode has no
  live-stream equivalent to start/stop).

**`StreamManager`** (`streaming/stream_manager.py`) owns one `asyncio.Task`
per active camera_id, each running the same
detect → track → evaluate-rules → dispatch-alerts → persist chain
`PipelineService`/`AlertEngine` already implement, reusing
`PipelineSettings.frame_skip`/`max_fps` (configured since Phase 1, wired
into actual code for the first time here) to bound CPU/broadcast rate.
`StreamBroadcaster` (`streaming/broadcaster.py`) fans each processed frame's
tracked-object summary out to every `WS /ws/stream/{camera_id}` client for
that camera — a separate, per-camera-keyed connection registry from Phase
5's global `ConnectionManager` (`/ws/alerts` carries rule-engine events only,
never raw per-frame detections).

**A real bug this caught: cancelling a stream could hang forever.**
`_run()`'s frame loop calls `await asyncio.to_thread(source.read)` because
`cv2.VideoCapture.read()`/directory polling are blocking calls. The first
`StreamManager.stop()` implementation called `task.cancel()` then `await
task` — but a `concurrent.futures.Future` backing an *already-running*
executor thread can't actually be cancelled; cancellation only takes effect
once that blocking call returns on its own. Against `DirectoryVideoSource` in
`watch=True` mode over an empty directory, `read()` polls forever, so
`task.cancel()` never had anything to interrupt — a hermetic test starting
and then stopping such a stream hung indefinitely (caught by actually
running the test, not by mypy/ruff, which saw nothing wrong). Fixed two
ways: `DirectoryVideoSource` now waits on a `threading.Event` instead of
`time.sleep`, so `close()` called from another thread wakes a blocked
`read()` immediately; and `StreamManager.stop()` now calls `source.close()`
*before* `task.cancel()`/`await task`, not after (previously `close()` only
ran in `_run()`'s `finally`, which a blocked task never reaches). This is
necessarily best-effort for `OpenCVVideoSource` against a stalled RTSP feed
— releasing a `cv2.VideoCapture` concurrently with an in-flight blocking
`read()` on another thread isn't guaranteed safe in OpenCV, so `stop()` may
still wait out that read on a genuinely stalled camera; documented as a
known limitation rather than papered over.

**Endpoints.** `GET /detect/stream` (list active streams, VIEWER+),
`POST /detect/stream` (start, OPERATOR+ — 404 unknown camera, 400 disabled
camera, 409 already streaming), `DELETE /detect/stream/{camera_id}` (stop,
OPERATOR+ — 404 if not active). `WS /ws/stream/{camera_id}` reads
`websocket.app.state.stream_broadcaster` directly rather than through a
`Depends()`, reusing the same fix Phase 5's `/ws/alerts` bug established for
WebSocket routes.

## Performance optimization (Phase 9)

Four concretely-flagged gaps, each closed with the smallest change that
actually closes it — no speculative new machinery (e.g. no real batched
inference, no LRU cache library), reusing patterns this codebase already
established rather than inventing new ones:

- **Redundant inference** (see "Redundant inference eliminated" under
  Phase 2, above) — `CachingInferenceModel`.
- **The event loop blocking during `/detect/image`/`/detect/video`** (see
  "Video decoding + inference no longer blocks the event loop" under
  Phase 3, above) — `asyncio.to_thread` around every blocking call in
  those handlers, the same pattern `StreamManager._run()` already used.
- **Rate limiter memory growth** (see "Rate limiting" under Phase 7,
  above) — a periodic sweep evicting quiet keys.
- **`DatabaseSettings.pool_size` configured since Phase 6 but never
  applied.** `database/engine.py::create_engine` now passes it to
  `create_async_engine`. Discovered while wiring this up: SQLAlchemy
  raises `TypeError` for `pool_size` when the URL resolves to a pool class
  that doesn't accept it — a real case being SQLite's `:memory:` URL,
  which always uses `StaticPool` regardless of this setting. Rather than
  let a previously-harmless (because unused) config value start crashing
  startup for that URL, `create_engine` retries without `pool_size` on a
  `TypeError`, so an in-memory database still degrades to the engine's own
  default pooling instead of failing to boot.

## Dockerization (Phase 10)

**Multi-stage build.** `Dockerfile`'s `builder` stage installs a pinned `uv`
binary (`COPY --from=ghcr.io/astral-sh/uv:0.5`, not a `pip install uv`
bootstrap step) and runs `uv sync --frozen --no-dev` into `/app/.venv`; the
`runtime` stage copies only that venv plus `src/`/`alembic.ini`/`migrations/`
— `uv` itself, its cache, and the build context never reach the final image.
`[tool.uv] package = true` means `uv sync` also builds this project's own
wheel, which needs `src/` *and* `README.md` present at sync time (`[project]
readme = "README.md"` in `pyproject.toml`) — both are copied before `uv
sync` runs, not after. **A real bug this caught:** the first attempt copied
only `pyproject.toml`/`uv.lock`/`src/`, and the build failed with `Error:
failed to open file '/app/README.md'` from the `uv_build` backend — found
by actually running `docker build`, not by inspecting the Dockerfile.

**The ML backend is a build arg, not a fixed choice.** `ARG UV_EXTRA_ARGS`
(default empty) is appended to `uv sync`, so `docker build --build-arg
UV_EXTRA_ARGS="--extra vision --extra postgres" .` opts into real YOLO
inference and/or Postgres at build time — the same optional-extras split
`pyproject.toml` already uses for local development, just exposed as a
build-time choice instead of only a `uv sync` flag. The default (no extra)
produces a working image with every non-ML capability (detection engine
architecture, tracking, events, alerts, database, full API, streaming) —
`active_detectors` comes back empty and `GET /health` says so, the same
honest degradation `build_enabled_detectors` already does when `ultralytics`
isn't installed locally.

**A real, non-obvious runtime dependency this Dockerfile documents.**
`opencv-python-headless` — despite shipping no GUI bindings — still
dynamically links against `libGL`/`libgomp` on Debian; without
`libgl1`/`libglib2.0-0`/`libgomp1` installed in the runtime stage, `import
cv2` (and therefore the whole app) fails at startup on a bare
`python:3.12-slim` image. This is a well-known real gotcha for this exact
package/base-image combination, not a hypothetical one.

**Non-root, and the one directory the app actually writes to.** The
runtime stage creates an unprivileged `sentinel` user and runs the process
as it; `/app/data` (sqlite db, downloaded/uploaded model weights, stored
evidence — the only paths this app writes to, per `SENTINEL_DATABASE__URL`/
`SENTINEL_STORAGE__LOCAL_PATH`/`SENTINEL_MODELS__WEIGHTS_DIR`'s Docker-image
defaults) is `chown`'d to that user and meant to be a mounted volume so it
survives container recreation — `docker-compose.yml` mounts `./data` there.

**`HEALTHCHECK` without adding a package.** A one-line `python -c
"import urllib.request..."` call rather than `curl`/`wget`, since neither
ships in `python:3.12-slim` and installing one just for a health probe
would be a needless runtime dependency next to a Python interpreter that
can already do the same GET request.

**No `.env` baked into the image.** `.dockerignore` excludes `.env` (and
`data/`, `tests/`, `docs/`) from the build context entirely — inside the
container, `pydantic-settings`' own `env_file=".env"` lookup simply finds
nothing, so all real configuration must come from actual container
environment variables (`docker-compose.yml`'s optional `env_file: - path:
./.env, required: false`, `docker run -e`, or a real orchestrator's secret
injection) — the standard production practice of not baking secrets into
an image, not a limitation.

**docker-compose.yml matches the app's own "SQLite is zero-setup" stance.**
`docker compose up --build` runs the API alone against SQLite by default —
no other services required, mirroring the non-Docker zero-setup path.
Postgres is an opt-in `profiles: ["postgres"]` service (`docker compose
--profile postgres up`), matching the `postgres` extra already being
opt-in for local development — not started unless explicitly asked for.

## Testing (Phase 11)

Every phase since Phase 2 shipped with its own tests as it was built —
Phase 11 is a dedicated hardening pass over the *whole* suite: measuring
real coverage, closing genuine gaps it found, and wiring CI, rather than
introducing a new testing approach.

**A real coverage-tooling bug this phase found before trusting any number
from it.** `coverage.py` (via `pytest-cov`) only traces the *main* thread
and the *main* greenlet unless told otherwise. This app's test suite
crosses both boundaries constantly: Starlette's `TestClient` runs the whole
ASGI app on a background thread (`anyio.from_thread.start_blocking_portal`),
and SQLAlchemy's async engine bridges every blocking DBAPI call through a
greenlet switch (`greenlet_spawn`, used by both `aiosqlite` and `asyncpg`).
Without `concurrency = ["thread", "greenlet"]` in `[tool.coverage.run]`
(`pyproject.toml`), a *first* coverage run showed `api/routers/cameras.py`
at 60% — every route's success/error body past its first `await` reported
as "Missing" even though the actual behavior worked and its test asserted
the right response. Proven with a debug `print()` directly in `get_camera`:
the branch printed (so it genuinely ran) while coverage still called it
uncovered — a tooling false negative, not a missing test. Fixing the config
brought that same file to 94% immediately, no test changes; the real
overall baseline was 96%, not 94%, once corrected. This is worth knowing
before trusting a coverage number from *any* FastAPI + SQLAlchemy-async
project without checking this setting.

**Gaps closed from the corrected baseline (96% -> 99%).** All six
repositories' `update`/`delete`/`list` paths that were genuinely never
exercised (not a tracing artifact) — e.g. `UserRepository` had no test for
`list()`, `update()`, or a successful `delete()`, only construction and the
`NotFoundError` path; `AlertRepository.delete()` had no test at all.
`StreamManager`'s frame_skip/max_fps throttling, its `VideoSourceError`/
generic-`Exception` handling in `_run()`, and a source that exhausts on its
own (vs. every other test explicitly calling `stop()`) had zero coverage.
`main.py`'s bootstrap-admin-on-startup block and the model-warmup-failure
handler were untested — closed with a test that builds a fresh
`create_app()` under real bootstrap env vars (`get_settings()` is
process-memoized, so cleared before/after to avoid leaking into other
test files that import the shared `app`) and one that monkeypatches
`ModelManager.loaded_models` to a model whose `warmup()` raises, proving
startup survives it. Several event rules (`MultiplePeopleRule`,
`LoiteringRule`, `RestrictedAreaIntrusionRule`, `TripwireCrossingRule`) had
never had their cooldown behavior or stale-state cleanup exercised, despite
`LabelPresenceRule`'s equivalent cooldown test existing since Phase 4 —
same rule, never actually proven for the sibling classes. `POST
/detect/video`'s track-accumulation, event-dispatch, and storage loops were
provably reachable in code but never exercised by a test, since every
existing test's synthetic footage contains no real detectable objects;
closed with FastAPI's own `app.dependency_overrides` mechanism (not a
patched module) swapping in a `PipelineService` built from the same
deterministic fake-detector pattern `test_stream_manager.py` already used.

**What's deliberately still not covered, and why that's a decision, not an
oversight:**
- `core/interfaces/video_source.py`'s abstract method bodies — they're
  `@abstractmethod` stubs that raise if ever called directly; there is no
  meaningful test for code that cannot execute.
- `models/yolo.py`'s error branches (`ModelLoadError` on a real corrupt
  weights file, the `cuda` half of `_resolved_device`) need either a GPU or
  deliberately corrupting a real downloaded checkpoint — environment-
  dependent in the same way `/dev/video0` availability was in Phase 8.
- `alerts/email_channel.py`'s `starttls()`/`login()` calls — the real local
  SMTP stub server `test_email_channel.py` already uses (real socket, real
  EHLO/MAIL/RCPT/DATA) explicitly implements no STARTTLS/AUTH, documented
  in that file's own docstring; building a TLS-capable test stub just to
  close two lines isn't proportionate to what it would cost.

**CI.** `.github/workflows/ci.yml` runs `ruff check`, `mypy src`, and `uv
run pytest --cov` on every push/PR — the same three commands this project
has run manually at the end of every phase, now automated. Deliberately
installs only `uv sync --extra dev` (no `vision` extra): CI stays fast, and
`test_detect_image_live.py` already auto-skips via `pytest.importorskip`
when `ultralytics` isn't installed, so nothing hermetic goes untested.

## Documentation (Phase 12)

Every phase already documented its own design decisions as it was built —
this phase is a consolidation and completeness pass over documentation
*as a deliverable in its own right*, not new design.

**A real, checkable gap: every endpoint's `/docs` page had no
description.** FastAPI derives each endpoint's OpenAPI `description` from
that *route function's own* docstring — not the module docstring, even
though every router file already has a thorough one. Checking this isn't
guesswork: `app.openapi()["paths"][path][method].get("description")` was
empty for all 19 endpoints before this phase. Fixed by adding a concise
docstring to every route function (what it does, auth requirement, the
specific 4xx conditions, and a pointer to a related endpoint where one
exists) — verified the same way afterward, this time confirming zero are
empty rather than assuming the fix worked.

**`.env.example` was audited against `AppSettings`, not just extended by
guesswork.** `SENTINEL_TRACKING__*` (ByteTracker tuning, real since Phase
3) and `SENTINEL_PIPELINE__FRAME_SKIP`/`MAX_FPS` (real since Phase
1/8-9) had no entries at all despite being genuinely operator-tunable;
`SECURITY__JWT_ALGORITHM`/`JWT_EXPIRE_MINUTES`/`API_KEY_HEADER` and
`DATABASE__ECHO`/`POOL_SIZE` were similarly absent. Added, then verified by
uncommenting every line in a copy of the file and constructing a real
`AppSettings(_env_file=...)` from it — every added variable name was
checked against the real field it claims to set, not assumed correct.
`PipelineSettings.batch_size` was deliberately *not* added: no real batching
exists (see Phase 9), and documenting it would suggest otherwise — the same
honesty standard applied to every other undocumented-on-purpose gap in this
project.

**A gap flagged, not silently fixed: no CORS middleware.** Every test and
live-boot check in this document talks to the API directly, so this was
never going to surface on its own — worth stating plainly in "What's
deferred to later phases" rather than leaving a future browser-based client
to discover it the hard way.

**Table of contents added to this document** (now 12 phases deep) and an
`app description=` added to `create_app()`'s `FastAPI(...)` call, so the
auto-generated `/docs` landing page explains the platform and auth model
before a reader reaches a single endpoint.

## Configuration

`AppSettings` (`config/settings.py`) is a `pydantic-settings` tree. Values
resolve from, in increasing priority: field defaults, `.env`, process
environment. Nested settings use `__` as the env delimiter:

```
SENTINEL_DATABASE__URL=postgresql+asyncpg://...
SENTINEL_DETECTORS__WEAPON__CONFIDENCE_THRESHOLD=0.6
```

`detectors: dict[str, DetectorSettings]` is pre-seeded with every built-in
detector key (`BUILTIN_DETECTOR_KEYS`) so an env var can target any one of
them without redeclaring the whole map. `get_settings()` is process-memoized
(`functools.lru_cache`); tests call `get_settings.cache_clear()` to isolate
env-var-driven cases.

SQLite (`sqlite+aiosqlite:///./data/sentinel.db`) is the default database URL
for zero-setup local development; switching to Postgres is one env var plus
`uv sync --extra postgres` once Phase 6 lands the SQLAlchemy layer.

## Dependency injection

No DI framework. FastAPI's own `Depends()` mechanism handles the API layer
(see `api/dependencies/config.py`); services and adapters elsewhere take
their dependencies as plain constructor arguments. A composition root
(`main.py`, growing in later phases) is the one place concrete
implementations get wired to interfaces.

## Entities vs. schemas

`core/entities/` are the domain model — plain pydantic models (mostly
`frozen=True`) with no FastAPI/SQLAlchemy awareness. `api/schemas/` holds
request/response shapes for the HTTP layer; they may differ from entities
(pagination envelopes, partial updates) and never leak into `services/` or
`core/`. `Frame` (`core/entities/media.py`) is deliberately a slotted
dataclass, not a pydantic model — it's constructed on the per-frame hot path
and wraps a raw `numpy.ndarray`, which pydantic can't validate natively
without overhead we don't want there.

## What's deferred to later phases

An interface exists now for storage (`core/interfaces/storage.py`), but no
concrete implementation does yet — `storage/` still contains only a
docstring-only `__init__.py`. `streaming/` (Phase 8) is now fully
implemented (see above) — note its endpoints (`/detect/stream`,
`/ws/stream/{camera_id}`) are gated (OPERATOR+/VIEWER+), unlike the still-open
`/detect/*`/`/alerts`/`/ws/alerts` surface from Phases 2-5. Auth on that
older detection/alert surface, ROI CRUD as its own resource (regions
currently travel embedded in a `Camera`), refresh tokens, and per-API-key
management/rotation are reasonable future asks beyond what's been built so
far.

**No CORS middleware is configured.** Every integration test and every
live-boot verification in this document talks to the API directly (server
to server, or `curl`/a Python client), not from a browser page served on a
different origin — so this gap has never actually blocked anything built
so far. A browser-based client (there's an empty `client/` directory
alongside this API, reserved for exactly that) would need
`fastapi.middleware.cors.CORSMiddleware` added to `create_app()` with an
explicit allowed-origins list before it could call this API cross-origin.
Flagged here rather than silently discovered later.

## Verified — Phase 1

- `uv sync --extra dev` installs cleanly on Python 3.12.
- `uv run ruff check .` / `uv run mypy src` — clean, strict.
- `uv run uvicorn sentinel_detect.main:app` boots and serves `GET /health`
  and `GET /docs`.

## Verified — Phase 2

- `uv run pytest` — unit tests cover `LabelMappedDetector` matching/threshold
  logic (fake models, no network), `ModelManager` error handling, and
  `build_enabled_detectors` graceful degradation, all hermetically.
- `uv sync --extra dev --extra vision` installs `ultralytics`/`torch`/
  `onnxruntime` on top of the base environment.
- With the `vision` extra installed, `POST /detect/image` was exercised
  end-to-end against the real `yolo11n.pt` checkpoint (auto-downloaded on
  first load) via `tests/integration/test_detect_image_live.py` — this test
  is skipped automatically (`pytest.importorskip`) when `ultralytics` isn't
  installed, so the default `dev`-only test run stays hermetic and fast.
- Discovered and fixed a real dependency conflict: `ultralytics` depends on
  `opencv-python` (GUI build), which installs the same `cv2` module as our
  own `opencv-python-headless` under a different package name — having both
  in one venv corrupts the install (uninstalling one deletes files the other
  needs). Fixed via `[tool.uv] override-dependencies` in `pyproject.toml`,
  making the `opencv-python` requirement unsatisfiable-but-harmless so uv
  never installs it; our own `opencv-python-headless` still provides `cv2`.

## Verified — Phase 3

- `uv run pytest` — 7 `ByteTracker` tests cover: confirmation delay
  (`min_hits`), ID persistence across smoothly-moving frames, track removal
  after `max_age` (and that a reappearance gets a *new* ID), per-class
  isolation with overlapping boxes, real BYTE stage-2 recovery of a
  low-confidence detection onto an existing track, low-confidence detections
  never starting a new track on their own, and `reset()`. Plus 4
  `KalmanBoxFilter` tests and 3 `TrackingService` tests — all hermetic, no
  network or ML backend required.
- `POST /detect/video` was exercised end-to-end with the `vision` extra
  installed against a real synthetic multi-frame `.mp4` (`cv2.VideoWriter`):
  confirmed real YOLO inference plus `ByteTracker` run per frame, the
  response reports `frames_processed` matching the input, and camera state
  is cleaned up afterward (no leaked tracker state for one-shot uploads).

## Verified — Phase 4

- `uv run pytest` — 21 event-rule tests, fully hermetic (rules evaluated
  directly against constructed `EventContext`s, no network/ML backend):
  every presence rule fires/is silent correctly and respects severity;
  count-threshold rules respect their configured minimum; restricted-zone
  intrusion fires only for tracks actually inside the polygon and is a
  no-op with no regions configured; tripwire crossing fires only on an
  actual side-flip (not on staying on one side), emits opposite event types
  for opposite directions, and ignores non-person tracks; loitering
  respects the dwell threshold; object_abandoned fires once per track,
  resets its clock on real movement, and ignores person tracks;
  object_removed fires only for tracks that were stably present
  (`hits >= min_hits`) and only once they actually disappear.
- `POST /detect/video` was exercised live (`vision` extra installed) with a
  `regions_json` payload (a restricted zone covering the whole frame)
  against a real synthetic video: confirmed the endpoint parses the JSON
  region, decodes and processes every frame, reports all 12 rules and all 3
  default detectors as active, and returns a well-formed (here, empty —
  the synthetic footage contains no real COCO objects, same honest caveat
  as Phase 2/3's live checks) `tracks`/`events` response with no errors.
- `GET /health` now also reports `enabled_event_rules`.

## Verified — Phase 5

- `uv run pytest` — `AlertEngine` tested with fake channels (dispatch fans
  out to every channel, a failing channel's `AlertDeliveryError` is
  recorded without stopping delivery to the others); `AlertStore` tested
  for ordering/bounding; `WebhookAlertChannel` tested against a real local
  `http.server.HTTPServer` (real JSON POST over a real socket, real
  `AlertDeliveryError` on a 500 response or an unreachable host);
  `SmtpEmailAlertChannel` tested against a minimal real local SMTP protocol
  stub (real EHLO/MAIL/RCPT/DATA exchange over a real socket); both
  channels' "missing required config" `ConfigurationError` paths covered.
  All hermetic — no network, no ML backend.
- `tests/integration/test_alerts_api.py` dispatches a synthetic event
  through the real app's wired-up `app.state.alert_engine` and confirms it
  reaches both `GET /alerts` and a real `TestClient.websocket_connect`
  client — proving the `AlertEngine`/`AlertStore`/`ConnectionManager` wiring
  end-to-end independent of whether the ML backend is installed.
- **A real bug this caught:** the first `WS /ws/alerts` implementation used
  an HTTP-style `Depends()` dependency that doesn't work for WebSocket
  routes (see above) — it passed every static check (ruff, mypy) and only
  failed when the route was actually exercised with a live connection.
  Fixed and re-verified.
- Live-booted the real server process (`uvicorn`, separate process, real
  TCP sockets — not `TestClient`'s in-process transport) and confirmed:
  `GET /health` reports `rest`/`websocket` as both configured and active by
  default; `GET /alerts` returns `[]` on a fresh boot; a real
  `websockets`-library client successfully connects to `ws://.../ws/alerts`
  over a real socket.

## Verified — Phase 6

- `uv run pytest` — 23 repository tests against a real (temp-file)
  `aiosqlite` database per test, not a mocked session: full CRUD round-trip
  for all six repositories, `NotFoundError` on updating/deleting a missing
  row, most-recent-first ordering, pagination (`offset`/`limit`), the
  `AlertRepository` ↔ `EventRepository` foreign-key relationship (an alert
  can't be created before its event exists; fetching an alert reconstructs
  its full nested `Event`), and JSON-column round-tripping for structured
  `Event.metadata`/`ConfigurationEntry.value`.
- **A real bug this caught, in the very first round-trip test:** SQLite
  hands back naive `datetime`s regardless of `DateTime(timezone=True)`, so
  a fetched `Detection` compared unequal to the one just created (mismatched
  tzinfo). Fixed with `database/types.py::UTCDateTime`, a `TypeDecorator`
  that re-attaches UTC tzinfo on read; applied to every timestamp column in
  every model.
- Alembic migration lifecycle verified directly: generated the initial
  autogenerated revision, ran `alembic upgrade head` against a clean SQLite
  file (created all 6 tables), `alembic downgrade base` (dropped them all
  cleanly), then `alembic upgrade head` again (recreated them) — a full
  reversible round trip, not just a one-way `upgrade` that was never tested
  going backward.
- Live-verified persistence against the real running server process, not
  just `TestClient`: booted `uvicorn` as a separate process, confirmed it
  auto-created `data/sentinel.db` with all 6 tables via `init_models()` on
  startup, then — using a separate Python process — inserted a `Detection`
  through `DetectionRepository` directly into that same on-disk database
  file while the server was still running, and confirmed the row was
  genuinely there via a raw `sqlite3` query. This proves the persistence
  layer works against a real file on disk under real concurrent access, not
  only inside a single in-process test.
- `POST /detect/video`'s storage stage was exercised live end-to-end
  (`detections_stored`/`events_stored`/`alerts_stored` present and
  self-consistent in the response; zero counts are correct and honest given
  the synthetic footage used, same caveat as every prior phase's live
  checks).

## Verified — Phase 7

- `uv run pytest` — hermetic coverage of every new primitive: `bcrypt`
  hash/verify round-trip and malformed-hash handling; JWT create/decode
  round-trip plus rejection of a wrong-secret token, an expired token,
  garbage input, and a token missing required claims; the rate limiter
  against a real minimal FastAPI app (within-limit succeeds, over-limit
  gets 429 + `Retry-After`, exempt paths are never limited, different
  API keys get independent limits); `get_current_user`/`require_role`
  called directly (bypassing FastAPI's DI — the `Annotated[...,
  Depends(...)]` aliases are ordinary types at the Python level) against a
  real temp-file database, covering the API-key path (configured/
  unconfigured), the JWT path (valid/nonexistent-user/inactive-user), and
  every RBAC boundary.
- Integration tests hit the real app + real database: `POST /auth/login`
  end-to-end (real bcrypt verify, real JWT issuance, real 401s for bad
  credentials/tokens); camera CRUD with real RBAC enforcement (VIEWER can
  read but not create, OPERATOR can create/update but not delete, ADMIN
  can do everything, duplicate IDs 409, missing IDs 404, a restricted-zone
  `Region` round-trips through create→get intact); `GET /events`/
  `GET /detections` camera-filtering against seeded rows, and a 401 with no
  credentials; `/config` read-vs-write RBAC and the create-then-update
  upsert path; `/metrics` returns real Prometheus text format whose
  `sentinel_http_requests_total` counter reflects the actual requests just
  made in that same test.
- **A real bug this design caught:** naming a repository method `list()` (to
  satisfy the `Repository[T, ID]` interface) shadowed the builtin `list`
  type for any later method's return-type annotation in the same class —
  `mypy` failed with "Function ... is not valid as a type" on
  `list_by_camera`'s signature. Fixed with an explicit `builtins.list[...]`
  reference; documented above so the next repository that needs a second
  listing method doesn't rediscover it the hard way.
- Live-verified the full stack against a real running server process with
  a bootstrap admin configured via env var: logged in over real HTTP,
  created/listed/updated/deleted a camera with the resulting JWT, confirmed
  an unauthenticated request gets a real 401, confirmed `/config` upsert
  round-trips, confirmed `/metrics` shows real per-endpoint request counts
  matching the calls just made (including the 401), and confirmed
  `/health` stays reachable regardless of rate-limit pressure.

## Verified — Phase 8

- `uv run pytest` — hermetic unit tests against real files/devices, no
  mocks: `OpenCVVideoSource` against a real synthetic `.mp4` (reads every
  frame, then exhausts) plus real failure paths (nonexistent file,
  unavailable device index, unreachable `rtsp://` host) and, where this
  sandbox happens to expose a real `/dev/video0`, a genuine device-index
  open+read (skipped gracefully in environments without one);
  `DirectoryVideoSource` against a real temp directory in both batch mode
  (drains existing files in sorted order, ignores non-images) and watch mode
  (a background thread drops a new file mid-poll and `read()` picks it up).
  `StreamManager` tested against a real `PipelineService`/`AlertEngine`/temp-file
  SQLite: starting a directory stream genuinely processes real image files,
  persists real `Detection`/`Event` rows, and dispatches a real alert;
  double-starting the same camera 409s; stopping an inactive camera 404s;
  `stop_all()` tears down multiple concurrent streams; starting an
  unsupported `SourceType.IMAGE` fails fast without leaking a task.
- **A real bug this caught:** the first `StreamManager.stop()` could hang
  forever cancelling a stream backed by `DirectoryVideoSource` in watch mode
  over an empty directory — `task.cancel()` can't interrupt a blocking call
  already running on a worker thread via `asyncio.to_thread`, and `close()`
  only ran in `_run()`'s `finally`, which a blocked task never reaches. Found
  by the hermetic `StreamManager` test suite actually hanging (not by
  mypy/ruff), fixed by having `DirectoryVideoSource` wait on a
  `threading.Event` `close()` can set from another thread, and by moving
  `source.close()` to run *before* `task.cancel()` in `stop()`. See "Live
  streaming (Phase 8)" above for the full writeup.
- `tests/integration/test_stream_api.py` hits the real app + real database:
  starting/listing/stopping a directory-backed stream end-to-end (real
  frames processed, `frames_processed` genuinely increments), every RBAC/
  error path (VIEWER can list but not start, unknown camera 404s, disabled
  camera 400s, double-start 409s, stopping an inactive stream 404s), and a
  real `TestClient.websocket_connect` client receiving a genuine
  per-frame broadcast (`frame_index`/`timestamp`/`tracks`) from a live
  background streaming task — not a synthetic message injected directly
  into the broadcaster.
- Full suite (`uv run pytest`) — 197 tests passing, hermetic, no network or
  ML backend required (Phase 8 doesn't depend on the `vision` extra any more
  than Phase 3's tracking tests did).

## Verified — Phase 9

- `uv run pytest` — hermetic coverage of every new primitive: `CachingInferenceModel`
  (a fake wrapped model's `predict_calls` counter proves repeat calls on the
  same `Frame` object hit the wrapped model exactly once, a different
  `Frame` object triggers a fresh call, and `load`/`warmup`/`is_loaded`/
  `class_names` all delegate correctly); a `PersonDetector` +
  `VehicleDetector` sharing one `CachingInferenceModel` through a real
  `DetectionService.detect()` call confirmed only one real inference call
  happens per frame despite two detectors; the rate limiter's periodic
  sweep (a quiet key with an aged-out hit is evicted once the sweep
  interval elapses, an active key survives, and the sweep is a no-op before
  its interval passes); `DatabaseSettings.pool_size` genuinely reaching the
  real engine's pool for a file-based SQLite URL, and `create_engine`
  degrading gracefully instead of raising for `sqlite+aiosqlite:///:memory:`
  (`StaticPool`, which doesn't accept `pool_size` at all — a real `TypeError`
  this test suite caught while wiring the setting up, not a hypothetical
  edge case).
- `tests/integration/test_detect_image_live.py` and `test_detect_video.py`
  (real YOLO inference, `vision` extra installed) still pass unchanged —
  proving `CachingInferenceModel` and the new `asyncio.to_thread` wrapping
  don't alter real detection behavior, only its cost/concurrency profile.
- Live-verified the actual performance claim, not just that the code runs:
  booted a real `uvicorn` process and sent a 300-frame real-inference
  `POST /detect/video` request (~35s wall time) in the background while
  concurrently polling `GET /health` on the same server — every `/health`
  call returned `200` in 2-5ms throughout the entire 35s window. Before
  this phase's `asyncio.to_thread` fix, that same request would have frozen
  the whole event loop (every other endpoint, and any active
  `StreamManager` background stream) for the full 35s.
- Full suite (`uv run pytest`) — 207 tests passing; `ruff check .` and
  `mypy src` both clean.

## Verified — Phase 10

- Built the default (no `vision` extra) image with real `docker build` —
  not just a Dockerfile read-through — and hit a real failure on the first
  attempt (`README.md` missing from the build context; see "Dockerization"
  above), fixed, and rebuilt successfully (final image ~1.22GB).
- Ran the built image as a real container (`docker run`, no test harness):
  `GET /health` returned a genuine `200` with `active_detectors: []` and a
  structured `detector_unavailable` log line per detector — the exact
  same honest degradation `build_enabled_detectors` already does when
  `ultralytics` isn't installed, now proven inside the container too, not
  just locally. Docker's own `HEALTHCHECK` reported `"Status":"healthy"`
  after the configured `start_period`. `docker exec ... whoami` confirmed
  the process runs as the unprivileged `sentinel` user, and `sentinel.db`
  was created under `/app/data` with correct ownership — proving the
  non-root user actually has write access to the one directory it needs,
  not just that the `Dockerfile` declares it should.
- **An environment constraint, not a design gap:** this sandbox's host disk
  was already at 99% (2.5GB free) before this phase started, and dropped to
  ~372MB free mid-build before recovering once the build finished and
  layers were pruned. Given that, the `--extra vision` build path (adds
  `ultralytics`/`torch`, plausibly 1-2GB+ more) was deliberately **not**
  build-verified here — attempting it risked filling the host disk during
  the build. The build-arg mechanism (`UV_EXTRA_ARGS`) is the same `uv
  sync` flag already proven to work for the default extras, so the risk is
  specifically about available disk in *this* sandbox, not the Dockerfile
  logic — but it's flagged here rather than silently claimed as verified,
  matching this project's practice of being explicit about what a given
  environment could and couldn't actually prove (same spirit as the
  `/dev/video0` and real-`ultralytics` caveats in earlier phases).
  Test/build image and build cache were removed immediately after
  verification (`docker rmi`, `docker builder prune -af`) rather than left
  on a disk that was already critically low.

## Verified — Phase 11

- **A real coverage-tooling bug found and fixed before trusting any number
  from it:** the first `pytest --cov` run reported `api/routers/cameras.py`
  at 60%, with entire route bodies past their first `await` marked
  "Missing." A debug `print()` placed directly inside `get_camera`'s 404
  branch proved it — and every other "missing" line — genuinely executed;
  coverage just wasn't seeing code on the other side of a
  `TestClient`-background-thread boundary or a SQLAlchemy async
  greenlet switch. Fixed via `concurrency = ["thread", "greenlet"]` in
  `[tool.coverage.run]`; the corrected baseline was 96%, not 94%, with zero
  test changes — see "Testing (Phase 11)" above for the full writeup.
- 57 new tests added closing every gap the corrected baseline actually
  showed: all six repositories' previously-untested `update`/`delete`/
  `list` paths (`tests/unit/test_database_repositories.py`, 23 -> 37
  tests); `StreamManager`'s frame_skip/max_fps throttling, error-handling,
  and natural-exhaustion paths (`test_stream_manager.py`); a new
  `test_stream_broadcaster.py` and `test_streaming_factory.py` for two
  previously test-file-less modules; `main.py`'s bootstrap-admin and
  model-warmup-failure paths (`tests/integration/test_lifespan.py`, new);
  cooldown/stale-state-cleanup behavior for `MultiplePeopleRule`,
  `LoiteringRule`, `RestrictedAreaIntrusionRule`, and `TripwireCrossingRule`
  (`test_event_rules.py`); `POST /detect/video`'s track-accumulation/event/
  storage loops via a real `app.dependency_overrides`-swapped
  `PipelineService` (`test_detect_video.py`); camera update/delete 404s,
  `Region`'s validation errors, `Registry.__iter__`, `build_enabled_channels`'
  graceful-degradation path, and the rate limiter's per-request (not just
  periodic-sweep) pruning.
- Full suite (`uv run pytest --cov`) — 264 tests passing, 99% statement
  coverage, `ruff check .` and `mypy src` both clean. The remaining 1% is
  three files with a documented, deliberate reason each (abstract method
  stubs that cannot execute; ML-backend error branches needing a GPU or a
  corrupted real checkpoint; a test SMTP stub that explicitly implements no
  STARTTLS/AUTH) — not gaps nobody looked at.
- Added `.github/workflows/ci.yml` (ruff + mypy + pytest --cov on every
  push/PR, `uv sync --extra dev` only — no `vision` extra, matching the
  fast/hermetic local default). Not yet exercised by an actual GitHub Actions
  run: this repository has no commits or remote yet, so this is verified as
  "the workflow YAML is well-formed and the three commands it runs are the
  exact ones this project has run manually and successfully all along," not
  as "a green CI run was observed."

## Verified — Phase 12

- Queried the real, running app's `app.openapi()` schema directly before
  and after the docstring pass: 19/19 endpoints had an empty `description`
  before, 0/19 after — not eyeballed, checked programmatically.
- Every newly-added `.env.example` variable was verified against real
  `AppSettings` fields, not just written from reading `config/settings.py`:
  every commented-out line was uncommented in a copy of the file and
  actually parsed via `AppSettings(_env_file=...)`, confirming
  `s.tracking`, `s.pipeline`, `s.database`, and `s.security` all reflect
  the values set — a typo'd field name would have raised or silently used
  a default instead of parsing, and this would have caught either.
- `uv run ruff check .`, `uv run mypy src`, and the full test suite (`uv
  run pytest --cov`) all still pass after every docstring/doc change — 264
  tests, 99% coverage, unchanged from Phase 11 (no runtime behavior changed
  in this phase, only documentation and OpenAPI metadata).
- Grepped the whole source tree and `README.md` for stale forward-looking
  phase references (`"is Phase N"`, `"no endpoint uses this yet"`, `"not
  yet"`) rather than relying on memory of what's still accurate. Found and
  fixed six genuinely stale ones, all written *before* Phase 7 shipped
  Camera CRUD/login/`POST /config` and never updated once it did:
  `database/repositories/camera_repository.py`, `user_repository.py`, and
  `configuration_repository.py` each still said "no API endpoint uses this
  yet" — all three now have real callers. `core/entities/user.py` still
  attributed hashing/JWT/RBAC to "Phase 7's concern" as a future item.
  `events/regions.py` and `api/routers/detect.py`'s `regions_json`
  description still said ROI management was Phase 7's future job, when
  registered cameras have carried real `regions` since Phase 7 and
  `StreamManager` has read them every frame since Phase 8.
  `api/routers/alerts.py`'s module docstring separately still said "Phase 6
  adds persistence" as a forward-looking statement. A second grep pass
  after fixing these confirmed no further matches.
