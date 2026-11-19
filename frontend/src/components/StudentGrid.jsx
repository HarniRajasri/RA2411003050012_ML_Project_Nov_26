import { useState } from "react";

function tileOf(d, classActive) {
  if (d.status === "DISCONNECTED") return ["offline", "Disconnected"];
  if (d.status === "RECONNECTING") return ["reconnecting", "Signal late"];
  if (d.attention_state === "ENGAGED") return ["engaged", "Estimated engaged"];
  if (d.attention_state === "POSSIBLE_ATTENTION_DRIFT") return ["drift", "Possible drift"];
  return ["nodata", classActive ? "Waiting for data" : "Connected"];
}

export default function StudentGrid({ devices, classActive }) {
  const [filter, setFilter] = useState("ALL");
  const visible = devices
    .filter((d) => (classActive ? d.in_class : d.status !== "DISCONNECTED"))
    .filter((d) => filter === "ALL" || d.source === filter);
  const sims = devices.some((d) => d.source === "SIMULATED");

  return (
    <section className="panel" aria-label="Students">
      <div className="panel-head">
        <h2>Students</h2>
        {sims && (
          <div className="tabs" role="tablist" aria-label="Filter by source">
            {[["ALL", "All"], ["REAL", "Real"], ["SIMULATED", "Simulated"]].map(([k, l]) => (
              <button key={k} className={`tab ${filter === k ? "on" : ""}`} onClick={() => setFilter(k)} role="tab" aria-selected={filter === k}>{l}</button>
            ))}
          </div>
        )}
      </div>
      {visible.length === 0 ? (
        <div className="empty">
          <h3>{classActive ? "No headbands have joined this class yet" : "No headbands connected"}</h3>
          <p>Power on a headband on the same Wi-Fi, or add simulated students on the Demo and simulation page.</p>
        </div>
      ) : (
        <div className="roster">
          {visible.map((d) => {
            const [cls, text] = tileOf(d, classActive);
            return (
              <div key={d.device_id} className={`tile ${cls}`} title={`${d.device_id}${d.student_label ? " - " + d.student_label : ""}`}>
                <div className="id">
                  <span>{d.student_label || d.device_id}</span>
                  {d.source === "SIMULATED" && <span className="badge sim">SIM</span>}
                </div>
                <div className="st">{text}</div>
                {d.joined_late && <div className="st faint">joined late</div>}
              </div>
            );
          })}
        </div>
      )}
      <div className="panel-body" style={{ borderTop: "1px solid var(--line)" }}>
        <div className="legend">
          <span><i style={{ background: "var(--engaged)" }} />Estimated engaged</span>
          <span><i style={{ background: "var(--drift)" }} />Possible attention drift</span>
          <span><i style={{ background: "var(--line-strong)" }} />No recent data</span>
          <span><i style={{ background: "var(--offline)" }} />Disconnected</span>
        </div>
      </div>
    </section>
  );
}
