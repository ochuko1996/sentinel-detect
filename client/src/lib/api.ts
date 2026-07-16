import type {
  Camera,
  CameraCreateRequest,
  CameraUpdateRequest,
  ConfigurationEntry,
  ConfigurationValue,
  Detection,
  DetectImageResponse,
  DetectVideoResponse,
  EventSummary,
  HealthResponse,
  Region,
  StreamStatusResponse,
  TokenResponse,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const TOKEN_KEY = "sentinel_detect_token";
const IDENTITY_KEY = "sentinel_detect_identity";

export interface StoredIdentity {
  username: string;
  role: TokenResponse["role"];
}

/** Auth token storage. `localStorage` is fine here — this is a thin console
 * over the API, not a security boundary in itself; the real auth boundary
 * is server-side (see docs/architecture.md in the backend repo). */
export const authStorage = {
  getToken(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TOKEN_KEY);
  },
  getIdentity(): StoredIdentity | null {
    if (typeof window === "undefined") return null;
    const raw = window.localStorage.getItem(IDENTITY_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as StoredIdentity;
    } catch {
      return null;
    }
  },
  set(token: string, identity: StoredIdentity): void {
    window.localStorage.setItem(TOKEN_KEY, token);
    window.localStorage.setItem(IDENTITY_KEY, JSON.stringify(identity));
  },
  clear(): void {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(IDENTITY_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function authHeaders(): Record<string, string> {
  const token = authStorage.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { ...authHeaders(), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(
      0,
      `Could not reach SENTINEL Detect backend at ${API_BASE_URL}. Is the API running?`,
    );
  }

  if (response.status === 401) {
    authStorage.clear();
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON — keep the generic message
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function jsonHeaders(): Record<string, string> {
  return { "Content-Type": "application/json" };
}

/** http(s) API_BASE_URL -> ws(s):// — for WS /ws/alerts and
 * WS /ws/stream/{camera_id}, which take no auth (see api/routers/websocket.py). */
export function wsUrl(path: string): string {
  return `${API_BASE_URL.replace(/^http/, "ws")}${path}`;
}

export const api = {
  login: async (username: string, password: string): Promise<TokenResponse> => {
    const body = new URLSearchParams({ username, password });
    const token = await request<TokenResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    authStorage.set(token.access_token, { username: token.username, role: token.role });
    return token;
  },

  logout: (): void => authStorage.clear(),

  health: () => request<HealthResponse>("/health"),

  detectImage: (file: File, cameraId?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (cameraId) form.append("camera_id", cameraId);
    return request<DetectImageResponse>("/detect/image", { method: "POST", body: form });
  },

  detectVideo: (file: File, opts?: { maxFrames?: number; regions?: Region[] }) => {
    const form = new FormData();
    form.append("file", file);
    if (opts?.regions?.length) {
      form.append("regions_json", JSON.stringify(opts.regions));
    }
    const query = opts?.maxFrames ? `?max_frames=${opts.maxFrames}` : "";
    return request<DetectVideoResponse>(`/detect/video${query}`, {
      method: "POST",
      body: form,
    });
  },

  listCameras: (offset = 0, limit = 100) =>
    request<Camera[]>(`/cameras?offset=${offset}&limit=${limit}`),

  getCamera: (id: string) => request<Camera>(`/cameras/${id}`),

  createCamera: (payload: CameraCreateRequest) =>
    request<Camera>("/camera", { method: "POST", headers: jsonHeaders(), body: JSON.stringify(payload) }),

  updateCamera: (id: string, payload: CameraUpdateRequest) =>
    request<Camera>(`/camera/${id}`, {
      method: "PUT",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    }),

  deleteCamera: (id: string) => request<void>(`/camera/${id}`, { method: "DELETE" }),

  listEvents: (params?: { cameraId?: string; offset?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.cameraId) q.set("camera_id", params.cameraId);
    q.set("offset", String(params?.offset ?? 0));
    q.set("limit", String(params?.limit ?? 100));
    return request<EventSummary[]>(`/events?${q.toString()}`);
  },

  listDetections: (params?: { cameraId?: string; offset?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.cameraId) q.set("camera_id", params.cameraId);
    q.set("offset", String(params?.offset ?? 0));
    q.set("limit", String(params?.limit ?? 100));
    return request<Detection[]>(`/detections?${q.toString()}`);
  },

  listAlerts: (limit = 100) => request<EventSummary[]>(`/alerts?limit=${limit}`),

  listStreams: () => request<StreamStatusResponse[]>("/detect/stream"),

  startStream: (cameraId: string) =>
    request<{ camera_id: string; status: string }>("/detect/stream", {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({ camera_id: cameraId }),
    }),

  stopStream: (cameraId: string) =>
    request<void>(`/detect/stream/${cameraId}`, { method: "DELETE" }),

  listConfig: (offset = 0, limit = 100) =>
    request<ConfigurationEntry[]>(`/config?offset=${offset}&limit=${limit}`),

  getConfig: (key: string) => request<ConfigurationEntry>(`/config/${key}`),

  upsertConfig: (key: string, value: ConfigurationValue) =>
    request<ConfigurationEntry>("/config", {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({ key, value }),
    }),
};
