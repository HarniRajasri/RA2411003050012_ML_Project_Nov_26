import { useWidth } from "./useWidth.js";
import { timeOf } from "../services/format.js";

const ROW = 16;
const GAP = 4;
const M = { l: 84, r: 12, t: 24, b: 6 };

/** One row per headband. Bars are the periods the device was connected; empty space is a disconnection. */
export default function TimelineChart({ timeline, filter = "ALL", windowSeconds = 600 }) {
  const [ref, width] = useWidth();
  if (!timeline || !timeline.devices.length) return <div ref={ref} className="empty">No devices connected during this class.</div>;

  const t0 = new Date(timeline.start).getTime();
  const t1 = Math.max(new Date(timeline.end).getTime(), t0 + 60000);
  let rows = timeline.devices;
  if (filter === "GAPS") rows = rows.filter((d) => d.disconnect_count > 0);
  if (filter === "LATE") rows = rows.filter((d) => d.joined_late);
  if (!rows.length) return <div ref={ref} className="empty">No devices match this filter.</div>;

  const iw = width - M.l - M.r;
  const H = M.t + rows.length * (ROW + GAP) + M.b;
  const x = (ms) => M.l + ((ms - t0) / (t1 - t0)) * iw;
  const step = windowSeconds * 1000;
  const ticks = [];
  for (let t = t0; t <= t1 + 1; t += step) ticks.push(t);

  return (
    <div ref={ref} style={{ maxHeight: 460, overflowY: "auto" }}>
      <svg className="chart" width={width} height={H} role="img" aria-label="Device connection timeline">
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={M.t} y2={H - M.b} stroke="var(--line)" />
            <text x={x(t)} y={14} textAnchor={i === 0 ? "start" : i === ticks.length - 1 ? "end" : "middle"}>{timeOf(new Date(t).toISOString(), false)}</text>
          </g>
        ))}
        {rows.map((d, i) => {
          const top = M.t + i * (ROW + GAP);
          const color = d.source === "SIMULATED" ? "#9a86dd" : "var(--brand)";
          return (
            <g key={d.device_id}>
              <text x={M.l - 8} y={top + ROW - 4} textAnchor="end" style={{ fill: "var(--ink-2)" }}>{d.device_id}</text>
              <rect x={M.l} y={top} width={iw} height={ROW} fill="var(--surface-2)" />
              {d.segments.map((s, k) => {
                const a = Math.max(x(new Date(s.start).getTime()), M.l);
                const b = Math.min(x(new Date(s.end).getTime()), M.l + iw);
                return <rect key={k} x={a} y={top} width={Math.max(2, b - a)} height={ROW} fill={color} rx="1.5">
                  <title>{`${d.device_id}: connected ${timeOf(s.start)} to ${timeOf(s.end)}`}</title>
                </rect>;
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
