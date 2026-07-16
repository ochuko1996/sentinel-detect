# SENTINEL Detect Console

An operations console for the `sentinel-detect/api` backend — dark,
technical, classified-document aesthetic (fictional agency branding —
"SENTINEL" — not any real government agency), the same design system as
the sibling `face-recognition/client` console. Next.js 14 (App Router),
TypeScript, Tailwind CSS, Framer Motion.

## Design

- **Fonts**: `Big Shoulders Display` (condensed, stamped headers) +
  `IBM Plex Mono` (all data/UI text), loaded via `next/font/google`.
- **Palette**: near-black panels, phosphor amber as the single dominant
  accent, alert red reserved for negative/destructive/critical states. See
  `tailwind.config.ts`.
- **Texture**: fixed grain + vignette overlays (`globals.css`), a fine
  grid background, scanline sweep during detection requests.
- **Motion**: staggered panel reveals on page load, a decode/scramble
  text effect for headings (`components/ui/DecodeText.tsx`).

## Pages

| Route | Purpose |
|---|---|
| `/login` | JWT login (`POST /auth/login`) |
| `/` | Dashboard — health, active streams, recent events |
| `/cameras` | Registered cameras + live/stopped status |
| `/cameras/new` | Register a camera (OPERATOR+) |
| `/cameras/[id]` | Detail — start/stop stream, enable/disable, delete (ADMIN) |
| `/cameras/[id]/live` | Live tracking telemetry — see "A real constraint" below |
| `/detect` | Upload an image or video, run the full pipeline against it |
| `/events` | Rule-engine event log, filterable by camera |
| `/alerts` | Live alert feed (`WS /ws/alerts`) backfilled from the REST store |
| `/config` | Runtime key/value config (reads: any role; writes: ADMIN) |

### A real constraint: the live view is telemetry, not video

`WS /ws/stream/{camera_id}` broadcasts only per-frame track metadata
(bounding box, label, confidence) — it never sends the frame's actual
pixels, and the message doesn't even include the frame's width/height. So
`/cameras/[id]/live` cannot honestly render a video overlay; instead it
shows an auto-scaled schematic plot of the current frame's tracked-object
positions (`components/stream/TrackRadar.tsx`) plus a live table. This is a
backend limitation, not a client shortcut — see `docs/architecture.md` in
the `api` repo for the streaming design.

## Running

Requires the `sentinel-detect/api` backend running (see `../api/README.md`)
with `SENTINEL_SECURITY__CORS_ORIGINS` allowing this app's origin (default
`["http://localhost:3000"]` already does, matching `npm run dev`'s port).

```bash
npm install
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at the API
npm run dev
```

Open `http://localhost:3000`. Log in with a bootstrap admin account (see
`../api/README.md`'s "Authentication" section for creating the first one).

## Notes

- Auth: a JWT from `POST /auth/login` is stored in `localStorage`
  (`lib/api.ts::authStorage`) and sent as `Authorization: Bearer <token>`
  on every request; `lib/auth-context.tsx` exposes the current identity
  (username/role) and `components/layout/RequireAuth.tsx` redirects to
  `/login` when there's no session. Role gating in the UI (hiding
  operator/admin-only actions) is a convenience — the real enforcement is
  server-side RBAC; the client never assumes a hidden button means the
  backend would have allowed the action anyway.
- All API calls are client-side (`src/lib/api.ts`).
- `src/lib/types.ts` mirrors `sentinel-detect/api/src/sentinel_detect/api/schemas/*.py`
  and `core/entities/*.py` by hand; keep the two in sync when backend
  response shapes change.
