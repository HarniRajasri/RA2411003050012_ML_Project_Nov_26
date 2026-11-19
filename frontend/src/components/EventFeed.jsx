import { timeOf } from "../services/format.js";

const TONE = {
  DEVICE_CONNECTED: "ok", DEVICE_RECONNECTED: "ok", FEEDBACK_ACKNOWLEDGED: "ok",
  DEVICE_DISCONNECTED: "bad", DRIFT_ESTIMATED: "warn", FEEDBACK_TRIGGERED: "warn",
  CLASS_STARTED: "", CLASS_ENDED: "",
};

export default function EventFeed({ events, limit = 60, title = "Live events" }) {
  return (
    <section className="panel" aria-label={title}>
      <div className="panel-head"><h2>{title}</h2><span className="small faint">newest first</span></div>
      {events.length === 0 ? (
        <div className="empty small">Nothing has happened yet. Connections, disconnections and feedback appear here.</div>
      ) : (
        <ul className="feed">
          {events.slice(0, limit).map((e) => (
            <li key={e.id}>
              <span className="t">{timeOf(e.timestamp)}</span>
              <span className={`dot ${TONE[e.event_type] || ""}`} />
              <span className="m">
                {e.message}
                {e.source === "SIMULATED" && <span className="badge sim" style={{ marginLeft: 8 }}>SIM</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
