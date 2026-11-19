import { useNavigate } from "react-router-dom";
import { ClassBadge } from "../components/Badge.jsx";
import { useToast } from "../components/Toast.jsx";
import { useFetch } from "../hooks/useFetch.js";
import { api } from "../services/api.js";
import { dateTimeOf, durationText, pct } from "../services/format.js";

export default function HistoryPage() {
  const toast = useToast();
  const nav = useNavigate();
  const { data, error, reload } = useFetch(() => api.classes(), [], 10000);

  const seed = async () => {
    try {
      const r = await api.seedDemo();
      toast("Sample class added. It is labelled DEMO / SIMULATED.", "ok");
      reload();
      nav(`/analytics/${r.class_id ?? r.id}`);
    } catch (e) {
      toast(e.message, "error");
    }
  };

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Class history</h1>
          <p>Every class recorded on this computer. Select a row to open its analytics.</p>
        </div>
        <div className="spacer" />
        <button className="btn" onClick={seed}>Load sample class</button>
      </div>
      <section className="panel">
        {error ? (
          <div className="empty"><h3>Could not load classes</h3><p>{error.message}</p></div>
        ) : !data || data.length === 0 ? (
          <div className="empty">
            <h3>No classes yet</h3>
            <p>Start a class on the dashboard, or load a sample class to explore the analytics.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr><th>Class</th><th>Started</th><th>Length</th><th className="r">Headbands</th><th className="r">Avg estimated engagement</th><th>Status</th></tr>
              </thead>
              <tbody>
                {data.map((c) => (
                  <tr key={c.id} className="click" tabIndex={0} onClick={() => nav(`/analytics/${c.id}`)} onKeyDown={(e) => e.key === "Enter" && nav(`/analytics/${c.id}`)}>
                    <td><b>{c.name}</b>{c.is_demo && <span className="badge sim" style={{ marginLeft: 8 }}>Demo</span>}</td>
                    <td className="num">{dateTimeOf(c.start_time)}</td>
                    <td className="num">{durationText(c.elapsed_seconds)}</td>
                    <td className="r num">{c.total_registered}</td>
                    <td className="r num">{pct(c.average_engagement_percentage, 1)}</td>
                    <td><ClassBadge cls={c} /></td>
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
