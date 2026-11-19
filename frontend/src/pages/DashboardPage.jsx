import { Link } from "react-router-dom";
import ClassControl from "../components/ClassControl.jsx";
import Readout from "../components/Readout.jsx";
import StudentGrid from "../components/StudentGrid.jsx";
import EventFeed from "../components/EventFeed.jsx";
import EegPanel from "../components/EegPanel.jsx";
import LiveChart from "../charts/LiveChart.jsx";
import WindowsChart from "../charts/WindowsChart.jsx";
import { useLive } from "../components/LiveContext.jsx";
import { useFetch } from "../hooks/useFetch.js";
import { api } from "../services/api.js";
import { pct } from "../services/format.js";

function WindowsSoFar({ cls }) {
  const { data } = useFetch(() => api.analytics(cls.id), [cls.id], 5000);
  if (!data) return null;
  const minutes = Math.round(cls.window_seconds / 60);
  const label = cls.window_seconds >= 120 ? `${minutes}-minute windows` : `${cls.window_seconds}-second windows`;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Engagement by interval</h2>
        <span className="small faint">{label}</span>
        {data.peak && <span className="badge ok">Highest so far {pct(data.peak.engagement_percentage)}</span>}
      </div>
      <div className="panel-body"><WindowsChart windows={data.windows} peakIndex={data.peak?.index} /></div>
    </section>
  );
}

export default function DashboardPage() {
  const { snapshot, events, history } = useLive();
  const cls = snapshot?.class || null;
  const metrics = snapshot?.metrics;
  const devices = snapshot?.devices || [];

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Live dashboard</h1>
          <p>Estimated engagement of the connected class. Values are estimates from head movement (and, for one device, replayed EEG-derived features), not a measure of what any student is thinking.</p>
        </div>
      </div>

      <ClassControl cls={cls} />
      <Readout metrics={metrics} />

      <div className="grid-2">
        <div style={{ display: "flex", flexDirection: "column", gap: 20, minWidth: 0 }}>
          <section className="panel">
            <div className="panel-head">
              <h2>Estimated engagement over time</h2>
              <span className="small faint">share of students with data who are estimated engaged</span>
            </div>
            <div className="panel-body">
              {cls ? <LiveChart history={history} /> : (
                <div className="empty">
                  <h3>Start a class to see the live chart</h3>
                  <p>Or review a finished class in <Link to="/analytics">Analytics</Link>.</p>
                </div>
              )}
            </div>
          </section>
          {cls && <WindowsSoFar cls={cls} />}
          <StudentGrid devices={devices} classActive={!!cls} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20, minWidth: 0 }}>
          <EegPanel eeg={snapshot?.eeg} />
          <EventFeed events={events} />
        </div>
      </div>
    </main>
  );
}
