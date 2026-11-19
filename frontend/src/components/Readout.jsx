import { pct } from "../services/format.js";

/** The headline numbers for the live class, as one instrument band rather than a wall of cards. */
export default function Readout({ metrics }) {
  const on = metrics?.class_active;
  const v = (x) => (on ? x : "-");
  const engagedPct = on && metrics.engagement_percentage !== null ? metrics.engagement_percentage : null;
  return (
    <section className="readout" aria-label="Live class summary">
      <div>
        <div className="v">{v(metrics?.connected)}<small>of {v(metrics?.total_registered)}</small></div>
        <div className="k">Connected now</div>
        <div className="n">peak {v(metrics?.peak_connections)}</div>
      </div>
      <div>
        <div className="v engaged">{v(metrics?.estimated_engaged)}<small>{engagedPct !== null ? pct(engagedPct) : ""}</small></div>
        <div className="k">Estimated engaged</div>
        <div className="n">of students with data</div>
      </div>
      <div>
        <div className="v drift">{v(metrics?.possible_drift)}</div>
        <div className="k">Possible attention drift</div>
        <div className="n">{on && metrics.no_data > 0 ? `${metrics.no_data} without recent data` : "estimate, not a verdict"}</div>
      </div>
      <div>
        <div className="v">{v(metrics?.continuous_from_start)}</div>
        <div className="k">Connected since start</div>
        <div className="n">never dropped out</div>
      </div>
      <div>
        <div className="v">{v(metrics?.disconnected_at_least_once)}</div>
        <div className="k">Disconnected at least once</div>
        <div className="n">may have reconnected</div>
      </div>
      <div>
        <div className="v">{v(metrics?.joined_after_start)}</div>
        <div className="k">Joined after start</div>
        <div className="n">after the grace period</div>
      </div>
    </section>
  );
}
