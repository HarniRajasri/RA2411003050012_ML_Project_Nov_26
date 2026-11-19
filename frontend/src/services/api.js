// Thin fetch wrapper. Every failure becomes an Error with a message a teacher can act on.
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the KHorizon backend. Check that it is running (see README).", 0);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const detail = data && (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return data;
}

export const api = {
  get: (p) => request("GET", p),
  post: (p, b) => request("POST", p, b ?? {}),
  patch: (p, b) => request("PATCH", p, b ?? {}),

  health: () => api.get("/api/health"),
  settings: () => api.get("/api/settings"),
  events: (limit = 60) => api.get(`/api/events?limit=${limit}`),
  liveHistory: () => api.get("/api/live/history"),
  eegStatus: () => api.get("/api/eeg/status"),

  classes: () => api.get("/api/classes"),
  currentClass: () => api.get("/api/classes/current"),
  startClass: (payload) => api.post("/api/classes/start", payload),
  endClass: () => api.post("/api/classes/end"),
  analytics: (id, source = "ALL") => api.get(`/api/classes/${id}/analytics?source=${source}`),
  timeline: (id) => api.get(`/api/classes/${id}/timeline`),
  classEvents: (id) => api.get(`/api/classes/${id}/events`),

  devices: () => api.get("/api/devices"),
  setLabel: (id, label) => api.patch(`/api/devices/${encodeURIComponent(id)}`, { student_label: label }),

  seedDemo: () => api.post("/api/demo/seed"),
  simStatus: () => api.get("/api/sim/status"),
  simAdd: (count) => api.post("/api/sim/add", { count }),
  simDisconnectRandom: (count) => api.post(`/api/sim/disconnect-random?count=${count}`),
  simReconnectAll: () => api.post("/api/sim/reconnect-all"),
  simScenario: (scenario, fraction) => api.post("/api/sim/scenario", { scenario, fraction }),
  simClear: () => api.post("/api/sim/clear"),
};

export function wsUrl() {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/dashboard`;
}
