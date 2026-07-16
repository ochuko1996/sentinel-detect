# SENTINEL Detect

AI-powered object detection and security analytics platform: images, video
uploads, and live camera streams (webcam/USB/RTSP/IP camera/directory feed)
all flow through the same detection → tracking → event → alert → storage
pipeline. Built incrementally, phase by phase — see
[`api/docs/architecture.md`](api/docs/architecture.md) for the full design
rationale, trade-offs, and what each phase actually verified.

This is a two-part repository:

| Directory | What it is |
|---|---|
| [`api/`](api/README.md) | The backend — FastAPI, async SQLAlchemy, a from-scratch ByteTrack tracker, Ultralytics YOLO inference, JWT/RBAC auth, live streaming, Docker, a 99%-covered test suite with CI |
| [`client/`](client/README.md) | The operations console — Next.js 14 + TypeScript + Tailwind, a dark "ops console" UI shared with the sibling `face-recognition` project |

## Quickstart

```bash
# Backend
cd api
uv sync --extra dev          # or: uv sync --extra dev --extra vision (real YOLO inference)
cp .env.example .env          # set SENTINEL_SECURITY__BOOTSTRAP_ADMIN_PASSWORD to create the first user
uv run uvicorn sentinel_detect.main:app --reload

# Console (separate terminal)
cd client
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`, log in with the bootstrap admin account, and
visit `http://localhost:8000/docs` for the API reference. See each
subdirectory's README for full setup details (Docker, model weights, alert
channels, database/Postgres, testing).

## A note on the two READMEs' relationship to this one

This file is the entry point for someone landing on the repo root; it
intentionally doesn't repeat what's already documented in depth in
`api/README.md`, `client/README.md`, and `api/docs/architecture.md` — follow
the links above rather than expecting duplicated detail here.
