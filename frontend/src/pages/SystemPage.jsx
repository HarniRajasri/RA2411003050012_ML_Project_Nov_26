import { useFetch } from "../hooks/useFetch.js";
import { api } from "../services/api.js";

const LABELS = {
  heartbeat_interval: ["Heartbeat interval", "seconds between device heartbeats"],
  device_timeout: ["Device timeout", "seconds of silence before a device counts as disconnected"],
  device_stale_after: ["Late heartbeat after", "seconds before the status changes to reconnecting"],
  join_grace_seconds: ["Join grace period", "seconds after start in which joining still counts as 'from start'"],
  motion_threshold: ["Motion threshold", "motion score treated as significant movement"],
  drift_threshold: ["Drift threshold", "estimated score below this is 'possible attention drift'"],
  engagement_window_seconds: ["Default analytics window", "seconds"],
  min_obs_per_window: ["Minimum observations", "per device per window, for it to count"],
  eeg_mode: ["EEG mode", "OFF, DATASET_REPLAY or PHYSICAL_EEG"],
  eeg_replay_file: ["EEG replay file", "features extracted from the recorded dataset"],
  eeg_target_device: ["EEG applied to", "the only device that receives EEG-derived evidence"],
  fusion_w_motion_moving: ["Weight: motion (moving)", "motion vs EEG when the head is moving"],
  fusion_w_eeg_moving: ["Weight: EEG (moving)", ""],
  fusion_w_motion_stable: ["Weight: motion (stable)", "motion vs EEG when the head is still"],
  fusion_w_eeg_stable: ["Weight: EEG (stable)", ""],
};

export default function SystemPage() {
  const { data: health } = useFetch(() => api.health(), [], 5000);
  const { data: settings } = useFetch(() => api.settings(), []);

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>System</h1>
          <p>Status, configuration (read only; edit <span className="mono">.env</span> and restart the backend to change it) and the limits of what this prototype claims.</p>
        </div>
      </div>

      <div className="grid-eq">
        <section className="panel">
          <div className="panel-head"><h2>Status</h2></div>
          <div className="panel-body">
            {health ? (
              <dl className="kv">
                <dt>Backend</dt><dd>{health.backend} (version {health.version})</dd>
                <dt>Database</dt><dd>{health.database}</dd>
                <dt>Dashboard connections</dt><dd>{health.websocket_clients}</dd>
                <dt>Server time</dt><dd>{new Date(health.server_time).toLocaleString()}</dd>
              </dl>
            ) : <p className="muted">Backend not reachable.</p>}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head"><h2>Configuration</h2></div>
          <div className="panel-body flush">
            {settings ? (
              <table className="tbl">
                <tbody>
                  {Object.keys(LABELS).filter((k) => k in settings).map((k) => (
                    <tr key={k}>
                      <td><b>{LABELS[k][0]}</b><div className="small faint">{LABELS[k][1]}</div></td>
                      <td className="mono r">{String(settings[k])}</td>
                    </tr>
                  ))}
                  <tr><td><b>Device key required</b><div className="small faint">optional shared key for headbands</div></td><td className="mono r">{settings.device_api_key_required ? "yes" : "no"}</td></tr>
                </tbody>
              </table>
            ) : <div className="empty">Loading...</div>}
          </div>
        </section>
      </div>

      <div className="grid-eq">
        <section className="panel">
          <div className="panel-head"><h2>What the estimates mean</h2></div>
          <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p>The headband measures head movement with an accelerometer and gyroscope. Movement patterns are turned into an <b>estimated engagement</b> level and a flag for <b>possible attention drift</b>. A student can be still and distracted, or moving and attentive.</p>
            <p>For one device, EEG-derived features from a recorded public dataset can be replayed alongside the movement data (<b>dataset replay, software-in-the-loop</b>). This shows how a real EEG sensor would plug in later. It is not live EEG from anyone in the room.</p>
            <p className="note">Class-level trends are the intended use. The estimates do not read brain activity, prove listening or comprehension, or diagnose anything, and must not be used to grade, discipline or single out a student.</p>
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><h2>Privacy</h2></div>
          <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p>Data stays on this computer, in a local SQLite file. Headbands identify themselves with a device ID, not a name. Student labels are optional and should be avoided in a real classroom.</p>
            <p>Only movement features and state changes are stored. No audio, video, location or personal profile is collected. Students should be told what the headband does and be able to take it off at any time.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
