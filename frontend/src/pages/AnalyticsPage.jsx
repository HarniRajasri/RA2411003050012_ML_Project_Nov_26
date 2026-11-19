import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import WindowsChart from "../charts/WindowsChart.jsx";
import TimelineChart from "../charts/TimelineChart.jsx";
import EventFeed from "../components/EventFeed.jsx";
import { ClassBadge } from "../components/Badge.jsx";
import { useFetch } from "../hooks/useFetch.js";
import { api } from "../services/api.js";
import { ATTN, clock, dateTimeOf, downloadCsv, pct, timeOf, windowLabel } from "../services/format.js";

const STATUS_TEXT = { complete: "Complete", partial: "Partial", in_progress: "In progress", upcoming: "Upcoming" };

function Summary({ s, cls }) {
  const cell = (v, k, n) => (
    <div><div className="v">{v}</div><div className="k">{k}</div>{n && <div className="n">{n}</div>}</div>
  );
  return (
    <section className="readout" aria-label="Class summary">
      {cell(clock(s.duration_seconds), "Class length (h:mm:ss)", cls.status === "ACTIVE" ? "still running" : null)}
      {cell(s.total_registered, "Headbands in class", `peak ${s.peak_connections} connected at once`)}
      {cell(s.continuous_from_start, "Connected since start", "never dropped out")}
      {cell(s.disconnected_at_least_once, "Disconnected at least once")}
      {cell(s.joined_after_start, "Joined after start")}
      {cell(pct(s.average_engagement_percentage, 1), "Average estimated engagement", "time-weighted over windows")}
      {cell(s.possible_drift_events, "Possible drift episodes", `${s.feedback_acknowledged} of ${s.feedback_events} feedback prompts acknowledged`)}
    </section>
  );
}

export default function AnalyticsPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data: classes } = useFetch(() => api.classes(), [], 15000);
  const [source, setSource] = useState("ALL");
  const [tlFilter, setTlFilter] = useState("ALL");

  const classId = id ? Number(id) : classes && classes.length ? classes[0].id : null;
  const live = classes?.find((c) => c.id === classId)?.status === "ACTIVE";
  const { data, error, loading } = useFetch(() => (classId ? api.analytics(classId, source) : Promise.resolve(null)), [classId, source], live ? 5000 : 0);
  const { data: timeline } = useFetch(() => (classId ? api.timeline(classId) : Promise.resolve(null)), [classId], live ? 10000 : 0);
  const { data: ev } = useFetch(() => (classId ? api.classEvents(classId) : Promise.resolve(null)), [classId], live ? 5000 : 0);

  useEffect(() => { setSource("ALL"); setTlFilter("ALL"); }, [classId]);

  if (classes && classes.length === 0) {
    return (
      <main className="page">
        <div className="page-head"><h1>Analytics</h1></div>
        <section className="panel"><div className="empty"><h3>No classes recorded yet</h3><p>Finish a class, or load a sample class from <Link to="/history">Class history</Link>.</p></div></section>
      </main>
    );
  }

  const exportCsv = () => {
    if (!data) return;
    downloadCsv(`khorizon_class_${data.class.id}_windows.csv`, [
      ["window_start", "window_end", "status", "connected_students", "estimated_engaged_students", "possible_drift_students", "estimated_engagement_percent", "observations"],
      ...data.windows.map((w) => [w.window_start, w.window_end, w.status, w.connected_students, w.estimated_engaged_students, w.possible_drift_students, w.engagement_percentage, w.observations]),
    ]);
  };

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Analytics</h1>
          <p>Estimated engagement by interval, connection continuity and events for one class.</p>
        </div>
        <div className="spacer" />
        <label className="field" style={{ minWidth: 260 }}>
          <span className="hint">Class</span>
          <select value={classId ?? ""} onChange={(e) => nav(`/analytics/${e.target.value}`)} aria-label="Select class">
            {(classes || []).map((c) => <option key={c.id} value={c.id}>{c.name}{c.status === "ACTIVE" ? " (live)" : ""}</option>)}
          </select>
        </label>
      </div>

      {error && <section className="panel"><div className="empty"><h3>Could not load analytics</h3><p>{error.message}</p></div></section>}
      {!data && loading && <section className="panel"><div className="empty">Loading analytics...</div></section>}

      {data && (
        <>
          <div className="btn-row">
            <strong style={{ fontSize: 16 }}>{data.class.name}</strong>
            <ClassBadge cls={data.class} />
            {data.class.is_demo && <span className="badge sim">Demo data</span>}
            <span className="small muted">{dateTimeOf(data.class.start_time)}{data.class.end_time ? ` to ${timeOf(data.class.end_time, false)}` : ""}</span>
            <div className="spacer" />
            {(data.summary.simulated_devices > 0) && (
              <div className="tabs" aria-label="Filter by data source">
                {[["ALL", "All"], ["REAL", "Real only"], ["SIMULATED", "Simulated only"]].map(([k, l]) => (
                  <button key={k} className={`tab ${source === k ? "on" : ""}`} onClick={() => setSource(k)}>{l}</button>
                ))}
              </div>
            )}
            <button className="btn small" onClick={exportCsv}>Export windows (CSV)</button>
          </div>

          {data.summary.simulated_devices > 0 && (
            <div className="banner sim" style={{ margin: "0 -24px" }}>
              <b>This class includes simulated students</b> ({data.summary.simulated_devices} of {data.summary.total_registered}). Use the source filter to separate real-device data from simulated data.
            </div>
          )}

          <Summary s={data.summary} cls={data.class} />

          <div className="grid-2">
            <section className="panel" style={{ minWidth: 0 }}>
              <div className="panel-head">
                <h2>Estimated engagement by interval</h2>
                <span className="small faint">{data.class.window_seconds >= 120 ? `${Math.round(data.class.window_seconds / 60)}-minute` : `${data.class.window_seconds}-second`} windows</span>
              </div>
              <div className="panel-body"><WindowsChart windows={data.windows} peakIndex={data.peak?.index} /></div>
              {data.peak && (
                <div className="panel-body" style={{ borderTop: "1px solid var(--line)" }}>
                  <strong>Highest estimated engagement: {windowLabel(data.peak)} ({pct(data.peak.engagement_percentage, 1)}).</strong>
                  <div className="small muted">{data.peak.statement}. It describes this class in this interval, not any one student.</div>
                </div>
              )}
            </section>

            <section className="panel" style={{ minWidth: 0 }}>
              <div className="panel-head"><h2>Estimate mix</h2></div>
              <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {(() => {
                  const a = data.summary.attention_distribution || {};
                  const eng = a.ENGAGED || 0;
                  const dr = a.POSSIBLE_ATTENTION_DRIFT || 0;
                  const tot = eng + dr;
                  return tot ? (
                    <>
                      <div style={{ display: "flex", height: 14, borderRadius: 3, overflow: "hidden" }} aria-hidden="true">
                        <i style={{ width: `${(eng / tot) * 100}%`, background: "var(--engaged)" }} />
                        <i style={{ width: `${(dr / tot) * 100}%`, background: "var(--drift)" }} />
                      </div>
                      <div className="stat-line">
                        <div><b>{tot ? ((eng / tot) * 100).toFixed(0) : 0}%</b><span className="muted">{ATTN.ENGAGED}</span></div>
                        <div><b>{tot ? ((dr / tot) * 100).toFixed(0) : 0}%</b><span className="muted">{ATTN.POSSIBLE_ATTENTION_DRIFT}</span></div>
                      </div>
                      <div className="small faint">{tot.toLocaleString()} estimates recorded across all students.</div>
                    </>
                  ) : <div className="muted">No estimates recorded for this selection.</div>;
                })()}
                <div className="small faint">Head movement states reported: {Object.entries(data.summary.motion_distribution || {}).map(([k, v]) => `${k.toLowerCase().replace(/_/g, " ")} ${v}`).join(", ") || "none"}.</div>
              </div>
            </section>
          </div>

          <section className="panel">
            <div className="panel-head"><h2>Interval table</h2></div>
            <div className="panel-body small muted" style={{ borderBottom: "1px solid var(--line)" }}>
              A student counts as <b>mostly engaged</b> in an interval when at least half of their estimates in it were "estimated engaged", otherwise <b>mostly drifting</b> (possible attention drift). Estimated engagement is the average of each student's engaged share.
            </div>
            <div className="table-wrap">
              <table className="tbl">
                <thead>
                  <tr><th>Interval</th><th>Status</th><th className="r">Connected students</th><th className="r">Students mostly engaged</th><th className="r">Students mostly drifting</th><th className="r">Estimated engagement</th><th className="r">Observations</th></tr>
                </thead>
                <tbody>
                  {data.windows.map((w) => (
                    <tr key={w.index} className={data.peak?.index === w.index ? "peak" : ""}>
                      <td className="num">{windowLabel(w)}{data.peak?.index === w.index && <span className="badge ok" style={{ marginLeft: 8 }}>Highest</span>}</td>
                      <td>{STATUS_TEXT[w.status]}</td>
                      <td className="r num">{w.connected_students ?? "-"}</td>
                      <td className="r num">{w.estimated_engaged_students ?? "-"}</td>
                      <td className="r num">{w.possible_drift_students ?? "-"}</td>
                      <td className="r num"><b>{pct(w.engagement_percentage, 1)}</b></td>
                      <td className="r num">{w.observations}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Connection timeline</h2>
              <div className="tabs">
                {[["ALL", "All headbands"], ["GAPS", "Had a disconnection"], ["LATE", "Joined late"]].map(([k, l]) => (
                  <button key={k} className={`tab ${tlFilter === k ? "on" : ""}`} onClick={() => setTlFilter(k)}>{l}</button>
                ))}
              </div>
            </div>
            <div className="panel-body">
              <TimelineChart timeline={timeline} filter={tlFilter} windowSeconds={data.class.window_seconds} />
              <div className="legend" style={{ marginTop: 8 }}>
                <span><i style={{ background: "var(--brand)" }} />Real device connected</span>
                <span><i style={{ background: "#9a86dd" }} />Simulated device connected</span>
                <span><i style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }} />Not connected</span>
              </div>
            </div>
          </section>

          <div className="grid-eq">
            {ev && <EventFeed events={ev.log} limit={200} title="Class events" />}
            <section className="panel">
              <div className="panel-head"><h2>How these numbers are made</h2></div>
              <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <p className="small">{data.methodology}</p>
                <p className="note small">Estimates come from head-movement patterns and, for a single device in dataset-replay mode, EEG-derived features from a recorded public dataset. They do not read minds, prove listening or comprehension, or diagnose anything.</p>
              </div>
            </section>
          </div>
        </>
      )}
    </main>
  );
}
