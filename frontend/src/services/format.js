export function pad(n) {
  return String(n).padStart(2, "0");
}

export function clock(seconds) {
  const s = Math.max(0, Math.round(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`;
}

export function durationText(seconds) {
  const s = Math.max(0, Math.round(seconds || 0));
  if (s < 60) return `${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${pad(m % 60)} min`;
}

export function timeOf(iso, withSeconds = true) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", ...(withSeconds ? { second: "2-digit" } : {}) });
}

export function dateTimeOf(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function ago(iso, nowMs = Date.now()) {
  if (!iso) return "never";
  const s = Math.max(0, Math.round((nowMs - new Date(iso).getTime()) / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s} s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)} h ago`;
}

export function pct(v, digits = 0) {
  return v === null || v === undefined ? "-" : `${Number(v).toFixed(digits)}%`;
}

export function windowLabel(w) {
  return `${timeOf(w.window_start, false)} - ${timeOf(w.window_end, false)}`;
}

export function windowMinutes(w, idx) {
  const start = new Date(w.window_start).getTime();
  return start;
}

export const ATTN = {
  ENGAGED: "Estimated engaged",
  POSSIBLE_ATTENTION_DRIFT: "Possible attention drift",
};

export const MOTION = {
  NORMAL: "Normal",
  MOVING: "Moving",
  POSSIBLE_ATTENTION_DRIFT: "Possible drift",
  FEEDBACK: "Feedback shown",
};

export function downloadCsv(filename, rows) {
  const esc = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = rows.map((r) => r.map(esc).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
