# SENTINEL Detect

AI-powered object detection and security analytics platform. Processes
images, video, webcams, RTSP/IP cameras, and directory feeds through a
modular detection → tracking → event → alert pipeline.

This repository was built incrementally, phase by phase. See
[`docs/architecture.md`](docs/architecture.md) (now with a
[table of contents](docs/architecture.md#contents)) for the design
rationale behind every phase, what each one verified, and what's
deliberately out of scope.

## Status: Phase 12 — Documentation (complete)

- Clean-architecture layering (`core/` entities + ports; everything else an
  adapter).
- Plugin registry so new detectors/trackers/event rules/alert channels/
  storage backends/video sources can be added without touching core code.
- Layered configuration (`pydantic-settings`, `.env` + env vars, nested
  overrides).
- Structured logging (`structlog`).
- **Detection engine**: `UltralyticsYoloModel` (YOLOv8/YOLOv11), a shared
  `ModelManager`, and 7 built-in detectors (person, vehicle, weapon, fire,
  smoke, ppe, animal) via one `LabelMappedDetector` implementation.
- **Tracking**: `ByteTracker` — a from-scratch ByteTrack (Kalman filter +
  Hungarian IoU assignment + two-stage high/low-confidence matching),
  assigning persistent per-camera, per-class track IDs.
- **Event engine**: 12 built-in rules — person/vehicle/weapon/fire/smoke
  detected, multiple_people, crowd_detected, restricted_area_intrusion,
  tripwire_crossing (entering/leaving), loitering, object_abandoned,
  object_removed — all configurable, all with cooldown-based debouncing.
- **Alert engine**: 4 working channels — REST (in-memory store +
  `GET /alerts`), WebSocket (live broadcast via `WS /ws/alerts`), Webhook
  (JSON POST to a configured URL), Email (real SMTP via stdlib `smtplib`,
  disabled by default pending real credentials). SMS/Push/Slack/Teams are
  reserved `AlertChannelType` entries for later.
- **Database layer**: async SQLAlchemy 2.0 (SQLite by default, Postgres via
  the `postgres` extra) with 6 tables — detections, events, cameras, users,
  configurations, and alerts (this platform's audit-trail/"logs" table).
  Alembic migrations alongside dev-convenience auto-create.
- **FastAPI backend**: JWT auth (`POST /auth/login`) with an `X-API-Key`
  alternative for service callers, RBAC (VIEWER/OPERATOR/ADMIN), a real
  in-memory rate limiter, and Prometheus metrics at `GET /metrics`. Full
  camera CRUD (`GET /cameras`, `GET /cameras/{id}`, `POST /camera`,
  `PUT /camera/{id}`, `DELETE /camera/{id}`), `GET /events` /
  `GET /detections` (paginated, filterable by `camera_id`), and
  `POST /config` / `GET /config` / `GET /config/{key}`.
- `POST /detect/image` runs every active detector over an uploaded image;
  `POST /detect/video` runs the full detection → tracking → event → alert →
  storage pipeline over an uploaded video (optionally with ROI regions),
  persisting every detection/event/alert it produces, and returns per-track
  summaries, every event raised, and storage counts; `GET /health` reports
  configured vs. actually-active detectors and alert channels.
- Person/vehicle/animal work out of the box on the stock COCO checkpoint;
  weapon/fire/smoke/ppe require fine-tuned weights and are disabled by
  default until supplied (see Model weights, below).
- **Streaming**: live, indefinitely-running per-camera pipelines over
  webcam/USB/RTSP/IP-camera feeds or a polled directory of images, running
  the exact same detection → tracking → event → alert → storage chain
  `POST /detect/video` uses. `GET /detect/stream` (list active streams),
  `POST /detect/stream` (start), `DELETE /detect/stream/{camera_id}` (stop)
  — OPERATOR+ to start/stop, any authenticated principal to list — plus
  `WS /ws/stream/{camera_id}` for a live per-frame broadcast of tracked
  objects to connected clients.
- **Performance**: detectors sharing a model (person/vehicle/animal all on
  `yolov11n`) no longer run redundant forward passes over the same frame
  (`CachingInferenceModel`); `POST /detect/image`/`POST /detect/video`'s
  blocking decode/inference work now runs off the event loop via
  `asyncio.to_thread`, so a long video-processing request no longer freezes
  the whole server (including live streams) for its duration; the rate
  limiter periodically evicts callers that have gone quiet instead of
  growing forever; `DatabaseSettings.pool_size` (configured since Phase 6)
  is now actually applied to the database engine.
- **Dockerized**: a multi-stage `Dockerfile` (pinned `uv` for dependency
  resolution, a slim non-root runtime image, a real `HEALTHCHECK`) and a
  `docker-compose.yml` that runs the API alone against SQLite by default —
  zero other services required, matching the app's own zero-setup stance —
  with Postgres available as an opt-in `profiles: ["postgres"]` service.
- **Tested**: 264 tests, 99% statement coverage (`ruff check .` and
  `mypy src` both clean), CI via `.github/workflows/ci.yml`. Found and fixed
  a real coverage-tooling gap along the way — `pytest-cov` was silently
  missing code executed across a `TestClient` background-thread boundary
  and a SQLAlchemy async greenlet switch (see `docs/architecture.md` for
  the full story) — so the number above reflects what's actually exercised,
  not an inflated one.
- **Documented**: every endpoint now has a real OpenAPI description (auth
  requirement, specific error conditions) at `/docs` — verified
  programmatically (`app.openapi()`), not eyeballed. `.env.example` covers
  every settings group, each variable checked against a real parsed
  `AppSettings` rather than written from reading the source. Six stale
  "not built yet" docstrings left over from before Phase 7 shipped Camera
  CRUD/login/`POST /config` were found (via a full-tree grep, not memory)
  and corrected.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

```bash
uv sync --extra dev             # runtime + dev dependencies (no ML backend)
uv sync --extra dev --extra vision  # + ultralytics/torch/onnxruntime, for real detection
cp .env.example .env             # optional: customize configuration
```

## Running

```bash
uv run uvicorn sentinel_detect.main:app --reload
```

Then visit `http://localhost:8000/health` or `http://localhost:8000/docs`.

On first startup with the `vision` extra installed, the stock COCO
checkpoint (`yolo11n.pt`, ~5MB) is auto-downloaded to `data/weights/` for the
person/vehicle/animal detectors. Without the `vision` extra (or without
network access), the app still starts — `/health` will just show an empty
`active_detectors` list.

Try it:

```bash
curl -F "file=@some_photo.jpg" http://localhost:8000/detect/image

curl -F "file=@some_clip.mp4" http://localhost:8000/detect/video

# With an ROI region (a one-shot upload has no registered camera to read
# regions from, so pass one directly; a registered camera's own regions,
# set via POST /camera, are used automatically for a live stream instead):
curl -F "file=@some_clip.mp4" \
     -F 'regions_json=[{"id":"r1","camera_id":"cam-1","name":"Zone",
         "type":"restricted_zone","polygon":{"points":[{"x":0,"y":0},
         {"x":640,"y":0},{"x":640,"y":480},{"x":0,"y":480}]}}]' \
     http://localhost:8000/detect/video

# Recent alerts (in-memory REST store — always available regardless of the database):
curl http://localhost:8000/alerts

# Live alert stream:
websocat ws://localhost:8000/ws/alerts   # or any WebSocket client

# Log in and manage cameras (see Authentication, below, for bootstrapping a user):
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=admin&password=$SENTINEL_ADMIN_PASSWORD" | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/cameras
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/events
curl http://localhost:8000/metrics

# Register a camera, then start/stop/list a live stream from it:
curl -H "Authorization: Bearer $TOKEN" -X POST http://localhost:8000/camera \
  -H "Content-Type: application/json" \
  -d '{"id":"cam-1","name":"Front Door","source_type":"directory","uri":"/path/to/snapshots"}'
curl -H "Authorization: Bearer $TOKEN" -X POST http://localhost:8000/detect/stream \
  -H "Content-Type: application/json" -d '{"camera_id":"cam-1"}'
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/detect/stream
websocat ws://localhost:8000/ws/stream/cam-1   # live per-frame tracked-object broadcast
curl -H "Authorization: Bearer $TOKEN" -X DELETE http://localhost:8000/detect/stream/cam-1
```

## Docker

```bash
docker compose up --build     # API alone, against SQLite — no other services required
```

Then visit `http://localhost:8000/health`. Data (the sqlite db, downloaded/
uploaded model weights, stored evidence) persists in `./data` on the host via
a bind mount, so it survives `docker compose down`.

To build with real YOLO inference and/or Postgres support (adds `ultralytics`/
`torch`, multiple GB):

```bash
SENTINEL_UV_EXTRA_ARGS="--extra vision --extra postgres" docker compose up --build
```

To run Postgres alongside the API instead of SQLite:

```bash
docker compose --profile postgres up --build
# then point the API at it, e.g. in .env:
# SENTINEL_DATABASE__URL=postgresql+asyncpg://sentinel:sentinel@postgres:5432/sentinel
```

`.env` (if present) is picked up automatically by `docker-compose.yml`; it's
never baked into the image itself (`.dockerignore` excludes it) — all
configuration reaches the container as real environment variables, same as
any other deployment of the image. Building and running with plain `docker`
instead of Compose works the same way:

```bash
docker build -t sentinel-detect-api .
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" --env-file .env sentinel-detect-api
```

## Model weights

`weapon`, `fire`, `smoke`, and `ppe` detectors are **disabled by default**
because no open pretrained model covers guns/rifles/fire/smoke/PPE. To
enable one: place a fine-tuned Ultralytics-compatible `.pt` file at
`data/weights/<name>.pt` (see `models.weights` in `.env.example`) and set,
e.g., `SENTINEL_DETECTORS__WEAPON__ENABLED=true`.

## Alert channels

`rest` and `websocket` work out of the box. `webhook` and `email` are
**disabled by default** since they need real external config:

```bash
SENTINEL_ALERTS__WEBHOOK__ENABLED=true
SENTINEL_ALERTS__WEBHOOK__PARAMS__URL=https://example.com/hook

SENTINEL_ALERTS__EMAIL__ENABLED=true
SENTINEL_ALERTS__EMAIL__PARAMS__SMTP_HOST=smtp.example.com
SENTINEL_ALERTS__EMAIL__PARAMS__FROM_ADDR=alerts@example.com
SENTINEL_ALERTS__EMAIL__PARAMS__TO_ADDRS=ops@example.com,security@example.com
SENTINEL_ALERTS__EMAIL__PARAMS__USERNAME=...
SENTINEL_ALERTS__EMAIL__PARAMS__PASSWORD=...
```

## Authentication

There's no `POST /users` endpoint, so something has to create the first
account. Set a bootstrap admin password before first startup:

```bash
SENTINEL_SECURITY__BOOTSTRAP_ADMIN_PASSWORD=change-me-now
# optional: SENTINEL_SECURITY__BOOTSTRAP_ADMIN_USERNAME=admin (this is the default)
```

An ADMIN user is created with that username/password on startup if one
doesn't already exist. Log in via `POST /auth/login` (OAuth2 password
form) to get a JWT; use it as `Authorization: Bearer <token>`.

For service-to-service calls, configure a static API key instead of a
per-user login:

```bash
SENTINEL_SECURITY__API_KEYS='["a-long-random-service-key"]'
```

...then send it as `X-API-Key: a-long-random-service-key`. Roles are
VIEWER (read-only) < OPERATOR (camera create/update, start/stop a stream)
< ADMIN (camera delete, `/config` writes); an API key is treated as
ADMIN-equivalent. `/detect/image`, `/detect/video`, `/alerts`, `/ws/alerts`,
`/health`, and `/metrics` remain unauthenticated — see `docs/architecture.md`
for why — but `/detect/stream` and `/ws/stream/{camera_id}` (Phase 8) *are*
gated, matching the rest of the administrative surface.

## Database

SQLite (`./data/sentinel.db`) is created automatically on first startup —
no setup needed. For Postgres, install the extra and point the URL at it:

```bash
uv sync --extra postgres
# SENTINEL_DATABASE__URL=postgresql+asyncpg://user:pass@localhost:5432/sentinel
```

Schema migrations use Alembic:

```bash
uv run alembic upgrade head              # apply migrations
uv run alembic revision --autogenerate -m "add some_column"   # after changing a model
```

The app also auto-creates any missing tables on startup (`create_all()`,
dev convenience) — don't run `alembic upgrade head` against a database that
was only ever bootstrapped that way without first reconciling with
`alembic stamp head` (see `docs/architecture.md`).

## Testing & linting

```bash
uv run pytest --cov=src/sentinel_detect --cov-report=term-missing  # hermetic, 99% coverage
uv run ruff check .
uv run mypy src
```

CI (`.github/workflows/ci.yml`) runs these same three commands on every
push/PR. **If you add `pytest-cov` to a FastAPI + async-SQLAlchemy project
of your own:** `[tool.coverage.run] concurrency = ["thread", "greenlet"]`
in `pyproject.toml` is required or coverage silently under-reports —
`TestClient` runs the app on a background thread, and SQLAlchemy's async
engine bridges DBAPI calls through a greenlet switch; without both,
genuinely-executed code past an `await` gets reported as untested (see
`docs/architecture.md`, "Testing (Phase 11)", for how this was found).

`tests/integration/test_detect_image_live.py` exercises real YOLO inference
end-to-end; it's automatically skipped unless the `vision` extra is
installed. `tests/integration/test_detect_video.py` exercises
`POST /detect/video`'s decode/track/event/aggregate plumbing hermetically (a
tiny synthetic video, no ML backend required); the `ByteTracker` algorithm
is covered in `tests/unit/test_byte_tracker.py` and all 12 event rules in
`tests/unit/test_event_rules.py` — both thoroughly and hermetically. The
webhook and email alert channels are tested against real local
`http.server`/SMTP-protocol stub servers (`tests/unit/test_webhook_channel.py`,
`tests/unit/test_email_channel.py`) — real sockets, not mocks.
`tests/integration/test_alerts_api.py` proves `GET /alerts` and
`WS /ws/alerts` are genuinely wired to the app's `AlertEngine`.
`tests/unit/test_database_repositories.py` runs full CRUD for all six
repositories against a real (temp-file) SQLite database per test — not a
mocked session. Auth/RBAC/rate-limiting are covered in
`tests/unit/test_passwords.py`, `test_tokens.py`, `test_rate_limit.py`, and
`test_auth_dependency.py` (hermetic); `tests/integration/test_auth_api.py`,
`test_cameras_api.py`, `test_events_detections_config_api.py`, and
`test_metrics_api.py` exercise the real endpoints end-to-end.
`tests/unit/test_opencv_source.py` and `test_directory_source.py` cover the
two `BaseVideoSource` implementations against real synthetic video
files/temp directories (and a real `/dev/video0` where the sandbox happens
to expose one); `tests/unit/test_stream_manager.py` runs a real
`PipelineService`/`AlertEngine`/temp-file-SQLite stack against a directory
stream, hermetically. `tests/integration/test_stream_api.py` exercises
`GET`/`POST`/`DELETE /detect/stream` and `WS /ws/stream/{camera_id}`
end-to-end, including RBAC and error paths.
`tests/unit/test_caching_model.py` proves `CachingInferenceModel` collapses
repeat same-frame `predict()` calls to one real inference (including a
`DetectionService` with two detectors sharing one cached model);
`tests/unit/test_rate_limit.py` covers the periodic idle-key sweep;
`tests/unit/test_database_engine.py` proves `DatabaseSettings.pool_size`
reaches the real engine and that construction degrades gracefully instead
of raising against an in-memory SQLite URL.
`tests/integration/test_lifespan.py` builds a fresh `create_app()` under
real bootstrap-admin env vars to prove that startup path end-to-end, and
proves startup survives a model that fails to warm up.
`tests/unit/test_region_entity.py`, `test_alerts_factory.py`, and
`test_stream_broadcaster.py`/`test_streaming_factory.py` cover, respectively,
`Region`'s validation, `build_enabled_channels`'s graceful degradation, and
two previously test-file-less streaming modules.

## Project layout

```
src/sentinel_detect/
  core/            entities + interfaces (ports) — the stable center
  config/          pydantic-settings configuration
  detectors/       person/vehicle/weapon/fire/smoke/ppe/animal detectors
  models/          inference backends: UltralyticsYoloModel + ModelManager
  tracking/        ByteTracker (Kalman filter + Hungarian IoU assignment)
  events/          rule engine: 12 built-in rules across 4 families
  alerts/          REST/WebSocket/webhook/email alert channels
  database/        async SQLAlchemy engine/session + ORM models + repositories
  security/        password hashing, JWT tokens, rate-limit middleware
  storage/         evidence/snapshot storage backends
  streaming/       video sources + live per-camera streaming (Phase 8)
  services/        use-case orchestration (Detection/Tracking/Event/Alert/Pipeline)
  api/             FastAPI routers, schemas, dependencies
  utils/           logging, Prometheus metrics, other cross-cutting helpers
tests/
  unit/
  integration/
migrations/        Alembic migrations (async template)
docs/
Dockerfile         multi-stage build: uv-resolved deps -> slim non-root runtime
docker-compose.yml API (+ optional Postgres, --profile postgres)
.github/workflows/ci.yml   ruff + mypy + pytest --cov on every push/PR
```

## Configuration

All configuration is environment-variable driven with `.env` support; see
`.env.example` and `src/sentinel_detect/config/settings.py` for the full set
of options, including per-detector confidence/IoU thresholds
(`SENTINEL_DETECTORS__<NAME>__...`) and model weights
(`SENTINEL_MODELS__WEIGHTS__<KEY>`).
