// Mirrors api/schemas/*.py and core/entities/*.py in the backend
// (sentinel-detect/api) exactly — keep these two in sync manually; there is
// no shared schema codegen.

// --- Geometry --------------------------------------------------------------

export interface Point {
  x: number;
  y: number;
}

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Polygon {
  points: Point[];
}

// --- Detection / tracking taxonomy ------------------------------------------

export type DetectionClass =
  | "person"
  | "car"
  | "bus"
  | "truck"
  | "motorcycle"
  | "bicycle"
  | "gun"
  | "rifle"
  | "knife"
  | "fire"
  | "flame"
  | "smoke"
  | "hard_hat"
  | "safety_vest"
  | "gloves"
  | "safety_glasses"
  | "dog"
  | "cat"
  | "cow"
  | "goat"
  | "horse";

export interface Detection {
  id: string;
  camera_id: string;
  detector: string;
  label: DetectionClass;
  confidence: number;
  bbox: BoundingBox;
  frame_width: number;
  frame_height: number;
  timestamp: string;
}

export type TrackState = "new" | "tracked" | "lost" | "removed";

export interface TrackedObject {
  track_id: number;
  camera_id: string;
  label: DetectionClass;
  confidence: number;
  bbox: BoundingBox;
  state: TrackState;
  first_seen: string;
  last_seen: string;
  hits: number;
  age: number;
}

export interface TrackSummary {
  track_id: number;
  label: string;
  first_seen_frame: number;
  last_seen_frame: number;
  frames_tracked: number;
  last_bbox: BoundingBox;
  last_confidence: number;
}

// --- Events / alerts ---------------------------------------------------------

export type EventType =
  | "person_detected"
  | "vehicle_detected"
  | "weapon_detected"
  | "fire_detected"
  | "smoke_detected"
  | "restricted_area_intrusion"
  | "loitering"
  | "crowd_detected"
  | "object_abandoned"
  | "object_removed"
  | "multiple_people"
  | "person_entering"
  | "person_leaving";

export type EventSeverity = "info" | "warning" | "critical";

/** Response shape for GET /events, GET /alerts, and each WS /ws/alerts frame's
 * logical content — the raw WS payload also carries `id`/`metadata` (see
 * `EventWsMessage`), which the REST/DB-backed endpoints omit. */
export interface EventSummary {
  type: EventType;
  severity: EventSeverity;
  rule: string;
  track_ids: number[];
  region_id: string | null;
  message: string;
  timestamp: string;
}

/** The exact payload WS /ws/alerts broadcasts: `Event.model_dump(mode="json")`. */
export interface EventWsMessage extends EventSummary {
  id: string;
  camera_id: string;
  metadata: Record<string, string | number | boolean>;
}

export type AlertChannelType =
  | "rest"
  | "websocket"
  | "email"
  | "webhook"
  | "sms"
  | "push"
  | "slack"
  | "teams";

export type AlertStatus = "pending" | "sent" | "failed";

// --- Cameras / regions -------------------------------------------------------

export type SourceType =
  | "image"
  | "video_file"
  | "webcam"
  | "usb"
  | "rtsp"
  | "ip_camera"
  | "directory";

export type RegionType =
  | "restricted_zone"
  | "safe_zone"
  | "entry_zone"
  | "exit_zone"
  | "tripwire";

export interface Region {
  id: string;
  camera_id: string;
  name: string;
  type: RegionType;
  polygon: Polygon | null;
  line: [Point, Point] | null;
}

export interface Camera {
  id: string;
  name: string;
  source_type: SourceType;
  uri: string;
  enabled: boolean;
  enabled_detectors: string[];
  regions: Region[];
  frame_rate_limit: number | null;
  inference_size: [number, number];
}

export interface CameraCreateRequest {
  id: string;
  name: string;
  source_type: SourceType;
  uri: string;
  enabled?: boolean;
  enabled_detectors?: string[];
  regions?: Region[];
  frame_rate_limit?: number | null;
  inference_size?: [number, number];
}

export type CameraUpdateRequest = Partial<Omit<CameraCreateRequest, "id">>;

// --- Streaming ---------------------------------------------------------------

export interface StreamStatusResponse {
  camera_id: string;
  started_at: string;
  frames_processed: number;
  last_error: string | null;
}

/** One WS /ws/stream/{camera_id} frame message. */
export interface StreamFrameMessage {
  frame_index: number;
  timestamp: string;
  tracks: Array<{
    track_id: number;
    label: string;
    confidence: number;
    bbox: BoundingBox;
  }>;
}

// --- Detect endpoints ---------------------------------------------------------

export interface DetectImageResponse {
  camera_id: string;
  frame_width: number;
  frame_height: number;
  detections: Detection[];
  active_detectors: string[];
}

export interface DetectVideoResponse {
  camera_id: string;
  frames_processed: number;
  active_detectors: string[];
  active_rules: string[];
  active_alert_channels: string[];
  tracks: TrackSummary[];
  events: EventSummary[];
  detections_stored: number;
  events_stored: number;
  alerts_stored: number;
}

// --- Config --------------------------------------------------------------------

export type ConfigurationValue =
  | string
  | number
  | boolean
  | Record<string, unknown>
  | unknown[]
  | null;

export interface ConfigurationEntry {
  key: string;
  value: ConfigurationValue;
  updated_at: string;
}

// --- Auth ------------------------------------------------------------------------

export type UserRole = "admin" | "operator" | "viewer";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: UserRole;
}

// --- Health ----------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  app_name: string;
  environment: string;
  configured_detectors: string[];
  active_detectors: string[];
  enabled_event_rules: string[];
  configured_alert_channels: string[];
  active_alert_channels: string[];
}

export interface ApiErrorBody {
  detail: string;
}
