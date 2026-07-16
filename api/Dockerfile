# syntax=docker/dockerfile:1

# Multi-stage build: the builder stage resolves/installs dependencies with
# uv into a venv; the runtime stage copies only that venv + source code, so
# uv itself, the uv/pip cache, and build-time-only files never end up in the
# final image.

FROM python:3.12-slim-bookworm AS builder

# Pinned uv binary via COPY from its official distroless image, rather than
# `pip install uv` or a curl|sh script — no extra Python bootstrap step, and
# the version is pinned by tag instead of "whatever's latest today".
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# `[tool.uv] package = true` (pyproject.toml) means `uv sync` also builds
# and installs this project itself, which needs `src/` present — and
# README.md too, since `[project] readme = "README.md"` makes the build
# backend read it — so both are copied before `uv sync` runs, not after.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Extras are a build arg, not hardcoded, so an operator can build a lean
# image (default: detection/tracking/events/alerts/database/API, no ML
# backend — matches the app's own "works without the vision extra"
# design) or opt into `--extra vision` (real YOLO inference; adds
# ultralytics/torch, multiple GB) and/or `--extra postgres` at build time:
#   docker build --build-arg UV_EXTRA_ARGS="--extra vision --extra postgres" .
ARG UV_EXTRA_ARGS=""
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev ${UV_EXTRA_ARGS}


FROM python:3.12-slim-bookworm AS runtime

# opencv-python-headless still dynamically links against libGL/libgomp on
# Debian even though it ships no GUI bindings — a well-known real gotcha on
# minimal base images (predict()/imread() import-time failures otherwise),
# not a hypothetical one.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin sentinel

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    SENTINEL_DATABASE__URL=sqlite+aiosqlite:///./data/sentinel.db \
    SENTINEL_STORAGE__LOCAL_PATH=./data/storage \
    SENTINEL_MODELS__WEIGHTS_DIR=./data/weights

# `data/` is the one directory the app writes to at runtime (sqlite db,
# downloaded/uploaded model weights, stored evidence) — owned by the
# unprivileged user and meant to be a mounted volume in practice so it
# survives container recreation.
RUN mkdir -p /app/data && chown -R sentinel:sentinel /app

USER sentinel

EXPOSE 8000

# A plain Python urllib call rather than curl/wget: keeps the runtime image
# free of an extra apt package just for the healthcheck.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "sentinel_detect.main:app", "--host", "0.0.0.0", "--port", "8000"]
