export function SourceBadge({ source }) {
  return source === "SIMULATED" ? <span className="badge sim">Simulated</span> : <span className="badge real">Real device</span>;
}

export function StatusBadge({ status }) {
  const map = {
    CONNECTED: ["ok", "Connected"],
    RECONNECTING: ["warn", "Reconnecting"],
    DISCONNECTED: ["", "Disconnected"],
  };
  const [cls, label] = map[status] || ["", status || "Unknown"];
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function ClassBadge({ cls }) {
  if (!cls) return null;
  return cls.status === "ACTIVE" ? <span className="badge ok">Live</span> : <span className="badge">Ended</span>;
}
