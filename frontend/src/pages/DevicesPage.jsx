import { useState } from "react";
import { SourceBadge, StatusBadge } from "../components/Badge.jsx";
import { useToast } from "../components/Toast.jsx";
import { useNow } from "../hooks/useNow.js";
import { useFetch } from "../hooks/useFetch.js";
import { api } from "../services/api.js";
import { ago, ATTN, MOTION } from "../services/format.js";

function LabelCell({ d, onSaved }) {
  const toast = useToast();
  const [val, setVal] = useState(d.student_label || "");
  const save = async () => {
    if (val === (d.student_label || "")) return;
    try {
      await api.setLabel(d.device_id, val.trim());
      toast(`Saved label for ${d.device_id}`, "ok");
      onSaved();
    } catch (e) {
      toast(e.message, "error");
    }
  };
  return (
    <input type="text" value={val} maxLength={40} placeholder="Optional label" aria-label={`Label for ${d.device_id}`}
           onChange={(e) => setVal(e.target.value)} onBlur={save} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
  );
}

export default function DevicesPage() {
  const { data, error, reload } = useFetch(() => api.devices(), [], 3000);
  const now = useNow(1000);
  const [filter, setFilter] = useState("ALL");
  const [showSample, setShowSample] = useState(false);
  const heard = (d) => showSample || d.last_seen;
  const hiddenCount = (data || []).filter((d) => !d.last_seen).length;
  const rows = (data || []).filter((d) => (filter === "ALL" || d.source === filter) && heard(d));
  const real = (data || []).filter((d) => d.source === "REAL").length;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Devices</h1>
          <p>Every headband the backend has heard from. Labels are optional and are for your reference; use identifiers rather than names where you can.</p>
        </div>
        <div className="spacer" />
        {hiddenCount > 0 && (
          <label className="small muted" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={showSample} onChange={(e) => setShowSample(e.target.checked)} />
            Include {hiddenCount} sample-data devices
          </label>
        )}
        <div className="tabs">
          {[["ALL", "All"], ["REAL", "Real devices"], ["SIMULATED", "Simulated"]].map(([k, l]) => (
            <button key={k} className={`tab ${filter === k ? "on" : ""}`} onClick={() => setFilter(k)}>{l}</button>
          ))}
        </div>
      </div>

      <section className="panel">
        {error ? (
          <div className="empty"><h3>Could not load devices</h3><p>{error.message}</p></div>
        ) : rows.length === 0 ? (
          <div className="empty">
            <h3>{real === 0 && filter !== "SIMULATED" ? "No headband has connected yet" : "No devices to show"}</h3>
            <p>Flash the firmware in <span className="mono">esp32/KHorizon_Headband</span> and power the headband on the same Wi-Fi as this computer. It registers by itself.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Device</th><th>Label</th><th>Source</th><th>Connection</th><th>Last heard</th><th>Head movement</th>
                  <th>Estimate</th><th>Method</th><th>Firmware</th><th>MAC</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.device_id}>
                    <td style={{ whiteSpace: "nowrap" }}><b>{d.device_id}</b></td>
                    <td><LabelCell d={d} onSaved={reload} /></td>
                    <td><SourceBadge source={d.source} /></td>
                    <td><StatusBadge status={d.status} /></td>
                    <td className="num">{ago(d.last_seen, now)}</td>
                    <td>{d.status === "CONNECTED" ? MOTION[d.motion_state] || "-" : "-"}</td>
                    <td>{d.status === "CONNECTED" ? ATTN[d.attention_state] || "-" : "-"}</td>
                    <td className="small">{d.fusion_mode === null || d.fusion_mode === undefined ? "-" : d.fusion_mode.startsWith("MOTION_EEG") ? "Motion + EEG features" : "Motion only"}</td>
                    <td className="mono">{d.firmware_version || "-"}</td>
                    <td className="mono">{d.mac_address || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
